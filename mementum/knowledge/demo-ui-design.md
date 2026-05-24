# Agent Flow Demo UI — Design Specification

React + Vite single-page application that demonstrates replay, resume,
append-only audit, and composite step structure of the agent flow runtime.

Frontend source lives in `bases/xagent/demo_ui/`.
In development both servers run independently; in production the Vite build
output is served as static files by the FastAPI `api_http` base.

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
│  ● run_e5f6  ⏸     │  ← waiting
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
| waiting           | purple  | ⏸   |
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
  │  case_id: …  vehicle: …  [+2 more]      [Resume] [Send Message]  │
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
  - `Resume` — shown when status is non-terminal and not waiting
  - `Send Message` — shown when status is `waiting`; clicking expands an
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
    │ (WAIT decision → waiting node)
    ▼
┌─────────────────────────────────────────────────────┐
│  ⏸  WAITING FOR MESSAGE                            │
│  "What year is the vehicle?"                        │
│  [Send Message here if run is still live]           │
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

Step type icons (inline SVG):
| step_type | Icon |
|-----------|------|
| planner   | compass SVG |
| subagent  | search SVG |
| summary   | clipboard SVG |
| tool_call | gear SVG |

Status colours (border-left accent + badge):
| StepStatus | Border | Badge bg |
|------------|--------|----------|
| pending    | gray   | gray     |
| running    | amber  | amber (Tailwind `animate-pulse`) |
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

When a run was resumed, the audit record shows which steps had `status=skipped`
(recovered from prior state). The flow chart:

- Inserts a horizontal dashed rule labelled **"─── Resume Point ───"** between
  the last skipped iteration and the first freshly-executed one.
- Renders skipped steps in slate-blue with a `↺ Replayed` badge.
- Renders fresh steps in their actual status colour.

Above the rule = recovered from checkpoint. Below = executed in this resume.

### 3.5 React Component Tree for Flow Chart

```
<FlowChart state audit>
  <IterationBlock iteration auditSteps resumePoint?>   (one per iteration)
    <StepNode step auditEntry onSelect>                ← PLANNER
    <Arrow />
    <ParallelGroup>
      <StepNode … />                                   ← each subagent
      …
    </ParallelGroup>
    <Arrow />
    <StepNode step auditEntry onSelect>                ← SUMMARY
  </IterationBlock>
  <ResumePoint />                                      ← inserted between iterations
  <WaitingNode wait onSubmitMessage? />                ← when waiting
  <FinalResult state />                                ← completed / failed
</FlowChart>
```

Each `<StepNode>` receives the matching `StepAuditEntry` for status, attempt
count, duration, and checkpoint_id. `onSelect` opens the `<StepDetailPanel>`.

### 3.6 Clicking a Step Node

Clicking any `<StepNode>` sets `selectedStep` state in `App`, which renders
the `<StepDetailPanel>` (see § 6).

---

## 4. Tab: Audit Log

Append-only chronological list of step records from `RunAuditRecord.steps`.

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
- **Extra** — `iter=N`, `chk=checkpoint_id` (truncated, copy-on-click), `attempt=N`

Append-only cues:
- New `<AuditRow>` elements animate in from below using a CSS keyframe on mount
  (`translateY(8px) → 0, opacity 0 → 1`).
- No row ever disappears or changes content after mount.
- Sticky header: **"Audit Log — append-only 🔒"**

`conversation_messages` from `AgentFlowState` are interleaved chronologically as
blue rows labelled `message_input`.

React implementation note: `<AuditLog>` receives the previous step count as a
prop so it knows which rows are new on each poll cycle and applies the entry
animation only to those.

---

## 5. Tab: State JSON

Pretty-printed `AgentFlowState` from `GET /agent-flow/runs/{run_id}`.

Features:
- Syntax-highlighted (strings=green, numbers=blue, keys=white, nulls=gray)
- Top-level keys collapsible via `<JsonViewer>` recursive component
- `iterations` array collapsed by default, expandable per index
- **Copy** button copies raw JSON
- **Raw** toggle removes highlighting for easy paste
- Auto-refreshes on the same 2 s poll when run is active

`<JsonViewer>` is a ~40-line recursive React component:
- `object` → renders key+collapsible subtree
- `array` → renders index+collapsible subtree
- scalar → renders coloured span

