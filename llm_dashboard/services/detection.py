"""
Service detection — identification de service actif, modeles, groupes exclusifs.

Les fonctions de detection sont pilotees par la config. Aucun port, backend,
modele ou pattern de processus n'est hardcode.
"""

from __future__ import annotations

import logging
import os as _os
import psutil as _psutil
import requests as _requests
import time as _time
import re as _re

from llm_dashboard.services.health import check_port_is_open, check_service_health

_logger = logging.getLogger("dashboard-llm.detection")


def join_url(base_url: str, endpoint: str) -> str:
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


def match_model(model_name: str | None, pattern: str | None) -> bool:
    if not pattern or not model_name:
        return False
    return bool(_re.search(pattern, model_name))


def guess_service_from_model(
    model_name: str | None,
    services: list,
) -> str | None:
    if not model_name:
        return None
    for svc in services:
        if svc.models_endpoint and svc.model_detect_pattern:
            if match_model(model_name, svc.model_detect_pattern):
                return svc.key
    return None


# ============================================================================
# Detection de processus generique (pilotee par config)
# ============================================================================

def find_process_for_service(svc) -> dict | None:
    """Trouve un processus correspondant aux patterns de processus du service.

    Args:
        svc: ServiceConfig avec process_patterns et process_exclude_patterns

    Returns:
        dict de proc.info ou None
    """
    patterns = svc.process_patterns
    excludes = svc.process_exclude_patterns
    pid_file = svc.pid_file

    if pid_file and _os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid_str = f.read().strip()
            if pid_str:
                pid = int(pid_str)
                if _psutil.pid_exists(pid):
                    return {'pid': pid, 'create_time': _psutil.Process(pid).create_time()}
        except Exception:
            pass

    if not patterns:
        return None

    try:
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline = proc.info.get('cmdline') or []
            cmdline_str = ' '.join(cmdline)
            if any(p in cmdline_str for p in patterns):
                if excludes and any(e in cmdline_str for e in excludes):
                    continue
                return proc.info
    except Exception as exc:
        _logger.debug("Failed to scan for process (patterns=%s): %s", patterns, exc)
    return None


def find_ik_llama_process():
    """Compatibilite retroactive pour les tests et appels existants.
    Cherche les processus ik_llama.cpp generiquement.
    """
    try:
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline_str = ' '.join(proc.info.get('cmdline') or [])
            if 'ik_llama' in cmdline_str or ('llama-server' in cmdline_str and 'GLM' in cmdline_str):
                return proc.info
    except Exception:
        pass
    return None


def find_llama_process():
    """Compatibilite retroactive — cherche llama-server sans ik_llama ni GLM."""
    try:
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline_str = ' '.join(proc.info.get('cmdline') or [])
            if ('llama-server' in cmdline_str
                    and 'ik_llama' not in cmdline_str
                    and 'GLM' not in cmdline_str):
                return proc.info
    except Exception:
        pass
    return None


def find_vllm_process(config=None):
    """Cherche un processus vLLM (via pid_file ou scan de processus)."""
    pid_file = ""
    if config:
        pid_file = config.get("paths", {}).get("vllm_pid_file", "")
    if pid_file and _os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            if _psutil.pid_exists(pid):
                return {'pid': pid, 'create_time': _psutil.Process(pid).create_time()}
        except Exception:
            pass
    try:
        for proc in _psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline_str = ' '.join(proc.info.get('cmdline') or [])
            name = proc.info.get('name') or ''
            if ('vllm serve' in cmdline_str) or ('VLLM::EngineCore' in name):
                return proc.info
    except Exception:
        pass
    return None


# ============================================================================
# Detection de modele
# ============================================================================

