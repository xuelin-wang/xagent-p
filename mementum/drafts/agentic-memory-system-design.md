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

Agent runs today produce observations and conclusions with no durable, auditable record of what was believed, when it was believed, and why. Each run starts with no structured memory of prior cases, vehicle history, or learned diagnostic patterns.

This design introduces a **memory control plane**: an append-only authoritative ledger backed by Postgres, with multiple replaceable projection indexes (temporal, graph, vector, keyword). The agent explicitly writes observations and fact proposals as step actions; a separate consolidation job promotes raw observations into durable facts and lessons on-demand.

**Core invariant:** Every memory must be explainable by a timeline and a provenance graph.

**Main design decision:** Separate the immutable source of truth (ledger + fact assertions) from replaceable read indexes (vector, graph, keyword). Backends are swappable; the ledger is not.

**Most important tradeoff:** Full provenance and bitemporal tracking add write overhead and schema complexity on the hot path. This is mitigated by keeping the hot path minimal (raw observations only) and deferring promotion to on-demand consolidation.

---

## 2. Background and Problem

The current agent runtime records step executions and tool calls in the step ledger, but does not maintain structured memory across runs or cases. This means:

- Prior diagnostic conclusions for the same vehicle are not retrievable in structured form.
- There is no way to ask "what did we believe on June 10, and what changed it?"
- Fleet-level patterns (recurring DTCs, known bad software versions) cannot accumulate from case history.
- Agent reasoning cannot be audited by tracing a conclusion back to its source observations.

A single vector database is not a solution. It provides semantic retrieval but loses update semantics, temporal reasoning, exact code matching (VINs, DTCs, part numbers), and source attribution. Summaries as sole long-term memory are lossy and non-auditable.

The diagnostic domain specifically requires bitemporal facts: vehicle state, software versions, repairs, and symptoms change over time, and the system must distinguish *when something was true* from *when it was learned*.

---

## 3. Goals and Non-Goals

**Goals**

- Full provenance: every fact traces to source observations, which trace to tool calls, runs, and turns.
- Bitemporal correctness: track both valid time (real world) and transaction time (system learned).
- Pluggable projections: graph, vector, and keyword indexes are adapters behind interfaces; each can be replaced independently.
- Safe scope promotion: case-local facts do not become fleet knowledge without passing a policy gate.
- Structured retrieval: every memory read returns an evidence bundle with citations, not raw text.

**Non-Goals**

- Real-time memory sync across replicas or distributed agents.
- Replacing the existing step runtime ledger — the step ledger remains authoritative for execution records; the memory system is a downstream consumer.
- Managing raw document storage (that stays in GCS/S3).
- Automatic consolidation triggers — consolidation is on-demand only in v1.

---

## 4. Core Concepts and Data Model

### Memory Scopes

All facts and observations are scoped. Four scopes are defined:

| Scope | What it contains |
|---|---|
| `case_memory` | Facts and evidence for one diagnostic case |
| `vehicle_memory` | Vehicle-specific history: VIN, ECU versions, prior repairs, prior DTCs |
| `fleet_memory` | Cross-case patterns, known issues, recurring fixes |
| `agent_memory` | Procedural lessons: tool usage mistakes, planning failures, evaluation outcomes |

Case facts are not readable as fleet knowledge until promoted through a policy gate.

### Confidence Levels

| Level | Meaning |
|---|---|
| `observed` | Directly from a source, tool result, or log |
| `inferred` | Derived by model or deterministic rule |
| `confirmed` | Validated by an additional source or human |
| `deprecated` | Superseded, retracted, or invalidated |

### Core Entities

**SourceObservation** — what a source actually produced. Immutable once written.

Fields: `observation_id`, `source_type` (user_msg / tool_result / doc_chunk / log_line / model_output), `source_ref` (exact tool/run/message reference), `content`, `payload`, `observed_at`, `recorded_at`, `hash`.

