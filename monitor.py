#!/usr/bin/env python3
"""
Monitor — point d'entree de compatibilite et lanceur principal.

Ce module existe pour la retro-compatibilite (tests, scripts).
La composition applicative reelle est dans llm_dashboard.app_factory.
"""
import logging
import os
from functools import partial

# ---- Re-exports de fonctions pures (importees par les tests) ----
from llm_dashboard.config import (
    DEFAULT_CONFIG, ENV_OVERRIDES,
    deep_update, parse_bool, parse_list,
    get_nested, set_nested, get_default,
    apply_env_overrides, validate_config, load_config,
)
from llm_dashboard.services.detection import join_url
from llm_dashboard.monitors.logs import tail_log_lines, read_journalctl_logs
from llm_dashboard.monitors.timings import (
    extract_llama_timings as _extract_llama_timings,
    extract_vllm_timings as _extract_vllm_timings,
    LLAMA_TIMINGS as _LLAMA_TIMINGS,
    VLLM_TIMINGS as _VLLM_TIMINGS,
)

# ---- Re-exports de detection (non-partial) ----
from llm_dashboard.services.detection import (
    find_ik_llama_process,
    find_llama_process,
    find_vllm_process,
)

from llm_dashboard.app_factory import create_full_app

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(
    level=os.environ.get("DASHBOARD_LOG_LEVEL", "INFO").upper(),
    format=LOG_FORMAT,
)

logger = logging.getLogger("dashboard-llm")

app, CONFIG = create_full_app(setup_signals=True)

# ---- Partial: re-crees pour retro-compatibilite (importes par les tests) ----
from llm_dashboard.services.commands import CommandRunner
from llm_dashboard.services.detection import (
    detect_model_name as _detect_model_name,
    _get_active_llama_key as _get_active_llama_key_fn,
    get_llama_status as _get_llama_status_fn,
    get_services_status as _get_services_status_fn,
    get_admin_services_status as _get_admin_services_status_fn,
)
from llm_dashboard.monitors.logs import (
    get_logs as _get_logs_fn,
    get_client_ips as _get_client_ips_fn,
)
from llm_dashboard.monitors.timings import (
    get_llama_timings as _get_llama_timings_fn,
    get_vllm_timings as _get_vllm_timings_fn,
)

# Recree les memes partials que le vieux monitor.py pour compat tests
get_services_status = partial(_get_services_status_fn, CONFIG, CommandRunner())
get_admin_services_status = partial(_get_admin_services_status_fn, CONFIG, CommandRunner())
get_logs = partial(_get_logs_fn, CONFIG, CommandRunner())
get_client_ips = partial(_get_client_ips_fn, CONFIG)
get_vllm_timings = partial(_get_vllm_timings_fn, CONFIG)


if __name__ == '__main__':
    app.run(
        host=CONFIG["server"]["host"],
        port=CONFIG["server"]["port"],
        debug=CONFIG["server"].get("debug", False),
    )
