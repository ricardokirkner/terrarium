# Development Guide

This document provides detailed instructions for setting up and working on Terrarium.

## Prerequisites

- **Python 3.10+** (3.13 recommended)
- **uv** - Fast Python package installer and resolver
  - Install: https://docs.astral.sh/uv/getting-started/installation/
- **Make** - Build automation
  - macOS: `brew install make` or use `gmake`
  - Linux: Usually pre-installed
  - Windows: Use WSL or install via package manager

## Quick Start

```bash
# Clone repository
git clone https://github.com/ricardokirkner/terrarium.git
cd terrarium

# Install dependencies
make install

# Run tests
make test

# Run checks (linting + formatting)
make check
```

## Available Commands

All commands are defined in the root `Makefile`:

```bash
make install          # Install all dependencies (uv sync)
make test             # Run all tests (unit + integration)
make test-unit        # Unit tests only
make test-integration # Integration tests only
make test-coverage    # Run tests with coverage report
make check            # Format check + linting (ruff, black)
make format           # Auto-format code (black, ruff)
make ci               # Full CI pipeline (check + test)
```

## Project Structure

```
terrarium/
├── vivarium/                    # Behavior tree execution engine
│   ├── src/vivarium/
│   │   ├── core/               # Core execution logic
│   │   │   ├── tree.py         # BehaviorTree, Node classes
│   │   │   ├── nodes/          # Sequence, Selector, Parallel, Action, Condition
│   │   │   ├── state.py        # State management
│   │   │   └── __init__.py
│   │   ├── events/             # Event definitions
│   │   └── __init__.py
│   ├── tests/                  # Unit and integration tests
│   │   ├── test_tree.py
│   │   ├── test_nodes.py
│   │   └── ...
│   ├── examples/               # Example behavior trees
│   │   └── simple_example.py
│   ├── README.md               # Vivarium package overview
│   └── pyproject.toml          # Vivarium package metadata
│
├── treehouse/                   # Observability and visualization tool
│   ├── src/treehouse/
│   │   ├── nodes/              # LLM node implementations
│   │   │   ├── llm_node.py
│   │   │   └── provider.py
│   │   ├── debugger/           # Tree debugger and inspector
│   │   ├── visualizer/         # Web-based visualization
│   │   └── __init__.py
│   ├── tests/                  # Unit and integration tests
│   ├── examples/               # Example usage with visualization
│   ├── README.md               # Treehouse package overview
│   └── pyproject.toml          # Treehouse package metadata
│
├── docs/                        # Documentation
│   ├── event-boundary.md       # Event contract between vivarium and treehouse
│   └── architecture.md         # System architecture (optional)
│
├── .github/
│   └── workflows/              # GitHub Actions CI/CD
│       ├── tests.yml           # Test on Python 3.10-3.13
│       ├── lint.yml            # Linting and formatting checks
│       └── publish.yml         # PyPI publishing on git tags
│
├── Makefile                     # Build targets
├── README.md                    # Project overview
├── CONTRIBUTING.md              # Contribution guidelines
├── DEVELOPMENT.md               # This file
├── PUBLISHING.md                # Publishing to PyPI
├── PUBLIC_RELEASE_CHECKLIST.md # Release checklist
└── LICENSE                      # Apache 2.0 license
```

## Vivarium Architecture

Vivarium is a behavior tree execution engine with deterministic semantics.

### Core Concepts

**Node Types:**
- `Condition`: Read-only evaluation, returns SUCCESS/FAILURE
- `Action`: Performs work, may return SUCCESS/FAILURE/RUNNING
- `Sequence`: Executes children in order until one fails
- `Selector`: Tries children until one succeeds
- `Parallel`: Executes all children, supports success/failure thresholds

**State:**
- Dict-like object passed through tree execution
- Supports both `state["key"]` and `state.key` access
- Only input to node logic

**BehaviorTree:**
- Wraps a root node
- Tracks tick count and execution

### Key Design Patterns

1. **Resumption**: Composite nodes track `current_index` to resume execution
2. **Stateless Evaluation**: Conditions are read-only
3. **Side-effect Prevention**: Parallel prevents re-executing completed children
4. **Relative Imports**: All imports within `src/vivarium/core/` use relative paths

## Treehouse Architecture

Treehouse is an external observability tool for behavior trees.

### Components

