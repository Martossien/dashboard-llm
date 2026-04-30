"""Phase 1.1 — Tests de RuntimeDependencies et app_factory decoupe.

Verifie que create_runtime_dependencies() est testable sans Flask,
et que les fonctions extraites (register_routes, setup_signal_handlers)
fonctionnent correctement.
"""
import pytest
from unittest.mock import patch, MagicMock


# ============================================================================
# RuntimeDependencies
# ============================================================================

class TestCreateRuntimeDependencies:
    """Tests pour create_runtime_dependencies()."""

    @pytest.fixture
    def config(self):
        return {
            "server": {"host": "127.0.0.1", "port": 5000, "debug": False},
            "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
            "services": {
                "ik_llama_cpp": {"name": "ik", "base_url": "http://127.0.0.1:8080",
                                 "health_endpoint": "/health", "timeout_seconds": 2},
                "llama_cpp": {"name": "llama", "base_url": "http://127.0.0.1:8080",
                              "health_endpoint": "/health", "timeout_seconds": 2},
                "vllm": {"name": "vllm", "base_url": "http://127.0.0.1:8080",
                         "health_endpoint": "/health", "timeout_seconds": 2},
                "ollama": {"name": "ollama", "base_url": "http://127.0.0.1:11434",
                           "health_endpoint": "/", "timeout_seconds": 2},
                "voxtral": {"name": "voxtral", "base_url": "http://127.0.0.1:6060",
                            "health_endpoint": "/healthz", "timeout_seconds": 2},
                "voxtral_stt": {"name": "voxtral_stt", "base_url": "http://127.0.0.1:7860",
                                "health_endpoint": "/", "timeout_seconds": 2},
            },
            "gpu": {"enable": False},
            "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                           "power_warning_percent": 70, "power_danger_percent": 90},
            "model_detection": {"cache_seconds": 5, "cache_grace_seconds": 30,
                                "process_scan_interval_seconds": 30,
                                "process_keywords": ["ik_llama", "server"],
                                "model_arg_flags": ["-m", "--model"]},
            "start_stop": {},
            "admin": {"enabled": True, "allow_force_stop": True},
        }

    def test_returns_runtime_dependencies(self, config):
        from llm_dashboard.runtime import create_runtime_dependencies, RuntimeDependencies

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            deps = create_runtime_dependencies(config)
            assert isinstance(deps, RuntimeDependencies)

    def test_runner_is_command_runner(self, config):
        from llm_dashboard.runtime import create_runtime_dependencies
        from llm_dashboard.services.commands import CommandRunner

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            deps = create_runtime_dependencies(config)
            assert isinstance(deps.runner, CommandRunner)

    def test_gpu_monitor_mockable(self, config):
        from llm_dashboard.runtime import create_runtime_dependencies

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.monitors.gpu.monitor.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            deps = create_runtime_dependencies(config)
            assert deps.gpu_monitor is not None
            assert deps.gpu_monitor.vendor_name == "cpu"

    def test_callables_are_callable(self, config):
        from llm_dashboard.runtime import create_runtime_dependencies

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.monitors.gpu.monitor.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            deps = create_runtime_dependencies(config)

            assert callable(deps.get_gpu_info)
            assert callable(deps.get_vram_status)
            assert callable(deps.get_gpu_processes)
            assert callable(deps.get_logs)
            assert callable(deps.get_services_status)
            assert callable(deps.detect_model_name)
            assert callable(deps.do_start_service)
            assert callable(deps.do_stop_service)
            assert callable(deps.create_controller)

    def test_no_flask_route_created(self, config):
        """create_runtime_dependencies() ne doit PAS creer de routes Flask."""
        from llm_dashboard.runtime import create_runtime_dependencies

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            deps = create_runtime_dependencies(config)
            assert not hasattr(deps, 'app')
            assert not hasattr(deps, 'flask_app')


# ============================================================================
# App Factory Split
# ============================================================================

