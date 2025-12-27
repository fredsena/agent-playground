"""LLM factory for creating configured language models."""
from langchain_openai import ChatOpenAI
from .config import llm_config

def get_llm(**overrides) -> ChatOpenAI:
    """Get a configured LLM instance.
    
    Args:
        **overrides: Override any config values (model, temperature, etc.)
    """
    return ChatOpenAI(
        model=overrides.get("model", llm_config.model),
        base_url=overrides.get("base_url", llm_config.base_url),
        api_key=overrides.get("api_key", llm_config.api_key),
        temperature=overrides.get("temperature", llm_config.temperature),
    )
