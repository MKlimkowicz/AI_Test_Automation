from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum
import json
from pathlib import Path

class AppType(Enum):
    REST_API = "rest_api"
    GRAPHQL = "graphql"
    GRPC = "grpc"
    WEBSOCKET = "websocket"
    CLI = "cli"
    LIBRARY = "library"
    MESSAGE_QUEUE = "message_queue"
    SERVERLESS = "serverless"
    BATCH_SCRIPT = "batch_script"

@dataclass
class HttpConnectionInfo:
    base_url: str = "http://localhost"
    port: int = 8080
    protocol: str = "http"
    auth_endpoint: Optional[str] = None
    health_endpoint: Optional[str] = None

@dataclass
class GrpcConnectionInfo:
    host: str = "localhost"
    port: int = 50051
    use_tls: bool = False
    proto_files: List[str] = field(default_factory=list)
    service_names: List[str] = field(default_factory=list)

@dataclass
class WebSocketConnectionInfo:
    ws_url: str = "ws://localhost"
    port: int = 8080
    protocol: str = "ws"
    message_format: str = "json"

@dataclass
class CliConnectionInfo:
    executable_path: str = "./app"
    working_directory: Optional[str] = None
    requires_build: bool = False
    build_command: Optional[str] = None

@dataclass
class MessageQueueConnectionInfo:
    broker_type: str = "rabbitmq"
    broker_url: str = "amqp://localhost"
    queue_names: List[str] = field(default_factory=list)
    topic_names: List[str] = field(default_factory=list)

@dataclass
class LibraryConnectionInfo:
    import_path: str = ""
    exportable_functions: List[str] = field(default_factory=list)
    exportable_classes: List[str] = field(default_factory=list)

@dataclass
class AppConstraints:
    requires_auth: bool = False
    auth_type: Optional[str] = None
    test_credentials: Optional[Dict[str, str]] = None
    rate_limits: Optional[Dict[str, Any]] = None
    required_env_vars: List[str] = field(default_factory=list)
    startup_time_seconds: int = 0
    requires_external_services: List[str] = field(default_factory=list)

@dataclass
class DatabaseInfo:
    type: Optional[str] = None
    connection_string: Optional[str] = None
    requires_cleanup: bool = False
    seed_data_available: bool = False
    migration_command: Optional[str] = None

@dataclass
class RestApiDetails:
    endpoints: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class GraphQLDetails:
    schema_path: Optional[str] = None
    queries: List[str] = field(default_factory=list)
    mutations: List[str] = field(default_factory=list)
    subscriptions: List[str] = field(default_factory=list)

@dataclass
class CliDetails:
    commands: List[Dict[str, Any]] = field(default_factory=list)
    supports_stdin: bool = False
    produces_output_files: bool = False

@dataclass
class LibraryDetails:
    functions: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class MessageQueueDetails:
    producers: List[str] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)
    message_schemas: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GrpcDetails:
    services: List[Dict[str, Any]] = field(default_factory=list)
    methods: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class WebSocketDetails:
    events: List[Dict[str, Any]] = field(default_factory=list)
    message_types: List[str] = field(default_factory=list)

@dataclass
class ServerlessDetails:
    functions: List[Dict[str, Any]] = field(default_factory=list)
    triggers: List[Dict[str, Any]] = field(default_factory=list)
    provider: Optional[str] = None

