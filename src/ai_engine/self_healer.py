import os
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient

def heal_failed_tests(json_report_path: str) -> Dict:
    client = OpenAIClient()
    
    project_root = Path(__file__).parent.parent.parent
    report_path = project_root / json_report_path
    
    if not report_path.exists():
        return {
            "test_errors": [],
            "actual_defects": [],
            "healed_count": 0,
            "defect_count": 0
        }
    
    with open(report_path, "r") as f:
        report_data = json.load(f)
    
    tests = report_data.get("tests", [])
    failed_tests = [t for t in tests if t.get("outcome") == "failed"]
    
    if not failed_tests:
        print("No failed tests found.")
        return {
            "test_errors": [],
            "actual_defects": [],
            "healed_count": 0,
            "defect_count": 0
        }
    
    print(f"Found {len(failed_tests)} failed test(s). Analyzing...")
    
    test_errors = []
    actual_defects = []
    
    for test in failed_tests:
        test_file = test.get("nodeid", "").split("::")[0]
        test_name = test.get("nodeid", "unknown")
        
        if not test_file:
            continue
        
        test_filepath = project_root / test_file
        
        if not test_filepath.exists():
            print(f"Test file not found: {test_filepath}")
            continue
        
        with open(test_filepath, "r") as f:
            test_code = f.read()
        
        print(f"Classifying failure: {test_name}")
        
        classification = client.classify_failure(test_code, test)
        
        failure_type = classification.get("classification", "UNKNOWN")
        reason = classification.get("reason", "No reason provided")
        confidence = classification.get("confidence", "unknown")
        
        if failure_type == "TEST_ERROR":
            print(f"  -> TEST_ERROR (confidence: {confidence})")
            print(f"     Reason: {reason}")
            print(f"  -> Healing test...")
            
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
            
            test_errors.append({
                "test_name": test_name,
                "reason": reason,
                "confidence": confidence,
                "original_error": test.get("call", {}).get("longrepr", "N/A"),
                "action": "Self-healed and regenerated",
                "file": str(test_filepath)
            })
            
            print(f"  -> Healed and saved to {test_filepath}")
        
        elif failure_type == "ACTUAL_DEFECT":
            print(f"  -> ACTUAL_DEFECT (confidence: {confidence})")
            print(f"     Reason: {reason}")
            
            actual_defects.append({
                "test_name": test_name,
                "reason": reason,
                "confidence": confidence,
                "error_message": test.get("call", {}).get("longrepr", "N/A"),
                "action": "Requires investigation - possible application bug"
            })
    
    result = {
        "test_errors": test_errors,
        "actual_defects": actual_defects,
        "healed_count": len(test_errors),
        "defect_count": len(actual_defects)
    }
    
    healing_report_path = project_root / "reports" / "healing_analysis.json"
    healing_report_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(healing_report_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nHealing Summary:")
    print(f"  Test Errors (Self-Healed): {result['healed_count']}")
    print(f"  Actual Defects (Need Investigation): {result['defect_count']}")
    print(f"  Report saved to: {healing_report_path}")
    
    return result

if __name__ == "__main__":
    result = heal_failed_tests("reports/pytest-report.json")
    print("\nHealing Analysis Complete")

