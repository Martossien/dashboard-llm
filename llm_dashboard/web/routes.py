"""Web blueprint — routes simples (/, /help, /health).

Pas d'import depuis monitor.py. Les dependances (CONFIG, render_template, jsonify)
sont injectees via le constructeur de la factory.
"""

from flask import render_template, jsonify


class WebRoutes:
    """Routes web simples du dashboard, sans logique metier."""

    def __init__(self, config: dict):
        self.config = config

    def register(self, app):
        config = self.config

        @app.route('/')
        def index():
            service_keys = list(config.get("services", {}).keys())
            return render_template(
                'dashboard.html',
                refresh_interval_ms=config["monitoring"]["refresh_interval_ms"],
                vram_warning_percent=config["thresholds"]["vram_warning_percent"],
                vram_danger_percent=config["thresholds"]["vram_danger_percent"],
                power_warning_percent=config["thresholds"]["power_warning_percent"],
                power_danger_percent=config["thresholds"]["power_danger_percent"],
                service_keys=service_keys,
            )

        @app.route('/health')
        def health():
            return jsonify({'status': 'ok', 'service': 'dashboard-llm'}), 200

        @app.route('/help')
        def help_page():
            return render_template(
                'help.html',
                dashboard_port=config["server"]["port"],
            )