import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

class Config:
    CLAUDE_API_KEY: Optional[str] = os.getenv("CLAUDE_API_KEY")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")

    MAX_TOKENS_ANALYSIS: int = int(os.getenv("MAX_TOKENS_ANALYSIS", "4000"))
    MAX_TOKENS_GENERATION: int = int(os.getenv("MAX_TOKENS_GENERATION", "8000"))
    MAX_TOKENS_CLASSIFICATION: int = int(os.getenv("MAX_TOKENS_CLASSIFICATION", "1000"))
    MAX_TOKENS_HEALING: int = int(os.getenv("MAX_TOKENS_HEALING", "4000"))
    MAX_TOKENS_BATCH_HEALING: int = int(os.getenv("MAX_TOKENS_BATCH_HEALING", "8000"))
    MAX_TOKENS_BUG_ANALYSIS: int = int(os.getenv("MAX_TOKENS_BUG_ANALYSIS", "2000"))
    MAX_TOKENS_SUMMARY: int = int(os.getenv("MAX_TOKENS_SUMMARY", "4000"))

    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    RETRY_MIN_WAIT: int = int(os.getenv("RETRY_MIN_WAIT", "2"))
    RETRY_MAX_WAIT: int = int(os.getenv("RETRY_MAX_WAIT", "30"))

    MAX_HEALING_ATTEMPTS: int = int(os.getenv("MAX_HEALING_ATTEMPTS", "3"))
    MAX_TESTS_PER_CATEGORY: int = int(os.getenv("MAX_TESTS_PER_CATEGORY", "5"))
    MAX_FILE_SIZE_KB: int = int(os.getenv("MAX_FILE_SIZE_KB", "50"))
    MAX_CONFIG_FILE_SIZE_KB: int = int(os.getenv("MAX_CONFIG_FILE_SIZE_KB", "100"))
    MAX_PARALLEL_WORKERS: int = int(os.getenv("MAX_PARALLEL_WORKERS", "4"))

    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "3600"))

    ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "true").lower() == "true"

    PARALLEL_TEST_GENERATION: bool = os.getenv("PARALLEL_TEST_GENERATION", "true").lower() == "true"
    PARALLEL_TEST_EXECUTION: bool = os.getenv("PARALLEL_TEST_EXECUTION", "true").lower() == "true"
    PYTEST_WORKERS: int = int(os.getenv("PYTEST_WORKERS", "4"))

    ENABLE_TEST_DEDUPLICATION: bool = os.getenv("ENABLE_TEST_DEDUPLICATION", "true").lower() == "true"
    DEDUPLICATION_SIMILARITY_THRESHOLD: float = float(os.getenv("DEDUPLICATION_SIMILARITY_THRESHOLD", "0.8"))

    ENABLE_NEGATIVE_TESTS: bool = os.getenv("ENABLE_NEGATIVE_TESTS", "true").lower() == "true"
    MAX_NEGATIVE_TESTS_PER_CATEGORY: int = int(os.getenv("MAX_NEGATIVE_TESTS_PER_CATEGORY", "3"))

    ENABLE_DATA_FACTORIES: bool = os.getenv("ENABLE_DATA_FACTORIES", "true").lower() == "true"

    ENABLE_SHARED_FIXTURES: bool = os.getenv("ENABLE_SHARED_FIXTURES", "false").lower() == "true"

    ENABLE_VECTOR_DB: bool = os.getenv("ENABLE_VECTOR_DB", "true").lower() == "true"
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", ".vector_store")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    HEALING_SIMILARITY_THRESHOLD: float = float(os.getenv("HEALING_SIMILARITY_THRESHOLD", "0.85"))
    DEDUP_VECTOR_THRESHOLD: float = float(os.getenv("DEDUP_VECTOR_THRESHOLD", "0.90"))
    CLASSIFICATION_SIMILARITY_THRESHOLD: float = float(os.getenv("CLASSIFICATION_SIMILARITY_THRESHOLD", "0.92"))

    RAG_MAX_CHUNKS: int = int(os.getenv("RAG_MAX_CHUNKS", "5"))
    CODE_CHUNK_SIZE: int = int(os.getenv("CODE_CHUNK_SIZE", "500"))

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
