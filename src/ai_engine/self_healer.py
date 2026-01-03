import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.ai_client import AIClient
from utils.config import config
from utils.logger import get_logger
from utils.helpers import strip_markdown_fences
from utils.app_metadata import load_app_metadata
from ai_engine.test_runner import run_single_test

_classification_cache = None
_analytics = None

def _get_analytics():
    global _analytics
    if _analytics is None:
        try:
            from utils.analytics import get_analytics
            _analytics = get_analytics()
        except Exception as e:
            logger.warning(f"Could not initialize Analytics: {e}")
    return _analytics

def _record_healing_analytics(result: Dict[str, Any]) -> None:
    analytics = _get_analytics()
    if analytics is None:
        return

    try:
        analytics.record_healing(
            attempts=result.get("healed_count", 0) + result.get("exceeded_count", 0),
            healed=result.get("healed_count", 0),
            from_kb=result.get("kb_healed_count", 0),
            defects=result.get("defect_count", 0),
            exceeded=result.get("exceeded_count", 0)
        )

        kb_stats = result.get("kb_stats", {})
        class_stats = result.get("classification_cache_stats", {})
        analytics.record_vector_db(
            kb_patterns=kb_stats.get("total_patterns", 0),
            classifications=class_stats.get("total_classifications", 0)
        )
    except Exception as e:
        logger.warning(f"Failed to record healing analytics: {e}")

def _get_classification_cache():
    global _classification_cache
    if _classification_cache is None and config.ENABLE_VECTOR_DB:
        try:
            from utils.classification_cache import get_classification_cache
            _classification_cache = get_classification_cache()
            logger.info("Classification Cache enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Classification Cache: {e}")
    return _classification_cache

def _get_cached_or_classify(
    client: AIClient,
    test_code: str,
    test_data: Dict[str, Any],
    app_type: str
) -> Dict[str, str]:
    error_message = test_data.get("call", {}).get("longrepr", "")

    cache = _get_classification_cache()
    if cache:
        cached = cache.get_cached_classification(error_message, test_code, app_type)
        if cached:
            return cached

    classification = client.classify_failure(test_code, test_data)

    if cache and classification:
        cache.store_classification(
            error_message=error_message,
            test_code=test_code,
            classification=classification.get("classification", "UNKNOWN"),
            reason=classification.get("reason", ""),
            confidence=classification.get("confidence", "low"),
            app_type=app_type
        )

    return classification

def _get_healing_kb():
    global _healing_kb
    if _healing_kb is None and config.ENABLE_VECTOR_DB:
        try:
            from utils.healing_kb import get_healing_kb
            _healing_kb = get_healing_kb()
            logger.info("Healing Knowledge Base enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Healing KB: {e}")
    return _healing_kb

def _try_kb_healing(
    test_code: str,
    error_message: str,
    app_type: str
) -> Tuple[Optional[str], bool]:
    kb = _get_healing_kb()
    if kb is None:
        return None, False

    suggestion = kb.get_best_fix(error_message, test_code, app_type)
    if suggestion and suggestion.pattern.healed_code:
        logger.info(
            f"Using KB fix (similarity={suggestion.similarity:.2f}, "
            f"success_rate={suggestion.pattern.success_rate:.2f})"
        )
        return suggestion.pattern.healed_code, True

    return None, False

def _store_healing_result(
    error_message: str,
    original_code: str,
    healed_code: str,
    error_type: str,
    app_type: str,
    success: bool
) -> None:
    kb = _get_healing_kb()
    if kb is None:
        return

    try:
        kb.store_pattern(
            error_message=error_message,
            original_code=original_code,
            healed_code=healed_code,
            error_type=error_type,
            app_type=app_type,
            success=success
        )
    except Exception as e:
        logger.warning(f"Could not store healing pattern: {e}")

logger = get_logger(__name__)
_healing_kb = None

