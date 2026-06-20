---

name: design-doc
description: Draft, review, revise, compress, and structure design documents for large product features, focused feature areas, agent applications, backend systems, and developer tools. Use when the user asks for a design doc, design proposal, architecture doc, technical design review, design-doc outline, or design-doc critique.
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Design Document Skill

## Purpose

Use this skill to help create or improve design documents for large product features, focused feature areas, agent applications, backend systems, or developer tools.

A design document is a decision-making artifact. Its job is to help reviewers understand the problem, evaluate the proposed design, align on tradeoffs, and implement the feature correctly.

Optimize for decision clarity, not document length.

## Core Principles

### 1. Make the decision clear

A good design document should make these points easy to understand:

* What problem are we solving?
* Why does it matter?
* What is in scope and out of scope?
* What design are we choosing?
* Why this design instead of alternatives?
* What tradeoffs and risks remain?
* What needs to be implemented?

Do not turn the document into a generic knowledge dump or a full implementation manual.

### 2. Be concise, but not incomplete

Include only information that changes the reader’s understanding of the problem, constraints, design, contracts, tradeoffs, risks, rollout, or open questions.

A true statement is not automatically worth including.

Avoid obvious or generic statements unless the design makes a specific, non-obvious choice related to them.

Prefer high information gain per sentence.

### 3. Separate main reading path from reference detail

The main document should contain what every reviewer must understand.

Move optional or exhaustive detail to appendices or linked sub-documents.

Good default size:

* Small design note: 1–2 pages
* Normal feature design: 4–8 pages
* Large focused feature area: 6–10 pages
* More than 10–12 pages: consider appendices or sub-design docs

### 4. Include design-level decisions, not every implementation detail

Include details that affect:

* Architecture
* Cross-component behavior
* User/system behavior
* Interfaces and contracts
* Data lifecycle
* State transitions
* Operational behavior
* Security, privacy, audit, or compliance
* Rollout and migration
* Future extensibility
* Major risks

Omit or defer details that can be safely decided during implementation without changing the design.

Use this test:

> If this detail changes, would the design meaningfully change?

If yes, include it. If no, omit it or move it to an appendix.

## When to Use This Skill

Use this skill when the user asks to:

* Draft a design document
* Review a design document
* Improve or rewrite a design document
* Create a design-doc outline
* Compress a long design document
* Turn notes into a structured design proposal
* Extract decisions, assumptions, tradeoffs, risks, or open questions
* Split a parent design doc from sub-design docs
* Prepare a document for technical review

## Default Workflow

When helping with a design document:

1. Identify the decision the document needs to support.
2. Identify the target audience.
3. Clarify the problem and scope.
4. Separate goals, requirements, constraints, and implementation details.
5. Define core concepts and ownership.
6. Describe the proposed design.
7. Add only the flows needed to understand important behavior.
8. State interfaces, contracts, and invariants.
9. Make alternatives, tradeoffs, risks, and open questions explicit.
10. Remove generic filler and obvious statements.
11. Keep the main reading path short.
12. Move reference detail to appendices when appropriate.

If the user provides enough context, proceed with a best-effort draft instead of asking many clarifying questions. Use clear assumptions where needed.

## Recommended Design Document Template

Use this structure unless the user asks for a different one.

### 1. Summary

Briefly state:

* The problem
* The proposed solution
* The main design decision
* The expected impact
* The most important tradeoff

A reviewer should understand the proposal at a high level from this section alone.

### 2. Background and Problem

Explain the current situation and the specific problem being solved.

Include only context needed to understand the design.

Cover:

* Current behavior or system state
* Pain points or limitations
* Why this matters now
* What happens if we do nothing

Avoid restating common knowledge.

### 3. Goals and Non-Goals

Separate goals from non-goals.

Goals are outcomes this design must achieve.

Non-goals are adjacent problems this design intentionally does not solve.

This section protects the document from scope creep.

### 4. Requirements and Constraints

Include only requirements and constraints that affect design choices.

Possible categories:

* Product behavior
* Functional requirements
* Technical constraints
* Operational constraints
* Data constraints
* Security, privacy, compliance, or audit constraints
* Performance, latency, reliability, or cost constraints

Avoid vague requirements such as “must be scalable” unless made specific.

### 5. Proposed Design

Describe the chosen design.

Cover:

