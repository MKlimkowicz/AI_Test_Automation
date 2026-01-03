
import hashlib
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

from utils.logger import get_logger
from utils.vector_store import VectorStore, get_vector_store
from utils.config import config

logger = get_logger(__name__)

COLLECTION_FILE_SNAPSHOTS = "file_snapshots"

@dataclass
class FileSnapshot:
    file_path: str
    content_hash: str
    size: int
    last_modified: str
    snapshot_time: str

@dataclass
class ChangeReport:
    added_files: List[str]
    modified_files: List[str]
    deleted_files: List[str]
    unchanged_files: List[str]
    total_changes: int

    @property
    def has_changes(self) -> bool:
        return self.total_changes > 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class ChangeDetector:

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        snapshot_dir: Optional[Path] = None
    ):
        self.vector_store = vector_store or get_vector_store()
        self.snapshot_dir = snapshot_dir or (config.get_project_root() / ".change_snapshots")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        self.vector_store.get_or_create_collection(COLLECTION_FILE_SNAPSHOTS)

    def _compute_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_snapshot_path(self, run_id: str = "latest") -> Path:
        return self.snapshot_dir / f"snapshot_{run_id}.json"

    def _load_snapshot(self, run_id: str = "latest") -> Dict[str, FileSnapshot]:
        snapshot_path = self._get_snapshot_path(run_id)
        if not snapshot_path.exists():
            return {}

        try:
            with open(snapshot_path, "r") as f:
                data = json.load(f)
            return {
                path: FileSnapshot(**snap)
                for path, snap in data.items()
            }
        except Exception as e:
            logger.warning(f"Failed to load snapshot: {e}")
            return {}

    def _save_snapshot(
        self,
        snapshots: Dict[str, FileSnapshot],
        run_id: str = "latest"
    ) -> None:
        snapshot_path = self._get_snapshot_path(run_id)
        try:
            data = {path: asdict(snap) for path, snap in snapshots.items()}
            with open(snapshot_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved snapshot: {snapshot_path}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot: {e}")

    def create_snapshot(
        self,
        files: Dict[str, str],
        run_id: str = "latest"
    ) -> Dict[str, FileSnapshot]:
        now = datetime.now().isoformat()
        snapshots: Dict[str, FileSnapshot] = {}

        for file_path, content in files.items():
            snapshot = FileSnapshot(
                file_path=file_path,
                content_hash=self._compute_hash(content),
                size=len(content),
                last_modified=now,
                snapshot_time=now
            )
            snapshots[file_path] = snapshot

        self._save_snapshot(snapshots, run_id)

        self._index_snapshots(snapshots)

        logger.info(f"Created snapshot with {len(snapshots)} files")
        return snapshots

    def _index_snapshots(self, snapshots: Dict[str, FileSnapshot]) -> None:
        texts = []
        metadatas = []
        ids = []

        for file_path, snapshot in snapshots.items():
            texts.append(file_path)
            metadatas.append({
                "content_hash": snapshot.content_hash,
                "size": snapshot.size,
                "snapshot_time": snapshot.snapshot_time,
            })
            ids.append(self._compute_hash(file_path))

        if texts:
            self.vector_store.add(COLLECTION_FILE_SNAPSHOTS, texts, metadatas, ids)

    def detect_changes(
        self,
        current_files: Dict[str, str],
        previous_run_id: str = "latest"
    ) -> ChangeReport:
        previous_snapshots = self._load_snapshot(previous_run_id)

        added_files: List[str] = []
        modified_files: List[str] = []
        deleted_files: List[str] = []
        unchanged_files: List[str] = []

        current_paths = set(current_files.keys())
        previous_paths = set(previous_snapshots.keys())

        for path in current_paths - previous_paths:
            added_files.append(path)

        for path in previous_paths - current_paths:
            deleted_files.append(path)

        for path in current_paths & previous_paths:
            current_hash = self._compute_hash(current_files[path])
            previous_hash = previous_snapshots[path].content_hash

            if current_hash != previous_hash:
                modified_files.append(path)
            else:
                unchanged_files.append(path)

        total_changes = len(added_files) + len(modified_files) + len(deleted_files)

        report = ChangeReport(
            added_files=sorted(added_files),
            modified_files=sorted(modified_files),
            deleted_files=sorted(deleted_files),
            unchanged_files=sorted(unchanged_files),
            total_changes=total_changes
        )

        if report.has_changes:
            logger.info(
                f"Changes detected: {len(added_files)} added, "
                f"{len(modified_files)} modified, {len(deleted_files)} deleted"
            )
        else:
            logger.info("No changes detected since last run")

        return report

    def get_changed_files_content(
        self,
        current_files: Dict[str, str],
        previous_run_id: str = "latest"
    ) -> Tuple[Dict[str, str], ChangeReport]:
        report = self.detect_changes(current_files, previous_run_id)

        changed_files: Dict[str, str] = {}

        for path in report.added_files + report.modified_files:
            if path in current_files:
                changed_files[path] = current_files[path]

        return changed_files, report

    def should_regenerate_tests(
        self,
        current_files: Dict[str, str],
        previous_run_id: str = "latest",
        threshold: float = 0.1
    ) -> Tuple[bool, ChangeReport]:
        report = self.detect_changes(current_files, previous_run_id)

        if not report.has_changes:
            return False, report

        total_files = len(current_files)
        if total_files == 0:
            return True, report

        change_ratio = report.total_changes / total_files

        should_regen = change_ratio >= threshold or len(report.added_files) > 0

        if should_regen:
            logger.info(
                f"Test regeneration recommended: {report.total_changes} changes "
                f"({change_ratio:.1%} of files)"
            )
        else:
            logger.info(
                f"Minor changes ({change_ratio:.1%}), incremental update sufficient"
            )

        return should_regen, report

    def save_run_snapshot(
        self,
        files: Dict[str, str],
        run_id: Optional[str] = None
    ) -> str:
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.create_snapshot(files, run_id)
        self.create_snapshot(files, "latest")

        return run_id

    def get_stats(self) -> Dict[str, Any]:
        stats = self.vector_store.collection_stats(COLLECTION_FILE_SNAPSHOTS)
        latest_snapshot = self._load_snapshot("latest")

        return {
            "indexed_files": stats.count,
            "latest_snapshot_files": len(latest_snapshot),
            "snapshot_dir": str(self.snapshot_dir),
        }

    def clear(self) -> None:
        self.vector_store.delete_collection(COLLECTION_FILE_SNAPSHOTS)
        self._ensure_collection()

        for snapshot_file in self.snapshot_dir.glob("snapshot_*.json"):
            snapshot_file.unlink()

        logger.info("Cleared all change detection data")

_default_detector: Optional[ChangeDetector] = None

def get_change_detector(
    vector_store: Optional[VectorStore] = None,
    snapshot_dir: Optional[Path] = None
) -> ChangeDetector:
    global _default_detector

    if _default_detector is None:
        _default_detector = ChangeDetector(vector_store, snapshot_dir)

    return _default_detector
