"""
Dashboard API route — /api/data.

Portable : tous les noms de service, backends et groupes sont extraits dynamiquement de la config.
"""

from __future__ import annotations

import logging
from typing import Callable

from flask import Flask, jsonify

from llm_dashboard.monitors.gpu.processes import process_vram_mib


def _get_service_name(config, key):
    svc = config.get("services", {}).get(key, {})
    return svc.get("name", key) if isinstance(svc, dict) else key


def _find_service_key_by_role(config, role):
    for k, v in config.get("services", {}).items():
        if isinstance(v, dict) and v.get("role") == role:
            return k
    return None


class DashboardAPIRoute:
    def __init__(self, config: dict,
                 get_cpu_info: Callable[[], dict],
                 get_ram_info: Callable[[], dict],
                 get_gpu_info: Callable[[], list],
                 get_services_status: Callable[[], dict],
                 get_llama_startup_state: Callable[[str | None], dict],
                 get_llama_timings: Callable[[], tuple],
                 get_vllm_timings: Callable[[], tuple],
                 get_logs: Callable[[], dict],
                 get_client_ips: Callable[[], list],
                 detect_model_name: Callable[[], str],
                 logger: logging.Logger | None = None,
                 get_ollama_models: Callable[[], list] | None = None,
                 get_llama_metrics: Callable[[], dict] | None = None,
                 get_gpu_processes: Callable[[], list] | None = None):
        self._config = config
        self._get_cpu = get_cpu_info
        self._get_ram = get_ram_info
        self._get_gpu = get_gpu_info
        self._get_services = get_services_status
        self._get_startup = get_llama_startup_state
        self._get_llama_timings = get_llama_timings
        self._get_vllm_timings = get_vllm_timings
        self._get_logs = get_logs
        self._get_ips = get_client_ips
        self._detect_model = detect_model_name
        self._logger = logger or logging.getLogger("dashboard-llm")
        self._get_ollama_models = get_ollama_models or (lambda: [])
        self._get_llama_metrics = get_llama_metrics or (lambda: {})
        self._get_gpu_processes = get_gpu_processes

    def register(self, app: Flask) -> None:
        config = self._config
        get_cpu = self._get_cpu
        get_ram = self._get_ram
        get_gpu = self._get_gpu
        get_services = self._get_services
        get_startup = self._get_startup
        get_llama_timings = self._get_llama_timings
        get_vllm_timings = self._get_vllm_timings
        get_logs = self._get_logs
        get_ips = self._get_ips
        detect_model = self._detect_model
        logger = self._logger
        get_ollama = self._get_ollama_models
        get_llama_met = self._get_llama_metrics

        @app.route('/api/data')
        def api_data():
            try:
                services_payload = get_services()
            except Exception as e:
                logger.error("get_services_status failed: %s", e)
                services_payload = {'services': {}, 'llama_latency_seconds': None,
                                    'slots_active': None, 'slots_total': None,
                                    'active_on_8080': None, 'model_on_8080': None,
                                    'active_services': {}, 'models_by_group': {}}

            active_on_8080 = services_payload.get('active_on_8080')
            active_services = services_payload.get('active_services', {})
            models_by_group = services_payload.get('models_by_group', {})

            # Noms dynamiques des services (backward compat)
            ik_key = None
            llama_key = None
            vllm_key = None
            for k, v in config.get("services", {}).items():
                if isinstance(v, dict):
                    backend = v.get("backend", "")
                    if backend == "vllm":
                        vllm_key = k
                    elif backend in ("llama.cpp",):
                        llama_key = k
                    elif backend in ("ik_llama.cpp",):
                        ik_key = k
            if not ik_key:
                ik_key = next((k for k, v in config.get("services", {}).items()
                               if isinstance(v, dict) and v.get("role") == "llm"), "ik_llama_cpp")
            if not llama_key:
                llama_key = "llama_cpp"
            if not vllm_key:
                vllm_key = "vllm"

            ik_name = _get_service_name(config, ik_key)
            llama_name = _get_service_name(config, llama_key)
            vllm_name = _get_service_name(config, vllm_key)

            active_llama_name = None
            if active_on_8080 in (ik_key, llama_key):
                active_llama_name = _get_service_name(config, active_on_8080)
            elif active_on_8080 in config.get("services", {}):
                active_llama_name = _get_service_name(config, active_on_8080)

            llama_health = services_payload.get('services', {}).get(
                active_llama_name or llama_name) if active_llama_name else None
            llama_latency = services_payload.get('llama_latency_seconds')

            try:
                startup_state = get_startup(llama_health)
            except Exception as e:
                logger.error("get_llama_startup_state failed: %s", e)
                startup_state = {"state": "DOWN", "loading_seconds": None,
                                 "eta_seconds": None, "avg_seconds": None}

            # Status du service actif avec latence/timings
            if active_on_8080 in (ik_key, llama_key) or active_on_8080 is None:
                if active_llama_name:
                    llama_health = services_payload.get('services', {}).get(active_llama_name, 'DOWN')
                llama_status = llama_health
                if startup_state.get('state') == 'LOADING':
                    llama_status = 'LOADING'
                elif llama_health == 'UP' and isinstance(llama_latency, (int, float)):
                    llama_status = 'SLOW' if llama_latency >= 5.0 else 'UP'
                if active_llama_name:
                    services_payload.setdefault('services', {})[active_llama_name] = llama_status
            else:
                startup_state = {"state": "DOWN", "loading_seconds": None,
                                 "eta_seconds": None, "avg_seconds": None}

            llama_pr, llama_gr = None, None
            vllm_pr, vllm_gr = None, None
            service_token_rates = {}
            try:
                from llm_dashboard.monitors.timings import get_services_token_rates
                service_token_rates = get_services_token_rates(config)
                if active_on_8080 in (ik_key, llama_key) or active_on_8080 is None:
                    llama_pr, llama_gr = get_llama_timings()
                elif active_on_8080 == vllm_key:
                    vllm_pr, vllm_gr = get_vllm_timings()
            except Exception as e:
                logger.error("get_llama/vllm_timings failed: %s", e)

            try:
                client_ips = get_ips()
            except Exception as e:
                logger.error("get_client_ips failed: %s", e)
                client_ips = []

            try:
                service_logs = get_logs()
            except Exception as e:
                logger.error("get_logs failed: %s", e)
                service_logs = {}

            try:
                model_name = detect_model()
            except Exception as e:
                logger.error("detect_model_name failed: %s", e)
                model_name = 'Unknown'

            svc_names = {}
            for k, v in config.get("services", {}).items():
                svc_names[k] = v.get("name", k) if isinstance(v, dict) else k

            try:
                gpu_proc_payload = _gpu_process_payload()
            except Exception:
                gpu_proc_payload = []

            return jsonify({
                'cpu': get_cpu(), 'ram': get_ram(), 'gpus': get_gpu(),
                'services': services_payload.get('services', {}),
                'slots_active': services_payload.get('slots_active'),
                'slots_total': services_payload.get('slots_total'),
                'service_logs': service_logs,
                'service_order': list(config.get("services", {}).keys()),
                'service_names': svc_names,
                'model_name': model_name,
                'prompt_tokens_per_second': llama_pr,
                'generation_tokens_per_second': llama_gr,
                'vllm_prompt_tokens_per_second': vllm_pr,
                'vllm_generation_tokens_per_second': vllm_gr,
                'client_ips': client_ips,
                'llama_service_name': llama_name,
                'ik_llama_service_name': ik_name,
                'vllm_service_name': vllm_name,
                'active_llama_service_name': active_llama_name,
                'llama_state': startup_state.get('state', 'DOWN'),
                'llama_loading_seconds': startup_state.get('loading_seconds'),
                'llama_eta_seconds': startup_state.get('eta_seconds'),
                'llama_avg_load_seconds': startup_state.get('avg_seconds'),
                'active_on_8080': active_on_8080,
                'model_on_8080': services_payload.get('model_on_8080'),
                'active_services': active_services,
                'models_by_group': models_by_group,
                'ollama_models': get_ollama(),
                'llama_metrics': get_llama_met(),
                'service_token_rates': service_token_rates,
                'gpu_processes': gpu_proc_payload,
                'gpu_process_count': len(gpu_proc_payload),
                'gpu_process_vram_total_mib': sum(process_vram_mib(p) for p in gpu_proc_payload),
            })

        def _gpu_process_payload():
            gp_config = config.get("gpu_processes", {})
            if not gp_config.get("enable", True):
                return []
            if not self._get_gpu_processes:
                return []
            show_cmd = gp_config.get("show_command", True)
            max_procs = gp_config.get("max_processes", 100)
            raw = self._get_gpu_processes()
            processes = []
            for p in raw:
                entry = dict(p)
                if not show_cmd:
                    entry["command"] = None
                processes.append(entry)
            processes.sort(key=lambda p: process_vram_mib(p), reverse=True)
            if max_procs and len(processes) > max_procs:
                processes = processes[:max_procs]
            return processes

        def get_ollama():
            try:
                return self._get_ollama_models() if self._get_ollama_models else []
            except Exception:
                return []

        def get_llama_met():
            try:
                return self._get_llama_metrics() if self._get_llama_metrics else {}
            except Exception:
                return {}