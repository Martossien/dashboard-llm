#!/usr/bin/env python3
import json
import logging
import os
import re
import signal
from functools import partial
import sys
import time

from llm_dashboard.config import (
    DEFAULT_CONFIG, ENV_OVERRIDES, deep_update, parse_bool, parse_list,
    get_nested, set_nested, get_default, apply_env_overrides, validate_config, load_config,
)
from llm_dashboard.services.health import check_service_health, check_port_is_open, wait_for_port_free
from llm_dashboard.services.detection import (
    join_url, find_ik_llama_process, find_llama_process, find_vllm_process,
    detect_model_name as _detect_model_name,
    _get_active_llama_key as _get_active_llama_key_fn,
    get_llama_status as _get_llama_status_fn,
    get_services_status as _get_services_status_fn,
    get_admin_services_status as _get_admin_services_status_fn,
)
from llm_dashboard.services.metrics import (
    get_ollama_models as _get_ollama_models_fn,
    get_llama_metrics as _get_llama_metrics_fn,
)
from llm_dashboard.services.ops import (
    do_start_service as _do_start_service_fn,
    do_stop_service as _do_stop_service_fn,
    stop_all_llm_engines as _stop_all_llm_engines_fn,
)
from llm_dashboard.monitors.logs import tail_log_lines, read_journalctl_logs, get_logs as _get_logs_fn, get_client_ips as _get_client_ips_fn, _get_active_llama_log_file as _get_active_llama_log_file_fn
from llm_dashboard.monitors.timings import (
    extract_llama_timings as _extract_llama_timings,
    extract_vllm_timings as _extract_vllm_timings,
    LLAMA_TIMINGS as _LLAMA_TIMINGS,
    VLLM_TIMINGS as _VLLM_TIMINGS,
    get_llama_timings as _get_llama_timings_fn,
    get_vllm_timings as _get_vllm_timings_fn,
)
from llm_dashboard.monitors.system import get_cpu_info, get_ram_info
from llm_dashboard.monitors.startup import (
    LOAD_STATS_PATH, LOAD_STATS, LLAMA_STARTUP,
    get_llama_startup_state, load_startup_stats,
)
from llm_dashboard.models import normalize_services_config
from llm_dashboard.services.registry import ServiceRegistry
from llm_dashboard.services.control import ServiceController
from llm_dashboard.web import (
    AdminAPIRoutes, AdminAuthRoutes, AdminPanelRoute,
    DashboardAPIRoute, create_app, register_public_api,
)
from flask import session
import psutil
import requests
from llm_dashboard.services.commands import CommandRunner
from llm_dashboard.monitors.gpu.monitor import GPUMonitor

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(
    level=os.environ.get("DASHBOARD_LOG_LEVEL", "INFO").upper(),
    format=LOG_FORMAT,
)
logger = logging.getLogger("dashboard-llm")
audit_logger = logging.getLogger("dashboard-llm.audit")

MODEL_CACHE = {
    'name': None,
    'last_check': 0.0,
    'last_process_scan': 0.0,
}


CONFIG = load_config()

# Savepoint C — partial: bind CONFIG + MODEL_CACHE to detect_model_name
detect_model_name = partial(_detect_model_name, CONFIG, MODEL_CACHE)
COMMAND_RUNNER = CommandRunner()
_GPU_MONITOR = None


def _get_gpu_monitor():
    global _GPU_MONITOR
    if _GPU_MONITOR is None:
        _GPU_MONITOR = GPUMonitor()
    return _GPU_MONITOR


# Savepoint D — partials: bind CONFIG + COMMAND_RUNNER to log functions
get_logs = partial(_get_logs_fn, CONFIG, COMMAND_RUNNER)
get_client_ips = partial(_get_client_ips_fn, CONFIG)
_get_active_llama_log_file = partial(_get_active_llama_log_file_fn, CONFIG, COMMAND_RUNNER)

# Savepoint E — partials: bind CONFIG + COMMAND_RUNNER to detection functions
_get_active_llama_key = partial(_get_active_llama_key_fn, CONFIG, COMMAND_RUNNER)
get_llama_status = partial(_get_llama_status_fn, CONFIG, COMMAND_RUNNER)
get_services_status = partial(_get_services_status_fn, CONFIG, COMMAND_RUNNER)

# Savepoint F — partials: bind CONFIG to timings functions
get_vllm_timings = partial(_get_vllm_timings_fn, CONFIG)
get_llama_timings = partial(_get_llama_timings_fn, CONFIG, _get_active_llama_log_file)

