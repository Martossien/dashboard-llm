"""
System monitors — CPU et RAM via psutil.

Extrait de monitor.py (Lot 8).
"""

import psutil


def get_cpu_info() -> dict[str, float]:
    """Charge CPU en pourcentage."""
    return {"load": psutil.cpu_percent(interval=None)}


def get_ram_info() -> dict[str, float]:
    """Memoire RAM : used, total, percent."""
    mem = psutil.virtual_memory()
    return {
        "used": mem.used / (1024**3),
        "total": mem.total / (1024**3),
        "percent": mem.percent,
    }
