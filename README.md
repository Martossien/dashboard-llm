# LLM Dashboard

Lightweight monitoring and administration dashboard for local LLM servers.

## Architecture

```
┌──────────────────────────────────────────────────┐
│ dashboard-llm  (Flask, port 5001)                │
├────────────────┬────────────────┬────────────────┤
│ Dashboard      │ Admin Panel    │ Configuration  │
│ GPU,services,  │ Start/Stop,    │ Audit, Add,    │
│ logs,token     │ Force Kill     │ Edit, Delete   │
│ rates          │                │ services       │
├────────────────┴────────────────┴────────────────┤
│ Config YAML ← editable via web UI, no CLI needed  │
│ Systemd services ← generated per backend          │
└──────────────────────────────────────────────────┘
```

**Backends**: vLLM, llama.cpp, ik_llama.cpp, SGLang, Ollama, LM Studio  
**Platforms**: Linux (NVIDIA GPU), 1-8 GPUs, systemd

## Quick Start

```bash
git clone https://github.com/Martossien/dashboard-llm.git
cd dashboard-llm
conda create -n dashboard-llm python=3.12 -y
conda activate dashboard-llm
pip install -e ".[nvidia]"

# Deploy as systemd service
sudo cp scripts/dashboard-llm.service /etc/systemd/system/
sudo systemctl enable --now dashboard-llm
```

Open `http://localhost:5001` — GPU, services, and logs in one page.

## Features

- **Real-time GPU monitoring** — 8 GPUs, VRAM, temp, power, SM/mem clocks, throttling
- **Per-service logs** — separate tabs per backend, live tail, noise filtering
- **Token rate tracking** — prompt + generation tok/s via Prometheus `/metrics`
- **Service lifecycle** — start/stop/force-kill via systemd, admin panel
- **Multi-backend** — vLLM, llama.cpp, ik_llama.cpp, SGLang, Ollama, LM Studio
- **Exclusive groups** — shared-port LLMs with mutual exclusion
- **Configuration page** — `/admin/config` with machine audit, service wizard, systemd generator
- **Prometheus `/metrics` endpoint** — CPU, RAM, GPU, services

## Configuration

Use the web UI at `/admin/config` or edit `config.example.yaml`.  
See `scripts/GUIDE.md` for detailed documentation.

```yaml
services:
  vllm_qwen27b:
    name: "Qwen3.6-27B (vLLM BF16)"
    backend: "vllm"
    role: "llm"
    base_url: "http://127.0.0.1:8002"
    systemd_unit: "vllm-qwen27b.service"
    process_patterns: ["vllm serve"]
    model_detect_pattern: "(?i)qwen36-27b"
```

## Admin Panel

- `/admin/panel` — start/stop/force-kill services
- `/admin/config` — audit machine, add/edit/delete services, generate systemd units
- Password: `python change_admin_password.py`

## License

MIT