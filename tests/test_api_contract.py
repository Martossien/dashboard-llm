"""
Tests de contrat JSON — Verification des champs retournes par l'API.

Ces tests figent le comportement actuel de /api/data et /api/admin/status.
Ils garantissent que le refactoring ne cassera pas le frontend existant.
"""

import json
import pytest


# ============================================================================
# Champs obligatoires — /api/data
# ============================================================================

REQUIRED_API_DATA_FIELDS = {
    "cpu",
    "ram",
    "gpus",
    "services",
    "slots_active",
    "slots_total",
    "service_logs",
    "service_order",
    "service_names",
    "model_name",
    "prompt_tokens_per_second",
    "generation_tokens_per_second",
    "vllm_prompt_tokens_per_second",
    "vllm_generation_tokens_per_second",
    "client_ips",
    "llama_service_name",
    "ik_llama_service_name",
    "vllm_service_name",
    "active_llama_service_name",
    "active_llm_service_name",
    "llama_state",
    "llama_loading_seconds",
    "llama_eta_seconds",
    "llama_avg_load_seconds",
    "active_on_8080",
    "model_on_8080",
}


# ============================================================================
# Champs obligatoires — /api/admin/status
# ============================================================================

REQUIRED_ADMIN_STATUS_FIELDS = {
    "services",
    "vram",
    "service_logs",
    "service_order",
    "service_names",
}


# ============================================================================
# Tests contrat /api/data
# ============================================================================

class TestAPIDataContract:
    """Tests de contrat pour GET /api/data."""

    def test_returns_200(self, client):
        """L'endpoint /api/data doit retourner 200."""
        response = client.get("/api/data")
        assert response.status_code == 200

    def test_returns_valid_json(self, client):
        """La reponse doit etre du JSON valide."""
        response = client.get("/api/data")
        data = response.get_json()
        assert isinstance(data, dict)

    def test_all_required_fields_present(self, client):
        """Tous les champs attendus par le frontend doivent etre presents."""
        response = client.get("/api/data")
        data = response.get_json()

        missing = REQUIRED_API_DATA_FIELDS - set(data.keys())
        assert not missing, (
            f"Champs manquants dans /api/data: {sorted(missing)}\n"
            f"Champs presents: {sorted(data.keys())}"
        )

    def test_cpu_structure(self, client):
        """Verifie la structure du champ cpu."""
        response = client.get("/api/data")
        data = response.get_json()

        assert "load" in data["cpu"], "cpu.load missing"
        assert isinstance(data["cpu"]["load"], (int, float)), \
            f"cpu.load should be numeric, got {type(data['cpu']['load'])}"

    def test_ram_structure(self, client):
        """Verifie la structure du champ ram."""
        response = client.get("/api/data")
        data = response.get_json()

        for field in ("used", "total", "percent"):
            assert field in data["ram"], f"ram.{field} missing"
        assert isinstance(data["ram"]["used"], (int, float))
        assert isinstance(data["ram"]["total"], (int, float))

    def test_gpus_is_list(self, client):
        """Verifie que gpus est une liste (meme vide)."""
        response = client.get("/api/data")
        data = response.get_json()

        assert isinstance(data["gpus"], list), \
            f"gpus should be a list, got {type(data['gpus'])}"

    def test_services_is_dict(self, client):
        """Verifie que services est un dict."""
        response = client.get("/api/data")
        data = response.get_json()

        assert isinstance(data["services"], dict), \
            f"services should be a dict, got {type(data['services'])}"

        # Chaque service doit etre l'un des statuts valides
        valid_statuses = {"UP", "DOWN", "SLOW", "LOADING", "UNRESPONSIVE"}
        for svc_name, status in data["services"].items():
            assert status in valid_statuses, \
                f"Service '{svc_name}' has invalid status: {status}"

    def test_service_order_is_list(self, client):
        """Verifie que service_order est une liste."""
        response = client.get("/api/data")
        data = response.get_json()

        assert isinstance(data["service_order"], list)
        assert len(data["service_order"]) > 0

    def test_service_names_is_dict(self, client):
        """Verifie que service_names est un dict."""
        response = client.get("/api/data")
        data = response.get_json()

        assert isinstance(data["service_names"], dict)
        # Les cles de service_order doivent etre dans service_names
        for key in data["service_order"]:
            assert key in data["service_names"], \
                f"service_order key '{key}' not in service_names"

    def test_service_logs_is_dict(self, client):
        """Verifie que service_logs est un dict."""
        response = client.get("/api/data")
        data = response.get_json()

        assert isinstance(data["service_logs"], dict)

    def test_token_rates_are_numeric_or_none(self, client):
        """Verifie que les token rates sont numeriques ou None."""
        response = client.get("/api/data")
        data = response.get_json()

        for field in ("prompt_tokens_per_second", "generation_tokens_per_second",
                       "vllm_prompt_tokens_per_second", "vllm_generation_tokens_per_second"):
            value = data[field]
            assert value is None or isinstance(value, (int, float)), \
                f"{field} should be numeric or None, got {type(value)}: {value}"

    def test_model_fields_are_string_or_none(self, client):
        """Verifie que les champs model sont str ou None."""
        response = client.get("/api/data")
        data = response.get_json()

        for field in ("model_name", "model_on_8080", "active_on_8080"):
            value = data[field]
            assert value is None or isinstance(value, str), \
                f"{field} should be str or None, got {type(value)}: {value}"

    def test_service_names_match_config(self, client):
        """Verifie que les noms de service correspondent a la config."""
        from monitor import CONFIG

        response = client.get("/api/data")
        data = response.get_json()

        # Verifier que les cles config sont dans service_names
        for svc_key in CONFIG["services"]:
            assert svc_key in data["service_names"], \
                f"Service key '{svc_key}' should be in service_names"

    def test_llama_service_names_match_config(self, client):
        """Verifie que les noms de service LLM sont soit None soit correspondent a la config."""
        response = client.get("/api/data")
        data = response.get_json()

        # These fields should always be present (may be null if no service found)
        assert "llama_service_name" in data
        assert "ik_llama_service_name" in data
        assert "vllm_service_name" in data
        assert "active_llama_service_name" in data
        assert "active_llm_service_name" in data

        # If a llama-family backend is found, the name should match config
        if data["llama_service_name"] is not None:
            assert isinstance(data["llama_service_name"], str)
            assert len(data["llama_service_name"]) > 0
        if data["ik_llama_service_name"] is not None:
            assert isinstance(data["ik_llama_service_name"], str)
            assert len(data["ik_llama_service_name"]) > 0
        if data["vllm_service_name"] is not None:
            assert isinstance(data["vllm_service_name"], str)
            assert len(data["vllm_service_name"]) > 0

    def test_active_llm_service_name_distinction(self, client):
        """Verifie que active_llm_service_name est present et que la
        distinction llama vs llm est correcte: si un service llama-family
        est actif, les deux champs pointent vers lui; si vLLM est actif,
        active_llama_service_name est None."""
        response = client.get("/api/data")
        data = response.get_json()

        assert "active_llm_service_name" in data
        active_8080 = data.get("active_on_8080")

        if active_8080 in ("ik_llama_cpp", "llama_cpp"):
            assert data["active_llama_service_name"] is not None
            assert data["active_llm_service_name"] == data["active_llama_service_name"]
        elif active_8080 is not None:
            assert data["active_llama_service_name"] is None
            assert data["active_llm_service_name"] is not None


