"""
Service controller — start/stop/restart/force-stop des services.

Encapsule la logique de controle admin. Utilise CommandRunner pour
toutes les commandes systeme. Respecte admin.allow_force_stop.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("dashboard-llm.control")


@dataclass(frozen=True)
class ControlResult:
    """Resultat d'une operation de controle (start/stop/restart/force_stop)."""

    key: str              # cle du service
    success: bool
    message: str
    stdout: str = ""
    stderr: str = ""
    killed_pids: tuple[int, ...] = ()


class ServiceController:
    """Controle du cycle de vie des services (start/stop/restart/force_stop).

    Utilise ServiceRegistry pour les configs et CommandRunner pour l'execution.
    Les operations destructives (force_stop, kill GPU) sont gardees par
    admin.allow_force_stop.
    """

    def __init__(self, registry, runner, vram_checker=None, port_checker=None,
                 gpu_process_lister=None, active_key_getter=None,
                 allow_force_stop: bool = False):
        """Initialise le controller.

        Args:
            registry: ServiceRegistry
            runner: CommandRunner
            vram_checker: callable() -> dict (ex: get_vram_status)
            port_checker: callable(port, timeout) -> bool (ex: wait_for_port_free)
            gpu_process_lister: callable() -> list[dict] (ex: get_gpu_processes)
            active_key_getter: callable(group) -> key actif, si connu
            allow_force_stop: si True, autorise fuser/kill GPU
        """
        self.registry = registry
        self.runner = runner
        self._vram_checker = vram_checker
        self._port_checker = port_checker
        self._gpu_process_lister = gpu_process_lister
        self._active_key_getter = active_key_getter
        self.allow_force_stop = allow_force_stop

    # ---- API publique ----

    def start_service(self, key: str) -> ControlResult:
        """Demarre un service. Si groupe exclusif, arrete d'abord le concurrent."""
        svc = self.registry.get(key)
        if svc is None:
            return ControlResult(key, False, f"Service inconnu: {key}")
        if not svc.start_command:
            return ControlResult(key, False, f"Pas de start_command pour: {key}")

        # Verifier VRAM
        if svc.vram_min_mib > 0 and self._vram_checker:
            vram = self._vram_checker()
            if vram.get("enabled") and not vram.get("error"):
                for gpu in vram.get("gpus", []):
                    if gpu["free_mb"] < svc.vram_min_mib:
                        return ControlResult(key, False,
                            f"GPU {gpu['index']} ({gpu['name']}) "
                            f"a seulement {gpu['free_mb']:.0f} MiB libres "
                            f"(min: {svc.vram_min_mib:.0f} MiB)")

        # Arreter le concurrent si groupe exclusif
        if svc.exclusive_group and self._active_key_getter:
            running_key = self._active_key_getter(svc.exclusive_group)
            if running_key and running_key != key:
                self.stop_service(running_key)
                time.sleep(3)

        result = self.runner.systemctl_start(svc.systemd_unit or "", timeout=60)
        if result.success:
            return ControlResult(key, True, f"Service {key} demarre.")
        return ControlResult(key, False,
            f"Echec du demarrage (rc={result.returncode}): {result.stderr}",
            stderr=result.stderr)

    def stop_service(self, key: str) -> ControlResult:
        """Arrete un service proprement (systemctl stop + fallback fuser)."""
        svc = self.registry.get(key)
        if svc is None:
            return ControlResult(key, False, f"Service inconnu: {key}")
        if not svc.stop_command:
            return ControlResult(key, False, f"Pas de stop_command pour: {key}")

        port = svc.port or 0

        # Etape 1: systemctl stop
        result = self.runner.systemctl_stop(svc.systemd_unit or "", timeout=15)
        if not result.success:
            if "inactive" in result.stderr.lower() or "not loaded" in result.stderr.lower():
                logger.info("stop_service(%s): already inactive.", key)
            else:
                logger.warning("stop_service(%s): systemctl stop failed (rc=%d): %s",
                             key, result.returncode, result.stderr[:200])
                if not self.allow_force_stop:
                    return ControlResult(key, False,
                        f"Echec de l'arret (rc={result.returncode}): {result.stderr}",
                        stderr=result.stderr)
            if svc.systemd_unit and self.allow_force_stop:
                self.runner.systemctl_kill(svc.systemd_unit, timeout=10)

        # Etape 2: verifier le port
        if port and self._port_checker:
            if not self._port_checker(port, timeout=8):
                if not self.allow_force_stop:
                    return ControlResult(key, False,
                        f"Port {port} encore occupe apres stop; force stop desactive.")
                logger.warning("stop_service(%s): port %d still occupied, force kill...", key, port)
                self.runner.fuser_kill_port(port, signal="TERM", timeout=10)
                time.sleep(3)
                if not self._port_checker(port, timeout=5):
                    self.runner.fuser_kill_port(port, signal="KILL", timeout=10)
                    time.sleep(2)

        # Etape 3: tuer les processus GPU residuels (LLM uniquement)
        if svc.exclusive_group and self.allow_force_stop:
            killed = self._kill_gpu_processes(threshold_mib=500, sigkill_after=5)
            if killed:
                logger.info("stop_service(%s): %d GPU processes killed.", key, len(killed))
                time.sleep(2)

        # Etape 4: verification finale
        if port and self._port_checker:
            if not self._port_checker(port, timeout=5):
                return ControlResult(key, False,
                    f"Port {port} encore occupe apres stop et force kill.")

        return ControlResult(key, True, f"Service {key} arrete.")

    def restart_service(self, key: str) -> ControlResult:
        """Redemarre un service (stop + 2s + start)."""
        self.stop_service(key)
        time.sleep(2)
        return self.start_service(key)

    def force_stop_service(self, key: str) -> ControlResult:
        """Force kill d'un service (stop normal + kill GPU residuels + fuser -KILL)."""
        if not self.allow_force_stop:
            return ControlResult(key, False,
                "Force stop refuse: admin.allow_force_stop est desactive.")

        svc = self.registry.get(key)
        if svc is None:
            return ControlResult(key, False, f"Service inconnu: {key}")

        normal_result = self.stop_service(key)

        # Kill GPU processes agressif (seuil bas)
        if self._gpu_process_lister:
            killed_pids = self._kill_gpu_processes(threshold_mib=100, sigkill_after=5)
        else:
            killed_pids = []

        # Force kill sur le port
        if svc.port:
            self.runner.fuser_kill_port(svc.port, signal="KILL", timeout=15)
            time.sleep(2)
            if self._port_checker and not self._port_checker(svc.port, timeout=5):
                return ControlResult(key, False,
                    f"Port {svc.port} encore occupe apres force kill!",
                    killed_pids=tuple(killed_pids))

        return ControlResult(key, True,
            f"Force kill {key} effectue. {len(killed_pids)} PIDs GPU tus.",
            killed_pids=tuple(killed_pids),
            stdout=normal_result.message)

    def stop_group(self, group: str) -> list[ControlResult]:
        """Arrete tous les services d'un groupe exclusif."""
        results = []
        for svc in self.registry.by_group(group):
            if svc.stop_command:
                result = self.runner.systemctl_stop(svc.systemd_unit or "", timeout=60)
                if result.success:
                    results.append(ControlResult(svc.key, True, "stopped"))
                else:
                    results.append(ControlResult(svc.key, False,
                        result.stderr, stderr=result.stderr))

        # Nettoyage du port du groupe
        group_svc = next(iter(self.registry.by_group(group)), None)
        if group_svc and group_svc.port:
            time.sleep(3)
            if self._port_checker and not self._port_checker(group_svc.port, timeout=5):
                if self.allow_force_stop:
                    self.runner.fuser_kill_port(group_svc.port, signal="TERM", timeout=10)
                    time.sleep(3)
                else:
                    logger.warning(
                        "stop_group(%s): port %d still occupied; force stop disabled.",
                        group, group_svc.port,
                    )

        # GPU cleanup
        if self.allow_force_stop:
            self._kill_gpu_processes(threshold_mib=500, sigkill_after=5)
            time.sleep(2)

        return results

    # ---- PID management ----

    def terminate_pid(self, pid: int, signal_name: str = "TERM") -> bool:
        """Envoie un signal a un processus.

        Args:
            pid: PID du processus (> 1)
            signal_name: 'TERM' (signal 15) ou 'KILL' (signal 9)

        Returns:
            True si le signal a ete envoye, False si le processus n'existe pas.
        """
        if pid <= 1:
            logger.warning("Refusing to signal PID %d (system process)", pid)
            return False
        if signal_name not in ("TERM", "KILL"):
            raise ValueError(f"Invalid signal: {signal_name}")

        try:
            self.runner.kill_pid(pid, signal_name)
            logger.info("Sent SIG%s to PID %d", signal_name, pid)
            return True
        except ProcessLookupError:
            logger.info("PID %d already dead", pid)
            return False
        except PermissionError:
            logger.warning("Permission denied for PID %d", pid)
            return False

    # ---- Interne ----

    def _kill_gpu_processes(self, threshold_mib: int = 500,
                            sigkill_after: int = 5) -> list[int]:
        """Tue les processus GPU au-dessus du seuil de VRAM.

        Args:
            threshold_mib: seuil minimum de VRAM en MiB pour cibler un processus
            sigkill_after: delai en secondes avant SIGKILL apres SIGTERM

        Returns:
            Liste des PIDs tues.
        """
        if not self._gpu_process_lister:
            return []

        processes = self._gpu_process_lister()
        if not processes:
            logger.info("_kill_gpu_processes: no GPU processes found.")
            return []

        big_procs = [p for p in processes if p.get("vram_mib", 0) >= threshold_mib]
        if not big_procs:
            logger.info("_kill_gpu_processes: no GPU process above %d MiB.", threshold_mib)
            return []

        pids_killed = []
        logger.info("_kill_gpu_processes: %d GPU processes above %d MiB",
                   len(big_procs), threshold_mib)

        # SIGTERM
        for p in big_procs:
            if self.terminate_pid(p["pid"], "TERM"):
                pids_killed.append(p["pid"])

        time.sleep(sigkill_after)

        # Survivants → SIGKILL
        survivors = self._gpu_process_lister()
        survivor_pids = {p["pid"] for p in survivors
                        if p.get("vram_mib", 0) >= threshold_mib}
        if survivor_pids:
            logger.warning("_kill_gpu_processes: %d processes survived SIGTERM",
                         len(survivor_pids))
            for pid in survivor_pids:
                self.terminate_pid(pid, "KILL")
            time.sleep(2)

        logger.info("_kill_gpu_processes: done. %d PIDs killed.", len(pids_killed))
        return pids_killed


