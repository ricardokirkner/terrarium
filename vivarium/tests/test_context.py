"""Tests for execution context."""

from vivarium.core.context import ExecutionContext


def test_context_tracks_tick_id():
    """ExecutionContext should track current tick_id."""
    ctx = ExecutionContext(tick_id=5)
    assert ctx.tick_id == 5


def test_context_builds_path():
    """ExecutionContext should build path as nodes are entered."""
    ctx = ExecutionContext(tick_id=1)
    assert ctx.path == ""

    # Root node has no parent, so no index
    ctx2 = ctx.child("root", "Selector")
    assert ctx2.path == "root"

    # Child of composite has an index
    ctx3 = ctx2.child("check_health", "Condition", 0)
    assert ctx3.path == "root/check_health[0]"


def test_context_tracks_composite_index():
    """ExecutionContext should track child index for composite nodes."""
    ctx = ExecutionContext(tick_id=1)
    # Root composite has no parent index
    ctx2 = ctx.child("seq", "Sequence")
    ctx3 = ctx2.child("child_a", "Action", 0)
    assert ctx3.path == "seq/child_a[0]"

    ctx4 = ctx2.child("child_b", "Action", 1)
    assert ctx4.path == "seq/child_b[1]"


def test_context_is_immutable():
    """ExecutionContext.enter should return a new context."""
    ctx = ExecutionContext(tick_id=1)
    ctx2 = ctx.child("root", "Selector")
    assert ctx.path == ""  # Original unchanged
    assert ctx2.path == "root"
