"""
Tests unitaires pour ServiceRegistry.

Ces tests sont independants de Flask, du reseau et du GPU.
Ils testent uniquement l'indexation et les requetes du registry.
"""

import pytest
from llm_dashboard.models import ServiceConfig
from llm_dashboard.services.registry import ServiceRegistry


# ============================================================================
# Fixtures de test
# ============================================================================

def _make_svc(key, **kwargs):
    """Helper: cree un ServiceConfig avec des defaults de test."""
    defaults = {
        "key": key,
        "display_name": key.replace("_", " ").title(),
        "backend": "llama.cpp",
        "role": "llm",
        "port": 8080,
        "base_url": f"http://127.0.0.1:8080",
        "health_endpoint": "/health",
        "exclusive_group": "llm_8080",
        "systemd_unit": f"{key}.service",
        "start_command": ("systemctl", "start", f"{key}.service"),
        "stop_command": ("systemctl", "stop", f"{key}.service"),
    }
    defaults.update(kwargs)
    return ServiceConfig(**defaults)


@pytest.fixture
def sample_services():
    """7 services realistes (comme la config actuelle)."""
    return [
        _make_svc("glm47", backend="ik_llama.cpp", display_name="GLM-4.7"),
        _make_svc("qwen36_35b_q8", backend="llama.cpp", display_name="Qwen 35B Q8"),
        _make_svc("qwen36_35b_udq8", backend="llama.cpp", display_name="Qwen 35B UD-Q8"),
        _make_svc("qwen36_27b_vllm", backend="vllm", display_name="Qwen 27B vLLM"),
        _make_svc("ollama", backend="ollama", role="llm", port=11434, exclusive_group=None,
                  systemd_unit="ollama.service",
                  start_command=("systemctl", "start", "ollama.service"),
                  stop_command=("systemctl", "stop", "ollama.service")),
        _make_svc("voxtral_tts", backend="gradio", role="auxiliary", port=6060, exclusive_group=None,
                  systemd_unit="voxtral-web.service"),
        _make_svc("voxtral_stt", backend="gradio", role="auxiliary", port=7860, exclusive_group=None,
                  systemd_unit="voxtral-webui.service"),
    ]


@pytest.fixture
def registry(sample_services):
    """Registry avec 7 services."""
    return ServiceRegistry(sample_services)


# ============================================================================
# Tests : construction
# ============================================================================

class TestRegistryConstruction:
    """Tests de construction du ServiceRegistry."""

    def test_empty_registry(self):
        """Un registry vide est valide."""
        reg = ServiceRegistry()
        assert reg.count() == 0
        assert reg.all() == []

    def test_empty_list(self):
        """Une liste vide est acceptee."""
        reg = ServiceRegistry([])
        assert reg.count() == 0

    def test_count(self, registry):
        """7 services attendus."""
        assert registry.count() == 7

    def test_duplicate_key_raises(self):
        """Deux services avec la meme cle levent ValueError."""
        svc1 = _make_svc("test")
        svc2 = _make_svc("test")
        with pytest.raises(ValueError, match="Duplicate service key"):
            ServiceRegistry([svc1, svc2])

    def test_invalid_role_raises(self):
        """Un role invalide leve ValueError."""
        svc = _make_svc("test", role="invalid_role")
        with pytest.raises(ValueError, match="role must be"):
            ServiceRegistry([svc])

    def test_empty_key_raises(self):
        """Une cle vide leve ValueError."""
        svc = _make_svc(key="")  # key est force a ""
        with pytest.raises(ValueError, match="key must not be empty"):
            ServiceRegistry([svc])

    def test_negative_timeout_raises(self):
        """Un timeout negatif leve ValueError."""
        svc = _make_svc("test", timeout_seconds=-1)
        with pytest.raises(ValueError, match="timeout_seconds must be > 0"):
            ServiceRegistry([svc])

    def test_invalid_port_raises(self):
        """Un port hors limites leve ValueError."""
        svc = _make_svc("test", port=99999)
        with pytest.raises(ValueError, match="port must be between"):
            ServiceRegistry([svc])

    def test_exclusive_group_without_port_raises(self):
        """Un groupe exclusif sans port leve ValueError."""
        svc = _make_svc("test", exclusive_group="grp", port=None)
        with pytest.raises(ValueError, match="exclusive_group must have a port"):
            ServiceRegistry([svc])


# ============================================================================
# Tests : requetes
# ============================================================================

