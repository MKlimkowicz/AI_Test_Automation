import json
import logging
import re
from typing import Optional, Dict, List, Tuple, Any, Iterator

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

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key: str = api_key or config.CLAUDE_API_KEY or ""
        if not self.api_key:
            raise ValueError("CLAUDE_API_KEY not found in environment variables")
        self.client: Anthropic = Anthropic(api_key=self.api_key)
        self.model: str = config.CLAUDE_MODEL
        self.enable_streaming: bool = config.ENABLE_STREAMING
        logger.debug(f"Initialized Claude client with model: {self.model}")

    def _create_retry_decorator(self) -> Any:
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

    def _call_api(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        @self._create_retry_decorator()
        def _make_request() -> str:
            logger.debug(f"Making Claude API call with max_tokens={max_tokens}")

            system_msg: str = ""
            user_messages: List[Dict[str, str]] = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)

            if self.enable_streaming:
                return self._stream_response(system_msg, user_messages, max_tokens, temperature)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_msg,
                messages=user_messages
            )
            return response.content[0].text.strip()

        return _make_request()

    def _stream_response(
        self,
        system_msg: str,
        user_messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> str:
        chunks: List[str] = []
        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_msg,
            messages=user_messages
        ) as stream:
            for text in stream.text_stream:
                chunks.append(text)
        return "".join(chunks).strip()

    def stream_response_iterator(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int
    ) -> Iterator[str]:
        system_msg: str = ""
        user_messages: List[Dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system_msg,
            messages=user_messages
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _extract_json(self, content: str) -> str:
        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if "```" in content:
            content = content.split("```")[0]

        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)

        return content.strip()

    def _get_connection_info(self, app_metadata: Dict[str, Any]) -> Tuple[str, str, int]:
        app_type: str = app_metadata.get("app_type", "rest_api")

        http_conn: Dict[str, Any] = app_metadata.get("http_connection", {})
        base_url: str = http_conn.get("base_url") or app_metadata.get("base_url", "http://localhost")
        port: int = http_conn.get("port") or app_metadata.get("port", 8080)

        return app_type, base_url, port

    def _format_code_sections(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str]
    ) -> str:
        code_section: str = ""
        if code_files:
            code_parts: List[str] = []
            config_parts: List[str] = []
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

        doc_section: str = ""
        if doc_files:
            doc_parts: List[str] = []
            for filepath, content in doc_files.items():
                doc_parts.append(f"### Documentation: {filepath}\n```\n{content}\n```")
            doc_section = "## Documentation\n\n" + "\n\n".join(doc_parts)

        content_sections: List[str] = []
        if code_section:
            content_sections.append(code_section)
        if doc_section:
            content_sections.append(doc_section)

        return "\n\n".join(content_sections)

    def _get_app_type_analysis_components(self, app_type: str) -> str:
        components: Dict[str, str] = {
            "rest_api": """### API Endpoints
List all endpoints found with HTTP method, path, request/response schema, and description

List authentication mechanisms (JWT, OAuth, API Key, etc.) and protected endpoints

List all database models/schemas found""",
            "cli": """### Commands
List all commands and subcommands with their arguments and flags

List input file formats, stdin handling, and output file generation

List expected exit codes and their meanings""",
            "library": """### Public API
List all exported functions and classes with their signatures

List function parameters, return types, and exceptions raised

List internal and external dependencies""",
            "graphql": """### Schema Overview
Describe the GraphQL schema structure

List all available queries with their parameters and return types

List all mutations with their input types and effects

List subscriptions if any""",
            "grpc": """### Services
List all gRPC services defined

List RPC methods with request/response message types

List streaming patterns used (unary, server, client, bidirectional)""",
            "websocket": """### Events
List WebSocket events (client-to-server and server-to-client)

List message formats and schemas

Describe connection, reconnection, and authentication handshake""",
            "message_queue": """### Queues/Topics
List all queues or topics used

List message formats and validation rules

List components that produce or consume messages""",
            "serverless": """### Functions
List all serverless functions and their handlers

List trigger types (API Gateway, S3, SQS, CloudWatch, etc.)

List environment variables and resource settings""",
            "batch_script": """### Entry Points
List main scripts and their purposes

List required input files and formats

List generated output files and formats"""
        }
        return components.get(app_type, components["library"])

    def _get_app_type_test_categories(self, app_type: str) -> str:
        from utils.app_types import get_categories_for_app_type
        categories = get_categories_for_app_type(app_type)

        category_descriptions: Dict[str, str] = {
            "functional": "Functional Tests - Verify business logic, feature correctness, happy paths and error handling",
            "security": "Security Tests - Authentication, authorization, input sanitization, data protection",
            "validation": "Validation Tests - Input validation, boundary conditions, data format validation",
            "performance": "Performance Tests - Response times, load testing, resource usage",
            "integration": "Integration Tests - Component interactions, external service integration",
            "argument_parsing": "Argument Parsing Tests - Command-line arguments, flags, options validation",
            "stdin_processing": "Stdin Processing Tests - Pipe input handling, streaming input",
            "file_operations": "File Operations Tests - Read/write files, file format handling",
            "exit_codes": "Exit Codes Tests - Success/error exit codes, error messages",
            "error_handling": "Error Handling Tests - Exception handling, graceful degradation",
            "unit": "Unit Tests - Individual function/method testing, isolated behavior",
            "edge_cases": "Edge Cases Tests - Boundary values, empty inputs, large inputs",
            "exceptions": "Exception Tests - Expected exceptions, error conditions",
            "type_validation": "Type Validation Tests - Type checking, input type handling",
            "queries": "Query Tests - GraphQL query testing, field selection, variables",
            "mutations": "Mutation Tests - GraphQL mutations, data modifications",
            "subscriptions": "Subscription Tests - Real-time updates, event streams",
            "authorization": "Authorization Tests - Permission checks, role-based access",
            "unary_calls": "Unary Call Tests - Single request-response gRPC calls",
            "streaming": "Streaming Tests - Server/client/bidirectional streaming",
            "error_codes": "Error Code Tests - gRPC status codes, error handling",
            "deadlines": "Deadline Tests - Timeout handling, deadline propagation",
            "connection": "Connection Tests - WebSocket connection establishment, handshake",
            "messaging": "Messaging Tests - Message send/receive, format validation",
            "events": "Event Tests - Event handling, event ordering",
            "reconnection": "Reconnection Tests - Connection recovery, state restoration",
            "publishing": "Publishing Tests - Message publishing, delivery confirmation",
            "consuming": "Consuming Tests - Message consumption, processing",
            "message_format": "Message Format Tests - Schema validation, serialization",
            "dead_letter": "Dead Letter Tests - Failed message handling, retry logic",
            "ordering": "Ordering Tests - Message order guarantees",
            "acknowledgment": "Acknowledgment Tests - Ack/nack handling",
            "handler_invocation": "Handler Invocation Tests - Function execution, event handling",
            "event_parsing": "Event Parsing Tests - Event source parsing, format handling",
            "cold_start": "Cold Start Tests - Initialization behavior, first invocation",
            "timeout_handling": "Timeout Tests - Execution time limits, long-running operations",
            "error_responses": "Error Response Tests - Error format, status codes",
            "execution": "Execution Tests - Script execution, process handling",
            "input_files": "Input File Tests - File reading, format parsing",
            "output_files": "Output File Tests - File generation, content validation",
            "environment": "Environment Tests - Environment variable handling, configuration"
        }

        result_lines = []
        for cat in categories:
            desc = category_descriptions.get(cat, f"{cat.replace('_', ' ').title()} Tests")
            result_lines.append(f"### {desc}")
            result_lines.append(f"List specific {cat.replace('_', ' ')} test scenarios")
            result_lines.append("")

        return "\n".join(result_lines)

    def analyze_code_and_docs(
        self,
        code_files: Dict[str, Tuple[str, str]],
        doc_files: Dict[str, str],
        languages: List[str],
        detected_app_type: Optional[str] = None,
        rag_context: Optional[str] = None
    ) -> str:
        logger.info("Analyzing code and documentation...")

        full_content: str = self._format_code_sections(code_files, doc_files)
        languages_str: str = ", ".join(languages) if languages else "None detected"

        rag_section = ""
        if rag_context:
            rag_section = f"""
The following code snippets were retrieved as particularly relevant:

{rag_context}

"""
            logger.info(f"Including RAG context ({len(rag_context)} chars) in analysis")

        app_type_hint = ""
        components_section = """### API Endpoints
List all endpoints found (if any) with HTTP method, path, and description

List all database models/schemas found (if any)"""
        test_categories_section = """### Functional Tests
List specific functional test scenarios that verify business logic, API endpoints, data validation, CRUD operations, user workflows, and feature correctness.

Only include if the application has performance-critical features. Include response time, load, and stress testing scenarios.

Only include if the application has authentication, authorization, or data handling. Include auth, input sanitization, and data protection scenarios."""

        if detected_app_type and detected_app_type != "rest_api":
            app_type_hint = f"\nDETECTED APPLICATION TYPE: {detected_app_type.upper()}\n"
            components_section = self._get_app_type_analysis_components(detected_app_type)
            test_categories_section = self._get_app_type_test_categories(detected_app_type)

        prompt: str = f"""Analyze the following application and generate a comprehensive markdown report for test planning.

Languages Detected: {languages_str}
{app_type_hint}
{rag_section}{full_content}

Generate a detailed analysis in markdown format with these sections:

- Total Code Files: [count]
- Total Configuration Files: [count]
- Total Documentation Files: [count]
- Languages Detected: [list languages]
- Application Type: [rest_api/cli/library/graphql/grpc/websocket/message_queue/serverless/batch_script]
- Framework Detected: [Flask/Django/FastAPI/Express/Spring/Click/argparse/None/Other]
- Key Dependencies: [list main dependencies from config files if available]
- Analysis Date: [current date]

List each file (code, configuration, and documentation) with brief description of its purpose

{components_section}

List important functions with their purpose

List important classes with their purpose

Summarize key points from documentation files (if any)

Analyze the application and suggest test scenarios. Only include categories where testing is relevant.

{test_categories_section}

Note: If a category is not applicable to this application, omit it entirely. Focus on what actually needs testing based on the code, dependencies, and documentation provided.

Return ONLY the markdown, no additional explanations."""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are an expert code analyst and QA architect. Analyze codebases and documentation thoroughly to generate comprehensive test strategies. You can create test plans from documentation alone or combined with code. Identify the application type accurately."},
            {"role": "user", "content": prompt}
        ]

        result: str = self._call_api(
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
    ) -> Dict[str, Any]:
        logger.info("Generating structured application metadata...")

        full_content: str = self._format_code_sections(code_files, doc_files)
        languages_str: str = ", ".join(languages) if languages else "unknown"

        prompt: str = f"""Analyze the code/documentation below and extract metadata as JSON.

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

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a code analyst. Output ONLY valid JSON, no markdown fences, no explanations."},
            {"role": "user", "content": prompt}
        ]

        logger.debug("Calling AI for metadata generation...")
        raw_content: str = self._call_api(
            messages,
            0.3,
            config.MAX_TOKENS_ANALYSIS
        )

        logger.debug(f"Raw AI response for metadata: {raw_content[:500]}...")

        content: str = self._extract_json(raw_content)
        logger.debug(f"Extracted JSON: {content[:500]}...")

        try:
            metadata: Dict[str, Any] = json.loads(content)

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
        app_metadata: Optional[Dict[str, Any]] = None,
        include_negative_tests: bool = True,
        use_data_factories: bool = True,
        rag_context: Optional[str] = None
    ) -> str:
        logger.info(f"Generating {category} tests ({len(scenarios)} scenarios)...")

        if app_metadata is None:
            app_metadata = {}

        app_type, base_url, port = self._get_connection_info(app_metadata)
        full_url: str = f"{base_url}:{port}"

        rag_section = ""
        if rag_context:
            rag_section = f"""
