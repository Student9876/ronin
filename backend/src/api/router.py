import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session
from typing import Literal

from src.config.agent_config import settings
from src.config.database import get_session

router = APIRouter(prefix="/agent", tags=["Agent Operations"])

class QueryPayload(BaseModel):
    thread_id: int
    query: str
    mode: Literal["general", "deep", "code"]

async def master_stream_switchboard(payload: QueryPayload, session: Session):
    # Verify the chosen processing engine exists in the config matrix
    if payload.mode not in settings.MODES:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid operational mode.'})}\n\n"
        return

    mode_cfg = settings.MODES[payload.mode]

    # Mode Dispatcher
    if payload.mode == "general":
        from src.agent.graphs.general_chat import stream_chat
        async for chunk in stream_chat(payload, mode_cfg, session):
            yield chunk

    elif payload.mode == "deep":
        from src.agent.graphs.deep_research import stream_research
        async for chunk in stream_research(payload, mode_cfg, session):
            yield chunk

    elif payload.mode == "code":
        yield f"data: {json.dumps({'type': 'error', 'message': 'Code Mode not yet implemented.'})}\n\n"

@router.post("/stream")
async def handle_agent_stream(payload: QueryPayload, session: Session = Depends(get_session)):
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    return StreamingResponse(
        master_stream_switchboard(payload, session),
        media_type="text/event-stream"
    )