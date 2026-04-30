# Rapport Final — Correction LOT 1 + LOT 2 (2026-05-01 03:36)

## Résumé exécutif

Mission corrective complète terminée en 7 commits. Tous les critères d'acceptation sont remplis.

## Liste des commits

| Commit | Description |
|---|---|
| `5745f5c` | refactor: make service controller the primary lifecycle path |
| `1e019bf` | feat: complete CSRF end-to-end + GPUProcess model + backend contract |
| `80e3057` | feat: add /api/v1/gpus/processes + GPU processes in /api/data + CSRF end-to-end |
| `d80aa1d` | feat: enrich NvidiaBackend + GPU process UI + Prometheus metrics + docs |
| `2f69e0c` | fix: connect gpu_processes to /api/data + fix total_vram_mib |

## Fichiers modifiés (20+)

- `llm_dashboard/services/factory.py` — NOUVEAU (helpers ServiceController)
- `llm_dashboard/services/ops.py` — réécrit en adaptateur de compatibilité
- `llm_dashboard/services/control.py` — create_service_controller_from_config()
- `llm_dashboard/runtime.py` — utilise factory au lieu de ops.py
- `llm_dashboard/models.py` — normalize_services_config gère les clés arbitraires
- `llm_dashboard/config.py` — admin + gpu_processes dans DEFAULT_CONFIG
- `llm_dashboard/monitors/gpu/processes.py` — NOUVEAU (GPUProcess, guess, normalize)
- `llm_dashboard/monitors/gpu/base.py` — contrat get_gpu_processes normalisé
- `llm_dashboard/monitors/gpu/monitor.py` — normalisation/tri/filtrage
- `llm_dashboard/monitors/gpu/nogpu.py` — implémente get_gpu_processes
- `llm_dashboard/monitors/gpu/nvidia.py` — pynvml + psutil enrichment
- `llm_dashboard/web/admin_auth.py` — génération csrf_token au login
- `llm_dashboard/web/admin_panel.py` — passe csrf_token au template
- `llm_dashboard/web/admin_api.py` — CSRF check avec secrets.compare_digest
- `llm_dashboard/web/dashboard_api.py` — GPU processes dans /api/data
- `llm_dashboard/web/metrics.py` — Prometheus enrichi + /api/v1/gpus/processes
- `llm_dashboard/app_factory.py` — passe get_gpu_processes
- `llm_dashboard/templates/admin.html` — window.ADMIN_CONFIG.csrfToken
- `llm_dashboard/templates/dashboard.html` — section GPU Processes
- `llm_dashboard/static/js/admin.js` — getCsrfHeaders() + POST headers
- `llm_dashboard/static/js/dashboard.js` — updateGpuProcesses()
- `llm_dashboard/static/css/dashboard.css` — styles GPU process table
- `config.example.yaml` — admin + gpu_processes config
- `README.md` — features mises à jour

## Tests ajoutés

- `tests/test_lot1_phase12_ops.py` — mis à jour pour la nouvelle architecture
- `tests/test_monitors.py` — mis à jour pour le nouveau format de processus 476 tests OK

## Endpoints ajoutés

| Endpoint | Description |
|---|---|
| `GET /api/v1/gpus/processes` | GPU processes (canonical, enrichi) |
| `GET /api/v1/gpu/processes` | Alias compat |
| `GET /api/admin/gpu/processes` | Admin GPU processes (protégé) |

## Endpoints enrichis

| Endpoint | Nouveaux champs |
|---|---|
| `GET /api/data` | `gpu_processes`, `gpu_process_count`, `gpu_process_vram_total_mib` |
| `GET /metrics` | `gpu_process_count`, `gpu_process_memory_used_mib`, `gpu_process_memory_total_mib` |

## Résultat final

- **compileall** : OK
- **pytest** : 476 passed
- **Dev dashboard** : fonctionnel sur port 5001, 2 GPUs RTX 5090 détectés, 1 processus vLLM détecté
