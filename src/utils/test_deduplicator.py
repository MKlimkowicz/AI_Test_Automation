
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger
from utils.vector_store import VectorStore, QueryResult, get_vector_store
from utils.config import config

logger = get_logger(__name__)

COLLECTION_TEST_SIGNATURES = "test_signatures"

@dataclass
class TestSignature:
    name: str
    category: str
    normalized_code: str
    file_path: Optional[str] = None

@dataclass
class DuplicateMatch:
    original_name: str
    original_category: str
    similarity: float

    @property
    def is_duplicate(self) -> bool:
        return self.similarity >= config.DEDUP_VECTOR_THRESHOLD

class TestDeduplicator:

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_vector_store()
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        self.vector_store.get_or_create_collection(COLLECTION_TEST_SIGNATURES)

    def _normalize_test_code(self, code: str) -> str:
        code = re.sub(r'#.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'\s+', ' ', code)
        code = re.sub(r'["\'][^"\']*["\']', '"STR"', code)
        code = re.sub(r'\b\d+\b', 'NUM', code)
        code = re.sub(r'\b(response|result|data|user|item|obj)\d*\b', 'VAR', code)
        return code.strip()

    def _extract_test_signature(self, test_code: str, test_name: str) -> str:
        normalized = self._normalize_test_code(test_code)

        elements = []

        clean_name = test_name.replace('test_', '').replace('_', ' ')
        elements.append(clean_name)

        assertions = re.findall(r'assert\s+[^#\n]+', test_code)
        for assertion in assertions[:3]:  # Limit to first 3
            elements.append(self._normalize_test_code(assertion))

        http_methods = re.findall(r'\.(get|post|put|patch|delete|head|options)\s*\(', test_code, re.I)
        elements.extend(http_methods)

        endpoints = re.findall(r'["\']/([\w/]+)["\']', test_code)
        elements.extend(endpoints[:2])

        return ' | '.join(elements)

    def register_test(
        self,
        test_name: str,
        test_code: str,
        category: str,
        file_path: Optional[str] = None
    ) -> str:
        signature = self._extract_test_signature(test_code, test_name)

        metadata = {
            "test_name": test_name,
            "category": category,
            "file_path": file_path or "",
            "code_preview": test_code[:500],
        }

        doc_id = self.vector_store.add_single(
            COLLECTION_TEST_SIGNATURES,
            signature,
            metadata
        )

        logger.debug(f"Registered test: {test_name} in category {category}")
        return doc_id

    def find_duplicates(
        self,
        test_name: str,
        test_code: str,
        category: Optional[str] = None,
        n_results: int = 5
    ) -> List[DuplicateMatch]:
        signature = self._extract_test_signature(test_code, test_name)

        where_filter = None
        if category:
            where_filter = {"category": category}

        results = self.vector_store.query(
            COLLECTION_TEST_SIGNATURES,
            signature,
            n_results=n_results,
            where=where_filter
        )

        matches = []
        for result in results:
            if result.metadata.get("test_name") == test_name:
                continue

            matches.append(DuplicateMatch(
                original_name=result.metadata.get("test_name", "unknown"),
                original_category=result.metadata.get("category", "unknown"),
                similarity=result.similarity
            ))

        return matches

    def is_duplicate(
        self,
        test_name: str,
        test_code: str,
        category: Optional[str] = None
    ) -> Tuple[bool, Optional[DuplicateMatch]]:
        matches = self.find_duplicates(test_name, test_code, category, n_results=1)

        if matches and matches[0].is_duplicate:
            return True, matches[0]

        return False, None

    def deduplicate_tests(
        self,
        tests: List[Dict[str, Any]],
        category: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        unique_tests = []
        duplicate_tests = []

        for test in tests:
            test_name = test.get("name", "")
            test_code = test.get("code", "")

            if not test_name or not test_code:
                continue

            is_dup, match = self.is_duplicate(test_name, test_code, category)

            if is_dup and match:
                logger.info(
                    f"Duplicate detected: {test_name} similar to {match.original_name} "
                    f"(similarity={match.similarity:.2f})"
                )
                duplicate_tests.append({
                    **test,
                    "duplicate_of": match.original_name,
                    "similarity": match.similarity
                })
            else:
                self.register_test(test_name, test_code, category)
                unique_tests.append(test)

        return unique_tests, duplicate_tests

    def deduplicate_code(
        self,
        test_code: str,
        category: str
    ) -> Tuple[str, int, int]:
        test_pattern = r'((?:@pytest\.[\w.()]+\s*\n)*def test_\w+\([^)]*\):.*?)(?=\n(?:@pytest\.|\ndef test_|\Z))'
        matches = re.findall(test_pattern, test_code, re.DOTALL)

        if not matches:
            return test_code, 0, 0

        original_count = len(matches)
        unique_tests = []
        removed_count = 0

        for test_func in matches:
            name_match = re.search(r'def (test_\w+)', test_func)
            if not name_match:
                unique_tests.append(test_func)
                continue

            test_name = name_match.group(1)

            is_dup, match = self.is_duplicate(test_name, test_func, category)

            if is_dup and match:
                logger.info(
                    f"Removing duplicate: {test_name} (similar to {match.original_name}, "
                    f"similarity={match.similarity:.2f})"
                )
                removed_count += 1
            else:
                self.register_test(test_name, test_func, category)
                unique_tests.append(test_func)

        first_test_pos = test_code.find('def test_')
        if first_test_pos > 0:
            header = test_code[:first_test_pos].rstrip() + '\n\n'
        else:
            header = ''

        deduplicated_code = header + '\n\n'.join(unique_tests)

        return deduplicated_code, original_count, removed_count

    def get_stats(self) -> Dict[str, Any]:
        stats = self.vector_store.collection_stats(COLLECTION_TEST_SIGNATURES)
        return {
            "total_tests_indexed": stats.count,
            "collection_name": stats.name,
        }

    def clear(self) -> None:
        self.vector_store.delete_collection(COLLECTION_TEST_SIGNATURES)
        self._ensure_collection()
        logger.info("Cleared test deduplication index")

_default_deduplicator: Optional[TestDeduplicator] = None

def get_test_deduplicator(vector_store: Optional[VectorStore] = None) -> TestDeduplicator:
    global _default_deduplicator

    if _default_deduplicator is None:
        _default_deduplicator = TestDeduplicator(vector_store)

    return _default_deduplicator