Use this code context to write more accurate tests:

{rag_context}

"""

        logger.info(f"Using app_type={app_type}, base_url={full_url}")

        scenarios_list: str = "\n".join([f"- {s}" for s in scenarios])

        test_template: str = self._get_test_template_for_app_type(app_type, full_url, use_data_factories)

        negative_test_instruction: str = ""
        if include_negative_tests and config.ENABLE_NEGATIVE_TESTS:
            negative_test_instruction = f"""
NEGATIVE TEST REQUIREMENTS:
For each main scenario, also generate negative test cases that verify:
- Invalid input handling (empty strings, null values, wrong types)
- Boundary conditions (max length, min length, edge values)
- Authentication failures (if applicable)
- Resource not found scenarios
- Duplicate resource handling
Generate up to {config.MAX_NEGATIVE_TESTS_PER_CATEGORY} negative tests per category.
Name negative tests with prefix: test_negative_
"""

        data_factory_instruction: str = ""
        if use_data_factories and config.ENABLE_DATA_FACTORIES:
            data_factory_instruction = """
DATA FACTORY REQUIREMENTS:
Create a TestDataFactory class at the top of the file with methods to generate test data:
- Use @staticmethod methods for data generation
- Each method should return a dictionary with ALL fields needed to CREATE the resource via API
- Use uuid for unique identifiers to ensure test isolation
- Include methods for valid data and invalid data variations
- IMPORTANT: These factories generate data for CREATING resources, not just credentials

