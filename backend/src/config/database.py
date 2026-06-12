from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship, create_engine, Session

# agent configuration matrix
from src.config.agent_config import settings

class Thread(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Cascade relationships: Dropping a Thread object drops all related child rows
    messages: List["Message"] = Relationship(
        back_populates="thread", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    artifacts: List["ResearchArtifact"] = Relationship(
        back_populates="thread", 
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="thread.id")
    role: str
    content: str
    statuses: str = Field(default="[]") # Stores LangGraph node tracking arrays as JSON strings
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    thread: Thread = Relationship(back_populates="messages")

class ResearchArtifact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="thread.id")
    subtopic: str
    url: str
    title: str
    content: str # Cleaned body content extracted by Trafilatura
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    thread: Thread = Relationship(back_populates="artifacts")

# Engine initialization
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session