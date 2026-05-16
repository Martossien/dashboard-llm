"""
Token rate monitors — extraction via Prometheus /metrics endpoint.

Chaque backend LLM expose /metrics en format Prometheus.
Priorite /metrics > fallback logs. Fonctionne pour vLLM, llama.cpp,
ik_llama.cpp, sglang. Ollama n'a pas /metrics.
"""

import logging
import os
import re
import time

import requests as _requests

from llm_dashboard.services.detection import join_url

logger = logging.getLogger("dashboard-llm.monitors.timings")

# Cache par service
_TIMINGS_CACHE = {}
_CACHE_TTL_SECONDS = 120


def _extract_rates_from_metrics(metrics: dict) -> tuple[float | None, float | None]:
    """Extrait prompt/generation token rates d'un dict de metriques Prometheus.

    Les cles varient selon le backend :
    - vLLM: utilise _estimate_vllm_rates() qui calcule les tok/s depuis les
      metriques de latence et les compteurs de tokens.
    - llama.cpp: n_tokens_second (global), llama_tokens_second
    - sglang: sglang:prompt_throughput / sglang:generation_throughput

    Les metriques _created (timestamps Prometheus) et _total (compteurs absolus)
    sont exclues de la capture directe car ce ne sont pas des taux.
    """
    is_vllm = any(k.startswith("vllm:") for k in metrics)

    if is_vllm:
        prompt, gen = _estimate_vllm_rates(metrics)
        if prompt is not None or gen is not None:
            return prompt, gen

    prompt = None
    gen = None
    for key, val in metrics.items():
        k = key.lower()
        if not isinstance(val, (int, float)) or val <= 0:
            continue
        if k.endswith("_created") or k.endswith("_total"):
            continue
        if "prompt" in k and ("throughput" in k or "tok" in k or "token" in k):
            if prompt is None:
                prompt = float(val)
        elif "generation" in k and ("throughput" in k or "tok" in k or "token" in k):
            if gen is None:
                gen = float(val)
        elif "n_tokens_second" in k:
            if "prompt" not in k and "gen" not in k:
                if gen is None:
                    gen = float(val)

    return prompt, gen


def _estimate_vllm_rates(metrics: dict) -> tuple[float | None, float | None]:
    """Estime les token/s vLLM depuis les metriques de request si les throughput ne sont pas disponibles.

    Utilise vllm:e2e_request_latency_seconds_sum/count pour le temps total,
    et vllm:prompt_tokens_total / vllm:generation_tokens_total pour les tokens.
    """
    prompt_total = metrics.get("vllm:prompt_tokens_total")
    gen_total = metrics.get("vllm:generation_tokens_total") or metrics.get("vllm:request_generation_tokens_sum")
    e2e_sum = metrics.get("vllm:e2e_request_latency_seconds_sum")
    e2e_count = metrics.get("vllm:e2e_request_latency_seconds_count")
    ttft_sum = metrics.get("vllm:time_to_first_token_seconds_sum")

    gen_count = metrics.get("vllm:generation_tokens_total") or metrics.get("vllm:request_generation_tokens_sum")

    prompt_rate = None
    gen_rate = None

    if e2e_sum and e2e_count and e2e_count > 0:
        total_elapsed = e2e_sum
        decode_time = total_elapsed
        if ttft_sum and ttft_sum > 0 and ttft_sum < total_elapsed:
            decode_time = total_elapsed - ttft_sum
        if gen_total and decode_time > 0:
            gen_rate = gen_total / decode_time
        if prompt_total and ttft_sum and ttft_sum > 0:
            prompt_rate = prompt_total / ttft_sum

    return prompt_rate, gen_rate


def _extract_rates_from_logs(log_file: str, backend: str,
                              max_lines: int = 50, block_size: int = 8192) -> tuple[float | None, float | None]:
    """Fallback : extraction des token rates depuis les logs."""
    from llm_dashboard.monitors.logs import tail_log_lines

    if not log_file or not os.path.exists(log_file):
        return None, None

    try:
        lines = tail_log_lines(log_file, max_lines, block_size)
    except Exception:
        return None, None

    if backend in ("llama.cpp", "ik_llama.cpp"):
        return _extract_llama_from_loglines(lines)
    elif backend == "vllm":
        return _extract_vllm_from_loglines(lines)

    return None, None


