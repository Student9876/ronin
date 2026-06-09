from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List

from src.database import get_session, Thread, Message

router = APIRouter(prefix="/threads", tags=["Threads"])

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