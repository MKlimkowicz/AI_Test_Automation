import json
import logging
from typing import Optional, Dict, List, Tuple

from anthropic import Anthropic, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from utils.config import config
from utils.logger import get_logger
from utils.helpers import strip_markdown_fences

logger = get_logger(__name__)


class AIClient:
    """Claude/Anthropic AI client (name kept for compatibility)"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.CLAUDE_API_KEY
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY not found in environment variables")
        self.client = Anthropic(api_key=self.api_key)
        self.model = config.CLAUDE_MODEL
        logger.debug(f"Initialized Claude client with model: {self.model}")
    
    def _create_retry_decorator(self):
        return retry(
            stop=stop_after_attempt(config.RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1,
                min=config.RETRY_MIN_WAIT,
                max=config.RETRY_MAX_WAIT
            ),
            retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError)),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
    
    def _call_api(self, messages: List[Dict], temperature: float, max_tokens: int) -> str:
        @self._create_retry_decorator()
        def _make_request():
            logger.debug(f"Making Claude API call with max_tokens={max_tokens}")
            
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_msg,
                messages=user_messages
            )
            return response.content[0].text.strip()
        
        return _make_request()

    def _extract_json(self, content: str) -> str:
        """Extract JSON from AI response, handling markdown fences and extra content."""
        content = content.strip()
        
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        
        if "```" in content:
            content = content.split("```")[0]
        
        import re
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        
        return content.strip()

    def _get_connection_info(self, app_metadata: Dict) -> tuple:
        app_type = app_metadata.get("app_type", "rest_api")
        
        http_conn = app_metadata.get("http_connection", {})
        base_url = http_conn.get("base_url") or app_metadata.get("base_url", "http://localhost")
        port = http_conn.get("port") or app_metadata.get("port", 8080)
        
        return app_type, base_url, port

    def _format_code_sections(
        self, 
        code_files: Dict[str, Tuple[str, str]], 
        doc_files: Dict[str, str]
    ) -> str:
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
        
        content_sections = []
        if code_section:
            content_sections.append(code_section)
        if doc_section:
            content_sections.append(doc_section)
        
        return "\n\n".join(content_sections)

    def analyze_code_and_docs(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str],
        languages: List[str]
    ) -> str:
        logger.info("Analyzing code and documentation...")
        
        full_content = self._format_code_sections(code_files, doc_files)
        languages_str = ", ".join(languages) if languages else "None detected"
        
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
            0.4,
            config.MAX_TOKENS_ANALYSIS
        )
        
        logger.info("Code analysis complete")
        return result

    def generate_app_metadata(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str],
        languages: List[str]
    ) -> Dict:
        logger.info("Generating structured application metadata...")

        full_content = self._format_code_sections(code_files, doc_files)
        languages_str = ", ".join(languages) if languages else "unknown"

        prompt = f"""Analyze the code/documentation below and extract metadata as JSON.

Languages: {languages_str}

{full_content}

Return ONLY a JSON object with these fields:
{{
  "app_type": "rest_api" | "cli" | "grpc" | "graphql" | "websocket" | "library" | "message_queue" | "serverless",
  "framework": "Flask" | "FastAPI" | "Express" | "Spring" | "none" | etc.,
  "languages": ["python"] | ["rust"] | ["javascript"] | etc.,
  "base_url": "http://localhost" (for web apps) or null,
  "port": 5050 (extract from code/docs) or null,
  "auth_required": true | false,
  "test_credentials": {{"username": "...", "password": "..."}} (if found in docs) or null,
  "health_endpoint": "/health" (if exists) or null
}}

