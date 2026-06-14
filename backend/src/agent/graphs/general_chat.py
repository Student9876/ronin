import json
from typing import Dict, List, Any, TypedDict
from openai import AsyncOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.config.agent_config import settings
from src.utils.network import get_http_client
from src.agent.tools.ingestion import ingest_url

# Initialize local LLM client globally for this module
client = AsyncOpenAI(base_url=settings.LOCAL_LLM_URL, api_key="lm-studio")

# Initialize LangGraph Checkpointer (In-memory state for context management)
memory = MemorySaver()

class MemoryState(TypedDict):
    summary: str
    messages: List[Dict[str, str]]

async def compact_history(state: MemoryState) -> Dict[str, Any]:
    """Background graph node to compress old messages into a persistent summary."""
    cfg = settings.MODES["general"]
    messages = state.get("messages", [])
    current_summary = state.get("summary", "")
    
    # Take the oldest 4 messages to summarize, retain the 2 most recent for immediate context
    old_msgs = messages[:4]
    retained_msgs = messages[4:]
    
    dialogue = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in old_msgs])
    
    prompt = f"""Synthesize a dense, ongoing summary of the user's conversation.
Previous Summary: {current_summary if current_summary else 'None.'}

New Dialogue to Compress:
{dialogue}

Return ONLY the updated summary text. Do not add conversational filler.
"""
    try:
        response = await client.chat.completions.create(
            model=cfg.model_name,
            messages=[
                {"role": "system", "content": "You are a highly efficient memory management process."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        new_summary = response.choices[0].message.content.strip()
        return {"summary": new_summary, "messages": retained_msgs}
    except Exception as e:
        print(f"Background compaction failed: {e}")
        return {}

def route_compaction(state: MemoryState) -> str:
    """Routing logic: Only run the compactor if history exceeds 6 messages."""
    msgs = state.get("messages", [])
    if len(msgs) > 6:
        return "compact_history"
    return END

# Construct the Background Graph
workflow = StateGraph(MemoryState)
workflow.add_node("compact_history", compact_history)
workflow.add_conditional_edges(START, route_compaction)
workflow.add_edge("compact_history", END)

memory_app = workflow.compile(checkpointer=memory)

async def stream_chat(payload: Any, mode_cfg: Any):
    """The foreground stream handler triggered by the FastAPI router wrapper with forced citation indexing."""
    thread_id = payload.thread_id
    query = payload.query
    
    # 1. Retrieve the active context from LangGraph Checkpointer
    config = {"configurable": {"thread_id": str(thread_id)}}
    state_snapshot = memory_app.get_state(config)
    current_state = state_snapshot.values if state_snapshot else {}
    
    summary = current_state.get("summary", "")
    past_messages = current_state.get("messages", [])
    
    # 2. Executing fast one-shot web scrape layer with link mapping
    scraped_context = ""
    source_links = []
    try:
        yield f"data: {json.dumps({'type': 'status', 'node': 'web_search', 'message': 'Searching the web for real-time data...'})}\n\n"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        async with get_http_client() as network_client:
            search_res = await network_client.get(settings.SEARXNG_URL, params={"q": query, "format": "json"}, headers=headers)
            results = []
            if search_res.status_code == 200:
                try:
                    results = search_res.json().get("results", [])[:2]
                except Exception as e:
                    print(f"General mode search JSON parse failed: {e}")
            
            idx = 1
            blocks = []
            for res in results:
                url = res.get("url")
                if not url: continue
                text = await ingest_url(thread_id=thread_id, subtopic=query, url=url)
                if not text.startswith("Failed") and not text.startswith("No parseable"):
                    # Limit chunk length per source to prevent blinding an 8B model
                    truncated_text = text[:1500] 
                    blocks.append(f"--- START SOURCE [{idx}] ---\nURL: {url}\nCONTENT:\n{truncated_text}\n--- END SOURCE [{idx}] ---")
                    source_links.append({"idx": idx, "url": url})
                    idx += 1
            
            if blocks:
                scraped_context = "\n\n".join(blocks)
    except Exception as e:
        print(f"General mode live web lookup fallback: {e}")

    # 3. Build VRAM-Optimized Prompt Block with Strict Citation Mandate
    system_prompt = mode_cfg.system_prompt
    if scraped_context:
        citation_instructions = "\n\nCRITICAL INSTRUCTION FOR CITATIONS:\n"
        for link in source_links:
            citation_instructions += f"Source [{link['idx']}] corresponds to the exact URL: {link['url']}\n"
        
        citation_instructions += (
            "\nYou must back up every factual assertion, troubleshooting step, or specification extracted from the web text "
            "by embedding its precise URL inline as a markdown link. "
            "Example format: 'According to community reports, flashing firmware version 1.0.4 resolves the tracking loss [Source](https://example.com/actual-link).'\n"
            "Do not omit the markdown link structure. Do not list references at the bottom without inline markdown links."
        )
        system_prompt += citation_instructions

    llm_messages = [{"role": "system", "content": system_prompt}]
    
    if summary:
        llm_messages.append({"role": "system", "content": f"Established Context Summary:\n{summary}"})
        
    if scraped_context:
        llm_messages.append({"role": "system", "content": f"Verified Live Web Documents:\n{scraped_context}"})
        
    llm_messages.extend(past_messages)
    llm_messages.append({"role": "user", "content": query})
    
    # 4. Stream response back to the UI via the router wrapper
    final_content = ""
    try:
        response_stream = await client.chat.completions.create(
            model=mode_cfg.model_name,
            messages=llm_messages,
            temperature=mode_cfg.temperature,
            max_tokens=mode_cfg.max_tokens,
            stream=True
        )
        
        async for chunk in response_stream:
            delta = chunk.choices[0].delta.content
            if delta:
                final_content += delta
                yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"
                
    except Exception as e:
        error_msg = f"Local LLM streaming error: {str(e)}"
        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
        yield "data: [DONE]\n\n"
        return
        
    # 5. Push the new interaction into LangGraph to trigger background memory management
    new_past_messages = past_messages + [
        {"role": "user", "content": query},
        {"role": "assistant", "content": final_content}
    ]
    
    await memory_app.ainvoke(
        {"summary": summary, "messages": new_past_messages},
        config=config
    )

    # 6. The Stream Kill Signal
    yield "data: [DONE]\n\n"