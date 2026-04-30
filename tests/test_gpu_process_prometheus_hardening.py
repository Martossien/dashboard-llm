"""Phase 4 — Tests Prometheus GPU process metrics."""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask


class TestPrometheusGPUMetrics:
    def test_count_per_gpu_index(self):
        from llm_dashboard.web.metrics import create_metrics_endpoint
        metrics_fn = create_metrics_endpoint(
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}},
            detect_model_name=lambda: "unknown",
            get_gpu_processes=lambda: [
                {"pid": 1, "used_vram_mib": 100, "gpu_index": 0, "backend": "nvidia", "process_name": "a", "service_guess": "vllm"},
                {"pid": 2, "used_vram_mib": 200, "gpu_index": 0, "backend": "nvidia", "process_name": "b", "service_guess": "vllm"},
                {"pid": 3, "used_vram_mib": 300, "gpu_index": 1, "backend": "nvidia", "process_name": "c", "service_guess": "ollama"},
            ],
        )
        with Flask(__name__).test_request_context():
            resp = metrics_fn()
        text = resp.data.decode()
        assert 'gpu_process_count{gpu_index="0",vendor="nvidia"} 2' in text
        assert 'gpu_process_count{gpu_index="1",vendor="nvidia"} 1' in text

    def test_total_by_vendor(self):
        from llm_dashboard.web.metrics import create_metrics_endpoint
        metrics_fn = create_metrics_endpoint(
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}},
            detect_model_name=lambda: "unknown",
            get_gpu_processes=lambda: [
                {"pid": 1, "used_vram_mib": 100, "gpu_index": 0, "backend": "nvidia", "process_name": "a", "service_guess": "vllm"},
                {"pid": 2, "used_vram_mib": 200, "gpu_index": 0, "backend": "nvidia", "process_name": "b", "service_guess": "vllm"},
            ],
        )
        with Flask(__name__).test_request_context():
            resp = metrics_fn()
        text = resp.data.decode()
        assert 'gpu_process_memory_total_mib{vendor="nvidia"} 300' in text

    def test_no_command_in_labels(self):
        from llm_dashboard.web.metrics import create_metrics_endpoint
        metrics_fn = create_metrics_endpoint(
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}},
            detect_model_name=lambda: "unknown",
            get_gpu_processes=lambda: [
                {"pid": 1, "command": "secret", "used_vram_mib": 100, "gpu_index": 0, "backend": "nvidia", "process_name": "a", "service_guess": "vllm"},
            ],
        )
        with Flask(__name__).test_request_context():
            resp = metrics_fn()
        text = resp.data.decode()
        assert 'secret' not in text
        assert 'username' not in text.lower()

    def test_exception_does_not_break_metrics(self):
        from llm_dashboard.web.metrics import create_metrics_endpoint
        metrics_fn = create_metrics_endpoint(
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}},
            detect_model_name=lambda: "unknown",
            get_gpu_processes=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        with Flask(__name__).test_request_context():
            resp = metrics_fn()
        text = resp.data.decode()
        assert 'cpu_load_percent' in text
        assert 'ram_used_gb' in text

    def test_mimetype_text_plain(self):
        from llm_dashboard.web.metrics import create_metrics_endpoint
        metrics_fn = create_metrics_endpoint(
            get_cpu_info=lambda: {"load": 0},
            get_ram_info=lambda: {"used": 0, "total": 0, "percent": 0},
            get_gpu_info=lambda: [],
            get_services_status=lambda: {"services": {}},
            detect_model_name=lambda: "unknown",
        )
        with Flask(__name__).test_request_context():
            resp = metrics_fn()
        assert resp.mimetype.startswith("text/plain")
