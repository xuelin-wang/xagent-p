---

name: design-doc
description: Draft, review, revise, compress, and structure design documents for large product features, focused feature areas, agent applications, backend systems, and developer tools. Use when the user asks for a design doc, design proposal, architecture doc, technical design review, design-doc outline, or design-doc critique.
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Design Document Skill

## Purpose

Use this skill to help create or improve design documents for large product features, focused feature areas, agent applications, backend systems, or developer tools.

A design document is a decision-making artifact. Its job is to help reviewers understand the problem, evaluate the proposed design, align on tradeoffs, and implement the feature correctly.

Optimize for decision clarity, not document length.

## Interaction Rule

Do not require the user to provide long repeated prompts.

When the user asks for design-doc help, infer the intended task mode and apply the corresponding workflow automatically.

Examples:

* “Create a design doc from these notes” → Notes to Outline or Draft Design Doc
* “Review this design doc” → Review Design Doc
* “Make this shorter” → Compress Design Doc
* “Improve this section” → Revise Design Doc
* “What are the open questions?” → Extract Decisions
* “This doc is getting too long” → Split Parent Doc and Sub-Docs or Compress Design Doc
* “Is this ready to share?” → Final Review Before Sharing


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

## Human-in-the-Loop Design Rule

Design documents represent design judgment, not just polished writing.

The agent may draft, organize, critique, compress, and clarify the document, but the human owner is responsible for the actual design decisions, tradeoffs, and final approval.

When drafting or revising a design document, distinguish clearly between:

* **Confirmed:** information explicitly provided by the user or source material
* **Assumption:** a reasonable inference made because context is missing
* **Open Question:** an unresolved decision that needs human judgment
* **Suggestion:** an improvement proposed by the agent

Do not present assumptions as confirmed facts.

Do not invent product requirements, architectural constraints, or tradeoff decisions unless they are clearly labeled as assumptions or suggestions.

If context is incomplete, proceed with a best-effort draft when useful, but make uncertainty visible.

## AI-Generated Document Quality Rule

Avoid the common failure mode of AI-generated design documents: polished but generic prose.

Do not fill every template section mechanically.

Do not add content merely because the section exists.

Do not expand obvious statements into long explanations.

Do not smooth over real uncertainty or tradeoffs.

Do not make the design sound more decided than it is.

Prefer a shorter document with clear decisions, assumptions, tradeoffs, risks, and open questions over a longer document that appears complete but hides judgment.

## Recommended Human + Agent Workflow

Use this workflow when helping create an important design document.

### 1. Capture human intent

Start from the human’s rough notes, decisions, constraints, concerns, and open questions.

Important inputs include:

* Problem being solved
* Scope
* Proposed direction
* Key decisions already made
* Known constraints
* Controversial points
* Important tradeoffs
* Open questions
* Target audience

The notes can be messy. Do not require polished input before helping.

### 2. Structure the design

Organize the material into a clear design-doc structure:

* Summary
* Problem
* Goals and non-goals
* Requirements and constraints
* Proposed design
* Core concepts
* Main flows
* Interfaces and contracts
* Invariants
* Alternatives
* Tradeoffs
* Risks
* Rollout
* Open questions

Only include sections that add decision value.

### 3. Mark uncertainty

Where context is missing, label it explicitly.

Use labels such as:

* **Assumption:** Initial traffic is expected to be low.
* **Open Question:** Should replay be exposed in the UI in v1?
* **Suggestion:** Consider separating user-visible messages from internal execution traces.

Never hide uncertainty inside confident prose.

### 4. Challenge the draft

Review the draft for design quality, not just writing quality.

Check for:

* Missing decisions
* Vague requirements
* Undefined concepts
* Fake alternatives
* Hidden assumptions
* Missing failure paths
* Missing tradeoffs
* Missing rollout or migration concerns
* Generic best-practice filler
* Premature implementation detail

### 5. Compress and sharpen

After the structure is correct, improve digestibility.

Actions:

* Remove obvious statements
* Merge repeated context
* Shorten long explanations
* Turn vague claims into concrete contracts
* Move reference details to appendix
* Keep the main reading path short
* Make decisions, assumptions, risks, and open questions easy to scan

### 6. Preserve human ownership

The final document should read as if it was written by someone who understands the system and owns the decision.

The agent should improve clarity and completeness, but should not replace human design judgment.

## Drafting From Limited Context

When the user asks for a design document but provides limited context:

1. Produce a useful partial draft or outline.
2. Clearly label assumptions.
3. List the most important open questions.
4. Avoid inventing unsupported details.
5. Prefer concise placeholders over generic filler.

Good:

> **Assumption:** The first version targets internal users and low traffic. This should be confirmed before finalizing the execution model.

Bad:

> The system will scale horizontally to support enterprise-grade traffic.

## Review Behavior for AI-Written Docs

When reviewing a design document that may have been AI-generated, look especially for:

