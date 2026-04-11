"""
test_screenshot_pipeline.py
Parse TrameViewer.tsx to verify screenshot debounce, viewport resolution,
and base64 download logic.
"""
import re

import pytest

TRAME_VIEWER_PATH = "dashboard/src/components/TrameViewer.tsx"


@pytest.fixture(scope="module")
def source():
    with open(TRAME_VIEWER_PATH, "r") as f:
        return f.read()


class TestScreenshotDebounce:
    def test_screenshot_debounce_guard(self, source):
        # handleScreenshot returns early if already capturing or timeout pending
        assert "if (screenshotCapturing || screenshotTimeoutRef.current) return" in source

    def test_screenshot_sets_capturing_state(self, source):
        # setScreenshotCapturing(true) called before send
        assert "setScreenshotCapturing(true)" in source

    def test_screenshot_clears_timeout_on_data(self, source):
        # screenshotTimeoutRef cleared when screenshot_data arrives
        assert "clearTimeout(screenshotTimeoutRef.current)" in source


class TestScreenshotViewportDimensions:
    def test_screenshot_reads_viewport_by_id(self, source):
        # getElementById('trame-viewport') to get dimensions
        assert "getElementById('trame-viewport')" in source

    def test_screenshot_reads_offsetWidth(self, source):
        assert "offsetWidth" in source

    def test_screenshot_reads_offsetHeight(self, source):
        assert "offsetHeight" in source

    def test_screenshot_sends_viewport_dimensions(self, source):
        # Sends width and height from viewport element
        assert "width: offsetWidth" in source
        assert "height: offsetHeight" in source


class TestScreenshotTimeout:
    def test_screenshot_uses_500ms_timeout(self, source):
        # Debounce reset with 500ms setTimeout
        assert "setTimeout(" in source and ", 500)" in source

    def test_screenshot_timeout_resets_capturing_state(self, source):
        # setScreenshotCapturing(false) inside the setTimeout callback
        # The timeout callback sets capturing to false
        assert "setScreenshotCapturing(false)" in source


class TestScreenshotDownload:
    def test_screenshot_download_uses_atob(self, source):
        # Base64 decode via atob()
        assert "atob(" in source

    def test_screenshot_download_creates_blob(self, source):
        # new Blob(...) for PNG download
        assert "new Blob(" in source

    def test_screenshot_download_uses_download_attr(self, source):
        # link.download = 'cfd-screenshot-...'
        assert "cfd-screenshot-" in source
        assert "link.download" in source or ".download =" in source

    def test_screenshot_download_appends_link_and_clicks(self, source):
        # Link appended to body, clicked, then removed
        assert "document.body.appendChild(link)" in source
        assert "link.click()" in source
        assert "document.body.removeChild(link)" in source

    def test_screenshot_revoke_url(self, source):
        # URL.revokeObjectURL(url) after click
        assert "URL.revokeObjectURL(url)" in source

    def test_screenshot_filename_includes_timestamp(self, source):
        # Filename includes ISO timestamp
        assert "new Date().toISOString()" in source
