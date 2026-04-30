# Final Correction Report (2026-05-01)

## Résumé

Passe corrective finale — tous les critères d'acceptation sont remplis.

## Problèmes corrigés

| # | Problème | Correction |
|---|---|---|
| 1 | Import circulaire `factory.py` ↔ `control.py` | Retiré |
| 2 | `_kill_gpu_processes` lit `vram_mib` seulement | `process_vram_mib()` accepte les deux schémas |
| 3 | `stop_all_llm_as_dicts` double arrêt | `processed_keys` set |
| 4 | Config admin/gpu_processes sans validation ENV | Overrides + validateurs |
| 5 | CSRF token injecté en string brute | `tojson` |
| 6 | CSRF erreur format incohérent | `csrf_failed` uniforme |
| 7 | `tr.innerHTML` XSS GPU process UI | `createElement` + `textContent` |
| 8 | JS accolade en trop | Braces 109/109 |
| 9 | `/api/data` collecte 3x les processus | Appel unique |
| 10 | `psutil.Process` dans la couche web | Retiré |
| 11 | `guess_gpu_process_service` retourne `None` | Retourne toujours `str` |
| 12 | Ordre guess: `llama_cpp` avant `vllm` | `vllm` avant `llama_cpp` |
| 13 | `normalize_gpu_process_dict` lève sur PID/VRAM invalide | `_safe_int`/`_safe_float` |
| 14 | CSS GPU Process Viewer dans bloc mobile | `@media` fermé avant GPU styles |
| 15 | API `max_processes` sans tri préalable | Tri AVANT limite |
| 16 | Prometheus vendor global (1er process) | Per-process vendor |
| 17 | Prometheus `except Exception: pass` | Warning loggé |
| 18 | `ServiceController` lève sur PID absent/invalide | `_safe_process_pid()` |
| 19 | API/admin sort/total fragile | `process_vram_mib()` partout |
| 20 | Prometheus `gpu_index=None` → `"None"` | `"unknown"` |

## Résultat final

- `python -m compileall .` : **OK**
- `pytest -q` : **523 passed**
- `python -m compileall llm_dashboard/ monitor.py` : **OK**

## Dette restante

- `ops.py` = adaptateur legacy (pas de suppression prévue)
- `monitor.py` = wrapper compatibilité pour tests
- Pas de backend AMD/Intel
