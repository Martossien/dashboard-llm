"""
Admin auth routes — /admin, /admin/login, /admin/logout.

Pas d'import depuis monitor.py. Les helpers admin_login_required()
et check_admin_password() sont injectes via le constructeur.
"""

import logging

from flask import (
    redirect,
    render_template,
    request,
    session,
    url_for,
)

logger = logging.getLogger("dashboard-llm")


class AdminAuthRoutes:
    """Routes d'authentification admin (login/logout)."""

    def __init__(self, config: dict, admin_login_required, check_admin_password, logger_=None):
        """Initialise avec les dependances de monitor.py.

        Args:
            config: dictionnaire CONFIG complet.
            admin_login_required: fonction () -> bool.
            check_admin_password: fonction (password: str) -> bool.
            logger_: logger optionnel injecte par l'application.
        """
        self._config = config
        self._login_required = admin_login_required
        self._check_password = check_admin_password
        self._logger = logger_ or logger

    def register(self, app):
        """Enregistre les routes sur l'application Flask."""
        config = self._config
        login_required = self._login_required
        check_password = self._check_password
        route_logger = self._logger

        @app.route('/admin')
        def admin_login_page():
            if config.get("admin", {}).get("enabled", True) is False:
                return redirect(url_for('admin_panel'))
            if login_required():
                return redirect(url_for('admin_panel'))
            return render_template('login.html')

        @app.route('/admin/login', methods=['POST'])
        def admin_login():
            if config.get("admin", {}).get("enabled", True) is False:
                session["admin_logged_in"] = True
                return redirect(url_for('admin_panel'))
            password = request.form.get('password', '')
            client_ip = request.remote_addr or "unknown"
            if check_password(password):
                route_logger.info("Admin login successful from %s", client_ip)
                session["admin_logged_in"] = True
                return redirect(url_for('admin_panel'))
            route_logger.warning(
                "Admin login FAILED from %s — password length: %d",
                client_ip, len(password),
            )
            return render_template('login.html', error="Mot de passe incorrect.")

        @app.route('/admin/logout')
        def admin_logout():
            session.pop("admin_logged_in", None)
            return redirect(url_for('index'))


def admin_login_required():
    """Retourne True si l'utilisateur est connecte."""
    if not CONFIG.get("admin", {}).get("enabled", True):
        return True
    return session.get("admin_logged_in") is True

def check_admin_password(password):
    """Verifie le mot de passe admin contre le hash configure."""
    default_hash = "pbkdf2:sha256:260000$ndkvw7ryKFNx99Am$b8f6b66a2f536fa1010bb72c3b7c48cb4b8e82c7a05be16401cc37ca2a95f90c"
    expected_hash = CONFIG.get("admin", {}).get("password_hash", default_hash)
    import werkzeug.security
    if not expected_hash.startswith("pbkdf2:"):
        logger.warning("admin.password_hash is not a pbkdf2 hash — refusing plaintext comparison. Run /opt/dashboard-llm/change_admin_password.py to set a proper hash.")
        return False
    return werkzeug.security.check_password_hash(expected_hash, str(password))