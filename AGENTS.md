# Follow the `CLAUDE.md`

## Cursor Cloud specific instructions

### Project overview

LangGraph-based AI agent that searches the web for a given topic, summarizes results in Korean, and sends the summary via email. See `CLAUDE.md` for full architecture and commands.

### Key commands

| Task | Command |
|------|---------|
| Install deps | `uv sync --all-packages` |
| Run tests | `uv run pytest tests/ -v` |
| Lint check | `uv run ruff check .` |
| Format check | `uv run ruff format --check .` |
| Dev server | `uv run langgraph dev --no-browser --port 8123` |

### Environment setup

- Python 3.13 is required (`.python-version`). Install via `uv python install 3.13` if not present.
- Copy `.env.example` to `.env` and fill in real API keys before running the dev server. Required keys: `GOOGLE_API_KEY`, `TAVILY_API_KEY`, `RESEND_API_KEY`.
- The dev server starts an in-memory LangGraph runtime (no Docker/DB needed). API docs at `http://localhost:8123/docs`.
- Tests use mocked external dependencies and run without API keys.

### Gotchas

- The `langgraph dev` command auto-opens a browser by default; always pass `--no-browser` in headless/cloud environments.
- LangSmith metadata submission warnings (403) are expected when `LANGSMITH_API_KEY` is not set; they do not affect functionality.
- Pre-existing ruff lint/format issues exist in `tests/` files (import sorting, unused imports). These are not blockers.
