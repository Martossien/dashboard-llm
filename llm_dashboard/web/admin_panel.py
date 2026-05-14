"""
Admin panel route — /admin/panel.

Pas d'import depuis monitor.py. Toutes les dependances sont injectees.
"""

import logging

from flask import redirect, render_template, url_for, session


class AdminPanelRoute:
    """Route du panneau d'administration (/admin/panel)."""

    def __init__(self, config: dict, is_admin_authenticated, get_admin_services_status,
                 get_vram_status, get_logs, logger=None):
        self._config = config
        self._login_required = is_admin_authenticated
        self._get_services = get_admin_services_status
        self._get_vram = get_vram_status
        self._get_logs = get_logs
        self._logger = logger or logging.getLogger("dashboard-llm")

    def register(self, app):
        config = self._config
        login_required = self._login_required
        get_services = self._get_services
        get_vram = self._get_vram
        get_logs = self._get_logs
        logger = self._logger

        @app.route('/admin/panel')
        def admin_panel():
            if not login_required():
                return redirect(url_for('admin_login_page'))
            services_status = get_services()
            vram = get_vram()
            try:
                service_logs = get_logs()
            except Exception as exc:
                service_logs = {}
                logger.error("get_logs failed in admin_panel: %s", exc)
            return render_template(
                'admin.html',
                services=services_status,
                vram=vram,
                service_logs=service_logs,
                service_order=list(config["services"].keys()),
                service_names={k: v["name"] for k, v in config["services"].items()},
                csrf_token=session.get("csrf_token", ""),
                csrf_header=config.get("admin", {}).get("csrf_header", "X-CSRF-Token"),
            )
