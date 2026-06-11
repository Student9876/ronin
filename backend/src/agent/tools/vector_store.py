import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import uuid

from src.config.agent_config import settings

class VectorManager:
    """A reusable Qdrant client for both Research and Code modes."""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        # Target the Qdrant Docker container
        self.client = QdrantClient(url=settings.QDRANT_URL)
        self._ensure_collection()

    def _ensure_collection(self):
        """Creates the collection if it doesn't exist. nomic-embed-text uses 768 dimensions."""
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

    async def get_embedding(self, text: str) -> list[float]:
        """Hits the dedicated Ollama container for vectorization."""
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                settings.OLLAMA_EMBED_URL,
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def insert_chunk(self, thread_id: int, text: str, metadata: dict):
        """Embeds and inserts a single chunk with thread isolation."""
        vector = await self.get_embedding(text)
        
        # Enforce thread_id in payload for strict isolation
        payload = {"thread_id": thread_id, "content": text, **metadata}
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload
                )
            ]
        )

    async def search_context(self, thread_id: int, query: str, limit: int = 3) -> list[dict]:
        """Retrieves top N relevant chunks strictly isolated to the current thread."""
        query_vector = await self.get_embedding(query)
        
        # Use the modernized query API required by qdrant-client v1.10+
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="thread_id",
                        match=MatchValue(value=thread_id)
                    )
                ]
            )
        )
        return [hit.payload for hit in results.points]

    def purge_thread(self, thread_id: int):
        """Deletes all vectors belonging to a deleted chat."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="thread_id", match=MatchValue(value=thread_id))]
            )
        )