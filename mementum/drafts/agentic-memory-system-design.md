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

This design introduces a **memory control plane** backed by Postgres, with multiple replaceable projection indexes (graph, vector, keyword). Canonical Postgres rows—raw sources, observations, fact assertions, fact relations, and derivation edges—are append-only. `memory_event` is an audit timeline over those records, not a second source of truth. The agent writes raw sources, observations, and validated fact proposals as explicit step actions; an on-demand consolidation job can add corroborated facts, lifecycle relations, and projection updates.

**Core invariant:** Every fact must be explainable through canonical provenance to captured raw sources. Cross-system pointers may be unavailable under their own retention policies, and retrieval must report that boundary explicitly.

**Main design decision:** Separate canonical append-only domain records in Postgres from replaceable read indexes. Fact lifecycle changes create new assertions or immutable relations; canonical assertions are never updated in place.

**Most important tradeoff:** Full provenance and bitemporal tracking add write overhead and schema complexity. The hot path writes only records needed by the semantic owner step; cross-record consolidation and heavy indexing remain asynchronous and on-demand in v1.

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
- Enforced isolation: trust scope and authorization scope are separate, mandatory filters on canonical and projected reads.

**Non-Goals**

- Real-time memory sync across replicas or distributed agents.
- Replacing the existing step runtime ledger — the step ledger remains authoritative for execution records; the memory system is a downstream consumer.
- Managing raw document storage (that stays in GCS/S3).
- Automatic consolidation triggers — consolidation is on-demand only in v1.
- Model-generated global conditional rules. V1 may store them as conversation-scoped proposals, but global publication requires independent corroboration or human approval.

---

## 4. Core Concepts and Data Model

### Memory Scopes and Authorization

All raw sources, observations, and facts carry three independent dimensions:

1. `tenant_id`: the authorization boundary. It is mandatory and immutable.
2. `scope_level` plus `conversation_id`: the evidentiary trust boundary.
3. `subject_type` plus `subject_ref`: what the record is about.

`scope_level` is not an access-control mechanism. Every canonical read, projection write, projection query, and provenance expansion is filtered by an `AccessContext` containing `tenant_id`, principal identity, and permitted subject boundaries. No API accepts an unscoped query. Global means reusable within an authorized tenant, not publicly readable or cross-tenant.

Raw content and derived memory may contain sensitive runtime data. Canonical databases and blobs use platform encryption at rest and TLS in transit. Audit events contain canonical IDs and minimal metadata, not raw prompts, tool payloads, or document text. Projection adapters receive only the minimum authorized fields needed for their query type. Application logs follow the repository rule against recording raw prompts, responses, tool payloads, full documents, or embeddings.

**Axis 1 — Trust level** (can this fact be used outside this conversation?)

| Level | Meaning |
|---|---|
| `conversation` | Depends on input messages or user assertions in a specific conversation. Not valid as evidence outside that conversation until promoted. |
| `global` | Accepted by a versioned policy as independent of conversational assumptions. Reusable within authorized tenant and subject boundaries. |

**Axis 2 — Subject reference** (what is this fact about, and how is it looked up?)

| Subject type | Meaning | Required identifier fields |
|---|---|---|
| `universal` | No specific subject — broadly applicable | — |
| `entity` | A named, identifiable thing | `entity_type` (e.g. vehicle, user, project, device) + `entity_id` (e.g. VIN, user_id) |
| `domain` | A category or cross-entity pattern | `domain_type` (e.g. dtc_pattern, firmware_class) + `domain_key` |
| `agent` | Procedural knowledge for a specific agent instance | `agent_id` |

`subject_ref` encodes both type and identifier as `{type}:{id}` (e.g. `vehicle:VIN123`, `dtc:P0A80`) so both are recoverable from a single indexed column without a join.

The primary promotion axis is trust level: `conversation` → `global`. Subject reference typically stays stable during promotion — a fact about `vehicle:VIN123` remains about that vehicle whether conversation-scoped or global. A separate promotion path escalates subject type when a pattern found across many entity-level facts qualifies as `domain` knowledge.

Conversation-scoped facts are not readable outside their conversation until a new global assertion is created through the policy gate. The original assertion remains conversation-scoped and active in its original context.

### Derivation Basis and Lifecycle

`derivation_basis` records how content was produced. It is distinct from assertion lifecycle.

| Value | Meaning |
|---|---|
| `observed` | Deterministically extracted from a structured source using a fixed parsing rule — no model judgment required (e.g. reading a named JSON field, applying a known log schema). The value is directly present in the source; the extraction rule is deterministic and not subject to model interpretation. |
| `inferred` | Extracted by a model or inferential process — including LLM-based extraction from structured sources where identifying the relevant facts, their granularity, or their mapping to subject/predicate/object triples requires model judgment. Most observations from user messages, free-text fields, and semi-structured tool responses are inferred. |
| `confirmed` | Validated by a corroborating source or human review |

Fact assertions use `assertion_status = proposed | observed | inferred | confirmed`. Terminal lifecycle changes are represented by immutable `FactRelation` rows (`supersedes`, `retracts`, `contradicts`, `corroborates`) rather than updates to the assertion. A numeric `confidence` is one promotion input; model confidence alone never authorizes promotion or contradiction resolution.

### Bitemporal Semantics

