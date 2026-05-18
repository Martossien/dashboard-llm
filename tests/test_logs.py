"""
Tests de caracterisation — Lecture de logs (tail_log_lines).

Teste le comportement actuel de tail_log_lines avec des fichiers fixtures.
Valide : lecture des dernieres lignes, filtrage ANSI, filtrage du bruit llama.cpp.
"""

import os
import re
import pytest


class TestTailLogLines:
    """Tests pour tail_log_lines(log_file, max_lines, block_size)."""

    def test_reads_last_lines(self, log_file_with_content):
        """Verifie que tail_log_lines lit les N dernieres lignes d'un fichier."""
        from monitor import tail_log_lines

        filepath, raw_lines = log_file_with_content
        result = tail_log_lines(filepath, max_lines=3, block_size=1024)

        assert len(result) >= 1, "Should return at least one line"
        # La derniere ligne ecrite est "Request from 192.168.1.100"
        assert any("192.168.1.100" in line for line in result), \
            f"Last meaningful line should be present, got: {result}"

    def test_reads_empty_file(self, temp_log_file):
        """Verifie qu'un fichier vide retourne une liste vide."""
        from monitor import tail_log_lines
        open(temp_log_file, "w").close()  # fichier vide
        result = tail_log_lines(temp_log_file, max_lines=10, block_size=1024)
        assert result == []

    def test_nonexistent_file(self):
        """Verifie qu'un fichier inexistant leve une exception."""
        from monitor import tail_log_lines
        with pytest.raises(FileNotFoundError):
            tail_log_lines("/nonexistent/path/file.log", max_lines=10, block_size=1024)

    def test_filters_ansi_escape(self, log_file_with_content):
        """Verifie que les sequences ANSI sont supprimees."""
        from monitor import tail_log_lines

        filepath, _ = log_file_with_content
        result = tail_log_lines(filepath, max_lines=50, block_size=1024)

        # Aucune ligne ne doit contenir de sequence ANSI
        for line in result:
            assert "\x1b[" not in line, f"ANSI escape found in: {line!r}"
            assert "\x1b]" not in line, f"ANSI escape found in: {line!r}"

    def test_filters_noise(self, log_file_with_content):
        """Verifie que les lignes de bruit llama.cpp sont filtrees."""
        from monitor import tail_log_lines

        filepath, _ = log_file_with_content
        result = tail_log_lines(filepath, max_lines=50, block_size=1024)

        # Les lignes de bruit ne doivent pas apparaitre
        noise_keywords = [
            "all tasks already finished",
            "all slots are idle",
            "waiting for new tasks",
        ]
        for line in result:
            for keyword in noise_keywords:
                assert keyword not in line.lower(), \
                    f"Noise line found in result: {line!r}"

    def test_max_lines_respected(self):
        """Verifie que max_lines est bien respecte."""
        from monitor import tail_log_lines
        import tempfile

        # Creer un fichier avec 200 lignes
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(200):
                f.write(f"Line {i:04d}: some meaningful log content here\n")
            filepath = f.name

        try:
            result = tail_log_lines(filepath, max_lines=10, block_size=4096)
            assert len(result) == 10, f"Expected 10 lines, got {len(result)}"
            # Les 10 dernieres lignes
            assert "Line 0199" in result[-1]
            assert "Line 0190" in result[0]
        finally:
            os.unlink(filepath)

    def test_empty_lines_skipped(self):
        """Verifie que les lignes vides sont ignorees."""
        from monitor import tail_log_lines
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n")
            f.write("  \n")
            f.write("meaningful line\n")
            f.write("\n")
            f.write("another line\n")
            filepath = f.name

        try:
            result = tail_log_lines(filepath, max_lines=50, block_size=1024)
            assert len(result) == 2, f"Expected 2 non-empty lines, got {len(result)}: {result}"
            assert "meaningful line" in result[0]
            assert "another line" in result[1]
        finally:
            os.unlink(filepath)

    def test_handles_utf8(self):
        """Verifie que tail_log_lines gere les caracteres UTF-8."""
        from monitor import tail_log_lines
        import tempfile

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".log", delete=False) as f:
            f.write("Log avec des accents : éèêë àâ îï ôö ùû\n".encode("utf-8"))
            f.write("Emoji test: 🚀🔥\n".encode("utf-8"))
            filepath = f.name

        try:
            result = tail_log_lines(filepath, max_lines=50, block_size=1024)
            assert len(result) == 2
            assert "accents" in result[0] or "avec" in result[0] or "éèêë" in result[0]
            assert "🚀" in result[1]
        finally:
            os.unlink(filepath)


