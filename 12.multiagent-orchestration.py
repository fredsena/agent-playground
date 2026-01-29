import os
import uuid
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver

from utils.tools.get_web_links import get_web_links
from utils.tools.get_web_data import get_web_data
from utils.llm import get_llm


def summarize_findings(text: str):
    """Summarize research findings (simulated)"""
    return f"Summary: {text[:200]}..."

# Set up persistent storage for long-term memory
checkpointer = MemorySaver()  # Use PostgresStore in production
store = InMemoryStore()  # Use PostgresStore in production

# Create a backend that routes /memories/ to persistent storage
def make_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),      # Ephemeral: lost after thread ends
        routes={
            "/memories/": StoreBackend(runtime)  # Persistent: survives threads
        }
    )

# Define specialized subagents
research_subagent = {
    "name": "research-specialist",
    "description": "Conducts in-depth research using web search on specific topics",
    "system_prompt": """You are a thorough research specialist. Your job is to:
    1. Break down research questions into searchable queries
    2. Use get_web_links, get_web_data to find relevant information
    3. Save key findings to /memories/research_notes.txt for future reference
    4. Return a concise summary with sources
    
    Always save findings so the main agent remembers them!""",
    "tools": [get_web_links, get_web_data, summarize_findings],
}

analyst_subagent = {
    "name": "analyst",
    "description": "Analyzes research data and extracts key insights",
    "system_prompt": """You are a data analyst. Your job is to:
    1. Take research findings from the research specialist
    2. Extract key insights and patterns
    3. Save analysis to /memories/insights.txt
    4. Return structured conclusions""",
    "tools": [summarize_findings],
}

llm = get_llm()

# Create the main supervisor agent
main_agent = create_deep_agent(
    model=llm,
    subagents=[research_subagent, analyst_subagent],
    system_prompt="""You are a research coordinator. Your job is to:
    1. Delegate research tasks to the research-specialist
    2. Ask the analyst to interpret findings
    3. Read /memories/research_notes.txt and /memories/insights.txt to remember previous work
    4. Build on past research to provide comprehensive answers
    
    IMPORTANT: Always check what we've learned before in /memories/ before starting new research!""",
    backend=make_backend,
    store=store,
    checkpointer=checkpointer,
    name="main-agent"
)

# Example usage: Multi-turn conversation with persistent memory
def run_research_workflow():
    # Thread 1: Initial research (different thread_id = new conversation)
    thread_1 = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    result1 = main_agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Research quantum computing trends and save your findings"
        }]
    }, config=thread_1)
    
    print("Thread 1 Result:")
    print(result1["messages"][-1].content)
    print()
    
    # Thread 2: Follow-up in a NEW conversation (different thread_id)
    # The agent can still access /memories/ from Thread 1!
    thread_2 = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    result2 = main_agent.invoke({
        "messages": [{
            "role": "user",
            "content": "What did we learn about quantum computing? Build on our previous research."
        }]
    }, config=thread_2)
    
    print("Thread 2 Result (different conversation, same persistent memory):")
    print(result2["messages"][-1].content)
    print()
    
    # Thread 3: Continue the same conversation
    result3 = main_agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Now research quantum computing applications in finance"
        }]
    }, config=thread_2)
    
    print("Thread 3 Result (same conversation):")
    print(result3["messages"][-1].content)

# Run the workflow
if __name__ == "__main__":
    run_research_workflow()