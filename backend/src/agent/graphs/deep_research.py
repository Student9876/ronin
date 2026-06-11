import json
import httpx
import instructor
from typing import Dict, List, Any, TypedDict
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from langgraph.graph import StateGraph, START, END

from src.config.agent_config import settings
from src.config.database import Message, engine
from sqlmodel import Session

# 1. Dual-Client Architecture
# Base client for pure text generation
base_client = AsyncOpenAI(base_url=settings.LOCAL_LLM_URL, api_key="lm-studio")
# Instructor-patched client strictly for structured JSON enforcement
instructor_client = instructor.from_openai(base_client, mode=instructor.Mode.JSON)

# 2. Pydantic Schemas & State Definition
class SubtopicsSchema(BaseModel):
    subtopics: List[str] = Field(description="A list of 3 highly specific research sub-topics.")

class ResearchState(TypedDict):
    topic: str
    subtopics: List[str]
    current_index: int
    current_subtopic: str
    raw_findings: List[str]                   # Temporary memory: wiped clean every cycle
    compressed_sections: List[Dict[str, str]] # Permanent memory: incrementally built
    final_report: str

# 3. Graph Nodes
async def chief_editor(state: ResearchState) -> Dict[str, Any]:
    """Generates the research plan and forces strict JSON output using Instructor."""
    prompt = f"Break down the following topic into exactly 3 distinct, highly specific sub-topics for investigation. Topic: {state['topic']}"
    
    try:
        # Instructor guarantees we get the SubtopicsSchema object back, no parsing required
        response = await instructor_client.chat.completions.create(
            model=settings.MODES["deep"].model_name,
            response_model=SubtopicsSchema,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_retries=2
        )
        subtopics = response.subtopics
    except Exception as e:
        print(f"Instructor parsing failed: {e}. Defaulting to generic subtopics.")
        subtopics = [f"General Analysis of {state['topic']}", "Current Trends", "Future Outlook"]
        
    return {"subtopics": subtopics, "current_index": 0}

async def queue_manager(state: ResearchState) -> Dict[str, Any]:
    """Iterates through the subtopics array."""
    idx = state.get("current_index", 0)
    subtopics = state.get("subtopics", [])
    
    if idx >= len(subtopics):
        return {"current_subtopic": "DONE"}
        
    return {"current_subtopic": subtopics[idx], "current_index": idx + 1}

async def searxng_scraper(state: ResearchState) -> Dict[str, Any]:
    """Hits the local SearXNG container to extract web data."""
    subtopic = state["current_subtopic"]
    params = {
        "q": subtopic,
        "format": "json",
        "engines": "google,duckduckgo,wikipedia",
        "language": "en"
    }
    
    raw_findings = []
    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(settings.SEARXNG_URL, params=params, timeout=15.0)
            resp.raise_for_status()
            results = resp.json().get("results", [])[:4] # Cap at 4 snippets to protect VRAM
            
            for r in results:
                if r.get("content"):
                    raw_findings.append(f"Fact from {r.get('url')}: {r.get('content')}")
    except Exception as e:
        print(f"SearXNG failed for '{subtopic}': {e}")
        
    if not raw_findings:
        raw_findings.append("No verifiable data discovered.")
        
    # We overwrite the raw_findings string entirely in the state
    return {"raw_findings": raw_findings}

async def compactor(state: ResearchState) -> Dict[str, Any]:
    """Map Phase: Shrinks raw search text into a dense summary, purging the raw text."""
    subtopic = state["current_subtopic"]
    raw_text = "\n".join(state["raw_findings"])
    
    prompt = f"Synthesize a factual report section for the sub-topic: '{subtopic}'. Use ONLY these facts:\n{raw_text}\n\nProvide output in Markdown."
    
    response = await base_client.chat.completions.create(
        model=settings.MODES["deep"].model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    
    new_section = {"subtopic": subtopic, "content": response.choices[0].message.content}
    
    # State Mutation: Append to sections, but critically, WIPE raw_findings back to empty.
    return {
        "compressed_sections": state.get("compressed_sections", []) + [new_section],
        "raw_findings": [] 
    }

async def synthesizer(state: ResearchState) -> Dict[str, Any]:
    """Reduce Phase: Merges the compressed sections into the final output."""
    sections = state.get("compressed_sections", [])
    body = "\n\n".join([f"## {s['subtopic']}\n{s['content']}" for s in sections])
    
    prompt = f"Assemble a cohesive, professional research report for the topic: '{state['topic']}'.\n\nCompiled Sections:\n{body}"
    
    response = await base_client.chat.completions.create(
        model=settings.MODES["deep"].model_name,
        messages=[
            {"role": "system", "content": settings.MODES["deep"].system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    return {"final_report": response.choices[0].message.content}

# 4. Routing Logic
def route_research(state: ResearchState) -> str:
    if state["current_subtopic"] == "DONE":
        return "synthesize"
    return "searxng_scraper"

# 5. Graph Assembly
workflow = StateGraph(ResearchState)
workflow.add_node("chief_editor", chief_editor)
workflow.add_node("queue_manager", queue_manager)
workflow.add_node("searxng_scraper", searxng_scraper)
workflow.add_node("compactor", compactor)
workflow.add_node("synthesize", synthesizer)

workflow.add_edge(START, "chief_editor")
workflow.add_edge("chief_editor", "queue_manager")
workflow.add_conditional_edges("queue_manager", route_research)
workflow.add_edge("searxng_scraper", "compactor")
workflow.add_edge("compactor", "queue_manager")
workflow.add_edge("synthesize", END)

research_app = workflow.compile()

# 6. FastAPI Router Interface
async def stream_research(payload: Any, mode_cfg: Any, session: Session):
    """The foreground stream handler triggered by the FastAPI router."""
    # Commit empty agent message to database
    user_msg_db = Message(thread_id=payload.thread_id, role="user", content=payload.query)
    session.add(user_msg_db)
    agent_msg_db = Message(thread_id=payload.thread_id, role="agent", content="", statuses="[]")
    session.add(agent_msg_db)
    session.commit()
    agent_msg_id = agent_msg_db.id

    initial_state = {
        "topic": payload.query,
        "subtopics": [],
        "current_index": 0,
        "current_subtopic": "",
        "raw_findings": [],
        "compressed_sections": [],
        "final_report": ""
    }

    agent_statuses = []
    final_report_content = ""

    # Stream graph progress events directly to the UI
    try:
        async for output in research_app.astream(initial_state):
            for node_name, state_update in output.items():
                msg = f"Agent executing: {node_name}..."
                if node_name == "chief_editor":
                    msg = f"Chief Editor planned {len(state_update.get('subtopics', []))} research lines."
                elif node_name == "searxng_scraper":
                    msg = "Extracting live web data..."
                elif node_name == "compactor":
                    msg = "Compressing findings to secure VRAM..."

                agent_statuses.append({"node": node_name, "message": msg})
                yield f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': msg})}\n\n"

                # When the final synthesis completes, yield the actual markdown report
                if node_name == "synthesize":
                    final_report_content = state_update.get("final_report", "")
                    yield f"data: {json.dumps({'type': 'delta', 'content': final_report_content})}\n\n"

        # Commit generation to SQLite
        with Session(engine) as fresh_session:
            db_msg = fresh_session.get(Message, agent_msg_id)
            if db_msg:
                db_msg.content = final_report_content
                db_msg.statuses = json.dumps(agent_statuses)
                fresh_session.add(db_msg)
            fresh_session.commit()

    except Exception as e:
        error_msg = f"Research execution failed: {str(e)}"
        print(error_msg)
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"