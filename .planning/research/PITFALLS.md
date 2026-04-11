# Pitfalls Research: ParaView Web to trame Migration

**Domain:** CFD Web Visualization — ParaView Web (wslink) to trame Framework Migration
**Researched:** 2026-04-11
**Confidence:** MEDIUM

> No official ParaView Web-to-trame migration guide exists. ParaViewWeb is officially in maintenance mode (no new features). Kitware directs users to trame. All findings below are synthesized from trame source code, official documentation (trame.readthedocs.io, kitware.github.io/trame), wslink protocol docs, and the ParaViewWeb GitHub README. Confidence is MEDIUM because official migration documentation does not exist and the team has no prior trame experience.

---

## Critical Pitfalls

### Pitfall 1: `@exportRpc` Protocol Classes Have No Direct trame Equivalent

**What goes wrong:**
`ParaViewWebVolumeRendering` and `ParaViewWebAdvancedFilters` (in `paraview_adv_protocols.py`) inherit from `ParaViewWebProtocol` and register RPCs via the `@exportRpc` decorator. In trame, there are no protocol classes and no `@exportRpc`. Every RPC method must be rewritten as either a state-changing method or a server-side callback triggered by client events.

**Why it happens:**
The mental model is inverted. ParaView Web is RPC-centric: the client explicitly calls a named method on a protocol instance. trame is state-centric: the client mutates shared state; the server reacts to state changes via `@state.change` decorators or `ctrl.on_*` lifecycle callbacks. There is no class-level filter registry in trame's equivalent pattern.

**How to avoid:**
- Map every `@exportRpc` method to one of:
  - A `ctrl.on_*` lifecycle callback (for server-initiated logic)
  - A method decorated with `@state.change("varName")` (for reactive state mutations)
  - A plain Python method called from a Vue component's `@click` handler via `server.controller`
- Replace class-level filter registry (`ParaViewWebAdvancedFilters._filters = {}`) with trame `state.filters = {}` — a shared dict that automatically syncs to the client
- Remove all `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` calls (lines 207, 244, 285, 312 in `paraview_adv_protocols.py`) — trame's reactivity handles viewport updates automatically when state mutates
- The `simple.Render()` calls should be retained for some operations but `InvokeEvent` must be removed

**Warning signs:**
- Code search finds `@exportRpc` or `from wslink.decorators import exportRpc` in migrated files
- Filter IDs returned from RPCs do not persist in `state` but in a Python class dict
- `self._app.SMApplication.InvokeEvent` still present after migration

**Phase to address:** Migration phase (Phase 20/22 equivalents)

---

### Pitfall 2: `simple.Render()` + `InvokeEvent` Pattern Breaks

**What goes wrong:**
Both protocol classes call `simple.Render()` followed by `self._app.SMApplication.InvokeEvent("UpdateEvent", ())` to push viewport updates to the client (e.g., lines 206-207 in `paraview_adv_protocols.py`). In trame, there is no `InvokeEvent`. The render/update cycle is managed differently depending on the view type.

**Why it happens:**
ParaViewWeb pushes viewport updates by explicitly invoking the UpdateEvent on the server's application object. trame's `VtkLocalView` widget auto-manages render windows — scene mutations via `simple.*` proxies automatically reflect in the client's rendered view once the render window is configured. There is no equivalent to `InvokeEvent`.

**How to avoid:**
- For `VtkLocalView`: scene mutations via `simple.*` proxies automatically propagate to the client. Explicit `simple.Render()` is still needed for some operations but `InvokeEvent` is replaced by relying on auto-state-push when `state` dict is mutated inside a server method, or calling `server.update()` explicitly
- For `VtkRemoteView`: render is triggered automatically on state change
- Remove all `self._app.SMApplication.InvokeEvent` calls — they raise `AttributeError` in trame context
- Test viewport updates after every filter operation to confirm the scene refreshes

**Warning signs:**
- After filter create/delete, the viewport freezes or shows stale geometry
- `AttributeError: '_Protocol' object has no attribute '_app'` in logs
- `AttributeError: 'NoneType' object has no attribute 'InvokeEvent'`
- `self._app` used anywhere in trame-native code

**Phase to address:** Migration phase (Phase 20/22 equivalents)

---

### Pitfall 3: `ParaviewWebManager` Session/Container Architecture Is Replaced Entirely

