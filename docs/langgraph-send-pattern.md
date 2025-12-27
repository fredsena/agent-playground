# LangGraph Send Pattern: Dynamic Parallel Routing

## Overview

`Send` is a LangGraph primitive that enables **dynamic, parallel execution** of graph nodes. It's particularly powerful for implementing the **fan-out/fan-in pattern** in multi-agent systems where you need to route queries to different specialized agents based on runtime decisions.

## Import

```python
from langgraph.types import Send
```

## Basic Syntax

```python
Send(node_name: str, input_state: dict)
```

### Parameters

1. **`node_name`** (str): The name of the graph node to invoke
2. **`input_state`** (dict): The state dictionary to pass to that node

## How It Works

### Traditional Static Routing vs Dynamic Send

**Static Routing** (hardcoded):
```python
# Always calls the same nodes in the same order
.add_edge("classify", "github")
.add_edge("classify", "notion")
.add_edge("classify", "slack")
```

**Dynamic Routing** with `Send`:
```python
def route_to_agents(state: RouterState) -> list[Send]:
    """Fan out to agents based on classifications."""
    return [
        Send(c["source"], {"query": c["query"]})
        for c in state["classifications"]
    ]

# Only calls nodes that are relevant at runtime
.add_conditional_edges("classify", route_to_agents, ["github", "notion", "slack"])
```

## Real-World Example: Multi-Agent Knowledge Router

### Context

A system that routes user queries to specialized knowledge agents (GitHub, Notion, Slack) based on which sources are relevant.

### Code Breakdown

```python
from langgraph.types import Send

class Classification(TypedDict):
    """A single routing decision."""
    source: Literal["github", "notion", "slack"]
    query: str

class RouterState(TypedDict):
    query: str
    classifications: list[Classification]
    results: Annotated[list[AgentOutput], operator.add]
    final_answer: str

def route_to_agents(state: RouterState) -> list[Send]:
    """Fan out to agents based on classifications."""
    return [
        Send(c["source"], {"query": c["query"]})
        for c in state["classifications"]
    ]
```

### Step-by-Step Execution

1. **Classification Phase**
   ```python
   # Classifier determines which agents are relevant
   classifications = [
       {"source": "github", "query": "Search for API authentication code"},
       {"source": "notion", "query": "Find authentication documentation"}
   ]
   ```

2. **Dynamic Routing with Send**
   ```python
   # route_to_agents creates Send objects dynamically
   [
       Send("github", {"query": "Search for API authentication code"}),
       Send("notion", {"query": "Find authentication documentation"})
   ]
   ```

3. **Parallel Execution**
   - Both `github` and `notion` nodes execute simultaneously
   - `slack` node is NOT invoked (not in classifications)

4. **Convergence**
   - All invoked agents complete their work
   - Results flow to the `synthesize` node
   - Final answer is generated from combined results

## Key Benefits

### 1. **Dynamic Decision Making**
The number and type of nodes executed is determined at runtime, not hardcoded in the graph definition.

```python
# Different queries invoke different agents
query1 = "How to authenticate?" 
# → Might invoke: github, notion, slack

query2 = "What's our vacation policy?"
# → Might invoke: notion only
```

### 2. **Parallel Execution**
All `Send` invocations happen concurrently, dramatically improving performance.

```python
# Sequential (slow)
result1 = query_github(...)
result2 = query_notion(...)
result3 = query_slack(...)
# Total time: T1 + T2 + T3

# Parallel with Send (fast)
[Send("github", ...), Send("notion", ...), Send("slack", ...)]
# Total time: max(T1, T2, T3)
```

### 3. **Efficient Resource Usage**
Only relevant agents are invoked, saving computational resources and API calls.

### 4. **Targeted Sub-queries**
Each agent receives a specialized sub-query optimized for its knowledge domain.

```python
[
    Send("github", {"query": "Find authentication implementation in code"}),
    Send("notion", {"query": "Get setup instructions from docs"}),
    Send("slack", {"query": "Find team discussions about auth best practices"})
]
```

## Graph Configuration

### Setting Up Conditional Edges

```python
workflow = (
    StateGraph(RouterState)
    .add_node("classify", classify_query)
    .add_node("github", query_github)
    .add_node("notion", query_notion)
    .add_node("slack", query_slack)
    .add_node("synthesize", synthesize_results)
    .add_edge(START, "classify")
    # Key line: conditional edges with Send
    .add_conditional_edges(
        "classify",              # Source node
        route_to_agents,         # Function returning list[Send]
        ["github", "notion", "slack"]  # Possible target nodes
    )
    .add_edge("github", "synthesize")
    .add_edge("notion", "synthesize")
    .add_edge("slack", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)
```