Fact assertions have two independent time dimensions:

- Valid time: `[valid_from, valid_to)`, when the claim is true in the represented world. Either bound may be open.
- Knowledge time: `known_at`, when the immutable assertion entered the canonical store.

Because assertions and lifecycle relations are append-only, knowledge-time history is reconstructed by considering only assertions and relations whose `known_at <= knowledge_as_of`. A later correction never changes what an earlier knowledge-time query returns.

The APIs use explicit parameters:

```python
get_facts(
    scope: ReadScope,
    *,
    valid_at: datetime | None,
    knowledge_as_of: datetime,
) -> list[FactAssertion]
```

`valid_at=None` means no valid-time filter. There is no ambiguous single `as_of` parameter.

### Core Entities

**RawSource** — immutable capture of what an external system produced. Never a fact or interpretation — only what the source actually emitted. Never overwritten.

Fields: `source_id`, `tenant_id`, `scope_level`, `conversation_id`, `subject_type`, `subject_ref`, `source_type`, `source_ref`, `content`, `content_ref_type`, `content_ref_loc`, `byte_size`, `payload`, `observed_at`, `known_at`, `hash`, `operation_key`.

`content` and `content_ref_type` / `content_ref_loc` are mutually exclusive: small payloads are stored inline in `content`; large payloads are written to an external blob store and `content` is null. `content_ref_type` identifies the storage backend (`s3`, `gcs`, `azure_blob`, `local_fs`, …); `content_ref_loc` is a backend-specific locator string. Retrieval is via `BlobStore.retrieve_blob(ref_type, locator)`. `byte_size` is always set and is used to make the inline-vs-external routing decision. The step runtime ledger can reference the same blob by the same `(content_ref_type, content_ref_loc)` pair, avoiding duplication. `hash` covers the full content regardless of where it is stored.

Raw sources are scoped at write time. The same content in two different scopes produces two distinct scoped records.

**Observation** — a single extracted unit fact, always derived from one or more raw sources via `DerivationEdge`. Never a full message or prose passage — always one statement. Immutable once written.

Fields: `observation_id`, `tenant_id`, `scope_level`, `conversation_id`, `subject_type`, `subject_ref`, `content`, `derivation_basis`, `known_at`, `hash`, `operation_key`.

Observations are scoped at write time. **Scope inheritance:** an observation always inherits `scope_level` and `conversation_id` from its parent raw source—an observation cannot be less restricted than its source. `subject_type` and `subject_ref` may be set more specifically by the extractor. A conversation-scoped observation is never widened in place; promotion requires a new global observation from independently acceptable evidence or an attributed human review. Provenance—which raw sources the observation was extracted from—is recorded in `DerivationEdge`, not inline.

**FactAssertion** — the system's interpretation. Versioned, never overwritten in place.

Fields: `assertion_id`, `tenant_id`, `scope_level`, `conversation_id`, `subject_type`, `subject_ref`, `fact_key`, `subject`, `predicate`, `object`, `assertion_status`, `confidence`, `valid_from`, `valid_to`, `known_at`, `attribution`, `operation_key`.

`operation_key` identifies one logical command. Each row also receives a deterministic record suffix when a command creates multiple rows, for example `{operation_key}:observation:2`; uniqueness constraints use the resulting row key. This makes retry idempotent without limiting a command to one observation or assertion.

**`subject_ref` vs `subject`:** `subject_ref` is the retrieval and scoping key — it identifies which entity or domain this fact belongs to for index lookups and scope filtering. `subject` / `predicate` / `object` is the semantic triple — the actual claim. For entity-scoped facts they are often the same value (e.g. both `vehicle:VIN123`), but they can differ: a fact scoped to `vehicle:VIN123` (`subject_ref`) might have a triple like `subject=vehicle:VIN123, predicate=correlates_with, object=dtc:P0A80` where the object references a different entity.

**FactRelation** — an immutable lifecycle or semantic edge. Fields: `relation_id`, `tenant_id`, `from_assertion_id` (nullable only for retraction), `to_assertion_id`, `relation_type`, `known_at`, `reason`, `attribution`, `operation_key`. Allowed lifecycle relations are `supersedes`, `retracts`, `contradicts`, and `corroborates`. Retraction is an attributed relation targeting the withdrawn assertion; canonical facts are never edited.

**CurrentFacts** — a parameterized query/view, not a mutable row:

```sql
eligible = assertions visible to AccessContext
           where assertion_status in ('observed', 'inferred', 'confirmed')
           and known_at <= knowledge_as_of
           and valid_from <= valid_at < valid_to  -- respecting open bounds

current_facts = eligible assertions not superseded or retracted by a relation
                visible at knowledge_as_of
```

“Latest” is evaluated per fact identity and only after authorization and time filtering. Future-valid assertions are not current before `valid_from`.

**DerivationEdge** — links a derived object to its parents, forming the full provenance DAG. Records `method` (llm_extract / deterministic_rule / human_review), `model_id`, `prompt_hash`, `tool_version`.

Three valid derivation patterns:
- `observation` ← `raw_source`: an extracted unit fact traces to the raw source(s) it was extracted from
- `fact` ← `observation`: a fact assertion traces to the unit observation(s) that support it
- `fact` ← `fact`: a higher-order fact traces to supporting facts

