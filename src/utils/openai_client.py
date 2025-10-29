import os
from typing import Optional, Dict
from openai import OpenAI

class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"

    def analyze_code(self, code_files: Dict[str, str]) -> str:
        files_content = "\n\n".join([
            f"### File: {filepath}\n```python\n{content}\n```"
            for filepath, content in code_files.items()
        ])
        
        prompt = f"""Analyze the following Python codebase and generate a comprehensive markdown report.

{files_content}

Generate a detailed analysis in markdown format with these sections:

# Code Analysis Report

## Project Overview
- Total Files: [count]
- Framework Detected: [Flask/Django/FastAPI/None/Other]
- Analysis Date: [current date]

## Project Structure
List each file with brief description of its purpose

## Components Discovered

### API Endpoints
List all endpoints found (if any) with HTTP method, path, and description

### Database Models
List all database models/schemas found (if any)

### Key Functions
List important functions with their purpose

### Key Classes
List important classes with their purpose

## Recommended Test Scenarios
Provide numbered list of specific test scenarios based on the code

Return ONLY the markdown, no additional explanations."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert code analyst and QA architect. Analyze codebases thoroughly and generate comprehensive test strategies."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=3000
        )
        
        return response.choices[0].message.content.strip()

    def generate_tests(self, analysis_markdown: str, scenario: str) -> str:
        prompt = f"""Generate pytest tests for the following test scenario based on code analysis.

Code Analysis:
{analysis_markdown}

Test Scenario to Implement:
{scenario}

Requirements:
- Generate complete, executable pytest tests
- Use minimal or no comments
- Use minimal docstrings (only for main test functions if necessary)
- Use type hints for clarity
- Follow pytest conventions
- Make tests independent and reusable
- Include necessary imports
- Return ONLY the Python code, no explanations

Generate the complete test file:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert test automation engineer. Generate clean, production-ready pytest tests with minimal comments and docstrings."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()

    def classify_failure(self, test_code: str, failure_info: dict) -> dict:
        prompt = f"""Analyze this test failure and classify it:

Test Code:
{test_code}

Failure Information:
- Test Name: {failure_info.get('nodeid', 'N/A')}
- Error Message: {failure_info.get('call', {}).get('longrepr', 'N/A')}
- Exception Type: {failure_info.get('call', {}).get('crash', {}).get('message', 'N/A')}

Determine if this is:
1. TEST_ERROR - Issue in the test code itself (wrong assertion, bad selector, timing, flaky test, incorrect setup, etc.)
2. ACTUAL_DEFECT - Legitimate bug in the application/database being tested

Respond in JSON format:
{{
    "classification": "TEST_ERROR" or "ACTUAL_DEFECT",
    "reason": "Brief explanation",
    "confidence": "high/medium/low"
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert QA engineer specializing in test failure analysis. Classify failures accurately."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        import json
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content.strip())

    def heal_test(self, test_code: str, failure_info: dict) -> str:
        prompt = f"""Fix this failing test:

Current Test Code:
{test_code}

Failure Information:
- Test Name: {failure_info.get('nodeid', 'N/A')}
- Error: {failure_info.get('call', {}).get('longrepr', 'N/A')}

Requirements:
- Fix the test error while maintaining test intent
- Use minimal or no comments
- Use minimal docstrings
- Use type hints
- Return ONLY the fixed Python code, no explanations

Generate the fixed test code:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert test automation engineer. Fix failing tests while maintaining their purpose. Generate clean code with minimal comments."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=2000
        )
        
        return response.choices[0].message.content.strip()

    def summarize_report(self, report_data: dict, healing_analysis: dict) -> str:
        prompt = f"""Generate a comprehensive test execution summary:

Test Results:
{report_data}

Self-Healing Analysis:
{healing_analysis}

Create a detailed markdown report with:
1. Executive Summary (pass rate, total tests, duration)
2. Test Results Overview
3. Failure Analysis:
   - Test Errors (Self-Healed) - with before/after comparison
   - Actual Defects (Requiring Investigation) - with details
4. Self-Healing Actions Taken
5. Recommendations

Format as markdown with clear sections and bullet points.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert QA reporting specialist. Create clear, actionable test reports."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=3000
        )
        
        return response.choices[0].message.content.strip()