* Generic sections that sound correct but add little information
* Vague claims such as “scalable,” “secure,” “maintainable,” or “easy to use”
* Overly complete templates where every section is filled regardless of relevance
* Missing real tradeoffs
* Assumptions stated as facts
* Repetition across sections
* Lack of prioritization
* Too much explanation of common knowledge
* Lack of clear decision ownership

Recommend removal, compression, or rewriting when content does not improve decision clarity.

## Default Workflow

When helping with a design document:

1. When helping with a design document, first recover the human’s design intent and separate confirmed decisions from assumptions.
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

## Task Mode Routing

When the user asks for help with a design document, infer the task mode from the request and apply the corresponding behavior. The user should not need to repeat detailed prompting instructions.

If the task mode is ambiguous, choose the most useful mode based on the provided material. Prefer useful progress over asking excessive clarification questions.

### Mode: Notes to Outline

Use when the user provides rough notes, ideas, bullets, meeting notes, issue descriptions, or partial context and asks to organize them.

Behavior:

* Organize the notes into a design-doc outline.
* Do not produce a polished full document yet unless explicitly requested.
* Separate confirmed information, assumptions, open questions, and agent suggestions.
* Identify missing context that would materially affect the design.
* Keep the outline concise and decision-focused.
* Avoid generic filler.

Output should include:

* Proposed title
* Target audience, if inferable
* Decision the doc should support
* Structured outline
* Confirmed information
* Assumptions
* Open questions
* Suggested additions or missing areas

### Mode: Draft Design Doc

Use when the user asks to draft, write, or create a design document.

Behavior:

* Start from the user’s provided intent, notes, constraints, and decisions.
* Produce a structured design document using the default template.
* Keep the main reading path concise.
* Do not fill template sections mechanically.
* Omit sections that do not add decision value.
* Clearly label assumptions and open questions.
* Do not invent unsupported requirements.
* Move excessive detail to appendix when appropriate.
* Prefer concrete contracts, flows, tradeoffs, and risks over generic best-practice prose.

Output should be a usable first draft, but not pretend to be final if important context is missing.

### Mode: Review Design Doc

Use when the user provides an existing design document and asks for review, critique, feedback, or quality check.

Behavior:

* Review for decision clarity, not just writing quality.
* Identify major gaps before minor wording issues.
* Look for vague claims, missing decisions, hidden assumptions, weak alternatives, missing tradeoffs, missing failure paths, and unnecessary detail.
* Call out sections that should be shortened, removed, merged, or moved to appendix.
* Distinguish design-substance issues from writing/style issues.
* Do not rewrite the whole document unless asked.

Output should include:

* Overall assessment
* Major strengths
* Major gaps
* Decision clarity issues
* Missing or weak sections
* Suggested cuts or compression
* Suggested additions
* Concrete rewrite examples where useful

### Mode: Revise Design Doc

Use when the user asks to improve, rewrite, restructure, or update an existing design document.

Behavior:

* Preserve the user’s design intent and confirmed decisions.
* Improve structure, clarity, and concision.
* Make assumptions, constraints, tradeoffs, risks, and open questions explicit.
* Remove generic filler and repeated explanations.
* Avoid changing substantive design decisions unless clearly framed as a suggestion.
* Keep terminology consistent.
* Keep the document reviewable.

Output should include the revised text or revised sections, plus a brief note summarizing important changes.

### Mode: Compress Design Doc

Use when the user asks to shorten, simplify, make concise, reduce length, or make the document easier to digest.

Behavior:

* Preserve decision-critical content.
* Remove obvious statements, generic best-practice prose, repeated context, and excessive implementation detail.
* Merge overlapping sections.
* Move reference detail to appendix.
* Keep decisions, assumptions, constraints, tradeoffs, risks, and open questions visible.
* Do not remove important nuance merely to make the document shorter.

Output should include:

* Compressed version
* Optional list of removed or moved content
* Any risks from compression, if important

### Mode: Extract Decisions

Use when the user asks what decisions, assumptions, risks, tradeoffs, or open questions exist in a document or notes.

Behavior:

* Extract the key design decisions.
* Separate confirmed decisions from assumptions and open questions.
* Identify tradeoffs and risks.
* Highlight decisions that appear implied but not explicitly stated.
* Do not invent decisions.

Output should include:

* Confirmed decisions
* Assumptions
* Open questions
* Tradeoffs
* Risks
* Suggested decisions to clarify

### Mode: Split Parent Doc and Sub-Docs

Use when the design is too large, spans multiple components, or the user asks whether to split the document.

Behavior:

* Identify what belongs in the parent design doc.
* Identify what should move to sub-design docs or appendices.
* Keep the parent focused on problem, scope, architecture, core decisions, integration points, tradeoffs, rollout, and risks.
* Move detailed schema, APIs, edge-case matrices, migration scripts, and component internals into sub-docs when appropriate.

Output should include:

