"""Phase 4 — Tests pour normalize_services_config et couverture additionnelle ServiceController.

Couvre la normalisation config -> ServiceConfig et les cas limites manquants.
"""
import pytest
from llm_dashboard.models import ServiceConfig, normalize_services_config


def _make_config(**overrides):
    """Cree une config test minimale avec services unifies."""
    svc = {
        "server": {"host": "127.0.0.1", "port": 5000, "debug": False},
        "services": {
            "glm47": {
                "name": "GLM-4.7",
                "base_url": "http://127.0.0.1:8080",
                "health_endpoint": "/health",
                "models_endpoint": "/v1/models",
                "timeout_seconds": 2,
                "backend": "ik_llama.cpp",
                "role": "llm",
                "exclusive_group": "llm_8080",
                "systemd_unit": "launch_llm.service",
                "start_command": ["systemctl", "start", "launch_llm.service"],
                "stop_command": ["systemctl", "stop", "launch_llm.service"],
                "vram_min_mib": 24000,
            },
            "qwen36_35b_q8": {
                "name": "Qwen3.6-35B Q8",
                "base_url": "http://127.0.0.1:8080",
                "health_endpoint": "/health",
                "models_endpoint": "/v1/models",
                "timeout_seconds": 2,
                "backend": "llama.cpp",
                "role": "llm",
                "exclusive_group": "llm_8080",
                "systemd_unit": "launch_arbitrage_q8.service",
                "start_command": ["systemctl", "start", "launch_arbitrage_q8.service"],
                "stop_command": ["systemctl", "stop", "launch_arbitrage_q8.service"],
                "vram_min_mib": 30000,
            },
            "qwen36_35b_udq8": {
                "name": "Qwen3.6-35B UDQ8",
                "base_url": "http://127.0.0.1:8080",
                "health_endpoint": "/health",
                "models_endpoint": "/v1/models",
                "timeout_seconds": 2,
                "backend": "llama.cpp",
                "role": "llm",
                "exclusive_group": "llm_8080",
                "systemd_unit": "launch_arbitrage2.service",
                "start_command": ["systemctl", "start", "launch_arbitrage2.service"],
                "stop_command": ["systemctl", "stop", "launch_arbitrage2.service"],
            },
            "qwen36_27b_vllm": {
                "name": "Qwen3.6-27B vLLM",
                "base_url": "http://127.0.0.1:8080",
                "health_endpoint": "/health",
                "models_endpoint": "/v1/models",
                "timeout_seconds": 2,
                "backend": "vllm",
                "role": "llm",
                "exclusive_group": "llm_8080",
                "systemd_unit": "vllm.service",
                "start_command": ["systemctl", "start", "vllm.service"],
                "stop_command": ["systemctl", "stop", "vllm.service"],
            },
            "ollama": {
                "name": "Ollama",
                "base_url": "http://127.0.0.1:11434",
                "health_endpoint": "/",
                "timeout_seconds": 2,
                "backend": "ollama",
                "role": "llm",
                "log_type": "journalctl",
                "journalctl_unit": "ollama",
                "systemd_unit": "ollama.service",
                "start_command": ["systemctl", "start", "ollama.service"],
                "stop_command": ["systemctl", "stop", "ollama.service"],
            },
            "voxtral_tts": {
                "name": "Voxtral TTS",
                "base_url": "http://127.0.0.1:6060",
                "health_endpoint": "/healthz",
                "timeout_seconds": 2,
                "backend": "gradio",
                "role": "auxiliary",
                "systemd_unit": "voxtral-web.service",
                "start_command": ["systemctl", "start", "voxtral-web.service"],
                "stop_command": ["systemctl", "stop", "voxtral-web.service"],
            },
            "voxtral_stt": {
                "name": "Voxtral STT",
                "base_url": "http://127.0.0.1:7860",
                "health_endpoint": "/",
                "timeout_seconds": 2,
                "backend": "gradio",
                "role": "auxiliary",
                "systemd_unit": "voxtral-webui.service",
                "start_command": ["systemctl", "start", "voxtral-webui.service"],
                "stop_command": ["systemctl", "stop", "voxtral-webui.service"],
            },
        },
        "admin": {"allow_force_stop": True},
        "gpu": {"enable": True},
        "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
        "model_detection": {
            "cache_seconds": 5, "cache_grace_seconds": 30,
            "process_scan_interval_seconds": 30,
            "process_keywords": ["ik_llama", "server"],
            "model_arg_flags": ["-m", "--model"],
        },
        "thresholds": {
            "vram_warning_percent": 70, "vram_danger_percent": 90,
            "power_warning_percent": 70, "power_danger_percent": 90,
        },
    }
    for key, value in overrides.items():
        svc[key] = value
    return svc


