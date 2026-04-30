"""
CommandRunner — Execution centralisee et securisee des commandes systeme.

Toute commande systemd, fuser, nvidia-smi ou journalctl doit passer par
ce module. Les arguments sont valides strictement avant execution.

Pas de subprocess.run() direct hors de ce module dans le reste du projet.

Utilisation:
    runner = CommandRunner()
    result = runner.systemctl_is_active("launch_llm.service")
    if result.success and result.stdout == "active":
        ...
"""

from __future__ import annotations

import logging
import os
import re
import signal as _signal
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger("dashboard-llm.commands")

# Regex de validation
_RE_SYSTEMD_UNIT = re.compile(r'^[A-Za-z0-9_.@:-]+\.service$')
_SIGNALS = ("TERM", "KILL")


@dataclass(frozen=True)
class CommandResult:
    """Resultat d'une commande executee par CommandRunner.

    Frozen=True : le resultat est immuable, pas de modification post-execution.
    """

    command: str = ""            # description lisible (ex: "systemctl is-active foo.service")
    stdout: str = ""
    stderr: str = ""
    returncode: int = -1
    timed_out: bool = False

    @property
    def success(self) -> bool:
        """La commande a reussi (returncode == 0, pas de timeout)."""
        return self.returncode == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """stdout nettoye (strip)."""
        return self.stdout.strip()


