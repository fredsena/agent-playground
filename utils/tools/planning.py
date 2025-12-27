"""Planning tools for task breakdown and thinking."""
from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from ..console import console

from ..state import DeepAgentState

@tool(
    "write_todos",
    parse_docstring=True,
    description=(
        "Create or update a TODO list for tracking progress through complex tasks. "
        "Use this at the start of multi-step workflows to plan your approach."
    ),
)
def write_todos(
    todos: list[dict],
    state: Annotated[DeepAgentState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Update the TODO list in agent state.

    Args:
        todos (list[dict]): List of TODO items with 'content' (str) and 'status' (pending/in_progress/completed) fields.
        state: Agent state (injected).
        tool_call_id: Tool call ID (injected).

    Returns:
        Command to update state with new TODOs.
    """
    console.print("📋 Updating TODO list", style="info")
    
    # Format TODOs for display
    todo_display = []
    for todo in todos:
        status_icon = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅"
        }.get(todo.get("status", "pending"), "❓")
        todo_display.append(f"  {status_icon} {todo.get('content', 'Unnamed task')}")
    
    console.print("\n".join(todo_display))
    
    return Command(
        update={
            "todos": todos,
            "messages": [
                ToolMessage(
                    f"TODO list updated with {len(todos)} items",
                    tool_call_id=tool_call_id
                )
            ],
        }
    )


@tool(
    "read_todos",
    parse_docstring=True,
    description="Read the current TODO list to check progress and decide next steps.",
)
def read_todos(
    state: Annotated[DeepAgentState, InjectedState],
) -> str:
    """Read current TODOs from state.

    Args:
        state: Agent state (injected).

    Returns:
        str: Formatted TODO list.
    """
    todos = state.get("todos", [])
    
    if not todos:
        return "No TODOs currently set."
    
    result = "Current TODO list:\n"
    for i, todo in enumerate(todos, 1):
        status = todo.get("status", "pending")
        status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(status, "❓")
        result += f"  {i}. {status_icon} [{status}] {todo.get('content', 'Unnamed')}\n"
    
    return result


@tool(
    "think",
    parse_docstring=True,
    description=(
        "Use this tool to reflect on your progress, plan next steps, or reason through "
        "complex decisions. This helps with strategic planning and task decomposition."
    ),
)
def think(reflection: str) -> str:
    """Reflect and plan during task execution.

    Args:
        reflection (str): Your thoughts, analysis, or planning notes.

    Returns:
        str: Confirmation that reflection was recorded.
    """
    console.print(f"💭 [dim]{reflection[:100]}...[/dim]" if len(reflection) > 100 else f"💭 [dim]{reflection}[/dim]")
    return f"Reflection noted. Continue with your plan."