**What goes wrong:**
`ParaviewWebManager.launch_session()` in `paraview_web_launcher.py` uses the `vtk.web.launcher` multi-session launcher with a JSON config, Docker sidecar containers per session, port allocation, idle timeout monitoring, and a custom `entrypoint_wrapper.sh` that imports `adv_protocols.py` before launching. trame does not use the ParaView Web launcher at all. The container architecture, port allocation, entrypoint approach, and idle monitoring all need redesign.

**Why it happens:**
trame applications are self-hosted Python apps. There is no `vtk.web.launcher` multi-session manager. Each trame app runs as a single process (or can be scaled via gunicorn/uvicorn). The concept of "named Docker containers per session" does not map to trame's architecture.

**How to avoid:**
- Replace `ParaviewWebManager` with a trame-native session management approach:
  - Option A: Single trame server with `server.start()` using its built-in WebSocket handling (simpler, scales to hundreds of concurrent users via asyncio)
  - Option B: Multiple gunicorn workers with sticky sessions if isolation is required
- Drop the `entrypoint_wrapper.sh` pattern entirely — adv_protocols.py RPCs are replaced by `server.controller` methods
- Remove the Docker image requirement for `vtk.web.launcher` module verification (line 75 in `paraview_web_launcher.py`)
- The `--platform linux/amd64` constraint remains relevant for Apple Silicon (Mesa software rendering), but the Docker container no longer needs to run the ParaView Web launcher
- The `_verify_image()` method and its `pvpython -c "import vtk.web.launcher"` check become unnecessary
- The idle monitor task (`_idle_monitor`, `_shutdown_idle_sessions`) must be replaced with trame's `ctrl.on_server_bind` or a separate async background task

**Warning signs:**
- `Dockerfile` still installs or references `vtk.web.launcher`
- `launch_session()` still tries to run `pvpython ... launcher.py`
- Session containers named `pvweb-{session_id}` still appear in `docker ps` after migration
- `PARAVIEW_WEB_PORT_RANGE_START/END` configuration still used

**Phase to address:** Infrastructure/migration phase (Phase 20)

---

### Pitfall 4: Filter ID (`id(clip)`) Is Not Stable Across Server Restarts

**What goes wrong:**
`paraview_adv_protocols.py` uses `filter_id = id(clip)` (lines 202, 239, 280) as the filter registry key. `id()` returns the Python object's memory address, which is not reproducible across server restarts. If a client caches a filter ID from a previous session and the server restarts, the IDs will mismatch.

**Why it happens:**
In ParaView Web, filter IDs are Python `id()` values returned to the client and stored there. On server restart, new filters get new addresses. The client still holds old IDs from the previous session.

**How to avoid:**
- Generate stable filter IDs using a UUID or incremental integer counter stored in `state`:
  ```python
  from trame.app import get_server
  server = get_server()
  state = server.state
  state._filter_id_counter = 0
  state.filters = {}

  def _next_filter_id():
      state._filter_id_counter += 1
      return f"filter_{state._filter_id_counter}"
  ```
- Client should use the string ID returned by the server, not the `id()` of the Python object
- Add server-side validation: reject filter IDs that are not in `state.filters`

**Warning signs:**
- After server restart, deleting or operating on a filter returns "Filter not found" even though it exists
- Filter list RPC returns IDs that the client cannot match to its internal state

**Phase to address:** Migration phase (Phase 22 equivalent)

---

### Pitfall 5: GPU Vendor Detection (`_detect_gpu`) Has No trame Equivalent

**What goes wrong:**
`ParaViewWebVolumeRendering._detect_gpu()` (lines 46-74 in `paraview_adv_protocols.py`) runs `eglinfo` as a subprocess to detect NVIDIA vs Mesa. In trame, GPU detection is handled differently — `VtkLocalView` renders client-side (no GPU needed on server), while `VtkRemoteView` renders server-side with whatever GPU is available.

**Why it happens:**
In the current architecture, the ParaView Web session container must detect its own GPU to choose between GPU ray cast and software ray cast. trame decouples rendering from the server for `VtkLocalView`, making server-side GPU detection unnecessary for that path.

**How to avoid:**
- For `VtkLocalView`: GPU detection is irrelevant — geometry is serialized and rendered in the browser via WebGL. No `eglinfo` call needed.
- For `VtkRemoteView`: If server-side rendering is needed, implement GPU detection via `vtkGraphicsFactory.GetBackEnd()` or similar VTK API instead of shelling out to `eglinfo`
- Move `volumeRenderingStatus` response data to `state.gpu_vendor`, `state.gpu_available` — trame's state sync replaces the RPC call
- The `smartVolumeMapper` logic (`simple._create_vtkSmartVolumeMapper()`) is ParaView-specific and may need review for trame compatibility