# Savepoint G — partials: admin status, metrics, start/stop ops
get_admin_services_status = partial(_get_admin_services_status_fn, CONFIG, COMMAND_RUNNER)
get_ollama_models = partial(_get_ollama_models_fn, CONFIG)
get_llama_metrics = partial(_get_llama_metrics_fn, CONFIG)
do_start_service = partial(_do_start_service_fn, CONFIG, COMMAND_RUNNER, _get_gpu_monitor())
do_stop_service = partial(_do_stop_service_fn, CONFIG, COMMAND_RUNNER, _get_gpu_monitor())
stop_all_llm_engines = partial(_stop_all_llm_engines_fn, CONFIG, COMMAND_RUNNER, _get_gpu_monitor())

app = create_app(CONFIG)
psutil.cpu_percent(interval=None)


load_startup_stats()


def admin_login_required():
    if not CONFIG.get("admin", {}).get("enabled", True):
        return True
    return session.get("admin_logged_in") is True


def check_admin_password(password):
    default_hash = "pbkdf2:sha256:260000$ndkvw7ryKFNx99Am$b8f6b66a2f536fa1010bb72c3b7c48cb4b8e82c7a05be16401cc37ca2a95f90c"
    expected_hash = CONFIG.get("admin", {}).get("password_hash", default_hash)
    import werkzeug.security
    if not expected_hash.startswith("pbkdf2:"):
        logger.warning("admin.password_hash is not a pbkdf2 hash — refusing plaintext comparison.")
        return False
    return werkzeug.security.check_password_hash(expected_hash, str(password))


def get_gpu_info():
    if not CONFIG.get("gpu", {}).get("enable", True):
        return []
    try:
        return _get_gpu_monitor().collect()
    except Exception as exc:
        logger.warning("Error getting GPU info: %s", exc)
        return []


def get_vram_status():
    if not CONFIG.get("gpu", {}).get("enable", True):
        return {"enabled": False}
    try:
        return _get_gpu_monitor().vram_status()
    except Exception as exc:
        return {"enabled": True, "error": str(exc)}


def get_gpu_processes():
    try:
        return _get_gpu_monitor().gpu_processes()
    except Exception as exc:
        logger.error("get_gpu_processes failed: %s", exc)
    return []


def check_port_free(port, timeout=10):
    for _ in range(timeout):
        if not check_port_is_open("127.0.0.1", port, timeout=1):
            return True
        time.sleep(1)
    return False


def _init_controller():
    services = normalize_services_config(CONFIG)
    registry = ServiceRegistry(services)
    allow_force_stop = CONFIG.get("admin", {}).get("allow_force_stop", True)
    return ServiceController(
        registry=registry,
        runner=COMMAND_RUNNER,
        vram_checker=get_vram_status,
        port_checker=check_port_free,
        gpu_process_lister=get_gpu_processes,
        active_key_getter=None,
        allow_force_stop=allow_force_stop,
    )


def _control_result_to_dict(result):
    return {
        "success": result.success,
        "message": result.message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "killed_pids": list(result.killed_pids),
    }


def signal_handler(sig, frame):
    global _GPU_MONITOR
    if _GPU_MONITOR is not None:
        try:
            _GPU_MONITOR.shutdown()
        except Exception:
            pass
    logger.info("Shutting down gracefully...")
    sys.exit(0)


_admin_auth = AdminAuthRoutes(CONFIG, admin_login_required, check_admin_password, logger)
_admin_auth.register(app)
_admin_panel = AdminPanelRoute(CONFIG, admin_login_required, get_admin_services_status, get_vram_status, get_logs, logger)
_admin_panel.register(app)
_admin_api = AdminAPIRoutes(CONFIG, admin_login_required, get_admin_services_status, get_vram_status, get_logs, do_start_service, do_stop_service, stop_all_llm_engines, _init_controller, _control_result_to_dict, logger, audit_logger=audit_logger)
_admin_api.register(app)
_dashboard_api = DashboardAPIRoute(CONFIG, get_cpu_info, get_ram_info, get_gpu_info, get_services_status, get_llama_startup_state, get_llama_timings, get_vllm_timings, get_logs, get_client_ips, detect_model_name, find_ik_llama_process, find_llama_process, logger, get_ollama_models=get_ollama_models, get_llama_metrics=get_llama_metrics)
_dashboard_api.register(app)
register_public_api(app, get_cpu_info, get_ram_info, get_gpu_info, get_services_status, detect_model_name, get_logs, get_llama_timings, get_vllm_timings, CONFIG)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    app.run(host=CONFIG["server"]["host"], port=CONFIG["server"]["port"], debug=CONFIG["server"]["debug"])