@dataclass
class AppMetadata:
    app_type: str = "rest_api"
    framework: str = "unknown"
    languages: List[str] = field(default_factory=list)
    constraints: AppConstraints = field(default_factory=AppConstraints)
    database: Optional[DatabaseInfo] = None

    http_connection: Optional[HttpConnectionInfo] = None
    grpc_connection: Optional[GrpcConnectionInfo] = None
    websocket_connection: Optional[WebSocketConnectionInfo] = None
    cli_connection: Optional[CliConnectionInfo] = None
    mq_connection: Optional[MessageQueueConnectionInfo] = None
    library_connection: Optional[LibraryConnectionInfo] = None

    rest_api_details: Optional[RestApiDetails] = None
    graphql_details: Optional[GraphQLDetails] = None
    cli_details: Optional[CliDetails] = None
    library_details: Optional[LibraryDetails] = None
    mq_details: Optional[MessageQueueDetails] = None
    grpc_details: Optional[GrpcDetails] = None
    websocket_details: Optional[WebSocketDetails] = None
    serverless_details: Optional[ServerlessDetails] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in asdict(self).items():
            if value is not None:
                result[key] = value
        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppMetadata":
        constraints_data: Dict[str, Any] = data.pop("constraints", {})
        constraints: AppConstraints = AppConstraints(**constraints_data) if constraints_data else AppConstraints()

        database_data: Optional[Dict[str, Any]] = data.pop("database", None)
        database: Optional[DatabaseInfo] = DatabaseInfo(**database_data) if database_data else None

        http_data: Optional[Dict[str, Any]] = data.pop("http_connection", None)
        http_connection: Optional[HttpConnectionInfo] = HttpConnectionInfo(**http_data) if http_data else None

        grpc_conn_data: Optional[Dict[str, Any]] = data.pop("grpc_connection", None)
        grpc_connection: Optional[GrpcConnectionInfo] = GrpcConnectionInfo(**grpc_conn_data) if grpc_conn_data else None

        ws_data: Optional[Dict[str, Any]] = data.pop("websocket_connection", None)
        websocket_connection: Optional[WebSocketConnectionInfo] = WebSocketConnectionInfo(**ws_data) if ws_data else None

        cli_conn_data: Optional[Dict[str, Any]] = data.pop("cli_connection", None)
        cli_connection: Optional[CliConnectionInfo] = CliConnectionInfo(**cli_conn_data) if cli_conn_data else None

        mq_conn_data: Optional[Dict[str, Any]] = data.pop("mq_connection", None)
        mq_connection: Optional[MessageQueueConnectionInfo] = MessageQueueConnectionInfo(**mq_conn_data) if mq_conn_data else None

        lib_conn_data: Optional[Dict[str, Any]] = data.pop("library_connection", None)
        library_connection: Optional[LibraryConnectionInfo] = LibraryConnectionInfo(**lib_conn_data) if lib_conn_data else None

        rest_data: Optional[Dict[str, Any]] = data.pop("rest_api_details", None)
        rest_api_details: Optional[RestApiDetails] = RestApiDetails(**rest_data) if rest_data else None

        graphql_data: Optional[Dict[str, Any]] = data.pop("graphql_details", None)
        graphql_details: Optional[GraphQLDetails] = GraphQLDetails(**graphql_data) if graphql_data else None

        cli_details_data: Optional[Dict[str, Any]] = data.pop("cli_details", None)
        cli_details: Optional[CliDetails] = CliDetails(**cli_details_data) if cli_details_data else None

        library_data: Optional[Dict[str, Any]] = data.pop("library_details", None)
        library_details: Optional[LibraryDetails] = LibraryDetails(**library_data) if library_data else None

        mq_details_data: Optional[Dict[str, Any]] = data.pop("mq_details", None)
        mq_details: Optional[MessageQueueDetails] = MessageQueueDetails(**mq_details_data) if mq_details_data else None

        grpc_details_data: Optional[Dict[str, Any]] = data.pop("grpc_details", None)
        grpc_details: Optional[GrpcDetails] = GrpcDetails(**grpc_details_data) if grpc_details_data else None

        ws_details_data: Optional[Dict[str, Any]] = data.pop("websocket_details", None)
        websocket_details: Optional[WebSocketDetails] = WebSocketDetails(**ws_details_data) if ws_details_data else None

        serverless_data: Optional[Dict[str, Any]] = data.pop("serverless_details", None)
        serverless_details: Optional[ServerlessDetails] = ServerlessDetails(**serverless_data) if serverless_data else None

        return cls(
            app_type=data.get("app_type", "rest_api"),
            framework=data.get("framework", "unknown"),
            languages=data.get("languages", []),
            constraints=constraints,
            database=database,
            http_connection=http_connection,
            grpc_connection=grpc_connection,
            websocket_connection=websocket_connection,
            cli_connection=cli_connection,
            mq_connection=mq_connection,
            library_connection=library_connection,
            rest_api_details=rest_api_details,
            graphql_details=graphql_details,
            cli_details=cli_details,
            library_details=library_details,
            mq_details=mq_details,
            grpc_details=grpc_details,
            websocket_details=websocket_details,
            serverless_details=serverless_details,
        )

    @classmethod
    def load(cls, path: Path) -> "AppMetadata":
        with open(path, "r") as f:
            data: Dict[str, Any] = json.load(f)
        return cls.from_dict(data)