**Warning signs:**
- `subprocess.run(["eglinfo"]...)` still present in migrated code
- `VtkRemoteView` configured without GPU fallback for Apple Silicon
- Volume rendering toggle fails silently on Apple Silicon because the renderer is not configured for Mesa

**Phase to address:** Migration phase (Phase 20 equivalent)

---

### Pitfall 6: OpenFOAM Case Directory Mounting Changes

**What goes wrong:**
`ParaviewWebManager._start_container()` mounts the case directory at `/data` inside the container (line 344 in `paraview_web_launcher.py`). In trame, the case directory must be accessible to the trame server process. The mounting path and mechanism differ.

**Why it happens:**
Each ParaView Web session had its own container with the case mounted. trame runs as a long-running server process, not a per-session container. File paths and mounts are managed differently.

**How to avoid:**
- Mount the case directory at the trame server host level, not per-session
- Pass the case directory path via `state.case_dir` and initialize OpenFOAM reader in a `ctrl.on_server_start` callback
- If per-session isolation is still required (multi-tenant security), use the trame app's multi-session capabilities or separate processes behind a reverse proxy
- Verify the OpenFOAM reader can access the mounted path from the trame server's context

**Warning signs:**
- OpenFOAM reader cannot find boundary file `/data/constant/polyMesh/boundary`
- Case directory not visible to trame server process
- Multiple users see each other's case data (isolation breach)

**Phase to address:** Migration phase (Phase 20 equivalent)

---

### Pitfall 7: Multi-Client Session Isolation Requires Redesign

**What goes wrong:**
`ParaViewWebManager` spawns a named Docker container (`pvweb-{session_id}`) per session, achieving hard isolation. trame's default mode shares the same server process (and thus `simple` state) across all connected clients. Without explicit isolation, one user's filter operations could affect another user's viewport.

**Why it happens:**
ParaView Web's launcher spawns a separate ParaView server process per session. trame's `VtkLocalView` is designed for multi-user but requires explicit configuration to prevent state leakage between clients.

**How to avoid:**
- Use trame's `server.enableSession()` or per-client state isolation patterns
- Register client-specific state using `ctrl.on_client_connected()` to initialize per-client `state` entries
- For `VtkLocalView`, each client gets its own scene object but the server's `simple` state is global — add client ID prefixes to filter keys in `state.filters`
- For `VtkRemoteLocalView`, ensure render window configuration is per-client
- Test with two browser tabs connected to the same session: operations in tab A must not change tab B's viewport

**Warning signs:**
- Opening a clip filter in one browser tab creates it in another tab's view
- Filter list RPC returns filters from other users' sessions
- Camera reset in one tab resets it for all tabs

