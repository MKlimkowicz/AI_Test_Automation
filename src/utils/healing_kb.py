
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger
from utils.vector_store import VectorStore, QueryResult, get_vector_store
from utils.config import config

logger = get_logger(__name__)

COLLECTION_HEALING_PATTERNS = "healing_patterns"

@dataclass
class HealingPattern:
    error_signature: str
    original_code: str
    healed_code: str
    error_type: str
    app_type: str
    success_count: int = 1
    failure_count: int = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

@dataclass
class HealingSuggestion:
    pattern: HealingPattern
    similarity: float
    confidence: float

    @property
    def should_apply(self) -> bool:
        return (
            self.similarity >= config.HEALING_SIMILARITY_THRESHOLD
            and self.confidence >= 0.7
            and self.pattern.success_rate >= 0.8
        )

class HealingKnowledgeBase:

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_vector_store()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        self.vector_store.get_or_create_collection(COLLECTION_HEALING_PATTERNS)

    def _create_error_signature(self, error_message: str, test_code: str) -> str:
        error_lines = error_message.strip().split('\n')
        key_error = error_lines[-1] if error_lines else error_message[:200]

        test_name = ""
        for line in test_code.split('\n'):
            if line.strip().startswith('def test_'):
                test_name = line.strip().split('(')[0].replace('def ', '')
                break

        return f"{key_error} | {test_name}"

    def store_pattern(
        self,
        error_message: str,
        original_code: str,
        healed_code: str,
        error_type: str,
        app_type: str,
        success: bool = True
    ) -> str:
        error_signature = self._create_error_signature(error_message, original_code)

        existing = self.find_similar_patterns(error_message, original_code, n_results=1)

        if existing and existing[0].similarity > 0.95:
            pattern_id = existing[0].pattern.error_signature
            self._update_pattern_stats(pattern_id, success)
            logger.debug(f"Updated existing pattern stats: {pattern_id[:50]}...")
            return pattern_id

        metadata = {
            "error_type": error_type,
            "app_type": app_type,
            "success_count": 1 if success else 0,
            "failure_count": 0 if success else 1,
            "original_code_hash": self.vector_store.embedding_service.text_hash(original_code),
            "healed_code_preview": healed_code[:500] if healed_code else "",
            "healed_code_full": healed_code,
        }

        doc_id = self.vector_store.add_single(
            COLLECTION_HEALING_PATTERNS,
            error_signature,
            metadata
        )

        logger.info(f"Stored new healing pattern: {error_signature[:50]}...")
        return doc_id

    def _update_pattern_stats(self, pattern_id: str, success: bool) -> None:
        result = self.vector_store.get_by_id(COLLECTION_HEALING_PATTERNS, pattern_id)
        if result:
            metadata = result.metadata.copy()
            if success:
                metadata["success_count"] = int(metadata.get("success_count", 0)) + 1
            else:
                metadata["failure_count"] = int(metadata.get("failure_count", 0)) + 1

            self.vector_store.update(COLLECTION_HEALING_PATTERNS, pattern_id, metadata=metadata)

    def find_similar_patterns(
        self,
        error_message: str,
        test_code: str,
        n_results: int = 5,
        app_type: Optional[str] = None
    ) -> List[HealingSuggestion]:
        error_signature = self._create_error_signature(error_message, test_code)

        where_filter = None
        if app_type:
            where_filter = {"app_type": app_type}

        results = self.vector_store.query(
            COLLECTION_HEALING_PATTERNS,
            error_signature,
            n_results=n_results,
            where=where_filter
        )

        suggestions = []
        for result in results:
            pattern = HealingPattern(
                error_signature=result.text,
                original_code="",  # Not stored for space efficiency
                healed_code=result.metadata.get("healed_code_full", ""),
                error_type=result.metadata.get("error_type", "unknown"),
                app_type=result.metadata.get("app_type", "unknown"),
                success_count=int(result.metadata.get("success_count", 0)),
                failure_count=int(result.metadata.get("failure_count", 0)),
            )

            confidence = pattern.success_rate * result.similarity

            suggestions.append(HealingSuggestion(
                pattern=pattern,
                similarity=result.similarity,
                confidence=confidence
            ))

        return suggestions

    def get_best_fix(
        self,
        error_message: str,
        test_code: str,
        app_type: Optional[str] = None
    ) -> Optional[HealingSuggestion]:
        suggestions = self.find_similar_patterns(
            error_message,
            test_code,
            n_results=1,
            app_type=app_type
        )

        if suggestions and suggestions[0].should_apply:
            logger.info(
                f"Found applicable healing pattern "
                f"(similarity={suggestions[0].similarity:.2f}, "
                f"success_rate={suggestions[0].pattern.success_rate:.2f})"
            )
            return suggestions[0]

        return None

    def record_outcome(
        self,
        error_message: str,
        test_code: str,
        success: bool
    ) -> None:
        suggestions = self.find_similar_patterns(error_message, test_code, n_results=1)

        if suggestions and suggestions[0].similarity > 0.9:
            results = self.vector_store.query(
                COLLECTION_HEALING_PATTERNS,
                self._create_error_signature(error_message, test_code),
                n_results=1
            )
            if results:
                self._update_pattern_stats(results[0].id, success)
                logger.debug(f"Recorded outcome for pattern: success={success}")

    def get_stats(self) -> Dict[str, Any]:
        stats = self.vector_store.collection_stats(COLLECTION_HEALING_PATTERNS)

        return {
            "total_patterns": stats.count,
            "collection_name": stats.name,
        }

    def clear(self) -> None:
        self.vector_store.delete_collection(COLLECTION_HEALING_PATTERNS)
        self._ensure_collection()
        logger.info("Cleared healing knowledge base")

_default_kb: Optional[HealingKnowledgeBase] = None

def get_healing_kb(vector_store: Optional[VectorStore] = None) -> HealingKnowledgeBase:
    global _default_kb

    if _default_kb is None:
        _default_kb = HealingKnowledgeBase(vector_store)

    return _default_kb
