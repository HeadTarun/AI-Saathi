# 🧰 Agent-Service-Toolkit — Complete Deep Dive & Hackathon Guide

> Codebase: `agent-service-toolkit-main`  
> Stack: **LangGraph + FastAPI + Streamlit + Pydantic**

---

## Step 1 — Architecture Overview

### Folder Map

```
agent-service-toolkit-main/
├── src/
│   ├── agents/          ← 🧠 All agent logic lives here
│   │   ├── agents.py    ← Registry: maps name → agent graph
│   │   ├── tools.py     ← Shared tool definitions
│   │   ├── research_assistant.py  ← ReAct-style agent (KEY EXAMPLE)
│   │   ├── chatbot.py             ← Simplest agent (@entrypoint style)
│   │   ├── interrupt_agent.py     ← Human-in-the-loop agent
│   │   ├── langgraph_supervisor_agent.py ← Multi-agent supervisor
│   │   └── ...
│   ├── core/
│   │   ├── llm.py       ← get_model() factory (all providers)
│   │   └── settings.py  ← Pydantic settings from .env
│   ├── schema/
│   │   ├── models.py    ← All LLM model enums (OpenAI, Groq, etc.)
│   │   └── schema.py    ← API types: UserInput, ChatMessage, etc.
│   ├── service/
│   │   └── service.py   ← FastAPI app: /invoke, /stream, /info endpoints
│   ├── memory/
│   │   ├── __init__.py  ← initialize_database() + initialize_store()
│   │   ├── sqlite.py    ← Default checkpointer (SQLite)
│   │   └── postgres.py  ← Production checkpointer
│   ├── client/          ← AgentClient for talking to the service
│   ├── streamlit_app.py ← Chat UI
│   ├── run_service.py   ← Entry point: starts FastAPI
│   └── run_client.py    ← CLI client demo
└── tests/
```

### How Data Flows Through the System

```
User (browser/CLI)
      │
      ▼
[Streamlit App]  ←──── uses ────►  [AgentClient]
      │                                  │
      ▼                                  ▼
[FastAPI Service]  /invoke or /stream endpoint
      │
      ├── _handle_input()         ← builds RunnableConfig + thread_id
      │
      ├── get_agent(agent_id)     ← fetches compiled graph from registry
      │
      ├── agent.ainvoke(...)      ← runs the LangGraph state machine
      │   or agent.astream(...)   ← streams tokens + messages
      │
      └── langchain_to_chat_message() → returns ChatMessage JSON
```

### The Three Layers

| Layer | What it does | Key file |
|---|---|---|
| **Agent Layer** | Business logic, tools, reasoning loops | `src/agents/` |
| **Service Layer** | HTTP API, auth, streaming, memory init | `src/service/service.py` |
| **Client/UI Layer** | Talks to service, renders chat | `src/streamlit_app.py` |

---

## Step 2 — How Agents Are Currently Implemented

### Pattern A: `StateGraph` (Most powerful — ReAct style)

Used by: `research_assistant.py`, `interrupt_agent.py`

```
StateGraph → add_node() → add_edge() / add_conditional_edges() → compile()
```

Every node is an **async function** that takes `(state, config)` and returns a partial state update.

### Pattern B: `@entrypoint` decorator (Simplest)

Used by: `chatbot.py`

```python
@entrypoint()
async def chatbot(inputs, *, previous, config):
    ...
    return entrypoint.final(value=..., save=...)
```

No explicit graph — just a function. Great for simple Q&A agents.

### Pattern C: `langgraph-supervisor` (Multi-agent)

Used by: `langgraph_supervisor_agent.py`

```python
workflow = create_supervisor([agent_a, agent_b], model=model, prompt="...")
langgraph_supervisor_agent = workflow.compile()
```

A supervisor LLM decides which sub-agent to route to.

### The Agent Registry (`agents.py`)

```python
agents: dict[str, Agent] = {
    "research-assistant": Agent(
        description="...",
        graph_like=research_assistant,  # the compiled graph
    ),
    ...
}
```

This is the **single registration point**. Add your agent here and it automatically gets:
- An HTTP endpoint `/your-agent-name/invoke` and `/your-agent-name/stream`
- A listing in `/info`
- Memory (checkpointer + store) injected at startup

### How Tools Work

Tools are registered via `model.bind_tools(tools)` in `wrap_model()`:

```python
def wrap_model(model):
    bound_model = model.bind_tools(tools)   # ← tool registration
    preprocessor = RunnableLambda(
        lambda state: [SystemMessage(content=instructions)] + state["messages"]
    )
    return preprocessor | bound_model
```

LangGraph's `ToolNode` handles executing the actual tool call:

```python
agent.add_node("tools", ToolNode(tools))
```

The LLM's response contains `tool_calls` → `ToolNode` executes them → result is added to messages → LLM sees the result and continues.

---

## Step 3 — The ReAct Pattern (Already Built In!)

### Is ReAct already implemented? **YES.**

`research_assistant.py` is a textbook ReAct agent. Here's the loop:

```
┌─────────────────────────────────────────────────────┐
│                   ReAct Loop                        │
│                                                     │
│  [guard_input] ──safe──► [model node]               │
│                              │                      │
│         ┌────────────────────┘                      │
│         │                                           │
│         ▼                                           │
│  has tool_calls?                                    │
│    YES ──► [tools node] ──► back to [model node]    │
│    NO  ──► END                                      │
└─────────────────────────────────────────────────────┘
```

### The exact code (annotated):

```python
# research_assistant.py

# THOUGHT: The LLM generates a response (possibly with tool calls)
async def acall_model(state, config):
    model_runnable = wrap_model(get_model(...))
    response = await model_runnable.ainvoke(state, config)  # THINK
    return {"messages": [response]}

# ACTION: ToolNode executes whatever tool the LLM asked for
agent.add_node("tools", ToolNode(tools))   # ACT

# OBSERVE: Result is added to messages state automatically
# The next acall_model() call sees the tool result → OBSERVATION

# ROUTING LOGIC (Reason → Act → Observe → Repeat or Stop)
def pending_tool_calls(state) -> Literal["tools", "done"]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"   # → ACT
    return "done"        # → END

agent.add_conditional_edges("model", pending_tool_calls, {"tools": "tools", "done": END})
agent.add_edge("tools", "model")  # OBSERVE → back to REASON
```

This is the **full ReAct loop** implemented natively in LangGraph.

---

## Step 4 — How to Add a Custom Agent (Step-by-Step)

### Step 4.1: Create the agent file

Create `src/agents/my_react_agent.py`:

```python
# src/agents/my_react_agent.py
from typing import Literal
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import ToolNode
from langchain_core.language_models.chat_models import BaseChatModel

from core import get_model, settings

# ── 1. Define State ────────────────────────────────────────────────────────────
class AgentState(MessagesState, total=False):
    remaining_steps: RemainingSteps  # prevents infinite loops

# ── 2. Define Tools ────────────────────────────────────────────────────────────
from langchain_core.tools import tool

@tool
def get_stock_price(ticker: str) -> str:
    """Get the current stock price for a given ticker symbol."""
    # Replace with real API call for hackathon
    prices = {"AAPL": "$189.50", "GOOGL": "$175.20", "MSFT": "$420.10"}
    return prices.get(ticker.upper(), f"Price not found for {ticker}")

@tool
def summarize_news(topic: str) -> str:
    """Get a summary of recent news for a given topic."""
    return f"Latest news on {topic}: Markets are showing positive trends today."

tools = [get_stock_price, summarize_news]

# ── 3. Bind Tools to Model ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a financial research assistant.
Use your tools to look up stock prices and news before answering.
Always cite the tools you used."""

def wrap_model(model: BaseChatModel) -> RunnableSerializable:
    bound = model.bind_tools(tools)
    preprocessor = RunnableLambda(
        lambda state: [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    )
    return preprocessor | bound

# ── 4. Define Node Functions ───────────────────────────────────────────────────
async def call_model(state: AgentState, config: RunnableConfig) -> AgentState:
    model = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    runnable = wrap_model(model)
    response = await runnable.ainvoke(state, config)

    # Safety: stop if too many steps remain
    if state["remaining_steps"] < 2 and response.tool_calls:
        return {"messages": [AIMessage(id=response.id, content="Need more steps.")]}
    return {"messages": [response]}

# ── 5. Build the Graph ─────────────────────────────────────────────────────────
def should_use_tools(state: AgentState) -> Literal["tools", "done"]:
    last = state["messages"][-1]
    if not isinstance(last, AIMessage):
        raise TypeError(f"Expected AIMessage, got {type(last)}")
    return "tools" if last.tool_calls else "done"

graph = StateGraph(AgentState)
graph.add_node("model", call_model)
graph.add_node("tools", ToolNode(tools))

graph.set_entry_point("model")
graph.add_conditional_edges("model", should_use_tools, {"tools": "tools", "done": END})
graph.add_edge("tools", "model")

# ── 6. Compile ────────────────────────────────────────────────────────────────
my_react_agent = graph.compile()
my_react_agent.name = "my-react-agent"  # optional but good practice
```

