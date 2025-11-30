import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient
from utils.config import config
from utils.logger import get_logger
from ai_engine.test_runner import run_single_test

logger = get_logger(__name__)


def heal_collection_errors(report_data: Dict, project_root: Path, client: OpenAIClient) -> Dict:
    collectors = report_data.get("collectors", [])
    failed_collectors = [c for c in collectors if c.get("outcome") == "failed"]
    
    if not failed_collectors:
        return {
            "collection_errors_found": 0,
            "collection_errors_fixed": 0,
            "collection_errors_remaining": 0
        }
    
    logger.info("=" * 80)
    logger.info("COLLECTION ERROR HEALING")
    logger.info("=" * 80)
    logger.info(f"Found {len(failed_collectors)} collection error(s)")
    
    fixed_count = 0
    
    for collector in failed_collectors:
        nodeid = collector.get("nodeid", "")
        error_msg = collector.get("longrepr", "")
        
        if not nodeid or nodeid == "tests/generated":
            continue
            
        test_file = project_root / nodeid
        
        if not test_file.exists():
            logger.warning(f"Test file not found: {test_file}")
            continue
        
        logger.info(f"Healing: {nodeid}")
        logger.debug(f"Error: {error_msg[:200]}...")
        
        with open(test_file, "r") as f:
            test_code = f.read()
        
        logger.debug("Analyzing collection error with AI...")
        
        try:
            fixed_code = client.fix_collection_error(
                test_file=str(test_file),
                test_code=test_code,
                error_message=error_msg
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
    
    if fixed_count > 0:
        logger.info("=" * 80)
        logger.info("Re-running pytest collection to verify fixes...")
        logger.info("=" * 80)
        
        try:
            result = subprocess.run(
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


def heal_failed_tests(json_report_path: str, max_attempts: int = None) -> Dict:
    if max_attempts is None:
        max_attempts = config.MAX_HEALING_ATTEMPTS
    
    client = OpenAIClient()
    
    project_root = config.get_project_root()
    report_path = project_root / json_report_path
    
    if not report_path.exists():
        logger.warning(f"Report file not found: {report_path}")
        result = {
            "successfully_healed": [],
            "actual_defects": [],
            "max_attempts_exceeded": [],
            "healed_count": 0,
            "defect_count": 0,
            "exceeded_count": 0,
            "commit_allowed": True
        }
        
        healing_report_path = project_root / "reports" / "healing_analysis.json"
        healing_report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(healing_report_path, "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Report saved to: {healing_report_path}")
        return result
    
    with open(report_path, "r") as f:
        report_data = json.load(f)
    
    collection_healing = heal_collection_errors(report_data, project_root, client)
    
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
    
    tests = report_data.get("tests", [])
    failed_tests = [t for t in tests if t.get("outcome") == "failed"]
    
    if not failed_tests:
        logger.info("No failed tests found.")
        result = {
            "successfully_healed": [],
            "actual_defects": [],
            "max_attempts_exceeded": [],
            "healed_count": 0,
            "defect_count": 0,
            "exceeded_count": 0,
            "commit_allowed": True
        }
        
        healing_report_path = project_root / "reports" / "healing_analysis.json"
        healing_report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(healing_report_path, "w") as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Report saved to: {healing_report_path}")
        return result
    
    logger.info(f"Found {len(failed_tests)} failed test(s). Starting iterative healing...")
    
    successfully_healed = []
    actual_defects = []
    max_attempts_exceeded = []
    
    for test in failed_tests:
        test_file = test.get("nodeid", "").split("::")[0]
        test_name = test.get("nodeid", "unknown")
        
        if not test_file:
            continue
        
        test_filepath = project_root / test_file
        
        if not test_filepath.exists():
            logger.warning(f"Test file not found: {test_filepath}")
            continue
        
        logger.info("=" * 80)
        logger.info(f"Processing: {test_name}")
        logger.info("=" * 80)
        
        with open(test_filepath, "r") as f:
            test_code = f.read()
        
        classification = client.classify_failure(test_code, test)
        failure_type = classification.get("classification", "UNKNOWN")
        reason = classification.get("reason", "No reason provided")
        confidence = classification.get("confidence", "unknown")
        
        logger.info(f"Initial classification: {failure_type} (confidence: {confidence})")
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
            attempts = 0
            healed_successfully = False
            rerun_result = None
            
            while attempts < max_attempts:
                attempts += 1
                logger.info(f"Attempt {attempts}/{max_attempts}: Healing test...")
                
                healed_code = client.heal_test(test_code, test)
                
                if healed_code.startswith("```python"):
                    healed_code = healed_code[9:]
                if healed_code.startswith("```"):
                    healed_code = healed_code[3:]
                if healed_code.endswith("```"):
                    healed_code = healed_code[:-3]
                healed_code = healed_code.strip()
                
                with open(test_filepath, "w") as f:
                    f.write(healed_code)
                
                logger.debug(f"Healed code saved to {test_filepath}")
                
                logger.info("Rerunning test...")
                rerun_result = run_single_test(test_name, project_root)
                
                if rerun_result.get("outcome") == "passed":
                    logger.info("Test PASSED after healing!")
                    successfully_healed.append({
                        "test_name": test_name,
                        "attempts": attempts,
                        "final_status": "PASS",
                        "original_reason": reason
                    })
                    healed_successfully = True
                    break
                
                logger.warning("Test still FAILED - re-classifying...")
                
                with open(test_filepath, "r") as f:
                    test_code = f.read()
                
                rerun_test_dict = {
                    "nodeid": test_name,
                    "outcome": "failed",
                    "call": {
                        "longrepr": rerun_result.get("error", "Unknown error")
                    }
                }
                
                classification = client.classify_failure(test_code, rerun_test_dict)
                failure_type = classification.get("classification", "UNKNOWN")
                reason = classification.get("reason", "No reason provided")
                confidence = classification.get("confidence", "unknown")
                
                logger.info(f"Re-classification: {failure_type} (confidence: {confidence})")
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
                max_attempts_exceeded.append({
                    "test_name": test_name,
                    "attempts": attempts,
                    "still_failing": True,
                    "last_error": rerun_result.get("error", "Unknown error") if rerun_result else test.get("call", {}).get("longrepr", "N/A")
                })
    
    commit_allowed = len(max_attempts_exceeded) == 0
    
    result = {
        "successfully_healed": successfully_healed,
        "actual_defects": actual_defects,
        "max_attempts_exceeded": max_attempts_exceeded,
        "healed_count": len(successfully_healed),
        "defect_count": len(actual_defects),
        "exceeded_count": len(max_attempts_exceeded),
        "commit_allowed": commit_allowed,
        "collection_errors": collection_healing
    }
    
    healing_report_path = project_root / "reports" / "healing_analysis.json"
    healing_report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(healing_report_path, "w") as f:
        json.dump(result, f, indent=2)
    
    logger.info("=" * 80)
    logger.info("HEALING SUMMARY")
    logger.info("=" * 80)
    
    coll_errors = result.get('collection_errors', {})
    if coll_errors.get('collection_errors_found', 0) > 0:
        logger.info("Collection Errors:")
        logger.info(f"  Found: {coll_errors['collection_errors_found']}")
        logger.info(f"  Fixed: {coll_errors['collection_errors_fixed']}")
        logger.info(f"  Remaining: {coll_errors['collection_errors_remaining']}")
    
    logger.info("Test Execution:")
    logger.info(f"  Successfully Healed: {result['healed_count']}")
    logger.info(f"  Actual Defects (Need Investigation): {result['defect_count']}")
    logger.info(f"  Max Attempts Exceeded: {result['exceeded_count']}")
    
    if commit_allowed:
        logger.info("Commit Allowed: YES")
    else:
        logger.warning("Commit Allowed: NO")
        logger.warning(f"  Reason: {result['exceeded_count']} test(s) still failing after max healing attempts")
    
    logger.info(f"Report saved to: {healing_report_path}")
    logger.info("=" * 80)
    
    return result


if __name__ == "__main__":
    result = heal_failed_tests("reports/pytest-report.json")
    logger.info("Healing Analysis Complete")
