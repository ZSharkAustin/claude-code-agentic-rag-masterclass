from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str = ""
    openai_api_key: str
    openai_embedding_model: str = "text-embedding-3-small"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    langsmith_api_key: str = ""
    langsmith_project: str = "rag-masterclass"
    langsmith_tracing: str = "true"
    frontend_url: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