### Step 4.2: Register in the agent registry

Open `src/agents/agents.py` and add **two lines**:

```python
# Add this import at the top (line ~16)
from agents.my_react_agent import my_react_agent

# Add this entry to the agents dict (around line 34)
agents: dict[str, Agent] = {
    # ... existing agents ...
    "my-react-agent": Agent(
        description="A financial research assistant with stock prices and news.",
        graph_like=my_react_agent,
    ),
}
```

**That's it.** Your agent is now live at:
- `POST /my-react-agent/invoke`
- `POST /my-react-agent/stream`
- Listed in `GET /info`

### Why each step matters

| Step | Why needed | What breaks if skipped |
|---|---|---|
| `AgentState(MessagesState)` | LangGraph needs typed state | Runtime errors on state access |
| `model.bind_tools(tools)` | Tells LLM what tools are available | LLM can't call any tools |
| `ToolNode(tools)` | Executes the tool calls | Tool calls are ignored |
| `add_conditional_edges` | Routes between reason and act | Infinite loop or immediate stop |
| `graph.compile()` | Finalizes the graph | Can't be run at all |
| Register in `agents.py` | Service discovery | Agent not reachable via HTTP |

---

## Step 5 — Adding New Tools

### Method 1: `@tool` decorator (Recommended for hackathons)

```python
from langchain_core.tools import tool

@tool
def fetch_weather(city: str) -> str:
    """Fetches the current weather for a city.
    
    Args:
        city: The name of the city to get weather for.
    
    Returns:
        A string describing current weather conditions.
    """
    # Call a real weather API here
    return f"It is sunny and 25°C in {city}."
```

> **The docstring IS the tool description.** LangGraph sends it to the LLM to explain when to use this tool. Write it well!

### Method 2: `tool()` function wrapping (like in `tools.py`)

```python
from langchain_core.tools import BaseTool, tool

def my_tool_func(query: str) -> str:
    """Does something useful with the query."""
    return f"Result for {query}"

my_tool: BaseTool = tool(my_tool_func)
my_tool.name = "MyTool"  # override the name shown to LLM
```

### Method 3: MCP Tools (external tool servers)

The repo already supports this in `github_mcp_agent/`. You can connect any MCP server.

### Connecting a Tool to Your Agent

```python
# In your agent file:
tools = [fetch_weather, get_stock_price, calculator]

def wrap_model(model):
    bound = model.bind_tools(tools)   # ← list all tools here
    ...

graph.add_node("tools", ToolNode(tools))  # ← same list here
```

### When to use tools vs direct LLM responses

| Use **Tools** when | Use **Direct LLM** when |
|---|---|
| Need real-time / dynamic data | Answering from training knowledge |
| Need to compute something | Summarizing, classifying, generating text |
| Need external APIs | Creative writing, Q&A |
| Need to read/write files/DBs | Explaining concepts |

### How tool invocation works internally

```
LLM response → has tool_calls? → YES
      ↓
ToolNode sees: {"name": "get_stock_price", "args": {"ticker": "AAPL"}}
      ↓
Calls: get_stock_price("AAPL")  → "$189.50"
      ↓
Adds ToolMessage(content="$189.50", tool_call_id=...) to state["messages"]
      ↓
Next model call SEES the ToolMessage as OBSERVATION
      ↓
LLM generates final answer using the tool result
```

---

## Step 6 — Memory & Persistence (Free Feature!)

Every agent automatically gets **two types of memory** injected at startup by the service:

### Short-term: Checkpointer (conversation history)

```python
# service.py (lifespan)
agent.checkpointer = saver   # SQLite by default
```

Users pass `thread_id` in requests → conversation is persisted per thread.

### Long-term: Store (cross-session data)

