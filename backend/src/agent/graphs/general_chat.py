import json
from typing import Dict, List, Any
from openai import AsyncOpenAI

from src.config.agent_config import settings
from src.utils.network import get_http_client
from src.agent.tools.ingestion import ingest_url
from src.agent.memory import memory_app

# Initialize local LLM client globally for this module
client = AsyncOpenAI(base_url=settings.LOCAL_LLM_URL, api_key="lm-studio")

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
                
            # Yield tool telemetry event
            yield f"data: {json.dumps({'type': 'tool', 'data': {'name': 'SearXNG Web Search & Scrape', 'status': 'completed', 'input': {'query': query}, 'output': f'Successfully scraped {len(source_links)} source URLs: ' + ', '.join([l['url'] for l in source_links])}})}\n\n"
    except Exception as e:
        print(f"General mode live web lookup fallback: {e}")

    # Yield state telemetry event
    yield f"data: {json.dumps({'type': 'state', 'data': {'thread_id': thread_id, 'query': query, 'summary': summary, 'sources_scraped': len(source_links)}})}\n\n"

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