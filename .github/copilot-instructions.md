# Copilot instructions for this repository

## Build, test, and lint commands

Use `uv` for local development commands:

```bash
uv sync --frozen
```

Lint and format checks (same pattern as CI):

```bash
uv run ruff format --check
uv run ruff check --output-format github
```

Type checking:

```bash
uv run mypy src/
```

Run the full test suite:

```bash
uv run pytest
```

Run a single test:

```bash
uv run pytest tests/service/test_service.py::test_invoke -q
```

Run Docker-marked integration tests:

```bash
uv run pytest tests/integration -v --run-docker
```

## High-level architecture

- The service entrypoint is `src/run_service.py`, which runs Uvicorn for `service:app` (`src/service/service.py`).
- `src/service/service.py` exposes `/info`, `/invoke`, `/stream` (SSE), `/history`, `/feedback`, and `/health`.
- Agent selection is registry-driven in `src/agents/agents.py`. `DEFAULT_AGENT` is `"research-assistant"`, and each registered key becomes a route namespace (for example `/{agent_id}/invoke`).
- At startup, service lifespan wiring initializes memory/checkpoint backends (`src/memory/*`) and attaches them to each loaded agent graph.
- Backends are selected from settings (`src/core/settings.py`) via `DATABASE_TYPE` (sqlite default, postgres, mongo).
- Model/provider configuration is centralized in `src/core/settings.py` and `src/core/llm.py`; at least one provider key/config must be present or settings initialization fails.
- `src/client/client.py` is the canonical API client used by `src/streamlit_app.py` and supports sync/async invoke plus SSE streaming.

## Key conventions in this codebase

- **Register agents centrally:** new agents must be added to `src/agents/agents.py` (description + graph) to show up in `/info` and become callable endpoints.
- **Preserve stream protocol shape:** SSE events are expected as `data: {"type":"message"|"token"|"error","content":...}` and terminated with `data: [DONE]`; the client parser depends on this exact contract.
- **Respect reserved runtime config keys:** request `agent_config` must not include `thread_id`, `user_id`, or `model` (service rejects these).
- **Conversation continuity is config-driven:** `thread_id` and `user_id` are passed through `RunnableConfig.configurable` and are the mechanism for chat continuity/history.
- **Tests use marker gating for Docker flows:** Docker-dependent tests are marked `@pytest.mark.docker` and are skipped unless `--run-docker` is provided (`tests/conftest.py`).
- **Default pytest environment includes a fake OpenAI key:** `pyproject.toml` sets `OPENAI_API_KEY=sk-fake-openai-key` for tests; this is relied on by settings validation tests and service tests.
