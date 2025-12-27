"""
Deep Agent File System Assistant - Interactive Chat Bot

A comprehensive Deep Agent that demonstrates:
- Planning capabilities with TODO tracking
- File system tools for managing large context
- Subagent delegation for specialized tasks
- Persistent memory across conversations

Inspired by Claude Code, Deep Research, and Manus patterns.
Based on LangGraph and LangChain 1.0 architecture.
"""

import pathlib
import time
from datetime import datetime
from typing import Annotated, Literal, NotRequired

from langchain.agents import create_agent, AgentState
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool, InjectedToolCallId, BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from typing_extensions import TypedDict

# Rich library for beautiful terminal output
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.theme import Theme

# prompt_toolkit for cross-platform history support
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML

from utils.llm import get_llm

from utils.tools.filesystem import (
    list_files,
    read_file,    
    find_file,
    write_file,
    create_folder
)

# =============================================================================
# RICH CONSOLE SETUP
# =============================================================================

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "bot": "bold cyan",
    "user": "bold green"
})
console = Console(theme=custom_theme)


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class Todo(TypedDict):
    """A structured task item for tracking progress."""
    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(left, right):
    """Merge two file dictionaries, right side takes precedence."""
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return {**left, **right}


class DeepAgentState(AgentState):
    """Extended agent state with TODO tracking and virtual file system."""
    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]


# =============================================================================
# FILE SYSTEM TOOLS
# =============================================================================

@tool(
    "list_files_in_dir",
    parse_docstring=True,
    description=(
        "List all files and folders in a specified directory. "
        "Can filter by file extensions and search recursively."
    ),
)
def list_files_in_dir(
    folder_path: str,
    extensions: list[str] = None,
    recursive: bool = False,
    show_hidden: bool = False
) -> str:
    """List files in a directory with optional filtering.

    Args:
        folder_path (str): The path to the folder to list.
        extensions (list[str]): Optional list of extensions to filter (e.g., [".md", ".txt"]).
        recursive (bool): Whether to search subdirectories. Defaults to False.
        show_hidden (bool): Whether to show hidden files. Defaults to False.

    Returns:
        str: Formatted list of files found, or error message.
    """
    console.print(f"📁 Listing files in '[cyan]{folder_path}[/cyan]'", style="info")
    
    path = pathlib.Path(folder_path).expanduser().resolve()
    
    if not path.exists():
        return f"Error: Directory does not exist: {path}"
    
    if not path.is_dir():
        return f"Error: Path is not a directory: {path}"
    
    try:
        items = []
        iterator = path.rglob("*") if recursive else path.iterdir()
        
        for item in sorted(iterator):
            # Skip hidden files if not requested
            if not show_hidden and item.name.startswith('.'):
                continue
            
            # Skip directories when listing files
            if item.is_dir():
                continue
            
            # Filter by extension if specified
            if extensions:
                if item.suffix.lower() not in [ext.lower() for ext in extensions]:
                    continue
            
            items.append(str(item))
        
        if not items:
            return f"No files found in {path}" + (f" with extensions {extensions}" if extensions else "")
        
        result = f"Found {len(items)} file(s) in {path}:\n\n"
        for item in items:
            result += f"  📄 {item}\n"
        
        return result
    
    except PermissionError:
        return f"Error: Permission denied accessing {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool(
    "read_file_content",
    parse_docstring=True,
    description=(
        "Read the contents of a text file from disk. "
        "Automatically detects encoding and handles large files."
    ),
)
def read_file_content(
    file_path: str,
    max_chars: int = 5000
) -> str:
    """Read content from a file on disk.

    Args:
        file_path (str): The full path to the file to read.
        max_chars (int): Maximum number of characters to return. Defaults to 5000.

    Returns:
        str: The file contents (possibly truncated), or error message.
    """
    console.print(f"📄 Reading file: '[cyan]{file_path}[/cyan]'", style="info")
    
    path = pathlib.Path(file_path).expanduser().resolve()
    
    if not path.exists():
        return f"Error: File does not exist: {path}"
    
    if not path.is_file():
        return f"Error: Path is not a file: {path}"
    
    try:
        # Try UTF-8 first
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            return f"Error: Cannot read file encoding: {str(e)}"
    except Exception as e:
        return f"Error reading file: {str(e)}"
    
    if not content:
        return f"File is empty: {path}"
    
    # Truncate if too long
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... [truncated, showing first {max_chars} of {len(content)} characters]"
    
    return f"=== Content of {path.name} ===\n\n{content}"