class CommandRunner:
    """Executeur centralise de commandes systeme avec validation stricte.

    Regles de securite :
    - Les unites systemd sont validees par regex.
    - Les ports sont bornes 1-65535.
    - Les signaux sont limites a TERM/KILL.
    - Les nombres de lignes sont bornes.
    - Toute execution est loggee.
    """

    # ---- Commandes systemd ----

    def systemctl_is_active(self, unit: str, timeout: int = 3) -> CommandResult:
        """Verifie si un service systemd est actif.

        Returns:
            CommandResult dont .stdout est 'active', 'inactive', etc.
        """
        self._validate_unit(unit)
        return self._run(
            ["systemctl", "is-active", unit],
            timeout=timeout,
            description=f"systemctl is-active {unit}",
        )

    def systemctl_start(self, unit: str, timeout: int = 60) -> CommandResult:
        """Demarre un service systemd."""
        self._validate_unit(unit)
        return self._run(
            ["systemctl", "start", unit],
            timeout=timeout,
            description=f"systemctl start {unit}",
        )

    def systemctl_stop(self, unit: str, timeout: int = 15) -> CommandResult:
        """Arrete un service systemd."""
        self._validate_unit(unit)
        return self._run(
            ["systemctl", "stop", unit],
            timeout=timeout,
            description=f"systemctl stop {unit}",
        )

    def systemctl_kill(self, unit: str, timeout: int = 10) -> CommandResult:
        """Envoie un kill force a un service systemd."""
        self._validate_unit(unit)
        return self._run(
            ["systemctl", "kill", unit],
            timeout=timeout,
            description=f"systemctl kill {unit}",
        )

    # ---- Commandes port/reseau ----

    def fuser_kill_port(self, port: int, signal: str = "TERM", timeout: int = 10) -> CommandResult:
        """Envoie un signal aux processus sur un port TCP via fuser -k.

        Args:
            port: numero de port (1-65535)
            signal: 'TERM' ou 'KILL'
            timeout: timeout en secondes
        """
        self._validate_port(port)
        self._validate_signal(signal)
        return self._run(
            ["fuser", "-k", f"-SIG{signal}", f"{port}/tcp"],
            timeout=timeout,
            description=f"fuser -k -SIG{signal} {port}/tcp",
        )

    # ---- Commandes de lecture ----

    def journalctl_unit(self, unit: str, lines: int = 50, timeout: int = 5) -> CommandResult:
        """Lit les logs d'un service systemd via journalctl.

        Args:
            unit: nom du service systemd
            lines: nombre de lignes (1-2000)
            timeout: timeout en secondes
        """
        self._validate_unit(unit)
        self._validate_lines(lines)
        return self._run(
            ["journalctl", "-u", unit, "-n", str(lines), "--no-pager", "-o", "cat"],
            timeout=timeout,
            description=f"journalctl -u {unit} -n {lines}",
        )

    # ---- Commandes GPU ----

    def nvidia_smi_query_gpu(self, timeout: int = 10) -> CommandResult:
        """Interroge nvidia-smi pour les infos GPU."""
        return self._run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=timeout,
            description="nvidia-smi --query-gpu",
        )

    def nvidia_smi_query_gpu_full(self, timeout: int = 10) -> CommandResult:
        """Interroge nvidia-smi pour toutes les metriques GPU (fallback sans pynvml)."""
        return self._run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.used,memory.free,memory.total,"
             "temperature.gpu,fan.speed,utilization.gpu,power.draw,power.limit",
             "--format=csv,noheader,nounits"],
            timeout=timeout,
            description="nvidia-smi --query-gpu (full)",
        )

    def nvidia_smi_query_compute_apps(self, timeout: int = 10) -> CommandResult:
        """Interroge nvidia-smi pour les processus GPU."""
        return self._run(
            ["nvidia-smi", "--query-compute-apps=pid,process_name,used_gpu_memory",
             "--format=csv,noheader,nounits"],
            timeout=timeout,
            description="nvidia-smi --query-compute-apps",
        )

    def nvidia_smi_power_limit(self, gpu_index: int, watts: int, timeout: int = 10) -> CommandResult:
        """Definit la limite de puissance d'un GPU."""
        if gpu_index < 0:
            raise ValueError(f"Invalid GPU index: {gpu_index}")
        if watts <= 0:
            raise ValueError(f"Invalid power limit: {watts}W")
        return self._run(
            ["nvidia-smi", "-i", str(gpu_index), "-pl", str(watts)],
            timeout=timeout,
            description=f"nvidia-smi -i {gpu_index} -pl {watts}",
        )

    # ---- Validation ----

    def _validate_unit(self, unit: str) -> None:
        """Valide le format d'un nom d'unite systemd."""
        if not unit:
            raise ValueError("systemd unit name must not be empty")
        if not _RE_SYSTEMD_UNIT.match(unit):
            raise ValueError(
                f"Invalid systemd unit name: '{unit}'. "
                f"Must match pattern: {_RE_SYSTEMD_UNIT.pattern}"
            )

    def _validate_port(self, port: int) -> None:
        """Valide un numero de port TCP."""
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValueError(f"Invalid port: {port}. Must be between 1 and 65535.")

    def _validate_signal(self, signal: str) -> None:
        """Valide un nom de signal (TERM ou KILL uniquement)."""
        if signal not in _SIGNALS:
            raise ValueError(f"Invalid signal: '{signal}'. Must be one of: {_SIGNALS}")

    def _validate_lines(self, lines: int) -> None:
        """Valide un nombre de lignes."""
        if not isinstance(lines, int) or not (1 <= lines <= 2000):
            raise ValueError(f"Invalid lines count: {lines}. Must be between 1 and 2000.")

    def _validate_pid(self, pid: int) -> None:
        """Valide un PID de processus."""
        if not isinstance(pid, int) or pid < 1:
            raise ValueError(f"Invalid PID: {pid}. Must be a positive integer.")

    def kill_pid(self, pid: int, signal: str = "TERM") -> None:
        """Envoie un signal a un processus par PID.

        Args:
            pid: identifiant du processus cible
            signal: 'TERM' ou 'KILL'

        Raises:
            ValueError: si le PID ou le signal est invalide
            ProcessLookupError: si le processus n'existe pas
            PermissionError: si les droits sont insuffisants
        """
        self._validate_pid(pid)
        self._validate_signal(signal)
        sig = getattr(_signal, f"SIG{signal}")
        logger.info("kill_pid: sending SIG%s to PID %d", signal, pid)
        os.kill(pid, sig)
        logger.info("kill_pid: SIG%s sent to PID %d", signal, pid)

    # ---- Execution ----

    def _run(self, cmd: list[str], timeout: int, description: str) -> CommandResult:
        """Execute une commande et retourne un CommandResult.

        Toute execution est loggee (commande + resultat).
        """
        logger.debug("Running: %s (timeout=%ds)", description, timeout)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            logger.debug(
                "Command result: %s -> rc=%d, stdout=%d bytes, stderr=%d bytes",
                description, result.returncode,
                len(result.stdout), len(result.stderr),
            )
            return CommandResult(
                command=description,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Command timed out: %s (timeout=%ds)", description, timeout)
            return CommandResult(
                command=description,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                returncode=-1,
                timed_out=True,
            )
        except Exception as e:
            logger.error("Command failed: %s: %s", description, e)
            return CommandResult(
                command=description,
                stdout="",
                stderr=str(e),
                returncode=-1,
            )
