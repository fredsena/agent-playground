"""Utilities for creating and managing sub-agents."""
from typing import Annotated, NotRequired, TypedDict
from langchain.agents import create_agent
from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from .console import console

class SubAgent(TypedDict):
    """Configuration for a specialized sub-agent."""
    name: str
    description: str
    prompt: str
    tools: NotRequired[list[str]]

def create_task_tool(tools, subagents: list[SubAgent], model, state_schema):
    """Create a task delegation tool for context isolation through sub-agents."""
    
    agents = {}
    tools_by_name = {}
    
    for tool_ in tools:
        if not isinstance(tool_, BaseTool):
            tool_ = tool(tool_)
        tools_by_name[tool_.name] = tool_
    
    for _agent in subagents:
        if "tools" in _agent:
            _tools = [tools_by_name[t] for t in _agent["tools"] if t in tools_by_name]
        else:
            _tools = tools
        agents[_agent["name"]] = create_agent(
            model, 
            system_prompt=_agent["prompt"], 
            tools=_tools, 
            state_schema=state_schema
        )
    
    other_agents_string = [f"- {a['name']}: {a['description']}" for a in subagents]
    
    @tool(description=f"Delegate a task to a specialized sub-agent. Available agents:\n" + "\n".join(other_agents_string))
    def task(
        description: str,
        subagent_type: str,
        state: Annotated[state_schema, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ):
        """Delegate a task to a sub-agent with isolated context.
        
        Args:
            description: Clear description of the task to perform.
            subagent_type: Name of the sub-agent to use.
        """
        if subagent_type not in agents:
            return f"Error: Unknown agent type '{subagent_type}'. Available: {list(agents.keys())}"
        
        console.print(f"🤖 Delegating to [cyan]{subagent_type}[/cyan]: {description[:50]}...", style="info")
        
        sub_agent = agents[subagent_type]
        
        # Create isolated context
        isolated_state = dict(state)
        isolated_state["messages"] = [{"role": "user", "content": description}]
        
        result = sub_agent.invoke(isolated_state)
        
        return Command(
            update={
                "files": result.get("files", {}),
                "messages": [
                    ToolMessage(
                        result["messages"][-1].content, 
                        tool_call_id=tool_call_id
                    )
                ],
            }
        )
    
    return task
