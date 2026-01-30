# 🪴 Vivarium

Vivarium is a **behavior tree execution environment** designed as a *living system*.

Agents act inside Vivarium. Behavior unfolds step by step. Every decision can be observed — without entangling execution with interpretation.

Vivarium exists to run behavior trees clearly, deterministically, and without opinionated tooling layered on top.

---

## What Vivarium Does

- Executes behavior trees with explicit, deterministic semantics
- Defines a clear node lifecycle (tick, enter, evaluate, succeed, fail, running)
- Emits structured, semantic execution events

Vivarium is intentionally small and auditable. Its purpose is execution, not explanation.

---

## Observability by Design

Vivarium treats observability as a **first-class concern**, but not an invasive one.

During execution, Vivarium emits events defined by the shared event boundary:

> `../docs/event-boundary.md`

These events are:

- behavior-tree–aware
- transport-agnostic
- safe to drop, buffer, or sample

Vivarium does not assume who is listening — or whether anyone is listening at all.

---

## What Vivarium Is *Not*

- Not an agent framework
- Not a UI or visualization tool
- Not coupled to any observability backend

Vivarium runs the behavior. Interpretation lives elsewhere.

---

## Status

Vivarium is early-stage and experimental.

The execution model is stable; APIs may change as the event boundary evolves.
