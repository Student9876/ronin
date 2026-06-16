# Import all tool modules here so they are registered in the global tool_registry at boot.
from src.agent.tools.registry import tool_registry, execute_tool
from src.agent.tools.search import web_search
from src.agent.tools.ingestion import ingest_url
from src.agent.tools.vector_store import vector_search

__all__ = ["tool_registry", "execute_tool", "web_search", "ingest_url", "vector_search"]
