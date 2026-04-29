"""
Tests de caracterisation — Fonctions utilitaires pures.

Ces fonctions n'ont pas de dependance systeme.
Elles doivent etre testees en isolation, sans mock.
"""

import pytest


# ============================================================================
# join_url
# ============================================================================

class TestJoinURL:
    """Tests pour join_url(base_url, endpoint)."""

    def test_basic(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:8080", "/health") == "http://127.0.0.1:8080/health"

    def test_base_with_trailing_slash(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:8080/", "/health") == "http://127.0.0.1:8080/health"

    def test_endpoint_without_slash(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:8080", "health") == "http://127.0.0.1:8080/health"

    def test_both_slashes(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:8080/", "health") == "http://127.0.0.1:8080/health"

    def test_both_with_slashes(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:8080/", "/health") == "http://127.0.0.1:8080/health"

    def test_https(self):
        from monitor import join_url
        assert join_url("https://example.com:443", "/api/v1") == "https://example.com:443/api/v1"

    def test_root_endpoint(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:11434", "/") == "http://127.0.0.1:11434/"

    def test_empty_endpoint(self):
        from monitor import join_url
        assert join_url("http://127.0.0.1:8080", "") == "http://127.0.0.1:8080/"


# ============================================================================
# parse_bool
# ============================================================================

class TestParseBool:
    """Tests pour parse_bool(value)."""

    def test_bool_true(self):
        from monitor import parse_bool
        assert parse_bool(True) is True

    def test_bool_false(self):
        from monitor import parse_bool
        assert parse_bool(False) is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "YES", "ON", " True ", " 1 "])
    def test_truthy_values(self, value):
        from monitor import parse_bool
        assert parse_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "FALSE", "NO", "OFF", " False ", " 0 "])
    def test_falsy_values(self, value):
        from monitor import parse_bool
        assert parse_bool(value) is False

    @pytest.mark.parametrize("value", ["maybe", "2", "", "t", "f", "N/A", "disabled"])
    def test_invalid_raises(self, value):
        from monitor import parse_bool
        with pytest.raises(ValueError, match="Invalid boolean value"):
            parse_bool(value)


# ============================================================================
# parse_list
# ============================================================================

class TestParseList:
    """Tests pour parse_list(value)."""

    def test_already_list(self):
        from monitor import parse_list
        assert parse_list(["a", "b", "c"]) == ["a", "b", "c"]

    def test_comma_separated(self):
        from monitor import parse_list
        assert parse_list("a,b,c") == ["a", "b", "c"]

    def test_with_spaces(self):
        from monitor import parse_list
        assert parse_list("a, b , c") == ["a", "b", "c"]

    def test_single_item(self):
        from monitor import parse_list
        assert parse_list("only") == ["only"]

    def test_empty_string(self):
        from monitor import parse_list
        assert parse_list("") == []

    def test_empty_list(self):
        from monitor import parse_list
        assert parse_list([]) == []

    def test_trailing_comma(self):
        from monitor import parse_list
        assert parse_list("a,b,") == ["a", "b"]


# ============================================================================
# deep_update
# ============================================================================

class TestDeepUpdate:
    """Tests pour deep_update(target, updates)."""

    def test_flat_merge(self):
        from monitor import deep_update
        target = {"a": 1, "b": 2}
        deep_update(target, {"b": 3, "c": 4})
        assert target == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        from monitor import deep_update
        target = {"a": {"x": 1, "y": 2}, "b": 3}
        deep_update(target, {"a": {"y": 20, "z": 30}})
        assert target == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}

    def test_deep_nested(self):
        from monitor import deep_update
        target = {"a": {"b": {"c": 1}}}
        deep_update(target, {"a": {"b": {"d": 2}}})
        assert target == {"a": {"b": {"c": 1, "d": 2}}}

    def test_override_non_dict(self):
        from monitor import deep_update
        target = {"a": {"x": 1}, "b": "hello"}
        deep_update(target, {"a": "overwrite"})
        assert target == {"a": "overwrite", "b": "hello"}

    def test_add_new_key(self):
        from monitor import deep_update
        target = {}
        deep_update(target, {"new": {"nested": "value"}})
        assert target == {"new": {"nested": "value"}}

    def test_empty_updates(self):
        from monitor import deep_update
        target = {"a": 1}
        deep_update(target, {})
        assert target == {"a": 1}


# ============================================================================
# get_nested / set_nested
# ============================================================================

class TestNestedAccess:
    """Tests pour get_nested et set_nested."""

    def test_get_nested_simple(self):
        from monitor import get_nested
        config = {"server": {"port": 5000}}
        assert get_nested(config, ("server", "port")) == 5000

    def test_get_nested_deep(self):
        from monitor import get_nested
        config = {"a": {"b": {"c": 42}}}
        assert get_nested(config, ("a", "b", "c")) == 42

    def test_get_nested_missing_raises(self):
        from monitor import get_nested
        config = {"a": 1}
        with pytest.raises(KeyError):
            get_nested(config, ("b",))

    def test_set_nested_existing(self):
        from monitor import set_nested
        config = {"server": {"port": 5000}}
        set_nested(config, ("server", "port"), 8080)
        assert config["server"]["port"] == 8080

    def test_set_nested_new_path(self):
        from monitor import set_nested
        config = {}
        set_nested(config, ("a", "b", "c"), 99)
        assert config == {"a": {"b": {"c": 99}}}

    def test_set_nested_preserves_siblings(self):
        from monitor import set_nested
        config = {"a": {"x": 1, "y": 2}}
        set_nested(config, ("a", "z"), 3)
        assert config == {"a": {"x": 1, "y": 2, "z": 3}}


# ============================================================================
# get_default
# ============================================================================

class TestGetDefault:
    """Tests pour get_default(path)."""

    def test_server_port_default(self):
        from monitor import get_default, DEFAULT_CONFIG
        assert get_default(("server", "port")) == DEFAULT_CONFIG["server"]["port"]

    def test_monitoring_refresh(self):
        from monitor import get_default
        assert get_default(("monitoring", "refresh_interval_ms")) == 1000

    def test_gpu_enable_default(self):
        from monitor import get_default
        assert get_default(("gpu", "enable")) is True


# ============================================================================
# ANSI escape cleaning (utilise dans tail_log_lines)
# ============================================================================

class TestANSICleaning:
    """Tests pour le nettoyage des sequences d'echappement ANSI."""

    def test_ansi_simple_pattern(self):
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07')
        text = "\x1b[32m[OK]\x1b[0m Service ready"
        cleaned = ansi_escape.sub('', text)
        assert cleaned == "[OK] Service ready"

    def test_no_ansi(self):
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07')
        text = "Normal log line"
        cleaned = ansi_escape.sub('', text)
        assert cleaned == "Normal log line"

    def test_ansi_bold(self):
        import re
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07')
        text = "\x1b[1mBOLD\x1b[0m normal"
        cleaned = ansi_escape.sub('', text)
        assert cleaned == "BOLD normal"


# ============================================================================
# Noise patterns (LLAMA_NOISE_PATTERNS)
# ============================================================================

class TestNoisePatterns:
    """Tests pour les patterns de filtrage de bruit llama.cpp."""

    def _get_patterns(self):
        import re
        return [
            re.compile(r'^\s*srv\s+stop:\s+all tasks already finished'),
            re.compile(r'^\s*srv\s+update_slots:\s+all slots are idle\s*$'),
            re.compile(r'^\s*que\s+start_loop:\s+waiting for new tasks\s*$'),
            re.compile(r'^\s*que\s+start_loop:\s+update slots\s*$'),
            re.compile(r'^\s*srv\s+update_slots:\s+run slots completed\s*$'),
            re.compile(r'^\s*que\s+start_loop:\s+processing new tasks\s*$'),
            re.compile(r'^\s*res\s+remove_waiti:\s+remove task\s'),
        ]

    @pytest.mark.parametrize("line", [
        "srv stop: all tasks already finished",
        "  srv stop: all tasks already finished",
        "srv update_slots: all slots are idle",
        "que start_loop: waiting for new tasks",
        "que start_loop: update slots",
        "srv update_slots: run slots completed",
        "que start_loop: processing new tasks",
        "res remove_waiti: remove task 1234",
    ])
    def test_noise_is_filtered(self, line):
        patterns = self._get_patterns()
        assert any(pat.search(line) for pat in patterns), f"'{line}' should match a noise pattern"

    @pytest.mark.parametrize("line", [
        "prompt eval time =  1234.56 ms /   512 tokens",
        "[2026-04-27 10:00:01] INFO  server: Model loaded",
        "generation eval time =  5678.90 ms /   256 tokens",
        "INFO: Started server process",
        "Listening on http://0.0.0.0:8080",
    ])
    def test_real_logs_not_filtered(self, line):
        patterns = self._get_patterns()
        assert not any(pat.search(line) for pat in patterns), f"'{line}' should NOT match a noise pattern"
