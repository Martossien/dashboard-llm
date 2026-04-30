"""
Service detection — identification du modele actif et du service sur un port.
"""

from __future__ import annotations

import logging
import os as _os
import psutil as _psutil
import requests as _requests
import time as _time

from llm_dashboard.services.health import check_port_is_open, check_service_health

_logger = logging.getLogger("dashboard-llm.detection")


def join_url(base_url: str, endpoint: str) -> str:
    """Concatene une base_url et un endpoint en gerant les slashes.

    >>> join_url("http://127.0.0.1:8080", "/health")
    'http://127.0.0.1:8080/health'
    >>> join_url("http://127.0.0.1:8080/", "health")
    'http://127.0.0.1:8080/health'
    """
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


def match_model(model_name: str | None, pattern: str | None) -> bool:
    """Verifie si un nom de modele correspond a un pattern de detection."""
    if not pattern or not model_name:
        return False
    import re
    return bool(re.search(pattern, model_name))


def guess_service_from_model(
    model_name: str | None,
    services: list,
) -> str | None:
    """Determine quelle cle de service correspond au nom de modele detecte."""
    if not model_name:
        return None
    for svc in services:
        if svc.models_endpoint and svc.model_detect_pattern:
            if match_model(model_name, svc.model_detect_pattern):
                return svc.key
    return None


def find_ik_llama_process() -> dict | None:
    try:
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline)
            if 'ik_llama' in cmdline_str or ('llama-server' in cmdline_str and 'GLM' in cmdline_str):
                return proc.info
    except Exception as exc:
        _logger.debug("Failed to scan for ik_llama process: %s", exc)
    return None


def find_llama_process() -> dict | None:
    try:
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline)
            if 'llama-server' in cmdline_str and 'ik_llama' not in cmdline_str and 'GLM' not in cmdline_str:
                return proc.info
    except Exception as exc:
        _logger.debug("Failed to scan for llama-server process: %s", exc)
    return None


def find_vllm_process() -> dict | None:
    try:
        if _os.path.exists("/root/.vllm_qwen36_27b.pid"):
            with open("/root/.vllm_qwen36_27b.pid", "r") as f:
                pid_str = f.read().strip()
            if pid_str:
                pid = int(pid_str)
                if _psutil.pid_exists(pid):
                    return {'pid': pid, 'create_time': _psutil.Process(pid).create_time()}
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline = proc.info.get('cmdline') or []
            if any('vllm serve' in ' '.join(cmdline)) or any('VLLM::EngineCore' in (proc.info.get('name') or '')):
                return proc.info
    except Exception as exc:
        _logger.debug("Failed to scan for vllm process: %s", exc)
    return None


def detect_model_name(config: dict, model_cache: dict) -> str:
    """Detecte le nom du modele actif. Prend config et model_cache en parametres."""
    model_name = None
    now = _time.time()
    cache_grace_seconds = config["model_detection"]["cache_grace_seconds"]
    if model_cache['name'] and now - model_cache['last_check'] < config["model_detection"]["cache_seconds"]:
        _logger.debug("detect_model_name: returning cached name=%s", model_cache['name'])
        return model_cache['name']
    try:
        if find_ik_llama_process() is not None:
            svc_key = 'ik_llama_cpp'
        elif find_llama_process() is not None:
            svc_key = 'llama_cpp'
        else:
            svc_key = 'ik_llama_cpp'
        svc_conf = config["services"].get(svc_key, config["services"]["ik_llama_cpp"])
        url = join_url(svc_conf["base_url"], svc_conf["models_endpoint"])
        timeout_seconds = svc_conf["timeout_seconds"]
        _logger.info("detect_model_name: querying %s (timeout=%.1fs)", url, min(timeout_seconds, 1.0))
        response = _requests.get(url, timeout=min(timeout_seconds, 1.0))
        _logger.info("detect_model_name: response status=%d", response.status_code)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                model_name = data['data'][0].get('id', None)
                _logger.info("detect_model_name: found model from API: %s", model_name)
            else:
                _logger.info("detect_model_name: API returned 200 but no model data")
        else:
            _logger.info("detect_model_name: API returned status %d", response.status_code)
    except _requests.exceptions.Timeout:
        _logger.warning("detect_model_name: API request timed out")
    except _requests.exceptions.ConnectionError as e:
        _logger.info("detect_model_name: connection error: %s", e)
    except Exception as e:
        _logger.warning("detect_model_name: error: %s", e)
    finally:
        model_cache['last_check'] = now

    if not model_name and now - model_cache['last_process_scan'] >= config["model_detection"]["process_scan_interval_seconds"]:
        _logger.info("detect_model_name: scanning processes (keywords=%s)", config["model_detection"]["process_keywords"])
        try:
            for proc in _psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    keywords = config["model_detection"]["process_keywords"]
                    if cmdline and any(keyword in c for c in cmdline for keyword in keywords):
                        for i, arg in enumerate(cmdline):
                            if arg in config["model_detection"]["model_arg_flags"] and i + 1 < len(cmdline):
                                model_name = cmdline[i + 1]
                                _logger.info("detect_model_name: found model from process %d: %s", proc.info['pid'], model_name)
                                break
                        if model_name:
                            break
                except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                    continue
        except Exception as e:
            _logger.warning("detect_model_name: process scan error: %s", e)
        model_cache['last_process_scan'] = now

    if model_name:
        model_cache['name'] = model_name
        model_cache['last_check'] = now
        _logger.info("detect_model_name: final result: %s", model_name)
        return model_name
    if model_cache['name']:
        if now - model_cache['last_check'] > cache_grace_seconds:
            _logger.info("detect_model_name: grace period expired, clearing cache")
            model_cache['name'] = None
            return 'Checking...'
        _logger.debug("detect_model_name: returning grace-cached name=%s", model_cache['name'])
        return model_cache['name']
    _logger.info("detect_model_name: no model found, returning Unknown")
    return 'Unknown'


