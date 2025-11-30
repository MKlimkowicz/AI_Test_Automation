import sys
import re
from pathlib import Path
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


def read_conftest(conftest_path: Path) -> Optional[str]:
    if not conftest_path.exists():
        logger.warning(f"Conftest file not found at {conftest_path}")
        return None
    
    with open(conftest_path, "r") as f:
        content = f.read()
    
    if not content.strip():
        logger.warning("Conftest file is empty")
        return None
    
    return content


def extract_test_scenarios(analysis_md: str) -> List[str]:
    scenarios = []
    
    scenario_section = re.search(
        r'##\s+Recommended Test Scenarios\s*\n(.*?)(?=\n##|\Z)',
        analysis_md,
        re.DOTALL | re.IGNORECASE
    )
    
    if scenario_section:
        scenario_text = scenario_section.group(1)

        categories = ['Functional Tests', 'Performance Tests', 'Security Tests']
        found_categories = False
        
        for category in categories:
            category_pattern = rf'###\s+{category}\s*\n(.*?)(?=\n###|\Z)'
            category_match = re.search(category_pattern, scenario_text, re.DOTALL | re.IGNORECASE)
            
            if category_match:
                found_categories = True
                category_content = category_match.group(1)
                lines = category_content.strip().split('\n')
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('List ') or line.startswith('Only include') or line.startswith('Suggest '):
                        continue
                    
                    if re.match(r'^\d+[\.\)]\s+', line):
                        scenario = re.sub(r'^\d+[\.\)]\s+', '', line)
                        scenarios.append(f"[{category.replace(' Tests', '')}] {scenario}")

                    elif line.startswith('-') or line.startswith('*'):
                        scenario = line[1:].strip()
                        if scenario and not scenario.endswith(':'):
                            scenarios.append(f"[{category.replace(' Tests', '')}] {scenario}")
        
        if not found_categories:
            lines = scenario_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if re.match(r'^\d+[\.\)]\s+', line):
                    scenario = re.sub(r'^\d+[\.\)]\s+', '', line)
                    scenarios.append(scenario)
                elif line.startswith('-') or line.startswith('*'):
                    scenario = line[1:].strip()
                    if scenario:
                        scenarios.append(scenario)
    
    if not scenarios:
        scenarios = ["Generic test based on code analysis"]
    
    logger.debug(f"Extracted {len(scenarios)} scenarios")
    return scenarios


def _clean_test_code(test_code: str) -> str:
    if test_code.startswith("```python"):
        test_code = test_code[9:]
    if test_code.startswith("```"):
        test_code = test_code[3:]
    if test_code.endswith("```"):
        test_code = test_code[:-3]
    return test_code.strip()


def _generate_single_test(
    client: OpenAIClient,
    scenario: str,
    analysis_markdown: str,
    idx: int,
    output_path: Path,
    conftest_content: Optional[str] = None
) -> Tuple[int, str, Optional[str]]:
    try:
        logger.info(f"Generating tests for scenario {idx + 1}: {scenario[:60]}...")
        
        test_code = client.generate_tests(analysis_markdown, scenario, conftest_content)
        test_code = _clean_test_code(test_code)
        
        test_filename = f"test_scenario_{idx + 1}.py"
        test_filepath = output_path / test_filename
        
        with open(test_filepath, "w") as f:
            f.write(test_code)
        
        logger.info(f"Generated: {test_filepath}")
        return (idx, scenario, str(test_filepath))
    
    except Exception as e:
        logger.error(f"Failed to generate test for scenario {idx + 1}: {e}")
        return (idx, scenario, None)


def generate_tests_parallel(
    scenarios: List[str],
    analysis_markdown: str,
    output_path: Path,
    max_workers: Optional[int] = None,
    conftest_content: Optional[str] = None
) -> List[str]:
    workers = max_workers or config.MAX_PARALLEL_WORKERS
    logger.info(f"Starting parallel test generation with {workers} workers...")
    
    client = OpenAIClient()
    
    generated_files = []
    failed_scenarios = []
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _generate_single_test,
                client,
                scenario,
                analysis_markdown,
                idx,
                output_path,
                conftest_content
            ): idx
            for idx, scenario in enumerate(scenarios)
        }
        
        for future in as_completed(futures):
            idx, scenario, filepath = future.result()
            if filepath:
                generated_files.append(filepath)
            else:
                failed_scenarios.append((idx, scenario))
    
    generated_files.sort(key=lambda x: int(x.split('_')[-1].replace('.py', '')))
    
    if failed_scenarios:
        logger.warning(f"{len(failed_scenarios)} scenario(s) failed to generate")
        for idx, scenario in failed_scenarios:
            logger.warning(f"  - Scenario {idx + 1}: {scenario[:50]}...")
    
    logger.info(f"Parallel generation complete: {len(generated_files)}/{len(scenarios)} successful")
    return generated_files


def generate_tests_sequential(
    scenarios: List[str],
    analysis_markdown: str,
    output_path: Path,
    conftest_content: Optional[str] = None
) -> List[str]:
    client = OpenAIClient()
    generated_files = []
    
    for idx, scenario in enumerate(scenarios):
        logger.info(f"Generating tests for scenario {idx + 1}/{len(scenarios)}: {scenario[:60]}...")
        
        try:
            test_code = client.generate_tests(analysis_markdown, scenario, conftest_content)
            test_code = _clean_test_code(test_code)
            
            test_filename = f"test_scenario_{idx + 1}.py"
            test_filepath = output_path / test_filename
            
            with open(test_filepath, "w") as f:
                f.write(test_code)
            
            generated_files.append(str(test_filepath))
            logger.info(f"Generated: {test_filepath}")
        
        except Exception as e:
            logger.error(f"Failed to generate test for scenario {idx + 1}: {e}")
    
    return generated_files


def generate_tests(
    analysis_md_path: str = None,
    output_dir: str = None,
    parallel: bool = True,
    conftest_path: str = None
) -> List[str]:
    project_root = config.get_project_root()
    
    if analysis_md_path is None:
        analysis_md_path = str(project_root / "reports" / "analysis.md")
    
    if output_dir is None:
        output_dir = "tests/generated"
    
    if conftest_path is None:
        conftest_path = str(project_root / "tests" / "conftest.py")
    
    analysis_path = Path(analysis_md_path)
    
    if not analysis_path.exists():
        logger.error(f"Analysis file not found at {analysis_path}")
        logger.error("Please run analyzer.py first to generate the analysis report.")
        return []
    
    with open(analysis_path, "r") as f:
        analysis_markdown = f.read()
    
    logger.info(f"Reading analysis from: {analysis_path}")
    logger.info(f"Analysis size: {len(analysis_markdown)} characters")
    
    conftest_content = read_conftest(Path(conftest_path))
    if conftest_content:
        logger.info(f"Reading conftest from: {conftest_path}")
        logger.info(f"Conftest size: {len(conftest_content)} characters")
    else:
        logger.info("No conftest.py found, tests will define their own fixtures")
    
    scenarios = extract_test_scenarios(analysis_markdown)
    logger.info(f"Extracted {len(scenarios)} test scenario(s):")
    for idx, scenario in enumerate(scenarios, 1):
        logger.debug(f"  {idx}. {scenario}")
    
    output_path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)
    
    if parallel and len(scenarios) > 1:
        generated_files = generate_tests_parallel(scenarios, analysis_markdown, output_path, conftest_content=conftest_content)
    else:
        generated_files = generate_tests_sequential(scenarios, analysis_markdown, output_path, conftest_content=conftest_content)
    
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
