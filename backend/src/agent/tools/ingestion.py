import trafilatura
from typing import List, Dict, Any
from sqlmodel import Session

from src.config.database import engine, ResearchArtifact
from src.agent.tools.vector_store import VectorManager

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

async def ingest_url(thread_id: int, subtopic: str, url: str) -> str:
    """
    Rips full text from a URL, commits it to SQLite as a master record,
    chunks it, embeds it via Ollama, and index drops it into Qdrant.
    """
    # 1. Fetch web data safely via Trafilatura
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return f"Failed to fetch network stream from: {url}"
            
        # Extract metadata and clean text main body (ignoring ads, navbars, and headers)
        raw_text = trafilatura.extract(downloaded, include_links=False, include_images=False)
        if not raw_text:
            return f"No parseable text corpus found at: {url}"
            
        # Extract title defensively
        title = trafilatura.extract_metadata(downloaded).title if trafilatura.extract_metadata(downloaded) else url
    except Exception as e:
        return f"Trafilatura extraction failure for {url}: {str(e)}"

    # 2. Commit the master copy to SQLite for persistent reference
    with Session(engine) as session:
        artifact = ResearchArtifact(
            thread_id=thread_id,
            subtopic=subtopic,
            url=url,
            title=title,
            content=raw_text
        )
        session.add(artifact)
        session.commit()

    # 3. Slit text and vectorize chunks into Qdrant for Gap Analysis retrieval
    text_chunks = chunk_text(raw_text)
    for i, chunk_slice in enumerate(text_chunks):
        metadata = {
            "url": url,
            "title": title,
            "subtopic": subtopic,
            "chunk_index": i
        }
        # Uses our VectorManager to embed via Ollama and store in Qdrant with thread filtering tags
        await research_vectors.insert_chunk(
            thread_id=thread_id,
            text=chunk_slice,
            metadata=metadata
        )

    print(f"Ingestion successful: {url} ({len(text_chunks)} chunks synchronized).")
    return raw_text