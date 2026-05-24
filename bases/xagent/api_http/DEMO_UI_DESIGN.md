# Agent Flow Demo UI — Design Specification

Single-page web application served by the existing FastAPI `api_http` base.
Goal: visually demonstrate replay, resume, append-only audit, and the step
composite structure without any build tooling.

---

## 1. Layout

```
┌───────────────────┬────────────────────────────────────────────────┐
│  NAV PANEL        │  MAIN PANEL                                     │
│  220 px, fixed    │  fluid, full height                             │
│  scrollable       │                                                 │
└───────────────────┴────────────────────────────────────────────────┘
```

### Left Navigation Panel (220 px, fixed height, overflow-y scroll)

```
┌─────────────────────┐
│  ⬡ Agent Flow       │  ← app title
│  [+ New Run]        │  ← always visible, opens start-run form
│  ─────────────────  │
│  ● run_a1b2  ✓     │  ← status dot + truncated ID + icon
│    diagnose no …    │  ← query snippet (1 line, ellipsis)
│                     │
│  ● run_c3d4  ⟳     │  ← running (animated dot)
│    check oil …      │
│                     │
│  ● run_e5f6  ⏸     │  ← waiting_for_user
│    engine light …   │
│                     │
│  ● run_g7h8  ✗     │  ← failed
│    smoke from …     │
└─────────────────────┘
```

Status dot colours:
| Status            | Colour  | Icon |
|-------------------|---------|------|
| pending           | gray    | ○    |
| running           | amber   | ⟳ (animated spin) |
| waiting_for_user  | purple  | ⏸   |
| completed         | green   | ✓    |
| failed            | red     | ✗    |
| paused            | blue    | ‖    |

Selected run is highlighted (light background + left accent bar).

---

## 2. Main Panel

Three zones stacked vertically:

```
┌────────────────────────────────────────────────────────────────┐
│  RUN HEADER  (sticky)                                          │
│  run_id  •  STATUS BADGE  •  query text                        │
│  case_id: …  vehicle: …  [+2 more]          [Resume] [Input]  │
├────────────────────────────────────────────────────────────────┤
│  TAB BAR                                                       │
│  [Flow Chart]  [Audit Log]  [State JSON]                       │
├────────────────────────────────────────────────────────────────┤
│  TAB CONTENT  (scrollable)                                     │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Run Header

- **run_id** monospace, copy-on-click
- **Status badge**: coloured pill using RunStatus values
- **Query**: full text, truncated to 2 lines (click to expand)
- **Metadata chips**: `case_id`, then key=value pairs; overflow hidden with "+N more" chip
- **Action buttons** (right-aligned, context-sensitive):
  - `Resume` — shown when status is non-terminal and not waiting_for_user
  - `Submit Input` — shown when status is `waiting_for_user`; clicking expands an
    inline text-area + submit button below the header

---

## 3. Tab: Flow Chart

Primary demo surface. Renders the execution graph from `AgentFlowState`.

### 3.1 Overall Structure (top-to-bottom)

```
  START
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  ITERATION 0                                        │
│                                                     │
│  ┌──────────┐      ┌───────────────────────┐      ┌──────────┐  │
│  │ PLANNER  │ ───► │  SUBAGENTS (parallel) │ ───► │ SUMMARY  │  │
│  │ planning │      │ ┌────────┐ ┌────────┐ │      │summarize │  │
│  │    ✓     │      │ │manuals │ │history │ │      │  replan  │  │
│  └──────────┘      │ │  ✓    │ │  ✓    │ │      └──────────┘  │
│                    │ └────────┘ └────────┘ │                    │
│                    └───────────────────────┘                    │
└─────────────────────────────────────────────────────┘
    │ (REPLAN decision → next iteration)
    ▼
┌─────────────────────────────────────────────────────┐
│  ITERATION 1                                        │
│  ... same structure ...                             │
└─────────────────────────────────────────────────────┘
    │ (ASK_USER decision → waiting node)
    ▼
┌─────────────────────────────────────────────────────┐
│  ⏸  WAITING FOR USER                               │
│  "What year is the vehicle?"                        │
│  [Submit Input here if run is still live]           │
└─────────────────────────────────────────────────────┘
    │ (user submits → next iteration)
    ▼
  FINAL RESULT
  ┌─────────────────────────────────────────────────────┐
  │  ✓  COMPLETED                                       │
  │  "manuals handled query 'diagnose no start'…"       │
  └─────────────────────────────────────────────────────┘
      — or —
  ┌─────────────────────────────────────────────────────┐
  │  ✗  FAILED                                          │
  │  Agent flow reached the maximum iteration count.    │
  └─────────────────────────────────────────────────────┘
