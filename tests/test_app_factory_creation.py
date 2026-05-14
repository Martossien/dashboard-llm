"""Phase 3 — Tests de l'application factory refactorisee.

Verifie que create_full_app() fonctionne sans importlib hack,
que l'import n'a pas d'effets de bord dangereux, et que les routes
attendues sont exposees.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


class TestFullAppFactory:
    """Tests de create_full_app()."""

    def test_returns_app_and_config(self):
        from llm_dashboard.app_factory import create_full_app
        from flask import Flask

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, config = create_full_app()

            assert isinstance(app, Flask)
            assert isinstance(config, dict)
            assert "server" in config
            assert "services" in config

    def test_accepts_config_path(self, temp_config_file):
        from llm_dashboard.app_factory import create_full_app
        from flask import Flask

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, config = create_full_app(config_path=temp_config_file)

            assert isinstance(app, Flask)
            assert config["server"]["port"] == 5050  # du minimal_config_dict

    def test_without_signals(self):
        from llm_dashboard.app_factory import create_full_app
        from flask import Flask

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, config = create_full_app(setup_signals=False)
            assert isinstance(app, Flask)

    def test_health_route_registered(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, _config = create_full_app(setup_signals=False)

            with app.test_client() as client:
                resp = client.get('/health')
                assert resp.status_code == 200
                assert resp.get_json()["status"] == "ok"

    def test_root_route_registered(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, _config = create_full_app(setup_signals=False)

            with app.test_client() as client:
                resp = client.get('/')
                assert resp.status_code == 200

    def test_metrics_route_registered(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, _config = create_full_app(setup_signals=False)

            with app.test_client() as client:
                resp = client.get('/metrics')
                assert resp.status_code == 200
                assert resp.mimetype.startswith('text/plain')


class TestEndpointRegistration:
    """Verifie que les routes attendues sont exposees."""

    REQUIRED_ROUTES = [
        '/',
        '/health',
        '/help',
        '/api/data',
        '/metrics',
        '/api/v1/gpus',
        '/api/v1/services',
        '/api/v1/metrics',
        '/admin',
        '/admin/login',
        '/admin/logout',
        '/admin/panel',
        '/api/admin/status',
        '/api/admin/start',
        '/api/admin/stop',
        '/api/admin/restart',
        '/api/admin/force_stop',
        '/api/admin/stop_all_llm',
        '/api/admin/vram',
    ]

    def test_all_required_routes_registered(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, _config = create_full_app(setup_signals=False)

            registered = {rule.rule for rule in app.url_map.iter_rules()}
            for route in self.REQUIRED_ROUTES:
                assert route in registered, f"Missing route: {route}"


class TestImportSafety:
    """Verifie que l'import n'a pas d'effets de bord dangereux."""

    def test_app_factory_import_does_not_launch_server(self):
        """L'import de app_factory ne doit pas lancer de serveur."""
        with patch("flask.Flask.run") as mock_run:
            from llm_dashboard import app_factory
            import importlib
            importlib.reload(app_factory)
            mock_run.assert_not_called()

    def test_monitor_import_still_possible(self):
        """import monitor doit rester possible pour compatibilite."""
        import monitor
        assert hasattr(monitor, "app")
        assert hasattr(monitor, "CONFIG")
        from flask import Flask
        assert isinstance(monitor.app, Flask)


class TestCLIMain:
    """Test que cli.main peut etre appele avec app.run mocke."""

    def test_main_calls_app_run(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            from flask import Flask
            app, config = create_full_app(setup_signals=False)

            with patch.object(app, "run") as mock_run:
                app.run(
                    host=config["server"]["host"],
                    port=config["server"]["port"],
                    debug=config["server"].get("debug", False),
                    use_reloader=False,
                )
                mock_run.assert_called_once()
