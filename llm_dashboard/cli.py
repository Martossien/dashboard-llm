"""CLI entry point for llm-dashboard."""

import logging


def main():
    """Launch the dashboard."""
    from llm_dashboard.app_factory import create_full_app

    app, config = create_full_app()

    logger = logging.getLogger("dashboard-llm")
    if config["server"].get("debug"):
        logger.warning(
            "DEBUG MODE ENABLED — Werkzeug debugger allows arbitrary code "
            "execution. Never use in production!"
        )
    app.run(
        host=config["server"]["host"],
        port=config["server"]["port"],
        debug=config["server"].get("debug", False),
        use_reloader=False,
    )


if __name__ == "__main__":
    main()
