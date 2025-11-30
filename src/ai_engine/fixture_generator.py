import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


def _clean_fixture_code(code: str) -> str:
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


def read_analysis(analysis_path: Path) -> Optional[str]:
    if not analysis_path.exists():
        logger.error(f"Analysis file not found at {analysis_path}")
        return None
    
    with open(analysis_path, "r") as f:
        return f.read()


def read_best_practices(best_practices_path: Path) -> Optional[str]:
    if not best_practices_path.exists():
        logger.warning(f"Best practices file not found at {best_practices_path}")
        return ""
    
    with open(best_practices_path, "r") as f:
        return f.read()


def generate_fixtures(
    analysis_md_path: str = None,
    best_practices_path: str = None,
    output_path: str = None
) -> Optional[str]:
    project_root = config.get_project_root()
    
    if analysis_md_path is None:
        analysis_md_path = str(project_root / "reports" / "analysis.md")
    
    if best_practices_path is None:
        best_practices_path = str(project_root / "test_templates" / "test_best_practices.md")
    
    if output_path is None:
        output_path = str(project_root / "tests" / "conftest.py")
    
    analysis_path = Path(analysis_md_path)
    practices_path = Path(best_practices_path)
    conftest_path = Path(output_path)
    
    analysis_markdown = read_analysis(analysis_path)
    if analysis_markdown is None:
        logger.error("Please run analyzer.py first to generate the analysis report.")
        return None
    
    logger.info(f"Reading analysis from: {analysis_path}")
    logger.info(f"Analysis size: {len(analysis_markdown)} characters")
    
    best_practices = read_best_practices(practices_path)
    if best_practices:
        logger.info(f"Reading best practices from: {practices_path}")
        logger.info(f"Best practices size: {len(best_practices)} characters")
    
    client = OpenAIClient()
    
    logger.info("Generating fixtures with AI...")
    fixture_code = client.generate_fixtures(analysis_markdown, best_practices)
    fixture_code = _clean_fixture_code(fixture_code)
    
    conftest_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(conftest_path, "w") as f:
        f.write(fixture_code)
    
    logger.info(f"Generated conftest.py at: {conftest_path}")
    
    return str(conftest_path)


if __name__ == "__main__":
    logger.info("Generating fixtures from analysis...")
    result = generate_fixtures()
    
    if result:
        logger.info(f"{'=' * 80}")
        logger.info(f"Successfully generated fixtures:")
        logger.info(f"  - {result}")
        logger.info(f"{'=' * 80}")
    else:
        logger.warning("Failed to generate fixtures. Please check the analysis file.")

