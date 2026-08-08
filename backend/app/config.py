from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    noor_env: str = 'development'
    database_url: str = 'sqlite+aiosqlite:///./noor.db'
    qdrant_url: str = 'http://localhost:6333'
    redis_url: str = 'redis://localhost:6379/0'
    llm_mode: str = 'hybrid'
    local_llm_base_url: str = 'http://localhost:11434'
    local_model_name: str = 'local-model'
    cloud_model_name: str = 'gpt-4.1-mini'
    openai_api_key: str = ''
    anthropic_api_key: str = ''
    gemini_api_key: str = ''
    hybrid_fallback_enabled: bool = True
    noor_require_confirmation_for_high_risk: bool = True
    noor_enable_browser_automation: bool = True
    noor_enable_mobile_bridge: bool = True
    noor_enable_public_posting: bool = False
    noor_cors_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    noor_ws_allowed_origins: str = 'http://localhost:3000,http://127.0.0.1:3000'
    model_config = ConfigDict(env_file='../.env', extra='ignore')
settings = Settings()
