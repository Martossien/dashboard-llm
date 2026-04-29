"""Tests de structure pour la couche web Flask."""

import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_API_DATA_FIELDS = {
    "cpu",
    "ram",
    "gpus",
    "services",
    "slots_active",
    "slots_total",
    "service_logs",
    "service_order",
    "service_names",
    "model_name",
    "prompt_tokens_per_second",
    "generation_tokens_per_second",
    "vllm_prompt_tokens_per_second",
    "vllm_generation_tokens_per_second",
    "client_ips",
    "llama_service_name",
    "ik_llama_service_name",
    "vllm_service_name",
    "active_llama_service_name",
    "llama_state",
    "llama_loading_seconds",
    "llama_eta_seconds",
    "llama_avg_load_seconds",
    "active_on_8080",
    "model_on_8080",
}


def _minimal_config():
    return {
        "monitoring": {"refresh_interval_ms": 1000},
        "thresholds": {
            "vram_warning_percent": 70,
            "vram_danger_percent": 90,
            "power_warning_percent": 70,
            "power_danger_percent": 90,
        },
        "services": {
            "svc_a": {"name": "Service A"},
            "svc_b": {"name": "Service B"},
        },
    }


def test_web_routes_importable_without_monitor(monkeypatch):
    sys.modules.pop("monitor", None)

    from llm_dashboard.web import (
        AdminAPIRoutes,
        AdminAuthRoutes,
        AdminPanelRoute,
        DashboardAPIRoute,
        WebRoutes,
        create_app,
    )

    assert AdminAPIRoutes.__name__ == "AdminAPIRoutes"
    assert AdminAuthRoutes.__name__ == "AdminAuthRoutes"
    assert AdminPanelRoute.__name__ == "AdminPanelRoute"
    assert DashboardAPIRoute.__name__ == "DashboardAPIRoute"
    assert WebRoutes.__name__ == "WebRoutes"
    assert create_app.__name__ == "create_app"
    assert "monitor" not in sys.modules


def test_create_app_configures_session_and_routes():
    from llm_dashboard.web import create_app

    config = _minimal_config()
    config["admin"] = {"session_secret": "test-secret"}

    app = create_app(config)

    assert app.secret_key == "test-secret"
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert {rule.endpoint for rule in app.url_map.iter_rules()} >= {
        "index",
        "help_page",
        "health",
    }


def test_create_app_accepts_template_folder(tmp_path):
    from llm_dashboard.web import create_app

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    app = create_app(_minimal_config(), template_folder=str(template_dir))

    assert app.template_folder == str(template_dir)


def test_monitor_uses_app_factory():
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")

    assert "create_app(CONFIG)" in source
    assert "Flask(__name__" not in source
    assert "from llm_dashboard.web.app import create_app" not in source


def test_monitor_does_not_define_admin_auth_routes():
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")

    assert "def admin_login_page(" not in source
    assert "def admin_login(" not in source
    assert "def admin_logout(" not in source
    assert "AdminAuthRoutes(CONFIG, admin_login_required, check_admin_password" in source


def test_monitor_does_not_define_admin_panel_route():
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")

    assert "def admin_panel(" not in source
    assert "AdminPanelRoute(CONFIG, admin_login_required" in source


def test_monitor_does_not_define_admin_api_routes():
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")

    forbidden_defs = [
        "def api_admin_status(",
        "def api_admin_vram(",
        "def api_admin_start(",
        "def api_admin_stop(",
        "def api_admin_restart(",
        "def api_admin_force_stop(",
        "def api_admin_stop_all_llm(",
    ]
    for marker in forbidden_defs:
        assert marker not in source
    assert "AdminAPIRoutes(CONFIG, admin_login_required" in source


def test_monitor_does_not_define_api_data_route():
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")

    assert "def api_data(" not in source
    assert "@app.route('/api/data')" not in source
    assert "DashboardAPIRoute(" in source