* Main components
* Responsibilities of each component
* Ownership boundaries
* How components interact
* Important state or data flow
* Why the design has this shape

This should be the core section of the document.

### 6. Core Concepts and Data Model

Define the important nouns in the system.

For each major concept, explain:

* What it represents
* Who creates it
* Who owns it
* Whether it is mutable or immutable
* How long it lives
* How it relates to other concepts

Include data model shape, but avoid full schema details unless needed for review.

### 7. Main Flows

Describe the important flows needed to understand the design.

Usually include:

* Happy path
* Important failure paths
* User clarification or fallback path
* Retry, replan, pause/resume, rollback, or recovery behavior, if relevant

Do not include exhaustive edge cases unless they change the design.

### 8. Interfaces and Contracts

Describe external or cross-component contracts.

Include relevant:

* Public APIs
* Internal service APIs
* Tool interfaces
* Events or messages
* State transitions
* Error behavior
* Compatibility expectations

Focus on contract-level detail, not code-level detail.

### 9. Invariants

List rules that should always be true.

Examples:

* A completed run record is immutable.
* Replay does not call external tools.
* User-visible messages are traceable to the run that produced them.
* Facts are invalidated rather than silently overwritten.
* Tool authorization happens before tool execution.

Invariants should be short, precise, and high value.

### 10. Alternatives Considered

Describe serious alternatives, not fake ones.

For each alternative, explain:

* What it is
* Benefits
* Drawbacks
* Why it was rejected, deferred, or chosen

The alternatives section should make the chosen design more credible.

### 11. Tradeoffs

State what this design optimizes for and what it gives up.

Examples:

* Simplicity vs flexibility
* Latency vs auditability
* Short-term delivery vs long-term extensibility
* Strong consistency vs availability
* Build vs buy
* Local implementation simplicity vs cross-system consistency

A credible design is explicit about tradeoffs.

### 12. Risks and Mitigations

List concrete risks.

For each risk, explain:

* What might go wrong
* Why it matters
* How the risk is reduced
* How the issue will be detected

Avoid vague risks like “complexity” unless made specific.

### 13. Rollout and Migration

Explain how the design will be shipped safely.

Cover relevant:

* Feature flags
* Phased rollout
* Shadow mode
* Internal-only launch
* Migration or backfill
* Rollback plan
* Compatibility with existing behavior or data

### 14. Open Questions

List unresolved decisions.

Each open question should be specific, bounded, and actionable.

Avoid hiding uncertainty inside vague prose.

### 15. Appendix

Use appendices for useful but non-essential details.

Possible appendix content:

* Full schema
* Full API examples
* Detailed case matrix
* Detailed sequence diagrams
* Benchmark results
* Migration scripts
* Extended alternatives analysis
* Detailed implementation task breakdown

## What Should Stay In

Keep information that helps readers:

* Understand the specific problem
* Understand user or system behavior
* Evaluate the proposed design
* See important constraints
* Understand core concepts and ownership
* Follow the main flows
* Understand cross-component contracts
* Recognize tradeoffs
* Identify risks and mitigations
* Understand rollout and migration implications
* Resolve or track open decisions

Useful examples:

* “Replay must not call external tools or LLMs.”
* “Completed run ledger records are immutable.”
* “Tool authorization happens before execution.”
* “This design prioritizes auditability over maximum throughput.”
* “Batch runs have no interactive session and cannot pause for user input.”

## What Should Stay Out

Omit or move to appendix:

* Obvious engineering principles
* Repeated background context
* Exhaustive edge-case matrices
* Full schema DDL unless needed for review
* Full OpenAPI specs unless contract-critical
* Code-level class and method names
* Minor validation messages
* Low-level retry constants unless product-critical
* Details that can be safely decided during implementation

Avoid vague statements such as:

* “The system should be scalable.”
* “The API should be easy to use.”
* “We need good logging.”
* “Security is important.”
* “The code should be maintainable.”

Make them specific or remove them.

Better:

* “Tool calls are recorded with tool name, input reference, output reference, status, latency, retry count, and error type.”
* “Only user-visible messages are stored in the conversation transcript; internal execution traces are stored in the run ledger.”
* “Replay uses persisted step outputs and does not call external tools or LLMs.”

## Detail-Level Guidance

A design document should contain enough detail to prevent important misunderstanding, but not so much that it becomes an implementation script.

