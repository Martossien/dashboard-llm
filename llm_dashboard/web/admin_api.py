"""
Admin API routes — /api/admin/status, start, stop, restart, force_stop, stop_all_llm, vram.

Pas d'import depuis monitor.py.
"""

import logging
import time

from flask import jsonify, request


class AdminAPIRoutes:
    """Routes API d'administration (/api/admin/*)."""

    def __init__(self, config, admin_login_required,
                 get_admin_services_status, get_vram_status, get_logs,
                 do_start_service, do_stop_service, stop_all_llm_engines,
                 _init_controller,
                 _control_result_to_dict, logger=None, audit_logger=None,
                 get_gpu_processes=None):
        self._config = config
        self._login_required = admin_login_required
        self._get_services = get_admin_services_status
        self._get_vram = get_vram_status
        self._get_logs = get_logs
        self._do_start = do_start_service
        self._do_stop = do_stop_service
        self._stop_all_llm = stop_all_llm_engines
        self._init_controller = _init_controller
        self._result_to_dict = _control_result_to_dict
        self._logger = logger or logging.getLogger("dashboard-llm")
        self._audit = audit_logger
        self._get_gpu_processes = get_gpu_processes

    def _log_action(self, action, service_key, result):
        if self._audit:
            self._audit.info("ACTION=%s SERVICE=%s RESULT=%s", action, service_key,
                            "OK" if result else "FAIL")

    def register(self, app):
        config = self._config
        login_required = self._login_required
        get_services = self._get_services
        get_vram = self._get_vram
        get_logs = self._get_logs
        do_start = self._do_start
        do_stop = self._do_stop
        stop_all_llm = self._stop_all_llm
        init_controller = self._init_controller
        result_to_dict = self._result_to_dict
        logger = self._logger
        _log_action = self._log_action

        def _check_csrf():
            csrf_enabled = config.get("admin", {}).get("csrf_enabled", False)
            if not csrf_enabled:
                return True
            csrf_header = config.get("admin", {}).get("csrf_header", "X-CSRF-Token")
            token = request.headers.get(csrf_header, "")
            from flask import session
            expected = session.get("csrf_token", "")
            if not token or token != expected:
                logger.warning("CSRF validation failed from %s", request.remote_addr or "unknown")
                return False
            return True

        @app.route('/api/admin/status')
        def api_admin_status():
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/status from %s",
                               request.remote_addr or "unknown")
                return jsonify({"error": "unauthorized"}), 401
            services_status = get_services()
            vram = get_vram()
            try:
                service_logs = get_logs()
            except Exception as exc:
                service_logs = {}
                logger.error("get_logs failed in api_admin_status: %s", exc)
            service_names = {}
            for k, v in config["services"].items():
                service_names[k] = v["name"]
            return jsonify({
                "services": services_status,
                "vram": vram,
                "service_logs": service_logs,
                "service_order": list(config["services"].keys()),
                "service_names": service_names,
            })

        @app.route('/api/admin/restart', methods=['POST'])
        def api_admin_restart():
            client_ip = request.remote_addr or "unknown"
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/restart from %s", client_ip)
                return jsonify({"error": "unauthorized"}), 401
            if not _check_csrf():
                return jsonify({"error": "csrf_validation_failed"}), 403
            data = request.get_json(silent=True) or {}
            key = data.get("service")
            if not key:
                return jsonify({"error": "missing service key"}), 400
            logger.info("Admin RESTART requested for %s from %s", key, client_ip)
            stop_result = do_stop(key)
            if not stop_result.get("success"):
                logger.warning("Admin RESTART stop failed for %s: %s", key,
                               stop_result.get("message"))
            time.sleep(2)
            start_result = do_start(key)
            if start_result.get("success"):
                logger.info("Admin RESTART success for %s", key)
            else:
                logger.error("Admin RESTART start failed for %s: %s", key,
                             start_result.get("message"))
            _log_action("restart", key, start_result.get("success", False))
            return jsonify(start_result)

        @app.route('/api/admin/start', methods=['POST'])
        def api_admin_start():
            client_ip = request.remote_addr or "unknown"
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/start from %s", client_ip)
                return jsonify({"error": "unauthorized"}), 401
            if not _check_csrf():
                return jsonify({"error": "csrf_validation_failed"}), 403
            data = request.get_json(silent=True) or {}
            key = data.get("service")
            if not key:
                return jsonify({"error": "missing service key"}), 400
            logger.info("Admin START requested for %s from %s", key, client_ip)
            result = do_start(key)
            logger.info("Admin START result for %s: %s", key, result.get("message", "?"))
            _log_action("start", key, result.get("success", False))
            return jsonify(result)

        @app.route('/api/admin/stop', methods=['POST'])
        def api_admin_stop():
            client_ip = request.remote_addr or "unknown"
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/stop from %s", client_ip)
                return jsonify({"error": "unauthorized"}), 401
            if not _check_csrf():
                return jsonify({"error": "csrf_validation_failed"}), 403
            data = request.get_json(silent=True) or {}
            key = data.get("service")
            if not key:
                return jsonify({"error": "missing service key"}), 400
            logger.info("Admin STOP requested for %s from %s", key, client_ip)
            result = do_stop(key)
            logger.info("Admin STOP result for %s: %s", key, result.get("message", "?"))
            _log_action("stop", key, result.get("success", False))
            return jsonify(result)

        @app.route('/api/admin/force_stop', methods=['POST'])
        def api_admin_force_stop():
            client_ip = request.remote_addr or "unknown"
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/force_stop from %s", client_ip)
                return jsonify({"error": "unauthorized"}), 401
            if not _check_csrf():
                return jsonify({"error": "csrf_validation_failed"}), 403
            data = request.get_json(silent=True) or {}
            key = data.get("service")
            if not key:
                return jsonify({"error": "missing service key"}), 400
            logger.warning("Admin FORCE_KILL requested for %s from %s", key, client_ip)
            result = init_controller().force_stop_service(key)
            _log_action("force_stop", key, result.success)
            payload = result_to_dict(result)
            payload["normal_stop_result"] = result.stdout
            return jsonify(payload)

        @app.route('/api/admin/stop_all_llm', methods=['POST'])
        def api_admin_stop_all_llm():
            client_ip = request.remote_addr or "unknown"
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/stop_all_llm from %s",
                               client_ip)
                return jsonify({"error": "unauthorized"}), 401
            if not _check_csrf():
                return jsonify({"error": "csrf_validation_failed"}), 403
            logger.info("Admin STOP_ALL_LLM requested from %s", client_ip)
            results = stop_all_llm()
            logger.info("Admin STOP_ALL_LLM result: %d services stopped", len(results))
            return jsonify({"success": True, "results": results})

        @app.route('/api/admin/vram')
        def api_admin_vram():
            if not login_required():
                logger.warning("Unauthorized admin API /api/admin/vram from %s",
                               request.remote_addr or "unknown")
                return jsonify({"error": "unauthorized"}), 401
            return jsonify(get_vram())

        @app.route('/api/admin/gpu/processes')
        def api_admin_gpu_processes():
            from flask import session
            if not login_required():
                return jsonify({"error": "unauthorized"}), 401
            processes = []
            if callable(self._get_gpu_processes):
                try:
                    processes = self._get_gpu_processes()
                except Exception as exc:
                    logger.warning("get_gpu_processes failed: %s", exc)
            return jsonify({"processes": processes})
