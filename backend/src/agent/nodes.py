import logging
import asyncio
import instructor
from openai import OpenAI
from src.agent.schemas import RoninState, ResearchPlan, AnalysisPayload, PageEvaluation
from src.agent.tools import WebScraperTool

logger = logging.getLogger(__name__)

# Initialize local LLM backend
raw_client = OpenAI(base_url="http://host.docker.internal:1234/v1", api_key="lm-studio")
ai_client = instructor.from_openai(raw_client, mode=instructor.Mode.JSON_SCHEMA)

# Persistent tool runtime across graph loops
shielded_runtime = WebScraperTool(max_concurrent=2)

async def plan_research_step(state: RoninState) -> dict:
    """Evaluates objective and outputs clean search targets."""
    topic = state["topic"]
    objective = state["objective"]
    depth = state.get("current_depth", 0)

    prompt = (
        f"Topic: {topic}\nObjective: {objective}\nResearch Depth Level: {depth}\n\n"
        f"Generate exactly 3 highly specific, natural-language search queries.\n"
        f"CRITICAL RULES:\n"
        f"1. DO NOT use boolean operators (AND, OR, parentheses). They will break the search engine.\n"
        f"2. Keep the 'rationale' under 15 words.\n"
        f"3. Write queries as standard targeted searches (e.g., 'solid state battery mass production Wh/kg 2026')."
    )
    
    try:
        plan: ResearchPlan = ai_client.chat.completions.create(
            model="meta-llama-3-8b-instruct",
            response_model=ResearchPlan,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800
        )
        return {"queries": plan.queries, "current_depth": depth + 1}
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return {"queries": [topic], "current_depth": depth + 1}

async def execute_scraping_cycle(state: RoninState) -> dict:
    """Fetches candidates and forces the LLM to evaluate them before memory insertion."""
    queries = state["queries"]
    topic = state["topic"]
    
    # 1. Fetch raw candidates concurrently
    tasks = [shielded_runtime.fetch_candidates(q) for q in queries]
    candidate_lists = await asyncio.gather(*tasks)
    
    # Flatten the lists of dictionaries
    all_candidates = [item for sublist in candidate_lists for item in sublist]
    
    manifest_updates = {}
    
    # 2. The Logic Gate: Evaluate every single snippet
    for candidate in all_candidates:
        prompt = (
            f"Topic Focus: {topic}\n\n"
            f"Evaluate this scraped web text. Is it a legitimate, highly-relevant source containing objective data about the topic? "
            f"Or is it SEO spam, a tutorial, dictionary definition, or irrelevant noise?\n\n"
            f"TITLE: {candidate['title']}\nTEXT: {candidate['content'][:800]}"
        )
        
        try:
            eval_result: PageEvaluation = ai_client.chat.completions.create(
                model="meta-llama-3-8b-instruct",
                response_model=PageEvaluation,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=50
            )
            
            if eval_result.is_valid_fact_source:
                logger.info(f"[ACCEPTED] Quality Data Found: {candidate['url']}")
                shielded_runtime.embed_passed_candidate(candidate)
                manifest_updates[candidate['url']] = candidate['title']
            else:
                logger.warning(f"[REJECTED] Spam/Irrelevant: {candidate['url']}")
                
        except Exception as e:
            logger.error(f"Evaluation failed for {candidate['url']}: {e}")

    current_manifest = state.get("source_manifest", {}) or {}
    current_manifest.update(manifest_updates)
        
    return {"source_manifest": current_manifest}

async def analyze_and_extract(state: RoninState) -> dict:
    """Extracts strictly grounded quotes to prevent hallucination."""
    topic = state["topic"]
    objective = state["objective"]
    
    # Target search specifically against the core objective
    focused_context = shielded_runtime.gather_semantic_context(
        target_query=f"{topic} {objective}", 
        top_k=6
    )

    prompt = (
        f"Topic: {topic}\nObjective: {objective}\n\n"
        f"Extract high-density facts from the context below. "
        f"CRITICAL: You MUST pull exact, word-for-word quotes to back up your facts. "
        f"If the context contains no relevant facts, return an empty list.\n\n"
        f"CONTEXT BLOCK:\n{focused_context}"
    )
    try:
        # Enforce structural contracts on extraction
        analysis: AnalysisPayload = ai_client.chat.completions.create(
            model="meta-llama-3-8b-instruct",
            response_model=AnalysisPayload,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=1500
        )
        
        # Stashing raw facts inside state for the final synthesis pass
        existing_facts = state.get("raw_findings", []) or []
        new_facts = [f.model_dump() for f in analysis.facts]
        
        return {"raw_findings": existing_facts + new_facts}
    except Exception as e:
        logger.error(f"Extraction step failed: {e}")
        return {}

async def synthesize_conclusion(state: RoninState) -> dict:
    """Generates the final comprehensive production markdown dossier."""
    facts = state.get("raw_findings", []) or []
    manifest = state.get("source_manifest", {}) or {}
    
    # Map the new schema fields into the prompt string
    compiled_facts = "\n".join([
        f"- {f['synthesized_insight']} (Source: {f['source_url']})\n  * VERIFIED QUOTE: \"{f['exact_quote']}\""
        for f in facts
    ])
    citations = "\n".join([f"- [{title}]({url})" for url, title in manifest.items()])

    prompt = (
        f"Synthesize an authoritative, exhaustive deep research report on: {state['topic']}.\n"
        f"Core Directive: {state['objective']}\n\n"
        f"EXTRACTED DATA CORE:\n{compiled_facts}\n\n"
        f"Produce a complete, structured markdown document. "
        f"CRITICAL: Ground your entire report ONLY on the provided Extracted Data Core. "
        f"If the data core is empty, write a single paragraph stating that no verified data passed the security filters."
    )
    try:
        completion = raw_client.chat.completions.create(
            model="meta-llama-3-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=3000
        )
        report = completion.choices[0].message.content
        final_markdown = f"{report}\n\n## References & Discovered Sources\n{citations}"
        return {"final_report": final_markdown}
    except Exception as e:
        logger.error(f"Dossier synthesis failed: {e}")
        return {"final_report": "# Synthesis Failure\nContext limits or model execution errored out."}