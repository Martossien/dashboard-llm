# Guide utilisateur — dashboard-llm

## Démarrage rapide

```bash
sudo systemctl start dashboard-llm   # Port 5001
sudo systemctl enable dashboard-llm  # Auto-start au boot
```

Accès : `http://localhost:5001` (dashboard), `http://localhost:5001/admin` (panel admin), `http://localhost:5001/admin/config` (configuration).

## Architecture

```
┌──────────────────────────────────────────────┐
│                     Dashboard-LLM             │
│                   (Flask, port 5001)           │
├──────────────────────────────────────────────┤
│ LLM Engines  │  Projets       │  Surveillance  │
│ (load models)│  (use API)     │  GPU, logs     │
├──────────────┼────────────────┼────────────────┤
│ vLLM Qwen27B │ Claude Proxy   │ 8x RTX 3090    │
│ llama heretic│ Voxtral STT    │ VRAM, temp     │
│ ikllama MTP  │                │ Token rates    │
│ minimax M2.7 │                │ Service logs   │
└──────────────┴────────────────┴────────────────┘
```

## Concepts

### Service
Un service est une instance d'un chargeur (backend) servant un modèle sur un port.
Exemple : `vllm_qwen27b` = vLLM + Qwen3.6-27B BF16 sur port 8002.

### Backend (chargeur)
Le logiciel qui charge et sert le modèle : vLLM, llama.cpp, ik_llama.cpp, SGLang, Ollama, LM Studio.

### Groupe exclusif
Services partageant un port. Un seul peut être actif à la fois.
Exemple : `llm_8030` contient `llama_qwen27b_heretic`, `ikllama_qwen27b_mtp`, `llama_qwen35b_moe`.

### Projet
Application qui utilise l'API des LLM sans charger de modèle.
Exemple : Claude Code Proxy, Speech-to-Text (Voxtral), open-webui.

## Page de configuration (/admin/config)

### Onglet Audit
Scanne la machine automatiquement :
- **Backends** : détecte vLLM, llama.cpp, ik_llama.cpp, SGLang, Ollama, LM Studio
- **Modèles** : scanne `~/models/` ET `~/.cache/lm-studio/models/`
- **Modèles shardés** : détecte automatiquement le premier fichier (`00001-of-NNNNN.gguf`)
- **Ports** : liste les ports LLM ouverts (8000-30100)
- **Services systemd** : liste les unités actives
- **Conda envs** : liste les environnements
- **GPUs** : modèle, VRAM totale

**Cliquez sur n'importe quel élément pour pré-remplir le formulaire.**

### Onglet Ajouter
Formulaire complet pour définir un service. Champs principaux :

