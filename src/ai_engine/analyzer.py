import os
import sys
from pathlib import Path
from typing import Dict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient

def scan_python_files(app_dir: str) -> Dict[str, str]:
    app_path = Path(app_dir)
    
    if not app_path.exists():
        print(f"Warning: Directory {app_dir} does not exist")
        return {}
    
    python_files = {}
    ignored_dirs = {'__pycache__', 'venv', 'env', '.venv', 'node_modules', '.git'}
    max_file_size = 50 * 1024
    
    for root, dirs, files in os.walk(app_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                relative_path = file_path.relative_to(app_path)
                
                try:
                    file_size = file_path.stat().st_size
                    if file_size > max_file_size:
                        print(f"Skipping {relative_path} (too large: {file_size} bytes)")
                        continue
                    
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        python_files[str(relative_path)] = content
                        print(f"Read: {relative_path} ({file_size} bytes)")
                
                except Exception as e:
                    print(f"Warning: Could not read {relative_path}: {e}")
    
    return python_files

def analyze_target(app_dir: str = None) -> str:
    if app_dir is None:
        project_root = Path(__file__).parent.parent.parent
        app_dir = str(project_root / "app")
    
    print(f"Scanning Python files in: {app_dir}")
    code_files = scan_python_files(app_dir)
    
    if not code_files:
        print("No Python files found. Creating placeholder analysis.")
        analysis_md = f"""# Code Analysis Report

## Project Overview
- Total Files: 0
- Framework Detected: None
- Analysis Date: {datetime.now().strftime("%Y-%m-%d")}

## Project Structure
No Python files found in the app directory.

## Recommended Test Scenarios
1. Create sample application code first
2. Run analyzer again after adding code
"""
        project_root = Path(__file__).parent.parent.parent
        output_path = project_root / "reports" / "analysis.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(analysis_md)
        
        print(f"Placeholder analysis saved to: {output_path}")
        return str(output_path)
    
    print(f"\nFound {len(code_files)} Python file(s)")
    print("Analyzing code with GPT-4o-mini...")
    
    client = OpenAIClient()
    analysis_md = client.analyze_code(code_files)
    
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
