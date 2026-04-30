"""
Configuration — chargement, validation, surcharges d'environnement.

Extrait de monitor.py (Lot 2).
Fonctions pures ou quasi pures, sans dependance Flask ni GPU.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any, Optional, Union

logger = logging.getLogger("dashboard-llm.config")

# import conditionnel (PyYAML est optionnel)
try:
    import yaml
except Exception:
    yaml: Any = None  # type: ignore[no-redef]


# ============================================================================
# Configuration par defaut
# ============================================================================

DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
    },
    "monitoring": {
        "refresh_interval_ms": 1000,
        "log_file": "/var/log/launch_llm.log",
        "log_lines": 50,
        "log_block_bytes": 8192,
    },
    "services": {
        "ik_llama_cpp": {
            "name": "ik_llama.cpp",
            "base_url": "http://127.0.0.1:8080",
            "health_endpoint": "/health",
            "models_endpoint": "/v1/models",
            "timeout_seconds": 2,
            "log_file": "/var/log/launch_llm.log",
        },
        "llama_cpp": {
            "name": "llama.cpp",
            "base_url": "http://127.0.0.1:8080",
            "health_endpoint": "/health",
            "models_endpoint": "/v1/models",
            "timeout_seconds": 2,
            "log_file": "/var/log/launch_arbitrage_q8.log",
        },
        "vllm": {
            "name": "vLLM Qwen3.6-27B",
            "base_url": "http://127.0.0.1:8080",
            "health_endpoint": "/health",
            "models_endpoint": "/v1/models",
            "timeout_seconds": 2,
            "log_file": "/var/log/vllm_qwen36_27b.log",
        },
        "ollama": {
            "name": "Ollama",
            "base_url": "http://127.0.0.1:11434",
            "health_endpoint": "/",
            "timeout_seconds": 2,
            "log_type": "journalctl",
            "journalctl_unit": "ollama",
            "journalctl_lines": 50,
        },
        "voxtral": {
            "name": "Voxtral-web (TTS)",
            "base_url": "http://127.0.0.1:6060",
            "health_endpoint": "/healthz",
            "log_file": "/opt/voxtral-web/logs/voxtral-web.log",
            "timeout_seconds": 2,
        },
        "voxtral_stt": {
            "name": "Voxtral-WebUI (STT)",
            "base_url": "http://127.0.0.1:7860",
            "health_endpoint": "/",
            "timeout_seconds": 2,
            "log_file": "/root/Voxtral-WebUI/app.log",
        },
    },
    "gpu": {
        "enable": True,
    },
    "model_detection": {
        "cache_seconds": 5,
        "cache_grace_seconds": 30,
        "process_scan_interval_seconds": 30,
        "process_keywords": ["ik_llama", "server"],
        "model_arg_flags": ["-m", "--model"],
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
    "DASHBOARD_LLAMA_URL": ("services", "llama_cpp", "base_url"),
    "DASHBOARD_LLAMA_HEALTH_ENDPOINT": ("services", "llama_cpp", "health_endpoint"),
    "DASHBOARD_LLAMA_MODELS_ENDPOINT": ("services", "llama_cpp", "models_endpoint"),
    "DASHBOARD_LLAMA_TIMEOUT": ("services", "llama_cpp", "timeout_seconds"),
    "DASHBOARD_OLLAMA_URL": ("services", "ollama", "base_url"),
    "DASHBOARD_OLLAMA_HEALTH_ENDPOINT": ("services", "ollama", "health_endpoint"),
    "DASHBOARD_OLLAMA_TIMEOUT": ("services", "ollama", "timeout_seconds"),
    "DASHBOARD_OLLAMA_LOG_TYPE": ("services", "ollama", "log_type"),
    "DASHBOARD_OLLAMA_JOURNALCTL_UNIT": ("services", "ollama", "journalctl_unit"),
    "DASHBOARD_OLLAMA_JOURNALCTL_LINES": ("services", "ollama", "journalctl_lines"),
    "DASHBOARD_VLLM_URL": ("services", "vllm", "base_url"),
    "DASHBOARD_VLLM_HEALTH_ENDPOINT": ("services", "vllm", "health_endpoint"),
    "DASHBOARD_VLLM_MODELS_ENDPOINT": ("services", "vllm", "models_endpoint"),
    "DASHBOARD_VLLM_TIMEOUT": ("services", "vllm", "timeout_seconds"),
    "DASHBOARD_VLLM_LOG_FILE": ("services", "vllm", "log_file"),
    "DASHBOARD_VOXTRAL_URL": ("services", "voxtral", "base_url"),
    "DASHBOARD_VOXTRAL_HEALTH_ENDPOINT": ("services", "voxtral", "health_endpoint"),
    "DASHBOARD_VOXTRAL_LOG_FILE": ("services", "voxtral", "log_file"),
    "DASHBOARD_VOXTRAL_TIMEOUT": ("services", "voxtral", "timeout_seconds"),
    "DASHBOARD_VOXTRAL_STT_URL": ("services", "voxtral_stt", "base_url"),
    "DASHBOARD_VOXTRAL_STT_HEALTH_ENDPOINT": ("services", "voxtral_stt", "health_endpoint"),
    "DASHBOARD_VOXTRAL_STT_LOG_FILE": ("services", "voxtral_stt", "log_file"),
    "DASHBOARD_VOXTRAL_STT_TIMEOUT": ("services", "voxtral_stt", "timeout_seconds"),
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
}


# ============================================================================
# Fonctions utilitaires de configuration
# ============================================================================

def deep_update(target: dict, updates: dict) -> None:
    """Fusion recursive : updates est merge dans target (modifie en place)."""
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def parse_bool(value: Union[bool, str, int]) -> bool:
    """Parse une valeur booleenne (bool, str, int)."""
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def parse_list(value: Union[list, str]) -> list:
    """Parse une liste (list existante ou str separee par des virgules)."""
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).split(",") if item.strip()]


def get_nested(config: dict, path: tuple) -> Any:
    """Accede a une valeur imbriquee dans un dict via un chemin de tuples."""
    current = config
    for key in path:
        current = current[key]
    return current


def set_nested(config: dict, path: tuple, value: Any) -> None:
    """Definit une valeur imbriquee, en creant les dicts intermediaires."""
    current = config
    for key in path[:-1]:
        current = current.setdefault(key, {})
    current[path[-1]] = value


def get_default(path: tuple) -> Any:
    """Retourne la valeur par defaut pour un chemin de config donne."""
    return get_nested(DEFAULT_CONFIG, path)


# ============================================================================
# Chargement et validation
# ============================================================================

def apply_env_overrides(config: dict) -> None:
    """Applique les surcharges de variables d'environnement sur la config."""
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


