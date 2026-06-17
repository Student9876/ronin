from datetime import datetime
from typing import List, Optional, AsyncGenerator
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

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

# Convert standard sqlite URL to aiosqlite (e.g. sqlite+aiosqlite:///ronin_database.db)
async_db_url = settings.DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

# Engine initialization
engine = create_async_engine(async_db_url, connect_args={"check_same_thread": False})

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session