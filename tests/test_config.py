"""
Tests de caracterisation — Configuration.

Teste le chargement, la validation et les overrides d'environnement.
Ces tests utilisent des fichiers YAML temporaires, pas de config reelle.
"""

import os
import json
import pytest


# ============================================================================
# Test : chargement de config YAML
# ============================================================================

class TestLoadConfig:
    """Tests pour load_config()."""

    def test_returns_defaults_when_no_config_file(self, monkeypatch):
        """Sans fichier de config, load_config retourne les defaults."""
        monkeypatch.setenv("DASHBOARD_CONFIG", "/nonexistent/path/config.yaml")
        # Forcer os.path.exists a retourner False (fichier inexistant)
        monkeypatch.setattr(os.path, "exists", lambda path: False)

        from monitor import load_config
        config = load_config()

        # Verifier les valeurs par defaut
        assert config["server"]["port"] == 5000
        assert config["server"]["host"] == "0.0.0.0"
        assert config["monitoring"]["refresh_interval_ms"] == 1000
        assert config["gpu"]["enable"] is True
        assert "ik_llama_cpp" in config["services"]
        assert "ollama" in config["services"]

    def test_loads_yaml_config(self, temp_config_file, monkeypatch):
        """Charge une config depuis un fichier YAML via load_config()."""
        from monitor import load_config

        # Forcer load_config a utiliser le fichier temporaire
        monkeypatch.setenv("DASHBOARD_CONFIG", temp_config_file)
        # Retablir os.path.exists pour ce fichier specifique (mocke par test_app)
        monkeypatch.setattr(os.path, "exists", lambda p: p == temp_config_file)

        config = load_config()

        assert isinstance(config, dict)
        assert "services" in config
        assert "server" in config
        assert config["server"]["port"] == 5050

    def test_env_override(self, monkeypatch):
        """Les variables d'environnement surchargent la config."""
        monkeypatch.setenv("DASHBOARD_CONFIG", "/nonexistent/path/config.yaml")
        monkeypatch.setenv("DASHBOARD_HOST", "192.168.1.1")
        monkeypatch.setenv("DASHBOARD_PORT", "9090")
        monkeypatch.setattr(os.path, "exists", lambda path: False)

        from monitor import load_config
        config = load_config()

        assert config["server"]["host"] == "192.168.1.1"
        assert config["server"]["port"] == 9090

    def test_env_override_bool(self, monkeypatch):
        """Les variables booleennes sont parsees correctement."""
        monkeypatch.setenv("DASHBOARD_CONFIG", "/nonexistent/path/config.yaml")
        monkeypatch.setenv("DASHBOARD_DEBUG", "true")
        monkeypatch.setenv("DASHBOARD_GPU_ENABLE", "false")
        monkeypatch.setattr(os.path, "exists", lambda path: False)

        from monitor import load_config
        config = load_config()

        assert config["server"]["debug"] is True
        assert config["gpu"]["enable"] is False

    def test_env_override_list(self, monkeypatch):
        """Les variables liste sont parsees correctement."""
        monkeypatch.setenv("DASHBOARD_CONFIG", "/nonexistent/path/config.yaml")
        monkeypatch.setenv("DASHBOARD_MODEL_PROCESS_KEYWORDS", "llama,vllm,ik_llama")
        monkeypatch.setattr(os.path, "exists", lambda path: False)

        from monitor import load_config
        config = load_config()

        assert config["model_detection"]["process_keywords"] == ["llama", "vllm", "ik_llama"]


# ============================================================================
# Test : validation de config
# ============================================================================

