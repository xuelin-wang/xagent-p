# Design Document Review Checklist

Use this checklist when reviewing, revising, or compressing a design document.

## Decision Clarity

* Is the main decision clear?
* Is the proposed design easy to find?
* Is the reason for the design clear?
* Is the document more than a description of implementation?
* Can a reviewer understand the proposal from the summary?

## Problem and Scope

* Is the problem specific?
* Is the current pain or limitation clear?
* Is the scope clear?
* Are non-goals explicit?
* Does the doc avoid solving adjacent problems accidentally?

## Requirements and Constraints

* Are goals separated from requirements?
* Are constraints explicit?
* Are requirements specific enough to affect design choices?
* Are vague requirements removed or rewritten?

Weak:

> The system should be scalable.

Better:

> The first version targets fewer than 100 active runs/day. The design avoids a distributed workflow engine until usage requires it.

## Proposed Design

* Are the main components clear?
* Are responsibilities clear?
* Are ownership boundaries clear?
* Are important data and state flows clear?
* Does the design explain why it has this shape?

## Core Concepts

* Are important terms defined?
* Are names used consistently?
* Are concept lifecycles clear?
* Is mutability clear?
* Are relationships between concepts clear?

## Flows

* Is there a clear happy path?
* Are important non-happy paths covered?
* Are failure, retry, fallback, or pause/resume behaviors covered when relevant?
* Are exhaustive edge cases avoided unless they change the design?

## Interfaces and Contracts

* Are public or cross-component contracts clear?
* Are APIs, events, tool interfaces, or state transitions described at the right level?
* Are error behaviors clear where they matter?
* Are implementation details avoided unless contract-critical?

## Invariants

* Are always-true rules stated?
* Are they precise?
* Would they help prevent implementation mistakes?

Examples:

* Completed records are immutable.
* Replay does not call external tools.
* Authorization happens before execution.

## Alternatives and Tradeoffs

* Are alternatives serious?
* Are benefits and drawbacks fairly described?
* Is the chosen design justified?
* Are tradeoffs honest?
* Does the doc avoid pretending the chosen design has no downsides?

## Risks and Rollout

* Are risks concrete?
* Does each risk explain impact and mitigation?
* Is rollout addressed?
* Is migration or compatibility addressed?
* Is rollback considered where relevant?

## Concision

* Can obvious statements be removed?
* Can repeated context be merged?
* Can full schemas or exhaustive cases move to appendix?
* Does every section help the reader make a better decision?

## Final Quality Bar

A good design document should let reviewers answer:

* What problem are we solving?
* What design are we choosing?
* Why this design?
* What is in and out of scope?
* What contracts must implementation follow?
* What tradeoffs and risks remain?
* What open decisions still need resolution?

