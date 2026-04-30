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
    service_guess: Optional[str] = None
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


def guess_gpu_process_service(process_name: Optional[str], command: Optional[str]) -> Optional[str]:
    """Devine le service auquel appartient un processus GPU.

    Heuristiques basees sur le nom du processus et sa ligne de commande.

    Returns:
        "vllm", "ollama", "llama_cpp", "ik_llama_cpp", "python", "unknown", ou None.
    """
    name_lower = (process_name or "").lower()
    cmd_lower = (command or "").lower()
    combined = f"{name_lower} {cmd_lower}"

    # ik_llama avant llama (pour eviter faux match)
    if "ik_llama" in combined:
        return "ik_llama_cpp"

    if "llama-server" in combined or "llama.cpp" in combined:
        return "llama_cpp"

    if "vllm" in combined or "api_server" in cmd_lower or "vllm.entrypoints" in cmd_lower:
        return "vllm"

    if "ollama" in combined:
        return "ollama"

    if "python" in name_lower:
        return "python"

    if process_name and process_name != "unknown":
        return "unknown"

    return None


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
        "pid": int(pid),
        "gpu_index": gpu_index,
        "process_name": process_name,
        "used_vram_mib": float(used_vram),
        "username": username,
        "command": command if show_command else None,
        "service_guess": service_guess,
        "backend": backend,
        "gpu_uuid": gpu_uuid,
    }
