# Phase 3 — Réduction du rôle central de monitor.py (2026-04-30)

## Résumé

Transformation de `monitor.py` de méga-orchestrateur en thin wrapper. La composition applicative est maintenant dans `app_factory.py`.

## Responsabilités retirées de monitor.py

| Responsabilité | Ancien | Nouveau |
|---|---|---|
| Chargement config | monitor.py | app_factory.py |
| Création CommandRunner | monitor.py | app_factory.py |
| Création GPUMonitor | monitor.py | app_factory.py |
| Création partials (~15) | monitor.py | app_factory.py |
| Wiring routes | monitor.py | app_factory.py |
| Signal handlers | monitor.py | app_factory.py |
| Side effects (psutil, load_startup_stats) | monitor.py (import) | app_factory.py (factory) |

## Nouvelle factory (`app_factory.py`)

`create_full_app(config_path=None, setup_signals=True)` — 201 lignes :
- Charge la configuration
- Crée CommandRunner, GPUMonitor, partials
- Crée l'app Flask (`create_app` du module web)
- Wire toutes les routes (AdminAuth, AdminPanel, AdminAPI, DashboardAPI, Public API)
- Enregistre les signal handlers (optionnel via `setup_signals=False`)
- Retourne `(app, config)`

Suppression de `importlib.util.spec_from_file_location`.

## Compatibilité conservée

`monitor.py` (35 lignes, était 218) :
- Appelle `create_full_app()` pour obtenir `app` et `CONFIG`
- Re-exporte les symboles importés par les tests (`load_config`, `validate_config`, `join_url`, `tail_log_lines`, etc.)
- Re-crée quelques partials pour compatibilité (`get_services_status`, etc.)
- `import monitor` fonctionne toujours, `monitor.app` et `monitor.CONFIG` sont des variables de module

## Tests ajoutés
- `tests/test_phase3_factory.py` — 10 nouveaux tests :
  - `create_full_app()` retourne app+config
  - Accepte `config_path`
  - Option `setup_signals=False`
  - Routes `/health`, `/`, `/metrics` enregistrées
  - Vérification exhaustive des 18 routes attendues
  - L'import de `app_factory` ne lance pas le serveur
  - `import monitor` toujours possible
  - `cli.main` peut mock l'app.run

## Tests mis à jour
- `tests/test_web_routes.py` — 5 tests d'analyse de source mis à jour pour refléter la nouvelle architecture

## Résultat pytest
```
359 passed in 13.99s
```

## Fichiers modifiés
- `llm_dashboard/app_factory.py` — réécriture complète (201 lignes, était 31)
- `monitor.py` — thin wrapper (92 lignes, était 218)
- `tests/test_phase3_factory.py` — NOUVEAU (10 tests)
- `tests/test_web_routes.py` — 5 tests d'analyse de source mis à jour
