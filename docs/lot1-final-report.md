# LOT 1 — Rapport final (2026-04-30)

## Résumé

Consolidation technique post-refactor en 4 phases.

| Phase | Description | Commit | Tests |
|---|---|---|---|
| 1.0 | Baseline et diagnostic | — | 438 ref |
| 1.1 | Extraction des dépendances runtime | `76a019e` | +13 |
| 1.2 | Convergence ops.py → ServiceController | `a02dfb7` | +9 |
| 1.3 | Réduction dépendance tests à monitor.py | `39645ab` | +3 |
| 1.4 | Durcissement CSRF admin POST | `39645ab` | +6 |

## Résultat

- **Tests**: 469 (était 438, +31)
- **compileall**: OK
- **469 passed in 22.43s**

## Ce qui a changé

### Phase 1.1
- `runtime.py` créé : `RuntimeDependencies` + `create_runtime_dependencies()`
- `app_factory.py` réduit de 224 à 127 lignes
- `create_full_app()` décomposée en `register_routes()` + `setup_signal_handlers()`
- `ModelCache` dataclass remplace le dict local

### Phase 1.2
- `create_service_controller_from_config()` ajouté dans `control.py`
- Tests d'adaptation `ops.py` → `ServiceController`

### Phase 1.3
- Tests de compatibilité `monitor.py` (import, app, CONFIG, run)

### Phase 1.4
- CSRF configurable sur les routes admin POST
- `admin.csrf_enabled` (défaut: false)
- `admin.csrf_header` (défaut: X-CSRF-Token)
- 5 endpoints POST protégés

## Dette restante LOT 1
- `ops.py` utilise encore la logique procédurale (délégation partielle)
- Tests non encore migrés de `monitor.py` vers modules réels (sécurité)
- `admin_auth.py` ne génère pas de `csrf_token` dans la session
