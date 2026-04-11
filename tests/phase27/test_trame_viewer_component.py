"""
test_trame_viewer_component.py
Parse TrameViewer.tsx to verify component structure, state machine,
message handlers, and bridge wiring.
"""
import re

import pytest

TRAME_VIEWER_PATH = "dashboard/src/components/TrameViewer.tsx"


@pytest.fixture(scope="module")
def source():
    with open(TRAME_VIEWER_PATH, "r") as f:
        return f.read()


class TestImports:
    def test_trameviewer_imports_cfd_viewer_bridge(self, source):
        assert "from '../services/CFDViewerBridge'" in source

    def test_trameviewer_imports_advanced_filter_panel(self, source):
        assert "import AdvancedFilterPanel from './AdvancedFilterPanel'" in source

    def test_trameviewer_no_paraview_web_websocket(self, source):
        # No WebSocket instantiation or URL scheme (postMessage only)
        assert "new WebSocket" not in source
        assert "ws://" not in source
        assert "wss://" not in source


class TestViewerStateType:
    def test_trameviewer_has_viewer_state_type(self, source):
        assert "export type ViewerState = 'idle' | 'launching' | 'connected' | 'disconnected' | 'error'" in source

    def test_trameviewer_viewer_state_has_all_five_states(self, source):
        # Verify all 5 states are present in the union type
        for state in ["idle", "launching", "connected", "disconnected", "error"]:
            assert f"'{state}'" in source


class TestMessageHandlers:
    def test_trameviewer_handles_ready_message(self, source):
        assert "case 'ready':" in source

    def test_trameviewer_handles_volume_status(self, source):
        assert "case 'volume_status':" in source

    def test_trameviewer_handles_filter_list(self, source):
        assert "case 'filter_list':" in source

    def test_trameviewer_handles_screenshot_data(self, source):
        assert "case 'screenshot_data':" in source

    def test_trameviewer_handles_camera(self, source):
        assert "case 'camera':" in source

    def test_trameviewer_handles_fields(self, source):
        assert "case 'fields':" in source


class TestVolumeWarnings:
    def test_trameviewer_volume_warning_mesa(self, source):
        # Apple Silicon Mesa warning
        assert "Apple Silicon detected" in source or "Mesa" in source

    def test_trameviewer_volume_warning_cell_count(self, source):
        # Large dataset cell count warning
        assert "cell_count_warning" in source
        assert "Large dataset" in source or "M cells" in source


class TestBridgeSendMapping:
    def test_trameviewer_bridgesend_maps_clip(self, source):
        assert "'clip_create'" in source or '"clip_create"' in source

    def test_trameviewer_bridgesend_maps_contour(self, source):
        assert "'contour_create'" in source or '"contour_create"' in source

    def test_trameviewer_bridgesend_maps_streamtracer(self, source):
        assert "'streamtracer_create'" in source or '"streamtracer_create"' in source

    def test_trameviewer_bridgesend_maps_filter_delete(self, source):
        assert "'filter_delete'" in source or '"filter_delete"' in source


class TestLaunchSession:
    def test_trameviewer_launch_calls_launch_visualization_session(self, source):
        # handleLaunch calls launchVisualizationSession
        assert "launchVisualizationSession" in source

    def test_trameviewer_launch_sets_session_url_and_id(self, source):
        # After launch, sessionUrl and sessionId are set
        assert "session_url" in source
        assert "session_id" in source


class TestIframeRendering:
    def test_trameviewer_iframe_src_is_session_url(self, source):
        # iframe src={sessionUrl}
        assert "src={sessionUrl}" in source

    def test_trameviewer_iframe_has_onload_handler(self, source):
        # iframe onLoad={handleIframeLoad}
        assert "onLoad={handleIframeLoad}" in source

    def test_trameviewer_trame_viewport_div_exists(self, source):
        # id="trame-viewport" for screenshot targeting
        assert 'id="trame-viewport"' in source


class TestInitialStateRequests:
    def test_trameviewer_onload_requests_volume_status(self, source):
        # handleIframeLoad sends volume_status
        assert "type: 'volume_status'" in source

    def test_trameviewer_onload_requests_filter_list(self, source):
        # handleIframeLoad sends filter_list
        assert "type: 'filter_list'" in source
