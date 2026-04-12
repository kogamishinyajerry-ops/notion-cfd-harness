---
gsd_state_version: 1.0
phase: 31
phase_name: Pipeline REST API + React Dashboard
status: draft
tool: none
---

# UI-SPEC: Phase 31 — Pipeline REST API + React Dashboard

## 1. Design System

### Theme
- **Mode**: Dark/light toggle (CSS custom property `--data-theme` on `<html>`)
- **Default**: `dark`
- **Implementation**: Mirror existing `MainLayout.tsx` pattern — `useState<'light'|'dark'>`, `document.documentElement.setAttribute('data-theme', theme)`. Do NOT refactor existing theme toggle.

### Spacing Scale (8-point grid, CSS custom properties)
| Token     | Value |
|-----------|-------|
| `--sp-1`  | 4px   |
| `--sp-2`  | 8px   |
| `--sp-4`  | 16px  |
| `--sp-6`  | 24px  |
| `--sp-8`  | 32px  |
| `--sp-12` | 48px  |

### Typography
| Role      | Size   | Weight | Line-height |
|-----------|--------|--------|-------------|
| Body/Caption | 14px | 400    | 1.5         |
| Heading 2 | 20px   | 600    | 1.2         |
| Card Name | 16px   | 600    | 1.2         |
| Heading 1 | 24px   | 600    | 1.2         |

**Font stack**: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif` (from existing `theme.css`)

### Color Contract
| Role      | Light mode   | Dark mode    | Usage                              |
|-----------|--------------|---------------|------------------------------------|
| Dominant  | `#ffffff`    | `#1d1d1f`     | Page background (`--bg-primary`)   |
| Secondary | `#f5f5f7`    | `#2a2a2e`     | Card/page background (`--bg-secondary`) |
| Accent    | `#e94560`    | `#e94560`     | Primary actions, active nav, CTAs  |
| Text      | `#1d1d1f`    | `#f5f5f7`     | Primary text (`--text-primary`)    |
| Muted     | `#6e6e73`    | `#a1a1a6`     | Secondary text (`--text-secondary`) |
| Border    | `#d2d2d7`    | `#48484a`     | Dividers, card borders (`--border-color`) |

### Pipeline Status Colors (new — add to theme.css)
| Status      | Color      | CSS variable        |
|-------------|------------|---------------------|
| PENDING     | `#9ca3af`  | `--color-pending`   |
| RUNNING     | `#f59e0b`  | `--color-running`   |
| COMPLETED   | `#10b981`  | `--color-completed` |
| FAILED      | `#ef4444`  | `--color-failed`    |
| CANCELLED   | `#6b7280`  | `--color-cancelled` |
| PAUSED      | `#8b5cf6`  | `--color-paused`    |
| SKIPPED     | `#facc15`  | `--color-skipped`   |

### Step Status Colors (node colors for Phase 33 DAG)
| Step Status | Color      | Matches pipeline status |
|-------------|------------|------------------------|
| PENDING     | `#9ca3af`  | gray                   |
| RUNNING     | `#3b82f6`  | blue                   |
| COMPLETED   | `#10b981`  | green                  |
| FAILED      | `#ef4444`  | red                    |
| SKIPPED     | `#facc15`  | yellow                 |

### Registry
- **Tool**: none (no shadcn)
- **Third-party registries**: none
- **External blocks**: none

---

## 2. Component Inventory

### 2.1 PipelinesPage (`/pipelines`)

**File**: `dashboard/src/pages/PipelinesPage.tsx`
**CSS file**: `dashboard/src/pages/PipelinesPage.css`

**Layout**: Single-column, `page` wrapper div. Header row with `<h1>` + "New Pipeline" button. Filter bar. Pipeline card list below.

**Header row**:
- `<h1>` "Pipelines" — 24px, weight 600
- Primary CTA button: "New Pipeline" — `btn btn-primary`, accent bg `#e94560`, white text, 8px 16px padding, 4px radius

**Filter bar**:
- Horizontal flex row, `--sp-2` gap
- Filter buttons matching `JobQueueView.css` `.filter-btn` pattern (outline style, active = accent fill)
- Filters: All / PENDING / RUNNING / COMPLETED / FAILED

