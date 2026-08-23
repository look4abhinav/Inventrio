"""Shared LLM configuration for all Inventrio agents."""

import os

from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

load_dotenv()

chat_model = OpenAIChatModel(
    # model_name="ox-alpha-free",
    model_name="minimax-m3",
    provider=OpenAIProvider(
        base_url=os.getenv("OPENCODE_BASE_URL"), api_key=os.getenv("OPENCODE_API_KEY")
    ),
)
