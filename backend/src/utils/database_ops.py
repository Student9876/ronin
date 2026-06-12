import json
from sqlmodel import Session
from src.config.database import engine, Message

def save_message(thread_id: int, role: str, content: str, statuses: list = None):
    """
    Universally commits a single message row to SQLite.
    Isolates all database session logic from the application routers and execution graphs.
    """
    with Session(engine) as db_session:
        msg = Message(
            thread_id=thread_id,
            role=role,
            content=content,
            statuses=json.dumps(statuses) if statuses else "[]"
        )
        db_session.add(msg)
        db_session.commit()