"""
Config API routes — audit machine, manage services, generate systemd units.
/admin/config/audit   — scan backends, models, ports, services
/admin/config/service — CRUD for services in config.yaml
/admin/config/systemd — generate systemd service file
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import yaml

from flask import Blueprint, jsonify, request, session

logger = logging.getLogger("dashboard-llm.config_api")

CONFIG_YAML = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml"))

# ===================================================================
# Backend templates — defaults per backend type
# ===================================================================

BACKEND_DEFAULTS = {
    "vllm": {
        "health_endpoint": "/health",
        "models_endpoint": "/v1/models",
        "timeout_seconds": 2,
        "startup_time_seconds": 900,
        "stop_timeout_seconds": 60,
        "process_patterns": ["vllm serve", "VLLM::EngineCore", "VLLM::Worker_TP"],
        "systemd_killmode": "mixed",
        "exec_start_template": (
            "vllm serve /path/to/model \\\n"
            "  --host 0.0.0.0 --port 8002 \\\n"
            "  --tensor-parallel-size 8 \\\n"
            "  --max-model-len 131072 \\\n"
            "  --gpu-memory-utilization 0.90 \\\n"
            "  --kv-cache-dtype fp8_e4m3 \\\n"
            "  --enable-prefix-caching --enable-chunked-prefill"
        ),
    },
    "llama.cpp": {
        "health_endpoint": "/health",
        "models_endpoint": "/v1/models",
        "timeout_seconds": 2,
        "startup_time_seconds": 90,
        "stop_timeout_seconds": 15,
        "process_patterns": ["llama-server"],
        "process_exclude_patterns": ["ik_llama", "GLM"],
        "systemd_killmode": "process",
        "exec_start_template": (
            os.path.expanduser("~/llama.cpp/build/bin/llama-server") + " \\\n"
            "  --model /path/to/model.gguf \\\n"
            "  --port 8030 --host 0.0.0.0 \\\n"
            "  --n-gpu-layers 999 --ctx-size 131072 \\\n"
            "  --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 \\\n"
            "  --batch-size 8192 --ubatch-size 4096 \\\n"
            "  --parallel 1 --no-mmap --mlock --jinja --metrics"
        ),
    },
    "ik_llama.cpp": {
        "health_endpoint": "/health",
        "models_endpoint": "/v1/models",
        "timeout_seconds": 2,
        "startup_time_seconds": 90,
        "stop_timeout_seconds": 15,
        "process_patterns": ["ik_llama"],
        "systemd_killmode": "process",
        "exec_start_template": (
            os.path.expanduser("~/ik_llama.cpp/build/bin/llama-server") + " \\\n"
            "  -m /path/to/model.gguf \\\n"
            "  --port 8080 --host 0.0.0.0 \\\n"
            "  -ngl 999 -c 131072 \\\n"
            "  -fa 1 -mqkv -muge \\\n"
            "  -ctk q8_0 -ctv q8_0 \\\n"
            "  --no-mmap --mlock --jinja --metrics"
        ),
    },
    "sglang": {
        "health_endpoint": "/health",
        "models_endpoint": "/v1/models",
        "timeout_seconds": 2,
        "startup_time_seconds": 600,
        "stop_timeout_seconds": 20,
        "process_patterns": ["sglang", "sglang.launch_server"],
        "systemd_killmode": "process",
        "exec_start_template": (
            "python -m sglang.launch_server \\\n"
            "  --model-path /path/to/model \\\n"
            "  --port 30000 --host 0.0.0.0 \\\n"
            "  --tp-size 8 \\\n"
            "  --context-length 131072"
        ),
    },
    "ollama": {
        "health_endpoint": "/",
        "models_endpoint": None,
        "timeout_seconds": 2,
        "startup_time_seconds": 5,
        "stop_timeout_seconds": 10,
        "process_patterns": ["ollama"],
        "systemd_killmode": "process",
        "log_type": "journalctl",
    },
    "proxy": {
        "health_endpoint": "/health",
        "timeout_seconds": 2,
        "startup_time_seconds": 10,
        "stop_timeout_seconds": 10,
        "systemd_killmode": "process",
    },
    "gradio": {
        "health_endpoint": "/",
        "timeout_seconds": 2,
        "startup_time_seconds": 30,
        "stop_timeout_seconds": 10,
        "systemd_killmode": "process",
    },
    "lmstudio": {
        "health_endpoint": "/v1/models",
        "models_endpoint": "/v1/models",
        "timeout_seconds": 2,
        "startup_time_seconds": 30,
        "stop_timeout_seconds": 15,
        "process_patterns": ["lm-studio", "LM Studio"],
        "systemd_killmode": "process",
    },
}

# ===================================================================
# Audit — scan the machine
# ===================================================================

def _shell(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except Exception:
        return "", 1


def audit_machine():
    results = {"backends": {}, "models": [], "conda_envs": [],
               "ports_open": [], "systemd_units": [], "gpus": []}

    # Backends — check multiple locations
    backends = {
        "vllm": [
            lambda: _shell(["which", "vllm"], timeout=3),
            lambda: _shell([os.path.expanduser("~/.local/bin/vllm"), "--version"], timeout=3),
            lambda: _shell([os.path.expanduser("~/miniconda3/envs/vllm_env/bin/vllm"), "--version"], timeout=3),
        ],
        "ollama": [
            lambda: _shell(["which", "ollama"], timeout=3),
            lambda: _shell(["/usr/local/bin/ollama", "--version"], timeout=3),
            lambda: ("/usr/local/bin/ollama", 0) if os.path.exists("/usr/local/bin/ollama") else ("", 1),
        ],
        "sglang": [
            lambda: _shell(["which", "sglang"], timeout=3),
            lambda: _shell([os.path.expanduser("~/.conda/envs/sglang/bin/sglang"), "--version"], timeout=2),
        ],
        "llama.cpp": [
            lambda: _shell(["ls", os.path.expanduser("~/llama.cpp/build/bin/llama-server")], timeout=2),
        ],
        "ik_llama.cpp": [
            lambda: _shell(["ls", os.path.expanduser("~/ik_llama.cpp/build/bin/llama-server")], timeout=2),
        ],
        "lmstudio": [
            lambda: _shell(["ls", os.path.expanduser("~/.cache/lm-studio/bin/lm-studio")], timeout=2),
            lambda: ("port 1234", 0) if _has_port(1234) else ("", 1),
            lambda: (os.path.expanduser("~/.cache/lm-studio"), 0) if os.path.isdir(os.path.expanduser("~/.cache/lm-studio")) else ("", 1),
        ],
    }
    for name, checks in backends.items():
        found = False
        path = None
        for check in checks:
            result = check()
            if isinstance(result, tuple) and len(result) == 2:
                out, rc = result
                if rc == 0:
                    found = True
                    path = out.strip() if isinstance(out, str) else name
                    break
            elif isinstance(result, bool) and result:
                found = True
                path = name
                break
        results["backends"][name] = {"found": found, "path": path}

    # Check for sglang via conda env if binary not found
    envs = _scan_conda_envs()
    results["conda_envs"] = envs
    if not results["backends"]["sglang"]["found"]:
        for env in envs:
            if "sglang" in env["name"].lower():
                results["backends"]["sglang"]["found"] = True
                results["backends"]["sglang"]["path"] = f"conda env: {env['name']}"
                break
    # vLLM via conda env too
    if not results["backends"]["vllm"]["found"]:
        for env in envs:
            if "vllm" in env["name"].lower():
                results["backends"]["vllm"]["found"] = True
                results["backends"]["vllm"]["path"] = f"conda env: {env['name']}"
                break

    # Models — also scan LM Studio cache
    models_dir = os.path.expanduser("~/models")
    if os.path.isdir(models_dir):
        for entry in sorted(os.listdir(models_dir)):
            full = os.path.join(models_dir, entry)
            if os.path.isdir(full):
                has_gguf = any(f.endswith(".gguf") for f in os.listdir(full) if os.path.isfile(os.path.join(full, f)))
                has_safetensors = any(f.endswith(".safetensors") for f in os.listdir(full) if os.path.isfile(os.path.join(full, f)))
                has_config = os.path.isfile(os.path.join(full, "config.json"))
                if has_gguf or has_safetensors or has_config:
                    size_gb = _dir_size_gb(full)
                    results["models"].append({
                        "name": entry,
                        "path": full,
                        "format": "gguf" if has_gguf else "safetensors" if has_safetensors else "hf",
                        "size_gb": round(size_gb, 1) if size_gb else None,
                        "source": "local",
                    })

    # LM Studio models
    lm_models = _scan_lm_studio_models()
    results["models"].extend(lm_models)
    results["lm_studio_model_count"] = len(lm_models)

    # Open ports (LLM-related)
    out, _ = _shell(["ss", "-tlnpH"])
    for line in out.splitlines():
        m = re.search(r'LISTEN.*?:(\d{4,5})\s', line)
        if m:
            port = int(m.group(1))
            if 8000 <= port <= 30100:
                results["ports_open"].append(port)

    # Systemd services
    out, _ = _shell(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend"])
    for line in out.splitlines():
        parts = line.split()
        if parts:
            results["systemd_units"].append(parts[0])

    # GPUs
    out, _ = _shell(["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"])
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            results["gpus"].append({"index": parts[0], "name": parts[1], "memory_total_mb": int(parts[2])})

    return results


def _scan_conda_envs():
    envs = []
    conda_dirs = [
        os.path.expanduser("~/.conda/envs"),
        os.path.expanduser("~/miniconda3/envs"),
    ]
    for conda_dir in conda_dirs:
        if os.path.isdir(conda_dir):
            for name in sorted(os.listdir(conda_dir)):
                env_path = os.path.join(conda_dir, name)
                if os.path.isdir(env_path):
                    python = os.path.join(env_path, "bin", "python")
                    envs.append({"name": name, "path": env_path, "has_python": os.path.exists(python)})
    return envs


def _dir_size_gb(path):
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except Exception:
        pass
    return total / (1024 ** 3) if total else 0


def _has_port(port):
    try:
        out, _ = _shell(["ss", "-tlnpH"])
        return f":{port}" in out
    except Exception:
        return False


def _scan_lm_studio_models():
    models = []
    cache_dir = os.path.expanduser("~/.cache/lm-studio/models")
    if not os.path.isdir(cache_dir):
        return models
    for publisher in sorted(os.listdir(cache_dir)):
        pub_dir = os.path.join(cache_dir, publisher)
        if not os.path.isdir(pub_dir):
            continue
        for model_name in sorted(os.listdir(pub_dir)):
            model_dir = os.path.join(pub_dir, model_name)
            if not os.path.isdir(model_dir):
                continue
            ggufs = sorted([f for f in os.listdir(model_dir) if f.endswith(".gguf")])
            if ggufs:
                size_gb = _dir_size_gb(model_dir)
                is_sharded = any("-of-" in f for f in ggufs)
                model_ggufs = [f for f in ggufs if "mmproj" not in f.lower()]
                if not model_ggufs:
                    model_ggufs = ggufs
                first_file = os.path.join(model_dir, model_ggufs[0])
                models.append({
                    "name": f"{publisher}/{model_name}",
                    "path": model_dir,
                    "first_gguf": first_file if is_sharded else os.path.join(model_dir, ggufs[0]),
                    "format": "gguf",
                    "size_gb": round(size_gb, 1) if size_gb else None,
                    "source": "lmstudio",
                    "file_count": len(ggufs),
                    "sharded": is_sharded,
                })
    return models


# ===================================================================
# Service CRUD
# ===================================================================

def read_config():
    if os.path.exists(CONFIG_YAML):
        with open(CONFIG_YAML, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def write_config(config_data):
    bak = CONFIG_YAML + ".backup"
    try:
        if os.path.exists(CONFIG_YAML):
            import shutil
            shutil.copy2(CONFIG_YAML, bak)
    except Exception:
        pass
    with open(CONFIG_YAML, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_services():
    config = read_config()
    return config.get("services", {})


def add_or_update_service(svc_key, svc_data):
    config = read_config()
    config.setdefault("services", {})[svc_key] = svc_data
    write_config(config)
    return True


def delete_service(svc_key):
    config = read_config()
    if svc_key in config.get("services", {}):
        del config["services"][svc_key]
        write_config(config)
        return True
    return False


# ===================================================================
# Systemd generation
# ===================================================================

SYSTEMD_TEMPLATE = """[Unit]
Description={description}
After=network-online.target nvidia-persistenced.service
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={group}
{env_vars}
ExecStart={exec_start}
ExecStop=/bin/kill -TERM $MAINPID
KillMode={killmode}
KillSignal=SIGTERM
TimeoutStopSec={stop_timeout}
Restart=no
StandardOutput=append:{log_file}
StandardError=append:{log_file}

