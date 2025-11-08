import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient

LANGUAGE_EXTENSIONS = {
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

CONFIG_FILES = {
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

def detect_languages(app_dir: str) -> List[str]:
    app_path = Path(app_dir)
    
    if not app_path.exists():
        return []
    
    ignored_dirs = {'__pycache__', 'venv', 'env', '.venv', 'node_modules', '.git', 'documentation'}
    extension_counts = Counter()
    
    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file in files:
            ext = Path(file).suffix.lower()
            if ext:
                extension_counts[ext] += 1
    
    detected_languages = []
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        for ext in extensions:
            if extension_counts.get(ext, 0) > 0:
                detected_languages.append(lang)
                break
    
    return detected_languages

def get_language_for_extension(ext: str) -> str:
    ext_lower = ext.lower()
    for lang, extensions in LANGUAGE_EXTENSIONS.items():
        if ext_lower in extensions:
            return lang
    return 'text'

def scan_code_files(app_dir: str, languages: List[str]) -> Dict[str, Tuple[str, str]]:
    app_path = Path(app_dir)
    
    if not app_path.exists():
        print(f"Warning: Directory {app_dir} does not exist")
        return {}
    
    target_extensions = set()
    for lang in languages:
        target_extensions.update(LANGUAGE_EXTENSIONS.get(lang, []))
    
    code_files = {}
    ignored_dirs = {'__pycache__', 'venv', 'env', '.venv', 'node_modules', '.git', 'documentation'}
    max_file_size = 50 * 1024
    
    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in target_extensions:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(app_path)
                
                try:
                    file_size = file_path.stat().st_size
                    if file_size > max_file_size:
                        print(f"Skipping {relative_path} (too large: {file_size} bytes)")
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        language = get_language_for_extension(ext)
                        code_files[str(relative_path)] = (content, language)
                        print(f"Read: {relative_path} ({file_size} bytes, {language})")
                
                except Exception as e:
                    print(f"Warning: Could not read {relative_path}: {e}")
    
    return code_files

def scan_config_files(app_dir: str, languages: List[str]) -> Dict[str, Tuple[str, str]]:
    app_path = Path(app_dir)
    
    if not app_path.exists():
        return {}
    
    config_files = {}
    max_file_size = 100 * 1024
    
    target_config_files = set()
    for lang in languages:
        if lang in CONFIG_FILES:
            target_config_files.update(CONFIG_FILES[lang])
    
    if not target_config_files:
        return {}
    
    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', 'venv', 'env', '.venv', 'node_modules', '.git', 'documentation'}]
        
        for file in files:
            if file in target_config_files or any(file.endswith(ext) for ext in target_config_files if ext.startswith('.')):
                file_path = Path(root) / file
                relative_path = file_path.relative_to(app_path)
                
                try:
                    file_size = file_path.stat().st_size
                    if file_size > max_file_size:
                        print(f"Skipping config {relative_path} (too large: {file_size} bytes)")
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        config_files[str(relative_path)] = (content, 'config')
                        print(f"Read config: {relative_path} ({file_size} bytes)")
                
                except Exception as e:
                    print(f"Warning: Could not read config {relative_path}: {e}")
    
    return config_files

def scan_documentation(doc_dir: str) -> Dict[str, str]:
    doc_path = Path(doc_dir)
    
    if not doc_path.exists():
        print(f"Documentation directory not found: {doc_dir}")
        return {}
    
    doc_files = {}
    doc_extensions = {'.md', '.txt', '.rst', '.adoc'}
    max_file_size = 100 * 1024
    
    for root, dirs, files in os.walk(doc_path):
        for file in files:
            ext = Path(file).suffix.lower()
            if ext in doc_extensions:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(doc_path)
                
                try:
                    file_size = file_path.stat().st_size
                    if file_size > max_file_size:
                        print(f"Skipping documentation {relative_path} (too large: {file_size} bytes)")
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        doc_files[str(relative_path)] = content
                        print(f"Read documentation: {relative_path} ({file_size} bytes)")
                
                except Exception as e:
                    print(f"Warning: Could not read documentation {relative_path}: {e}")
    
    return doc_files

def analyze_target(app_dir: str = None) -> str:
    if app_dir is None:
        project_root = Path(__file__).parent.parent.parent
        app_dir = str(project_root / "app")
    
    print(f"Scanning application in: {app_dir}")
    
    detected_languages = detect_languages(app_dir)
    
    if detected_languages:
        print(f"Detected languages: {', '.join(detected_languages)}")
        code_files = scan_code_files(app_dir, detected_languages)
        config_files = scan_config_files(app_dir, detected_languages)
    else:
        print("No code files detected in app directory")
        code_files = {}
        config_files = {}
    
    # Merge config files into code files
    code_files.update(config_files)
    
    # TEMPORARY FILTER: Only scan sample_api files (user will revert later)
    code_files = {k: v for k, v in code_files.items() if 'sample_api' in k}
    
    doc_dir = str(Path(app_dir) / "documentation")
    print(f"\nScanning documentation in: {doc_dir}")
    doc_files = scan_documentation(doc_dir)
    
    # TEMPORARY FILTER: Only scan sample_api_docs (user will revert later)
    doc_files = {k: v for k, v in doc_files.items() if 'sample_api' in k}
    
    if not code_files and not doc_files:
        print("\nNo code or documentation found. Creating placeholder analysis.")
        analysis_md = f"""# Code Analysis Report

## Project Overview
- Total Files: 0
- Languages Detected: None
- Documentation Files: 0
- Analysis Date: {datetime.now().strftime("%Y-%m-%d")}

## Project Structure
No code or documentation files found in the app directory.

## Recommended Test Scenarios
1. Add application code to the app directory, or
2. Add documentation to app/documentation directory
3. Run analyzer again after adding content
"""
        project_root = Path(__file__).parent.parent.parent
        output_path = project_root / "reports" / "analysis.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(analysis_md)
        
        print(f"Placeholder analysis saved to: {output_path}")
        return str(output_path)
    
    print(f"\nFound {len(code_files)} code file(s) and {len(doc_files)} documentation file(s)")
    print("Analyzing with GPT-4o-mini...")
    
    client = OpenAIClient()
    analysis_md = client.analyze_code_and_docs(code_files, doc_files, detected_languages)
    
    if analysis_md.startswith("```markdown"):
        analysis_md = analysis_md[11:]
    if analysis_md.startswith("```"):
        analysis_md = analysis_md[3:]
    if analysis_md.endswith("```"):
        analysis_md = analysis_md[:-3]
    analysis_md = analysis_md.strip()
    
    project_root = Path(__file__).parent.parent.parent
    output_path = project_root / "reports" / "analysis.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write(analysis_md)
    
    print(f"\nAnalysis complete!")
    print(f"Report saved to: {output_path}")
    print(f"\nAnalysis Preview:")
    print("=" * 80)
    print(analysis_md[:500] + "..." if len(analysis_md) > 500 else analysis_md)
    print("=" * 80)
    
    return str(output_path)

if __name__ == "__main__":
    analyze_target()
