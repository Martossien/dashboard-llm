"""Tests pour /metrics et /api/v1/*."""

from flask import Flask


def _register_public_api(app):
    from llm_dashboard.web.metrics import register_public_api

    register_public_api(
        app,
        get_cpu_info=lambda: {"load": 12.5},
        get_ram_info=lambda: {"used": 2.0, "total": 8.0, "percent": 25.0},
        get_gpu_info=lambda: [
            {
                "id": '0"bad',
                "memory": {"used": 1.5, "total": 8.0},
                "temp": 55,
                "gpu_util": 42,
                "power": 120,
            }
        ],
        get_services_status=lambda: {
            "services": {'svc"one': "UP", "svc_down": "DOWN"},
            "active_on_8080": "llama_cpp",
            "model_on_8080": "model-a",
        },
        detect_model_name=lambda: 'model"quoted',
        get_logs=lambda: {},
        get_llama_timings=lambda: (None, None),
        get_vllm_timings=lambda: (None, None),
        config={},
    )


def test_metrics_endpoint_prometheus_format():
    app = Flask(__name__)
    _register_public_api(app)

    response = app.test_client().get("/metrics")
    text = response.data.decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert "# HELP cpu_load_percent CPU load percentage" in text
    assert "cpu_load_percent 12.5" in text
    assert text.count("# HELP gpu_memory_used_gib") == 1
    assert text.count("# TYPE llm_service_up gauge") == 1
    assert 'gpu_memory_used_gib{gpu="0\\"bad"} 1.5' in text
    assert 'llm_service_up{service="svc\\"one"} 1' in text
    assert 'llm_model_info{model="model\\"quoted"} 1' in text


def test_public_json_endpoints():
    app = Flask(__name__)
    _register_public_api(app)
    client = app.test_client()

    assert client.get("/api/v1/gpus").get_json()["gpus"][0]["temp"] == 55
    assert client.get("/api/v1/services").get_json()["active_on_ports"] == {
        "8080": "llama_cpp"
    }
    metrics = client.get("/api/v1/metrics").get_json()
    assert metrics["cpu"] == {"load": 12.5}
    assert metrics["model"] == 'model"quoted'