[Install]
WantedBy=multi-user.target
"""


def generate_systemd_unit(svc_key, svc_data):
    backend = svc_data.get("backend", "auto")
    defaults = BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["proxy"])
    name = svc_data.get("name", svc_key)
    user = svc_data.get("systemd_user", "admin_ia")

    # ExecStart: user-provided > template > empty
    exec_start = svc_data.get("exec_start", "").replace("\n", " \\\n    ")
    if not exec_start:
        exec_start = defaults.get("exec_start_template", "")

    # Env vars
    env_vars = ""
    if backend == "vllm":
        cuda_home = os.environ.get("CUDA_HOME", "/usr/local/cuda")
        conda_prefix = os.path.expanduser("~/miniconda3/envs/vllm_env")
        env_vars = f"Environment=CUDA_HOME={cuda_home}\nEnvironment=PATH={cuda_home}/bin:{conda_prefix}/bin:/usr/bin:/bin\nEnvironment=LD_LIBRARY_PATH={cuda_home}/lib64"
    elif backend in ("llama.cpp", "ik_llama.cpp"):
        if backend == "ik_llama.cpp":
            lib_path = os.path.expanduser("~/ik_llama.cpp/build/bin")
        else:
            lib_path = os.path.expanduser("~/llama.cpp/build/bin")
        env_vars = f"Environment=LD_LIBRARY_PATH={lib_path}"
    elif backend == "sglang":
        env_vars = "Environment=CUDA_HOME=/usr/local/cuda"

    log_file = svc_data.get("log_file", f"/var/log/{svc_key}.log")
    stop_timeout = svc_data.get("stop_timeout_seconds", defaults.get("stop_timeout_seconds", 15))

    return SYSTEMD_TEMPLATE.format(
        description=f"{name} — {backend}",
        user=user,
        group=user,
        env_vars=env_vars,
        exec_start=exec_start,
        killmode=defaults.get("systemd_killmode", "process"),
        stop_timeout=stop_timeout,
        log_file=log_file,
    )


def install_systemd_unit(svc_key, svc_data):
    content = generate_systemd_unit(svc_key, svc_data)
    unit_name = f"{svc_key}.service"
    unit_path = f"/etc/systemd/system/{unit_name}"
    try:
        with open("/tmp/" + unit_name, "w") as f:
            f.write(content)
        subprocess.run(["sudo", "cp", "/tmp/" + unit_name, unit_path], capture_output=True, check=False)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
        return {"success": True, "unit_name": unit_name, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e), "content": content}


# ===================================================================
# Flask blueprint
# ===================================================================

def create_config_api(config, admin_login_required) -> Blueprint:
    bp = Blueprint("config_api", __name__)

    @bp.route("/api/admin/config/audit")
    def api_audit():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(audit_machine())

    @bp.route("/api/admin/config/services")
    def api_services():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(get_services())

    @bp.route("/api/admin/config/backend-defaults")
    def api_backend_defaults():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        backend = request.args.get("backend", "auto")
        return jsonify(BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["proxy"]))

    @bp.route("/api/admin/config/service", methods=["POST"])
    def api_add_service():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(force=True)
        svc_key = data.get("key", "").strip()
        if not svc_key:
            return jsonify({"error": "Missing service key"}), 400
        ok = add_or_update_service(svc_key, data)
        if ok:
            _restart_dashboard()
        return jsonify({"success": ok, "key": svc_key})

    @bp.route("/api/admin/config/service/<svc_key>", methods=["DELETE"])
    def api_delete_service(svc_key):
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        ok = delete_service(svc_key)
        if ok:
            _restart_dashboard()
        return jsonify({"success": ok, "key": svc_key})

    @bp.route("/api/admin/config/systemd/generate", methods=["POST"])
    def api_generate_systemd():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(force=True)
        svc_key = data.get("key", "untitled")
        content = generate_systemd_unit(svc_key, data)
        return jsonify({"content": content, "key": svc_key})

    @bp.route("/api/admin/config/systemd/install", methods=["POST"])
    def api_install_systemd():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json(force=True)
        svc_key = data.get("key", "untitled")
        return jsonify(install_systemd_unit(svc_key, data))

    @bp.route("/api/admin/config/restart", methods=["POST"])
    def api_restart():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        ok = _restart_dashboard()
        return jsonify({"success": ok})

    @bp.route("/api/admin/config/systemd/read")
    def api_read_systemd():
        if not admin_login_required():
            return jsonify({"error": "Unauthorized"}), 401
        unit = request.args.get("unit", "")
        if not unit:
            return jsonify({"exec_start": ""})
        unit_path = f"/etc/systemd/system/{unit}"
        if not os.path.exists(unit_path):
            return jsonify({"exec_start": ""})
        try:
            with open(unit_path, "r") as f:
                content = f.read()
            match = re.search(r'^ExecStart=(.+?)(?:\n\S|\Z)', content, re.MULTILINE | re.DOTALL)
            exec_start = match.group(1).strip() if match else ""
            exec_start = re.sub(r'\n\s+', ' ', exec_start)
            return jsonify({"exec_start": exec_start, "unit": unit})
        except Exception:
            return jsonify({"exec_start": ""})

    return bp


def _restart_dashboard():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "dashboard-llm.service"],
                       capture_output=True, timeout=10)
        return True
    except Exception as e:
        logger.error("Failed to restart dashboard: %s", e)
        return False