**FactAssertion** — the system's interpretation. Versioned, never overwritten in place.

Fields: `assertion_id`, `scope_type`, `scope_id`, `fact_key` (stable dedupe key), `subject`, `predicate`, `object`, `status`, `confidence`, `valid_from`, `valid_to`, `recorded_at`, `retracted_at`, `supersedes_assertion_id`, `attribution` (model_id, prompt_hash, tool_version, run_id).

**Status values:** `proposed` → `observed` / `inferred` / `confirmed` → `contradicted` / `retracted` / `superseded`

**CurrentFacts** — a view, not a mutable row:

```sql
current_facts = latest non-retracted assertions
                where valid_to is null
                and status in ('observed', 'inferred', 'confirmed')
```

**DerivationEdge** — links a derived fact or summary to its parent observations or facts. Records `method` (llm_extract / deterministic_rule / human_review), `model_id`, `prompt_hash`, `tool_version`.

**MemoryIndexRef** — tracks which external indexes (pgvector, Qdrant, Graphiti, Neo4j) contain a given object, and with which embedding model.

### Fact Operations

| Operation | Meaning |
|---|---|
| `assert_fact` | Add a new claim |
| `confirm_fact` | Mark a claim as validated |
| `supersede_fact` | Replace an old claim with a newer one |
| `contradict_fact` | Mark a conflict between two claims; resolve by confidence |
| `retract_fact` | Withdraw a claim |
| `close_validity` | Fact was true but is no longer true (set `valid_to`) |
| `merge_entity` | Entity resolution: two nodes are the same |
| `split_entity` | Undo a bad entity merge |

**Contradiction resolution policy:** When two assertions conflict, the one with higher confidence is kept as active; the lower-confidence assertion is tagged `contradiction_resolved` (not deleted). Both records are retained for audit.

### Promotion Ladder

```
case observation
  → case fact
  → case conclusion
  → fleet/global diagnostic knowledge   (requires confidence threshold policy gate)
```

The promotion policy is a configurable rule: an assertion must reach a defined confidence threshold before it is eligible for promotion to a broader scope. The policy structure is extensible but starts with a threshold check.

---

## 5. Proposed Architecture

```
┌─────────────────────────────────────────┐
│  Agent / Planner / Tools                │
│  (writes to memory as a step action)    │
└────────────────┬────────────────────────┘
                 │  MemoryLedger.append_event()
                 │  FactStore.assert_fact()
                 ▼
┌─────────────────────────────────────────┐
│  Authoritative Memory Ledger            │
│  Postgres: memory_event,                │
│  source_observation, fact_assertion,    │
│  derivation_edge, memory_index_ref      │
└───────────────┬─────────────────────────┘
                │  outbox → projection updates
                │  (on-demand consolidation)
    ┌───────────┼───────────┬────────────────┐
    ▼           ▼           ▼                ▼
┌────────┐ ┌────────┐ ┌─────────┐    ┌────────────┐
│Temporal│ │ Graph  │ │ Vector  │    │  Keyword   │
│ facts  │ │Graphiti│ │pgvector │    │ Postgres   │
│Postgres│ │/ Neo4j │ │/ Qdrant │    │ FTS+trgm   │
└────────┘ └────────┘ └─────────┘    └────────────┘
                 │
                 ▼
        MemoryRetriever
        (retrieval router → evidence bundle)
```

**Four layers:**

1. **Authoritative ledger** — Postgres. Append-only. Never overwritten. Source of truth for all facts, observations, and derivations.
2. **Fact store** — Postgres. Versioned fact assertions with bitemporal fields. `current_facts` is a view.
3. **Projection indexes** — Temporal (Postgres bitemporal views), Graph (Graphiti/Neo4j), Vector (pgvector first), Keyword (Postgres FTS + pg_trgm). Each is an adapter behind an interface.
4. **Retrieval router** — `MemoryRetriever` classifies the query, fans out to appropriate projections, merges results, and returns a structured evidence bundle.