Example for REST API with user authentication:
class TestDataFactory:
    @staticmethod
    def valid_user() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"username": f"user_{uid}", "email": f"user_{uid}@test.com", "password": f"Pass_{uid}123"}

    @staticmethod
    def valid_admin_user() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"username": f"admin_{uid}", "email": f"admin_{uid}@test.com", "password": f"Admin_{uid}123", "role": "admin"}

    @staticmethod
    def invalid_user_short_username() -> dict:
        return {"username": "ab", "email": "test@test.com", "password": "ValidPass123"}

Usage in tests - ALWAYS create resources first:
    user_data = TestDataFactory.valid_user()
    api_client.post(f"{base_url}/api/users", json=user_data)  # CREATE the user
    login_response = api_client.post(f"{base_url}/api/auth/login", json={"username": user_data["username"], "password": user_data["password"]})
"""

        prompt: str = f"""Generate a pytest test file with EXACTLY {len(scenarios)} SEPARATE test functions.

APPLICATION TYPE: {app_type.upper()}
BASE URL: {full_url}

ANALYSIS/DOCUMENTATION:
{analysis_markdown}
{rag_section}
{test_template}

{data_factory_instruction}

{negative_test_instruction}

SCENARIOS TO IMPLEMENT (one test function per scenario):
{scenarios_list}

CRITICAL RULES:
1. Create EXACTLY {len(scenarios)} SEPARATE test functions - one per scenario above
2. DO NOT combine scenarios into a single test
3. Each test function name: test_<descriptive_name>
4. NEVER assume data already exists - each test MUST create its own prerequisite data via API calls
5. Use the fixtures defined in the template above
6. NO comments, NO docstrings
7. Keep each test focused on ONE scenario
8. Use the EXACT BASE_URL provided: {full_url}
9. Use EXACT endpoint paths from the documentation
10. Use type hints for all function parameters and return types

SELF-CONTAINED TEST PATTERN (MANDATORY):
- For authentication/login tests: First CREATE a user via POST /api/users, THEN login with those credentials
- For order tests: First create user, login, create product, THEN create order
- For any test requiring existing resources: CREATE them first via API calls within the test
- Use TestDataFactory to generate unique data, then POST it to create the resource
- Example pattern for login test:
  1. user_data = TestDataFactory.valid_user()
  2. api_client.post(f"{{base_url}}/api/users", json=user_data)  # CREATE user first
  3. response = api_client.post(f"{{base_url}}/api/auth/login", json={{"username": user_data["username"], "password": user_data["password"]}})
  4. assert response.status_code == 200

Generate the file with fixtures then {len(scenarios)} individual test functions:"""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": f"Generate EXACTLY {len(scenarios)} SEPARATE test functions for a {app_type} application. DO NOT combine them. Each scenario = one test function. NO comments. CRITICAL: Tests must be self-contained - create prerequisite resources via API calls before testing. Never assume users/data exist."},
            {"role": "user", "content": prompt}
        ]

        result: str = self._call_api(
            messages,
            0.7,
            config.MAX_TOKENS_BATCH_HEALING
        )

        logger.debug(f"Category test generation complete for {category}")
        return result

    def _get_data_factory_for_app_type(self, app_type: str) -> str:
        factories: Dict[str, str] = {
            "rest_api": """
class TestDataFactory:
    @staticmethod
    def valid_user() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"username": f"user_{uid}", "email": f"user_{uid}@test.com", "password": f"Pass_{uid}123!"}

    @staticmethod
    def invalid_user_short_username() -> dict:
        return {"username": "ab", "email": "test@test.com", "password": "ValidPass123!"}

    @staticmethod
    def invalid_user_bad_email() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"username": f"user_{uid}", "email": "invalid-email", "password": "ValidPass123!"}

    @staticmethod
    def invalid_user_short_password() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"username": f"user_{uid}", "email": f"user_{uid}@test.com", "password": "short"}
""",
            "cli": """
class TestDataFactory:
    @staticmethod
    def valid_args() -> list:
        return ["--verbose", "--output", f"/tmp/test_{uuid.uuid4().hex[:8]}.txt"]

    @staticmethod
    def invalid_args() -> list:
        return ["--nonexistent-flag", "--invalid"]

    @staticmethod
    def sample_input_content() -> str:
        uid = uuid.uuid4().hex[:8]
        return f"Sample input data for test {uid}\\nLine 2\\nLine 3"

    @staticmethod
    def empty_input() -> str:
        return ""

    @staticmethod
    def large_input(lines: int = 1000) -> str:
        return "\\n".join([f"Line {i}: data_{uuid.uuid4().hex[:8]}" for i in range(lines)])
""",
            "library": """
class TestDataFactory:
    @staticmethod
    def valid_input() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"id": uid, "name": f"test_{uid}", "value": 42}

    @staticmethod
    def invalid_input_missing_required() -> dict:
        return {"name": "incomplete"}

    @staticmethod
    def invalid_input_wrong_type() -> dict:
        return {"id": 12345, "name": None, "value": "not_a_number"}

    @staticmethod
    def edge_case_empty() -> dict:
        return {}

    @staticmethod
    def edge_case_large_value() -> dict:
        return {"id": "x" * 10000, "value": 10**100}
""",
            "graphql": """
