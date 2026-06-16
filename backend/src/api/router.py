import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session
from typing import Literal, AsyncGenerator, Optional

from src.config.agent_config import settings
from src.config.database import get_session
from src.utils.database_ops import save_message

router = APIRouter(prefix="/agent", tags=["Agent Operations"])

class QueryPayload(BaseModel):
    thread_id: int
    query: str
    mode: Literal["general", "deep", "code"]
    search_depth: Optional[Literal["quick", "comprehensive", "exhaustive"]] = "comprehensive"
    strictness: Optional[Literal["lenient", "strict"]] = "strict"

async def stream_and_record(payload: QueryPayload, engine_generator: AsyncGenerator):
    """
    A universal wrapper that streams an engine's execution to the client,
    accumulates text and status data silently in memory, and cleanly 
    commits the final agent result to SQLite.
    """
    accumulated_content = ""
    tracked_statuses = []

    # 1. Stream live data to the frontend while mirroring payloads into memory
    async for chunk in engine_generator:
        yield chunk
        
        try:
            data_str = chunk.replace("data: ", "").strip()
            if data_str and data_str != "[DONE]":
                parsed = json.loads(data_str)
                if parsed.get("type") == "delta":
                    accumulated_content += parsed.get("content", "")
                elif parsed.get("type") == "status":
                    tracked_statuses.append(parsed)
        except Exception:
            # Silently ignore parsing errors on malformed chunks to protect the live stream
            pass

    # 2. Graph execution complete. Safely persist the agent's memory to the database.
    if accumulated_content.strip() or tracked_statuses:
        save_message(
            thread_id=payload.thread_id,
            role="agent",
            content=accumulated_content.strip(),
            statuses=tracked_statuses
        )

@router.post("/stream")
async def handle_agent_stream(payload: QueryPayload): # Removed session dependency
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    # Verify the chosen processing engine exists in the config matrix
    if payload.mode not in settings.MODES:
        raise HTTPException(status_code=400, detail="Invalid operational mode.")

    mode_cfg = settings.MODES[payload.mode]

    # Step 1: Pre-Execution Commit - Save User Prompt Globally
    save_message(thread_id=payload.thread_id, role="user", content=payload.query)

    # Step 2: Mode Dispatcher - Select Target Engine
    if payload.mode == "general":
        from src.agent.graphs.general_chat import stream_chat
        # Removed the session argument here to match the pure graph
        engine_generator = stream_chat(payload, mode_cfg)

    elif payload.mode == "deep":
        from src.agent.graphs.deep_research import stream_research
        engine_generator = stream_research(payload, mode_cfg)

    elif payload.mode == "code":
        async def stub_code_mode():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Code Mode not yet implemented.'})}\n\n"
            yield "data: [DONE]\n\n"
        engine_generator = stub_code_mode()

    # Step 3: Return the Wrapped Stream Controller
    return StreamingResponse(
        stream_and_record(payload, engine_generator),
        media_type="text/event-stream"
    )