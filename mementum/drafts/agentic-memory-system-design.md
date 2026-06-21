---
title: Agentic Memory System Design
status: draft
category: architecture
tags: [memory, agent-runtime, postgres, provenance, temporal]
related:
  - agent-runtime-framework-design
  - architecture-decisions
  - implementation-invariants
---

# Agentic Memory System Design

## 1. Summary

Agent runs today produce observations and conclusions with no durable, auditable record of what was believed, when it was believed, and why. Each run starts with no structured memory of prior tasks, entity history, or learned patterns.

This design introduces a **memory control plane**: an append-only authoritative ledger backed by Postgres, with multiple replaceable projection indexes (temporal, graph, vector, keyword). The agent explicitly writes observations and fact proposals as step actions; a separate consolidation job extracts observations from raw sources and promotes them into durable facts and lessons on-demand.

**Core invariant:** Every memory must be explainable by a timeline and a provenance graph.

**Main design decision:** Separate the immutable source of truth (ledger + fact assertions) from replaceable read indexes (vector, graph, keyword). Backends are swappable; the ledger is not.

**Most important tradeoff:** Full provenance and bitemporal tracking add write overhead and schema complexity on the hot path. This is mitigated by keeping the hot path minimal (raw observations only) and deferring promotion to on-demand consolidation.

---

## 2. Background and Problem

The current agent runtime records step executions and tool calls in the step ledger, but does not maintain structured memory across runs or tasks. This means:

- Prior conclusions about the same entity (user, project, customer, document, etc.) are not retrievable in structured form.
- There is no way to ask "what did we believe on June 10, and what changed it?"
- Cross-task patterns cannot accumulate from task history into shared domain knowledge.
- Agent reasoning cannot be audited by tracing a conclusion back to its observations and raw sources.

A single vector database is not a solution. It provides semantic retrieval but loses update semantics, temporal reasoning, exact identifier matching (IDs, codes, version strings, names), and source attribution. Summaries as sole long-term memory are lossy and non-auditable.

Agents operating over time require bitemporal facts: entity state, configurations, and relationships change over time, and the system must distinguish *when something was true in the world* from *when the system learned it*.

---

## 3. Goals and Non-Goals

**Goals**

- Full provenance: every fact traces to observations, which trace to raw sources, which trace to tool calls, runs, and turns.
- Bitemporal correctness: track both valid time (real world) and transaction time (system learned).
- Pluggable projections: graph, vector, and keyword indexes are adapters behind interfaces; each can be replaced independently.
- Safe scope promotion: conversation-scoped facts do not become global knowledge without passing a policy gate.
- Structured retrieval: every memory read returns an evidence bundle with citations, not raw text.

**Non-Goals**

- Real-time memory sync across replicas or distributed agents.
- Replacing the existing step runtime ledger — the step ledger remains authoritative for execution records; the memory system is a downstream consumer.
- Managing raw document storage (that stays in GCS/S3).
- Automatic consolidation triggers — consolidation is on-demand only in v1.

---

## 4. Core Concepts and Data Model

### Memory Scopes

All raw sources, observations, and facts are scoped along two independent axes.

**Axis 1 — Trust level** (can this fact be used outside this conversation?)

| Level | Meaning |
|---|---|
| `conversation` | Depends on input messages or user assertions in a specific conversation. Not valid as evidence outside that conversation until promoted. |
| `global` | Verified independent of any conversational assumptions. Safe to use across any context. |

**Axis 2 — Subject reference** (what is this fact about, and how is it looked up?)

| Subject type | Meaning | Required identifier fields |
|---|---|---|
| `universal` | No specific subject — broadly applicable | — |
| `entity` | A named, identifiable thing | `entity_type` (e.g. vehicle, user, project, device) + `entity_id` (e.g. VIN, user_id) |
| `domain` | A category or cross-entity pattern | `domain_type` (e.g. dtc_pattern, firmware_class) + `domain_key` |
| `agent` | Procedural knowledge for a specific agent instance | `agent_id` |

`subject_ref` encodes both type and identifier as `{type}:{id}` (e.g. `vehicle:VIN123`, `dtc:P0A80`) so both are recoverable from a single indexed column without a join.

The primary promotion axis is trust level: `conversation` → `global`. Subject reference typically stays stable during promotion — a fact about `vehicle:VIN123` remains about that vehicle whether conversation-scoped or global. A separate promotion path escalates subject type when a pattern found across many entity-level facts qualifies as `domain` knowledge.

Conversation-scoped facts are not readable outside their conversation until promoted through the policy gate.

### Derivation Basis

How an observation or fact was derived. Used as `observation.derivation_basis` and as the initial value of `fact_assertion.status`.

| Value | Meaning |
|---|---|
| `observed` | Directly read from a source, tool result, or log — no model inference |
| `inferred` | Derived by model extraction or deterministic rule |
| `confirmed` | Validated by a corroborating source or human review |
| `deprecated` | Superseded, retracted, or invalidated |

`fact_assertion` additionally has a numeric `confidence` field (0.0–1.0) for the promotion gate threshold comparison, separate from the lifecycle `status`.

### Core Entities

**RawSource** — immutable capture of what an external system produced. Never a fact or interpretation — only what the source actually emitted. Never overwritten.

Fields: `source_id`, `scope_level` (conversation / global), `conversation_id` (non-null when conversation-scoped), `subject_type` (universal / entity / domain / agent), `subject_ref` (`{type}:{id}` or null), `source_type` (user_msg / tool_call / tool_result / doc_chunk / log_line), `source_ref` (pointer to step ledger or external system), `content`, `content_ref_type`, `content_ref_loc`, `byte_size`, `payload`, `observed_at`, `recorded_at`, `hash`.

