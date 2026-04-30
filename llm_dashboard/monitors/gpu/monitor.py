"""
GPUMonitor — facade unifiee pour les metriques GPU.

Utilise le backend auto-detected par factory.py.
"""
from __future__ import annotations

import logging
from typing import Optional

from llm_dashboard.monitors.gpu.factory import get_gpu_backend
from llm_dashboard.monitors.gpu.processes import normalize_gpu_process_dict

logger = logging.getLogger("dashboard-llm.gpu")


class GPUMonitor:
    """Collecteur de metriques GPU, quel que soit le vendor."""

    def __init__(self, backend=None):
        self.backend = backend or get_gpu_backend()

    def collect(self) -> list[dict]:
        """Retourne la liste des GPUs au format attendu par /api/data."""
        return [d.to_dict() for d in self.backend.get_devices()]

    def vram_status(self) -> dict:
        return self.backend.get_vram_status()

    def gpu_processes(
        self,
        show_command: bool = True,
        max_processes: Optional[int] = None,
    ) -> list[dict]:
        """Retourne les processus GPU normalises, tries par VRAM decroissante.

        Args:
            show_command: si False, masque la commande.
            max_processes: limite optionnelle du nombre de processus.

        Returns:
            list[dict] compatible GPUProcess.to_dict(), triee par used_vram_mib desc.
        """
        try:
            raw = self.backend.get_gpu_processes()
        except Exception as exc:
            logger.warning("gpu_processes: backend error: %s", exc)
            return []

        if not raw:
            return []

        normalized = []
        for p in raw:
            if isinstance(p, dict):
                normalized.append(normalize_gpu_process_dict(p, show_command=show_command))
            elif hasattr(p, 'to_dict'):
                normalized.append(p.to_dict(show_command=show_command))
            else:
                continue

        normalized.sort(key=lambda p: p.get("used_vram_mib", 0), reverse=True)

        if max_processes:
            normalized = normalized[:max_processes]

        return normalized

    @property
    def vendor_name(self) -> str:
        return self.backend.vendor_name

    def shutdown(self):
        self.backend.shutdown()
