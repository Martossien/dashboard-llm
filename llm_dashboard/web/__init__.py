"""Web layer — routes Flask."""
from llm_dashboard.web.admin_api import AdminAPIRoutes
from llm_dashboard.web.admin_auth import AdminAuthRoutes
from llm_dashboard.web.admin_panel import AdminPanelRoute
from llm_dashboard.web.app import create_app
from llm_dashboard.web.config_api import create_config_api
from llm_dashboard.web.config_panel import ConfigPanelRoute
from llm_dashboard.web.dashboard_api import DashboardAPIRoute
from llm_dashboard.web.metrics import create_metrics_endpoint, register_public_api
from llm_dashboard.web.routes import WebRoutes

__all__ = [
    "AdminAPIRoutes",
    "AdminAuthRoutes",
    "AdminPanelRoute",
    "ConfigPanelRoute",
    "DashboardAPIRoute",
    "WebRoutes",
    "create_app",
    "create_config_api",
    "create_metrics_endpoint",
    "register_public_api",
]
