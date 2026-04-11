# Phase 15: ParaView Web Server Integration - Research

**Researched:** 2026-04-11
**Domain:** ParaView Web Python launcher (`pvpython`) + Docker subprocess lifecycle management
**Confidence:** MEDIUM (official docs confirmed launcher API and arguments; Docker image content needs in-situ verification)

## Summary

ParaView Web is a VTK/ParaView visualization framework that exposes rendering via WebSocket using a Python launcher and JavaScript client. PV-01 requires launching `pvpython` (the ParaView Python interpreter) as a subprocess from the FastAPI server, managing session lifecycle (launch on request, idle shutdown at 30 min), and exposing a WebSocket connection for the frontend JS client. The architecture follows a **sidecar Docker container pattern** -- a long-running container per session, managed via REST API calls from FastAPI, mirroring the existing `OpenFOAMDockerExecutor` pattern. The ParaView Web Python launcher (`vtk.web.launcher`) takes a JSON config file and exposes a session management REST API (create/query/delete) for the visualization process lifecycle.

**Primary recommendation:** Build a `ParaviewWebManager` service (mirroring `OpenFOAMDockerExecutor`) that launches ParaView Web as a detached Docker container with the `openfoam/openfoam10-paraview510` image (already in use), manages a REST-based session lifecycle, tracks idle time in the FastAPI server, and issues `DELETE /session/{id}` to shut down cleanly.

## Phase Requirements (from REQUIREMENTS.md)

| ID | Requirement | Research Support |
|----|-------------|------------------|
| PV-01.1 | `pvpython` launcher is launchable as a subprocess from the API server | Launcher command: `pvpython lib/site-packages/vtk/web/launcher.py config.json` with JSON config; launched via `asyncio.create_subprocess_exec` in detached Docker |
| PV-01.2 | Lifecycle: launch on first viewer request, shutdown after configurable idle timeout (default 30 min) | SessionManager REST API: POST to create, GET to query, DELETE to stop; FastAPI tracks last activity timestamp |
| PV-01.3 | Session configurable for port (default 8081); no port conflicts with existing services | `resources` config with `port_range`; port 8080 reserved for dashboard; dynamic allocation from range [8081, 8090] |
| PV-01.4 | Each session scoped to a specific job result directory | `--data /case` Docker volume mount (read-only `:ro`) passes case directory to ParaView |
| PV-01.5 | Graceful failure if ParaView Web not installed or fails to start | `docker image inspect` before launch; subprocess exit code check; 10s startup timeout with clear error messages |

## User Constraints (from CONTEXT.md)

*No CONTEXT.md found for this phase. All decisions are open for research-driven recommendation.*

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `openfoam/openfoam10-paraview510` | latest (Docker image, already in use) | ParaView + OpenFOAM reader in Docker | Already in project Docker cache; includes `pvpython` + `vtk.web.launcher` + OpenFOAM reader |
| ParaViewWeb Python launcher | v3.2.21 (part of paraviewweb package in image) | Session lifecycle management via REST API | `vtk.web.launcher` module handles port allocation, process start/stop |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.create_subprocess_exec` | stdlib | Launch Docker container from FastAPI | All process launches in API server |
| `subprocess.DEVNULL` | stdlib | Suppress noisy Docker logs in container stdout | Container stdout not needed by API server |

### NOT Using (diverging from STACK.md recommendation of trame)
> **NOTE:** STACK.md recommends `trame>=3.10.0` as the backend. REQUIREMENTS.md PV-01 explicitly requires `pvpython` launcher (ParaView Web), not trame. These are different frameworks:
> - **trame**: Python web framework with `trame.server` CLI; pure Python server
> - **ParaView Web**: Uses `pvpython` + `vtk.web.launcher`; separate session manager process
> - The decision to use ParaView Web over trame was explicitly made in REQUIREMENTS.md ("ParaView Web (not trame) for v1.4.0")
> - Future migration to trame is tracked in the Deferred Ideas section

---

## Architecture Patterns

### Recommended Project Structure
```
api_server/
├── services/
│   └── paraview_web_manager.py   # ParaviewWebManager: session lifecycle, idle tracking
├── routers/
│   └── visualization.py           # REST endpoints: POST /visualization/launch, GET /status, POST /shutdown
└── config.py                      # Add PARAVIEW_WEB_PORT_RANGE, PARAVIEW_WEB_IDLE_TIMEOUT
```

### Pattern 1: Sidecar Docker Container (Session-Per-Job)
**What:** One long-running Docker container per ParaView Web session, not embedded in FastAPI process.
**When to use:** Every time a user requests the 3D viewer for a specific job result.
**Why not embedded:** ParaView Web's event loop is not asyncio-compatible with uvicorn; GPU resources need isolation.

**Example lifecycle:**
```python
# 1. Launch (FastAPI POST /visualization/launch {job_id, case_dir})
#    - Write config JSON with port, authKey, data directory
#    - docker run -d --name pvweb-{session_id} -v {case_dir}:/data:ro -p {port}:9000
#    - Container starts ParaView Web launcher in background
#    - Launcher listens on port 9000 inside container (mapped to external {port})

