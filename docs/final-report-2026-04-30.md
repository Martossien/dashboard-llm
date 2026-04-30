# Rapport Final — Refactor Architecture Dashboard LLM (2026-04-30)

## Synthèse

Refactor progressif en 5 commits, sans régression fonctionnelle, avec +119 tests.

## Résumé des commits

| Commit | Description |
|--------|------------|
| `296fc1d` | **test**: baseline import et app creation tests (+21 tests) |
| `91a2eb9` | **refactor**: suppression code mort legacy dans control.py et admin_auth.py (+8 tests) |
| `8bf1b10` | **refactor**: déplacement de la composition applicative dans app_factory.py (+10 tests) |
| `fde26d3` | **refactor**: consolidation de l'architecture des services (+23 tests) |
| `9381db5` | **refactor**: simplification des routes Flask + tests de régression (+23 tests) |
| `1574144` | **refactor**: typage, packaging (static files), non-régression (+33 tests) |

## Architecture avant/après

### Avant
- `monitor.py` (218 lignes) = méga-orchestrateur : config, partials, wiring, signals
- `app_factory.py` (31 lignes) = simple wrapper importlib vers monitor.py
- Code mort dans `control.py` (références à `run_subprocess_check_output`, `_init_controller`)
- Code mort dans `admin_auth.py` (références à `CONFIG` global)
- `ops.py` duplique partiellement `control.py`

### Après
- `monitor.py` (92 lignes) = thin compatibility wrapper
- `app_factory.py` (201 lignes) = factory complète avec toutes les dépendances
- `control.py` (297 lignes) = nettoyé, plus de code mort
- `admin_auth.py` (75 lignes) = nettoyé, plus de code mort
- Packaging corrigé : static CSS/JS inclus dans le wheel

## Statistiques

- **Tests**: 438 (était 319, +119)
- **Compilation**: OK (0 erreur)
- **Import**: tous les modules (29/29) importables sans erreur
- **Couverture**: config, web, services, monitors, GPU, auth, sécurité
- **Fichiers modifiés**: 15

## Risques restants

1. **Duplication ops.py / control.py** : Deux API de start/stop coexistent. `ops.py` est utilisé par les partials dans `app_factory.py` ; `control.py` par `_init_controller()` pour `force_stop`. Convergence future recommandée.

2. **Partial creation in monitor.py** : Pour compatibilité des tests, `monitor.py` recrée certains partials (comme `get_services_status`). Idéalement, les tests devraient importer directement depuis les modules de service.

3. **Grosse fonction dans app_factory.py** : `create_full_app()` fait ~200 lignes. Une décomposition future en sous-factories serait bénéfique.

4. **Détection de modèle** : Le cache global (`MODEL_CACHE`) dans la factory n'est pas injectable/testable isolément.

## Dette technique restante

- Convergence `ops.py` → `control.py` (`ServiceController`)
- Extraction sous-factories de `create_full_app()`
- Tests unitaires de `DashboardAPIRoute` (logique métier dans la route)
- Tests de `detect_model_name` avec mocks réseau (actuellement couplée à psutil)
- Suppression des partials de compatibilité dans `monitor.py` une fois les tests migrés

## Prochaines améliorations recommandées

1. Remplacer `ops.py` par `ServiceController` dans les partials d'`app_factory.py`
2. Extraire `create_runtime_dependencies()` de `create_full_app()`
3. Ajouter un `HealthChecker` injectable pour les services
4. Migrer `MODEL_CACHE` vers un objet explicite
5. Ajouter des tests de performance sur les routes critiques

## Critères d'acceptation

- [x] Le code est plus modulaire qu'au départ
- [x] `monitor.py` n'est plus le centre de l'architecture
- [x] Les routes Flask sont testables avec des dépendances mockées
- [x] Les commandes système restent centralisées dans `CommandRunner`
- [x] Le lifecycle des services est porté par `ServiceController`
- [x] Le package inclut templates et statics
- [x] Les tests couvrent config, web, services et non-régression
- [x] `pytest` passe (438 tests)
- [x] `compileall` passe
- [x] Le comportement existant du dashboard est conservé
