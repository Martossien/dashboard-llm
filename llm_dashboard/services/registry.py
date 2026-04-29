"""
ServiceRegistry — Index central des services (pur, sans I/O).

Le registry est la source unique de verite pour tous les modules :
- API dashboard (/api/data)
- API admin (/api/admin/status)
- Detection de modele actif
- Controle admin (start/stop)

Il NE fait AUCUN appel reseau, subprocess, psutil ou pynvml.
Ces responsabilites sont deleguees a ServiceDetector, ServiceHealthChecker
et ServiceController (lots suivants).

Utilisation :
    from llm_dashboard.models import normalize_services_config
    from llm_dashboard.services.registry import ServiceRegistry

    config = load_config()
    services = normalize_services_config(config)
    registry = ServiceRegistry(services)

    for svc in registry.by_group("llm_8080"):
        print(svc.display_name)
"""

from __future__ import annotations

from typing import Optional

from llm_dashboard.models import ServiceConfig


class ServiceRegistry:
    """Index immuable des services.

    Construit une fois au demarrage a partir de la configuration normalisee.
    Les requetes sont en O(1) grace aux index internes.

    Les statuts dynamiques (UP/DOWN, latence, modele actif) ne sont PAS
    stockes ici. Ils sont geres par ServiceHealthChecker et ServiceDetector.
    """

    def __init__(self, services: Optional[list[ServiceConfig]] = None) -> None:
        """Initialise le registry avec une liste de ServiceConfig.

        Args:
            services: liste de ServiceConfig (issue de normalize_services_config()).
                      Si None, le registry est vide.
        """
        self._services: dict[str, ServiceConfig] = {}
        self._by_role: dict[str, list[ServiceConfig]] = {}
        self._by_group: dict[str, list[ServiceConfig]] = {}

        if services:
            for svc in services:
                self._validate(svc)
                self._index(svc)

    # ---- Methodes de consultation ----

    def all(self) -> list[ServiceConfig]:
        """Tous les services enregistres, dans l'ordre d'insertion."""
        return list(self._services.values())

    def get(self, key: str) -> Optional[ServiceConfig]:
        """Retourne un service par sa cle, ou None."""
        return self._services.get(key)

    def by_role(self, role: str) -> list[ServiceConfig]:
        """Services filtres par role ('llm', 'auxiliary', 'dashboard')."""
        return list(self._by_role.get(role, []))

    def by_group(self, group: str) -> list[ServiceConfig]:
        """Services appartenant a un groupe exclusif (ex: 'llm_8080')."""
        return list(self._by_group.get(group, []))

    def monitorable(self) -> list[ServiceConfig]:
        """Services qui peuvent etre monitorés (health check + logs).

        Actuellement : tous les services sont monitorables.
        Futur : on pourrait exclure les services avec log_source='none'.
        """
        return self.all()

    def controllable(self) -> list[ServiceConfig]:
        """Services qui peuvent etre administrés (start/stop).

        Critere : avoir un systemd_unit OU un start_command.
        """
        return [
            svc for svc in self.all()
            if svc.systemd_unit or svc.start_command
        ]

    # ---- Methodes derivees — remplacent les anciennes fonctions eparpillees ----

    def llm_services(self) -> list[ServiceConfig]:
        """Services de type LLM uniquement."""
        return self.by_role("llm")

    def auxiliary_services(self) -> list[ServiceConfig]:
        """Services auxiliaires (non-LLM)."""
        return self.by_role("auxiliary")

    def groups(self) -> list[str]:
        """Liste des groupes exclusifs definis."""
        return list(self._by_group.keys())

    def count(self) -> int:
        """Nombre total de services."""
        return len(self._services)

    # ---- Methodes internes ----

    def _validate(self, svc: ServiceConfig) -> None:
        """Valide les invariants d'un ServiceConfig.

        Leve ValueError si un invariant est viole.
        """
        if not svc.key:
            raise ValueError("ServiceConfig.key must not be empty")
        if not svc.display_name:
            raise ValueError(f"ServiceConfig.display_name must not be empty (key={svc.key})")
        if svc.role not in ("llm", "auxiliary", "dashboard"):
            raise ValueError(
                f"ServiceConfig.role must be 'llm', 'auxiliary' or 'dashboard', "
                f"got '{svc.role}' (key={svc.key})"
            )
        if not svc.backend:
            raise ValueError(f"ServiceConfig.backend must not be empty (key={svc.key})")
        if svc.timeout_seconds <= 0:
            raise ValueError(
                f"ServiceConfig.timeout_seconds must be > 0, "
                f"got {svc.timeout_seconds} (key={svc.key})"
            )
        if svc.port is not None and not (1 <= svc.port <= 65535):
            raise ValueError(
                f"ServiceConfig.port must be between 1 and 65535, "
                f"got {svc.port} (key={svc.key})"
            )
        if svc.exclusive_group and svc.port is None:
            raise ValueError(
                f"ServiceConfig with exclusive_group must have a port "
                f"(key={svc.key}, group={svc.exclusive_group})"
            )

    def _index(self, svc: ServiceConfig) -> None:
        """Indexe un ServiceConfig dans les dictionnaires internes."""
        if svc.key in self._services:
            raise ValueError(f"Duplicate service key: {svc.key}")

        self._services[svc.key] = svc
        self._by_role.setdefault(svc.role, []).append(svc)

        if svc.exclusive_group:
            self._by_group.setdefault(svc.exclusive_group, []).append(svc)

    def __repr__(self) -> str:
        return f"<ServiceRegistry: {self.count()} services, {len(self.groups())} groups>"

    def __len__(self) -> int:
        return self.count()

    def __contains__(self, key: str) -> bool:
        return key in self._services

    def __iter__(self):
        return iter(self._services.values())
