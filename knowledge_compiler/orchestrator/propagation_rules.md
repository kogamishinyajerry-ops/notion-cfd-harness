# Knowledge Compiler: Orchestrator Propagation Rules
**Phase**: 3
**Purpose**: Define how knowledge changes propagate through the orchestrator

---

## 1. Propagation Overview

```
Knowledge Change (diff_engine) → Impact Analysis → Orchestrator Action
```

When `diff_engine.py` detects a change in Phase2 knowledge assets:

| Change Type | Impact | Orchestrator Action |
|-------------|-------|---------------------|
| NEW | New knowledge unit added | Hot-reload if compatible, restart if schema change |
| DELETE | Knowledge unit removed | **HALT** — requires manual review |
| TEXT_EDIT | Formatting/whitespace | Ignore — no impact |
| SEMANTIC_EDIT | Content meaning changed | Invalidate affected components |
| EVIDENCE_EDIT | Validation data changed | Re-run benchmarks, re-verify |
| CHART_RULE_EDIT | Rendering rule changed | Regenerate affected charts |

---

## 2. Component-Knowledge Mapping

Each orchestrator component depends on specific Phase2 knowledge units:

| Component | Dependent Knowledge Units | Impact on Change |
|-----------|-------------------------|-----------------|
| Task Builder | chapters.yaml, task_wizard.py | Restart |
| CAD Parser | chapters.yaml (CH-001) | Hot-reload |
| Physics Planner | formulas.yaml, data_points.yaml, evidence.yaml | Hot-reload |
| Mesh Builder | chapters.yaml (CH-002), formulas.yaml (FORM-009) | Hot-reload |
| Solver Runner | formulas.yaml | Hot-reload |
| Monitor | formulas.yaml (convergence criteria) | Hot-reload |
| Verify Console | All executables, all units | **ALWAYS** re-validate |

---

## 3. Hot-Reload Rules

A component supports hot-reload if:

1. **Schema-compatible**: The changed unit's structure hasn't broken
2. **No running state**: Component isn't actively executing a task
3. **Reversible**: Change can be undone without side effects

**Hot-reload procedure**:
```python
def hot_reload_component(component_id: str, change: DiffReport):
    if not can_hot_reload(change):
        return False
    component = get_component(component_id)
    component.reload_knowledge(change.unit_id)
    return True
```

---

## 4. Invalidate-and-Restart Rules

**HALT conditions** (require manual intervention):
- `DELETE` change type — knowledge cannot be un-deleted
- Schema-breaking `SEMANTIC_EDIT` — e.g., formula signature change
- `EVIDENCE_EDIT` that invalidates current task's validation

**Restart procedure**:
1. Stop all running tasks
2. Apply knowledge changes
3. Clear all caches
4. Re-initialize components
5. Require human approval before resuming

---

## 5. Validation Re-Trigger Rules

When `EVIDENCE_EDIT` or `CHART_RULE_EDIT` is detected:

1. Find all active tasks referencing the changed unit
2. Mark their verification as `STALE`
3. Re-run `VerifyConsole` for each affected task
4. Update `VerificationReport` with new results
5. If new result is `FAIL`, pause task and notify

---

## 6. Decision Tree

```
                    ┌─────────────┐
                    │ Change      │
                    │ Detected    │
                    └──────┬──────┘
                           │
                ┌───────────┴───────────┐
                │   Change Type?        │
                └───────────┬───────────┘
           ┌────────────┼────────────┐
           │            │            │
        TEXT_EDIT   NEW/DELETE   OTHERS
           │            │            │
           │        ┌───┴────┐   ┌───┴─────────┐
           │        │ HALT  │   │ Semantic?  │
           │        │ Manual │   └────┬───────┘
           │        │ Review │        │
        Ignore      └────────┘   ┌────┴─────┐
                               │ Impact?  │
                          ┌──────┴──────┬──────┐
                     Hot-reload   Invalidate  Re-verify
```

---

## 7. Integration with diff_engine.py

```python
from knowledge_compiler.executables.diff_engine import ChangeType, diff_files

def handle_knowledge_change(baseline_commit: str, current_path: str):
    changes = diff_files(baseline_commit, current_path)
    for change in changes:
        if change.change_type == ChangeType.DELETE:
            emergency_shutdown(change)
        elif change.change_type == ChangeType.EVIDENCE_EDIT:
            reverify_all_tasks(change.impacted_executables)
        elif change.change_type == ChangeType.SEMANTIC_EDIT:
            if change.requires_review:
                request_opus_review(change)
            else:
                hot_reload_affected_components(change)
```

---

## 8. Rollback Support

If a propagating change breaks active tasks:

1. **Pause** all affected tasks
2. **Revert** knowledge change using git
3. **Restart** orchestrator components
4. **Resume** tasks from last known good state
5. **Notify** user with incident report

---

## 9. Version Compatibility Matrix

| Knowledge Compiler | Orchestrator | Compatible? |
|--------------------|--------------|--------------|
| v1.0 (baseline) | v1.0 | ✅ Yes |
| v1.0 + F-P2-001 fix | v1.0 | ✅ Yes (hot-reload) |
| v1.0 + F-P2-005 (diff_engine) | v1.1 | ✅ Yes (requires restart) |
| v1.0 + schema break | v1.1 | ❌ No — upgrade orchestrator |

**Rule**: Orchestrator version must be >= Knowledge Compiler version
for schema-compatible changes.
