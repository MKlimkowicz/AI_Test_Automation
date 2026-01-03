import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.ai_client import AIClient
from utils.config import config
from utils.logger import get_logger
from utils.app_metadata import AppMetadata
from utils.helpers import strip_markdown_fences
from utils.cache import AnalysisCache

logger = get_logger(__name__)

_code_rag = None

def _get_code_rag():
    global _code_rag
    if _code_rag is None and config.ENABLE_VECTOR_DB:
        try:
            from utils.code_rag import get_code_rag
            _code_rag = get_code_rag()
            logger.info("Code RAG enabled for enhanced analysis")
        except Exception as e:
            logger.warning(f"Could not initialize Code RAG: {e}")
    return _code_rag

def _index_code_for_rag(app_dir: str, languages: List[str]) -> Dict[str, int]:
    rag = _get_code_rag()
    if rag is None:
        return {}

    try:
        app_path = Path(app_dir)
        extensions = []
        for lang in languages:
            extensions.extend(LANGUAGE_EXTENSIONS.get(lang, []))

        if not extensions:
            extensions = ['.py']  # Default to Python

        stats = rag.index_directory(
            app_path,
            extensions=extensions,
            exclude_patterns=['test_', '_test.', 'tests/', '__pycache__', 'node_modules', '.git']
        )
        logger.info(f"Code RAG indexed {stats['chunks']} chunks from {stats['files']} files")
        return stats
    except Exception as e:
        logger.warning(f"Failed to index code for RAG: {e}")
        return {}

def _get_rag_context(app_type: str = "rest_api") -> str:
    rag = _get_code_rag()
    if rag is None:
        return ""

    try:
        context = rag.get_context_for_analysis(app_type)
        if context:
            logger.debug(f"Retrieved RAG context ({len(context)} chars)")
        return context
    except Exception as e:
        logger.warning(f"Failed to get RAG context: {e}")
        return ""

_change_detector = None

def _get_change_detector():
    global _change_detector
    if _change_detector is None and config.ENABLE_VECTOR_DB:
        try:
            from utils.change_detector import get_change_detector
            _change_detector = get_change_detector()
            logger.info("Change detection enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Change Detector: {e}")
    return _change_detector

def _check_for_changes(code_files: Dict[str, Tuple[str, str]]) -> Tuple[bool, Optional[Any]]:
    detector = _get_change_detector()
    if detector is None:
        return True, None  # Assume changes if no detector

    try:
        files_dict = {path: content for path, (content, _) in code_files.items()}
        should_regen, report = detector.should_regenerate_tests(files_dict)
        return should_regen, report
    except Exception as e:
        logger.warning(f"Change detection failed: {e}")
        return True, None

def _save_code_snapshot(code_files: Dict[str, Tuple[str, str]]) -> None:
    detector = _get_change_detector()
    if detector is None:
        return

    try:
        files_dict = {path: content for path, (content, _) in code_files.items()}
        detector.save_run_snapshot(files_dict)
        logger.debug("Saved code snapshot for change detection")
    except Exception as e:
        logger.warning(f"Failed to save code snapshot: {e}")

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

def _record_analysis_analytics(
    files_count: int,
    languages: List[str],
    app_type: str
) -> None:
    analytics = _get_analytics()
    if analytics is None:
        return

    try:
        analytics.record_analysis(
            files_analyzed=files_count,
            languages=languages,
            app_type=app_type
        )
    except Exception as e:
        logger.warning(f"Failed to record analysis analytics: {e}")

LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
    'python': ['.py'],
    'javascript': ['.js', '.jsx', '.mjs'],
    'typescript': ['.ts', '.tsx'],
    'java': ['.java'],
    'go': ['.go'],
    'ruby': ['.rb'],
    'php': ['.php'],
    'csharp': ['.cs'],
    'cpp': ['.cpp', '.cc', '.cxx', '.hpp', '.h'],
    'rust': ['.rs'],
    'swift': ['.swift'],
    'kotlin': ['.kt', '.kts'],
    'scala': ['.scala'],
    'r': ['.r', '.R'],
    'shell': ['.sh', '.bash'],
    'sql': ['.sql']
}

CONFIG_FILES: Dict[str, List[str]] = {
    'javascript': ['package.json', 'package-lock.json', 'tsconfig.json', '.eslintrc.json'],
    'typescript': ['package.json', 'package-lock.json', 'tsconfig.json', '.eslintrc.json'],
    'python': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile', 'poetry.lock'],
    'rust': ['Cargo.toml', 'Cargo.lock'],
    'go': ['go.mod', 'go.sum'],
    'java': ['pom.xml', 'build.gradle', 'build.gradle.kts'],
    'ruby': ['Gemfile', 'Gemfile.lock'],
    'php': ['composer.json', 'composer.lock'],
    'csharp': ['.csproj', 'packages.config'],
    'swift': ['Package.swift'],
    'kotlin': ['build.gradle.kts', 'settings.gradle.kts'],
    'scala': ['build.sbt', 'build.sc']
}

