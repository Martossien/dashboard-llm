"""
Tests d'integration — demarrent la vraie app Flask avec test_client()
et verifient que tout le cablage (partials, routes, config) fonctionne.

Ces tests completent les tests unitaires mockes.
"""

import json

import pytest


class TestAppFactory:
    """Tests utilisant create_full_app() — le chemin du CLI (Lot 24)."""

    def test_create_full_app_returns_app_and_config(self):
        from llm_dashboard.app_factory import create_full_app
        from flask import Flask

        app, config = create_full_app()
        assert isinstance(app, Flask)
        assert isinstance(config, dict)
        assert "server" in config

    def test_app_from_factory_serves_health(self):
        from llm_dashboard.app_factory import create_full_app

        app, _config = create_full_app()

        with app.test_client() as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ok"
            assert data["service"] == "dashboard-llm"

    def test_app_from_factory_serves_api_data(self):
        from llm_dashboard.app_factory import create_full_app

        app, _config = create_full_app()

        with app.test_client() as client:
            response = client.get("/api/data")
            assert response.status_code == 200
            data = response.get_json()

            assert isinstance(data, dict)
            assert "cpu" in data
            assert "ram" in data
            assert "gpus" in data
            assert "services" in data


class TestApiDataCompleteContract:
    """Verification que /api/data contient tous les champs des Lots 21-24."""

    def test_contains_lot21_23_fields(self, client):
        response = client.get("/api/data")
        assert response.status_code == 200
        data = response.get_json()

        assert "ollama_models" in data, "Lot 23: ollama_models missing"
        assert isinstance(data["ollama_models"], list), \
            "ollama_models should be a list"

        assert "llama_metrics" in data, "Lot 23: llama_metrics missing"
        assert isinstance(data["llama_metrics"], dict), \
            "llama_metrics should be a dict"

    def test_ollama_models_is_empty_when_down(self, client):
        response = client.get("/api/data")
        data = response.get_json()
        assert data["ollama_models"] == []

    def test_llama_metrics_is_empty_when_down(self, client):
        response = client.get("/api/data")
        data = response.get_json()
        assert data["llama_metrics"] == {}

    def test_contains_all_legacy_fields(self, client):
        response = client.get("/api/data")
        assert response.status_code == 200
        data = response.get_json()

        legacy_fields = {
            "cpu", "ram", "gpus", "services", "slots_active",
            "slots_total", "service_logs", "service_order", "service_names",
            "model_name", "prompt_tokens_per_second", "generation_tokens_per_second",
            "vllm_prompt_tokens_per_second", "vllm_generation_tokens_per_second",
            "client_ips", "llama_service_name", "ik_llama_service_name",
            "vllm_service_name", "active_llama_service_name",
            "active_llm_service_name", "llama_state",
            "llama_loading_seconds", "llama_eta_seconds", "llama_avg_load_seconds",
            "active_on_8080", "model_on_8080",
        }
        missing = legacy_fields - set(data)
        assert not missing, f"Legacy fields missing: {sorted(missing)}"

    def test_services_not_empty(self, client):
        response = client.get("/api/data")
        data = response.get_json()
        assert isinstance(data["services"], dict)
        assert len(data["services"]) >= 5, \
            f"Expected >= 5 services, got {len(data['services'])}"

    def test_service_order_matches_service_names_keys(self, client):
        response = client.get("/api/data")
        data = response.get_json()

        for key in data["service_order"]:
            assert key in data["service_names"], \
                f"Key '{key}' in service_order but not in service_names"


class TestAdminIntegration:
    """Tests d'integration admin panel avec authentification."""

    def test_admin_status_contains_expected_shape(self, admin_client):
        response = admin_client.get("/api/admin/status")
        assert response.status_code == 200
        data = response.get_json()

        assert "services" in data
        assert "vram" in data
        assert "service_logs" in data
        assert "service_order" in data
        assert "service_names" in data

        assert isinstance(data["vram"], dict)
        assert "enabled" in data["vram"]

    def test_admin_api_protected_without_session(self, client):
        endpoints = [
            ("GET", "/api/admin/status"),
            ("GET", "/api/admin/vram"),
            ("POST", "/api/admin/start"),
            ("POST", "/api/admin/stop"),
            ("POST", "/api/admin/restart"),
            ("POST", "/api/admin/force_stop"),
            ("POST", "/api/admin/stop_all_llm"),
        ]
        for method, url in endpoints:
            if method == "GET":
                response = client.get(url)
            else:
                response = client.post(
                    url,
                    data=json.dumps({"service": "svc_a"}),
                    content_type="application/json",
                )
            assert response.status_code == 401, \
                f"{method} {url} returned {response.status_code}, expected 401"

    def test_health_does_not_expose_secrets(self, client):
        response = client.get("/health")
        data = response.get_json()

        sensitive = {"password", "secret", "key", "token", "hash", "config"}
        found = [k for k in data if k in sensitive or any(s in k for s in sensitive)]
        assert not found, f"Secrets exposed in /health: {found}"


class TestPublicApiIntegration:
    """Tests d'integration pour /metrics et /api/v1/*."""

    def test_metrics_endpoint_returns_prometheus(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        assert response.mimetype == "text/plain"

        text = response.data.decode("utf-8")
        assert "# HELP cpu_load_percent" in text
        assert "cpu_load_percent" in text

    def test_api_v1_gpus_returns_list(self, client):
        response = client.get("/api/v1/gpus")
        assert response.status_code == 200
        data = response.get_json()
        assert "gpus" in data
        assert isinstance(data["gpus"], list)

    def test_api_v1_services_returns_dict(self, client):
        response = client.get("/api/v1/services")
        assert response.status_code == 200
        data = response.get_json()
        assert "services" in data
        assert "active_services_by_group" in data

    def test_api_v1_metrics_returns_dict(self, client):
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.get_json()
        assert "cpu" in data


class TestHtmlPagesIntegration:
    """Tests d'integration sur les pages HTML."""

    def test_index_returns_200_and_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.content_type

    def test_help_returns_200(self, client):
        response = client.get("/help")
        assert response.status_code == 200

    def test_admin_login_page_accessible(self, client):
        response = client.get("/admin")
        assert response.status_code in (200, 302)

    def test_templates_reference_static_assets(self, client):
        response = client.get("/")
        html = response.data.decode("utf-8")

        assert "url_for('static'" in html or '"/static/' in html or "'/static/" in html, \
            "Root page should reference static assets"

    def test_static_css_served(self, client):
        for path in ("/static/css/dashboard.css", "/static/css/admin.css"):
            response = client.get(path)
            assert response.status_code == 200, \
                f"{path} returned {response.status_code}"

    def test_static_js_served(self, client):
        for path in ("/static/js/dashboard.js", "/static/js/admin.js"):
            response = client.get(path)
            assert response.status_code == 200, \
                f"{path} returned {response.status_code}"
