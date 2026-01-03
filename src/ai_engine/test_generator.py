import sys
import re
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.ai_client import AIClient
from utils.config import config
from utils.logger import get_logger
from utils.helpers import strip_markdown_fences
from utils.app_metadata import load_app_metadata

logger = get_logger(__name__)

_test_deduplicator = None
_code_rag = None
_analytics = None

def _get_analytics():
    global _analytics
    if _analytics is None:
        try:
            from utils.analytics import get_analytics
            _analytics = get_analytics()
        except Exception as e:
            logger.warning(f"Could not initialize Analytics: {e}")
    return _analytics

def _get_test_deduplicator():
    global _test_deduplicator
    if _test_deduplicator is None and config.ENABLE_VECTOR_DB:
        try:
            from utils.test_deduplicator import get_test_deduplicator
            _test_deduplicator = get_test_deduplicator()
            logger.info("Vector-based test deduplication enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Test Deduplicator: {e}")
    return _test_deduplicator

def _get_code_rag():
    global _code_rag
    if _code_rag is None and config.ENABLE_VECTOR_DB:
        try:
            from utils.code_rag import get_code_rag
            _code_rag = get_code_rag()
        except Exception as e:
            logger.warning(f"Could not initialize Code RAG: {e}")
    return _code_rag

def _get_rag_context_for_scenarios(category: str, scenarios: List[str]) -> str:
    rag = _get_code_rag()
    if rag is None:
        return ""

    try:
        combined_query = f"{category} " + " ".join(scenarios[:3])
        context = rag.get_context_for_scenario(combined_query, category)
        if context:
            logger.debug(f"Retrieved RAG context for {category} ({len(context)} chars)")
        return context
    except Exception as e:
        logger.warning(f"Failed to get RAG context for {category}: {e}")
        return ""

CATEGORY_FILE_MAP: Dict[str, str] = {
    "Functional": "test_functional.py",
    "Security": "test_security.py",
    "Validation": "test_validation.py",
    "Performance": "test_performance.py",
    "Integration": "test_integration.py",
}

def extract_scenarios_by_category(analysis_md: str) -> Dict[str, List[str]]:
    scenarios_by_category: Dict[str, List[str]] = {}

    scenario_section = re.search(
        r'##\s+(?:Recommended\s+)?Test Scenarios\s*\n(.*)',
        analysis_md,
        re.DOTALL | re.IGNORECASE
    )

    if scenario_section:
        scenario_text: str = scenario_section.group(1)

        categories: List[str] = ['Functional Tests', 'Performance Tests', 'Security Tests', 'Validation Tests', 'Integration Tests']

        for category in categories:
            category_pattern: str = rf'###\s+{category}\s*\n(.*?)(?=\n###\s+[A-Z]|\Z)'
            category_match = re.search(category_pattern, scenario_text, re.DOTALL | re.IGNORECASE)

            if category_match:
                category_name: str = category.replace(' Tests', '')
                category_content: str = category_match.group(1)
                lines: List[str] = category_content.strip().split('\n')

                category_scenarios: List[str] = []
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
                        scenario: str = re.sub(r'^\d+[\.\)]\s+', '', line)
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
                    max_tests: int = config.MAX_TESTS_PER_CATEGORY
                    if len(category_scenarios) > max_tests:
                        logger.info(f"Limiting {category_name} from {len(category_scenarios)} to {max_tests} scenarios")
                        category_scenarios = category_scenarios[:max_tests]
                    scenarios_by_category[category_name] = category_scenarios
                    logger.info(f"Using {len(category_scenarios)} scenarios for {category_name}")

    if not scenarios_by_category:
        scenarios_by_category["Functional"] = ["Generic test based on code analysis"]

    total: int = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Total extracted: {total} scenarios in {len(scenarios_by_category)} categories")
    return scenarios_by_category

