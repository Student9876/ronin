import asyncio
import json
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

# Import your compiled LangGraph application
from src.agent.graph import app as workflow_app # <-- Change this if your compiled graph variable is named differently

router = APIRouter(prefix="/research", tags=["Research"])

async def live_langgraph_stream(query: str):
    """
    Executes the real LangGraph agent and streams node transitions and outputs.
    """
    # Initialize the state exactly as your main.py used to
    initial_state = {
        "topic": query,
        "objective": "Extract high-density factual insights and metrics.",
        "current_depth": 0
    }

    try:
        # Stream the graph execution asynchronously
        async for output in workflow_app.astream(initial_state):
            # output is a dict where the key is the node name that just finished
            for node_name, state_update in output.items():
                
                # 1. Map LangGraph nodes to UI Status Messages
                if node_name == "plan_research_step":
                    msg = f"Generated search queries for: '{query}'"
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                    
                elif node_name == "execute_scraping_cycle":
                    sources = state_update.get("source_manifest", {})
                    msg = f"Scraped and evaluated {len(sources)} verified sources."
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                    
                elif node_name == "analyze_and_extract":
                    facts = state_update.get("raw_findings", [])
                    msg = f"Extracted {len(facts)} grounded facts from memory."
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                
                elif node_name == "synthesize_conclusion":
                    msg = "Synthesis complete."
                    yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"
                    
                    # 2. Yield the final generated markdown report
                    final_report = state_update.get("final_report", "")
                    # For now, we dump the whole report as one delta. 
                    # True token-by-token streaming requires LLM callback handlers.
                    yield f"data: {json.dumps({'type': 'delta', 'content': final_report})}\n\n"

    except asyncio.CancelledError:
        print("Client disconnected from the SSE stream. Execution halted.")
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

@router.get("/stream")
async def stream_research(query: str = Query(..., min_length=1, description="The research topic target")):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
        
    return StreamingResponse(
        live_langgraph_stream(query), 
        media_type="text/event-stream"
    )