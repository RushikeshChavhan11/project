from datetime import date, datetime

from quicktracker.extensions import db
from quicktracker.models import Attendance, Student
from quicktracker.routes import _mark_present, _safe_csv_cell


def test_unauthenticated_user_is_redirected_to_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]



def test_unauthenticated_api_returns_json_401(client):
    response = client.post("/api/attendance/recognize", json={"subject": "Test", "image": ""})
    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()["ok"] is False

def test_login_opens_dashboard(authenticated_client):
    response = authenticated_client.get("/dashboard")
    assert response.status_code == 200
    assert b"QuiickTracker" in response.data


def test_malformed_json_returns_client_error(authenticated_client):
    response = authenticated_client.post(
        "/api/attendance/recognize",
        data="[]",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_recognition_rejects_non_text_json_fields(authenticated_client):
    response = authenticated_client.post(
        "/api/attendance/recognize",
        json={"subject": 123, "image": ["not", "text"]},
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_recognition_requires_a_trained_gallery(authenticated_client):
    response = authenticated_client.post(
        "/api/attendance/recognize",
        json={"subject": "Software Engineering", "image": "data:image/jpeg;base64,AA=="},
    )
    assert response.status_code == 400
    assert "No trained face embeddings" in response.get_json()["message"]


def test_duplicate_attendance_is_blocked(app):
    with app.app_context():
        student = Student(
            student_id="TEST-001",
            name="Test Student",
            course_name="MCA",
            year="First Year",
        )
        db.session.add(student)
        db.session.commit()

        first_status, first_record = _mark_present(student, "Computer Vision", 0.81)
        second_status, second_record = _mark_present(student, "Computer Vision", 0.90)

        assert first_status == "marked"
        assert second_status == "already"
        assert first_record.id == second_record.id
        assert Attendance.query.count() == 1


def test_csv_export_escapes_formula_cells(authenticated_client, app):
    with app.app_context():
        student = Student(
            student_id="TEST-002",
            name="=2+2",
            course_name="MCA",
            year="Second Year",
        )
        db.session.add(student)
        db.session.flush()
        db.session.add(
            Attendance(
                student_id=student.id,
                subject="@SUM(A1:A2)",
                session_date=date.today(),
                captured_at=datetime.now(),
                similarity=0.81,
                status="Present",
            )
        )
        db.session.commit()

    response = authenticated_client.get("/reports/attendance.csv")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert "'=2+2" in body
    assert "'@SUM(A1:A2)" in body


def test_pdf_export_returns_a_pdf(authenticated_client, app):
    with app.app_context():
        student = Student(
            student_id="TEST-003",
            name="PDF Test",
            course_name="MCA",
            year="Second Year",
        )
        db.session.add(student)
        db.session.flush()
        db.session.add(
            Attendance(
                student_id=student.id,
                subject="Database Systems",
                session_date=date.today(),
                captured_at=datetime.now(),
                similarity=0.77,
                status="Present",
            )
        )
        db.session.commit()

    response = authenticated_client.get("/reports/attendance.pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")


def test_csv_formula_escape_helper():
    assert _safe_csv_cell("normal text") == "normal text"
    assert _safe_csv_cell("=1+1") == "'=1+1"
    assert _safe_csv_cell("  @cmd") == "'  @cmd"



def test_admin_pages_render(authenticated_client):
    paths = [
        "/dashboard",
        "/students",
        "/students/new",
        "/train",
        "/attendance/capture",
        "/attendance",
        "/analytics",
    ]
    for path in paths:
        response = authenticated_client.get(path)
        assert response.status_code == 200, path



def test_invalid_date_filters_do_not_crash_or_return_unfiltered_records(authenticated_client, app):
    with app.app_context():
        student = Student(
            student_id="DATE-001",
            name="Date Filter Test",
            course_name="MCA",
            year="First Year",
        )
        db.session.add(student)
        db.session.flush()
        db.session.add(
            Attendance(
                student_id=student.id,
                subject="Testing",
                session_date=date.today(),
                captured_at=datetime.now(),
                similarity=0.8,
                status="Present",
            )
        )
        db.session.commit()

    response = authenticated_client.get("/attendance?date_from=2026-99-99&date_to=2026-10-01")
    assert response.status_code == 200
    assert b"No matching records" in response.data


def test_reversed_date_filters_do_not_return_unfiltered_records(authenticated_client, app):
    with app.app_context():
        student = Student(
            student_id="DATE-002",
            name="Date Filter Test 2",
            course_name="MCA",
            year="First Year",
        )
        db.session.add(student)
        db.session.flush()
        db.session.add(
            Attendance(
                student_id=student.id,
                subject="Testing",
                session_date=date.today(),
                captured_at=datetime.now(),
                similarity=0.8,
                status="Present",
            )
        )
        db.session.commit()

    response = authenticated_client.get("/attendance?date_from=2026-11-01&date_to=2026-10-01")
    assert response.status_code == 200
    assert b"No matching records" in response.data


def test_login_rejects_external_redirect(app):
    client = app.test_client()
    response = client.post(
        "/login?next=//example.com/steal-session",
        data={"username": "test-admin", "password": "a-secure-test-password"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_analytics_export_link_preserves_filters_and_chart_date_range(authenticated_client):
    response = authenticated_client.get(
        "/analytics?subject=Computer+Vision&course=MCA&year=Second+Year"
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "subject=Computer+Vision" in page
    assert "course=MCA" in page
    assert "year=Second+Year" in page
    assert "date_from=" in page
    assert "date_to=" in page