**Pipeline card** (`.pipeline-card`):
- Background: `--bg-primary`, border 1px `--border-color`, 8px radius, 16px padding
- Left border 3px colored by status (`.border-left` variant using status color)
- Hover: border-color `--accent-color`, box-shadow `--card-shadow`
- Content:
  - Row 1: Pipeline name (`.pipeline-name`, 16px weight 600) + status badge (`.status-badge`)
  - Row 2: Pipeline ID (monospace, 14px, muted) + description (14px, muted, truncated)
  - Row 3: Created date (14px, muted) + step count + duration
  - Footer: "View Details" link + "Delete" button (destructive, text-only, red on hover)

**Empty state** (`.empty-state`):
- Centered, 3rem padding, muted text
- Icon area (CSS-only circle with "plus" pseudo-element or unicode `+`)
- Heading: "No pipelines yet"
- Body: "Create your first pipeline to automate your CFD workflow."
- CTA: "Create Pipeline" button

**Loading state**:
- Centered spinner (`.loading-spinner`, existing pattern)
- "Loading pipelines..." muted text

**Delete confirmation**: Browser `confirm()` dialog — "Delete pipeline '{name}'? This cannot be undone."

---

### 2.2 PipelineDetailPage (`/pipelines/:pipelineId`)

**File**: `dashboard/src/pages/PipelineDetailPage.tsx`
**CSS file**: `dashboard/src/pages/PipelineDetailPage.css`

**Layout**: Vertical stack, `page` wrapper. Header with back link + status badge. Meta grid. Control bar. Tab content area.

**Header** (`.pipeline-detail-header`):
- Back link: `← Back to Pipelines`, accent color, 14px
- Pipeline name `<h1>` 24px weight 600
- Pipeline status badge (colored by current status)
- Description paragraph (14px, muted)

**Meta grid** (`.pipeline-meta-grid`, `grid-template-columns: repeat(auto-fill, minmax(160px, 1fr))`):
- Labels: 14px uppercase muted, values: 14px weight 500
- Fields: ID (monospace), Name, Status, Created, Updated, Step Count, Duration (computed)

**Control bar** (`.pipeline-control-bar`):
- Horizontal flex, `gap: --sp-4`, wraps on mobile
- Buttons (`.btn` classes):
  - Start (PENDING only): green bg `#10b981`, white text
  - Pause (RUNNING only): amber bg `#f59e0b`, dark text
  - Resume (PAUSED only): blue bg `#3b82f6`, white text
  - Cancel (RUNNING or PAUSED): outline red, `#ef4444` border+text
- Disabled state: opacity 0.5, `cursor: not-allowed`
- Loading state during API call: spinner inside button (small, 16px)

**Progress bar** (RUNNING only, `.pipeline-progress`):
- Full-width bar, 8px height, rounded
- `--bg-tertiary` track, `--color-running` fill
- Percentage label right-aligned, 14px muted
- Computed: `(completed_step_count / total_step_count) * 100`

**Tab system** (identical to `JobDetailPage.css` `.job-content-tabs`):
- Tabs: Steps | Events | Config
- Active tab: bottom border 2px `--accent-color`, accent text
- Inactive: muted text
- `.tab-btn` padding: --sp-4 --sp-6

**Steps tab** (`.steps-view`):
- Vertical list of step rows (`.step-row`)
- Each step row:
  - Step name (16px weight 500)
  - Step type badge (e.g. "generate", "run", "monitor", "visualize", "report") — small, muted bg pill
  - Step status badge (colored)
  - Duration / started-at / completed-at (14px muted)
  - Depends-on list (14px muted, comma-separated step names)
  - Expand button → expands result object if COMPLETED/FAILED (JSON in monospace)
- Step rows colored left-border by status (3px)

**Events tab** (`.events-view`):
- Vertical scrollable list, max-height 400px
- Each event: timestamp (monospace 14px muted) + event type badge + sequence number + message
- Event type badges: colored by category (pipeline vs step event)

