import asyncio
import trafilatura
from typing import List, Dict, Any
from src.agent.tools.vector_store import VectorManager
from src.agent.tools.registry import tool_registry

# Instantiate our reusable vector store manager for research
research_vectors = VectorManager("research_nodes")

def chunk_text(text: str, chunk_size: int = 1500, chunk_overlap: int = 150) -> List[str]:
    """
    Slices raw scraped text into character-based chunks with defensive sliding overlaps.
    Keeps chunks within safety margins for our local 8B model's context.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Shift forward by chunk size minus overlap to create the sliding window
        start += chunk_size - chunk_overlap
    return chunks

@tool_registry.register("ingest_url", "Fetches body text from a URL and vector indexes to Qdrant.")
async def ingest_url(thread_id: int, subtopic: str, url: str) -> str:
    """
    Rips full text from a URL, chunks it, embeds it via Ollama,
    and index drops it into Qdrant.
    """
    # 1. Fetch web data safely via Trafilatura
    try:
        downloaded = await asyncio.to_thread(trafilatura.fetch_url, url)
        if not downloaded:
            return f"Failed to fetch network stream from: {url}"
            
        # Extract metadata and clean text main body (ignoring ads, navbars, and headers)
        raw_text = await asyncio.to_thread(trafilatura.extract, downloaded, include_links=False, include_images=False)
        if not raw_text:
            return f"No parseable text corpus found at: {url}"
            
        # Extract title defensively
        metadata = await asyncio.to_thread(trafilatura.extract_metadata, downloaded)
        title = metadata.title if metadata else url
    except Exception as e:
        return f"Trafilatura extraction failure for {url}: {str(e)}"

    # 3. Slice text and vectorize chunks into Qdrant in a single batch
    text_chunks = chunk_text(raw_text)
    chunks_to_insert = []
    for i, chunk_slice in enumerate(text_chunks):
        metadata = {
            "url": url,
            "title": title,
            "subtopic": subtopic,
            "chunk_index": i
        }
        chunks_to_insert.append({
            "text": chunk_slice,
            "metadata": metadata
        })
        
    if chunks_to_insert:
        # Run vector indexing in the background so it doesn't block the stream response
        asyncio.create_task(research_vectors.insert_chunks(thread_id, chunks_to_insert))
 
    print(f"Ingestion successful: {url} ({len(text_chunks)} chunks synchronized).")
    return raw_text