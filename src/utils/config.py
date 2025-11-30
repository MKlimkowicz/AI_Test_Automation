import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    OPENAI_TEMPERATURE_ANALYSIS: float = float(os.getenv("OPENAI_TEMPERATURE_ANALYSIS", "0.4"))
    OPENAI_TEMPERATURE_GENERATION: float = float(os.getenv("OPENAI_TEMPERATURE_GENERATION", "0.7"))
    OPENAI_TEMPERATURE_CLASSIFICATION: float = float(os.getenv("OPENAI_TEMPERATURE_CLASSIFICATION", "0.3"))
    OPENAI_TEMPERATURE_HEALING: float = float(os.getenv("OPENAI_TEMPERATURE_HEALING", "0.5"))
    OPENAI_TEMPERATURE_BUG_ANALYSIS: float = float(os.getenv("OPENAI_TEMPERATURE_BUG_ANALYSIS", "0.3"))
    OPENAI_TEMPERATURE_SUMMARY: float = float(os.getenv("OPENAI_TEMPERATURE_SUMMARY", "0.4"))
    OPENAI_TEMPERATURE_FIXTURES: float = float(os.getenv("OPENAI_TEMPERATURE_FIXTURES", "0.5"))
    
    OPENAI_MAX_TOKENS_ANALYSIS: int = int(os.getenv("OPENAI_MAX_TOKENS_ANALYSIS", "3000"))
    OPENAI_MAX_TOKENS_GENERATION: int = int(os.getenv("OPENAI_MAX_TOKENS_GENERATION", "2000"))
    OPENAI_MAX_TOKENS_CLASSIFICATION: int = int(os.getenv("OPENAI_MAX_TOKENS_CLASSIFICATION", "500"))
    OPENAI_MAX_TOKENS_HEALING: int = int(os.getenv("OPENAI_MAX_TOKENS_HEALING", "2000"))
    OPENAI_MAX_TOKENS_BUG_ANALYSIS: int = int(os.getenv("OPENAI_MAX_TOKENS_BUG_ANALYSIS", "1500"))
    OPENAI_MAX_TOKENS_SUMMARY: int = int(os.getenv("OPENAI_MAX_TOKENS_SUMMARY", "3000"))
    OPENAI_MAX_TOKENS_FIXTURES: int = int(os.getenv("OPENAI_MAX_TOKENS_FIXTURES", "3000"))
    
    OPENAI_RETRY_ATTEMPTS: int = int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3"))
    OPENAI_RETRY_MIN_WAIT: int = int(os.getenv("OPENAI_RETRY_MIN_WAIT", "2"))
    OPENAI_RETRY_MAX_WAIT: int = int(os.getenv("OPENAI_RETRY_MAX_WAIT", "30"))
    
    MAX_HEALING_ATTEMPTS: int = int(os.getenv("MAX_HEALING_ATTEMPTS", "3"))
    MAX_FILE_SIZE_KB: int = int(os.getenv("MAX_FILE_SIZE_KB", "50"))
    MAX_CONFIG_FILE_SIZE_KB: int = int(os.getenv("MAX_CONFIG_FILE_SIZE_KB", "100"))
    MAX_PARALLEL_WORKERS: int = int(os.getenv("MAX_PARALLEL_WORKERS", "4"))
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/ai_test_automation.log")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    APP_DIR: str = os.getenv("APP_DIR", "app")
    
    @classmethod
    def validate(cls) -> bool:
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        return True
    
    @classmethod
    def get_project_root(cls) -> Path:
        return Path(__file__).parent.parent.parent


config = Config()
