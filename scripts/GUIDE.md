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

**Cliquez sur n'importe quel élément pour pré-remplir le formulaire.**

### Onglet Ajouter
Formulaire pas-à-pas :
1. **Clé** : identifiant unique (ex: `vllm_qwen27b`)
2. **Rôle** : LLM Engine ou Projet
3. **Backend** : chargeur utilisé (pré-rempli si cliqué depuis l'audit)
4. **Nom affiché** : visible dans le dashboard
5. **Port** : port TCP (pré-rempli si cliqué depuis l'audit)
6. **URL** : `http://127.0.0.1:<port>` (auto-généré)
7. **Systemd unit** : nom du service systemd
8. **Modèle** : chemin du fichier GGUF ou dossier HF (cliquable depuis l'audit)
9. **Log** : fichier de log
10. **Groupe exclusif** : si le service partage un port

Boutons :
- **[👁 Aperçu YAML]** : montre le bloc YAML généré
- **[📄 Générer .service]** : preview du fichier systemd
- **[📥 Installer le service]** : écrit dans `/etc/systemd/system/`
- **[💾 Sauvegarder]** : écrit `config.yaml` + redémarre le dashboard

### Onglet Services
Liste des services définis avec :
- Nom, rôle (LLM/Projet/Auxiliaire), backend, port, health (🟢 UP/🔴 DOWN), systemd
- **[✏ Éditer]** : charge le service dans l'onglet Ajouter
- **[🗑 Supprimer]** : retire de config.yaml

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

## Backend supporté

| Backend | Santé | Modèles | Métriques | Token rates | Systemd |
|---------|-------|---------|-----------|-------------|---------|
| vLLM | /health | /v1/models | /metrics | ✅ (logs+metrics) | mixed |
| llama.cpp | /health | /v1/models | /metrics | ✅ (logs+metrics) | process |
| ik_llama.cpp | /health | /v1/models | /metrics | ✅ (logs+metrics) | process |
| SGLang | /health | /v1/models | /metrics | ✅ (metrics) | process |
| Ollama | / | /api/tags | — | ❌ (/metrics 404) | process |
| LM Studio | /v1/models | /v1/models | — | ❌ | process |

## Fichiers

```
dashboard-llm/
├── config.yaml           ← configuration (NE PAS éditer à la main, utiliser /admin/config)
├── config.example.yaml   ← exemple commenté
├── requirements.txt      ← dépendances Python
├── change_admin_password.py
├── llm_dashboard/        ← code source
│   ├── web/              ← routes Flask (API + pages)
│   ├── services/         ← détection, santé, contrôle
│   ├── monitors/         ← GPU, logs, timings
│   ├── templates/        ← HTML (dashboard, admin, config, help)
│   └── static/           ← CSS, JS
├── scripts/              ← scripts de lancement manuel (déprécié, utiliser systemd)
│   ├── GUIDE.md
│   └── .pids/
└── tests/                ← tests unitaires
```