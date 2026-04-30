"""Test /api/data robustness with invalid GPU process VRAM."""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


class TestDashboardAPIGPUProcessRobustness:
    def test_invalid_vram_does_not_500(self):
        """Values VRAM invalides ne doivent pas casser /api/data."""
        from llm_dashboard.web.dashboard_api import DashboardAPIRoute

        app = Flask(__name__)
        config = {
            "services": {
                "ik_llama_cpp": {"name": "ik"},
                "llama_cpp": {"name": "llama"},
                "vllm": {"name": "vllm"},
            },
            "gpu_processes": {"enable": True},
        }

        mock_processes = [
            {"pid": 1234, "gpu_index": 0, "process_name": "python",
             "used_vram_mib": "bad-value", "username": "llm",
             "command": "python -m vllm", "service_guess": "vllm",
             "backend": "nvidia", "gpu_uuid": "GPU-test"},
        ]

        DashboardAPIRoute(
            config,
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}, "slots_active": None, "slots_total": None,
                                          "llama_latency_seconds": None, "active_on_8080": None, "model_on_8080": None},
            get_llama_startup_state=lambda s: {"state": "DOWN", "loading_seconds": None, "eta_seconds": None, "avg_seconds": None},
            get_llama_timings=lambda: (None, None),
            get_vllm_timings=lambda: (None, None),
            get_logs=lambda: {},
            get_client_ips=lambda: [],
            detect_model_name=lambda: "unknown",
            find_ik_llama_process=lambda: None,
            find_llama_process=lambda: None,
            get_gpu_processes=lambda: mock_processes,
        ).register(app)

        with app.test_client() as client:
            resp = client.get('/api/data')
            assert resp.status_code == 200
            data = resp.get_json()
            assert "gpu_processes" in data
            assert "gpu_process_count" in data
            assert "gpu_process_vram_total_mib" in data
            assert data["gpu_process_count"] == 1
            assert isinstance(data["gpu_process_vram_total_mib"], (int, float))
            assert data["gpu_process_vram_total_mib"] == 0.0