IMPORTANT:
- Extract the ACTUAL port from the code (look for app.run(port=...) or similar)
- Extract test credentials if mentioned in documentation
- Return ONLY valid JSON, no explanations"""

        messages = [
            {"role": "system", "content": "You are a code analyst. Output ONLY valid JSON, no markdown fences, no explanations."},
            {"role": "user", "content": prompt}
        ]

        logger.debug("Calling AI for metadata generation...")
        raw_content = self._call_api(
            messages,
            0.3,
            config.MAX_TOKENS_ANALYSIS
        )
        
        logger.debug(f"Raw AI response for metadata: {raw_content[:500]}...")
        
        content = self._extract_json(raw_content)
        logger.debug(f"Extracted JSON: {content[:500]}...")

        try:
            metadata = json.loads(content)
            
            if not metadata.get("languages") and languages:
                metadata["languages"] = languages
            
            if metadata.get("base_url") and metadata.get("port"):
                metadata["http_connection"] = {
                    "base_url": metadata.get("base_url"),
                    "port": metadata.get("port"),
                    "protocol": "https" if "https" in metadata.get("base_url", "") else "http",
                    "health_endpoint": metadata.get("health_endpoint")
                }
            
            logger.info(f"Metadata generation complete: app_type={metadata.get('app_type')}, port={metadata.get('port')}")
            return metadata
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {e}")
            logger.error(f"Raw content was: {raw_content}")
            return {
                "app_type": "rest_api",
                "framework": "unknown",
                "languages": languages if languages else [],
                "base_url": "http://localhost",
                "port": 8080,
                "auth_required": False,
                "http_connection": {"base_url": "http://localhost", "port": 8080, "protocol": "http"}
            }

    def generate_category_tests(
        self,
        analysis_markdown: str,
        category: str,
        scenarios: List[str],
        app_metadata: Dict = None
    ) -> str:
        logger.info(f"Generating {category} tests ({len(scenarios)} scenarios)...")

        if app_metadata is None:
            app_metadata = {}
        
        app_type, base_url, port = self._get_connection_info(app_metadata)
        full_url = f"{base_url}:{port}"
        
        logger.info(f"Using app_type={app_type}, base_url={full_url}")

        scenarios_list = "\n".join([f"- {s}" for s in scenarios])
        
        test_template = self._get_test_template_for_app_type(app_type, full_url)

        prompt = f"""Generate a pytest test file with EXACTLY {len(scenarios)} SEPARATE test functions.

APPLICATION TYPE: {app_type.upper()}
BASE URL: {full_url}

ANALYSIS/DOCUMENTATION:
{analysis_markdown}

{test_template}

SCENARIOS TO IMPLEMENT (one test function per scenario):
{scenarios_list}

CRITICAL RULES:
1. Create EXACTLY {len(scenarios)} SEPARATE test functions - one per scenario above
2. DO NOT combine scenarios into a single test
3. Each test function name: test_<descriptive_name>
4. Each test is independent - creates its own data
5. Use the fixtures defined in the template above
6. NO comments, NO docstrings
7. Keep each test focused on ONE scenario
8. Use the EXACT BASE_URL provided: {full_url}
9. Use EXACT endpoint paths from the documentation

Generate the file with fixtures then {len(scenarios)} individual test functions:"""

        messages = [
            {"role": "system", "content": f"Generate EXACTLY {len(scenarios)} SEPARATE test functions for a {app_type} application. DO NOT combine them. Each scenario = one test function. NO comments."},
            {"role": "user", "content": prompt}
        ]

        result = self._call_api(
            messages,
            0.7,
            config.MAX_TOKENS_BATCH_HEALING
        )

        logger.debug(f"Category test generation complete for {category}")
        return result

    def _get_test_template_for_app_type(self, app_type: str, base_url: str) -> str:
        templates = {
            "rest_api": f"""MANDATORY FILE STRUCTURE FOR REST API:

```python
import pytest
import requests
import uuid

BASE_URL = "{base_url}"

@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({{"Content-Type": "application/json"}})
    yield session
    session.close()

@pytest.fixture
def api_base_url():
    return BASE_URL

@pytest.fixture  
def test_user_data():
    uid = uuid.uuid4().hex[:8]
    return {{
        "username": f"user_{{uid}}",
        "email": f"user_{{uid}}@example.com",
        "password": f"securepass_{{uid}}"
    }}
```
""",
            "cli": f"""MANDATORY FILE STRUCTURE FOR CLI APPLICATION:

```python
import pytest
import subprocess
import uuid
import os

@pytest.fixture
def cli_runner():
    def _run(args, input_text=None, env=None):
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            input=input_text,
            env=full_env
        )
        return result
    return _run

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
""",
            "grpc": f"""MANDATORY FILE STRUCTURE FOR gRPC SERVICE:

```python
import pytest
import grpc
import uuid

@pytest.fixture
def grpc_channel():
    channel = grpc.insecure_channel("{base_url.replace('http://', '').replace('https://', '')}")
    yield channel
    channel.close()

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
""",
            "library": """MANDATORY FILE STRUCTURE FOR LIBRARY/MODULE:

```python
import pytest
import uuid

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]

@pytest.fixture
def sample_data(unique_id):
    return {
        "id": unique_id,
        "name": f"test_{unique_id}"
    }
```
""",
            "graphql": f"""MANDATORY FILE STRUCTURE FOR GraphQL API:

```python
import pytest
import requests
import uuid

GRAPHQL_URL = "{base_url}/graphql"

@pytest.fixture
def graphql_client():
    session = requests.Session()
    session.headers.update({{"Content-Type": "application/json"}})
    yield session
    session.close()

@pytest.fixture
def execute_query(graphql_client):
    def _execute(query, variables=None):
        payload = {{"query": query}}
        if variables:
            payload["variables"] = variables
        return graphql_client.post(GRAPHQL_URL, json=payload)
    return _execute

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
""",
            "websocket": f"""MANDATORY FILE STRUCTURE FOR WebSocket APPLICATION:

```python
import pytest
import websocket
import json
import uuid

WS_URL = "{base_url.replace('http', 'ws')}/ws"

@pytest.fixture
def ws_connection():
    ws = websocket.create_connection(WS_URL)
    yield ws
    ws.close()

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
"""
        }
        
        return templates.get(app_type, templates["rest_api"])

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
1. TEST_ERROR - Issue in the test code itself:
   - Wrong endpoint URL (e.g., using "/users" instead of "/api/users")
   - Wrong HTTP method
   - Wrong assertion
   - Bad test data
   - Timing/race condition
   - Missing setup/cleanup
   
2. ACTUAL_DEFECT - Legitimate bug in the application:
   - Correct endpoint returns wrong data
   - Business logic error
   - Database constraint violation
   - Authentication/authorization bug

IMPORTANT: A 404 response on a POST/PUT request usually means WRONG URL (TEST_ERROR), not a missing feature.
If the test uses an endpoint like "/users" or "/login" but the API uses "/api/users" or "/api/auth/login", that's TEST_ERROR.

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
            0.3,
            config.MAX_TOKENS_CLASSIFICATION
        )
        
        content = self._extract_json(content)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse classification JSON: {e}")
            return {
                "classification": "TEST_ERROR",
                "confidence": "low",
                "reason": "Failed to parse AI response"
            }

    def heal_test(self, test_code: str, failure_info: dict, app_metadata: Dict = None) -> str:
        logger.info(f"Healing test: {failure_info.get('nodeid', 'unknown')}")
        
        if app_metadata is None:
            app_metadata = {}
        
        app_type, base_url, port = self._get_connection_info(app_metadata)
        
        app_context = self._get_healing_context_for_app_type(app_type, f"{base_url}:{port}")
        
        prompt = f"""Fix this failing test for a {app_type.upper()} application.

{app_context}

Current Test Code:
{test_code}

Failure Information:
- Test Name: {failure_info.get('nodeid', 'N/A')}
- Error: {failure_info.get('call', {}).get('longrepr', 'N/A')}

Requirements:
- Fix the test error while maintaining test intent
- Keep all fixture definitions in place (tests are self-contained)
- Use the correct patterns for {app_type} applications
- NO comments of any kind
- NO docstrings of any kind
- Use type hints
- Return ONLY the fixed Python code, no explanations

Generate the fixed test code:"""

        messages = [
            {"role": "system", "content": f"You are an expert test automation engineer specializing in {app_type} applications. Fix failing tests while maintaining their purpose. Generate clean code with NO comments and NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            0.5,
            config.MAX_TOKENS_HEALING
        )
        
        logger.debug("Test healing complete")
        return result

    def _get_healing_context_for_app_type(self, app_type: str, base_url: str) -> str:
        contexts = {
            "rest_api": f"""APPLICATION CONTEXT:
- This is a REST API test using requests library
- BASE_URL should be: {base_url}
- Use api_client fixture for HTTP requests
- Use api_base_url fixture for the base URL""",
            "graphql": f"""APPLICATION CONTEXT:
- This is a GraphQL API test
- GRAPHQL_URL should be: {base_url}/graphql
- Use graphql_client fixture for requests
- Use execute_query fixture for GraphQL queries""",
            "cli": """APPLICATION CONTEXT:
- This is a CLI application test using subprocess
- Use cli_runner fixture to execute commands
- Check exit codes and stdout/stderr""",
            "grpc": f"""APPLICATION CONTEXT:
- This is a gRPC service test
- Use grpc_channel fixture for connections
- Channel should connect to: {base_url.replace('http://', '').replace('https://', '')}""",
            "websocket": f"""APPLICATION CONTEXT:
- This is a WebSocket application test
- WS_URL should be: {base_url.replace('http', 'ws')}/ws
- Use ws_connection fixture for WebSocket connections""",
            "library": """APPLICATION CONTEXT:
- This is a library/module test
- Import and test functions/classes directly
- Use sample_data and unique_id fixtures for test data"""
        }
        return contexts.get(app_type, contexts["rest_api"])

    def fix_collection_error(self, test_file: str, test_code: str, error_message: str, app_metadata: Dict = None) -> str:
        logger.info(f"Fixing collection error in: {test_file}")
        
        if app_metadata is None:
            app_metadata = {}
        
        app_type, base_url, port = self._get_connection_info(app_metadata)
        
        app_context = self._get_healing_context_for_app_type(app_type, f"{base_url}:{port}")
        
        prompt = f"""Fix this pytest collection error for a {app_type.upper()} application.

{app_context}

Test File: {test_file}

Current Test Code:
```python
{test_code}
```

Collection Error:
{error_message}

Common Issues to Fix:
1. ImportError: Trying to import functions that don't exist or aren't exportable
   - Solution: Use proper test patterns for {app_type} applications
   - Do NOT import application functions directly

2. Syntax errors or invalid Python
   - Solution: Fix syntax issues

3. Missing fixtures or dependencies
   - Solution: Add required fixtures or imports

Requirements:
- Fix the collection error while maintaining test intent
- Use proper testing patterns for {app_type} applications
- Keep all fixture definitions in place (tests are self-contained)
- NO comments of any kind
- NO docstrings of any kind
- Use type hints where appropriate
- Return ONLY the fixed Python code, no explanations or markdown formatting

Generate the fixed test code:"""

        messages = [
            {"role": "system", "content": f"You are an expert test automation engineer specializing in {app_type} applications. Fix pytest collection errors using proper testing patterns. Generate code with NO comments and NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        content = self._call_api(
            messages,
            0.3,
            config.MAX_TOKENS_HEALING
        )
        
        content = strip_markdown_fences(content)
        
        logger.debug("Collection error fix complete")
        return content

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
            0.3,
            config.MAX_TOKENS_BUG_ANALYSIS
        )
        
        logger.debug("Bug analysis complete")
        return result

    def validate_tests(self, test_files: Dict[str, str], app_metadata: Dict = None) -> dict:
        logger.info("Validating generated tests with AI reviewer...")

        if app_metadata is None:
            app_metadata = {}
        
        app_type, base_url, port = self._get_connection_info(app_metadata)
        
        logger.info(f"Validating for app_type={app_type}, port={port}")

        serialized_tests = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )

        prompt = f"""You are auditing generated pytest test files. Focus ONLY on issues that will cause test FAILURES.

APPLICATION TYPE: {app_type.upper()}
EXPECTED BASE URL: {base_url}:{port}

IMPORTANT: These tests are SELF-CONTAINED. Each file has its own fixtures.
This is INTENTIONAL - do NOT flag fixture definitions as issues.

Generated tests:
{serialized_tests}

CRITICAL ISSUES TO CHECK (these cause test failures):
1. Missing imports (pytest, requests, uuid, subprocess, etc.)
2. Syntax errors or invalid Python
3. Using wrong port (expected: {port})
4. Tests using fixtures that are not defined in the same file
5. Missing fixture decorators (@pytest.fixture)

IGNORE these (they are NOT issues):
- Each file defining its own fixtures - THIS IS CORRECT
- BASE_URL or similar constants at module level - THIS IS CORRECT
- Test naming conventions
- Minor overlaps between test scenarios

Respond in JSON:
{{
  "status": "pass" | "fail",
  "issues": [
    {{
      "type": "missing-import" | "syntax-error" | "wrong-port" | "undefined-fixture",
      "detail": "Description with file and line reference",
      "suggestion": "How to fix"
    }}
  ]
}}

