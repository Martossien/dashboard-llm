# Phase 1.0 — Diagnostic LOT 1 (2026-04-30 17:04)

## État initial

| Indicateur | Valeur |
|---|---|
| Tests | 438 passed |
| compileall | OK |
| Working tree | clean |
| Commits | 9 |

## Fichiers concernés

| Fichier | Lignes | Analyse |
|---|---|---|
| `app_factory.py` | 224 | Trop de responsabilités dans `create_full_app()` |
| `monitor.py` | 78 | Wrapper correct, mais recrée des partials |
| `ops.py` | 202 | Duplique `control.py` pour start/stop |
| `control.py` | 297 | ServiceController déjà propre |

## Dépendance des tests à monitor.py

~70 imports de tests ciblent `monitor.py` :
- `test_config.py` : 8 imports (load_config, validate_config, DEFAULT_CONFIG)
- `test_utils.py` : ~35 imports (join_url, parse_bool, parse_list, deep_update, etc.)
- `test_logs.py` : 10 imports (tail_log_lines, read_journalctl_logs)
- `test_api_contract.py` : 4 imports (CONFIG, get_services_status)
- `test_phase678_combined.py` : 3 imports
- `conftest.py` : 3 imports (fixtures via `import monitor`)

## Risques repérés

1. **taille `create_full_app()`** : 224 lignes, difficile à maintenir et tester isolément
2. **duplication ops/control** : deux chemins start/stop, risque de divergence
3. **dépendance tests → monitor.py** : les tests devraient importer les vrais modules
4. **routes admin POST sans CSRF** : routes start/stop/restart/force_stop exposées

## Fichiers prioritaires Phase 1.1

- `llm_dashboard/app_factory.py` : split en sous-fonctions
- `llm_dashboard/runtime.py` (nouveau) : RuntimeDependencies
