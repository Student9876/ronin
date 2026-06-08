import asyncio
import httpx
import logging
import uuid
from bs4 import BeautifulSoup
from src.agent.memory import EphemeralVectorStore

logger = logging.getLogger(__name__)

class WebScraperTool:
    def __init__(self, max_concurrent: int = 2):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.http_client = httpx.AsyncClient(
            timeout=25.0, 
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        self.memory = EphemeralVectorStore()

    async def shutdown(self):
        await self.http_client.aclose()

    async def fetch_candidates(self, query: str) -> list[dict]:
        """Fetches raw data from SearXNG but DOES NOT store it yet."""
        url = "http://searxng:8080/search"
        params = {"q": query, "format": "json", "engines": "bing,qwant", "categories": "news,science"}
        candidates = []
        
        async with self.semaphore:
            try:
                resp = await self.http_client.get(url, params=params)
                if resp.status_code == 200:
                    results = resp.json().get("results", [])[:5] # Take top 5 candidates
                    for item in results:
                        link = item.get("url")
                        content = item.get("content")
                        title = item.get("title", "Unknown Source")
                        
                        if link and content:
                            candidates.append({
                                "url": link,
                                "title": title,
                                "content": content,
                                "query": query
                            })
                elif resp.status_code >= 429:
                    logger.warning(f"Rate limited on '{query}'.")
                    await asyncio.sleep(5.0)
            except Exception as e:
                logger.error(f"Fetch failed for '{query}': {e}")
            finally:
                await asyncio.sleep(1.5)
                
        return candidates

    def embed_passed_candidate(self, candidate: dict):
        """Only called by the LLM Evaluator when a page passes inspection."""
        payload = f"URL: {candidate['url']}\nTITLE: {candidate['title']}\nTEXT: {candidate['content']}"
        self.memory.ingest_search_results(raw_text=payload, source_query=candidate['query'])

    def gather_semantic_context(self, target_query: str, top_k: int = 6) -> str:
        return self.memory.semantic_search(query=target_query, top_k=top_k)