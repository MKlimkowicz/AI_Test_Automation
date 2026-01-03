import argparse
import ast
import json
import py_compile
import sys
from dataclasses import dataclass, asdict
from importlib import util as importlib_util
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.config import config
from utils.logger import get_logger
from utils.ai_client import AIClient
from utils.app_metadata import load_app_metadata

logger = get_logger(__name__)

@dataclass
class ValidationIssue:
    type: str
    message: str
    suggestion: Optional[str] = None

@dataclass
class ValidationResult:
    target: str
    syntax_ok: bool
    imports_ok: bool
    ai_passed: Optional[bool] = None
    issues: Optional[List[ValidationIssue]] = None
    autofix_applied: bool = False
    healing_attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = asdict(self)
        data["issues"] = [asdict(issue) for issue in self.issues or []]
        return data

def _compile_check(py_path: Path) -> Tuple[bool, Optional[str]]:
    try:
        py_compile.compile(str(py_path), doraise=True)
        return True, None
    except py_compile.PyCompileError as exc:
        return False, str(exc)

def _extract_imports(code: str) -> Set[str]:
    imports: Set[str] = set()
    try:
        tree: ast.Module = ast.parse(code)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module: str = node.module.split(".")[0]
                if node.level == 0:
                    imports.add(module)
    return imports

def _check_imports(modules: Set[str]) -> Tuple[bool, List[ValidationIssue], List[str]]:
    missing: List[ValidationIssue] = []
    raw_missing: List[str] = []
    for module in sorted(modules):
        if not module or module.startswith("_"):
            continue
        try:
            if importlib_util.find_spec(module) is None:
                raise ModuleNotFoundError
        except ModuleNotFoundError:
            missing.append(
                ValidationIssue(
                    type="missing-import",
                    message=f"Module '{module}' is not available or not installed.",
                    suggestion=f"Install or mock '{module}' or ensure it is available during tests."
                )
            )
            raw_missing.append(module)
    return len(missing) == 0, missing, raw_missing

def _auto_fix_imports(py_path: Path, code: str, missing_modules: List[str]) -> Tuple[bool, str]:
    mapping: Dict[str, str] = {
        "uuid": "import uuid\n",
        "requests": "import requests\n",
        "pytest": "import pytest\n",
    }
    additions: List[str] = []
    for module in missing_modules:
        statement: Optional[str] = mapping.get(module)
        if statement and statement not in code:
            additions.append(statement)

    if not additions:
        return False, code

    lines: List[str] = code.splitlines()
    insert_idx: int = 0
    while insert_idx < len(lines) and (lines[insert_idx].startswith("#") and "!" in lines[insert_idx]):
        insert_idx += 1
    updated_code: str = (
        "".join(additions) + "\n".join(lines[insert_idx:]) if insert_idx == 0
        else "\n".join(lines[:insert_idx]) + "\n" + "".join(additions) + "\n".join(lines[insert_idx:])
    )

    if not updated_code.endswith("\n"):
        updated_code += "\n"

    py_path.write_text(updated_code)
    return True, updated_code

