from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utc_now_naive() -> datetime:
    """Return the current UTC time as a naive value for existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    year = db.Column(db.String(30), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

    images = db.relationship(
        "StudentImage", back_populates="student", cascade="all, delete-orphan"
    )
    embeddings = db.relationship(
        "FaceEmbedding", back_populates="student", cascade="all, delete-orphan"
    )
    attendance_records = db.relationship(
        "Attendance", back_populates="student", cascade="all, delete-orphan"
    )


class StudentImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    image_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

    student = db.relationship("Student", back_populates="images")


class FaceEmbedding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, unique=True, index=True)
    vector_json = db.Column(db.JSON, nullable=False)
    sample_count = db.Column(db.Integer, default=0, nullable=False)
    model_name = db.Column(db.String(80), default="OpenCV SFace", nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

    student = db.relationship("Student", back_populates="embeddings")


class Attendance(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "subject", "session_date", name="uq_attendance_student_subject_day"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, index=True)
    subject = db.Column(db.String(100), nullable=False, index=True)
    session_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    captured_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    similarity = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Present", nullable=False)

    student = db.relationship("Student", back_populates="attendance_records")
