"""Client SDK adapters."""

from typing import Literal

from compatflow.adapters.litellm import LiteLLMAdapter
from compatflow.adapters.openai_python import OpenAIPythonAdapter

AdapterName = Literal["openai-python", "litellm"]
ADAPTER_NAMES = ("openai-python", "litellm")


def get_adapter(name: AdapterName) -> OpenAIPythonAdapter | LiteLLMAdapter:
    if name == "openai-python":
        return OpenAIPythonAdapter()
    if name == "litellm":
        return LiteLLMAdapter()
    raise ValueError(f"unknown adapter: {name}")


__all__ = [
    "ADAPTER_NAMES",
    "AdapterName",
    "LiteLLMAdapter",
    "OpenAIPythonAdapter",
    "get_adapter",
]
