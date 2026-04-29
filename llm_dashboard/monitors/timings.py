"""
Token rate monitors — extraction des debits de tokens (prompt/generation)
pour llama.cpp, ik_llama.cpp et vLLM.

Extrait de monitor.py (Lot 5).
"""

import logging
import os
import re
import time

logger = logging.getLogger("dashboard-llm.monitors.timings")

# Cache des derniers debits (variables au niveau module pour persistance)
LLAMA_TIMINGS = {
    "prompt_tokens_per_second": None,
    "generation_tokens_per_second": None,
    "last_update": None,
}

VLLM_TIMINGS = {
    "prompt_tokens_per_second": None,
    "generation_tokens_per_second": None,
    "last_update": None,
}


def extract_llama_timings(log_file, max_lines=50, block_size=8192):
    """Extrait les debits de tokens (prompt/generation) depuis un log llama.cpp.

    Args:
        log_file: chemin du fichier de log
        max_lines: nombre de lignes a analyser
        block_size: taille des blocs de lecture

    Returns:
        tuple[float|None, float|None]: (prompt_rate, generation_rate)
    """
    from llm_dashboard.monitors.logs import tail_log_lines

    if not os.path.exists(log_file):
        return None, None

    try:
        lines = tail_log_lines(log_file, max_lines, block_size)
    except Exception as exc:
        logger.debug("Failed to read timings from %s: %s", log_file, exc)
        return None, None

    prompt_rate = None
    generation_rate = None

    prompt_patterns = [
        r"(?:prompt|sampling)\s+eval\s+time.*?(\d+(?:\.\d+)?)\s+(?:tok(?:ens?)?\s+per\s+sec|t\/s|tokens\/s|tok\/s|tokens?\s+per\s+second)",
        r"(\d+(?:\.\d+)?)\s+(?:tok(?:ens?)?\s+per\s+sec|t\/s|tokens\/s|tok\/s).*?(?:prompt|sampling)",
        r"n_tokens_second=([\d.]+)",
        r"(\d+(?:\.\d+)?)\s+(?:token|tokens)\s+per\s+second",
    ]

    generation_patterns = [
        r"(?:generation|predict)\s+eval\s+time.*?(\d+(?:\.\d+)?)\s+(?:tok(?:ens?)?\s+per\s+sec|t\/s|tokens\/s|tok\/s|tokens?\s+per\s+second)",
        r"(\d+(?:\.\d+)?)\s+(?:tok(?:ens?)?\s+per\s+sec|t\/s|tokens\/s|tok\/s).*?(?:generation|predict)",
        r"n_tokens_second=([\d.]+)",
        r"(\d+(?:\.\d+)?)\s+(?:token|tokens)\s+per\s+second",
    ]

    for line in reversed(lines):
        line_lower = line.lower()
        is_prompt_line = "prompt" in line_lower or "sampling" in line_lower
        is_generation_line = "generation" in line_lower or "predict" in line_lower

        if prompt_rate is None and (is_prompt_line or ("n_tokens_second" in line_lower and not is_generation_line)):
            for pattern in prompt_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    try:
                        rate = float(match.group(1))
                        if 0 < rate < 10000:
                            prompt_rate = rate
                            break
                    except (ValueError, IndexError):
                        continue

        if generation_rate is None and (is_generation_line or ("n_tokens_second" in line_lower and not is_prompt_line)):
            for pattern in generation_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    try:
                        rate = float(match.group(1))
                        if 0 < rate < 10000:
                            generation_rate = rate
                            break
                    except (ValueError, IndexError):
                        continue

        if prompt_rate is not None and generation_rate is not None:
            break

    _cache_timings(prompt_rate, generation_rate, LLAMA_TIMINGS)

    return LLAMA_TIMINGS["prompt_tokens_per_second"], LLAMA_TIMINGS["generation_tokens_per_second"]


def extract_vllm_timings(log_file, max_lines=50, block_size=8192):
    """Extrait les debits de tokens depuis un log vLLM.

    Format attendu:
        Avg prompt throughput: 989.7 tokens/s, Avg generation throughput: 34.7 tokens/s

    Returns:
        tuple[float|None, float|None]: (prompt_rate, generation_rate)
    """
    from llm_dashboard.monitors.logs import tail_log_lines

    if not os.path.exists(log_file):
        return None, None

    try:
        lines = tail_log_lines(log_file, max_lines, block_size)
    except Exception as exc:
        logger.debug("Failed to read vLLM timings from %s: %s", log_file, exc)
        return None, None

    prompt_rate = None
    generation_rate = None

    vllm_pattern = re.compile(
        r'Avg prompt throughput:\s*([\d.]+)\s*tokens/s,\s*Avg generation throughput:\s*([\d.]+)\s*tokens/s'
    )

    for line in reversed(lines):
        match = vllm_pattern.search(line)
        if match:
            try:
                p_rate = float(match.group(1))
                g_rate = float(match.group(2))
                if p_rate > 0.5:
                    prompt_rate = p_rate
                if g_rate > 0.5:
                    generation_rate = g_rate
                break
            except (ValueError, IndexError):
                continue

    _cache_timings(prompt_rate, generation_rate, VLLM_TIMINGS)

    return VLLM_TIMINGS["prompt_tokens_per_second"], VLLM_TIMINGS["generation_tokens_per_second"]


def _cache_timings(prompt_rate, generation_rate, cache_dict):
    """Met a jour le cache de debits."""
    if prompt_rate is not None:
        cache_dict["prompt_tokens_per_second"] = prompt_rate
    if generation_rate is not None:
        cache_dict["generation_tokens_per_second"] = generation_rate
    if prompt_rate is not None or generation_rate is not None:
        cache_dict["last_update"] = time.time()


def get_llama_timings(config, get_log_file_fn):
    log_file = get_log_file_fn()
    return extract_llama_timings(log_file, config["monitoring"]["log_lines"], config["monitoring"]["log_block_bytes"])


def get_vllm_timings(config):
    log_file = config["services"]["vllm"].get("log_file", "/var/log/vllm_qwen36_27b.log")
    return extract_vllm_timings(log_file, config["monitoring"]["log_lines"], config["monitoring"]["log_block_bytes"])
