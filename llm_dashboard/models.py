"""
Modeles de donnees partages.

ServiceConfig représente un service LLM ou auxiliaire de facon unifiee.
La config unifiee (config.yaml) porte tous les attributs par service.
Aucun mapping hardcode — les services sont lus dynamiquement depuis la config.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ServiceConfig:
    key: str
    display_name: str
    backend: str = ""                              # "llama.cpp" | "ik_llama.cpp" | "vllm" | "ollama" | "sglang" | "openai" | "gradio" | "auto"
    role: str = "auxiliary"                       # "llm" | "auxiliary" | "dashboard"
    exclusive_group: Optional[str] = None          # services partageant le meme groupe sont mutuellement exclusifs
    port: Optional[int] = None
    base_url: Optional[str] = None
    health_endpoint: str = "/health"
    models_endpoint: Optional[str] = None
    timeout_seconds: float = 2.0
    log_source: str = "file"                      # "file" | "journalctl" | "none"
    log_file: Optional[str] = None
    journalctl_unit: Optional[str] = None
    model_detect_pattern: Optional[str] = None     # regex sur model_id retourne par /v1/models
    process_patterns: tuple[str, ...] = ()
    process_exclude_patterns: tuple[str, ...] = ()
    start_command: tuple[str, ...] = ()
    stop_command: tuple[str, ...] = ()
    systemd_unit: Optional[str] = None
    vram_min_mib: int = 0
    allow_force_stop: bool = False
    pid_file: Optional[str] = None


def normalize_services_config(config):
    """Construit une liste de ServiceConfig depuis la config unifiee.

    Chaque entree de config["services"] produit un ServiceConfig.
    Le port est extrait automatiquement du base_url si non specifie.
    """
    services = []
    svc_section = config.get("services", {})
    admin_section = config.get("admin", {})

    for svc_key, svc_conf in svc_section.items():
        if not isinstance(svc_conf, dict):
            continue

        base_url = svc_conf.get("base_url", "")
        port = svc_conf.get("port") or _extract_port(base_url)

        process_patterns = svc_conf.get("process_patterns", [])
        if isinstance(process_patterns, str):
            process_patterns = [process_patterns]
        process_exclude = svc_conf.get("process_exclude_patterns", [])
        if isinstance(process_exclude, str):
            process_exclude = [process_exclude]
        start_cmd = svc_conf.get("start_command", [])
        stop_cmd = svc_conf.get("stop_command", [])

        svc = ServiceConfig(
            key=svc_key,
            display_name=svc_conf.get("name", svc_key),
            backend=svc_conf.get("backend", "auto"),
            role=svc_conf.get("role", "auxiliary"),
            exclusive_group=svc_conf.get("exclusive_group"),
            port=port,
            base_url=base_url or None,
            health_endpoint=svc_conf.get("health_endpoint", "/health"),
            models_endpoint=svc_conf.get("models_endpoint"),
            timeout_seconds=svc_conf.get("timeout_seconds", 2.0),
            log_source=svc_conf.get("log_type", "file"),
            log_file=svc_conf.get("log_file") or None,
            journalctl_unit=svc_conf.get("journalctl_unit"),
            model_detect_pattern=svc_conf.get("model_detect_pattern"),
            process_patterns=tuple(process_patterns),
            process_exclude_patterns=tuple(process_exclude),
            start_command=tuple(start_cmd),
            stop_command=tuple(stop_cmd),
            systemd_unit=svc_conf.get("systemd_unit"),
            vram_min_mib=svc_conf.get("vram_min_mib", 0),
            allow_force_stop=admin_section.get("allow_force_stop", False),
            pid_file=svc_conf.get("pid_file"),
        )
        services.append(svc)

    return services


def _extract_port(base_url):
    if not base_url:
        return None
    try:
        return int(base_url.rsplit(":", 1)[-1].rstrip("/"))
    except (ValueError, IndexError):
        return None