`content` and `content_ref_type` / `content_ref_loc` are mutually exclusive: small payloads are stored inline in `content`; large payloads are written to an external blob store and `content` is null. `content_ref_type` identifies the storage backend (`s3`, `gcs`, `azure_blob`, `local_fs`, …); `content_ref_loc` is a backend-specific locator string. Retrieval is via `BlobStore.retrieve_blob(ref_type, locator)`. `byte_size` is always set and is used to make the inline-vs-external routing decision. The step runtime ledger can reference the same blob by the same `(content_ref_type, content_ref_loc)` pair, avoiding duplication. `hash` covers the full content regardless of where it is stored.

Raw sources are scoped at write time. The same content in two different scopes produces two distinct scoped records.

**Observation** — a single extracted unit fact, always derived from one or more raw sources via `DerivationEdge`. Never a full message or prose passage — always one statement. Immutable once written.

Fields: `observation_id`, `scope_level` (conversation / global), `conversation_id` (non-null when conversation-scoped), `subject_type` (universal / entity / domain / agent), `subject_ref` (`{type}:{id}` or null), `content` (single statement), `derivation_basis` (observed / inferred / confirmed / deprecated — how this unit fact was derived), `recorded_at`, `hash`.

Observations are scoped at write time. **Scope inheritance:** an observation always inherits `scope_level` and `conversation_id` from its parent raw source — an observation cannot be less restricted than its source. `subject_type` and `subject_ref` may be set more specifically by the extractor (e.g. a `universal`-scoped raw source can produce an `entity`-scoped observation if the extraction identifies a specific entity). A conversation-scoped observation is not available as evidence for facts outside that conversation until explicitly promoted through the policy gate. Provenance — which raw sources the observation was extracted from — is recorded in `DerivationEdge`, not inline.

**FactAssertion** — the system's interpretation. Versioned, never overwritten in place.

Fields: `assertion_id`, `scope_level` (conversation / global), `conversation_id` (non-null when conversation-scoped), `subject_type` (universal / entity / domain / agent), `subject_ref` (`{type}:{id}` or null), `fact_key` (stable dedupe key), `subject`, `predicate`, `object`, `status`, `confidence`, `valid_from`, `valid_to`, `recorded_at`, `retracted_at`, `supersedes_assertion_id`, `attribution` (model_id, prompt_hash, tool_version, run_id).

**`subject_ref` vs `subject`:** `subject_ref` is the retrieval and scoping key — it identifies which entity or domain this fact belongs to for index lookups and scope filtering. `subject` / `predicate` / `object` is the semantic triple — the actual claim. For entity-scoped facts they are often the same value (e.g. both `vehicle:VIN123`), but they can differ: a fact scoped to `vehicle:VIN123` (`subject_ref`) might have a triple like `subject=vehicle:VIN123, predicate=correlates_with, object=dtc:P0A80` where the object references a different entity.

**Status values:** `proposed` → `observed` / `inferred` / `confirmed` → `contradicted` / `retracted` / `superseded`

**CurrentFacts** — a view, not a mutable row:

```sql
current_facts = latest non-retracted assertions
                where valid_to is null
                and status in ('observed', 'inferred', 'confirmed')
```

**DerivationEdge** — links a derived object to its parents, forming the full provenance DAG. Records `method` (llm_extract / deterministic_rule / human_review), `model_id`, `prompt_hash`, `tool_version`.

Three valid derivation patterns:
- `observation` ← `raw_source`: an extracted unit fact traces to the raw source(s) it was extracted from
- `fact` ← `observation`: a fact assertion traces to the unit observation(s) that support it
- `fact` ← `fact`: a higher-order fact traces to supporting facts

No layer-skipping is permitted. A fact cannot derive directly from a raw source — every claim must pass through an explicit observation. This ensures the promotion gate always evaluates a unit-fact granularity record, and can trace it back to the raw source to determine whether the underlying input is conversation-specific.

**MemoryIndexRef** — tracks which external indexes (pgvector, Qdrant, Graphiti, Neo4j) contain a given object, and with which embedding model.

### Fact Operations

| Operation | Meaning |
|---|---|
| `assert_fact` | Add a new claim |
| `confirm_fact` | Mark a claim as validated |
| `supersede_fact` | Replace an old claim with a newer one |
| `promote_fact` | Promote a conversation-scoped fact to global scope: creates a new `fact_assertion` with `scope_level = global`, same `subject_ref` / `fact_key`, and `supersedes_assertion_id` pointing to the conversation-scoped predecessor |
| `contradict_fact` | Mark a conflict between two claims; resolve by confidence |
| `retract_fact` | Withdraw a claim |
| `close_validity` | Fact was true but is no longer true (set `valid_to`) |
| `merge_entity` | Entity resolution: two nodes are the same |
| `split_entity` | Undo a bad entity merge |
| `extract_conditional` | When a fact depends on a conversation-scoped assumption that blocks direct promotion, extract a new `global` / `domain` fact with `predicate = conditional_rule` and `object = {antecedent: [...], consequent: {...}}`. The antecedent must be as tight as possible — only predicates strictly necessary for the consequent, not incidental conversational context (e.g. not "user mentioned this in a vehicle diagnostics session"). The original conversation-scoped fact is not promoted; the conditional is a new record linked via `DerivationEdge`. Can be triggered at assertion time (preferred — model has freshest context) or during promotion gate evaluation. |

**`fact_key` construction:** `fact_key` is a deterministic string over `(subject_ref, predicate)` — e.g. `sha256("{subject_ref}|{predicate}")` or a human-readable slug. It is scope-independent: the same claim about the same entity has the same `fact_key` whether conversation-scoped or global. This allows `supersede_fact`, `promote_fact`, and `contradict_fact` to locate the predecessor record by key without a full table scan.

**Contradiction resolution policy:** When two assertions conflict on the same `fact_key`, the one with higher confidence is kept as active; the lower-confidence assertion is tagged `contradiction_resolved` (not deleted). Both records are retained for audit.

### Promotion Ladder

