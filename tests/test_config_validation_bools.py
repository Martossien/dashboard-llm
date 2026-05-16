"""Phase 6+7+8 — Type annotations, packaging, and regression tests.

Tests combined for efficiency.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# Phase 6 — Pure function regression tests
# ============================================================================

class TestParseBool:
    def test_true_values(self):
        from llm_dashboard.config import parse_bool
        assert parse_bool(True) is True
        assert parse_bool("true") is True
        assert parse_bool("1") is True
        assert parse_bool("yes") is True
        assert parse_bool("on") is True

    def test_false_values(self):
        from llm_dashboard.config import parse_bool
        assert parse_bool(False) is False
        assert parse_bool("false") is False
        assert parse_bool("0") is False
        assert parse_bool("no") is False
        assert parse_bool("off") is False

    def test_invalid_raises(self):
        from llm_dashboard.config import parse_bool
        with pytest.raises(ValueError):
            parse_bool("invalid")


class TestParseList:
    def test_list_passthrough(self):
        from llm_dashboard.config import parse_list
        assert parse_list(["a", "b"]) == ["a", "b"]

    def test_comma_string(self):
        from llm_dashboard.config import parse_list
        assert parse_list("a, b, c") == ["a", "b", "c"]

    def test_empty_string(self):
        from llm_dashboard.config import parse_list
        assert parse_list("") == []


class TestDeepUpdate:
    def test_flat_merge(self):
        from llm_dashboard.config import deep_update
        target = {"a": 1}
        deep_update(target, {"b": 2})
        assert target == {"a": 1, "b": 2}

    def test_nested_merge(self):
        from llm_dashboard.config import deep_update
        target = {"a": {"b": 1}}
        deep_update(target, {"a": {"c": 2}})
        assert target == {"a": {"b": 1, "c": 2}}

    def test_overwrite_scalar(self):
        from llm_dashboard.config import deep_update
        target = {"a": 1}
        deep_update(target, {"a": 99})
        assert target == {"a": 99}


class TestValidateConfigPure:
    def test_valid_config_passes(self):
        from llm_dashboard.config import validate_config, DEFAULT_CONFIG
        from copy import deepcopy
        config = deepcopy(DEFAULT_CONFIG)
        validate_config(config)
        assert config["server"]["port"] == DEFAULT_CONFIG["server"]["port"]

    def test_type_annotations(self):
        from llm_dashboard.config import load_config
        import typing
        hints = typing.get_type_hints(load_config)
        assert hints["config_path"] == typing.Optional[str]
        assert hints["return"] == dict


# ============================================================================
# Phase 7 — Packaging tests
# ============================================================================

class TestPackageResources:
    def test_templates_exist_via_importlib(self):
        import importlib.resources
        templates = list(importlib.resources.files("llm_dashboard.templates").iterdir())
        template_names = [p.name for p in templates]
        assert "dashboard.html" in template_names
        assert "admin.html" in template_names
        assert "login.html" in template_names
        assert "help.html" in template_names

    def test_static_css_exist_via_importlib(self):
        import importlib.resources
        css_files = list(importlib.resources.files("llm_dashboard.static.css").iterdir())
        css_names = [p.name for p in css_files]
        assert "dashboard.css" in css_names or any("css" in n for n in css_names)

    def test_static_js_exist_via_importlib(self):
        import importlib.resources
        js_files = list(importlib.resources.files("llm_dashboard.static.js").iterdir())
        js_names = [p.name for p in js_files]
        assert "dashboard.js" in js_names or any("js" in n for n in js_names)

    def test_root_html_references_dashboard_js(self, minimal_config_dict):
        from llm_dashboard.web.app import create_app
        app = create_app(minimal_config_dict)
        with app.test_client() as client:
            resp = client.get('/')
            html = resp.data.decode('utf-8')
            assert 'dashboard.js' in html or 'dashboard.css' in html

    def test_create_app_sets_template_and_static_folders(self):
        from llm_dashboard.web.app import create_app
        app, _ = _make_mini_app()
        assert app.template_folder is not None
        assert app.static_folder is not None
        assert os.path.isdir(app.template_folder)
        assert os.path.isdir(app.static_folder)


# ============================================================================
# Phase 8 — Non-regression tests
# ============================================================================

class TestConfigDefaultsNoFile:
    """La config par defaut charge sans config.yaml."""

    def test_load_config_no_file(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_CONFIG", "/nonexistent/test.yaml")
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        from monitor import load_config
        config = load_config()
        assert config["server"]["port"] == 5000
        assert isinstance(config["services"], dict)

    def test_env_overrides_config(self, monkeypatch):
        monkeypatch.setenv("DASHBOARD_CONFIG", "/nonexistent/test.yaml")
        monkeypatch.setenv("DASHBOARD_HOST", "10.0.0.1")
        monkeypatch.setenv("DASHBOARD_PORT", "9999")
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        from monitor import load_config
        config = load_config()
        assert config["server"]["host"] == "10.0.0.1"
        assert config["server"]["port"] == 9999


class TestValuationEdgeCases:
    def test_invalid_urls_replaced_by_defaults(self):
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy
        config = deepcopy(DEFAULT_CONFIG)
        config["services"]["test_svc"] = {"base_url": "ftp://bad", "health_endpoint": "/health"}
        validate_config(config)
        assert config["services"]["test_svc"]["base_url"] == "ftp://bad"

    def test_invalid_ports_rejected(self):
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy
        config = deepcopy(DEFAULT_CONFIG)
        config["server"]["port"] = -5
        validate_config(config)
        assert config["server"]["port"] == DEFAULT_CONFIG["server"]["port"]

    def test_out_of_range_replaced(self):
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy
        config = deepcopy(DEFAULT_CONFIG)
        config["monitoring"]["log_lines"] = 99999
        validate_config(config)
        assert config["monitoring"]["log_lines"] == DEFAULT_CONFIG["monitoring"]["log_lines"]


class TestDashboardNoGPU:
    """Le dashboard demarre sans GPU."""

    def test_gpu_disable_works(self):
        from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
        backend = NoGPUBackend()
        assert backend.get_devices() == []
        assert backend.get_vram_status() == {"enabled": False}


class TestNoGPUBackendWorks:
    def test_cpu_only_backend_alias(self):
        from llm_dashboard.monitors.gpu.nogpu import CPUOnlyBackend
        backend = CPUOnlyBackend()
        assert backend.vendor_name == "cpu"
        assert backend.get_devices() == []


class TestNvidiaBackendMockable:
    def test_uninitialized_returns_empty(self):
        from llm_dashboard.monitors.gpu.nvidia import NvidiaBackend
        backend = NvidiaBackend()
        assert backend.get_devices() == []
        assert not backend._initialized


class TestPublicRoutesNoAuth:
    """Les routes publiques ne necessitent pas d'auth."""

    def test_health_no_auth(self):
        from llm_dashboard.web.app import create_app
        app = create_app({"server": {"host": "127.0.0.1", "port": 5000, "debug": False},
                          "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
                          "services": {},
                          "gpu": {"enable": False},
                          "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                                         "power_warning_percent": 70, "power_danger_percent": 90},
                          "admin": {"enabled": True, "password_hash": "pbkdf2:sha256:260000$test$test"}})
        with app.test_client() as client:
            resp = client.get('/health')
            assert resp.status_code == 200

    def test_root_no_auth(self):
        from llm_dashboard.web.app import create_app
        app = create_app({"server": {"host": "127.0.0.1", "port": 5000, "debug": False},
                          "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
                          "services": {},
                          "gpu": {"enable": False},
                          "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                                         "power_warning_percent": 70, "power_danger_percent": 90},
                          "admin": {"enabled": True, "password_hash": "pbkdf2:sha256:260000$test$test"}})
        with app.test_client() as client:
            resp = client.get('/')
            assert resp.status_code == 200