def detect_model_name(config: dict, model_cache: dict) -> str:
    model_name = None
    now = _time.time()
    cache_grace_seconds = config["model_detection"]["cache_grace_seconds"]

    if model_cache['name'] and now - model_cache['last_check'] < config["model_detection"]["cache_seconds"]:
        _logger.debug("detect_model_name: returning cached name=%s", model_cache['name'])
        return model_cache['name']

    # Essayer /v1/models sur tous les services configures qui ont l'endpoint
    services = config.get("services", {})
    for svc_key, svc_conf in services.items():
        if not svc_conf.get("models_endpoint"):
            continue
        try:
            url = join_url(svc_conf["base_url"], svc_conf["models_endpoint"])
            timeout = min(svc_conf.get("timeout_seconds", 2), 2)
            resp = _requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data and len(data['data']) > 0:
                    model_name = data['data'][0].get('id', '')
                    _logger.info("detect_model_name: found %s from %s", model_name, svc_key)
                    break
        except Exception:
            continue

    model_cache['last_check'] = now

    # Fallback: scan de processus
    if not model_name and now - model_cache.get('last_process_scan', 0) >= config["model_detection"]["process_scan_interval_seconds"]:
        _logger.info("detect_model_name: scanning processes")
        try:
            for proc in _psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    keywords = config["model_detection"]["process_keywords"]
                    flags = config["model_detection"]["model_arg_flags"]
                    if cmdline and any(keyword in c for c in cmdline for keyword in keywords):
                        for i, arg in enumerate(cmdline):
                            if arg in flags and i + 1 < len(cmdline):
                                model_name = cmdline[i + 1]
                                _logger.info("detect_model_name: found from process %d: %s",
                                             proc.info['pid'], model_name)
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
        return model_name

    if model_cache['name']:
        if now - model_cache['last_check'] > cache_grace_seconds:
            model_cache['name'] = None
            return 'Checking...'
        return model_cache['name']

    return 'Unknown'


# ============================================================================
# Service status — base sur les groupes exclusifs
# ============================================================================

def get_services_status(config: dict, command_runner=None) -> dict:
    """Retourne le statut de tous les services, avec gestion des groupes exclusifs.

    Pour chaque groupe exclusif, un seul service peut etre UP.
    La detection utilise /v1/models pour identifier le service actif.
    """
    services = config.get("services", {})
    service_statuses = {}
    group_active = {}       # group_name -> active_service_key
    group_models = {}       # group_name -> model_id on that port
    group_latencies = {}    # group_name -> latency
    group_slots = {}        # group_name -> (slots_active, slots_total)

    # Construire la liste des groupes exclusifs
    groups = {}
    for svc_key, svc_conf in services.items():
        grp = svc_conf.get("exclusive_group") if isinstance(svc_conf, dict) else None
        if grp:
            groups.setdefault(grp, []).append(svc_key)

    # Pour chaque groupe, trouver le service actif
    for grp_name, member_keys in groups.items():
        if not member_keys:
            continue
        ref_svc = services[member_keys[0]]
        port = ref_svc.get("port") or _extract_port(ref_svc.get("base_url", ""))

        if port and check_port_is_open("127.0.0.1", port, timeout=1):
            # Port ouvert — interroger /v1/models pour identifier le service
            models_ep = ref_svc.get("models_endpoint", "/v1/models")
            base_url = ref_svc.get("base_url", "")
            model_id = None
            if base_url and models_ep:
                try:
                    url = join_url(base_url, models_ep)
                    resp = _requests.get(url, timeout=2)
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'data' in data and len(data['data']) > 0:
                            model_id = data['data'][0].get('id', '')
                except Exception:
                    pass

            # Trouver quel membre du groupe correspond au modele detecte
            active_key = None
            for key in member_keys:
                svc = services[key]
                pattern = svc.get("model_detect_pattern") if isinstance(svc, dict) else None
                if model_id and pattern and match_model(model_id, pattern):
                    active_key = key
                    break

            # Fallback: utiliser la detection de processus
            if not active_key:
                for key in member_keys:
                    svc = services[key]
                    if isinstance(svc, dict):
                        proc_patterns = svc.get("process_patterns", [])
                        for proc in _psutil.process_iter(['cmdline']):
                            cmd = ' '.join(proc.info.get('cmdline') or [])
                            if any(p in cmd for p in proc_patterns):
                                active_key = key
                                break
                    if active_key:
                        break

            # Fallback final: premier membre
            if not active_key:
                active_key = member_keys[0]

            # Health check du service actif
            active_conf = services.get(active_key, services.get(member_keys[0], {}))
            health_ep = active_conf.get("health_endpoint", "/health")
            timeout_s = active_conf.get("timeout_seconds", 2)

            status = 'DOWN'
            latency = None
            slots_active = None
            slots_total = None

            if base_url:
                try:
                    url = join_url(base_url, health_ep)
                    start = _time.time()
                    resp = _requests.get(url, timeout=timeout_s)
                    latency = _time.time() - start
                    if resp.status_code < 400:
                        status = 'UP'
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            sp = data.get('slots_processing')
                            si = data.get('slots_idle')
                            if isinstance(sp, int) and isinstance(si, int):
                                slots_active = sp
                                slots_total = sp + si
                        except Exception:
                            pass
                except Exception:
                    pass

            group_active[grp_name] = active_key
            group_models[grp_name] = model_id
            group_latencies[grp_name] = latency
            group_slots[grp_name] = (slots_active, slots_total)

            # Tous les membres du groupe: DOWN sauf celui actif
            for key in member_keys:
                svc_conf = services[key]
                name = (svc_conf.get("name", key) if isinstance(svc_conf, dict) else key)
                service_statuses[name] = status if key == active_key else 'DOWN'
        else:
            # Port ferme — verifier si un processus tourne (LOADING)
            for key in member_keys:
                svc_conf = services[key]
                name = (svc_conf.get("name", key) if isinstance(svc_conf, dict) else key)
                proc_pats = svc_conf.get("process_patterns", []) if isinstance(svc_conf, dict) else []
                proc_excl = svc_conf.get("process_exclude_patterns", []) if isinstance(svc_conf, dict) else []
                has_proc = False
                if proc_pats:
                    for proc in _psutil.process_iter(['cmdline']):
                        cmd = ' '.join(proc.info.get('cmdline') or [])
                        if any(p in cmd for p in proc_pats):
                            if proc_excl and any(e in cmd for e in proc_excl):
                                continue
                            has_proc = True
                            break
                service_statuses[name] = 'LOADING' if has_proc else 'DOWN'

    # Services hors groupe (independants)
    for svc_key, svc_conf in services.items():
        if not isinstance(svc_conf, dict):
            continue
        grp = svc_conf.get("exclusive_group")
        if grp:
            continue  # deja traite dans les groupes
        name = svc_conf.get("name", svc_key)
        base_url = svc_conf.get("base_url", "")
        health_ep = svc_conf.get("health_endpoint", "/health")
        timeout_s = svc_conf.get("timeout_seconds", 2)

        if base_url:
            try:
                status, _ = check_service_health(base_url, health_ep, timeout_s)
                service_statuses[name] = status
            except Exception:
                service_statuses[name] = 'DOWN'
        else:
            service_statuses[name] = 'DOWN'

    # Latence globale (pour compatibilite) — utilise le premier groupe actif
    active_on_8080 = None
    model_on_8080 = None
    primary_group = next(iter(group_active), None)
    if primary_group:
        active_on_8080 = group_active[primary_group]
        model_on_8080 = group_models.get(primary_group)

    return {
        'services': service_statuses,
        'llama_latency_seconds': group_latencies.get(primary_group),
        'slots_active': group_slots.get(primary_group, (None, None))[0],
        'slots_total': group_slots.get(primary_group, (None, None))[1],
        'active_on_8080': active_on_8080,
        'model_on_8080': model_on_8080,
        'active_services': group_active,
        'models_by_group': group_models,
    }


