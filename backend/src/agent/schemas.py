from pydantic import BaseModel, Field
from typing import List, Dict
from typing_extensions import TypedDict

# --- LLM PROTOCOLS ---

class ResearchPlan(BaseModel):
    queries: List[str] = Field(..., description="Targeted natural language search queries.")
    rationale: str = Field(..., description="Brief strategic reasoning under 15 words.")

class PageEvaluation(BaseModel):
    is_valid_fact_source: bool = Field(..., description="True ONLY if the text contains specific, objective facts about the target topic. False if it is SEO spam, a tutorial, dictionary definition, or irrelevant.")

class ExtractedFact(BaseModel):
    source_url: str = Field(..., description="The exact source URL.")
    exact_quote: str = Field(..., description="CRITICAL: An exact, word-for-word quote from the text that contains the data. Do not summarize.")
    synthesized_insight: str = Field(..., description="A clean, professional synthesis of what that quote means.")

class AnalysisPayload(BaseModel):
    facts: List[ExtractedFact] = Field(default_factory=list)

# --- LANGGRAPH STATE CONTRACT ---

class RoninState(TypedDict):
    topic: str
    objective: str
    max_depth: int
    current_depth: int
    queries: List[str]
    source_manifest: Dict[str, str]
    raw_findings: List[Dict]
    final_report: str
    
class ResearchAgentState(TypedDict):
    query: str                      # Original user research topic
    search_queries: List[str]       # Generated search terms for engines
    sources: List[Dict[str, str]]   # Scraped raw data: [{"url": "...", "content": "..."}]
    current_step: str               # Tracker for the active executing node
    report: str                     # The accumulating final markdown text