def heal_collection_errors(
    report_data: Dict[str, Any],
    project_root: Path,
    client: AIClient,
    app_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, int]:
    collectors: List[Dict[str, Any]] = report_data.get("collectors", [])
    failed_collectors: List[Dict[str, Any]] = [c for c in collectors if c.get("outcome") == "failed"]

    if not failed_collectors:
        return {
            "collection_errors_found": 0,
            "collection_errors_fixed": 0,
            "collection_errors_remaining": 0
        }

    if app_metadata is None:
        app_metadata = {}

    logger.info("=" * 80)
    logger.info("COLLECTION ERROR HEALING")
    logger.info("=" * 80)
    logger.info(f"Found {len(failed_collectors)} collection error(s)")

    fixed_count: int = 0

    for collector in failed_collectors:
        nodeid: str = collector.get("nodeid", "")
        error_msg: str = collector.get("longrepr", "")

        if not nodeid or nodeid == "tests/generated":
            continue

        test_file: Path = project_root / nodeid

        if not test_file.exists():
            logger.warning(f"Test file not found: {test_file}")
            continue

        logger.info(f"Healing: {nodeid}")
        logger.debug(f"Error: {error_msg[:200]}...")

        with open(test_file, "r") as f:
            test_code: str = f.read()

        logger.debug("Analyzing collection error with AI...")

        try:
            fixed_code: str = client.fix_collection_error(
                test_file=str(test_file),
                test_code=test_code,
                error_message=error_msg,
                app_metadata=app_metadata
            )

            if fixed_code and fixed_code.strip() != test_code.strip():
                with open(test_file, "w") as f:
                    f.write(fixed_code)

                logger.info(f"Fixed collection error in {nodeid}")
                fixed_count += 1
            else:
                logger.warning(f"AI could not fix collection error in {nodeid}")
        except Exception as e:
            logger.error(f"Error fixing collection error: {e}")

    remaining_errors: int
    if fixed_count > 0:
        logger.info("=" * 80)
        logger.info("Re-running pytest collection to verify fixes...")
        logger.info("=" * 80)

        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                ["pytest", "tests/generated/", "--collect-only", "-q"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if "error" in result.stdout.lower() or "error" in result.stderr.lower():
                remaining_errors = result.stderr.count("ERROR")
                logger.warning(f"{remaining_errors} collection error(s) still remain")
            else:
                logger.info("All collection errors fixed!")
                remaining_errors = 0
        except Exception as e:
            logger.warning(f"Could not verify collection fixes: {e}")
            remaining_errors = len(failed_collectors) - fixed_count
    else:
        remaining_errors = len(failed_collectors)

    return {
        "collection_errors_found": len(failed_collectors),
        "collection_errors_fixed": fixed_count,
        "collection_errors_remaining": remaining_errors
    }

def heal_failed_tests(
    json_report_path: str,
    max_attempts: Optional[int] = None
) -> Dict[str, Any]:
    if max_attempts is None:
        max_attempts = config.MAX_HEALING_ATTEMPTS

    client: AIClient = AIClient()

    project_root: Path = config.get_project_root()
    report_path: Path = project_root / json_report_path

    app_metadata: Dict[str, Any] = load_app_metadata(project_root)
    logger.info(f"Healing with app_type={app_metadata.get('app_type')}, port={app_metadata.get('port')}")

    if not report_path.exists():
        logger.warning(f"Report file not found: {report_path}")
        result: Dict[str, Any] = {
            "successfully_healed": [],
            "actual_defects": [],
            "max_attempts_exceeded": [],
            "healed_count": 0,
            "defect_count": 0,
            "exceeded_count": 0
        }

        healing_report_path: Path = project_root / "reports" / "healing_analysis.json"
        healing_report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(healing_report_path, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Report saved to: {healing_report_path}")
        return result

    with open(report_path, "r") as f:
        report_data: Dict[str, Any] = json.load(f)

    collection_healing: Dict[str, int] = heal_collection_errors(report_data, project_root, client, app_metadata)

    if collection_healing["collection_errors_fixed"] > 0:
        logger.info("=" * 80)
        logger.info("Re-running tests after fixing collection errors...")
        logger.info("=" * 80)

        try:
            subprocess.run(
                [
                    "pytest", "tests/generated/",
                    "--json-report",
                    "--json-report-file=reports/pytest-report.json",
                    "-v"
                ],
                cwd=project_root,
                timeout=120
            )

            with open(report_path, "r") as f:
                report_data = json.load(f)

            logger.info("Tests re-executed after collection fixes")
        except Exception as e:
            logger.warning(f"Could not rerun tests: {e}")

    tests: List[Dict[str, Any]] = report_data.get("tests", [])
    failed_tests: List[Dict[str, Any]] = [t for t in tests if t.get("outcome") == "failed"]

    if not failed_tests:
        logger.info("No failed tests found.")
        result = {
            "successfully_healed": [],
            "actual_defects": [],
            "max_attempts_exceeded": [],
            "healed_count": 0,
            "defect_count": 0,
            "exceeded_count": 0
        }

        healing_report_path = project_root / "reports" / "healing_analysis.json"
        healing_report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(healing_report_path, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Report saved to: {healing_report_path}")
        return result

    logger.info(f"Found {len(failed_tests)} failed test(s). Starting iterative healing...")

    successfully_healed: List[Dict[str, Any]] = []
    actual_defects: List[Dict[str, Any]] = []
    max_attempts_exceeded_list: List[Dict[str, Any]] = []

    for test in failed_tests:
        test_file: str = test.get("nodeid", "").split("::")[0]
        test_name: str = test.get("nodeid", "unknown")

        if not test_file:
            continue

        test_filepath: Path = project_root / test_file

        if not test_filepath.exists():
            logger.warning(f"Test file not found: {test_filepath}")
            continue

        logger.info("=" * 80)
        logger.info(f"Processing: {test_name}")
        logger.info("=" * 80)

        with open(test_filepath, "r") as f:
            test_code: str = f.read()

        current_app_type: str = app_metadata.get("app_type", "rest_api")
        classification: Dict[str, str] = _get_cached_or_classify(client, test_code, test, current_app_type)
        failure_type: str = classification.get("classification", "UNKNOWN")
        reason: str = classification.get("reason", "No reason provided")
        confidence: str = classification.get("confidence", "unknown")
        from_cache: bool = classification.get("from_cache", False)

        cache_indicator: str = " [cached]" if from_cache else ""
        logger.info(f"Initial classification: {failure_type} (confidence: {confidence}){cache_indicator}")
        logger.debug(f"Reason: {reason}")

        if failure_type == "ACTUAL_DEFECT":
            logger.info("Marked as ACTUAL_DEFECT - requires investigation")
            actual_defects.append({
                "test_name": test_name,
                "classification": "ACTUAL_DEFECT",
                "reason": reason,
                "confidence": confidence,
                "error": test.get("call", {}).get("longrepr", "N/A"),
                "analysis": reason
            })
            continue

        if failure_type == "TEST_ERROR":
            attempts: int = 0
            healed_successfully: bool = False
            rerun_result: Optional[Dict[str, Any]] = None
            original_test_code: str = test_code
            error_for_kb: str = test.get("call", {}).get("longrepr", "")
            app_type: str = app_metadata.get("app_type", "rest_api")

            while attempts < max_attempts:
                attempts += 1
                logger.info(f"Attempt {attempts}/{max_attempts}: Healing test...")

                healed_code: str = ""
                from_kb: bool = False
                if attempts == 1:
                    healed_code, from_kb = _try_kb_healing(test_code, error_for_kb, app_type)

                if not healed_code:
                    healed_code = client.heal_test(test_code, test, app_metadata)
                    healed_code = strip_markdown_fences(healed_code)
                else:
                    logger.info("Applied fix from Healing Knowledge Base")

                with open(test_filepath, "w") as f:
                    f.write(healed_code)

                logger.debug(f"Healed code saved to {test_filepath}")

                logger.info("Rerunning test...")
                rerun_result = run_single_test(test_name, project_root)

                if rerun_result.get("outcome") == "passed":
                    logger.info("Test PASSED after healing!")

                    _store_healing_result(
                        error_message=error_for_kb,
                        original_code=original_test_code,
                        healed_code=healed_code,
                        error_type="TEST_ERROR",
                        app_type=app_type,
                        success=True
                    )

                    successfully_healed.append({
                        "test_name": test_name,
                        "attempts": attempts,
                        "final_status": "PASS",
                        "original_reason": reason,
                        "from_kb": from_kb
                    })
                    healed_successfully = True
                    break

                logger.warning("Test still FAILED - re-classifying...")

                with open(test_filepath, "r") as f:
                    test_code = f.read()

                rerun_test_dict: Dict[str, Any] = {
                    "nodeid": test_name,
                    "outcome": "failed",
                    "call": {
                        "longrepr": rerun_result.get("error", "Unknown error")
                    }
                }

                classification = _get_cached_or_classify(client, test_code, rerun_test_dict, app_type)
                failure_type = classification.get("classification", "UNKNOWN")
                reason = classification.get("reason", "No reason provided")
                confidence = classification.get("confidence", "unknown")
                reclassify_cached: bool = classification.get("from_cache", False)

                cache_ind: str = " [cached]" if reclassify_cached else ""
                logger.info(f"Re-classification: {failure_type} (confidence: {confidence}){cache_ind}")
                logger.debug(f"Reason: {reason}")

                if failure_type == "ACTUAL_DEFECT":
                    logger.info("Now classified as ACTUAL_DEFECT - stopping healing")
                    actual_defects.append({
                        "test_name": test_name,
                        "classification": "ACTUAL_DEFECT",
                        "reason": reason,
                        "confidence": confidence,
                        "error": rerun_result.get("error", "N/A"),
                        "analysis": reason,
                        "healing_attempts": attempts
                    })
                    break

                if attempts >= max_attempts:
                    logger.warning(f"Max attempts ({max_attempts}) reached")
                    break

            if not healed_successfully and failure_type == "TEST_ERROR":
                logger.warning("Max healing attempts exceeded - test still failing")

                _store_healing_result(
                    error_message=error_for_kb,
                    original_code=original_test_code,
                    healed_code=healed_code if healed_code else "",
                    error_type="TEST_ERROR",
                    app_type=app_type,
                    success=False
                )

                max_attempts_exceeded_list.append({
                    "test_name": test_name,
                    "attempts": attempts,
                    "still_failing": True,
                    "last_error": rerun_result.get("error", "Unknown error") if rerun_result else test.get("call", {}).get("longrepr", "N/A")
                })

    kb_healed_count: int = sum(1 for h in successfully_healed if h.get("from_kb", False))

    kb_stats: Dict[str, Any] = {}
    kb = _get_healing_kb()
    if kb:
        kb_stats = kb.get_stats()

    classification_stats: Dict[str, Any] = {}
    class_cache = _get_classification_cache()
    if class_cache:
        classification_stats = class_cache.get_stats()

    result = {
        "successfully_healed": successfully_healed,
        "actual_defects": actual_defects,
        "max_attempts_exceeded": max_attempts_exceeded_list,
        "healed_count": len(successfully_healed),
        "kb_healed_count": kb_healed_count,
        "defect_count": len(actual_defects),
        "exceeded_count": len(max_attempts_exceeded_list),
        "collection_errors": collection_healing,
        "kb_stats": kb_stats,
        "classification_cache_stats": classification_stats
    }

    healing_report_path = project_root / "reports" / "healing_analysis.json"
    healing_report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(healing_report_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("=" * 80)
    logger.info("HEALING SUMMARY")
    logger.info("=" * 80)

    coll_errors: Dict[str, int] = result.get('collection_errors', {})
    if coll_errors.get('collection_errors_found', 0) > 0:
        logger.info("Collection Errors:")
        logger.info(f"  Found: {coll_errors['collection_errors_found']}")
        logger.info(f"  Fixed: {coll_errors['collection_errors_fixed']}")
        logger.info(f"  Remaining: {coll_errors['collection_errors_remaining']}")

    logger.info("Test Execution:")
    logger.info(f"  Successfully Healed: {result['healed_count']}")
    if result.get('kb_healed_count', 0) > 0:
        logger.info(f"    (From Knowledge Base: {result['kb_healed_count']})")
    logger.info(f"  Actual Defects (Need Investigation): {result['defect_count']}")
    logger.info(f"  Max Attempts Exceeded: {result['exceeded_count']}")

    if result.get('kb_stats') or result.get('classification_cache_stats'):
        logger.info("Vector DB Stats:")
        if result.get('kb_stats'):
            logger.info(f"  Healing Patterns: {result['kb_stats'].get('total_patterns', 0)}")
        if result.get('classification_cache_stats'):
            logger.info(f"  Cached Classifications: {result['classification_cache_stats'].get('total_classifications', 0)}")

    logger.info(f"Report saved to: {healing_report_path}")
    logger.info("=" * 80)

    _record_healing_analytics(result)

    return result

if __name__ == "__main__":
    result: Dict[str, Any] = heal_failed_tests("reports/pytest-report.json")
    logger.info("Healing Analysis Complete")
