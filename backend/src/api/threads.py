from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from pydantic import BaseModel

from src.config.database import get_session, Thread, Message
from src.agent.tools.vector_store import VectorManager

# Instantiate the vector manager for thread purging
research_vectors = VectorManager("research_nodes")


router = APIRouter(prefix="/threads", tags=["Threads"])

class ThreadUpdate(BaseModel):
    title: str

@router.post("/", response_model=Thread)
async def create_thread(session: AsyncSession = Depends(get_session)):
    """Creates a new empty chat thread."""
    thread = Thread(title="New Research Session")
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread

@router.get("/", response_model=List[Thread])
async def get_threads(session: AsyncSession = Depends(get_session)):
    """Fetches all threads for the sidebar, newest first."""
    statement = select(Thread).order_by(Thread.created_at.desc())
    result = await session.execute(statement)
    return result.scalars().all()

@router.get("/{thread_id}/messages", response_model=List[Message])
async def get_thread_messages(thread_id: int, session: AsyncSession = Depends(get_session)):
    """Loads the chat history when a user clicks a thread."""
    thread = await session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    statement = select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at.asc())
    result = await session.execute(statement)
    return result.scalars().all()

@router.patch("/{thread_id}", response_model=Thread)
async def rename_thread(thread_id: int, update_data: ThreadUpdate, session: AsyncSession = Depends(get_session)):
    """Renames a specific thread."""
    thread = await session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    thread.title = update_data.title
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread

@router.delete("/{thread_id}")
async def delete_thread(thread_id: int, session: AsyncSession = Depends(get_session)):
    """Deletes a thread and all associated messages."""
    thread = await session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Safely delete all child messages first to avoid SQLite foreign key constraints
    statement = select(Message).where(Message.thread_id == thread_id)
    result = await session.execute(statement)
    messages = result.scalars().all()
    for msg in messages:
        await session.delete(msg)
        
    await session.delete(thread)
    await session.commit()
    
    # Purge vectors from Qdrant to prevent memory leak
    try:
        research_vectors.purge_thread(thread_id)
    except Exception as e:
        print(f"Qdrant thread purge failed: {e}")

    return {"ok": True}