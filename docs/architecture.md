# Architecture — Dashboard LLM

## Point d'entrée CLI

```
llm-dashboard                    # via pyproject.toml [project.scripts]
  → llm_dashboard.cli.main()
    → llm_dashboard.app_factory.create_full_app()
    → app.run(...)
```

**Alternative** : `python monitor.py` (compatibilité legacy).

## Factory Flask

`llm_dashboard.app_factory.create_full_app(config_path=None, setup_signals=True)`

1. Charge la configuration (`load_config`)
2. Crée les dépendances runtime (CommandRunner, GPUMonitor)
3. Crée les partials (detection, logs, timings, ops)
4. Crée l'app Flask (`create_app`)
5. Wire les routes (AdminAuth, AdminPanel, AdminAPI, DashboardAPI, ConfigPanel, ConfigAPI, PublicAPI)
6. Enregistre les signal handlers (SIGINT, SIGTERM)
7. Retourne `(app, config)`

## Configuration

- `config.py` : fonctions pures de chargement/validation YAML
- Environnement : `DASHBOARD_*` overrides
- Validation : plages de ports, URLs, types, listes
- `models.py` : `ServiceConfig` (dataclass), `normalize_services_config()`

## CommandRunner

Module unique autorisé à exécuter des commandes système :
- Systemd : `is-active`, `start`, `stop`, `kill`
- Réseau : `fuser_kill_port`
- Logs : `journalctl_unit`
- GPU : `nvidia_smi_query_*`, `nvidia_smi_power_limit`
- Process : `kill_pid`

**Sécurité** : validation stricte (regex systemd, bornes ports, signaux TERM/KILL).

## ServiceController

Cycle de vie des services :
- `start_service(key)` — vérifie VRAM, gère les groupes exclusifs, démarre systemd
- `stop_service(key)` — arrêt propre + fuser fallback
- `restart_service(key)` — stop + 2s + start
- `force_stop_service(key)` — arrêt agressif (gardé par `allow_force_stop`)
- `stop_group(group)` — arrêt groupé
- `terminate_pid(pid, signal)` — signal à un processus

## ServiceRegistry

Index immuable des services (pur, sans I/O) :
- `get(key)` → `ServiceConfig`
- `by_role(role)` → `list[ServiceConfig]`
- `by_group(group)` → `list[ServiceConfig]`
- `monitorable()`, `controllable()`, `llm_services()`, `auxiliary_services()`

## Filtrage intelligent des logs

Module `monitors/logs.py` :
- `LOG_FILTER_PRESETS` — dictionnaire de patterns regex nommés (uvicorn_access, werkzeug_access, health_check_serving, etc.)
- `BACKEND_LOG_FILTERS` — mapping backend → liste de presets à appliquer
- `_resolve_filter_patterns(svc_config)` — résout les patterns actifs selon le backend et le paramètre `log_filter` du service
- `default` : filtre auto selon le backend (recommandé)
- `verbose` : aucun filtrage (mode debug)

Backends supportés pour le filtrage : vllm, ik_llama.cpp, llama.cpp, proxy, ollama, sglang, lmstudio, gradio.

## GPUMonitor

Façade unifiée multi-backend :
- `NvidiaBackend` : pynvml (préféré) ou nvidia-smi (fallback)
- `NoGPUBackend` : retourne liste vide

## Routes publiques

| Route | Méthode | Description |
|-------|---------|-------------|
| `/` | GET | Dashboard HTML |
| `/health` | GET | Health check JSON |
| `/help` | GET | Page d'aide |
| `/api/data` | GET | Données dashboard JSON (inclut `active_llm_service_name`, `active_llama_service_name`) |
| `/metrics` | GET | Prometheus text |
| `/api/v1/gpus` | GET | GPUs JSON |
| `/api/v1/services` | GET | Services JSON |
| `/api/v1/metrics` | GET | Métriques JSON |
| `/api/v1/gpus/processes` | GET | Processus GPU JSON |

## Routes admin

| Route | Méthode | Auth |
|-------|---------|------|
| `/admin` | GET | Non |
| `/admin/login` | POST | Non |
| `/admin/logout` | GET | Non |
| `/admin/panel` | GET | Oui |
| `/admin/config` | GET | Oui |
| `/api/admin/status` | GET | Oui |
| `/api/admin/start` | POST | Oui |
| `/api/admin/stop` | POST | Oui |
| `/api/admin/restart` | POST | Oui |
| `/api/admin/force_stop` | POST | Oui |
| `/api/admin/stop_all_llm` | POST | Oui |
| `/api/admin/vram` | GET | Oui |
| `/api/admin/gpu/processes` | GET | Oui |
| `/api/admin/config/audit` | GET | Oui |
| `/api/admin/config/services` | GET | Oui |
| `/api/admin/config/service` | POST | Oui |
| `/api/admin/config/service/<key>` | DELETE | Oui |
| `/api/admin/config/backend-defaults` | GET | Oui |
| `/api/admin/config/systemd/generate` | POST | Oui |
| `/api/admin/config/systemd/install` | POST | Oui |
| `/api/admin/config/systemd/read` | GET | Oui |
| `/api/admin/config/restart` | POST | Oui |

## Stratégie de tests

- **541 tests** : unitaires, routes, intégration, import
- **Unitaires** : config, CommandRunner, ServiceController, ServiceRegistry, pure functions, log filtering presets
- **Routes** : Flask test_client avec mocks (pas d'appels système réels)
- **Contrat API** : vérifie les champs `active_llm_service_name` et `active_llama_service_name` dans `/api/data`
- **Intégration** : `create_full_app()` + test_client sur routes publiques
- **Import** : tous les modules importables sans erreur
- **Non-régression** : env overrides, validation, auth, sécurité commandes, merge config service

## Exécution

```bash
# Installation
pip install -e ".[dev]"

# Tests
pytest -q

# Lancement local
python -m llm_dashboard
# ou
python monitor.py
```
