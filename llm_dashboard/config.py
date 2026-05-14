"""
Configuration — chargement, validation, surcharges d'environnement.

Configuration portable : les services sont definis UNIQUEMENT dans config.yaml.
Aucun nom de service, port, backend, modele ou chemin de fichier n'est hardcode.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any, Optional, Union

logger = logging.getLogger("dashboard-llm.config")

try:
    import yaml
except Exception:
    yaml: Any = None  # type: ignore[no-redef]


# ============================================================================
# Configuration par defaut — minimal, aucun service hardcode
# ============================================================================

DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
    },
    "monitoring": {
        "refresh_interval_ms": 1000,
        "log_file": "",
        "log_lines": 50,
        "log_block_bytes": 8192,
    },
    "services": {},
    "gpu": {
        "enable": True,
    },
    "model_detection": {
        "cache_seconds": 5,
        "cache_grace_seconds": 30,
        "process_scan_interval_seconds": 30,
        "process_keywords": ["llama", "server", "vllm", "python"],
        "model_arg_flags": ["-m", "--model"],
        "backend_detection": True,
    },
    "paths": {
        "load_stats": "llama_load_stats.json",
        "vllm_pid_file": "",
    },
    "thresholds": {
        "vram_warning_percent": 70,
        "vram_danger_percent": 90,
        "power_warning_percent": 70,
        "power_danger_percent": 90,
    },
    "admin": {
        "enabled": True,
        "allow_force_stop": True,
        "csrf_enabled": True,
        "csrf_header": "X-CSRF-Token",
    },
    "gpu_processes": {
        "enable": True,
        "show_command": True,
        "max_processes": 100,
    },
}

ENV_OVERRIDES = {
    "DASHBOARD_HOST": ("server", "host"),
    "DASHBOARD_PORT": ("server", "port"),
    "DASHBOARD_DEBUG": ("server", "debug"),
    "DASHBOARD_REFRESH_INTERVAL_MS": ("monitoring", "refresh_interval_ms"),
    "DASHBOARD_LOG_FILE": ("monitoring", "log_file"),
    "DASHBOARD_LOG_LINES": ("monitoring", "log_lines"),
    "DASHBOARD_LOG_BLOCK_BYTES": ("monitoring", "log_block_bytes"),
    "DASHBOARD_GPU_ENABLE": ("gpu", "enable"),
    "DASHBOARD_MODEL_CACHE_SECONDS": ("model_detection", "cache_seconds"),
    "DASHBOARD_MODEL_CACHE_GRACE_SECONDS": ("model_detection", "cache_grace_seconds"),
    "DASHBOARD_MODEL_PROCESS_SCAN_INTERVAL": ("model_detection", "process_scan_interval_seconds"),
    "DASHBOARD_MODEL_PROCESS_KEYWORDS": ("model_detection", "process_keywords"),
    "DASHBOARD_MODEL_ARG_FLAGS": ("model_detection", "model_arg_flags"),
    "DASHBOARD_VRAM_WARNING_PERCENT": ("thresholds", "vram_warning_percent"),
    "DASHBOARD_VRAM_DANGER_PERCENT": ("thresholds", "vram_danger_percent"),
    "DASHBOARD_POWER_WARNING_PERCENT": ("thresholds", "power_warning_percent"),
    "DASHBOARD_POWER_DANGER_PERCENT": ("thresholds", "power_danger_percent"),
    "DASHBOARD_ADMIN_ENABLED": ("admin", "enabled"),
    "DASHBOARD_ADMIN_ALLOW_FORCE_STOP": ("admin", "allow_force_stop"),
    "DASHBOARD_ADMIN_CSRF_ENABLED": ("admin", "csrf_enabled"),
    "DASHBOARD_ADMIN_CSRF_HEADER": ("admin", "csrf_header"),
    "DASHBOARD_GPU_PROCESSES_ENABLE": ("gpu_processes", "enable"),
    "DASHBOARD_GPU_PROCESSES_SHOW_COMMAND": ("gpu_processes", "show_command"),
    "DASHBOARD_GPU_PROCESSES_MAX": ("gpu_processes", "max_processes"),
    "DASHBOARD_PATHS_LOAD_STATS": ("paths", "load_stats"),
    "DASHBOARD_PATHS_VLLM_PID_FILE": ("paths", "vllm_pid_file"),
}


# ============================================================================
# Fonctions utilitaires de configuration
# ============================================================================

def deep_update(target: dict, updates: dict) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def parse_bool(value: Union[bool, str, int]) -> bool:
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def parse_list(value: Union[list, str]) -> list:
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).split(",") if item.strip()]


def get_nested(config: dict, path: tuple) -> Any:
    current = config
    for key in path:
        current = current[key]
    return current


def set_nested(config: dict, path: tuple, value: Any) -> None:
    current = config
    for key in path[:-1]:
        current = current.setdefault(key, {})
    current[path[-1]] = value


def get_default(path: tuple) -> Any:
    return get_nested(DEFAULT_CONFIG, path)


# ============================================================================
# Chargement et validation
# ============================================================================

def apply_env_overrides(config: dict) -> None:
    for env_key, path in ENV_OVERRIDES.items():
        if env_key not in os.environ:
            continue
        raw_value = os.environ[env_key]
        default_value = get_default(path)
        try:
            if isinstance(default_value, bool):
                value = parse_bool(raw_value)
            elif isinstance(default_value, int):
                value = int(raw_value)
            elif isinstance(default_value, float):
                value = float(raw_value)
            elif isinstance(default_value, list):
                value = parse_list(raw_value)
            else:
                value = raw_value
            set_nested(config, path, value)
        except ValueError as exc:
            logger.warning("Invalid env override %s=%r (%s)", env_key, raw_value, exc)


def _safe_get_nested(config: dict, path: tuple) -> Optional[Any]:
    try:
        return get_nested(config, path)
    except (KeyError, TypeError):
        return None


def validate_config(config: dict) -> None:
    _validate_global(config)
    _validate_services(config)
    _validate_lists(config)
    _validate_admin(config)
    _validate_gpu_processes(config)


def _validate_global(config: dict) -> None:
    checks = [
        (("server", "port"), int, 1, 65535),
        (("monitoring", "refresh_interval_ms"), int, 100, 60000),
        (("monitoring", "log_lines"), int, 1, 2000),
        (("monitoring", "log_block_bytes"), int, 1024, 1048576),
        (("model_detection", "cache_seconds"), int, 1, 300),
        (("model_detection", "cache_grace_seconds"), int, 1, 600),
        (("model_detection", "process_scan_interval_seconds"), int, 1, 600),
        (("thresholds", "vram_warning_percent"), int, 1, 100),
        (("thresholds", "vram_danger_percent"), int, 1, 100),
        (("thresholds", "power_warning_percent"), int, 1, 100),
        (("thresholds", "power_danger_percent"), int, 1, 100),
    ]
    for path, expected_type, minimum, maximum in checks:
        value = _safe_get_nested(config, path)
        if value is None:
            continue
        if not isinstance(value, expected_type):
            logger.warning("Invalid type for %s, using default", ".".join(path))
            set_nested(config, path, get_default(path))
            continue
        if value < minimum or value > maximum:
            logger.warning("Out of range value for %s, using default", ".".join(path))
            set_nested(config, path, get_default(path))


def _validate_services(config: dict) -> None:
    services = config.get("services", {})
    if isinstance(services, dict):
        for svc_key, svc_conf in services.items():
            if not isinstance(svc_conf, dict):
                continue
            _validate_service(config, svc_key, svc_conf)


def _validate_service(config: dict, svc_key: str, svc_conf: dict) -> None:
    if not isinstance(svc_conf.get("timeout_seconds"), (int, float)):
        svc_conf["timeout_seconds"] = 2
        logger.warning("services.%s.timeout_seconds invalid, set to 2", svc_key)
    elif svc_conf["timeout_seconds"] < 0.1:
        svc_conf["timeout_seconds"] = 2

    base_url = svc_conf.get("base_url", "")
    if base_url and not isinstance(base_url, str):
        svc_conf["base_url"] = ""
    elif base_url and not base_url.startswith(("http://", "https://")):
        logger.warning("services.%s.base_url does not start with http(s)://", svc_key)

    for ep in ("health_endpoint", "models_endpoint"):
        ep_val = svc_conf.get(ep)
        if ep_val is not None and not (isinstance(ep_val, str) and (ep_val.startswith("/") or ep_val == "")):
            svc_conf[ep] = "/health" if ep == "health_endpoint" else "/v1/models"

    jc_lines = svc_conf.get("journalctl_lines")
    if jc_lines is not None:
        if not isinstance(jc_lines, int) or jc_lines < 1:
            svc_conf["journalctl_lines"] = 50


def _validate_lists(config: dict) -> None:
    list_paths = [
        ("model_detection", "process_keywords"),
        ("model_detection", "model_arg_flags"),
    ]
    for path in list_paths:
        value = _safe_get_nested(config, path)
        if value is None:
            continue
        if not isinstance(value, list) or not value:
            logger.warning("Invalid list for %s, using default", ".".join(path))
            set_nested(config, path, get_default(path))


def _validate_admin(config: dict) -> None:
    import re
    for key in ("enabled", "allow_force_stop", "csrf_enabled"):
        value = _safe_get_nested(config, ("admin", key))
        if value is not None and not isinstance(value, bool):
            logger.warning("Invalid bool for admin.%s, using default", key)
            set_nested(config, ("admin", key), get_default(("admin", key)))
    csrf_header = _safe_get_nested(config, ("admin", "csrf_header"))
    if csrf_header is not None:
        if not isinstance(csrf_header, str) or not re.fullmatch(r"[A-Za-z0-9-]+", csrf_header):
            logger.warning("Invalid admin.csrf_header, using default")
            set_nested(config, ("admin", "csrf_header"), get_default(("admin", "csrf_header")))


def _validate_gpu_processes(config: dict) -> None:
    for key in ("enable", "show_command"):
        value = _safe_get_nested(config, ("gpu_processes", key))
        if value is not None and not isinstance(value, bool):
            logger.warning("Invalid bool for gpu_processes.%s, using default", key)
            set_nested(config, ("gpu_processes", key), get_default(("gpu_processes", key)))
    max_procs = _safe_get_nested(config, ("gpu_processes", "max_processes"))
    if max_procs is not None:
        if not isinstance(max_procs, int) or not (1 <= max_procs <= 10000):
            logger.warning("Invalid gpu_processes.max_processes, using default")
            set_nested(config, ("gpu_processes", "max_processes"), get_default(("gpu_processes", "max_processes")))


def load_config(config_path: Optional[str] = None) -> dict:
    config = deepcopy(DEFAULT_CONFIG)

    if config_path is None:
        config_path = os.environ.get(
            "DASHBOARD_CONFIG",
            os.path.join(os.path.dirname(__file__), "..", "config.yaml"),
        )

    if config_path and os.path.exists(config_path):
        if yaml is None:
            logger.warning("PyYAML not installed, ignoring %s and using defaults", config_path)
        else:
            try:
                with open(config_path, "r", encoding="utf-8") as handle:
                    data = yaml.safe_load(handle) or {}
                if isinstance(data, dict):
                    deep_update(config, data)
                    logger.info("Loaded configuration from %s", config_path)
                else:
                    logger.warning("Config file %s is not a mapping, using defaults", config_path)
            except Exception as exc:
                logger.error("Failed to load config %s: %s", config_path, exc)
    else:
        logger.info("Config file %s not found, using defaults", config_path)

    apply_env_overrides(config)
    validate_config(config)
    return config