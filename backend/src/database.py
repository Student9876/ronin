import json
from datetime import datetime
from typing import List, Optional
from sqlmodel import Field, SQLModel, create_engine, Session

# --- MODELS ---

class Thread(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="New Research Thread")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="thread.id", index=True)
    role: str  # 'user' or 'agent'
    content: str
    statuses: Optional[str] = Field(default="[]") # Stored as JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)

# --- ENGINE ---

sqlite_file_name = "ronin_database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session