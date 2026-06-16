import logging
from typing import TypedDict, Annotated, Sequence, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from src.utils.llm_client import call_local_llm_structured

logger = logging.getLogger(__name__)

class MemoryState(TypedDict):
    """
    Isolated state schema for conversation history management.
    Uses standard message sequence accumulation or primitive dict lists.
    """
    messages: list
    summary: str


class ConversationSummary(BaseModel):
    summary: str = Field(description="A concise, high-density summary of the conversation history so far.")

async def compact_history(state: MemoryState) -> dict:
    """
    Node: Detects when the message backlog exceeds safety boundaries 
    and squashes older blocks into a high-density rolling context summary.
    """
    messages = state.get("messages", [])
    
    # Defensive execution: if history is shallow, bypass compaction entirely
    if len(messages) <= 6:
        return {"messages": []}

    logger.info(f"Compaction triggered. Processing {len(messages)} historical records.")
    
    # Keep the latest 2 messages to maintain immediate operational context
    preserved_messages = messages[-2:]
    messages_to_summarize = messages[:-2]

    # Invoke our centralized LLM client helper to generate the summary
    system_prompt = (
        "You are an expert conversation summarizer. Synthesize the provided dialogue history "
        "into a single high-density summary paragraph. Retain key facts, products mentioned, "
        "user settings, and past decisions."
    )
    user_prompt = "\n".join([f"{m.get('role', 'unknown').capitalize()}: {m.get('content', '')}" for m in messages_to_summarize])
    
    try:
        result = await call_local_llm_structured(system_prompt, user_prompt, ConversationSummary)
        summary = result.summary
    except Exception as e:
        logger.error(f"Failed to generate rolling context summary: {e}")
        summary = "Prior conversation summarized to maintain context boundaries."

    return {
        "messages": preserved_messages,
        "summary": summary
    }

def route_compaction(state: MemoryState) -> Literal["compact", "__end__"]:
    """
    Conditional Edge Router: Evaluates whether the active state window
    requires compression before handing execution back to the client transport.
    """
    if len(state.get("messages", [])) > 6:
        return "compact"
    return "__end__"

# Initialize ephemeral in-memory checkpointer for thread-isolated tracking
checkpointer = MemorySaver()

# Build the independent memory sub-graph
workflow = StateGraph(MemoryState)

# Define nodes
workflow.add_node("compact", compact_history)

# Define structural routing
workflow.add_conditional_edges(
    START,
    route_compaction,
    {
        "compact": "compact",
        "__end__": END
    }
)

workflow.add_edge("compact", END)

# Compile the final standalone checkpointer application
memory_app = workflow.compile(checkpointer=checkpointer)

async def bootstrap_memory_state(thread_id: int):
    """
    Ensures the LangGraph checkpointer is bootstrapped with historical messages 
    from the SQLite database if no state is currently present.
    """
    config = {"configurable": {"thread_id": str(thread_id)}}
    state_snapshot = memory_app.get_state(config)
    
    # If the checkpointer is completely empty or missing messages, bootstrap from database
    if not state_snapshot or not state_snapshot.values or not state_snapshot.values.get("messages"):
        from src.config.database import engine, Message
        from sqlmodel import Session, select
        
        with Session(engine) as session:
            statement = select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at.asc())
            db_messages = session.exec(statement).all()
            
        if db_messages:
            # Reconstruct the past messages list
            past_messages = []
            for msg in db_messages:
                # Map to standard role/content dicts that the graphs expect
                past_messages.append({"role": msg.role, "content": msg.content})
                
            # If the database has messages, populate them. 
            # Note: the compaction router will automatically compact them if they exceed 6 messages on initialization
            await memory_app.ainvoke(
                {"summary": "", "messages": past_messages},
                config=config
            )