---

## 6. Write Path

The agent writes to the memory ledger explicitly as a step action — not via outbox subscription from the step runtime.

```
agent step action
  → append MemoryEvent to ledger
  → store SourceObservation (immutable)
  → LLM emits structured MemoryOperation proposal:
      { operation, subject, predicate, object, confidence, derived_from[] }
  → deterministic validator checks proposal
  → FactStore.assert_fact() commits
  → DerivationEdge links fact to source observations
  → MemoryIndexRef schedules projection update
```

**The LLM never directly mutates canonical facts.** It proposes a structured operation; deterministic code validates and commits.

Projection updates (graph, vector, keyword) are written synchronously for small payloads on the hot path and deferred to the consolidation worker for heavier indexing.

---

## 7. Read Path (Retrieval Router)

```
retrieval request
  → classify query type
  → fetch current case state        (FactStore.get_current_facts)
  → fetch temporal facts as-of      (FactStore.get_facts_as_of)
  → traverse graph for related entities (GraphIndex.traverse)
  → retrieve similar prior cases    (VectorIndex.search)
  → retrieve exact code/VIN matches (keyword search)
  → rerank / merge / deduplicate
  → return EvidenceBundle
```

**Query routing examples:**

| Query type | Retrieval strategy |
|---|---|
| "What changed before the fault?" | temporal facts + event timeline |
| "Have we seen this DTC before?" | vector + keyword + graph |
| "Which ECU/software version is implicated?" | graph traversal + temporal validity |
| "Why did the agent conclude X?" | derivation DAG + source observations |
| "What is the latest confirmed diagnosis?" | current_facts view |

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
      "source_observations": ["...", "..."],
      "valid_from": "2026-06-10T00:00:00Z",
      "status": "confirmed"
    }
  ]
}
```

The agent cites evidence from the bundle rather than asserting "memory says."

---

## 8. Background Consolidation

**Trigger:** On-demand only in v1 (manual invocation or explicit API call). No automatic post-run or nightly triggers.

**Input:** New ledger events since the last consolidation checkpoint for a given scope.

**Output per consolidation run:**
- Candidate facts extracted from raw observations
- Candidate graph edges
- Case summary
- Lessons learned
- Retractions / supersessions for stale facts
- Retrieval index updates (vector, graph, keyword)

**Promotion gate:** A fact assertion is eligible for scope promotion (e.g., `case_memory` → `fleet_memory`) only when its confidence meets the configured threshold for that scope transition. The policy is a versioned rule object; the initial implementation is a single numeric threshold per scope transition. The policy structure is designed to accommodate richer rules (multi-source agreement, human review flag) in the future without schema changes.

**Contradiction handling during consolidation:** When two assertions conflict on the same `fact_key` within a scope, the consolidation worker:
1. Compares confidence values.
2. Marks the lower-confidence assertion as `contradiction_resolved`.
3. Retains both records in the ledger.
4. Logs the resolution in a `memory_event` with `event_type: contradiction_resolved`.

**Open Question:** At what scale does on-demand consolidation become a bottleneck? When should this shift to event-driven (post-run outbox) or scheduled? *(Deferred for v1.)*

---

## 9. Interfaces and Contracts

All application code depends on these interfaces. Backends are adapters.

```python
class MemoryLedger:
    def append_event(self, event: MemoryEvent) -> EventId: ...
    def get_timeline(self, scope: Scope) -> list[MemoryEvent]: ...

class FactStore:
    def assert_fact(self, assertion: FactAssertion) -> FactAssertionId: ...
    def retract_fact(self, assertion_id: str, reason: str) -> None: ...
    def get_current_facts(self, scope: Scope) -> list[FactAssertion]: ...
    def get_facts_as_of(self, scope: Scope, as_of: datetime) -> list[FactAssertion]: ...

class ProvenanceStore:
    def link_derivation(self, child_id: str, parent_ids: list[str], method: str) -> None: ...
    def explain(self, object_id: str) -> ProvenanceGraph: ...

