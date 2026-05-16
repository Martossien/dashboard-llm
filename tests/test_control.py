"""Tests pour ServiceController (control.py)."""
import pytest
from unittest.mock import MagicMock, patch, call
from llm_dashboard.services.control import ServiceController, ControlResult
from llm_dashboard.services.commands import CommandResult


def _make_svc(key, **kw):
    from llm_dashboard.models import ServiceConfig
    defaults = {
        "key": key, "display_name": key.title(), "backend": "llama.cpp",
        "role": "llm", "exclusive_group": "llm_8080", "port": 8080,
        "systemd_unit": f"{key}.service",
        "start_command": ("systemctl", "start", f"{key}.service"),
        "stop_command": ("systemctl", "stop", f"{key}.service"),
    }
    defaults.update(kw)
    return ServiceConfig(**defaults)


def _make_registry(*services):
    from llm_dashboard.services.registry import ServiceRegistry
    return ServiceRegistry(list(services))


def _make_group_registry():
    return _make_registry(
        _make_svc("active"),
        _make_svc("target"),
        _make_svc("idle"),
    )


@pytest.fixture
def mock_runner():
    r = MagicMock()
    r.systemctl_start.return_value = CommandResult(returncode=0, command="start")
    r.systemctl_stop.return_value = CommandResult(returncode=0, command="stop")
    r.systemctl_kill.return_value = CommandResult(returncode=0, command="kill")
    r.fuser_kill_port.return_value = CommandResult(returncode=0, command="fuser")
    return r


@pytest.fixture
def mock_vram():
    def _checker():
        return {"enabled": True, "gpus": [{"index": 0, "name": "GPU0", "free_mb": 30000}]}
    return _checker


@pytest.fixture
def mock_port_free():
    def _checker(port, timeout=5):
        return True  # port libre
    return _checker


class TestStartService:
    def test_unknown_service(self, mock_runner):
        reg = _make_registry()
        ctrl = ServiceController(reg, mock_runner)
        r = ctrl.start_service("nope")
        assert not r.success
        assert "inconnu" in r.message.lower()

    def test_no_start_command(self, mock_runner):
        svc = _make_svc("test", start_command=(), systemd_unit=None)
        reg = _make_registry(svc)
        ctrl = ServiceController(reg, mock_runner)
        r = ctrl.start_service("test")
        assert not r.success

    def test_insufficient_vram(self, mock_runner):
        svc = _make_svc("test", vram_min_mib=50000)
        reg = _make_registry(svc)
        def low_vram():
            return {"enabled": True, "gpus": [{"index": 0, "name": "GPU0", "free_mb": 1000}]}
        ctrl = ServiceController(reg, mock_runner, vram_checker=low_vram)
        r = ctrl.start_service("test")
        assert not r.success
        assert "VRAM totale libre" in r.message
        assert "50000" in r.message

    def test_insufficient_vram_multi_gpu(self, mock_runner):
        svc = _make_svc("test", vram_min_mib=50000)
        reg = _make_registry(svc)
        def multi_gpu_vram():
            return {"enabled": True, "gpus": [
                {"index": 0, "name": "RTX 3090", "free_mb": 24109},
                {"index": 1, "name": "RTX 3090", "free_mb": 24109},
            ]}
        ctrl = ServiceController(reg, mock_runner, vram_checker=multi_gpu_vram)
        r = ctrl.start_service("test")
        assert not r.success
        assert "VRAM totale libre" in r.message
        assert "48218" in r.message

    def test_sufficient_vram_multi_gpu(self, mock_runner, mock_port_free):
        svc = _make_svc("test", vram_min_mib=50000, exclusive_group=None)
        reg = _make_registry(svc)
        def multi_gpu_vram():
            return {"enabled": True, "gpus": [
                {"index": 0, "name": "RTX 3090", "free_mb": 26000},
                {"index": 1, "name": "RTX 3090", "free_mb": 26000},
            ]}
        ctrl = ServiceController(reg, mock_runner, vram_checker=multi_gpu_vram, port_checker=mock_port_free)
        r = ctrl.start_service("test")
        assert r.success

    def test_success(self, mock_runner, mock_vram, mock_port_free):
        svc = _make_svc("test", exclusive_group=None, vram_min_mib=0)
        reg = _make_registry(svc)
        ctrl = ServiceController(reg, mock_runner, vram_checker=mock_vram, port_checker=mock_port_free)
        r = ctrl.start_service("test")
        assert r.success
        mock_runner.systemctl_start.assert_called_once()

    def test_exclusive_group_stops_only_active_service(self, mock_runner, mock_vram, mock_port_free):
        reg = _make_group_registry()
        ctrl = ServiceController(
            reg,
            mock_runner,
            vram_checker=mock_vram,
            port_checker=mock_port_free,
            active_key_getter=lambda group: "active",
        )

        r = ctrl.start_service("target")

        assert r.success
        mock_runner.systemctl_stop.assert_called_once_with("active.service", timeout=15)
        mock_runner.systemctl_start.assert_called_once_with("target.service", timeout=60)


