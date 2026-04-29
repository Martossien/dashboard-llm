"""
LLM startup state tracking — load time stats, ETA, elapsed.

Extrait de monitor.py (Savepoint B).
"""

import json
import logging
import os
import time

from llm_dashboard.services.detection import find_llama_process

logger = logging.getLogger("dashboard-llm.startup")

LOAD_STATS_PATH = "/opt/dashboard-llm/llama_load_stats.json"
LOAD_STATS = {"durations_seconds": [], "avg_seconds": None}
LLAMA_STARTUP = {"pid": None, "start_time": None, "ready_recorded": False}


def load_startup_stats():
    try:
        if os.path.exists(LOAD_STATS_PATH):
            with open(LOAD_STATS_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                durations = data.get("durations_seconds", [])
                if isinstance(durations, list):
                    cleaned = [float(item) for item in durations if isinstance(item, (int, float))]
                    LOAD_STATS["durations_seconds"] = cleaned[-5:]
                    if cleaned:
                        LOAD_STATS["avg_seconds"] = sum(LOAD_STATS["durations_seconds"]) / len(LOAD_STATS["durations_seconds"])
    except Exception as exc:
        logger.debug("Failed to load startup stats: %s", exc)


def save_startup_stats():
    try:
        payload = {
            "durations_seconds": LOAD_STATS.get("durations_seconds", []),
            "avg_seconds": LOAD_STATS.get("avg_seconds"),
        }
        with open(LOAD_STATS_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except Exception as exc:
        logger.debug("Failed to save startup stats: %s", exc)


def record_startup_duration(duration_seconds):
    if duration_seconds <= 0:
        return
    durations = LOAD_STATS.get("durations_seconds", [])
    durations.append(duration_seconds)
    durations = durations[-5:]
    LOAD_STATS["durations_seconds"] = durations
    LOAD_STATS["avg_seconds"] = sum(durations) / len(durations)
    save_startup_stats()


load_startup_stats()


def get_llama_startup_state(llama_status):
    proc = find_llama_process()
    now = time.time()
    if not proc:
        LLAMA_STARTUP["pid"] = None
        LLAMA_STARTUP["start_time"] = None
        LLAMA_STARTUP["ready_recorded"] = False
        return {
            "state": "DOWN",
            "loading_seconds": None,
            "eta_seconds": None,
            "avg_seconds": LOAD_STATS.get("avg_seconds"),
        }

    pid = proc.get("pid")
    start_time = proc.get("create_time")
    if start_time and (LLAMA_STARTUP["start_time"] != start_time or LLAMA_STARTUP["pid"] != pid):
        LLAMA_STARTUP["pid"] = pid
        LLAMA_STARTUP["start_time"] = start_time
        LLAMA_STARTUP["ready_recorded"] = False

    elapsed = None
    if start_time:
        elapsed = max(0.0, now - start_time)

    if llama_status == 'UP':
        if start_time and not LLAMA_STARTUP["ready_recorded"]:
            record_startup_duration(max(0.0, now - start_time))
            LLAMA_STARTUP["ready_recorded"] = True
        return {
            "state": "READY",
            "loading_seconds": elapsed,
            "eta_seconds": 0,
            "avg_seconds": LOAD_STATS.get("avg_seconds"),
        }

    if LLAMA_STARTUP["ready_recorded"]:
        return {
            "state": "UNRESPONSIVE",
            "loading_seconds": elapsed,
            "eta_seconds": None,
            "avg_seconds": LOAD_STATS.get("avg_seconds"),
        }

    avg = LOAD_STATS.get("avg_seconds")
    loading_threshold = avg if isinstance(avg, (int, float)) else 900.0
    loading_threshold = max(60.0, loading_threshold)
    if elapsed is not None and elapsed > loading_threshold:
        return {
            "state": "UNRESPONSIVE",
            "loading_seconds": elapsed,
            "eta_seconds": None,
            "avg_seconds": avg,
        }

    eta = None
    if elapsed is not None and isinstance(avg, (int, float)):
        eta = max(0.0, avg - elapsed)

    return {
        "state": "LOADING",
        "loading_seconds": elapsed,
        "eta_seconds": eta,
        "avg_seconds": avg,
    }
