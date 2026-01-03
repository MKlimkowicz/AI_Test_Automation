
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path
from datetime import datetime

from utils.logger import get_logger
from utils.config import config

logger = get_logger(__name__)

@dataclass
class RunMetrics:
    run_id: str
    timestamp: str
    duration_seconds: float = 0.0

    files_analyzed: int = 0
    languages_detected: List[str] = field(default_factory=list)
    app_type: str = ""

    scenarios_generated: int = 0
    tests_generated: int = 0
    tests_deduplicated: int = 0
    categories: List[str] = field(default_factory=list)

    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0

    healing_attempts: int = 0
    healed_successfully: int = 0
    healed_from_kb: int = 0
    actual_defects: int = 0
    max_attempts_exceeded: int = 0

    kb_patterns_stored: int = 0
    classifications_cached: int = 0
    rag_chunks_indexed: int = 0

    cache_hits: int = 0
    cache_misses: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunMetrics":
        return cls(**data)

@dataclass
class AggregateStats:
    total_runs: int = 0
    total_tests_generated: int = 0
    total_tests_passed: int = 0
    total_tests_failed: int = 0
    total_healing_attempts: int = 0
    total_healed: int = 0
    total_healed_from_kb: int = 0
    total_actual_defects: int = 0

    avg_tests_per_run: float = 0.0
    avg_pass_rate: float = 0.0
    avg_healing_success_rate: float = 0.0
    kb_hit_rate: float = 0.0

    most_common_app_type: str = ""
    most_common_languages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class WorkflowAnalytics:

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (config.get_project_root() / ".analytics")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._current_run: Optional[RunMetrics] = None
        self._start_time: Optional[datetime] = None

    def _get_runs_file(self) -> Path:
        return self.data_dir / "runs.json"

    def _load_runs(self) -> List[RunMetrics]:
        runs_file = self._get_runs_file()
        if not runs_file.exists():
            return []

        try:
            with open(runs_file, "r") as f:
                data = json.load(f)
            return [RunMetrics.from_dict(r) for r in data]
        except Exception as e:
            logger.warning(f"Failed to load runs: {e}")
            return []

    def _save_runs(self, runs: List[RunMetrics]) -> None:
        runs_file = self._get_runs_file()
        try:
            with open(runs_file, "w") as f:
                json.dump([r.to_dict() for r in runs], f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save runs: {e}")

    def start_run(self, run_id: Optional[str] = None) -> str:
        if run_id is None:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._start_time = datetime.now()
        self._current_run = RunMetrics(
            run_id=run_id,
            timestamp=self._start_time.isoformat()
        )
        logger.info(f"Analytics: Started tracking run {run_id}")
        return run_id

    def end_run(self) -> Optional[RunMetrics]:
        if self._current_run is None:
            return None

        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
            self._current_run.duration_seconds = duration

        runs = self._load_runs()
        runs.append(self._current_run)

        if len(runs) > 100:
            runs = runs[-100:]

        self._save_runs(runs)

        result = self._current_run
        logger.info(f"Analytics: Run {result.run_id} completed in {result.duration_seconds:.1f}s")

        self._current_run = None
        self._start_time = None

        return result

    def record_analysis(
        self,
        files_analyzed: int,
        languages: List[str],
        app_type: str
    ) -> None:
        if self._current_run:
            self._current_run.files_analyzed = files_analyzed
            self._current_run.languages_detected = languages
            self._current_run.app_type = app_type

    def record_generation(
        self,
        scenarios: int,
        tests: int,
        deduplicated: int,
        categories: List[str]
    ) -> None:
        if self._current_run:
            self._current_run.scenarios_generated = scenarios
            self._current_run.tests_generated = tests
            self._current_run.tests_deduplicated = deduplicated
            self._current_run.categories = categories

    def record_execution(
        self,
        passed: int,
        failed: int,
        skipped: int = 0
    ) -> None:
        if self._current_run:
            self._current_run.tests_passed = passed
            self._current_run.tests_failed = failed
            self._current_run.tests_skipped = skipped

    def record_healing(
        self,
        attempts: int,
        healed: int,
        from_kb: int,
        defects: int,
        exceeded: int
    ) -> None:
        if self._current_run:
            self._current_run.healing_attempts = attempts
            self._current_run.healed_successfully = healed
            self._current_run.healed_from_kb = from_kb
            self._current_run.actual_defects = defects
            self._current_run.max_attempts_exceeded = exceeded

    def record_vector_db(
        self,
        kb_patterns: int = 0,
        classifications: int = 0,
        rag_chunks: int = 0
    ) -> None:
        if self._current_run:
            self._current_run.kb_patterns_stored = kb_patterns
            self._current_run.classifications_cached = classifications
            self._current_run.rag_chunks_indexed = rag_chunks

    def record_cache(self, hits: int, misses: int) -> None:
        if self._current_run:
            self._current_run.cache_hits = hits
            self._current_run.cache_misses = misses

    def get_aggregate_stats(self, last_n_runs: Optional[int] = None) -> AggregateStats:
        runs = self._load_runs()

        if last_n_runs:
            runs = runs[-last_n_runs:]

        if not runs:
            return AggregateStats()

        stats = AggregateStats(total_runs=len(runs))

        app_types: Dict[str, int] = {}
        languages: Dict[str, int] = {}

        for run in runs:
            stats.total_tests_generated += run.tests_generated
            stats.total_tests_passed += run.tests_passed
            stats.total_tests_failed += run.tests_failed
            stats.total_healing_attempts += run.healing_attempts
            stats.total_healed += run.healed_successfully
            stats.total_healed_from_kb += run.healed_from_kb
            stats.total_actual_defects += run.actual_defects

            if run.app_type:
                app_types[run.app_type] = app_types.get(run.app_type, 0) + 1

            for lang in run.languages_detected:
                languages[lang] = languages.get(lang, 0) + 1

        stats.avg_tests_per_run = stats.total_tests_generated / len(runs) if runs else 0

        total_executed = stats.total_tests_passed + stats.total_tests_failed
        stats.avg_pass_rate = (stats.total_tests_passed / total_executed * 100) if total_executed else 0

        stats.avg_healing_success_rate = (
            stats.total_healed / stats.total_healing_attempts * 100
        ) if stats.total_healing_attempts else 0

        stats.kb_hit_rate = (
            stats.total_healed_from_kb / stats.total_healed * 100
        ) if stats.total_healed else 0

        if app_types:
            stats.most_common_app_type = max(app_types, key=app_types.get)

        if languages:
            sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)
            stats.most_common_languages = [lang for lang, _ in sorted_langs[:3]]

        return stats

    def get_recent_runs(self, n: int = 10) -> List[RunMetrics]:
        runs = self._load_runs()
        return runs[-n:] if runs else []

    def get_insights(self) -> Dict[str, Any]:
        stats = self.get_aggregate_stats()
        recent = self.get_recent_runs(5)

        insights = {
            "summary": {
                "total_runs": stats.total_runs,
                "total_tests_generated": stats.total_tests_generated,
                "avg_tests_per_run": round(stats.avg_tests_per_run, 1),
                "avg_pass_rate": f"{stats.avg_pass_rate:.1f}%",
            },
            "healing": {
                "total_healed": stats.total_healed,
                "success_rate": f"{stats.avg_healing_success_rate:.1f}%",
                "kb_hit_rate": f"{stats.kb_hit_rate:.1f}%",
                "actual_defects_found": stats.total_actual_defects,
            },
            "trends": {},
            "recommendations": [],
        }

        if len(recent) >= 2:
            recent_pass_rates = []
            for run in recent:
                total = run.tests_passed + run.tests_failed
                if total > 0:
                    recent_pass_rates.append(run.tests_passed / total * 100)

            if len(recent_pass_rates) >= 2:
                trend = recent_pass_rates[-1] - recent_pass_rates[0]
                insights["trends"]["pass_rate"] = f"{'↑' if trend > 0 else '↓'} {abs(trend):.1f}%"

        if stats.avg_pass_rate < 70:
            insights["recommendations"].append(
                "Pass rate is below 70%. Consider reviewing test generation prompts."
            )

        if stats.kb_hit_rate < 20 and stats.total_healed > 10:
            insights["recommendations"].append(
                "KB hit rate is low. The healing knowledge base is still learning."
            )

        if stats.total_actual_defects > stats.total_healed:
            insights["recommendations"].append(
                "More defects than healed tests. Application may have significant issues."
            )

        return insights

    def print_summary(self) -> None:
        stats = self.get_aggregate_stats()
        insights = self.get_insights()

        logger.info("=" * 60)
        logger.info("WORKFLOW ANALYTICS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Runs: {stats.total_runs}")
        logger.info(f"Total Tests Generated: {stats.total_tests_generated}")
        logger.info(f"Average Tests/Run: {stats.avg_tests_per_run:.1f}")
        logger.info(f"Average Pass Rate: {stats.avg_pass_rate:.1f}%")
        logger.info("-" * 40)
        logger.info("Healing Statistics:")
        logger.info(f"  Total Healed: {stats.total_healed}")
        logger.info(f"  Success Rate: {stats.avg_healing_success_rate:.1f}%")
        logger.info(f"  KB Hit Rate: {stats.kb_hit_rate:.1f}%")
        logger.info(f"  Actual Defects: {stats.total_actual_defects}")

        if insights["recommendations"]:
            logger.info("-" * 40)
            logger.info("Recommendations:")
            for rec in insights["recommendations"]:
                logger.info(f"  • {rec}")

        logger.info("=" * 60)

    def export_report(self, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            output_path = config.get_project_root() / "reports" / "analytics_report.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        report = {
            "generated_at": datetime.now().isoformat(),
            "aggregate_stats": self.get_aggregate_stats().to_dict(),
            "insights": self.get_insights(),
            "recent_runs": [r.to_dict() for r in self.get_recent_runs(10)],
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Analytics report exported to: {output_path}")
        return output_path

    def clear(self) -> None:
        runs_file = self._get_runs_file()
        if runs_file.exists():
            runs_file.unlink()
        self._current_run = None
        self._start_time = None
        logger.info("Cleared all analytics data")

_default_analytics: Optional[WorkflowAnalytics] = None

def get_analytics(data_dir: Optional[Path] = None) -> WorkflowAnalytics:
    global _default_analytics

    if _default_analytics is None:
        _default_analytics = WorkflowAnalytics(data_dir)

    return _default_analytics
