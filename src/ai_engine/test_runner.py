import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def run_single_test(test_nodeid: str, project_root: Optional[Path] = None) -> Dict:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    temp_report = project_root / "reports" / f"temp_test_report_{hash(test_nodeid)}.json"
    
    cmd = [
        sys.executable, "-m", "pytest",
        test_nodeid,
        "--json-report",
        f"--json-report-file={temp_report}",
        "--tb=short",
        "-v"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if temp_report.exists():
            with open(temp_report, "r") as f:
                report_data = json.load(f)
            
            temp_report.unlink()
            
            tests = report_data.get("tests", [])
            if tests:
                test_result = tests[0]
                return {
                    "nodeid": test_result.get("nodeid"),
                    "outcome": test_result.get("outcome"),
                    "duration": test_result.get("duration", 0),
                    "call": test_result.get("call", {}),
                    "error": test_result.get("call", {}).get("longrepr", ""),
                    "exit_code": result.returncode
                }
        
        return {
            "nodeid": test_nodeid,
            "outcome": "passed" if result.returncode == 0 else "failed",
            "duration": 0,
            "call": {},
            "error": result.stderr if result.returncode != 0 else "",
            "exit_code": result.returncode
        }
    
    except subprocess.TimeoutExpired:
        return {
            "nodeid": test_nodeid,
            "outcome": "failed",
            "duration": 60,
            "call": {},
            "error": "Test execution timed out after 60 seconds",
            "exit_code": -1
        }
    
    except Exception as e:
        return {
            "nodeid": test_nodeid,
            "outcome": "failed",
            "duration": 0,
            "call": {},
            "error": str(e),
            "exit_code": -1
        }


def run_multiple_tests(test_nodeids: List[str], project_root: Optional[Path] = None) -> List[Dict]:
    results = []
    for nodeid in test_nodeids:
        print(f"Running test: {nodeid}")
        result = run_single_test(nodeid, project_root)
        results.append(result)
        
        outcome = result.get("outcome")
        if outcome == "passed":
            print(f"  ✓ PASSED")
        elif outcome == "failed":
            print(f"  ✗ FAILED")
        else:
            print(f"  ⊘ {outcome.upper()}")
    
    return results


def run_all_tests(project_root: Optional[Path] = None) -> Dict:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent
    
    report_file = project_root / "reports" / "pytest-report.json"
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/generated",
        "--json-report",
        f"--json-report-file={report_file}",
        "--html=reports/html/report.html",
        "--self-contained-html",
        "-v"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if report_file.exists():
            with open(report_file, "r") as f:
                return json.load(f)
        
        return {
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "tests": [],
            "exit_code": result.returncode
        }
    
    except Exception as e:
        print(f"Error running tests: {e}")
        return {
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "tests": [],
            "error": str(e)
        }


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_nodeid = sys.argv[1]
        result = run_single_test(test_nodeid)
        print(json.dumps(result, indent=2))
    else:
        print("Running all tests...")
        result = run_all_tests()
        summary = result.get("summary", {})
        print(f"Total: {summary.get('total', 0)}")
        print(f"Passed: {summary.get('passed', 0)}")
        print(f"Failed: {summary.get('failed', 0)}")
