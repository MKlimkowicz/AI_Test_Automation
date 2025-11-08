import os
from typing import Optional, Dict, List, Tuple
from openai import OpenAI

class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"

    def analyze_code_and_docs(self, code_files: Dict[str, Tuple[str, str]], doc_files: Dict[str, str], languages: List[str]) -> str:
        code_section = ""
        if code_files:
            code_parts = []
            config_parts = []
            for filepath, (content, language) in code_files.items():
                if language == 'config':
                    # Determine fence type based on file extension
                    if filepath.endswith('.json'):
                        fence = 'json'
                    elif filepath.endswith('.toml'):
                        fence = 'toml'
                    elif filepath.endswith('.xml'):
                        fence = 'xml'
                    elif filepath.endswith('.yaml') or filepath.endswith('.yml'):
                        fence = 'yaml'
                    else:
                        fence = 'text'
                    config_parts.append(f"### Configuration: {filepath}\n```{fence}\n{content}\n```")
                else:
                    code_parts.append(f"### File: {filepath}\n```{language}\n{content}\n```")
            
            if code_parts:
                code_section = "## Application Code\n\n" + "\n\n".join(code_parts)
            if config_parts:
                config_section = "## Configuration Files\n\n" + "\n\n".join(config_parts)
                code_section = code_section + "\n\n" + config_section if code_section else config_section
        
        doc_section = ""
        if doc_files:
            doc_parts = []
            for filepath, content in doc_files.items():
                doc_parts.append(f"### Documentation: {filepath}\n```\n{content}\n```")
            doc_section = "## Documentation\n\n" + "\n\n".join(doc_parts)
        
        languages_str = ", ".join(languages) if languages else "None detected"
        
        content_sections = []
        if code_section:
            content_sections.append(code_section)
        if doc_section:
            content_sections.append(doc_section)
        
        full_content = "\n\n".join(content_sections)
        
        prompt = f"""Analyze the following application and generate a comprehensive markdown report for test planning.

Languages Detected: {languages_str}

{full_content}

Generate a detailed analysis in markdown format with these sections:

# Code Analysis Report

## Project Overview
- Total Code Files: [count]
- Total Configuration Files: [count]
- Total Documentation Files: [count]
- Languages Detected: [list languages]
- Framework Detected: [Flask/Django/FastAPI/Express/Spring/None/Other]
- Key Dependencies: [list main dependencies from config files if available]
- Analysis Date: [current date]

## Project Structure
List each file (code, configuration, and documentation) with brief description of its purpose

## Components Discovered

### API Endpoints
List all endpoints found (if any) with HTTP method, path, and description

### Database Models
List all database models/schemas found (if any)

### Key Functions
List important functions with their purpose

### Key Classes
List important classes with their purpose

## Documentation Summary
Summarize key points from documentation files (if any)

## Recommended Test Scenarios

Analyze the application and suggest test scenarios in the following categories. Only include categories where testing is relevant and necessary - not all categories are required for every application.

### Functional Tests
List specific functional test scenarios that verify business logic, API endpoints, data validation, CRUD operations, user workflows, and feature correctness. Include scenarios for:
- Happy path testing
- Edge cases
- Error handling
- Input validation
- Business rule enforcement

### Performance Tests
Only include if the application has performance-critical features, scalability requirements, or handles significant load. Suggest scenarios for:
- Response time testing
- Load testing
- Stress testing
- Concurrency testing
- Resource usage monitoring
- Database query performance

### Security Tests
Only include if the application has authentication, authorization, data handling, or external integrations. Suggest scenarios for:
- Authentication and authorization
- Input sanitization and injection prevention
- Data encryption and privacy
- Rate limiting
- Token/session management
- Access control validation

Note: If a category is not applicable to this application, omit it entirely. Focus on what actually needs testing based on the code, dependencies, and documentation provided.

Return ONLY the markdown, no additional explanations."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert code analyst and QA architect. Analyze codebases and documentation thoroughly to generate comprehensive test strategies. You can create test plans from documentation alone or combined with code."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=3000
        )
        
        return response.choices[0].message.content.strip()

    def analyze_code(self, code_files: Dict[str, str]) -> str:
        converted_files = {path: (content, 'python') for path, content in code_files.items()}
        return self.analyze_code_and_docs(converted_files, {}, ['python'])

    def generate_tests(self, analysis_markdown: str, scenario: str) -> str:
        prompt = f"""Generate pytest tests for the following test scenario based on code analysis.

NOTE: The application under test can be written in ANY language (Python, JavaScript, Java, Go, Rust, etc.), but tests are ALWAYS written in Python using pytest.

Code Analysis:
{analysis_markdown}

Test Scenario to Implement:
{scenario}

UNIVERSAL TEST BEST PRACTICES - MUST FOLLOW:

1. TEST ISOLATION - Use unique identifiers for ALL test data:
   ✅ CORRECT: username = f'user_{{uuid.uuid4().hex[:8]}}'
   ❌ WRONG: username = 'testuser'  # Will conflict with other tests!

2. FIXTURES - Use fixtures for setup/teardown:
   ```python
   @pytest.fixture
   def unique_id():
       return uuid.uuid4().hex[:8]
   
   @pytest.fixture
   def test_user_data(unique_id):
       return {{
           'username': f'user_{{unique_id}}',
           'email': f'user_{{unique_id}}@example.com',
           'password': 'securepass123'
       }}
   ```