# 2. Connect (frontend)
#    - JS client calls GET /visualization/{session_id}/connect
#    - FastAPI queries launcher REST API for sessionURL + secret
#    - Returns { sessionURL: "ws://host:{port}/ws", secret: "..." }
#    - Frontend connects WebSocket directly to ParaView Web port

# 3. Idle shutdown (FastAPI background task)
#    - Track last WebSocket activity per session (via heartbeat or proxy)
#    - After 30 min idle: POST /visualization/{session_id}/shutdown
#    - FastAPI calls launcher DELETE /session/{id} OR docker kill

# 4. Explicit shutdown (user navigates away)
#    - Frontend calls POST /visualization/{session_id}/shutdown
#    - Same cleanup as idle shutdown
```

### Pattern 2: ParaView Web Launcher JSON Config
**Source:** [ParaViewWeb Python Launcher Docs](https://kitware.github.io/paraviewweb/docs/python_launcher.html) [HIGH confidence]

```json
{
  "host": "0.0.0.0",
  "port": 9000,
  "endpoint": "/paraview",
  "sessionURL": "ws://${host}:${port}/ws",
  "timeout": 10,
  "log_dir": "/tmp/paraview-logs",
  "fields": ["sessionURL", "secret", "id"],
  "resources": [
    { "host": "localhost", "port_range": [8081, 8090] }
  ],
  "apps": {
    "visualizer": {
      "cmd": [
        "${python_exec}",
        "-dr",
        "${vtkjs_path}/server/pvw-visualizer.py",
        "--port", "${port}",
        "--data", "/data",
        "--authKey", "${secret}",
        "-f"
      ],
      "ready_line": "Starting factory"
    }
  }
}
```

**Substitute variables:**
- `${python_exec}` = `pvpython`
- `${vtkjs_path}` = path to vtk web scripts in Docker image
- `${port}` = allocated port from range
- `${secret}` = session auth key
- `${host}` = container host

### Pattern 3: FastAPI Subprocess Management
**Source:** Project pattern from `OpenFOAMDockerExecutor._run_solver_streaming` [HIGH confidence - existing code]

```python
async def _launch_container(self, session_id: str, case_dir: Path, port: int) -> str:
    docker_binary = self._docker_binary()
    config_path = self._write_launcher_config(session_id, port)

    proc = await asyncio.create_subprocess_exec(
        docker_binary,
        "run",
        "-d",
        "--name", f"pvweb-{session_id}",
        "-v", f"{case_dir.resolve()}:/data:ro",
        "-p", f"{port}:9000",
        "--entrypoint", "pvpython",
        self.image,
        "lib/site-packages/vtk/web/launcher.py",
        config_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    container_id_bytes = await proc.stdout.readline()
    return container_id_bytes.decode().strip()
```

### Pattern 4: Session Activity Tracking (Idle Timeout)
**What:** In-memory dict mapping `session_id -> last_activity_timestamp`.
**When to use:** To implement 30-minute idle shutdown.
**How:** Each WebSocket frame forwarded through FastAPI proxy (or a heartbeat REST call every 60s from frontend) updates the timestamp. A background `asyncio` task runs every 60s, checks all sessions, and shuts down those idle > 30 min.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session management REST API | Custom HTTP server for ParaView lifecycle | ParaView Web's built-in `vtk.web.launcher` REST API | Handles port allocation, process start/stop, ready detection |
| WebSocket protocol for ParaView rendering | Custom WebSocket frame format | ParaView Web's `SmartConnect` JS client + `vtk.web` protocol | Complex VTK rendering protocol; already implemented |
| Port allocation for concurrent sessions | Hardcoded port or random port | ParaView Web's `resources.port_range` config | Handles conflicts, returns available port |
| Idle timeout | SIGAR/x System monitoring | FastAPI in-memory timestamp + asyncio background task | Already in-process, no extra deps |

---

## Common Pitfalls

### Pitfall 1: Using `--rm` on Long-Running Containers
**What goes wrong:** Container is removed immediately on exit; no chance to collect exit code or logs.
**Why it happens:** The `OpenFOAMDockerExecutor` uses `--rm` for short-lived solver containers. ParaView Web containers are long-running.
**How to avoid:** Use `--name` (for clean `docker kill`) instead of `--rm`. On shutdown, explicitly `docker kill` or call launcher DELETE API.
**Warning signs:** `docker ps` shows no trace of the container after startup.

### Pitfall 2: ParaView Web Image Missing `vtk.web.launcher`
**What goes wrong:** Container starts but `pvpython lib/site-packages/vtk/web/launcher.py` fails with "module not found".
**Why it happens:** The `openfoam/openfoam10-paraview510` image includes ParaView but the ParaViewWeb Python package may not be installed at that path.
**How to avoid:** Before claiming PV-01 complete, verify the launcher module exists at that path inside the container:
  ```bash
  docker run --rm openfoam/openfoam10-paraview510 pvpython -c "import vtk.web.launcher; print('found')"
  ```
**This is the #1 verification item before any implementation begins.**

### Pitfall 3: macOS Docker No GPU Support for ParaView Rendering
**What goes wrong:** ParaView uses EGL/OSMesa for offscreen rendering inside Docker. On macOS (Apple Silicon), Docker uses QEMU emulation for `linux/amd64` images, which may lack GPU/EGL support.
**Why it happens:** ParaView's VTK rendering needs GPU access. Without `--gpus all`, the container falls back to software rendering (OSMesa), which is very slow.
**How to avoid:** Test rendering startup in container; if logs show "无法创建渲染上下文", fall back to OSMesa or note as a known limitation for macOS dev. On Linux with NVIDIA, use `--gpus all`.

### Pitfall 4: Port Conflict with Dashboard (Port 8080)
**What goes wrong:** ParaView Web starts on 8081 but the Vite proxy also uses 8080; WebSocket proxy routing fails silently.
**Why it happens:** Two services both expecting port 8080 on the host.
**How to avoid:** Use port 8081+ for ParaView Web (per PV-01.3). Document in `config.py` that port 8080 is reserved for dashboard.

### Pitfall 5: OpenFOAMReader Not Loading Case Directory
**What goes wrong:** `OpenFOAMReader` fails silently or reads zero fields.
**Why it happens:** OpenFOAM case directory needs `case.foam` file or a `polyMesh` directory. The path must end with the case directory, not a specific file.
**How to avoid:** Mount the case directory at `/data` (not `/data/case.foam`) and ensure `case.foam` exists. Validate before launching the viewer.

---

## Code Examples

### ParaView Web Launcher Config Generation
```python
# api_server/services/paraview_web_manager.py
import json
import uuid

def generate_launcher_config(session_id: str, port: int, case_dir: str, secret: str) -> dict:
    """Generate ParaView Web launcher config for a session."""
    return {
        "host": "0.0.0.0",
        "port": 9000,  # Internal container port
        "endpoint": f"/paraview/{session_id}",
        "sessionURL": f"ws://${{host}}:{port}/ws",
        "timeout": 10,
        "log_dir": f"/tmp/pvweb-{session_id}",
        "fields": ["sessionURL", "secret", "id"],
        "resources": [
            {"host": "localhost", "port_range": [port, port]}
        ],
        "apps": {
            "openfoam_viewer": {
                "cmd": [
                    "pvpython",
                    "-dr",
                    "lib/site-packages/vtk/web/launcher.py",
                    "--port", str(port),
                    "--data", "/data",
                    "--authKey", secret,
                    "-f"
                ],
                "ready_line": "Starting factory"
            }
        }
    }
```
**Source:** [ParaViewWeb Python Launcher Docs](https://kitware.github.io/paraviewweb/docs/python_launcher.html) [HIGH]

### ParaView Web JavaScript Client Connection
```javascript
// Dashboard/src/components/ParaViewViewer.tsx
import { SmartConnect } from '@kitware/paraview-web';  // or raw WebSocket if using native

const config = {
    sessionManagerURL: 'http://localhost:8081/paraview',
    application: 'loader'
};

const smartConnect = new SmartConnect(config);
smartConnect.onConnectionReady((session) => {
    session.renderView(canvasRef.current, { viewId: 'main' });
});
smartConnect.onConnectionError((error) => {
    console.error('ParaView Web connection failed:', error);
});
```
**Source:** [ParaViewWeb Launcher API Docs](https://kitware.github.io/paraviewweb/docs/launcher_api.html) [HIGH]

### FastAPI Session Shutdown
```python
# api_server/services/paraview_web_manager.py
async def shutdown_session(self, session_id: str) -> None:
    """Stop a ParaView Web session via launcher DELETE or docker kill."""
    if session_id not in self._sessions:
        return

    session = self._sessions[session_id]

    # Try graceful shutdown via launcher REST API first
    try:
        async with self._http_client as client:
            await client.delete(f"{session.launcher_url}/session/{session_id}")
    except Exception:
        pass  # Fall back to docker kill

    # Docker kill as fallback
    docker_binary = shutil.which("docker")
    await asyncio.create_subprocess_exec(
        docker_binary, "kill", f"pvweb-{session_id}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )

    del self._sessions[session_id]
```
**Source:** Project pattern from `OpenFOAMDockerExecutor._run_solver_streaming` [HIGH]

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ParaView Web with Java server | ParaView Web Python-only launcher | ~2019 | Removed Glassfish dependency; pure Python server |
| ParaViewWeb v3.x | trame (vtk.js-based) | v3.2.21 (2021) maintenance | trame is the active successor; ParaView Web is in maintenance |
| Custom WebSocket renderer | ParaView Web SmartConnect JS client | ParaView Web 3.x | Standardized client-server protocol |

**Deprecated/outdated:**
- **Java-based ParaViewWeb server** (removed ~2019): Do not use `paraview-web-server` Java package
- **ParaView Glance for large CFD cases**: Only for pre-exported VTKJS scenes; OpenFOAM cases too large
- **Client-side VTK.js direct rendering**: Memory/performance issues with large meshes; server-side rendering required

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `openfoam/openfoam10-paraview510` image includes `vtk.web.launcher` at `lib/site-packages/vtk/web/launcher.py` | Standard Stack, Pitfall 2 | Container starts but launcher module not found; must use different image or install paraviewweb via pip |
| A2 | ParaView Web JS client (`SmartConnect`) is available as an npm package (`@kitware/paraview-web` or similar) | Code Examples | Frontend cannot connect to ParaView Web server; may need alternative connection method |
| A3 | Docker on macOS (Apple Silicon) can run ParaView rendering via EGL/OSMesa in container | Common Pitfalls | Rendering fails or is extremely slow on macOS dev machines |
| A4 | The `OpenFOAMReader` proxy can load a case directory mounted at `/data` inside the container | Code Examples | Case loads but no geometry visible; requires different reader configuration |

**If A1 proves wrong**, the alternative is to install `paraviewweb` pip package in a custom Dockerfile:
```dockerfile
FROM python:3.10-slim
RUN pip install paraviewweb vtk
```

---

## Open Questions

1. **Which exact path inside `openfoam/openfoam10-paraview510` contains `vtk.web.launcher`?**
   - What we know: The image includes ParaView 5.10 + OpenFOAM 10. ParaView includes VTK, which includes web components.
   - What's unclear: The exact filesystem path to the launcher module.
   - Recommendation: Verify with `docker run --rm openfoam/openfoam10-paraview510 find / -name "launcher.py" 2>/dev/null` before implementation.

2. **Is `paraview-web` npm package available and compatible with ParaView Web v3.2.21 server?**
   - What we know: `SmartConnect` is the JS client for ParaView Web servers.
   - What's unclear: The exact npm package name and whether it's still maintained.
   - Recommendation: Check npm for `@kitware/paraview-web` or `paraview-web` package.

3. **How does the frontend ParaView Web JS client know the session's WebSocket URL?**
   - What we know: After POST /visualization/launch, FastAPI returns session info including `sessionURL` and `secret`.
   - What's unclear: Does the frontend poll a FastAPI endpoint for connection info, or does the frontend go directly to the ParaView Web launcher REST API?
   - Recommendation: Frontend calls `GET /visualization/{session_id}/connect` on FastAPI; FastAPI proxies to ParaView Web launcher's GET endpoint.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | ParaView Web container runtime | yes | 29.2.1 | None (blocks PV-01) |
| `openfoam/openfoam10-paraview510` | ParaView + OpenFOAM reader | not locally cached | latest | `kitware/trame:py3.10-glvnd` (different image, less OpenFOAM support) |
| `pvpython` | Launcher interpreter | no (not in PATH) | — | Inside Docker container only |
| GPU (NVIDIA) | ParaView EGL rendering | unknown | — | OSMesa software rendering (slow) |
| macOS (Apple Silicon) | Development platform | yes | Darwin 25.3.0 | Linux VM for rendering tests |

**Missing dependencies with no fallback:**
- **GPU rendering on macOS**: No viable fallback for interactive 3D rendering in Docker on Apple Silicon. Recommend Linux rendering validation environment.

**Missing dependencies with fallback:**
- **`openfoam/openfoam10-paraview510` image**: Will be pulled on first launch if not cached. No action needed if Docker daemon is running.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing project standard) |
| Config file | `pytest.ini` or `pyproject.toml` (existing) |
| Quick run command | `pytest tests/api_tests/ -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PV-01.1 | `pvpython` launcher starts as subprocess | integration | `pytest tests/phase15/ -x` (new) | no |
| PV-01.2 | Idle timeout kills process after 30 min | unit/integration | Mock timer; assert container killed | no |
| PV-01.3 | Port configurable; default 8081; no conflicts | unit | `pytest tests/phase15/test_port_allocation.py` | no |
| PV-01.4 | Session scoped to case directory | integration | Mount fake case; verify inside container | no |
| PV-01.5 | Graceful failure if ParaView Web not installed | unit | Mock docker failure; assert error message | no |

### Wave 0 Gaps
- [ ] `tests/phase15/test_paraview_web_manager.py` — tests for `ParaviewWebManager` class
- [ ] `tests/phase15/test_visualization_router.py` — tests for FastAPI visualization endpoints
- [ ] `tests/phase15/conftest.py` — fixtures for mock Docker, mock launcher config
- [ ] Framework install: No new framework needed (pytest already in project)

*(No existing test infrastructure covers PV-01 requirements)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | Each session scoped to a specific job's case directory (`:ro` mount); session authKey prevents unauthorized access |
| V5 Input Validation | yes | case_dir path must be validated as absolute, existing, inside allowed directories; session_id must be UUID |
| V3 Session Management | yes | Session authKey generated per session; session deleted on shutdown |

### Known Threat Patterns for ParaView Web + Docker

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via case_dir | Tampering | Validate `case_dir` is absolute and within allowed roots before mounting |
| Unauthorized session access | Information Disclosure | Generate cryptographically random authKey per session; do not expose launcher port directly |
| Container escape (if compromised) | Elevation | Run container as non-root user (already done in OpenFOAMDockerExecutor) |
| Port conflict causing DoS | Denial of Service | Use port range allocation; fail with clear message if no port available |

---

## Sources

### Primary (HIGH confidence)
- [ParaViewWeb Python Launcher Docs](https://kitware.github.io/paraviewweb/docs/python_launcher.html) — launcher command, config file format, application cmd args
- [ParaViewWeb Launcher API Docs](https://kitware.github.io/paraviewweb/docs/launcher_api.html) — REST API (POST/GET/DELETE session management), SmartConnect JS client config
- [ParaViewWeb Launching Examples](https://kitware.github.io/paraviewweb/docs/launching_examples.html) — `${python_exec} -dr ${path}/server/pvw-visualizer.py --port ${port} --data ${dataDir} --authKey ${secret} -f` command format
- Project: `openfoam_docker.py` — existing Docker executor pattern to mirror [HIGH]

### Secondary (MEDIUM confidence)
- [ParaViewWeb API Index](https://kitware.github.io/paraviewweb/api/) — confirms SmartConnect JS client, WebSocket protocol
- [ParaViewWeb GitHub README](https://github.com/Kitware/ParaViewWeb) — v3.2.21 in maintenance mode; trame is successor
- [ARCHITECTURE.md](/.planning/research/ARCHITECTURE.md) — sidecar pattern recommendation, iframe vs direct WS comparison
- [STACK.md](/.planning/research/STACK.md) — trame recommendation (note: superseded by REQUIREMENTS.md decision for ParaView Web)

### Tertiary (LOW confidence — needs in-situ verification)
- [ASSUMED] `openfoam/openfoam10-paraview510` includes `vtk.web.launcher` at expected path
- [ASSUMED] ParaView Web JS client npm package name and availability
- [ASSUMED] OpenFOAMReader proxy configuration inside Docker container

---

## Metadata

**Confidence breakdown:**
- Standard Stack: MEDIUM — official docs confirmed launcher API; Docker image content unverified
- Architecture: MEDIUM-HIGH — sidecar pattern confirmed in docs; specific Docker image path needs verification
- Pitfalls: MEDIUM — common Docker/container pitfalls documented; ParaView-specific pitfalls need implementation to confirm

**Research date:** 2026-04-11
**Valid until:** 2026-05-11 (60 days; ParaView Web v3.2.21 is stable/maintenance, not changing rapidly)
