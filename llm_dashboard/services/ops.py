"""
Service operations — start/stop des services LLM et nettoyage GPU.

Extrait de monitor.py (Lot 20, Savepoint G).
"""

import logging
import os
import signal as _signal
import time

from llm_dashboard.services.health import check_port_is_open
from llm_dashboard.services.detection import get_admin_services_status

_logger = logging.getLogger("dashboard-llm.ops")


def _check_port_free(port, timeout=10):
    for _ in range(timeout):
        if not check_port_is_open("127.0.0.1", port, timeout=1):
            return True
        time.sleep(1)
    return False


def _run_cmd(command_runner, cmd, timeout=5):
    try:
        cmd = list(cmd)
        result = None
        if len(cmd) >= 3 and cmd[0] == "systemctl":
            action, unit = cmd[1], cmd[2]
            if action == "is-active":
                result = command_runner.systemctl_is_active(unit, timeout=timeout)
            elif action == "start":
                result = command_runner.systemctl_start(unit, timeout=timeout)
            elif action == "stop":
                result = command_runner.systemctl_stop(unit, timeout=timeout)
            elif action == "kill":
                result = command_runner.systemctl_kill(unit, timeout=timeout)
        elif len(cmd) >= 4 and cmd[0] == "fuser" and cmd[1] == "-k":
            sig = cmd[2].replace("-SIG", "")
            port = int(str(cmd[3]).split("/", 1)[0])
            result = command_runner.fuser_kill_port(port, signal=sig, timeout=timeout)
        if result is None:
            return "", "Command not allowed: {}".format(" ".join(str(c) for c in cmd)), -1
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1


def _kill_gpu_processes(gpu_monitor, kill_vram_threshold_mib=100, sigkill_after=5):
    try:
        processes = gpu_monitor.gpu_processes()
    except Exception as exc:
        _logger.error("_kill_gpu_processes: failed to list GPU processes: %s", exc)
        return []
    if not processes:
        return []
    big_procs = [p for p in processes if p.get("vram_mib", 0) >= kill_vram_threshold_mib]
    if not big_procs:
        return []
    pids_killed = []
    for p in big_procs:
        try:
            os.kill(p["pid"], _signal.SIGTERM)
            _logger.info("  SIGTERM -> PID %d (%s, %.0f MiB)", p["pid"], p.get("name", "?"), p.get("vram_mib", 0))
            pids_killed.append(p["pid"])
        except (ProcessLookupError, PermissionError) as e:
            _logger.warning("  Cannot signal PID %d: %s", p["pid"], e)
    time.sleep(sigkill_after)
    try:
        survivors = gpu_monitor.gpu_processes()
    except Exception:
        survivors = []
    survivor_pids = {p["pid"] for p in survivors if p.get("vram_mib", 0) >= kill_vram_threshold_mib}
    if survivor_pids:
        for pid in survivor_pids:
            try:
                os.kill(pid, _signal.SIGKILL)
                _logger.info("  SIGKILL -> PID %d", pid)
            except (ProcessLookupError, PermissionError) as e:
                _logger.warning("  Cannot SIGKILL PID %d: %s", pid, e)
        time.sleep(2)
    _logger.info("_kill_gpu_processes: done. %d PIDs killed.", len(pids_killed))
    return pids_killed


def _get_running_llm_key_on_8080(config, command_runner):
    status = get_admin_services_status(config, command_runner)
    for key, svc in status.items():
        if svc.get("is_llm") and svc.get("port") == 8080 and svc.get("running"):
            return key
    return None


def do_start_service(config, command_runner, gpu_monitor, key):
    all_conf = config.get("start_stop", {})
    if key not in all_conf:
        return {"success": False, "message": "Service inconnu: {}".format(key)}
    conf = all_conf[key]
    if not conf.get("start_command", []):
        return {"success": False, "message": "Pas de start_command pour: {}".format(key)}
    is_llm = conf.get("is_llm", False)
    vram_min = conf.get("vram_min_mib", 0)
    if vram_min > 0 and gpu_monitor:
        try:
            vram = gpu_monitor.vram_status()
            if vram.get("enabled") and not vram.get("error"):
                for gpu in vram.get("gpus", []):
                    if gpu["free_mb"] < vram_min:
                        return {"success": False, "message": "GPU {} ({}) a seulement {:.0f} MiB libres (min: {:.0f} MiB)".format(
                            gpu["index"], gpu["name"], gpu["free_mb"], vram_min)}
        except Exception as exc:
            _logger.warning("do_start_service: vram check failed: %s", exc)
    if is_llm and conf.get("port") == 8080:
        running_key = _get_running_llm_key_on_8080(config, command_runner)
        if running_key and running_key != key:
            do_stop_service(config, command_runner, gpu_monitor, running_key)
            time.sleep(3)
    stdout, stderr, rc = _run_cmd(command_runner, conf.get("start_command", []), timeout=60)
    if rc != 0:
        return {"success": False, "message": "Echec du demarrage (rc={}): {}".format(rc, stderr)}
    return {"success": True, "message": "Service {} demarre.".format(key)}


