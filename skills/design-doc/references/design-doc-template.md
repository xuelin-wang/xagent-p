# Design Document Template

Use this template for large product features, focused feature areas, agent applications, backend systems, and developer tools.

Do not fill every section mechanically. Include a section only when it helps readers understand the problem, design, tradeoffs, risks, or implementation contract.

## 1. Summary

Briefly explain:

* What problem this design solves
* What solution is proposed
* What major decision is being made
* What impact is expected
* What tradeoff matters most

The summary should let a reviewer understand the proposal in a few minutes.

## 2. Background and Problem

Explain the current situation and the specific problem.

Include:

* Current behavior or system state
* Pain points or limitations
* Why this matters now
* What happens if we do nothing

Avoid generic background that the target audience already knows.

## 3. Goals and Non-Goals

### Goals

List the concrete outcomes this design must achieve.

### Non-Goals

List adjacent problems this design intentionally does not solve.

## 4. Requirements and Constraints

Include only requirements and constraints that affect the design.

Possible categories:

* Product behavior
* Functional requirements
* Technical constraints
* Operational constraints
* Data constraints
* Security, privacy, compliance, or audit constraints
* Performance, latency, reliability, or cost constraints

## 5. Proposed Design

Describe the chosen design.

Cover:

* Main components
* Responsibilities
* Ownership boundaries
* How components interact
* Important state or data flow
* Why the design has this shape

This should be the core section of the document.

## 6. Core Concepts and Data Model

Define important concepts.

For each major concept, explain:

* What it represents
* Who creates it
* Who owns it
* Whether it is mutable or immutable
* How long it lives
* How it relates to other concepts

Include data model shape, but avoid full schema detail unless required for review.

## 7. Main Flows

Describe the flows needed to understand the design.

Usually include:

* Happy path
* Important failure paths
* User clarification or fallback path
* Retry, replan, pause/resume, rollback, or recovery behavior, if relevant

Avoid exhaustive case analysis unless it changes the design.

## 8. Interfaces and Contracts

Describe external or cross-component contracts.

Include relevant:

* Public APIs
* Internal APIs
* Tool interfaces
* Events or messages
* State transitions
* Error behavior
* Compatibility expectations

Focus on contract-level detail, not code-level detail.

## 9. Invariants

List rules that should always be true.

Examples:

* Completed records are immutable.
* Replay does not call external tools.
* User-visible messages are traceable to the run that produced them.
* Facts are invalidated rather than silently overwritten.
* Authorization happens before execution.

## 10. Alternatives Considered

Describe serious alternatives.

For each alternative:

* What it is
* Benefits
* Drawbacks
* Why it was rejected, deferred, or chosen

Avoid fake alternatives.

## 11. Tradeoffs

State what this design optimizes for and what it gives up.

Examples:

* Simplicity vs flexibility
* Latency vs auditability
* Short-term delivery vs long-term extensibility
* Strong consistency vs availability
* Build vs buy

## 12. Risks and Mitigations

For each concrete risk, explain:

* What might go wrong
* Why it matters
* How the risk is reduced
* How the issue will be detected

## 13. Rollout and Migration

Explain how the design will be shipped safely.

Cover relevant:

* Feature flags
* Phased rollout
* Shadow mode
* Internal-only launch
* Migration or backfill
* Rollback plan
* Compatibility with existing behavior or data

## 14. Open Questions

List unresolved decisions.

Each open question should be specific, bounded, and actionable.

## 15. Appendix

Use appendices for useful but non-essential detail.

Possible appendix content:

* Full schema
* Full API examples
* Detailed case matrix
* Detailed sequence diagrams
* Benchmark results
* Migration scripts
* Extended alternatives analysis
* Detailed implementation task breakdown
