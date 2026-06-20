from pydantic import BaseModel
from pydantic_settings import BaseSettings
from typing import Dict, Literal, Optional

class ModeSettings(BaseModel):
    mode_id: Literal["general", "deep", "code"]
    model_name: str
    temperature: float
    max_tokens: int
    system_prompt: str

class AgentConfigMatrix(BaseSettings):
    # Core Infrastructure Endpoints
    # host.docker.internal allows the Docker container to exit safely to the host machine's ports
    LLM_BASE_URL: str = "http://host.docker.internal:1234/v1"
    LLM_API_KEY: str = "lm-studio"
    LOCAL_LLM_URL: Optional[str] = None  # Legacy support fallback

    GENERAL_MODEL: str = "meta-llama-3-8b-instruct"
    DEEP_MODEL: str = "meta-llama-3-8b-instruct"
    CODE_MODEL: str = "meta-llama-3-8b-instruct"

    SEARXNG_URL: str = "http://searxng:8080/search"
    QDRANT_URL: str = "http://qdrant:6333"
    EMBEDDING_MODEL: str = "gemini-embedding-2"
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

    def model_post_init(self, __context):
        # Sync legacy env var name if set
        if self.LOCAL_LLM_URL:
            self.LLM_BASE_URL = self.LOCAL_LLM_URL
        else:
            self.LOCAL_LLM_URL = self.LLM_BASE_URL

        # Dynamically override the configuration matrix with env overrides
        self.MODES["general"].model_name = self.GENERAL_MODEL
        self.MODES["deep"].model_name = self.DEEP_MODEL
        self.MODES["code"].model_name = self.CODE_MODEL

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = AgentConfigMatrix()