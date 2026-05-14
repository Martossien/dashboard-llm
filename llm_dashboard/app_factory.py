"""
Application factory complete — cree l'app Flask avec toutes ses dependances.

Point de composition principal. Delegue la creation des dependances a runtime.py
et le wiring des routes a register_routes().
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from llm_dashboard.config import load_config
from llm_dashboard.runtime import create_runtime_dependencies, RuntimeDependencies
from llm_dashboard.monitors.system import get_cpu_info, get_ram_info
from llm_dashboard.monitors.startup import load_startup_stats, configure_startup_paths
from llm_dashboard.web import (
    AdminAPIRoutes, AdminAuthRoutes, AdminPanelRoute,
    ConfigPanelRoute, DashboardAPIRoute,
    create_app as _create_flask_app, register_public_api,
    create_config_api,
)

logger = logging.getLogger("dashboard-llm")


def register_routes(app, config: dict, deps: RuntimeDependencies) -> None:
    """Enregistre toutes les routes sur l'application Flask.

    Args:
        app: application Flask
        config: dictionnaire de configuration
        deps: dependances runtime (RuntimeDependencies)
    """
    audit_logger = logging.getLogger("dashboard-llm.audit")

    admin_auth = AdminAuthRoutes(
        config, deps.is_admin_authenticated, deps.check_admin_password, logger
    )
    admin_auth.register(app)

    admin_panel = AdminPanelRoute(
        config, deps.is_admin_authenticated,
        deps.get_admin_services_status, deps.get_vram_status,
        deps.get_logs, logger,
    )
    admin_panel.register(app)

    admin_api = AdminAPIRoutes(
        config, deps.is_admin_authenticated,
        deps.get_admin_services_status, deps.get_vram_status,
        deps.get_logs,
        deps.do_start_service, deps.do_stop_service,
        deps.stop_all_llm_engines,
        deps.create_controller, deps.control_result_to_dict,
        logger, audit_logger=audit_logger,
        get_gpu_processes=deps.get_gpu_processes,
    )
    admin_api.register(app)

    # Configuration page
    config_panel = ConfigPanelRoute(config, deps.is_admin_authenticated)
    config_panel.register(app)
    config_api = create_config_api(config, deps.is_admin_authenticated)
    app.register_blueprint(config_api)

    dashboard_api = DashboardAPIRoute(
        config,
        get_cpu_info, get_ram_info,
        deps.get_gpu_info, deps.get_services_status,
        deps.get_llama_startup_state,
        deps.get_llama_timings, deps.get_vllm_timings,
        deps.get_logs, deps.get_client_ips,
        deps.detect_model_name,
        logger,
        get_ollama_models=deps.get_ollama_models,
        get_llama_metrics=deps.get_llama_metrics,
        get_gpu_processes=deps.get_gpu_processes,
    )
    dashboard_api.register(app)

    register_public_api(
        app, get_cpu_info, get_ram_info,
        deps.get_gpu_info, deps.get_services_status,
        deps.detect_model_name, deps.get_logs,
        deps.get_llama_timings, deps.get_vllm_timings,
        config,
        get_gpu_processes=deps.get_gpu_processes,
    )


def setup_signal_handlers(gpu_monitor) -> None:
    """Enregistre les handlers SIGINT/SIGTERM pour l'arret propre.

    Args:
        gpu_monitor: instance GPUMonitor a shutdown.
    """
    import signal
    import sys

    def _signal_handler(sig, frame):
        try:
            gpu_monitor.shutdown()
        except Exception:
            pass
        logger.info("Shutting down gracefully...")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)


def create_full_app(
    config_path: Optional[str] = None,
    setup_signals: bool = True,
):
    """Cree et configure l'application Flask avec toutes ses dependances.

    Args:
        config_path: chemin vers config.yaml (None = auto-detection)
        setup_signals: si True, enregistre les handlers SIGINT/SIGTERM

    Returns:
        tuple (app: Flask, config: dict)
    """
    config = load_config(config_path)
    deps = create_runtime_dependencies(config)
    configure_startup_paths(config)

    app = _create_flask_app(config)

    register_routes(app, config, deps)

    if setup_signals:
        setup_signal_handlers(deps.gpu_monitor)

    return app, config