1. **Clé** : identifiant unique (ex: `vllm_qwen27b`). En lecture seule lors de l'édition.
2. **Rôle** : LLM Engine, Projet ou Auxiliaire
3. **Backend** : chargeur utilisé (pré-rempli si cliqué depuis l'audit). Remplit automatiquement les valeurs par défaut.
4. **Nom affiché** : visible dans le dashboard
5. **Port** : port TCP (pré-rempli si cliqué depuis l'audit)
6. **Base URL** : `http://127.0.0.1:<port>` (auto-généré)
7. **Health endpoint** : chemin du health check (ex: `/health`, `/`). Auto-rempli par backend.
8. **Models endpoint** : chemin pour détecter le modèle (ex: `/v1/models`). Laisser vide si le service n'expose pas de modèles.
9. **Timeout (s)** : délai pour les health checks (défaut: 2s)
10. **Systemd unit** : nom du service systemd
11. **Modèle** : chemin du fichier GGUF ou dossier HF (cliquable depuis l'audit)
12. **Log file** : fichier de log du service
13. **Filtre de logs** : `default` (filtrage auto selon le backend) ou `verbose` (tout afficher)
14. **Commande de lancement (ExecStart)** : éditable librement, template par backend
15. **Groupe exclusif** : si le service partage un port

Section **Paramètres avancés** (collapsée par défaut) :
- **Commande start/stop** : commandes système pour démarrer/arrêter le service
- **Startup time (s)** : temps de démarrage avant health check
- **Pattern détection modèle** : regex pour identifier le modèle chargé
- **Process patterns** : mots-clés pour détecter le processus
- **Process exclude** : mots-clés à exclure de la détection

**Comportement lors de l'édition** : les champs non modifiés sont conservés (merge, pas remplacement). La clé est en lecture seule. Les champs inconnus sont ignorés (whitelist). CSRF requis sur toutes les soumissions.

Contraintes de validation :
- **Clé** : lettres, chiffres, tirets, underscores uniquement (`^[a-zA-Z0-9_-]+$`)
- **Systemd unit** : format `.service` valide (`^[A-Za-z0-9_.@:-]+\.service$`)
- **Nom du service** : pas de retours à la ligne (sanitisé dans le fichier systemd)

Boutons :
- **[👁 Aperçu YAML]** : montre le YAML généré avant de sauvegarder
- **[💾 Sauvegarder]** : écrit dans `config.yaml` + redémarre le dashboard
- **[📄 Générer .service]** : preview du fichier systemd
- **[📥 Installer le service]** : écrit dans `/etc/systemd/system/`

### Onglet Services
Liste des services définis avec :
- Nom, rôle (LLM/Projet/Auxiliaire), backend, port, filtre de logs, health (🟢 UP/🔴 DOWN), systemd
- **[✏ Éditer]** : charge le service dans l'onglet Ajouter (merge, les champs manquants sont conservés)
- **[🗑 Supprimer]** : retire de config.yaml

## Filtrage intelligent des logs

Chaque service a un paramètre `log_filter` :
- `default` (recommandé) : filtre automatiquement les lignes inutiles selon le backend :
  - **vLLM** : access logs uvicorn (GET /health, /metrics, /v1/models)
  - **llama.cpp / ik_llama.cpp** : lignes répétitives (srv stop, slots idle, etc.)
  - **proxy** : access logs werkzeug, 404 /metrics, redirects /login, health checks répétitifs
  - **gradio** : access logs, 404 /metrics, health checks
  - **ollama / sglang / lmstudio** : pas de filtrage supplémentaire
- `verbose` : affiche tout, utile pour le debug

Configuré dans `/admin/config` → champ "Filtre de logs" ou dans `config.yaml` :
```yaml
services:
  mon_service:
    log_filter: default  # ou verbose
```

## Utiliser des modèles LM Studio

LM Studio télécharge les modèles dans `~/.cache/lm-studio/models/<editeur>/<modele>/`.
Ces modèles peuvent être utilisés avec llama.cpp ou ik_llama.cpp directement.

**Modèle sharded** (plusieurs fichiers `00001-of-NNNNN.gguf`) :
- Pointez vers le **premier** fichier shard
- llama.cpp/ik_llama.cpp détectent automatiquement les shards suivants
- La page config détecte ça automatiquement

Exemple :
```
Modèle LM Studio : .../MiniMax-M2.7-GGUF/MiniMax-M2.7-IQ5_K-00001-of-00005.gguf
Backend : ik_llama.cpp
Port : 8080
```

## Service systemd

Chaque LLM Engine peut être géré comme un service systemd.
Le dashboard génère le fichier `.service` automatiquement.

Commandes manuelles :
```bash
sudo systemctl start vllm-qwen27b.service
sudo systemctl stop vllm-qwen27b.service
sudo systemctl status vllm-qwen27b.service
journalctl -u vllm-qwen27b.service -f
```

L'admin panel (onglet `/admin/panel`) permet de start/stop/force kill depuis le web.

## Scripts (déprécié - utiliser systemd)

Les scripts `scripts/*/start.sh` et `scripts/*/stop.sh` sont conservés pour usage manuel
ou debug. La méthode recommandée est systemd.

```
scripts/
  GUIDE.md              ← conventions d'écriture des scripts
  .pids/                ← PID files (git-ignored)
  vllm_qwen27b/         ← un répertoire par service
    start.sh / stop.sh
  llama_qwen27b_heretic/
    start.sh / stop.sh
  ...
```

## Changer le mot de passe admin

```bash
cd ~/dashboard-llm
python change_admin_password.py
```

Le script s'auto-détecte et utilise le bon environnement conda.

## Backends supportés

| Backend | Health endpoint | Models endpoint | Métriques | Token rates | Systemd killmode | Log filter |
|---------|----------------|-----------------|-----------|-------------|------------------|------------|
| vLLM | /health | /v1/models | /metrics | ✅ (logs+metrics) | mixed | Access logs uvicorn |
| llama.cpp | /health | /v1/models | /metrics | ✅ (logs+metrics) | process | Lignes répétitives |
| ik_llama.cpp | /health | /v1/models | /metrics | ✅ (logs+metrics) | process | Lignes répétitives |
| SGLang | /health | /v1/models | /metrics | ✅ (metrics) | process | Aucun filtre |
| Ollama | / | — | — | ❌ | process | Aucun filtre |
| LM Studio | /v1/models | /v1/models | — | ❌ | process | Aucun filtre |
| Proxy | /health | — | — | ❌ | process | Access logs werkzeug |
| Gradio | / | — | — | ❌ | process | Access logs, 404 /metrics |

Les endpoints et filtres sont auto-configurés par le backend dans `/admin/config`.

## Fichiers

```
dashboard-llm/
├── config.yaml           ← configuration (NE PAS éditer à la main, utiliser /admin/config)
├── config.example.yaml   ← exemple commenté
├── requirements.txt      ← dépendances Python
├── change_admin_password.py
├── monitor.py            ← compatibilité legacy, appelle app_factory
├── llm_dashboard/        ← code source
│   ├── app_factory.py    ← factory principale (crée app + dépendances)
│   ├── config.py         ← chargement/validation YAML
│   ├── models.py         ← ServiceConfig dataclass
│   ├── runtime.py        ← RuntimeDependencies dataclass
│   ├── web/              ← routes Flask (API + pages)
│   │   ├── app.py              ← create_app()
│   │   ├── routes.py           ← /, /health, /help
│   │   ├── dashboard_api.py    ← /api/data
│   │   ├── admin_api.py        ← /api/admin/* (start/stop/status)
│   │   ├── admin_auth.py       ← /admin, /admin/login, /admin/logout
│   │   ├── admin_panel.py      ← /admin/panel
│   │   ├── config_api.py       ← /api/admin/config/* (CRUD, audit, systemd)
│   │   ├── config_panel.py     ← /admin/config (HTML)
│   │   └── metrics.py          ← /metrics + /api/v1/*
│   ├── services/         ← détection, santé, contrôle
│   │   ├── commands.py         ← CommandRunner (exécution centralisée)
│   │   ├── control.py         ← ServiceController (cycle de vie)
│   │   ├── factory.py          ← factory pour ServiceController
│   │   ├── ops.py              ← adaptateur legacy
│   │   ├── detection.py        ← détection modèle/processus/services
│   │   ├── health.py           ← health checks (HTTP + systemd)
│   │   ├── metrics.py          ← métriques Ollama/llama.cpp
│   │   └── registry.py         ← ServiceRegistry (index immuable)
│   ├── monitors/         ← GPU, logs, timings
│   │   ├── gpu/                ← GPU (NvidiaBackend, NoGPUBackend, factory)
│   │   ├── logs.py             ← logs + filtrage intelligent par backend
│   │   ├── timings.py          ← token rates (Prometheus + logs)
│   │   ├── startup.py          ← état démarrage LLM
│   │   └── system.py           ← CPU/RAM (psutil)
│   ├── templates/        ← HTML (dashboard, admin, config, help)
│   └── static/           ← CSS, JS
├── scripts/              ← scripts de lancement manuel (déprécié, utiliser systemd)
│   ├── GUIDE.md
│   └── .pids/
└── tests/                ← 541 tests
```