```
raw source  [conversation-scoped]
  → observation  [conversation-scoped, unit fact]
  → fact assertion  [conversation-scoped]
        ↓  confidence threshold + source-scope check
        ├── sources all global
        │       → promote_fact → fact assertion  [global, same subject_ref]
        └── sources include conversational assumption
                ↓  model evaluates abstraction value
                │  (earliest opportunity: at assertion time)
                ├── not generalisable → stays conversation-scoped
                └── generalisable
                        → extract_conditional
                          → fact assertion  [global, domain]
                             predicate: conditional_rule
                             object: { antecedent: [...], consequent: {...} }
                             antecedent: tight — only conditions necessary for consequent
                          (original fact stays conversation-scoped; linked via DerivationEdge)
  → fact assertion  [global]
        ↓  cross-entity pattern confirmed across many entities
  → fact assertion  [global, domain subject]
```

The primary promotion step is trust-level promotion: `conversation` → `global`. Subject reference (what the fact is about) stays the same. A separate, less frequent promotion escalates `subject_type` from `entity` to `domain` when a pattern is confirmed across enough entity-level facts to qualify as fleet-wide knowledge. When a fact depends on a conversational assumption that blocks direct promotion, a third path extracts a conditional fact globally — capturing the *pattern* rather than the *conclusion*. The promotion policy is a versioned, configurable rule; the initial implementation is a confidence threshold plus a source-scope check.

---

## 5. Proposed Architecture

```
┌─────────────────────────────────────────────────┐
│  Agent / Planner / Tools                        │
│  (writes to memory as explicit step actions)    │
└──────────────────┬──────────────────────────────┘
                   │  1. RawSourceStore.store_raw_source()
                   │     └─ large content → BlobStore.store_blob()
                   │  2. ObservationStore.store_observation()  [unit facts]
                   │     + ProvenanceStore.link_derivation()   [obs ← raw_source]
                   │  3. FactStore.assert_fact()
                   │     + ProvenanceStore.link_derivation()   [fact ← obs]
                   │  4. MemoryLedger.append_event()
                   ▼
┌─────────────────────────────────────────────────┐
│  Authoritative Memory Ledger                    │
│  Postgres: memory_event, raw_source,            │
│  observation, fact_assertion,                   │
│  derivation_edge, memory_index_ref              │
└──────────────────┬──────────────────────────────┘
                   │  on-demand consolidation
                   │  (promotes conversation→global;
                   │   updates projection indexes)
    ┌──────────────┼──────────────┬───────────────────┐
    ▼              ▼              ▼                   ▼
┌────────┐  ┌──────────┐  ┌───────────┐    ┌──────────────┐
│Temporal│  │  Graph   │  │  Vector   │    │   Keyword    │
│ facts  │  │ Graphiti │  │ pgvector  │    │  Postgres    │
│Postgres│  │ / Neo4j  │  │ / Qdrant  │    │  FTS+trgm    │
└────────┘  └──────────┘  └───────────┘    └──────────────┘
                   │
                   ▼
          MemoryRetriever
          (query router → EvidenceBundle)
```

**Five layers:**

1. **Raw source + observation store** — Postgres. Immutable. `RawSourceStore` captures what external systems produced; `ObservationStore` holds unit facts extracted from raw sources. Large raw content offloaded to `BlobStore`.
2. **Authoritative ledger** — Postgres. Append-only. `FactStore` holds versioned, bitemporal fact assertions. `ProvenanceStore` holds derivation edges. `MemoryLedger` holds the event timeline. Never overwritten.
3. **Projection indexes** — Temporal (Postgres bitemporal views), Graph (Graphiti/Neo4j), Vector (pgvector first), Keyword (Postgres FTS + pg_trgm). Each is an adapter behind an interface; rebuilt from the ledger on demand.
4. **Blob store** — pluggable external storage (`BlobStore` interface) for large raw source content. Shared with the step runtime ledger to avoid duplication.
5. **Retrieval router** — `MemoryRetriever` classifies the query, fans out to appropriate projections, merges results, and returns a structured `EvidenceBundle`.

---

## 6. Context Dependencies

The memory system does not operate in isolation. It depends on external systems for execution context and raw artifact storage. These dependencies are explicit and bounded: the memory system references them via `source_ref` pointers but does not own, replicate, or enforce integrity against their records.

### Step Runtime Ledger

The step runtime ledger records agent runs, turns, and step executions. It is the authoritative source for:

- Run and turn identifiers (`run_id`, `turn_id`, `step_id`)
- Tool invocation records (when a tool was called, by which run, in which step)
- Execution timing and sequencing

The memory system is a downstream consumer of the step ledger. When a `raw_source` record with `source_type = "tool_call"`, `"tool_result"`, or `"user_msg"` is written, its `source_ref` field carries a pointer into the step ledger (e.g., `{run_id, step_id, tool_name}`). This pointer is non-enforced: the memory system records what it believes the originating step was, but holds no foreign key constraint against the ledger.

**Boundary contract:**
- The step ledger is not queried at memory read time. Provenance traversal (`ProvenanceStore.explain()`) resolves chains within the memory system only; reaching the `source_ref` boundary requires a separate cross-system lookup.
- If the step ledger is unavailable or its records are purged, `source_ref` chains become unresolvable at the boundary. Raw sources, observations, and facts remain valid within the memory system, but external audit of the originating execution is no longer possible.
- The memory system does not subscribe to or react to step ledger events in v1. The agent writes to both systems explicitly as step actions.

### Document and Artifact Storage

Raw documents, artifacts, and large binary payloads are stored in GCS or S3, not in the memory system. The memory system holds a `raw_source` record (`source_type = "doc_chunk"`) with `source_ref` pointing to the originating storage location (bucket, object path, byte range). The raw artifact is not replicated.

**Relationship to the shared blob store:** These are two independent concerns. `source_ref` on a `doc_chunk` raw source is a provenance pointer — it records where the original document lives. `content_ref_type` / `content_ref_loc` are a storage mechanism — they record where the extracted content text is stored when it is too large to inline. A `doc_chunk` raw source may use both: `source_ref` pointing to the origin document in GCS/S3, and `content_ref_type`/`content_ref_loc` pointing to the blob store where the extracted passage text is held.