No layer-skipping is permitted. A fact cannot derive directly from a raw source — every claim must pass through an explicit observation. This ensures the promotion gate always evaluates a unit-fact granularity record, and can trace it back to the raw source to determine whether the underlying input is conversation-specific.

**MemoryIndexRef** — a rebuildable projection-status record. It tracks tenant, canonical object, backend namespace, model/version, status, and indexed timestamp. It is not authoritative memory.

### Fact Operations

| Operation | Meaning |
|---|---|
| `assert_fact` | Add a new claim |
| `confirm_fact` | Create a confirmed assertion linked by `corroborates`; do not edit the predecessor |
| `supersede_fact` | Create a replacement assertion plus a `supersedes` relation |
| `promote_fact` | Create a global assertion from newly corroborated evidence and link it by `derived_from`/`corroborates`; do not supersede the conversation assertion |
| `contradict_fact` | Create a `contradicts` relation; resolution is a separate policy decision |
| `retract_fact` | Create a retraction assertion plus a `retracts` relation |
| `close_validity` | Create a successor assertion with a closed valid-time interval plus `supersedes` |
| `merge_entity` | Entity resolution: two nodes are the same |
| `split_entity` | Undo a bad entity merge |
| `extract_conditional` | Create a conversation-scoped proposed rule linked to its evidence. Global publication is a separate reviewed operation requiring independent global evidence or human approval. |

**Fact identity and cardinality:** predicates are registered with `single`, `set`, or `temporal-series` cardinality. For single-valued predicates, `fact_key` is deterministic over `(tenant_id, subject_ref, predicate)`. For set-valued and temporal-series predicates, normalized object identity is included. Contradiction candidates must share a fact key and have overlapping valid-time intervals. Unknown predicates default to set-valued so multiple values are not incorrectly treated as conflicts.

**Contradiction resolution policy:** Confidence can rank candidates but never resolves a conflict alone. V1 considers assertion status, source authority, valid-time overlap, recency of evidence, and human decisions. If policy cannot select a winner, both assertions remain visible as disputed. Resolution creates a new assertion and lifecycle relations; it never tags or edits existing rows.

### Promotion Ladder

```
raw source  [conversation-scoped]
  → observation  [conversation-scoped, unit fact]
  → fact assertion  [conversation-scoped]
        ↓  independent global evidence or human approval
        ├── insufficient corroboration → remains conversation-scoped
        └── corroborated
                → new observation(s) from global source(s)
                → new fact assertion [global, same subject_ref]
                → corroborates/derived_from links to supporting records
  → fact assertion  [global]
        ↓  cross-entity pattern confirmed across many entities
  → fact assertion  [global, domain subject]
```

Promotion does not relabel or replace a conversation assertion. It creates a distinct global assertion supported by evidence valid at global scope. An approval is captured as an attributed `human_review` raw source and observation, preserving the no-layer-skipping invariant. Subject reference stays stable for trust-level promotion. Entity-to-domain generalization is a separate operation requiring a versioned, application-specific policy. Model-generated conditional rules remain conversation-scoped proposals in v1; global publication requires independent corroboration or human approval.

---

## 5. Proposed Architecture

```
┌─────────────────────────────────────────────────┐
│  Agent / Planner / Tools                        │
│  (writes to memory as explicit step actions)    │
└──────────────────┬──────────────────────────────┘
                   │  MemoryCommandService.commit()
                   │  ├─ content-addressed BlobStore write
                   │  └─ one Postgres transaction:
                   │     canonical rows + audit event + outbox
                   ▼
┌─────────────────────────────────────────────────┐
│  Canonical Memory Store                         │
│  Postgres: raw_source,                          │
│  observation, fact_assertion,                   │
│  fact_relation, derivation_edge                  │
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
2. **Canonical store** — Postgres. Append-only raw sources, observations, fact assertions, fact relations, and derivation edges are authoritative. `memory_event` provides a convenient audit timeline over committed canonical records but is not independently authoritative.
3. **Projection indexes** — Temporal (Postgres bitemporal views), Graph (Graphiti/Neo4j), Vector (pgvector first), Keyword (Postgres FTS + pg_trgm). Each is an adapter behind an interface and can be rebuilt from canonical rows.
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

No external system has direct write access to canonical memory tables. Writes flow through validated memory commands issued by agent steps, consolidation workers, or authorized reviewers; each command records actor attribution and an idempotent operation key.

---

## 7. Write Path

The agent issues memory commands explicitly as step actions—there is no subscription from the step runtime in v1. A command carries `tenant_id`, actor attribution, semantic-owner `step_id`, and a stable `operation_key`. Retrying the same command returns the original result.

**Raw source selection policy:** Only raw sources used as evidence for at least one observation are captured in canonical memory. Other messages and tool records remain in the step ledger. “Full provenance” therefore means complete provenance for each persisted fact, not duplication of the complete execution history.

```
agent step action
  → validate authorization, scope invariants, predicate schema, and provenance shape
  → store RawSource (immutable, scoped):
      if byte_size < threshold  → content stored inline
      if byte_size >= threshold → BlobStore.store_blob(content)
                                    → set content_ref_type, content_ref_loc; null content
  → extractor emits unit facts → N Observation records (immutable, scoped, always inline)
  → DerivationEdge links each Observation to its parent RawSource(s)
  → LLM emits structured MemoryOperation proposals from Observations:
      { operation, subject, predicate, object, confidence, derived_from[] }
  → deterministic validator checks each proposal
  → MemoryCommand commits assertions with initial assertion_status:
      llm_extract (any source)                      → inferred
      deterministic fixed-schema parser (no model)  → observed
      unvalidated conditional draft                 → proposed
  → DerivationEdge links each FactAssertion to its parent Observation(s)
  → append audit MemoryEvent referencing committed canonical record IDs
  → append ProjectionOutbox entries for affected canonical records
