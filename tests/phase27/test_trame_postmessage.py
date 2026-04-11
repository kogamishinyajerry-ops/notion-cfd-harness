"""
Tests for trame_server.py postMessage JavaScript handler block.

Verifies that all 14 case types exist in the injected JS script block,
and that the 'ready' broadcast and camera polling are present.
"""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/Users/Zhuanz/Desktop/notion-cfd-harness")


def get_js_script_block() -> str:
    """Extract the injected JS script block from trame_server.py source.

    Uses regex to find the _server.add_custom_script(\"\"\"...\"\"\") call
    and returns just the JavaScript content between the triple-double-quotes.
    """
    with open(PROJECT_ROOT / "trame_server.py") as f:
        content = f.read()

    # Pattern: _server.add_custom_script("""<content>""")
    # The content may span multiple lines and contain any characters except """
    pattern = r'_server\.add_custom_script\s*\(\s*"""(.*?)"""\s*\)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        pytest.fail("Could not find _server.add_custom_script(...) call in trame_server.py")
    return match.group(1)


class TestPostMessageHandler:
    """Tests for the 14 postMessage case types in the JS script block."""

    @pytest.fixture
    def script(self) -> str:
        return get_js_script_block()

    def test_all_14_message_cases_exist(self, script: str):
        """Verify all 14 case types are present in the switch statement."""
        cases = [
            "field",        # case 'field'
            "slice",        # case 'slice'
            "slice_off",    # case 'slice_off'
            "color_preset", # case 'color_preset'
            "scalar_range", # case 'scalar_range'
            "volume_toggle",# case 'volume_toggle'
            "timestep",     # case 'timestep'
            "clip_create",  # case 'clip_create'
            "contour_create",  # case 'contour_create'
            "streamtracer_create",  # case 'streamtracer_create'
            "filter_delete", # case 'filter_delete'
            "filter_list",   # case 'filter_list'
            "volume_status", # case 'volume_status'
            "screenshot",    # case 'screenshot'
        ]
        missing = [c for c in cases if f"case '{c}':" not in script]
        assert not missing, f"Missing case types: {missing}"
        assert len(cases) == 14

    def test_ready_message_broadcast(self, script: str):
        """Assert the 'ready' postMessage broadcast is present."""
        assert "postMessage({ type: 'ready' }" in script, (
            "'ready' broadcast missing from script block"
        )

    def test_camera_polling_interval(self, script: str):
        """Assert setInterval polling at ~500ms increments camera_poll_trigger."""
        assert "setInterval" in script, "setInterval not found in script block"
        assert "camera_poll_trigger" in script, "camera_poll_trigger not found in script block"
        assert "500" in script, "500ms polling interval not found"

    def test_volume_toggle_calls_ctrl(self, script: str):
        """Assert volume_toggle case calls ctrl.on_volume_rendering_toggle."""
        vol_idx = script.find("case 'volume_toggle':")
        assert vol_idx != -1, "volume_toggle case not found"
        # Extract 200 chars after case to check for ctrl call
        case_block = script[vol_idx : vol_idx + 300]
        assert "on_volume_rendering_toggle" in case_block, (
            "ctrl.on_volume_rendering_toggle call not found in volume_toggle case"
        )

    def test_filter_delete_calls_ctrl(self, script: str):
        """Assert filter_delete case calls ctrl.on_filter_delete."""
        del_idx = script.find("case 'filter_delete':")
        assert del_idx != -1, "filter_delete case not found"
        case_block = script[del_idx : del_idx + 300]
        assert "on_filter_delete" in case_block, (
            "ctrl.on_filter_delete call not found in filter_delete case"
        )

    def test_screenshot_calls_ctrl(self, script: str):
        """Assert screenshot case calls ctrl.on_screenshot."""
        ss_idx = script.find("case 'screenshot':")
        assert ss_idx != -1, "screenshot case not found"
        case_block = script[ss_idx : ss_idx + 300]
        assert "on_screenshot" in case_block, (
            "ctrl.on_screenshot call not found in screenshot case"
        )

    def test_trame_bridge_initialized(self, script: str):
        """Assert window._trameBridge is initialized at the top of the script."""
        assert "window._trameBridge = window._trameBridge || {}" in script, (
            "window._trameBridge initialization missing"
        )

    def test_message_listener_registered(self, script: str):
        """Assert addEventListener('message', ...) is present."""
        assert "addEventListener('message'" in script or 'addEventListener("message"' in script, (
            "message event listener not registered"
        )

    def test_trame_server_reference_captured(self, script: str):
        """Assert window._trameServer captures state and ctrl references."""
        assert "window._trameServer" in script, (
            "window._trameServer reference capture missing"
        )
        assert "state" in script and "ctrl" in script, (
            "state/ctrl not referenced in script"
        )
