from typing import List, Dict, Any
from src.agent.tools.registry import tool_registry
from src.config.agent_config import settings
from src.utils.network import get_http_client

@tool_registry.register("web_search", "Queries SearXNG search engine for real-time web results.")
async def web_search(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Executes a web query against the SearXNG search container.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    async with get_http_client() as network_client:
        try:
            search_res = await network_client.get(
                settings.SEARXNG_URL,
                params={"q": query, "format": "json"},
                headers=headers,
            )
            if search_res.status_code == 200:
                try:
                    return search_res.json().get("results", [])[:limit]
                except Exception as e:
                    print(f"Web search JSON parse failed: {e}")
            else:
                print(f"SearXNG returned status {search_res.status_code}")
        except Exception as e:
            print(f"Web search network error: {e}")
            
    return []