def deduplicate_scenarios(
    scenarios_by_category: Dict[str, List[str]],
    client: AIClient
) -> Dict[str, List[str]]:
    if not config.ENABLE_TEST_DEDUPLICATION:
        return scenarios_by_category

    deduplicated: Dict[str, List[str]] = {}

    for category, scenarios in scenarios_by_category.items():
        if len(scenarios) <= 1:
            deduplicated[category] = scenarios
            continue

        logger.info(f"Deduplicating {category} scenarios ({len(scenarios)} scenarios)...")
        unique_scenarios: List[str] = client.deduplicate_scenarios(
            scenarios,
            threshold=config.DEDUPLICATION_SIMILARITY_THRESHOLD
        )
        deduplicated[category] = unique_scenarios
        logger.info(f"{category}: {len(scenarios)} -> {len(unique_scenarios)} scenarios after deduplication")

    return deduplicated

def _generate_category_tests(
    client: AIClient,
    category: str,
    scenarios: List[str],
    analysis_markdown: str,
    output_path: Path,
    app_metadata: Dict[str, Any]
) -> Tuple[str, Optional[str], Dict[str, int]]:
    dedup_stats: Dict[str, int] = {"original": 0, "removed": 0}

    try:
        filename: str = CATEGORY_FILE_MAP.get(category, f"test_{category.lower()}.py")
        logger.info(f"Generating {category} tests ({len(scenarios)} scenarios) -> {filename}")

        rag_context = _get_rag_context_for_scenarios(category, scenarios)

        test_code: str = client.generate_category_tests(
            analysis_markdown,
            category,
            scenarios,
            app_metadata,
            include_negative_tests=config.ENABLE_NEGATIVE_TESTS,
            use_data_factories=config.ENABLE_DATA_FACTORIES,
            rag_context=rag_context
        )
        test_code = strip_markdown_fences(test_code)

        deduplicator = _get_test_deduplicator()
        if deduplicator:
            test_code, original_count, removed_count = deduplicator.deduplicate_code(
                test_code, category
            )
            dedup_stats = {"original": original_count, "removed": removed_count}
            if removed_count > 0:
                logger.info(
                    f"Vector deduplication: removed {removed_count}/{original_count} "
                    f"duplicate tests in {category}"
                )

        test_filepath: Path = output_path / filename

        with open(test_filepath, "w") as f:
            f.write(test_code)

        logger.info(f"Generated: {test_filepath} ({len(scenarios)} test functions)")
        return (category, str(test_filepath), dedup_stats)

    except Exception as e:
        logger.error(f"Failed to generate {category} tests: {e}")
        return (category, None, dedup_stats)

