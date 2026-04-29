"""Web blueprint — routes simples (/, /help, /health).

Pas d'import depuis monitor.py. Les dependances (CONFIG, render_template, jsonify)
sont injectees via le constructeur de la factory.
"""

from flask import render_template, jsonify


class WebRoutes:
    """Routes web simples du dashboard, sans logique metier."""

    def __init__(self, config: dict):
        """Initialise avec une config (CONFIG dict).

        Args:
            config: dictionnaire de configuration complet du dashboard.
        """
        self.config = config

    def register(self, app):
        """Enregistre les routes sur l'application Flask."""
        config = self.config

        @app.route('/')
        def index():
            return render_template(
                'dashboard.html',
                refresh_interval_ms=config["monitoring"]["refresh_interval_ms"],
                vram_warning_percent=config["thresholds"]["vram_warning_percent"],
                vram_danger_percent=config["thresholds"]["vram_danger_percent"],
                power_warning_percent=config["thresholds"]["power_warning_percent"],
                power_danger_percent=config["thresholds"]["power_danger_percent"],
            )

        @app.route('/health')
        def health():
            return jsonify({'status': 'ok', 'service': 'dashboard-llm'}), 200

        @app.route('/help')
        def help_page():
            return render_template('help.html')
