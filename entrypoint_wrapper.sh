#!/bin/bash
# entrypoint_wrapper.sh — PID 1 inside ParaView Web session containers.
# Imports adv_protocols.py (if present) before starting the wslink server.

set -euo pipefail

PROTOCOLS_FILE="/tmp/adv_protocols.py"

# Attempt to import adv_protocols.py using pvpython.
# This registers @exportRpc decorated classes with wslink's global registry.
if [ -f "$PROTOCOLS_FILE" ]; then
    echo "[entrypoint_wrapper] Found $PROTOCOLS_FILE, importing protocols..."
    # Use pvpython to import so ParaView/Python paths are set up correctly.
    # The import must succeed (rc=0) before we proceed.
    if ! pvpython -c "import sys; sys.path.insert(0, '/tmp'); import adv_protocols; print('adv_protocols imported OK')"; then
        echo "[entrypoint_wrapper] ADV_PROTOCOL_ERROR: failed to import $PROTOCOLS_FILE" >&2
        exit 1
    fi
    echo "[entrypoint_wrapper] Protocols registered with wslink."
else
    echo "[entrypoint_wrapper] $PROTOCOLS_FILE not found — skipping protocol import."
fi

# Exec the original command (e.g., pvpython launcher.py ...).
# exec replaces this shell with pvpython, so wslink starts after import.
exec "$@"