```python
# In an agent node function:
async def my_node(state, config, store: BaseStore):
    user_id = config["configurable"].get("user_id")
    namespace = (user_id,)
    
    # READ
    item = await store.aget(namespace, key="preferences")
    
    # WRITE
    await store.aput(namespace, "preferences", {"theme": "dark"})
```

See `interrupt_agent.py` for a full working example of using the store.

---

## Step 7 — Hackathon Strategy

### ✅ Reuse As-Is (Don't Touch)

| Component | Why safe to reuse |
|---|---|
| `src/service/service.py` | Complete HTTP API, auth, streaming — production quality |
| `src/core/llm.py` | All LLM providers wired, just call `get_model()` |
| `src/core/settings.py` | Settings from `.env` — just add your keys |
| `src/memory/` | Checkpointing + store — injected automatically |
| `src/client/client.py` | Python client for your own apps |
| `src/schema/schema.py` | All request/response types |

### ⚠️ Only Modify What's Needed

| File | When to modify |
|---|---|
| `src/agents/agents.py` | Add your agent to registry (2 lines) |
| `src/schema/models.py` | Only if adding a new LLM provider |
| `src/streamlit_app.py` | Only if you need UI customization |
| `.env` | Add your API keys |

### 🆕 Create New Files For Your Work

- `src/agents/your_agent.py` — your agent logic
- `src/agents/your_tools.py` — your custom tools

### Quickest Prototype Path

1. Copy `research_assistant.py` → `my_agent.py`
2. Replace `tools = [web_search, calculator]` with your tools
3. Update the system prompt (`instructions`)
4. Register in `agents.py`
5. Run `python src/run_service.py`
6. Test with `curl` or the Streamlit UI

---

## Step 8 — Full End-to-End Example

Here is a complete, working **"Hackathon News Agent"** that:
- Uses a custom tool
- Runs a full ReAct loop
- Is wired into the service

### File: `src/agents/hackathon_agent.py`

```python
"""
Hackathon Demo Agent — ReAct pattern with a custom tool.
"""
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import tool
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import ToolNode

from core import get_model, settings


# ─── STATE ────────────────────────────────────────────────────────────────────

class AgentState(MessagesState, total=False):
    remaining_steps: RemainingSteps


# ─── TOOLS ────────────────────────────────────────────────────────────────────

@tool
def search_hackathon_projects(category: str) -> str:
    """Search for hackathon project ideas in a given category.
    
    Args:
        category: The domain to search (e.g., 'health', 'finance', 'education')
    
    Returns:
        A list of project ideas with descriptions.
    """
    ideas = {
        "health": "1. AI symptom checker\n2. Mental health chatbot\n3. Medication reminder",
        "finance": "1. Expense tracker with AI insights\n2. Budget planner\n3. Fraud detector",
        "education": "1. Personalized tutor\n2. Quiz generator\n3. Study schedule optimizer",
    }
    return ideas.get(category.lower(), f"No ideas found for category: {category}")


@tool
def evaluate_project_feasibility(project_name: str, hours_available: int) -> str:
    """Evaluate if a project can be built in the given hours.
    
    Args:
        project_name: Name of the proposed project
        hours_available: Number of hours for the hackathon
    
    Returns:
        Feasibility assessment with recommendations.
    """
    if hours_available < 12:
        return f"'{project_name}' is HIGH RISK in {hours_available}h. Simplify scope significantly."
    elif hours_available < 24:
        return f"'{project_name}' is FEASIBLE in {hours_available}h. Focus on core MVP only."
    else:
        return f"'{project_name}' is COMFORTABLE in {hours_available}h. Can add extra features."


tools = [search_hackathon_projects, evaluate_project_feasibility]


# ─── MODEL SETUP ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a hackathon project advisor.
Your job is to help teams pick the right project idea and plan their time.

ALWAYS use your tools before giving recommendations:
1. First search for project ideas in the relevant category
2. Then evaluate the feasibility of promising ideas
3. Finally give a concrete recommendation

Be encouraging but realistic about what can be built in limited time."""


def wrap_model(model):
    bound = model.bind_tools(tools)
    preprocessor = RunnableLambda(
        lambda state: [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"],
        name="StateModifier",
    )
    return preprocessor | bound


# ─── NODES ────────────────────────────────────────────────────────────────────

async def call_model(state: AgentState, config: RunnableConfig) -> AgentState:
    """REASON step: LLM thinks and optionally requests a tool."""
    model = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    runnable = wrap_model(model)
    response = await runnable.ainvoke(state, config)

    # Safety valve: prevent infinite tool loops
    if state["remaining_steps"] < 2 and response.tool_calls:
        return {
            "messages": [AIMessage(id=response.id, content="Ran out of steps. Here's what I know so far.")]
        }
    return {"messages": [response]}


def should_use_tools(state: AgentState) -> Literal["tools", "done"]:
    """Router: ACT if there are tool calls, otherwise END."""
    last = state["messages"][-1]
    if not isinstance(last, AIMessage):
        raise TypeError(f"Expected AIMessage, got {type(last)}")
    return "tools" if last.tool_calls else "done"


# ─── GRAPH ────────────────────────────────────────────────────────────────────
#
#  Entry → [call_model] → has tool_calls?
#                              YES → [ToolNode] → back to [call_model]
#                              NO  → END
#
# This IS the ReAct loop:
#   call_model  = THOUGHT + REASON
#   ToolNode    = ACTION
#   tool result = OBSERVATION (auto-added to messages)

graph = StateGraph(AgentState)
graph.add_node("model", call_model)
graph.add_node("tools", ToolNode(tools))

graph.set_entry_point("model")
graph.add_conditional_edges("model", should_use_tools, {"tools": "tools", "done": END})
graph.add_edge("tools", "model")

hackathon_agent = graph.compile()
hackathon_agent.name = "hackathon-agent"
```

