import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Config:
    # Claude/Anthropic settings
    CLAUDE_API_KEY: Optional[str] = os.getenv("CLAUDE_API_KEY")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
    
    # Token limits
    MAX_TOKENS_ANALYSIS: int = int(os.getenv("MAX_TOKENS_ANALYSIS", "4000"))
    MAX_TOKENS_GENERATION: int = int(os.getenv("MAX_TOKENS_GENERATION", "8000"))
    MAX_TOKENS_CLASSIFICATION: int = int(os.getenv("MAX_TOKENS_CLASSIFICATION", "1000"))
    MAX_TOKENS_HEALING: int = int(os.getenv("MAX_TOKENS_HEALING", "4000"))
    MAX_TOKENS_BATCH_HEALING: int = int(os.getenv("MAX_TOKENS_BATCH_HEALING", "8000"))
    MAX_TOKENS_BUG_ANALYSIS: int = int(os.getenv("MAX_TOKENS_BUG_ANALYSIS", "2000"))
    MAX_TOKENS_SUMMARY: int = int(os.getenv("MAX_TOKENS_SUMMARY", "4000"))
    
    # Retry settings
    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    RETRY_MIN_WAIT: int = int(os.getenv("RETRY_MIN_WAIT", "2"))
    RETRY_MAX_WAIT: int = int(os.getenv("RETRY_MAX_WAIT", "30"))
    
    MAX_HEALING_ATTEMPTS: int = int(os.getenv("MAX_HEALING_ATTEMPTS", "3"))
    MAX_TESTS_PER_CATEGORY: int = int(os.getenv("MAX_TESTS_PER_CATEGORY", "5"))
    MAX_FILE_SIZE_KB: int = int(os.getenv("MAX_FILE_SIZE_KB", "50"))
    MAX_CONFIG_FILE_SIZE_KB: int = int(os.getenv("MAX_CONFIG_FILE_SIZE_KB", "100"))
    MAX_PARALLEL_WORKERS: int = int(os.getenv("MAX_PARALLEL_WORKERS", "4"))
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/ai_test_automation.log")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    APP_DIR: str = os.getenv("APP_DIR", "app")
    
    @classmethod
    def validate(cls) -> bool:
        if not cls.CLAUDE_API_KEY:
            raise ValueError("CLAUDE_API_KEY environment variable is required")
        return True
    
    @classmethod
    def get_project_root(cls) -> Path:
        return Path(__file__).parent.parent.parent


config = Config()
