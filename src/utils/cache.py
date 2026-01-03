import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

class AnalysisCache:

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = 3600):
        if cache_dir is None:
            from utils.config import config
            cache_dir = config.get_project_root() / ".cache"
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, code_files: Dict[str, Tuple[str, str]], doc_files: Dict[str, str]) -> str:
        content_parts: list[str] = []
        for filepath in sorted(code_files.keys()):
            content, lang = code_files[filepath]
            content_parts.append(f"{filepath}:{lang}:{content}")
        for filepath in sorted(doc_files.keys()):
            content_parts.append(f"{filepath}:{doc_files[filepath]}")
        combined = "\n".join(content_parts)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str, cache_type: str) -> Path:
        return self.cache_dir / f"{cache_type}_{cache_key}.json"

    def get_analysis(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        cache_key = self._compute_hash(code_files, doc_files)
        analysis_path = self._get_cache_path(cache_key, "analysis")
        metadata_path = self._get_cache_path(cache_key, "metadata")

        if not analysis_path.exists() or not metadata_path.exists():
            return None

        try:
            with open(analysis_path, "r") as f:
                cached_analysis = json.load(f)
            with open(metadata_path, "r") as f:
                cached_metadata = json.load(f)

            if time.time() - cached_analysis.get("timestamp", 0) > self.ttl_seconds:
                return None

            return cached_analysis.get("content"), cached_metadata.get("content")
        except (json.JSONDecodeError, KeyError):
            return None

    def set_analysis(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str],
        analysis_md: str,
        metadata: Dict[str, Any]
    ) -> None:
        cache_key = self._compute_hash(code_files, doc_files)
        analysis_path = self._get_cache_path(cache_key, "analysis")
        metadata_path = self._get_cache_path(cache_key, "metadata")

        with open(analysis_path, "w") as f:
            json.dump({"timestamp": time.time(), "content": analysis_md}, f)
        with open(metadata_path, "w") as f:
            json.dump({"timestamp": time.time(), "content": metadata}, f)

    def invalidate(self) -> int:
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count

    def get_cache_key(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str]
    ) -> str:
        return self._compute_hash(code_files, doc_files)

class TestGenerationCache:

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = 3600):
        if cache_dir is None:
            from utils.config import config
            cache_dir = config.get_project_root() / ".cache" / "tests"
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, *args: Any) -> str:
        content = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"tests_{cache_key}.json"

    def _is_valid(self, cached_data: Dict[str, Any]) -> bool:
        timestamp = cached_data.get("timestamp", 0)
        return time.time() - timestamp <= self.ttl_seconds

    def get_generated_tests(
        self,
        analysis_hash: str,
        category: str,
        scenarios: List[str],
        app_metadata: Dict[str, Any]
    ) -> Optional[str]:
        cache_key = self._compute_hash(analysis_hash, category, scenarios, app_metadata)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)

            if not self._is_valid(cached):
                return None

            return cached.get("content")
        except (json.JSONDecodeError, KeyError):
            return None

    def set_generated_tests(
        self,
        analysis_hash: str,
        category: str,
        scenarios: List[str],
        app_metadata: Dict[str, Any],
        test_code: str
    ) -> None:
        cache_key = self._compute_hash(analysis_hash, category, scenarios, app_metadata)
        cache_path = self._get_cache_path(cache_key)

        with open(cache_path, "w") as f:
            json.dump({"timestamp": time.time(), "content": test_code}, f)

    def invalidate(self) -> int:
        count = 0
        for cache_file in self.cache_dir.glob("tests_*.json"):
            cache_file.unlink()
            count += 1
        return count

class ClassificationCache:

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = 7200):
        if cache_dir is None:
            from utils.config import config
            cache_dir = config.get_project_root() / ".cache" / "classifications"
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, test_code: str, error_message: str) -> str:
        content = f"{test_code}:::{error_message}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"classification_{cache_key}.json"

    def get_classification(
        self,
        test_code: str,
        error_message: str
    ) -> Optional[Dict[str, str]]:
        cache_key = self._compute_hash(test_code, error_message)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)

            if time.time() - cached.get("timestamp", 0) > self.ttl_seconds:
                return None

            return cached.get("content")
        except (json.JSONDecodeError, KeyError):
            return None

    def set_classification(
        self,
        test_code: str,
        error_message: str,
        classification: Dict[str, str]
    ) -> None:
        cache_key = self._compute_hash(test_code, error_message)
        cache_path = self._get_cache_path(cache_key)

        with open(cache_path, "w") as f:
            json.dump({"timestamp": time.time(), "content": classification}, f)

class HealingCache:

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = 86400):
        if cache_dir is None:
            from utils.config import config
            cache_dir = config.get_project_root() / ".cache" / "healing"
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _compute_hash(self, test_code: str, error_message: str, app_type: str) -> str:
        content = f"{test_code}:::{error_message}:::{app_type}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"healed_{cache_key}.json"

    def get_healed_test(
        self,
        test_code: str,
        error_message: str,
        app_type: str
    ) -> Optional[str]:
        cache_key = self._compute_hash(test_code, error_message, app_type)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)

            if time.time() - cached.get("timestamp", 0) > self.ttl_seconds:
                return None

            if not cached.get("success", False):
                return None

            return cached.get("content")
        except (json.JSONDecodeError, KeyError):
            return None

    def set_healed_test(
        self,
        test_code: str,
        error_message: str,
        app_type: str,
        healed_code: str,
        success: bool
    ) -> None:
        cache_key = self._compute_hash(test_code, error_message, app_type)
        cache_path = self._get_cache_path(cache_key)

        with open(cache_path, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "content": healed_code,
                "success": success
            }, f)

class WorkflowCache:

    def __init__(self, cache_dir: Optional[Path] = None, ttl_seconds: int = 3600):
        if cache_dir is None:
            from utils.config import config
            cache_dir = config.get_project_root() / ".cache"
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds

        self.analysis = AnalysisCache(cache_dir, ttl_seconds)
        self.tests = TestGenerationCache(cache_dir / "tests", ttl_seconds)
        self.classifications = ClassificationCache(cache_dir / "classifications", ttl_seconds * 2)
        self.healing = HealingCache(cache_dir / "healing", ttl_seconds * 24)

    def invalidate_all(self) -> Dict[str, int]:
        return {
            "analysis": self.analysis.invalidate(),
            "tests": self.tests.invalidate(),
            "classifications": self.classifications.invalidate(),
            "healing": self.healing.invalidate(),
        }
