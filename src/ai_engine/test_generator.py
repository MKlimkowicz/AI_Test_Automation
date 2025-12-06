import sys
import re
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.ai_client import AIClient
from utils.config import config
from utils.logger import get_logger
from utils.helpers import strip_markdown_fences

logger = get_logger(__name__)

CATEGORY_FILE_MAP = {
    "Functional": "test_functional.py",
    "Security": "test_security.py",
    "Validation": "test_validation.py",
    "Performance": "test_performance.py",
    "Integration": "test_integration.py",
}


def extract_scenarios_by_category(analysis_md: str) -> Dict[str, List[str]]:
    scenarios_by_category: Dict[str, List[str]] = {}
    
    scenario_section = re.search(
        r'##\s+Recommended Test Scenarios\s*\n(.*)',
        analysis_md,
        re.DOTALL | re.IGNORECASE
    )
    
    if scenario_section:
        scenario_text = scenario_section.group(1)

        categories = ['Functional Tests', 'Performance Tests', 'Security Tests', 'Validation Tests', 'Integration Tests']
        
        for category in categories:
            category_pattern = rf'###\s+{category}\s*\n(.*?)(?=\n###\s+[A-Z]|\Z)'
            category_match = re.search(category_pattern, scenario_text, re.DOTALL | re.IGNORECASE)
            
            if category_match:
                category_name = category.replace(' Tests', '')
                category_content = category_match.group(1)
                lines = category_content.strip().split('\n')
                
                category_scenarios = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('####'):
                        continue
                    if line.startswith('|'):
                        continue
                    if line.startswith('List ') or line.startswith('Only include') or line.startswith('Suggest '):
                        continue
                    
                    if re.match(r'^\d+[\.\)]\s+', line):
                        scenario = re.sub(r'^\d+[\.\)]\s+', '', line)
                        scenario = re.sub(r'\*\*([^*]+)\*\*', r'\1', scenario)
                        scenario = scenario.strip()
                        if scenario and len(scenario) > 5:
                            category_scenarios.append(scenario)
                    elif line.startswith('-') or line.startswith('*'):
                        scenario = line[1:].strip()
                        scenario = re.sub(r'\*\*([^*]+)\*\*', r'\1', scenario)
                        if scenario and not scenario.endswith(':') and len(scenario) > 5:
                            category_scenarios.append(scenario)
                
                if category_scenarios:
                    max_tests = config.MAX_TESTS_PER_CATEGORY
                    if len(category_scenarios) > max_tests:
                        logger.info(f"Limiting {category_name} from {len(category_scenarios)} to {max_tests} scenarios")
                        category_scenarios = category_scenarios[:max_tests]
                    scenarios_by_category[category_name] = category_scenarios
                    logger.info(f"Using {len(category_scenarios)} scenarios for {category_name}")
    
    if not scenarios_by_category:
        scenarios_by_category["Functional"] = ["Generic test based on code analysis"]
    
    total = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Total extracted: {total} scenarios in {len(scenarios_by_category)} categories")
    return scenarios_by_category


def _generate_category_tests(
    client: AIClient,
    category: str,
    scenarios: List[str],
    analysis_markdown: str,
    output_path: Path,
    app_metadata: Dict
) -> Tuple[str, Optional[str]]:
    try:
        filename = CATEGORY_FILE_MAP.get(category, f"test_{category.lower()}.py")
        logger.info(f"Generating {category} tests ({len(scenarios)} scenarios) -> {filename}")
        
        test_code = client.generate_category_tests(
            analysis_markdown, 
            category, 
            scenarios,
            app_metadata
        )
        test_code = strip_markdown_fences(test_code)
        
        test_filepath = output_path / filename
        
        with open(test_filepath, "w") as f:
            f.write(test_code)
        
        logger.info(f"Generated: {test_filepath} ({len(scenarios)} test functions)")
        return (category, str(test_filepath))
    
    except Exception as e:
        logger.error(f"Failed to generate {category} tests: {e}")
        return (category, None)


