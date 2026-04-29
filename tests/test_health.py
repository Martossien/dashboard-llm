"""Tests pour llm_dashboard/services/health.py."""
import pytest
from unittest.mock import patch, MagicMock


class TestCheckServiceHealth:
    def test_up_when_status_lt_400(self):
        """HTTP 200 -> UP."""
        from llm_dashboard.services.health import check_service_health

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("llm_dashboard.services.health._requests") as mock_requests:
            mock_requests.get.return_value = mock_response
            status, latency = check_service_health("http://127.0.0.1:8080", "/health")

        assert status == "UP"
        assert latency is not None
        assert latency >= 0

    def test_down_when_status_ge_400(self):
        """HTTP 500 -> DOWN."""
        from llm_dashboard.services.health import check_service_health

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("llm_dashboard.services.health._requests") as mock_requests:
            mock_requests.get.return_value = mock_response
            status, latency = check_service_health("http://127.0.0.1:8080", "/health")

        assert status == "DOWN"

    def test_down_on_connection_error(self):
        """Exception reseau -> DOWN."""
        from llm_dashboard.services.health import check_service_health

        with patch("llm_dashboard.services.health._requests") as mock_requests:
            mock_requests.get.side_effect = Exception("Connection refused")
            status, latency = check_service_health("http://127.0.0.1:8080", "/health")

        assert status == "DOWN"
        assert latency is None

    def test_down_on_timeout(self):
        """Timeout -> DOWN."""
        from llm_dashboard.services.health import check_service_health
        import requests as real_requests

        with patch("llm_dashboard.services.health._requests") as mock_requests:
            mock_requests.get.side_effect = real_requests.exceptions.Timeout()
            status, latency = check_service_health("http://127.0.0.1:8080", "/health")

        assert status == "DOWN"

    def test_url_constructed_correctly(self):
        """L'URL est correctement construite avec base_url + endpoint."""
        from llm_dashboard.services.health import check_service_health

        with patch("llm_dashboard.services.health._requests") as mock_requests:
            mock_requests.get.return_value = MagicMock(status_code=200)
            check_service_health("http://127.0.0.1:8080/", "health")

        mock_requests.get.assert_called_once_with(
            "http://127.0.0.1:8080/health", timeout=2.0
        )

    def test_down_when_requests_not_available(self, monkeypatch):
        """Si requests n'est pas installe, retourne DOWN."""
        import importlib
        import llm_dashboard.services.health

        monkeypatch.setattr(llm_dashboard.services.health, "_requests", None)
        status, latency = llm_dashboard.services.health.check_service_health(
            "http://127.0.0.1:8080", "/health"
        )
        assert status == "DOWN"
        assert latency is None


class TestCheckPortIsOpen:
    def test_port_open(self):
        """Simule un port ouvert (connect_ex retourne 0)."""
        from llm_dashboard.services.health import check_port_is_open

        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0

        with patch("socket.socket", return_value=mock_sock):
            result = check_port_is_open("127.0.0.1", 8080)

        assert result is True

    def test_port_closed(self):
        """Simule un port ferme (connect_ex retourne != 0)."""
        from llm_dashboard.services.health import check_port_is_open

        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1

        with patch("socket.socket", return_value=mock_sock):
            result = check_port_is_open("127.0.0.1", 8080)

        assert result is False

    def test_socket_error(self):
        """Erreur socket -> False."""
        from llm_dashboard.services.health import check_port_is_open

        with patch("socket.socket", side_effect=OSError()):
            result = check_port_is_open("127.0.0.1", 8080)

        assert result is False


class TestWaitForPortFree:
    def test_port_already_free(self):
        """Port deja libre -> True immediatement."""
        from llm_dashboard.services.health import wait_for_port_free

        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 1  # connexion refusee

        with patch("socket.socket", return_value=mock_sock):
            result = wait_for_port_free("127.0.0.1", 8080, timeout=3)

        assert result is True

    def test_port_stays_occupied(self):
        """Port occupe -> timeout -> False."""
        from llm_dashboard.services.health import wait_for_port_free

        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0  # connexion acceptee

        with patch("socket.socket", return_value=mock_sock), \
             patch("time.sleep"):  # ne pas attendre vraiment
            result = wait_for_port_free("127.0.0.1", 8080, timeout=3)

        assert result is False


class TestCheckSystemdUnitActive:
    def test_unit_active(self):
        """systemctl is-active retourne 'active'."""
        from llm_dashboard.services.health import check_systemd_unit_active

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="active", stderr="", returncode=0)
            result = check_systemd_unit_active("test.service")

        assert result is True

    def test_unit_activating(self):
        """systemctl is-active retourne 'activating'."""
        from llm_dashboard.services.health import check_systemd_unit_active

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="activating", stderr="", returncode=0)
            result = check_systemd_unit_active("test.service")

        assert result is True

    def test_unit_inactive(self):
        """systemctl is-active retourne 'inactive'."""
        from llm_dashboard.services.health import check_systemd_unit_active

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="inactive", stderr="", returncode=0)
            result = check_systemd_unit_active("test.service")

        assert result is False

    def test_subprocess_error(self):
        """Erreur subprocess -> False."""
        from llm_dashboard.services.health import check_systemd_unit_active

        with patch("subprocess.run", side_effect=Exception("No systemctl")):
            result = check_systemd_unit_active("test.service")

        assert result is False