```

**The LLM never directly writes canonical facts.** It proposes a structured operation; deterministic code validates and commits. A semantic-owner step may write observations immediately, or a later consolidation run may extract them from captured raw sources. The same raw source/extractor version pair is idempotent and is never processed twice into duplicate observations.

**Commit and recovery contract:**

1. External blob content is written first under a content-addressed, idempotent locator.
2. Raw sources, observations, assertions, derivation edges, audit events, and projection-outbox rows created by one command commit in one Postgres transaction.
3. A transaction failure leaves no canonical rows. An orphaned content-addressed blob is safe and can be garbage-collected after a retention window.
4. Projection workers consume the outbox at least once. Projection upserts are idempotent by `(tenant_id, object_type, object_id, projection_version)`.
5. Projection failures never roll back canonical memory. They remain retryable and are exposed as staleness.

No external projection is updated synchronously on the hot path. This removes dual-write ambiguity and follows the runtime’s existing logical-commit pattern.

---

## 8. Read Path (Retrieval Router)

```
retrieval request + AccessContext
  → authorize tenant, conversation, and subject boundaries
  → classify query type
  → fetch current task state         (FactStore.get_facts with current times)
  → fetch facts by valid_at and knowledge_as_of (FactStore.get_facts)
  → traverse graph for related entities (GraphIndex.traverse)
  → retrieve similar prior tasks     (VectorIndex.search)
  → retrieve exact identifier matches (keyword search)
  → rerank / merge / deduplicate
  → attach projection freshness and evidence availability
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
      "assertion_status": "confirmed"
    }
  ],
  "knowledge_as_of": "2026-06-21T12:00:00Z",
  "projection_freshness": {"vector": "...", "graph": "..."},
  "partial": false
}
```

The agent cites evidence from the bundle rather than asserting "memory says." Every retrieval requires bounded `limit` and pagination/cursor behavior. Ordering is deterministic after reranking: score descending, then `known_at`, then object ID. If a raw blob or cross-system source is unavailable, the hit is retained with `partial=true` and an explicit evidence-availability marker; inaccessible raw content is never copied into the response.

---

## 9. Background Consolidation

**Trigger:** On-demand only in v1 (manual invocation or explicit API call). No automatic post-run or nightly triggers.

**Input:** Canonical records selected after the last committed consolidation checkpoint for `(tenant_id, scope, policy_version)`. A consolidation run has a stable `consolidation_run_id`; rerunning it is idempotent.

**Output per consolidation run:**
- Observations extracted from raw sources (unit facts, one statement per record)
- Candidate facts derived from observations
- Candidate domain or agent assertions, including lessons that satisfy policy
- Lifecycle relations for stale, contradicted, or corroborated assertions
- Projection-outbox entries for vector, graph, and keyword updates

Task/session summaries used for similarity search are disposable projection documents generated from canonical fact IDs. They are not a second class of canonical memory and must be rebuildable.

**Promotion gate:** A conversation assertion is eligible to seed a separate global assertion only when the evaluator has independent global-scoped corroborating observations or an authorized human approval captured as a global `human_review` observation. Confidence thresholds may reject a candidate but cannot establish global validity. The evaluator records the policy version, evidence IDs, decision, and actor. The new global assertion derives from the global evidence and may be linked to the conversation assertion with `corroborates`; the conversation assertion is not superseded.

**Conditional extraction:** A worker may create a conversation-scoped `proposed` conditional for later review. V1 never publishes such a proposal globally based only on model judgment. Global publication follows the same corroborating-evidence or human-approval rule as other promotions.

**Contradiction handling during consolidation:** Candidates must share a fact key and overlap in valid time. The worker creates a `contradicts` relation and applies the versioned resolution policy. If source authority, confirmation, recency, and confidence do not produce an unambiguous result, both remain disputed. A resolution creates a new assertion and `supersedes`/`corroborates` relations; existing rows remain unchanged.

The checkpoint advances in the same transaction as the consolidation run’s canonical writes and outbox entries. Failed runs do not advance it. Concurrent workers acquire a scope-level lease or compare-and-swap the checkpoint version.

**Open Question:** At what scale does on-demand consolidation become a bottleneck? When should this shift to event-driven (post-run outbox) or scheduled? *(Deferred for v1.)*

---

## 10. Interfaces and Contracts

All application code depends on these interfaces. Backends are adapters.

```python
@dataclass
class Scope:
    tenant_id: str
    scope_level: str           # conversation | global
    conversation_id: str | None  # non-null when scope_level = conversation
    subject_type: str          # universal | entity | domain | agent
    subject_ref: str | None    # "{type}:{id}" e.g. "vehicle:VIN123"; null for universal

@dataclass
class AccessContext:
    tenant_id: str
    principal_id: str
    allowed_conversation_ids: frozenset[str]
    allowed_subject_prefixes: frozenset[str]

