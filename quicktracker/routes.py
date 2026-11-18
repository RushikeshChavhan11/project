from __future__ import annotations

import base64
import binascii
import csv
import io
import json
import logging
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import cv2
from flask import (
    Blueprint, current_app, flash, jsonify, make_response, redirect,
    render_template, request, send_file, send_from_directory, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .face_engine import FaceEngine, FaceEngineError, cosine_similarity
from .models import Attendance, FaceEmbedding, Student, StudentImage, User

bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)


def _local_now() -> datetime:
    timezone = ZoneInfo(current_app.config.get("TIMEZONE", "Asia/Kolkata"))
    return datetime.now(timezone).replace(tzinfo=None)


def _local_today() -> date:
    return _local_now().date()


def get_face_engine() -> FaceEngine:
    """Return one reusable face engine per Flask application instance."""
    engine = current_app.extensions.get("quicktracker_face_engine")
    if engine is None:
        engine = FaceEngine(
            current_app.config["MODEL_DIR"],
            detection_threshold=current_app.config["FACE_DETECTION_THRESHOLD"],
        )
        current_app.extensions["quicktracker_face_engine"] = engine
    return engine


def _valid_extension(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def _decode_uploaded_image(uploaded_file) -> bytes:
    if not uploaded_file or not uploaded_file.filename:
        raise ValueError("Choose an image file.")
    if not _valid_extension(uploaded_file.filename):
        raise ValueError("Use JPG, JPEG, PNG, or WEBP image files only.")
    data = uploaded_file.read()
    uploaded_file.stream.seek(0)
    if len(data) > current_app.config["MAX_IMAGE_BYTES"]:
        raise ValueError("Each image must be 5 MB or smaller.")
    try:
        image = FaceEngine.decode_image(data)
        height, width = image.shape[:2]
        if width > 4096 or height > 4096:
            raise ValueError("Image dimensions must not exceed 4096 pixels on either side.")
        try:
            ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        except cv2.error as exc:
            raise ValueError("Could not process the uploaded image.") from exc
        if not ok:
            raise ValueError("Could not process the uploaded image.")
        return encoded.tobytes()
    except FaceEngineError as exc:
        raise ValueError(str(exc)) from exc


def _attendance_query():
    query = Attendance.query.join(Student)
    subject = request.args.get("subject", "").strip()
    course = request.args.get("course", "").strip()
    year = request.args.get("year", "").strip()
    student_id = request.args.get("student_id", "").strip()
    start = request.args.get("date_from", "").strip()
    end = request.args.get("date_to", "").strip()

    if subject:
        query = query.filter(Attendance.subject.ilike(f"%{subject}%"))
    if course:
        query = query.filter(Student.course_name.ilike(f"%{course}%"))
    if year:
        query = query.filter(Student.year == year)
    if student_id:
        query = query.filter(Student.student_id.ilike(f"%{student_id}%"))
    try:
        start_date = date.fromisoformat(start) if start else None
        end_date = date.fromisoformat(end) if end else None
        if (start_date and start_date.isoformat() != start) or (end_date and end_date.isoformat() != end):
            raise ValueError("Use the YYYY-MM-DD date format.")
        if start_date and end_date and start_date > end_date:
            flash("The start date cannot be later than the end date.", "warning")
            query = query.filter(False)
        else:
            if start_date:
                query = query.filter(Attendance.session_date >= start_date)
            if end_date:
                query = query.filter(Attendance.session_date <= end_date)
    except ValueError:
        flash("Date filters must use YYYY-MM-DD format.", "warning")
        query = query.filter(False)
    return query.order_by(Attendance.session_date.desc(), Attendance.captured_at.desc())



def _safe_csv_cell(value):
    """Neutralize spreadsheet formula prefixes in untrusted exported text."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _attendance_rows():
    rows = _attendance_query().all()
    return [
        {
            "student_id": row.student.student_id,
            "name": row.student.name,
            "course": row.student.course_name,
            "year": row.student.year,
            "subject": row.subject,
            "date": row.session_date.isoformat(),
            "time": row.captured_at.strftime("%H:%M:%S"),
            "similarity": f"{row.similarity:.3f}",
            "status": row.status,
        }
        for row in rows
    ]


def _best_student_match(vector: list[float]):
    best_student = None
    best_score = -1.0
    for gallery_item in FaceEmbedding.query.all():
        try:
            candidate = gallery_item.vector_json
            score = cosine_similarity(vector, candidate)
        except (TypeError, ValueError, json.JSONDecodeError):
            logger.exception("Skipping invalid embedding row %s", gallery_item.id)
            continue
        if score > best_score:
            best_student = gallery_item.student
            best_score = score
    return best_student, best_score


def _mark_present(student: Student, subject: str, similarity: float):
    today = _local_today()
    existing = Attendance.query.filter_by(
        student_id=student.id, subject=subject, session_date=today
    ).first()
    if existing:
        return "already", existing

    record = Attendance(
        student_id=student.id,
        subject=subject,
        session_date=today,
        captured_at=_local_now(),
        similarity=float(similarity),
        status="Present",
    )
    db.session.add(record)
    try:
        db.session.commit()
        return "marked", record
    except IntegrityError:
        db.session.rollback()
        existing = Attendance.query.filter_by(
            student_id=student.id, subject=subject, session_date=today
        ).first()
        return "already", existing


@bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get("remember") == "on")
            next_url = request.args.get("next", "")
            # Accept only a relative path on this host. Backslashes and control
            # characters are rejected because browsers may normalize them.
            parsed_next = urlsplit(next_url)
            if (
                next_url.startswith("/")
                and not next_url.startswith("//")
                and not parsed_next.scheme
                and not parsed_next.netloc
                and "\\" not in next_url
                and not any(character in next_url for character in ("\r", "\n"))
            ):
                return redirect(next_url)
            return redirect(url_for("main.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("main.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    today = _local_today()
    student_count = Student.query.count()
    today_count = Attendance.query.filter_by(session_date=today).count()
    trained_count = FaceEmbedding.query.count()
    recent = Attendance.query.order_by(Attendance.captured_at.desc()).limit(8).all()
    return render_template(
        "dashboard.html",
        student_count=student_count,
        today_count=today_count,
        trained_count=trained_count,
        recent=recent,
        today=today,
    )


@bp.route("/students")
@login_required
def students():
    search = request.args.get("q", "").strip()
    query = Student.query
    if search:
        query = query.filter(
            or_(
                Student.student_id.ilike(f"%{search}%"),
                Student.name.ilike(f"%{search}%"),
                Student.course_name.ilike(f"%{search}%"),
            )
        )
    records = query.order_by(Student.created_at.desc()).all()
    return render_template("students.html", students=records, search=search)


@bp.route("/students/new", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()
        course_name = request.form.get("course_name", "").strip()
        year = request.form.get("year", "").strip()
        images = [item for item in request.files.getlist("images") if item and item.filename]

        if not all([student_id, name, course_name, year]):
            flash("Student ID, name, course, and year are required.", "warning")
            return render_template("student_form.html")
        if len(student_id) > 50 or len(name) > 120 or len(course_name) > 100 or len(year) > 30:
            flash("One or more fields exceed the allowed length.", "warning")
            return render_template("student_form.html")
        if Student.query.filter_by(student_id=student_id).first():
            flash("A student with that ID already exists.", "warning")
            return render_template("student_form.html")
        if request.form.get("consent") != "yes":
            flash("Confirm that the student data is collected with informed consent and institutional authorization.", "warning")
            return render_template("student_form.html")
        if not images:
            flash("Capture or select at least one face image. Five varied images are recommended.", "warning")
            return render_template("student_form.html")
        max_images = current_app.config["MAX_IMAGES_PER_STUDENT"]
        if len(images) > max_images:
            flash(f"Upload no more than {max_images} images for one student.", "warning")
            return render_template("student_form.html")

        try:
            image_bytes = [_decode_uploaded_image(image) for image in images]
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("student_form.html")

        student = Student(
            student_id=student_id,
            name=name,
            course_name=course_name,
            year=year,
        )
        student_folder = None
        try:
            db.session.add(student)
            db.session.flush()
            student_folder = Path(current_app.config["UPLOAD_FOLDER"]) / str(student.id)
            student_folder.mkdir(parents=True, exist_ok=True)
            for data in image_bytes:
                filename = f"{uuid.uuid4().hex}.jpg"
                target = student_folder / filename
                target.write_bytes(data)
                db.session.add(
                    StudentImage(student_id=student.id, image_path=f"{student.id}/{filename}")
                )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            if student_folder is not None:
                shutil.rmtree(student_folder, ignore_errors=True)
            flash("A student with that ID already exists. Refresh the page and try again.", "warning")
            return render_template("student_form.html")
        except Exception:
            db.session.rollback()
            if student_folder is not None:
                shutil.rmtree(student_folder, ignore_errors=True)
            logger.exception("Student registration failed")
            flash("Could not save the student. Please try again.", "danger")
            return render_template("student_form.html")

        flash(
            f"{student.name} was registered with {len(image_bytes)} image(s). Run Train Images to build the recognition gallery.",
            "success",
        )
        return redirect(url_for("main.students"))

    return render_template("student_form.html")


@bp.route("/students/<int:student_pk>/delete", methods=["POST"])
@login_required
def delete_student(student_pk):
    student = Student.query.get_or_404(student_pk)
    folder = Path(current_app.config["UPLOAD_FOLDER"]) / str(student.id)
    db.session.delete(student)
    db.session.commit()
    shutil.rmtree(folder, ignore_errors=True)
    flash(f"Student {student.student_id} and associated records were deleted.", "success")
    return redirect(url_for("main.students"))


@bp.route("/train", methods=["GET", "POST"])
@login_required
def train_images():
    engine = get_face_engine()
    if request.method == "POST":
        if not engine.ready:
            flash("Face models are not installed. Follow the model setup instructions below.", "warning")
            return redirect(url_for("main.train_images"))

        students_list = Student.query.order_by(Student.student_id).all()
        trained = 0
        skipped = []
        for student in students_list:
            vectors = []
            for image in student.images:
                image_path = Path(current_app.config["UPLOAD_FOLDER"]) / image.image_path
                try:
                    vectors.append(engine.extract_largest(image_path.read_bytes()))
                except (OSError, FaceEngineError) as exc:
                    skipped.append(f"{student.student_id}: {exc}")
            if not vectors:
                stale_embedding = FaceEmbedding.query.filter_by(student_id=student.id).first()
                if stale_embedding is not None:
                    db.session.delete(stale_embedding)
                skipped.append(f"{student.student_id}: no usable face images")
                continue
            average = np.mean(np.asarray(vectors, dtype=np.float32), axis=0)
            norm = float(np.linalg.norm(average))
            if norm <= 1e-12:
                stale_embedding = FaceEmbedding.query.filter_by(student_id=student.id).first()
                if stale_embedding is not None:
                    db.session.delete(stale_embedding)
                skipped.append(f"{student.student_id}: embedding could not be normalized")
                continue
            average = (average / norm).astype(float).tolist()
            embedding = FaceEmbedding.query.filter_by(student_id=student.id).first()
            if embedding is None:
                embedding = FaceEmbedding(student_id=student.id)
                db.session.add(embedding)
            embedding.vector_json = average
            embedding.sample_count = len(vectors)
            embedding.model_name = "OpenCV SFace (YuNet detector)"
            embedding.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            trained += 1

        db.session.commit()
        message = f"Embedding gallery updated for {trained} student(s)."
        if skipped:
            message += f" {len(skipped)} image/student issue(s) were skipped; review the details below."
            flash("\n".join(skipped[:8]), "warning")
        flash(message, "success" if trained else "warning")
        return redirect(url_for("main.train_images"))

    return render_template(
        "train.html",
        student_count=Student.query.count(),
        trained_count=FaceEmbedding.query.count(),
        image_count=StudentImage.query.count(),
        missing_models=engine.missing_models,
    )


@bp.route("/attendance/capture")
@login_required
def capture_attendance():
    subjects = [row[0] for row in db.session.query(Attendance.subject).distinct().order_by(Attendance.subject).all()]
    return render_template("capture_attendance.html", subjects=subjects)


@bp.route("/api/attendance/recognize", methods=["POST"])
@login_required
def recognize_attendance():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "message": "The request body must be a JSON object."}), 400
    subject_value = payload.get("subject")
    image_value = payload.get("image")
    if not isinstance(subject_value, str) or not isinstance(image_value, str):
        return jsonify({"ok": False, "message": "Subject and image must be text values."}), 400
    subject = subject_value.strip()
    image_data = image_value
    if not subject or len(subject) > 100:
        return jsonify({"ok": False, "message": "Enter a valid subject name (max 100 characters)."}), 400
    if not image_data.startswith("data:image/") or "," not in image_data:
        return jsonify({"ok": False, "message": "Capture an image before marking attendance."}), 400
    try:
        encoded = image_data.split(",", 1)[1]
        max_encoded_size = ((current_app.config["MAX_IMAGE_BYTES"] + 2) // 3) * 4
        if len(encoded) > max_encoded_size:
            return jsonify({"ok": False, "message": "Captured image is too large."}), 413
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return jsonify({"ok": False, "message": "The captured image data is invalid."}), 400
    if len(raw) > current_app.config["MAX_IMAGE_BYTES"]:
        return jsonify({"ok": False, "message": "Captured image is too large."}), 413
    if FaceEmbedding.query.count() == 0:
        return jsonify({"ok": False, "message": "No trained face embeddings are available. Register students and train images first."}), 400

    try:
        detected = get_face_engine().extract_all(raw)
        threshold = current_app.config["FACE_MATCH_THRESHOLD"]
        outcomes = []
        seen_students = set()
        for face in detected:
            student, score = _best_student_match(face["embedding"])
            if student is None or score < threshold:
                outcomes.append({"status": "unknown", "message": "Student not in database", "similarity": round(score, 3)})
                continue
            if student.id in seen_students:
                continue
            seen_students.add(student.id)
            status, _record = _mark_present(student, subject, score)
            outcomes.append(
                {
                    "status": status,
                    "student_id": student.student_id,
                    "name": student.name,
                    "similarity": round(score, 3),
                    "message": "Attendance captured" if status == "marked" else "Already marked for this subject today",
                }
            )
        return jsonify({"ok": True, "detected_faces": len(detected), "results": outcomes})
    except FaceEngineError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception:
        logger.exception("Attendance recognition failed")
        return jsonify({"ok": False, "message": "Recognition failed. Check the server log and model setup."}), 500


@bp.route("/attendance")
@login_required
def attendance():
    records = _attendance_query().limit(500).all()
    courses = [row[0] for row in db.session.query(Student.course_name).distinct().order_by(Student.course_name).all()]
    years = [row[0] for row in db.session.query(Student.year).distinct().order_by(Student.year).all()]
    return render_template(
        "attendance.html", records=records, courses=courses, years=years,
        filters=request.args,
    )


@bp.route("/reports/attendance.csv")
@login_required
def export_csv():
    rows = _attendance_rows()
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["student_id", "name", "course", "year", "subject", "date", "time", "similarity", "status"],
    )
    writer.writeheader()
    writer.writerows([{key: _safe_csv_cell(value) for key, value in row.items()} for row in rows])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=quicktracker_attendance.csv"
    return response


@bp.route("/reports/attendance.pdf")
@login_required
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    rows = _attendance_rows()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    elements = [Paragraph("QuiickTracker - Attendance Report", styles["Title"]), Spacer(1, 12)]
    table_data = [["Student ID", "Name", "Course", "Year", "Subject", "Date", "Time", "Score", "Status"]]
    table_data.extend([
        [r["student_id"], r["name"], r["course"], r["year"], r["subject"], r["date"], r["time"], r["similarity"], r["status"]]
        for r in rows
    ])
    if len(table_data) == 1:
        table_data.append(["No records match the selected filters.", "", "", "", "", "", "", "", ""])
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6f4a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d6ded9")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="quicktracker_attendance.pdf")


@bp.route("/analytics")
@login_required
def analytics():
    end_date = _local_today()
    start_date = end_date - timedelta(days=13)
    subject = request.args.get("subject", "").strip()
    year = request.args.get("year", "").strip()
    course = request.args.get("course", "").strip()

    query = Attendance.query.join(Student).filter(
        Attendance.session_date >= start_date,
        Attendance.session_date <= end_date,
    )
    if subject:
        query = query.filter(Attendance.subject == subject)
    if year:
        query = query.filter(Student.year == year)
    if course:
        query = query.filter(Student.course_name == course)

    grouped = (
        query.with_entities(Attendance.session_date, func.count(Attendance.id))
        .group_by(Attendance.session_date)
        .order_by(Attendance.session_date)
        .all()
    )
    counts = {day: count for day, count in grouped}
    days = [start_date + timedelta(days=i) for i in range(14)]
    values = [counts.get(day, 0) for day in days]
    total_records = sum(values)
    students_query = Student.query
    if year:
        students_query = students_query.filter(Student.year == year)
    if course:
        students_query = students_query.filter(Student.course_name == course)
    total_students = students_query.count()
    average = (total_records / len([v for v in values if v > 0])) if any(values) else 0

    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=130)
    ax.plot([d.strftime("%d %b") for d in days], values, marker="o", linewidth=2)
    ax.set_title("Daily attendance")
    ax.set_ylabel("Students marked present")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.25)
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    image_buffer = io.BytesIO()
    fig.savefig(image_buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    chart = base64.b64encode(image_buffer.getvalue()).decode("ascii")

    subjects = [row[0] for row in db.session.query(Attendance.subject).distinct().order_by(Attendance.subject).all()]
    years = [row[0] for row in db.session.query(Student.year).distinct().order_by(Student.year).all()]
    courses = [row[0] for row in db.session.query(Student.course_name).distinct().order_by(Student.course_name).all()]
    return render_template(
        "analytics.html", chart=chart, days=days, values=values,
        total_records=total_records, total_students=total_students,
        average=average, subjects=subjects, years=years, courses=courses,
        selected_subject=subject, selected_year=year, selected_course=course,
        start_date=start_date, end_date=end_date,
    )


@bp.route("/media/<path:filename>")
@login_required
def private_media(filename):
    response = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
    response.headers["Cache-Control"] = "private, no-store"
    return response


@bp.app_errorhandler(404)
def not_found(_error):
    if not current_user.is_authenticated:
        return redirect(url_for("main.login"))
    return render_template("404.html"), 404


@bp.app_errorhandler(413)
def file_too_large(_error):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "message": "The uploaded content exceeds the application limit."}), 413
    flash("The uploaded content exceeds the application limit.", "danger")
    return redirect(url_for("main.dashboard" if current_user.is_authenticated else "main.login"))