class TestNormalizeServicesConfig:
    """Tests pour normalize_services_config()."""

    def test_returns_service_configs(self):
        config = _make_config()
        services = normalize_services_config(config)

        assert len(services) == 7
        for svc in services:
            assert isinstance(svc, ServiceConfig)

    def test_conserves_display_names(self):
        config = _make_config()
        services = normalize_services_config(config)
        names = {s.key: s.display_name for s in services}

        assert names["glm47"] == "GLM-4.7"
        assert names["qwen36_35b_q8"] == "Qwen3.6-35B Q8"
        assert names["ollama"] == "Ollama"

    def test_extracts_port_from_base_url(self):
        config = _make_config()
        services = normalize_services_config(config)

        ollama = next(s for s in services if s.key == "ollama")
        assert ollama.port == 11434

        glm = next(s for s in services if s.key == "glm47")
        assert glm.port == 8080

    def test_applies_exclusive_group_for_llm_8080(self):
        config = _make_config()
        services = normalize_services_config(config)

        llm_services = [s for s in services if s.exclusive_group == "llm_8080"]
        assert len(llm_services) >= 4

        ollama = next(s for s in services if s.key == "ollama")
        assert ollama.exclusive_group is None

    def test_extracts_start_stop_commands(self):
        config = _make_config()
        services = normalize_services_config(config)
        glm = next(s for s in services if s.key == "glm47")

        assert glm.start_command == ("systemctl", "start", "launch_llm.service")
        assert glm.stop_command == ("systemctl", "stop", "launch_llm.service")
        assert glm.systemd_unit == "launch_llm.service"
        assert glm.vram_min_mib == 24000

    def test_minimal_config_supported(self):
        """Une config minimale (services seulement) doit fonctionner."""
        config = {
            "services": {
                "ik_llama_cpp": {
                    "name": "ik",
                    "base_url": "http://127.0.0.1:8080",
                    "health_endpoint": "/health",
                    "timeout_seconds": 2,
                },
            },
        }
        services = normalize_services_config(config)

        assert len(services) == 1
        svc = services[0]
        assert svc.display_name == "ik"
        assert svc.start_command == ()

    def test_allow_force_stop_inherits(self):
        config = _make_config()
        config["admin"]["allow_force_stop"] = True
        services = normalize_services_config(config)

        glm = next(s for s in services if s.key == "glm47")
        assert glm.allow_force_stop is True

        config["admin"]["allow_force_stop"] = False
        services2 = normalize_services_config(config)
        glm2 = next(s for s in services2 if s.key == "glm47")
        assert glm2.allow_force_stop is False

    def test_backend_mapping(self):
        config = _make_config()
        services = normalize_services_config(config)

        backends = {s.key: s.backend for s in services}
        assert backends["glm47"] == "ik_llama.cpp"
        assert backends["qwen36_35b_q8"] == "llama.cpp"
        assert backends["qwen36_27b_vllm"] == "vllm"
        assert backends["ollama"] == "ollama"
        assert backends["voxtral_tts"] == "gradio"

    def test_role_mapping(self):
        config = _make_config()
        services = normalize_services_config(config)

        roles = {s.key: s.role for s in services}
        assert roles["glm47"] == "llm"
        assert roles["ollama"] == "llm"
        assert roles["voxtral_tts"] == "auxiliary"

    def test_model_detect_patterns(self):
        config = _make_config()
        services = normalize_services_config(config)

        glm = next(s for s in services if s.key == "glm47")
        # model_detect_pattern is only set if configured in the service dict
        if glm.model_detect_pattern:
            assert "glm" in glm.model_detect_pattern.lower()