class MemoryCommandService:
    def commit(self, access: AccessContext,
               command: MemoryCommand) -> MemoryCommandResult: ...

class RawSourceStore:
    def get_raw_source(self, access: AccessContext, source_id: str) -> RawSource: ...

class ObservationStore:
    def get_observations(self, access: AccessContext,
                         scope: Scope) -> list[Observation]: ...

class AuditTimelineStore:
    def get_timeline(self, access: AccessContext,
                     scope: Scope) -> list[MemoryEvent]: ...

class FactStore:
    def get_facts(self, access: AccessContext, scope: Scope, *,
                  valid_at: datetime | None,
                  knowledge_as_of: datetime,
                  limit: int, cursor: str | None) -> FactPage: ...

class ProvenanceStore:
    def link_derivation(self,
                        child_type: str,           # observation | fact | summary | ...
                        child_id: str,
                        parents: list[tuple[str, str]],  # [(parent_type, parent_id), ...]
                        method: str) -> None: ...  # llm_extract | deterministic_rule | human_review
    def explain(self, access: AccessContext, object_type: str,
                object_id: str, max_depth: int) -> ProvenanceGraph: ...

class VectorIndex:
    def upsert(self, item: IndexedMemory) -> None: ...
    def search(self, access: AccessContext, query: str,
               filters: dict, k: int) -> list[SearchHit]: ...

class GraphIndex:
    def upsert_entity(self, entity: Entity) -> None: ...
    def upsert_relation(self, relation: Relation) -> None: ...
    def traverse(self, access: AccessContext,
                 query: GraphQuery) -> list[GraphHit]: ...

class MemoryRetriever:
    def retrieve(self, access: AccessContext,
                 request: RetrievalRequest) -> EvidenceBundle: ...

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
| `MemoryCommandService` | Postgres transaction | — |
| `RawSourceStore` | Postgres `raw_source` table | — |
| `ObservationStore` | Postgres `observation` table | — |
| `AuditTimelineStore` | Postgres `memory_event` table | — |
| `FactStore` | Postgres bitemporal tables | — |
| `ProvenanceStore` | Postgres `derivation_edge` | — |
| `VectorIndex` | pgvector | Qdrant, Weaviate |
| `GraphIndex` | Graphiti (optional in v1) | Neo4j, Zep |
| `MemoryRetriever` | Custom router | — |
| `BlobStore` | GCS | S3, Azure Blob, local filesystem |

### Provenance Integrity

`derivation_edge` uses typed parent/child IDs, so ordinary polymorphic foreign keys are insufficient. `MemoryCommand` validation enforces the allowed edge matrix, same-tenant ownership, and parent existence inside the canonical transaction. A recursive cycle check rejects an edge when the proposed child is already an ancestor of its parent. Database triggers or deferred constraint checks enforce the same rules for privileged maintenance writes. Provenance queries require an authorization context and a bounded depth.

### Repository Placement and Runtime Integration

The design preserves the existing Polylith boundaries:

- `components/xagent/agent_memory/`: domain models, predicate registry, command service, retrieval service, policy interfaces, and in-memory adapters used by deterministic tests.
- `components/xagent/agent_persistence/`: shared artifact/blob contracts only where the execution and memory systems genuinely share storage; memory domain repositories do not extend step repositories.
- `components/xagent/agent_flow/`: thin memory step actions that construct commands with `run_id`, `conversation_id`, semantic-owner `step_id`, and operation key. It does not own memory policy or storage.
- `bases/xagent/`: optional HTTP/CLI endpoints for authorized retrieval, consolidation, and review.

The semantic owner emits a memory command only after its result is stable. Step success and memory commit are separate durable operations in v1; the memory operation key derives from the step id and logical command index, so resume safely retries an incomplete memory action. If later requirements demand atomicity across the execution and memory stores, adopt a step-runtime outbox rather than a cross-database transaction.

---

## 11. Invariants

- Canonical raw sources, observations, fact assertions, fact relations, and derivation edges are append-only. `memory_event` is an audit timeline, not a second source of truth.
- The LLM never directly writes canonical facts. It proposes structured operations; deterministic code validates and commits.
- Every persisted fact is explainable through canonical provenance to captured raw sources; unavailable external boundaries are reported explicitly.
- Contradiction is not deletion. Contradictory assertions are retained and linked by immutable relations.
- No fact may derive directly from a raw source. Every fact must have at least one observation as an intermediate parent in the derivation chain.
- Every observation is a single extracted unit fact — never a full message, passage, or multi-statement prose block.
- Every observation records derivation edges to its raw sources. Global assertions require independent global evidence or attributed human approval; conversation provenance alone is insufficient.
- Raw sources, observations, and facts are scoped at write time with two independent fields: `scope_level` (conversation / global) and `subject_ref` (what entity or domain the record is about).
- Every canonical and projected read requires `AccessContext`; tenant authorization is applied before trust scope, ranking, or provenance expansion.
- Conversation-scoped facts are not readable outside their conversation. Promotion creates a separate global assertion and never widens the original record.
- Subject reference (`subject_type` + `subject_ref`) stays stable during trust-level promotion. Subject type escalation (entity → domain) is a separate promotion path requiring cross-entity confirmation.
- Current facts are derived from assertions and lifecycle relations at explicit valid and knowledge times, never stored as mutable canonical rows.
- Every projection index entry has a corresponding `MemoryIndexRef` record that identifies its backend and embedding model.
- One memory command commits canonical rows, its audit event, and projection-outbox entries atomically and is idempotent by operation key.
- Projection indexes are disposable and may be stale; retrieval reports their freshness.
- Model-generated conditional rules cannot become global in v1 without independent global evidence or authorized human approval.