def do_stop_service(config, command_runner, gpu_monitor, key):
    all_conf = config.get("start_stop", {})
    if key not in all_conf:
        return {"success": False, "message": "Service inconnu: {}".format(key)}
    conf = all_conf[key]
    stop_cmd = conf.get("stop_command", [])
    if not stop_cmd:
        return {"success": False, "message": "Pas de stop_command pour: {}".format(key)}
    is_llm = conf.get("is_llm", False)
    port = conf.get("port", 0)
    _logger.info("do_stop_service(%s): systemctl stop...", key)
    stdout, stderr, rc = _run_cmd(command_runner, stop_cmd, timeout=15)
    if rc != 0:
        if "inactive" in stderr.lower() or "not loaded" in stderr.lower():
            _logger.info("do_stop_service(%s): service deja inactif.", key)
        else:
            _logger.warning("do_stop_service(%s): stop a echoue (rc=%d): %s", key, rc, stderr[:200])
        unit = conf.get("systemd_unit", "")
        if unit:
            try:
                command_runner.systemctl_kill(unit, timeout=10)
                _logger.info("do_stop_service(%s): systemctl kill %s envoye.", key, unit)
            except Exception:
                pass
    if port:
        port_free = _check_port_free(port, timeout=8)
        if not port_free:
            _logger.warning("do_stop_service(%s): port %d encore occupe, force kill...", key, port)
            try:
                command_runner.fuser_kill_port(port, signal="TERM", timeout=10)
            except Exception:
                pass
            time.sleep(3)
            port_free = _check_port_free(port, timeout=5)
            if not port_free:
                try:
                    command_runner.fuser_kill_port(port, signal="KILL", timeout=10)
                except Exception:
                    pass
                time.sleep(2)
    if is_llm and gpu_monitor:
        _logger.info("do_stop_service(%s): kill_gpu_processes...", key)
        killed = _kill_gpu_processes(gpu_monitor, kill_vram_threshold_mib=500, sigkill_after=5)
        if killed:
            _logger.info("do_stop_service(%s): %d processus GPU tus.", key, len(killed))
            time.sleep(2)
    if port:
        if not _check_port_free(port, timeout=5):
            return {"success": False, "message": "Port {} encore occupe apres stop et force kill.".format(port)}
    return {"success": True, "message": "Service {} arrete.".format(key)}


def stop_all_llm_engines(config, command_runner, gpu_monitor):
    results = []
    status = get_admin_services_status(config, command_runner)
    for key, svc in status.items():
        if not svc.get("is_llm") or svc.get("port") != 8080 or not svc.get("running"):
            continue
        conf = config.get("start_stop", {}).get(key, {})
        stop_cmd = conf.get("stop_command", [])
        if not stop_cmd:
            results.append({"key": key, "status": "error", "message": "no stop_command configured"})
            continue
        stdout, stderr, rc = _run_cmd(command_runner, stop_cmd, timeout=60)
        results.append({"key": key, "status": "stopped" if rc == 0 else "failed", "stdout": stdout, "stderr": stderr})
    time.sleep(3)
    if not _check_port_free(8080, timeout=5):
        _logger.warning("stop_all_llm_engines: port 8080 encore occupe, force kill...")
        try:
            command_runner.fuser_kill_port(8080, signal="TERM", timeout=10)
        except Exception:
            pass
        time.sleep(3)
    if gpu_monitor:
        killed = _kill_gpu_processes(gpu_monitor, kill_vram_threshold_mib=500, sigkill_after=5)
        if killed:
            _logger.info("stop_all_llm_engines: %d processus GPU residuels tus.", len(killed))
    time.sleep(2)
    return results