class TestDataFactory:
    @staticmethod
    def valid_query_variables() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"id": uid, "limit": 10, "offset": 0}

    @staticmethod
    def invalid_query_variables() -> dict:
        return {"id": None, "limit": -1}

    @staticmethod
    def mutation_input() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"name": f"item_{uid}", "description": f"Test item {uid}"}
""",
            "grpc": """
class TestDataFactory:
    @staticmethod
    def valid_request_data() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"id": uid, "name": f"grpc_test_{uid}"}

    @staticmethod
    def invalid_request_data() -> dict:
        return {"id": "", "name": None}

    @staticmethod
    def large_payload() -> dict:
        return {"data": "x" * 10000}
""",
            "websocket": """
class TestDataFactory:
    @staticmethod
    def valid_message() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {"type": "message", "id": uid, "content": f"Test message {uid}"}

    @staticmethod
    def invalid_message() -> dict:
        return {"type": "unknown", "malformed": True}

    @staticmethod
    def ping_message() -> dict:
        return {"type": "ping", "timestamp": int(time.time())}
""",
            "message_queue": """
class TestDataFactory:
    @staticmethod
    def valid_message() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {
            "message_id": uid,
            "timestamp": datetime.now().isoformat(),
            "payload": {"action": "test", "data": f"content_{uid}"},
            "headers": {"content_type": "application/json"}
        }

    @staticmethod
    def invalid_message_missing_payload() -> dict:
        return {"message_id": uuid.uuid4().hex[:8]}

    @staticmethod
    def invalid_message_wrong_format() -> str:
        return "This is not JSON"

    @staticmethod
    def batch_messages(count: int = 10) -> list:
        return [TestDataFactory.valid_message() for _ in range(count)]
""",
            "serverless": """
class TestDataFactory:
    @staticmethod
    def api_gateway_event() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {
            "httpMethod": "POST",
            "path": "/test",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"id": uid, "action": "test"}),
            "queryStringParameters": {"param1": "value1"},
            "pathParameters": {"id": uid}
        }

    @staticmethod
    def s3_event() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {
            "Records": [{
                "s3": {
                    "bucket": {"name": f"test-bucket-{uid}"},
                    "object": {"key": f"test-object-{uid}.json"}
                }
            }]
        }

    @staticmethod
    def sqs_event() -> dict:
        uid = uuid.uuid4().hex[:8]
        return {
            "Records": [{
                "messageId": uid,
                "body": json.dumps({"action": "process", "data": uid})
            }]
        }

    @staticmethod
    def invalid_event() -> dict:
        return {"invalid": True, "missing_required_fields": True}
""",
            "batch_script": """
class TestDataFactory:
    @staticmethod
    def valid_input_file_content() -> str:
        uid = uuid.uuid4().hex[:8]
        return f"header1,header2,header3\\nvalue1_{uid},value2,value3\\nvalue4,value5_{uid},value6"

    @staticmethod
    def invalid_input_file_content() -> str:
        return "malformed,csv\\nwrong,number,of,columns"

    @staticmethod
    def empty_file_content() -> str:
        return ""

    @staticmethod
    def large_file_content(rows: int = 1000) -> str:
        header = "id,name,value"
        rows_data = [f"{i},{uuid.uuid4().hex[:8]},{i*100}" for i in range(rows)]
        return header + "\\n" + "\\n".join(rows_data)
"""
        }
        return factories.get(app_type, factories["library"])

    def _get_test_template_for_app_type(self, app_type: str, base_url: str, use_data_factories: bool = True) -> str:
        factory_import: str = ""
        if use_data_factories and config.ENABLE_DATA_FACTORIES:
            factory_import = self._get_data_factory_for_app_type(app_type)

        templates: Dict[str, str] = {
            "rest_api": f"""MANDATORY FILE STRUCTURE FOR REST API:

```python
import pytest
import requests
import uuid
from typing import Generator, Dict, Any

BASE_URL: str = "{base_url}"
{factory_import}

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
    uid: str = uuid.uuid4().hex[:8]
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
import tempfile
from pathlib import Path
from typing import Callable, Optional, Dict, Any, Generator

{factory_import}

@pytest.fixture
def cli_runner() -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run(
        args: list[str],
        input_text: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> subprocess.CompletedProcess[str]:
        full_env: Dict[str, str] = os.environ.copy()
        if env:
            full_env.update(env)
        result: subprocess.CompletedProcess[str] = subprocess.run(
            args,
            capture_output=True,
            text=True,
            input=input_text,
            env=full_env,
            cwd=cwd,
            timeout=timeout
        )
        return result
    return _run

@pytest.fixture
def temp_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    workspace: Path = tmp_path / f"workspace_{{uuid.uuid4().hex[:8]}}"
    workspace.mkdir(parents=True, exist_ok=True)
    yield workspace

@pytest.fixture
def input_file(temp_workspace: Path) -> Callable[[str], Path]:
    def _create(content: str, filename: Optional[str] = None) -> Path:
        if filename is None:
            filename = f"input_{{uuid.uuid4().hex[:8]}}.txt"
        file_path: Path = temp_workspace / filename
        file_path.write_text(content)
        return file_path
    return _create

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]

@pytest.fixture
def assert_exit_code() -> Callable[[subprocess.CompletedProcess, int], None]:
    def _assert(result: subprocess.CompletedProcess, expected: int) -> None:
        assert result.returncode == expected, f"Expected exit code {{expected}}, got {{result.returncode}}. Stderr: {{result.stderr}}"
    return _assert
```
""",
            "grpc": f"""MANDATORY FILE STRUCTURE FOR gRPC SERVICE:

```python
import pytest
import grpc
import uuid
import time
from typing import Generator, Dict, Any, Optional

GRPC_HOST: str = "{base_url.replace('http://', '').replace('https://', '')}"
{factory_import}

@pytest.fixture
def grpc_channel() -> Generator[grpc.Channel, None, None]:
    channel: grpc.Channel = grpc.insecure_channel(GRPC_HOST)
    yield channel
    channel.close()

@pytest.fixture
def grpc_channel_with_timeout() -> Generator[grpc.Channel, None, None]:
    channel: grpc.Channel = grpc.insecure_channel(GRPC_HOST)
    try:
        grpc.channel_ready_future(channel).result(timeout=10)
    except grpc.FutureTimeoutError:
        pytest.skip("gRPC server not available")
    yield channel
    channel.close()

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]

@pytest.fixture
def call_options() -> grpc.CallOptions:
    return grpc.CallOptions(timeout=30)
```
""",
            "library": f"""MANDATORY FILE STRUCTURE FOR LIBRARY/MODULE:

```python
import pytest
import uuid
import importlib
from typing import Dict, Any, Callable, Optional, Generator
from pathlib import Path

{factory_import}

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]

@pytest.fixture
def sample_data(unique_id: str) -> Dict[str, Any]:
    return {{
        "id": unique_id,
        "name": f"test_{{unique_id}}",
        "value": 42
    }}

@pytest.fixture
def temp_file(tmp_path: Path) -> Callable[[str, str], Path]:
    def _create(content: str, filename: Optional[str] = None) -> Path:
        if filename is None:
            filename = f"temp_{{uuid.uuid4().hex[:8]}}.txt"
        file_path: Path = tmp_path / filename
        file_path.write_text(content)
        return file_path
    return _create

@pytest.fixture
def assert_raises_with_message() -> Callable:
    def _assert(exception_type: type, message_contains: str):
        return pytest.raises(exception_type, match=message_contains)
    return _assert
```
""",
            "graphql": f"""MANDATORY FILE STRUCTURE FOR GraphQL API:

```python
import pytest
import requests
import uuid
from typing import Generator, Dict, Any, Optional, Callable, List

GRAPHQL_URL: str = "{base_url}/graphql"
{factory_import}

@pytest.fixture
def graphql_client() -> Generator[requests.Session, None, None]:
    session: requests.Session = requests.Session()
    session.headers.update({{"Content-Type": "application/json"}})
    yield session
    session.close()

@pytest.fixture
def execute_query(graphql_client: requests.Session) -> Callable[..., Dict[str, Any]]:
    def _execute(query: str, variables: Optional[Dict[str, Any]] = None, operation_name: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {{"query": query}}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name
        response = graphql_client.post(GRAPHQL_URL, json=payload)
        return response.json()
    return _execute

@pytest.fixture
def execute_mutation(execute_query: Callable) -> Callable[..., Dict[str, Any]]:
    def _execute(mutation: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return execute_query(mutation, variables)
    return _execute

@pytest.fixture
def assert_no_errors() -> Callable[[Dict[str, Any]], None]:
    def _assert(response: Dict[str, Any]) -> None:
        assert "errors" not in response or response["errors"] is None, f"GraphQL errors: {{response.get('errors')}}"
    return _assert

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]
```
""",
            "websocket": f"""MANDATORY FILE STRUCTURE FOR WebSocket APPLICATION:

```python
import pytest
import websocket
import json
import uuid
import time
import threading
from typing import Generator, Dict, Any, List, Optional, Callable

WS_URL: str = "{base_url.replace('http', 'ws')}/ws"
{factory_import}

@pytest.fixture
def ws_connection() -> Generator[websocket.WebSocket, None, None]:
    ws: websocket.WebSocket = websocket.create_connection(WS_URL, timeout=10)
    yield ws
    ws.close()

@pytest.fixture
def ws_send_and_receive(ws_connection: websocket.WebSocket) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _send_receive(message: Dict[str, Any], timeout: float = 5.0) -> Dict[str, Any]:
        ws_connection.send(json.dumps(message))
        ws_connection.settimeout(timeout)
        response: str = ws_connection.recv()
        return json.loads(response)
    return _send_receive

@pytest.fixture
def ws_message_collector(ws_connection: websocket.WebSocket) -> Callable[[int, float], List[Dict[str, Any]]]:
    def _collect(count: int, timeout: float = 10.0) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        ws_connection.settimeout(timeout)
        for _ in range(count):
            try:
                response: str = ws_connection.recv()
                messages.append(json.loads(response))
            except websocket.WebSocketTimeoutException:
                break
        return messages
    return _collect

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]
```
""",
            "message_queue": f"""MANDATORY FILE STRUCTURE FOR MESSAGE QUEUE APPLICATION:

```python
import pytest
import uuid
import json
import time
from typing import Generator, Dict, Any, List, Optional, Callable
from datetime import datetime

{factory_import}

@pytest.fixture
def unique_queue_name() -> str:
    return f"test_queue_{{uuid.uuid4().hex[:8]}}"

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]

@pytest.fixture
def message_validator() -> Callable[[Dict[str, Any], List[str]], bool]:
    def _validate(message: Dict[str, Any], required_fields: List[str]) -> bool:
        for field in required_fields:
            if field not in message:
                return False
        return True
    return _validate

@pytest.fixture
def wait_for_message() -> Callable[[Callable, float, float], Optional[Any]]:
    def _wait(check_func: Callable, timeout: float = 10.0, interval: float = 0.5) -> Optional[Any]:
        start_time: float = time.time()
        while time.time() - start_time < timeout:
            result = check_func()
            if result is not None:
                return result
            time.sleep(interval)
        return None
    return _wait

@pytest.fixture
def assert_message_received() -> Callable[[List[Dict], str], None]:
    def _assert(messages: List[Dict], message_id: str) -> None:
        ids = [m.get("message_id") for m in messages]
        assert message_id in ids, f"Message {{message_id}} not found in received messages"
    return _assert
```
""",
            "serverless": f"""MANDATORY FILE STRUCTURE FOR SERVERLESS FUNCTION:

```python
import pytest
import uuid
import json
import time
from typing import Dict, Any, Optional, Callable, Generator
from datetime import datetime

{factory_import}

@pytest.fixture
def lambda_context() -> Any:
    class MockLambdaContext:
        function_name: str = "test_function"
        function_version: str = "$LATEST"
        invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
        memory_limit_in_mb: int = 128
        aws_request_id: str = uuid.uuid4().hex
        log_group_name: str = "/aws/lambda/test_function"
        log_stream_name: str = f"{{datetime.now().strftime('%Y/%m/%d')}}/[$LATEST]{{uuid.uuid4().hex}}"

        def get_remaining_time_in_millis(self) -> int:
            return 30000
    return MockLambdaContext()

@pytest.fixture
def invoke_handler() -> Callable[[Callable, Dict[str, Any], Any], Dict[str, Any]]:
    def _invoke(handler: Callable, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        return handler(event, context)
    return _invoke

@pytest.fixture
def assert_response_status() -> Callable[[Dict[str, Any], int], None]:
    def _assert(response: Dict[str, Any], expected_status: int) -> None:
        actual_status = response.get("statusCode", response.get("status"))
        assert actual_status == expected_status, f"Expected status {{expected_status}}, got {{actual_status}}"
    return _assert

@pytest.fixture
def parse_response_body() -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def _parse(response: Dict[str, Any]) -> Dict[str, Any]:
        body = response.get("body", "{{}}")
        if isinstance(body, str):
            return json.loads(body)
        return body
    return _parse

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]
```
""",
            "batch_script": f"""MANDATORY FILE STRUCTURE FOR BATCH SCRIPT:

```python
import pytest
import subprocess
import uuid
import os
import tempfile
from pathlib import Path
from typing import Generator, Dict, Any, Callable, Optional, List

{factory_import}

@pytest.fixture
def temp_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    workspace: Path = tmp_path / f"batch_{{uuid.uuid4().hex[:8]}}"
    workspace.mkdir(parents=True, exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(workspace)
    yield workspace
    os.chdir(original_cwd)

@pytest.fixture
def create_input_file(temp_workspace: Path) -> Callable[[str, str], Path]:
    def _create(content: str, filename: str) -> Path:
        file_path: Path = temp_workspace / filename
        file_path.write_text(content)
        return file_path
    return _create

@pytest.fixture
def run_script() -> Callable[[str, Optional[Dict[str, str]], Optional[int]], subprocess.CompletedProcess]:
    def _run(script_path: str, env: Optional[Dict[str, str]] = None, timeout: int = 60) -> subprocess.CompletedProcess:
        full_env: Dict[str, str] = os.environ.copy()
        if env:
            full_env.update(env)
        return subprocess.run(
            ["python", script_path] if script_path.endswith(".py") else ["bash", script_path],
            capture_output=True,
            text=True,
            env=full_env,
            timeout=timeout
        )
    return _run

@pytest.fixture
def assert_file_exists(temp_workspace: Path) -> Callable[[str], None]:
    def _assert(filename: str) -> None:
        file_path = temp_workspace / filename
        assert file_path.exists(), f"Expected output file {{filename}} not found"
    return _assert

@pytest.fixture
def read_output_file(temp_workspace: Path) -> Callable[[str], str]:
    def _read(filename: str) -> str:
        file_path = temp_workspace / filename
        return file_path.read_text()
    return _read

@pytest.fixture
def unique_id() -> str:
    return uuid.uuid4().hex[:8]
```
"""
        }

        return templates.get(app_type, templates["rest_api"])

    def _get_classification_prompt_for_app_type(self, app_type: str) -> str:
        prompts: Dict[str, str] = {
            "rest_api": """
TEST_ERROR examples for REST API:
- Wrong endpoint URL (e.g., using "/users" instead of "/api/users")
- Wrong HTTP method (GET instead of POST)
- Wrong request headers or content-type
- Bad assertion on response structure
- Missing authentication headers
- Timing/race condition in tests

ACTUAL_DEFECT examples for REST API:
- Correct endpoint returns wrong data
- Business logic error in response
- Database constraint violation
- Authentication returns wrong status
- Server error (5xx) on valid request""",
            "cli": """
TEST_ERROR examples for CLI:
- Wrong command path or executable name
- Wrong argument format or flags
- Incorrect expected exit code
- File path issues (not found, wrong permissions)
- Wrong stdin input format
- Timeout too short for operation

ACTUAL_DEFECT examples for CLI:
- Command produces wrong output
- Command crashes unexpectedly
- Wrong exit code for valid input
- Output file has wrong content
- Environment variables not processed correctly""",
            "library": """
TEST_ERROR examples for Library:
- Wrong import path or module name
- Wrong function/method name
- Wrong parameter types or order
- Incorrect expected exception
- Bad assertion on return value
- Missing test setup/teardown

ACTUAL_DEFECT examples for Library:
- Function returns wrong value
- Unexpected exception raised
- State mutation issues
- Memory leaks or resource issues
- Thread safety problems""",
            "graphql": """
TEST_ERROR examples for GraphQL:
- Wrong query/mutation syntax
- Non-existent field names
- Wrong variable types
- Missing required variables
- Wrong operation name

ACTUAL_DEFECT examples for GraphQL:
- Resolver returns wrong data
- Authorization logic fails
- N+1 query issues
- Subscription doesn't trigger
- Data mutation not persisted""",
            "grpc": """
TEST_ERROR examples for gRPC:
- Wrong service/method name
- Wrong message format
- Channel connection issues
- Timeout too short
- Wrong metadata format

ACTUAL_DEFECT examples for gRPC:
- Service returns wrong response
- Wrong status code returned
- Streaming breaks unexpectedly
- Server-side error handling issue
- Deadline exceeded on server""",
            "websocket": """
TEST_ERROR examples for WebSocket:
- Wrong WebSocket URL
- Wrong message format
- Connection timeout too short
- Missing handshake headers
- Not waiting for response

ACTUAL_DEFECT examples for WebSocket:
- Server sends wrong message
- Connection drops unexpectedly
- Events not triggered correctly
- Message ordering issues
- Authentication handshake fails""",
            "message_queue": """
TEST_ERROR examples for Message Queue:
- Wrong queue/topic name
- Wrong message format
- Consumer timeout too short
- Connection string issues
- Missing acknowledgment

ACTUAL_DEFECT examples for Message Queue:
- Message not delivered
- Message processed incorrectly
- Dead letter not triggered
- Ordering guarantee violated
- Duplicate message handling fails""",
            "serverless": """
TEST_ERROR examples for Serverless:
- Wrong handler function name
- Wrong event structure
- Missing context mock
- Wrong environment variables in test
- Response format mismatch

ACTUAL_DEFECT examples for Serverless:
- Handler logic error
- Timeout exceeded
- Memory limit exceeded
- Wrong response status code
- Cold start issues""",
            "batch_script": """
TEST_ERROR examples for Batch Script:
- Wrong script path
- Wrong input file format
- Missing environment variables
- Working directory issues
- Timeout too short

