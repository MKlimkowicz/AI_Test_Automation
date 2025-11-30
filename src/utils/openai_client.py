import json
import logging
from typing import Optional, Dict, List, Tuple

from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = config.OPENAI_MODEL
        logger.debug(f"Initialized OpenAI client with model: {self.model}")
    
    def _create_retry_decorator(self):
        return retry(
            stop=stop_after_attempt(config.OPENAI_RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1,
                min=config.OPENAI_RETRY_MIN_WAIT,
                max=config.OPENAI_RETRY_MAX_WAIT
            ),
            retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
    
    def _call_api(self, messages: List[Dict], temperature: float, max_tokens: int) -> str:
        @self._create_retry_decorator()
        def _make_request():
            logger.debug(f"Making API call with temp={temperature}, max_tokens={max_tokens}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        
        return _make_request()

    def analyze_code_and_docs(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str],
        languages: List[str]
    ) -> str:
        logger.info("Analyzing code and documentation...")
        
        code_section = ""
        if code_files:
            code_parts = []
            config_parts = []
            for filepath, (content, language) in code_files.items():
                if language == 'config':
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

        messages = [
            {"role": "system", "content": "You are an expert code analyst and QA architect. Analyze codebases and documentation thoroughly to generate comprehensive test strategies. You can create test plans from documentation alone or combined with code."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_ANALYSIS,
            config.OPENAI_MAX_TOKENS_ANALYSIS
        )
        
        logger.info("Code analysis complete")
        return result

    def analyze_code(self, code_files: Dict[str, str]) -> str:
        converted_files = {path: (content, 'python') for path, content in code_files.items()}
        return self.analyze_code_and_docs(converted_files, {}, ['python'])

    def generate_tests(self, analysis_markdown: str, scenario: str, conftest_content: Optional[str] = None) -> str:
        logger.info(f"Generating tests for scenario: {scenario[:50]}...")
        
        conftest_section = ""
        if conftest_content:
            conftest_section = f"""
AVAILABLE FIXTURES FROM conftest.py - USE THESE:
```python
{conftest_content}
```

CRITICAL: You MUST use the fixtures defined above. Do NOT redefine fixtures that already exist in conftest.py.
Simply use them as function parameters in your test functions.

"""
        
        prompt = f"""Generate pytest tests for the following test scenario based on code analysis.

NOTE: The application under test can be written in ANY language (Python, JavaScript, Java, Go, Rust, etc.), but tests are ALWAYS written in Python using pytest.

Code Analysis:
{analysis_markdown}

Test Scenario to Implement:
{scenario}
{conftest_section}
UNIVERSAL TEST BEST PRACTICES - MUST FOLLOW:

1. TEST ISOLATION - Use unique identifiers for ALL test data:
   ✅ CORRECT: username = f'user_{{uuid.uuid4().hex[:8]}}'
   ❌ WRONG: username = 'testuser'

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
   - ❌ WRONG: from sample_api import create_user

Requirements:
- Generate complete, executable pytest tests
- If conftest.py fixtures are provided above, USE THEM - do NOT redefine them
- Only import fixtures by using them as test function parameters
- ALWAYS use uuid.uuid4().hex[:8] for unique test data identifiers (or use unique_id fixture if available)
- Choose appropriate testing approach based on application type:
  * REST API → use requests/httpx for HTTP calls (or use api_client fixture if available)
  * CLI → use subprocess for command execution (or use cli_runner fixture if available)
  * Python app → import and test directly if applicable
  * gRPC → use grpc client
  * WebSocket → use websocket client
- Use type hints for clarity
- Follow pytest conventions
- Make tests independent and reusable
- Include necessary imports (uuid, pytest, requests/subprocess/etc.)
- NO comments of any kind
- NO docstrings of any kind
- Code must be self-explanatory through clear naming
- Return ONLY the Python code, no explanations

UNIQUE SCENARIOS - CRITICAL:
- Generate tests ONLY for the specific scenario provided above
- Do NOT generate tests for other scenarios not mentioned
- Each test function must test ONE distinct behavior
- Do NOT duplicate test logic - if testing "create user", create ONE test function for it
- Use descriptive function names that clearly indicate what is being tested

Generate the complete test file:"""

        messages = [
            {"role": "system", "content": "You are an expert test automation engineer. Generate tests ONLY for the specific scenario provided. Do NOT duplicate tests or add extra scenarios. Each test must be unique. NO comments, NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_GENERATION,
            config.OPENAI_MAX_TOKENS_GENERATION
        )
        
        logger.debug("Test generation complete")
        return result

    def classify_failure(self, test_code: str, failure_info: dict) -> dict:
        logger.debug(f"Classifying failure for: {failure_info.get('nodeid', 'unknown')}")
        
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

        messages = [
            {"role": "system", "content": "You are an expert QA engineer specializing in test failure analysis. Classify failures accurately."},
            {"role": "user", "content": prompt}
        ]
        
        content = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_CLASSIFICATION,
            config.OPENAI_MAX_TOKENS_CLASSIFICATION
        )
        
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        return json.loads(content.strip())

    def heal_test(self, test_code: str, failure_info: dict) -> str:
        logger.info(f"Healing test: {failure_info.get('nodeid', 'unknown')}")
        
        prompt = f"""Fix this failing test:

Current Test Code:
{test_code}

Failure Information:
- Test Name: {failure_info.get('nodeid', 'N/A')}
- Error: {failure_info.get('call', {}).get('longrepr', 'N/A')}

Requirements:
- Fix the test error while maintaining test intent
- NO comments of any kind
- NO docstrings of any kind
- Use type hints
- Return ONLY the fixed Python code, no explanations

Generate the fixed test code:"""

        messages = [
            {"role": "system", "content": "You are an expert test automation engineer. Fix failing tests while maintaining their purpose. Generate clean code with NO comments and NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_HEALING,
            config.OPENAI_MAX_TOKENS_HEALING
        )
        
        logger.debug("Test healing complete")
        return result

    def fix_collection_error(self, test_file: str, test_code: str, error_message: str) -> str:
        logger.info(f"Fixing collection error in: {test_file}")
        
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
- NO comments of any kind
- NO docstrings of any kind
- Use type hints where appropriate
- Return ONLY the fixed Python code, no explanations or markdown formatting

Generate the fixed test code:"""

        messages = [
            {"role": "system", "content": "You are an expert test automation engineer. Fix pytest collection errors by analyzing import issues and using proper testing patterns. For Flask apps, use test client instead of importing route functions. Generate code with NO comments and NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        content = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_CLASSIFICATION,
            config.OPENAI_MAX_TOKENS_HEALING
        )
        
        if content.startswith("```python"):
            content = content[9:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        logger.debug("Collection error fix complete")
        return content.strip()

    def analyze_bug(self, defect_info: dict) -> str:
        logger.info(f"Analyzing bug: {defect_info.get('test_name', 'unknown')}")
        
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

        messages = [
            {"role": "system", "content": "You are an expert software debugger and QA engineer. Analyze bugs thoroughly and provide actionable investigation guidance."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_BUG_ANALYSIS,
            config.OPENAI_MAX_TOKENS_BUG_ANALYSIS
        )
        
        logger.debug("Bug analysis complete")
        return result

    def generate_fixtures(self, analysis_markdown: str, best_practices: str) -> str:
        logger.info("Generating conftest.py fixtures...")
        
        prompt = f"""Generate pytest fixtures for conftest.py based ONLY on what is detected in the code analysis.

Code Analysis:
{analysis_markdown}

Best Practices Reference (for patterns only):
{best_practices}

CRITICAL REQUIREMENTS:

1. IMPORTS - MUST include ALL necessary imports at the very top:
   - import pytest
   - import uuid (if generating unique data)
   - import requests (if making HTTP calls)
   - Any other imports needed by your fixtures
   - VERIFY every module you use is imported

2. NO HARDCODED TEST DATA - CRITICAL:
   - NEVER use hardcoded usernames like "testuser" or "admin"
   - NEVER use hardcoded emails like "test@example.com"
   - ALWAYS generate unique data using uuid.uuid4().hex[:8]
   - Example: f"user_{{uuid.uuid4().hex[:8]}}" for usernames
   - Example: f"user_{{uuid.uuid4().hex[:8]}}@example.com" for emails

3. ONLY create fixtures relevant to the analyzed application:
   - If API endpoints detected → create api_client, api_base_url fixtures
   - If authentication detected → create authenticated_client fixture
   - If database models detected → create db fixtures
   - If the app uses specific port/URL → use that in fixtures
   - If user creation exists → create user data factory fixtures
   - If no auth exists → do NOT create auth fixtures
   - If no database → do NOT create db fixtures

4. Include cleanup/teardown using yield where appropriate

5. CODE STYLE - CRITICAL:
   - NO comments of any kind
   - NO docstrings of any kind
   - NO inline comments
   - Code must be self-explanatory through clear naming

6. Return ONLY the Python code, no explanations or markdown formatting

Generate fixtures with ALL imports and NO hardcoded data:"""

        messages = [
            {"role": "system", "content": "You are an expert test automation engineer. CRITICAL: 1) Include ALL imports at the top (pytest, uuid, requests, etc). 2) NEVER use hardcoded data - always use uuid for unique values. 3) NO comments, NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_FIXTURES,
            config.OPENAI_MAX_TOKENS_FIXTURES
        )
        
        logger.info("Fixture generation complete")
        return result

    def validate_conftest(self, conftest_code: str, best_practices: str) -> dict:
        logger.info("Validating conftest.py with AI reviewer...")

        prompt = f"""You are auditing a pytest conftest.py file. Review the fixtures for correctness and best practices.

conftest.py:
```python
{conftest_code}
```

Best Practices Reference:
{best_practices}

Review Checklist:
- Duplicate fixtures or conflicting definitions
- Missing imports required by fixtures
- Hardcoded usernames/emails/passwords instead of unique uuid usage
- Fixtures lacking cleanup/teardown when resources are created
- Fixtures not using yields when cleanup required
- Any other risky or incorrect patterns

Respond in JSON with this structure:
{{
  "status": "pass" | "fail",
  "issues": [
    {{
      "type": "missing-import" | "duplicate-fixture" | "hardcoded-data" | "cleanup" | "other",
      "detail": "Description of the issue",
      "suggestion": "Actionable advice to fix"
    }}
  ]
}}

If everything looks good, use status "pass" and return an empty issues list."""

        messages = [
            {"role": "system", "content": "You are an expert pytest code reviewer. Produce objective, actionable feedback."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self._call_api(
                messages,
                config.OPENAI_TEMPERATURE_CLASSIFICATION,
                config.OPENAI_MAX_TOKENS_CLASSIFICATION
            )
            return json.loads(response)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI conftest validation failed: %s", exc)
            return {"status": "error", "issues": [{"type": "exception", "detail": str(exc)}]}

    def validate_tests(self, test_files: Dict[str, str], conftest_code: str) -> dict:
        logger.info("Validating generated tests with AI reviewer...")

        serialized_tests = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )

        prompt = f"""You are auditing generated pytest test files.

Fixtures available (from conftest.py):
```python
{conftest_code}
```

Generated tests:
{serialized_tests}

Review Checklist:
- Duplicate or overlapping test scenarios across files
- Tests redefining fixtures instead of using ones from conftest
- Missing imports or unused imports
- Lack of unique data (should rely on uuid or fixtures)
- Multiple assertions for unrelated concerns in a single test
- Clear test names indicating scenario covered

Respond in JSON with this structure:
{{
  "status": "pass" | "fail",
  "issues": [
    {{
      "type": "duplicate-test" | "fixture-misuse" | "hardcoded-data" | "naming" | "other",
      "detail": "Description of the issue with file reference",
      "suggestion": "Actionable advice to fix"
    }}
  ]
}}

If everything looks good, use status "pass" and an empty issue list."""

        messages = [
            {"role": "system", "content": "You are an expert pytest reviewer. Identify duplicate scenarios and best-practice violations."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self._call_api(
                messages,
                config.OPENAI_TEMPERATURE_CLASSIFICATION,
                config.OPENAI_MAX_TOKENS_SUMMARY
            )
            return json.loads(response)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI test validation failed: %s", exc)
            return {"status": "error", "issues": [{"type": "exception", "detail": str(exc)}]}

    def heal_conftest(self, conftest_code: str, issues: List[Dict], best_practices: str) -> str:
        logger.info("Healing conftest.py via AI...")

        issues_text = json.dumps(issues, indent=2)
        prompt = f"""You must FIX the pytest conftest.py file described below.

Current conftest.py:
```python
{conftest_code}
```

Issues detected:
{issues_text}

Best practices reference:
{best_practices}

Requirements:
- Produce ONE complete conftest.py file that resolves all issues above
- Include ALL required imports at the top
- Use uuid-based unique data (no hardcoded usernames/emails/passwords)
- Keep fixtures relevant to the detected application only
- Use yield for cleanup when necessary
- NO comments, NO docstrings
- Return ONLY the Python code, no explanations or markdown fences
"""

        messages = [
            {"role": "system", "content": "You are an expert pytest engineer. Fix the provided conftest.py file to resolve all issues."},
            {"role": "user", "content": prompt}
        ]

        try:
            result = self._call_api(
                messages,
                config.OPENAI_TEMPERATURE_HEALING,
                config.OPENAI_MAX_TOKENS_HEALING
            )
            return result.strip()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI conftest healing failed: %s", exc)
            return ""

    def heal_tests(self, test_files: Dict[str, str], conftest_code: str, issues: List[Dict]) -> Dict[str, str]:
        logger.info("Healing generated tests via AI...")

        serialized_tests = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )
        issues_text = json.dumps(issues, indent=2)

        prompt = f"""You must FIX the generated pytest test files below.

Fixtures available from conftest.py:
```python
{conftest_code}
```

Current tests:
{serialized_tests}

Issues detected:
{issues_text}

Requirements:
- Resolve duplicate scenarios and enforce unique test coverage
- Ensure tests use fixtures from conftest.py instead of redefining setup
- Replace any hardcoded test data with uuid-based values or fixture outputs
- Keep imports minimal and valid
- Preserve descriptive test names
- NO comments, NO docstrings
- Return JSON mapping absolute file paths to their FIXED code. Example:
{{"/abs/path/to/test_file.py": "<fixed python code>"}}

Only return JSON. Do not include markdown fences or additional text.
"""

        messages = [
            {"role": "system", "content": "You are an expert pytest engineer. Fix the provided tests to resolve all validation issues."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self._call_api(
                messages,
                config.OPENAI_TEMPERATURE_HEALING,
                config.OPENAI_MAX_TOKENS_HEALING
            )
            healed = json.loads(response)
            if not isinstance(healed, dict):
                raise ValueError("Expected JSON object mapping file paths to code")
            return {path: code.strip() for path, code in healed.items() if isinstance(code, str)}
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI test healing failed: %s", exc)
            return {}

    def summarize_report(self, report_data: dict, healing_analysis: dict) -> str:
        logger.info("Generating test execution summary...")
        
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

        messages = [
            {"role": "system", "content": "You are an expert QA reporting specialist. Create clear, actionable test reports with emphasis on iterative healing results and bug identification."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            config.OPENAI_TEMPERATURE_SUMMARY,
            config.OPENAI_MAX_TOKENS_SUMMARY
        )
        
        logger.info("Summary generation complete")
        return result
