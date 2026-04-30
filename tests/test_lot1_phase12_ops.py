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

    def _min_config(self, **start_stop):
        return {
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
            "start_stop": start_stop,
            "admin": {"allow_force_stop": True},
        }

    def test_do_start_service_unknown_service(self):
        from llm_dashboard.services.ops import do_start_service
        result = do_start_service(self._min_config(), MagicMock(), MagicMock(), "nope")
        assert not result["success"]
        assert "inconnu" in result["message"].lower()

    def test_do_start_service_no_start_command(self):
        from llm_dashboard.services.ops import do_start_service
        config = self._min_config(test={"display_name": "Test"})
        result = do_start_service(config, MagicMock(), MagicMock(), "test")
        assert not result["success"]
        assert "start_command" in result["message"].lower()

    def test_do_stop_service_unknown_service(self):
        from llm_dashboard.services.ops import do_stop_service
        result = do_stop_service(self._min_config(), MagicMock(), MagicMock(), "nope")
        assert not result["success"]
        assert "inconnu" in result["message"].lower()

    def test_stop_all_llm_engines_no_active(self):
        """Sans services demarres, stop_all retourne une liste vide."""
        from llm_dashboard.services.ops import stop_all_llm_engines
        results = stop_all_llm_engines(self._min_config(), MagicMock(), MagicMock())
        assert isinstance(results, list)

    def test_do_start_service_with_mocked_systemctl(self):
        from llm_dashboard.services.ops import do_start_service

        config = self._min_config(test={
            "display_name": "Test",
            "port": 5055,
            "is_llm": False,
            "start_command": ["systemctl", "start", "test.service"],
            "systemd_unit": "test.service",
        })
        mock_runner = MagicMock()
        mock_runner.systemctl_start.return_value = type('r', (), {
            'stdout': '', 'stderr': '', 'returncode': 0, 'success': True
        })()

        result = do_start_service(config, mock_runner, MagicMock(), "test")
        assert result["success"] is True

    def test_do_stop_service_with_mocked_systemctl(self):
        from llm_dashboard.services.ops import do_stop_service

        config = self._min_config(test={
            "display_name": "Test",
            "port": 5055,
            "is_llm": False,
            "stop_command": ["systemctl", "stop", "test.service"],
            "systemd_unit": "test.service",
        })
        mock_runner = MagicMock()
        mock_runner.systemctl_stop.return_value = type('r', (), {
            'stdout': '', 'stderr': '', 'returncode': 0, 'success': True
        })()

        result = do_stop_service(config, mock_runner, MagicMock(), "test")
        assert result["success"] is True

    def test_result_format_compatible(self):
        from llm_dashboard.services.control import ControlResult
        from llm_dashboard.services.factory import control_result_to_dict

        ctrl_result = ControlResult("test", True, "ok", stdout="out", stderr="err", killed_pids=(123,))
        d = control_result_to_dict(ctrl_result)
        assert d["success"] is True
        assert d["message"] == "ok"
        assert d["stdout"] == "out"
        assert d["stderr"] == "err"
        assert d["killed_pids"] == [123]
