"""Фабрика Flask-приложения."""

from flask import Flask

from app.config import Config
from app.services.vacancy_sources.trudvsem import TrudvsemSource


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.extensions["vacancy_source"] = TrudvsemSource(
        timeout=app.config["VACANCY_API_TIMEOUT"],
        cache_ttl=app.config["VACANCY_CACHE_TTL"],
    )

    from app.routes import bp

    app.register_blueprint(bp)
    return app
