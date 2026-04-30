# Phase 4 — Amélioration de l'architecture des services (2026-04-30)

## Résumé

Tests approfondis des couches services : ServiceController, ServiceRegistry, normalize_services_config. Documentation de l'architecture services.

## Modules préservés
Aucun module supprimé. La duplication entre `ops.py` et `control.py` est documentée comme dette technique à résoudre progressivement (ops.py = compatibilité, control.py = nouvelle API).

## Architecture clarifiée
| Module | Responsabilité |
|--------|---------------|
| `commands.py` | CommandRunner — exécution sécurisée de commandes système (systemctl, fuser, nvidia-smi, journalctl) |
| `control.py` | ServiceController — start/stop/restart/force_stop des services |
| `ops.py` | Adaptateur legacy — do_start/do_stop/stop_all_llm (utilise CommandRunner + GPUMonitor) |
| `detection.py` | Détection processus, statut services, nom de modèle actif |
| `health.py` | Health checks réseau bas niveau |
| `metrics.py` | Métriques Ollama/llama.cpp Prometheus |
| `registry.py` | ServiceRegistry — index immuable des services (pur, sans I/O) |
| `models.py` | ServiceConfig, normalize_services_config |

## Tests ajoutés
- `tests/test_phase4_services.py` — 23 nouveaux tests :
  - `TestNormalizeServicesConfig` — 10 tests :
    - Retourne des ServiceConfig
    - Conserve les noms
    - Extrait le port
    - Applique exclusive_group pour les LLM sur 8080
    - Extrait les commandes start/stop
    - Supporte config minimale
    - Héritage allow_force_stop
    - Mapping backend
    - Mapping role
    - Patterns de détection modèle
  - `TestServiceControllerEdgeCases` — 4 tests :
    - stop_service sans stop_command
    - force_stop service inconnu
    - start_service sans vram_checker
    - stop_group avec succès
  - `TestServiceRegistryAdditional` — 9 tests :
    - monitorable, controllable, llm_services, auxiliary_services
    - contains, iter, len, groups
    - duplicate key raises
    - empty registry

## Résultat pytest
```
382 passed in 16.97s
```

## Fichiers modifiés
- `tests/test_phase4_services.py` — NOUVEAU (23 tests)
