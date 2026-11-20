import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()


def get_model(model: str = "openai/gpt-oss-120b"):
    if model == "openai/gpt-oss-20b":
        return ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0,
            max_tokens=2048,
            reasoning_effort="low",
            max_retries=6,
        )

    return ChatGroq(
        model=model,
        temperature=0,
        max_retries=6,
    )


def get_llm(fast: bool = False):
    return get_model("openai/gpt-oss-20b" if fast else "openai/gpt-oss-120b")