* Recommended document structure
* Parent doc outline
* Suggested sub-docs
* What content moves where
* Rationale for the split

### Mode: Final Review Before Sharing

Use when the user asks whether the design doc is ready for review or sharing.

Behavior:

* Check whether the document is understandable, concise, and decision-focused.
* Identify blockers that should be fixed before sharing.
* Identify non-blocking improvements.
* Check that assumptions and open questions are visible.
* Check that the summary is strong enough for busy reviewers.

Output should include:

* Ready / not ready assessment
* Blocking issues
* Suggested improvements
* Final review checklist

## Skill Retrospective Mode

Use this mode when the user asks to improve this skill, or when a design-doc task reveals that the skill instructions were incomplete, unclear, too verbose, too generic, or hard to apply.

The agent may inspect the skill content and propose improvements, but must not automatically rewrite the skill unless the user explicitly asks.

### When to Suggest Skill Improvements

Suggest a skill improvement only when there is evidence from the current task, such as:

* The skill produced generic filler.
* The skill overfilled the template.
* The skill asked for unnecessary clarification.
* The skill missed an important design-doc section.
* The skill failed to distinguish confirmed information from assumptions.
* The skill did not provide the right task mode.
* The skill created too much detail instead of a concise main reading path.
* The user had to repeat instructions that should have been encoded in the skill.
* A reusable prompt pattern emerged that should become a task mode or rule.

Do not suggest changes just because the skill could be more elaborate.

### Retrospective Output

When proposing skill improvements, output:

1. **Observed issue**

   * What happened in the current task?

2. **Why it matters**

   * How did it reduce design-doc quality, usability, or efficiency?

3. **Proposed skill change**

   * The exact rule, task mode, checklist item, or reference-file update to add.

4. **Where to put it**

   * `SKILL.md`, `references/design-doc-template.md`, `references/review-checklist.md`, or another file.

5. **Risk of the change**

   * Could this make the skill too rigid, too verbose, or overfit to one case?

6. **Patch**

   * Provide a concise copy-paste-ready patch or replacement text.

### Improvement Principles

Keep skill improvements small and evidence-based.

Prefer adding:

* A missing task mode
* A sharper behavior rule
* A checklist item
* A reusable output format
* A short anti-pattern warning

Avoid adding:

* Long explanations
* Generic best practices
* One-off project details
* Rules that only apply to a single document
* Instructions that make the skill harder to use

### Human Approval Rule

Skill updates require human approval.

The agent may propose changes, but the user decides whether to apply them.

If editing files directly, show the proposed diff first unless the user explicitly asked to apply the update.


## Mode: Conversation to Design State

Use when the user has been discussing a design through back-and-forth conversation and wants to prepare for drafting, updating, or reviewing a design document.

Do not treat the whole conversation as design-doc prose.

Instead, extract the current design state.

Behavior:

* Identify confirmed decisions from the conversation.
* Identify assumptions that were inferred but not explicitly confirmed.
* Identify open questions that still need human judgment.
* Identify rejected, deferred, or superseded options.
* Identify important tradeoffs and risks.
* Identify terminology and core concepts that should be used consistently.
* Identify which design-doc sections are likely affected.
* Ignore exploratory ideas that were discussed but not adopted.
* Do not present assumptions as decisions.
* Do not draft a full design document unless the user asks for one.

Output should include:

### Confirmed Decisions

List decisions explicitly made or clearly accepted by the user.

### Assumptions

List reasonable inferences that need confirmation.

### Open Questions

List unresolved questions that affect the design.

### Deferred or Rejected Options

List options discussed but not chosen, if relevant.

### Tradeoffs and Risks

List important tradeoffs and risks surfaced in the conversation.

### Suggested Document Updates

List design-doc sections that should be created or updated.

### Missing Context

List only the missing context that materially affects the design.

Use this mode before drafting or updating a design document from a long conversation.


## Mode: Update Design Doc from Conversation

Use when the user asks to update an existing design document based on recent discussion.

Behavior:

* First extract the design-state changes from the conversation.
* Distinguish new confirmed decisions from assumptions and suggestions.
* Identify which document sections should change.
* Preserve existing content that is still correct.
* Avoid rewriting unrelated sections.
* Remove or revise content that is now superseded.
* Keep the update concise and decision-focused.
* If important uncertainty remains, update the Open Questions section instead of pretending the decision is final.

Output should include:

1. Summary of changes
2. Sections updated
3. Revised text or patch
4. Assumptions that need confirmation
5. Open questions that remain

Prefer targeted updates over full rewrites unless the document structure is no longer suitable.


## Reference Files

This skill may include optional reference files under references/.

Use them as follows:

* references/design-doc-template.md: use when drafting a new design document or restructuring an existing one.
* references/review-checklist.md: use when reviewing, critiquing, or quality-checking a design document.

Do not copy reference content mechanically. Apply it based on the user’s task and the specific design context.