## State Management

### Input State for Each Agent

Each node invoked via `Send` receives its own isolated input state:

```python
class AgentInput(TypedDict):
    """Simple input state for each subagent."""
    query: str

def query_github(state: AgentInput) -> dict:
    """Query the GitHub agent."""
    # Receives only: {"query": "specific github query"}
    result = github_agent.invoke({
        "messages": [{"role": "user", "content": state["query"]}]
    })
    return {"results": [{"source": "github", "result": result["messages"][-1].content}]}
```

### Aggregating Results

Results from all parallel agents are aggregated using the `operator.add` reducer:

```python
class RouterState(TypedDict):
    results: Annotated[list[AgentOutput], operator.add]  # Aggregates results
    # ↑ Each agent appends to this list
```

This means:
- GitHub agent returns: `{"results": [{"source": "github", "result": "..."}]}`
- Notion agent returns: `{"results": [{"source": "notion", "result": "..."}]}`
- Final state has: `{"results": [<github result>, <notion result>]}`

## Complete Flow Diagram

```
User Query
    ↓
[classify] ← Analyzes query, determines which agents to invoke
    ↓
route_to_agents() ← Returns list[Send]
    ↓
    ├─→ Send("github", {...}) ─→ [github agent] ─┐
    ├─→ Send("notion", {...}) ─→ [notion agent] ─┤
    └─→ Send("slack", {...})  ─→ [slack agent]  ─┤
                                                   ↓
                                              [synthesize] ← Combines all results
                                                   ↓
                                              Final Answer
```

## Common Patterns

### 1. Fan-out/Fan-in (Shown Above)
Route to multiple agents in parallel, then combine results.

### 2. Conditional Single Send
Route to exactly one agent based on classification.

```python
def route_to_specialist(state: State) -> list[Send]:
    """Route to single most relevant specialist."""
    specialist = determine_best_specialist(state["query"])
    return [Send(specialist, {"query": state["query"]})]
```

### 3. Hierarchical Routing
First-level routing that triggers second-level routing.

```python
def route_to_regions(state: State) -> list[Send]:
    """Route to regional agents, which then route to local agents."""
    return [
        Send(f"region_{region}", {"query": state["query"]})
        for region in state["target_regions"]
    ]
```

## Best Practices

### ✅ Do

- Use `Send` when the routing decision is based on runtime data
- Return empty list `[]` if no nodes should be invoked
- Keep input states minimal and focused
- Use type hints for clarity

### ❌ Don't

- Don't use `Send` for static, always-executed paths (use `add_edge` instead)
- Don't pass the entire graph state if nodes only need a subset
- Don't forget to handle empty classification cases

## Error Handling

```python
def route_to_agents(state: RouterState) -> list[Send]:
    """Fan out to agents based on classifications."""
    if not state.get("classifications"):
        # No classifications → no agents to invoke
        return []
    
    return [
        Send(c["source"], {"query": c["query"]})
        for c in state["classifications"]
        if c["source"] in ["github", "notion", "slack"]  # Validate sources
    ]
```

## Performance Considerations

### Parallel Execution Benefits

For N agents with average execution time T:
- **Sequential**: Total time ≈ N × T
- **Parallel with Send**: Total time ≈ T (assuming sufficient resources)

### Example Timing

```python
# Sequential execution
github_time = 2s
notion_time = 3s
slack_time = 2s
Total = 7s

# Parallel execution with Send
Total = max(2s, 3s, 2s) = 3s
Speedup: 2.3x
```

## Related Concepts

- **Conditional Edges**: The graph mechanism that enables dynamic routing
- **State Reducers**: How results from parallel executions are combined (`operator.add`)
- **Map-Reduce Pattern**: `Send` implements the "map" phase; aggregation implements "reduce"

## References

- [LangGraph Documentation](https://docs.langchain.com/oss/python/langchain/multi-agent/router-knowledge-base)
- Example: [`06.multi-agent-knowledge-router.py`]
- Related: Fan-out/Fan-in architectural pattern

## Summary

`Send` is a powerful primitive for building **flexible, efficient multi-agent systems**. It enables:

1. ✨ **Runtime-determined routing** - Decide which nodes to invoke based on actual data
2. ⚡ **Parallel execution** - Run multiple agents simultaneously for speed
3. 🎯 **Targeted processing** - Each agent gets optimized input for its specialty
4. 🔧 **Resource efficiency** - Only invoke the agents you actually need

Perfect for building intelligent routers, classification systems, and dynamic multi-agent workflows!
