import pathlib
import re
from datetime import datetime

import requests
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain.agents import create_agent

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import SummarizationMiddleware
from langchain.messages import HumanMessage, AIMessage
from pprint import pprint

from typing import Any
from langchain.agents import AgentState
from langchain.messages import RemoveMessage
from langgraph.runtime import Runtime
from langchain.agents.middleware import before_agent, after_agent
from langchain.messages import ToolMessage

from utils.llm import get_llm

llm = get_llm()

# @before_agent
# def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
#     """Remove all the tool messages from the state"""
#     messages = state["messages"]
#     tool_messages = [m for m in messages if isinstance(m, ToolMessage)]    
#     return {"messages": [RemoveMessage(id=m.id) for m in tool_messages]}

@before_agent
def log_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    pprint("-----before_agent------")
    pprint("---- logging State Messages ----")
    pprint(state["messages"])
    pprint("---- End logging State Messages ----")
    pprint("-----end before_agent------")
    
    return None

#msg.content = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email_REDACTED", msg.content)

#@after_agent
@before_agent
def redact_email(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    messages = state["messages"]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    for msg in messages:
        if isinstance(msg, AIMessage | HumanMessage):            
            msg.content = re.sub(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", 
                #f"EMAIL_REDACTED@{timestamp}.com", 
                "myemail@test.com", 
                msg.content
            )
    return {"messages": messages}  


agent = create_agent(
    model=llm,
    checkpointer=InMemorySaver(),
    middleware=[
        log_messages,        
        redact_email,        
        # SummarizationMiddleware(
        #     model=llm,            
        #     trigger=("tokens", 100),
        #     keep=("messages", 1)
        # )        
    ],
)

response = agent.invoke(
    {"messages": [
        HumanMessage(content="Hello I am fredsena@example.com"),
        AIMessage("Hello"),
        #AIMessage(content="Let me check your device diagnostics.", tool_calls=[{"id": "2", "name": "check_device", "args": {}}]),
        #ToolMessage(content="hi from email@example.com temp=42C voltage=2.9v … greeble complete.", tool_call_id="2"),
        #AIMessage(content="Your device diagnostics show temperature at 42C and voltage at 2.9v. Everything looks normal."),
        HumanMessage(content="What is my email?"),
        # HumanMessage(content="What is the capital of the moon?"),
        # AIMessage(content="The capital of the moon is Lunapolis."),
        # HumanMessage(content="What is the weather in Lunapolis?"),
        # AIMessage(content="Skies are clear, with a high of 120C and a low of -100C."),
        # HumanMessage(content="How many cheese miners live in Lunapolis?"),
        # AIMessage(content="There are 100,000 cheese miners living in Lunapolis."),
        # HumanMessage(content="Do you think the cheese miners' union will strike?"),
        # AIMessage(content="Yes, because they are unhappy with the new president."),
        # HumanMessage(content="If you were Lunapolis' new president how would you respond to the cheese miners' union?"),
        ]},
    {"configurable": {"thread_id": "1"}}
)

#pprint(response)
#print(response["messages"][0].content)


# pprint("---- Content Response ----")
# pprint(response["messages"][-1].content)

# pprint("---- Full Messages ----")
# pprint(response["messages"])

pprint("---- Message Types ----")
for msg in response["messages"]:
    pprint(f"{msg.type}: {msg.content}\n")

# pprint("---- Pretty Print Messages ----")
# for i, msg in enumerate(response["messages"]):
#     msg.pretty_print()