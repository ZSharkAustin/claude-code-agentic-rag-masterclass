from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    langsmith_api_key: str = ""
    langsmith_project: str = "rag-masterclass"
    langsmith_tracing: str = "true"
    frontend_url: str = "http://localhost:5173"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
