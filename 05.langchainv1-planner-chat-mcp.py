import pathlib
import re
from typing import Dict, Any
import requests
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain.agents import create_agent

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

from langgraph.checkpoint.memory import MemorySaver, InMemorySaver
from langchain_core.tools import tool
from utils.llm import get_llm

import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from tavily import TavilyClient

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

load_dotenv()

async def main():
    # Get today's date for the system prompt
    today = datetime.now()

    db = SQLDatabase.from_uri("sqlite:///resources/Chinook.db")

    @tool
    def query_playlist_db(query: str) -> str:
        """Query the database for playlist information. start by fetching all columns from the `Genre` table to identify the correct attribute for filtering"""

        try:
            return db.run(query)
        except Exception as e:
            return f"Error querying database: {e}"

    tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    @tool(
        "web_search", 
        parse_docstring=True, 
        description=("Search the web for information")
    )
    def web_search(query: str) -> Dict[str, Any]:
        """Search the web for information using Tavily.

        Args:
            query (str): The search query to look up on the web.

        Returns:
            Dict[str, Any]: Search results from Tavily, or error dict if search fails.
        """
        try:
            return tavily_client.search(query)
        except Exception as e:
            return {"error": f"Web search failed: {str(e)}"}


    @tool(
        "find_file",
        parse_docstring=True,
        description=(
            "Find files by name or pattern across a directory tree. "
            "Works on both Linux and Windows. Returns the full paths of matching files."
        ),
    )
    def find_file(
        filename: str, 
        search_dir: str = ".",
        recursive: bool = True
    ) -> str:
        """Find files by name or pattern in a directory.

        Args:
            filename (str): The file name or pattern to search for (e.g., "*.txt", "config.json").
            search_dir (str): The directory to search in. Defaults to current directory.
            recursive (bool): Whether to search subdirectories. Defaults to True.

        Returns:
            str: Comma-separated list of full paths to matching files, or "No files found" if empty.

        Raises:
            ValueError: If the search directory doesn't exist.
        """
        #console.print(f"🔍 Searching for '[cyan]{filename}[/cyan]' in '[blue]{search_dir}[/blue]'", style="info")
        
        # Convert to pathlib.Path for cross-platform compatibility
        search_path = pathlib.Path(search_dir).expanduser().resolve()
        
        if not search_path.exists():
            raise ValueError(f"Directory does not exist: {search_path}")
        
        if not search_path.is_dir():
            raise ValueError(f"Path is not a directory: {search_path}")
        
        # Search for matching files
        try:
            if recursive:
                # Recursive search using glob
                matches = list(search_path.glob(f"**/{filename}"))
            else:
                # Non-recursive search
                matches = list(search_path.glob(filename))
            
            if matches:
                # Convert to absolute paths and return as comma-separated string
                file_paths = [str(m.resolve()) for m in matches]
                return ", ".join(file_paths)
            else:
                return f"No files found matching '{filename}' in {search_path}"
        
        except Exception as e:
            return f"Error during search: {str(e)}"


    # Connect to MCP servers
    mcp_client = MultiServerMCPClient(
        {
            # "time": {
            #     "transport": "stdio",
            #     "command": "npx",
            #     "args": ["-y", "@theo.foobar/mcp-time"],
            # },
            "msdocs": {
                "transport": "streamable_http",            
                "url": "https://learn.microsoft.com/api/mcp",
            },
            "langchaindocs": {
                "transport": "streamable_http",            
                "url": "https://docs.langchain.com/mcp",
            },
            "travel_server": {
                "transport": "streamable_http",
                "url": "https://mcp.kiwi.com"
            }            
        },
    )

    # Load tools from the MCP servers
    mcp_tools = await mcp_client.get_tools()
    print(f"Loaded {len(mcp_tools)} MCP tools: {[t.name for t in mcp_tools]}\n")

    llm = get_llm()

    class WeddingState(AgentState):
        origin: str
        destination: str
        guest_count: str
        genre: str
        wedding_date: str


    # Travel agent
    travel_agent = create_agent(
        model=llm,
        tools=mcp_tools,
        system_prompt=f"""
        You are a travel agent. Search for flights to the desired destination wedding location.
        IMPORTANT: Today's date is {today.strftime('%Y-%m-%d')}. All flight dates MUST be in the future.
        You are not allowed to ask any more follow up questions, you must find the best flight options based on the following criteria:
        - Price (lowest, economy class)
        - Duration (shortest)
        - Date (use the provided date or choose a future date that works well for a wedding)
        To make things easy, only look for one ticket, one way.
        You may need to make multiple searches to iteratively find the best options.
        Once you have found the best options, let the user know your shortlist of options.
        """
    )

    # Venue agent
    venue_agent = create_agent(
        model=llm,
        tools=[web_search],
        system_prompt="""
        You are a venue specialist. Search for venues in the desired location, and with the desired capacity.
        You are not allowed to ask any more follow up questions, you must find the best venue options based on the following criteria:
        - Price (lowest)
        - Capacity (exact match)
        - Reviews (highest)
        You may need to make multiple searches to iteratively find the best options.
        """
    )

    # Playlist agent
    playlist_agent = create_agent(
        model=llm,
        tools=[query_playlist_db],
        system_prompt="""
        You are a playlist specialist. Query the sql database and curate the perfect playlist for a wedding given a genre.
        Once you have your playlist, calculate the total duration and cost of the playlist, each song has an associated price.
        If you run into errors when querying the database, try to fix them by making changes to the query.
        Do not come back empty handed, keep trying to query the db until you find a list of songs.
        You may need to make multiple queries to iteratively find the best options.
        """
    )

    @tool
    async def search_flights(runtime: ToolRuntime) -> str:
        """Travel agent searches for flights to the desired destination wedding location."""
        origin = runtime.state.get("origin")
        destination = runtime.state.get("destination")
        wedding_date = runtime.state.get("wedding_date")
        
        if not origin or not destination:
            return "Error: Please update the state with origin and destination first using the update_state tool."
        
        date_info = f" on or around {wedding_date}" if wedding_date else ""
        response = await travel_agent.ainvoke({"messages": [HumanMessage(content=f"Find flights from {origin} to {destination}{date_info}")]})
        return response['messages'][-1].content

    @tool
    def search_venues(runtime: ToolRuntime) -> str:
        """Venue agent chooses the best venue for the given location and capacity."""
        destination = runtime.state.get("destination")
        capacity = runtime.state.get("guest_count")
        
        if not destination or not capacity:
            return "Error: Please update the state with destination and guest_count first using the update_state tool."
        
        query = f"Find wedding venues in {destination} for {capacity} guests"
        response = venue_agent.invoke({"messages": [HumanMessage(content=query)]})
        return response['messages'][-1].content

    @tool
    def suggest_playlist(runtime: ToolRuntime) -> str:
        """Playlist agent curates the perfect playlist for the given genre."""
        genre = runtime.state.get("genre")
        
        if not genre:
            return "Error: Please update the state with genre first using the update_state tool."
        
        query = f"Find {genre} tracks for wedding playlist"
        response = playlist_agent.invoke({"messages": [HumanMessage(content=query)]})
        return response['messages'][-1].content

    @tool
    def update_state(origin: str, destination: str, guest_count: str, genre: str, wedding_date: str = "", runtime: ToolRuntime = None) -> str:
        """Update the state when you know the values: origin, destination, guest_count, genre, and optionally wedding_date"""
        update_dict = {
            "origin": origin, 
            "destination": destination, 
            "guest_count": guest_count, 
            "genre": genre,
            "messages": [ToolMessage("Successfully updated state", tool_call_id=runtime.tool_call_id)]
        }
        if wedding_date:
            update_dict["wedding_date"] = wedding_date
        return Command(update=update_dict)

    coordinator = create_agent(
        model=llm,
        tools=[search_flights, search_venues, suggest_playlist, update_state],
        #tools=[*mcp_tools, search_venues, suggest_playlist, update_state],
        state_schema=WeddingState,
        system_prompt=f"""
        You are a wedding coordinator. Delegate tasks to your specialists for flights, venues and playlists.
        Today's date is {today.strftime('%Y-%m-%d')}.
        First find all the information you need to update the state (origin, destination, guest_count, genre, and wedding_date if provided). 
        Once that is done you can delegate the tasks.
        Once you have received their answers, coordinate the perfect wedding for me.
        """,
        #checkpointer=InMemorySaver(),
    )


    agent = create_agent(
        system_prompt=f"You are a helpful assistant. IMPORTANT GUIDELINES FOR DATE-SENSITIVE OPERATIONS: - Today's date is: {today.strftime('%Y-%m-%d (%A, %B %d, %Y)')} Use only tools to answer the user.",
        model=llm,
        tools=[*mcp_tools, find_file, web_search],  # Unpack MCP tools and add find_file
        #checkpointer=InMemorySaver(),
    )

    # Thread ID for maintaining conversation history
    thread_id = "conversation_1"

    # Initialize Rich console
    console = Console()

    # Display welcome banner
    console.print(Panel.fit(
        "[bold cyan]🤖 Assistant Chat Bot[/bold cyan]\n"
        "[dim]Powered by MCP Tools & LangChain[/dim]",
        border_style="cyan"
    ))
    console.print("[yellow]Type 'quit', 'exit', or 'bye' to end the conversation.[/yellow]\n")

    # Display loaded tools in a nice table
    tools_table = Table(title="[bold green]Available Tools[/bold green]", show_header=True)
    tools_table.add_column("Tool Name", style="cyan")
    tools_table.add_column("Count", style="magenta")
    
    mcp_tool_names = ', '.join([t.name for t in mcp_tools])
    tools_table.add_row("MCP Tools", f"{len(mcp_tools)} ({mcp_tool_names})")
    tools_table.add_row("Custom Tools", "2 (find_file, web_search)")
    
    console.print(tools_table)
    console.print()

    # Chat loop
    while True:
        # Get user input
        user_input = console.input("[bold blue]You:[/bold blue] ").strip()
        
        # Check for exit commands
        if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
            console.print("\n[bold green]👋 Thanks for chatting! Goodbye![/bold green]")
            break
        
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
        
        #async for event in agent.astream_events(
        async for event in coordinator.astream_events(
            {"messages": [human_msg]},
            #config={"configurable": {"thread_id": thread_id}},
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
