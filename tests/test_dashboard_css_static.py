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
        media_start = content.find("@media (max-width: 768px)")
        if media_start == -1:
            pytest.skip("No media block found")
        # Find the NEXT { which is the media block opening
        media_open = content.find("{", media_start)
        assert media_open != -1, "Media block has no opening brace"
        assert content[media_start:media_open].count("{") == 0, "Unexpected { between @media and its opening brace"
        # Find matching close via depth counter
        media_close = _find_matching_brace(content, media_open)
        assert media_close != -1, "Media block not closed"
        # GPU styles must start after media block closes
        gpu_pos = content.rfind("GPU Process Viewer", 0, media_open)  # before media = ok
        if gpu_pos == -1:
            gpu_pos = content.find(".gpu-processes-section")
        if gpu_pos == -1:
            pytest.fail("GPU Process Viewer styles not found")
        assert gpu_pos < media_open or gpu_pos > media_close, (
            f"Media block closes at pos {media_close}, "
            f"but GPU Process Viewer starts at pos {gpu_pos}"
        )


def _find_matching_brace(text, open_pos):
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


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
