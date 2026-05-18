from __future__ import annotations

from flask import Flask

from app.config import Config


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)

    # Register blueprints
    from app.routes import bp as api_bp

    app.register_blueprint(api_bp)

    return app