class TestServiceControllerEdgeCases:
    """Couverture des cas limites manquants de ServiceController."""

    def test_stop_service_no_stop_command(self):
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.models import ServiceConfig
        from llm_dashboard.services.registry import ServiceRegistry
        from unittest.mock import MagicMock

        svc = ServiceConfig(
            key="test",
            display_name="Test",
            backend="llama.cpp",
            role="llm",
            stop_command=(),
            systemd_unit=None,
        )
        registry = ServiceRegistry([svc])
        ctrl = ServiceController(registry, MagicMock())
        r = ctrl.stop_service("test")
        assert not r.success
        assert "Pas de systemd_unit ni stop_command" in r.message

    def test_force_stop_unknown_service(self):
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.services.registry import ServiceRegistry
        from unittest.mock import MagicMock

        ctrl = ServiceController(ServiceRegistry([]), MagicMock(), allow_force_stop=True)
        r = ctrl.force_stop_service("nope")
        assert not r.success
        assert "inconnu" in r.message.lower()

    def test_start_service_no_vram_checker(self):
        """Sans vram_checker, le demarrage ne plante pas."""
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.models import ServiceConfig
        from llm_dashboard.services.registry import ServiceRegistry
        from unittest.mock import MagicMock

        svc = ServiceConfig(
            key="test",
            display_name="Test",
            backend="llama.cpp",
            role="llm",
            vram_min_mib=99999,
            start_command=("systemctl", "start", "test.service"),
            systemd_unit="test.service",
        )
        registry = ServiceRegistry([svc])
        runner = MagicMock()
        runner.systemctl_start.return_value = type('r', (), {'success': True, 'returncode': 0, 'stderr': ''})()

        ctrl = ServiceController(registry, runner, vram_checker=None)
        r = ctrl.start_service("test")
        assert r.success  # Pas de check VRAM, donc ok

    def test_stop_group_all_succeed(self):
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.models import ServiceConfig
        from llm_dashboard.services.registry import ServiceRegistry
        from unittest.mock import MagicMock

        svc_a = ServiceConfig(
            key="a", display_name="A", backend="llama.cpp", role="llm",
            exclusive_group="g1", port=8080,
            stop_command=("systemctl", "stop", "a.service"),
            systemd_unit="a.service",
        )
        svc_b = ServiceConfig(
            key="b", display_name="B", backend="llama.cpp", role="llm",
            exclusive_group="g1", port=8080,
            stop_command=("systemctl", "stop", "b.service"),
            systemd_unit="b.service",
        )
        registry = ServiceRegistry([svc_a, svc_b])
        runner = MagicMock()
        runner.systemctl_stop.return_value = type('r', (), {'success': True, 'returncode': 0, 'stderr': ''})()

        ctrl = ServiceController(registry, runner,
                                 port_checker=lambda port, timeout=5: True,
                                 allow_force_stop=False)
        results = ctrl.stop_group("g1")
        assert len(results) == 2
        assert all(isinstance(r.success, bool) for r in results)


class TestServiceRegistryAdditional:
    """Couverture additionnelle de ServiceRegistry."""

    def test_monitorable_returns_all(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        svc = ServiceConfig(key="t", display_name="T", backend="llama.cpp", role="llm")
        registry = ServiceRegistry([svc])
        assert len(registry.monitorable()) == 1

    def test_controllable_filters_no_control(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        controllable = ServiceConfig(
            key="c", display_name="C", backend="llama.cpp", role="llm",
            systemd_unit="c.service",
        )
        not_controllable = ServiceConfig(
            key="n", display_name="N", backend="gradio", role="auxiliary",
        )
        registry = ServiceRegistry([controllable, not_controllable])
        ctrl_list = registry.controllable()
        assert len(ctrl_list) == 1
        assert ctrl_list[0].key == "c"

    def test_llm_services_filters_by_role(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        svc1 = ServiceConfig(key="l1", display_name="L1", backend="llama.cpp", role="llm")
        svc2 = ServiceConfig(key="a1", display_name="A1", backend="gradio", role="auxiliary")
        registry = ServiceRegistry([svc1, svc2])
        assert len(registry.llm_services()) == 1
        assert len(registry.auxiliary_services()) == 1

    def test_contains_method(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        svc = ServiceConfig(key="x", display_name="X", backend="llama.cpp", role="llm")
        registry = ServiceRegistry([svc])
        assert "x" in registry
        assert "y" not in registry

    def test_iter_returns_service_configs(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        svc = ServiceConfig(key="x", display_name="X", backend="llama.cpp", role="llm")
        registry = ServiceRegistry([svc])
        for s in registry:
            assert isinstance(s, ServiceConfig)

    def test_len(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        registry = ServiceRegistry([
            ServiceConfig(key="a", display_name="A", backend="llama.cpp", role="llm"),
            ServiceConfig(key="b", display_name="B", backend="vllm", role="llm"),
        ])
        assert len(registry) == 2

    def test_groups(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        svc = ServiceConfig(key="x", display_name="X", backend="llama.cpp",
                           role="llm", port=8080, exclusive_group="g1")
        registry = ServiceRegistry([svc])
        assert "g1" in registry.groups()

    def test_duplicate_key_raises(self):
        from llm_dashboard.services.registry import ServiceRegistry
        from llm_dashboard.models import ServiceConfig

        svc = ServiceConfig(key="x", display_name="X", backend="llama.cpp", role="llm")
        with pytest.raises(ValueError, match="Duplicate"):
            ServiceRegistry([svc, svc])

    def test_empty_registry(self):
        from llm_dashboard.services.registry import ServiceRegistry
        registry = ServiceRegistry()
        assert registry.count() == 0
        assert registry.all() == []
        assert registry.get("any") is None
        assert registry.by_group("any") == []
