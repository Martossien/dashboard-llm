"""
Admin auth routes — /admin, /admin/login, /admin/logout.

Pas d'import depuis monitor.py. Les helpers is_admin_authenticated()
et check_admin_password() sont injectes via le constructeur.
"""

import logging
import secrets

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

    def __init__(self, config: dict, is_admin_authenticated, check_admin_password, logger_=None):
        """Initialise avec les dependances de monitor.py.

        Args:
            config: dictionnaire CONFIG complet.
            is_admin_authenticated: fonction () -> bool.
            check_admin_password: fonction (password: str) -> bool.
            logger_: logger optionnel injecte par l'application.
        """
        self._config = config
        self._login_required = is_admin_authenticated
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
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for('admin_panel'))
            password = request.form.get('password', '')
            client_ip = request.remote_addr or "unknown"
            if check_password(password):
                route_logger.info("Admin login successful from %s", client_ip)
                session["admin_logged_in"] = True
                session["csrf_token"] = secrets.token_urlsafe(32)
                return redirect(url_for('admin_panel'))
            route_logger.warning(
                "Admin login FAILED from %s — password length: %d",
                client_ip, len(password),
            )
            return render_template('login.html', error="Mot de passe incorrect.")

        @app.route('/admin/logout')
        def admin_logout():
            session.pop("admin_logged_in", None)
            session.pop("csrf_token", None)
            return redirect(url_for('index'))


