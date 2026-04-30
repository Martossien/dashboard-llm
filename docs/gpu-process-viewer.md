# GPU Process Viewer

## Objectif

Afficher les processus utilisant les GPUs NVIDIA en temps réel, avec enrichissement (nom, utilisateur, commande, service deviné).

## Schéma JSON

```json
{
  "pid": 1234,
  "gpu_index": 0,
  "process_name": "VLLM::EngineCore",
  "used_vram_mib": 24576.0,
  "username": "root",
  "command": "python -m vllm.entrypoints...",
  "service_guess": "vllm",
  "backend": "nvidia",
  "gpu_uuid": "GPU-abc123"
}
```

## Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/v1/gpus/processes` | Non | Canonical, processus triés par VRAM décroissant |
| `GET /api/v1/gpu/processes` | Non | Alias compatible |
| `GET /api/admin/gpu/processes` | Oui | Admin, même format |

## Réponse

```json
{
  "processes": [...],
  "count": 1,
  "total_vram_mib": 31668.0,
  "enabled": true
}
```

## Configuration

```yaml
gpu_processes:
  enable: true          # Activer la collecte
  show_command: true    # Afficher la ligne de commande
  max_processes: 100    # Nombre max de processus
```

Variables d'environnement :
- `DASHBOARD_GPU_PROCESSES_ENABLE`
- `DASHBOARD_GPU_PROCESSES_SHOW_COMMAND`
- `DASHBOARD_GPU_PROCESSES_MAX`

## Métriques Prometheus

```
gpu_process_count{gpu_index="0",vendor="nvidia"} 1
gpu_process_memory_used_mib{pid="1234",gpu_index="0",process_name="python",service="vllm",vendor="nvidia"} 24576
gpu_process_memory_total_mib{vendor="nvidia"} 24576
```

## Sécurité

- Pas de bouton kill dans le dashboard public
- `show_command=false` masque la commande
- Pas de `username` ni `command` dans les labels Prometheus

## Limitations

- NVIDIA prioritaire (NVML > nvidia-smi)
- Fallback nvidia-smi sans GPU index
- `service_guess` heuristique (peut être `unknown`)
- Sans GPU : retourne liste vide
