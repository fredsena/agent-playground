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

# agent = create_agent(
#     system_prompt="You are a helpful assistant.",
#     model=llm,
#     checkpointer=InMemorySaver(),
#     tools=[get_web_links, get_web_data, find_file,read_file,write_file,list_files,create_folder],
# )



from langchain.tools import tool, ToolRuntime

@tool
def read_email(runtime: ToolRuntime) -> str:
    """Read an email from the given address."""
    # take email from state
    return runtime.state["email"]

@tool
def send_email(body: str) -> str:
    """Send an email to the given address with the given subject and body."""
    # fake email sending
    return f"Email sent"

from langchain.agents import create_agent, AgentState
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import HumanInTheLoopMiddleware

class EmailState(AgentState):
    email: str

agent = create_agent(
    model=llm,
    tools=[read_email, send_email],
    state_schema=EmailState,
    checkpointer=InMemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "read_email": False,
                "send_email": True,
            },
            description_prefix="Tool execution requires approval",
        ),
    ],
)

from langchain.messages import HumanMessage

config = {"configurable": {"thread_id": "1"}}

response = agent.invoke(
    {
        "messages": [HumanMessage(content="Please read my email and send a response.")],
        "email": "Hi Seán, I'm going to be late for our meeting tomorrow. Can we reschedule? Best, John."
    },
    config=config
)

from pprint import pprint

pprint(response)

print(response['__interrupt__'])

# Access just the 'body' argument from the tool call
print(response['__interrupt__'][0].value['action_requests'][0]['args']['body'])

#Approve

from langgraph.types import Command

response = agent.invoke(
    Command( 
        resume={"decisions": [{"type": "approve"}]}
    ), 
    config=config # Same thread ID to resume the paused conversation
)

pprint(response)

#Reject
response = agent.invoke(
    Command(        
        resume={
            "decisions": [
                {
                    "type": "reject",
                    # An explanation of why the request was rejected
                    "message": "No please sign off - Your merciful leader, Seán."
                }
            ]
        }
    ), 
    config=config # Same thread ID to resume the paused conversation
    )   

pprint(response)

print(response['__interrupt__'][0].value['action_requests'][0]['args']['body'])

#Edit
response = agent.invoke(
    Command(        
        resume={
            "decisions": [
                {
                    "type": "edit",
                    # Edited action with tool name and args
                    "edited_action": {
                        # Tool name to call.
                        # Will usually be the same as the original action.
                        "name": "send_email",
                        # Arguments to pass to the tool.
                        "args": {"body": "This is the last straw, you're fired!"},
                    }
                }
            ]
        }
    ), 
    config=config # Same thread ID to resume the paused conversation
    )   

pprint(response)



# thread_id = "conversation_1"

# console.print()

# console.print(Panel.fit(
#     "[bold cyan]🤖 AI Assistant Chat Bot[/bold cyan]\n\n"
#     "[dim]Features:[/dim]\n"
#     f"  • Powered by [green]{llm.model_name}[/green]\n"
#     "  • Terminal-like typing effects\n"
#     "  • File operations (find, read, write)\n"
#     "  • Web link search\n"
#     "  • Conversation history\n\n"
#     "[yellow]Type 'quit', 'exit', or 'bye' to end the conversation.[/yellow]",
#     border_style="cyan",
#     padding=(1, 2)
# ))
# console.print()

# # Initialize prompt session with persistent history file inside the project folder
# project_root = pathlib.Path(__file__).parent.resolve()
# history_file = project_root / ".chat_history"
# history_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
# session = PromptSession(history=FileHistory(str(history_file)))

# # Chat loop
# while True:
#     # Get user input with prompt_toolkit (supports arrow up/down history)
#     try:
#         user_input = session.prompt(HTML('\n<ansigreen><b>You:</b></ansigreen> ')).strip()
#     except (KeyboardInterrupt, EOFError):
#         console.print("\n[yellow]👋 Goodbye![/yellow]")
#         break
    
#     # Check for exit commands
#     if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
#         console.print("\n[bold yellow]👋 Thanks for chatting! Goodbye![/bold yellow]")
#         break
    
#     # Skip empty inputs
#     if not user_input:
#         continue
    
#     # Create human message
#     human_msg = HumanMessage(user_input)
    
#     # Show status while AI is thinking
#     with console.status("[bold cyan]🤖 Thinking...", spinner="dots"):
#         # Invoke agent with thread configuration to maintain history
#         result = agent.invoke(
#             {"messages": [human_msg]},
#             config={"configurable": {"thread_id": thread_id}}
#         )
    
#     # Get and display the AI's response with typing effect
#     ai_response = result["messages"][-1].content
#     console.print("\n[bold cyan]🤖 Bot:[/bold cyan] ", end="")    
#     console.print(Markdown(ai_response))

# console.print("\n")
