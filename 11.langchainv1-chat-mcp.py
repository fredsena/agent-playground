import pathlib
import re
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

from langgraph.checkpoint.memory import MemorySaver, InMemorySaver
from langchain_core.tools import tool
from utils.llm import get_llm

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain.agents import create_agent

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Rich library for beautiful terminal output
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from rich.live import Live
from rich.table import Table
from langchain_community.utilities import SQLDatabase
from langchain.agents import AgentState
from langchain.tools import ToolRuntime
from langchain.messages import HumanMessage, ToolMessage
from langgraph.types import Command
from langchain.agents import create_agent

# prompt_toolkit for input history
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML

from utils.tools.filesystem import (
    # list_files,
    # read_file,    
    # find_file,
    write_file,
    # create_folder,    
    # search_text_patterns,
)

# Memory utilities for /clear command
from utils.tools.memory import clear_memory, set_memory_references, clear_all_memory

load_dotenv()

async def main():
    # Get today's date for the system prompt
    today = datetime.now()

    # Connect to MCP servers
    mcp_client = MultiServerMCPClient(
        {
            # "time": {
            #     "transport": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@theo.foobar/mcp-time"],
            # },
            # "msdocs": {
            #     "transport": "streamable_http",            
            #     "url": "https://learn.microsoft.com/api/mcp",
            # },
            # "langchaindocs": {
            #     "transport": "streamable_http",            
            #     "url": "https://docs.langchain.com/mcp",
            # },
            # "travel_server": {
            #     "transport": "streamable_http",
            #     "url": "https://mcp.kiwi.com"
            # },
            "ai-context": {
                "transport": "stdio",
                "command": "npx",
                "args": ["@ai-coders/context@latest", "mcp"],
            },            
        },
    )

    # Load tools from the MCP servers
    mcp_tools = await mcp_client.get_tools()
    print(f"Loaded {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}\n")

    llm = get_llm()

    # Create checkpointer instance so we can reference it for clearing memory
    checkpointer = InMemorySaver()

    agent = create_agent(
        system_prompt=f"You are a helpful assistant. IMPORTANT GUIDELINES FOR DATE-SENSITIVE OPERATIONS: - Today's date is: {today.strftime('%Y-%m-%d (%A, %B %d, %Y)')}
        Use only tools to answer the user.",
        model=llm,
        tools=[*mcp_tools,write_file],  # Unpack MCP tools and add find_file
        # checkpointer=InMemorySaver(),  # OLD: inline checkpointer
        checkpointer=checkpointer,  # NEW: use variable for memory clearing
    )

    # Set memory references so the clear_memory tool can access the checkpointer
    set_memory_references(checkpointer, "conversation_1")

    # Thread ID for maintaining conversation history
    thread_id = "conversation_1"

    # Initialize Rich console
    console = Console()

    # Initialize prompt session with persistent history
    project_root = pathlib.Path(__file__).parent.resolve()
    history_file = project_root / ".chat_history_mcp"
    session = PromptSession(history=FileHistory(str(history_file)))

    # Display welcome banner
    # OLD welcome banner:
    # console.print(Panel.fit(
    #     "[bold cyan]🤖 Assistant Chat Bot[/bold cyan]\n"
    #     "[dim]Powered by MCP Tools & LangChain[/dim]",
    #     border_style="cyan"
    # ))
    # console.print("[yellow]Type 'quit', 'exit', or 'bye' to end the conversation.[/yellow]\n")
    
    # NEW welcome banner with /clear command:
    console.print(Panel.fit(
        "[bold cyan]🤖 Assistant Chat Bot[/bold cyan]\n"
        "[dim]Powered by MCP Tools & LangChain[/dim]\n\n"
        "[yellow]Commands:[/yellow]\n"
        "  • [cyan]/clear[/cyan] - Clear memory and start fresh\n"
        "  • [cyan]quit/exit/bye[/cyan] - End conversation",
        border_style="cyan"
    ))

    # Display loaded tools in a nice table
    tools_table = Table(title="[bold green]Available Tools[/bold green]", show_header=True)
    tools_table.add_column("Tool Name", style="cyan")
    tools_table.add_column("Count", style="magenta")
    
    mcp_tool_names = ', '.join([t.name for t in mcp_tools])
    tools_table.add_row("MCP Tools", f"{len(mcp_tools)} ({mcp_tool_names})")
    tools_table.add_row("Custom Tools", "(write_file)")
    
    console.print(tools_table)
    console.print()

    # Chat loop
    while True:
        # Get user input with prompt_toolkit (supports arrow up/down history)
        try:
            user_input = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt(HTML('\n<ansigreen><b>You:</b></ansigreen> ')).strip()
            )
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]👋 Goodbye![/yellow]")
            break
        
        # Check for exit commands
        if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
            console.print("\n[bold green]👋 Thanks for chatting! Goodbye![/bold green]")
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
        
        # Display bot response header
        console.print()
        
        # Stream the agent's response with live rendering
        full_response = ""
        current_tool = None
        
        async for event in agent.astream_events(
            {"messages": [human_msg]},
            config={"configurable": {"thread_id": thread_id}},
            version="v2"
        ):
            kind = event["event"]
            
            # Display streaming tokens from the LLM
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    if not full_response:
                        # First chunk - print the bot label
                        console.print("[bold green]🤖 Bot:[/bold green] ", end="")
                    console.print(content, end="", style="white")
                    full_response += content
            
            # Show when tools are being called
            elif kind == "on_tool_start":
                tool_name = event["name"]
                current_tool = tool_name
                console.print()
                console.print(Panel(
                    f"[bold yellow]Calling tool: {tool_name}[/bold yellow]",
                    border_style="yellow",
                    padding=(0, 1)
                ))
            
            # Show tool results
            elif kind == "on_tool_end":
                tool_name = event["name"]
                console.print(Panel(
                    f"[bold green]✓ Tool completed: {tool_name}[/bold green]",
                    border_style="green",
                    padding=(0, 1)
                ))
                console.print()
        
        console.print("\n")  # Add newline after response


# Run the async main function
if __name__ == "__main__":
    asyncio.run(main())
