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

Build container images (mirrors CI Docker build):

```bash
docker build -f docker/Dockerfile.service -t agent-service-toolkit.service:local .
docker build -f docker/Dockerfile.app -t agent-service-toolkit.app:local .
```

## High-level architecture

- Runtime entrypoint is `src/run_service.py`, which boots Uvicorn for `service:app` (`src/service/service.py`) and also initializes the Study Companion DB pool on startup/shutdown.
- `src/service/service.py` is the main HTTP surface for agent orchestration (`/info`, `/{agent_id}/invoke`, `/{agent_id}/stream`, `/history`, `/feedback`, `/health`).
- Agent routing is registry-driven in `src/agents/agents.py`: each `AGENTS` key becomes a valid path namespace; default fallback is `research-assistant`.
- FastAPI lifespan wiring in `src/service/service.py` + `src/memory/__init__.py` initializes checkpointer/store backends (SQLite/Postgres/Mongo checkpointer, SQLite/Postgres store) and injects them into each loaded agent graph.
- LLM/provider and model availability are centralized in `src/core/settings.py` and `src/core/llm.py`; service startup fails if no provider is configured.
- `src/api/study_routes.py` adds a second API domain under `/study/*` for onboarding, teaching, quiz generation/submission, progress, and replanning, backed by `src/db/connection.py` and `src/db/schema.sql`.
- `src/client/client.py` is the canonical client for `/info`, invoke/stream/history/feedback; `src/streamlit_app.py` is the main consumer (chat UI + Study Companion dev dashboard).

## Key conventions in this codebase

- **Register agents centrally:** new agents must be added to `src/agents/agents.py` (description + graph) to show up in `/info` and become callable endpoints.
- **Preserve stream protocol shape:** SSE events are expected as `data: {"type":"message"|"token"|"error","content":...}` and terminated with `data: [DONE]`; the client parser depends on this exact contract.
- **Respect reserved runtime config keys:** request `agent_config` must not include `thread_id`, `user_id`, or `model` (service rejects these).
- **Conversation continuity is config-driven:** `thread_id` and `user_id` are passed through `RunnableConfig.configurable` and are the mechanism for chat continuity/history.
- **Tests use marker gating for Docker flows:** Docker-dependent tests are marked `@pytest.mark.docker` and are skipped unless `--run-docker` is provided (`tests/conftest.py`).
- **Default pytest environment includes a fake OpenAI key:** `pyproject.toml` sets `OPENAI_API_KEY=sk-fake-openai-key` for tests; this is relied on by settings validation tests and service tests.
- **Study onboarding window is constrained in API schema:** `/study/onboard` enforces `duration_days` between 2 and 7 and defaults `start_date` using `Asia/Kolkata` timezone logic.
- **Quiz responses are intentionally sanitized before returning to UI:** `/study/quiz/generate` strips `correct_index` and explanation fields from generated questions.
- **Progress/replan flows rely on DB state, not in-memory session state:** `/study/replan/{user_id}` reads `study_plans.meta` flags and only re-schedules remaining `pending` days.
