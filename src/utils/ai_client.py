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
from utils.app_metadata import AppMetadata, get_json_schema

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
            0.4,
            config.MAX_TOKENS_ANALYSIS
        )
        
        logger.info("Code analysis complete")
        return result

    def analyze_code(self, code_files: Dict[str, str]) -> str:
        converted_files = {path: (content, 'python') for path, content in code_files.items()}
        return self.analyze_code_and_docs(converted_files, {}, ['python'])

    def generate_app_metadata(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str],
        languages: List[str]
    ) -> Dict:
        logger.info("Generating structured application metadata...")

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

        json_schema = get_json_schema()

        prompt = f"""Analyze the following application and generate STRUCTURED JSON metadata for test fixture generation.

Languages Detected: {languages_str}

{full_content}

Based on the code and documentation above, determine:
1. What TYPE of application is this? (REST API, GraphQL, gRPC, WebSocket, CLI, Library, Message Queue, Serverless, Batch Script)
2. What framework/technology stack is used?
3. What are the connection details? (URLs, ports, protocols)
4. What are the constraints? (auth requirements, env vars, external dependencies)
5. Is there a database? What type?
6. What are the testable components? (endpoints, commands, functions, etc.)

OUTPUT REQUIREMENTS:
- Return ONLY valid JSON matching the schema below
- Include ONLY the relevant connection type and details based on app_type
- If a field is not applicable or unknown, use null
- For test_credentials, extract from documentation or code if available
- For endpoints/commands/functions, list ALL discovered items

JSON SCHEMA:
{json_schema}

EXAMPLES BY APP TYPE:

For REST API:
{{
  "app_type": "rest_api",
  "framework": "Flask",
  "languages": ["python"],
  "constraints": {{
    "requires_auth": true,
    "auth_type": "bearer",
    "test_credentials": {{"username": "admin", "password": "admin123"}},
    "required_env_vars": [],
    "startup_time_seconds": 2
  }},
  "database": {{"type": "in-memory", "requires_cleanup": false}},
  "http_connection": {{
    "base_url": "http://localhost",
    "port": 5050,
    "protocol": "http",
    "auth_endpoint": "/api/auth/login",
    "health_endpoint": "/health"
  }},
  "rest_api_details": {{
    "endpoints": [
      {{"method": "GET", "path": "/health", "auth_required": false}},
      {{"method": "POST", "path": "/api/users", "auth_required": false}}
    ]
  }}
}}

For CLI Application:
{{
  "app_type": "cli",
  "framework": "clap",
  "languages": ["rust"],
  "constraints": {{
    "requires_auth": false,
    "required_env_vars": ["DATABASE_URL"],
    "startup_time_seconds": 0
  }},
  "cli_connection": {{
    "executable_path": "./target/release/myapp",
    "requires_build": true,
    "build_command": "cargo build --release"
  }},
  "cli_details": {{
    "commands": [
      {{"name": "list", "args": [], "flags": ["--json", "--verbose"], "expected_exit_code": 0}},
      {{"name": "add", "args": ["name"], "flags": ["--force"], "expected_exit_code": 0}}
    ],
    "supports_stdin": true
  }}
}}

For Library/Module:
{{
  "app_type": "library",
  "framework": "none",
  "languages": ["python"],
  "constraints": {{
    "requires_auth": false,
    "required_env_vars": []
  }},
  "library_connection": {{
    "import_path": "mypackage.utils",
    "exportable_functions": ["calculate_total", "validate_input"],
    "exportable_classes": ["DataProcessor", "Validator"]
  }},
  "library_details": {{
    "functions": [
      {{"name": "calculate_total", "params": ["items", "tax_rate"], "return_type": "float", "is_async": false}},
      {{"name": "validate_input", "params": ["data"], "return_type": "bool", "is_async": false}}
    ],
    "classes": [
      {{"name": "DataProcessor", "methods": ["process", "transform"], "constructor_params": ["config"]}}
    ]
  }}
}}

For gRPC Service:
{{
  "app_type": "grpc",
  "framework": "tonic",
  "languages": ["rust"],
  "constraints": {{
    "requires_auth": false,
    "required_env_vars": []
  }},
  "grpc_connection": {{
    "host": "localhost",
    "port": 50051,
    "use_tls": false,
    "proto_files": ["proto/service.proto"],
    "service_names": ["UserService", "AuthService"]
  }},
  "grpc_details": {{
    "services": [{{"name": "UserService", "methods": ["GetUser", "CreateUser", "ListUsers"]}}],
    "methods": [
      {{"name": "GetUser", "request_type": "GetUserRequest", "response_type": "User"}},
      {{"name": "CreateUser", "request_type": "CreateUserRequest", "response_type": "User"}}
    ]
  }}
}}

Now analyze the provided code/documentation and generate the appropriate JSON metadata:"""

        messages = [
            {"role": "system", "content": "You are an expert code analyst. Analyze applications of ANY type (REST API, CLI, Library, gRPC, GraphQL, WebSocket, Message Queue, Serverless) and output ONLY valid JSON metadata. Be precise about connection details, ports, and authentication requirements."},
            {"role": "user", "content": prompt}
        ]

        content = self._call_api(
            messages,
            0.4,
            config.MAX_TOKENS_ANALYSIS
        )

        content = self._extract_json(content)

        try:
            metadata = json.loads(content)
            logger.info("Structured metadata generation complete")
            return metadata
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {e}")
            logger.debug(f"Raw content: {content}")
            return {
                "app_type": "rest_api",
                "framework": "unknown",
                "languages": languages,
                "constraints": {"requires_auth": False, "required_env_vars": []},
                "http_connection": {"base_url": "http://localhost", "port": 8080, "protocol": "http"}
            }

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
            0.7,
            config.MAX_TOKENS_GENERATION
        )
        
        logger.debug("Test generation complete")
        return result

    def generate_category_tests(
        self,
        analysis_markdown: str,
        category: str,
        scenarios: List[str],
        conftest_content: Optional[str] = None
    ) -> str:
        logger.info(f"Generating {category} tests ({len(scenarios)} scenarios)...")

        scenarios_list = "\n".join([f"- {s}" for s in scenarios])

        prompt = f"""Generate a pytest test file with EXACTLY {len(scenarios)} SEPARATE test functions.

API DOCUMENTATION (USE EXACT ENDPOINT PATHS FROM HERE):
{analysis_markdown}

MANDATORY FILE STRUCTURE:

```python
import pytest
import requests
import uuid

BASE_URL = "http://localhost:5050"

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

# Then {len(scenarios)} SEPARATE test functions below
```

SCENARIOS TO IMPLEMENT (one test function per scenario):
{scenarios_list}

CRITICAL RULES:
1. Create EXACTLY {len(scenarios)} SEPARATE test functions - one per scenario above
2. DO NOT combine scenarios into a single test
3. Each test function name: test_<descriptive_name>
4. Each test is independent - creates its own data
5. Use fixtures: api_client, api_base_url, test_user_data
6. NO comments, NO docstrings
7. Keep each test focused on ONE scenario
8. **USE EXACT ENDPOINT PATHS FROM THE DOCUMENTATION ABOVE**
   - If docs say "/api/users" use "/api/users" NOT "/users"
   - If docs say "/api/auth/login" use "/api/auth/login" NOT "/login"
   - DO NOT invent endpoints like "/register" - use what's documented

Generate the file with fixtures then {len(scenarios)} individual test functions:"""

        messages = [
            {"role": "system", "content": f"Generate EXACTLY {len(scenarios)} SEPARATE test functions. DO NOT combine them. Each scenario = one test function. NO comments."},
            {"role": "user", "content": prompt}
        ]

        result = self._call_api(
            messages,
            0.7,
            config.MAX_TOKENS_BATCH_HEALING
        )

        logger.debug(f"Category test generation complete for {category}")
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
            0.5,
            config.MAX_TOKENS_HEALING
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
            0.3,
            config.MAX_TOKENS_HEALING
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
            0.3,
            config.MAX_TOKENS_BUG_ANALYSIS
        )
        
        logger.debug("Bug analysis complete")
        return result

    def generate_fixtures(self, analysis_markdown: str, best_practices: str) -> str:
        return self.generate_fixtures_with_metadata(analysis_markdown, best_practices, "", "rest_api")

    def generate_fixtures_with_metadata(
        self, 
        analysis_markdown: str, 
        best_practices: str,
        metadata_context: str,
        app_type: str
    ) -> str:
        logger.info(f"Generating conftest.py fixtures for {app_type} application...")

        app_type_fixtures = self._get_app_type_fixture_examples(app_type)

        metadata_section = ""
        if metadata_context:
            metadata_section = f"""
## STRUCTURED APPLICATION METADATA (USE THIS FOR PRECISE FIXTURE GENERATION):
{metadata_context}

IMPORTANT: Use the exact values from the metadata above (URLs, ports, credentials, etc.)
"""
        
        prompt = f"""Generate pytest fixtures for conftest.py based on the application analysis and metadata.

APPLICATION TYPE: {app_type.upper()}
{metadata_section}

Code Analysis:
{analysis_markdown}

Best Practices Reference (for patterns only):
{best_practices}

{app_type_fixtures}

CRITICAL REQUIREMENTS:

1. IMPORTS - MUST include ALL necessary imports at the very top:
   - import pytest
   - import uuid (if generating unique data)
   - import requests (for REST APIs)
   - import subprocess (for CLI applications)
   - import grpc (for gRPC services)
   - import websocket (for WebSocket applications)
   - Any other imports needed by your fixtures
   - VERIFY every module you use is imported

2. NO HARDCODED TEST DATA - CRITICAL:
   - NEVER use hardcoded usernames like "testuser" or "admin"
   - NEVER use hardcoded emails like "test@example.com"
   - ALWAYS generate unique data using uuid.uuid4().hex[:8]
   - Example: f"user_{{uuid.uuid4().hex[:8]}}" for usernames
   - Example: f"user_{{uuid.uuid4().hex[:8]}}@example.com" for emails

3. USE METADATA VALUES:
   - Use exact base_url and port from metadata
   - Use auth_endpoint path from metadata if auth is required
   - Use test_credentials from metadata for authenticated fixtures
   - Create fixtures matching the app_type (CLI runner, gRPC channel, etc.)

4. APP-TYPE SPECIFIC FIXTURES:
   - REST API: api_client, api_base_url, authenticated_client
   - CLI: cli_runner, cli_executable, working_directory
   - gRPC: grpc_channel, grpc_stub
   - WebSocket: ws_connection, ws_url
   - Library: module imports, function references
   - GraphQL: graphql_client, graphql_url, graphql_query helper
   - Message Queue: connection, channel, queue fixtures

5. Include cleanup/teardown using yield where appropriate

6. CODE STYLE - CRITICAL:
   - NO comments of any kind
   - NO docstrings of any kind
   - NO inline comments
   - Code must be self-explanatory through clear naming

7. Return ONLY the Python code, no explanations or markdown formatting

Generate fixtures with ALL imports and NO hardcoded data:"""

        messages = [
            {"role": "system", "content": f"You are an expert test automation engineer specializing in {app_type} applications. Generate pytest fixtures that match the exact application type and use precise values from the provided metadata. CRITICAL: 1) Include ALL imports at the top. 2) NEVER use hardcoded data - always use uuid for unique values. 3) NO comments, NO docstrings."},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_api(
            messages,
            0.5,
            config.MAX_TOKENS_GENERATION
        )
        
        logger.info("Fixture generation complete")
        return result

    def _get_app_type_fixture_examples(self, app_type: str) -> str:
        examples = {
            "rest_api": """
## REST API FIXTURE EXAMPLES:
```python
import pytest
import requests
import uuid

@pytest.fixture
def api_base_url():
    return "http://localhost:5050"  # Use actual port from metadata

@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()

@pytest.fixture
def authenticated_client(api_client, api_base_url):
    # Use test_credentials from metadata
    response = api_client.post(f"{api_base_url}/api/auth/login", json={
        "username": "admin",  # From metadata
        "password": "admin123"  # From metadata
    })
    token = response.json().get("token")
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client
```
""",
            "cli": """
## CLI APPLICATION FIXTURE EXAMPLES:
```python
import pytest
import subprocess
import uuid
import os

@pytest.fixture
def cli_executable():
    return "./target/release/myapp"  # Use actual path from metadata

@pytest.fixture
def cli_runner():
    def _run_command(args, input_text=None, env=None):
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
    return _run_command

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
""",
            "grpc": """
## gRPC SERVICE FIXTURE EXAMPLES:
```python
import pytest
import grpc
import uuid

@pytest.fixture
def grpc_channel():
    channel = grpc.insecure_channel("localhost:50051")  # Use port from metadata
    yield channel
    channel.close()

@pytest.fixture
def grpc_stub(grpc_channel):
    # Import the generated stub - adjust based on proto files in metadata
    from generated import service_pb2_grpc
    return service_pb2_grpc.MyServiceStub(grpc_channel)

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
""",
            "websocket": """
## WEBSOCKET APPLICATION FIXTURE EXAMPLES:
```python
import pytest
import websocket
import json
import uuid

@pytest.fixture
def ws_url():
    return "ws://localhost:8080/ws"  # Use actual URL from metadata

@pytest.fixture
def ws_connection(ws_url):
    ws = websocket.create_connection(ws_url)
    yield ws
    ws.close()

@pytest.fixture
def ws_send_receive():
    def _send_receive(ws, message):
        ws.send(json.dumps(message))
        return json.loads(ws.recv())
    return _send_receive
```
""",
            "graphql": """
## GRAPHQL API FIXTURE EXAMPLES:
```python
import pytest
import requests
import uuid

@pytest.fixture
def graphql_url():
    return "http://localhost:4000/graphql"  # Use actual URL from metadata

@pytest.fixture
def graphql_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()

@pytest.fixture
def graphql_query():
    def _execute_query(client, url, query, variables=None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        return client.post(url, json=payload)
    return _execute_query
```
""",
            "library": """
## LIBRARY/MODULE FIXTURE EXAMPLES:
```python
import pytest
import uuid

# Import the module/package being tested - adjust based on import_path from metadata
# from mypackage import MyClass, my_function

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]

@pytest.fixture
def sample_data(unique_id):
    return {
        "id": unique_id,
        "name": f"test_{unique_id}"
    }

# Add fixtures for common test data structures used by library functions
```
""",
            "message_queue": """
## MESSAGE QUEUE FIXTURE EXAMPLES:
```python
import pytest
import pika
import json
import uuid

@pytest.fixture
def rabbitmq_connection():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters("localhost")  # Use broker_url from metadata
    )
    yield connection
    connection.close()

@pytest.fixture
def rabbitmq_channel(rabbitmq_connection):
    channel = rabbitmq_connection.channel()
    yield channel
    channel.close()

@pytest.fixture
def test_queue(rabbitmq_channel, unique_id):
    queue_name = f"test_queue_{unique_id}"
    rabbitmq_channel.queue_declare(queue=queue_name, auto_delete=True)
    yield queue_name

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```
""",
            "serverless": """
## SERVERLESS FUNCTION FIXTURE EXAMPLES:
```python
import pytest
import requests
import json
import uuid

@pytest.fixture
def function_url():
    # Use the deployed function URL or local emulator
    return "http://localhost:3000"

@pytest.fixture
def invoke_function():
    def _invoke(url, event_data):
        response = requests.post(url, json=event_data)
        return response
    return _invoke

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]

@pytest.fixture
def sample_event(unique_id):
    return {
        "requestContext": {"requestId": unique_id},
        "body": json.dumps({"test": True})
    }
```
"""
        }
        
        return examples.get(app_type, examples.get("rest_api", ""))

    def validate_tests(self, test_files: Dict[str, str], conftest_code: str = "") -> dict:
        logger.info("Validating generated tests with AI reviewer...")

        serialized_tests = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )

        prompt = f"""You are auditing generated pytest test files. Focus ONLY on issues that will cause test FAILURES.

IMPORTANT: These tests are SELF-CONTAINED. Each file has its own fixtures (api_client, api_base_url, test_user_data).
This is INTENTIONAL - do NOT flag fixture definitions as issues.

Generated tests:
{serialized_tests}

CRITICAL ISSUES TO CHECK (these cause test failures):
1. Missing imports (pytest, requests, uuid, etc.)
2. Syntax errors or invalid Python
3. Using wrong port (should be 5050)
4. Tests using fixtures that are not defined in the same file
5. Missing fixture decorators (@pytest.fixture)

IGNORE these (they are NOT issues):
- Each file defining its own fixtures (api_client, api_base_url, test_user_data) - THIS IS CORRECT
- BASE_URL constant at module level - THIS IS CORRECT
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
            {"role": "system", "content": "You are an expert pytest reviewer. Identify duplicate scenarios and best-practice violations. Return ONLY valid JSON, no markdown."},
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

    def heal_tests(self, test_files: Dict[str, str], conftest_code: str, issues: List[Dict]) -> Dict[str, str]:
        logger.info("Healing generated tests via AI...")

        healed_result = self._heal_tests_batch(test_files, conftest_code, issues)
        
        if healed_result:
            return healed_result
        
        logger.info("Batch healing failed, trying individual file healing...")
        return self._heal_tests_individually(test_files, conftest_code, issues)

    def _heal_tests_batch(self, test_files: Dict[str, str], conftest_code: str, issues: List[Dict]) -> Dict[str, str]:
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
            {"role": "system", "content": "You are an expert pytest engineer. Fix the provided tests to resolve all validation issues. Return ONLY valid JSON."},
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

    def _heal_tests_individually(self, test_files: Dict[str, str], conftest_code: str, issues: List[Dict]) -> Dict[str, str]:
        healed_files = {}
        
        for filepath, code in test_files.items():
            file_issues = [i for i in issues if filepath in i.get("detail", "")]
            if not file_issues:
                continue
            
            logger.info(f"Healing individual file: {filepath}")
            
            prompt = f"""Fix this pytest test file.

