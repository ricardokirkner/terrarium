# Contributing to Terrarium

Thank you for your interest in contributing to Terrarium! We welcome bug reports, feature suggestions, and pull requests.

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to ricardo@kirkner.com.ar.

## Reporting Bugs

Before submitting a bug report:
- Check the [issues](https://github.com/ricardokirkner/terrarium/issues) to see if the bug has already been reported
- Include as much detail as possible:
  - A clear title and description
  - Python version and OS
  - Steps to reproduce the issue
  - Expected vs. actual behavior
  - Relevant code examples or tracebacks

## Suggesting Features

Feature suggestions are tracked as [GitHub Issues](https://github.com/ricardokirkner/terrarium/issues).

When suggesting a feature:
- Use a clear, descriptive title
- Provide a detailed description of the desired behavior
- Explain why this feature would be useful
- List examples of how it would be used
- Note if this would be a breaking change

## Development Setup

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Make](https://www.gnu.org/software/make/)

### Local Development

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/terrarium.git
   cd terrarium
   ```

3. Install dependencies:
   ```bash
   make install
   ```

4. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

### Running Tests

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run a specific test file
uv run pytest tests/test_file.py -v

# Run a specific test
uv run pytest tests/test_file.py::test_name -v
```

### Code Quality

```bash
# Run linting and formatting checks
make check

# Run full CI pipeline (check + test)
make ci
```

The project uses:
- **ruff** for linting
- **black** for code formatting
- **pytest** for testing

## Submitting Pull Requests

1. Ensure your code passes all checks:
   ```bash
   make ci
   ```

2. Write clear commit messages:
   - First line: concise summary (50 chars max)
   - Blank line
   - Detailed explanation if needed

3. Push your branch to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

4. Create a pull request on GitHub:
   - Reference any related issues
   - Describe what the PR does and why
   - List any breaking changes

### PR Guidelines

- Keep PRs focused on a single feature or fix
- Add tests for new functionality
- Ensure all existing tests pass
- Update documentation if needed
- Follow the style guide (see below)

## Style Guide

### Python Code Style

We use **ruff** for linting and **black** for formatting. These tools are automatically run by `make check`.

Key rules:
- Line length: 88 characters (enforced by black)
- Use meaningful variable and function names
- Add docstrings to public classes and functions
- Type hints are encouraged but not required

### Imports

- Organize imports in three groups: standard library, third-party, local
- Use relative imports within `src/vivarium/core/`
- `ruff` enforces import organization automatically

### Testing

- Write tests for all public APIs and functionality
- Use pytest for test organization
- Use clear test names: `test_<component>_<behavior>`
- Mark integration tests with `@pytest.mark.integration`
- Aim for high coverage of new code

Example:
```python
def test_sequence_executes_children_in_order(state):
    """Sequence should execute children sequentially."""
    action1 = SuccessAction()
    action2 = SuccessAction()
    seq = Sequence([action1, action2])
    
    status = seq.execute(state)
    
    assert status == NodeStatus.SUCCESS
    assert action1.executed
    assert action2.executed
```

### Documentation

- Update `README.md` if your changes affect usage
- Update relevant docs in `docs/` directory
- Add docstrings to new functions/classes
- Keep examples up to date

## Project Structure

```
terrarium/
├── vivarium/              # Behavior tree execution engine
│   ├── src/vivarium/
│   │   ├── core/         # Core execution logic
│   │   └── __init__.py
│   ├── tests/            # Unit and integration tests
│   ├── examples/         # Example behavior trees
│   └── pyproject.toml
├── treehouse/             # Observability and visualization tool
│   ├── src/treehouse/
│   │   ├── nodes/        # LLM node implementations
│   │   ├── debugger/     # Tree debugger
│   │   └── __init__.py
│   ├── tests/
│   ├── examples/
│   └── pyproject.toml
├── docs/                  # Documentation
│   └── event-boundary.md # Event contract specification
├── Makefile              # Build targets
└── README.md
```

## Architecture Overview

- **Vivarium**: Pure behavior tree execution with deterministic semantics
- **Treehouse**: External observability tool that consumes vivarium execution events
- **Event Boundary**: The shared contract between execution and observation (see `docs/event-boundary.md`)

See [README.md](README.md) for more details.

## Questions?

Feel free to open an issue or contact us at ricardo@kirkner.com.ar.

---

**Thank you for contributing to Terrarium!**
