from langgraph.graph import StateGraph, END
from src.agent.schemas import RoninState
from src.agent.nodes import (
    plan_research_step,
    execute_scraping_cycle,
    analyze_and_extract,
    synthesize_conclusion
)

def depth_check_router(state: RoninState) -> str:
    """Routes the agent loop based on maximum target execution depth."""
    if state.get("current_depth", 0) >= state.get("max_depth", 2):
        return "synthesize"
    return "plan"

# Instantiate clean graph workflow
workflow = StateGraph(RoninState)

# Add processing actors
workflow.add_node("plan", plan_research_step)
workflow.add_node("scrape", execute_scraping_cycle)
workflow.add_node("extract", analyze_and_extract)
workflow.add_node("synthesize", synthesize_conclusion)

# Establish execution paths
workflow.set_entry_point("plan")
workflow.add_edge("plan", "scrape")
workflow.add_edge("scrape", "extract")

# Set up the loop boundary
workflow.add_conditional_edges(
    "extract",
    depth_check_router,
    {
        "plan": "plan",
        "synthesize": "synthesize"
    }
)

workflow.add_edge("synthesize", END)

# Compile executable graph interface
app = workflow.compile()
