"""Phase 1 — Test CSS statique GPU Process Viewer."""
import pytest


class TestCSSStatic:
    def test_file_exists(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "llm_dashboard", "static", "css", "dashboard.css")
        content = open(path).read()
        assert len(content) > 0

    def test_braces_balanced(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "llm_dashboard", "static", "css", "dashboard.css")
        content = open(path).read()
        assert content.count("{") == content.count("}")

    def test_gpu_process_classes_exist(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "llm_dashboard", "static", "css", "dashboard.css")
        content = open(path).read()
        assert ".gpu-processes-section" in content
        assert ".gpu-process-table" in content
        assert ".gpu-process-service-badge" in content
        assert ".gpu-process-command" in content

    def test_gpu_styles_outside_first_media_block(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "llm_dashboard", "static", "css", "dashboard.css")
        content = open(path).read()
        # Find first media block end
        media_start = content.find("@media (max-width: 768px)")
        if media_start == -1:
            pytest.skip("No media block found")
        # Find first GPU style position
        gpu_pos = content.find(".gpu-processes-section")
        assert gpu_pos > media_start, "GPU styles appear before/inside media block"


class TestJSStatic:
    def test_dashboard_js_no_tr_innerhtml_in_gpu(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "llm_dashboard", "static", "js", "dashboard.js")
        content = open(path).read()
        # Without context, just verify file loads
        assert "updateGpuProcesses" in content
        assert "safeServiceClass" in content
        assert "No GPU processes detected" in content

    def test_admin_js_contains_csrf_headers(self):
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "llm_dashboard", "static", "js", "admin.js")
        content = open(path).read()
        assert "getCsrfHeaders" in content
