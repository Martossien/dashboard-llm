"""
GPU Process model — representation normalisee d'un processus GPU.

Inspire de nvitop et gpustat. Format stable pour API REST et Prometheus.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class GPUProcess:
    """Representation unifiee d'un processus utilisant un GPU.

    Frozen=True : immuable une fois cree.
    """

    pid: int
    used_vram_mib: float
    process_name: str = "unknown"
    gpu_index: Optional[int] = None
    username: Optional[str] = None
    command: Optional[str] = None
    service_guess: str = "unknown"
    backend: str = "unknown"
    gpu_uuid: Optional[str] = None

    def to_dict(self, show_command: bool = True) -> dict:
        """Convertit en dictionnaire pret pour JSON.

        Args:
            show_command: si False, command est None.
        """
        return {
            "pid": self.pid,
            "gpu_index": self.gpu_index,
            "process_name": self.process_name,
            "used_vram_mib": self.used_vram_mib,
            "username": self.username,
            "command": self.command if show_command else None,
            "service_guess": self.service_guess,
            "backend": self.backend,
            "gpu_uuid": self.gpu_uuid,
        }


def guess_gpu_process_service(process_name: Optional[str], command: Optional[str],
                              service_patterns: Optional[dict] = None) -> str:
    """Devine le service auquel appartient un processus GPU.

    Heuristiques basees sur le nom du processus et sa ligne de commande.
    Peut recevoir un dict {service_key: [patterns]} depuis la config
    pour etre entierement dynamique.

    Returns:
        Cle de service devinee ou "unknown".
    """
    name_lower = (process_name or "").lower()
    cmd_lower = (command or "").lower()
    combined = f"{name_lower} {cmd_lower}"

    if service_patterns:
        for svc_key, patterns in service_patterns.items():
            if patterns:
                if any(p in combined for p in patterns):
                    return svc_key

    # Default heuristics (universal)
    if "ik_llama" in combined:
        return "ik_llama_cpp"
    if "vllm" in combined or "VLLM::" in combined or "vllm.entrypoints" in cmd_lower:
        return "vllm"
    if "ollama" in combined:
        return "ollama"
    if "sglang" in combined:
        return "sglang"
    if "llama-server" in combined or "llama.cpp" in combined:
        return "llama_cpp"
    if "python" in name_lower:
        return "python"

    return "unknown"


def process_vram_mib(proc: dict) -> float:
    """Extrait la VRAM d'un dict processus (nouveau ou ancien schema)."""
    try:
        return float(proc.get("used_vram_mib", proc.get("vram_mib", 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def normalize_gpu_process_dict(raw: dict, show_command: bool = True) -> dict:
    """Normalise un dict de processus GPU (ancien format) vers le nouveau schema.

    Args:
        raw: dict avec au moins "pid" et "vram_mib" ou "used_vram_mib".
        show_command: si False, command est None.

    Returns:
        dict compatible avec GPUProcess.to_dict().
    """
    pid = raw.get("pid", 0)
    process_name = raw.get("process_name") or raw.get("name", "unknown")
    used_vram = raw.get("used_vram_mib") or raw.get("vram_mib", 0.0)
    command = raw.get("command")
    gpu_index = raw.get("gpu_index")
    username = raw.get("username")
    backend = raw.get("backend", "unknown")
    gpu_uuid = raw.get("gpu_uuid")

    service_guess = raw.get("service_guess")
    if not service_guess:
        service_guess = guess_gpu_process_service(process_name, command)

    return {
        "pid": _safe_int(pid),
        "gpu_index": gpu_index if isinstance(gpu_index, int) else None,
        "process_name": process_name,
        "used_vram_mib": _safe_float(used_vram),
        "username": username,
        "command": command if show_command else None,
        "service_guess": service_guess or "unknown",
        "backend": backend,
        "gpu_uuid": gpu_uuid,
    }


def _safe_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
