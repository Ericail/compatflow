"""Client SDK adapters."""

from typing import Literal

from compatflow.adapters.litellm import LiteLLMAdapter
from compatflow.adapters.openai_node import OpenAINodeAdapter
from compatflow.adapters.openai_python import OpenAIPythonAdapter

AdapterName = Literal["openai-python", "litellm", "openai-node"]
ADAPTER_NAMES = ("openai-python", "litellm", "openai-node")


def get_adapter(name: AdapterName) -> OpenAIPythonAdapter | LiteLLMAdapter | OpenAINodeAdapter:
    if name == "openai-python":
        return OpenAIPythonAdapter()
    if name == "litellm":
        return LiteLLMAdapter()
    if name == "openai-node":
        return OpenAINodeAdapter()
    raise ValueError(f"unknown adapter: {name}")


__all__ = [
    "ADAPTER_NAMES",
    "AdapterName",
    "LiteLLMAdapter",
    "OpenAINodeAdapter",
    "OpenAIPythonAdapter",
    "get_adapter",
]
