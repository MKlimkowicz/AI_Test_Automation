import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.ai_client import AIClient
from utils.config import config
from utils.logger import get_logger
from utils.helpers import strip_markdown_fences
from ai_engine.bug_reporter import generate_bugs_report

logger = get_logger(__name__)

def summarize_report(html_report_path: str, healing_analysis_path: str) -> str:
    client: AIClient = AIClient()

    project_root: Path = config.get_project_root()
    html_path: Path = project_root / html_report_path
    healing_path: Path = project_root / healing_analysis_path

    json_report_path: Path = project_root / "reports" / "pytest-report.json"

    report_data: Dict[str, Any] = {}
    if json_report_path.exists():
        with open(json_report_path, "r") as f:
            report_data = json.load(f)

    healing_data: Dict[str, Any] = {}
    if healing_path.exists():
        with open(healing_path, "r") as f:
            healing_data = json.load(f)

    summary: Dict[str, Any] = report_data.get("summary", {})

    report_info: Dict[str, Any] = {
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
        "duration": summary.get("duration", 0),
        "tests": report_data.get("tests", [])
    }

    logger.info("Generating AI summary...")

    markdown_summary: str = client.summarize_report(report_info, healing_data)
    markdown_summary = strip_markdown_fences(markdown_summary)

    actual_defects: List[Dict[str, Any]] = healing_data.get("actual_defects", [])
    if actual_defects:
        logger.info(f"Generating detailed bug report for {len(actual_defects)} defect(s)...")
        try:
            bugs_file: str = generate_bugs_report(healing_analysis_path)
            if bugs_file:
                logger.info(f"BUGS.md generated successfully: {bugs_file}")
                markdown_summary += f"\n\n---\n\n## Bug Report\n\n"
                markdown_summary += f"**{len(actual_defects)} potential bug(s) identified.**\n\n"
                markdown_summary += f"Detailed bug analysis available in: [`reports/BUGS.md`](../BUGS.md)\n\n"
                markdown_summary += f"Each bug includes:\n"
                markdown_summary += f"- Root cause analysis\n"
                markdown_summary += f"- Severity assessment\n"
                markdown_summary += f"- Reproduction steps\n"
                markdown_summary += f"- Suggested investigation areas\n"
                markdown_summary += f"- Potential fixes\n"
            else:
                logger.warning("BUGS.md generation returned empty path")
        except Exception as e:
            logger.error(f"Error generating BUGS.md: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    else:
        logger.info("No actual defects found - skipping BUGS.md generation")

    timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    summary_filename: str = f"summary_{timestamp}.md"
    summary_path: Path = project_root / "reports" / "summaries" / summary_filename
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with open(summary_path, "w") as f:
        f.write(markdown_summary)

    logger.info(f"Summary saved to: {summary_path}")

    return str(summary_path)

if __name__ == "__main__":
    summary_file: str = summarize_report(
        "reports/html/report.html",
        "reports/healing_analysis.json"
    )
    logger.info(f"Summary generated: {summary_file}")
