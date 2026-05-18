"""
Config API routes — audit machine, manage services, generate systemd units.
/admin/config/audit   — scan backends, models, ports, services
/admin/config/service — CRUD for services in config.yaml
/admin/config/systemd — generate systemd service file
"""

from __future__ import annotations

import fcntl
import logging
import os
import re
import subprocess
import tempfile
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
        "models_endpoint": None,
        "timeout_seconds": 2,
        "startup_time_seconds": 10,
        "stop_timeout_seconds": 10,
        "systemd_killmode": "process",
    },
    "gradio": {
        "health_endpoint": "/",
        "models_endpoint": None,
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
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(CONFIG_YAML), suffix=".yaml.tmp")
    try:
        with os.fdopen(tmp_fd, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, CONFIG_YAML)
    except Exception:
        os.unlink(tmp_path)
        raise


def get_services():
    config = read_config()
    return config.get("services", {})


_config_lock_fd = open(os.path.join(tempfile.gettempdir(), "dashboard-llm-config.lock"), "w")


def _acquire_config_lock():
    fcntl.flock(_config_lock_fd, fcntl.LOCK_EX)


def _release_config_lock():
    fcntl.flock(_config_lock_fd, fcntl.LOCK_UN)


def add_or_update_service(svc_key, svc_data):
    _acquire_config_lock()
    try:
        config = read_config()
        existing = config.get("services", {}).get(svc_key, {})
        if existing and isinstance(existing, dict):
            merged = dict(existing)
            merged.update(svc_data)
        else:
            merged = svc_data
        config.setdefault("services", {})[svc_key] = merged
        write_config(config)
    finally:
        _release_config_lock()
    return True


def delete_service(svc_key):
    _acquire_config_lock()
    try:
        config = read_config()
        if svc_key in config.get("services", {}):
            del config["services"][svc_key]
            write_config(config)
            return True
        return False
    finally:
        _release_config_lock()


# ===================================================================
# Systemd generation
# ===================================================================

SAFE_FLAT_RE = re.compile(r'^[^\n\r/]+$')
SAFE_PATH_RE = re.compile(r'^[^\n\r]+$')
SAFE_DESCRIPTION_RE = re.compile(r'^[^\n\r]+$')


def _sanitize_flat_field(value, max_len=255):
    s = str(value).strip()[:max_len]
    if not s:
        return s
    if '..' in s or not SAFE_FLAT_RE.match(s):
        raise ValueError(f"Invalid value: {value!r}")
    return s


def _sanitize_path_field(value, max_len=4096):
    s = str(value).strip()[:max_len]
    if not s:
        return s
    if '..' in s or not SAFE_PATH_RE.match(s):
        raise ValueError(f"Invalid value: {value!r}")
    return s


def _sanitize_description_field(value, max_len=255):
    s = str(value).strip()[:max_len]
    if not s:
        return s
    if not SAFE_DESCRIPTION_RE.match(s):
        raise ValueError(f"Invalid value: {value!r}")
    return s


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
    svc_key = _sanitize_flat_field(svc_key)
    backend = svc_data.get("backend", "auto")
    defaults = BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["proxy"])
    name = _sanitize_description_field(svc_data.get("name", svc_key))
    user = _sanitize_flat_field(svc_data.get("systemd_user", "admin_ia"))
    ALLOWED_SYSTEMD_USERS = {"admin_ia", "root"}
    if user not in ALLOWED_SYSTEMD_USERS:
        raise ValueError(f"systemd_user '{user}' not allowed")

    # ExecStart: user-provided > template > empty
    exec_start = svc_data.get("exec_start", "").replace("\r", "").replace("\n", " \\\n    ")
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

    log_file = _sanitize_path_field(svc_data.get("log_file", f"/var/log/{svc_key}.log"))
    stop_timeout = str(int(svc_data.get("stop_timeout_seconds", defaults.get("stop_timeout_seconds", 15))))

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
        tmp_fd, tmp_path = tempfile.mkstemp(prefix=unit_name + ".", suffix=".tmp")
        with os.fdopen(tmp_fd, 'w') as f:
            f.write(content)
        os.chmod(tmp_path, 0o600)
        subprocess.run(["sudo", "cp", tmp_path, unit_path], capture_output=True, check=False)
        os.unlink(tmp_path)
        subprocess.run(["sudo", "systemctl", "daemon-reload"], capture_output=True, check=False)
        return {"success": True, "unit_name": unit_name, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e), "content": content}


# ===================================================================
# Flask blueprint
# ===================================================================