class VectorIndex:
    def upsert(self, item: IndexedMemory) -> None: ...
    def search(self, query: str, filters: dict, k: int) -> list[SearchHit]: ...

class GraphIndex:
    def upsert_entity(self, entity: Entity) -> None: ...
    def upsert_relation(self, relation: Relation) -> None: ...
    def traverse(self, query: GraphQuery) -> list[GraphHit]: ...

class MemoryRetriever:
    def retrieve(self, request: RetrievalRequest) -> EvidenceBundle: ...
```

**Initial backend choices:**

| Interface | v1 backend | Upgrade path |
|---|---|---|
| `MemoryLedger` | Postgres | — |
| `FactStore` | Postgres bitemporal tables | — |
| `ProvenanceStore` | Postgres `derivation_edge` | — |
| `VectorIndex` | pgvector | Qdrant, Weaviate |
| `GraphIndex` | Graphiti (optional in v1) | Neo4j, Zep |
| `MemoryRetriever` | Custom router | — |

---

## 10. Invariants

- The memory ledger is append-only. Source observations are immutable once written.
- The LLM never directly mutates canonical facts. It proposes structured operations; deterministic code commits.
- Every memory is explainable by a timeline and a provenance graph.
- Contradiction is not deletion. Contradictory assertions are retained and tagged.
- Case facts are not readable as fleet knowledge until promoted through the policy gate.
- `current_facts` is always a view over the fact assertions table, never a separately maintained mutable table.
- Every projection index entry has a corresponding `MemoryIndexRef` record that identifies its backend and embedding model.

---

## 11. Alternatives Considered

**Single vector DB as memory**
Rejected. Loses update semantics, temporal reasoning, exact code matching (VINs, DTCs), source attribution, and replay capability.

**Summaries as sole long-term memory**
Rejected. Summaries are lossy and non-auditable. They cannot answer "what source supported this conclusion?"

**LLM direct mutation of canonical facts**
Rejected. Introduces uncontrolled writes with no validation, provenance, or rollback. Recent memory-security research identifies this as a primary attack and integrity risk.

**Managed memory service (Mem0, Zep, Letta) as system of record**
Deferred. Useful as projection adapters behind the `GraphIndex` or `VectorIndex` interface. Not acceptable as the authoritative ledger because they do not provide deterministic provenance, exact bitemporal control, or SQL joins against the step runtime ledger.

**Outbox-driven integration with step runtime**
Deferred. The agent writing explicitly to the memory ledger as a step action is simpler for v1. Outbox subscription can be added when memory write volume justifies decoupling.

---

## 12. Tradeoffs

**Auditability vs hot-path latency**
Full provenance recording adds writes on the hot path. Mitigated by keeping the hot path minimal (raw observations + minimal candidate facts only) and deferring heavy consolidation to on-demand background jobs.

**Pluggability vs operational simplicity**
Abstract interfaces require upfront discipline. The payoff is that any backend (pgvector → Qdrant, Graphiti → Neo4j) can be swapped without touching agent code. The cost is an extra indirection layer.

**Case-local safety vs fleet knowledge velocity**
Requiring a confidence threshold gate before promoting case facts to fleet knowledge prevents premature or incorrect pollution of shared knowledge. The cost is that fleet knowledge accumulates more slowly and only when consolidation is explicitly triggered.

**On-demand consolidation vs continuous**
On-demand is simpler and predictable for v1. The cost is that retrieval freshness depends on when consolidation was last run. Stale projections may affect retrieval quality between consolidation runs.

---

## 13. Risks and Mitigations

**Consolidation backlog under high run volume**
If many cases close without consolidation, the gap between raw observations and durable facts grows large. *Mitigation:* track last-consolidated checkpoint per scope; surface staleness in observability. *Detection:* alert when observation count since last consolidation exceeds a threshold.

**Entity resolution errors polluting the graph projection**
A wrong `merge_entity` operation links unrelated vehicles or ECUs. *Mitigation:* `split_entity` operation is a first-class fact operation. Graph projection is a read index only; the ledger is not affected. *Detection:* graph traversal returning unexpected cross-case links.

**Embedding model drift invalidating vector indexes**
Changing the embedding model makes existing vector indexes semantically incompatible. *Mitigation:* `MemoryIndexRef` tracks `embedding_model` per indexed object; reindexing is a defined operation. *Open Question: full reindex strategy is not yet designed — see OQ #4.*

**LLM hallucinating high-confidence fact proposals**
A model-generated fact proposal carries a fabricated high confidence score, bypassing the promotion gate. *Mitigation:* confidence from model output is treated as `inferred`; only `confirmed` status (requires corroborating source or human validation) is eligible for the highest promotion tiers.

---

## 14. Open Questions

**OQ-3 Entity resolution.** How does the graph projection decide when two mentions refer to the same entity? Deterministic (VIN match), model-driven, or human-gated? This affects graph index correctness and the `merge_entity` / `split_entity` operation triggers.

**OQ-4 Embedding versioning.** When the embedding model changes, what is the strategy for migrating or reindexing existing vector index entries? Is this a background reindex job, a versioned namespace, or a dual-read during transition?

**OQ-5 Scope boundary enforcement.** What prevents a case-local fact from being read as fleet knowledge before promotion? Is isolation enforced in the retrieval layer (scope filter on every query), in the schema (`scope_type` column on `fact_assertion`), or by convention? Currently enforced by convention — this should become an explicit retrieval-layer contract.

**OQ-7 Retention and archival policy.** How long are closed-case source observations and fact assertions retained? Is there a data-lifecycle or compliance requirement that affects what can be stored or for how long?

**OQ-8 Security and access control.** Are memory scopes isolated by access control, or is isolation purely logical? Can a run scoped to `case_memory` read `fleet_memory` freely?

---

## 15. Appendix

### A. Postgres Table Sketches

```sql
memory_event (
  event_id        uuid primary key,
  scope_type      text not null,   -- case, vehicle, fleet, agent
  scope_id        text not null,
  event_type      text not null,   -- tool_result, fact_asserted, fact_retracted,
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

source_observation (
  observation_id  uuid primary key,
  source_type     text not null,   -- user_msg, tool_result, doc_chunk, log_line
  source_ref      jsonb not null,
  content         text,
  payload         jsonb,
  observed_at     timestamptz,
  recorded_at     timestamptz not null default now(),
  hash            text not null unique
);

fact_assertion (
  assertion_id            uuid primary key,
  scope_type              text not null,
  scope_id                text not null,
  fact_key                text not null,  -- stable dedupe key
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
  child_type    text not null,   -- fact, summary, graph_edge, vector_doc
  child_id      uuid not null,
  parent_type   text not null,   -- observation, fact, document, tool_call
  parent_id     uuid not null,
  method        text not null,   -- llm_extract, deterministic_rule, human_review
  model_id      text,
  prompt_hash   text,
  tool_version  text,
  created_at    timestamptz not null default now(),
  primary key (child_type, child_id, parent_type, parent_id)
);

memory_index_ref (
  object_type      text not null,  -- observation, fact, case_summary, doc_chunk
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

### C. Retrieval Query Routing Reference

| Query type | Retrieval strategy |
|---|---|
| What changed before the fault? | temporal facts + event timeline |
| Have we seen this DTC before? | vector + keyword + graph |
| Which ECU/software version is implicated? | graph traversal + temporal validity |
| Why did the agent conclude X? | derivation DAG + source observations |
| What is the latest confirmed diagnosis? | current_facts view |
| Show full audit trail | memory_event timeline |
| Find similar prior cases | vector search on case summaries |
| Exact VIN / DTC / part number lookup | keyword (FTS + trigram) |