@tool(
    "write_results_file",
    parse_docstring=True,
    description=(
        "Write content to a file on disk. Creates parent directories if needed. "
        "Use this to save summaries, results, or any output file."
    ),
)
def write_results_file(
    file_path: str,
    content: str,
    append: bool = False
) -> str:
    """Write content to a file on disk.

    Args:
        file_path (str): The path where the file should be created/written.
        content (str): The content to write to the file.
        append (bool): If True, append to existing file. Defaults to False.

    Returns:
        str: Success message with file path and size, or error message.
    """
    console.print(f"✍️  Writing to file: '[cyan]{file_path}[/cyan]'", style="info")
    
    path = pathlib.Path(file_path).expanduser().resolve()
    
    try:
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(content)
        
        file_size = path.stat().st_size
        action = "appended to" if append else "written to"
        
        return f"✅ Successfully {action} '{path}' ({file_size} bytes)"
    
    except PermissionError:
        return f"Error: Permission denied writing to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool(
    "find_files",
    parse_docstring=True,
    description=(
        "Search for files by name pattern (glob) across a directory tree. "
        "Returns full paths to matching files."
    ),
)
def find_files(
    pattern: str,
    search_dir: str = ".",
    recursive: bool = True
) -> str:
    """Find files by name pattern.

    Args:
        pattern (str): The file pattern to search for (e.g., "*.txt", "config.*", "README*").
        search_dir (str): Directory to search in. Defaults to current directory.
        recursive (bool): Whether to search subdirectories. Defaults to True.

    Returns:
        str: Comma-separated list of matching file paths, or message if none found.
    """
    console.print(f"🔍 Searching for '[cyan]{pattern}[/cyan]' in '[blue]{search_dir}[/blue]'", style="info")
    
    search_path = pathlib.Path(search_dir).expanduser().resolve()
    
    if not search_path.exists():
        return f"Error: Directory does not exist: {search_path}"
    
    if not search_path.is_dir():
        return f"Error: Path is not a directory: {search_path}"
    
    try:
        if recursive:
            matches = list(search_path.glob(f"**/{pattern}"))
        else:
            matches = list(search_path.glob(pattern))
        
        # Filter out directories
        matches = [m for m in matches if m.is_file()]
        
        if matches:
            file_paths = [str(m.resolve()) for m in matches]
            return f"Found {len(file_paths)} file(s):\n" + "\n".join(f"  📄 {p}" for p in file_paths)
        else:
            return f"No files found matching '{pattern}' in {search_path}"
    
    except Exception as e:
        return f"Error during search: {str(e)}"


# =============================================================================
# PLANNING TOOLS (TODO Management)
# =============================================================================

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


# =============================================================================
# SUBAGENT INFRASTRUCTURE
# =============================================================================

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
        state: Annotated[DeepAgentState, InjectedState],
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


# =============================================================================
# MAIN AGENT SETUP
# =============================================================================

# LLM Configuration
# llm = ChatOpenAI(
#     model="qwen/qwen3-4b-2507",
#     base_url="http://127.0.0.1:1234/v1",
#     temperature=0.0,
#     api_key="11111111111111"
# )

# LLM Configuration
llm = get_llm()

# Sub-agent tools (tools available to sub-agents)
subagent_tools = [read_file_content, think]

# Define specialized sub-agents
FILE_SEARCH_AGENT = {
    "name": "file-search-agent",
    "description": "Searches for files in directories. Use for finding files by pattern or extension.",
    "prompt": """You are a file search specialist. Your job is to find files based on user criteria.

Use the available tools to:
1. List files in directories with filtering
2. Search for files by pattern
3. Report back what you found

Be thorough but efficient. Always report the full paths of files found.""",
    "tools": ["find_files", "list_files_in_dir", "think"],
}

SUMMARIZATION_AGENT = {
    "name": "summarization-agent", 
    "description": "Reads files and creates concise summaries. Use for summarizing file contents.",
    "prompt": """You are a content summarization specialist. Your job is to read files and create clear, concise summaries.

For each file:
1. Read the file content using read_file_content
2. Analyze the content type (code, documentation, data, etc.)
3. Create a concise 2-3 sentence summary highlighting key points
4. Return a structured summary

Be concise but informative. Focus on what's most important in each file.""",
    "tools": ["read_file_content", "think"],
}

# Create task delegation tool
file_search_tools = [find_files, list_files_in_dir, think]
summarization_tools = [read_file_content, think]

