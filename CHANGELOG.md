# Changelog

All notable changes to Terrarium will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-02-11

### Added

#### Vivarium

- **Core Behavior Tree Execution Engine**
  - `BehaviorTree` class for running trees with deterministic semantics
  - Node interface for creating custom behavior tree nodes
  - Full test coverage (236 tests) with predictable execution

- **Node Types**
  - `Action`: Performs work, may modify state, returns SUCCESS/FAILURE/RUNNING
  - `Condition`: Read-only evaluation, returns SUCCESS/FAILURE
  - `Sequence`: Executes children in order, all must succeed
  - `Selector`: Tries children until one succeeds
  - `Parallel`: Runs all children simultaneously with configurable thresholds

- **State Management**
  - `State` class: Dict-like container for tree execution context
  - Supports both bracket and dot notation access (`state["key"]` and `state.key`)

- **Deterministic Execution**
  - Same state input always produces same output
  - Resumption support for composite nodes via `current_index` tracking
  - Child status tracking in Parallel nodes to prevent duplicate side-effects

- **Decorators and Utilities**
  - `@action` decorator for simple action creation
  - `@condition` decorator for simple condition creation
  - Comprehensive docstrings for all public APIs

- **Examples**
  - Simple behavior tree example
  - Complex example with nested composites
  - Real-world pattern examples

#### Treehouse

- **Observability Tool**
  - External monitoring of Vivarium behavior trees
  - Event-driven architecture via shared event boundary

- **LLM Integration**
  - `LLMNode` for behavior trees that interact with language models
  - Provider interface for LLM integration (`provider.py`)
  - Multiple LLM provider support

- **Debugging and Inspection**
  - Tree debugger for runtime inspection
  - Step-through execution capabilities
  - Node status tracking and visualization

- **Web-Based Visualizer**
  - FastAPI-based visualization server
  - Real-time tree visualization
  - WebSocket support for live updates
  - Interactive node inspection

- **Examples**
  - Basic LLM integration example
  - Visualizer usage example
  - Real-world agent pattern examples

#### Documentation

- Comprehensive `README.md` for project overview
- `docs/event-boundary.md`: Event contract specification between Vivarium and Treehouse
- Package-specific READMEs for Vivarium and Treehouse
- Architecture documentation and design principles
- API documentation via docstrings

#### Build and Release Infrastructure

- GitHub Actions workflows:
  - `tests.yml`: Automated testing on Python 3.10-3.13, all PRs and main branch pushes
  - `lint.yml`: Code linting and formatting checks
  - `publish.yml`: Automated PyPI publishing on git tags
  
- Build configuration:
  - `pyproject.toml` for both packages with metadata and dependencies
  - Hatchling build backend
  - Development dependency management via uv

- Development tooling:
  - `Makefile` with common tasks
  - ruff configuration for linting
  - black configuration for code formatting
  - pytest configuration with markers for integration tests
  - uv workspace configuration for monorepo management

#### Community

- `CONTRIBUTING.md`: Contribution guidelines and workflow
- `DEVELOPMENT.md`: Development setup and common tasks
- `LICENSE`: Apache 2.0 license

### Project Status

- **Vivarium**: 236 unit/integration tests, deterministic execution engine stable
- **Treehouse**: 252 unit/integration tests, observability features functional
- **Total Test Coverage**: 488 tests across both packages
- **Early-stage Release**: Core architecture is stable; API may evolve

### Notes

- ⚠️ Event boundary is v0; breaking changes may occur in future versions
- No external dependencies for Vivarium (pure Python execution)
- Treehouse has optional visualizer extras for web UI

---

## How to Upgrade

### From Pre-Release

This is the initial public release. No upgrade path exists.

### To Next Release

Subscribe to release notifications at https://github.com/ricardokirkner/terrarium/releases to stay updated.

---

## Security

For security issues, please email ricardo@kirkner.com.ar instead of using the issue tracker.

---

## Links

- **GitHub**: https://github.com/ricardokirkner/terrarium
- **PyPI (Vivarium)**: https://pypi.org/project/vivarium/
- **PyPI (Treehouse)**: https://pypi.org/project/treehouse/
- **Documentation**: https://github.com/ricardokirkner/terrarium/tree/main/docs