**Config tab** (`.config-view`):
- Key-value pairs in `.config-item` (existing pattern from JobDetailPage)
- Shows: pipeline ID, name, description, DAG adjacency list (JSON monospace), created_at, updated_at

**Real-time updates**:
- WebSocket connection on mount if status is RUNNING/MONITORING
- Reconnect logic: on close, wait 3s then reconnect, up to 5 retries
- After 5 failed reconnects, fall back to polling every 5s
- Polling indicator: small pulsing dot in header "Reconnecting..." / "Polling" text

**WebSocket URL**: `ws://localhost:8000/ws/pipelines/{pipeline_id}`
- Message types handled: `pipeline_started`, `step_started`, `step_completed`, `step_failed`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`

---

### 2.3 PipelineCreatePage (`/pipelines/new`)

**File**: `dashboard/src/pages/PipelineCreatePage.tsx`
**CSS file**: `dashboard/src/pages/PipelineCreatePage.css`

**DAG builder**: Form-based (NOT visual node editor). Visual DAG editor is Phase 33.

**Layout**: Centered form, max-width 720px, `page` wrapper.

**Form sections** (vertical stack, 24px gap):

**Section 1: Basic Info**
- Pipeline name: text input, required, max 64 chars
- Description: textarea, optional, max 256 chars

**Section 2: Steps Builder** (`.steps-builder`)
- Step list (`.step-list`): each step is a card (`.step-card`) with:
  - Step name (text input, required)
  - Step type (select: generate / run / monitor / visualize / report)
  - Depends on (multi-select checkboxes of previously-added step names)
  - Params (JSON textarea, optional, placeholder `{}`)
  - Remove step button (red text button, bottom-right of card)
- "Add Step" button: outline style, `+` prefix
- Steps can be reordered via "Move Up" / "Move Down" buttons (text buttons)
- Minimum 1 step required

**Section 3: Actions**
- "Create Pipeline" (primary, accent) — disabled if form invalid
- "Cancel" (secondary, outline) — returns to `/pipelines`

**Validation**:
- Name required, non-empty
- At least 1 step
- Each step has a name and type
- Circular dependency detection: if selected `depends_on` creates a cycle, show inline error "Circular dependency detected" on the offending step

**Error state**: inline `.form-error` text below field, red color `#ef4444`, 14px

**Success**: redirect to `/pipelines/{new_pipeline_id}` after `POST /pipelines`

---

### 2.4 Navigation

**Route additions** (update `dashboard/src/router.tsx`):
- `/pipelines` → `PipelinesPage`
- `/pipelines/new` → `PipelineCreatePage`
- `/pipelines/:pipelineId` → `PipelineDetailPage`

**MainLayout nav**: Add `Pipelines` nav link between `Jobs` and `Reports`:
```tsx
<NavLink to="/pipelines" className={...}>Pipelines</NavLink>
```

---

## 3. API Integration

### Endpoints (add to `dashboard/src/services/api.ts`)

| Method | Endpoint                       | Description                    |
|--------|--------------------------------|--------------------------------|
| GET    | `/pipelines`                   | List all pipelines             |
| GET    | `/pipelines/{id}`              | Get pipeline detail            |
| POST   | `/pipelines`                   | Create pipeline (body: DAG)    |
| PUT    | `/pipelines/{id}`              | Update pipeline (PENDING only)  |
| DELETE | `/pipelines/{id}`              | Cancel and delete pipeline     |
| POST   | `/pipelines/{id}/start`        | Start pipeline execution        |
| POST   | `/pipelines/{id}/pause`        | Pause pipeline                  |
| POST   | `/pipelines/{id}/resume`       | Resume paused pipeline          |
| POST   | `/pipelines/{id}/cancel`       | Cancel pipeline                 |
| GET    | `/pipelines/{id}/steps`        | Get all steps with statuses     |
| GET    | `/pipelines/{id}/events`       | Get buffered pipeline events    |

### API Response Types (add to `dashboard/src/services/types.ts`)

