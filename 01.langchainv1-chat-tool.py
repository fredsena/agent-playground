import os
import pathlib
import re
import time

import requests
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain.agents import create_agent

from langchain.agents.middleware import PIIMiddleware, SummarizationMiddleware

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver, InMemorySaver
from typing import Literal
from langchain.tools import tool

from typing_extensions import NotRequired

from langchain.tools.tool_node import ToolCallRequest
from langchain.messages import ToolMessage
from langgraph.types import Command
from typing import Callable

from langchain.agents.middleware import wrap_tool_call

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langgraph.runtime import Runtime
from typing import Any, Callable

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.status import Status
from rich.syntax import Syntax
from rich.theme import Theme

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML

from utils.llm import get_llm
from utils.tools.filesystem import (
    list_files,
    read_file,    
    find_file,
    write_file,
    create_folder,    
    search_text_patterns,
)

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

from utils.tools.get_web_links import get_web_links
from utils.tools.get_web_data import get_web_data
from utils.tools.git_tools import git_command, git_status
from utils.tools.memory import clear_memory, set_memory_references, clear_all_memory


# Initialize Rich console with custom theme
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "bot": "bold cyan",
    "user": "bold green"
})
console = Console(theme=custom_theme)

llm = get_llm()

# Create checkpointer instance so we can reference it for clearing memory
checkpointer = InMemorySaver()

# IMPORTANT: When the clear_memory tool is used, you MUST:
# 1. Treat everything as a completely NEW conversation
# 2. Do NOT reference any prior information, names, topics, or context
# 3. Respond as if meeting the user for the very first time
# 4. Never say things like "Hello again" or use any previously mentioned names

SYSTEM_PROMPT = """You are a helpful assistant."""

agent = create_agent(
    system_prompt=SYSTEM_PROMPT,
    model=llm,
    checkpointer=checkpointer,
    tools=[get_web_links, get_web_data, 
            find_file,read_file,write_file,
            list_files,create_folder,
            git_command, git_status,
            search_text_patterns,
            clear_memory,  # Tool for AI to clear memory when asked
        ],
)

# Set memory references so the clear_memory tool can access the checkpointer
set_memory_references(checkpointer, "conversation_1")

thread_id = "conversation_1"

console.print()

console.print(Panel.fit(
    "[bold cyan]🤖 AI Assistant Chat Bot[/bold cyan]\n\n"
    "[dim]Features:[/dim]\n"
    f"  • Powered by [green]{llm.model_name}[/green]\n"
    "  • Terminal-like typing effects\n"
    "  • File operations (find, read, write)\n"
    "  • Web link search\n"
    "  • Conversation history\n\n"
    "[yellow]Commands:[/yellow]\n"
    "  • [cyan]/clear[/cyan] - Clear all memory and start fresh\n"
    "  • [cyan]quit/exit/bye[/cyan] - End conversation",
    border_style="cyan",
    padding=(1, 2)
))
console.print()

# Initialize prompt session with persistent history file inside the project folder
project_root = pathlib.Path(__file__).parent.resolve()
history_file = project_root / ".chat_history"
history_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
session = PromptSession(history=FileHistory(str(history_file)))

# Chat loop
while True:
    # Get user input with prompt_toolkit (supports arrow up/down history)
    try:
        user_input = session.prompt(HTML('\n<ansigreen><b>You:</b></ansigreen> ')).strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]👋 Goodbye![/yellow]")
        break
    
    # Check for exit commands
    if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
        console.print("\n[bold yellow]👋 Thanks for chatting! Goodbye![/bold yellow]")
        break
    
    # Check for /clear command to clear memory
    if user_input.lower() == '/clear':
        result = clear_all_memory()
        console.print()
        console.rule("[bold magenta]🧹 Memory Cleared[/bold magenta]", style="magenta")
        console.print("[bold green]✅ All conversation context has been erased![/bold green]")
        console.print("[dim]Starting fresh - the AI will not remember anything from before.[/dim]")
        console.rule(style="magenta")
        console.print()
        continue
    
    # Skip empty inputs
    if not user_input:
        continue
    
    # Create human message
    human_msg = HumanMessage(user_input)
    
    # Show status while AI is thinking
    with console.status("[bold cyan]🤖 Thinking...", spinner="dots"):
        # Invoke agent with thread configuration to maintain history
        result = agent.invoke(
            {"messages": [human_msg]},
            config={"configurable": {"thread_id": thread_id}}
        )
    
    # Get and display the AI's response with typing effect
    ai_response = result["messages"][-1].content
    console.print("\n[bold cyan]🤖 Bot:[/bold cyan] ", end="")    
    console.print(Markdown(ai_response))

console.print("\n")
