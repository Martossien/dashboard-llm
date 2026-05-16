"""Tests pour llm_dashboard/monitors/timings.py."""

from llm_dashboard.monitors.timings import (
    _extract_llama_from_loglines,
    _extract_vllm_from_loglines,
    _extract_rates_from_logs,
)


def test_extract_llama_from_loglines_eval():
    prompt_rate, gen_rate = _extract_llama_from_loglines([
        "prompt eval time = 1234.56 ms / 512 tokens (2.41 ms per token, 414.83 tokens per second)",
        "generation eval time = 5678.90 ms / 256 tokens (22.18 ms per token, 45.08 tokens per second)",
    ])
    assert prompt_rate == 414.83
    assert gen_rate == 45.08


def test_extract_llama_from_loglines_prompt_only():
    prompt_rate, gen_rate = _extract_llama_from_loglines([
        "prompt eval time = 10 ms / 10 tokens (1 ms per token, 100.0 tokens per second)",
    ])
    assert prompt_rate == 100.0
    assert gen_rate is None


def test_extract_vllm_from_loglines_throughput():
    prompt_rate, gen_rate = _extract_vllm_from_loglines([
        "Avg prompt throughput: 989.7 tokens/s, Avg generation throughput: 34.7 tokens/s",
    ])
    assert prompt_rate == 989.7
    assert gen_rate == 34.7


def test_extract_llama_from_loglines_empty():
    prompt_rate, gen_rate = _extract_llama_from_loglines([])
    assert prompt_rate is None
    assert gen_rate is None


def test_extract_vllm_from_loglines_empty():
    prompt_rate, gen_rate = _extract_vllm_from_loglines([])
    assert prompt_rate is None
    assert gen_rate is None


def test_extract_rates_from_logs_missing_file():
    prompt_rate, gen_rate = _extract_rates_from_logs("/nonexistent/path.log", "llama.cpp")
    assert prompt_rate is None
    assert gen_rate is None