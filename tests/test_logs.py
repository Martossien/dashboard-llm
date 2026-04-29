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
