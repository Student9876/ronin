import json
from typing import Dict, List, Any

from src.config.agent_config import settings
from src.utils.network import get_http_client
import asyncio
from src.agent.tools.ingestion import ingest_url
from src.agent.memory import memory_app, bootstrap_memory_state
from src.utils.llm_client import llm_client

async def stream_chat(payload: Any, mode_cfg: Any):
    """The foreground stream handler triggered by the FastAPI router wrapper with a dynamic ReAct agent loop."""
    thread_id = payload.thread_id
    query = payload.query
    
    # Bootstrap the LangGraph checkpointer memory from SQL history if empty
    await bootstrap_memory_state(thread_id)
    
    # 1. Retrieve the active context from LangGraph Checkpointer
    config = {"configurable": {"thread_id": str(thread_id)}}
    state_snapshot = memory_app.get_state(config)
    current_state = state_snapshot.values if state_snapshot else {}
    
    summary = current_state.get("summary", "")
    past_messages = current_state.get("messages", [])

    # Yield initial state telemetry event
    yield f"data: {json.dumps({'type': 'state', 'data': {'thread_id': thread_id, 'query': query, 'summary': summary, 'sources_scraped': 0}})}\n\n"

    # Define tools schemas for Gemini (OpenAI compatible format)
    tools_schema = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Queries SearXNG search engine for real-time web results when the user requests information that requires current web search data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query keywords to look up."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results to return (default 3)."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "ingest_url",
                "description": "Fetches and extracts full text content from a specific URL. Use this to scrape the details of a specific web page returned by search results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The absolute URL of the web page to scrape."
                        },
                        "subtopic": {
                            "type": "string",
                            "description": "The topic or query keywords corresponding to this scrape."
                        }
                    },
                    "required": ["url", "subtopic"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "vector_search",
                "description": "Searches previously scraped documents and vector-indexed contexts strictly within the current thread to answer questions using history.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Semantic search query."
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of relevant chunks to retrieve (default 3)."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # Build ReAct Prompt Instructions
    system_prompt = (
        f"{mode_cfg.system_prompt}\n\n"
        "You are a helpful, advanced AI coding and research agent. You have access to real-time tools for search, web page scraping, and vector search in your database.\n"
        "Strict Guidelines:\n"
        "1. Actively use the web_search tool if the user's request requires fresh real-world information, technical specifications, or latest releases.\n"
        "2. After searching, use ingest_url on the most promising results to scrape deep information. Never answer with placeholder knowledge when you can scrape live sources.\n"
        "3. If referencing facts retrieved from a scraped page, you MUST cite the source inline. Use format: [Source](url).\n"
        "4. Use vector_search if the user is asking about previous contexts or documents you ingested in this thread.\n"
        "5. Execute tools as needed, analyze results, and respond directly to the user when you are done."
    )

    llm_messages = [{"role": "system", "content": system_prompt}]
    if summary:
        llm_messages.append({"role": "system", "content": f"Established Context Summary:\n{summary}"})
    
    # Query and inject cross-thread long-term semantic memories
    try:
        from src.agent.tools.long_term_memory import long_term_memory
        lt_memories = await long_term_memory.retrieve_long_term_memories(query, limit=2)
        if lt_memories:
            memories_block = "\n".join([f"- {m}" for m in lt_memories])
            llm_messages.append({
                "role": "system", 
                "content": (
                    "Cross-Thread Historical Memories (Context retrieved from other sessions):\n"
                    f"{memories_block}\n"
                    "Use this historical context if it is relevant to the user's current request."
                )
            })
    except Exception as e:
        print(f"Failed to retrieve long-term memories: {e}")
    
    # Extend conversation history
    llm_messages.extend(past_messages)
    llm_messages.append({"role": "user", "content": query})

    MAX_TURNS = 5
    turn = 0
    final_content = ""
    
    from src.agent.tools.registry import execute_tool

    while turn < MAX_TURNS:
        turn += 1
        
        try:
            response = await llm_client.chat.completions.create(
                model=mode_cfg.model_name,
                messages=llm_messages,
                temperature=mode_cfg.temperature,
                max_tokens=mode_cfg.max_tokens,
                tools=tools_schema
            )
        except Exception as e:
            error_msg = f"LLM client call error: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
            yield "data: [DONE]\n\n"
            return
            
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        
        if tool_calls:
            # Parse assistant message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in tool_calls
                ]
            }
            llm_messages.append(assistant_msg)
            
            # Execute tools
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments
                
                try:
                    tool_args = json.loads(tool_args_str)
                except Exception:
                    tool_args = {}
                    
                yield f"data: {json.dumps({'type': 'status', 'node': tool_name, 'message': f'Executing agent tool: {tool_name}...' })}\n\n"
                
                if tool_name in ["ingest_url", "vector_search"]:
                    tool_args["thread_id"] = thread_id
                    
                try:
                    result, telemetry = await execute_tool(tool_name, **tool_args)
                except Exception as e:
                    result = f"Error executing tool {tool_name}: {e}"
                    telemetry = {
                        "name": tool_name,
                        "status": "failed",
                        "input": tool_args,
                        "output": str(e),
                        "duration_ms": 0
                    }
                    
                yield f"data: {json.dumps({'type': 'tool', 'data': telemetry })}\n\n"
                
                tool_response_msg = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(result)
                }
                llm_messages.append(tool_response_msg)
            
            continue
        else:
            # Final text response
            content = message.content or ""
            final_content = content
            
            # Simulate streaming delta to the frontend
            chunk_size = 12
            for i in range(0, len(content), chunk_size):
                delta = content[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'delta', 'content': delta})}\n\n"
                await asyncio.sleep(0.01)
                
            break

    # Save conversation state in LangGraph checkpointer
    new_past_messages = past_messages + [
        {"role": "user", "content": query},
        {"role": "assistant", "content": final_content}
    ]
    
    await memory_app.ainvoke(
        {"summary": summary, "messages": new_past_messages},
        config=config
    )

    yield "data: [DONE]\n\n"