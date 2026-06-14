import json
import httpx
from typing import List, Dict, Any, TypedDict, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

from src.config.agent_config import settings
from src.utils.network import get_http_client
from src.agent.tools.ingestion import ingest_url
from src.agent.graphs.general_chat import memory_app

# --- Structured Output Schemas ---
class ResearchChecklist(BaseModel):
    sub_queries: List[str] = Field(
        description="A list of exactly 3 highly specific search queries."
    )

class FactEvaluation(BaseModel):
    is_valuable: bool = Field(description="True if the text contains explicit evidence answering the query.")
    key_finding: str = Field(default="", description="A dense sentence containing the extracted fact. Empty if not valuable.")

# --- LangGraph State Definition ---
class DeepResearchState(TypedDict):
    thread_id: int
    query: str
    chat_history: str
    pending_tasks: List[str]
    current_task: str
    evaluation_attempts: int
    scraped_text: str  # Temporary buffer for the evaluator
    current_url: str   # Tagged URL for the current scrape
    verified_facts: List[Dict[str, str]]

# --- Local LLM JSON Helper ---
# --- Structural-Agnostic JSON Helper ---
async def call_local_llm_structured(system_prompt: str, user_prompt: str, response_model: Any) -> Any:
    """Forces the local 8B model to return JSON and aggressively extracts data even if the model echoes the schema."""
    schema_json = response_model.schema_json() if hasattr(response_model, "schema_json") else response_model.model_json_schema()
    enforced_system = f"{system_prompt}\n\nYou MUST respond strictly in valid JSON matching this schema format:\n{schema_json}\nReturn ONLY the JSON object, no conversational text."
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.LOCAL_LLM_URL + "/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": enforced_system},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1
            },
            timeout=60.0
        )
        response.raise_for_status()
        
        raw_json = response.json()["choices"][0]["message"]["content"].strip()
        
        # 1. Strip markdown wrapping
        if "```json" in raw_json:
            raw_json = raw_json.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_json:
            raw_json = raw_json.split("```")[1].split("```")[0].strip()
            
        # 2. THE FIX: Isolate the core JSON object to drop conversational trailing text
        start_idx = raw_json.find('{')
        end_idx = raw_json.rfind('}')
        if start_idx != -1 and end_idx != -1:
            raw_json = raw_json[start_idx:end_idx+1]
            
        try:
            parsed_data = json.loads(raw_json)
        except Exception as e:
            print(f"Raw JSON parsing failed: {e}. Falling back to emergency initialization.")
            if response_model.__name__ == "ResearchChecklist":
                fallback_queries = [
                    user_prompt,
                    f"{user_prompt} in-depth specifications",
                    f"{user_prompt} reddit reviews",
                ]
                return response_model(sub_queries=fallback_queries)
            return response_model(sub_queries=[user_prompt])

        # Aggressive deep scanner to pull queries out of any schema-echoing dictionary structures
        def find_sub_queries_deep(d: Any) -> List[str]:
            if isinstance(d, dict):
                # Scenario 1: Correct structural extraction or partially corrected keys
                if "sub_queries" in d and isinstance(d["sub_queries"], list):
                    return [str(x) for x in d["sub_queries"]]
                # Scenario 2: Model echoed the schema properties and hid the values in 'default'
                if "sub_queries" in d and isinstance(d["sub_queries"], dict):
                    sq = d["sub_queries"]
                    if "default" in sq and isinstance(sq["default"], list):
                        return [str(x) for x in sq["default"]]
                    if "example" in sq and isinstance(sq["example"], list):
                        return [str(x) for x in sq["example"]]
                if "default" in d and isinstance(d["default"], list):
                    return [str(x) for x in d["default"]]
                # Deep traverse values
                for val in d.values():
                    found = find_sub_queries_deep(val)
                    if found:
                        return found
            elif isinstance(d, list):
                if all(isinstance(x, str) for x in d) and len(d) > 0:
                    return d
                for item in d:
                    found = find_sub_queries_deep(item)
                    if found:
                        return found
            return []

        # If we are resolving the planner node checklist path, apply the deep query scanner
        if response_model.__name__ == "ResearchChecklist":
            extracted_queries = find_sub_queries_deep(parsed_data)
            if extracted_queries:
                return response_model(sub_queries=extracted_queries[:3])
            
        # Standard structural fallback for non-checklist schemas (e.g., FactEvaluation)
        try:
            if hasattr(response_model, "model_validate"):
                return response_model.model_validate(parsed_data)
            return response_model.parse_obj(parsed_data)
        except Exception:
            if "properties" in parsed_data:
                parsed_data = parsed_data["properties"]
            if hasattr(response_model, "model_validate"):
                return response_model.model_validate(parsed_data)
            return response_model.parse_obj(parsed_data)
        

