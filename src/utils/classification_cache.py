
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger
from utils.vector_store import VectorStore, QueryResult, get_vector_store
from utils.config import config

logger = get_logger(__name__)

COLLECTION_CLASSIFICATIONS = "error_classifications"

@dataclass
class CachedClassification:
    error_signature: str
    classification: str  # TEST_ERROR or ACTUAL_DEFECT
    reason: str
    confidence: str
    app_type: str
    usage_count: int = 1

@dataclass
class ClassificationMatch:
    cached: CachedClassification
    similarity: float

    @property
    def should_use(self) -> bool:
        return self.similarity >= config.CLASSIFICATION_SIMILARITY_THRESHOLD

class ClassificationCache:

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_vector_store()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        self.vector_store.get_or_create_collection(COLLECTION_CLASSIFICATIONS)

    def _create_signature(self, error_message: str, test_code: str) -> str:
        error_lines = error_message.strip().split('\n')
        core_error = error_lines[-1] if error_lines else error_message[:300]

        test_structure = []
        for line in test_code.split('\n'):
            line = line.strip()
            if line.startswith('def test_'):
                test_structure.append(line.split('(')[0])
            elif line.startswith('assert '):
                test_structure.append(line[:80])
            elif 'raise' in line or 'Error' in line:
                test_structure.append(line[:80])

        structure_str = ' | '.join(test_structure[:3])
        return f"{core_error} | {structure_str}"

    def store_classification(
        self,
        error_message: str,
        test_code: str,
        classification: str,
        reason: str,
        confidence: str,
        app_type: str
    ) -> str:
        signature = self._create_signature(error_message, test_code)

        existing = self.find_similar(error_message, test_code, n_results=1)
        if existing and existing[0].similarity > 0.95:
            self._increment_usage(existing[0].cached.error_signature)
            logger.debug(f"Updated existing classification usage count")
            return existing[0].cached.error_signature

        metadata = {
            "classification": classification,
            "reason": reason,
            "confidence": confidence,
            "app_type": app_type,
            "usage_count": 1,
            "error_preview": error_message[:500],
        }

        doc_id = self.vector_store.add_single(
            COLLECTION_CLASSIFICATIONS,
            signature,
            metadata
        )

        logger.debug(f"Stored classification: {classification} for {signature[:50]}...")
        return doc_id

    def _increment_usage(self, signature: str) -> None:
        results = self.vector_store.query(
            COLLECTION_CLASSIFICATIONS,
            signature,
            n_results=1
        )
        if results:
            metadata = results[0].metadata.copy()
            metadata["usage_count"] = int(metadata.get("usage_count", 0)) + 1
            self.vector_store.update(COLLECTION_CLASSIFICATIONS, results[0].id, metadata=metadata)

    def find_similar(
        self,
        error_message: str,
        test_code: str,
        n_results: int = 3,
        app_type: Optional[str] = None
    ) -> List[ClassificationMatch]:
        signature = self._create_signature(error_message, test_code)

        where_filter = None
        if app_type:
            where_filter = {"app_type": app_type}

        results = self.vector_store.query(
            COLLECTION_CLASSIFICATIONS,
            signature,
            n_results=n_results,
            where=where_filter
        )

        matches = []
        for result in results:
            cached = CachedClassification(
                error_signature=result.text,
                classification=result.metadata.get("classification", "UNKNOWN"),
                reason=result.metadata.get("reason", ""),
                confidence=result.metadata.get("confidence", "low"),
                app_type=result.metadata.get("app_type", "unknown"),
                usage_count=int(result.metadata.get("usage_count", 0)),
            )
            matches.append(ClassificationMatch(cached=cached, similarity=result.similarity))

        return matches

    def get_cached_classification(
        self,
        error_message: str,
        test_code: str,
        app_type: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        matches = self.find_similar(error_message, test_code, n_results=1, app_type=app_type)

        if matches and matches[0].should_use:
            match = matches[0]
            logger.info(
                f"Using cached classification: {match.cached.classification} "
                f"(similarity={match.similarity:.2f}, used {match.cached.usage_count} times)"
            )
            self._increment_usage(match.cached.error_signature)
            return {
                "classification": match.cached.classification,
                "reason": f"[Cached] {match.cached.reason}",
                "confidence": match.cached.confidence,
                "from_cache": True,
                "similarity": match.similarity,
            }

        return None

    def get_stats(self) -> Dict[str, Any]:
        stats = self.vector_store.collection_stats(COLLECTION_CLASSIFICATIONS)
        return {
            "total_classifications": stats.count,
            "collection_name": stats.name,
        }

    def clear(self) -> None:
        self.vector_store.delete_collection(COLLECTION_CLASSIFICATIONS)
        self._ensure_collection()
        logger.info("Cleared classification cache")

_default_cache: Optional[ClassificationCache] = None

def get_classification_cache(vector_store: Optional[VectorStore] = None) -> ClassificationCache:
    global _default_cache

    if _default_cache is None:
        _default_cache = ClassificationCache(vector_store)

    return _default_cache
