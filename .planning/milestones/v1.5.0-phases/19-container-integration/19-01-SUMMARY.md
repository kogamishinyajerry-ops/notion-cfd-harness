---
phase: "19-container-integration"
plan: "01"
subsystem: "container-integration"
tags:
  - "paraview-web"
  - "docker"
  - "protocol-registration"
  - "wslink"
dependency_graph:
  requires: []
  provides:
    - "CONT-01.1"
    - "CONT-01.2"
    - "CONT-01.3"
    - "CONT-01.4"
  affects:
    - "Phase 20 (Volume Rendering)"
    - "Phase 21 (Screenshot Export)"
    - "Phase 22 (Advanced Filters)"
tech_stack:
  added:
    - "Dockerfile (openfoam/openfoam10-paraview510 base, entrypoint_wrapper.sh baked in)"
    - "entrypoint_wrapper.sh (PID 1 wrapper, pvpython import, exec replacement)"
    - "paraview_adv_protocols.py (placeholder, Phase 20+ populate)"
  patterns:
    - "PID 1 entrypoint wrapper for import ordering"
    - "Read-only volume mount for host-sourced protocol file"
    - "On-demand Docker image build at session launch"
key_files:
  created:
    - "Dockerfile"
    - "entrypoint_wrapper.sh"
    - "api_server/services/paraview_adv_protocols.py"
  modified:
    - "api_server/services/paraview_web_launcher.py"
decisions:
  - "Used PID 1 entrypoint wrapper (exec form) instead of CMD override — allows import before wslink init"
  - "Build custom image on-demand at launch_session() time — avoids pre-build requirement"
  - "adv_protocols.py mounted read-only (:ro) — host path hardcoded as project absolute path"
  - "ADV_PROTOCOL_ERROR echoed to stderr and propagated via container exit code 1"
metrics:
  duration: "task-level commits: 4"
  completed: "2026-04-11"
---

# Phase 19 Plan 01: Container Integration Summary

## One-liner

PID 1 entrypoint wrapper that imports `adv_protocols.py` before exec'ing the wslink server, with on-demand custom Docker image build.

## What Was Done

### Task 1: Dockerfile

Created `/Users/Zhuanz/Desktop/notion-cfd-harness/Dockerfile` — 11 lines, exec-form `ENTRYPOINT ["/entrypoint_wrapper.sh"]` baked in at build time.

### Task 2: entrypoint_wrapper.sh

Created `/Users/Zhuanz/Desktop/notion-cfd-harness/entrypoint_wrapper.sh` — 26 lines, executable. Sequence:

1. Checks for `/tmp/adv_protocols.py`
2. Imports via `pvpython -c "import sys; sys.path.insert(0, '/tmp'); import adv_protocols"`
3. On failure: `echo ADV_PROTOCOL_ERROR to stderr`, exits 1
4. On success: `exec "$@"` replaces PID 1 with pvpython

Import ordering is guaranteed: wrapper runs before wslink, exec replaces after.

### Task 3: paraview_web_launcher.py updates

Modified `/Users/Zhuanz/Desktop/notion-cfd-harness/api_server/services/paraview_web_launcher.py`:

- `PARAVIEW_WEB_IMAGE` changed from `openfoam/openfoam10-paraview510` to `cfd-workbench:openfoam-v10`
- Added `build_custom_image()` async method: `docker image inspect` first, skip build if present, else `docker build -t cfd-workbench:openfoam-v10 .` from project root
- Added `self._image_built = False` to `__init__`, called `build_custom_image()` before `_verify_image()` in `launch_session()`
- `_start_container()`: added volume mount `-v .../paraview_adv_protocols.py:/tmp/adv_protocols.py:ro`, changed `--entrypoint pvpython` to `--entrypoint /entrypoint_wrapper.sh`, moved `lib/site-packages/vtkmodules/web/launcher.py /tmp/launcher_config.json` to positional CMD args

### Task 4: paraview_adv_protocols.py placeholder

Created `/Users/Zhuanz/Desktop/notion-cfd-harness/api_server/services/paraview_adv_protocols.py` — 18 lines, empty placeholder with docstring. No import errors when run through `pvpython -c "import sys; sys.path.insert(0, '/tmp'); import adv_protocols"`.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface

| Flag | File | Description |
|------|------|-------------|
| none new | Dockerfile | Standard base image + COPY + ENTRYPOINT |
| none new | entrypoint_wrapper.sh | Set -e guards against silent failures |
| none new | paraview_web_launcher.py | Mount paths use hardcoded project root (not user input) |

## CONT-01 Requirements Addressed

| ID | Requirement | How Addressed |
|----|-------------|---------------|
| CONT-01.1 | File mounted at /tmp/adv_protocols.py | Volume mount in `_start_container`: `/tmp/adv_protocols.py:ro` |
| CONT-01.2 | Protocols registered before first WS connection | entrypoint_wrapper.sh imports before `exec "$@"`, import ordering guaranteed |
| CONT-01.3 | Wrapper handles import ordering | Script runs as PID 1 via exec form ENTRYPOINT; `exec "$@"` replaces after import |
| CONT-01.4 | Import error surfaced as user-facing error | ADV_PROTOCOL_ERROR to stderr + exit 1; `_wait_for_ready()` detects container crash and surfaces logs |

## Commits

| Hash | Message |
|------|---------|
| 6ef6c17 | feat(19-01): add Dockerfile with entrypoint wrapper for custom ParaView Web image |
| e436895 | feat(19-01): add entrypoint_wrapper.sh for adv_protocols import before wslink start |
| e53adc8 | feat(19-01): wire custom image, adv_protocols mount, and entrypoint wrapper in launcher |
| 0f56994 | feat(19-01): add paraview_adv_protocols.py placeholder for Phase 20+ protocol population |

## Self-Check

All created files exist on disk. All commit hashes found in git log. Plan verification grep commands all pass.
