"""Tests pour monitors/system.py et monitors/gpu/."""
import pytest
from unittest.mock import MagicMock, patch


class TestSystemMonitors:
    def test_get_cpu_info_mocked(self):
        with patch("psutil.cpu_percent", return_value=42.0):
            from llm_dashboard.monitors.system import get_cpu_info
            result = get_cpu_info()
        assert result == {"load": 42.0}

    def test_get_ram_info_mocked(self):
        mock_mem = MagicMock()
        mock_mem.used = 16 * 1024**3
        mock_mem.total = 32 * 1024**3
        mock_mem.percent = 50.0
        with patch("psutil.virtual_memory", return_value=mock_mem):
            from llm_dashboard.monitors.system import get_ram_info
            result = get_ram_info()
        assert result["used"] == 16.0
        assert result["total"] == 32.0
        assert result["percent"] == 50.0


class TestGPUDevice:
    def test_to_dict(self):
        from llm_dashboard.monitors.gpu.base import GPUDevice
        d = GPUDevice(
            index=0, name="Test GPU", vendor="nvidia",
            memory_total_mib=32768, memory_used_mib=16384, memory_free_mib=16384,
            temperature_c=65, fan_speed_pct=45,
            utilization_gpu_pct=85, utilization_memory_pct=40,
            power_draw_w=350, power_limit_w=575,
        )
        j = d.to_dict()
        assert j["id"] == 0
        assert j["name"] == "Test GPU"
        assert j["temp"] == 65
        assert j["fan"] == 45
        assert j["power"] == 350
        assert j["power_limit"] == 575
        assert j["memory"]["used"] == pytest.approx(16.0, rel=0.1)
        assert j["gpu_util"] == 85


class TestNoGPUBackend:
    def test_returns_empty(self):
        from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
        backend = NoGPUBackend()
        assert backend.get_devices() == []
        assert backend.vendor_name == "cpu"

    def test_vram_status_disabled(self):
        from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
        backend = NoGPUBackend()
        assert backend.get_vram_status() == {"enabled": False}


class TestNvidiaBackend:
    def test_gpu_processes_use_injected_runner(self):
        from llm_dashboard.monitors.gpu.nvidia import NvidiaBackend
        from llm_dashboard.services.commands import CommandResult

        runner = MagicMock()
        runner.nvidia_smi_query_compute_apps.return_value = CommandResult(
            command="nvidia-smi --query-compute-apps",
            stdout="1234, python, 2048\nbad,line\n5678, llama-server, 8192\n",
            returncode=0,
        )

        backend = NvidiaBackend(runner=runner)
        assert backend.get_gpu_processes() == [
            {"pid": 1234, "name": "python", "vram_mib": 2048.0},
            {"pid": 5678, "name": "llama-server", "vram_mib": 8192.0},
        ]
        runner.nvidia_smi_query_compute_apps.assert_called_once_with(timeout=10)

    def test_gpu_processes_returns_empty_on_command_error(self):
        from llm_dashboard.monitors.gpu.nvidia import NvidiaBackend
        from llm_dashboard.services.commands import CommandResult

        runner = MagicMock()
        runner.nvidia_smi_query_compute_apps.return_value = CommandResult(
            command="nvidia-smi --query-compute-apps",
            stderr="failed",
            returncode=1,
        )

        backend = NvidiaBackend(runner=runner)
        assert backend.get_gpu_processes() == []


class TestGPUMonitor:
    def test_collect_with_nogpu(self):
        from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor
        monitor = GPUMonitor(backend=NoGPUBackend())
        result = monitor.collect()
        assert result == []

    def test_collect_with_mocked_nvidia(self):
        from llm_dashboard.monitors.gpu.base import GPUDevice
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor

        mock_backend = MagicMock()
        mock_backend.get_devices.return_value = [
            GPUDevice(index=0, name="RTX 5090", vendor="nvidia",
                      memory_total_mib=32768, memory_used_mib=8192, memory_free_mib=24576),
        ]
        mock_backend.vendor_name = "nvidia"

        monitor = GPUMonitor(backend=mock_backend)
        result = monitor.collect()
        assert len(result) == 1
        assert result[0]["name"] == "RTX 5090"

    def test_vram_status_with_mocked_backend(self):
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor

        mock_backend = MagicMock()
        mock_backend.get_vram_status.return_value = {
            "enabled": True,
            "gpus": [
                {
                    "index": "0",
                    "name": "RTX 5090",
                    "used_mb": 8192,
                    "free_mb": 24576,
                    "total_mb": 32768,
                    "usage_percent": 25.0,
                }
            ],
        }

        monitor = GPUMonitor(backend=mock_backend)
        assert monitor.vram_status()["gpus"][0]["usage_percent"] == 25.0
        mock_backend.get_vram_status.assert_called_once_with()

    def test_default_backend_vram_status_from_devices(self):
        from llm_dashboard.monitors.gpu.base import AbstractGPUBackend, GPUDevice

        class FakeBackend(AbstractGPUBackend):
            @property
            def vendor_name(self):
                return "fake"

            def initialize(self):
                return True

            def get_devices(self):
                return [
                    GPUDevice(
                        index=0,
                        name="Fake GPU",
                        vendor="fake",
                        memory_total_mib=1000,
                        memory_used_mib=250,
                        memory_free_mib=750,
                    )
                ]

            def shutdown(self):
                pass

        status = FakeBackend().get_vram_status()
        assert status == {
            "enabled": True,
            "gpus": [
                {
                    "index": "0",
                    "name": "Fake GPU",
                    "used_mb": 250,
                    "free_mb": 750,
                    "total_mb": 1000,
                    "usage_percent": 25.0,
                }
            ],
        }