IGNORED_DIRS: set[str] = {'__pycache__', 'venv', 'env', '.venv', 'node_modules', '.git', 'documentation'}

def detect_languages(app_dir: str) -> List[str]:
    app_path: Path = Path(app_dir)

    if not app_path.exists():
        logger.warning(f"Directory does not exist: {app_dir}")
        return []

    extension_counts: Counter[str] = Counter()

    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            ext: str = Path(file).suffix.lower()
            if ext:
                extension_counts[ext] += 1

    detected_languages: List[str] = []
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        for ext in extensions:
            if extension_counts.get(ext, 0) > 0:
                detected_languages.append(lang)
                break

    logger.debug(f"Detected languages: {detected_languages}")
    return detected_languages

def get_language_for_extension(ext: str) -> str:
    ext_lower: str = ext.lower()
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        if ext_lower in extensions:
            return lang
    return 'text'

def scan_code_files(app_dir: str, languages: List[str]) -> Dict[str, Tuple[str, str]]:
    app_path: Path = Path(app_dir)

    if not app_path.exists():
        logger.warning(f"Directory does not exist: {app_dir}")
        return {}

    target_extensions: set[str] = set()
    for lang in languages:
        target_extensions.update(LANGUAGE_EXTENSIONS.get(lang, []))

    code_files: Dict[str, Tuple[str, str]] = {}
    max_file_size: int = config.MAX_FILE_SIZE_KB * 1024

    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            ext: str = Path(file).suffix.lower()
            if ext in target_extensions:
                file_path: Path = Path(root) / file
                relative_path: Path = file_path.relative_to(app_path)

                try:
                    file_size: int = file_path.stat().st_size
                    if file_size > max_file_size:
                        logger.debug(f"Skipping {relative_path} (too large: {file_size} bytes)")
                        continue

                    with open(file_path, 'r', encoding='utf-8') as f:
                        content: str = f.read()
                        language: str = get_language_for_extension(ext)
                        code_files[str(relative_path)] = (content, language)
                        logger.debug(f"Read: {relative_path} ({file_size} bytes, {language})")

                except Exception as e:
                    logger.warning(f"Could not read {relative_path}: {e}")

    return code_files

def scan_config_files(app_dir: str, languages: List[str]) -> Dict[str, Tuple[str, str]]:
    app_path: Path = Path(app_dir)

    if not app_path.exists():
        return {}

    config_files_found: Dict[str, Tuple[str, str]] = {}
    max_file_size: int = config.MAX_CONFIG_FILE_SIZE_KB * 1024

    target_config_files: set[str] = set()
    for lang in languages:
        if lang in CONFIG_FILES:
            target_config_files.update(CONFIG_FILES[lang])

    if not target_config_files:
        return {}

    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            if file in target_config_files or any(file.endswith(ext) for ext in target_config_files if ext.startswith('.')):
                file_path: Path = Path(root) / file
                relative_path: Path = file_path.relative_to(app_path)

                try:
                    file_size: int = file_path.stat().st_size
                    if file_size > max_file_size:
                        logger.debug(f"Skipping config {relative_path} (too large: {file_size} bytes)")
                        continue

                    with open(file_path, 'r', encoding='utf-8') as f:
                        content: str = f.read()
                        config_files_found[str(relative_path)] = (content, 'config')
                        logger.debug(f"Read config: {relative_path} ({file_size} bytes)")

                except Exception as e:
                    logger.warning(f"Could not read config {relative_path}: {e}")

    return config_files_found

def scan_documentation(doc_dir: str) -> Dict[str, str]:
    doc_path: Path = Path(doc_dir)

    if not doc_path.exists():
        logger.debug(f"Documentation directory not found: {doc_dir}")
        return {}

    doc_files: Dict[str, str] = {}
    doc_extensions: set[str] = {'.md', '.txt', '.rst', '.adoc'}
    max_file_size: int = config.MAX_CONFIG_FILE_SIZE_KB * 1024

    for root, dirs, files in os.walk(doc_path):
        for file in files:
            ext: str = Path(file).suffix.lower()
            if ext in doc_extensions:
                file_path: Path = Path(root) / file
                relative_path: Path = file_path.relative_to(doc_path)

                try:
                    file_size: int = file_path.stat().st_size
                    if file_size > max_file_size:
                        logger.debug(f"Skipping documentation {relative_path} (too large: {file_size} bytes)")
                        continue

                    with open(file_path, 'r', encoding='utf-8') as f:
                        content: str = f.read()
                        doc_files[str(relative_path)] = content
                        logger.debug(f"Read documentation: {relative_path} ({file_size} bytes)")

                except Exception as e:
                    logger.warning(f"Could not read documentation {relative_path}: {e}")

    return doc_files