# ============================================================================
# Tests contrat /health
# ============================================================================

class TestHealthEndpoint:
    """Tests pour GET /health."""

    def test_returns_200(self, client):
        """L'endpoint /health doit retourner 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_valid_json(self, client):
        """La reponse doit etre du JSON valide."""
        response = client.get("/health")
        data = response.get_json()
        assert isinstance(data, dict)

    def test_status_is_ok(self, client):
        """Le statut doit etre 'ok'."""
        response = client.get("/health")
        data = response.get_json()
        assert data.get("status") == "ok"
        assert data.get("service") == "dashboard-llm"


# ============================================================================
# Tests contrat /api/admin/status
# ============================================================================

class TestAdminStatusContract:
    """Tests de contrat pour GET /api/admin/status."""

    def test_returns_401_without_session(self, client):
        """Sans session admin, l'endpoint doit retourner 401."""
        response = client.get("/api/admin/status")
        assert response.status_code == 401

    def test_all_required_fields_present(self, admin_client):
        """Tous les champs attendus par le frontend admin doivent etre presents."""
        response = admin_client.get("/api/admin/status")
        assert response.status_code == 200

        data = response.get_json()
        missing = REQUIRED_ADMIN_STATUS_FIELDS - set(data.keys())
        assert not missing, (
            f"Champs manquants dans /api/admin/status: {sorted(missing)}\n"
            f"Champs presents: {sorted(data.keys())}"
        )

    def test_services_is_dict(self, admin_client):
        """Verifie que services est un dict."""
        response = admin_client.get("/api/admin/status")
        data = response.get_json()

        assert isinstance(data["services"], dict)

    def test_vram_is_dict(self, admin_client):
        """Verifie que vram est un dict avec enabled."""
        response = admin_client.get("/api/admin/status")
        data = response.get_json()

        assert isinstance(data["vram"], dict)
        assert "enabled" in data["vram"]

    def test_service_order_and_names_consistent(self, admin_client):
        """Verifie que service_order et service_names sont coherents."""
        response = admin_client.get("/api/admin/status")
        data = response.get_json()

        assert isinstance(data["service_order"], list)
        assert isinstance(data["service_names"], dict)
        for key in data["service_order"]:
            assert key in data["service_names"]


