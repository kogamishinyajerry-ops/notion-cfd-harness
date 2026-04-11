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

# Placeholder — populate with @exportRpc protocol classes in Phase 20+.
