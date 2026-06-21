import uuid
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.config.agent_config import settings

logger = logging.getLogger(__name__)

class LongTermMemoryManager:
    def __init__(self):
        self.collection_name = "long_term_memories"
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = QdrantClient(url=settings.QDRANT_URL)
            self._ensure_collection()
        return self._client

    def _ensure_collection(self):
        if not self._client.collection_exists(self.collection_name):
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

    async def get_embedding(self, text: str) -> list[float]:
        from src.utils.llm_client import llm_client
        response = await llm_client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=[text],
            dimensions=768
        )
        return response.data[0].embedding

    async def save_memory_summary(self, thread_id: int, summary: str):
        """Saves a summary paragraph to long-term memory."""
        if not summary or not summary.strip() or summary == "Prior conversation summarized to maintain context boundaries.":
            return
            
        try:
            vector = await self.get_embedding(summary)
            payload = {
                "thread_id": thread_id,
                "content": summary
            }
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
            logger.info(f"Successfully saved compaction summary for thread {thread_id} to long-term memory.")
        except Exception as e:
            logger.error(f"Failed to save summary to long-term memory: {e}")

    async def retrieve_long_term_memories(self, query: str, limit: int = 2) -> list[str]:
        """Retrieves matching summaries across all threads to serve as long-term memory."""
        try:
            query_vector = await self.get_embedding(query)
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit
            )
            return [hit.payload["content"] for hit in results.points if "content" in hit.payload]
        except Exception as e:
            logger.error(f"Failed to retrieve long-term memories: {e}")
            return []

# Singleton instance for application-wide use
long_term_memory = LongTermMemoryManager()