def generate_tests_by_category_parallel(
    scenarios_by_category: Dict[str, List[str]],
    analysis_markdown: str,
    output_path: Path,
    app_metadata: Dict[str, Any]
) -> Tuple[List[str], Dict[str, int]]:
    generated_files: List[str] = []
    failed_categories: List[str] = []
    total_dedup_stats: Dict[str, int] = {"original": 0, "removed": 0}

    max_workers: int = min(config.MAX_PARALLEL_WORKERS, len(scenarios_by_category))
    logger.info(f"Generating {len(scenarios_by_category)} category files in parallel (max {max_workers} workers)...")
    logger.info(f"Categories to generate: {list(scenarios_by_category.keys())}")
    logger.info(f"Using app_type={app_metadata.get('app_type')}, port={app_metadata.get('port')}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: Dict[Any, str] = {}

        for category, scenarios in scenarios_by_category.items():
            client: AIClient = AIClient()
            future = executor.submit(
                _generate_category_tests,
                client,
                category,
                scenarios,
                analysis_markdown,
                output_path,
                app_metadata
            )
            futures[future] = category

        for future in as_completed(futures):
            category = futures[future]
            try:
                cat, filepath, dedup_stats = future.result()
                total_dedup_stats["original"] += dedup_stats.get("original", 0)
                total_dedup_stats["removed"] += dedup_stats.get("removed", 0)
                if filepath:
                    generated_files.append(filepath)
                    logger.info(f"Successfully generated: {filepath}")
                else:
                    failed_categories.append(cat)
                    logger.error(f"Failed to generate tests for category: {cat}")
            except Exception as e:
                failed_categories.append(category)
                logger.error(f"Exception generating {category} tests: {e}")

    if failed_categories:
        logger.warning(f"{len(failed_categories)} category(ies) failed to generate: {failed_categories}")

    total_scenarios: int = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Generation complete: {len(generated_files)}/{len(scenarios_by_category)} files, {total_scenarios} total scenarios")

    if total_dedup_stats["removed"] > 0:
        logger.info(
            f"Vector deduplication total: removed {total_dedup_stats['removed']}/{total_dedup_stats['original']} duplicate tests"
        )

    return generated_files, total_dedup_stats

def generate_tests_by_category_sequential(
    scenarios_by_category: Dict[str, List[str]],
    analysis_markdown: str,
    output_path: Path,
    app_metadata: Dict[str, Any]
) -> Tuple[List[str], Dict[str, int]]:
    client: AIClient = AIClient()
    generated_files: List[str] = []
    failed_categories: List[str] = []
    total_dedup_stats: Dict[str, int] = {"original": 0, "removed": 0}

    logger.info(f"Generating {len(scenarios_by_category)} category files sequentially...")
    logger.info(f"Categories to generate: {list(scenarios_by_category.keys())}")
    logger.info(f"Using app_type={app_metadata.get('app_type')}, port={app_metadata.get('port')}")

    for category, scenarios in scenarios_by_category.items():
        logger.info(f"Processing category: {category} ({len(scenarios)} scenarios)")
        cat, filepath, dedup_stats = _generate_category_tests(
            client, category, scenarios, analysis_markdown, output_path, app_metadata
        )
        total_dedup_stats["original"] += dedup_stats.get("original", 0)
        total_dedup_stats["removed"] += dedup_stats.get("removed", 0)
        if filepath:
            generated_files.append(filepath)
            logger.info(f"Successfully generated: {filepath}")
        else:
            failed_categories.append(cat)
            logger.error(f"Failed to generate tests for category: {cat}")

    if failed_categories:
        logger.warning(f"{len(failed_categories)} category(ies) failed to generate: {failed_categories}")

    total_scenarios: int = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Generation complete: {len(generated_files)}/{len(scenarios_by_category)} files, {total_scenarios} total scenarios")

    if total_dedup_stats["removed"] > 0:
        logger.info(
            f"Vector deduplication total: removed {total_dedup_stats['removed']}/{total_dedup_stats['original']} duplicate tests"
        )

    return generated_files, total_dedup_stats

def generate_shared_conftest(output_path: Path, app_metadata: Dict[str, Any]) -> Optional[str]:
    if not config.ENABLE_SHARED_FIXTURES:
        return None

    logger.info("Generating shared conftest.py for fixtures...")

    app_type: str = app_metadata.get("app_type", "rest_api")
    base_url: str = app_metadata.get("base_url", "http://localhost")
    port: int = app_metadata.get("port", 8080)
    full_url: str = f"{base_url}:{port}"

    conftest_content: str = f'''import pytest
import requests
import uuid
from typing import Generator, Dict, Any

BASE_URL: str = "{full_url}"

class TestDataFactory:
    @staticmethod
    def valid_user() -> Dict[str, str]:
        uid: str = uuid.uuid4().hex[:8]
        return {{
            "username": f"user_{{uid}}",
            "email": f"user_{{uid}}@test.com",
            "password": f"Pass_{{uid}}123!"
        }}

    @staticmethod
    def invalid_user_short_username() -> Dict[str, str]:
        return {{
            "username": "ab",
            "email": "test@test.com",
            "password": "ValidPass123!"
        }}

    @staticmethod
    def invalid_user_bad_email() -> Dict[str, str]:
        uid: str = uuid.uuid4().hex[:8]
        return {{
            "username": f"user_{{uid}}",
            "email": "invalid-email",
            "password": "ValidPass123!"
        }}

@pytest.fixture
def api_client() -> Generator[requests.Session, None, None]:
    session: requests.Session = requests.Session()
    session.headers.update({{"Content-Type": "application/json"}})
    yield session
    session.close()

@pytest.fixture
def api_base_url() -> str:
    return BASE_URL

@pytest.fixture
def test_user_data() -> Dict[str, str]:
    return TestDataFactory.valid_user()

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]

@pytest.fixture
def data_factory() -> type:
    return TestDataFactory
'''

    conftest_path: Path = output_path / "conftest.py"
    with open(conftest_path, "w") as f:
        f.write(conftest_content)

    logger.info(f"Generated shared conftest.py: {conftest_path}")
    return str(conftest_path)

def generate_tests(
    analysis_md_path: Optional[str] = None,
    output_dir: Optional[str] = None
) -> List[str]:
    project_root: Path = config.get_project_root()

    if analysis_md_path is None:
        analysis_md_path = str(project_root / "reports" / "analysis.md")

    if output_dir is None:
        output_dir = "tests/generated"

    analysis_path: Path = Path(analysis_md_path)

    if not analysis_path.exists():
        logger.error(f"Analysis file not found at {analysis_path}")
        logger.error("Please run analyzer.py first to generate the analysis report.")
        return []

    with open(analysis_path, "r") as f:
        analysis_markdown: str = f.read()

    app_metadata: Dict[str, Any] = load_app_metadata(project_root)

    logger.info(f"Reading analysis from: {analysis_path}")
    logger.info(f"Analysis size: {len(analysis_markdown)} characters")
    logger.info(f"Using app metadata: {app_metadata.get('app_type')}, port={app_metadata.get('port')}")
    logger.info("Generating self-contained tests")

    scenarios_by_category: Dict[str, List[str]] = extract_scenarios_by_category(analysis_markdown)

    if config.ENABLE_TEST_DEDUPLICATION:
        client: AIClient = AIClient()
        scenarios_by_category = deduplicate_scenarios(scenarios_by_category, client)

    total_scenarios: int = sum(len(s) for s in scenarios_by_category.values())
    logger.info(f"Extracted {total_scenarios} test scenarios in {len(scenarios_by_category)} categories:")
    for category, scenarios in scenarios_by_category.items():
        logger.info(f"  - {category}: {len(scenarios)} scenarios")
        for idx, scenario in enumerate(scenarios, 1):
            logger.debug(f"      {idx}. {scenario}")

    output_path: Path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)

    if config.ENABLE_SHARED_FIXTURES:
        generate_shared_conftest(output_path, app_metadata)

    if config.PARALLEL_TEST_GENERATION:
        generated_files, dedup_stats = generate_tests_by_category_parallel(
            scenarios_by_category,
            analysis_markdown,
            output_path,
            app_metadata
        )
    else:
        generated_files, dedup_stats = generate_tests_by_category_sequential(
            scenarios_by_category,
            analysis_markdown,
            output_path,
            app_metadata
        )

    if dedup_stats.get("removed", 0) > 0:
        deduplicator = _get_test_deduplicator()
        if deduplicator:
            stats = deduplicator.get_stats()
            logger.info(f"Test deduplication index: {stats.get('total_tests_indexed', 0)} unique tests indexed")

    analytics = _get_analytics()
    if analytics:
        try:
            analytics.record_generation(
                scenarios=total_scenarios,
                tests=dedup_stats.get("original", total_scenarios),
                deduplicated=dedup_stats.get("removed", 0),
                categories=list(scenarios_by_category.keys())
            )
        except Exception as e:
            logger.warning(f"Failed to record generation analytics: {e}")

    return generated_files

if __name__ == "__main__":
    logger.info("Generating tests from analysis...")
    files: List[str] = generate_tests()

    if files:
        logger.info(f"{'=' * 80}")
        logger.info(f"Successfully generated {len(files)} test file(s):")
        for file in files:
            logger.info(f"  - {file}")
        logger.info(f"{'=' * 80}")
    else:
        logger.warning("No tests generated. Please check the analysis file.")
