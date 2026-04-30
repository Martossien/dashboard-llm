"""
Application factory complete — cree l'app Flask avec toutes ses dependances.

Point de composition principal. Toutes les dependances sont creees et wirees ici.
monitor.py et cli.py appellent cette factory.
"""
from __future__ import annotations

import logging
import os
from functools import partial

from llm_dashboard.config import load_config
from llm_dashboard.services.commands import CommandRunner
from llm_dashboard.monitors.gpu.monitor import GPUMonitor
from llm_dashboard.models import normalize_services_config
from llm_dashboard.services.registry import ServiceRegistry
from llm_dashboard.services.control import ServiceController
from llm_dashboard.services.detection import (
    detect_model_name as _detect_model_name,
    _get_active_llama_key as _get_active_llama_key_fn,
    get_llama_status as _get_llama_status_fn,
    get_services_status as _get_services_status_fn,
    get_admin_services_status as _get_admin_services_status_fn,
    find_ik_llama_process,
    find_llama_process,
    find_vllm_process,
)
from llm_dashboard.services.health import check_port_is_open, wait_for_port_free
from llm_dashboard.services.metrics import (
    get_ollama_models as _get_ollama_models_fn,
    get_llama_metrics as _get_llama_metrics_fn,
)
from llm_dashboard.services.ops import (
    do_start_service as _do_start_service_fn,
    do_stop_service as _do_stop_service_fn,
    stop_all_llm_engines as _stop_all_llm_engines_fn,
)
from llm_dashboard.monitors.logs import (
    get_logs as _get_logs_fn,
    get_client_ips as _get_client_ips_fn,
    _get_active_llama_log_file as _get_active_llama_log_file_fn,
)
from llm_dashboard.monitors.timings import (
    extract_llama_timings,
    extract_vllm_timings,
    get_llama_timings as _get_llama_timings_fn,
    get_vllm_timings as _get_vllm_timings_fn,
)
from llm_dashboard.monitors.system import get_cpu_info, get_ram_info
from llm_dashboard.monitors.startup import (
    LOAD_STATS, LLAMA_STARTUP,
    get_llama_startup_state, load_startup_stats,
)
from llm_dashboard.web import (
    AdminAPIRoutes, AdminAuthRoutes, AdminPanelRoute,
    DashboardAPIRoute, create_app as _create_flask_app, register_public_api,
)

import psutil

logger = logging.getLogger("dashboard-llm")


