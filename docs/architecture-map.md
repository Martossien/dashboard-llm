# Architecture Map — dashboard-llm (Updated post-refactor)

**Dernière mise à jour** : 2026-04-30

## Flux de création de l'application

```
cli.py / monitor.py
  → app_factory.create_full_app(config_path, setup_signals)
    → load_config()
    → CommandRunner()
    → GPUMonitor()  (→ NvidiaBackend or NoGPUBackend)
    → partials (detection, logs, timings, ops)
    → create_app()  (→ Flask + WebRoutes)
    → wiring routes (AdminAuth, AdminPanel, AdminAPI, DashboardAPI, register_public_api)
    → signal handlers (if setup_signals=True)
    → return (app, config)
```

## monitor.py — rôle actuel

Compatibility wrapper (92 lignes, était 218) :
- Appelle `create_full_app()` et expose `app` et `CONFIG` comme globals
- Re-exporte `load_config`, `validate_config`, `DEFAULT_CONFIG`, etc. pour compatibilité des tests
- Re-crée quelques partials pour compatibilité (`get_services_status`, etc.)
- `if __name__ == '__main__'` lance le serveur

## Modules Web (llm_dashboard/web/)
| Fichier | Classe/Fonction | Rôle |
|---------|----------------|------|
| `app.py` | `create_app(config)` | Factory Flask minimale |
| `routes.py` | `WebRoutes` | Routes simples (`/`, `/health`, `/help`) |
| `dashboard_api.py` | `DashboardAPIRoute` | Route `/api/data` — JSON principal |
| `admin_api.py` | `AdminAPIRoutes` | Routes `/api/admin/*` (start/stop/status/restart/force_stop) |
| `admin_auth.py` | `AdminAuthRoutes` | Routes `/admin`, `/admin/login`, `/admin/logout` |
| `admin_panel.py` | `AdminPanelRoute` | Route `/admin/panel` (HTML) |
| `metrics.py` | `create_metrics_endpoint`, `register_public_api` | `/metrics` Prometheus + `/api/v1/*` REST |

## Modules Services (llm_dashboard/services/)
| Fichier | Classe/Fonction | Rôle |
|---------|----------------|------|
| `commands.py` | `CommandRunner`, `CommandResult` | Exécution centralisée sécurisée de commandes système |
| `control.py` | `ServiceController`, `ControlResult` | Cycle de vie start/stop/restart/force_stop |
| `ops.py` | `do_start_service`, `do_stop_service`, `stop_all_llm_engines` | Adaptateur legacy (Ancienne API start/stop) |
| `detection.py` | `detect_model_name`, `get_services_status`, `get_admin_services_status`, etc. | Détection modèle/processus/services |
| `health.py` | `check_service_health`, `check_port_is_open`, `wait_for_port_free` | Health checks réseau |
| `metrics.py` | `get_ollama_models`, `get_llama_metrics` | Métriques Ollama/llama.cpp Prometheus |
| `registry.py` | `ServiceRegistry` | Index immuable des services (pur, sans I/O) |

## Modules Monitors (llm_dashboard/monitors/)
| Fichier | Classe/Fonction | Rôle |
|---------|----------------|------|
| `gpu/monitor.py` | `GPUMonitor` | Façade unifiée GPU |
| `gpu/base.py` | `AbstractGPUBackend`, `GPUDevice` | Interface abstraite GPU |
| `gpu/factory.py` | `get_gpu_backend()` | Auto-détection NVIDIA/NoGPU |
| `gpu/nvidia.py` | `NvidiaBackend` | Backend pynvml + nvidia-smi |
| `gpu/nogpu.py` | `NoGPUBackend` | Fallback sans GPU |
| `system.py` | `get_cpu_info`, `get_ram_info` | Métriques système (psutil) |
| `logs.py` | `get_logs`, `get_client_ips`, `tail_log_lines`, `read_journalctl_logs` | Logs services |
| `timings.py` | `get_llama_timings`, `get_vllm_timings`, `extract_llama_timings`, `extract_vllm_timings` | Timings tokens/s |
| `startup.py` | `get_llama_startup_state`, `load_startup_stats`, `record_startup_duration` | État démarrage LLM |

## Configuration
| Fichier | Rôle |
|---------|------|
| `config.py` | Chargement, validation YAML, surcharges ENV, fonctions pures |
| `models.py` | `ServiceConfig` (dataclass), `normalize_services_config()` |

## Points d'entrée
| Fichier | Rôle |
|---------|------|
| `cli.py` | `main()` — CLI entry point |
| `app_factory.py` | `create_full_app()` — factory qui charge monitor.py via importlib |
| `monitor.py` | Point de compatibilité/composition — charge config, crée partials, wire routes |
| `__main__.py` | `from llm_dashboard.cli import main` |

## Dépendance à monitor.py
- `app_factory.py` → `monitor.py` (via `importlib.util.spec_from_file_location`)
- `tests/conftest.py` → `monitor.py` (via `import monitor`)
- Tous les tests dépendent de `monitor.py` pour l'import de fonctions pures (`load_config`, `validate_config`, etc.)

## Problèmes de qualité identifiés (audit 2026-05-16)

### 1. ~~Code legacy mort dans control.py (lignes 299-330)~~ — CORRIGÉ
- `check_service_is_running()` et `kill_gpu_processes()` standalone n'existent plus.
- `_kill_gpu_processes` est maintenant une méthode propre de `ServiceController`.
- `_safe_process_pid()` utilisé, pas de refs à `run_subprocess_check_output` ni `_init_controller`.

### 2. ~~Fonctions standalone orphelines dans admin_auth.py~~ — CORRIGÉ
- `AdminAuthRoutes` est une classe propre avec injection par constructeur.
- Pas de fonctions standalone `admin_login_required`/`check_admin_password` dans ce fichier.
- L'injection se fait via `runtime.py` → `is_admin_authenticated` / `check_admin_password`.

### 3. ~~app_factory.py utilise importlib pour charger monitor.py~~ — CORRIGÉ
- `app_factory.py` fait `from llm_dashboard.runtime import ...` directement.
- Pas d'`importlib` nulle part.

### 4. monitor.py — wrappers de compatibilité (toujours pertinent)
- `monitor.py` est maintenant un wrapper minimal (76 lignes) qui :
  - Re-exporte les fonctions pures pour les tests
  - Appelle `create_full_app()` et expose `app`, `CONFIG`
  - Crée des partials de compatibilité pour les tests
- **Bug actif** : lignes 21-26 importent 4 symboles supprimés de `timings.py` :
  - `extract_llama_timings` → renommé `_extract_llama_from_loglines`
  - `extract_vllm_timings` → renommé `_extract_vllm_from_loglines`
  - `LLAMA_TIMINGS` → supprimé
  - `VLLM_TIMINGS` → supprimé
- Ces imports cassent `import monitor` → 524 tests en ERROR.

### 5. ops.py / control.py — cohabitation voulue (pas un bug)
- `ops.py` = adaptateur legacy qui délègue à `ServiceController` via `factory.py`.
- `control.py` = API propre `ServiceController`.
- `runtime.py` utilise directement `factory.py`, pas `ops.py`.

### 6. ~~admin_auth.py: classes utilisent monitor.py pour l'injection~~ — CORRIGÉ
- L'injection se fait via `runtime.py` (dataclass `RuntimeDependencies`).
- `app_factory.py` wire les dépendances proprement.
- `monitor.py` n'est plus responsable de l'injection.
