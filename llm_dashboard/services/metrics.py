"""
Service metrics — Ollama model list and llama.cpp Prometheus metrics.

No dependency on monitor.py — takes config as a parameter.
"""

import logging

import requests as _requests

from llm_dashboard.services.detection import join_url

_logger = logging.getLogger("dashboard-llm.metrics")


def _parse_prometheus_metrics(text: str) -> dict:
    result = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        parts = stripped.rsplit(" ", 1)
        if len(parts) == 2:
            key = parts[0].split("{")[0].strip()
            try:
                result[key] = float(parts[1])
            except ValueError:
                pass
    return result


def get_ollama_models(config: dict) -> list:
    svc = config.get("services", {}).get("ollama", {})
    if not svc.get("base_url"):
        return []
    url = join_url(svc["base_url"], "/api/tags")
    timeout = svc.get("timeout_seconds", 3)
    try:
        resp = _requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json().get("models", [])
    except Exception:
        pass
    return []


def get_llama_metrics(config: dict) -> dict:
    services = config.get("services", {})
    for svc_key, svc_conf in services.items():
        if not isinstance(svc_conf, dict):
            continue
        if not svc_conf.get("base_url"):
            continue
        url = join_url(svc_conf["base_url"], "/metrics")
        try:
            resp = _requests.get(url, timeout=2)
            if resp.status_code == 200:
                return _parse_prometheus_metrics(resp.text)
        except Exception:
            continue
    return {}
