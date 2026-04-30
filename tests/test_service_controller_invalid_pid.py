"""Phase 5 — Tests ServiceController avec PID invalide."""
import pytest
from unittest.mock import MagicMock, patch
from llm_dashboard.services.control import ServiceController, _safe_process_pid


class TestSafeProcessPID:
    def test_valid_pid(self):
        assert _safe_process_pid({"pid": 1234}) == 1234

    def test_pid_zero(self):
        assert _safe_process_pid({"pid": 0}) is None

    def test_pid_one(self):
        assert _safe_process_pid({"pid": 1}) is None

    def test_pid_missing(self):
        assert _safe_process_pid({}) is None

    def test_pid_non_numeric(self):
        assert _safe_process_pid({"pid": "abc"}) is None

    def test_pid_none(self):
        assert _safe_process_pid({"pid": None}) is None


class TestKillGPUProcessesInvalidPID:
    def _make_proc(self, pid, vram):
        return {"pid": pid, "used_vram_mib": vram, "process_name": "test"}

    def test_pid_missing_ignored(self):
        procs = [{"used_vram_mib": 1000}]
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)
        with patch.object(ctrl, "terminate_pid", return_value=True) as mock_term:
            result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
            mock_term.assert_not_called()

    def test_pid_invalid_ignored(self):
        procs = [{"pid": "bad", "used_vram_mib": 1000}]
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)
        with patch.object(ctrl, "terminate_pid", return_value=True) as mock_term:
            result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
            mock_term.assert_not_called()

    def test_pid_zero_ignored(self):
        procs = [{"pid": 0, "used_vram_mib": 1000}]
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)
        with patch.object(ctrl, "terminate_pid", return_value=True) as mock_term:
            result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
            mock_term.assert_not_called()

    def test_pid_one_ignored(self):
        procs = [{"pid": 1, "used_vram_mib": 1000}]
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)
        with patch.object(ctrl, "terminate_pid", return_value=True) as mock_term:
            result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
            mock_term.assert_not_called()

    def test_valid_pid_signaled(self):
        procs = [{"pid": 1234, "used_vram_mib": 1000}]
        empty_procs = []
        # First call returns procs, second (survivor check) returns empty
        gpu_lister = MagicMock(side_effect=[procs, empty_procs])
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=gpu_lister)
        with patch.object(ctrl, "terminate_pid", return_value=True) as mock_term:
            result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
            mock_term.assert_called_once_with(1234, "TERM")

    def test_no_real_os_kill(self):
        procs = [{"pid": 9999, "used_vram_mib": 1000}]
        ctrl = ServiceController(MagicMock(), MagicMock(), gpu_process_lister=lambda: procs)
        result = ctrl._kill_gpu_processes(threshold_mib=500, sigkill_after=0)
        assert isinstance(result, list)