**Boundary contract:**
- Raw source records are immutable once written. If the source artifact changes or is deleted in GCS/S3, the `raw_source` record in the memory system is not updated. The `hash` field captures the content at capture time.
- Re-extraction from a modified document produces a new `raw_source` record with a different `hash`, not an in-place update.

### Shared Blob Store

Large `raw_source` content (above a configured byte threshold) is written to an external blob store rather than stored inline. The memory system and step runtime ledger both reference the same blob by `(ref_type, locator)`, so content is never duplicated regardless of how many subsystems reference it.

The blob store backend is pluggable. The memory system interacts with it only through the `BlobStore` interface (see §10). `ref_type` identifies the backend; `locator` is a backend-specific string whose format is defined by that backend (e.g. an S3 key, a GCS object path, a local filesystem path).

**Boundary contract:**
- The blob store is write-once from the memory system's perspective. Content is immutable once written, consistent with `raw_source` immutability.
- Observations (unit facts extracted from a raw source) are always stored inline — they are short by definition. A blob store outage does not prevent observation or fact reads; it only prevents re-reading the original large raw content.
- The `hash` field on `raw_source` covers the full content and serves as an integrity check regardless of storage location.
- If a blob is unreachable or deleted, the `raw_source` record remains valid as a provenance record; its content is simply unavailable until the blob is restored.

### Dependency Summary

| External system | What it holds | How memory system references it | Integrity enforcement |
|---|---|---|---|
| Step runtime ledger | Run / turn / step execution records | `source_ref` on `raw_source` | None — non-enforced pointer |
| Shared blob store (S3 / GCS / other) | Large raw source content above inline threshold | `content_ref_type` + `content_ref_loc` on `raw_source` | None — `hash` covers content integrity |
| Document store (GCS/S3) | Raw documents and artifacts | `source_ref` on `doc_chunk` raw source | None — `hash` captures content at capture time |
| Tool systems (GTAC, OBD-II, etc.) | Live data and case records | `source_ref` on `tool_call` / `tool_result` raw source | None — raw source is an immutable snapshot |

No external system has write access to the memory system. All writes flow through the agent as explicit step actions.

---

## 7. Write Path

The agent writes to the memory ledger explicitly as a step action — not via outbox subscription from the step runtime.

**Raw source selection policy:** Only raw sources that are upstream of at least one observation need to be stored — i.e., the agent stores a `RawSource` record only when it intends to extract observations from it. Raw sources with no derivation edges (messages or tool calls that the agent does not use as evidence) are not required to be stored; they remain in the step ledger only.

```
agent step action
  → append MemoryEvent to ledger
  → store RawSource (immutable, scoped):
      if byte_size < threshold  → content stored inline
      if byte_size >= threshold → BlobStore.store_blob(content)
                                    → set content_ref_type, content_ref_loc; null content
  → LLM extracts unit facts → N Observation records (immutable, scoped, always inline)
  → DerivationEdge links each Observation to its parent RawSource(s)
  → LLM emits structured MemoryOperation proposals from Observations:
      { operation, subject, predicate, object, confidence, derived_from[] }
  → deterministic validator checks each proposal
  → FactStore.assert_fact() commits with initial status:
      derived_from method = llm_extract       → status = inferred
      derived_from method = deterministic_rule → status = observed
      (status = proposed is only used for unvalidated drafts; never set after validation passes)
  → DerivationEdge links each FactAssertion to its parent Observation(s)
  → (optional) if fact depends on a conversation-scoped assumption:
      LLM emits a paired extract_conditional proposal:
        { predicate: conditional_rule,
          antecedent: [...],   ← tight: only conditions necessary for consequent
          consequent: {...} }
      FactStore.assert_fact() writes the conditional as global / domain,
        status = proposed, lower confidence than the original
      DerivationEdge links the conditional back to the conversation-scoped fact
      (preferred here — model has freshest context; can also occur at promotion time)
  → MemoryIndexRef schedules projection update
```

**The LLM never directly mutates canonical facts.** It proposes a structured operation; deterministic code validates and commits.

Projection updates (graph, vector, keyword) are written synchronously for small payloads on the hot path and deferred to the consolidation worker for heavier indexing.

---

## 8. Read Path (Retrieval Router)

```
retrieval request
  → classify query type
  → fetch current task state         (FactStore.get_current_facts)
  → fetch temporal facts as-of       (FactStore.get_facts_as_of)
  → traverse graph for related entities (GraphIndex.traverse)
  → retrieve similar prior tasks     (VectorIndex.search)
  → retrieve exact identifier matches (keyword search)
  → rerank / merge / deduplicate
  → return EvidenceBundle
```

**Query routing examples:**

| Query type | Retrieval strategy |
|---|---|
| "What changed before this event?" | temporal facts + event timeline |
| "Have we seen this pattern before?" | vector + keyword + graph |
| "Which entity/version is implicated?" | graph traversal + temporal validity |
| "Why did the agent conclude X?" | derivation DAG + observations + raw sources |
| "What is the latest confirmed state?" | current_facts view |

**EvidenceBundle contract:**

```json
{
  "query": "...",
  "hits": [
    {
      "object_type": "fact_assertion",
      "object_id": "...",
      "score": 0.91,
      "retrieval_path": ["graph", "temporal"],
      "summary": "...",
      "observations": ["...", "..."],
      "valid_from": "2026-06-10T00:00:00Z",
      "status": "confirmed"
    }
  ]
}
```

The agent cites evidence from the bundle rather than asserting "memory says."

---

## 9. Background Consolidation

**Trigger:** On-demand only in v1 (manual invocation or explicit API call). No automatic post-run or nightly triggers.

**Input:** New ledger events since the last consolidation checkpoint for a given scope.

