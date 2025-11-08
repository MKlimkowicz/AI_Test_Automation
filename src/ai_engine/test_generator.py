import os
import sys
import re
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.openai_client import OpenAIClient

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
    
    return scenarios

def generate_tests(analysis_md_path: str = None, output_dir: str = "tests/generated") -> List[str]:
    project_root = Path(__file__).parent.parent.parent
    
    if analysis_md_path is None:
        analysis_md_path = str(project_root / "reports" / "analysis.md")
    
    analysis_path = Path(analysis_md_path)
    
    if not analysis_path.exists():
        print(f"Error: Analysis file not found at {analysis_path}")
        print("Please run analyzer.py first to generate the analysis report.")
        return []
    
    with open(analysis_path, "r") as f:
        analysis_markdown = f.read()
    
    print(f"Reading analysis from: {analysis_path}")
    print(f"Analysis size: {len(analysis_markdown)} characters\n")
    
    scenarios = extract_test_scenarios(analysis_markdown)
    print(f"Extracted {len(scenarios)} test scenario(s):\n")
    for idx, scenario in enumerate(scenarios, 1):
        print(f"  {idx}. {scenario}")
    
    client = OpenAIClient()
    
    output_path = project_root / output_dir
    output_path.mkdir(parents=True, exist_ok=True)
    
    generated_files = []
    
    for idx, scenario in enumerate(scenarios):
        print(f"\nGenerating tests for scenario {idx + 1}/{len(scenarios)}: {scenario}")
        
        test_code = client.generate_tests(analysis_markdown, scenario)
        
        if test_code.startswith("```python"):
            test_code = test_code[9:]
        if test_code.startswith("```"):
            test_code = test_code[3:]
        if test_code.endswith("```"):
            test_code = test_code[:-3]
        test_code = test_code.strip()
        
        test_filename = f"test_scenario_{idx + 1}.py"
        test_filepath = output_path / test_filename
        
        with open(test_filepath, "w") as f:
            f.write(test_code)
        
        generated_files.append(str(test_filepath))
        print(f"Generated: {test_filepath}")
    
    return generated_files

if __name__ == "__main__":
    print("Generating tests from analysis...\n")
    files = generate_tests()
    
    if files:
        print(f"\n{'=' * 80}")
        print(f"Successfully generated {len(files)} test file(s):")
        for file in files:
            print(f"  - {file}")
        print(f"{'=' * 80}")
    else:
        print("\nNo tests generated. Please check the analysis file.")
