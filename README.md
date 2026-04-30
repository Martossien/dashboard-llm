# LLM Dashboard

Lightweight monitoring and administration dashboard for local LLM servers.

Supports **llama.cpp**, **ik_llama.cpp**, **vLLM**, **Ollama**, and any
OpenAI-compatible API. Monitor GPU usage, token rates, service health, and
manage service lifecycle (start/stop/restart) from a web interface.

## Screenshots

(Coming soon)

## Features

- Real-time GPU monitoring (NVIDIA via pynvml, multi-GPU)
- Per-service terminal logs with noise filtering
- Token rate tracking (prompt + generation tok/s)
- Prometheus /metrics endpoint (CPU, RAM, GPU, services, GPU processes)
- REST API (/api/v1/gpus, /api/v1/services, /api/v1/metrics, /api/v1/gpus/processes)
- Service lifecycle management (start/stop/restart/force-kill)
- Admin panel with CSRF protection
- GPU Process Viewer (process name, VRAM, command, user, service guess)
- Multi-backend support (llama.cpp, ik_llama.cpp, vLLM, Ollama)
- Exclusive group management (one LLM per port)
- Temperature and power monitoring
- Prometheus `/metrics` endpoint

## Quick Start

```bash
pip install llm-dashboard
cp config.example.yaml config.yaml
# Edit config.yaml with your services
python -m llm_dashboard
# Open http://localhost:5000
```

## Docker

```bash
docker compose up -d
```

## Configuration

See `config.example.yaml` for all options.

## License

MIT

## Credits

Inspired by:
- [nvitop](https://github.com/XuehaiPan/nvitop) — NVIDIA GPU process viewer
- [gpustat](https://github.com/wookayin/gpustat) — GPU monitoring CLI
- [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter) — Prometheus GPU metrics
- [oobabooga textgen](https://github.com/oobabooga/textgen) — Local LLM interface
- [CoolerControl](https://github.com/codifryed/CoolerControl) — Thermal/fan control
- [XPU Manager](https://github.com/intel/xpumanager) — Intel GPU management
- [pyrsmi](https://github.com/ROCm/pyrsmi) — AMD ROCm monitoring
