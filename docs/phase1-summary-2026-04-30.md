# Phase 1 — Stabilisation minimale et diagnostic (2026-04-30)

## Résumé

Phase de diagnostic sans modification fonctionnelle. Établissement d'une baseline fiable avant refactor.

## Fichiers modifiés
- `tests/test_baseline_imports.py` — NOUVEAU (21 tests d'import et création d'app)
- `docs/architecture-map.md` — NOUVEAU (carte architecturale complète)

## Problèmes détectés (non corrigés, documentés)

### Code legacy mort
1. **`control.py:299-330`** — Fonctions `check_service_is_running(svc_conf)` et `kill_gpu_processes()` référencent `run_subprocess_check_output()` et `_init_controller()` qui n'existent pas dans ce module. Code mort.
2. **`admin_auth.py:76-90`** — Fonctions standalone `admin_login_required()` et `check_admin_password()` référencent `CONFIG` global non défini. Dupliquent les versions injectées de `monitor.py`.

### Architecture problématique
3. **`monitor.py`** est un méga-orchestrateur (218 lignes) — charge config, crée CommandRunner, GPUMonitor, tous les partials, wire les routes, enregistre les signaux.
4. **`app_factory.py`** utilise `importlib.util.spec_from_file_location` pour charger `monitor.py` — fragile.
5. **`ops.py`** duplique partiellement `control.py` — deux API de start/stop coexistent.

### Autres
6. **`admin_auth.py`** — classes propres mais monitor.py doit injecter les helpers d'auth.
7. Tests dans `conftest.py` dépendent fortement de `import monitor` (import side-effect lourd).

## Tests ajoutés
- 18 tests d'import de package/modules (`test_baseline_imports.py`)
- 3 tests de création d'app Flask minimale via `create_app()` (sans monitor.py)

## Résultat pytest
```
340 passed in 13.77s
```

## Commandes lancées
- `python -m compileall .` — OK
- `python -m pytest -q` — 340 passed

## Commit créé
À venir (fin de phase).

## Prochaines phases
- Phase 2 : Supprimer le code mort (control.py, admin_auth.py)
- Phase 3 : Réduire le rôle de monitor.py via app_factory
