import json
import httpx
import re
from typing import Any, List

from src.config.agent_config import settings

def _salvage_queries(raw_text: str, default_query: str) -> List[str]:
    """Attempts to regex-rip the queries out of broken JSON. If failed, builds a dense keyword query."""
    # 1. Regex attempt: Find anything inside brackets that looks like a string array
    match = re.search(r'\[(.*?)\]', raw_text, re.DOTALL)
    if match:
        items = re.findall(r'"([^"]+)"', match.group(1))
        # Filter out schema placeholders
        valid_items = [x for x in items if x != "sub_queries" and len(x.strip()) > 0]
        if len(valid_items) >= 1:
            return valid_items[:3]
            
    # 2. Stop-word keyword extraction (Drops "I", "am", "what", "are", etc.)
    stop_words = {"i", "am", "is", "are", "what", "how", "the", "a", "an", "to", "for", "with", "on", "in", "of", "and", "my", "build", "planning", "intend", "run", "as", "daily", "driver"}
    words = [w for w in default_query.split() if w.lower() not in stop_words and len(w) > 2]
    
    # Take the top 5 densest keywords (e.g., "AMD Ryzen 9800X3D Arch Linux")
    safe_query = " ".join(words[:6]).replace("?", "").replace(".", "").replace(",", "")
    
    return [
        f"{safe_query}",
        f"{safe_query} specifications",
        f"{safe_query} reddit"
    ]

def _generate_fallback(response_model: Any, user_prompt: str, raw_llm_text: str = "") -> Any:
    """Generates a safe fallback object based on the expected schema if JSON parsing completely fails."""
    if response_model.__name__ == "ResearchChecklist":
        salvaged = _salvage_queries(raw_llm_text, user_prompt)
        return response_model(sub_queries=salvaged)
        
    elif response_model.__name__ == "FactEvaluation":
        return response_model(is_valuable=False, key_finding="")
    
    return response_model.construct() if hasattr(response_model, "construct") else response_model()

def _find_list_deep(d: Any, target_key: str = "sub_queries") -> List[str]:
    """Aggressive deep scanner to pull arrays out of any schema-echoing dictionary structures."""
    if isinstance(d, dict):
        # 1. If the dict is explicitly a JSON schema definition, do not parse it for values
        if d.get("type") == "object" and "properties" in d:
            return []
            
        if target_key in d and isinstance(d[target_key], list):
            # 2. Prevent extracting the property name if the model echoed it
            cleaned = [str(x) for x in d[target_key] if str(x) != target_key]
            if cleaned:
                return cleaned
                
        if target_key in d and isinstance(d[target_key], dict):
            sq = d[target_key]
            if "default" in sq and isinstance(sq["default"], list):
                cleaned = [str(x) for x in sq["default"] if str(x) != target_key]
                if cleaned: return cleaned
            if "example" in sq and isinstance(sq["example"], list):
                cleaned = [str(x) for x in sq["example"] if str(x) != target_key]
                if cleaned: return cleaned
                
        if "default" in d and isinstance(d["default"], list):
            cleaned = [str(x) for x in d["default"] if str(x) != target_key]
            if cleaned: return cleaned
            
        for key, val in d.items():
            # 3. CRITICAL: Never extract the "required" array from a schema string
            if key in ["required", "type", "description"]:
                continue
            found = _find_list_deep(val, target_key)
            if found:
                return found
                
    elif isinstance(d, list):
        if all(isinstance(x, str) for x in d) and len(d) > 0:
            # 4. A real search query is longer than a single schema word
            cleaned = [x for x in d if x != target_key]
            if cleaned and len(cleaned[0]) > 3:
                return cleaned
        for item in d:
            found = _find_list_deep(item, target_key)
            if found:
                return found
                
    return []

async def call_local_llm_structured(system_prompt: str, user_prompt: str, response_model: Any) -> Any:
    """Forces the local model to return JSON and aggressively extracts data even if the model echoes the schema."""
    schema_json = response_model.schema_json() if hasattr(response_model, "schema_json") else response_model.model_json_schema()
    
    enforced_system = (
        f"{system_prompt}\n\n"
        f"OUTPUT FORMAT: Return ONLY a valid JSON object matching this schema format:\n{schema_json}\n"
        "Return ONLY the JSON object. No markdown. No conversational text. No 'Here is your JSON'. "
        "If you include any text outside the curly braces, the system will crash."
    )
    
    raw_json = ""
    async with httpx.AsyncClient() as client:
        try:
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
        except Exception as e:
            print(f"Network error calling LLM: {e}")
            return _generate_fallback(response_model, user_prompt, raw_json)
        
        # Strip markdown wrapping
        if "```json" in raw_json:
            raw_json = raw_json.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_json:
            raw_json = raw_json.split("```")[1].split("```")[0].strip()
            
        # Isolate the core JSON object
        start_idx = raw_json.find('{')
        end_idx = raw_json.rfind('}')
        if start_idx != -1 and end_idx != -1:
            raw_json = raw_json[start_idx:end_idx+1]
            
        try:
            parsed_data = json.loads(raw_json)
        except Exception as e:
            print(f"Raw JSON parsing failed: {e}. Falling back to regex salvage.")
            return _generate_fallback(response_model, user_prompt, raw_json)
            
        if response_model.__name__ == "ResearchChecklist":
            extracted = _find_list_deep(parsed_data)
            if extracted:
                return response_model(sub_queries=extracted[:3])

        # Standard structural fallback for schemas
        try:
            if hasattr(response_model, "model_validate"):
                return response_model.model_validate(parsed_data)
            return response_model.parse_obj(parsed_data)
        except Exception:
            if "properties" in parsed_data:
                parsed_data = parsed_data["properties"]
            
            if "sub_queries" in parsed_data and isinstance(parsed_data["sub_queries"], dict):
                if "default" in parsed_data["sub_queries"]:
                    parsed_data["sub_queries"] = parsed_data["sub_queries"]["default"]
                    
            try:
                if hasattr(response_model, "model_validate"):
                    return response_model.model_validate(parsed_data)
                return response_model.parse_obj(parsed_data)
            except Exception as e:
                print(f"Pydantic schema validation failed: {e}")
                return _generate_fallback(response_model, user_prompt, raw_json)