from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from pydantic import BaseModel

from src.config.database import get_session, Thread, Message

router = APIRouter(prefix="/threads", tags=["Threads"])

class ThreadUpdate(BaseModel):
    title: str

@router.post("/", response_model=Thread)
def create_thread(session: Session = Depends(get_session)):
    """Creates a new empty chat thread."""
    thread = Thread(title="New Research Session")
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return thread

@router.get("/", response_model=List[Thread])
def get_threads(session: Session = Depends(get_session)):
    """Fetches all threads for the sidebar, newest first."""
    statement = select(Thread).order_by(Thread.created_at.desc())
    return session.exec(statement).all()

@router.get("/{thread_id}/messages", response_model=List[Message])
def get_thread_messages(thread_id: int, session: Session = Depends(get_session)):
    """Loads the chat history when a user clicks a thread."""
    thread = session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    statement = select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at.asc())
    return session.exec(statement).all()

@router.patch("/{thread_id}", response_model=Thread)
def rename_thread(thread_id: int, update_data: ThreadUpdate, session: Session = Depends(get_session)):
    """Renames a specific thread."""
    thread = session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    thread.title = update_data.title
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return thread

@router.delete("/{thread_id}")
def delete_thread(thread_id: int, session: Session = Depends(get_session)):
    """Deletes a thread and all associated messages."""
    thread = session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Safely delete all child messages first to avoid SQLite foreign key constraints
    statement = select(Message).where(Message.thread_id == thread_id)
    messages = session.exec(statement).all()
    for msg in messages:
        session.delete(msg)
        
    session.delete(thread)
    session.commit()
    return {"ok": True}