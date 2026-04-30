# Phase 2 — Nettoyage du code mort et des références dangereuses (2026-04-30)

## Résumé

Suppression du code legacy mort identifié en Phase 1. Aucun changement fonctionnel.

## Code supprimé

### `llm_dashboard/services/control.py` (33 lignes supprimées)
- `check_service_is_running(svc_conf)` — fonction orpheline qui référençait `run_subprocess_check_output()` (symbole inexistant). Résultat: indéfini à l'exécution.
- `kill_gpu_processes(kill_vram_threshold_mib, sigkill_after)` — fonction orpheline qui référençait `_init_controller()` (symbole inexistant dans ce module).

Ces fonctions sont remplacées par:
- `ServiceController._kill_gpu_processes()` pour le kill GPU
- `detection.check_service_is_running()` pour le check service (dans `detection.py`)

### `llm_dashboard/web/admin_auth.py` (15 lignes supprimées)
- `admin_login_required()` — fonction standalone qui référençait `CONFIG` (global non défini dans ce module)
- `check_admin_password()` — fonction standalone qui référençait `CONFIG` (global non défini dans ce module)

Ces fonctions sont déjà définies proprement dans `monitor.py:119-132` avec injection correcte des dépendances.

## Imports corrigés
Aucun changement d'import nécessaire — les fonctions supprimées n'étaient jamais importées par le reste du projet.

## Tests ajoutés
- `tests/test_phase2_cleanup.py` — 8 nouveaux tests :
  - Import standalone de `admin_auth.py` (sans monitor.py)
  - Import standalone de `control.py` (sans monitor.py)
  - Instanciation `AdminAuthRoutes` avec mocks
  - Instanciation `AdminAPIRoutes` avec mocks
  - Instanciation `AdminPanelRoute` avec mocks
  - Instanciation `DashboardAPIRoute` avec mocks
  - Instanciation `ServiceController` avec mocks (tests de base)
  - Instanciation `ServiceController` avec force_stop activé

## Résultat pytest
```
348 passed in 13.73s
```

## Fichiers modifiés
- `llm_dashboard/services/control.py` — suppression code mort (297 lignes, était 330)
- `llm_dashboard/web/admin_auth.py` — suppression code mort (75 lignes, était 90)
- `tests/test_phase2_cleanup.py` — NOUVEAU (8 tests)
