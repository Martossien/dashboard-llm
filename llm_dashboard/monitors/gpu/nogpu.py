"""
Fallback GPU backend — quand aucun GPU n'est disponible.
"""

from llm_dashboard.monitors.gpu.base import AbstractGPUBackend, GPUDevice


class NoGPUBackend(AbstractGPUBackend):
    """Backend sans GPU — retourne une liste vide."""

    def get_devices(self) -> list[GPUDevice]:
        return []

    def get_vram_status(self) -> dict:
        return {"enabled": False}

    @property
    def vendor_name(self) -> str:
        return "cpu"


# Alias pour compatibilite
CPUOnlyBackend = NoGPUBackend