---

## 6. Step Detail Side Panel

`<StepDetailPanel>` slides in from the right (380 px) when a step node is
selected. `selectedStep` state lives in `App`; `null` hides the panel.
Dismiss: click overlay, press Escape, or click ✕.

```
┌─────────────────────────────────────┐
│  ✕                                  │
│  subagent:manuals                   │  ← step_name
│  subagent  •  succeeded             │  ← type + status badge
│  Iteration 0  •  attempt 1/1        │
│  Duration: 1.32 s                   │
│  Checkpoint: chk_def  [copy]        │
│  ↺ Replayed from checkpoint         │  ← only when status=skipped
│  ─────────────────────────────────  │
│  ▶ Input                            │  ← collapsible
│  { "name": "manuals" }              │
│  ─────────────────────────────────  │
│  ▶ Output                           │  ← collapsible
│  { "name": "manuals",               │
│    "status": "completed", … }       │
│  ─────────────────────────────────  │
│  ▶ Error                            │  ← only when failed
│  { … }                              │
└─────────────────────────────────────┘
```

Data source: matching `StepAuditEntry` from `RunAuditRecord.steps`.
JSON sections reuse `<JsonViewer>`.

---

## 7. Start Run Form (Modal)

`<NewRunModal>` triggered by "+ New Run" in the nav.

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

On submit: `POST /agent-flow/runs` → select new run in nav → switch to
Flow Chart tab → begin polling.

---

## 8. Backend Additions Required

### 8.1 New Endpoints

| Method | Path | Returns | Source |
|--------|------|---------|--------|
| `GET` | `/agent-flow/runs` | `list[AgentFlowState]` | `RunRepository.list_runs()` |
| `GET` | `/agent-flow/runs/{run_id}/audit` | `RunAuditRecord` | `replay.build_audit_record()` |
| `GET` | `/demo` | static file redirect | Vite build output |

### 8.2 Protocol Extension

`RunRepository` (in `repositories.py`) needs one new method:

```python
async def list_runs(self) -> list[AgentFlowState]: ...
```

`InMemoryRunRepository` returns `list(self._runs.values())` in insertion order.

### 8.3 CORS (development only)

The Vite dev server runs on port 5173; FastAPI runs on port 8000. Add
`CORSMiddleware` to the FastAPI app gated behind an env flag:

```python
# app.py — only when DEMO_CORS=1
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)
```

In production the Vite build output is served from the same origin, so CORS
is not needed.

### 8.4 Serving the Built Frontend

```python
# app.py
from fastapi.staticfiles import StaticFiles
_STATIC = Path(__file__).parent / "static" / "demo"
if _STATIC.exists():
    app.mount("/demo", StaticFiles(directory=_STATIC, html=True), name="demo")
```

`npm run build` in `bases/xagent/demo_ui/` writes output to
`bases/xagent/api_http/static/demo/` (configured in `vite.config.ts`).

### 8.5 Files Touched (backend)

```
components/xagent/agent_persistence/repositories.py   ← add list_runs to protocol
components/xagent/agent_persistence/memory.py         ← implement list_runs
bases/xagent/api_http/routes_agent_flow.py            ← GET /runs, GET /runs/{id}/audit
bases/xagent/api_http/app.py                          ← static mount + CORS flag
```

---

## 9. Technology Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Framework | React 18 + TypeScript | Component tree maps 1:1 to the visual/data tree; type safety matches backend Pydantic models |
| Build tool | Vite 5 | Fast HMR, minimal config, outputs to any directory |
| Styling | Tailwind CSS v3 (PostCSS, not CDN) | Utility classes; `animate-pulse` and keyframe extensions for audit row animation |
| Flow chart | Pure CSS flex + borders | The graph is a fixed DAG shape; no D3/Cytoscape needed |
| JSON viewer | `<JsonViewer>` recursive component | ~40 lines; no external dependency |
| Icons | Inline SVG (heroicons subset) | No icon font download; crisp at any size |
| HTTP | `fetch()` + `useEffect` polling | Native; cleanup on unmount avoids interval leaks |
| State | `useState` / `useEffect` in `App` | No external state library needed at this scale |

---

## 10. Polling Strategy