---

## 12. Alternatives Considered

**Single vector DB as memory**
Rejected. Loses update semantics, temporal reasoning, exact identifier matching (IDs, codes, version strings), source attribution, and replay capability.

**Summaries as sole long-term memory**
Rejected. Summaries are lossy and non-auditable. They cannot answer "what source supported this conclusion?"

**LLM direct mutation of canonical facts**
Rejected. Introduces uncontrolled writes with no validation, provenance, or rollback. Recent memory-security research identifies this as a primary attack and integrity risk.

**Managed memory service (Mem0, Zep, Letta) as system of record**
Deferred. Useful as projection adapters behind the `GraphIndex` or `VectorIndex` interface. Not acceptable as the canonical store because they do not provide deterministic provenance, exact bitemporal control, or SQL joins against the step runtime ledger.

**Outbox-driven integration with step runtime**
Deferred. Explicit memory commands from semantic-owner steps are simpler for v1. Subscription to a step-runtime outbox can be added when integration volume justifies decoupling.

---

## 13. Tradeoffs

**Auditability vs hot-path latency**
Full provenance recording adds writes on the hot path. Mitigated by keeping the hot path minimal (raw sources + extracted observations + minimal candidate facts) and deferring heavy consolidation to on-demand background jobs.

**Pluggability vs operational simplicity**
Abstract interfaces require upfront discipline. The payoff is that any backend (pgvector → Qdrant, Graphiti → Neo4j) can be swapped without touching agent code. The cost is an extra indirection layer.

**Conversation-scoped safety vs global knowledge velocity**
Requiring independent global evidence or human approval prevents a conversation claim from silently becoming shared knowledge. The cost is slower global knowledge accumulation and additional review or corroboration work.

**On-demand consolidation vs continuous**
On-demand is simpler and predictable for v1. The cost is that retrieval freshness depends on when consolidation was last run. Stale projections may affect retrieval quality between consolidation runs.

---

## 14. Risks and Mitigations

**Consolidation backlog under high run volume**
If many tasks complete without consolidation, the gap between raw sources and durable facts grows large. *Mitigation:* track last-consolidated checkpoint per scope; surface staleness in observability. *Detection:* alert when observation count since last consolidation exceeds a threshold.

**Entity resolution errors polluting the graph projection**
A wrong `merge_entity` operation links unrelated entities. *Mitigation:* `split_entity` is a first-class operation. Graph projection is a read index only; canonical fact history is not edited. *Detection:* graph traversal returning unexpected cross-task links.

**Embedding model drift invalidating vector indexes**
Changing the embedding model makes existing vector indexes semantically incompatible. *Mitigation:* `MemoryIndexRef` tracks `embedding_model` per indexed object; reindexing is a defined operation. *Open Question: full reindex strategy is not yet designed — see OQ #4.*

**LLM hallucinating high-confidence fact proposals**
A model-generated fact proposal carries a fabricated high confidence score. *Mitigation:* model confidence can only reject, rank, or flag a proposal; it cannot establish global validity. Global publication requires independent evidence or an authorized human decision. *Detection:* monitor promotion decisions by evidence type and policy version.

**Cross-tenant or cross-conversation disclosure**
A projection query or provenance expansion omits a mandatory scope filter. *Mitigation:* require `AccessContext` in all repository and retrieval interfaces; namespace projection entries by tenant; authorize before ranking or graph expansion. *Detection:* negative isolation tests for every backend and audit logs for denied reads.

**Partial canonical writes or projection divergence**
A crash occurs between related writes, or an index update fails. *Mitigation:* commit canonical rows, audit event, and outbox atomically; use content-addressed blobs and idempotent projection consumers. *Detection:* outbox age, failed-attempt counts, and projection freshness in retrieval responses.

**Incorrect automatic contradiction resolution**
Two legitimate set-valued or non-overlapping temporal facts are treated as conflicting. *Mitigation:* predicate cardinality registry, valid-time overlap checks, and disputed state when policy cannot decide. *Detection:* sampled resolution audits and reversal rate.

---

## 15. Rollout, Recovery, and Acceptance Criteria

**Phase 1 — canonical store only.** Add in-memory repository implementations and deterministic tests for immutability, idempotency, temporal queries, scope isolation, provenance, and lifecycle relations. Integrate memory writes as explicit semantic-owner steps. Retrieval uses Postgres/in-memory canonical queries only.

**Phase 2 — Postgres and audit timeline.** Add migrations, transactional command handling, content-addressed blob writes, consolidation checkpoints, and projection outbox. Run internally with writes disabled by default, then shadow-write from selected runs and compare expected records without exposing memory to agents.

**Phase 3 — retrieval projections.** Enable tenant-namespaced keyword and vector projections behind feature flags. Graph remains optional. Compare projected results against canonical queries, expose freshness, and test rebuild from canonical rows.