class TestStopService:
    def test_unknown_service(self, mock_runner):
        reg = _make_registry()
        ctrl = ServiceController(reg, mock_runner)
        r = ctrl.stop_service("nope")
        assert not r.success

    def test_success(self, mock_runner, mock_port_free):
        svc = _make_svc("test", port=None, exclusive_group=None)
        reg = _make_registry(svc)
        ctrl = ServiceController(reg, mock_runner, port_checker=mock_port_free)
        r = ctrl.stop_service("test")
        assert r.success

    def test_occupied_port_without_force_stop_does_not_fuser(self, mock_runner):
        svc = _make_svc("test", port=8080)
        reg = _make_registry(svc)
        ctrl = ServiceController(
            reg,
            mock_runner,
            port_checker=lambda port, timeout=5: False,
            allow_force_stop=False,
        )

        r = ctrl.stop_service("test")

        assert not r.success
        mock_runner.fuser_kill_port.assert_not_called()

    def test_failed_systemctl_without_force_stop_does_not_systemctl_kill(self, mock_runner):
        svc = _make_svc("test", port=None, exclusive_group=None)
        reg = _make_registry(svc)
        mock_runner.systemctl_stop.return_value = CommandResult(returncode=1, stderr="failed")
        ctrl = ServiceController(reg, mock_runner, allow_force_stop=False)

        r = ctrl.stop_service("test")

        assert not r.success
        mock_runner.systemctl_kill.assert_not_called()


class TestForceStop:
    def test_refused_when_disabled(self, mock_runner):
        svc = _make_svc("test")
        reg = _make_registry(svc)
        ctrl = ServiceController(reg, mock_runner, allow_force_stop=False)
        r = ctrl.force_stop_service("test")
        assert not r.success
        assert "allow_force_stop" in r.message.lower()

    def test_allowed_when_enabled(self, mock_runner, mock_port_free):
        svc = _make_svc("test")
        reg = _make_registry(svc)
        ctrl = ServiceController(reg, mock_runner, allow_force_stop=True,
                                 port_checker=mock_port_free,
                                 gpu_process_lister=lambda: [])
        r = ctrl.force_stop_service("test")
        assert r.success


class TestRestart:
    def test_calls_stop_then_start(self, mock_runner, mock_vram, mock_port_free):
        svc = _make_svc("test", exclusive_group=None, vram_min_mib=0, port=None)
        reg = _make_registry(svc)
        ctrl = ServiceController(reg, mock_runner, vram_checker=mock_vram, port_checker=mock_port_free)
        r = ctrl.restart_service("test")
        assert r.success
        assert mock_runner.systemctl_stop.called
        assert mock_runner.systemctl_start.called


class TestStopGroup:
    def test_occupied_group_port_without_force_stop_does_not_fuser(self, mock_runner):
        reg = _make_group_registry()
        ctrl = ServiceController(
            reg,
            mock_runner,
            port_checker=lambda port, timeout=5: False,
            allow_force_stop=False,
        )

        results = ctrl.stop_group("llm_8080")

        assert len(results) == 3
        mock_runner.fuser_kill_port.assert_not_called()


class TestTerminatePID:
    def test_refuses_pid_1(self):
        ctrl = ServiceController(MagicMock(), MagicMock())
        assert not ctrl.terminate_pid(1, "TERM")

    def test_refuses_pid_0(self):
        ctrl = ServiceController(MagicMock(), MagicMock())
        assert not ctrl.terminate_pid(0, "KILL")

    def test_invalid_signal(self):
        ctrl = ServiceController(MagicMock(), MagicMock())
        with pytest.raises(ValueError, match="Invalid signal"):
            ctrl.terminate_pid(1234, "HUP")


class TestKillGPUProcesses:
    def _make_proc(self, pid, vram):
        return {"pid": pid, "name": "test", "vram_mib": vram}

    def test_no_processes(self):
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: [])
        result = ctrl._kill_gpu_processes(threshold_mib=500)
        assert result == []

    def test_processes_below_threshold(self):
        procs = [self._make_proc(100, 100), self._make_proc(200, 200)]
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)
        result = ctrl._kill_gpu_processes(threshold_mib=500)
        assert result == []

    def test_processes_above_threshold_killed(self):
        procs = [self._make_proc(100, 1000)]
        # Apres SIGTERM, le processeur survit (meme liste), donc SIGKILL est envoye aussi
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)

        with patch.object(ctrl, "terminate_pid", return_value=True) as mock_term:
            result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
            assert len(result) == 1
            mock_term.assert_any_call(100, "TERM")


class TestControlResult:
    def test_success(self):
        r = ControlResult("test", True, "ok")
        assert r.success

    def test_failure(self):
        r = ControlResult("test", False, "failed")
        assert not r.success

    def test_immutable(self):
        r = ControlResult("test", True, "ok")
        with pytest.raises(Exception):
            r.success = False
