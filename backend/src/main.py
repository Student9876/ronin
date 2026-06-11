from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from src.api import threads
from src.api import router as agent_router # Import the new unified switchboard

app = FastAPI(
    title="Ronin Core Engine",
    description="Backend engine for orchestrating multi-agent workflows, including deep research and general chat.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(threads.router)
api_v1.include_router(agent_router.router) # Mounts /api/v1/agent/stream

app.include_router(api_v1)