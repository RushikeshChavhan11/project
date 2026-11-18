from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, url_for
from flask_wtf.csrf import CSRFError
from flask_login import current_user

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")  # Load the project-local .env before Config reads variables.

from .config import Config
from .extensions import csrf, db, login_manager


@login_manager.user_loader
def load_user(user_id):
    from .models import User

    return db.session.get(User, int(user_id))


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["MODEL_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.unauthorized_handler
    def handle_unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "message": "Please sign in again to continue."}), 401
        return redirect(url_for("main.login", next=request.full_path))

    from . import models  # noqa: F401
    from .routes import bp

    app.register_blueprint(bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        from flask import flash, redirect, request, url_for

        if request.path.startswith("/api/"):
            from flask import jsonify

            return jsonify({"ok": False, "message": "Your session expired. Refresh the page and try again."}), 400
        flash("Your session expired. Please try again.", "warning")
        return redirect(url_for("main.dashboard" if current_user.is_authenticated else "main.login"))

    with app.app_context():
        db.create_all()

    @app.cli.command("init-db")
    def init_db_command():
        """Create database tables."""
        db.create_all()
        click.echo("QuiickTracker database tables are ready.")

    @app.cli.command("create-admin")
    def create_admin_command():
        """Create an administrator account interactively."""
        from .models import User

        username = click.prompt("Admin username").strip()
        password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)
        if len(username) < 3 or len(password) < 10:
            raise click.ClickException("Use a username of at least 3 characters and a password of at least 10 characters.")
        if User.query.filter_by(username=username).first():
            raise click.ClickException("That username already exists.")
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator '{username}' created.")

    @app.context_processor
    def inject_app_settings():
        return {"app_name": "QuiickTracker", "threshold": app.config["FACE_MATCH_THRESHOLD"]}

    return app
