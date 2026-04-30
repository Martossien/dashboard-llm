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
5. Wire les routes (AdminAuth, AdminPanel, AdminAPI, DashboardAPI, PublicAPI)
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
| `/api/data` | GET | Données dashboard JSON |
| `/metrics` | GET | Prometheus text |
| `/api/v1/gpus` | GET | GPUs JSON |
| `/api/v1/services` | GET | Services JSON |
| `/api/v1/metrics` | GET | Métriques JSON |

## Routes admin

| Route | Méthode | Auth |
|-------|---------|------|
| `/admin` | GET | Non |
| `/admin/login` | POST | Non |
| `/admin/logout` | GET | Non |
| `/admin/panel` | GET | Oui |
| `/api/admin/status` | GET | Oui |
| `/api/admin/start` | POST | Oui |
| `/api/admin/stop` | POST | Oui |
| `/api/admin/restart` | POST | Oui |
| `/api/admin/force_stop` | POST | Oui |
| `/api/admin/stop_all_llm` | POST | Oui |
| `/api/admin/vram` | GET | Oui |

## Stratégie de tests

- **Unitaires** : config, CommandRunner, ServiceController, ServiceRegistry, pure functions
- **Routes** : Flask test_client avec mocks (pas d'appels système réels)
- **Intégration** : `create_full_app()` + test_client sur routes publiques
- **Import** : tous les modules importables sans erreur
- **Non-régression** : env overrides, validation, auth, sécurité commandes

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
