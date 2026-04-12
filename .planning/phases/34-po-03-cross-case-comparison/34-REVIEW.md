# Phase 34 Code Review — PO-03 Cross-Case Comparison

## Scope
Phase 34 plans 01 (backend) + 02 (frontend), 13 commits, ~5,700 LOC changed.

---

## Findings Summary

| Severity | Count | Blocking? |
|----------|-------|-----------|
| CR (Critical) | 1 | Yes |
| WR (Warning) | 2 | No |
| IN (Informational) | 3 | No |

---

## CR-01: `Object.entries()` called on JSON string — RUNTIME ERROR

**File:** `dashboard/src/components/MetricsTable.tsx:232-234`

```typescript
// MetricsTable.tsx
{Object.entries(row.params)
  .map(([k, v]) => `${k}=${v}`)
  .join(', ')}
```

**Problem:** `MetricsRow.params` is defined as `str` in the Pydantic model and populated with `json.dumps(case.param_combination)` — a JSON string like `'{"velocity":1,"resolution":50}'`. Calling `Object.entries()` on a string iterates over string characters, not key-value pairs.

**Fix:** Parse JSON before iterating:
```typescript
{Object.entries(JSON.parse(row.params))
  .map(([k, v]) => `${k}=${v}`)
  .join(', ')}
```

---

## WR-01: Docker script path mismatch — delta computation silently fails

**File:** `api_server/services/comparison_service.py:159`

```python
script_path.write_text(script_content)  # Written to host filesystem

subprocess.run(
    ["docker", "exec", docker_name, "pvpython", f"/scripts/{script_path.name}"],
    ...
)
```

**Problem:** The script is written to `output_dir` on the host filesystem, but `docker exec pvpython /scripts/{name}` tries to access it at `/scripts/` inside the container. Unless `/scripts` is a bind-mounted directory, this will fail silently. The container's filesystem has no access to host paths.

**Fix options:**
1. Write script to a bind-mounted host directory (e.g., mount a host temp dir to `/scripts` in the container)
2. Use `docker cp` to copy the script into the container before exec
3. Pass script content via stdin: `docker exec ... pvpython -c "$(cat script.py)"`

**Severity: WR** because the `compute_delta_field` function returns an error tuple, so the failure is caught and reported — it won't crash silently. However, it will always fail in the current deployment configuration.

---

## WR-02: `subprocess.Popen` trame sessions never cleaned up

**File:** `api_server/routers/comparisons.py:158`

```python
subprocess.Popen(
    ["python3", str(trame_script_path)],
    cwd=str(_DELTA_OUTPUT_DIR),
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
```

**Problem:** Every call to `POST /comparisons/{id}/delta-session` launches a trame subprocess. These processes accumulate and are never killed. Over time this will exhaust file descriptors and memory. Also, `trame_script_path` is never deleted.

**Fix:** Add a process registry with TTL, or launch trame as a short-lived server that exits when the client disconnects. At minimum, delete `trame_script_path` after launching.

---

## IN-01: `MetricsTable` `execution_time` column shows "—" for `undefined` but cell renders as `—` for `undefined` only

**File:** `dashboard/src/components/MetricsTable.tsx:240-242`

```typescript
{row.execution_time !== undefined
  ? `${row.execution_time.toFixed(2)}s`
  : '—'}
```

**Observation:** `execution_time` can be `undefined` (not in response) or `null` (from API). The current check only handles `undefined`. Consider also checking `!= null` or using `??`.

---

## IN-02: `comparison_service.py` `get_all_completed_cases()` called twice in `compute_delta`

**File:** `api_server/services/comparison_service.py:298-299`

```python
case_a = next((c for c in self._sweep_db.get_all_completed_cases() if c.id == case_a_id), None)
case_b = next((c for c in self._sweep_db.get_all_completed_cases() if c.id == case_b_id), None)
```

**Observation:** Two full table scans for two lookups. Not blocking but could be optimized with `get_case()` if that method exists and is efficient.

---

## IN-03: `delta_session` endpoint returns before trame is ready

**File:** `api_server/routers/comparisons.py:154-167`

```python
subprocess.Popen(...)  # Fire and forget
return {"trame_url": trame_url, "session_id": session_id}
```

**Observation:** The URL is returned immediately after `Popen`, but trame startup (including ParaView reader initialization) can take 5-30 seconds. The iframe will load before the server is ready. The DeltaFieldViewer should handle this with a retry/loading state, which it does (loading state while `trameUrl` is null).

---

## Actions Required Before Merge

| ID | Action | Owner |
|----|--------|-------|
| CR-01 | Parse JSON in MetricsTable before Object.entries | Backend/Frontend |
| WR-01 | Fix docker script path (use stdin cat or docker cp) | Backend |
| WR-02 | Add subprocess cleanup or delete trame script after launch | Backend |

---

## Files Reviewed

| File | CR | WR | IN |
|------|----|----|----|
| `api_server/services/comparison_service.py` | 1 | 1 | 1 |
| `api_server/routers/comparisons.py` | 0 | 1 | 1 |
| `api_server/models.py` | 0 | 0 | 0 |
| `dashboard/src/components/MetricsTable.tsx` | 1 | 0 | 1 |
| `dashboard/src/components/ConvergenceOverlay.tsx` | 0 | 0 | 0 |
| `dashboard/src/components/DeltaFieldViewer.tsx` | 0 | 0 | 0 |
| `dashboard/src/pages/ComparisonPage.tsx` | 0 | 0 | 0 |