def validate_tests(
    tests_dir: Path,
    allow_autofix: bool = True,
    max_healing_attempts: int = 3,
    app_metadata: Optional[Dict[str, Any]] = None
) -> ValidationResult:
    logger.info("Validating tests in %s", tests_dir)

    if app_metadata is None:
        app_metadata = {}

    test_files: List[Path] = sorted(tests_dir.glob("test_*.py"))
    if not test_files:
        issues: List[ValidationIssue] = [ValidationIssue(type="missing-tests", message=f"No test_*.py files found in {tests_dir}")]
        return ValidationResult(target=str(tests_dir), syntax_ok=False, imports_ok=False, issues=issues)

    client: AIClient = AIClient()
    healing_attempts: int = 0
    autofix_applied: bool = False

    while healing_attempts <= max_healing_attempts:
        issues = []
        syntax_ok: bool = True
        imports_ok: bool = True
        file_content: Dict[str, str] = {}

        for test_file in test_files:
            code: str = test_file.read_text()
            file_content[str(test_file)] = code
            file_syntax_ok: bool
            syntax_error: Optional[str]
            file_syntax_ok, syntax_error = _compile_check(test_file)
            if not file_syntax_ok:
                syntax_ok = False
                issues.append(ValidationIssue(type="syntax-error", message=f"{test_file}: {syntax_error}"))

            imports: Set[str] = _extract_imports(code)
            file_imports_ok: bool
            import_issues: List[ValidationIssue]
            missing_modules: List[str]
            file_imports_ok, import_issues, missing_modules = _check_imports(imports)
            if not file_imports_ok:
                imports_ok = False
                issues.extend(
                    ValidationIssue(type=issue.type, message=f"{test_file}: {issue.message}", suggestion=issue.suggestion)
                    for issue in import_issues
                )
                if allow_autofix and missing_modules:
                    applied: bool
                    updated_code: str
                    applied, updated_code = _auto_fix_imports(test_file, code, missing_modules)
                    if applied:
                        autofix_applied = True
                        file_content[str(test_file)] = updated_code

        ai_passed: Optional[bool] = None
        if syntax_ok and imports_ok:
            try:
                review: Dict[str, Any] = client.validate_tests(file_content, app_metadata)
                ai_passed = review.get("status") == "pass"
                for item in review.get("issues", []):
                    issues.append(
                        ValidationIssue(
                            type=item.get("type", "ai-issue"),
                            message=item.get("detail", "AI detected issue"),
                            suggestion=item.get("suggestion")
                        )
                    )
            except Exception as exc:
                logger.warning("AI test validation skipped: %s", exc)

        if syntax_ok and imports_ok and (ai_passed in (True, None)):
            return ValidationResult(
                target=str(tests_dir),
                syntax_ok=syntax_ok,
                imports_ok=imports_ok,
                ai_passed=ai_passed,
                issues=issues,
                autofix_applied=autofix_applied,
                healing_attempts=healing_attempts,
            )

        if healing_attempts >= max_healing_attempts:
            logger.error("Test validation failed after %s healing attempts", healing_attempts)
            return ValidationResult(
                target=str(tests_dir),
                syntax_ok=syntax_ok,
                imports_ok=imports_ok,
                ai_passed=ai_passed,
                issues=issues,
                autofix_applied=autofix_applied,
                healing_attempts=healing_attempts,
            )

        healing_attempts += 1
        logger.info("Attempting AI healing for generated tests (attempt %s)", healing_attempts)
        try:
            heal_payload: List[Dict[str, Any]] = [
                {
                    "type": issue.type,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                }
                for issue in issues
            ]
            healed_files: Dict[str, str] = client.heal_tests(file_content, heal_payload)
            if healed_files:
                for path_str, healed_code in healed_files.items():
                    if healed_code and healed_code.strip():
                        Path(path_str).write_text(
                            healed_code if healed_code.endswith("\n") else healed_code + "\n"
                        )
                continue
        except Exception as exc:
            logger.warning("AI healing of tests failed: %s", exc)
        break

    return ValidationResult(
        target=str(tests_dir),
        syntax_ok=False,
        imports_ok=False,
        ai_passed=False,
        issues=issues,
        autofix_applied=autofix_applied,
        healing_attempts=healing_attempts,
    )

def _write_report(result: ValidationResult, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), indent=2))
    logger.info("Validation report written to %s", report_path)

def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Validate generated pytest tests")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tests_parser = subparsers.add_parser("tests", help="Validate generated tests")
    tests_parser.add_argument("--tests-dir", default="tests/generated", help="Directory containing generated tests")
    tests_parser.add_argument("--report", default="reports/validation_tests.json")

    args: argparse.Namespace = parser.parse_args()

    project_root: Path = config.get_project_root()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    app_metadata: Dict[str, Any] = load_app_metadata(project_root)

    result: ValidationResult = validate_tests(project_root / args.tests_dir, app_metadata=app_metadata)
    _write_report(result, project_root / args.report)

    issues_to_log: List[str] = [f"- {issue.type}: {issue.message}" for issue in result.issues or []]
    if issues_to_log:
        logger.info("Validation issues found:\n%s", "\n".join(issues_to_log))

    if result.syntax_ok and result.imports_ok and (result.ai_passed in (True, None)):
        logger.info("Validation passed for %s", result.target)
        return 0

    logger.error("Validation failed for %s", result.target)
    return 1

if __name__ == "__main__":
    sys.exit(main())
