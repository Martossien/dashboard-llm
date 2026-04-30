"""
Abstract GPU backend — interface pour tous les vendors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GPUDevice:
    """Representation unifiee d'un GPU, quel que soit le vendor."""
    index: int
    name: str
    vendor: str                         # "nvidia" | "amd" | "cpu"
    memory_total_mib: float
    memory_used_mib: float
    memory_free_mib: float
    temperature_c: Optional[float] = None
    fan_speed_pct: Optional[float] = None
    utilization_gpu_pct: Optional[float] = None
    utilization_memory_pct: Optional[float] = None
    power_draw_w: Optional[float] = None
    power_limit_w: Optional[float] = None
    vram_temp_c: Optional[float] = None
    sm_clock_mhz: Optional[int] = None
    mem_clock_mhz: Optional[int] = None
    is_throttled: Optional[bool] = None
    encoder_util_pct: Optional[int] = None
    decoder_util_pct: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "id": self.index,
            "name": self.name,
            "temp": self.temperature_c or 0,
            "vram_temp": self.vram_temp_c,
            "fan": self.fan_speed_pct or 0,
            "power": self.power_draw_w or 0,
            "power_limit": self.power_limit_w or 0,
            "gpu_util": self.utilization_gpu_pct or 0,
            "sm_clock": self.sm_clock_mhz,
            "mem_clock": self.mem_clock_mhz,
            "throttled": self.is_throttled,
            "encoder_util": self.encoder_util_pct,
            "decoder_util": self.decoder_util_pct,
            "memory": {
                "used": self.memory_used_mib / 1024,
                "free": self.memory_free_mib / 1024,
                "total": self.memory_total_mib / 1024,
            },
        }


class AbstractGPUBackend(ABC):
    """Interface unifiee pour tous les backends GPU."""

    @abstractmethod
    def get_devices(self) -> list[GPUDevice]:
        """Retourne la liste des GPUs detectes."""
        ...

    def get_vram_status(self) -> dict:
        """Retourne le statut VRAM au format attendu par l'admin panel."""
        gpus = []
        for device in self.get_devices():
            total = device.memory_total_mib
            used = device.memory_used_mib
            free = device.memory_free_mib
            gpus.append({
                "index": str(device.index),
                "name": device.name,
                "used_mb": used,
                "free_mb": free,
                "total_mb": total,
                "usage_percent": (used / total * 100) if total > 0 else 0,
            })
        return {"enabled": True, "gpus": gpus}

    def get_gpu_processes(self) -> list:
        """Retourne les processus GPU consommateurs de VRAM.

        Returns:
            list[GPUProcess] ou list[dict] (normalise par GPUMonitor).
        """
        return []

    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Nom du vendor."""
        ...

    def shutdown(self) -> None:
        """Nettoie les ressources."""
        pass