task_tool = create_task_tool(
    file_search_tools + summarization_tools,
    [FILE_SEARCH_AGENT, SUMMARIZATION_AGENT],
    llm,
    DeepAgentState
)

# All tools available to main agent
all_tools = [
    list_files_in_dir,
    read_file_content,
    write_results_file,
    find_files,
    create_folder,
    write_todos,
    read_todos,
    think,
    task_tool,
]

# Main agent system prompt
DEEP_AGENT_INSTRUCTIONS = f"""You are a Deep Agent File System Assistant. Today's date is {datetime.now().strftime("%B %d, %Y")}.

You help users with file system tasks including:
- Searching and listing files
- Reading and summarizing file contents
- Creating summary reports
- Organizing and managing files

## Planning with TODOs

For complex multi-step tasks:
1. Use `write_todos` to create a plan at the start
2. After each step, use `read_todos` to check progress
3. Update TODO status as you complete each step
4. Use `think` to reflect on progress and plan next steps

## Sub-Agent Delegation

For specialized tasks, you can delegate to sub-agents:
- **file-search-agent**: For finding files by pattern or in directories
- **summarization-agent**: For reading and summarizing file contents

Delegate when tasks benefit from isolated focus. Each sub-agent has clean context.

## File Operations

- Use `list_files_in_dir` to see what's in a folder
- Use `find_files` to search by pattern (e.g., "*.md", "*.py")
- Use `read_file_content` to read file contents
- Use `write_results_file` to save results to disk

## Best Practices

1. Always create a TODO plan for multi-step tasks
2. Use `think` to reason through complex decisions
3. Delegate appropriately to sub-agents
4. Save final results to disk when requested
5. Be concise but helpful in responses
"""

# Create the main agent
agent = create_agent(
    model=llm,
    tools=all_tools,
    system_prompt=DEEP_AGENT_INSTRUCTIONS,
    state_schema=DeepAgentState,
    checkpointer=InMemorySaver(),
)


# =============================================================================
# INTERACTIVE CHAT LOOP
# =============================================================================

def main():
    """Run the interactive chat bot."""
    
    # Thread ID for conversation persistence
    thread_id = "deep_agent_session_1"
    
    # Display header
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🤖 Deep Agent File System Assistant[/bold cyan]\n\n"
        f"  • Powered by [green]{llm.model_name}[/green]\n"
        "[dim]A comprehensive Deep Agent with:[/dim]\n"
        "  • 📋 Planning with TODO tracking\n"
        "  • 📁 File system tools\n"
        "  • 🔀 Sub-agent delegation\n"
        "  • 💾 Persistent memory\n\n"
        "[dim]Example requests:[/dim]\n"
        '  • "List all .py files in ~/projects"\n'
        '  • "Find and summarize all markdown files in ./docs"\n'
        '  • "Search for config files and save a summary"\n\n'
        "[yellow]Type 'quit', 'exit', or 'bye' to end.[/yellow]",
        border_style="cyan",
        padding=(1, 2)
    ))
    console.print()
    
    # Initialize prompt session with history
    history_file = pathlib.Path.home() / ".deep_agent_history"
    session = PromptSession(history=FileHistory(str(history_file)))
    
    # Initial state
    initial_state = {"todos": [], "files": {}}
    
    # Chat loop
    while True:
        try:
            user_input = session.prompt(HTML('\n<ansigreen><b>You:</b></ansigreen> ')).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]👋 Goodbye![/yellow]")
            break
        
        # Check for exit
        if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
            console.print("\n[bold yellow]👋 Thanks for using Deep Agent! Goodbye![/bold yellow]")
            break
        
        # Skip empty input
        if not user_input:
            continue
        
        # Create message
        human_msg = HumanMessage(user_input)
        
        # Process with status indicator
        with console.status("[bold cyan]🤖 Processing...", spinner="dots"):
            try:
                result = agent.invoke(
                    {"messages": [human_msg], **initial_state},
                    config={"configurable": {"thread_id": thread_id}}
                )
            except Exception as e:
                console.print(f"\n[bold red]Error:[/bold red] {str(e)}")
                continue
        
        # Display response
        ai_response = result["messages"][-1].content
        console.print("\n[bold cyan]🤖 Bot:[/bold cyan]")
        console.print(Markdown(ai_response))
        
        # Update state for next iteration
        if "todos" in result:
            initial_state["todos"] = result["todos"]
        if "files" in result:
            initial_state["files"] = result["files"]
    
    console.print("\n")


if __name__ == "__main__":
    main()