- **LLM Nodes**: Behavior tree nodes that interact with language models
- **Debugger**: Runtime inspection and stepping
- **Visualizer**: Web-based UI for tree visualization and monitoring
- **Event Consumer**: Reads vivarium events via the event boundary

### Event Boundary

Treehouse and Vivarium communicate through a shared event boundary (see `docs/event-boundary.md`). This decouples execution from observation.

## Running Tests

### Unit Tests Only

```bash
make test-unit
```

Or directly:
```bash
uv run pytest tests/ -v -m "not integration"
```

### Integration Tests Only

```bash
make test-integration
```

Or:
```bash
uv run pytest tests/ -v -m "integration"
```

### Specific Test File

```bash
uv run pytest tests/test_tree.py -v
```

### Specific Test

```bash
uv run pytest tests/test_tree.py::test_name -v
```

### With Coverage

```bash
make test-coverage
```

Coverage reports are generated in `htmlcov/`.

## Code Quality

### Linting and Formatting

```bash
# Check without modifying
make check

# Auto-format code
make format
```

**Tools:**
- **ruff**: Fast Python linter
  - Line length: 88 characters
  - Enabled rules: E, F, W, B, C, I (errors, undefined names, warnings, bugbear, complexity, imports)
- **black**: Code formatter
  - Line length: 88 characters

### Type Hints

Type hints are encouraged but not required. The project aims to be fully typed in future versions.

## Working with Both Packages

Treehouse depends on Vivarium. When working on both:

```bash
# Install both with dev dependencies
make install

# Run tests for both
make test

# Format and lint both
make check
```

The workspace is configured in `pyproject.toml` with:
```toml
[tool.uv.sources]
terrarium-vivarium = { path = "../vivarium" }
```

This allows treehouse to develop against the local vivarium.

## Publishing and Distribution

See [PUBLISHING.md](PUBLISHING.md) for details on:
- Building packages locally
- Testing installation
- Publishing to PyPI
- Version management

## Documentation

### For Users

- `README.md` - Quick start and overview
- `docs/event-boundary.md` - Event contract specification
- Package READMEs - Vivarium and Treehouse specific guides

### For Developers

- `DEVELOPMENT.md` - This file
- `CONTRIBUTING.md` - How to contribute
- Docstrings in source code
- Examples in `vivarium/examples/` and `treehouse/examples/`

When adding new features, update relevant documentation:
1. Add docstrings to public APIs
2. Update package README if user-facing
3. Add examples if introducing new patterns
4. Update `docs/` if affecting architecture

## Common Tasks

### Adding a New Test

1. Create test file: `tests/test_feature.py`
2. Use pytest fixtures and mock classes
3. Mark integration tests: `@pytest.mark.integration`

Example:
```python
import pytest
from vivarium.core.nodes import Sequence, Action
from vivarium.core.state import State
from vivarium.core.tree import NodeStatus

class SuccessAction(Action):
    def execute(self, state):
        return NodeStatus.SUCCESS

def test_sequence_continues_on_success():
    state = State()
    seq = Sequence([SuccessAction(), SuccessAction()])
    
    status = seq.execute(state)
    
    assert status == NodeStatus.SUCCESS
```

### Adding a New Module

1. Create `src/vivarium/newmodule/` or `src/treehouse/newmodule/`
2. Add `__init__.py` with public exports
3. Create tests in `tests/test_newmodule.py`
4. Add docstrings to public classes/functions
5. Update relevant documentation

### Updating Dependencies

```bash
# View current dependencies
uv pip list

# Add a new dependency (to pyproject.toml dev group)
# Edit pyproject.toml directly, then:
make install

# Update all dependencies to latest compatible
uv sync --upgrade
```

## Troubleshooting

### Import Errors

If you see import errors after pulling changes:
```bash
make install
```

This reinstalls dependencies.

### Test Failures After Changes

1. Ensure you're on the correct branch
2. Run `make install` to sync dependencies
3. Run `make check` to catch format/lint issues
4. Run `make test` to verify all tests pass

### Code Format Issues

```bash
# Auto-fix formatting issues
make format

# Check if there are remaining issues
make check
```

## Getting Help

- Check existing issues: https://github.com/ricardokirkner/terrarium/issues
- Open a new issue: https://github.com/ricardokirkner/terrarium/issues/new
- Contact: ricardo@kirkner.com.ar

---

For more details on contributing, see [CONTRIBUTING.md](CONTRIBUTING.md).
