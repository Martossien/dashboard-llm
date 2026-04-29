"""
Fixtures pytest pour le dashboard-llm (production monitor.py).

Version simplifiee compatible avec le fichier de production.
"""
import os
import sys
import tempfile
import pytest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)


@pytest.fixture
def temp_config_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def minimal_config_dict():
    return {
        "server": {"host": "127.0.0.1", "port": 5050, "debug": False},
        "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
        "services": {
            "ik_llama_cpp": {"name": "ik_llama.cpp", "base_url": "http://127.0.0.1:8080", "health_endpoint": "/health", "models_endpoint": "/v1/models", "timeout_seconds": 2, "log_file": "/var/log/launch_llm.log"},
            "llama_cpp": {"name": "llama.cpp", "base_url": "http://127.0.0.1:8080", "health_endpoint": "/health", "models_endpoint": "/v1/models", "timeout_seconds": 2, "log_file": "/var/log/launch_arbitrage_q8.log"},
            "vllm": {"name": "vLLM Qwen3.6-27B", "base_url": "http://127.0.0.1:8080", "health_endpoint": "/health", "models_endpoint": "/v1/models", "timeout_seconds": 2, "log_file": "/var/log/vllm_qwen36_27b.log"},
            "ollama": {"name": "Ollama", "base_url": "http://127.0.0.1:11434", "health_endpoint": "/", "timeout_seconds": 2, "log_type": "journalctl", "journalctl_unit": "ollama", "journalctl_lines": 50},
            "voxtral": {"name": "Voxtral-web (TTS)", "base_url": "http://127.0.0.1:6060", "health_endpoint": "/healthz", "log_file": "/opt/voxtral-web/logs/voxtral-web.log", "timeout_seconds": 2},
            "voxtral_stt": {"name": "Voxtral-WebUI (STT)", "base_url": "http://127.0.0.1:7860", "health_endpoint": "/", "timeout_seconds": 2, "log_file": "/root/Voxtral-WebUI/app.log"},
        },
        "gpu": {"enable": False},
        "model_detection": {"cache_seconds": 5, "cache_grace_seconds": 30, "process_scan_interval_seconds": 30, "process_keywords": ["ik_llama", "server"], "model_arg_flags": ["-m", "--model"]},
        "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90, "power_warning_percent": 70, "power_danger_percent": 90},
        "admin": {"enabled": True, "password_hash": "pbkdf2:sha256:260000$test$test", "session_secret": "test-secret-key-for-tests-only"},
        "start_stop": {"glm47": {"display_name": "GLM-4.7", "port": 8080, "is_llm": True, "systemd_unit": "launch_llm.service"}},
    }


@pytest.fixture
def temp_config_file(temp_config_dir, minimal_config_dict):
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")
    config_path = os.path.join(temp_config_dir, "test_config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(minimal_config_dict, f)
    return config_path


@pytest.fixture
def temp_log_file():
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".log", delete=False) as f:
        filepath = f.name
    yield filepath
    try: os.unlink(filepath)
    except OSError: pass


@pytest.fixture
def log_file_with_content(temp_log_file):
    lines = [
        b"[2026-04-27 10:00:01] INFO  server: Model loaded successfully\n",
        b"[2026-04-27 10:00:02] INFO  server: Starting HTTP server on port 8080\n",
        b"prompt eval time =  1234.56 ms /   512 tokens (  2.41 ms per token, 414.83 tokens per second)\n",
        b"generation eval time =  5678.90 ms /   256 tokens ( 22.18 ms per token, 45.08 tokens per second)\n",
        b"\x1b[32m[OK]\x1b[0m Service ready\n",
        b"srv stop: all tasks already finished\n",
        b"[2026-04-27 10:00:10] INFO  server: Request from 192.168.1.100\n",
    ]
    with open(temp_log_file, "wb") as f:
        for line in lines: f.write(line)
    return temp_log_file, lines


