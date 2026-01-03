import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)

def run_single_test(test_nodeid: str, project_root: Optional[Path] = None) -> Dict[str, Any]:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    temp_report: Path = project_root / "reports" / f"temp_test_report_{hash(test_nodeid)}.json"

    cmd: List[str] = [
        sys.executable, "-m", "pytest",
        test_nodeid,
        "--json-report",
        f"--json-report-file={temp_report}",
        "--tb=short",
        "-v"
    ]

    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=60
        )

        if temp_report.exists():
            with open(temp_report, "r") as f:
                report_data: Dict[str, Any] = json.load(f)

            temp_report.unlink()

            tests: List[Dict[str, Any]] = report_data.get("tests", [])
            if tests:
                test_result: Dict[str, Any] = tests[0]
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

def run_multiple_tests(test_nodeids: List[str], project_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for nodeid in test_nodeids:
        logger.info(f"Running test: {nodeid}")
        result: Dict[str, Any] = run_single_test(nodeid, project_root)
        results.append(result)

        outcome: Optional[str] = result.get("outcome")
        if outcome == "passed":
            logger.info(f"  ✓ PASSED")
        elif outcome == "failed":
            logger.warning(f"  ✗ FAILED")
        else:
            logger.info(f"  ⊘ {outcome.upper() if outcome else 'UNKNOWN'}")

    return results

def run_all_tests(project_root: Optional[Path] = None, parallel: bool = True) -> Dict[str, Any]:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    report_file: Path = project_root / "reports" / "pytest-report.json"

    cmd: List[str] = [
        sys.executable, "-m", "pytest",
        "tests/generated",
        "--json-report",
        f"--json-report-file={report_file}",
        "--html=reports/html/report.html",
        "--self-contained-html",
        "-v"
    ]

    if parallel and config.PARALLEL_TEST_EXECUTION:
        workers: int = config.PYTEST_WORKERS
        cmd.extend(["-n", str(workers)])

    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
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
        logger.error(f"Error running tests: {e}")
        return {
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "tests": [],
            "error": str(e)
        }

def run_tests_parallel(
    test_dir: str = "tests/generated",
    project_root: Optional[Path] = None,
    workers: Optional[int] = None
) -> Dict[str, Any]:
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent

    if workers is None:
        workers = config.PYTEST_WORKERS

    report_file: Path = project_root / "reports" / "pytest-report.json"
    html_report: Path = project_root / "reports" / "html" / "report.html"

    html_report.parent.mkdir(parents=True, exist_ok=True)

    cmd: List[str] = [
        sys.executable, "-m", "pytest",
        test_dir,
        "-n", str(workers),
        "--json-report",
        f"--json-report-file={report_file}",
        "--html", str(html_report),
        "--self-contained-html",
        "-v",
        "--dist=loadfile"
    ]

    logger.info(f"Running tests in parallel with {workers} workers...")
    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=600
        )

        logger.debug(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)

        if report_file.exists():
            with open(report_file, "r") as f:
                report_data: Dict[str, Any] = json.load(f)
            report_data["exit_code"] = result.returncode
            return report_data

        return {
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "tests": [],
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except subprocess.TimeoutExpired:
        logger.error("Test execution timed out after 600 seconds")
        return {
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "tests": [],
            "error": "Test execution timed out",
            "exit_code": -1
        }

    except Exception as e:
        logger.error(f"Error running parallel tests: {e}")
        return {
            "summary": {"total": 0, "passed": 0, "failed": 0},
            "tests": [],
            "error": str(e),
            "exit_code": -1
        }

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_nodeid: str = sys.argv[1]
        result: Dict[str, Any] = run_single_test(test_nodeid)
        logger.debug(json.dumps(result, indent=2))
    else:
        logger.info("Running all tests...")
        if config.PARALLEL_TEST_EXECUTION:
            result = run_tests_parallel()
        else:
            result = run_all_tests(parallel=False)
        summary: Dict[str, Any] = result.get("summary", {})
        logger.info(f"Total: {summary.get('total', 0)}")
        logger.info(f"Passed: {summary.get('passed', 0)}")
        logger.info(f"Failed: {summary.get('failed', 0)}")