```

### 3.2 Step Node Visual

Each atomic step is a card:

```
┌──────────────────────────────────┐
│  [TYPE ICON]  step_name          │
│               status badge       │
│  attempt 1/1  •  1.23 s          │
│  [↺ Replayed from checkpoint]    │  ← only when status=skipped
└──────────────────────────────────┘
```

Step type icons (inline SVG or unicode):
| step_type | Icon |
|-----------|------|
| planner   | 🗺 (map) or compass SVG |
| subagent  | 🔍 (search) or agent SVG |
| summary   | 📋 (clipboard) or sigma SVG |
| tool_call | ⚙ (gear) |

Status colours (border-left accent + badge):
| StepStatus | Border | Badge bg |
|------------|--------|----------|
| pending    | gray   | gray     |
| running    | amber  | amber (pulse animation) |
| succeeded  | green  | green    |
| failed     | red    | red      |
| skipped    | slate-blue | slate-blue + "↺ Replayed" label |

### 3.3 Composite Step Visuals

**Sequence (outer iteration block):**
Rounded container card with a label `ITERATION N` in the top-left corner.
Children rendered horizontally with arrows between them.

**Parallel (subagents group):**
A dashed-border container labelled `SUBAGENTS — parallel`.
Children rendered side-by-side with no arrows between siblings.
A single incoming arrow from PLANNER and a single outgoing arrow to SUMMARY
attach to the group container, not individual children.

```
PLANNER ──► ┌──── parallel ────┐ ──► SUMMARY
            │ manuals  history │
            └──────────────────┘
```

### 3.4 Resume Visualisation

When a run was resumed (`/resume` was called on a non-terminal run), the
audit record shows which steps had status `skipped` (recovered from prior
state). The flow chart adds:

- A horizontal dashed rule labelled **"─── Resume Point ───"** between the
  last skipped step's iteration and the first freshly-executed step.
- Skipped steps rendered in slate-blue with `↺ Replayed` badge.
- Fresh steps rendered in their actual status colour.

This makes it visually clear: above the line = recovered from checkpoint,
below the line = executed in this resume call.

### 3.5 Clicking a Step Node

Clicking any node slides in the **Step Detail Panel** from the right (see § 5).

---

## 4. Tab: Audit Log

Append-only chronological list of `StepEvent` records fetched from
`GET /agent-flow/runs/{run_id}/audit`. Newest events appear at the bottom.

```
──── Audit Log  (append-only) ────────────────────────────────────

  timestamp               event_type       step_name           extra
  ─────────────────────────────────────────────────────────────────
  2024-01-01 10:00:00.001  step_created    planner             iter=0
  2024-01-01 10:00:00.002  step_succeeded  planner             chk=chk_abc
  2024-01-01 10:00:01.010  step_created    subagent:manuals    iter=0
  2024-01-01 10:00:01.011  step_created    subagent:history    iter=0
  2024-01-01 10:00:02.330  step_succeeded  subagent:manuals    chk=chk_def
  2024-01-01 10:00:02.901  step_succeeded  subagent:history    chk=chk_ghi
  2024-01-01 10:00:03.100  step_created    summary             iter=0
  2024-01-01 10:00:04.200  step_succeeded  summary             chk=chk_jkl
