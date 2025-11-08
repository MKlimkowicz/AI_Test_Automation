import os
import json
import sys
import subprocess
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient
from ai_engine.test_runner import run_single_test

def heal_collection_errors(report_data: Dict, project_root: Path, client: OpenAIClient) -> Dict:
    """
    Heal pytest collection errors (import failures, syntax errors, etc.)
    
    Args:
        report_data: Pytest JSON report data
        project_root: Project root directory
        client: OpenAI client for AI-powered fixes
    
    Returns:
        Dict with collection healing results
    """
    collectors = report_data.get("collectors", [])
    failed_collectors = [c for c in collectors if c.get("outcome") == "failed"]
    
    if not failed_collectors:
        return {
            "collection_errors_found": 0,
            "collection_errors_fixed": 0,
            "collection_errors_remaining": 0
        }
    
    print(f"\n{'='*80}")
    print(f"COLLECTION ERROR HEALING")
    print(f"{'='*80}")
    print(f"Found {len(failed_collectors)} collection error(s)\n")
    
    fixed_count = 0
    
    for collector in failed_collectors:
        nodeid = collector.get("nodeid", "")
        error_msg = collector.get("longrepr", "")
        
        # Extract file path from nodeid
        if not nodeid or nodeid == "tests/generated":
            continue
            
        test_file = project_root / nodeid
        
        if not test_file.exists():
            print(f"⚠ Test file not found: {test_file}")
            continue
        
        print(f"Healing: {nodeid}")
        print(f"Error: {error_msg[:200]}...")
        
        # Read the test file
        with open(test_file, "r") as f:
            test_code = f.read()
        
        # Ask AI to fix the collection error
        print("  → Analyzing collection error with AI...")
        
        try:
            fixed_code = client.fix_collection_error(
                test_file=str(test_file),
                test_code=test_code,
                error_message=error_msg
            )
            
            if fixed_code and fixed_code.strip() != test_code.strip():
                # Save the fixed code
                with open(test_file, "w") as f:
                    f.write(fixed_code)
                
                print(f"  ✓ Fixed collection error in {nodeid}")
                fixed_count += 1
            else:
                print(f"  ⚠ AI could not fix collection error in {nodeid}")
        except Exception as e:
            print(f"  ✗ Error fixing collection error: {e}")
    
    # Rerun pytest collection to check if errors are fixed
    if fixed_count > 0:
        print(f"\n{'='*80}")
        print(f"Re-running pytest collection to verify fixes...")
        print(f"{'='*80}\n")
        
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
                print(f"⚠ {remaining_errors} collection error(s) still remain")
            else:
                print(f"✓ All collection errors fixed!")
                remaining_errors = 0
        except Exception as e:
            print(f"⚠ Could not verify collection fixes: {e}")
            remaining_errors = len(failed_collectors) - fixed_count
    else:
        remaining_errors = len(failed_collectors)
    
    return {
        "collection_errors_found": len(failed_collectors),
        "collection_errors_fixed": fixed_count,
        "collection_errors_remaining": remaining_errors
    }