class TestRegistryQueries:
    """Tests des methodes de consultation."""

    def test_all_returns_all(self, registry):
        """all() retourne les 7 services."""
        assert len(registry.all()) == 7

    def test_get_existing(self, registry):
        """get() retourne le bon service."""
        svc = registry.get("glm47")
        assert svc is not None
        assert svc.key == "glm47"
        assert svc.backend == "ik_llama.cpp"

    def test_get_missing(self, registry):
        """get() retourne None pour une cle inconnue."""
        assert registry.get("nonexistent") is None

    def test_contains(self, registry):
        """L'operateur in fonctionne."""
        assert "glm47" in registry
        assert "nonexistent" not in registry

    def test_by_role_llm(self, registry):
        """by_role('llm') retourne 5 services."""
        llms = registry.by_role("llm")
        assert len(llms) == 5
        for svc in llms:
            assert svc.role == "llm"

    def test_by_role_auxiliary(self, registry):
        """by_role('auxiliary') retourne 2 services."""
        aux = registry.by_role("auxiliary")
        assert len(aux) == 2
        for svc in aux:
            assert svc.role == "auxiliary"

    def test_by_group(self, registry):
        """by_group('llm_8080') retourne les 4 LLM sur port 8080."""
        llm8080 = registry.by_group("llm_8080")
        assert len(llm8080) == 4
        keys = {svc.key for svc in llm8080}
        assert keys == {"glm47", "qwen36_35b_q8", "qwen36_35b_udq8", "qwen36_27b_vllm"}

    def test_llm_services(self, registry):
        """llm_services() est un alias de by_role('llm')."""
        assert len(registry.llm_services()) == 5
        assert registry.llm_services() == registry.by_role("llm")

    def test_auxiliary_services(self, registry):
        """auxiliary_services() est un alias de by_role('auxiliary')."""
        assert len(registry.auxiliary_services()) == 2

    def test_monitorable(self, registry):
        """monitorable() retourne tous les services."""
        assert len(registry.monitorable()) == 7

    def test_controllable(self, registry):
        """controllable() retourne les services avec systemd_unit ou start_command."""
        controllable = registry.controllable()
        assert len(controllable) == 7  # tous ont un systemd_unit dans nos fixtures

    def test_controllable_excludes_without_commands(self):
        """Un service sans start_command ni systemd_unit n'est pas controllable."""
        svc = _make_svc("no_ctrl", systemd_unit=None, start_command=(), stop_command=())
        reg = ServiceRegistry([svc])
        assert len(reg.controllable()) == 0

    def test_iteration(self, registry):
        """L'iteration fonctionne."""
        keys = [svc.key for svc in registry]
        assert len(keys) == 7
        assert "glm47" in keys

    def test_len(self, registry):
        """len(registry) fonctionne."""
        assert len(registry) == 7

    def test_repr(self, registry):
        """repr() est informatif."""
        r = repr(registry)
        assert "ServiceRegistry" in r
        assert "7 services" in r


# ============================================================================
# Tests : proprietes des services
# ============================================================================

class TestServiceProperties:
    """Tests des proprietes des ServiceConfig apres normalisation."""

    def test_llm_services_have_exclusive_group(self, registry):
        """Les LLM sur port 8080 ont exclusive_group='llm_8080'."""
        for svc in registry.by_group("llm_8080"):
            assert svc.exclusive_group == "llm_8080"
            assert svc.port == 8080

    def test_ollama_not_in_llm_8080(self, registry):
        """Ollama n'est PAS dans le groupe llm_8080."""
        ollama = registry.get("ollama")
        assert ollama is not None
        assert ollama.port == 11434
        assert ollama.exclusive_group is None

    def test_auxiliary_not_in_any_group(self, registry):
        """Les auxiliaires n'ont pas de groupe exclusif."""
        for svc in registry.by_role("auxiliary"):
            assert svc.exclusive_group is None

    def test_frozen_services(self, registry):
        """ServiceConfig est frozen — impossible de modifier."""
        svc = registry.get("glm47")
        with pytest.raises(Exception):  # FrozenInstanceError ou dataclass error
            svc.display_name = "hacked"

    def test_match_patterns_from_normalized_config(self, minimal_config_dict):
        """Les services normalises depuis la config ont des model_detect_pattern."""
        from llm_dashboard.models import normalize_services_config
        services = normalize_services_config(minimal_config_dict)
        registry = ServiceRegistry(services)

        for svc in registry.by_group("llm_8080"):
            assert svc.model_detect_pattern is not None, \
                f"{svc.key} should have model_detect_pattern when normalized from config"

    def test_start_command_is_tuple(self, registry):
        """start_command est bien un tuple (pas une liste mutable)."""
        for svc in registry.all():
            if svc.start_command:
                assert isinstance(svc.start_command, tuple), \
                    f"{svc.key}.start_command should be tuple, got {type(svc.start_command)}"


# ============================================================================
# Tests : integration avec normalize_services_config
# ============================================================================

class TestNormalizeIntegration:
    """Tests d'integration entre normalize_services_config et ServiceRegistry."""

    def test_full_config_roundtrip(self):
        """La config actuelle peut etre normalisee et indexee sans erreur."""
        import yaml
        import os

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config.yaml"
        )

        if not os.path.exists(config_path):
            pytest.skip("config.yaml not found (dev workspace)")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        from llm_dashboard.models import normalize_services_config
        services = normalize_services_config(config)
        registry = ServiceRegistry(services)

        assert registry.count() == len(config.get("services", {}))
        llm_groups = [g for g in registry.groups() if "llm" in g]
        assert len(llm_groups) >= 1
        assert registry.get("ollama") is not None

    def test_minimal_config_normalizes(self, minimal_config_dict):
        """La config minimale de test se normalise correctement."""
        from llm_dashboard.models import normalize_services_config
        services = normalize_services_config(minimal_config_dict)
        registry = ServiceRegistry(services)

        assert registry.count() == len(minimal_config_dict.get("services", {}))
        assert registry.get("ik_llama_cpp") is not None


# ============================================================================
# Tests : groupes exclusifs (logique metier a venir)
# ============================================================================

class TestExclusiveGroups:
    """Tests de la logique de groupes exclusifs (preparation Lot 3+)."""

    def test_group_members_all_llm(self, registry):
        """Tous les membres d'un groupe exclusif sont des LLM."""
        for svc in registry.by_group("llm_8080"):
            assert svc.role == "llm"

    def test_group_members_same_port(self, registry):
        """Tous les membres d'un groupe exclusif partagent le meme port."""
        ports = {svc.port for svc in registry.by_group("llm_8080")}
        assert ports == {8080}

    def test_no_service_in_multiple_groups(self):
        """Un service ne peut pas appartenir a plusieurs groupes (garanti par l'indexation)."""
        # Ce test verifie que l'indexation par cle est unique.
        # Creer un service et verifier qu'il n'est compte qu'une fois.
        svc = _make_svc("test")
        reg = ServiceRegistry([svc])
        assert reg.count() == 1
        assert len(reg.by_group("llm_8080")) == 1