**Phase to address:** Migration phase (Phase 20/22 equivalent) — must be verified before multi-user testing

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `@exportRpc` classes and wrap them in trame | Avoid rewriting RPC methods | The entire trame state model is bypassed; creates a hybrid architecture that is harder to debug and maintain | Never — this defeats the migration purpose |
| Keep global Python dict for filter registry without client ID prefix | Simpler code | Cross-client state leakage in multi-user scenarios | Only in single-user MVP |
| Keep Docker container per session instead of trame server | Preserves existing infra | Loses trame's async benefits; adds container overhead; complicates deployment | Only if strict process isolation is a hard requirement |
| Skip stable filter ID generation | Avoid extra state management | Filter operations fail silently after server restart | Only in MVP with short-lived sessions |
| Implement volume rendering as server-side only (`VtkRemoteView`) | Simpler initial implementation | On Apple Silicon without GPU, server-side rendering is CPU-only and slow | Only for NVIDIA GPU deployments |
| Keep `simple.Render()` + `InvokeEvent` pattern (undetected) | Works in ParaViewWeb | `InvokeEvent` raises `AttributeError` in trame; silent failures | Never — must be replaced |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|-----------------|
| OpenFOAM reader | Assuming ParaView reader path `/data` works the same in trame | Verify reader path resolves from trame server context; use absolute paths |
| WebSocket port | Reusing ParaView Web port range (8081-8090) for trame | trame defaults to port 8080; configure explicitly; ensure no port conflicts |
| React frontend | Keeping the existing WebSocket RPC router (`message.id` routing) | Replace with trame's `server.controller` — the frontend RPC pattern changes fundamentally |
| Docker daemon | Building image with `vtk.web.launcher` dependency | Remove launcher dependency from Dockerfile; use `pip install trame trame-vtk` |
| Apple Silicon | Expecting GPU ray cast to work with `VtkRemoteView` | Use `VtkLocalView` (client-side WebGL rendering) so server GPU is irrelevant; or use `VtkRemoteView` with Mesa fallback |
| Container startup | Assuming entrypoint_wrapper.sh import pattern still applies | trame initializes server in Python directly; no launcher entrypoint needed |
| Image verification | `verify_paraview_web_image()` checking `vtk.web.launcher` | Remove this check; verify `trame` package is installed instead |
| Idle monitoring | `_idle_monitor` task using `docker kill` | trame has no per-session containers; implement idle timeout as a state TTL or asyncio task |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Large mesh sent to `VtkLocalView` without LOD | Browser tab freezes during geometry transfer | Use `VtkLocalView` with appropriate geometry decimation; limit mesh complexity before transfer | Meshes with >5M cells |
| `VtkRemoteView` image quality too high | 100+ ms latency on camera orbit | Set appropriate `quality` and `ratio` parameters on `VtkRemoteView` | >3 concurrent users or slow client devices |
| `simple.Render()` called on every filter parameter change | Server CPU spikes | Debounce state changes; batch updates; only render on explicit commit | Interactive slider manipulation |
| Filter registry iteration over `state.filters` on every RPC | Slow RPC responses as filter count grows | Use `state.filters` as a dict with O(1) lookups; do not iterate for filter operations | >100 filters in session |
| Serializing full mesh on every state change | Network saturation, UI lag | `VtkLocalView` only sends geometry delta; configure appropriately |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| No authentication on trame WebSocket endpoint | Any user can execute server-side filter operations | Use trame's built-in authentication or add a reverse proxy auth layer |
| OpenFOAM case files accessible via predictable paths | Data leakage between users | Validate case path ownership before mounting; use user-specific subdirectories |
| `subprocess.run` with unsanitized inputs (future extensions) | Command injection | Never pass user input directly to subprocess; use VTK API instead of shell commands |
| No rate limiting on filter RPCs | DoS from rapid filter creation | Add throttling in `ctrl.on_*` callbacks using `asyncio.sleep` or a token bucket |
| No session isolation between multi-users | Users can affect each other's visualization state | Use client-ID-scoped state with `ctrl.on_client_connected()` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Viewport does not update after filter apply | User creates filter but sees no change — assumes it failed | Always return confirmation with visual feedback; verify viewport updates in test |
| Volume rendering toggle shows no feedback on Apple Silicon | User clicks Enable Volume but nothing happens | Check GPU availability and show informative message if GPU unavailable |
| Filter list does not update after delete | User deletes filter but it still appears in the list | Trigger UI refresh via `state.filters` mutation after every delete |
| Session timeout is invisible | User's session dies silently during long analysis | Show connection status indicator; implement client-side reconnect logic |
| Filter operations block WebSocket | User's camera freezes while clip is being created | Move filter creation to async handler; show progress in UI |

---

## "Looks Done But Isn't" Checklist

Verify these during implementation, not just during demo:

- [ ] **RPC methods:** `@exportRpc` decorator fully replaced — verify no `from wslink.decorators import exportRpc` in migrated files
- [ ] **`InvokeEvent` removed:** Verify no `self._app.SMApplication` or `InvokeEvent` references in trame codebase
- [ ] **Filter IDs stable:** Server restart does not break existing client-side filter references
- [ ] **Multi-client isolation:** Two simultaneous users do not see each other's filters or camera changes
- [ ] **Viewport updates:** Clip/contour/stream tracer operations visibly update the 3D view
- [ ] **Docker cleanup:** Old `pvweb-{session_id}` containers are not created; old launcher image verification removed
- [ ] **Apple Silicon rendering:** Volume rendering toggle produces visible output via `VtkLocalView` (WebGL) or graceful fallback
- [ ] **OpenFOAM reader:** Case directory resolves correctly; boundary file found at expected path
- [ ] **Frontend RPC router:** React components use trame state/callback pattern, not wslink `message.id` routing
- [ ] **Idle monitoring:** Replaced `_idle_monitor` with trame-compatible timeout mechanism
- [ ] **Image verification:** `verify_paraview_web_image()` replaced with `pip show trame` equivalent
- [ ] **Filter registry:** `ParaViewWebAdvancedFilters._filters` class dict replaced with `state.filters`

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| `@exportRpc` classes not migrated | HIGH | Roll back frontend to ParaView Web temporarily; re-plan migration as a full rewrite |
| Filter state leakage between clients | HIGH | Immediately enable client ID prefixes on filter keys; deploy hotfix; audit all state mutations |
| `InvokeEvent` causing `AttributeError` | MEDIUM | Wrap in try/except during migration; systematically replace with state mutation |
| Docker container leaks (old containers not cleaned) | LOW | Run `docker rm $(docker ps -aq -f name=pvweb)` to clean up; update cleanup code |
| Apple Silicon volume rendering silent failure | MEDIUM | Switch to `VtkLocalView`; remove server-side GPU detection; verify WebGL support in client |
| `vtk.web.launcher` dependency still in Dockerfile | MEDIUM | Remove launcher from Dockerfile; rebuild image; remove verification code |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| `@exportRpc` protocol rewrite | Phase 20 (ParaView Web protocol migration) | No `exportRpc` imports; all RPCs mapped to `ctrl.on_*` or `@state.change` |
| `InvokeEvent` removal | Phase 20 | No `_app.SMApplication` references; viewport updates verified in test |
| Container architecture replacement | Phase 20 (infrastructure) | Docker containers named `pvweb-*` are not created; trame server process handles sessions |
| Stable filter IDs | Phase 22 (advanced filters) | Server restart does not break filter operations in existing session |
| GPU detection refactor | Phase 20 | `VtkLocalView` renders correctly on Apple Silicon; no `eglinfo` subprocess calls |
| OpenFOAM path mounting | Phase 20 | Reader initializes without path errors; case geometry loads in view |
| Multi-client isolation | Phase 20/22 (before multi-user testing) | Two-tab test passes; no cross-client state leakage |
| Frontend RPC router rewrite | Phase 20 | React components use trame state/callback pattern, not wslink `message.id` routing |
| Idle monitoring replacement | Phase 20 | Sessions time out correctly via trame-compatible mechanism |

---

## Sources

| Source | URL | Confidence | Verifies |
|--------|-----|------------|---------|
| ParaViewWeb GitHub README | https://github.com/Kitware/paraviewweb | HIGH | ParaViewWeb maintenance mode status; trame recommendation |
| trame documentation (trame.readthedocs.io) | https://trame.readthedocs.io/en/latest/index.html | HIGH | State management, VTK widgets, server callbacks, life cycle callbacks |
| trame.widgets.paraview | https://trame.readthedocs.io/en/latest/trame.widgets.paraview.html | HIGH | `VtkLocalView`, `VtkRemoteView`, `VtkRemoteLocalView` API |
| trame main module | https://trame.readthedocs.io/en/latest/trame.html | HIGH | `get_server()`, `state`, `ctrl`, server initialization |
| trame.widgets.client | https://trame.readthedocs.io/en/latest/trame.widgets.client.html | HIGH | `ClientStateChange`, `ClientTriggers`, `JSEval` widgets |
| wslink GitHub README | https://github.com/Kitware/wslink | HIGH | wslink is actively maintained as trame's underlying protocol |
| trame PyPI page | https://pypi.org/project/trame/ | HIGH | v3.12.0, Python >= 3.9 requirement |
| Kitware/trame GitHub discussions | https://github.com/Kitware/trame/discussions/840 | MEDIUM | ParaView 6.1+ bundle planned for trame/vtk-local |
| `paraview_adv_protocols.py` | `api_server/services/paraview_adv_protocols.py` | HIGH | Existing `@exportRpc` implementations (Phase 20/22 work products) |
| `paraview_web_launcher.py` | `api_server/services/paraview_web_launcher.py` | HIGH | Existing Docker sidecar launcher (Phase 20 work product) |
| `Dockerfile` | `Dockerfile` | HIGH | Existing `openfoam/openfoam10-paraview510` image dependency |

**Confidence notes:**
- No official migration guide from Kitware exists (MEDIUM confidence on all recommendations)
- Team has no prior trame experience — requires validation during migration
- Some trame APIs (e.g., `VtkLocalView` geometry export) not fully documented — may require source code review during migration
- ParaView support for trame is still evolving (Discussion #840 notes ParaView 6.1 bundle is "hoped for")

---

*Pitfalls research for: ParaView Web to trame migration*
*Researched: 2026-04-11*
*Confidence: MEDIUM — no official migration guide exists; findings synthesized from trame docs, wslink protocol docs, and codebase analysis*
