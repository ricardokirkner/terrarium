"""State management for behavior trees.

The State class provides a flexible, dict-like container for storing agent
state that is passed through the behavior tree during execution. It supports
both dictionary-style access and dot notation for convenience.
"""

from typing import Any


class State:
    """A dict-like class for storing agent state in behavior trees.

    State provides a flexible container that supports:
    - Dictionary-style access: state["key"], state.get("key")
    - Dot notation access: state.key
    - Nested access: state.player.health
    - Standard dict operations: get, set, has, keys, values, items

    Nested State objects are automatically created when accessing undefined
    attributes via dot notation, enabling deep nested structures.

    Examples:
        >>> state = State()
        >>> state.set("health", 100)
        >>> state.get("health")
        100
        >>> state.health
        100
        >>> state.player.health = 50
        >>> state.player.health
        50
    """

    def __init__(self, data: dict[str, Any] | None = None):
        """Initialize the State with optional initial data.

        Args:
            data: Optional dictionary of initial state values.
        """
        # Use object.__setattr__ to avoid triggering our custom __setattr__
        object.__setattr__(self, "_data", {})
        if data is not None:
            for key, value in data.items():
                self.set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from state.

        Args:
            key: The key to look up.
            default: Value to return if key is not found.

        Returns:
            The value associated with key, or default if not found.
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in state.

        Args:
            key: The key to set.
            value: The value to store.
        """
        # Convert nested dicts to State objects
        if isinstance(value, dict) and not isinstance(value, State):
            value = State(value)
        self._data[key] = value

    def has(self, key: str) -> bool:
        """Check if a key exists in state.

        Args:
            key: The key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        return key in self._data

    def __getattr__(self, key: str) -> Any:
        """Support dot notation access (state.key).

        If the key doesn't exist, creates a new nested State object
        to support chained access like state.player.health = 50.
        """
        if key.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{key}'")

        if key in self._data:
            return self._data[key]

        # Create nested State for undefined keys to support chaining
        nested = State()
        self._data[key] = nested
        return nested

    def __setattr__(self, key: str, value: Any) -> None:
        """Support dot notation assignment (state.key = value)."""
        if key.startswith("_"):
            object.__setattr__(self, key, value)  # pragma: no cover
        else:
            self.set(key, value)

    def __getitem__(self, key: str) -> Any:
        """Support bracket notation access (state["key"])."""
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Support bracket notation assignment (state["key"] = value)."""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator (key in state)."""
        return self.has(key)

    def __iter__(self):
        """Support iteration over keys."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return number of keys in state."""
        return len(self._data)

    def keys(self):
        """Return state keys."""
        return self._data.keys()

    def values(self):
        """Return state values."""
        return self._data.values()

    def items(self):
        """Return state items as (key, value) pairs."""
        return self._data.items()

    def update(self, data: dict[str, Any]) -> None:
        """Update state with values from a dictionary.

        Args:
            data: Dictionary of values to add/update.
        """
        for key, value in data.items():
            self.set(key, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to a plain dictionary.

        Recursively converts nested State objects to dicts.

        Returns:
            Dictionary representation of the state.
        """
        result = {}
        for key, value in self._data.items():
            if isinstance(value, State):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result

    def __repr__(self) -> str:
        """Return string representation of state."""
        return f"State({self.to_dict()!r})"
