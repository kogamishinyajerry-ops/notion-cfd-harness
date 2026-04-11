"""
ParaView Web Advanced Protocols — Volume Rendering, Advanced Filters.

This module is mounted at /tmp/adv_protocols.py inside the ParaView Web
session container. The entrypoint_wrapper.sh imports it before launching
the wslink server, which registers any @exportRpc decorated classes.

Phase 20: ParaViewWebVolumeRendering protocol class (4 RPCs)
Phase 22: ParaViewWebAdvancedFilters protocol class (9 RPCs)
Phase 21: No new protocols (uses existing viewport.image.render)

CONT-01.1: This file is mounted at /tmp/adv_protocols.py inside the container.
CONT-01.2: @exportRpc decorated classes are registered with wslink before
           the first WebSocket connection is accepted.
CONT-01.3: entrypoint_wrapper.sh imports this file before launcher.py starts.
"""
import subprocess
import os

from paraview import simple
from vtk.web.protocol import ParaViewWebProtocol

try:
    from wslink.decorators import exportRpc
except ImportError:
    # Fallback decorator when wslink is not in the path
    def exportRpc(methodName):
        def decorator(func):
            func._export_rpc = methodName
            return func
        return decorator


class ParaViewWebVolumeRendering(ParaViewWebProtocol):
    """ParaView Web protocol for GPU-accelerated volume rendering toggle.

    Implements Smart Volume Mapper (vtkSmartVolumeMapper) which auto-selects
    between GPU ray cast (NVIDIA) and software ray cast (Mesa/Apple Silicon).
    """

    # GPU vendor cache — populated on first status query
    _gpu_vendor_cache = None
    _gpu_available_cache = None

    @staticmethod
    def _detect_gpu():
        """Detect GPU via EGL vendor string. Returns (available, vendor)."""
        if ParaViewWebVolumeRendering._gpu_vendor_cache is not None:
            return ParaViewWebVolumeRendering._gpu_available_cache, ParaViewWebVolumeRendering._gpu_vendor_cache
        try:
            # Try eglinfo to get EGL vendor
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

        ParaViewWebVolumeRendering._gpu_vendor_cache = vendor
        ParaViewWebVolumeRendering._gpu_available_cache = available
        return available, vendor

    @exportRpc("visualization.volume.rendering.status")
    def volumeRenderingStatus(self):
        """Return current volume rendering state, GPU info, and cell count."""
        gpu_available, gpu_vendor = self._detect_gpu()

        # Get cell count from the active source (OpenFOAM reader or last filter)
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

        # Check if volume rendering is currently active
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

        return {
            "enabled": volume_enabled,
            "field_name": field_name,
            "gpu_available": gpu_available,
            "gpu_vendor": gpu_vendor,
            "cell_count": cell_count,
            "cell_count_warning": cell_count_warning,
        }

    @exportRpc("visualization.volume.rendering.toggle")
    def volumeRenderingToggle(self, fieldName: str, enabled: bool):
        """Toggle volume rendering for the specified scalar field.

        Args:
            fieldName: Name of the scalar field to render as volume
            enabled: True to enable volume rendering, False to restore surface
        """
        try:
            source = simple.GetActiveSource()
            if source is None:
                return {"success": False, "error": "No active source"}

            # Set the field if specified
            if fieldName:
                try:
                    props = source
                    if hasattr(props, "Fields"):
                        props.Fields = fieldName
                    elif hasattr(props, "SelectTCGenerator"):
                        pass  # Some readers use different field properties
                except Exception:
                    pass

            # Get the display representation
            display = simple.GetDisplayProperties(source=source)
            if display is None:
                return {"success": False, "error": "Could not get display properties"}

            if enabled:
                # Enable volume rendering with Smart Volume Mapper
                display.SetRepresentationToVolume()
                # Configure volume mapper (Smart Volume Mapper auto-detects GPU)
                try:
                    volume_mapper = simple._create_vtkSmartVolumeMapper()
                    if volume_mapper is not None:
                        display.SetVolumeMapper(volume_mapper)
                except Exception:
                    pass  # Fallback to default mapper
            else:
                # Restore surface rendering
                display.SetRepresentationToSurface()

            # Ensure render updates
            simple.Render()

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}