```typescript
export interface Pipeline {
  id: string;
  name: string;
  description?: string;
  status: PipelineStatus;
  steps: PipelineStep[];
  config: PipelineConfig;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

export type PipelineStatus = 'PENDING' | 'RUNNING' | 'MONITORING' | 'VISUALIZING' | 'REPORTING' | 'COMPLETED' | 'FAILED' | 'CANCELLED' | 'PAUSED';

export interface PipelineStep {
  id: string;
  pipeline_id: string;
  step_type: StepType;
  step_order: number;
  depends_on: string[];  // step IDs
  params: Record<string, unknown>;
  status: StepStatus;
  result?: StepResult;
  started_at?: string;
  completed_at?: string;
}

export type StepType = 'generate' | 'run' | 'monitor' | 'visualize' | 'report';
export type StepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';

export interface StepResult {
  status: 'success' | 'diverged' | 'validation_failed' | 'error';
  exit_code: number;
  validation_checks?: Record<string, boolean>;
  diagnostics?: Record<string, unknown>;
}

export interface PipelineConfig {
  dag: Record<string, string[]>;  // step_id → depends_on step_ids
}

export interface PipelineEvent {
  sequence: number;
  type: 'pipeline_started' | 'step_started' | 'step_completed' | 'step_failed' | 'pipeline_completed' | 'pipeline_failed' | 'pipeline_cancelled' | 'pipeline_paused' | 'pipeline_resumed';
  pipeline_id: string;
  step_id?: string;
  timestamp: string;
  data?: Record<string, unknown>;
}
```

### WebSocket Service

**File**: `dashboard/src/services/pipelineWs.ts`
- Extend existing `wsService` pattern for pipeline-specific WS at `/ws/pipelines/{pipeline_id}`
- Message types: `pipeline_started`, `step_started`, `step_completed`, `step_failed`, `pipeline_completed`, `pipeline_failed`, `pipeline_cancelled`, `pipeline_paused`, `pipeline_resumed`
- Sequence number tracking for reconnect replay
- Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, 16s), max 5 retries
- After max retries, switch to HTTP polling every 5s

### Polling Fallback

- If WebSocket disconnected and retries exhausted, poll `GET /pipelines/{id}` every 5 seconds
- Stop polling when pipeline reaches terminal state (COMPLETED / FAILED / CANCELLED)
- On tab focus (visibilitychange event), immediately refetch to sync state

---

## 4. Data Fetching

### Tanstack Query Integration

**Note**: Dashboard currently uses raw `useEffect`/`useState` with `apiClient`. Phase 31 may introduce `@tanstack/react-query` if it already exists in package.json. Check `dashboard/package.json` before implementing.

If `@tanstack/react-query` is not in package.json, use the existing pattern (no new library).

### Query Strategy
- `GET /pipelines`: `useQuery({ queryKey: ['pipelines'], queryFn: () => apiClient.getPipelines(), refetchInterval: 10000 })` — 10s polling for list page
- `GET /pipelines/{id}`: `useQuery({ queryKey: ['pipeline', id], queryFn: () => apiClient.getPipeline(id) })` — no auto-polling; rely on WebSocket
- `GET /pipelines/{id}/steps`: included in pipeline detail response
- `GET /pipelines/{id}/events`: fetched on mount of Events tab (lazy)

---

## 5. State Transitions

### Pipeline Status State Machine (display only)
```
PENDING → RUNNING → MONITORING → VISUALIZING → REPORTING → COMPLETED
                ↘ FAILED ↙ CANCELLED ↙ PAUSED ↔ RESUME
```

### Button Visibility Rules
| Status       | Start | Pause | Resume | Cancel |
|--------------|-------|-------|--------|--------|
| PENDING      | ✅    | ❌    | ❌    | ✅     |
| RUNNING      | ❌    | ✅    | ❌    | ✅     |
| PAUSED       | ❌    | ❌    | ✅    | ✅     |
| MONITORING   | ❌    | ✅    | ❌    | ✅     |
| VISUALIZING  | ❌    | ✅    | ❌    | ✅     |
| REPORTING    | ❌    | ❌    | ❌    | ✅     |
| COMPLETED    | ❌    | ❌    | ❌    | ❌     |
| FAILED       | ✅*   | ❌    | ❌    | ❌     |
| CANCELLED    | ✅*   | ❌    | ❌    | ❌     |

