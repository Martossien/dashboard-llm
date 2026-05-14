"""LOT 2 — Tests du GPU Process Viewer.

Verifie les nouveaux endpoints /api/v1/gpu/processes et /api/admin/gpu/processes.
"""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


class TestGPUPprocessPublic:
    """Tests de l'endpoint public /api/v1/gpu/processes."""

    def test_returns_process_list_when_available(self):
        from llm_dashboard.web.metrics import register_public_api

        app = Flask(__name__)
        mock_processes = [
            {"pid": 1234, "name": "llama-server", "vram_mib": 8000.0},
            {"pid": 5678, "name": "python", "vram_mib": 2500.0},
        ]

        with patch("psutil.process_iter", return_value=[]):
            register_public_api(
                app,
                get_cpu_info=lambda: {"load": 0},
                get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
                get_gpu_info=lambda: [],
                get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
                detect_model_name=lambda: "unknown",
                get_logs=lambda: {},
                get_llama_timings=lambda: (None, None),
                get_vllm_timings=lambda: (None, None),
                config={"services": {}},
                get_gpu_processes=lambda: mock_processes,
            )

            with app.test_client() as client:
                resp = client.get('/api/v1/gpu/processes')
                assert resp.status_code == 200
                data = resp.get_json()
                assert "processes" in data
                assert "total_vram_mib" in data
                assert data["total_vram_mib"] == 10500.0
                assert len(data["processes"]) == 2

    def test_returns_empty_when_no_processes(self):
        from llm_dashboard.web.metrics import register_public_api

        app = Flask(__name__)
        register_public_api(
            app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"services": {}},
            get_gpu_processes=lambda: [],
        )

        with app.test_client() as client:
            resp = client.get('/api/v1/gpu/processes')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["processes"] == []
            assert data["total_vram_mib"] == 0

    def test_returns_empty_when_callback_is_none(self):
        from llm_dashboard.web.metrics import register_public_api

        app = Flask(__name__)
        register_public_api(
            app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"services": {}},
            get_gpu_processes=None,
        )

        with app.test_client() as client:
            resp = client.get('/api/v1/gpu/processes')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["processes"] == []
            assert data["total_vram_mib"] == 0

    def test_handles_exception_gracefully(self):
        from llm_dashboard.web.metrics import register_public_api

        app = Flask(__name__)
        register_public_api(
            app,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
            detect_model_name=lambda: "unknown",
            get_logs=lambda: {},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            config={"services": {}},
            get_gpu_processes=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        with app.test_client() as client:
            resp = client.get('/api/v1/gpu/processes')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["processes"] == []

    def test_sorted_by_vram_desc(self):
        from llm_dashboard.web.metrics import register_public_api

        app = Flask(__name__)
        mock_processes = [
            {"pid": 1, "name": "small", "vram_mib": 100.0},
            {"pid": 2, "name": "big", "vram_mib": 9000.0},
            {"pid": 3, "name": "medium", "vram_mib": 500.0},
        ]

        with patch("psutil.process_iter", return_value=[]):
            register_public_api(
                app,
                get_cpu_info=lambda: {"load": 0},
                get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
                get_gpu_info=lambda: [],
                get_services_status=lambda: {"services": {}, "active_on_8080": None, "model_on_8080": None},
                detect_model_name=lambda: "unknown",
                get_logs=lambda: {},
                get_llama_timings=lambda: (None, None),
                get_vllm_timings=lambda: (None, None),
                config={"services": {}},
                get_gpu_processes=lambda: mock_processes,
            )

            with app.test_client() as client:
                resp = client.get('/api/v1/gpu/processes')
                data = resp.get_json()
                # Must be sorted descending by VRAM
                vrams = [p["vram_mib"] for p in data["processes"]]
                assert vrams == [9000.0, 500.0, 100.0]


class TestGPUProcessAdmin:
    """Tests de l'endpoint admin /api/admin/gpu/processes."""

    def test_returns_processes_when_authenticated(self):
        from llm_dashboard.web.admin_api import AdminAPIRoutes

        app = Flask(__name__)
        app.secret_key = "test"
        app.config["TESTING"] = True

        mock_processes = [{"pid": 1234, "name": "test", "vram_mib": 500.0}]

        AdminAPIRoutes(
            config={"admin": {"enabled": True}, "services": {}, "start_stop": {}},
            is_admin_authenticated=lambda: True,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True},
            do_stop_service=lambda k: {"success": True},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
            get_gpu_processes=lambda: mock_processes,
        ).register(app)

        with app.test_client() as client:
            resp = client.get('/api/admin/gpu/processes')
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["processes"]) == 1
            assert data["processes"][0]["pid"] == 1234

    def test_requires_auth(self):
        from llm_dashboard.web.admin_api import AdminAPIRoutes

        app = Flask(__name__)
        app.secret_key = "test"
        app.config["TESTING"] = True

        AdminAPIRoutes(
            config={"admin": {"enabled": True}, "services": {}, "start_stop": {}},
            is_admin_authenticated=lambda: False,
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