| Condition | Endpoint polled | Interval |
|-----------|-----------------|----------|
| Nav always | `GET /agent-flow/runs` | 3 s |
| Active non-terminal run selected | `GET /agent-flow/runs/{id}` + `GET /agent-flow/runs/{id}/audit` | 2 s |
| Terminal run selected | none | — |

Polling uses `useEffect` with a `setInterval`; the cleanup function clears the
interval so no leak occurs on unmount or run-change. Polling stops automatically
when `status` is `completed` or `failed`.

---

## 11. Dev & Build Setup

### Development (two terminals)

```bash
# terminal 1 — FastAPI with CORS enabled
DEMO_CORS=1 uv run uvicorn xagent.api_http.main:app --reload --port 8000

# terminal 2 — Vite dev server
cd bases/xagent/demo_ui
npm install
npm run dev          # http://localhost:5173
```

Vite proxies are not needed because CORS is permissive in dev mode.
The React app calls `http://localhost:8000` directly.

### Production / Demo build

```bash
cd bases/xagent/demo_ui
npm run build        # outputs to bases/xagent/api_http/static/demo/

uv run uvicorn xagent.api_http.main:app --port 8000
# open http://localhost:8000/demo
```

---

## 12. Implementation Stages

### Stage 1 — Backend Endpoints (~2 h)
**Goal**: all API surface the UI needs exists and is tested.

Files:
- `repositories.py` — add `list_runs()` to `RunRepository` Protocol
- `memory.py` — implement `list_runs()` on `InMemoryRunRepository`
- `routes_agent_flow.py` — add `GET /runs`, `GET /runs/{id}/audit`
- `app.py` — CORS flag, static mount for Vite build output

Tests:
- `test_api_http_app.py`: assert new routes present, list-runs and audit responses

---

### Stage 2 — Vite + React Shell (~1.5 h)
**Goal**: project scaffolded, two-panel layout renders, API client wired.

Files created under `bases/xagent/demo_ui/`:
```
package.json
vite.config.ts        ← outDir: ../api_http/static/demo
tsconfig.json
tailwind.config.js
postcss.config.js
src/
  main.tsx
  App.tsx             ← two-panel CSS Grid, polling orchestration
  api/client.ts       ← fetch wrappers for all endpoints
  types/agent_flow.ts ← TypeScript interfaces mirroring Pydantic models
  components/shared/
    StatusBadge.tsx
    JsonViewer.tsx
    SidePanel.tsx
```

Deliverables:
- Two-panel layout renders with placeholder content
- `client.ts` covers all 5 endpoints (list runs, get run, start, resume, input, audit)
- TypeScript types defined for `AgentFlowState`, `RunAuditRecord`, `StepAuditEntry`

---

### Stage 3 — Navigation Panel (~1.5 h)
**Goal**: run list populates from live API, new-run modal works.

Files:
```
src/components/nav/
  NavPanel.tsx        ← polling run list, selected highlight
  RunListItem.tsx     ← status dot, id, query snippet
  NewRunModal.tsx     ← form + POST /runs
```

Deliverables:
- Nav polled every 3 s
- Status dots with correct colours and spin animation
- Selected run highlighted with left accent bar
- New Run modal submits and selects the created run
- Empty state: "No runs yet — start one above"

---

### Stage 4 — Run Header + Tab Bar (~1 h)
**Goal**: header and tabs render for selected run.

Files:
```
src/components/run/
  RunHeader.tsx       ← id, status, query, metadata chips, action buttons
  TabBar.tsx          ← tab switcher with active indicator
  SubmitInputForm.tsx ← inline textarea + POST /runs/{id}/input
```

Deliverables:
- Header sticky, updates on each poll
- Resume button triggers `POST /runs/{id}/resume`
- Send Message form appears when `status=waiting`
- Tab bar switches between Flow Chart / Audit Log / State JSON

---

### Stage 5 — Flow Chart (~3 h)
**Goal**: execution graph renders correctly from state + audit data.