def _register_dashboard_api(app):
    from llm_dashboard.web import DashboardAPIRoute

    DashboardAPIRoute(
        _minimal_dashboard_config(),
        get_cpu_info=lambda: {"load": 1.0},
        get_ram_info=lambda: {"used": 2.0, "total": 8.0, "percent": 25.0},
        get_gpu_info=lambda: [],
        get_services_status=lambda: {
            "services": {
                "ik": "UP",
                "llama": "DOWN",
                "vllm": "DOWN",
            },
            "llama_latency_seconds": 0.1,
            "slots_active": 1,
            "slots_total": 4,
            "active_on_8080": "ik_llama_cpp",
            "model_on_8080": "glm",
        },
        get_llama_startup_state=lambda status: {
            "state": "READY",
            "loading_seconds": None,
            "eta_seconds": None,
            "avg_seconds": None,
        },
        get_llama_timings=lambda: (10.0, 20.0),
        get_vllm_timings=lambda: (None, None),
        get_logs=lambda: {"ik_llama_cpp": ["log"]},
        get_client_ips=lambda: ["10.0.0.1"],
        detect_model_name=lambda: "glm",
        find_ik_llama_process=lambda: None,
        find_llama_process=lambda: None,
    ).register(app)


def _minimal_dashboard_config():
    return {
        "services": {
            "ik_llama_cpp": {"name": "ik"},
            "llama_cpp": {"name": "llama"},
            "vllm": {"name": "vllm"},
        }
    }


def test_dashboard_api_route_registers_expected_endpoint():
    app = Flask(__name__)
    _register_dashboard_api(app)

    rules = {rule.endpoint: rule.rule for rule in app.url_map.iter_rules()}
    assert rules["api_data"] == "/api/data"


def test_dashboard_api_returns_required_fields():
    app = Flask(__name__)
    _register_dashboard_api(app)

    response = app.test_client().get("/api/data")
    data = response.get_json()

    assert response.status_code == 200
    assert REQUIRED_API_DATA_FIELDS <= set(data)
    assert data["cpu"] == {"load": 1.0}
    assert data["model_name"] == "glm"
    assert data["active_llama_service_name"] == "ik"


def _register_admin_api(app, *, logged_in=True):
    from llm_dashboard.web import AdminAPIRoutes

    AdminAPIRoutes(
        _minimal_config(),
        admin_login_required=lambda: logged_in,
        get_admin_services_status=lambda: {"svc_a": {"running": True}},
        get_vram_status=lambda: {"enabled": False},
        get_logs=lambda: {"svc_a": ["log"]},
        do_start_service=lambda key: {"success": True, "message": f"started {key}"},
        do_stop_service=lambda key: {"success": True, "message": f"stopped {key}"},
        stop_all_llm_engines=lambda: [{"key": "svc_a", "status": "stopped"}],
        _init_controller=lambda: None,
        _control_result_to_dict=lambda result: {"success": result.success},
    ).register(app)


def test_admin_api_routes_register_expected_endpoints():
    app = Flask(__name__)
    _register_admin_api(app)

    rules = {rule.endpoint: rule.rule for rule in app.url_map.iter_rules()}
    assert rules["api_admin_status"] == "/api/admin/status"
    assert rules["api_admin_vram"] == "/api/admin/vram"
    assert rules["api_admin_start"] == "/api/admin/start"
    assert rules["api_admin_stop"] == "/api/admin/stop"
    assert rules["api_admin_restart"] == "/api/admin/restart"
    assert rules["api_admin_force_stop"] == "/api/admin/force_stop"
    assert rules["api_admin_stop_all_llm"] == "/api/admin/stop_all_llm"


def test_admin_api_requires_auth_on_all_routes():
    app = Flask(__name__)
    _register_admin_api(app, logged_in=False)
    client = app.test_client()

    requests = [
        client.get("/api/admin/status"),
        client.get("/api/admin/vram"),
        client.post("/api/admin/start", json={"service": "svc_a"}),
        client.post("/api/admin/stop", json={"service": "svc_a"}),
        client.post("/api/admin/restart", json={"service": "svc_a"}),
        client.post("/api/admin/force_stop", json={"service": "svc_a"}),
        client.post("/api/admin/stop_all_llm"),
    ]
    for response in requests:
        assert response.status_code == 401
        assert response.get_json() == {"error": "unauthorized"}


def test_admin_api_stop_all_uses_injected_function():
    app = Flask(__name__)
    _register_admin_api(app, logged_in=True)

    response = app.test_client().post("/api/admin/stop_all_llm")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "results": [{"key": "svc_a", "status": "stopped"}],
    }


