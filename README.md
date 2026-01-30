# 🌿 Terrarium

Terrarium is a small, intentional ecosystem for **building and understanding agent behavior**.

It is built around a simple separation of concerns:

- **Vivarium** runs behavior trees — this is where agent behavior *lives*
- **Treehouse** observes behavior trees — this is where agent behavior is *understood*

Execution and interpretation are deliberately decoupled. Agents act first; understanding comes from observation, not interference.

Both components communicate through a shared, semantic event boundary defined in `docs/event-boundary.md`.

---

## Why Terrarium?

As agents grow more capable, their failures become harder to explain.

Logs flatten behavior. Metrics hide intent. Prompts explain goals, not decisions.

Terrarium takes a different approach: it treats **behavior itself as the primary object of study**.

- Vivarium focuses on *doing*
- Treehouse focuses on *seeing*

Together, they form a system where agent behavior can be executed, observed, replayed, and reasoned about — without collapsing everything into a monolithic framework.

---

## Repository Structure

```text
terrarium/
├─ README.md              # This file
├─ docs/
│  └─ event-boundary.md   # Shared semantic execution contract
├─ vivarium/
│  └─ README.md           # Behavior tree runtime
└─ treehouse/
   └─ README.md           # Observability & interpretability
```

---

## Status

Terrarium is early-stage and experimental.

The separation between execution and interpretation is intentional and foundational. APIs will evolve; the boundary will remain.