class TestValidateConfig:
    """Tests pour validate_config()."""

    def test_valid_config_passes(self, monkeypatch):
        """Une config valide ne doit pas etre modifiee (ou seulement pour les defauts)."""
        from monitor import validate_config
        from monitor import DEFAULT_CONFIG
        from copy import deepcopy

        config = deepcopy(DEFAULT_CONFIG)
        # Rendre la config valide explicitement
        config["server"]["port"] = 5000
        config["monitoring"]["refresh_interval_ms"] = 1000

        validate_config(config)

        # Les valeurs valides ne doivent pas etre changees
        assert config["server"]["port"] == 5000

    def test_invalid_port_replaced(self):
        """Un port invalide est remplace par le defaut."""
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy

        config = deepcopy(DEFAULT_CONFIG)
        config["server"]["port"] = -1  # invalide

        validate_config(config)

        assert config["server"]["port"] == DEFAULT_CONFIG["server"]["port"]

    def test_out_of_range_refresh_interval(self):
        """Un refresh_interval_ms hors limites est remplace."""
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy

        config = deepcopy(DEFAULT_CONFIG)
        config["monitoring"]["refresh_interval_ms"] = 99999  # > 60000

        validate_config(config)

        assert config["monitoring"]["refresh_interval_ms"] == DEFAULT_CONFIG["monitoring"]["refresh_interval_ms"]

    def test_invalid_url_replaced(self):
        """Une URL invalide est remplacee."""
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy

        config = deepcopy(DEFAULT_CONFIG)
        config["services"]["ollama"]["base_url"] = "ftp://invalid"

        validate_config(config)

        assert config["services"]["ollama"]["base_url"] == DEFAULT_CONFIG["services"]["ollama"]["base_url"]

    def test_invalid_endpoint_replaced(self):
        """Un health_endpoint sans / est remplace."""
        from monitor import validate_config, DEFAULT_CONFIG
        from copy import deepcopy

        config = deepcopy(DEFAULT_CONFIG)
        config["services"]["ollama"]["health_endpoint"] = "health"

        validate_config(config)

        assert config["services"]["ollama"]["health_endpoint"] == DEFAULT_CONFIG["services"]["ollama"]["health_endpoint"]


# ============================================================================
# Test : exemple de normalisation (preparation Phase 2)
# ============================================================================

class TestConfigNormalization:
    """Tests preparatoires pour la normalisation services + start_stop -> ServiceConfig."""

    def test_services_keys_are_present(self, minimal_config_dict):
        """Verifie que la config minimale a les cles services et start_stop."""
        assert "services" in minimal_config_dict
        assert "start_stop" in minimal_config_dict

    def test_port_8080_is_shared(self, minimal_config_dict):
        """Verifie que les services LLM partagent le port 8080."""
        llm_services = [
            k for k, v in minimal_config_dict["services"].items()
            if "8080" in v.get("base_url", "")
        ]
        assert len(llm_services) >= 2, f"Expected at least 2 services on port 8080, got {llm_services}"

    def test_start_stop_has_required_fields(self, minimal_config_dict):
        """Verifie que chaque entree start_stop a les champs requis."""
        required_fields = {"display_name", "port", "is_llm"}
        for key, svc in minimal_config_dict["start_stop"].items():
            missing = required_fields - set(svc.keys())
            assert not missing, f"start_stop.{key} missing fields: {missing}"

    def test_llm_services_have_systemd_unit(self, minimal_config_dict):
        """Verifie que les LLMs ont un systemd_unit (sauf si non applicable)."""
        for key, svc in minimal_config_dict["start_stop"].items():
            if svc.get("is_llm"):
                # Au moins un des deux : systemd_unit, start_command, ou raw_start
                has_control = (
                    svc.get("systemd_unit") or
                    svc.get("start_command") or
                    svc.get("raw_start")
                )
                assert has_control, f"LLM {key} has no control mechanism"


# ============================================================================
# Test : exemple YAML valide
# ============================================================================

class TestExampleConfig:
    """Verifie que config.example.yaml est chargeable sans erreur."""

    def test_example_yaml_loads(self):
        """Le fichier config.example.yaml doit etre un YAML valide."""
        import yaml

        example_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config.example.yaml"
        )

        if not os.path.exists(example_path):
            pytest.skip("config.example.yaml not found")

        with open(example_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict), "config.example.yaml should be a YAML mapping"
        assert "services" in data, "config.example.yaml should have services section"
        assert "server" in data, "config.example.yaml should have server section"

    def test_example_yaml_has_no_hardcoded_secrets(self):
        """Le fichier exemple ne doit pas contenir de secrets en dur."""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config.example.yaml"
        )

        if not os.path.exists(example_path):
            pytest.skip("config.example.yaml not found")

        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Pas de mot de passe en clair
        assert "Cpam80_" not in content, \
            "config.example.yaml should not contain hardcoded passwords"

    def test_current_config_is_valid_yaml(self):
        """Le config.yaml actuel doit etre chargeable."""
        import yaml

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config.yaml"
        )

        if not os.path.exists(config_path):
            pytest.skip("config.yaml not found (dev workspace)")

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict)
        assert "services" in data
        assert "start_stop" in data
