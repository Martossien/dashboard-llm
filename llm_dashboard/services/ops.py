"""
Service operations — compatibility adapter (legacy).

Delegue toute la logique metier a ServiceController via le module factory.
Les signatures restent compatibles avec les anciens appels de monitor.py/runtime.py.

Ne plus utiliser directement pour du nouveau code.
Preferer ServiceController + llm_dashboard.services.factory.
"""
from __future__ import annotations

import logging

from llm_dashboard.services.factory import (
    create_service_controller_from_config,
    start_service_as_dict,
    stop_service_as_dict,
    stop_all_llm_as_dicts,
)

_logger = logging.getLogger("dashboard-llm.ops")


def do_start_service(config: dict, command_runner, gpu_monitor, key: str) -> dict:
    """(LEGACY) Demarre un service. Delegue a ServiceController.

    Args:
        config: dictionnaire complet (avec start_stop, services, admin).
        command_runner: instance CommandRunner.
        gpu_monitor: instance GPUMonitor.
        key: cle du service (start_stop key).

    Returns:
        dict {"success": bool, "message": str, ...}
    """
    ctrl = create_service_controller_from_config(config, command_runner, gpu_monitor)
    return start_service_as_dict(ctrl, key)


def do_stop_service(config: dict, command_runner, gpu_monitor, key: str) -> dict:
    """(LEGACY) Arrete un service. Delegue a ServiceController.

    Args:
        config: dictionnaire complet.
        command_runner: instance CommandRunner.
        gpu_monitor: instance GPUMonitor.
        key: cle du service.

    Returns:
        dict {"success": bool, "message": str, ...}
    """
    ctrl = create_service_controller_from_config(config, command_runner, gpu_monitor)
    return stop_service_as_dict(ctrl, key)


def stop_all_llm_engines(config: dict, command_runner, gpu_monitor) -> list[dict]:
    """(LEGACY) Arrete tous les moteurs LLM. Delegue a ServiceController.

    Args:
        config: dictionnaire complet.
        command_runner: instance CommandRunner.
        gpu_monitor: instance GPUMonitor.

    Returns:
        list[dict]
    """
    ctrl = create_service_controller_from_config(config, command_runner, gpu_monitor)
    return stop_all_llm_as_dicts(ctrl)
