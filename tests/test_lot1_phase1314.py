"""Phase 1.3 + 1.4 — Tests compatibilite monitor.py et CSRF admin.

Verifie que monitor.py reste fonctionnel et que le durcissement CSRF
des routes admin POST fonctionne correctement.
"""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


# ============================================================================
# Phase 1.3 — Compatibilite monitor.py
# ============================================================================

class TestMonitorCompat:
    """Tests de compatibilite monitor.py."""

    def test_import_monitor_works(self):
        """import monitor doit fonctionner avec mocks GPU."""
        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.monitor.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            # Force reload to avoid cached import
            import monitor
            import importlib
            importlib.reload(monitor)

            assert hasattr(monitor, "app")
            assert hasattr(monitor, "CONFIG")
            assert monitor.app is not None
            assert isinstance(monitor.CONFIG, dict)

    def test_monitor_exposes_legacy_exports(self):
        """Les re-exports legacy fonctionnent toujours."""
        from llm_dashboard.services.detection import join_url
        assert callable(join_url)
        assert join_url("http://x:8080", "/health") == "http://x:8080/health"

        from llm_dashboard.config import parse_bool
        assert parse_bool("true") is True

        from llm_dashboard.monitors.logs import tail_log_lines
        assert callable(tail_log_lines)

        from llm_dashboard.monitors.logs import read_journalctl_logs
        assert callable(read_journalctl_logs)

    def test_monitor_can_be_run_directly(self):
        """python monitor.py reste conceptuellement possible (mocke)."""
        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.monitor.get_gpu_backend") as mock_gpu, \
             patch("flask.Flask.run") as mock_run:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            import monitor
            import importlib
            importlib.reload(monitor)

            # Simuler __main__ execution
            monitor.app.run(host="127.0.0.1", port=5000, debug=False)
            mock_run.assert_called_once()


# ============================================================================
# Phase 1.4 — CSRF admin POST
# ============================================================================

class TestCSRFProtection:
    """Tests du durcissement CSRF sur les routes admin POST."""

    @pytest.fixture
    def csrf_app(self):
        """App avec CSRF active."""
        from llm_dashboard.web.admin_api import AdminAPIRoutes

        app = Flask(__name__)
        app.secret_key = "test"
        app.config["TESTING"] = True

        config = {
            "admin": {
                "enabled": True,
                "csrf_enabled": True,
                "csrf_header": "X-CSRF-Token",
            },
            "services": {},
            "start_stop": {},
        }

        AdminAPIRoutes(
            config,
            is_admin_authenticated=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True, "message": "ok"},
            do_stop_service=lambda k: {"success": True, "message": "ok"},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
        ).register(app)

        return app, config

    @pytest.fixture
    def csrf_disabled_app(self):
        """App avec CSRF desactivee (defaut)."""
        from llm_dashboard.web.admin_api import AdminAPIRoutes

        app = Flask(__name__)
        app.secret_key = "test"
        app.config["TESTING"] = True

        config = {
            "admin": {"enabled": True, "csrf_enabled": False},
            "services": {},
            "start_stop": {},
        }

        AdminAPIRoutes(
            config,
            is_admin_authenticated=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True, "message": "ok"},
            do_stop_service=lambda k: {"success": True, "message": "ok"},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
        ).register(app)

        return app, config

    def test_csrf_disabled_allows_post(self, csrf_disabled_app):
        """Sans CSRF, les POST admin fonctionnent normalement."""
        app, _ = csrf_disabled_app
        with app.test_client() as client:
            resp = client.post('/api/admin/start', json={"service": "test"})
            assert resp.status_code == 200

    def test_csrf_enabled_rejects_without_token(self, csrf_app):
        """Avec CSRF active, sans token → 403."""
        app, _ = csrf_app
        with app.test_client() as client:
            resp = client.post('/api/admin/start', json={"service": "test"})
            assert resp.status_code == 403
            assert resp.get_json()["error"] == "csrf_failed"

    def test_csrf_enabled_accepts_with_valid_token(self, csrf_app):
        """Avec CSRF active et token valide → 200."""
        app, _ = csrf_app
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["csrf_token"] = "test-token-123"

            resp = client.post(
                '/api/admin/start',
                json={"service": "test"},
                headers={"X-CSRF-Token": "test-token-123"},
            )
            assert resp.status_code == 200

    def test_csrf_enabled_rejects_wrong_token(self, csrf_app):
        """Avec CSRF active et mauvais token → 403."""
        app, _ = csrf_app
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["csrf_token"] = "correct-token"

            resp = client.post(
                '/api/admin/start',
                json={"service": "test"},
                headers={"X-CSRF-Token": "wrong-token"},
            )
            assert resp.status_code == 403

    def test_csrf_applies_to_all_post_routes(self, csrf_app):
        """CSRF protege tous les endpoints POST admin."""
        app, _ = csrf_app
        routes = [
            '/api/admin/start',
            '/api/admin/stop',
            '/api/admin/restart',
            '/api/admin/force_stop',
            '/api/admin/stop_all_llm',
        ]
        with app.test_client() as client:
            for route in routes:
                resp = client.post(route, json={"service": "test"})
                assert resp.status_code == 403, f"CSRF missing on {route}"

    def test_csrf_does_not_block_get_routes(self, csrf_app):
        """CSRF ne bloque pas les routes GET admin."""
        app, _ = csrf_app
        with app.test_client() as client:
            resp = client.get('/api/admin/status')
            assert resp.status_code == 200

            resp = client.get('/api/admin/vram')
            assert resp.status_code == 200
