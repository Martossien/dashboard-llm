"""Tests pour llm_dashboard/monitors/timings.py."""

from pathlib import Path


def _reset_timing_caches():
    from llm_dashboard.monitors.timings import LLAMA_TIMINGS, VLLM_TIMINGS

    LLAMA_TIMINGS.update({
        "prompt_tokens_per_second": None,
        "generation_tokens_per_second": None,
        "last_update": None,
    })
    VLLM_TIMINGS.update({
        "prompt_tokens_per_second": None,
        "generation_tokens_per_second": None,
        "last_update": None,
    })


def test_extract_llama_timings_from_eval_lines(tmp_path):
    """Les lignes llama.cpp doivent extraire les debits, pas le nombre de tokens."""
    from llm_dashboard.monitors.timings import extract_llama_timings

    _reset_timing_caches()
    log_file = tmp_path / "llama.log"
    log_file.write_text(
        "prompt eval time = 1234.56 ms / 512 tokens "
        "(2.41 ms per token, 414.83 tokens per second)\n"
        "generation eval time = 5678.90 ms / 256 tokens "
        "(22.18 ms per token, 45.08 tokens per second)\n",
        encoding="utf-8",
    )

    prompt_rate, generation_rate = extract_llama_timings(str(log_file))

    assert prompt_rate == 414.83
    assert generation_rate == 45.08


def test_extract_llama_timings_returns_cached_values_when_next_read_has_no_rates(tmp_path):
    """Le cache conserve le dernier debit connu si une lecture suivante ne trouve rien."""
    from llm_dashboard.monitors.timings import extract_llama_timings

    _reset_timing_caches()
    log_file = tmp_path / "llama.log"
    log_file.write_text(
        "prompt eval time = 10 ms / 10 tokens (1 ms per token, 100.0 tokens per second)\n",
        encoding="utf-8",
    )
    assert extract_llama_timings(str(log_file)) == (100.0, None)

    log_file.write_text("ordinary log line without token rates\n", encoding="utf-8")
    assert extract_llama_timings(str(log_file)) == (100.0, None)


def test_extract_vllm_timings_from_throughput_line(tmp_path):
    """Les lignes vLLM exposent prompt et generation throughput sur une seule ligne."""
    from llm_dashboard.monitors.timings import extract_vllm_timings

    _reset_timing_caches()
    log_file = tmp_path / "vllm.log"
    log_file.write_text(
        "Avg prompt throughput: 989.7 tokens/s, "
        "Avg generation throughput: 34.7 tokens/s\n",
        encoding="utf-8",
    )

    assert extract_vllm_timings(str(log_file)) == (989.7, 34.7)


def test_extract_timings_missing_file_returns_none_tuple(tmp_path):
    """Un fichier absent ne doit pas lever d'exception."""
    from llm_dashboard.monitors.timings import extract_llama_timings, extract_vllm_timings

    _reset_timing_caches()
    missing = tmp_path / "missing.log"

    assert not Path(missing).exists()
    assert extract_llama_timings(str(missing)) == (None, None)
    assert extract_vllm_timings(str(missing)) == (None, None)