class TestAppFactorySplit:
    """Tests pour create_full_app() apres extraction des dependances."""

    def test_create_full_app_returns_app_and_config(self):
        from llm_dashboard.app_factory import create_full_app
        from flask import Flask

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, config = create_full_app(setup_signals=False)
            assert isinstance(app, Flask)
            assert isinstance(config, dict)

    def test_setup_signals_false_does_not_register_handlers(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.monitor.get_gpu_backend") as mock_gpu, \
             patch("signal.signal") as mock_signal:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            create_full_app(setup_signals=False)
            mock_signal.assert_not_called()

    def test_setup_signals_true_registers_handlers(self):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.monitor.get_gpu_backend") as mock_gpu, \
             patch("signal.signal") as mock_signal:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            create_full_app(setup_signals=True)
            assert mock_signal.call_count >= 2

    def test_accepts_config_path(self, temp_config_file):
        from llm_dashboard.app_factory import create_full_app

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.app_factory.load_startup_stats"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            app, config = create_full_app(config_path=temp_config_file, setup_signals=False)
            assert config["server"]["port"] == 5050

    def test_register_routes_enregisters_expected_endpoints(self):
        from llm_dashboard.app_factory import register_routes
        from llm_dashboard.web.app import create_app
        from llm_dashboard.runtime import create_runtime_dependencies

        config = {
            "server": {"host": "127.0.0.1", "port": 5000, "debug": False},
            "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
            "services": {
                "ik_llama_cpp": {"name": "ik", "base_url": "http://127.0.0.1:8080",
                                 "health_endpoint": "/health", "timeout_seconds": 2},
                "llama_cpp": {"name": "llama", "base_url": "http://127.0.0.1:8080",
                              "health_endpoint": "/health", "timeout_seconds": 2},
                "vllm": {"name": "vllm", "base_url": "http://127.0.0.1:8080",
                         "health_endpoint": "/health", "timeout_seconds": 2},
                "ollama": {"name": "ollama", "base_url": "http://127.0.0.1:11434",
                           "health_endpoint": "/", "timeout_seconds": 2},
                "voxtral": {"name": "voxtral", "base_url": "http://127.0.0.1:6060",
                            "health_endpoint": "/healthz", "timeout_seconds": 2},
                "voxtral_stt": {"name": "voxtral_stt", "base_url": "http://127.0.0.1:7860",
                                "health_endpoint": "/", "timeout_seconds": 2},
            },
            "gpu": {"enable": False},
            "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90,
                           "power_warning_percent": 70, "power_danger_percent": 90},
            "model_detection": {"cache_seconds": 5, "cache_grace_seconds": 30,
                                "process_scan_interval_seconds": 30,
                                "process_keywords": ["ik_llama", "server"],
                                "model_arg_flags": ["-m", "--model"]},
            "start_stop": {},
            "admin": {"enabled": True, "allow_force_stop": True,
                      "session_secret": "test"},
        }

        with patch("llm_dashboard.runtime.psutil.cpu_percent"), \
             patch("llm_dashboard.monitors.gpu.factory.get_gpu_backend") as mock_gpu:
            from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
            mock_gpu.return_value = NoGPUBackend()

            deps = create_runtime_dependencies(config)
            deps.get_llama_startup_state = lambda s: {"state": "DOWN"}

            app = create_app(config)
            register_routes(app, config, deps)

            # Verifier que les routes principales sont enregistrees
            rules = {rule.rule for rule in app.url_map.iter_rules()}
            assert "/health" in rules
            assert "/" in rules
            assert "/api/data" in rules
            assert "/metrics" in rules
            assert "/api/v1/gpus" in rules
            assert "/api/admin/status" in rules
            assert "/admin/panel" in rules

    def test_import_does_not_launch_server(self):
        with patch("flask.Flask.run") as mock_run:
            import llm_dashboard.app_factory
            import importlib
            importlib.reload(llm_dashboard.app_factory)
            mock_run.assert_not_called()


class TestModelCache:
    """Tests pour ModelCache."""

    def test_defaults(self):
        from llm_dashboard.runtime import ModelCache
        cache = ModelCache()
        assert cache.name is None
        assert cache.last_check == 0.0
        assert cache.last_process_scan == 0.0

    def test_to_dict(self):
        from llm_dashboard.runtime import ModelCache
        cache = ModelCache(name="glm", last_check=123.0, last_process_scan=100.0)
        d = cache.to_dict()
        assert d["name"] == "glm"
        assert d["last_check"] == 123.0
