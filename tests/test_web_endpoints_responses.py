"""Phase 5 — Tests de regression des routes Flask avec Flask test_client.

Toutes les routes publique et admin sont testees avec des mocks,
sans aucun appel systeme ou reseau reel.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


def _make_app(with_admin=True):
    """Cree une app Flask minimale avec toutes les routes enregistrees."""
    from llm_dashboard.web.app import create_app
    from llm_dashboard.web.admin_auth import AdminAuthRoutes
    from llm_dashboard.web.admin_panel import AdminPanelRoute
    from llm_dashboard.web.dashboard_api import DashboardAPIRoute

    config = {
        "server": {"host": "127.0.0.1", "port": 5050, "debug": False},
        "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
        "services": {
            "ik_llama_cpp": {"name": "ik_llama.cpp"},
            "llama_cpp": {"name": "llama.cpp"},
            "vllm": {"name": "vLLM"},
            "ollama": {"name": "Ollama"},
            "voxtral": {"name": "Voxtral TTS"},
            "voxtral_stt": {"name": "Voxtral STT"},
        },
        "gpu": {"enable": False},
        "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                       "power_warning_percent": 70, "power_danger_percent": 90},
        "admin": {"enabled": True,
                   "password_hash": "pbkdf2:sha256:260000$test$test",
                   "session_secret": "test-secret"},
    }
    app = create_app(config)
    app.config["TESTING"] = True
    return app, config


def _register_dashboard_api(app, config):
    from llm_dashboard.web.dashboard_api import DashboardAPIRoute
    DashboardAPIRoute(
        config,
        get_cpu_info=lambda: {"load": 50.0},
        get_ram_info=lambda: {"used": 16.0, "total": 32.0, "percent": 50.0},
        get_gpu_info=lambda: [],
        get_services_status=lambda: {
            "services": {
                "ik_llama.cpp": "UP",
                "llama.cpp": "DOWN",
                "vLLM": "DOWN",
                "Ollama": "DOWN",
                "Voxtral TTS": "DOWN",
                "Voxtral STT": "DOWN",
            },
            "llama_latency_seconds": 0.5,
            "slots_active": 1,
            "slots_total": 4,
            "active_on_8080": "ik_llama_cpp",
            "model_on_8080": "glm-4.7-iq5",
        },
        get_llama_startup_state=lambda status: {
            "state": "READY", "loading_seconds": None,
            "eta_seconds": None, "avg_seconds": None,
        },
        get_llama_timings=lambda: (10.0, 20.0),
        get_vllm_timings=lambda: (None, None),
        get_logs=lambda: {},
        get_client_ips=lambda: ["192.168.1.100"],
        detect_model_name=lambda: "glm-4.7-iq5",
    ).register(app)


def _register_admin_routes(app, config, logged_in=True):
    from llm_dashboard.web.admin_auth import AdminAuthRoutes
    from llm_dashboard.web.admin_panel import AdminPanelRoute
    from llm_dashboard.web.admin_api import AdminAPIRoutes
    from llm_dashboard.services.control import ControlResult

    AdminAuthRoutes(
        config,
        is_admin_authenticated=lambda: logged_in,
        check_admin_password=lambda p: p == "secret",
    ).register(app)

    AdminPanelRoute(
        config,
        is_admin_authenticated=lambda: logged_in,
        get_admin_services_status=lambda: {
            "test_service": {"key": "test_service", "display_name": "Test",
                            "running": True, "is_llm": False, "port": 1234}
        },
        get_vram_status=lambda: {"enabled": False},
        get_logs=lambda: {},
    ).register(app)

    AdminAPIRoutes(
        config,
        is_admin_authenticated=lambda: logged_in,
        get_admin_services_status=lambda: {
            "test_service": {"key": "test_service", "display_name": "Test",
                            "running": True, "is_llm": False, "port": 1234}
        },
        get_vram_status=lambda: {"enabled": False},
        get_logs=lambda: {},
        do_start_service=lambda key: {"success": True, "message": f"started {key}"},
        do_stop_service=lambda key: {"success": True, "message": f"stopped {key}"},
        stop_all_llm_engines=lambda: [{"key": "svc", "status": "stopped"}],
        _init_controller=lambda: MagicMock(force_stop_service=lambda key: ControlResult(key, True, "killed")),
        _control_result_to_dict=lambda r: {"success": r.success, "message": r.message},
    ).register(app)


def _register_public_api(app, config):
    from llm_dashboard.web.metrics import register_public_api
    register_public_api(
        app,
        get_cpu_info=lambda: {"load": 50.0},
        get_ram_info=lambda: {"used": 16.0, "total": 32.0, "percent": 50.0},
        get_gpu_info=lambda: [],
        get_services_status=lambda: {
            "services": {"svc": "UP"},
            "active_services": {},
            "models_by_group": {},
        },
        detect_model_name=lambda: "test-model",
        get_logs=lambda: {},
        get_llama_timings=lambda: (None, None),
        get_vllm_timings=lambda: (None, None),
        config=config,
    )


class TestPublicRoutes:
    """Tests des routes publiques avec client Flask."""

    @pytest.fixture
    def client(self):
        app, config = _make_app()
        _register_dashboard_api(app, config)
        _register_public_api(app, config)
        return app.test_client()

    def test_health_returns_json(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "dashboard-llm"

    def test_root_returns_html(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert 'dashboard' in resp.data.decode('utf-8').lower()

    def test_api_data_returns_json(self, client):
        resp = client.get('/api/data')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "cpu" in data
        assert "ram" in data
        assert "gpus" in data
        assert "services" in data

    def test_api_v1_gpus_returns_json(self, client):
        resp = client.get('/api/v1/gpus')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "gpus" in data
        assert isinstance(data["gpus"], list)

    def test_api_v1_services_returns_json(self, client):
        resp = client.get('/api/v1/services')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "services" in data
        assert "active_services_by_group" in data
        assert "models_by_group" in data

    def test_api_v1_metrics_returns_json(self, client):
        resp = client.get('/api/v1/metrics')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "cpu" in data
        assert "ram" in data
        assert "services" in data
        assert "model" in data

    def test_metrics_returns_text_plain(self, client):
        resp = client.get('/metrics')
        assert resp.status_code == 200
        assert resp.mimetype.startswith('text/plain')
        text = resp.data.decode('utf-8')
        assert 'cpu_load_percent' in text
        assert 'ram_used_gb' in text


class TestAdminRoutesAuth:
    """Tests des routes admin — verification de l'authentification."""

    @pytest.fixture
    def client_no_auth(self):
        app, config = _make_app()
        _register_admin_routes(app, config, logged_in=False)
        return app.test_client()

    @pytest.fixture
    def client_with_auth(self):
        app, config = _make_app()
        _register_admin_routes(app, config, logged_in=True)
        return app.test_client()

    def test_admin_panel_redirects_when_not_logged_in(self, client_no_auth):
        resp = client_no_auth.get('/admin/panel', follow_redirects=False)
        assert resp.status_code == 302
        assert '/admin' in resp.headers['Location']

    def test_api_admin_status_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.get('/api/admin/status')
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "unauthorized"

    def test_api_admin_start_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.post('/api/admin/start', json={"service": "test_service"})
        assert resp.status_code == 401

    def test_api_admin_stop_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.post('/api/admin/stop', json={"service": "test_service"})
        assert resp.status_code == 401

    def test_api_admin_restart_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.post('/api/admin/restart', json={"service": "test_service"})
        assert resp.status_code == 401

    def test_api_admin_force_stop_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.post('/api/admin/force_stop', json={"service": "test_service"})
        assert resp.status_code == 401

    def test_api_admin_stop_all_llm_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.post('/api/admin/stop_all_llm')
        assert resp.status_code == 401

    def test_api_admin_vram_returns_401_unauthenticated(self, client_no_auth):
        resp = client_no_auth.get('/api/admin/vram')
        assert resp.status_code == 401


class TestAdminRoutesAuthorized:
    """Tests des routes admin — connecte."""

    @pytest.fixture
    def client(self):
        app, config = _make_app()
        _register_admin_routes(app, config, logged_in=True)
        return app.test_client()

    def test_admin_status_returns_json(self, client):
        resp = client.get('/api/admin/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert "services" in data
        assert "vram" in data

    def test_admin_vram_returns_json(self, client):
        resp = client.get('/api/admin/vram')
        assert resp.status_code == 200

    def test_admin_start_missing_service(self, client):
        resp = client.post('/api/admin/start', json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "missing service key"

    def test_admin_start_known_service(self, client):
        resp = client.post('/api/admin/start', json={"service": "test_service"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_admin_stop_missing_service(self, client):
        resp = client.post('/api/admin/stop', json={})
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "missing service key"

    def test_admin_stop_known_service(self, client):
        resp = client.post('/api/admin/stop', json={"service": "test_service"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_admin_stop_all_llm(self, client):
        resp = client.post('/api/admin/stop_all_llm')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_admin_force_stop(self, client):
        resp = client.post('/api/admin/force_stop', json={"service": "test_service"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