def analyze_target(app_dir: Optional[str] = None, use_cache: bool = True, force: bool = False) -> str:
    if app_dir is None:
        project_root: Path = config.get_project_root()
        app_dir = str(project_root / config.APP_DIR)

    logger.info(f"Scanning application in: {app_dir}")

    detected_languages: List[str] = detect_languages(app_dir)

    if detected_languages:
        logger.info(f"Detected languages: {', '.join(detected_languages)}")
        code_files: Dict[str, Tuple[str, str]] = scan_code_files(app_dir, detected_languages)
        config_files_scanned: Dict[str, Tuple[str, str]] = scan_config_files(app_dir, detected_languages)
    else:
        logger.warning("No code files detected in app directory")
        code_files = {}
        config_files_scanned = {}

    code_files.update(config_files_scanned)

    code_files = {k: v for k, v in code_files.items() if 'sample_api' in k}

    doc_dir: str = str(Path(app_dir) / "documentation")
    logger.info(f"Scanning documentation in: {doc_dir}")
    doc_files: Dict[str, str] = scan_documentation(doc_dir)

    doc_files = {k: v for k, v in doc_files.items() if 'sample_api' in k}

    if not code_files and not doc_files:
        logger.warning("No code or documentation found. Creating placeholder analysis.")
        analysis_md: str = f"""# Code Analysis Report

- Total Files: 0
- Languages Detected: None
- Documentation Files: 0
- Analysis Date: {datetime.now().strftime("%Y-%m-%d")}

No code or documentation files found in the app directory.

1. Add application code to the app directory, or
2. Add documentation to app/documentation directory
3. Run analyzer again after adding content
"""
        project_root = config.get_project_root()
        output_path: Path = project_root / "reports" / "analysis.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(analysis_md)

        logger.info(f"Placeholder analysis saved to: {output_path}")
        return str(output_path)

    cache: Optional[AnalysisCache] = None
    cached_result: Optional[Tuple[str, Dict]] = None

    if use_cache and config.ENABLE_CACHE:
        cache = AnalysisCache(ttl_seconds=config.CACHE_TTL_SECONDS)
        cached_result = cache.get_analysis(code_files, doc_files)

        if cached_result:
            analysis_md, metadata_dict = cached_result
            logger.info("Using cached analysis results")

            project_root = config.get_project_root()
            output_path = project_root / "reports" / "analysis.md"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                f.write(analysis_md)

            metadata: AppMetadata = AppMetadata.from_dict(metadata_dict)
            metadata_path: Path = project_root / "reports" / "app_metadata.json"
            metadata.save(metadata_path)

            logger.info(f"Cached analysis restored to: {output_path}")
            return str(output_path)

    if not force and config.ENABLE_VECTOR_DB:
        has_changes, change_report = _check_for_changes(code_files)
        if not has_changes and change_report is not None:
            logger.info("No significant changes detected since last run")
            project_root = config.get_project_root()
            output_path = project_root / "reports" / "analysis.md"
            if output_path.exists():
                logger.info(f"Using previous analysis: {output_path}")
                logger.info(f"Change summary: {change_report.total_changes} changes")
                return str(output_path)

    logger.info(f"Found {len(code_files)} code file(s) and {len(doc_files)} documentation file(s)")

    rag_stats = _index_code_for_rag(app_dir, detected_languages)

    rag_context = _get_rag_context()

    logger.info(f"Analyzing with Claude ({config.CLAUDE_MODEL})...")

    client: AIClient = AIClient()
    analysis_md = client.analyze_code_and_docs(
        code_files,
        doc_files,
        detected_languages,
        rag_context=rag_context
    )
    analysis_md = strip_markdown_fences(analysis_md)

    project_root = config.get_project_root()
    output_path = project_root / "reports" / "analysis.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(analysis_md)

    logger.info(f"Markdown report saved to: {output_path}")

    logger.info("Generating structured metadata...")
    metadata_dict = client.generate_app_metadata(code_files, doc_files, detected_languages)
    metadata = AppMetadata.from_dict(metadata_dict)

    metadata_path = project_root / "reports" / "app_metadata.json"
    metadata.save(metadata_path)
    logger.info(f"Structured metadata saved to: {metadata_path}")

    if cache is not None:
        cache.set_analysis(code_files, doc_files, analysis_md, metadata_dict)
        logger.info("Analysis results cached")

    _save_code_snapshot(code_files)

    _record_analysis_analytics(
        files_count=len(code_files),
        languages=detected_languages,
        app_type=metadata_dict.get("app_type", "unknown")
    )

    logger.info("Analysis complete!")

    preview: str = analysis_md[:500] + "..." if len(analysis_md) > 500 else analysis_md
    logger.debug(f"Analysis Preview:\n{'=' * 80}\n{preview}\n{'=' * 80}")

    return str(output_path)

if __name__ == "__main__":
    analyze_target()