**Output per consolidation run:**
- Observations extracted from raw sources (unit facts, one statement per record)
- Candidate facts derived from observations
- Candidate graph edges
- Task/session summary
- Lessons learned
- Retractions / supersessions for stale facts
- Retrieval index updates (vector, graph, keyword)

**Promotion gate:** A fact assertion is eligible for scope promotion (e.g., `conversation` → `global`) only when its confidence meets the configured threshold for that scope transition, and the promotion evaluator judges that its upstream sources hold true at the target scope. The evaluator traverses the full provenance chain — fact → observation → raw sources — and checks whether any upstream raw source is conversation-scoped (e.g. a user assumption or conversation-local input) that would not hold true outside that conversation. The policy is a versioned rule object; the initial implementation is a confidence threshold per scope transition plus a source-scope check. The policy structure is designed to accommodate richer rules (multi-source agreement, human review flag) in the future without schema changes.

**Conditional extraction at promotion time:** When the gate blocks a fact due to conversation-scoped upstream sources, the consolidation worker checks whether a conditional form was already extracted at assertion time (`status = proposed`). If one exists, the worker confirms or discards it. If none exists, the worker may attempt late conditional extraction using the original fact and its provenance chain. The **tight-condition principle** applies in both cases: the antecedent must contain only predicates strictly necessary for the consequent — not incidental conversational context. A tight antecedent makes the conditional testable against any future entity or context without reference to the original conversation. For example, extracting `IF has_recent_repair(battery) AND has_active_dtc(P0A80) THEN likely_cause = battery_replacement` is valid; including `IF technician_mentioned_this_in_session AND has_recent_repair(battery) AND ...` is not, because the first condition is conversation-specific and not evaluable in a new context.

**Contradiction handling during consolidation:** When two assertions conflict on the same `fact_key` within a scope, the consolidation worker:
1. Compares confidence values.
2. Marks the lower-confidence assertion as `contradiction_resolved`.
3. Retains both records in the ledger.
4. Logs the resolution in a `memory_event` with `event_type: contradiction_resolved`.

**Open Question:** At what scale does on-demand consolidation become a bottleneck? When should this shift to event-driven (post-run outbox) or scheduled? *(Deferred for v1.)*

---

## 10. Interfaces and Contracts

All application code depends on these interfaces. Backends are adapters.

```python
@dataclass
class Scope:
    scope_level: str           # conversation | global
    conversation_id: str | None  # non-null when scope_level = conversation
    subject_type: str          # universal | entity | domain | agent
    subject_ref: str | None    # "{type}:{id}" e.g. "vehicle:VIN123"; null for universal

class RawSourceStore:
    def store_raw_source(self, raw_source: RawSource) -> RawSourceId: ...
    def get_raw_source(self, source_id: str) -> RawSource: ...

class ObservationStore:
    def store_observation(self, observation: Observation) -> ObservationId: ...
    def get_observations(self, scope: Scope) -> list[Observation]: ...

class MemoryLedger:
    def append_event(self, event: MemoryEvent) -> EventId: ...
    def get_timeline(self, scope: Scope) -> list[MemoryEvent]: ...

class FactStore:
    def assert_fact(self, assertion: FactAssertion) -> FactAssertionId: ...
    def retract_fact(self, assertion_id: str, reason: str) -> None: ...
    def get_current_facts(self, scope: Scope) -> list[FactAssertion]: ...
    def get_facts_as_of(self, scope: Scope, as_of: datetime) -> list[FactAssertion]: ...

class ProvenanceStore:
    def link_derivation(self,
                        child_type: str,           # observation | fact | summary | ...
                        child_id: str,
                        parents: list[tuple[str, str]],  # [(parent_type, parent_id), ...]
                        method: str) -> None: ...  # llm_extract | deterministic_rule | human_review
    def explain(self, object_type: str, object_id: str) -> ProvenanceGraph: ...

class VectorIndex:
    def upsert(self, item: IndexedMemory) -> None: ...
    def search(self, query: str, filters: dict, k: int) -> list[SearchHit]: ...

class GraphIndex:
    def upsert_entity(self, entity: Entity) -> None: ...
    def upsert_relation(self, relation: Relation) -> None: ...
    def traverse(self, query: GraphQuery) -> list[GraphHit]: ...

class MemoryRetriever:
    def retrieve(self, request: RetrievalRequest) -> EvidenceBundle: ...

@dataclass
class BlobRef:
    ref_type: str   # s3 | gcs | azure_blob | local_fs | ...
    locator: str    # backend-specific string (S3 key, GCS object path, etc.)

class BlobStore:
    def store_blob(self, content: str) -> BlobRef: ...
    def retrieve_blob(self, ref_type: str, locator: str) -> str: ...
```

**Initial backend choices:**

| Interface | v1 backend | Upgrade path |
|---|---|---|
| `RawSourceStore` | Postgres `raw_source` table | — |
| `ObservationStore` | Postgres `observation` table | — |
| `MemoryLedger` | Postgres | — |
| `FactStore` | Postgres bitemporal tables | — |
| `ProvenanceStore` | Postgres `derivation_edge` | — |
| `VectorIndex` | pgvector | Qdrant, Weaviate |
| `GraphIndex` | Graphiti (optional in v1) | Neo4j, Zep |
| `MemoryRetriever` | Custom router | — |
| `BlobStore` | GCS | S3, Azure Blob, local filesystem |

---

## 11. Invariants

