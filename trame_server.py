#!/usr/bin/env pvpython
"""
trame_server.py — ParaView Web to trame migration.

Replaces:
  - entrypoint_wrapper.sh (container entrypoint)
  - adv_protocols.py (@exportRpc protocol classes)
  - launcher.py (vtk.web.launcher multi-process launcher)

Phase 23: Minimal sphere rendering skeleton.
Phase 24: All 7 RPC handlers migrated (@ctrl.add/@state.change), UUID filter registry.

Usage:
    pvpython /trame_server.py --port 9000
    pvpython /trame_server.py --port 9000 --data /data/case.foam
"""

import argparse
import uuid
import subprocess

from paraview import simple
from trame.app import get_server
from trame.ui.vuetify import SinglePageLayout
from trame.html import paraview
from trame.widgets import vuetify


# =============================================================================
# GPU Detection — copied verbatim from paraview_adv_protocols.py
# =============================================================================

_gpu_vendor_cache = None
_gpu_available_cache = None


def _detect_gpu():
    """Detect GPU via EGL vendor string. Returns (available, vendor).

    Copied verbatim from paraview_adv_protocols.py ParaViewWebVolumeRendering._detect_gpu().
    """
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
    """Build the filter list response from state.filters registry."""
    filters = []
    for filter_uuid, info in state.filters.items():
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

@state.change("volume_rendering_status_request")
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

    state.volume_rendering_status = {
        "enabled": volume_enabled,
        "field_name": field_name,
        "gpu_available": gpu_available,
        "gpu_vendor": gpu_vendor,
        "cell_count": cell_count,
        "cell_count_warning": cell_count_warning,
    }


@ctrl.add
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
        ctrl.view_update()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# Filter Handlers — replace ParaViewWebAdvancedFilters @exportRpc
# =============================================================================

@ctrl.add
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
        state.filters[filter_uuid] = {
            "type": "clip",
            "proxy": clip,
            "params": {"insideOut": inside_out, "scalarValue": scalar_value},
        }

        simple.Render()
        ctrl.view_update()
        state.filter_list = _get_filter_list()
        return {"success": True, "filterId": filter_uuid, "proxyId": filter_uuid}

    except Exception as e:
        return {"success": False, "error": str(e)}


@ctrl.add
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
        state.filters[filter_uuid] = {
            "type": "contour",
            "proxy": contour,
            "params": {"isovalues": isovalues},
        }

        simple.Render()
        ctrl.view_update()
        state.filter_list = _get_filter_list()
        return {"success": True, "filterId": filter_uuid, "proxyId": filter_uuid}

    except Exception as e:
        return {"success": False, "error": str(e)}


@ctrl.add
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
        state.filters[filter_uuid] = {
            "type": "streamtracer",
            "proxy": streamtracer,
            "params": {"integrationDirection": integration_direction, "maxSteps": max_steps},
        }

        simple.Render()
        ctrl.view_update()
        state.filter_list = _get_filter_list()
        return {"success": True, "filterId": filter_uuid, "proxyId": filter_uuid}

    except Exception as e:
        return {"success": False, "error": str(e)}


@ctrl.add
def on_filter_delete(filter_id: str):
    """Delete a filter by its UUID.

    Replaces: @exportRpc("visualization.filters.delete")
    TRAME-02.4: filter_id is a UUID hex string (previously int from id()).
    """
    try:
        filter_info = state.filters.get(filter_id)
        if filter_info is None:
            return {"success": False, "error": f"Filter {filter_id} not found"}

        filter_proxy = filter_info["proxy"]
        simple.Delete(filter_proxy)

        del state.filters[filter_id]

        simple.Render()
        ctrl.view_update()
        state.filter_list = _get_filter_list()
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


@state.change("filter_list_request")
def on_filter_list_request(filter_list_request, **kwargs):
    """Reactive handler: fires when client sets state.filter_list_request = True.

    Replaces: @exportRpc("visualization.filters.list")
    """
    state.filter_list = _get_filter_list()


# =============================================================================
# Main — trame server setup
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="trame CFD Viewer Server")
    parser.add_argument("--port", type=int, default=9000,
                        help="Port to serve on (default: 9000)")
    parser.add_argument("--data", default=None,
                        help="Path to OpenFOAM case directory (future Phase 24)")
    args = parser.parse_args()

    simple.DisableModules()
    view = build_view()

    server = get_server()
    state, ctrl = server.state, server.controller

    # Initialize filter registry with UUID keys (replaces class-level _filters dict)
    state.filters = {}  # {uuid_hex: {"type": str, "proxy": object, "params": dict}}

    html_view = paraview.VtkRemoteView(view)

    layout = SinglePageLayout(server)
    layout.title.set_text("CFD Viewer — trame")

    with layout.content:
        vuetify.VContainer(
            fluid=True,
            classes="pa-0 fill-height",
            children=[html_view]
        )

    server.start(
        port=args.port,
        host="0.0.0.0",
        open_browser=False,
        show_connection_info=False,
    )


if __name__ == "__main__":
    main()