def _extract_llama_from_loglines(lines) -> tuple[float | None, float | None]:
    prompt_rate = None
    generation_rate = None
    for line in reversed(lines):
        line_lower = line.lower()
        if "n_tokens_second" in line_lower:
            match = re.search(r"n_tokens_second=([\d.]+)", line_lower)
            if match:
                generation_rate = float(match.group(1))
                break
    for line in reversed(lines):
        line_lower = line.lower()
        m = re.search(r"(\d+(?:\.\d+)?)\s+(?:tok(?:ens?)?\s+per\s+sec(?:ond)?|t/s|tokens/s|tok/s)", line_lower)
        if m:
            val = float(m.group(1))
            if "prompt" in line_lower or "sampling" in line_lower:
                prompt_rate = val if prompt_rate is None else prompt_rate
            elif "generation" in line_lower or "predict" in line_lower:
                generation_rate = val if generation_rate is None else generation_rate
            elif generation_rate is None:
                generation_rate = val
        if prompt_rate is not None and generation_rate is not None:
            break
    return prompt_rate, generation_rate


def _extract_vllm_from_loglines(lines) -> tuple[float | None, float | None]:
    vllm_pattern = re.compile(
        r'Avg prompt throughput:\s*([\d.]+)\s*tokens/s,\s*Avg generation throughput:\s*([\d.]+)\s*tokens/s'
    )
    for line in reversed(lines):
        match = vllm_pattern.search(line)
        if match:
            p = float(match.group(1))
            g = float(match.group(2))
            return (p if p > 0.5 else None, g if g > 0.5 else None)
    return None, None


def get_services_token_rates(config: dict) -> dict:
    """Interroge /metrics pour chaque service, extrait les taux de tokens.

    Returns:
        {svc_key: {"prompt": float|None, "generation": float|None}}
    """
    global _TIMINGS_CACHE
    rates = {}
    now = time.time()

    for svc_key, svc_conf in config.get("services", {}).items():
        if not isinstance(svc_conf, dict):
            continue
        base_url = svc_conf.get("base_url", "")
        if not base_url:
            continue

        prompt_rate = None
        gen_rate = None

        # 1) Prometheus /metrics
        try:
            url = join_url(base_url, "/metrics")
            resp = _requests.get(url, timeout=2)
            if resp.status_code == 200:
                from llm_dashboard.services.metrics import _parse_prometheus_metrics
                parsed = _parse_prometheus_metrics(resp.text)
                prompt_rate, gen_rate = _extract_rates_from_metrics(parsed)
        except Exception:
            pass

        # 2) Fallback logs
        if prompt_rate is None and gen_rate is None:
            backend = svc_conf.get("backend", "")
            log_file = svc_conf.get("log_file", "")
            if backend and log_file:
                lines = config["monitoring"]["log_lines"]
                try:
                    prompt_rate, gen_rate = _extract_rates_from_logs(log_file, backend, lines)
                except Exception:
                    pass

        if prompt_rate or gen_rate:
            _TIMINGS_CACHE[svc_key] = {
                "prompt": prompt_rate,
                "generation": gen_rate,
                "last_update": now,
            }

        cached = _TIMINGS_CACHE.get(svc_key)
        if cached and (now - cached.get("last_update", 0)) < _CACHE_TTL_SECONDS:
            rates[svc_key] = cached
        elif cached:
            del _TIMINGS_CACHE[svc_key]

    return rates


# Backward compatibility: keep old function signatures for runtime.py
def get_llama_timings(config: dict, get_log_file_fn) -> tuple[float | None, float | None]:
    rates = get_services_token_rates(config)
    now = time.time()
    for svc_key, rate in rates.items():
        svc = config.get("services", {}).get(svc_key, {})
        backend = svc.get("backend", "")
        if backend in ("llama.cpp", "ik_llama.cpp"):
            cached = _TIMINGS_CACHE.get(svc_key)
            if cached and _is_service_healthy(config, svc_key) and (now - cached.get("last_update", 0)) < _CACHE_TTL_SECONDS:
                return cached.get("prompt"), cached.get("generation")
    return None, None


def _is_service_healthy(config, svc_key):
    from llm_dashboard.services.health import check_service_health
    svc = config.get("services", {}).get(svc_key, {})
    if not svc:
        return False
    url = svc.get("base_url", "")
    ep = svc.get("health_endpoint", "/health")
    to = svc.get("timeout_seconds", 2)
    if not url:
        return False
    try:
        status, _ = check_service_health(url, ep, to)
        return status == "UP"
    except Exception:
        return False


def get_vllm_timings(config: dict) -> tuple[float | None, float | None]:
    rates = get_services_token_rates(config)
    now = time.time()
    for svc_key, rate in rates.items():
        svc = config.get("services", {}).get(svc_key, {})
        if svc.get("backend") == "vllm":
            cached = _TIMINGS_CACHE.get(svc_key)
            if cached and (now - cached.get("last_update", 0)) < _CACHE_TTL_SECONDS:
                return rate.get("prompt"), rate.get("generation")
            return None, None
    return None, None