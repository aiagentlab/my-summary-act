# My Summary Agent

Act: Project
Cast: Graph/Workflow(Package)

<!-- AUTO-MANAGED: act-overview -->
## Act Overview

**Purpose:** 입력한 토픽에 대해 웹 검색 후 결과를 구조화된 형태로 요약하고 이메일로 전달하는 AI 에이전트
**Domain:** Information Retrieval & Summarization

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: casts-table -->
## Casts

| Cast Name | Purpose | Location |
|-----------|---------|----------|
| Orchestrator | 토픽 기반 웹 검색 → 구조화된 요약 → 미들웨어 기반 승인 → 이메일 발송 (Conditional + Middleware) | [CLAUDE.md](casts/orchestrator/CLAUDE.md) |

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: project-structure -->
## Project Structure

```
my-summary-agent/
├── CLAUDE.md                    # Act-level architecture doc (THIS FILE)
├── pyproject.toml               # Project dependencies
├── langgraph.json               # LangGraph configuration
├── .env.example                 # Environment variables template
├── casts/                       # All Cast implementations
│   ├── __init__.py
│   ├── base_graph.py            # Base graph utilities
│   ├── base_node.py             # Base node utilities
│   └── orchestrator/            # Orchestrator Cast package
│       ├── CLAUDE.md            # Cast-level architecture doc
│       ├── graph.py             # Graph definition
│       ├── pyproject.toml       # Cast-specific dependencies
│       └── modules/             # Implementation modules
└── tests/                       # Test suites
    ├── cast_tests/              # Integration tests
    └── node_tests/              # Unit tests
```

<!-- END AUTO-MANAGED -->

<!-- AUTO-MANAGED: development-commands -->
## Development Commands

### Dev Server

```bash
uv run langgraph dev # Start dev server
uv run langgraph dev --tunnel # With tunnel (for non-Chrome browsers)
```

### Sync Environment

```bash
uv sync --all-packages              # All casts + dev
uv sync --package <cast>            # Specific cast
uv sync --all-packages --no-dev     # Production (no dev dependencies)
uv sync --reinstall --all-packages  # Force reinstall
```

`uv run` automatically checks environment before execution.

Manual sync rarely needed when using:
- `uv add` / `uv remove` (auto-syncs)
- `uv run` commands

### Create Cast

```bash
uv run act cast -c "<cast name>"
```

### Add Act Dependency

Add shared dependencies across all casts.

```bash
uv add <package>                    # Production
uv add --dev <package>              # Development
uv add --group test <package>       # Test only
uv add --group lint <package>       # Lint only
uv remove <package>                 # Remove
```

<!-- END AUTO-MANAGED -->

<!-- MANUAL -->
## Notes

Add project-specific notes here. This section is never auto-modified.

<!-- END MANUAL -->
