# Architecture Map — dashboard-llm

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

## Problèmes de qualité immédiats identifiés

### 1. Code legacy mort dans control.py (lignes 299-330)
- `check_service_is_running(svc_conf)` — référence `run_subprocess_check_output()` (inexistante)
- `kill_gpu_processes()` — référence `_init_controller()` (inexistante dans ce module)

### 2. Fonctions standalone orphelines dans admin_auth.py (lignes 76-90)
- `admin_login_required()` — référence `CONFIG` (global non défini dans ce module)
- `check_admin_password()` — référence `CONFIG` (global non défini dans ce module)
- Ces fonctions sont dupliquées dans monitor.py (versions avec dépendances correctes)

### 3. app_factory.py utilise importlib pour charger monitor.py
- `importlib.util.spec_from_file_location` — pattern fragile
- Devrait appeler directement la factory interne

### 4. monitor.py est un méga-orchestrateur
- Charge la config
- Crée CommandRunner
- Crée GPUMonitor
- Crée tous les partials
- Wire toutes les routes
- Enregistre les signal handlers
- Expose `app` et `CONFIG` comme module-level globals

### 5. Duplication ops.py / control.py
- Deux implémentations de start/stop coexistent
- `ops.py` = adaptateur ancienne API
- `control.py` = nouvelle API ServiceController
- monitor.py utilise `ops.py` pour les partials, pas `control.py`

### 6. admin_auth.py: classes utilisent monitor.py pour l'injection
- Les classes `AdminAuthRoutes`, `AdminPanelRoute`, `AdminAPIRoutes` sont propres
- Mais monitor.py doit créer et injecter `admin_login_required` et `check_admin_password`
