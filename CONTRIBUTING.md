# Contributing to Terrarium

Thank you for your interest in contributing! This document outlines how to get started.

## Code of Conduct

Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for package management
- Git

### Setup

```bash
git clone https://github.com/ricardokirkner/terrarium.git
cd terrarium
make install
```

## Development Workflow

### Running Tests

```bash
# From root (runs all tests)
make test

# From a package directory
cd vivarium
make test

# Run specific test
uv run pytest tests/test_tree.py::test_name -v
```

### Code Quality

```bash
# Format and lint (required before PR)
make check

# Full CI pipeline
make ci
```

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add trace comparison API
fix: prevent double-pause when stepping
docs: update README with examples
chore: update dependencies
```

## What to Work On

### Good First Issues

- Documentation improvements
- Example code
- Test coverage gaps
- Bug fixes

### Planned Features (v0.2+)

See [MISSING_FEATURES.md](MISSING_FEATURES.md) for the roadmap:

- Trace comparison and diffing
- Cost visualization
- State snapshots
- Event filtering in visualizer
- Tree validation and linting

### Before Starting Large Work

For significant features or changes:

1. **Open an issue** describing the feature or problem
2. **Wait for feedback** before investing time
3. **Discuss approach** to ensure alignment with project vision

## Architecture Guidelines

### Vivarium (Execution)

- **Zero external dependencies** — keep it minimal
- **Deterministic execution** — same inputs always produce same outputs
- **Event-driven** — emit structured events, don't couple to observers
- Tests in `tests/`, implementation in `src/vivarium/core/`

### Treehouse (Observation)

- **Observer pattern** — implements `EventEmitter` protocol
- **Decoupled from Vivarium** — could observe other behavior tree engines
- **Optional dependencies** — visualizer requires FastAPI, but core doesn't
- Tests in `tests/`, implementation in `src/treehouse/`

## Testing Requirements

- **Unit tests** for all new functionality
- **Integration tests** marked with `@pytest.mark.integration` for multi-module tests
- Maintain **>85% code coverage** for new code
- All tests must pass: `make test`

## Pull Request Process

1. **Fork and create a feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** with tests

3. **Ensure code quality**
   ```bash
   make ci
   ```

4. **Push and open a PR** with a clear description

5. **Respond to review feedback** promptly

## Documentation Standards

- Add docstrings to all public functions/classes
- Update README if adding user-facing features
- Include examples in docstrings for complex features
- Mention breaking changes in commit message

## Release Process (Maintainers)

1. Update version in both `pyproject.toml` files
2. Update `CHANGELOG.md` with user-facing changes
3. Create git tag: `git tag -a v0.X.Y -m "Release v0.X.Y"`
4. Push tag and commits
5. GitHub Actions publishes to PyPI automatically

## Questions?

- **Issues**: Use GitHub Issues for bugs and feature requests
- **Discussions**: Use GitHub Discussions for questions and design ideas
- **Email**: ricardo@kirkner.com.ar for direct contact

---

Thank you for contributing to Terrarium!