class TestReadJournalctLogs:
    """Tests pour read_journalctl_logs (mocke)."""

    def test_returns_empty_on_error(self, monkeypatch):
        """Verifie que la fonction retourne [] si subprocess echoue."""
        import subprocess

        def mock_run_fail(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="journalctl", timeout=5)

        monkeypatch.setattr("subprocess.run", mock_run_fail)

        from monitor import read_journalctl_logs
        result = read_journalctl_logs("ollama.service", 50)
        assert result == []

    def test_returns_last_lines(self, monkeypatch):
        """Verifie que la fonction retourne les dernieres lignes."""
        import subprocess

        stdout = "\n".join(f"line {i}" for i in range(100))

        def mock_run(*args, **kwargs):
            return type('result', (), {
                'stdout': stdout,
                'stderr': '',
                'returncode': 0,
            })()

        monkeypatch.setattr("subprocess.run", mock_run)

        from monitor import read_journalctl_logs
        result = read_journalctl_logs("ollama.service", max_lines=10)
        assert len(result) == 10
        assert result[-1] == "line 99"


class TestLogFilterPresets:
    """Tests pour le filtrage intelligent des logs par preset/backend."""

    def test_resolve_filter_default_vllm(self):
        """vllm avec log_filter=default doit filtrer les access logs uvicorn."""
        from llm_dashboard.monitors.logs import _resolve_filter_patterns, LOG_FILTER_PRESETS

        svc_conf = {"backend": "vllm", "log_filter": "default"}
        patterns = _resolve_filter_patterns(svc_conf)

        uvicorn_preset = LOG_FILTER_PRESETS["uvicorn_access"]
        assert uvicorn_preset in patterns

    def test_resolve_filter_default_proxy(self):
        """proxy avec log_filter=default doit filtrer werkzeug access + 404 metrics."""
        from llm_dashboard.monitors.logs import _resolve_filter_patterns, LOG_FILTER_PRESETS

        svc_conf = {"backend": "proxy", "log_filter": "default"}
        patterns = _resolve_filter_patterns(svc_conf)

        assert LOG_FILTER_PRESETS["werkzeug_access"] in patterns
        assert LOG_FILTER_PRESETS["werkzeug_metrics_404"] in patterns
        assert LOG_FILTER_PRESETS["login_redirect"] in patterns

    def test_resolve_filter_verbose_disables_all(self):
        """log_filter=verbose doit desactiver tout filtrage."""
        from llm_dashboard.monitors.logs import _resolve_filter_patterns

        svc_conf = {"backend": "vllm", "log_filter": "verbose"}
        patterns = _resolve_filter_patterns(svc_conf)

        assert patterns == []

    def test_resolve_filter_default_llama(self):
        """llama.cpp avec log_filter=default doit avoir les patterns llama noise."""
        from llm_dashboard.monitors.logs import _resolve_filter_patterns, LLAMA_NOISE_PATTERNS

        svc_conf = {"backend": "llama.cpp"}
        patterns = _resolve_filter_patterns(svc_conf)

        for noise_pat in LLAMA_NOISE_PATTERNS:
            assert noise_pat in patterns

    def test_resolve_filter_default_unknown_backend(self):
        """Un backend inconnu doit avoir seulement les patterns llama generiques."""
        from llm_dashboard.monitors.logs import _resolve_filter_patterns, LLAMA_NOISE_PATTERNS

        svc_conf = {"backend": "unknown"}
        patterns = _resolve_filter_patterns(svc_conf)

        assert patterns == list(LLAMA_NOISE_PATTERNS)

    def test_uvicorn_access_filter_matches(self):
        """Le preset uvicorn_access doit matcher les access logs vLLM."""
        from llm_dashboard.monitors.logs import LOG_FILTER_PRESETS

        pattern = LOG_FILTER_PRESETS["uvicorn_access"]
        assert pattern.search('(APIServer pid=12345) INFO:     127.0.0.1:54342 - "GET /metrics HTTP/1.1" 200 OK')
        assert pattern.search('(APIServer pid=12345) INFO:     127.0.0.1:54342 - "GET /v1/models HTTP/1.1" 200 OK')
        assert pattern.search('(APIServer pid=12345) INFO:     127.0.0.1:54342 - "GET /health HTTP/1.1" 200 OK')

    def test_uvicorn_access_filter_preserves_important(self):
        """Le preset uvicorn_access ne doit pas matcher les vrais logs vLLM importants."""
        from llm_dashboard.monitors.logs import LOG_FILTER_PRESETS

        pattern = LOG_FILTER_PRESETS["uvicorn_access"]
        assert not pattern.search('WARNING: Model loaded successfully')
        assert not pattern.search('ERROR: Out of memory')

    def test_werkzeug_access_filter_matches(self):
        """Le preset werkzeug_access doit matcher les access logs werkzeug."""
        from llm_dashboard.monitors.logs import LOG_FILTER_PRESETS

        pattern = LOG_FILTER_PRESETS["werkzeug_access"]
        assert pattern.search('2026-05-18 09:35:35 [INFO] - werkzeug:- 127.0.0.1 - - [18/May/2026 09:35:35] "GET /metrics HTTP/1.1" 200 -')
        assert pattern.search('2026-05-18 09:35:36 [INFO] - werkzeug:- 127.0.0.1 - - [18/May/2026 09:35:36] "GET / HTTP/1.1" 302 -')
        assert pattern.search('2026-05-18 09:35:36 [INFO] - werkzeug:- 127.0.0.1 - - [18/May/2026 09:35:36] "GET /login?next=/ HTTP/1.1" 200 -')

    def test_werkzeug_metrics_404_filter_matches(self):
        """Le preset werkzeug_metrics_404 doit matcher les 404 /metrics."""
        from llm_dashboard.monitors.logs import LOG_FILTER_PRESETS

        pattern = LOG_FILTER_PRESETS["werkzeug_metrics_404"]
        assert pattern.search('[2026-05-18 09:35:34,266] [WARNING] [srt-editor] 404: /metrics')
        assert pattern.search('[WARNING] [srt-editor] 404: /metrics')

    def test_login_redirect_filter_matches(self):
        """Le preset login_redirect doit matcher les redirects vers /login."""
        from llm_dashboard.monitors.logs import LOG_FILTER_PRESETS

        pattern = LOG_FILTER_PRESETS["login_redirect"]
        assert pattern.search('2026-05-18 09:35:36 [INFO] - werkzeug:- 127.0.0.1 - - [18/May/2026 09:35:36] "GET /login?next=/ HTTP/1.1" 200 -')

    def test_health_check_serving_filter_matches(self):
        """Le preset health_check_serving doit matcher les health checks Flask/Gradio."""
        from llm_dashboard.monitors.logs import LOG_FILTER_PRESETS

        pattern = LOG_FILTER_PRESETS["health_check_serving"]
        assert pattern.search('[2026-05-18 09:35:36,084] [DEBUG] [srt-editor] GET / — serving srt-editor-pro.html')
        assert pattern.search('[DEBUG] [my-app] GET / — serving index.html')
        assert not pattern.search('[INFO] [srt-editor] SRT Editor Pro server starting')
        assert not pattern.search('[WARNING] [srt-editor] 404: /metrics')

    def test_tail_log_lines_with_verbose_filter(self):
        """tail_log_lines avec filter_patterns=[] ne doit rien filtrer."""
        import tempfile
        from monitor import tail_log_lines

        noise_line = 'srv  stop: all tasks already finished, no need to cancel'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(noise_line + "\n")
            f.write("Important log message\n")
            filepath = f.name

        try:
            result = tail_log_lines(filepath, max_lines=50, block_size=1024,
                                     filter_patterns=[])
            assert len(result) == 2
            assert noise_line in result[0]
        finally:
            os.unlink(filepath)

    def test_tail_log_lines_with_custom_filter(self):
        """tail_log_lines doit filtrer selon les patterns fournis."""
        import re
        import tempfile
        from monitor import tail_log_lines

        access_line = '(APIServer pid=999) INFO:     127.0.0.1:12345 - "GET /metrics HTTP/1.1" 200 OK'
        important_line = "WARNING: Out of memory"
        custom_patterns = [re.compile(r'^\(APIServer pid=\d+\) INFO:')]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(access_line + "\n")
            f.write(important_line + "\n")
            filepath = f.name

        try:
            result = tail_log_lines(filepath, max_lines=50, block_size=1024,
                                     filter_patterns=custom_patterns)
            assert len(result) == 1
            assert "Out of memory" in result[0]
        finally:
            os.unlink(filepath)
