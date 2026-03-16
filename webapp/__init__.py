import logging
import os

from flask import Flask

from .config import Config
from .db.database import ensure_database
from .routes import goals_bp, imports_bp, pages_bp, stats_bp, tours_bp


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_TMP_DIR"], exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app.logger.setLevel(logging.INFO)

    ensure_database()

    app.register_blueprint(pages_bp)
    app.register_blueprint(imports_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(tours_bp)
    app.register_blueprint(stats_bp)

    return app