```

Row anatomy:
- **Timestamp** — ISO, monospace, gray
- **Event type badge** — coloured pill (step_created=gray, step_succeeded=green,
  step_failed=red)
- **Step name** — monospace
- **Extra** — `iter=N`, `chk=checkpoint_id` (truncated with copy-on-click), `attempt=N` for retries

Append-only cues:
- New rows slide in from the bottom when polling detects new events.
- No row ever disappears or changes content (immutable after render).
- A sticky header reads **"Audit Log — append-only"** with a lock icon.

The user_input_events from the run state are interleaved chronologically as
purple rows labelled `user_input`.

---

## 5. Tab: State JSON

Pretty-printed `AgentFlowState` JSON from `GET /agent-flow/runs/{run_id}`.

Features:
- Syntax-highlighted (strings=green, numbers=blue, keys=white, nulls=gray)
- Top-level keys collapsible (triangle toggle)
- `iterations` array collapsed by default, expandable per index
- **Copy** button (top-right) copies raw JSON
- **Raw** toggle removes syntax highlighting for easy paste
- Auto-refreshes on the same 2 s poll when run is active

---

## 6. Step Detail Side Panel

Slides in from the right (width ~380 px) when a step node is clicked.
Clicking outside or pressing Escape dismisses it.

```
┌─────────────────────────────────────┐
│  ✕                                  │
│  subagent:manuals                   │  ← step_name
│  subagent  •  succeeded             │  ← type + status badge
│  Iteration 0  •  attempt 1/1        │
│  Duration: 1.32 s                   │
│  Checkpoint: chk_def  [copy]        │
│  ↺ Replayed from checkpoint         │  ← only when skipped
│  ─────────────────────────────────  │
│  ▶ Input                            │  ← collapsible
│  {                                  │
│    "name": "manuals"                │
│  }                                  │
│  ─────────────────────────────────  │
│  ▶ Output                           │  ← collapsible
│  {                                  │
│    "name": "manuals",               │
│    "status": "completed",           │
│    "content": "recovered manual…"   │
│  }                                  │
│  ─────────────────────────────────  │
│  ▶ Error                            │  ← only when failed
│  { … }                              │
└─────────────────────────────────────┘
```

Data source: the matching `StepAuditEntry` from `RunAuditRecord.steps`.

---

## 7. Start Run Form (Modal)

Triggered by "+ New Run" in the nav.

```
┌──────────────────────────────────────┐
│  Start New Run                    ✕  │
│  ─────────────────────────────────── │
│  Query *                             │
│  ┌────────────────────────────────┐  │
│  │ diagnose no start              │  │
│  └────────────────────────────────┘  │
│                                      │
│  Case ID (optional)                  │
│  ┌────────────────────────────────┐  │
│  │                                │  │
│  └────────────────────────────────┘  │
│                                      │
│  Metadata JSON (optional)            │
│  ┌────────────────────────────────┐  │
│  │ {"vehicle": "example"}         │  │
│  └────────────────────────────────┘  │
│                                      │
│                    [Cancel]  [Start] │
└──────────────────────────────────────┘
```

On submit: `POST /agent-flow/runs`, select the new run in nav, switch to
Flow Chart tab, begin polling.

---

## 8. Backend Additions Required

### 8.1 New Endpoints

| Method | Path | Returns | Source |
|--------|------|---------|--------|
| `GET` | `/agent-flow/runs` | `list[AgentFlowState]` | `RunRepository.list_runs()` |
| `GET` | `/agent-flow/runs/{run_id}/audit` | `RunAuditRecord` | `replay.build_audit_record()` |
| `GET` | `/demo` | `FileResponse` | `static/demo.html` |

### 8.2 Protocol Extension

`RunRepository` (in `repositories.py`) needs one new method:

```python
async def list_runs(self) -> list[AgentFlowState]: ...
```

`InMemoryRunRepository` stores states in a dict keyed by run_id; `list_runs`
returns `list(self._runs.values())` in insertion order.

### 8.3 Files Touched (backend)

```
components/xagent/agent_persistence/repositories.py   ← add list_runs to protocol
components/xagent/agent_persistence/memory.py         ← implement list_runs
bases/xagent/api_http/routes_agent_flow.py            ← GET /runs, GET /runs/{id}/audit
bases/xagent/api_http/app.py                          ← GET /demo route + static dir
```

---

## 9. Technology Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Styling | Tailwind CSS via CDN | No build step; utility classes cover everything needed |
| Flow chart | Pure CSS/HTML (flex + borders) | The graph is a fixed DAG shape, not arbitrary; no D3/Cytoscape needed |
| JSON viewer | Inline recursive JS renderer | Avoids external dependency; ~60 lines |
| Icons | Inline SVG snippets | No icon font download; crisp at any size |
| HTTP | `fetch()` + `setInterval` | Native, no library |

---

## 10. Polling Strategy

| Condition | Endpoint polled | Interval |
|-----------|-----------------|----------|
| Nav always | `GET /agent-flow/runs` | 3 s |
| Active run selected (non-terminal) | `GET /agent-flow/runs/{id}` + `GET /agent-flow/runs/{id}/audit` | 2 s |
| Terminal run selected | none | — |

Polling stops for a run as soon as status is `completed` or `failed`.
The nav continues polling to catch new runs started externally (e.g., via CLI).

---

## 11. Implementation Stages

### Stage 1 — Backend Endpoints (~2 h)
**Goal**: all API surface the UI needs is available.

Files:
- `repositories.py` — add `list_runs()` to `RunRepository` Protocol
- `memory.py` — implement `list_runs()` on `InMemoryRunRepository`
- `routes_agent_flow.py` — add `GET /runs` and `GET /runs/{id}/audit`
- `app.py` — add `GET /demo` FileResponse route

Tests:
- Extend `test_api_http_app.py`: assert `/agent-flow/runs` in routes
- Add tests for list-runs response and audit response

---

### Stage 2 — Shell + Navigation (~2 h)
**Goal**: two-panel layout renders, run list populates from live API.

File: `bases/xagent/api_http/static/demo.html`

Deliverables:
- CSS Grid two-panel layout (220 px nav, fluid main)
- Nav: polled run list with status dots and badges
- Selected-run highlight and left accent bar
- "+ New Run" button → modal with start-run form
- Main panel: empty state ("Select a run or start a new one")
- Run header renders (id, status badge, query, metadata chips)

---

### Stage 3 — Flow Chart (~3 h)
**Goal**: execution graph renders from `AgentFlowState` with correct composite structure.

File: `demo.html`

Deliverables:
- Iteration container cards (sequential wrapper)
- PLANNER node → SUBAGENTS parallel group → SUMMARY node per iteration
- Arrow connectors between nodes and groups
- Status colours and badges on each node
- WAITING_FOR_USER node and FINAL RESULT node
- Summary decision label on SUMMARY node (final / replan / ask_user)
- Resume Point dashed rule + skipped-step slate-blue styling

---

### Stage 4 — Step Detail Side Panel (~2 h)
**Goal**: clicking a node shows full step data.

File: `demo.html`

Deliverables:
- Slide-in panel (CSS transform transition)
- Step metadata (name, type, status, iteration, attempt, duration, checkpoint_id)
- "↺ Replayed" indicator for skipped steps
- Collapsible JSON viewer (input, output, error sections)
- Dismiss on outside-click or Escape

---

### Stage 5 — Audit Log Tab (~2 h)
**Goal**: append-only step events rendered with animations.

File: `demo.html`

Deliverables:
- Chronological rows from `RunAuditRecord.steps` (via `/audit` endpoint)
- Event type badges (step_created, step_succeeded, step_failed)
- user_input rows interleaved from `AgentFlowState.user_input_events`
- Slide-in animation for new rows on poll
- Sticky "Audit Log — append-only 🔒" header

---

### Stage 6 — State JSON Tab + Actions (~2 h)
**Goal**: full state visibility and all interactive actions work end-to-end.

File: `demo.html`

Deliverables:
- Syntax-highlighted, collapsible JSON viewer for AgentFlowState
- Copy + Raw toggle
- Resume button → `POST /runs/{id}/resume` → refresh
- Submit Input inline form → `POST /runs/{id}/input` → refresh
- Loading skeletons while fetch is in-flight
- Error banner on failed fetch (non-2xx)
- Auto-stop polling when run reaches terminal state

---

### Stage 7 — Polish (~1 h)
**Goal**: consistent visual quality and edge cases handled.

Deliverables:
- Empty nav state ("No runs yet — start one above")
- 404 graceful handling if a run disappears between polls
- Responsive: main panel scrolls independently at narrow widths
- Tab indicator (dot) on Audit Log tab when new events arrive while tab is not active
- Favicon and page title update to reflect active run status

---

**Total estimated effort: ~14 h across 7 stages**

---

## 12. File Locations Summary

```
bases/xagent/api_http/
├── app.py                       ← add GET /demo
├── routes_agent_flow.py         ← add GET /runs, GET /runs/{id}/audit
├── static/
│   └── demo.html                ← entire frontend (single file)
└── DEMO_UI_DESIGN.md            ← this document

components/xagent/agent_persistence/
├── repositories.py              ← add list_runs to RunRepository Protocol
└── memory.py                    ← implement list_runs on InMemoryRunRepository
```
