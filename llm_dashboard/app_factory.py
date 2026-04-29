"""
Application factory complete — cree l'app Flask avec toutes ses dependances.
Utilise par cli.py pour eviter le sys.path hack.
"""

import importlib.util
import os
import sys


def create_full_app():
    """Cree et retourne (app, config) prets a etre lances.

    Utilise importlib pour charger monitor.py explicitement,
    sans modifier sys.path.
    """
    # Charger monitor.py via importlib (chemin explicite, pas de sys.path hack)
    monitor_path = os.path.join(
        os.path.dirname(__file__), "..", "monitor.py"
    )
    monitor_path = os.path.abspath(monitor_path)

    if "monitor" not in sys.modules:
        spec = importlib.util.spec_from_file_location("monitor", monitor_path)
        monitor = importlib.util.module_from_spec(spec)
        sys.modules["monitor"] = monitor
        spec.loader.exec_module(monitor)
    else:
        import monitor

    return monitor.app, monitor.CONFIG
