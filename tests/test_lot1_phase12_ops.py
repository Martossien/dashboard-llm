"""Phase 1.2 — Tests de l'adaptateur ops.py vers ServiceController.

Verifie que ops.py produit les memes resultats que ServiceController
pour les operations start/stop/stop_all, et que le nouveau helper
create_service_controller_from_config() fonctionne.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestCreateServiceControllerFromConfig:
    """Tests pour create_service_controller_from_config()."""

    def test_creates_controller_with_known_services(self):
        from llm_dashboard.services.control import create_service_controller_from_config
        from llm_dashboard.services.control import ServiceController
        from llm_dashboard.services.commands import CommandRunner

        config = {
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
            "start_stop": {},
            "admin": {"allow_force_stop": True},
        }
        runner = CommandRunner()
        ctrl = create_service_controller_from_config(config, runner)
        assert isinstance(ctrl, ServiceController)

    def test_unknown_service_returns_error(self):
        from llm_dashboard.services.control import create_service_controller_from_config
        from llm_dashboard.services.commands import CommandRunner

        config = {
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
            "start_stop": {"test_svc": {"display_name": "Test", "port": 1234,
                                         "is_llm": False, "systemd_unit": "test.service",
                                         "start_command": ["systemctl", "start", "test.service"],
                                         "stop_command": ["systemctl", "stop", "test.service"]}},
            "admin": {"allow_force_stop": True},
        }
        runner = CommandRunner()
        ctrl = create_service_controller_from_config(config, runner)

        with patch.object(runner, "systemctl_start", return_value=MagicMock(success=True, returncode=0, stderr="")):
            result = ctrl.start_service("nope")
            assert not result.success

        with patch.object(runner, "systemctl_stop", return_value=MagicMock(success=True, returncode=0, stderr="")):
            result = ctrl.stop_service("nope")
            assert not result.success


class TestOpsAdapter:
    """Tests que ops.py reste fonctionnel (compatibilite)."""

    def test_do_start_service_unknown_service(self):
        from llm_dashboard.services.ops import do_start_service
        config = {"start_stop": {}}
        result = do_start_service(config, MagicMock(), MagicMock(), "nope")
        assert not result["success"]
        assert "inconnu" in result["message"].lower()

    def test_do_start_service_no_start_command(self):
        from llm_dashboard.services.ops import do_start_service
        config = {"start_stop": {"test": {"display_name": "Test"}}}
        result = do_start_service(config, MagicMock(), MagicMock(), "test")
        assert not result["success"]
        assert "start_command" in result["message"].lower()

    def test_do_stop_service_unknown_service(self):
        from llm_dashboard.services.ops import do_stop_service
        config = {"start_stop": {}}
        result = do_stop_service(config, MagicMock(), MagicMock(), "nope")
        assert not result["success"]
        assert "inconnu" in result["message"].lower()

    def test_stop_all_llm_engines_no_services(self):
        from llm_dashboard.services.ops import stop_all_llm_engines

        with patch("llm_dashboard.services.ops.get_admin_services_status",
                   return_value={}), \
             patch("llm_dashboard.services.ops._check_port_free",
                   return_value=True):
            results = stop_all_llm_engines({"start_stop": {}}, MagicMock(), MagicMock())
            assert isinstance(results, list)
            assert len(results) == 0  # pas de services actifs

    def test_do_start_service_with_mocked_systemctl(self):
        from llm_dashboard.services.ops import do_start_service, _run_cmd

        config = {"start_stop": {"test": {"display_name": "Test",
                                           "start_command": ["systemctl", "start", "test.service"],
                                           "systemd_unit": "test.service"}}}
        mock_runner = MagicMock()
        mock_runner.systemctl_start.return_value = type('r', (), {
            'stdout': '', 'stderr': '', 'returncode': 0
        })()
        mock_runner.systemctl_start.return_value.stdout = ''

        result = do_start_service(config, mock_runner, MagicMock(), "test")
        assert result["success"] is True

    def test_do_stop_service_with_mocked_systemctl(self):
        from llm_dashboard.services.ops import do_stop_service

        config = {"start_stop": {"test": {"display_name": "Test",
                                           "stop_command": ["systemctl", "stop", "test.service"],
                                           "systemd_unit": "test.service"}}}
        mock_runner = MagicMock()
        mock_runner.systemctl_stop.return_value = type('r', (), {
            'stdout': '', 'stderr': '', 'returncode': 0
        })()
        mock_runner.systemctl_stop.return_value.stdout = ''

        with patch("llm_dashboard.services.ops._check_port_free", return_value=True):
            result = do_stop_service(config, mock_runner, MagicMock(), "test")
            assert result["success"] is True

    def test_result_format_compatible(self):
        """Les resultats de ops.py et ServiceController doivent avoir le meme format JSON."""
        from llm_dashboard.services.ops import do_start_service
        from llm_dashboard.services.control import ControlResult

        # ops.py result
        ops_result = do_start_service({"start_stop": {}}, MagicMock(), MagicMock(), "nope")
        assert "success" in ops_result
        assert "message" in ops_result
        assert isinstance(ops_result["success"], bool)

        # ServiceController result
        ctrl_result = ControlResult("test", True, "ok")
        assert hasattr(ctrl_result, "success")
        assert hasattr(ctrl_result, "message")