def create_service_controller_from_config(
    config: dict,
    runner,
    gpu_monitor=None,
    port_checker=None,
):
    """Cree un ServiceController a partir d'une config et d'un runner.

    Args:
        config: dictionnaire de configuration complet (avec start_stop, services, admin).
        runner: instance CommandRunner.
        gpu_monitor: instance GPUMonitor (optionnel, pour VRAM check et GPU processes).
        port_checker: callable(port, timeout) -> bool (optionnel).

    Returns:
        ServiceController configure.
    """
    from llm_dashboard.models import normalize_services_config
    from llm_dashboard.services.registry import ServiceRegistry

    services = normalize_services_config(config)
    registry = ServiceRegistry(services)
    allow_force_stop = config.get("admin", {}).get("allow_force_stop", False)

    def _vram_checker():
        if not gpu_monitor:
            return {"enabled": False}
        try:
            return gpu_monitor.vram_status()
        except Exception:
            return {"enabled": False}

    def _gpu_process_lister():
        if not gpu_monitor:
            return []
        try:
            return gpu_monitor.gpu_processes()
        except Exception:
            return []

    return ServiceController(
        registry=registry,
        runner=runner,
        vram_checker=_vram_checker,
        port_checker=port_checker,
        gpu_process_lister=_gpu_process_lister,
        active_key_getter=None,
        allow_force_stop=allow_force_stop,
    )

