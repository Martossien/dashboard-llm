"""Tests unitaires pour CommandRunner + CommandResult."""
import pytest
from unittest.mock import patch, MagicMock
from llm_dashboard.services.commands import CommandRunner, CommandResult


class TestCommandResult:
    def test_success(self):
        r = CommandResult(stdout="active", stderr="", returncode=0)
        assert r.success
        assert r.output == "active"

    def test_failure(self):
        r = CommandResult(stdout="", stderr="error", returncode=1)
        assert not r.success

    def test_timed_out(self):
        r = CommandResult(timed_out=True, returncode=0)
        assert not r.success

    def test_immutable(self):
        r = CommandResult(stdout="test", stderr="", returncode=0)
        with pytest.raises(Exception):
            r.returncode = 1


class TestCommandRunnerValidation:
    """Tests de validation des arguments (sans subprocess)."""

    def test_invalid_unit_rejected(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid systemd unit"):
            runner.systemctl_is_active("rm -rf /")

    def test_empty_unit_rejected(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="must not be empty"):
            runner.systemctl_is_active("")

    def test_valid_unit_accepted(self):
        runner = CommandRunner()
        with patch.object(runner, "_run") as mock_run:
            mock_run.return_value = CommandResult(stdout="active", returncode=0)
            runner.systemctl_is_active("test.service")
        mock_run.assert_called_once()

    def test_unit_without_dot_service_rejected(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid systemd unit"):
            runner.systemctl_is_active("test-unit")

    def test_port_too_low(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid port"):
            runner.fuser_kill_port(0)

    def test_port_too_high(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid port"):
            runner.fuser_kill_port(99999)

    def test_valid_port(self):
        runner = CommandRunner()
        with patch.object(runner, "_run") as mock_run:
            mock_run.return_value = CommandResult(returncode=0)
            runner.fuser_kill_port(8080, signal="TERM")
        mock_run.assert_called_once()

    def test_invalid_signal(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid signal"):
            runner.fuser_kill_port(8080, signal="HUP")

    def test_valid_signals(self):
        runner = CommandRunner()
        for sig in ("TERM", "KILL"):
            with patch.object(runner, "_run") as mock_run:
                mock_run.return_value = CommandResult(returncode=0)
                runner.fuser_kill_port(8080, signal=sig)

    def test_lines_too_low(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid lines count"):
            runner.journalctl_unit("test.service", lines=0)

    def test_lines_too_high(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid lines count"):
            runner.journalctl_unit("test.service", lines=9999)

    def test_valid_lines(self):
        runner = CommandRunner()
        with patch.object(runner, "_run") as mock_run:
            mock_run.return_value = CommandResult(returncode=0)
            runner.journalctl_unit("test.service", lines=100)
        mock_run.assert_called_once()

    def test_negative_gpu_index(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid GPU index"):
            runner.nvidia_smi_power_limit(-1, 300)

    def test_zero_watts(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid power limit"):
            runner.nvidia_smi_power_limit(0, 0)

    def test_negative_watts(self):
        runner = CommandRunner()
        with pytest.raises(ValueError, match="Invalid power limit"):
            runner.nvidia_smi_power_limit(0, -100)


class TestCommandRunnerExecution:
    """Tests d'execution avec subprocess mocke."""

    @pytest.fixture
    def runner(self):
        return CommandRunner()

    def test_systemctl_is_active_runs_correct_command(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="active\n", stderr="", returncode=0)
            result = runner.systemctl_is_active("test.service")

        assert result.success
        assert result.output == "active"
        mock_run.assert_called_once_with(
            ["systemctl", "is-active", "test.service"],
            capture_output=True, text=True, timeout=3,
        )

    def test_systemctl_start(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            result = runner.systemctl_start("test.service", timeout=60)

        assert result.success

    def test_systemctl_stop(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            result = runner.systemctl_stop("test.service")

        assert result.success

    def test_fuser_kill_term(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            result = runner.fuser_kill_port(8080, signal="TERM")

        assert result.success

    def test_fuser_kill_kill(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="", returncode=0)
            result = runner.fuser_kill_port(8080, signal="KILL")

        assert result.success

    def test_timeout_produces_timed_out_result(self, runner):
        import subprocess as real_subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = real_subprocess.TimeoutExpired(cmd="test", timeout=5)
            result = runner.systemctl_start("test.service", timeout=5)

        assert not result.success
        assert result.timed_out
        assert result.returncode == -1

    def test_generic_exception(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            result = runner.systemctl_is_active("test.service")

        assert not result.success
        assert result.returncode == -1

    def test_journalctl_unit(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="line1\nline2\n", stderr="", returncode=0)
            result = runner.journalctl_unit("ollama.service", lines=10)

        assert result.success
        assert "line1" in result.output

    def test_nvidia_smi_query_gpu(self, runner):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="0, GeForce RTX 5090, 1000, 28000, 30720\n", stderr="", returncode=0)
            result = runner.nvidia_smi_query_gpu()

        assert result.success
        assert "RTX 5090" in result.stdout