Usually include:

* One clear happy path
* A small number of important non-happy paths
* Core concepts
* Key interfaces
* Data lifecycle
* State transitions, if behavior is stateful
* Diagrams where they reduce explanation
* Important risks and tradeoffs

Usually exclude:

* Exhaustive cases
* Minor validation rules
* Internal helper functions
* Full task breakdown
* Obvious background
* Local coding choices

## Diagram Guidance

Use diagrams only when they clarify the design faster than prose.

Good diagram types:

* Component diagram
* State machine
* Sequence diagram
* Data lifecycle diagram
* Ownership boundary diagram

Every diagram should have a purpose.

When adding a diagram, also explain what decision, relationship, or flow it clarifies.

Avoid decorative diagrams that merely repeat the text.

## Output Modes

### Draft from scratch

When drafting from scratch, produce a complete structured design document using the default template.

If context is missing, make reasonable assumptions and list them explicitly.

### Outline

When asked for an outline, produce section headings with short notes about what each section should contain.

Do not overfill the outline with generic text.

### Review

When reviewing an existing design document, produce:

* Overall assessment
* Major gaps
* Sections that are unclear
* Sections that should be shortened or removed
* Missing decisions
* Missing risks or tradeoffs
* Missing contracts or flows
* Suggested restructuring
* Concrete rewrite suggestions

### Compression

When compressing a design document:

* Preserve decision-critical content
* Remove generic best-practice statements
* Remove repeated context
* Merge overlapping sections
* Move reference details to appendix
* Keep assumptions, constraints, tradeoffs, risks, and open questions visible

### Notes to design doc

When converting notes into a design document:

* Group notes by problem, goals, design, contracts, flows, risks, and open questions
* Preserve user-provided constraints
* Do not invent unsupported requirements
* Mark uncertain points as assumptions or open questions

### Parent doc vs sub-design docs

If the feature area is too large for one readable document:

* Create a parent design doc for problem, scope, architecture, core decisions, and integration points
* Move detailed component designs into sub-docs
* Keep the parent doc focused on how the pieces fit together

## Writing Style

Use direct, specific language.

Prefer:

> Tool calls are recorded in the run ledger with input reference, output reference, status, latency, and error type.

Avoid:

> The system should have good observability.

Prefer:

> This design intentionally stores visible conversation messages separately from internal execution traces.

Avoid:

> The system stores data in a clean and maintainable way.

Use:

* Clear headings
* Short paragraphs
* Bullets for scanability
* Precise terms
* Consistent names for concepts
* Explicit labels such as Decision, Assumption, Constraint, Deferred, and Open Question

Avoid:

* Generic filler
* Repeated arguments
* Undefined terminology
* Premature implementation detail
* Fake alternatives
* Hidden uncertainty

## Review Checklist

Before finalizing a design document, check:

* Is the problem clear?
* Is the scope clear?
* Are goals and non-goals separated?
* Are requirements specific and design-relevant?
* Is the proposed design easy to find?
* Are core concepts defined?
* Are ownership and lifecycle clear?
* Are main flows understandable?
* Are important contracts stated?
* Are invariants explicit?
* Are alternatives serious?
* Are tradeoffs honest?
* Are risks concrete?
* Is rollout addressed?
* Are open questions visible?
* Can reference details move to an appendix?
* Does every section help the reader make a better decision?

## Agent Behavior Rules

When using this skill:

* Improve decision clarity before improving wording.
* Preserve user-provided constraints and terminology unless clearly wrong.
* Do not add generic best-practice filler.
* Do not invent requirements without labeling them as assumptions.
* Do not over-specify implementation details.
* Do not hide uncertainty.
* Do not treat all details as equally important.
* Prefer concise, reviewable structure.
* Prefer concrete contracts over vague claims.
* Prefer serious tradeoff analysis over one-sided justification.
* Prefer a useful partial design over asking excessive clarifying questions.

Default behavior:

> Preserve necessary information, remove low-value prose, make decisions explicit, and keep the main reading path short.

## Reference Files

This skill may include optional reference files under references/.

Use them as follows:

* references/design-doc-template.md: use when drafting a new design document or restructuring an existing one.
* references/review-checklist.md: use when reviewing, critiquing, or quality-checking a design document.

Do not copy reference content mechanically. Apply it based on the user’s task and the specific design context.