def get_admin_services_status(config: dict, command_runner) -> dict:
    s = get_services_status(config, command_runner)
    health_statuses = s.get("services", {})
    active_on_8080 = s.get("active_on_8080")
    status = {}

    for key, conf in config.get("services", {}).items():
        if not isinstance(conf, dict):
            continue
        role = conf.get("role", "auxiliary")
        port = conf.get("port") or _extract_port(conf.get("base_url", ""))
        grp = conf.get("exclusive_group")
        name = conf.get("name", key)

        running = False
        if role == "llm" and grp:
            running = (active_on_8080 == key)
        else:
            running = _systemd_is_active(conf, command_runner)

        status[key] = {
            "key": key,
            "display_name": name,
            "role": role,
            "backend": conf.get("backend", ""),
            "port": port or 0,
            "running": running,
            "health": health_statuses.get(name, "DOWN"),
            "unit": conf.get("systemd_unit", ""),
            "exclusive_group": grp,
        }
    return status


def _systemd_is_active(svc_conf: dict, command_runner) -> bool:
    unit = svc_conf.get("systemd_unit", "")
    if not unit:
        return False
    try:
        result = command_runner.systemctl_is_active(unit, timeout=3)
        return result.stdout.strip() in ("active", "activating")
    except Exception:
        return False


def _extract_port(base_url):
    if not base_url:
        return None
    try:
        return int(base_url.rsplit(":", 1)[-1].rstrip("/"))
    except (ValueError, IndexError):
        return None