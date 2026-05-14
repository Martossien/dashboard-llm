"""
Config panel route — /admin/config.
"""

from flask import redirect, render_template, url_for, session


class ConfigPanelRoute:
    def __init__(self, config, admin_login_required, logger=None):
        self._config = config
        self._login = admin_login_required

    def register(self, app):
        config = self._config
        login = self._login

        @app.route("/admin/config")
        def admin_config():
            if not login():
                return redirect(url_for("admin_login_page"))
            return render_template(
                "config.html",
                csrf_token=session.get("csrf_token", ""),
                csrf_header=config.get("admin", {}).get("csrf_header", "X-CSRF-Token"),
                dashboard_port=config["server"]["port"],
            )