"""
Universal pytest fixtures for testing applications in ANY language.

This file provides global fixtures for testing various application types:
- REST APIs (any language)
- CLI applications (any language)
- Python applications
- gRPC services
- WebSocket servers
- Databases
- Message queues

Tests are ALWAYS written in Python (pytest), but the application under test
can be in any language.
"""

import pytest
import uuid
import sys
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Dict, Any

# Add app directory to Python path for Python applications
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))


@pytest.fixture
def unique_id():
    """
    Generate a unique identifier for test data.
    
    Returns:
        str: 8-character unique identifier
    
    Example:
        def test_create_user(client, unique_id):
            username = f'user_{unique_id}'
            # username will be unique for each test run
    """
    return uuid.uuid4().hex[:8]


@pytest.fixture
def unique_username(unique_id):
    """
    Generate a unique username for testing.
    
    Returns:
        str: Unique username with format 'user_{unique_id}'
    """
    return f'user_{unique_id}'


@pytest.fixture
def unique_email(unique_id):
    """
    Generate a unique email for testing.
    
    Returns:
        str: Unique email with format 'user_{unique_id}@example.com'
    """
    return f'user_{unique_id}@example.com'


@pytest.fixture
def test_user_data(unique_id):
    """
    Generate complete user data for testing with unique identifiers.
    
    Returns:
        dict: User data with unique username and email
    
    Example:
        def test_create_user(client, test_user_data):
            response = client.post('/api/users', json=test_user_data)
            assert response.status_code == 201
    """
    return {
        'username': f'user_{unique_id}',
        'email': f'user_{unique_id}@example.com',
        'password': 'securepass123'
    }


@pytest.fixture(autouse=True)
def reset_app_state():
    """
    Reset application state between tests (if needed).
    
    This fixture runs automatically before each test to ensure clean state.
    Modify this based on your application's state management needs.
    """
    # Setup: runs before each test
    yield
    # Teardown: runs after each test
    # Add any cleanup logic here if needed
    pass


@pytest.fixture(scope="session")
def test_config():
    """
    Provide test configuration that persists across the test session.
    
    Returns:
        dict: Test configuration settings
    """
    return {
        'TESTING': True,
        'DEBUG': False,
        'WTF_CSRF_ENABLED': False
    }


# ============================================================================
# REST API Testing Fixtures (for APIs in any language)
# ============================================================================

@pytest.fixture
def api_base_url():
    """
    Base URL for REST API testing.
    Override this in your tests for different environments.
    
    Returns:
        str: API base URL
    """
    return os.getenv('API_BASE_URL', 'http://localhost:8080')


@pytest.fixture
def api_client(api_base_url):
    """
    HTTP client for testing REST APIs (any language).
    
    Works with APIs written in Python, JavaScript, Java, Go, Rust, etc.
    
    Returns:
        requests.Session: Configured HTTP session
    """
    import requests
    
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    yield session
    session.close()


@pytest.fixture
def authenticated_api_client(api_client, api_base_url):
    """
    Authenticated HTTP client for APIs requiring authentication.
    
    Override authentication logic based on your API's auth mechanism.
    
    Returns:
        requests.Session: Authenticated HTTP session
    """
    # Example: Login and get token
    response = api_client.post(f'{api_base_url}/auth/login', json={
        'username': 'admin',
        'password': 'admin123'
    })
    
    if response.status_code == 200:
        token = response.json().get('token')
        api_client.headers.update({'Authorization': f'Bearer {token}'})
    
    return api_client


# ============================================================================
# CLI Application Testing Fixtures (for CLIs in any language)
# ============================================================================

@pytest.fixture
def cli_executable():
    """
    Path to CLI executable for testing.
    Override this in your tests for different CLI applications.
    
    Returns:
        str: Path to executable
    """
    return os.getenv('CLI_EXECUTABLE', './myapp')


def run_cli_command(executable: str, args: list, input_data: str = None) -> subprocess.CompletedProcess:
    """
    Helper function to run CLI commands.
    
    Args:
        executable: Path to executable
        args: Command arguments
        input_data: Optional stdin input
    
    Returns:
        subprocess.CompletedProcess: Command result
    """
    cmd = [executable] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_data,
        timeout=30
    )


@pytest.fixture
def temp_file(unique_id):
    """
    Create temporary file for CLI testing.
    Automatically cleaned up after test.
    
    Returns:
        str: Path to temporary file
    """
    with tempfile.NamedTemporaryFile(
        mode='w',
        delete=False,
        suffix=f'_{unique_id}.txt'
    ) as f:
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_directory(unique_id):
    """
    Create temporary directory for testing.
    Automatically cleaned up after test.
    
    Returns:
        str: Path to temporary directory
    """
    temp_dir = tempfile.mkdtemp(suffix=f'_{unique_id}')
    yield temp_dir
    
    # Cleanup
    import shutil
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


# ============================================================================
# Database Testing Fixtures (for any database)
# ============================================================================

@pytest.fixture
def db_connection_string():
    """
    Database connection string.
    Override this in your tests or use environment variable.
    
    Returns:
        str: Database connection string
    """
    return os.getenv('TEST_DB_URL', 'postgresql://test:test@localhost/test_db')


# ============================================================================
# WebSocket Testing Fixtures (for WebSocket servers in any language)
# ============================================================================

@pytest.fixture
def websocket_url():
    """
    WebSocket server URL.
    Override this in your tests for different environments.
    
    Returns:
        str: WebSocket URL
    """
    return os.getenv('WS_URL', 'ws://localhost:8080/ws')


# ============================================================================
# gRPC Testing Fixtures (for gRPC services in any language)
# ============================================================================

@pytest.fixture
def grpc_server_address():
    """
    gRPC server address.
    Override this in your tests for different environments.
    
    Returns:
        str: gRPC server address
    """
    return os.getenv('GRPC_SERVER', 'localhost:50051')


# Helper functions for tests

def generate_unique_users(count: int, base_id: str = None) -> list:
    """
    Generate multiple unique user data dictionaries.
    
    Args:
        count: Number of users to generate
        base_id: Optional base identifier (uses UUID if not provided)
    
    Returns:
        list: List of user data dictionaries
    
    Example:
        users = generate_unique_users(5)
        for user_data in users:
            client.post('/api/users', json=user_data)
    """
    if base_id is None:
        base_id = uuid.uuid4().hex[:8]
    
    return [
        {
            'username': f'user_{base_id}_{i}',
            'email': f'user_{base_id}_{i}@example.com',
            'password': 'securepass123'
        }
        for i in range(count)
    ]


def assert_valid_user_response(data: dict, expected_username: str = None):
    """
    Assert that a user response has the expected structure.
    
    Args:
        data: Response data to validate
        expected_username: Optional username to verify
    
    Raises:
        AssertionError: If response structure is invalid
    """
    assert 'id' in data, "Response should contain user ID"
    assert 'username' in data, "Response should contain username"
    assert 'email' in data, "Response should contain email"
    assert 'password' not in data, "Response should not contain password"
    assert '@' in data['email'], "Email should be valid format"
    
    if expected_username:
        assert data['username'] == expected_username, f"Expected username {expected_username}"

