import asyncio
import json
from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from src.agent.graph import app as workflow_app
from src.database import get_session, Message, Thread, engine

router = APIRouter(prefix="/research", tags=["Research"])

async def live_langgraph_stream(query: str, thread_id: int, depth: str, strictness: str, session: Session):
    # 1. Save User Message
    user_msg = Message(thread_id=thread_id, role="user", content=query)
    session.add(user_msg)
    
    # 2. Pre-create Agent Message and grab its ID
    agent_msg = Message(thread_id=thread_id, role="agent", content="", statuses="[]")
    session.add(agent_msg)
    session.commit()
    
    agent_msg_id = agent_msg.id  # Save this ID for the fresh session later

    # Pass settings into your LangGraph state (assuming RoninState supports this, otherwise they are just available here)
    initial_state = {
        "topic": query,
        "objective": f"Extract high-density factual insights. Depth: {depth}. Strictness: {strictness}.",
        "current_depth": 0
    }

    agent_statuses = []
    final_report_content = ""

    try:
        msg = f"Initializing research protocol for: {query}"
        agent_statuses.append({"node": "init", "message": msg})
        yield f"data: {json.dumps({'type': 'status', 'node': 'init', 'message': msg})}\n\n"
        await asyncio.sleep(0.1)

        async for output in workflow_app.astream(initial_state):
            for node_name, state_update in output.items():
                print(f"DEBUG: Received from node: {node_name}")  # Add this line
                
                if node_name == "plan":
                    msg = f"Generated search queries (Depth: {depth})"
                    agent_statuses.append({"node": node_name, "message": msg})
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                    
                elif node_name == "scrape":
                    sources = state_update.get("source_manifest", {})
                    msg = f"Scraped and evaluated verified sources (Strictness: {strictness})."
                    agent_statuses.append({"node": node_name, "message": msg})
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                    
                elif node_name == "extract":
                    facts = state_update.get("raw_findings", [])
                    msg = f"Extracted {len(facts)} grounded facts from memory."
                    agent_statuses.append({"node": node_name, "message": msg})
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                
                elif node_name == "synthesize":
                    msg = "Synthesis complete."
                    agent_statuses.append({"node": node_name, "message": msg})
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                    
                    final_report_content = state_update.get("final_report", "")
                    yield f"data: {json.dumps({'type': 'delta', 'content': final_report_content})}\n\n"

        # 3. FRESH SESSION: Write to the DB safely after the long delay
        with Session(engine) as fresh_session:
            db_msg = fresh_session.get(Message, agent_msg_id)
            if db_msg:
                db_msg.content = final_report_content
                db_msg.statuses = json.dumps(agent_statuses)
                fresh_session.add(db_msg)
            
            thread = fresh_session.get(Thread, thread_id)
            if thread and thread.title == "New Research Session":
                thread.title = query[:40] + ("..." if len(query) > 40 else "")
                fresh_session.add(thread)
                
            fresh_session.commit()

    except asyncio.CancelledError:
        # Don't save "interrupted" - the workflow may still be processing
        # Just log and exit gracefully
        print("Client disconnected. Workflow may continue in background.")
        pass  # Let it be, the message stays as empty in DB
        
    except Exception as e:
        error_msg = f"\n\n**SYSTEM ERROR:** {str(e)}\n\n"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        
        with Session(engine) as fresh_session:
            db_msg = fresh_session.get(Message, agent_msg_id)
            if db_msg:
                db_msg.content = final_report_content + error_msg
                db_msg.statuses = json.dumps(agent_statuses)
                fresh_session.add(db_msg)
                fresh_session.commit()

@router.get("/stream")
async def stream_research(
    query: str = Query(...), 
    thread_id: int = Query(...),
    depth: str = Query(default="comprehensive"),
    strictness: str = Query(default="strict"),
    session: Session = Depends(get_session)
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    thread = session.get(Thread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")

    return StreamingResponse(
        live_langgraph_stream(query, thread_id, depth, strictness, session), 
        media_type="text/event-stream"
    )