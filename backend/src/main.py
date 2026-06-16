from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.database import create_db_and_tables
from src.api.router import router as agent_router
from src.api.threads import router as threads_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This fires immediately on container bootup and recreates missing tables
    create_db_and_tables()
    yield

app = FastAPI(
    title="Ronin Intelligence Platform Engine",
    version="1.0.0",
    lifespan=lifespan
)

# --- CORS BLOCK ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Whitelist your Next.js dev server
    allow_credentials=True,
    allow_methods=["*"], # Allow POST, GET, OPTIONS, etc.
    allow_headers=["*"], # Allow all headers
)

# Core Router Mounting
app.include_router(agent_router, prefix="/api/v1")
app.include_router(threads_router, prefix="/api/v1")