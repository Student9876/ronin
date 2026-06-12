from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Dict, Literal

class ModeSettings(BaseModel):
    mode_id: Literal["general", "deep", "code"]
    model_name: str
    temperature: float
    max_tokens: int
    system_prompt: str

class AgentConfigMatrix(BaseSettings):
    # Core Infrastructure Endpoints
    # host.docker.internal allows the Docker container to exit safely to the host machine's ports
    LOCAL_LLM_URL: str = "http://host.docker.internal:1234/v1"
    SEARXNG_URL: str = "http://searxng:8080/search"
    QDRANT_URL: str = "http://qdrant:6333"
    OLLAMA_EMBED_URL: str = "http://ollama:11434/api/embeddings"
    DATABASE_URL: str = "sqlite:///ronin_database.db"

    # Strict System Constraints Matrix
    MODES: Dict[str, ModeSettings] = {
        "general": ModeSettings(
            mode_id="general",
            model_name="meta-llama-3-8b-instruct",
            temperature=0.7,
            max_tokens=2048,
            system_prompt="You are a precise local terminal assistant. Provide direct, objective answers. No sugar-coating."
        ),
        "deep": ModeSettings(
            mode_id="deep",
            model_name="meta-llama-3-8b-instruct", 
            temperature=0.1, # Drop temperature close to zero to force rigid fact synthesis
            max_tokens=4096,
            system_prompt="You are a lead synthesis supervisor. Compile fragmented grounding artifacts into high-density reference dossiers."
        ),
        "code": ModeSettings(
            mode_id="code",
            model_name="meta-llama-3-8b-instruct",
            temperature=0.0, # Zero variance required for exact code syntax generation
            max_tokens=4096,
            system_prompt="You are a senior systems developer. Generate strict semantic implementations using provided AST syntax code blocks."
        )
    }

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = AgentConfigMatrix()