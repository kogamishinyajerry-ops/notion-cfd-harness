#!/usr/bin/env pvpython
"""
trame_server.py — Minimal ParaView Web to trame migration skeleton.

Replaces:
  - entrypoint_wrapper.sh (container entrypoint)
  - adv_protocols.py (@exportRpc protocol classes)
  - launcher.py (vtk.web.launcher multi-process launcher)

Serves a minimal ParaView sphere via VtkRemoteView at the allocated port.
All ParaView operations (OpenFOAMReader, filters, volume rendering) will be
added in Phase 24.

Usage:
    pvpython /trame_server.py --port 9000
    pvpython /trame_server.py --port 9000 --data /data/case.foam
"""

import argparse

from paraview import simple
from trame.app import get_server
from trame.ui.vuetify import SinglePageLayout
from trame.html import paraview
from trame.widgets import vuetify


def build_view():
    """Create a minimal ParaView scene with a sphere.

    In Phase 24 this will be replaced with OpenFOAM case loading.
    For now, use a simple Sphere source as the minimal geometry verification.
    """
    # Create a sphere source — minimal geometry to verify ParaView + trame wiring
    sphere = simple.Sphere()
    sphere.ThetaResolution = 16
    sphere.PhiResolution = 16

    # Get the render view
    view = simple.GetRenderView()
    view.CenterAxesVisibility = 0  # Hide axes for cleaner look

    # Render the sphere
    simple.Render()
    return view


def main():
    parser = argparse.ArgumentParser(description="trame CFD Viewer Server")
    parser.add_argument("--port", type=int, default=9000,
                        help="Port to serve on (default: 9000)")
    parser.add_argument("--data", default=None,
                        help="Path to OpenFOAM case directory (future Phase 24)")
    args = parser.parse_args()

    # Initialize ParaView
    simple.DisableModules()

    # Build the ParaView scene
    view = build_view()

    # Create trame server
    server = get_server()
    state, ctrl = server.state, server.controller

    # Create the ParaView remote view (server-side rendering, image streamed to client)
    html_view = paraview.VtkRemoteView(view)

    # Set up the Vuetify UI layout
    layout = SinglePageLayout(server)
    layout.title.set_text("CFD Viewer — trame skeleton")

    # Main content area: contains only the 3D viewport
    with layout.content:
        vuetify.VContainer(
            fluid=True,
            classes="pa-0 fill-height",
            children=[html_view]
        )

    # Start the server — blocking call
    # open_browser=False: containerized environment has no browser
    # show_connection_info=False: reduce log noise
    server.start(
        port=args.port,
        host="0.0.0.0",
        open_browser=False,
        show_connection_info=False,
    )


if __name__ == "__main__":
    main()
