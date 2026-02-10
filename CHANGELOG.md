# Changelog

All notable changes to Terrarium will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-10

### Added

#### Vivarium (Execution Engine)
- Behavior tree execution with deterministic semantics
- Node types: Action, Condition, Sequence, Selector, Parallel
- Decorators: Inverter, Repeater, RetryUntilSuccess
- State management with dict-like interface
- Event emission protocol (EventEmitter) for external observation
- Comprehensive test suite (236 tests)

#### Treehouse (Observability)
- Trace collection from Vivarium events
- Execution trace serialization (JSON export/import)
- Terminal trace visualization with colors and tree structure
- Timeline view for chronological execution analysis
- TraceCollector for event aggregation
- Metrics calculation: duration, tokens, costs
- Web-based visualizer with real-time updates (FastAPI + WebSocket)
- LLM integration: OpenAI, Anthropic, and local Ollama support
- LLM-backed Action and Condition nodes
- Debugging: breakpoints, step-through, live inspection
- DebuggerTree for interactive execution control

#### Documentation & Release
- Comprehensive README with architecture overview
- CONTRIBUTING guide with development workflow
- Event Boundary specification (v0)
- Apache 2.0 license
- Examples: chatbot with tools, LLM agent, combat AI, debugging

### Changed

- **Breaking**: Flattened Vivarium package structure
  - `from vivarium.core import ...` → `from vivarium import ...`
  - Cleaner public API for v0.1.0

### Known Limitations

- Trace comparison not yet implemented (planned for v0.2)
- Cost visualization minimal (planned for v0.2)
- State snapshots not captured (planned for v0.2)
- No trace replay for saved executions (planned for v0.2)
- Web visualizer filtering not fully implemented (planned for v0.2)

---

## Planned for Future Releases

### v0.2.0 (Next)
- Trace comparison and diffing API
- Cost breakdown visualizations
- State snapshots before/after each node
- Event filtering in web visualizer
- Live tail mode with configurable log levels

### v0.3.0
- Tree validation and linting
- Coverage analysis across multiple runs
- Performance profiling (flame graphs)
- Multi-agent coordination visualization

### Future
- Export to standard trace formats (OpenTelemetry, etc.)
- Distributed tracing support
- Advanced cost optimization recommendations
- Integration with popular LLM frameworks

---

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Support

- Report issues: https://github.com/ricardokirkner/terrarium/issues
- Discussions: https://github.com/ricardokirkner/terrarium/discussions
- Email: ricardo@kirkner.com.ar