**Phase 4 — controlled promotion.** Enable promotion for an allowlisted tenant and predicate set. Require human approval initially; automate only policies with measured false-promotion rates.

**Rollback:** Disable memory reads and writes independently by feature flag. Canonical append-only rows remain for audit. Drop and rebuild disposable projections. A faulty assertion is retracted or superseded by new records, never edited or deleted.

**Acceptance criteria:**

- Retrying a command produces no duplicate canonical rows or projection effects.
- Failure at every write boundary produces either no canonical command result or one complete result.
- Valid-time and knowledge-time test matrices reproduce historical beliefs after later corrections.
- Cross-tenant and unauthorized cross-conversation reads return no canonical, projected, or provenance data.
- Rebuilding every enabled projection from canonical rows produces equivalent query results within documented ranking tolerance.
- Retrieval reports stale or partial evidence rather than silently presenting it as complete.
- Promotion cannot succeed from model confidence or conversation-scoped evidence alone.

---

## 16. Open Questions

**OQ-3 Entity resolution.** How does the graph projection decide when two mentions refer to the same entity? Deterministic (exact ID match), model-driven (semantic similarity), or human-gated? This affects graph index correctness and the `merge_entity` / `split_entity` operation triggers. The answer is likely application-specific.

**OQ-4 Embedding versioning.** When the embedding model changes, what is the strategy for migrating or reindexing existing vector index entries? Is this a background reindex job, a versioned namespace, or a dual-read during transition?

**OQ-7 Retention and archival policy.** How long are completed-task raw sources, observations, and fact assertions retained? Is there a data-lifecycle or compliance requirement that affects what can be stored or for how long?

**OQ-8 Subject authorization policy.** Tenant isolation and mandatory access context are decided. The remaining product decision is how principals receive access to subject prefixes and conversations, and whether global facts are readable by every principal in a tenant or only by roles.

**OQ-9 Predicate registry ownership.** Which component owns predicate cardinality, normalization, and conflict policy, and how are schema versions migrated?

---

## 17. Appendix

### A. Postgres Table Sketches

