"""Phase 6 — Tests de contrat GPU Process pour les nouveaux champs.

Couvre le schema moderne (process_name, used_vram_mib, service_guess)
ainsi que le schema legacy (name, vram_mib).
"""
import pytest
from unittest.mock import MagicMock, patch


class TestGPUNormalization:
    def test_modern_schema(self):
        from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict
        r = normalize_gpu_process_dict({
            "pid": 1234, "process_name": "python", "used_vram_mib": 24576.0,
            "username": "llm", "command": "python -m vllm", "gpu_index": 0,
            "backend": "nvidia", "gpu_uuid": "GPU-123",
        })
        assert r["pid"] == 1234
        assert r["process_name"] == "python"
        assert r["used_vram_mib"] == 24576.0

    def test_legacy_schema(self):
        from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict
        r = normalize_gpu_process_dict({"pid": 1, "name": "test", "vram_mib": 100.0})
        assert r["process_name"] == "test"
        assert r["used_vram_mib"] == 100.0

    def test_invalid_pid_does_not_raise(self):
        from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict
        r = normalize_gpu_process_dict({"pid": "abc"})
        assert r["pid"] == 0

    def test_missing_pid_defaults_zero(self):
        from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict
        r = normalize_gpu_process_dict({})
        assert r["pid"] == 0

    def test_invalid_vram_does_not_raise(self):
        from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict
        r = normalize_gpu_process_dict({"pid": 1, "vram_mib": "bad"})
        assert r["used_vram_mib"] == 0.0

    def test_show_command_false_masks(self):
        from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict
        r = normalize_gpu_process_dict({"pid": 1, "command": "secret"}, show_command=False)
        assert r["command"] is None

    def test_process_vram_mib_both_schemas(self):
        from llm_dashboard.monitors.gpu.processes import process_vram_mib
        assert process_vram_mib({"used_vram_mib": 100}) == 100.0
        assert process_vram_mib({"vram_mib": 50}) == 50.0
        assert process_vram_mib({}) == 0.0
        assert process_vram_mib({"used_vram_mib": "bad"}) == 0.0

    def test_guess_vllm_from_python_command(self):
        from llm_dashboard.monitors.gpu.processes import guess_gpu_process_service
        assert guess_gpu_process_service("python", "python -m vllm.entrypoints.openai.api_server") == "vllm"

    def test_guess_ik_llama_before_llama(self):
        from llm_dashboard.monitors.gpu.processes import guess_gpu_process_service
        assert guess_gpu_process_service("ik_llama", "--model") == "ik_llama_cpp"

    def test_guess_ollama(self):
        from llm_dashboard.monitors.gpu.processes import guess_gpu_process_service
        assert guess_gpu_process_service("ollama", "") == "ollama"

    def test_guess_unknown_returns_string(self):
        from llm_dashboard.monitors.gpu.processes import guess_gpu_process_service
        r = guess_gpu_process_service(None, None)
        assert isinstance(r, str)
        assert r == "unknown"


class TestCPUOnlyBackendFallback:
    def test_no_gpu_returns_empty(self):
        from llm_dashboard.monitors.gpu.nogpu import NoGPUBackend
        b = NoGPUBackend()
        assert b.get_gpu_processes() == []


class TestGPUMonitorNormalization:
    def test_empty_result_on_exception(self):
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor
        b = MagicMock()
        b.get_gpu_processes.side_effect = RuntimeError("boom")
        m = GPUMonitor(backend=b)
        assert m.gpu_processes() == []

    def test_sorts_by_vram_desc(self):
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor
        b = MagicMock()
        b.get_gpu_processes.return_value = [
            {"pid": 1, "used_vram_mib": 100},
            {"pid": 2, "used_vram_mib": 9000},
            {"pid": 3, "used_vram_mib": 500},
        ]
        m = GPUMonitor(backend=b)
        r = m.gpu_processes()
        assert [p["used_vram_mib"] for p in r] == [9000, 500, 100]

    def test_max_processes_limits(self):
        from llm_dashboard.monitors.gpu.monitor import GPUMonitor
        b = MagicMock()
        b.get_gpu_processes.return_value = [{"pid": i, "used_vram_mib": 100 - i} for i in range(10)]
        m = GPUMonitor(backend=b)
        assert len(m.gpu_processes(max_processes=3)) == 3
