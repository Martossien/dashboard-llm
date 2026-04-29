"""Tests pour llm_dashboard/services/detection.py."""
import pytest
from llm_dashboard.services.detection import join_url, match_model, guess_service_from_model


class TestJoinURL:
    def test_basic(self):
        assert join_url("http://127.0.0.1:8080", "/health") == "http://127.0.0.1:8080/health"

    def test_base_trailing_slash(self):
        assert join_url("http://127.0.0.1:8080/", "/health") == "http://127.0.0.1:8080/health"

    def test_endpoint_no_slash(self):
        assert join_url("http://127.0.0.1:8080", "health") == "http://127.0.0.1:8080/health"

    def test_both_slashes(self):
        assert join_url("http://127.0.0.1:8080/", "health") == "http://127.0.0.1:8080/health"

    def test_https(self):
        assert join_url("https://example.com:443", "/api/v1") == "https://example.com:443/api/v1"


class TestMatchModel:
    def test_exact_match(self):
        assert match_model("qwen3-35b-arbitrage-ud-q8_k_xl", r"(?i)qwen3-35b.*ud-q8")

    def test_partial_match(self):
        assert match_model("qwen3-35b-arbitrage-q8_0", r"(?i)qwen3-35b.*q8(?!.*ud)")

    def test_no_match(self):
        assert not match_model("mistral-7b-instruct", r"(?i)qwen3-35b")

    def test_none_model(self):
        assert not match_model(None, r"(?i)test")

    def test_none_pattern(self):
        assert not match_model("anything", None)

    def test_both_none(self):
        assert not match_model(None, None)

    def test_glm_pattern(self):
        assert match_model("glm-4.7-iq5", r"(?i)glm|ik_llama")

    def test_vllm_pattern(self):
        assert match_model("qwen36-27b-fp8", r"(?i)qwen36-27b|qwen3.6-27b")


class TestGuessServiceFromModel:
    def _make_svc(self, key, pattern):
        from llm_dashboard.models import ServiceConfig
        return ServiceConfig(
            key=key, display_name=key, backend="llama.cpp",
            models_endpoint="/v1/models", model_detect_pattern=pattern,
        )

    def test_matches_q8(self):
        svcs = [
            self._make_svc("qwen36_35b_udq8", r"(?i)qwen3-35b.*ud-q8"),
            self._make_svc("qwen36_35b_q8", r"(?i)qwen3-35b.*q8(?!.*ud)"),
        ]
        result = guess_service_from_model("qwen3-35b-arbitrage-q8_0", svcs)
        assert result == "qwen36_35b_q8"

    def test_matches_udq8(self):
        svcs = [
            self._make_svc("qwen36_35b_udq8", r"(?i)qwen3-35b.*ud-q8"),
            self._make_svc("qwen36_35b_q8", r"(?i)qwen3-35b.*q8(?!.*ud)"),
        ]
        result = guess_service_from_model("qwen3-35b-arbitrage-ud-q8_k_xl", svcs)
        assert result == "qwen36_35b_udq8"

    def test_no_match_returns_none(self):
        svcs = [self._make_svc("test", r"(?i)qwen")]
        result = guess_service_from_model("mistral-7b", svcs)
        assert result is None

    def test_none_model_returns_none(self):
        svcs = [self._make_svc("test", r"(?i)test")]
        result = guess_service_from_model(None, svcs)
        assert result is None

    def test_no_models_endpoint_skipped(self):
        from llm_dashboard.models import ServiceConfig
        svc = ServiceConfig(
            key="test", display_name="test", backend="llama.cpp",
            models_endpoint=None, model_detect_pattern=r"(?i)test",
        )
        result = guess_service_from_model("test-model", [svc])
        assert result is None
