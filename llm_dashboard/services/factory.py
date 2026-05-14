"""
Service factory — helpers pour creer ServiceController et wrappers compatibles dict.

Centralise la logique de creation du ServiceController pour eviter la duplication
entre runtime.py, ops.py et monitor.py.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from llm_dashboard.models import normalize_services_config
from llm_dashboard.services.registry import ServiceRegistry
from llm_dashboard.services.control import ServiceController, ControlResult
from llm_dashboard.services.health import check_port_is_open

logger = logging.getLogger("dashboard-llm.factory")


def create_service_controller_from_config(
    config: dict,
    runner,
    gpu_monitor=None,
    allow_force_stop: Optional[bool] = None,
    active_key_getter=None,
):
    """Cree un ServiceController a partir de la config.

    Args:
        config: dictionnaire complet (services + start_stop + admin).
        runner: instance CommandRunner.
        gpu_monitor: instance GPUMonitor (optionnel).
        allow_force_stop: override du flag admin.allow_force_stop (None = lire config).
        active_key_getter: callable(group) -> key actif (optionnel).

    Returns:
        ServiceController configure et pret a l'emploi.
    """
    services = normalize_services_config(config)
    try:
        registry = ServiceRegistry(services)
    except (ValueError, KeyError, TypeError):
        logger.warning("Failed to normalize services config, using empty registry")
        registry = ServiceRegistry([])

    if allow_force_stop is None:
        allow_force_stop = config.get("admin", {}).get("allow_force_stop", False)

    def _vram_checker():
        if not gpu_monitor:
            return {"enabled": False}
        try:
            return gpu_monitor.vram_status()
        except Exception:
            return {"enabled": False}

    def _port_checker(port, timeout=10):
        for _ in range(timeout):
            if not check_port_is_open("127.0.0.1", port, timeout=1):
                return True
            time.sleep(1)
        return False

    def _gpu_process_lister():
        if not gpu_monitor:
            return []
        try:
            return gpu_monitor.gpu_processes()
        except Exception:
            return []

    return ServiceController(
        registry=registry,
        runner=runner,
        vram_checker=_vram_checker,
        port_checker=_port_checker,
        gpu_process_lister=_gpu_process_lister,
        active_key_getter=active_key_getter,
        allow_force_stop=allow_force_stop,
    )


def control_result_to_dict(result: ControlResult) -> dict:
    """Convertit un ControlResult en dict compatible avec l'ancienne API ops.py."""
    return {
        "success": result.success,
        "message": result.message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "killed_pids": list(result.killed_pids),
    }


def start_service_as_dict(controller: ServiceController, key: str) -> dict:
    """Demarre un service via ServiceController et retourne un dict."""
    result = controller.start_service(key)
    return control_result_to_dict(result)


def stop_service_as_dict(controller: ServiceController, key: str) -> dict:
    """Arrete un service via ServiceController et retourne un dict."""
    result = controller.stop_service(key)
    return control_result_to_dict(result)


def force_stop_service_as_dict(controller: ServiceController, key: str) -> dict:
    """Force kill un service via ServiceController et retourne un dict."""
    result = controller.force_stop_service(key)
    return control_result_to_dict(result)


def stop_all_llm_as_dicts(controller: ServiceController) -> list[dict]:
    """Arrete tous les LLM sans doublons (par groupe, puis individuel)."""
    results = []
    processed_keys: set = set()

    for group in controller.registry.groups():
        services = controller.registry.by_group(group)
        llm_services = [s for s in services if s.role == "llm"]
        if llm_services:
            group_results = controller.stop_group(group)
            for r in group_results:
                processed_keys.add(r.key)
                results.append(control_result_to_dict(r))

    for svc in controller.registry.llm_services():
        if svc.key in processed_keys:
            continue
        if svc.systemd_unit or svc.stop_command:
            result = controller.stop_service(svc.key)
            results.append(control_result_to_dict(result))

    return results
