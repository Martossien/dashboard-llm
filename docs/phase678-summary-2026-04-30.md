# Phase 6+7+8 — Qualité de code, packaging et non-régression (2026-04-30)

## Résumé

Améliorations de qualité de code, correction du packaging des fichiers statiques, et extension de la couverture de non-régression.

## Phase 6 — Typage et conventions
- `config.py` : annotations de type ajoutées sur toutes les fonctions publiques
- `__future__ import annotations` ajouté pour compatibilité
- Tests de fonctions pures ajoutés (`parse_bool`, `parse_list`, `deep_update`, `validate_config`)

## Phase 7 — Packaging
- `pyproject.toml` : ajout des fichiers statiques CSS/JS dans le wheel
  ```toml
  include = [
      "llm_dashboard/templates/*.html",
      "llm_dashboard/static/css/*.css",
      "llm_dashboard/static/js/*.js",
  ]
  ```
- Tests de ressources via `importlib.resources` (templates, CSS, JS)
- Test que la route `/` référence `dashboard.js`
- Test que `create_app` configure correctement `template_folder` et `static_folder`

## Phase 8 — Non-régression
- Config par défaut charge sans config.yaml
- Variables d'environnement surchargent la config
- URLs invalides remplacées par défauts
- Ports invalides rejetés
- Dashboard démarre sans GPU (NoGPUBackend)
- Backend NVIDIA est initialisable sans GPU réel (mockable)
- Routes publiques ne nécessitent pas d'auth
- Routes admin nécessitent l'auth
- Commandes système rejettent les arguments dangereux (injection systemd, port, signal)
- Dashboard fonctionne sans config utilisateur

## Résultat pytest
```
438 passed in 17.24s
```

## Fichiers modifiés
- `llm_dashboard/config.py` — annotations de type
- `pyproject.toml` — inclusion fichiers statiques
- `tests/test_phase678_combined.py` — NOUVEAU (33 tests)
