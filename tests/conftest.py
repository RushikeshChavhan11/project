from pathlib import Path

import pytest

from quicktracker import create_app
from quicktracker.extensions import db
from quicktracker.models import User


@pytest.fixture()
def app(tmp_path: Path):
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret-key",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.sqlite3'}",
            "UPLOAD_FOLDER": tmp_path / "uploads",
            "MODEL_DIR": tmp_path / "models",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        db.create_all()
        admin = User(username="test-admin")
        admin.set_password("a-secure-test-password")
        db.session.add(admin)
        db.session.commit()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def authenticated_client(client):
    response = client.post(
        "/login",
        data={"username": "test-admin", "password": "a-secure-test-password"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    return client