Files:
```
src/components/flow/
  FlowChart.tsx       ← top-level, maps iterations to blocks
  IterationBlock.tsx  ← rounded container, horizontal child layout
  ParallelGroup.tsx   ← dashed border, side-by-side children
  StepNode.tsx        ← card with icon, status, attempt, duration
  Arrow.tsx           ← horizontal connector SVG line
  ResumePoint.tsx     ← dashed rule with label
  WaitingNode.tsx     ← wait/message block
  FinalResult.tsx     ← completed / failed terminal card
```

Deliverables:
- Each iteration renders PLANNER → SUBAGENTS(parallel) → SUMMARY
- Status colours and badges on all nodes
- `↺ Replayed` badge on skipped nodes
- Resume Point rule inserted between iterations using audit data
- Summary decision label (final / replan / ask_user) on SUMMARY node
- WAITING node with pending prompt and conversation message resume behavior
- FINAL RESULT card (completed or failed)

---

### Stage 6 — Step Detail Side Panel (~1.5 h)
**Goal**: clicking a node shows full step data in a slide-in panel.

Files:
```
src/components/flow/StepDetailPanel.tsx
```

Deliverables:
- Slide-in via CSS `transform: translateX` transition
- Step metadata (name, type, status, iteration, attempt, duration, checkpoint_id)
- `↺ Replayed from checkpoint` indicator for skipped steps
- `<JsonViewer>` sections for input, output, error (collapsible)
- Dismiss on outside-click or Escape

---

### Stage 7 — Audit Log Tab (~1.5 h)
**Goal**: append-only step events rendered with entry animations.

Files:
```
src/components/audit/
  AuditLog.tsx        ← scrollable list, sticky header
  AuditRow.tsx        ← single event row with mount animation
```

Deliverables:
- Rows sourced from `RunAuditRecord.steps` + `AgentFlowState.conversation_messages`
- Event type badges (step_created / step_succeeded / step_failed / message_input)
- New rows animate in from below on each poll cycle
- Rows never change after mount
- Sticky "Audit Log — append-only 🔒" header

---

### Stage 8 — State JSON Tab + Polish (~1.5 h)
**Goal**: full state visibility and consistent edge-case handling.

Files:
```
src/components/state/StateJsonTab.tsx
```

Deliverables:
- Syntax-highlighted `<JsonViewer>` for full `AgentFlowState`
- Copy + Raw toggle
- Loading skeleton while fetch is in-flight
- Error banner on non-2xx responses
- Empty main panel state ("Select a run or start a new one")
- 404 graceful handling if run disappears between polls
- Tab dot indicator on Audit Log when new events arrive while on another tab
- Page title updates to reflect active run status

---

**Total estimated effort: ~13.5 h across 8 stages**

---

## 13. File Locations Summary

```
bases/xagent/demo_ui/                  ← React + Vite source (new base)
├── package.json
├── vite.config.ts                     ← outDir: ../api_http/static/demo
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/
    │   └── client.ts
    ├── types/
    │   └── agent_flow.ts
    └── components/
        ├── shared/
        │   ├── StatusBadge.tsx
        │   ├── JsonViewer.tsx
        │   └── SidePanel.tsx
        ├── nav/
        │   ├── NavPanel.tsx
        │   ├── RunListItem.tsx
        │   └── NewRunModal.tsx
        ├── run/
        │   ├── RunHeader.tsx
        │   ├── TabBar.tsx
        │   └── SubmitInputForm.tsx
        ├── flow/
        │   ├── FlowChart.tsx
        │   ├── IterationBlock.tsx
        │   ├── ParallelGroup.tsx
        │   ├── StepNode.tsx
        │   ├── Arrow.tsx
        │   ├── ResumePoint.tsx
        │   ├── WaitingNode.tsx
        │   ├── FinalResult.tsx
        │   └── StepDetailPanel.tsx
        ├── audit/
        │   ├── AuditLog.tsx
        │   └── AuditRow.tsx
        └── state/
            └── StateJsonTab.tsx

bases/xagent/api_http/                 ← existing FastAPI base
├── app.py                             ← CORS flag, static mount for /demo
├── routes_agent_flow.py               ← GET /runs, GET /runs/{id}/audit
├── static/
│   └── demo/                          ← Vite build output (gitignored)
└── DEMO_UI_DESIGN.md                  ← this document

components/xagent/agent_persistence/
├── repositories.py                    ← add list_runs to RunRepository Protocol
└── memory.py                          ← implement list_runs
```