Fixtures available from conftest.py:
```python
{conftest_code}
```

Current test file ({filepath}):
```python
{code}
```

Issues to fix:
{json.dumps(file_issues, indent=2)}

CRITICAL REQUIREMENTS:
1. ALL API calls MUST use api_base_url fixture:
   WRONG: api_client.get("/api/users")
   WRONG: api_client.get("http://localhost:5000/api/users")
   CORRECT: api_client.get(f"{{api_base_url}}/api/users")

2. Add api_base_url to function parameters if not present:
   WRONG: def test_something(api_client):
   CORRECT: def test_something(api_client, api_base_url):

3. Use fixtures from conftest.py - do NOT redefine them
4. NO comments, NO docstrings
5. Return ONLY the fixed Python code
"""

            messages = [
                {"role": "system", "content": "You are an expert pytest engineer. Fix the test file. Return ONLY Python code."},
                {"role": "user", "content": prompt}
            ]

            try:
                response = self._call_api(
                    messages,
                    0.5,
                    config.MAX_TOKENS_HEALING
                )
                
                if response.startswith("```python"):
                    response = response[9:]
                if response.startswith("```"):
                    response = response[3:]
                if response.endswith("```"):
                    response = response[:-3]
                
                healed_files[filepath] = response.strip()
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
            0.4,
            config.MAX_TOKENS_SUMMARY
        )
        
        logger.info("Summary generation complete")
        return result