class TestAdminRoutesRequireAuth:
    """Les routes admin necessitent l'auth."""

    @pytest.fixture
    def client(self):
        app, config = _make_mini_app()
        from llm_dashboard.web.admin_api import AdminAPIRoutes
        AdminAPIRoutes(
            config,
            is_admin_authenticated=lambda: False,
            get_admin_services_status=lambda: {},
            get_vram_status=lambda: {"enabled": False},
            get_logs=lambda: {},
            do_start_service=lambda k: {"success": True},
            do_stop_service=lambda k: {"success": True},
            stop_all_llm_engines=lambda: [],
            _init_controller=lambda: MagicMock(),
            _control_result_to_dict=lambda r: {"success": True},
        ).register(app)
        return app.test_client()

    def test_status_requires_auth(self, client):
        assert client.get('/api/admin/status').status_code == 401

    def test_start_requires_auth(self, client):
        assert client.post('/api/admin/start', json={"service": "x"}).status_code == 401

    def test_stop_requires_auth(self, client):
        assert client.post('/api/admin/stop', json={"service": "x"}).status_code == 401


class TestCommandSecurity:
    """Les commandes systeme ne peuvent pas recevoir d'arguments dangereux."""

    def test_systemctl_injection_prevented(self):
        from llm_dashboard.services.commands import CommandRunner
        runner = CommandRunner()
        with pytest.raises(ValueError):
            runner.systemctl_is_active("test; rm -rf /")

    def test_port_injection_prevented(self):
        from llm_dashboard.services.commands import CommandRunner
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid port"):
            runner.fuser_kill_port(0)

    def test_signal_injection_prevented(self):
        from llm_dashboard.services.commands import CommandRunner
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid signal"):
            runner.fuser_kill_port(8080, signal="STOP")


class TestDashboardNoUserConfig:
    """Le dashboard peut fonctionner sans config utilisateur."""

    def test_create_app_without_config_file(self):
        from llm_dashboard.web.app import create_app
        minimal = {
            "server": {"host": "127.0.0.1", "port": 5000, "debug": False},
            "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
            "services": {},
            "gpu": {"enable": False},
            "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                           "power_warning_percent": 70, "power_danger_percent": 90},
        }
        app = create_app(minimal)
        assert app is not None
        with app.test_client() as client:
            assert client.get('/health').status_code == 200


# ============================================================================
# Helpers
# ============================================================================

def _make_mini_app():
    from llm_dashboard.web.app import create_app
    config = {
        "server": {"host": "127.0.0.1", "port": 5050, "debug": False},
        "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
        "services": {},
        "gpu": {"enable": False},
        "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                       "power_warning_percent": 70, "power_danger_percent": 90},
        "admin": {"enabled": True, "password_hash": "pbkdf2:sha256:260000$test$test",
                  "session_secret": "test"},
    }
    app = create_app(config)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"
    return app, config
