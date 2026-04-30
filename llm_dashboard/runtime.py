"""
Runtime dependencies — regroupement explicite des dependances de l'application.

Extrait de app_factory.py (Phase 1.1).
Permet de creer et tester les dependances independamment de Flask.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Callable, Optional

from llm_dashboard.services.commands import CommandRunner
from llm_dashboard.services.detection import (
    detect_model_name as _detect_model_name,
    _get_active_llama_key as _get_active_llama_key_fn,
    get_llama_status as _get_llama_status_fn,
    get_services_status as _get_services_status_fn,
    get_admin_services_status as _get_admin_services_status_fn,
)
from llm_dashboard.services.health import check_port_is_open
from llm_dashboard.services.metrics import (
    get_ollama_models as _get_ollama_models_fn,
    get_llama_metrics as _get_llama_metrics_fn,
)
from llm_dashboard.services.factory import (
    create_service_controller_from_config,
    start_service_as_dict,
    stop_service_as_dict,
    stop_all_llm_as_dicts,
    control_result_to_dict,
)
from llm_dashboard.monitors.gpu.monitor import GPUMonitor
from llm_dashboard.monitors.logs import (
    get_logs as _get_logs_fn,
    get_client_ips as _get_client_ips_fn,
    _get_active_llama_log_file as _get_active_llama_log_file_fn,
)
from llm_dashboard.monitors.timings import (
    get_llama_timings as _get_llama_timings_fn,
    get_vllm_timings as _get_vllm_timings_fn,
)
from llm_dashboard.models import normalize_services_config
from llm_dashboard.services.registry import ServiceRegistry
from llm_dashboard.services.control import ServiceController

import psutil

logger = logging.getLogger("dashboard-llm")


@dataclass
class ModelCache:
    """Cache de detection du modele actif (remplace le dict local)."""

    name: Optional[str] = None
    last_check: float = 0.0
    last_process_scan: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "last_check": self.last_check,
            "last_process_scan": self.last_process_scan,
        }


@dataclass
class RuntimeDependencies:
    """Dependances runtime de l'application dashboard.

    Cree une fois au demarrage, injecte dans toutes les routes.
    Immutable conceptuellement (les callables ne changent pas).
    """

    config: dict
    runner: CommandRunner
    gpu_monitor: GPUMonitor
    model_cache: ModelCache

    # Callables (partials)
    get_gpu_info: Callable[[], list]
    get_vram_status: Callable[[], dict]
    get_gpu_processes: Callable[[], list]
    get_logs: Callable[[], dict]
    get_client_ips: Callable[[], list]
    get_services_status: Callable[[], dict]
    get_admin_services_status: Callable[[], dict]
    get_llama_timings: Callable[[], tuple]
    get_vllm_timings: Callable[[], tuple]
    detect_model_name: Callable[[], str]
    get_ollama_models: Callable[[], list]
    get_llama_metrics: Callable[[], dict]

    # Admin ops (compatibilite via ops.py)
    do_start_service: Callable[[str], dict]
    do_stop_service: Callable[[str], dict]
    stop_all_llm_engines: Callable[[], list]

    # Auth helpers
    admin_login_required: Callable[[], bool]
    check_admin_password: Callable[[str], bool]

    # Factory for controller
    create_controller: Callable[[], ServiceController]
    control_result_to_dict: Callable[[Any], dict]


def create_runtime_dependencies(config: dict) -> RuntimeDependencies:
    """Cree toutes les dependances runtime a partir d'une config.

    Args:
        config: dictionnaire de configuration complet.

    Returns:
        RuntimeDependencies pret a etre injecte dans les routes.
    """
    runner = CommandRunner()
    gpu_monitor = GPUMonitor()
    model_cache = ModelCache()

    # Partial: model detection (pass ModelCache dict for mutation)
    detect_model = partial(_detect_model_name, config, model_cache.__dict__)

    # Partial: logs
    get_logs_fn = partial(_get_logs_fn, config, runner)
    get_client_ips_fn = partial(_get_client_ips_fn, config)
    get_active_log_file = partial(_get_active_llama_log_file_fn, config, runner)

    # Partial: detection
    get_services_status = partial(_get_services_status_fn, config, runner)
    get_admin_services_status = partial(_get_admin_services_status_fn, config, runner)

    # Partial: timings
    get_vllm_timings = partial(_get_vllm_timings_fn, config)
    get_llama_timings = partial(_get_llama_timings_fn, config, get_active_log_file)

    # Partial: admin / metrics / ops (via ServiceController)
    get_ollama_models = partial(_get_ollama_models_fn, config)
    get_llama_metrics = partial(_get_llama_metrics_fn, config)

    # Wrapper: ServiceController for lifecycle operations
    def _make_controller():
        return create_service_controller_from_config(config, runner, gpu_monitor)

    def do_start(key: str) -> dict:
        return start_service_as_dict(_make_controller(), key)

    def do_stop(key: str) -> dict:
        return stop_service_as_dict(_make_controller(), key)

    def stop_all_llm() -> list[dict]:
        return stop_all_llm_as_dicts(_make_controller())

    # Helpers GPU
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
        for _ in range(timeout):
            if not check_port_is_open("127.0.0.1", port, timeout=1):
                return True
            time.sleep(1)
        return False

    def _create_controller():
        return create_service_controller_from_config(config, runner, gpu_monitor)

    def _control_result_to_dict(result):
        return control_result_to_dict(result)

    # Auth helpers
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

    # Side effects de demarrage
    psutil.cpu_percent(interval=None)

    return RuntimeDependencies(
        config=config,
        runner=runner,
        gpu_monitor=gpu_monitor,
        model_cache=model_cache,
        get_gpu_info=get_gpu_info,
        get_vram_status=get_vram_status,
        get_gpu_processes=get_gpu_processes,
        get_logs=get_logs_fn,
        get_client_ips=get_client_ips_fn,
        get_services_status=get_services_status,
        get_admin_services_status=get_admin_services_status,
        get_llama_timings=get_llama_timings,
        get_vllm_timings=get_vllm_timings,
        detect_model_name=detect_model,
        get_ollama_models=get_ollama_models,
        get_llama_metrics=get_llama_metrics,
        do_start_service=do_start,
        do_stop_service=do_stop,
        stop_all_llm_engines=stop_all_llm,
        admin_login_required=admin_login_required,
        check_admin_password=check_admin_password,
        create_controller=_create_controller,
        control_result_to_dict=control_result_to_dict,
    )
