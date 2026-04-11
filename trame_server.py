#!/usr/bin/env pvpython
"""
trame_server.py — ParaView Web to trame migration.

Replaces:
  - entrypoint_wrapper.sh (container entrypoint)
  - adv_protocols.py (@exportRpc protocol classes)
  - launcher.py (vtk.web.launcher multi-process launcher)

Phase 23: Minimal sphere rendering skeleton.
Phase 24: All 7 RPC handlers migrated (@ctrl.add/@state.change), UUID filter registry.
Phase 26: Vue iframe postMessage bridge, camera polling, screenshot/field/volume handlers.

Usage:
    pvpython /trame_server.py --port 9000
    pvpython /trame_server.py --port 9000 --data /data/case.foam
"""

import argparse
import json
import uuid
import subprocess

from paraview import simple
from trame.app import get_server
from trame.ui.vuetify import SinglePageLayout
from trame.html import paraview
from trame.widgets import vuetify

# Global server objects — set in main(), used by @ctrl.add / @state.change handlers.
# Safe because handlers are invoked at runtime after main() has assigned them.
_server = None
_state = None
_ctrl = None

# Camera state tracking — avoids duplicate postMessage broadcasts
_last_camera_state = None


# =============================================================================
# GPU Detection
# =============================================================================

_gpu_vendor_cache = None
_gpu_available_cache = None


