# 🌳 Treehouse

Treehouse is an **external observability and interpretability tool** for behavior-tree–driven agents.

It lets you observe how behavior unfolds in real time — which branches were evaluated, which paths were taken, and where execution stalled or failed — without interfering with execution.

Treehouse is where you go to *watch behavior trees think*.

---

## What Treehouse Does

- Consumes semantic execution events
- Reconstructs behavior tree execution over time
- Surfaces decisions in structural, human-readable form

Treehouse treats behavior trees — not logs or metrics — as the unit of meaning.

---

## Event Boundary

Treehouse relies on the shared event boundary defined here:

> `../docs/event-boundary.md`

This boundary is Treehouse’s primary input API. Any runtime that emits compatible events can be observed — Vivarium is a natural fit, not a requirement.

---

## What Treehouse Is *Not*

- Not a runtime
- Not a controller
- Not coupled to a specific agent framework

Treehouse observes. It does not direct.

---

## Status

Treehouse is early-stage and exploratory.

The focus is on correctness, clarity, and faithful reconstruction of behavior — polish comes later.

---

*Run the behavior. Observe the decisions. Understand the agent.*
