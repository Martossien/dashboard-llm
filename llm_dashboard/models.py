"""
Modeles de donnees partages.

Contient ServiceConfig (representation unifiee d'un service)
et la fonction de normalisation de l'ancienne config.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ServiceConfig:
    """Representation unifiee d'un service LLM ou auxiliaire.

    Fusionne les informations actuellement dispersees entre :
    - CONFIG["services"] (monitoring, logs, noms)
    - CONFIG["start_stop"] (administration, commandes, VRAM)
    - Heuristiques dans get_services_status(), _get_active_llama_key(), etc.

    Frozen=True garantit l'immutabilite : un ServiceConfig est cree une fois,
    jamais modifie. Les etats dynamiques (UP/DOWN, latence) sont geres par
    le ServiceRegistry (Lot 3).
    """

    key: str
    display_name: str
    backend: str                                    # "llama.cpp" | "ik_llama.cpp" | "vllm" | "ollama" | "openai" | "gradio"
    role: str = "auxiliary"                         # "llm" | "auxiliary" | "dashboard"
    exclusive_group: Optional[str] = None           # ex: "llm_8080" — services mutuellement exclusifs
    port: Optional[int] = None
    base_url: Optional[str] = None
    health_endpoint: str = "/health"
    models_endpoint: Optional[str] = None
    timeout_seconds: float = 2.0
    log_source: str = "file"                        # "file" | "journalctl" | "none"
    log_file: Optional[str] = None
    journalctl_unit: Optional[str] = None
    model_detect_pattern: Optional[str] = None     # regex sur model_on_port pour identifier ce service
    start_command: tuple[str, ...] = ()
    stop_command: tuple[str, ...] = ()
    systemd_unit: Optional[str] = None
    vram_min_mib: int = 0
    allow_force_stop: bool = False


# ============================================================================
# Normalisation de l'ancienne config (services + start_stop) -> ServiceConfig[]
# ============================================================================

# Mapping entre les cles start_stop et les cles services pour l'ancien format.
# Aujourd'hui : start_stop.glm47 ↔ services.ik_llama_cpp (detecte par heuristique)
#             start_stop.qwen36_35b_q8 ↔ services.llama_cpp
#             start_stop.qwen36_35b_udq8 ↔ services.llama_cpp (variante)
#             start_stop.qwen36_27b_vllm ↔ services.vllm
#             start_stop.ollama ↔ services.ollama
#             start_stop.voxtral_tts ↔ services.voxtral
#             start_stop.voxtral_stt ↔ services.voxtral_stt

_SS_TO_SVC = {
    "glm47": {
        "svc_key": "ik_llama_cpp",
        "backend": "ik_llama.cpp",
        "role": "llm",
        "exclusive_group": "llm_8080",
        "model_detect_pattern": "(?i)glm|ik_llama",
    },
    "qwen36_35b_udq8": {
        "svc_key": "llama_cpp",
        "backend": "llama.cpp",
        "role": "llm",
        "exclusive_group": "llm_8080",
        "model_detect_pattern": "(?i)qwen3-35b.*ud-q8",
    },
    "qwen36_35b_q8": {
        "svc_key": "llama_cpp",
        "backend": "llama.cpp",
        "role": "llm",
        "exclusive_group": "llm_8080",
        "model_detect_pattern": "(?i)qwen3-35b.*q8(?!.*ud)",
    },
    "qwen36_27b_vllm": {
        "svc_key": "vllm",
        "backend": "vllm",
        "role": "llm",
        "exclusive_group": "llm_8080",
        "model_detect_pattern": "(?i)qwen36-27b|qwen3.6-27b",
    },
    "ollama": {
        "svc_key": "ollama",
        "backend": "ollama",
        "role": "llm",
    },
    "voxtral_tts": {
        "svc_key": "voxtral",
        "backend": "gradio",
        "role": "auxiliary",
    },
    "voxtral_stt": {
        "svc_key": "voxtral_stt",
        "backend": "gradio",
        "role": "auxiliary",
    },
}


def normalize_services_config(config):
    """Normalise l'ancien format de config en liste de ServiceConfig.

    Lit config["services"] (monitoring) et config["start_stop"] (admin)
    et produit une liste unifiee de ServiceConfig.

    Cette fonction est temporaire : elle permet la migration progressive.
    La cible finale est un bloc "services:" enrichi unique dans config.yaml
    (cf. recommandations §3 Architecture cible recommandee).

    Args:
        config: dict complet de configuration (format actuel)

    Returns:
        list[ServiceConfig]: liste de tous les services enregistres,
                             ordonnes comme service_order actuel.
    """
    services = []
    svc_section = config.get("services", {})
    ss_section = config.get("start_stop", {})

    for ss_key, mapping in _SS_TO_SVC.items():
        svc_key = mapping["svc_key"]
        svc_conf = svc_section.get(svc_key, {})
        ss_conf = ss_section.get(ss_key, {})

        # Construire ServiceConfig en fusionnant services + start_stop
        svc = ServiceConfig(
            key=ss_key,  # cle start_stop pour l'admin (ex: "qwen36_35b_q8")
            display_name=ss_conf.get("display_name", svc_conf.get("name", ss_key)),
            backend=mapping["backend"],
            role=mapping.get("role", "auxiliary"),
            exclusive_group=mapping.get("exclusive_group"),
            port=ss_conf.get("port") or _extract_port(svc_conf.get("base_url", "")),
            base_url=svc_conf.get("base_url"),
            health_endpoint=svc_conf.get("health_endpoint", "/health"),
            models_endpoint=svc_conf.get("models_endpoint"),
            timeout_seconds=svc_conf.get("timeout_seconds", 2.0),
            log_source=svc_conf.get("log_type", "file"),
            log_file=svc_conf.get("log_file") or ss_conf.get("log_file"),
            journalctl_unit=svc_conf.get("journalctl_unit"),
            model_detect_pattern=mapping.get("model_detect_pattern"),
            start_command=tuple(ss_conf.get("start_command", [])),
            stop_command=tuple(ss_conf.get("stop_command", [])),
            systemd_unit=ss_conf.get("systemd_unit"),
            vram_min_mib=ss_conf.get("vram_min_mib", 0),
            allow_force_stop=config.get("admin", {}).get("allow_force_stop", False),
        )
        services.append(svc)

    # Ajouter les entrees start_stop non mappees (services arbitraires)
    mapped_keys = set(_SS_TO_SVC.keys())
    for ss_key, ss_conf in ss_section.items():
        if ss_key in mapped_keys:
            continue
        is_llm = ss_conf.get("is_llm", False)
        svc = ServiceConfig(
            key=ss_key,
            display_name=ss_conf.get("display_name", ss_key),
            backend="systemd" if ss_conf.get("systemd_unit") else "unknown",
            role="llm" if is_llm else "auxiliary",
            exclusive_group=None,
            port=ss_conf.get("port"),
            base_url=None,
            health_endpoint="/",
            start_command=tuple(ss_conf.get("start_command", [])),
            stop_command=tuple(ss_conf.get("stop_command", [])),
            systemd_unit=ss_conf.get("systemd_unit"),
            vram_min_mib=ss_conf.get("vram_min_mib", 0),
            allow_force_stop=config.get("admin", {}).get("allow_force_stop", False),
        )
        services.append(svc)

    return services


def _extract_port(base_url):
    """Extrait le port d'une URL (ex: 'http://127.0.0.1:8080' -> 8080)."""
    if not base_url:
        return None
    try:
        return int(base_url.rsplit(":", 1)[-1].rstrip("/"))
    except (ValueError, IndexError):
        return None