def create_config_api(config, is_admin_authenticated) -> Blueprint:
    bp = Blueprint("config_api", __name__)

    def _check_csrf():
        csrf_enabled = config.get("admin", {}).get("csrf_enabled", False)
        if not csrf_enabled:
            return True
        csrf_header = config.get("admin", {}).get("csrf_header", "X-CSRF-Token")
        token = request.headers.get(csrf_header, "")
        import secrets
        expected = session.get("csrf_token", "")
        if not token or not expected or not secrets.compare_digest(token, expected):
            logger.warning("CSRF validation failed on config API from %s", request.remote_addr or "unknown")
            return False
        return True

    UNIT_NAME_RE = re.compile(r'^[A-Za-z0-9_.@:-]+\.service$')

    @bp.route("/api/admin/config/audit")
    def api_audit():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(audit_machine())

    @bp.route("/api/admin/config/services")
    def api_services():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        return jsonify(get_services())

    @bp.route("/api/admin/config/backend-defaults")
    def api_backend_defaults():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        backend = request.args.get("backend", "auto")
        defaults = BACKEND_DEFAULTS.get(backend, BACKEND_DEFAULTS["proxy"])
        LOG_FILTER_INFO = {
            "vllm": "Filtre les access logs uvicorn (GET /health, /metrics, /v1/models).",
            "ik_llama.cpp": "Filtre les lignes repetitives llama.cpp (srv stop, slots idle, etc.).",
            "llama.cpp": "Filtre les lignes repetitives llama.cpp (srv stop, slots idle, etc.).",
            "proxy": "Filtre les access logs werkzeug, les 404 /metrics, les redirects /login et les health checks repetitifs.",
            "ollama": "Aucun filtre supplementaire (journalctl).",
            "sglang": "Aucun filtre supplementaire.",
            "lmstudio": "Aucun filtre supplementaire.",
            "gradio": "Filtre les access logs, les 404 /metrics et les health checks repetitifs.",
        }
        result = dict(defaults)
        result["log_filter_info"] = LOG_FILTER_INFO.get(backend, "Filtre les lignes de log inutiles selon le backend.")
        return jsonify(result)

    @bp.route("/api/admin/config/service", methods=["POST"])
    def api_add_service():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        if not _check_csrf():
            return jsonify({"error": "csrf_failed"}), 403
        data = request.get_json(force=True)
        svc_key = data.get("key", "").strip()
        if not svc_key:
            return jsonify({"error": "Missing service key"}), 400
        if not re.match(r'^[a-zA-Z0-9_-]+$', svc_key):
            return jsonify({"error": "Invalid key format: use letters, digits, hyphens, underscores"}), 400
        ALLOWED_FIELDS = {
            'name', 'backend', 'role', 'base_url', 'port', 'health_endpoint',
            'models_endpoint', 'timeout_seconds', 'systemd_unit', 'model_path',
            'log_file', 'log_filter', 'log_type', 'startup_time_seconds',
            'model_detect_pattern', 'process_patterns', 'process_exclude_patterns',
            'start_command', 'stop_command', 'exclusive_group', 'exec_start',
            'stop_timeout_seconds', 'journalctl_unit', 'journalctl_lines',
            'vram_min_mib', 'systemd_user',
        }
        clean_data = {k: v for k, v in data.items() if k in ALLOWED_FIELDS and v is not None}
        if 'systemd_unit' in clean_data and not re.match(r'^[A-Za-z0-9_.@:-]+\.service$', clean_data['systemd_unit']):
            return jsonify({"error": "Invalid systemd unit name format"}), 400
        ok = add_or_update_service(svc_key, clean_data)
        if ok:
            _restart_dashboard()
        return jsonify({"success": ok, "key": svc_key})

    @bp.route("/api/admin/config/service/<svc_key>", methods=["DELETE"])
    def api_delete_service(svc_key):
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        if not _check_csrf():
            return jsonify({"error": "csrf_failed"}), 403
        if not re.match(r'^[a-zA-Z0-9_-]+$', svc_key):
            return jsonify({"error": "Invalid key format"}), 400
        ok = delete_service(svc_key)
        if ok:
            _restart_dashboard()
        return jsonify({"success": ok, "key": svc_key})

    @bp.route("/api/admin/config/systemd/generate", methods=["POST"])
    def api_generate_systemd():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        if not _check_csrf():
            return jsonify({"error": "csrf_failed"}), 403
        data = request.get_json(force=True)
        svc_key = data.get("key", "untitled")
        if not re.match(r'^[a-zA-Z0-9_-]+$', svc_key):
            return jsonify({"error": "Invalid key format"}), 400
        try:
            content = generate_systemd_unit(svc_key, data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"content": content, "key": svc_key})

    @bp.route("/api/admin/config/systemd/install", methods=["POST"])
    def api_install_systemd():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        if not _check_csrf():
            return jsonify({"error": "csrf_failed"}), 403
        data = request.get_json(force=True)
        svc_key = data.get("key", "untitled")
        if not re.match(r'^[a-zA-Z0-9_-]+$', svc_key):
            return jsonify({"error": "Invalid key format"}), 400
        try:
            result = install_systemd_unit(svc_key, data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify(result)

    @bp.route("/api/admin/config/restart", methods=["POST"])
    def api_restart():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        if not _check_csrf():
            return jsonify({"error": "csrf_failed"}), 403
        ok = _restart_dashboard()
        return jsonify({"success": ok})

    @bp.route("/api/admin/config/systemd/read")
    def api_read_systemd():
        if not is_admin_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
        unit = request.args.get("unit", "")
        if not unit:
            return jsonify({"exec_start": ""})
        if not UNIT_NAME_RE.match(unit):
            return jsonify({"error": "Invalid unit name"}), 400
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