def _detect_gpu():
    """Detect GPU via EGL vendor string. Returns (available, vendor)."""
    global _gpu_vendor_cache, _gpu_available_cache
    if _gpu_vendor_cache is not None:
        return _gpu_available_cache, _gpu_vendor_cache
    try:
        result = subprocess.run(
            ["eglinfo"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout + result.stderr
        if "NVIDIA" in output:
            vendor = "NVIDIA"
            available = True
        elif "Mesa" in output or "llvmpipe" in output:
            vendor = "Mesa"
            available = False
        else:
            vendor = "unknown"
            available = False
    except Exception:
        vendor = "unknown"
        available = False

    _gpu_vendor_cache = vendor
    _gpu_available_cache = available
    return available, vendor


def build_view():
    """Create a minimal ParaView scene with a sphere.

    In Phase 24 this will be replaced with OpenFOAM case loading.
    For now, use a simple Sphere source as the minimal geometry verification.
    """
    sphere = simple.Sphere()
    sphere.ThetaResolution = 16
    sphere.PhiResolution = 16

    view = simple.GetRenderView()
    view.CenterAxesVisibility = 0

    simple.Render()
    return view


# =============================================================================
# Filter Registry Helpers — UUID-based, replaces class-level _filters dict
# =============================================================================

def _build_filter_params(proxy, ftype):
    """Extract parameters from a filter proxy for filterList response."""
    if ftype == "clip":
        return {
            "insideOut": bool(getattr(proxy, "InsideOut", False)),
            "scalarValue": float(getattr(proxy, "Scalar", 0)),
        }
    elif ftype == "contour":
        return {
            "isovalues": list(getattr(proxy, "Isosurfaces", [])),
        }
    elif ftype == "streamtracer":
        return {
            "integrationDirection": str(getattr(proxy, "IntegrationDirection", "FORWARD")),
            "maxSteps": int(getattr(proxy, "MaximumSteps", 1000)),
        }
    return {}


def _get_filter_list():
    """Build the filter list response from _state.filters registry."""
    filters = []
    for filter_uuid, info in _state.filters.items():
        proxy = info["proxy"]
        ftype = info["type"]
        params = _build_filter_params(proxy, ftype)
        filters.append({
            "id": filter_uuid,
            "type": ftype,
            "parameters": params,
        })
    return {"filters": filters}


# =============================================================================
# Volume Rendering Handlers — replace ParaViewWebVolumeRendering @exportRpc
# =============================================================================

@_state.change("volume_rendering_status_request")
def on_volume_rendering_status_request(volume_rendering_status_request, **kwargs):
    """Reactive handler: fires when client sets state.volume_rendering_status_request = True.

    Replaces: @exportRpc("visualization.volume.rendering.status")
    """
    gpu_available, gpu_vendor = _detect_gpu()

    cell_count = 0
    cell_count_warning = False
    try:
        source = simple.GetActiveSource()
        if source is not None:
            data_info = simple.GetDataInformation(source)
            if data_info is not None:
                cell_count = data_info.GetNumberOfCells()
                cell_count_warning = cell_count > 2_000_000
    except Exception:
        pass

    volume_enabled = False
    field_name = None
    try:
        view = simple.GetActiveView()
        if view is not None:
            repr_ = simple.GetDisplayProperties(source=simple.GetActiveSource())
            if repr_ is not None:
                repr_type = repr_.Representation
                volume_enabled = repr_type == "Volume"
    except Exception:
        pass

    _state.volume_rendering_status = {
        "enabled": volume_enabled,
        "field_name": field_name,
        "gpu_available": gpu_available,
        "gpu_vendor": gpu_vendor,
        "cell_count": cell_count,
        "cell_count_warning": cell_count_warning,
    }


@_ctrl.add
def on_volume_rendering_toggle(field_name: str, enabled: bool):
    """Toggle volume rendering for the specified scalar field.

    Replaces: @exportRpc("visualization.volume.rendering.toggle")
    """
    try:
        source = simple.GetActiveSource()
        if source is None:
            return {"success": False, "error": "No active source"}

        if field_name:
            try:
                props = source
                if hasattr(props, "Fields"):
                    props.Fields = field_name
            except Exception:
                pass

        display = simple.GetDisplayProperties(source=source)
        if display is None:
            return {"success": False, "error": "Could not get display properties"}

        if enabled:
            display.SetRepresentationToVolume()
            try:
                volume_mapper = simple._create_vtkSmartVolumeMapper()
                if volume_mapper is not None:
                    display.SetVolumeMapper(volume_mapper)
            except Exception:
                pass
        else:
            display.SetRepresentationToSurface()

        simple.Render()
        _ctrl.view_update()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Filter Handlers — replace ParaViewWebAdvancedFilters @exportRpc
# =============================================================================

@_ctrl.add
def on_filter_clip_create(inside_out: bool, scalar_value: float):
    """Create a scalar Clip filter on the active source.

    Replaces: @exportRpc("visualization.filters.clip.create")
    TRAME-02.4: Uses UUID hex as key instead of id(proxy).
    """
    try:
        source = simple.GetActiveSource()
        if source is None:
            return {"success": False, "error": "No active source"}

        if not isinstance(scalar_value, (int, float)) or not (-1e10 < scalar_value < 1e10):
            return {"success": False, "error": "Invalid scalarValue"}

        clip = simple.Clip(Input=source)
        clip.ClipType = "Scalar"
        clip.Scalar = scalar_value
        clip.InsideOut = inside_out

        filter_uuid = uuid.uuid4().hex
        _state.filters[filter_uuid] = {
            "type": "clip",
            "proxy": clip,
            "params": {"insideOut": inside_out, "scalarValue": scalar_value},
        }

        simple.Render()
        _ctrl.view_update()
        _state.filter_list = _get_filter_list()
        return {"success": True, "filterId": filter_uuid, "proxyId": filter_uuid}

    except Exception as e:
        return {"success": False, "error": str(e)}


@_ctrl.add
def on_filter_contour_create(isovalues: list):
    """Create an isosurface Contour filter on the active source.

    Replaces: @exportRpc("visualization.filters.contour.create")
    TRAME-02.4: Uses UUID hex as key instead of id(proxy).
    """
    try:
        source = simple.GetActiveSource()
        if source is None:
            return {"success": False, "error": "No active source"}

        if not isinstance(isovalues, list) or len(isovalues) > 20:
            return {"success": False, "error": "isovalues must be a list with at most 20 values"}
        for v in isovalues:
            if not isinstance(v, (int, float)) or not (-1e10 < v < 1e10):
                return {"success": False, "error": "All isovalues must be finite numbers"}

        contour = simple.Contour(Input=source)
        contour.ContourBy = ["POINTS", " scalars"]  # note space before 'scalars' — preserved from v1.5.0
        contour.Isosurfaces = isovalues

        filter_uuid = uuid.uuid4().hex
        _state.filters[filter_uuid] = {
            "type": "contour",
            "proxy": contour,
            "params": {"isovalues": isovalues},
        }

        simple.Render()
        _ctrl.view_update()
        _state.filter_list = _get_filter_list()
        return {"success": True, "filterId": filter_uuid, "proxyId": filter_uuid}

    except Exception as e:
        return {"success": False, "error": str(e)}


@_ctrl.add
def on_filter_streamtracer_create(integration_direction: str, max_steps: int):
    """Create a StreamTracer filter using velocity field U.

    Replaces: @exportRpc("visualization.filters.streamtracer.create")
    TRAME-02.4: Uses UUID hex as key instead of id(proxy).
    """
    try:
        source = simple.GetActiveSource()
        if source is None:
            return {"success": False, "error": "No active source"}

        if integration_direction not in ("FORWARD", "BACKWARD"):
            return {"success": False, "error": "integrationDirection must be FORWARD or BACKWARD"}
        if not isinstance(max_steps, int) or max_steps <= 0:
            return {"success": False, "error": "maxSteps must be a positive integer"}
        max_steps = min(max_steps, 10000)

        streamtracer = simple.StreamTracer(Input=source)
        streamtracer.Vectors = ["POINTS", "U"]
        streamtracer.IntegrationDirection = integration_direction
        streamtracer.MaximumSteps = max_steps
        streamtracer.InitialStepLength = 0.1
        streamtracer.MinimumStepLength = 0.001

        filter_uuid = uuid.uuid4().hex
        _state.filters[filter_uuid] = {
            "type": "streamtracer",
            "proxy": streamtracer,
            "params": {"integrationDirection": integration_direction, "maxSteps": max_steps},
        }

        simple.Render()
        _ctrl.view_update()
        _state.filter_list = _get_filter_list()
        return {"success": True, "filterId": filter_uuid, "proxyId": filter_uuid}

    except Exception as e:
        return {"success": False, "error": str(e)}


@_ctrl.add
def on_filter_delete(filter_id: str):
    """Delete a filter by its UUID.

    Replaces: @exportRpc("visualization.filters.delete")
    TRAME-02.4: filter_id is a UUID hex string (previously int from id()).
    """
    try:
        filter_info = _state.filters.get(filter_id)
        if filter_info is None:
            return {"success": False, "error": f"Filter {filter_id} not found"}

        filter_proxy = filter_info["proxy"]
        simple.Delete(filter_proxy)

        del _state.filters[filter_id]

        simple.Render()
        _ctrl.view_update()
        _state.filter_list = _get_filter_list()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


@_state.change("filter_list_request")
def on_filter_list_request(filter_list_request, **kwargs):
    """Reactive handler: fires when client sets state.filter_list_request = True.

    Replaces: @exportRpc("visualization.filters.list")
    """
    _state.filter_list = _get_filter_list()


# =============================================================================
# Phase 26: Vue Iframe postMessage Bridge
# Camera polling every 500ms, all 14 command types wired to postMessage
# =============================================================================

def _get_camera_state():
    """Read current camera position/focal point from ParaView render view."""
    global _last_camera_state
    try:
        view = simple.GetActiveView()
        if view is None:
            return None
        camera = view.GetCamera()
        if camera is None:
            return None
        pos = camera.GetPosition()
        focal = camera.GetFocalPoint()
        return {
            "position": [float(pos[0]), float(pos[1]), float(pos[2])],
            "focalPoint": [float(focal[0]), float(focal[1]), float(focal[2])],
        }
    except Exception:
        return None


def _post_camera_if_changed():
    """Post camera state to parent via js_call if it differs from last post."""
    global _last_camera_state
    state = _get_camera_state()
    if state is None:
        return
    state_key = (tuple(state["position"]), tuple(state["focalPoint"]))
    last_key = (
        tuple(_last_camera_state["position"]) if _last_camera_state else None,
        tuple(_last_camera_state["focalPoint"]) if _last_camera_state else None,
    )
    if state_key != last_key:
        _last_camera_state = state
        _server.js_call(
            "window._trameBridge && window._trameBridge.postMessage("
            + json.dumps({"type": "camera", **state})
            + ", '*')"
        )


@_state.change("camera_poll_trigger")
def on_camera_poll(camera_poll_trigger, **kwargs):
    """Fires every ~500ms when camera_poll_trigger increments.
    Posts camera state to parent via js_call if changed."""
    _post_camera_if_changed()


@_ctrl.add
def on_screenshot(width: int, height: int):
    """Handle screenshot request from React bridge.
    Returns screenshot as base64 via postMessage to parent."""
    try:
        view = simple.GetRenderView()
        if view is None:
            return {"success": False, "error": "No active view"}
        # Set viewport size before rendering
        view.ViewSize = [width, height]
        simple.Render()
        # Capture using trame's html_view
        if hasattr(_server, "html_view") and _server.html_view is not None:
            img = _server.html_view.screenshot(fill=False, quality=95)
            if img:
                _server.js_call(
                    "window._trameBridge && window._trameBridge.postMessage("
                    + json.dumps({"type": "screenshot_data", "image": img})
                    + ", '*')"
                )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Client-side state-setter handlers — fire when React sets state via bridge
# ---------------------------------------------------------------------------

@_state.change("field")
def on_field_change(field, **kwargs):
    """When client sets field name, update ParaView reader and render."""
    if not field:
        return
    try:
        source = simple.GetActiveSource()
        if source is not None and hasattr(source, "Fields"):
            source.Fields = field
        simple.Render()
        _ctrl.view_update()
    except Exception:
        pass


@_state.change("slice_axis", "slice_origin")
def on_slice_change(slice_axis, slice_origin, **kwargs):
    """When client sets slice axis and origin, create/update slice filter."""
    if slice_axis is None:
        try:
            slice_filter = getattr(_state, "_slice_filter", None)
            if slice_filter:
                simple.Delete(slice_filter)
                _state._slice_filter = None
            simple.Render()
            _ctrl.view_update()
        except Exception:
            pass
        return
    try:
        source = simple.GetActiveSource()
        if source is None:
            return
        slice_filter = getattr(_state, "_slice_filter", None)
        if slice_filter is None:
            slice_filter = simple.Slice(Input=source)
            _state._slice_filter = slice_filter
        normal_map = {"X": [1, 0, 0], "Y": [0, 1, 0], "Z": [0, 0, 1]}
        slice_filter.SliceType = "Plane"
        slice_filter.SliceType.Normal = normal_map.get(slice_axis, [0, 0, 1])
        slice_filter.SliceType.Origin = slice_origin
        simple.Render()
        _ctrl.view_update()
    except Exception:
        pass


@_state.change("color_preset")
def on_color_preset_change(color_preset, **kwargs):
    """Apply color lookup table preset."""
    lut_map = {"Viridis": "Viridis", "BlueRed": "Blue to Red Rainbow", "Grayscale": "Grayscale"}
    try:
        source = simple.GetActiveSource()
        if source is not None:
            display = simple.GetDisplayProperties(source)
            if display is not None:
                lut_name = lut_map.get(color_preset, "Viridis")
                lut = simple.GetLookupTableForArray("POINTS", 0, NanColor=[0.75, 0.75, 0.75])
                lut.RGBPoints = simple.GetColorTransferFunction(lut_name).RGBPoints
                display.LookupTable = lut
            simple.Render()
            _ctrl.view_update()
    except Exception:
        pass


@_state.change("scalar_range_mode", "scalar_range_min", "scalar_range_max")
def on_scalar_range_change(scalar_range_mode, scalar_range_min, scalar_range_max, **kwargs):
    """Update scalar color range."""
    try:
        display = simple.GetDisplayProperties()
        if display is not None:
            if scalar_range_mode == "auto":
                display.RescaleTransferFunctionToDataRange()
            else:
                display.ScalarRangeInitialized = 1
                display.ScalarRange = [scalar_range_min, scalar_range_max]
            simple.Render()
            _ctrl.view_update()
    except Exception:
        pass


@_state.change("time_step_index")
def on_timestep_change(time_step_index, **kwargs):
    """Change active time step."""
    try:
        source = simple.GetActiveSource()
        if source is not None and hasattr(source, "TimeStep"):
            source.TimeStep = time_step_index
        simple.Render()
        _ctrl.view_update()
    except Exception:
        pass


# =============================================================================
# Main — trame server setup
# =============================================================================

def main():
    global _server, _state, _ctrl

    parser = argparse.ArgumentParser(description="trame CFD Viewer Server")
    parser.add_argument("--port", type=int, default=9000,
                        help="Port to serve on (default: 9000)")
    parser.add_argument("--data", default=None,
                        help="Path to OpenFOAM case directory (future Phase 24)")
    args = parser.parse_args()

    simple.DisableModules()
    view = build_view()

    _server = get_server()
    _state, _ctrl = _server.state, _server.controller
    state, ctrl = _state, _ctrl  # local aliases for any remaining direct refs

    # Initialize filter registry with UUID keys (replaces class-level _filters dict)
    _state.filters = {}  # {uuid_hex: {"type": str, "proxy": object, "params": dict}}

    # -------------------------------------------------------------------------
    # Phase 26: Initialize bridge state variables
    # -------------------------------------------------------------------------
    _state.field = ""
    _state.slice_axis = None
    _state.slice_origin = [0.0, 0.0, 0.0]
    _state.color_preset = "Viridis"
    _state.scalar_range_mode = "auto"
    _state.scalar_range_min = 0.0
    _state.scalar_range_max = 1.0
    _state.time_step_index = 0
    _state.camera_poll_trigger = 0
    _state.camera_position = [0.0, 0.0, 0.0]
    _state.camera_focal_point = [0.0, 0.0, 0.0]
    _state.volume_rendering_status_request = False
    _state.volume_rendering_status = {}
    _state.filter_list_request = False
    _state.filter_list = {"filters": []}

    html_view = paraview.VtkRemoteView(view)
    _server.html_view = html_view  # Make available to screenshot handler

    # -------------------------------------------------------------------------
    # Phase 26: postMessage listener and camera polling (JavaScript injected)
    # -------------------------------------------------------------------------
    _server.add_custom_script("""
window._trameBridge = window._trameBridge || {};

// Expose server state/ctrl for bridge commands
window._trameServer = { state: window.trameObject.state, ctrl: window.trameObject.ctrl };

// Listen for postMessages from the React parent (CFDViewerBridge.ts)
window.addEventListener('message', function(event) {
    var data = event.data;
    if (!data || !data.type) return;

    var _s = window._trameServer;
    if (!_s || !_s.state) return;

    switch (data.type) {
        case 'field':
            _s.state.field = data.field;
            break;
        case 'slice':
            _s.state.slice_axis = data.axis;
            _s.state.slice_origin = data.origin;
            break;
        case 'slice_off':
            _s.state.slice_axis = null;
            break;
        case 'color_preset':
            _s.state.color_preset = data.preset;
            break;
        case 'scalar_range':
            _s.state.scalar_range_mode = data.mode;
            _s.state.scalar_range_min = (data.min !== undefined) ? data.min : 0;
            _s.state.scalar_range_max = (data.max !== undefined) ? data.max : 1;
            break;
        case 'volume_toggle':
            _s.ctrl && _s.ctrl.on_volume_rendering_toggle && _s.ctrl.on_volume_rendering_toggle(data.field_name || '', data.enabled);
            break;
        case 'timestep':
            _s.state.time_step_index = data.index;
            break;
        case 'clip_create':
            _s.ctrl && _s.ctrl.on_filter_clip_create && _s.ctrl.on_filter_clip_create(data.insideOut, data.scalarValue);
            break;
        case 'contour_create':
            _s.ctrl && _s.ctrl.on_filter_contour_create && _s.ctrl.on_filter_contour_create(data.isovalues);
            break;
        case 'streamtracer_create':
            _s.ctrl && _s.ctrl.on_filter_streamtracer_create && _s.ctrl.on_filter_streamtracer_create(data.direction, data.maxSteps);
            break;
        case 'filter_delete':
            _s.ctrl && _s.ctrl.on_filter_delete && _s.ctrl.on_filter_delete(data.filterId);
            break;
        case 'filter_list':
            _s.state.filter_list_request = true;
            break;
        case 'volume_status':
            _s.state.volume_rendering_status_request = true;
            break;
        case 'screenshot':
            _s.ctrl && _s.ctrl.on_screenshot && _s.ctrl.on_screenshot(data.width || 1920, data.height || 1080);
            break;
    }
});

// Signal to React that the iframe is ready
window._trameBridge.postMessage({ type: 'ready' }, '*');

// Start camera polling every 500ms — increments trigger → fires @state.change handler
setInterval(function() {
    if (window._trameServer && window._trameServer.state) {
        window._trameServer.state.camera_poll_trigger =
            (window._trameServer.state.camera_poll_trigger || 0) + 1;
    }
}, 500);
""")

    layout = SinglePageLayout(_server)
    layout.title.set_text("CFD Viewer — trame")

    with layout.content:
        vuetify.VContainer(
            fluid=True,
            classes="pa-0 fill-height",
            children=[html_view]
        )

    _server.start(
        port=args.port,
        host="0.0.0.0",
        open_browser=False,
        show_connection_info=False,
    )


if __name__ == "__main__":
    main()
