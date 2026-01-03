from typing import Dict, List, Any
from dataclasses import dataclass, field

@dataclass
class AppTypeConfig:
    categories: List[str]
    analysis_sections: List[str]
    failure_patterns: Dict[str, str]
    healing_hints: List[str]

APP_TYPE_CONFIGS: Dict[str, AppTypeConfig] = {
    "rest_api": AppTypeConfig(
        categories=["functional", "security", "validation", "performance", "integration"],
        analysis_sections=[
            "API Endpoints (Method, Path, Description)",
            "Authentication/Authorization",
            "Request/Response Schemas",
            "Error Response Format",
            "Rate Limiting",
        ],
        failure_patterns={
            r"ConnectionRefusedError": "CONNECTION_ERROR",
            r"404.*Not Found": "TEST_ERROR",
            r"401.*Unauthorized": "AUTH_ERROR",
            r"403.*Forbidden": "AUTH_ERROR",
            r"500.*Internal Server Error": "ACTUAL_DEFECT",
            r"Wrong endpoint URL": "TEST_ERROR",
            r"Wrong HTTP method": "TEST_ERROR",
        },
        healing_hints=[
            "Check endpoint URL matches API documentation",
            "Verify HTTP method (GET/POST/PUT/DELETE)",
            "Check request headers and content-type",
            "Verify authentication token/credentials",
            "Check response structure assumptions",
        ],
    ),
    "cli": AppTypeConfig(
        categories=["argument_parsing", "stdin_processing", "file_operations", "exit_codes", "error_handling"],
        analysis_sections=[
            "Commands and Subcommands",
            "Command-Line Arguments and Flags",
            "Input/Output Handling (stdin, files)",
            "Exit Codes and Error Messages",
            "Environment Variables",
        ],
        failure_patterns={
            r"FileNotFoundError": "TEST_ERROR",
            r"PermissionError": "TEST_ERROR",
            r"exit code.*expected.*got": "POSSIBLE_DEFECT",
            r"No such file or directory": "TEST_ERROR",
            r"command not found": "TEST_ERROR",
            r"subprocess\.TimeoutExpired": "TEST_ERROR",
        },
        healing_hints=[
            "Check executable path is correct",
            "Verify command-line arguments format",
            "Check working directory exists",
            "Verify file paths are absolute or relative correctly",
            "Check stdin input format",
        ],
    ),
    "library": AppTypeConfig(
        categories=["unit", "edge_cases", "exceptions", "type_validation", "integration"],
        analysis_sections=[
            "Public API (exported functions/classes)",
            "Function Signatures and Return Types",
            "Exceptions Raised",
            "Usage Examples",
            "Dependencies",
        ],
        failure_patterns={
            r"ImportError": "TEST_ERROR",
            r"ModuleNotFoundError": "TEST_ERROR",
            r"AttributeError": "POSSIBLE_DEFECT",
            r"TypeError": "POSSIBLE_DEFECT",
            r"ValueError": "POSSIBLE_DEFECT",
            r"AssertionError": "ASSERTION_FAILURE",
        },
        healing_hints=[
            "Check import path is correct",
            "Verify function/class names match API",
            "Check parameter types and order",
            "Verify expected exceptions are raised",
            "Check return value type and structure",
        ],
    ),
    "graphql": AppTypeConfig(
        categories=["queries", "mutations", "subscriptions", "errors", "authorization", "validation"],
        analysis_sections=[
            "Schema Overview",
            "Queries Available",
            "Mutations Available",
            "Subscriptions (if any)",
            "Custom Scalars and Types",
            "Authorization Rules",
        ],
        failure_patterns={
            r"GraphQL error": "POSSIBLE_DEFECT",
            r"Cannot query field": "TEST_ERROR",
            r"Unknown argument": "TEST_ERROR",
            r"Variable.*not provided": "TEST_ERROR",
            r"Not authorized": "AUTH_ERROR",
        },
        healing_hints=[
            "Check query/mutation syntax",
            "Verify field names exist in schema",
            "Check variable types match schema",
            "Verify required variables are provided",
            "Check authorization headers",
        ],
    ),
    "grpc": AppTypeConfig(
        categories=["unary_calls", "streaming", "error_codes", "deadlines", "metadata"],
        analysis_sections=[
            "Services and Methods",
            "Message Types (Request/Response)",
            "Streaming Patterns (unary, server, client, bidirectional)",
            "Error Handling",
            "Metadata and Headers",
        ],
        failure_patterns={
            r"StatusCode\.UNAVAILABLE": "CONNECTION_ERROR",
            r"StatusCode\.NOT_FOUND": "TEST_ERROR",
            r"StatusCode\.INVALID_ARGUMENT": "TEST_ERROR",
            r"StatusCode\.INTERNAL": "ACTUAL_DEFECT",
            r"StatusCode\.UNIMPLEMENTED": "TEST_ERROR",
            r"grpc\.FutureTimeoutError": "TEST_ERROR",
        },
        healing_hints=[
            "Check service and method names",
            "Verify message format matches proto definition",
            "Check channel connection settings",
            "Verify timeout values are appropriate",
            "Check metadata/headers format",
        ],
    ),
    "websocket": AppTypeConfig(
        categories=["connection", "messaging", "events", "reconnection", "errors"],
        analysis_sections=[
            "Connection Endpoint",
            "Message Types and Formats",
            "Events (client and server)",
            "Authentication Handshake",
            "Heartbeat/Ping-Pong",
        ],
        failure_patterns={
            r"WebSocketConnectionClosedException": "CONNECTION_ERROR",
            r"WebSocketTimeoutException": "TEST_ERROR",
            r"Connection refused": "CONNECTION_ERROR",
            r"Handshake failed": "AUTH_ERROR",
            r"Invalid frame": "TEST_ERROR",
        },
        healing_hints=[
            "Check WebSocket URL format (ws:// or wss://)",
            "Verify message JSON structure",
            "Check connection timeout values",
            "Verify authentication in handshake",
            "Check event handlers are set up",
        ],
    ),
    "message_queue": AppTypeConfig(
        categories=["publishing", "consuming", "message_format", "dead_letter", "ordering", "acknowledgment"],
        analysis_sections=[
            "Queues/Topics",
            "Message Schemas",
            "Producers and Consumers",
            "Dead Letter Handling",
            "Ordering Guarantees",
            "Acknowledgment Mode",
        ],
        failure_patterns={
            r"ConnectionError": "CONNECTION_ERROR",
            r"QueueNotFound": "TEST_ERROR",
            r"MessageFormatError": "TEST_ERROR",
            r"ConsumerTimeout": "TEST_ERROR",
            r"AcknowledgmentFailed": "POSSIBLE_DEFECT",
        },
        healing_hints=[
            "Check broker connection settings",
            "Verify queue/topic names exist",
            "Check message format matches schema",
            "Verify consumer timeout is sufficient",
            "Check acknowledgment mode",
        ],
    ),
    "serverless": AppTypeConfig(
        categories=["handler_invocation", "event_parsing", "cold_start", "timeout_handling", "error_responses"],
        analysis_sections=[
            "Functions and Handlers",
            "Event Sources (API Gateway, S3, SQS, etc.)",
            "Environment Variables",
            "Timeout and Memory Settings",
            "Error Response Format",
        ],
        failure_patterns={
            r"Handler.*not found": "TEST_ERROR",
            r"Timeout": "POSSIBLE_DEFECT",
            r"Out of memory": "POSSIBLE_DEFECT",
            r"Event parsing error": "TEST_ERROR",
            r"Permission denied": "AUTH_ERROR",
        },
        healing_hints=[
            "Check handler function name and path",
            "Verify event structure matches expected format",
            "Check context mock is correct",
            "Verify environment variables are set",
            "Check response format for the trigger type",
        ],
    ),
    "batch_script": AppTypeConfig(
        categories=["execution", "input_files", "output_files", "error_handling", "environment"],
        analysis_sections=[
            "Script Entry Point",
            "Input File Requirements",
            "Output File Locations",
            "Exit Codes",
            "Environment Dependencies",
        ],
        failure_patterns={
            r"FileNotFoundError": "TEST_ERROR",
            r"PermissionError": "TEST_ERROR",
            r"Script failed": "POSSIBLE_DEFECT",
            r"Output file not created": "POSSIBLE_DEFECT",
            r"subprocess\.CalledProcessError": "POSSIBLE_DEFECT",
        },
        healing_hints=[
            "Check script path is correct",
            "Verify input files exist and have correct format",
            "Check working directory is set",
            "Verify environment variables are configured",
            "Check output directory exists and is writable",
        ],
    ),
}

