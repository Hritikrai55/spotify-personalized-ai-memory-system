"""Thin wrapper around the Groq-hosted LLM used throughout the pipeline."""
from langchain_groq import ChatGroq
from src.config import settings


def get_llm(temperature: float = 0.0) -> ChatGroq:
    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY not set. Copy .env.example to .env and add your key."
        )
    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=temperature,
    )
