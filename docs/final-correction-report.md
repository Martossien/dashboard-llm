# Final Correction Report (2026-05-01)

## Problèmes corrigés

| # | Problème | Correction |
|---|---|---|
| 1 | Import circulaire `factory.py` ↔ `control.py` | Retiré l'import de factory dans control.py |
| 2 | `_kill_gpu_processes` lit `vram_mib` seulement | Helper `process_vram_mib()` accepte les deux schémas |
| 3 | `stop_all_llm_as_dicts` double arrêt | Déduplication avec `processed_keys` set |
| 4 | Config admin/gpu_processes sans validation ENV | 7 overrides + validateurs ajoutés |
| 5 | CSRF token injecté en string brute | `tojson` dans admin.html |
| 6 | CSRF erreur format incohérent | `csrf_failed` uniforme |
| 7 | `tr.innerHTML` XSS dans GPU process UI | `createElement` + `textContent` |
| 8 | JavaScript accolade en trop | Braces 109/109 |
| 9 | `/api/data` collecte 3x les processus | Appel unique dans `api_data()` |
| 10 | `psutil.Process` dans la couche web | Retiré (déjà dans NvidiaBackend) |
| 11 | `guess_gpu_process_service` retourne `None` | Retourne toujours `str` |
| 12 | Ordre guess: `llama_cpp` avant `vllm` | `vllm` avant `llama_cpp` |
| 13 | `normalize_gpu_process_dict` lève sur PID/VRAM invalide | `_safe_int` / `_safe_float` |
| 14 | Prometheus `gpu_process_count` sans `gpu_index` | Agrégé par `(gpu_index, vendor)` |
| 15 | API publique ignore `gpu_processes.enable` | Config respectée, `enabled` dans le payload |
| 16 | UI masquée quand 0 processus | Reste visible avec état vide |

## Problèmes restants hors scope

- `ops.py` utilise encore une logique procédurale (adaptateur, pas supprimable)
- `monitor.py` recrée des partials pour compatibilité tests
- Pas de backend AMD/Intel
- Pas de TUI

## Résultat final

- **compileall** : OK
- **pytest** : 491 passed
- **Endpoints** : `/api/v1/gpus/processes`, `/api/v1/gpu/processes`, `/api/admin/gpu/processes`
- **UI** : GPU Process Viewer avec badges service, état vide visible
- **CSRF** : Token généré/login, injecté/tojson, vérifié/compare_digest

## Dette technique restante

- `ops.py` → migration complète vers ServiceController
- `monitor.py` partials → suppression après migration des tests
- `admin_auth.py` → pas de génération de token dans l'endpoint séparé
