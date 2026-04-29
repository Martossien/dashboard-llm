"""
GPUMonitor — facade unifiee pour les metriques GPU.

Utilise le backend auto-detected par factory.py.
"""

from llm_dashboard.monitors.gpu.factory import get_gpu_backend


class GPUMonitor:
    """Collecteur de metriques GPU, quel que soit le vendor."""

    def __init__(self, backend=None):
        self.backend = backend or get_gpu_backend()

    def collect(self) -> list[dict]:
        """Retourne la liste des GPUs au format attendu par /api/data.

        Format compatible avec l'ancien get_gpu_info() :
        {"id": int, "name": str, "temp": float, "fan": float,
         "power": float, "power_limit": float, "gpu_util": float,
         "memory": {"used": float(GiB), "free": float(GiB), "total": float(GiB)}}
        """
        return [d.to_dict() for d in self.backend.get_devices()]

    def vram_status(self) -> dict:
        return self.backend.get_vram_status()

    def gpu_processes(self) -> list[dict]:
        return self.backend.get_gpu_processes()

    @property
    def vendor_name(self) -> str:
        return self.backend.vendor_name

    def shutdown(self):
        self.backend.shutdown()