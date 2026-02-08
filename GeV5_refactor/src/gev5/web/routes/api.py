"""Routes API / Web à terme.

Pour l'instant, l'application legacy continue d'utiliser api_flsk.py.
Ce module servira de point d'entrée propre pour les nouvelles routes Flask.
"""
from flask import Blueprint, Flask

bp = Blueprint("api", __name__)

def init_app(app: Flask) -> None:
    app.register_blueprint(bp)
