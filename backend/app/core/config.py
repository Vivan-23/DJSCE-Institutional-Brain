from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode
from typing import Annotated, List


class Settings(BaseSettings):
    PROJECT_NAME: str = "Company Brain API"
    VERSION: str = "1.0.0"

    # Databases
    DATABASE_URL: str = "postgresql://company_brain_user:brain_secure_pass@localhost:5432/company_brain_db"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "brain_graph_pass"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    REDIS_URL: str = "redis://localhost:6379/0"

    # Required secrets — no defaults; must be set via .env or environment
    GROQ_API_KEY: str
    SECRET_KEY: str

    # LLM — model used for RAG, extraction, and the Company PA. A high-capability
    # model improves extraction/PA reasoning; override via env for production.
    LLM_MODEL: str = "openai/gpt-oss-120b"

    # Company PA — end-of-day check-in time (local hour, 24h) per employee timezone
    PA_CHECKIN_HOUR: int = 17
    # A commitment with no update for this many hours is eligible for a follow-up
    COMMITMENT_FOLLOWUP_HOURS: int = 48

    # JWT
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # CORS — accepts a comma-separated string (env/.env) or a list (code default).
    # NoDecode disables pydantic-settings' default JSON parsing so a plain string
    # like "http://localhost:3000,http://localhost:3001" is handled by the validator.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"


settings = Settings()

# Apply per-company overrides from company.yaml (single source of truth). Kept
# out of the Settings class so a bad/missing profile can never break boot.
try:
    from app.core.company_config import get_company_config

    _company = get_company_config()
    settings.PA_CHECKIN_HOUR = _company.pa_checkin_hour
    settings.COMMITMENT_FOLLOWUP_HOURS = _company.commitment_followup_hours
except Exception:  # noqa: BLE001
    pass