def get_json_schema() -> str:
    return '''{
  "app_type": "rest_api | graphql | grpc | websocket | cli | library | message_queue | serverless | batch_script",
  "framework": "string (e.g., Flask, FastAPI, Express, Spring, Actix, etc.)",
  "languages": ["string"],
  "constraints": {
    "requires_auth": "boolean",
    "auth_type": "bearer | basic | api_key | oauth | none | null",
    "test_credentials": {"username": "string", "password": "string"} | null,
    "rate_limits": {"requests_per_minute": "number"} | null,
    "required_env_vars": ["string"],
    "startup_time_seconds": "number",
    "requires_external_services": ["string"]
  },
  "database": {
    "type": "postgres | mysql | sqlite | mongo | redis | in-memory | none | null",
    "connection_string": "string | null",
    "requires_cleanup": "boolean",
    "seed_data_available": "boolean",
    "migration_command": "string | null"
  } | null,

  "http_connection": {
    "base_url": "string (e.g., http://localhost)",
    "port": "number",
    "protocol": "http | https",
    "auth_endpoint": "string | null",
    "health_endpoint": "string | null"
  } | null,

  "grpc_connection": {
    "host": "string",
    "port": "number",
    "use_tls": "boolean",
    "proto_files": ["string"],
    "service_names": ["string"]
  } | null,

  "websocket_connection": {
    "ws_url": "string",
    "port": "number",
    "protocol": "ws | wss",
    "message_format": "json | binary | text"
  } | null,

  "cli_connection": {
    "executable_path": "string",
    "working_directory": "string | null",
    "requires_build": "boolean",
    "build_command": "string | null"
  } | null,

  "mq_connection": {
    "broker_type": "rabbitmq | kafka | redis",
    "broker_url": "string",
    "queue_names": ["string"],
    "topic_names": ["string"]
  } | null,

  "library_connection": {
    "import_path": "string",
    "exportable_functions": ["string"],
    "exportable_classes": ["string"]
  } | null,

  "rest_api_details": {
    "endpoints": [
      {
        "method": "GET | POST | PUT | DELETE | PATCH",
        "path": "string",
        "auth_required": "boolean",
        "request_body": {} | null,
        "response_schema": {} | null
      }
    ]
  } | null,

  "graphql_details": {
    "schema_path": "string | null",
    "queries": ["string"],
    "mutations": ["string"],
    "subscriptions": ["string"]
  } | null,

  "cli_details": {
    "commands": [
      {
        "name": "string",
        "args": ["string"],
        "flags": ["string"],
        "description": "string",
        "expected_exit_code": "number"
      }
    ],
    "supports_stdin": "boolean",
    "produces_output_files": "boolean"
  } | null,

  "library_details": {
    "functions": [
      {
        "name": "string",
        "params": ["string"],
        "return_type": "string",
        "is_async": "boolean"
      }
    ],
    "classes": [
      {
        "name": "string",
        "methods": ["string"],
        "constructor_params": ["string"]
      }
    ]
  } | null,

  "mq_details": {
    "producers": ["string"],
    "consumers": ["string"],
    "message_schemas": {}
  } | null,

  "grpc_details": {
    "services": [{"name": "string", "methods": ["string"]}],
    "methods": [{"name": "string", "request_type": "string", "response_type": "string"}]
  } | null,

  "websocket_details": {
    "events": [{"name": "string", "payload_schema": {}}],
    "message_types": ["string"]
  } | null,

  "serverless_details": {
    "functions": [{"name": "string", "handler": "string", "runtime": "string"}],
    "triggers": [{"type": "http | schedule | queue | event", "config": {}}],
    "provider": "aws | azure | gcp | vercel | null"
  } | null
}'''

def load_app_metadata(project_root: Path) -> Dict[str, Any]:
    from utils.logger import get_logger
    logger = get_logger(__name__)

    metadata_path = project_root / "reports" / "app_metadata.json"

    if metadata_path.exists():
        try:
            app_metadata = AppMetadata.load(metadata_path)
            return app_metadata.to_dict()
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse app_metadata.json: {e}")
        except Exception as e:
            logger.warning(f"Failed to load app_metadata.json: {e}")

    return get_default_app_metadata()

def get_default_app_metadata() -> Dict[str, Any]:
    return {
        "app_type": "rest_api",
        "framework": "unknown",
        "languages": [],
        "base_url": "http://localhost",
        "port": 8080,
        "auth_required": False,
        "http_connection": {
            "base_url": "http://localhost",
            "port": 8080,
            "protocol": "http"
        }
    }
