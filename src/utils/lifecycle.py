import subprocess
import time
import importlib
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SetupResult:
    success: bool
    message: str
    process: Optional[subprocess.Popen] = None
    cleanup_func: Optional[Callable] = None

class AppLifecycleManager:

    def __init__(self, app_metadata: Dict[str, Any], project_root: Optional[Path] = None):
        self.app_metadata = app_metadata
        self.app_type = app_metadata.get("app_type", "rest_api")
        self.project_root = project_root or Path.cwd()
        self._running_processes: list[subprocess.Popen] = []
        self._cleanup_callbacks: list[Callable] = []

    def setup(self) -> SetupResult:
        handlers = {
            "rest_api": self._setup_rest_api,
            "graphql": self._setup_rest_api,
            "cli": self._setup_cli,
            "library": self._setup_library,
            "grpc": self._setup_grpc,
            "websocket": self._setup_websocket,
            "message_queue": self._setup_message_queue,
            "serverless": self._setup_serverless,
            "batch_script": self._setup_batch_script,
        }

        handler = handlers.get(self.app_type, self._setup_default)
        try:
            return handler()
        except Exception as e:
            logger.error(f"Setup failed for {self.app_type}: {e}")
            return SetupResult(success=False, message=str(e))

    def teardown(self) -> None:
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Cleanup callback failed: {e}")

        for process in self._running_processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                logger.warning(f"Failed to terminate process: {e}")

        self._running_processes.clear()
        self._cleanup_callbacks.clear()

    def _setup_rest_api(self) -> SetupResult:
        http_conn = self.app_metadata.get("http_connection", {})
        base_url = http_conn.get("base_url", self.app_metadata.get("base_url", "http://localhost"))
        port = http_conn.get("port", self.app_metadata.get("port", 8080))
        health_endpoint = http_conn.get("health_endpoint", self.app_metadata.get("health_endpoint"))

        if health_endpoint:
            import requests
            try:
                response = requests.get(f"{base_url}:{port}{health_endpoint}", timeout=5)
                if response.status_code == 200:
                    return SetupResult(
                        success=True,
                        message=f"REST API already running at {base_url}:{port}"
                    )
            except requests.RequestException:
                pass

        return SetupResult(
            success=True,
            message=f"REST API setup skipped - assuming server is managed externally at {base_url}:{port}"
        )

    def _setup_cli(self) -> SetupResult:
        cli_conn = self.app_metadata.get("cli_connection", {})
        executable_path = cli_conn.get("executable_path", "./app")
        requires_build = cli_conn.get("requires_build", False)
        build_command = cli_conn.get("build_command")

        if requires_build and build_command:
            logger.info(f"Building CLI application: {build_command}")
            try:
                result = subprocess.run(
                    build_command,
                    shell=True,
                    cwd=str(self.project_root),
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode != 0:
                    return SetupResult(
                        success=False,
                        message=f"Build failed: {result.stderr}"
                    )
                logger.info("CLI build successful")
            except subprocess.TimeoutExpired:
                return SetupResult(
                    success=False,
                    message="Build timed out after 120 seconds"
                )

        executable = Path(executable_path)
        if not executable.is_absolute():
            executable = self.project_root / executable_path

        if executable.exists():
            return SetupResult(
                success=True,
                message=f"CLI executable ready at {executable}"
            )

        return SetupResult(
            success=True,
            message=f"CLI setup complete (executable: {executable_path})"
        )

    def _setup_library(self) -> SetupResult:
        lib_conn = self.app_metadata.get("library_connection", {})
        import_path = lib_conn.get("import_path", "")

        if import_path:
            try:
                if str(self.project_root) not in sys.path:
                    sys.path.insert(0, str(self.project_root))

                module = importlib.import_module(import_path)
                return SetupResult(
                    success=True,
                    message=f"Library '{import_path}' imported successfully"
                )
            except ImportError as e:
                return SetupResult(
                    success=False,
                    message=f"Failed to import library '{import_path}': {e}"
                )

        return SetupResult(
            success=True,
            message="Library setup complete (no specific import path configured)"
        )

    def _setup_grpc(self) -> SetupResult:
        grpc_conn = self.app_metadata.get("grpc_connection", {})
        host = grpc_conn.get("host", "localhost")
        port = grpc_conn.get("port", 50051)

        try:
            import grpc
            channel = grpc.insecure_channel(f"{host}:{port}")
            try:
                grpc.channel_ready_future(channel).result(timeout=5)
                channel.close()
                return SetupResult(
                    success=True,
                    message=f"gRPC server available at {host}:{port}"
                )
            except grpc.FutureTimeoutError:
                channel.close()
                return SetupResult(
                    success=True,
                    message=f"gRPC server not responding at {host}:{port} - tests may skip"
                )
        except ImportError:
            return SetupResult(
                success=True,
                message="gRPC library not installed - setup skipped"
            )

    def _setup_websocket(self) -> SetupResult:
        ws_conn = self.app_metadata.get("websocket_connection", {})
        ws_url = ws_conn.get("ws_url", "ws://localhost")
        port = ws_conn.get("port", 8080)

        try:
            import websocket
            full_url = f"{ws_url}:{port}/ws"
            ws = websocket.create_connection(full_url, timeout=5)
            ws.close()
            return SetupResult(
                success=True,
                message=f"WebSocket server available at {full_url}"
            )
        except Exception as e:
            return SetupResult(
                success=True,
                message=f"WebSocket server not available at {ws_url}:{port} - tests may skip: {e}"
            )

    def _setup_message_queue(self) -> SetupResult:
        mq_conn = self.app_metadata.get("message_queue_connection", {})
        broker_type = mq_conn.get("broker_type", "rabbitmq")
        broker_url = mq_conn.get("broker_url", "amqp://localhost")

        return SetupResult(
            success=True,
            message=f"Message queue setup for {broker_type} at {broker_url} - assuming broker is running"
        )

    def _setup_serverless(self) -> SetupResult:
        serverless_details = self.app_metadata.get("serverless_details", {})
        provider = serverless_details.get("provider", "aws")

        return SetupResult(
            success=True,
            message=f"Serverless setup for {provider} - tests will use local invocation"
        )

    def _setup_batch_script(self) -> SetupResult:
        return SetupResult(
            success=True,
            message="Batch script setup complete - tests will use temp directories"
        )

    def _setup_default(self) -> SetupResult:
        return SetupResult(
            success=True,
            message=f"Default setup for app type: {self.app_type}"
        )

    def wait_for_ready(self, timeout: int = 30, check_interval: float = 0.5) -> bool:
        if self.app_type not in ["rest_api", "graphql", "grpc", "websocket"]:
            return True

        http_conn = self.app_metadata.get("http_connection", {})
        health_endpoint = http_conn.get("health_endpoint", self.app_metadata.get("health_endpoint"))

        if not health_endpoint:
            return True

        base_url = http_conn.get("base_url", self.app_metadata.get("base_url", "http://localhost"))
        port = http_conn.get("port", self.app_metadata.get("port", 8080))
        health_url = f"{base_url}:{port}{health_endpoint}"

        import requests
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    logger.info(f"Application ready at {health_url}")
                    return True
            except requests.RequestException:
                pass

            time.sleep(check_interval)

        logger.warning(f"Application did not become ready within {timeout} seconds")
        return False

    def register_cleanup(self, callback: Callable) -> None:
        self._cleanup_callbacks.append(callback)

    def __enter__(self) -> "AppLifecycleManager":
        result = self.setup()
        if not result.success:
            raise RuntimeError(f"Application setup failed: {result.message}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.teardown()
