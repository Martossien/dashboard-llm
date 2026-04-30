"""Phase 2+3 — Tests API publique + admin GPU process config."""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


class TestPublicGPUProcessAPIConfig:
    def test_enabled_false_returns_payload(self):
        from llm_dashboard.web.metrics import register_public_api
        app = Flask(__name__)
        register_public_api(app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"gpu_processes": {"enable": False}},
            get_gpu_processes=lambda: [{"pid": 1, "vram_mib": 100}],
        )
        with app.test_client() as client:
            resp = client.get('/api/v1/gpus/processes')
            data = resp.get_json()
            assert data["enabled"] is False
            assert data["processes"] == []
            assert data["count"] == 0
            assert data["total_vram_mib"] == 0

    def test_show_command_false_masks(self):
        from llm_dashboard.web.metrics import register_public_api
        app = Flask(__name__)
        register_public_api(app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"gpu_processes": {"enable": True, "show_command": False}},
            get_gpu_processes=lambda: [{"pid": 1, "command": "secret"}],
        )
        with app.test_client() as client:
            resp = client.get('/api/v1/gpus/processes')
            data = resp.get_json()
            assert data["enabled"] is True
            assert data["processes"][0]["command"] is None

    def test_max_processes_limits(self):
        from llm_dashboard.web.metrics import register_public_api
        app = Flask(__name__)
        processes = [{"pid": i, "used_vram_mib": 100 - i} for i in range(10)]
        register_public_api(app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"gpu_processes": {"enable": True, "max_processes": 3}},
            get_gpu_processes=lambda: processes,
        )
        with app.test_client() as client:
            resp = client.get('/api/v1/gpus/processes')
            data = resp.get_json()
            assert len(data["processes"]) == 3

    def test_sort_before_max(self):
        """Les plus gros consommateurs VRAM doivent être retournés quand max_processes limite."""
        from llm_dashboard.web.metrics import register_public_api
        app = Flask(__name__)
        # Unsorted: 100, 900, 500
        processes = [
            {"pid": 1, "used_vram_mib": 100},
            {"pid": 2, "used_vram_mib": 900},
            {"pid": 3, "used_vram_mib": 500},
        ]
        register_public_api(app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"gpu_processes": {"enable": True, "max_processes": 2}},
            get_gpu_processes=lambda: processes,
        )
        with app.test_client() as client:
            resp = client.get('/api/v1/gpus/processes')
            data = resp.get_json()
            assert len(data["processes"]) == 2
            # Must be the top 2 by VRAM: 900 and 500, not 100 and 900
            vrams = [p["used_vram_mib"] for p in data["processes"]]
            assert vrams == [900, 500], f"Expected [900, 500] got {vrams}"

    def test_alias_same_as_canonical(self):
        from llm_dashboard.web.metrics import register_public_api
        app = Flask(__name__)
        register_public_api(app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"gpu_processes": {"enable": True}},
            get_gpu_processes=lambda: [{"pid": 1, "used_vram_mib": 100}],
        )
        with app.test_client() as client:
            r1 = client.get('/api/v1/gpus/processes').get_json()
            r2 = client.get('/api/v1/gpu/processes').get_json()
            assert r1 == r2


class TestAdminGPUProcessAPI:
    def test_unauthenticated_returns_401(self):
        from llm_dashboard.web.admin_api import AdminAPIRoutes
        app = Flask(__name__)
        app.secret_key = "test"
        AdminAPIRoutes(
            config={"admin": {"enabled": True}, "services": {}, "start_stop": {}},
            admin_login_required=lambda: False,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True},
            do_stop_service=lambda k: {"success": True},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
            get_gpu_processes=lambda: [],
        ).register(app)
        with app.test_client() as client:
            resp = client.get('/api/admin/gpu/processes')
            assert resp.status_code == 401

    def test_authenticated_returns_stable_payload(self):
        from llm_dashboard.web.admin_api import AdminAPIRoutes
        app = Flask(__name__)
        app.secret_key = "test"
        AdminAPIRoutes(
            config={"admin": {"enabled": True}, "gpu_processes": {"enable": True},
                    "services": {}, "start_stop": {}},
            admin_login_required=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True},
            do_stop_service=lambda k: {"success": True},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
            get_gpu_processes=lambda: [],
        ).register(app)
        with app.test_client() as client:
            resp = client.get('/api/admin/gpu/processes')
            data = resp.get_json()
            assert "processes" in data
            assert "count" in data
            assert "total_vram_mib" in data
            assert "enabled" in data

    def test_admin_max_processes_sorted(self):
        """Admin endpoint must sort before applying max_processes."""
        from llm_dashboard.web.admin_api import AdminAPIRoutes
        app = Flask(__name__)
        app.secret_key = "test"
        AdminAPIRoutes(
            config={"admin": {"enabled": True}, "gpu_processes": {"enable": True, "max_processes": 2},
                    "services": {}, "start_stop": {}},
            admin_login_required=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True},
            do_stop_service=lambda k: {"success": True},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
            get_gpu_processes=lambda: [
                {"pid": 1, "used_vram_mib": 100},
                {"pid": 2, "used_vram_mib": 900},
                {"pid": 3, "used_vram_mib": 500},
            ],
        ).register(app)
        with app.test_client() as client:
            resp = client.get('/api/admin/gpu/processes')
            data = resp.get_json()
            assert data["count"] == 2
            vrams = [p["used_vram_mib"] for p in data["processes"]]
            assert vrams == [900, 500], f"Expected [900, 500] got {vrams}"
