import os
import secrets
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_ROOT = PACKAGE_ROOT / "instance"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(48)
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL")
        or f"sqlite:///{(INSTANCE_ROOT / 'quicktracker.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = INSTANCE_ROOT / "uploads"
    _model_dir = Path(os.getenv("MODEL_DIR", "models")).expanduser()
    MODEL_DIR = _model_dir if _model_dir.is_absolute() else PACKAGE_ROOT / _model_dir
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
    FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.363"))
    FACE_DETECTION_THRESHOLD = float(os.getenv("FACE_DETECTION_THRESHOLD", "0.90"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH_MB", "30")) * 1024 * 1024
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_IMAGES_PER_STUDENT = 5
    ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 8
