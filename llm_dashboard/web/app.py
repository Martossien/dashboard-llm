"""
Flask application factory.

Cree et configure l'application Flask du dashboard.
Pas d'import depuis monitor.py — toutes les dependances sont injectees.
"""

import logging
import os
import secrets

from flask import Flask

from llm_dashboard.web.routes import WebRoutes


def create_app(config: dict, *, template_folder: str | None = None) -> Flask:
    """Cree l'application Flask configuree.

    Args:
        config: dictionnaire de configuration complet (equivalent a CONFIG).
        template_folder: chemin optionnel vers le dossier de templates.

    Returns:
        Application Flask prete a recevoir des routes.
    """
    if template_folder is None:
        template_folder = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates',
        )
    static_folder = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'static',
    )
    app = Flask(__name__, template_folder=template_folder,
                static_folder=static_folder)

    # Session
    session_secret = config.get("admin", {}).get("session_secret")
    if not session_secret:
        session_secret = secrets.token_hex(32)
        logging.getLogger("dashboard-llm").warning(
            "No admin.session_secret configured — using random secret "
            "(sessions will not survive restart)"
        )
    app.secret_key = session_secret
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Werkzeug logging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # Routes web simples
    web = WebRoutes(config)
    web.register(app)

    return app
