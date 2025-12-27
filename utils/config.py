"""Configuration management for agent-playground."""
import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class LLMConfig:
    model: str = os.getenv("LLM_MODEL", "qwen/qwen3-4b-2507")
    base_url: str = os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1")
    api_key: str = os.getenv("LLM_API_KEY", "")
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

# Singleton instance
llm_config = LLMConfig()
