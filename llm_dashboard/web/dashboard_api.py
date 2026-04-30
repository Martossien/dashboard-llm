"""
Dashboard API route — /api/data.

Pas d'import depuis monitor.py.
"""

from __future__ import annotations

import logging
from typing import Callable

from flask import Flask, jsonify


class DashboardAPIRoute:
    """Route /api/data — endpoint JSON principal du dashboard."""

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
                 find_ik_llama_process: Callable[[], dict | None],
                 find_llama_process: Callable[[], dict | None],
                 logger: logging.Logger | None = None,
                 get_ollama_models: Callable[[], list] | None = None,
                 get_llama_metrics: Callable[[], dict] | None = None,
                 get_gpu_processes: Callable[[], list] | None = None):
        ...
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
        self._find_ik = find_ik_llama_process
        self._find_llama = find_llama_process
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
        find_ik = self._find_ik
        find_llama = self._find_llama
        logger = self._logger
        get_ollama = self._get_ollama_models
        get_llama_met = self._get_llama_metrics

        @app.route('/api/data')
        def api_data():
            try:
                services_payload = get_services()
            except Exception as e:
                logger.error("get_services_status failed: %s", e)
                services_payload = {
                    'services': {svc["name"]: 'DOWN' for svc in config["services"].values()},
                    'llama_latency_seconds': None, 'slots_active': None,
                    'slots_total': None, 'active_on_8080': None, 'model_on_8080': None,
                }
            active_on_8080 = services_payload.get('active_on_8080')

            ik_name = config["services"]["ik_llama_cpp"]["name"]
            llama_name = config["services"]["llama_cpp"]["name"]
            vllm_name = config["services"]["vllm"]["name"]

            active_llama_name = None
            if active_on_8080 == 'ik_llama_cpp':
                active_llama_name = ik_name
            elif active_on_8080 == 'llama_cpp':
                active_llama_name = llama_name

            llama_health = services_payload['services'].get(
                active_llama_name or llama_name) if active_llama_name else None
            llama_latency = services_payload.get('llama_latency_seconds')
            try:
                startup_state = get_startup(llama_health)
            except Exception as e:
                logger.error("get_llama_startup_state failed: %s", e)
                startup_state = {"state": "DOWN", "loading_seconds": None,
                                 "eta_seconds": None, "avg_seconds": None}

            if active_on_8080 in ('ik_llama_cpp', 'llama_cpp') or active_on_8080 is None:
                if active_llama_name:
                    llama_health = services_payload['services'].get(active_llama_name, 'DOWN')
                llama_status = llama_health
                if startup_state['state'] == 'LOADING':
                    llama_status = 'LOADING'
                elif llama_health == 'UP' and isinstance(llama_latency, (int, float)):
                    llama_status = 'SLOW' if llama_latency >= 5.0 else 'UP'
                elif llama_health and llama_health != 'UP':
                    has_proc = find_ik() if active_on_8080 == 'ik_llama_cpp' else find_llama()
                    llama_status = 'UNRESPONSIVE' if has_proc else 'DOWN'
                if active_llama_name:
                    services_payload['services'][active_llama_name] = llama_status
            else:
                startup_state = {"state": "DOWN", "loading_seconds": None,
                                 "eta_seconds": None, "avg_seconds": None}

            llama_pr, llama_gr = None, None
            vllm_pr, vllm_gr = None, None
            try:
                if active_on_8080 in ('ik_llama_cpp', 'llama_cpp') or active_on_8080 is None:
                    llama_pr, llama_gr = get_llama_timings()
                elif active_on_8080 == 'vllm':
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
            for k, v in config["services"].items():
                svc_names[k] = v["name"]

            return jsonify({
                'cpu': get_cpu(), 'ram': get_ram(), 'gpus': get_gpu(),
                'services': services_payload['services'],
                'slots_active': services_payload['slots_active'],
                'slots_total': services_payload['slots_total'],
                'service_logs': service_logs,
                'service_order': list(config["services"].keys()),
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
                'llama_state': startup_state['state'],
                'llama_loading_seconds': startup_state['loading_seconds'],
                'llama_eta_seconds': startup_state['eta_seconds'],
                'llama_avg_load_seconds': startup_state['avg_seconds'],
                'active_on_8080': active_on_8080,
                'model_on_8080': services_payload.get('model_on_8080'),
                'ollama_models': get_ollama(),
                'llama_metrics': get_llama_met(),
                'gpu_processes': _get_gpu_processes_payload(),
                'gpu_process_count': len(_get_gpu_processes_payload()),
                'gpu_process_vram_total_mib': sum(p.get('used_vram_mib', 0) for p in _get_gpu_processes_payload()),
            })

        def _get_gpu_processes_payload():
            gp_config = config.get("gpu_processes", {})
            if not gp_config.get("enable", True):
                return []
            try:
                if not self._get_gpu_processes:
                    return []
                show_cmd = gp_config.get("show_command", True)
                max_procs = gp_config.get("max_processes", 100)
                raw = self._get_gpu_processes()
                # If raw returns dicts with show_command support, use that
                # Otherwise filter command client-side
                processes = []
                for p in raw:
                    entry = dict(p)
                    if not show_cmd:
                        entry["command"] = None
                    processes.append(entry)
                if max_procs and len(processes) > max_procs:
                    processes = processes[:max_procs]
                return processes
            except Exception as e:
                logger.error("get_gpu_processes failed in /api/data: %s", e)
                return []

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