- The memory ledger is append-only. Raw sources and observations are immutable once written.
- The LLM never directly mutates canonical facts. It proposes structured operations; deterministic code commits.
- Every memory is explainable by a timeline and a provenance graph.
- Contradiction is not deletion. Contradictory assertions are retained and tagged.
- No fact may derive directly from a raw source. Every fact must have at least one observation as an intermediate parent in the derivation chain.
- Every observation is a single extracted unit fact — never a full message, passage, or multi-statement prose block.
- Every observation records derivation edges to the raw source(s) it was extracted from. The promotion gate traverses this chain to verify that no upstream raw source is conversation-scoped before promoting a fact to global scope.
- Raw sources, observations, and facts are scoped at write time with two independent fields: `scope_level` (conversation / global) and `subject_ref` (what entity or domain the record is about).
- Conversation-scoped facts are not readable outside their conversation until promoted through the policy gate.
- Subject reference (`subject_type` + `subject_ref`) stays stable during trust-level promotion. Subject type escalation (entity → domain) is a separate promotion path requiring cross-entity confirmation.
- `current_facts` is always a view over the fact assertions table, never a separately maintained mutable table.
- Every projection index entry has a corresponding `MemoryIndexRef` record that identifies its backend and embedding model.
- Conditional facts produced by `extract_conditional` have minimal antecedents: only predicates strictly necessary for the consequent. Incidental conversational context (e.g. session identifiers, speaker identity, turn position) must not appear as antecedent conditions — it would make the conditional unevaluable outside the original conversation.

---

## 12. Alternatives Considered

**Single vector DB as memory**
Rejected. Loses update semantics, temporal reasoning, exact identifier matching (IDs, codes, version strings), source attribution, and replay capability.

**Summaries as sole long-term memory**
Rejected. Summaries are lossy and non-auditable. They cannot answer "what source supported this conclusion?"

**LLM direct mutation of canonical facts**
Rejected. Introduces uncontrolled writes with no validation, provenance, or rollback. Recent memory-security research identifies this as a primary attack and integrity risk.

**Managed memory service (Mem0, Zep, Letta) as system of record**
Deferred. Useful as projection adapters behind the `GraphIndex` or `VectorIndex` interface. Not acceptable as the authoritative ledger because they do not provide deterministic provenance, exact bitemporal control, or SQL joins against the step runtime ledger.

**Outbox-driven integration with step runtime**
Deferred. The agent writing explicitly to the memory ledger as a step action is simpler for v1. Outbox subscription can be added when memory write volume justifies decoupling.

---

## 13. Tradeoffs

**Auditability vs hot-path latency**
Full provenance recording adds writes on the hot path. Mitigated by keeping the hot path minimal (raw sources + extracted observations + minimal candidate facts) and deferring heavy consolidation to on-demand background jobs.

**Pluggability vs operational simplicity**
Abstract interfaces require upfront discipline. The payoff is that any backend (pgvector → Qdrant, Graphiti → Neo4j) can be swapped without touching agent code. The cost is an extra indirection layer.

**Conversation-scoped safety vs global knowledge velocity**
Requiring a confidence threshold gate before promoting conversation-scoped facts to global scope prevents premature or incorrect pollution of shared knowledge. The cost is that global knowledge accumulates more slowly and only when consolidation is explicitly triggered.

**On-demand consolidation vs continuous**
On-demand is simpler and predictable for v1. The cost is that retrieval freshness depends on when consolidation was last run. Stale projections may affect retrieval quality between consolidation runs.

---

## 14. Risks and Mitigations

**Consolidation backlog under high run volume**
If many tasks complete without consolidation, the gap between raw sources and durable facts grows large. *Mitigation:* track last-consolidated checkpoint per scope; surface staleness in observability. *Detection:* alert when observation count since last consolidation exceeds a threshold.

**Entity resolution errors polluting the graph projection**
A wrong `merge_entity` operation links unrelated entities. *Mitigation:* `split_entity` operation is a first-class fact operation. Graph projection is a read index only; the ledger is not affected. *Detection:* graph traversal returning unexpected cross-task links.

**Embedding model drift invalidating vector indexes**
Changing the embedding model makes existing vector indexes semantically incompatible. *Mitigation:* `MemoryIndexRef` tracks `embedding_model` per indexed object; reindexing is a defined operation. *Open Question: full reindex strategy is not yet designed — see OQ #4.*

**LLM hallucinating high-confidence fact proposals**
A model-generated fact proposal carries a fabricated high confidence score, bypassing the promotion gate. *Mitigation:* confidence from model output is treated as `inferred`; only `confirmed` status (requires corroborating source or human validation) is eligible for the highest promotion tiers.

---

## 15. Open Questions

**OQ-3 Entity resolution.** How does the graph projection decide when two mentions refer to the same entity? Deterministic (exact ID match), model-driven (semantic similarity), or human-gated? This affects graph index correctness and the `merge_entity` / `split_entity` operation triggers. The answer is likely application-specific.

**OQ-4 Embedding versioning.** When the embedding model changes, what is the strategy for migrating or reindexing existing vector index entries? Is this a background reindex job, a versioned namespace, or a dual-read during transition?

**OQ-5 Scope boundary enforcement.** What prevents a conversation-scoped fact from being read outside its conversation before promotion? Is isolation enforced in the retrieval layer (scope filter on every query), in the schema (`scope_level` column on `fact_assertion`), or by convention? Currently enforced by convention — this should become an explicit retrieval-layer contract.

**OQ-7 Retention and archival policy.** How long are completed-task raw sources, observations, and fact assertions retained? Is there a data-lifecycle or compliance requirement that affects what can be stored or for how long?

**OQ-8 Security and access control.** Are memory scopes isolated by access control, or is isolation purely logical? Can a run with a conversation-scoped context read global domain facts freely? Can different `subject_ref` entities (e.g. `vehicle:VIN123` vs `vehicle:VIN456`) be isolated from each other?

---

## 16. Appendix

### A. Postgres Table Sketches

