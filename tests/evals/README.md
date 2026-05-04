# Study Companion Agent Evals

This directory contains deterministic golden evals for the LangGraph Study Companion agent.
They mock external LLM calls and tool execution, then validate the public agent contract.

## What The Evals Cover

- onboarding / building a plan
- teaching a plan day
- generating a quiz
- submitting quiz results
- replanning after failure
- progress summary
- ambiguous user-message routing

Each eval checks:

- stable structured output shape: `agent`, `task`, `message`, `data`, `events`
- no hidden chain-of-thought, system prompt, developer prompt, or hidden reasoning leakage
- selected tool is allowlisted for the routed intent
- expected agent/task/data for the golden case

## Run

From the repo root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests\evals -v
```

To run alongside the focused backend tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
```

If the uv-managed virtualenv cannot launch in the sandbox on Windows, rerun with the same
command after granting permission for `.\.venv\Scripts\python.exe`.