def validate_config(config: dict) -> None:
    """Valide la configuration et remplace les valeurs invalides par les defauts."""
    checks = [
        (("server", "port"), int, 1, 65535),
        (("monitoring", "refresh_interval_ms"), int, 100, 60000),
        (("monitoring", "log_lines"), int, 1, 2000),
        (("monitoring", "log_block_bytes"), int, 1024, 1048576),
        (("services", "ik_llama_cpp", "timeout_seconds"), (int, float), 0.1, 60),
        (("services", "llama_cpp", "timeout_seconds"), (int, float), 0.1, 60),
        (("services", "vllm", "timeout_seconds"), (int, float), 0.1, 60),
        (("services", "ollama", "timeout_seconds"), (int, float), 0.1, 60),
        (("services", "ollama", "journalctl_lines"), int, 1, 500),
        (("services", "voxtral", "timeout_seconds"), (int, float), 0.1, 60),
        (("services", "voxtral_stt", "timeout_seconds"), (int, float), 0.1, 60),
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

    _validate_urls(config)
    _validate_endpoints(config)
    _validate_lists(config)
    _validate_admin(config)
    _validate_gpu_processes(config)


def _safe_get_nested(config: dict, path: tuple) -> Optional[Any]:
    """get_nested qui retourne None si le chemin n'existe pas (pour validation)."""
    try:
        return get_nested(config, path)
    except (KeyError, TypeError):
        return None


def _validate_urls(config: dict) -> None:
    """Valide les URLs de base des services."""
    url_paths = [
        ("services", "ik_llama_cpp", "base_url"),
        ("services", "llama_cpp", "base_url"),
        ("services", "ollama", "base_url"),
        ("services", "voxtral", "base_url"),
        ("services", "vllm", "base_url"),
        ("services", "voxtral_stt", "base_url"),
    ]
    for path in url_paths:
        value = _safe_get_nested(config, path)
        if value is None:
            continue
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            logger.warning("Invalid URL for %s, using default", ".".join(path))
            set_nested(config, path, get_default(path))


def _validate_endpoints(config: dict) -> None:
    """Valide les health/model endpoints (doivent commencer par /)."""
    endpoint_paths = [
        ("services", "ik_llama_cpp", "health_endpoint"),
        ("services", "ik_llama_cpp", "models_endpoint"),
        ("services", "llama_cpp", "health_endpoint"),
        ("services", "llama_cpp", "models_endpoint"),
        ("services", "ollama", "health_endpoint"),
        ("services", "vllm", "health_endpoint"),
        ("services", "vllm", "models_endpoint"),
        ("services", "voxtral", "health_endpoint"),
        ("services", "voxtral_stt", "health_endpoint"),
    ]
    for path in endpoint_paths:
        value = _safe_get_nested(config, path)
        if value is None:
            continue
        if not isinstance(value, str) or not value.startswith("/"):
            logger.warning("Invalid endpoint for %s, using default", ".".join(path))
            set_nested(config, path, get_default(path))


def _validate_lists(config: dict) -> None:
    """Valide les champs de type liste."""
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
    """Valide la section admin."""
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
    """Valide la section gpu_processes."""
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
    """Charge la configuration depuis un fichier YAML, avec surcharges env.

    Args:
        config_path: chemin vers config.yaml. Si None, utilise DASHBOARD_CONFIG
                     ou le defaut (/opt/dashboard-llm/config.yaml).

    Returns:
        dict: configuration complete, fusionnee avec les defaults et validee.
    """
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