# --- The Graph Nodes ---
async def planner_node(state: DeepResearchState):
    history_context = f"\nRecent Conversation Context:\n{state.get('chat_history', 'None')}" if state.get('chat_history') else ""
    
    system_prompt = (
        "You are a lead technical research architect. Break the user's objective into exactly 3 highly specific, distinct search engine queries. "
        "CRITICAL: Generate pure search keywords only. DO NOT generate URLs or links. "
        "Use the Recent Conversation Context to resolve any pronouns (like 'it', 'this one') into specific product names or subjects before writing the search queries."
        f"{history_context}"
    )
    try:
        plan = await call_local_llm_structured(system_prompt, state["query"], ResearchChecklist)
        queries = plan.sub_queries[:3] if plan.sub_queries else [state["query"]]
    except Exception as e:
        print(f"Planner failed: {e}")
        queries = [state["query"]] 
        
    return {"pending_tasks": queries, "evaluation_attempts": 0, "verified_facts": []}

async def scraper_node(state: DeepResearchState):
    tasks = state["pending_tasks"]
    if not tasks:
        return {} # Failsafe

    current_task = state["current_task"]
    if state["evaluation_attempts"] == 0:
        current_task = tasks.pop(0)

    extracted_text = ""
    target_url = ""

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    async with get_http_client() as network_client:
        try:
            search_res = await network_client.get(
                settings.SEARXNG_URL,
                params={"q": current_task, "format": "json"},
                headers=headers,
            )
            
            # Guard against SearXNG HTML error pages
            if search_res.status_code == 200:
                try:
                    results = search_res.json().get("results", [])
                except Exception as e:
                    print(f"Scraper warning: unable to parse SearXNG JSON for query '{current_task}': {e}")
                    results = []
                
                # Grab the top valid link
                for res in results[:3]:
                    url = res.get("url")
                    if not url: continue
                    text = await ingest_url(thread_id=state["thread_id"], subtopic=current_task, url=url)
                    if not text.startswith("Failed") and not text.startswith("No parseable"):
                        # Clear out heavy whitespace blocks to pack more actual content into the window
                        cleaned_text = " ".join(text.split())
                        # Expand context window to 8,000 characters to capture the actual forum body
                        extracted_text = cleaned_text[:8000] 
                        target_url = url
                        break
            else:
                print(f"Scraper warning: SearXNG returned status {search_res.status_code}")
        except Exception as e:
            print(f"Scraper error: {e}")

    return {
        "pending_tasks": tasks,
        "current_task": current_task,
        "scraped_text": extracted_text,
        "current_url": target_url
    }

async def evaluator_node(state: DeepResearchState):
    if not state["scraped_text"]:
        # Network failed to find readable data. Treat as failed evaluation.
        return handle_failed_evaluation(state)

    system_prompt = (
        "You are a ruthless technical data grader. Analyze the scraped text against the target search query.\n\n"
        "CRITICAL RULES:\n"
        "1. The AMD Ryzen 7 9800X3D is a modern Zen 5 processor. Reject any outdated software designed for Zen 3 or older (like zenpower3, zenmonitor).\n"
        "2. If the text mentions general CPU cooling tips or basic motherboard settings without addressing the active query parameters, mark it false.\n"
        "3. Only mark true if the text provides specific, technical facts or verified parameters relevant to modern hardware configurations."
    )
    user_prompt = f"Target Query: {state['current_task']}\n\nScraped Text:\n{state['scraped_text']}"
    
    try:
        evaluation = await call_local_llm_structured(system_prompt, user_prompt, FactEvaluation)
    except Exception:
        # If parsing fails, fail-safe to reject the text
        return handle_failed_evaluation(state)

    verified = state["verified_facts"]
    
    if evaluation.is_valuable and evaluation.key_finding:
        # Success: Save fact, reset attempts for the next task
        verified.append({
            "url": state["current_url"],
            "fact": evaluation.key_finding
        })
        return {
            "verified_facts": verified,
            "evaluation_attempts": 0 
        }
    else:
        # Failure: text was useless.
        return handle_failed_evaluation(state)

def handle_failed_evaluation(state: DeepResearchState):
    attempts = state["evaluation_attempts"] + 1
    current_task = state["current_task"]
    
    if attempts < 2:
        # Mutate query to try deeper without assuming it's a bug
        current_task = current_task + " in-depth specifications OR reddit"
        return {"current_task": current_task, "evaluation_attempts": attempts}
    else:
        return {"evaluation_attempts": 0}
    

# --- Conditional Edge Routing ---
def route_after_evaluation(state: DeepResearchState) -> Literal["scraper", "end"]:
    # If we just reset attempts to 0, it means we either succeeded or maxed out.
    # Check if there are tasks left to process.
    if state["evaluation_attempts"] == 0 and not state["pending_tasks"]:
        return "end"
    # Otherwise, loop back to the scraper
    return "scraper"

