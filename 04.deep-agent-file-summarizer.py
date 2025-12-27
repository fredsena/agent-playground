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
from datetime import datetime
from typing import Annotated

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import InjectedState

# Rich library for beautiful terminal output
from rich.panel import Panel
from rich.markdown import Markdown

# prompt_toolkit for cross-platform history support
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML

# Import shared modules
from utils.llm import get_llm
from utils.state import DeepAgentState
from utils.subagents import create_task_tool
from utils.console import console
from utils.prompts import (
    FILE_SEARCH_AGENT_PROMPT, 
    SUMMARIZATION_AGENT_PROMPT, 
    get_deep_agent_instructions
)

from utils.tools.filesystem import (
    list_files,
    read_file,    
    find_file,
    write_file,
    create_folder
)

from utils.tools.websearchtools import (
    web_hybrid_search,
)

# Import shared tools
from utils.tools.filesystem import (
    list_files_in_dir,
    read_file_content,
    write_results_file,
    find_files
)
from utils.tools.planning import (
    write_todos,
    read_todos,
    think
)

# =============================================================================
# MAIN AGENT SETUP
# =============================================================================

# LLM Configuration
llm = get_llm()

# Define specialized sub-agents
FILE_SEARCH_AGENT = {
    "name": "file-search-agent",
    "description": "Searches for files in directories. Use for finding files by pattern or extension.",
    "prompt": FILE_SEARCH_AGENT_PROMPT,
    "tools": ["find_files", "list_files_in_dir", "think"],
}

SUMMARIZATION_AGENT = {
    "name": "summarization-agent", 
    "description": "Reads files and creates concise summaries. Use for summarizing file contents.",
    "prompt": SUMMARIZATION_AGENT_PROMPT,
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
    web_hybrid_search,
    think,
    task_tool,
]

# Create the main agent
agent = create_agent(
    model=llm,
    tools=all_tools,
    system_prompt=get_deep_agent_instructions(),
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
