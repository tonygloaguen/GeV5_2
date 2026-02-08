"""Création de l'application Flask (interface Web GeV5)."""
from flask import Flask
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    # Enregistrement des blueprints / routes (à créer progressivement)
    try:
        from .routes import api  # type: ignore
        api.init_app(app)
    except Exception:
        # Pas encore de routes refactorisées : ce n'est pas bloquant.
        pass

    return app