ACTUAL_DEFECT examples for Batch Script:
- Script produces wrong output
- Script crashes on valid input
- Output file not created
- Data transformation error
- Exit code handling bug"""
        }
        return prompts.get(app_type, prompts["library"])

    def classify_failure(
        self,
        test_code: str,
        failure_info: Dict[str, Any],
        app_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        logger.debug(f"Classifying failure for: {failure_info.get('nodeid', 'unknown')}")

        if app_metadata is None:
            app_metadata = {}

        app_type = app_metadata.get("app_type", "rest_api")
        error_message = failure_info.get('call', {}).get('longrepr', 'N/A')

        from utils.app_types import pre_classify_failure
        quick_classification = pre_classify_failure(str(error_message), app_type)
        if quick_classification == "CONNECTION_ERROR":
            return {
                "classification": "TEST_ERROR",
                "reason": "Connection error - server may not be running or URL is wrong",
                "confidence": "high"
            }

        type_specific_prompt = self._get_classification_prompt_for_app_type(app_type)

        prompt: str = f"""Analyze this {app_type.upper()} test failure and classify it:

Test Code:
{test_code}

Failure Information:
- Test Name: {failure_info.get('nodeid', 'N/A')}
- Error Message: {error_message}
- Exception Type: {failure_info.get('call', {}).get('crash', {}).get('message', 'N/A')}

Determine if this is:
1. TEST_ERROR - Issue in the test code itself
2. ACTUAL_DEFECT - Legitimate bug in the application

{type_specific_prompt}

Respond in JSON format:
{{
    "classification": "TEST_ERROR" or "ACTUAL_DEFECT",
    "reason": "Brief explanation",
    "confidence": "high/medium/low"
}}"""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": f"You are an expert QA engineer specializing in {app_type} application test failure analysis. Classify failures accurately."},
            {"role": "user", "content": prompt}
        ]

        content: str = self._call_api(
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

    def heal_test(
        self,
        test_code: str,
        failure_info: Dict[str, Any],
        app_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        logger.info(f"Healing test: {failure_info.get('nodeid', 'unknown')}")

        if app_metadata is None:
            app_metadata = {}

        app_type, base_url, port = self._get_connection_info(app_metadata)

        app_context: str = self._get_healing_context_for_app_type(app_type, f"{base_url}:{port}")

        prompt: str = f"""Fix this failing test for a {app_type.upper()} application.

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
- Use type hints for all functions
- Return ONLY the fixed Python code, no explanations

Generate the fixed test code:"""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": f"You are an expert test automation engineer specializing in {app_type} applications. Fix failing tests while maintaining their purpose. Generate clean code with NO comments and NO docstrings."},
            {"role": "user", "content": prompt}
        ]

        result: str = self._call_api(
            messages,
            0.5,
            config.MAX_TOKENS_HEALING
        )

        logger.debug("Test healing complete")
        return result

    def _get_healing_context_for_app_type(self, app_type: str, base_url: str) -> str:
        contexts: Dict[str, str] = {
            "rest_api": f"""APPLICATION CONTEXT:
- This is a REST API test using requests library
- BASE_URL should be: {base_url}
- Use api_client fixture for HTTP requests
- Use api_base_url fixture for the base URL
- Response parsing should handle both flat and nested JSON structures""",
            "graphql": f"""APPLICATION CONTEXT:
- This is a GraphQL API test
- GRAPHQL_URL should be: {base_url}/graphql
- Use graphql_client fixture for requests
- Use execute_query fixture for GraphQL queries
- Use assert_no_errors fixture to check for GraphQL errors""",
            "cli": """APPLICATION CONTEXT:
- This is a CLI application test using subprocess
- Use cli_runner fixture to execute commands
- Use temp_workspace fixture for isolated file operations
- Use input_file fixture to create input files
- Use assert_exit_code fixture to verify exit codes
- Check both stdout and stderr for output validation""",
            "grpc": f"""APPLICATION CONTEXT:
- This is a gRPC service test
- GRPC_HOST should be: {base_url.replace('http://', '').replace('https://', '')}
- Use grpc_channel fixture for connections
- Use grpc_channel_with_timeout for tests requiring connection verification
- Handle grpc.FutureTimeoutError when server unavailable""",
            "websocket": f"""APPLICATION CONTEXT:
- This is a WebSocket application test
- WS_URL should be: {base_url.replace('http', 'ws')}/ws
- Use ws_connection fixture for WebSocket connections
- Use ws_send_and_receive fixture for request-response pattern
- Use ws_message_collector for collecting multiple messages
- Handle WebSocketTimeoutException for timeout scenarios""",
            "library": """APPLICATION CONTEXT:
- This is a library/module test
- Import and test functions/classes directly
- Use sample_data and unique_id fixtures for test data
- Use temp_file fixture for file-based tests
- Use assert_raises_with_message for exception testing""",
            "message_queue": """APPLICATION CONTEXT:
- This is a message queue test
- Use unique_queue_name fixture for isolated test queues
- Use message_validator fixture to check message format
- Use wait_for_message fixture for async message consumption
- Use assert_message_received to verify message delivery
- Clean up queues after tests""",
            "serverless": """APPLICATION CONTEXT:
- This is a serverless function test
- Use lambda_context fixture for mock AWS Lambda context
- Use invoke_handler fixture to call handlers
- Use assert_response_status to check response codes
- Use parse_response_body for extracting response data
- Test different event source formats (API Gateway, S3, SQS)""",
            "batch_script": """APPLICATION CONTEXT:
- This is a batch script test
- Use temp_workspace fixture for isolated execution directory
- Use create_input_file fixture to prepare input files
- Use run_script fixture to execute scripts
- Use assert_file_exists to verify output files
- Use read_output_file to check output content
- Test both success and error scenarios with different exit codes"""
        }
        return contexts.get(app_type, contexts["library"])

    def fix_collection_error(
        self,
        test_file: str,
        test_code: str,
        error_message: str,
        app_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        logger.info(f"Fixing collection error in: {test_file}")

        if app_metadata is None:
            app_metadata = {}

        app_type, base_url, port = self._get_connection_info(app_metadata)

        app_context: str = self._get_healing_context_for_app_type(app_type, f"{base_url}:{port}")

        prompt: str = f"""Fix this pytest collection error for a {app_type.upper()} application.

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

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": f"You are an expert test automation engineer specializing in {app_type} applications. Fix pytest collection errors using proper testing patterns. Generate code with NO comments and NO docstrings."},
            {"role": "user", "content": prompt}
        ]

        content: str = self._call_api(
            messages,
            0.3,
            config.MAX_TOKENS_HEALING
        )

        content = strip_markdown_fences(content)

        logger.debug("Collection error fix complete")
        return content

    def analyze_bug(self, defect_info: Dict[str, Any]) -> str:
        logger.info(f"Analyzing bug: {defect_info.get('test_name', 'unknown')}")

        prompt: str = f"""Analyze this potential application bug and provide detailed investigation guidance:

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

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are an expert software debugger and QA engineer. Analyze bugs thoroughly and provide actionable investigation guidance."},
            {"role": "user", "content": prompt}
        ]

        result: str = self._call_api(
            messages,
            0.3,
            config.MAX_TOKENS_BUG_ANALYSIS
        )

        logger.debug("Bug analysis complete")
        return result

    def validate_tests(
        self,
        test_files: Dict[str, str],
        app_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        logger.info("Validating generated tests with AI reviewer...")

        if app_metadata is None:
            app_metadata = {}

        app_type, base_url, port = self._get_connection_info(app_metadata)

        logger.info(f"Validating for app_type={app_type}, port={port}")

        serialized_tests: str = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )

        prompt: str = f"""You are auditing generated pytest test files. Focus ONLY on issues that will cause test FAILURES.

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

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": f"You are an expert pytest reviewer for {app_type} applications. Check for syntax and import issues. Return ONLY valid JSON, no markdown."},
            {"role": "user", "content": prompt}
        ]

        try:
            response: str = self._call_api(
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
        except Exception as exc:
            logger.warning("AI test validation failed: %s", exc)
            return {"status": "error", "issues": [{"type": "exception", "detail": str(exc)}]}

    def heal_tests(
        self,
        test_files: Dict[str, str],
        issues: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        logger.info("Healing generated tests via AI...")

        healed_result: Dict[str, str] = self._heal_tests_batch(test_files, issues)

        if healed_result:
            return healed_result

        logger.info("Batch healing failed, trying individual file healing...")
        return self._heal_tests_individually(test_files, issues)

    def _heal_tests_batch(
        self,
        test_files: Dict[str, str],
        issues: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        serialized_tests: str = "\n\n".join(
            f"### {path}\n```python\n{code}\n```" for path, code in test_files.items()
        )
        issues_text: str = json.dumps(issues, indent=2)

        prompt: str = f"""You must FIX the generated pytest test files below.

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

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are an expert pytest engineer. Fix the provided self-contained tests to resolve validation issues. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            response: str = self._call_api(
                messages,
                0.5,
                config.MAX_TOKENS_BATCH_HEALING
            )

            response = self._extract_json(response)

            healed: Dict[str, Any] = json.loads(response)
            if not isinstance(healed, dict):
                raise ValueError("Expected JSON object mapping file paths to code")
            return {path: code.strip() for path, code in healed.items() if isinstance(code, str)}
        except json.JSONDecodeError as e:
            logger.warning("Batch healing returned invalid JSON: %s", e)
            return {}
        except Exception as exc:
            logger.warning("AI batch test healing failed: %s", exc)
            return {}

    def _heal_tests_individually(
        self,
        test_files: Dict[str, str],
        issues: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        healed_files: Dict[str, str] = {}

        for filepath, code in test_files.items():
            file_issues: List[Dict[str, Any]] = [i for i in issues if filepath in i.get("detail", "")]
            if not file_issues:
                continue

            logger.info(f"Healing individual file: {filepath}")

            prompt: str = f"""Fix this pytest test file.

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

            messages: List[Dict[str, str]] = [
                {"role": "system", "content": "You are an expert pytest engineer. Fix the self-contained test file. Return ONLY Python code."},
                {"role": "user", "content": prompt}
            ]

            try:
                response: str = self._call_api(
                    messages,
                    0.5,
                    config.MAX_TOKENS_HEALING
                )

                response = strip_markdown_fences(response)
                healed_files[filepath] = response
            except Exception as exc:
                logger.warning(f"Failed to heal {filepath}: {exc}")

        return healed_files

    def summarize_report(
        self,
        report_data: Dict[str, Any],
        healing_analysis: Dict[str, Any]
    ) -> str:
        logger.info("Generating test execution summary...")

        prompt: str = f"""Generate a comprehensive test execution summary:

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

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are an expert QA reporting specialist. Create clear, actionable test reports with emphasis on iterative healing results and bug identification."},
            {"role": "user", "content": prompt}
        ]

        result: str = self._call_api(
            messages,
            0.4,
            config.MAX_TOKENS_SUMMARY
        )

        logger.info("Summary generation complete")
        return result

    def deduplicate_scenarios(
        self,
        scenarios: List[str],
        threshold: float = 0.8
    ) -> List[str]:
        if len(scenarios) <= 1:
            return scenarios

        logger.info(f"Deduplicating {len(scenarios)} scenarios...")

        scenarios_text: str = "\n".join([f"{i+1}. {s}" for i, s in enumerate(scenarios)])

        prompt: str = f"""Analyze these test scenarios and remove duplicates or very similar ones.

Scenarios:
{scenarios_text}

Rules:
1. Remove scenarios that test essentially the same thing
2. Keep the more comprehensive/specific version when duplicates exist
3. Similarity threshold: {threshold * 100}% - if two scenarios are more than {threshold * 100}% similar, keep only one
4. Return ONLY a JSON array of the unique scenario texts (not numbers)

Example output:
["Verify user login with valid credentials", "Test error handling for invalid email"]

Return ONLY the JSON array, no explanations."""

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": "You are a test planning expert. Identify and remove duplicate test scenarios. Return ONLY valid JSON array."},
            {"role": "user", "content": prompt}
        ]

        try:
            response: str = self._call_api(messages, 0.3, 2000)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            unique_scenarios: List[str] = json.loads(response)
            logger.info(f"Deduplicated to {len(unique_scenarios)} unique scenarios")
            return unique_scenarios
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Deduplication failed: {e}, returning original scenarios")
            return scenarios