@pytest.fixture(scope="session")
def test_app():
    import psutil, requests, subprocess, socket
    from unittest.mock import patch, MagicMock

    mock_vmem = MagicMock()
    mock_vmem.used = 16 * 1024**3
    mock_vmem.total = 32 * 1024**3
    mock_vmem.percent = 50.0

    with patch.object(psutil, "cpu_percent", return_value=50.0), \
         patch.object(psutil, "virtual_memory", return_value=mock_vmem), \
         patch.object(psutil, "process_iter", return_value=[]), \
         patch.object(psutil, "pid_exists", return_value=False), \
         patch.object(subprocess, "run", return_value=MagicMock(stdout="", stderr="", returncode=0)), \
         patch.object(requests, "get", side_effect=Exception("Mocked connection refused")), \
         patch.object(requests, "post", side_effect=Exception("Mocked connection refused")), \
         patch.object(socket, "socket", return_value=MagicMock(connect_ex=MagicMock(return_value=1), close=MagicMock(), settimeout=MagicMock())), \
         patch.dict(os.environ, {"DASHBOARD_CONFIG": "/nonexistent/test_config.yaml", "DASHBOARD_GPU_ENABLE": "false"}):

        import monitor
        os.environ.pop("DASHBOARD_GPU_ENABLE", None)

        test_config = {
            "server": {"host": "127.0.0.1", "port": 5050, "debug": False},
            "monitoring": {"refresh_interval_ms": 1000, "log_lines": 50, "log_block_bytes": 8192},
            "services": {
                "ik_llama_cpp": {"name": "ik_llama.cpp", "base_url": "http://127.0.0.1:8080", "health_endpoint": "/health", "models_endpoint": "/v1/models", "timeout_seconds": 2, "log_file": "/var/log/launch_llm.log"},
                "llama_cpp": {"name": "llama.cpp", "base_url": "http://127.0.0.1:8080", "health_endpoint": "/health", "models_endpoint": "/v1/models", "timeout_seconds": 2, "log_file": "/var/log/launch_arbitrage_q8.log"},
                "vllm": {"name": "vLLM Qwen3.6-27B", "base_url": "http://127.0.0.1:8080", "health_endpoint": "/health", "models_endpoint": "/v1/models", "timeout_seconds": 2, "log_file": "/var/log/vllm_qwen36_27b.log"},
                "ollama": {"name": "Ollama", "base_url": "http://127.0.0.1:11434", "health_endpoint": "/", "timeout_seconds": 2, "log_type": "journalctl", "journalctl_unit": "ollama", "journalctl_lines": 50},
                "voxtral": {"name": "Voxtral-web (TTS)", "base_url": "http://127.0.0.1:6060", "health_endpoint": "/healthz", "log_file": "/opt/voxtral-web/logs/voxtral-web.log", "timeout_seconds": 2},
                "voxtral_stt": {"name": "Voxtral-WebUI (STT)", "base_url": "http://127.0.0.1:7860", "health_endpoint": "/", "timeout_seconds": 2, "log_file": "/root/Voxtral-WebUI/app.log"},
            },
            "gpu": {"enable": False},
            "model_detection": {"cache_seconds": 5, "cache_grace_seconds": 30, "process_scan_interval_seconds": 30, "process_keywords": ["ik_llama", "server"], "model_arg_flags": ["-m", "--model"]},
            "thresholds": {"vram_warning_percent": 70, "vram_danger_percent": 90, "power_warning_percent": 70, "power_danger_percent": 90},
            "admin": {"enabled": True, "password_hash": "pbkdf2:sha256:260000$test$test", "session_secret": "test-secret-key-for-tests-only"},
            "start_stop": {"glm47": {"display_name": "GLM-4.7", "port": 8080, "is_llm": True, "systemd_unit": "launch_llm.service"}},
        }
        monitor.CONFIG.clear()
        monitor.CONFIG.update(test_config)

        app = monitor.app
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret"
        yield app


@pytest.fixture
def client(test_app):
    return test_app.test_client()


@pytest.fixture(autouse=True)
def reset_admin_config():
    import monitor
    if "admin" in monitor.CONFIG:
        monitor.CONFIG["admin"]["enabled"] = True
    yield


@pytest.fixture
def admin_client(test_app, client):
    import monitor
    original_enabled = monitor.CONFIG["admin"].get("enabled", True)
    monitor.CONFIG["admin"]["enabled"] = False
    with client.session_transaction() as sess:
        sess["admin_logged_in"] = True
    yield client
    monitor.CONFIG["admin"]["enabled"] = original_enabled