def _get_active_llama_key(config: dict, command_runner) -> str:
    try:
        url = join_url(
            config["services"]["llama_cpp"]["base_url"],
            config["services"]["llama_cpp"]["models_endpoint"],
        )
        response = _requests.get(url, timeout=1.0)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                model_id = data['data'][0].get('id', '').lower()
                if 'glm' in model_id or 'ik_llama' in model_id:
                    return 'ik_llama_cpp'
                return 'llama_cpp'
    except Exception:
        pass
    if find_ik_llama_process() is not None:
        return 'ik_llama_cpp'
    for svc_key in ['qwen36_35b_q8', 'qwen36_35b_udq8']:
        systemd_unit = config.get("start_stop", {}).get(svc_key, {}).get("systemd_unit", "")
        if systemd_unit:
            try:
                result = command_runner.systemctl_is_active(systemd_unit, timeout=3)
                if result.stdout.strip() == "active":
                    return 'llama_cpp'
            except Exception:
                pass
    if find_llama_process() is not None:
        return 'llama_cpp'
    return 'llama_cpp'


def get_llama_status(config: dict, command_runner) -> tuple[str, float | None, int | None, int | None]:
    status = 'DOWN'
    latency = None
    slots_active = None
    slots_total = None
    svc_key = _get_active_llama_key(config, command_runner) if check_port_is_open("127.0.0.1", 8080, timeout=1) else 'ik_llama_cpp'
    svc_conf = config["services"].get(svc_key, config["services"]["ik_llama_cpp"])
    try:
        url = join_url(svc_conf["base_url"], svc_conf["health_endpoint"])
        timeout_seconds = svc_conf["timeout_seconds"]
        start = _time.time()
        response = _requests.get(url, timeout=timeout_seconds)
        latency = _time.time() - start
        if response.status_code < 400:
            status = 'UP'
        if response.status_code == 200:
            data = response.json()
            slots_processing = data.get('slots_processing')
            slots_idle = data.get('slots_idle')
            if isinstance(slots_processing, int) and isinstance(slots_idle, int):
                slots_active = slots_processing
                slots_total = slots_processing + slots_idle
    except Exception as e:
        _logger.debug("get_llama_status error: %s", e)
    return status, latency, slots_active, slots_total


