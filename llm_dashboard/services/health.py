"""
Service health checking — verification de l'etat des services.

Les fonctions ici font des appels reseau (HTTP, socket TCP), mais
elles sont isolees dans ce module. Le ServiceRegistry, lui, reste pur.
"""

import logging
import socket
import time

logger = logging.getLogger("dashboard-llm.services.health")

# import conditionnel : requests peut ne pas etre disponible
try:
    import requests as _requests
except Exception:
    _requests = None


def check_service_health(base_url: str, health_endpoint: str,
                         timeout_seconds: float = 2.0) -> tuple[str, float | None]:
    """Verifie la sante d'un service via HTTP GET sur son health endpoint.

    Args:
        base_url: URL de base (ex: "http://127.0.0.1:8080")
        health_endpoint: chemin du health check (ex: "/health")
        timeout_seconds: timeout HTTP en secondes

    Returns:
        tuple (status, latency_seconds):
        - status: "UP" si HTTP < 400, "DOWN" sinon
        - latency_seconds: temps de reponse en secondes, ou None si echec
    """
    if _requests is None:
        return "DOWN", None

    url = base_url.rstrip("/") + "/" + health_endpoint.lstrip("/")
    start = time.time()
    try:
        response = _requests.get(url, timeout=timeout_seconds)
        latency = time.time() - start
        status = "UP" if response.status_code < 400 else "DOWN"
        return status, latency
    except Exception as e:
        logger.debug("check_service_health error for %s: %s", url, e)
        return "DOWN", None


def check_port_is_open(host: str = "127.0.0.1", port: int = 8080,
                       timeout: float = 1.0) -> bool:
    """Verifie si un port TCP est ouvert (connexion acceptee).

    Args:
        host: adresse IP
        port: numero de port
        timeout: timeout socket en secondes

    Returns:
        True si le port accepte les connexions.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_port_free(host: str = "127.0.0.1", port: int = 8080,
                       timeout: int = 10) -> bool:
    """Attend qu'un port TCP soit libere.

    Args:
        host: adresse IP
        port: numero de port
        timeout: temps maximum d'attente en secondes

    Returns:
        True si le port est libre, False si toujours occupe apres timeout.
    """
    for _ in range(timeout):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result != 0:  # connexion refusee = port libre
                return True
        except Exception:
            return True
        time.sleep(1)
    return False


def check_systemd_unit_active(unit: str, timeout: int = 3) -> bool:
    """Verifie si un service systemd est actif via CommandRunner.

    Args:
        unit: nom du service systemd (ex: "launch_llm.service")
        timeout: timeout subprocess en secondes

    Returns:
        True si systemctl is-active retourne "active" ou "activating".
    """
    from llm_dashboard.services.commands import CommandRunner
    runner = CommandRunner()
    try:
        result = runner.systemctl_is_active(unit, timeout=timeout)
        return result.success and result.stdout.strip() in ("active", "activating")
    except ValueError as e:
        logger.debug("check_systemd_unit_active validation error for %s: %s", unit, e)
        return False