def heal_failed_tests(json_report_path: str, max_attempts: int = 3) -> Dict:
    """
    Iteratively heal failed tests classified as TEST_ERROR.
    
    Args:
        json_report_path: Path to pytest JSON report
        max_attempts: Maximum healing attempts per test (default: 3)
    
    Returns:
        Dict with healing results including successfully healed, actual defects, and exceeded attempts
    """
    client = OpenAIClient()
    
    project_root = Path(__file__).parent.parent.parent
    report_path = project_root / json_report_path
    
    if not report_path.exists():
        print(f"Report file not found: {report_path}")
        result = {
            "successfully_healed": [],
            "actual_defects": [],
            "max_attempts_exceeded": [],
            "healed_count": 0,
            "defect_count": 0,
            "exceeded_count": 0,
            "commit_allowed": True
        }
        
        # Save the result even when report doesn't exist
        healing_report_path = project_root / "reports" / "healing_analysis.json"
        healing_report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(healing_report_path, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"Report saved to: {healing_report_path}")
        return result
    
    with open(report_path, "r") as f:
        report_data = json.load(f)
    
    # First, heal any collection errors (import failures, syntax errors, etc.)
    collection_healing = heal_collection_errors(report_data, project_root, client)
    
    # If collection errors were fixed, we need to rerun tests to get updated results
    if collection_healing["collection_errors_fixed"] > 0:
        print(f"\n{'='*80}")
        print(f"Re-running tests after fixing collection errors...")
        print(f"{'='*80}\n")
        
        try:
            # Rerun pytest to get updated report
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
            
            # Reload the report
            with open(report_path, "r") as f:
                report_data = json.load(f)
            
            print(f"✓ Tests re-executed after collection fixes\n")
        except Exception as e:
            print(f"⚠ Could not rerun tests: {e}\n")
    
    tests = report_data.get("tests", [])
    failed_tests = [t for t in tests if t.get("outcome") == "failed"]
    
    if not failed_tests:
        print("No failed tests found.")
        result = {
            "successfully_healed": [],
            "actual_defects": [],
            "max_attempts_exceeded": [],
            "healed_count": 0,
            "defect_count": 0,
            "exceeded_count": 0,
            "commit_allowed": True
        }
        
        # Save the result even when there are no failures
        healing_report_path = project_root / "reports" / "healing_analysis.json"
        healing_report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(healing_report_path, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"\nReport saved to: {healing_report_path}")
        return result
    
    print(f"Found {len(failed_tests)} failed test(s). Starting iterative healing...\n")
    
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
            print(f"Test file not found: {test_filepath}")
            continue
        
        print(f"{'='*80}")
        print(f"Processing: {test_name}")
        print(f"{'='*80}")
        
        # Initial classification
        with open(test_filepath, "r") as f:
            test_code = f.read()
        
        classification = client.classify_failure(test_code, test)
        failure_type = classification.get("classification", "UNKNOWN")
        reason = classification.get("reason", "No reason provided")
        confidence = classification.get("confidence", "unknown")
        
        print(f"Initial classification: {failure_type} (confidence: {confidence})")
        print(f"Reason: {reason}")
        
        # If ACTUAL_DEFECT, don't heal - just record
        if failure_type == "ACTUAL_DEFECT":
            print(f"→ Marked as ACTUAL_DEFECT - requires investigation\n")
            actual_defects.append({
                "test_name": test_name,
                "classification": "ACTUAL_DEFECT",
                "reason": reason,
                "confidence": confidence,
                "error": test.get("call", {}).get("longrepr", "N/A"),
                "analysis": reason
            })
            continue
        
        # If TEST_ERROR, start iterative healing
        if failure_type == "TEST_ERROR":
            attempts = 0
            healed_successfully = False
            
            while attempts < max_attempts:
                attempts += 1
                print(f"\n→ Attempt {attempts}/{max_attempts}: Healing test...")
                
                # Heal the test
                healed_code = client.heal_test(test_code, test)
                
                # Clean up code fences
                if healed_code.startswith("```python"):
                    healed_code = healed_code[9:]
                if healed_code.startswith("```"):
                    healed_code = healed_code[3:]
                if healed_code.endswith("```"):
                    healed_code = healed_code[:-3]
                healed_code = healed_code.strip()
                
                # Save healed test
                with open(test_filepath, "w") as f:
                    f.write(healed_code)
                
                print(f"  Healed code saved to {test_filepath}")
                
                # Rerun the healed test
                print(f"  Rerunning test...")
                rerun_result = run_single_test(test_name, project_root)
                
                if rerun_result.get("outcome") == "passed":
                    print(f"  ✓ Test PASSED after healing!")
                    successfully_healed.append({
                        "test_name": test_name,
                        "attempts": attempts,
                        "final_status": "PASS",
                        "original_reason": reason
                    })
                    healed_successfully = True
                    break
                
                # Test still failed - re-classify
                print(f"  ✗ Test still FAILED - re-classifying...")
                
                # Read the healed code for re-classification
                with open(test_filepath, "r") as f:
                    test_code = f.read()
                
                # Create test dict from rerun result for classification
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
                
                print(f"  Re-classification: {failure_type} (confidence: {confidence})")
                print(f"  Reason: {reason}")
                
                if failure_type == "ACTUAL_DEFECT":
                    print(f"  → Now classified as ACTUAL_DEFECT - stopping healing")
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
                
                # Still TEST_ERROR, continue healing if attempts remain
                if attempts >= max_attempts:
                    print(f"  → Max attempts ({max_attempts}) reached")
                    break
            
            # Check if we exceeded max attempts without success
            if not healed_successfully and failure_type == "TEST_ERROR":
                print(f"  → Max healing attempts exceeded - test still failing\n")
                max_attempts_exceeded.append({
                    "test_name": test_name,
                    "attempts": attempts,
                    "still_failing": True,
                    "last_error": rerun_result.get("error", "Unknown error") if 'rerun_result' in locals() else test.get("call", {}).get("longrepr", "N/A")
                })
        
        print()  # Empty line between tests
    
    # Determine if commit should be allowed
    commit_allowed = len(max_attempts_exceeded) == 0
    
    result = {
        "successfully_healed": successfully_healed,
        "actual_defects": actual_defects,
        "max_attempts_exceeded": max_attempts_exceeded,
        "healed_count": len(successfully_healed),
        "defect_count": len(actual_defects),
        "exceeded_count": len(max_attempts_exceeded),
        "commit_allowed": commit_allowed,
        "collection_errors": collection_healing if 'collection_healing' in locals() else {
            "collection_errors_found": 0,
            "collection_errors_fixed": 0,
            "collection_errors_remaining": 0
        }
    }
    
    healing_report_path = project_root / "reports" / "healing_analysis.json"
    healing_report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(healing_report_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"{'='*80}")
    print(f"HEALING SUMMARY")
    print(f"{'='*80}")
    
    # Collection errors summary
    coll_errors = result.get('collection_errors', {})
    if coll_errors.get('collection_errors_found', 0) > 0:
        print(f"\nCollection Errors:")
        print(f"  Found: {coll_errors['collection_errors_found']}")
        print(f"  Fixed: {coll_errors['collection_errors_fixed']}")
        print(f"  Remaining: {coll_errors['collection_errors_remaining']}")
    
    # Test execution summary
    print(f"\nTest Execution:")
    print(f"  ✓ Successfully Healed: {result['healed_count']}")
    print(f"  ⚠ Actual Defects (Need Investigation): {result['defect_count']}")
    print(f"  ✗ Max Attempts Exceeded: {result['exceeded_count']}")
    
    print(f"\nCommit Allowed: {'YES' if commit_allowed else 'NO'}")
    if not commit_allowed:
        print(f"  Reason: {result['exceeded_count']} test(s) still failing after max healing attempts")
    print(f"\nReport saved to: {healing_report_path}")
    print(f"{'='*80}\n")
    
    return result

if __name__ == "__main__":
    result = heal_failed_tests("reports/pytest-report.json")
    print("\nHealing Analysis Complete")