```sql
memory_event (
  event_id          uuid primary key,
  scope_level       text not null,   -- conversation | global
  conversation_id   text,            -- non-null when scope_level = conversation
  subject_type      text not null,   -- universal | entity | domain | agent
  subject_ref       text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  event_type        text not null,   -- tool_result, fact_asserted, fact_retracted,
                                   -- summary_created, contradiction_resolved
  actor_type      text not null,   -- user, agent, tool, system, reviewer
  actor_id        text,
  run_id          uuid,
  turn_id         uuid,
  step_id         uuid,
  payload         jsonb not null,
  event_hash      text not null,
  created_at      timestamptz not null default now()
);

raw_source (
  source_id         uuid primary key,
  scope_level       text not null,   -- conversation | global
  conversation_id   text,            -- non-null when scope_level = conversation
  subject_type      text not null,   -- universal | entity | domain | agent
  subject_ref       text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  source_type       text not null,   -- user_msg, tool_call, tool_result, doc_chunk, log_line
  source_ref        jsonb not null,  -- pointer to step ledger or external system
  content           text,            -- inline content; null when content is externalized
  content_ref_type  text,            -- blob store backend: s3 | gcs | azure_blob | local_fs | ...
  content_ref_loc   text,            -- backend-specific locator string
  byte_size         int not null,    -- full content size; used for inline vs external routing
  payload           jsonb,           -- structured metadata; always inline (small by design)
  observed_at       timestamptz,
  recorded_at       timestamptz not null default now(),
  hash              text not null,   -- hash of full content regardless of storage location
  unique (scope_level, conversation_id, subject_ref, hash),
  check (
    (content is not null and content_ref_type is null and content_ref_loc is null) or
    (content is null     and content_ref_type is not null and content_ref_loc is not null)
  )
);

observation (
  observation_id    uuid primary key,
  scope_level       text not null,   -- conversation | global
  conversation_id   text,            -- non-null when scope_level = conversation
  subject_type      text not null,   -- universal | entity | domain | agent
  subject_ref       text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  content            text not null,   -- single extracted unit fact statement
  derivation_basis   text not null,   -- observed | inferred | confirmed | deprecated
  recorded_at     timestamptz not null default now(),
  hash            text not null,
  unique (scope_level, conversation_id, subject_ref, hash)
  -- derivation edges to parent raw_source(s) are in derivation_edge, not inline
);

fact_assertion (
  assertion_id            uuid primary key,
  scope_level             text not null,   -- conversation | global
  conversation_id         text,            -- non-null when scope_level = conversation
  subject_type            text not null,   -- universal | entity | domain | agent
  subject_ref             text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  fact_key                text not null,   -- stable dedupe key
  subject                 text not null,
  predicate               text not null,
  object                  jsonb not null,
  status                  text not null,  -- proposed, observed, inferred, confirmed,
                                          -- contradicted, contradiction_resolved,
                                          -- retracted, superseded
  confidence              numeric,
  valid_from              timestamptz,
  valid_to                timestamptz,
  recorded_at             timestamptz not null default now(),
  retracted_at            timestamptz,
  supersedes_assertion_id uuid,
  created_by_run_id       uuid,
  attribution             jsonb not null  -- model_id, prompt_hash, tool_version
);

derivation_edge (
  child_type    text not null,   -- observation, fact, summary, graph_edge, vector_doc
  child_id      uuid not null,
  parent_type   text not null,   -- raw_source, observation, fact
  parent_id     uuid not null,
  method        text not null,   -- llm_extract, deterministic_rule, human_review
  model_id      text,
  prompt_hash   text,
  tool_version  text,
  created_at    timestamptz not null default now(),
  primary key (child_type, child_id, parent_type, parent_id)
);

memory_index_ref (
  object_type      text not null,  -- raw_source, observation, fact, summary
  object_id        uuid not null,
  index_type       text not null,  -- vector, graph, keyword
  backend          text not null,  -- pgvector, qdrant, graphiti, neo4j
  external_id      text not null,
  embedding_model  text,
  indexed_at       timestamptz not null default now(),
  primary key (object_type, object_id, index_type, backend)
);
```

### B. Tool Selection by Layer

| Layer | v1 tool | Upgrade path |
|---|---|---|
| System of record | Postgres (psycopg3, no ORM) | — |
| Vector search | pgvector | Qdrant, Weaviate, Milvus |
| Keyword search | Postgres FTS + pg_trgm | OpenSearch, Vespa |
| Graph projection | Graphiti (optional v1) | Neo4j, Zep |
| Temporal facts | Postgres bitemporal tables | — |
| Background jobs | Simple worker | Celery / RQ / Temporal / Arq |
| Observability | OpenTelemetry trace/span IDs in ledger | — |
| Raw artifact storage | GCS / S3 | — |
| Large content blob store (`BlobStore`) | GCS | S3, Azure Blob, local filesystem |

### C. Retrieval Query Routing Reference

| Query type | Retrieval strategy |
|---|---|
| What changed before this event? | temporal facts + event timeline |
| Have we seen this pattern before? | vector + keyword + graph |
| Which entity/version is implicated? | graph traversal + temporal validity |
| Why did the agent conclude X? | derivation DAG + observations + raw sources |
| What is the latest confirmed state? | current_facts view |
| Show full audit trail | memory_event timeline |
| Find similar prior tasks | vector search on task summaries |
| Exact identifier / code / version lookup | keyword (FTS + trigram) |

---

### D. Application Mapping: Vehicle Diagnostics

This section maps the generic memory system design onto a vehicle diagnostic agent (HAR/GTAC case workflow) and validates coverage.

#### Scope Mapping

**Trust level:**

| `scope_level` | `conversation_id` | Vehicle diagnostic meaning |
|---|---|---|
| `conversation` | e.g. `conv-HAR-4521` | Facts within one active diagnostic case that depend on technician inputs or unverified user assertions |
| `global` | null | Verified facts safe to use across any case or query |

**Subject reference:**

| `subject_type` | `subject_ref` example | Vehicle diagnostic meaning |
|---|---|---|
| `entity` | `vehicle:VIN123` | Facts about a specific vehicle — ECU versions, repair history, active DTCs |
| `entity` | `case:HAR-4521` | Facts about a specific diagnostic case — conclusion, ruled-out hypotheses |
| `domain` | `dtc:P0A80` | Fleet-wide patterns for a DTC — correlated firmware versions, common repair outcomes |
| `domain` | `firmware:ECU_FW_2.3.1` | Known issues associated with a firmware version across the fleet |
| `agent` | `agent:diag-v2` | Procedural lessons for the diagnostic agent — tool misuse patterns, planning failures |
| `universal` | null | Broadly applicable rules not tied to a specific entity or domain |

