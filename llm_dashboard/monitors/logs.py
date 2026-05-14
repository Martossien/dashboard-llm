"""
Log monitors — lecture de logs (tail, journalctl, filtrage).

Extrait de monitor.py (Lot 5).
"""

import logging
import os
import re
from collections import deque

from llm_dashboard.services.health import check_port_is_open

logger = logging.getLogger("dashboard-llm.monitors.logs")

# Patterns de bruit llama.cpp — lignes repetitives a filtrer
LLAMA_NOISE_PATTERNS = [
    re.compile(r'^\s*srv\s+stop:\s+all tasks already finished'),
    re.compile(r'^\s*srv\s+update_slots:\s+all slots are idle\s*$'),
    re.compile(r'^\s*que\s+start_loop:\s+waiting for new tasks\s*$'),
    re.compile(r'^\s*que\s+start_loop:\s+update slots\s*$'),
    re.compile(r'^\s*srv\s+update_slots:\s+run slots completed\s*$'),
    re.compile(r'^\s*que\s+start_loop:\s+processing new tasks\s*$'),
    re.compile(r'^\s*res\s+remove_waiti:\s+remove task\s'),
]

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07')


def tail_log_lines(log_file: str, max_lines: int, block_size: int) -> list[str]:
    """Lit les dernieres lignes d'un fichier de log, avec filtrage ANSI et bruit.

    Args:
        log_file: chemin du fichier de log
        max_lines: nombre maximum de lignes a retourner
        block_size: taille des blocs de lecture en bytes

    Returns:
        list[str]: lignes de log nettoyees, les plus recentes en dernier
    """
    raw_max = max_lines * 200
    with open(log_file, 'rb') as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        data = b''
        remaining = file_size
        while remaining > 0 and data.count(b'\n') <= raw_max:
            read_size = block_size if remaining >= block_size else remaining
            remaining -= read_size
            f.seek(remaining)
            data = f.read(read_size) + data
        raw_lines = data.splitlines()[-raw_max:]

    lines = deque(maxlen=max_lines)
    for raw_line in reversed(raw_lines):
        line = raw_line.decode('utf-8', errors='ignore').strip()
        if not line:
            continue
        clean_line = ANSI_ESCAPE.sub('', line)
        if any(pat.search(clean_line) for pat in LLAMA_NOISE_PATTERNS):
            continue
        lines.appendleft(clean_line)
        if len(lines) >= max_lines:
            break
    return list(lines)


def read_journalctl_logs(unit: str, max_lines: int) -> list[str]:
    """Lit les logs d'un service systemd via journalctl (CommandRunner).

    Args:
        unit: nom du service systemd (ex: "ollama")
        max_lines: nombre maximum de lignes

    Returns:
        list[str]: lignes de log, ou liste vide si erreur
    """
    from llm_dashboard.services.commands import CommandRunner
    runner = CommandRunner()
    try:
        result = runner.journalctl_unit(unit, lines=max_lines, timeout=5)
        if result.success and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            return lines[-max_lines:]
        return []
    except ValueError as e:
        logger.debug("Failed to read journalctl logs for %s: %s", unit, e)
        return []


def _get_active_llama_log_file(config: dict, command_runner) -> str:
    svc_services = config.get("services", {})

    def _get_log(svc_key):
        return svc_services.get(svc_key, {}).get("log_file", "")

    for svc_key, svc_conf in svc_services.items():
        if not isinstance(svc_conf, dict):
            continue
        port = _extract_port(svc_conf.get("base_url", ""))
        if port and check_port_is_open("127.0.0.1", port, timeout=1):
            process_patterns = svc_conf.get("process_patterns", [])
            if process_patterns:
                import psutil
                for proc in psutil.process_iter(['cmdline']):
                    cmd = ' '.join(proc.info.get('cmdline') or [])
                    if any(p in cmd for p in process_patterns):
                        log = svc_conf.get("log_file", "")
                        if log and os.path.exists(log):
                            return log
            log = svc_conf.get("log_file", "")
            if log and os.path.exists(log):
                return log

    for svc_key in svc_services:
        log = _get_log(svc_key)
        if log and os.path.exists(log):
            return log
    return ""


def _extract_port(base_url):
    if not base_url:
        return None
    try:
        return int(base_url.rsplit(":", 1)[-1].rstrip("/"))
    except (ValueError, IndexError):
        return None


def get_logs(config: dict, command_runner) -> dict:
    max_lines = config["monitoring"]["log_lines"]
    log_block_bytes = config["monitoring"]["log_block_bytes"]
    service_logs = {}
    for svc_key, svc_conf in config["services"].items():
        log_type = svc_conf.get("log_type", "file")
        if log_type == "journalctl":
            unit = svc_conf.get("journalctl_unit", svc_key)
            jctl_lines = svc_conf.get("journalctl_lines", max_lines)
            lines = read_journalctl_logs(unit, jctl_lines)
            if not lines:
                lines = ["(no logs from journalctl unit {})".format(unit)]
            service_logs[svc_key] = lines
        else:
            log_file = svc_conf.get("log_file")
            if not log_file:
                service_logs[svc_key] = ["(no log file configured)"]
                continue
            if os.path.exists(log_file):
                if os.path.getsize(log_file) == 0:
                    service_logs[svc_key] = ["Service is not running or has not produced any logs yet."]
                else:
                    try:
                        lines = tail_log_lines(log_file, max_lines, log_block_bytes)
                        if not lines:
                            service_logs[svc_key] = ["(log file has no meaningful entries)"]
                        else:
                            service_logs[svc_key] = list(lines)
                    except Exception as e:
                        service_logs[svc_key] = ["Error reading logs: {}".format(str(e))]
            else:
                service_logs[svc_key] = ["Log file not created yet..."]
    return service_logs


def get_client_ips(config: dict) -> list[str]:
    log_file = config["monitoring"].get("log_file", "")
    if not log_file:
        for svc_conf in config.get("services", {}).values():
            if isinstance(svc_conf, dict) and svc_conf.get("log_file"):
                log_file = svc_conf["log_file"]
                break
    if not log_file or not os.path.exists(log_file):
        return []
    try:
        max_lines = config["monitoring"]["log_lines"]
        block_bytes = config["monitoring"]["log_block_bytes"]
        lines = tail_log_lines(log_file, max_lines, block_bytes)
        ip_pattern = r'remote_addr="([^"]+)"'
        ips = []
        for line in lines:
            ips.extend(re.findall(ip_pattern, line))
        return list(set(ip for ip in ips if ip != '127.0.0.1'))
    except Exception as e:
        logger.error("Failed to extract client IPs from log file: %s", e)
        return []
