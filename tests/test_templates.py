"""Tests de non-regression pour l'extraction des templates Flask."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_monitor_has_no_inline_templates():
    """Le lot templates ne doit pas laisser les gros HTML dans monitor.py."""
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")
    forbidden = [
        "HTML_TEMPLATE",
        "ADMIN_TEMPLATE",
        "LOGIN_TEMPLATE",
        "HELP_TEMPLATE",
        "render_template_string",
    ]
    for marker in forbidden:
        assert marker not in source


def test_monitor_has_no_direct_gpu_or_subprocess_calls():
    """Les lots precedents ne doivent pas regresser pendant l'extraction UI."""
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")
    forbidden = [
        "pynvml",
        "nvml_initialized",
        "subprocess.run",
        "socket.socket",
        "os.kill",
    ]
    for marker in forbidden:
        assert marker not in source


def test_monitor_does_not_redefine_extracted_helpers():
    """Le monolithe doit importer les helpers extraits au lieu de les recopier."""
    source = (ROOT / "monitor.py").read_text(encoding="utf-8")
    forbidden_defs = [
        "def load_config(",
        "def check_service_health(",
        "def join_url(",
        "def tail_log_lines(",
        "def read_journalctl_logs(",
        "def extract_llama_timings(",
        "def extract_vllm_timings(",
    ]
    for marker in forbidden_defs:
        assert marker not in source


def test_template_files_exist():
    template_dir = ROOT / "llm_dashboard" / "templates"
    for name in ("dashboard.html", "admin.html", "login.html", "help.html"):
        path = template_dir / name
        assert path.exists()
        assert path.read_text(encoding="utf-8").lstrip().startswith("<!DOCTYPE html>")


def test_public_pages_render_from_templates(client):
    for path, marker in (
        ("/", "System & AI Dashboard"),
        ("/help", "Aide"),
        ("/admin", "Admin Login"),
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.data.decode("utf-8")