**Example combinations:**

| scope_level | subject_type | subject_ref | Meaning |
|---|---|---|---|
| `conversation` | `entity` | `vehicle:VIN123` | Technician assertion about VIN123 in this case — unverified |
| `global` | `entity` | `vehicle:VIN123` | Confirmed durable knowledge about VIN123 |
| `global` | `domain` | `dtc:P0A80` | Fleet-wide verified pattern for P0A80 |
| `global` | `agent` | `agent:diag-v2` | Diagnostic agent procedural lessons |

#### Raw Source Mapping

| `source_type` | Vehicle diagnostic example |
|---|---|
| `tool_call` | GTAC case query invocation with parameters, OBD-II scan request |
| `tool_result` | GTAC case query response, OBD-II scan output, live data stream snapshot |
| `doc_chunk` | Service bulletin paragraph, repair manual section |
| `log_line` | Timestamped voltage drop in vehicle log, CAN bus trace entry |
| `user_msg` | Technician note ("battery replaced last week"), customer complaint |

Observations (unit facts) are extracted from these raw sources. Examples:
- From `user_msg` "Battery replaced last week, DTC P0A80 active" → two observations: "battery was replaced" and "DTC P0A80 is active"
- From `tool_result` GTAC response → observations for each distinct fact in the response (DTC status, software version, repair history entries)

#### Fact Assertion Mapping

Generic `subject / predicate / object` maps naturally to diagnostic facts:

| Subject | Predicate | Object | Status |
|---|---|---|---|
| `vehicle:VIN123` | `has_active_dtc` | `P0A80` | `observed` |
| `vehicle:VIN123` | `has_software_version` | `ECU_FW_2.3.1` | `confirmed` |
| `vehicle:VIN123` | `had_repair` | `battery_replacement` | `confirmed` |
| `dtc:P0A80` | `correlates_with` | `ECU_FW_2.3.1` | `inferred` |
| `case:HAR-4521` | `conclusion` | `ECU_firmware_fault` | `confirmed` |
| `cause:low_voltage` | `ruled_out_for` | `case:HAR-4521` | `confirmed` |

Bitemporal fields are essential here: `valid_from` / `valid_to` capture when a software version was installed or a DTC was active; `recorded_at` captures when the agent learned it — these differ when a technician reports a past repair.

#### Entity Graph Shape

The graph projection for vehicle diagnostics has a natural shape:

```
case → vehicle → ECU → software_version → DTC → symptom → test_result → repair → outcome
```

Each edge is a `FactAssertion` with derivation edges to the observations that established it, which in turn trace back to the raw sources. The `split_entity` and `merge_entity` operations handle cases where a VIN is mis-transcribed or two case records refer to the same vehicle.

#### Confidence Level Mapping

| Level | Vehicle diagnostic meaning |
|---|---|
| `observed` | DTC directly read from OBD-II scan or GTAC tool result |
| `inferred` | Agent hypothesis derived from symptom pattern or prior case similarity |
| `confirmed` | Validated by a second source (technician confirmation, corroborating log entry, or second tool) |
| `deprecated` | Superseded by a newer scan, retracted by technician, or ruled out by test result |

#### Retrieval Query Mapping

| Diagnostic question | Query type | Retrieval strategy |
|---|---|---|
| "What DTCs were active before the fault?" | temporal — what changed | temporal facts + event timeline |
| "Have we seen P0A80 + ECU_FW_2.3.1 before?" | pattern — prior cases | vector + keyword + graph |
| "Which ECU software version is implicated?" | relational — entity state | graph traversal + temporal validity |
| "Why did the agent conclude ECU fault?" | audit — reasoning trace | derivation DAG + observations + raw sources |
| "Latest confirmed diagnosis for VIN123?" | current state | current_facts view |
| "Full audit trail for case HAR-4521" | audit — full timeline | memory_event timeline |
| "Similar prior cases with DTC P0A80" | similar cases | vector search on task summaries |
| "VIN / DTC / part number exact lookup" | exact identifier | keyword (FTS + trigram) |

#### Gap Analysis

The following diagnostic requirements are covered by the generic design with no gaps:

| Diagnostic requirement | Covered by |
|---|---|
| Track DTCs per vehicle over time | `global` / `entity` / `vehicle:VIN` + bitemporal `fact_assertion` |
| Link DTC to software version and repair | `GraphIndex` edges + `derivation_edge` |
| Audit trail: why did agent conclude X? | `ProvenanceStore.explain()` + `derivation_edge` |
| Cross-case fleet pattern accumulation | `global` / `domain` subject + promotion policy |
| Contradictory evidence (two conflicting diagnoses) | `contradict_fact` operation + `contradiction_resolved` status |
| Technician overrides agent conclusion | `supersede_fact` with `actor_type: user` |
| Retrieve similar prior cases | `VectorIndex.search` on task summaries |
| Exact VIN / DTC / part number lookup | keyword index (Postgres FTS + trigram) |
| Replay: what did we know at case open? | `FactStore.get_facts_as_of(as_of=case_open_time)` |
| Ruled-out hypotheses preserved for audit | `retract_fact` (not delete) — retained in ledger |

**No gaps identified** for the vehicle diagnostic domain. All diagnostic-specific requirements map cleanly to the generic design.

One domain-specific consideration worth noting: entity resolution (OQ-3) is straightforward for vehicles because VIN is a globally unique, deterministic identifier. The `merge_entity` / `split_entity` operations exist for mis-transcription correction, not semantic disambiguation. This makes vehicle diagnostics a simpler case of OQ-3 than domains where entity identity is ambiguous.