def test_admin_auth_routes_register_expected_endpoints():
    from llm_dashboard.web import AdminAuthRoutes

    app = Flask(__name__)
    app.secret_key = "test"

    @app.route("/admin/panel")
    def admin_panel():
        return "panel"

    @app.route("/")
    def index():
        return "index"

    routes = AdminAuthRoutes(
        {"admin": {"enabled": True}},
        admin_login_required=lambda: False,
        check_admin_password=lambda password: password == "secret",
    )
    routes.register(app)

    rules = {rule.endpoint: rule.rule for rule in app.url_map.iter_rules()}
    assert rules["admin_login_page"] == "/admin"
    assert rules["admin_login"] == "/admin/login"
    assert rules["admin_logout"] == "/admin/logout"


def test_admin_auth_login_success_and_logout():
    from llm_dashboard.web import AdminAuthRoutes

    app = Flask(__name__)
    app.secret_key = "test"

    @app.route("/admin/panel")
    def admin_panel():
        return "panel"

    @app.route("/")
    def index():
        return "index"

    AdminAuthRoutes(
        {"admin": {"enabled": True}},
        admin_login_required=lambda: False,
        check_admin_password=lambda password: password == "secret",
    ).register(app)

    client = app.test_client()
    response = client.post("/admin/login", data={"password": "secret"}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/panel")

    with client.session_transaction() as sess:
        assert sess["admin_logged_in"] is True

    response = client.get("/admin/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    with client.session_transaction() as sess:
        assert "admin_logged_in" not in sess


def test_admin_auth_login_failure_renders_login():
    from llm_dashboard.web import AdminAuthRoutes

    app = Flask(__name__, template_folder=str(ROOT / "llm_dashboard" / "templates"))
    app.secret_key = "test"

    @app.route("/admin/panel")
    def admin_panel():
        return "panel"

    AdminAuthRoutes(
        {"admin": {"enabled": True}},
        admin_login_required=lambda: False,
        check_admin_password=lambda password: False,
    ).register(app)

    response = app.test_client().post("/admin/login", data={"password": "bad"})
    assert response.status_code == 200
    assert "Mot de passe incorrect" in response.data.decode("utf-8")


def test_admin_panel_route_registers_expected_endpoint():
    from llm_dashboard.web import AdminPanelRoute

    app = Flask(__name__)
    AdminPanelRoute(
        _minimal_config(),
        admin_login_required=lambda: True,
        get_admin_services_status=lambda: {},
        get_vram_status=lambda: {"enabled": False},
        get_logs=lambda: {},
    ).register(app)

    rules = {rule.endpoint: rule.rule for rule in app.url_map.iter_rules()}
    assert rules["admin_panel"] == "/admin/panel"


def test_admin_panel_redirects_when_unauthorized():
    from llm_dashboard.web import AdminPanelRoute

    app = Flask(__name__)
    app.secret_key = "test"

    @app.route("/admin")
    def admin_login_page():
        return "login"

    AdminPanelRoute(
        _minimal_config(),
        admin_login_required=lambda: False,
        get_admin_services_status=lambda: {},
        get_vram_status=lambda: {"enabled": False},
        get_logs=lambda: {},
    ).register(app)

    response = app.test_client().get("/admin/panel", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")


def test_admin_panel_renders_when_authorized():
    from llm_dashboard.web import AdminPanelRoute

    app = Flask(__name__, template_folder=str(ROOT / "llm_dashboard" / "templates"))
    app.secret_key = "test"

    AdminPanelRoute(
        _minimal_config(),
        admin_login_required=lambda: True,
        get_admin_services_status=lambda: {
            "svc_a": {
                "display_name": "Service A",
                "running": True,
                "is_llm": False,
                "port": 1234,
            }
        },
        get_vram_status=lambda: {"enabled": False},
        get_logs=lambda: {"svc_a": ["line 1"]},
    ).register(app)

    response = app.test_client().get("/admin/panel")
    html = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Admin Panel" in html
    assert "Service A" in html


def test_web_routes_register_expected_endpoints():
    from llm_dashboard.web import WebRoutes

    app = Flask(__name__)
    WebRoutes(_minimal_config()).register(app)

    rules = {rule.endpoint: rule.rule for rule in app.url_map.iter_rules()}
    assert rules["index"] == "/"
    assert rules["help_page"] == "/help"
    assert rules["health"] == "/health"