# --- Graph Assembly ---
workflow = StateGraph(DeepResearchState)
workflow.add_node("planner", planner_node)
workflow.add_node("scraper", scraper_node)
workflow.add_node("evaluator", evaluator_node)

workflow.add_edge(START, "planner")
workflow.add_edge("planner", "scraper")
workflow.add_edge("scraper", "evaluator")
workflow.add_conditional_edges("evaluator", route_after_evaluation, {"scraper": "scraper", "end": END})

research_graph = workflow.compile()

# --- Unified Streaming Interface (The Orchestrator) ---
async def stream_research(payload: Any, mode_cfg: Any):
    # 1. Retrieve short-term memory history from the checkpointer to fix amnesia context loss
    config = {"configurable": {"thread_id": str(payload.thread_id)}}
    try:
        state_snapshot = memory_app.get_state(config)
        current_chat = state_snapshot.values if state_snapshot else {}
        past_messages = current_chat.get("messages", [])
        
        # Format last 3 messages into a string block for the planner node
        history_blocks = []
        for m in past_messages[-3:]:
            history_blocks.append(f"{m['role'].capitalize()}: {m['content']}")
        chat_history_str = "\n".join(history_blocks)
    except Exception as e:
        print(f"Failed to fetch conversation history for planner context: {e}")
        chat_history_str = ""

    initial_state = {
        "thread_id": payload.thread_id,
        "query": payload.query,
        "chat_history": chat_history_str,  # Injected history context mapping
        "pending_tasks": [],
        "current_task": "",
        "evaluation_attempts": 0,
        "scraped_text": "",
        "current_url": "",
        "verified_facts": []
    }
    
    current_state = initial_state.copy()
    
    def format_status(node_name: str, message: str):
        return f"data: {json.dumps({'type': 'status', 'node': node_name, 'message': message})}\n\n"

    yield format_status("system", "Booting Deep Research Protocol...")
    
    async for event in research_graph.astream(initial_state):
        node_name = list(event.keys())[0]
        
        if event[node_name]: 
            current_state.update(event[node_name])
            
        if node_name == "planner":
            yield format_status("planner", f"Deconstructed query into {len(current_state['pending_tasks'])} execution paths.")
        elif node_name == "scraper":
            yield format_status("scraper", f"Analyzing sources for: {current_state['current_task']}")
        elif node_name == "evaluator":
            if current_state["evaluation_attempts"] == 0:
                yield format_status("evaluator", "Fact validated and secured.")
            else:
                yield format_status("evaluator", "Data insufficient. Adjusting parameters and digging deeper...")
                
    yield format_status("synthesizer", "Synthesizing final highly-cited report...")
    
    # Compile the validated facts block
    facts_block = ""
    for idx, f in enumerate(current_state["verified_facts"]):
        facts_block += f"Fact [{idx+1}]: {f['fact']}\nSource URL: {f['url']}\n\n"

    # SHORT-CIRCUIT SAFETY EDGE: Prevent 8B hallucination if zero facts are returned
    if not facts_block.strip():
        yield f"data: {json.dumps({'type': 'delta', 'content': 'The deep research protocol could not extract verified data for this query from the target sources. Please refine your search parameters.'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    system_prompt = (
        f"{mode_cfg.system_prompt}\n\n"
        "You are a strict technical research synthesizer. Your ONLY job is to write a comprehensive report using strictly the facts provided below.\n\n"
        "HARD TECHNICAL RULES:\n"
        "1. DO NOT invent or extrapolate features. If a detail is not in the VERIFIED FACTS MATRIX, do not mention it.\n"
        "2. Keep real-world hardware architecture accurate. The Ryzen 7 9800X3D is Zen 5. Do NOT reference legacy Zen 3 utilities.\n"
        "3. Explicitly distinguish between motherboard BIOS settings (like PBO, Curve Optimizer) and operating system parameters (like Linux kernel boot flags, amd_pstate, cpufreq scaling governors).\n\n"
        "CRITICAL RULE FOR CITATIONS:\n"
        "You MUST use inline markdown links immediately after stating a fact. [Source](url). No reference lists at the bottom.\n\n"
        "VERIFIED FACTS MATRIX:\n"
        f"{facts_block}"
    )
    
    final_content = ""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            settings.LOCAL_LLM_URL + "/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": payload.query}
                ], 
                "temperature": 0.2, 
                "stream": True
            },
            timeout=120.0
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line.replace("data: ", "")
                    if data_str.strip() == "[DONE]": break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            final_content += delta
                            yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"
                    except:
                        pass

    # Commit the interaction back to memory_app so follow-up queries maintain deep research history
    new_past_messages = past_messages + [
        {"role": "user", "content": payload.query},
        {"role": "assistant", "content": final_content}
    ]
    await memory_app.ainvoke(
        {"summary": current_chat.get("summary", ""), "messages": new_past_messages},
        config=config
    )

    yield "data: [DONE]\n\n"