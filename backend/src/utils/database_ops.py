import json
from src.config.database import async_session_maker, Message

async def save_message(thread_id: int, role: str, content: str, statuses: list = None):
    """
    Universally commits a single message row to SQLite asynchronously.
    Isolates all database session logic from the application routers and execution graphs.
    """
    async with async_session_maker() as db_session:
        msg = Message(
            thread_id=thread_id,
            role=role,
            content=content,
            statuses=json.dumps(statuses) if statuses else "[]"
        )
        db_session.add(msg)
        await db_session.commit()