def get_categories_for_app_type(app_type: str) -> List[str]:
    config = APP_TYPE_CONFIGS.get(app_type)
    if config:
        return config.categories
    return APP_TYPE_CONFIGS["library"].categories

def get_analysis_sections_for_app_type(app_type: str) -> List[str]:
    config = APP_TYPE_CONFIGS.get(app_type)
    if config:
        return config.analysis_sections
    return APP_TYPE_CONFIGS["library"].analysis_sections

def get_failure_patterns_for_app_type(app_type: str) -> Dict[str, str]:
    config = APP_TYPE_CONFIGS.get(app_type)
    if config:
        return config.failure_patterns
    return APP_TYPE_CONFIGS["library"].failure_patterns

def get_healing_hints_for_app_type(app_type: str) -> List[str]:
    config = APP_TYPE_CONFIGS.get(app_type)
    if config:
        return config.healing_hints
    return APP_TYPE_CONFIGS["library"].healing_hints

def get_all_app_types() -> List[str]:
    return list(APP_TYPE_CONFIGS.keys())

def pre_classify_failure(error_message: str, app_type: str) -> str | None:
    import re
    patterns = get_failure_patterns_for_app_type(app_type)
    for pattern, classification in patterns.items():
        if re.search(pattern, error_message, re.IGNORECASE):
            return classification
    return None