def get_services_status(config: dict, command_runner) -> dict:
    port_8080_status, port_8080_latency, slots_active, slots_total = get_llama_status(config, command_runner)
    model_on_8080 = None
    active_on_8080 = None

    if port_8080_status == 'UP':
        try:
            url = join_url(
                config["services"]["llama_cpp"]["base_url"],
                config["services"]["llama_cpp"]["models_endpoint"],
            )
            response = _requests.get(url, timeout=1.0)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    model_on_8080 = data['data'][0].get('id', '')
        except Exception:
            pass

    has_ik_llama = find_ik_llama_process() is not None
    has_llama = find_llama_process() is not None
    has_vllm = find_vllm_process() is not None

    if port_8080_status == 'UP':
        if has_vllm or (model_on_8080 and 'qwen36' in model_on_8080.lower() and 'ik_llama' not in model_on_8080.lower() and 'glm' not in model_on_8080.lower()):
            active_on_8080 = 'vllm'
        elif has_ik_llama and (model_on_8080 is None or 'glm' in model_on_8080.lower() or 'ik_llama' in model_on_8080.lower()):
            active_on_8080 = 'ik_llama_cpp'
        elif model_on_8080 and ('glm' in model_on_8080.lower() or 'ik_llama' in model_on_8080.lower()):
            active_on_8080 = 'ik_llama_cpp'
        elif has_llama or model_on_8080:
            active_on_8080 = 'llama_cpp'
        else:
            active_on_8080 = 'llama_cpp'
    else:
        if has_vllm:
            active_on_8080 = 'vllm'
        elif has_ik_llama:
            active_on_8080 = 'ik_llama_cpp'
        elif has_llama:
            active_on_8080 = 'llama_cpp'

    if active_on_8080 == 'vllm':
        ik_llama_status = 'DOWN'
        llama_status = 'DOWN'
        vllm_status = port_8080_status
    elif active_on_8080 == 'ik_llama_cpp':
        ik_llama_status = port_8080_status
        llama_status = 'DOWN'
        vllm_status = 'DOWN'
    elif active_on_8080 == 'llama_cpp':
        ik_llama_status = 'DOWN'
        llama_status = port_8080_status
        vllm_status = 'DOWN'
    else:
        ik_llama_status = 'LOADING' if has_ik_llama else 'DOWN'
        llama_status = 'LOADING' if has_llama else 'DOWN'
        vllm_status = 'LOADING' if has_vllm else 'DOWN'

    if active_on_8080 not in ('ik_llama_cpp', 'llama_cpp'):
        port_8080_latency = None
        slots_active = None
        slots_total = None

    ollama_status, _ = check_service_health(
        config["services"]["ollama"]["base_url"],
        config["services"]["ollama"]["health_endpoint"],
        config["services"]["ollama"]["timeout_seconds"],
    )

    voxtral_status, _ = check_service_health(
        config["services"]["voxtral"]["base_url"],
        config["services"]["voxtral"]["health_endpoint"],
        config["services"]["voxtral"]["timeout_seconds"],
    )

    voxtral_stt_status, _ = check_service_health(
        config["services"]["voxtral_stt"]["base_url"],
        config["services"]["voxtral_stt"]["health_endpoint"],
        config["services"]["voxtral_stt"]["timeout_seconds"],
    )

    return {
        'services': {
            config["services"]["ik_llama_cpp"]["name"]: ik_llama_status,
            config["services"]["llama_cpp"]["name"]: llama_status,
            config["services"]["vllm"]["name"]: vllm_status,
            config["services"]["ollama"]["name"]: ollama_status,
            config["services"]["voxtral"]["name"]: voxtral_status,
            config["services"]["voxtral_stt"]["name"]: voxtral_stt_status,
        },
        'llama_latency_seconds': port_8080_latency,
        'slots_active': slots_active,
        'slots_total': slots_total,
        'active_on_8080': active_on_8080,
        'model_on_8080': model_on_8080,
    }


def check_service_is_running(svc_conf: dict, command_runner) -> bool:
    cmd = svc_conf.get("service_check", ["systemctl", "is-active", "unknown.service"])
    try:
        if len(cmd) >= 3 and cmd[0] == "systemctl" and cmd[1] == "is-active":
            result = command_runner.systemctl_is_active(cmd[2], timeout=3)
            if result.stdout.strip() in ("active", "activating"):
                return True
    except Exception:
        pass
    url = svc_conf.get("base_url")
    timeout = svc_conf.get("timeout_seconds", 2)
    endpoint = svc_conf.get("health_endpoint", "/")
    if url:
        status, _ = check_service_health(url, endpoint, min(timeout, 2))
        if status == "UP":
            return True
    port = svc_conf.get("port", 0)
    if port and check_port_is_open("127.0.0.1", port, timeout=1):
        return True
    return False


def get_admin_services_status(config: dict, command_runner) -> dict:
    try:
        s = get_services_status(config, command_runner)
    except Exception as exc:
        _logger.error("get_services_status() failed in admin: %s", exc)
        s = {}
    active_on_8080 = s.get("active_on_8080")
    model_on_8080 = s.get("model_on_8080", "")
    status = {}
    for key, conf in config.get("start_stop", {}).items():
        is_llm = conf.get("is_llm", False)
        port = conf.get("port", 0)
        running = False
        if is_llm and port == 8080:
            if active_on_8080 == 'llama_cpp':
                if key == 'glm47':
                    if not model_on_8080 or model_on_8080.lower() == 'glm-4.7-iq5':
                        running = True
                elif key == 'qwen36_35b_q8':
                    if model_on_8080 and 'qwen3-35b-arbitrage' in model_on_8080.lower() and 'q8' in model_on_8080.lower() and 'ud' not in model_on_8080.lower():
                        running = True
                elif key == 'qwen36_35b_udq8':
                    if model_on_8080 and 'qwen3-35b-arbitrage' in model_on_8080.lower() and 'ud-q8' in model_on_8080.lower():
                        running = True
            elif active_on_8080 == 'vllm':
                if key == 'qwen36_27b_vllm':
                    running = True
        else:
            running = check_service_is_running(conf, command_runner)
        status[key] = {
            "key": key,
            "display_name": conf.get("display_name", key),
            "is_llm": is_llm,
            "port": port,
            "running": running,
            "unit": conf.get("systemd_unit", ""),
        }
    return status



