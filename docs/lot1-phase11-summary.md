# Phase 1.1 — Extraction des dépendances runtime (2026-04-30)

## Résumé

Création de `llm_dashboard/runtime.py` avec `RuntimeDependencies` et `create_runtime_dependencies()`.
Découpage de `create_full_app()` en fonctions spécialisées.

## Fichiers modifiés

| Fichier | Avant | Après |
|---|---|---|
| `llm_dashboard/app_factory.py` | 224 lignes | 127 lignes |
| `llm_dashboard/runtime.py` | — | NOUVEAU, 228 lignes |

## Nouvelles fonctions

- `create_runtime_dependencies(config)` → `RuntimeDependencies`
- `register_routes(app, config, deps)` → `None`
- `setup_signal_handlers(gpu_monitor)` → `None`
- `create_full_app(config_path, setup_signals)` → orchestrateur (63 lignes)

## RuntimeDependencies

Dataclass contenant toutes les dépendances :
- `config`, `runner`, `gpu_monitor`, `model_cache`
- 18 callables (partials ou closures)
- `create_controller()` pour le ServiceController
- Testable sans Flask

## Tests ajoutés

- `tests/test_lot1_phase11.py` — 13 tests :
  - `create_runtime_dependencies()` retourne RuntimeDependencies
  - `runner` est un CommandRunner
  - `gpu_monitor` est mockable
  - Les callables sont appelables
  - Aucune route Flask créée
  - `create_full_app(setup_signals=False)` n'enregistre pas les handlers
  - `create_full_app(setup_signals=True)` enregistre les handlers
  - Accepte config_path
  - `register_routes()` enregistre les endpoints attendus
  - Pas de lancement serveur à l'import
  - ModelCache defaults et to_dict

## Résultat
```
451 passed in 17.27s — compileall OK
```