3. CLEAR ASSERTIONS - Be specific with helpful messages:
   ✅ CORRECT: assert response.status_code == 201, f"Expected 201, got {{response.status_code}}"
   ✅ CORRECT: assert 'id' in data, "Response should contain user ID"
   ❌ WRONG: assert response.status_code == 201

4. APPLICATION TYPE PATTERNS:

   REST API (any language):
   ```python
   import requests
   
   @pytest.fixture
   def api_client():
       session = requests.Session()
       session.headers.update({{'Content-Type': 'application/json'}})
       yield session
       session.close()
   
   def test_api_endpoint(api_client):
       response = api_client.get('http://localhost:8080/api/users')
       assert response.status_code == 200
   ```

   CLI Application (any language):
   ```python
   import subprocess
   
   def test_cli_command():
       result = subprocess.run(['./myapp', '--help'], capture_output=True, text=True)
       assert result.returncode == 0
       assert 'Usage:' in result.stdout
   ```

   Python Flask/FastAPI:
   ```python
   from myapp import create_app
   
   @pytest.fixture
   def client():
       app = create_app()
       app.config['TESTING'] = True
       with app.test_client() as client:
           yield client
   ```

5. IMPORTS - Only import what actually exists:
   - For Python apps: Import only modules/functions that are exportable
   - For non-Python apps: Use HTTP clients (requests), subprocess, or appropriate client libraries
   - ✅ CORRECT: from sample_api import create_app
   - ❌ WRONG: from sample_api import create_user  # Route functions are not importable!

Requirements:
- Generate complete, executable pytest tests
- ALWAYS use uuid.uuid4().hex[:8] for unique test data identifiers
- Use fixtures for test data generation and cleanup
- Choose appropriate testing approach based on application type:
  * REST API → use requests/httpx for HTTP calls
  * CLI → use subprocess for command execution
  * Python app → import and test directly if applicable
  * gRPC → use grpc client
  * WebSocket → use websocket client
- Use type hints for clarity
- Follow pytest conventions
- Make tests independent and reusable
- Include necessary imports (uuid, pytest, requests/subprocess/etc.)
- Use minimal comments (code should be self-explanatory)
- Add docstrings only for test functions to explain what's being tested
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

    def fix_collection_error(self, test_file: str, test_code: str, error_message: str) -> str:
        """
        Fix pytest collection errors (import failures, syntax errors, etc.)
        
        Args:
            test_file: Path to the test file
            test_code: Current test code
            error_message: Collection error message from pytest
        
        Returns:
            Fixed test code
        """
        prompt = f"""Fix this pytest collection error:

Test File: {test_file}

Current Test Code:
```python
{test_code}
```

Collection Error:
{error_message}

Common Issues to Fix:
1. ImportError: Trying to import functions that don't exist or aren't exportable
   - Solution: Use Flask test client instead of importing route functions
   - Example: Replace `from sample_api import create_user` with using `client.post('/api/users', ...)`

2. Syntax errors or invalid Python
   - Solution: Fix syntax issues

3. Missing fixtures or dependencies
   - Solution: Add required fixtures or imports

Requirements:
- Fix the collection error while maintaining test intent
- For Flask apps with app factory pattern, use test client instead of importing route functions
- Use minimal or no comments
- Use minimal docstrings
- Use type hints where appropriate
- Return ONLY the fixed Python code, no explanations or markdown formatting

Generate the fixed test code:"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert test automation engineer. Fix pytest collection errors by analyzing import issues and using proper testing patterns. For Flask apps, use test client instead of importing route functions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code fences if present
        if content.startswith("```python"):
            content = content[9:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        return content.strip()

    def analyze_bug(self, defect_info: dict) -> str:
        """
        Generate detailed bug analysis for an ACTUAL_DEFECT.
        
        Args:
            defect_info: Dictionary containing defect information
        
        Returns:
            Detailed bug analysis as markdown
        """
        prompt = f"""Analyze this potential application bug and provide detailed investigation guidance:

Bug Information:
- Test Name: {defect_info.get('test_name', 'Unknown')}
- Classification: {defect_info.get('classification', 'ACTUAL_DEFECT')}
- Confidence: {defect_info.get('confidence', 'unknown')}
- Error Message: {defect_info.get('error', 'N/A')}
- AI Analysis: {defect_info.get('analysis', 'N/A')}

Provide a detailed bug report with:
1. **Root Cause Analysis**: What is likely causing this failure?
2. **Affected Components**: Which parts of the application are involved?
3. **Severity Assessment**: Critical/High/Medium/Low and why
4. **Reproduction Steps**: How to reproduce this bug
5. **Suggested Investigation Areas**: Where developers should look
6. **Potential Fixes**: Possible solutions or approaches
7. **Related Code**: Which files/functions to examine

Format as clear, actionable markdown.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert software debugger and QA engineer. Analyze bugs thoroughly and provide actionable investigation guidance."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
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
3. Iterative Healing Process:
   - Successfully Healed Tests (with number of attempts)
   - Tests that exceeded max healing attempts
4. Failure Analysis:
   - Test Errors (Self-Healed) - with healing iterations
   - Actual Defects (Requiring Investigation) - with detailed analysis
5. Self-Healing Actions Taken
6. Bug Report Summary (if actual defects found)
7. Commit Status (allowed or blocked)
8. Recommendations

Format as markdown with clear sections and bullet points.
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert QA reporting specialist. Create clear, actionable test reports with emphasis on iterative healing results and bug identification."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=3000
        )
        
        return response.choices[0].message.content.strip()