def generate_tests_by_category(
    scenarios_by_category: Dict[str, List[str]],
    analysis_markdown: str,
    output_path: Path,
    app_metadata: Dict
) -> List[str]:
    client = AIClient()
    generated_files = []
    failed_categories = []
    
    logger.info(f"Generating {len(scenarios_by_category)} category files sequentially...")
    logger.info(f"Categories to generate: {list(scenarios_by_category.keys())}")
    logger.info(f"Using app_type={app_metadata.get('app_type')}, port={app_metadata.get('port')}")
    
    for category, scenarios in scenarios_by_category.items():
        logger.info(f"Processing category: {category} ({len(scenarios)} scenarios)")
        cat, filepath = _generate_category_tests(
            client, category, scenarios, analysis_markdown, output_path, app_metadata
        )
        if filepath:
            generated_files.append(filepath)
            logger.info(f"Successfully generated: {filepath}")
        else:
            failed_categories.append(cat)
            logger.error(f"Failed to generate tests for category: {cat}")
    
    if failed_categories:
        logger.warning(f"{len(failed_categories)} category(ies) failed to generate: {failed_categories}")
    
    total_scenarios = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Generation complete: {len(generated_files)}/{len(scenarios_by_category)} files, {total_scenarios} total scenarios")
    return generated_files


def load_app_metadata(project_root: Path) -> Dict:
    metadata_path = project_root / "reports" / "app_metadata.json"
    
    if metadata_path.exists():
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            logger.info(f"Loaded app metadata: app_type={metadata.get('app_type')}, port={metadata.get('port')}")
            return metadata
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse app_metadata.json: {e}")
    else:
        logger.warning(f"No app_metadata.json found at {metadata_path}")
    
    return {
        "app_type": "rest_api",
        "framework": "unknown",
        "languages": [],
        "base_url": "http://localhost",
        "port": 8080,
        "auth_required": False
    }


def generate_tests(
    analysis_md_path: str = None,
    output_dir: str = None
) -> List[str]:
    project_root = config.get_project_root()
    
    if analysis_md_path is None:
        analysis_md_path = str(project_root / "reports" / "analysis.md")
    
    if output_dir is None:
        output_dir = "tests/generated"
    
    analysis_path = Path(analysis_md_path)
    
    if not analysis_path.exists():
        logger.error(f"Analysis file not found at {analysis_path}")
        logger.error("Please run analyzer.py first to generate the analysis report.")
        return []
    
    with open(analysis_path, "r") as f:
        analysis_markdown = f.read()
    
    app_metadata = load_app_metadata(project_root)
    
    logger.info(f"Reading analysis from: {analysis_path}")
    logger.info(f"Analysis size: {len(analysis_markdown)} characters")
    logger.info(f"Using app metadata: {app_metadata.get('app_type')}, port={app_metadata.get('port')}")
    logger.info("Generating self-contained tests")
    
    scenarios_by_category = extract_scenarios_by_category(analysis_markdown)
    
    total_scenarios = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Extracted {total_scenarios} test scenarios in {len(scenarios_by_category)} categories:")
    for category, scenarios in scenarios_by_category.items():
        logger.info(f"  - {category}: {len(scenarios)} scenarios")
        for idx, scenario in enumerate(scenarios, 1):
            logger.debug(f"      {idx}. {scenario}")
    
    output_path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)
    
    generated_files = generate_tests_by_category(
        scenarios_by_category,
        analysis_markdown,
        output_path,
        app_metadata
    )
    
    return generated_files


if __name__ == "__main__":
    logger.info("Generating tests from analysis...")
    files = generate_tests()
    
    if files:
        logger.info(f"{'=' * 80}")
        logger.info(f"Successfully generated {len(files)} test file(s):")
        for file in files:
            logger.info(f"  - {file}")
        logger.info(f"{'=' * 80}")
    else:
        logger.warning("No tests generated. Please check the analysis file.")