# ============================================================================
# Tests routes principales
# ============================================================================

class TestMainRoutes:
    """Tests pour les routes principales (HTML)."""

    def test_index_returns_html(self, client):
        """GET / doit retourner du HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.content_type

    def test_index_contains_dashboard(self, client):
        """La page d'accueil doit contenir le titre du dashboard."""
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert "Dashboard" in html or "dashboard" in html.lower()

    def test_help_returns_html(self, client):
        """GET /help doit retourner du HTML."""
        response = client.get("/help")
        assert response.status_code == 200
        assert "text/html" in response.content_type

    def test_admin_redirects_to_login(self, client):
        """GET /admin sans session doit rediriger vers login (ou afficher la page)."""
        response = client.get("/admin", follow_redirects=False)
        # Soit 302 redirect, soit 200 (login page)
        assert response.status_code in (200, 302)

    def test_admin_panel_redirects_to_login(self, client):
        """GET /admin/panel sans session doit rediriger vers login."""
        response = client.get("/admin/panel", follow_redirects=False)
        assert response.status_code in (302, 200)


# ============================================================================
# Tests securite basiques
# ============================================================================

class TestSecurityBasics:
    """Tests de securite basiques."""

    def test_admin_api_status_requires_auth(self, client):
        """L'API admin doit exiger une authentification."""
        response = client.get("/api/admin/status")
        assert response.status_code == 401

    def test_admin_api_start_requires_auth(self, client):
        """POST /api/admin/start doit exiger une authentification."""
        response = client.post("/api/admin/start",
                               data=json.dumps({"service": "test"}),
                               content_type="application/json")
        assert response.status_code == 401

    def test_admin_api_stop_requires_auth(self, client):
        """POST /api/admin/stop doit exiger une authentification."""
        response = client.post("/api/admin/stop",
                               data=json.dumps({"service": "test"}),
                               content_type="application/json")
        assert response.status_code == 401

    def test_admin_api_force_stop_requires_auth(self, client):
        """POST /api/admin/force_stop doit exiger une authentification."""
        response = client.post("/api/admin/force_stop",
                               data=json.dumps({"service": "test"}),
                               content_type="application/json")
        assert response.status_code == 401

    def test_no_sensitive_data_in_health(self, client):
        """L'endpoint /health ne doit pas exposer de donnees sensibles."""
        response = client.get("/health")
        data = response.get_json()

        sensitive_keys = {"password", "secret", "key", "token", "hash", "config"}
        for key in data:
            assert key not in sensitive_keys, \
                f"/health exposes sensitive key: {key}"


# ============================================================================
# Tests de non-regression : appels destructifs
# ============================================================================

class TestDestructiveCommandProtection:
    """Verifie que les commandes destructives sont protegees."""

    def test_stop_all_llm_requires_auth(self, client):
        """POST /api/admin/stop_all_llm doit exiger une authentification."""
        response = client.post("/api/admin/stop_all_llm",
                               content_type="application/json")
        assert response.status_code == 401

    def test_restart_requires_auth(self, client):
        """POST /api/admin/restart doit exiger une authentification."""
        response = client.post("/api/admin/restart",
                               data=json.dumps({"service": "test"}),
                               content_type="application/json")
        assert response.status_code == 401


# ============================================================================
# Test direct get_services_status (detecte les erreurs de signature)
# ============================================================================

class TestGetServicesStatusDirect:
    """Tests directs sur get_services_status() — verifie qu'elle ne leve pas d'exception."""

    def test_returns_dict_with_expected_keys(self, client):
        """get_services_status() doit retourner un dict avec les cles attendues."""
        from monitor import get_services_status
        result = get_services_status()
        assert isinstance(result, dict)
        assert "services" in result
        assert "active_on_8080" in result
        assert "model_on_8080" in result

    def test_services_dict_has_valid_statuses(self, client):
        """Chaque service doit avoir un statut valide."""
        from monitor import get_services_status
        result = get_services_status()
        valid = {"UP", "DOWN", "SLOW", "LOADING", "UNRESPONSIVE"}
        for svc_name, status in result["services"].items():
            assert status in valid, f"Invalid status '{status}' for '{svc_name}'"

    def test_does_not_raise(self, client):
        """get_services_status() ne doit lever aucune exception."""
        from monitor import get_services_status
        try:
            result = get_services_status()
            assert isinstance(result, dict)
        except Exception as e:
            pytest.fail(f"get_services_status() raised {type(e).__name__}: {e}")