def create_full_app(config_path=None, setup_signals=True):
    """Cree et configure l'application Flask avec toutes ses dependances.

    Args:
        config_path: chemin vers config.yaml (None = auto-detection)
        setup_signals: si True, enregistre le handler SIGINT (runtime uniquement)

    Returns:
        tuple (app: Flask, config: dict)
    """
    # ---- 1. Configuration ----
    config = load_config(config_path)

    # ---- 2. Dependances runtime ----
    runner = CommandRunner()
    gpu_monitor = GPUMonitor()

    MODEL_CACHE = {
        'name': None,
        'last_check': 0.0,
        'last_process_scan': 0.0,
    }

    # ---- 3. Partial: model detection ----
    detect_model = partial(_detect_model_name, config, MODEL_CACHE)

    # ---- 4. Partial: logs ----
    get_logs = partial(_get_logs_fn, config, runner)
    get_client_ips = partial(_get_client_ips_fn, config)
    get_active_log_file = partial(_get_active_llama_log_file_fn, config, runner)

    # ---- 5. Partial: detection ----
    get_active_llama_key = partial(_get_active_llama_key_fn, config, runner)
    get_llama_status = partial(_get_llama_status_fn, config, runner)
    get_services_status = partial(_get_services_status_fn, config, runner)

    # ---- 6. Partial: timings ----
    get_vllm_timings = partial(_get_vllm_timings_fn, config)
    get_llama_timings = partial(_get_llama_timings_fn, config, get_active_log_file)

    # ---- 7. Partial: admin / metrics / ops ----
    get_admin_services_status = partial(_get_admin_services_status_fn, config, runner)
    get_ollama_models = partial(_get_ollama_models_fn, config)
    get_llama_metrics = partial(_get_llama_metrics_fn, config)
    do_start = partial(_do_start_service_fn, config, runner, gpu_monitor)
    do_stop = partial(_do_stop_service_fn, config, runner, gpu_monitor)
    stop_all_llm = partial(_stop_all_llm_engines_fn, config, runner, gpu_monitor)

    # ---- 8. Application Flask ----
    app = _create_flask_app(config)

    # Side effects de demarrage (uniquement ici, pas a l'import)
    psutil.cpu_percent(interval=None)
    load_startup_stats()

    # ---- 9. Helpers d'auth (injectes, pas globaux) ----
    def admin_login_required():
        if not config.get("admin", {}).get("enabled", True):
            return True
        from flask import session
        return session.get("admin_logged_in") is True

    def check_admin_password(password):
        import werkzeug.security
        default_hash = "pbkdf2:sha256:260000$ndkvw7ryKFNx99Am$b8f6b66a2f536fa1010bb72c3b7c48cb4b8e82c7a05be16401cc37ca2a95f90c"
        expected_hash = config.get("admin", {}).get("password_hash", default_hash)
        if not expected_hash.startswith("pbkdf2:"):
            logger.warning("admin.password_hash is not a pbkdf2 hash — refusing plaintext comparison.")
            return False
        return werkzeug.security.check_password_hash(expected_hash, str(password))

    def get_gpu_info():
        if not config.get("gpu", {}).get("enable", True):
            return []
        try:
            return gpu_monitor.collect()
        except Exception as exc:
            logger.warning("Error getting GPU info: %s", exc)
            return []

    def get_vram_status():
        if not config.get("gpu", {}).get("enable", True):
            return {"enabled": False}
        try:
            return gpu_monitor.vram_status()
        except Exception as exc:
            return {"enabled": True, "error": str(exc)}

    def get_gpu_processes():
        try:
            return gpu_monitor.gpu_processes()
        except Exception as exc:
            logger.error("get_gpu_processes failed: %s", exc)
            return []

    def check_port_free(port, timeout=10):
        import time
        for _ in range(timeout):
            if not check_port_is_open("127.0.0.1", port, timeout=1):
                return True
            time.sleep(1)
        return False

    def _init_controller():
        services = normalize_services_config(config)
        registry = ServiceRegistry(services)
        allow_force_stop = config.get("admin", {}).get("allow_force_stop", True)
        return ServiceController(
            registry=registry,
            runner=runner,
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

    # ---- 10. Wiring routes ----
    audit_logger = logging.getLogger("dashboard-llm.audit")

    admin_auth = AdminAuthRoutes(config, admin_login_required, check_admin_password, logger)
    admin_auth.register(app)

    admin_panel = AdminPanelRoute(config, admin_login_required, get_admin_services_status, get_vram_status, get_logs, logger)
    admin_panel.register(app)

    admin_api = AdminAPIRoutes(config, admin_login_required, get_admin_services_status, get_vram_status, get_logs, do_start, do_stop, stop_all_llm, _init_controller, _control_result_to_dict, logger, audit_logger=audit_logger)
    admin_api.register(app)

    dashboard_api = DashboardAPIRoute(config, get_cpu_info, get_ram_info, get_gpu_info, get_services_status, get_llama_startup_state, get_llama_timings, get_vllm_timings, get_logs, get_client_ips, detect_model, find_ik_llama_process, find_llama_process, logger, get_ollama_models=get_ollama_models, get_llama_metrics=get_llama_metrics)
    dashboard_api.register(app)

    register_public_api(app, get_cpu_info, get_ram_info, get_gpu_info, get_services_status, detect_model, get_logs, get_llama_timings, get_vllm_timings, config)

    # ---- 11. Signal handlers (runtime uniquement) ----
    if setup_signals:
        import signal

        def _signal_handler(sig, frame):
            try:
                gpu_monitor.shutdown()
            except Exception:
                pass
            logger.info("Shutting down gracefully...")
            import sys
            sys.exit(0)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

    return app, config
