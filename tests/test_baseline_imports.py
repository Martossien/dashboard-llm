"""Phase 1 — Baseline import and app creation tests.

Verifie que le package est importable et que la factory Flask fonctionne.
"""
import pytest


class TestPackageImport:
    """Le package doit etre importable sans erreur."""

    def test_import_llm_dashboard(self):
        import llm_dashboard
        assert llm_dashboard.__version__

    def test_import_config(self):
        from llm_dashboard import config
        assert hasattr(config, "load_config")
        assert hasattr(config, "DEFAULT_CONFIG")
        assert hasattr(config, "validate_config")

    def test_import_web_app(self):
        from llm_dashboard.web.app import create_app
        assert callable(create_app)

    def test_import_models(self):
        from llm_dashboard.models import ServiceConfig, normalize_services_config
        assert ServiceConfig
        assert callable(normalize_services_config)

    def test_import_registry(self):
        from llm_dashboard.services.registry import ServiceRegistry
        assert ServiceRegistry

    def test_import_commands(self):
        from llm_dashboard.services.commands import CommandRunner, CommandResult
        assert CommandRunner
        assert CommandResult

    def test_import_health(self):
        import llm_dashboard.services.health
        assert hasattr(llm_dashboard.services.health, "check_service_health")
        assert hasattr(llm_dashboard.services.health, "check_port_is_open")

    def test_import_detection(self):
        import llm_dashboard.services.detection
        assert hasattr(llm_dashboard.services.detection, "get_services_status")

    def test_import_system(self):
        from llm_dashboard.monitors.system import get_cpu_info, get_ram_info
        assert callable(get_cpu_info)
        assert callable(get_ram_info)

    def test_import_gpu_monitor(self):
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor
        assert GPUMonitor

    def test_import_gpu_base(self):
        from llm_dashboard.monitors.gpu.base import AbstractGPUBackend, GPUDevice
        assert AbstractGPUBackend
        assert GPUDevice

    def test_import_gpu_factory(self):
        from llm_dashboard.monitors.gpu.factory import get_gpu_backend
        assert callable(get_gpu_backend)

    def test_import_nogpu_backend(self):
        from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
        assert NoGPUBackend

    def test_import_admin_api(self):
        from llm_dashboard.web.admin_api import AdminAPIRoutes
        assert AdminAPIRoutes

    def test_import_admin_auth(self):
        from llm_dashboard.web.admin_auth import AdminAuthRoutes
        assert AdminAuthRoutes

    def test_import_admin_panel(self):
        from llm_dashboard.web.admin_panel import AdminPanelRoute
        assert AdminPanelRoute

    def test_import_dashboard_api(self):
        from llm_dashboard.web.dashboard_api import DashboardAPIRoute
        assert DashboardAPIRoute

    def test_import_control(self):
        from llm_dashboard.services.control import ServiceController, ControlResult
        assert ServiceController
        assert ControlResult


class TestAppFactoryMinimal:
    """Tests de creation d'application Flask via create_app() (sans monitor.py)."""

    def test_create_app_with_minimal_config(self, minimal_config_dict):
        from llm_dashboard.web.app import create_app
        from flask import Flask

        app = create_app(minimal_config_dict)
        assert isinstance(app, Flask)
        assert app.secret_key is not None

    def test_create_app_registers_health(self, minimal_config_dict):
        from llm_dashboard.web.app import create_app

        app = create_app(minimal_config_dict)
        with app.test_client() as client:
            resp = client.get('/health')
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

    def test_create_app_registers_root(self, minimal_config_dict):
        from llm_dashboard.web.app import create_app

        app = create_app(minimal_config_dict)
        with app.test_client() as client:
            resp = client.get('/')
            assert resp.status_code == 200
            content = resp.data.decode('utf-8')
            assert 'dashboard' in content.lower()