```sql
memory_event (
  event_id          uuid primary key,
  tenant_id         text not null,
  scope_level       text not null,   -- conversation | global
  conversation_id   text,            -- non-null when scope_level = conversation
  subject_type      text not null,   -- universal | entity | domain | agent
  subject_ref       text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  event_type        text not null,   -- tool_result, fact_asserted, fact_retracted,
                                   -- summary_created, contradiction_recorded
  actor_type      text not null,   -- user, agent, tool, system, reviewer
  actor_id        text,
  run_id          uuid,
  turn_id         uuid,
  step_id         uuid,
  payload         jsonb not null,
  operation_key   text not null,
  event_hash      text not null,
  known_at        timestamptz not null default now(),
  unique (tenant_id, operation_key, event_type)
);

raw_source (
  source_id         uuid primary key,
  tenant_id         text not null,
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
  known_at          timestamptz not null default now(),
  operation_key     text not null,
  hash              text not null,   -- hash of full content regardless of storage location
  unique (tenant_id, operation_key),
  unique (tenant_id, scope_level, conversation_id, subject_ref, hash),
  check ((scope_level = 'conversation' and conversation_id is not null) or
         (scope_level = 'global' and conversation_id is null)),
  check (
    (content is not null and content_ref_type is null and content_ref_loc is null) or
    (content is null     and content_ref_type is not null and content_ref_loc is not null)
  )
);

observation (
  observation_id    uuid primary key,
  tenant_id         text not null,
  scope_level       text not null,   -- conversation | global
  conversation_id   text,            -- non-null when scope_level = conversation
  subject_type      text not null,   -- universal | entity | domain | agent
  subject_ref       text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  content            text not null,   -- single extracted unit fact statement
  derivation_basis   text not null,   -- observed | inferred | confirmed
  known_at        timestamptz not null default now(),
  operation_key   text not null,
  hash            text not null,
  unique (tenant_id, operation_key),
  unique (tenant_id, scope_level, conversation_id, subject_ref, hash),
  check ((scope_level = 'conversation' and conversation_id is not null) or
         (scope_level = 'global' and conversation_id is null))
  -- derivation edges to parent raw_source(s) are in derivation_edge, not inline
);

fact_assertion (
  assertion_id            uuid primary key,
  tenant_id               text not null,
  scope_level             text not null,   -- conversation | global
  conversation_id         text,            -- non-null when scope_level = conversation
  subject_type            text not null,   -- universal | entity | domain | agent
  subject_ref             text,            -- "{type}:{id}" e.g. "vehicle:VIN123"; null for universal
  fact_key                text not null,   -- stable dedupe key
  subject                 text not null,
  predicate               text not null,
  object                  jsonb not null,
  assertion_status        text not null,  -- proposed, observed, inferred, confirmed
  confidence              numeric,
  valid_from              timestamptz,
  valid_to                timestamptz,
  known_at                timestamptz not null default now(),
  created_by_run_id       uuid,
  attribution             jsonb not null, -- model_id, prompt_hash, tool_version
  operation_key           text not null,
  unique (tenant_id, operation_key),
  check (valid_to is null or valid_from is null or valid_from < valid_to),
  check ((scope_level = 'conversation' and conversation_id is not null) or
         (scope_level = 'global' and conversation_id is null))
);

fact_relation (
  relation_id       uuid primary key,
  tenant_id         text not null,
  from_assertion_id uuid,          -- null only for retracts
  to_assertion_id   uuid not null,
  relation_type     text not null, -- supersedes, retracts, contradicts, corroborates
  reason            text,
  attribution       jsonb not null,
  operation_key     text not null,
  known_at          timestamptz not null default now(),
  unique (tenant_id, operation_key),
  unique (tenant_id, from_assertion_id, to_assertion_id, relation_type),
  check ((relation_type = 'retracts' and from_assertion_id is null) or
         (relation_type <> 'retracts' and from_assertion_id is not null))
);

derivation_edge (
  tenant_id     text not null,
  child_type    text not null,   -- observation, fact, summary, graph_edge, vector_doc
  child_id      uuid not null,
  parent_type   text not null,   -- raw_source, observation, fact
  parent_id     uuid not null,
  method        text not null,   -- llm_extract, deterministic_rule, human_review
  model_id      text,
  prompt_hash   text,
  tool_version  text,
  known_at      timestamptz not null default now(),
  operation_key text not null,
  primary key (tenant_id, child_type, child_id, parent_type, parent_id),
  unique (tenant_id, operation_key)
);

memory_index_ref (
  tenant_id        text not null,
  object_type      text not null,  -- raw_source, observation, fact, summary
  object_id        uuid not null,
  index_type       text not null,  -- vector, graph, keyword
  backend          text not null,  -- pgvector, qdrant, graphiti, neo4j
  external_id      text not null,
  embedding_model  text,
  projection_version text not null,
  status           text not null, -- pending, indexed, failed
  indexed_at       timestamptz,
  primary key (tenant_id, object_type, object_id, index_type, backend, projection_version)
);

projection_outbox (
  outbox_id          uuid primary key,
  tenant_id          text not null,
  object_type        text not null,
  object_id          uuid not null,
  projection_type    text not null,
  projection_version text not null,
  operation_key      text not null,
  created_at         timestamptz not null default now(),
  processed_at       timestamptz,
  attempt_count      int not null default 0,
  last_error         text,
  unique (tenant_id, operation_key, projection_type, projection_version)
);

consolidation_checkpoint (
  tenant_id          text not null,
  scope_key          text not null,
  policy_version     text not null,
  cursor             text not null,
  version            bigint not null,
  updated_at         timestamptz not null default now(),
  primary key (tenant_id, scope_key, policy_version)
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
| Observability | OpenTelemetry trace/span IDs in audit events | — |
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

Bitemporal fields are essential here: `valid_from` / `valid_to` capture when a software version was installed or a DTC was active; `known_at` captures when the agent learned it—these differ when a technician reports a past repair.

#### Entity Graph Shape

The graph projection for vehicle diagnostics has a natural shape:

```
case → vehicle → ECU → software_version → DTC → symptom → test_result → repair → outcome
```

Each edge is a `FactAssertion` with derivation edges to the observations that established it, which in turn trace back to the raw sources. The `split_entity` and `merge_entity` operations handle cases where a VIN is mis-transcribed or two case records refer to the same vehicle.

#### Assertion Basis Mapping

| Assertion status | Vehicle diagnostic meaning |
|---|---|
| `observed` | DTC directly read from OBD-II scan or GTAC tool result |
| `inferred` | Agent hypothesis derived from symptom pattern or prior case similarity |
| `confirmed` | Validated by a second source (technician confirmation, corroborating log entry, or second tool) |

Lifecycle changes such as supersession, retraction, or contradiction are represented by `FactRelation` rows rather than additional assertion-status values.

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

The following diagnostic requirements map to the generic design, subject to the open retention, authorization-policy, predicate-registry, and entity-resolution decisions:

| Diagnostic requirement | Covered by |
|---|---|
| Track DTCs per vehicle over time | `global` / `entity` / `vehicle:VIN` + bitemporal `fact_assertion` |
| Link DTC to software version and repair | `GraphIndex` edges + `derivation_edge` |
| Audit trail: why did agent conclude X? | `ProvenanceStore.explain()` + `derivation_edge` |
| Cross-case fleet pattern accumulation | `global` / `domain` subject + promotion policy |
| Contradictory evidence (two conflicting diagnoses) | `contradict_fact` operation + immutable `contradicts` relation |
| Technician overrides agent conclusion | `supersede_fact` with `actor_type: user` |
| Retrieve similar prior cases | `VectorIndex.search` on task summaries |
| Exact VIN / DTC / part number lookup | keyword index (Postgres FTS + trigram) |
| Replay: what did we know at case open? | `FactStore.get_facts(knowledge_as_of=case_open_time, valid_at=...)` |
| Ruled-out hypotheses preserved for audit | `retract_fact` relation; canonical assertion remains retained |

The mapping validates the core abstractions but does not close the open policy questions above. In particular, VIN identity simplifies entity resolution but does not define who may read a vehicle’s memory or how long that memory may be retained.

One domain-specific consideration worth noting: entity resolution (OQ-3) is straightforward for vehicles because VIN is a globally unique, deterministic identifier. The `merge_entity` / `split_entity` operations exist for mis-transcription correction, not semantic disambiguation. This makes vehicle diagnostics a simpler case of OQ-3 than domains where entity identity is ambiguous.