### Register it — Edit `src/agents/agents.py`

```python
# Add import
from agents.hackathon_agent import hackathon_agent

# Add to dict
agents: dict[str, Agent] = {
    # ... existing agents ...
    "hackathon-agent": Agent(
        description="A hackathon project advisor with feasibility evaluation.",
        graph_like=hackathon_agent,
    ),
}
```

### Test it with curl

```bash
# Non-streaming
curl -X POST http://localhost:8080/hackathon-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "I have 24 hours, interested in health tech. What should I build?"}'

# Streaming (see tokens live)
curl -X POST http://localhost:8080/hackathon-agent/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "I have 24 hours, interested in health tech. What should I build?", "stream_tokens": true}'
```

### What the ReAct loop looks like at runtime

```
User: "I have 24 hours, interested in health tech. What should I build?"

THOUGHT (call_model):
  "I should search for health category projects first."
  → tool_calls: [search_hackathon_projects(category="health")]

ACTION (ToolNode):
  → executes search_hackathon_projects("health")
  → returns "1. AI symptom checker\n2. Mental health chatbot\n3. Medication reminder"

OBSERVATION (auto-added to messages as ToolMessage):
  "1. AI symptom checker\n2. Mental health chatbot\n3. Medication reminder"

THOUGHT (call_model again):
  "Let me check if 'AI symptom checker' is feasible in 24 hours."
  → tool_calls: [evaluate_project_feasibility(project_name="AI symptom checker", hours_available=24)]

ACTION (ToolNode):
  → "'AI symptom checker' is COMFORTABLE in 24h. Can add extra features."

OBSERVATION (added to messages)

THOUGHT (call_model again):
  No more tool calls needed.
  → Generates final answer synthesizing both observations.

DONE → Returns to user.
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│              ADDING A NEW AGENT: 2 FILES                    │
│                                                             │
│  1. src/agents/my_agent.py                                  │
│     - Define AgentState(MessagesState)                      │
│     - Define @tool functions                                │
│     - bind_tools() in wrap_model()                          │
│     - Build StateGraph with model + tools nodes             │
│     - Add conditional_edges for ReAct loop                  │
│     - my_agent = graph.compile()                            │
│                                                             │
│  2. src/agents/agents.py                                    │
│     - from agents.my_agent import my_agent                  │
│     - "my-agent": Agent(description="...", graph_like=...)  │
│                                                             │
│  Result: /my-agent/invoke and /my-agent/stream are LIVE    │
└─────────────────────────────────────────────────────────────┘

get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
  ↑ Always use this to get the LLM — handles all providers automatically

ToolNode(tools)
  ↑ Always use this — handles tool execution + error handling

state["remaining_steps"] < 2
  ↑ Always add this guard — prevents infinite loops
```
