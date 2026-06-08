import uuid
import logging
import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

class EphemeralVectorStore:
    def __init__(self, collection_name: str = "ronin_context"):
        # Ephemeral client lives purely in memory for fast, isolated agent runs
        self.client = chromadb.EphemeralClient()
        
        # Uses an efficient, lightweight local model (all-MiniLM-L6-v2) by default
        # Runs fast on CPU, no GPU required.
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn
        )

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """Splits massive raw text blocks into overlapping mathematical chunks."""
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap # Step forward, but overlap to preserve context

        return chunks

    def ingest_search_results(self, raw_text: str, source_query: str):
        """Chunks raw HTML/Text and pushes it into the vector space."""
        if not raw_text.strip():
            return

        chunks = self._chunk_text(raw_text)
        
        # Generate unique IDs and metadata for each chunk
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source_query": source_query} for _ in chunks]

        self.collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Ingested {len(chunks)} vector chunks into memory from query: '{source_query}'")

    def semantic_search(self, query: str, top_k: int = 4) -> str:
        """Retrieves the mathematically closest chunks to the target objective."""
        if self.collection.count() == 0:
            return ""

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )
        
        # Stitch the top K relevant chunks back into a single string for the LLM
        retrieved_documents = results.get('documents', [[]])[0]
        return "\n\n...[CONTEXT BREAK]...\n\n".join(retrieved_documents)