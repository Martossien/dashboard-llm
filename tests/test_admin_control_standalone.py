"""Phase 2 — Tests d'import sans monitor.py et instanciation avec mocks.

Verifie que les modules clefs sont importables sans monitor.py
et que les classes principales peuvent etre instanciees avec des mocks.
"""
import pytest
from unittest.mock import MagicMock


class TestImportWithoutMonitor:
    """Les modules doivent etre importables sans importer monitor.py au prealable."""

    def test_admin_auth_importable_standalone(self):
        """admin_auth.py ne contient plus de references non definies a CONFIG."""
        from llm_dashboard.web.admin_auth import AdminAuthRoutes
        assert AdminAuthRoutes

    def test_control_importable_standalone(self):
        """control.py ne contient plus de fonctions orphelines."""
        from llm_dashboard.services.control import ServiceController, ControlResult
        assert ServiceController
        assert ControlResult


class TestClassInstantiation:
    """Les classes principales doivent etre instanciables avec des mocks."""

    def test_admin_auth_routes_instantiation(self):
        from llm_dashboard.web.admin_auth import AdminAuthRoutes
        config = {"admin": {"enabled": True, "password_hash": "pbkdf2:sha256:0$test$test"}}
        instance = AdminAuthRoutes(config, lambda: True, lambda p: True)
        assert isinstance(instance, AdminAuthRoutes)

    def test_admin_api_routes_instantiation(self):
        from llm_dashboard.web.admin_api import AdminAPIRoutes
        config = {"admin": {"enabled": True}, "services": {}, "start_stop": {}}
        instance = AdminAPIRoutes(
            config,
            is_admin_authenticated=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True, "message": "ok"},
            do_stop_service=lambda k: {"success": True, "message": "ok"},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": r.success, "message": r.message},
        )
        assert isinstance(instance, AdminAPIRoutes)

    def test_admin_panel_route_instantiation(self):
        from llm_dashboard.web.admin_panel import AdminPanelRoute
        config = {"services": {}}
        instance = AdminPanelRoute(
            config,
            is_admin_authenticated=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
        )
        assert isinstance(instance, AdminPanelRoute)

    def test_dashboard_api_route_instantiation(self):
        from llm_dashboard.web.dashboard_api import DashboardAPIRoute
        config = {
            "services": {
                "ik_llama_cpp": {"name": "ik_llama.cpp"},
                "llama_cpp": {"name": "llama.cpp"},
                "vllm": {"name": "vLLM"},
            }
        }
        instance = DashboardAPIRoute(
            config,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None},
            get_llama_startup_state=lambda s: {"state": "DOWN"},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            get_logs=lambda: {},
            get_client_ips=lambda: [],
            detect_model_name=lambda: "Unknown",
            find_ik_llama_process=lambda: None,
            find_llama_process=lambda: None,
        )
        assert isinstance(instance, DashboardAPIRoute)

    def test_service_controller_instantiation(self):
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.services.registry import ServiceRegistry
        registry = ServiceRegistry([])
        runner = MagicMock()
        ctrl = ServiceController(registry, runner)
        assert isinstance(ctrl, ServiceController)
        assert ctrl.registry is registry
        assert ctrl.allow_force_stop is False

    def test_service_controller_with_force_stop_enabled(self):
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.services.registry import ServiceRegistry
        ctrl = ServiceController(ServiceRegistry([]), MagicMock(), allow_force_stop=True)
        assert ctrl.allow_force_stop is True
