import json
import httpx
from typing import List, Dict, Any, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from src.config.agent_config import settings
from src.agent.tools.vector_store import VectorManager
from src.agent.tools.ingestion import ingest_url
from src.utils.network import get_http_client

# Initialize our reusable vector client
research_vectors = VectorManager("research_nodes")

# --- Structured Output Schemas ---
class GapAnalysis(BaseModel):
    is_context_sufficient: bool = Field(
        description="True if previous research artifacts inside this chat are completely sufficient to answer the prompt. False if new research is required."
    )
    missing_subtopics: List[str] = Field(
        default=[],
        description="If context is insufficient, provide a list of highly specific subtopics or queries that must be scraped to fill the knowledge gap."
    )

class ResearchPlan(BaseModel):
    queries: List[str] = Field(description="List of 2-3 target search queries optimized for a search engine to fulfill the missing requirements.")

# --- LangGraph State Definition ---
class DeepResearchState(Dict[str, Any]):
    thread_id: int
    query: str
    is_sufficient: bool
    missing_subtopics: List[str]
    research_queries: List[str]
    retrieved_context: str
    final_response: str

# --- Helper function for Local LLM JSON handling ---
async def call_local_llm_structured(prompt: str, response_model: Any) -> Any:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.LOCAL_LLM_URL + "/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": "You are a precise data extraction engine. Respond strictly in valid JSON matching the requested schema."},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0
            },
            timeout=60.0
        )
        response.raise_for_status()
        raw_json = response.json()["choices"][0]["message"]["content"]
        return response_model.parse_raw(raw_json)

# --- The Graph Nodes (Strictly Returning State) ---

async def librarian_gap_analysis(state: DeepResearchState):
    past_nodes = await research_vectors.search_context(thread_id=state["thread_id"], query=state["query"], limit=4)
    context_str = "\n\n".join([f"Source: {h['url']}\nContent: {h['content']}" for h in past_nodes]) if past_nodes else "No previous research conducted."
    
    prompt = f"User Intent: {state['query']}\nAvailable Context:\n{context_str}\nAnalyze if context is sufficient."
    
    try:
        analysis = await call_local_llm_structured(prompt, GapAnalysis)
        return {
            "is_sufficient": analysis.is_context_sufficient,
            "missing_subtopics": analysis.missing_subtopics,
            "retrieved_context": context_str
        }
    except Exception:
        return {"is_sufficient": False, "missing_subtopics": [state["query"]], "retrieved_context": ""}

async def chief_editor_planner(state: DeepResearchState):
    prompt = f"Original Goal: {state['query']}\nMissing Info: {', '.join(state['missing_subtopics'])}\nGenerate 2 search queries."
    try:
        plan = await call_local_llm_structured(prompt, ResearchPlan)
        return {"research_queries": plan.queries}
    except:
        return {"research_queries": [state["query"]]}

async def concurrent_scraper(state: DeepResearchState):
    queries = state["research_queries"]
    new_scraped_text_blocks = []
    
    # Instantiate our centralized, footprint-guarded network utility
    async with get_http_client() as client:
        for q in queries:
            try:
                search_res = await client.get(settings.SEARXNG_URL, params={"q": q, "format": "json"})
                results = search_res.json().get("results", [])[:2]
                
                for res in results:
                    url = res.get("url")
                    if not url: continue
                    
                    full_text = await ingest_url(thread_id=state["thread_id"], subtopic=q, url=url)
                    if not full_text.startswith("Failed") and not full_text.startswith("No parseable"):
                        new_scraped_text_blocks.append(full_text)
            except Exception as e:
                print(f"Scraper error parsing network data: {e}")

    combined_context = state["retrieved_context"] + "\n\n" + "\n\n".join(new_scraped_text_blocks)
    return {"retrieved_context": combined_context}

# --- Conditional Routing ---
def route_after_analysis(state: DeepResearchState) -> Literal["enough_context", "need_research"]:
    return "enough_context" if state["is_sufficient"] else "need_research"

# --- Graph Assembly ---
workflow = StateGraph(DeepResearchState)
workflow.add_node("librarian", librarian_gap_analysis)
workflow.add_node("chief_editor", chief_editor_planner)
workflow.add_node("scraper", concurrent_scraper)

workflow.set_entry_point("librarian")
workflow.add_conditional_edges("librarian", route_after_analysis, {"enough_context": END, "need_research": "chief_editor"})
workflow.add_edge("chief_editor", "scraper")
workflow.add_edge("scraper", END)

deep_research_graph = workflow.compile()

# --- Unified Streaming Interface (Pure Orchestrator) ---
async def stream_research(payload: Any, mode_cfg: Any):
    initial_state = {
        "thread_id": payload.thread_id,
        "query": payload.query,
        "is_sufficient": False,
        "missing_subtopics": [],
        "research_queries": [],
        "retrieved_context": "",
        "final_response": ""
    }
    
    current_state = initial_state.copy()
    
    # Helper to construct proper Server Sent Events
    def format_status(node_name: str, message: str):
        return f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': message})}\n\n"

    yield format_status("system", "Booting Deep Research Protocol...")
    
    async for event in deep_research_graph.astream(initial_state):
        node_name = list(event.keys())[0]
        current_state.update(event[node_name])
        
        if node_name == "librarian":
            msg = "Historical context is sufficient. Bypassing live scrape." if current_state["is_sufficient"] else "Knowledge gap detected. Formulating search plan."
            yield format_status("librarian", msg)
        elif node_name == "chief_editor":
            yield format_status("editor", "Target search queries generated.")
        elif node_name == "scraper":
            yield format_status("scraper", "Web data successfully extracted and vectorized.")

    yield format_status("synthesizer", "Synthesizing final report...")
    
    prompt = f"Analyze and answer comprehensively based on this validated data:\n\nUser Request: {current_state['query']}\n\nContext:\n{current_state['retrieved_context']}"
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            settings.LOCAL_LLM_URL + "/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "stream": True},
            timeout=90.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line.replace("data: ", "")
                    if data_str.strip() == "[DONE]": break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            # We just blindly yield the delta string; the router wrapper handles all the saving
                            yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"
                    except:
                        pass

    # The Stream Kill Signal - Forces the UI and router wrapper to lock states
    yield "data: [DONE]\n\n"