Return "pass" if tests are syntactically correct and self-contained. Only fail for actual errors."""

        messages = [
            {"role": "system", "content": f"You are an expert pytest reviewer for {app_type} applications. Check for syntax and import issues. Return ONLY valid JSON, no markdown."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self._call_api(
                messages,
                0.3,
                config.MAX_TOKENS_SUMMARY
            )
            response = self._extract_json(response)
            
            if not response:
                return {"status": "pass", "issues": []}
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning("AI test validation returned invalid JSON: %s", e)
            return {"status": "pass", "issues": []}
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI test validation failed: %s", exc)
            return {"status": "error", "issues": [{"type": "exception", "detail": str(exc)}]}

    def heal_tests(self, test_files: Dict[str, str], issues: List[Dict]) -> Dict[str, str]:
        logger.info("Healing generated tests via AI...")

        healed_result = self._heal_tests_batch(test_files, issues)
        
        if healed_result:
            return healed_result
        
        logger.info("Batch healing failed, trying individual file healing...")
        return self._heal_tests_individually(test_files, issues)

    def _heal_tests_batch(self, test_files: Dict[str, str], issues: List[Dict]) -> Dict[str, str]:
        serialized_tests = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )
        issues_text = json.dumps(issues, indent=2)

        prompt = f"""You must FIX the generated pytest test files below.

IMPORTANT: These tests are SELF-CONTAINED. Each file has its own fixtures defined at the top.
Do NOT remove fixture definitions - they are intentional.

Current tests:
{serialized_tests}

Issues detected:
{issues_text}

Requirements:
- Fix the specific issues listed above
- Keep all fixture definitions in place (tests are self-contained)
- Replace any hardcoded test data with uuid-based values
- Keep imports minimal and valid
- Preserve descriptive test names
- NO comments, NO docstrings
- Return JSON mapping absolute file paths to their FIXED code. Example:
{{"/abs/path/to/test_file.py": "<fixed python code>"}}

Only return JSON. Do not include markdown fences or additional text.
"""

        messages = [
            {"role": "system", "content": "You are an expert pytest engineer. Fix the provided self-contained tests to resolve validation issues. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self._call_api(
                messages,
                0.5,
                config.MAX_TOKENS_BATCH_HEALING
            )
            
            response = self._extract_json(response)
            
            healed = json.loads(response)
            if not isinstance(healed, dict):
                raise ValueError("Expected JSON object mapping file paths to code")
            return {path: code.strip() for path, code in healed.items() if isinstance(code, str)}
        except json.JSONDecodeError as e:
            logger.warning("Batch healing returned invalid JSON: %s", e)
            return {}
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("AI batch test healing failed: %s", exc)
            return {}

    def _heal_tests_individually(self, test_files: Dict[str, str], issues: List[Dict]) -> Dict[str, str]:
        healed_files = {}
        
        for filepath, code in test_files.items():
            file_issues = [i for i in issues if filepath in i.get("detail", "")]
            if not file_issues:
                continue
            
            logger.info(f"Healing individual file: {filepath}")
            
            prompt = f"""Fix this pytest test file.

IMPORTANT: This test is SELF-CONTAINED with its own fixtures defined at the top.
Do NOT remove fixture definitions - they are intentional.

Current test file ({filepath}):
```python
{code}
```

Issues to fix:
{json.dumps(file_issues, indent=2)}

CRITICAL REQUIREMENTS:
1. Keep all fixture definitions in place
2. ALL API calls MUST use the api_base_url fixture defined in this file
3. Replace any hardcoded test data with uuid-based values
4. NO comments, NO docstrings
5. Return ONLY the fixed Python code
"""

            messages = [
                {"role": "system", "content": "You are an expert pytest engineer. Fix the self-contained test file. Return ONLY Python code."},
                {"role": "user", "content": prompt}
            ]

            try:
                response = self._call_api(
                    messages,
                    0.5,
                    config.MAX_TOKENS_HEALING
                )
                
                response = strip_markdown_fences(response)
                healed_files[filepath] = response
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"Failed to heal {filepath}: {exc}")
        
        return healed_files

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
7. Recommendations

Format as markdown with clear sections and bullet points.
"""

        messages = [
            {"role": "system", "content": "You are an expert QA reporting specialist. Create clear, actionable test reports with emphasis on iterative healing results and bug identification."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            0.4,
            config.MAX_TOKENS_SUMMARY
        )
        
        logger.info("Summary generation complete")
        return result