`*` Re-run: creates a new pipeline with same definition

---

## 6. Error States

### API Error
- Toast notification: bottom-right, red accent border, error message, 5s auto-dismiss
- On create/update failure: inline form error below submit button

### WebSocket Disconnect
- Header indicator: amber pulsing dot + "Reconnecting..." text
- After 5 retries: "Polling" indicator (gray dot + "Polling..." text)
- On reconnect: green flash "Connected" for 2s, then hide indicator

### Empty States
- Pipelines list: "No pipelines yet" (see Component Inventory 2.1)
- Pipeline detail steps: "No steps defined" (only if malformed — should not happen)
- Events: "No events yet" (monospace empty state, same structure as logs)

### Validation Errors
- Circular dependency: inline red error on step card
- Missing required field: red border on input + error text below
- API-level error (409 Conflict on update non-PENDING): alert banner above form

---

## 7. File Map

```
dashboard/src/
  pages/
    PipelinesPage.tsx          [NEW]
    PipelinesPage.css          [NEW]
    PipelineDetailPage.tsx     [NEW]
    PipelineDetailPage.css     [NEW]
    PipelineCreatePage.tsx     [NEW]
    PipelineCreatePage.css     [NEW]
  services/
    pipeline.ts                [NEW — pipeline-specific API methods]
    pipelineWs.ts              [NEW — WebSocket service for pipelines]
    types.ts                   [MODIFY — add Pipeline*, Step*, PipelineEvent types]
    api.ts                     [MODIFY — add pipeline endpoints]
    config.ts                  [MODIFY — add pipeline WS endpoint]
  router.tsx                  [MODIFY — add 3 pipeline routes]
  theme.css                    [MODIFY — add pipeline status CSS variables]
```

---

## 8. Copywriting Contract

| Element              | Copy                                                        |
|----------------------|-------------------------------------------------------------|
| Page heading         | "Pipelines"                                                 |
| Empty state heading  | "No pipelines yet"                                          |
| Empty state body     | "Create your first pipeline to automate your CFD workflow." |
| Create CTA           | "New Pipeline"                                              |
| Step type labels     | generate / run / monitor / visualize / report (lowercase)  |
| Delete confirm title | "Delete Pipeline?"                                          |
| Delete confirm body  | "Are you sure you want to delete '{name}'? This cannot be undone." |
| Loading text         | "Loading pipelines..." / "Loading pipeline..."              |
| Error text           | "Failed to load pipelines: {error}" / "Failed to load pipeline: {error}" |
| WebSocket reconnecting | "Reconnecting..." / "Polling"                             |
| Cancel button        | "Cancel Pipeline"                                            |
| Start button         | "Start"                                                     |
| Pause button         | "Pause"                                                     |
| Resume button        | "Resume"                                                    |
| No events text       | "No events recorded yet."                                    |
| Create pipeline CTA  | "Create Pipeline" (form submit button)                      |
| Step add button      | "Add Step"                                                  |
| Config tab label     | "Config"                                                    |
| Steps tab label      | "Steps"                                                     |
| Events tab label     | "Events"                                                    |

---

## 9. Safety Gate

| Item | Status |
|------|--------|
| Tool: none | ✅ No third-party components introduced |
| Registry: none | ✅ No external blocks |
| Network access | ✅ WebSocket URLs are internal (localhost) |
| Dynamic code execution | ✅ No eval/Function used |

---

## 10. Quality Checklist

- [ ] All spacing values are multiples of 4
- [ ] Typography uses exactly 4 sizes (14px body/caption, 16px card name, 20px h2, 24px h1) — no ad-hoc sizes
- [ ] Status badges use CSS variables from theme, not hardcoded hex
- [ ] Dark/light theme toggle is NOT refactored — kept identical to MainLayout
- [ ] WebSocket reconnect logic covers 5 retries then polling fallback
- [ ] Tab system is identical to JobDetailPage pattern
- [ ] Form validation includes circular dependency detection
- [ ] No hardcoded colors — all use CSS custom properties
- [ ] Routing added to router.tsx, nav link added to MainLayout
- [ ] All new pages wrapped in `.page` class
