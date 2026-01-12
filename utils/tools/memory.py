"""
Memory management tools for clearing conversation context.
"""
from langchain_core.tools import tool
from typing import Optional

# Global reference to the checkpointer - will be set by the main application
_checkpointer = None
_current_thread_id = None

def set_memory_references(checkpointer, thread_id: str):
    """
    Set the global references to the checkpointer and thread_id.
    Call this from your main application after creating the agent.
    """
    global _checkpointer, _current_thread_id
    _checkpointer = checkpointer
    _current_thread_id = thread_id

def update_thread_id(thread_id: str):
    """Update the current thread_id reference."""
    global _current_thread_id
    _current_thread_id = thread_id

def clear_all_memory() -> str:
    """
    Clear all conversation memory from the checkpointer.
    Returns a success or error message.
    """
    global _checkpointer
    
    if _checkpointer is None:
        return "Error: Checkpointer not initialized."
    
    try:
        # InMemorySaver stores data in .storage dict
        if hasattr(_checkpointer, 'storage'):
            _checkpointer.storage.clear()
        # Also try clearing writes if present
        if hasattr(_checkpointer, 'writes'):
            _checkpointer.writes.clear()
        return "🧹 MEMORY CLEARED SUCCESSFULLY. All previous conversation context has been erased. You must now treat this as a completely NEW conversation - do NOT reference any prior information, names, topics, or context. Ask the user how you can help them as if meeting them for the first time."
    except Exception as e:
        return f"Error clearing memory: {str(e)}"

def clear_thread_memory(thread_id: Optional[str] = None) -> str:
    """
    Clear memory for a specific thread.
    If no thread_id provided, clears the current thread.
    """
    global _checkpointer, _current_thread_id
    
    if _checkpointer is None:
        return "Error: Checkpointer not initialized."
    
    target_thread = thread_id or _current_thread_id
    
    if target_thread is None:
        return "Error: No thread_id specified."
    
    try:
        if hasattr(_checkpointer, 'storage'):
            # Remove all keys related to this thread
            keys_to_remove = [
                key for key in list(_checkpointer.storage.keys()) 
                if target_thread in str(key)
            ]
            for key in keys_to_remove:
                del _checkpointer.storage[key]
        return f"✅ Memory for thread '{target_thread}' cleared successfully!"
    except Exception as e:
        return f"Error clearing thread memory: {str(e)}"


@tool
def clear_memory(scope: str = "all") -> str:
    """
    Clears the conversation memory/context to start fresh.
    Use this tool when the user asks to:
    - Clear the memory or context
    - Start fresh or start over
    - Forget previous conversations
    - Begin a new process with different data
    
    Args:
        scope: Either "all" to clear all memory, or "thread" to clear only current thread.
               Defaults to "all".
    
    Returns:
        A message confirming the memory was cleared.
    """
    
    print("🧹 Invoking clear memory tool")
    
    if scope == "thread":
        return clear_thread_memory()
    else:
        return clear_all_memory()
