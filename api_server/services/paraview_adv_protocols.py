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


class ParaViewWebAdvancedFilters(ParaViewWebProtocol):
    """ParaView Web protocol for advanced filters: Clip, Contour, StreamTracer.

    Tracks filter proxy IDs in a class-level dict so they can be deleted by ID.
    All filter operations call simple.Render() + InvokeEvent to push viewport updates.
    """

    # Filter registry: filterId (int) -> {"type": str, "proxy": object}
    _filters = {}

    @exportRpc("visualization.filters.clip.create")
    def clipFilterCreate(self, insideOut: bool, scalarValue: float):
        """Create a scalar Clip filter on the active source.

        Args:
            insideOut: If True, clip everything outside the scalar threshold
            scalarValue: Scalar threshold value
        """
        try:
            source = simple.GetActiveSource()
            if source is None:
                return {"success": False, "error": "No active source"}

            # Validate inputs
            if not isinstance(scalarValue, (int, float)) or not (-1e10 < scalarValue < 1e10):
                return {"success": False, "error": "Invalid scalarValue"}

            # Create clip filter
            clip = simple.Clip(Input=source)
            clip.ClipType = "Scalar"
            clip.Scalar = scalarValue
            clip.InsideOut = insideOut

            # Register filter
            filter_id = id(clip)
            ParaViewWebAdvancedFilters._filters[filter_id] = {"type": "clip", "proxy": clip}

            # Push viewport update
            simple.Render()
            self._app.SMApplication.InvokeEvent("UpdateEvent", ())

            return {"success": True, "filterId": filter_id, "proxyId": filter_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @exportRpc("visualization.filters.contour.create")
    def contourFilterCreate(self, isovalues: list):
        """Create an isosurface Contour filter on the active source.

        Args:
            isovalues: List of scalar isovalue thresholds
        """
        try:
            source = simple.GetActiveSource()
            if source is None:
                return {"success": False, "error": "No active source"}

            # Validate: max 20 isovalues
            if not isinstance(isovalues, list) or len(isovalues) > 20:
                return {"success": False, "error": "isovalues must be a list with at most 20 values"}
            for v in isovalues:
                if not isinstance(v, (int, float)) or not (-1e10 < v < 1e10):
                    return {"success": False, "error": "All isovalues must be finite numbers"}

            # Create contour filter
            contour = simple.Contour(Input=source)
            contour.ContourBy = ["POINTS", " scalars"]
            contour.Isosurfaces = isovalues

            # Register filter
            filter_id = id(contour)
            ParaViewWebAdvancedFilters._filters[filter_id] = {"type": "contour", "proxy": contour}

            # Push viewport update
            simple.Render()
            self._app.SMApplication.InvokeEvent("UpdateEvent", ())

            return {"success": True, "filterId": filter_id, "proxyId": filter_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @exportRpc("visualization.filters.streamtracer.create")
    def streamTracerFilterCreate(self, integrationDirection: str, maxSteps: int):
        """Create a StreamTracer filter using velocity field U.

        Args:
            integrationDirection: "FORWARD" or "BACKWARD"
            maxSteps: Maximum number of integration steps (cap at 10000)
        """
        try:
            source = simple.GetActiveSource()
            if source is None:
                return {"success": False, "error": "No active source"}

            # Validate inputs
            if integrationDirection not in ("FORWARD", "BACKWARD"):
                return {"success": False, "error": "integrationDirection must be FORWARD or BACKWARD"}
            if not isinstance(maxSteps, int) or maxSteps <= 0:
                return {"success": False, "error": "maxSteps must be a positive integer"}
            maxSteps = min(maxSteps, 10000)  # Cap at 10000

            # Create stream tracer
            streamtracer = simple.StreamTracer(Input=source)
            streamtracer.Vectors = ["POINTS", "U"]  # Velocity field U
            streamtracer.IntegrationDirection = integrationDirection
            streamtracer.MaximumSteps = maxSteps
            streamtracer.InitialStepLength = 0.1
            streamtracer.MinimumStepLength = 0.001

            # Register filter
            filter_id = id(streamtracer)
            ParaViewWebAdvancedFilters._filters[filter_id] = {"type": "streamtracer", "proxy": streamtracer}

            # Push viewport update
            simple.Render()
            self._app.SMApplication.InvokeEvent("UpdateEvent", ())

            return {"success": True, "filterId": filter_id, "proxyId": filter_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @exportRpc("visualization.filters.delete")
    def filterDelete(self, filterId: int):
        """Delete a filter by its proxy ID.

        Args:
            filterId: The filter ID returned from a create RPC
        """
        try:
            filter_info = ParaViewWebAdvancedFilters._filters.get(filterId)
            if filter_info is None:
                return {"success": False, "error": f"Filter {filterId} not found"}

            filter_proxy = filter_info["proxy"]
            simple.Delete(filter_proxy)

            # Remove from registry
            del ParaViewWebAdvancedFilters._filters[filterId]

            # Push viewport update
            simple.Render()
            self._app.SMApplication.InvokeEvent("UpdateEvent", ())

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @exportRpc("visualization.filters.list")
    def filterList(self):
        """Return all active filters with their types and parameters."""
        filters = []
        for filter_id, info in ParaViewWebAdvancedFilters._filters.items():
            proxy = info["proxy"]
            params = {}
            ftype = info["type"]
            if ftype == "clip":
                params = {
                    "insideOut": bool(getattr(proxy, "InsideOut", False)),
                    "scalarValue": float(getattr(proxy, "Scalar", 0)),
                }
            elif ftype == "contour":
                params = {
                    "isovalues": list(getattr(proxy, "Isosurfaces", [])),
                }
            elif ftype == "streamtracer":
                params = {
                    "integrationDirection": str(getattr(proxy, "IntegrationDirection", "FORWARD")),
                    "maxSteps": int(getattr(proxy, "MaximumSteps", 1000)),
                }
            filters.append({
                "id": filter_id,
                "type": ftype,
                "parameters": params,
            })
        return {"filters": filters}
