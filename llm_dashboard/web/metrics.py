"""Prometheus /metrics endpoint and public /api/v1/* REST API.

Pas d'import depuis monitor.py.
"""

from flask import jsonify, Response


def _escape_label(value) -> str:
    """Echappe une valeur de label Prometheus."""
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def create_metrics_endpoint(get_cpu_info, get_ram_info, get_gpu_info,
                            get_services_status, detect_model_name,
                            get_gpu_processes=None):
    """Cree une route /metrics au format Prometheus text."""

    def metrics():
        lines = []

        # CPU
        cpu = get_cpu_info()
        lines.append('# HELP cpu_load_percent CPU load percentage')
        lines.append('# TYPE cpu_load_percent gauge')
        lines.append(f'cpu_load_percent {cpu["load"]}')

        # RAM
        ram = get_ram_info()
        lines.append('# HELP ram_used_gb RAM used in GB')
        lines.append('# TYPE ram_used_gb gauge')
        lines.append(f'ram_used_gb {ram["used"]}')
        lines.append('# HELP ram_total_gb RAM total in GB')
        lines.append('# TYPE ram_total_gb gauge')
        lines.append(f'ram_total_gb {ram["total"]}')

        # GPU
        lines.append('# HELP gpu_memory_used_gib GPU memory used')
        lines.append('# TYPE gpu_memory_used_gib gauge')
        lines.append('# HELP gpu_temperature_celsius GPU temperature')
        lines.append('# TYPE gpu_temperature_celsius gauge')
        lines.append('# HELP gpu_utilization_pct GPU utilization')
        lines.append('# TYPE gpu_utilization_pct gauge')
        lines.append('# HELP gpu_power_watts GPU power draw')
        lines.append('# TYPE gpu_power_watts gauge')
        gpus = get_gpu_info()
        for gpu in gpus:
            idx = _escape_label(gpu.get('id', 0))
            mem = gpu.get('memory', {})
            lines.append(f'gpu_memory_used_gib{{gpu="{idx}"}} {mem.get("used", 0)}')
            lines.append(f'gpu_temperature_celsius{{gpu="{idx}"}} {gpu.get("temp", 0)}')
            lines.append(f'gpu_utilization_pct{{gpu="{idx}"}} {gpu.get("gpu_util", 0)}')
            lines.append(f'gpu_power_watts{{gpu="{idx}"}} {gpu.get("power", 0)}')

        # Services
        lines.append('# HELP llm_service_up Service health status')
        lines.append('# TYPE llm_service_up gauge')
        services = get_services_status()
        for svc_name, status in (services.get('services', {}) or {}).items():
            svc_label = _escape_label(svc_name)
            up_value = 1 if status == 'UP' else 0
            lines.append(f'llm_service_up{{service="{svc_label}"}} {up_value}')

        # Model
        model = _escape_label(detect_model_name() or 'unknown')
        lines.append('# HELP llm_model_info Active model name')
        lines.append('# TYPE llm_model_info gauge')
        lines.append(f'llm_model_info{{model="{model}"}} 1')

        # GPU Processes
        if callable(get_gpu_processes):
            lines.append('# HELP gpu_process_count Number of GPU processes')
            lines.append('# TYPE gpu_process_count gauge')
            lines.append('# HELP gpu_process_memory_used_mib GPU process memory usage in MiB')
            lines.append('# TYPE gpu_process_memory_used_mib gauge')
            lines.append('# HELP gpu_process_memory_total_mib Total GPU memory used by processes in MiB')
            lines.append('# TYPE gpu_process_memory_total_mib gauge')
            try:
                all_procs = get_gpu_processes()
                vendor = _escape_label("nvidia")
                total_vram = sum(p.get("used_vram_mib", p.get("vram_mib", 0)) for p in all_procs)
                lines.append(f'gpu_process_count{{vendor="{vendor}"}} {len(all_procs)}')
                lines.append(f'gpu_process_memory_total_mib{{vendor="{vendor}"}} {total_vram}')
                for p in all_procs:
                    pid = _escape_label(str(p.get("pid", "?")))
                    name = _escape_label(p.get("process_name", p.get("name", "unknown")))
                    gpu_idx = _escape_label(str(p.get("gpu_index", "unknown")))
                    service = _escape_label(p.get("service_guess", "unknown"))
                    vram = p.get("used_vram_mib", p.get("vram_mib", 0))
                    lines.append(
                        f'gpu_process_memory_used_mib{{'
                        f'pid="{pid}",gpu_index="{gpu_idx}",'
                        f'process_name="{name}",service="{service}",'
                        f'vendor="{vendor}"}} {vram}'
                    )
            except Exception:
                pass

        lines.append('')
        return Response('\n'.join(lines), mimetype='text/plain; version=0.0.4')

    return metrics


def register_public_api(app, get_cpu_info, get_ram_info, get_gpu_info,
                        get_services_status, detect_model_name,
                        get_logs, get_llama_timings, get_vllm_timings,
                        config, get_gpu_processes=None):
    """Enregistre /metrics, /api/v1/gpus, /api/v1/services, /api/v1/metrics, /api/v1/gpu/processes."""

    _ = get_logs, get_llama_timings, get_vllm_timings  # unused for now

    @app.route('/metrics')
    def metrics_route():
        return create_metrics_endpoint(
            get_cpu_info, get_ram_info, get_gpu_info,
            get_services_status, detect_model_name,
            get_gpu_processes=get_gpu_processes,
        )()

    @app.route('/api/v1/gpus')
    def public_gpus():
        return jsonify({"gpus": get_gpu_info()})

    @app.route('/api/v1/services')
    def public_services():
        svc_status = get_services_status()
        return jsonify({
            "services": svc_status.get("services", {}),
            "active_on_ports": {
                "8080": svc_status.get("active_on_8080"),
            },
            "model_on_8080": svc_status.get("model_on_8080"),
        })

    @app.route('/api/v1/metrics')
    def public_metrics():
        cpu = get_cpu_info()
        ram = get_ram_info()
        gpus = get_gpu_info()
        svc_status = get_services_status()
        return jsonify({
            "cpu": cpu,
            "ram": ram,
            "gpus": gpus,
            "services": svc_status.get("services", {}),
            "model": detect_model_name() or "unknown",
        })

    @app.route('/api/v1/gpus/processes')
    @app.route('/api/v1/gpu/processes')
    def public_gpus_processes():
        return public_gpu_processes_inner()

    def public_gpu_processes_inner():
        processes = []
        if callable(get_gpu_processes):
            try:
                raw = get_gpu_processes()
                # Enrich with human-readable process name via psutil when available
                for p in raw:
                    entry = dict(p)
                    try:
                        import psutil
                        proc = psutil.Process(p["pid"])
                        entry["process_name"] = proc.name()
                        entry["cmdline"] = " ".join(proc.cmdline()[:3])
                    except Exception:
                        entry["process_name"] = p.get("name", "unknown")
                        entry["cmdline"] = ""
                    processes.append(entry)
            except Exception:
                pass

        # Sort by VRAM usage descending (like nvitop/gpustat)
        processes.sort(key=lambda p: p.get("vram_mib", 0), reverse=True)

        return jsonify({
            "processes": processes,
            "total_vram_mib": sum(p.get("vram_mib", 0) for p in processes),
        })
