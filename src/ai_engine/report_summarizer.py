import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient

def summarize_report(html_report_path: str, healing_analysis_path: str) -> str:
    client = OpenAIClient()
    
    project_root = Path(__file__).parent.parent.parent
    html_path = project_root / html_report_path
    healing_path = project_root / healing_analysis_path
    
    json_report_path = project_root / "reports" / "pytest-report.json"
    
    report_data = {}
    if json_report_path.exists():
        with open(json_report_path, "r") as f:
            report_data = json.load(f)
    
    healing_data = {}
    if healing_path.exists():
        with open(healing_path, "r") as f:
            healing_data = json.load(f)
    
    summary = report_data.get("summary", {})
    
    report_info = {
        "total": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
        "duration": summary.get("duration", 0),
        "tests": report_data.get("tests", [])
    }
    
    print("Generating AI summary...")
    
    markdown_summary = client.summarize_report(report_info, healing_data)
    
    if markdown_summary.startswith("```markdown"):
        markdown_summary = markdown_summary[11:]
    if markdown_summary.startswith("```"):
        markdown_summary = markdown_summary[3:]
    if markdown_summary.endswith("```"):
        markdown_summary = markdown_summary[:-3]
    markdown_summary = markdown_summary.strip()
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    summary_filename = f"summary_{timestamp}.md"
    summary_path = project_root / "reports" / "summaries" / summary_filename
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_path, "w") as f:
        f.write(markdown_summary)
    
    print(f"Summary saved to: {summary_path}")
    
    return str(summary_path)

if __name__ == "__main__":
    summary_file = summarize_report(
        "reports/html/report.html",
        "reports/healing_analysis.json"
    )
    print(f"\nSummary generated: {summary_file}")

