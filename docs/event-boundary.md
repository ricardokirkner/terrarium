# The Terrarium Event Boundary (v0)

This document defines the **shared semantic event boundary** between **Vivarium** (execution) and **Treehouse** (observation).

It is the most important contract in the Terrarium ecosystem.

Vivarium emits events. Treehouse (and other tools) consume them.
Execution and interpretation are deliberately decoupled.

---

## Purpose

The event boundary exists to make **agent behavior observable without making execution fragile**.

It provides a common language for describing what *happened* during behavior tree execution, without prescribing:

- how events are stored
- how they are visualized
- how they are interpreted
- whether they are retained at all

---

## Design Principles

### 1. Semantic, Not Mechanical

Events describe **behavior tree meaning**, not implementation details.

Good events answer questions like:

- Which node was evaluated?
- Why did a branch fail?
- Where did execution stall?

They do *not* describe:

- call stacks
- internal data structures
- framework-specific control flow

---

### 2. One-Way by Design

The boundary is strictly **write-only** from the runtime’s perspective.

- Vivarium emits events
- Observers listen
- No control, feedback, or mutation flows back into execution

This guarantees:

- determinism
- safety in production
- observability without Heisenbugs

---

### 3. Transport-Agnostic

The boundary defines **event semantics**, not transport.

Events may be:

- logged
- streamed
- buffered
- sampled
- dropped

Correctness of execution must never depend on observation.

---

### 4. Observer Plurality

Treehouse is a first consumer — not the only one.

Any tool that understands this boundary can:

- visualize behavior
- analyze decisions
- compare executions
- support debugging or research

---

## Conceptual Model

Execution is modeled as a sequence of **ticks**.

Within each tick, nodes transition through a well-defined lifecycle.
Events capture these transitions.

```text
Tick
 ├─ Node entered
 │   ├─ Condition evaluated
 │   ├─ Action invoked
 │   └─ Result produced
 └─ Tick completed
```

---

## Core Event Types (v0)

The following event types form the minimal viable boundary.

### Tick Events

- `tick_started`
- `tick_completed`

Each tick has a unique identifier.

---

### Node Lifecycle Events

- `node_entered`
- `node_exited`
- `node_result`

Where `node_result` is one of:

- `success`
- `failure`
- `running`

---

### Condition Events

- `condition_evaluated`

Payload may include:

- condition name
- input snapshot (opaque)
- boolean result

---

### Action Events

- `action_invoked`
- `action_completed`

Payload may include:

- action name
- arguments (opaque)
- outcome
- duration

---

## Required Event Fields

Every event **must** include:

```text
- event_type
- tick_id
- node_id
- node_type
- path_in_tree
- timestamp
```

These fields allow observers to:

- reconstruct structure
- preserve causality
- correlate events across time

---

## Optional Context Fields

Events **may** include additional context, such as:

- retry counters
- execution duration
- LLM prompt or tool metadata (opaque to Vivarium)
- environment state hashes

The boundary does not interpret these fields.

---

## Ordering Guarantees

Vivarium guarantees:

- total ordering of events *within a tick*
- causal ordering across ticks
- no reordering or retroactive mutation

Observers may assume:

> If event B follows event A in the stream, B happened *after* A.

Observers **must tolerate missing, partial, or sampled event streams**. Observation is best-effort by design and must never be required for correct execution.

---

## Versioning

This document defines **Event Boundary v0**.

Breaking changes will:

- increment the major version
- be documented explicitly
- prioritize observer compatibility

---

## Non-Goals

The event boundary does *not* attempt to:

- standardize visualization
- prescribe storage formats
- encode agent intent
- replace tracing systems

Its purpose is narrower and more precise: **to describe behavior clearly**.

---

## Why This Boundary Matters

Without a stable boundary:

- observability becomes invasive
- runtimes ossify
- interpretation tools break easily

With it:

- execution and understanding evolve independently
- multiple observers become possible
- agent behavior becomes inspectable by design

---

## Minimal Example (Illustrative)

The following example shows a single semantic event as it might be emitted by Vivarium and consumed by Treehouse. This is *illustrative*, not a fixed schema:

```json
{
  "event_type": "condition_evaluated",
  "tick_id": "42",
  "node_id": "auth_check",
  "node_type": "Condition",
  "path_in_tree": "selector/condition@0",
  "timestamp": "2026-01-30T13:41:22.531Z",
  "payload": {
    "result": false
  }
}
```

Observers should rely on semantic meaning and ordering guarantees, not on the presence of any specific optional field.

---

*Run the behavior. Emit the meaning. Interpret elsewhere.*
