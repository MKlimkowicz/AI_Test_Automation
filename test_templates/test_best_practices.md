# Test Best Practices Guide

## Overview

This guide provides best practices for writing pytest fixtures in conftest.py and tests for applications written in ANY programming language. Tests are always written in Python using pytest.

---

# Part 1: Conftest Fixtures and Helper Functions

## Fixture Scopes

### Function Scope (Default)

```python
import pytest
import uuid

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]
```

### Module Scope

```python
import pytest
import requests

@pytest.fixture(scope="module")
def api_session():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()
```

### Session Scope

```python
import pytest

@pytest.fixture(scope="session")
def database_connection():
    import psycopg2
    conn = psycopg2.connect("dbname=test user=test password=test")
    yield conn
    conn.close()
```

---

## Core Fixture Patterns

### Unique Identifier Generator

```python
import pytest
import uuid

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]

@pytest.fixture
def unique_email(unique_id):
    return f"user_{unique_id}@example.com"

@pytest.fixture
def unique_username(unique_id):
    return f"user_{unique_id}"
```

### Test Data Factory

```python
import pytest
import uuid

@pytest.fixture
def user_data_factory():
    def _create_user_data(username=None, email=None, password="securepass123"):
        uid = uuid.uuid4().hex[:8]
        return {
            "username": username or f"user_{uid}",
            "email": email or f"user_{uid}@example.com",
            "password": password
        }
    return _create_user_data

@pytest.fixture
def test_user_data(unique_id):
    return {
        "username": f"user_{unique_id}",
        "email": f"user_{unique_id}@example.com",
        "password": "securepass123"
    }
```

### Resource Cleanup with Yield

```python
import pytest
import os
import tempfile

@pytest.fixture
def temp_file(unique_id):
    filepath = f"/tmp/test_{unique_id}.txt"
    with open(filepath, "w") as f:
        f.write("test content")
    yield filepath
    if os.path.exists(filepath):
        os.unlink(filepath)

@pytest.fixture
def created_resource(api_client, api_base_url, test_user_data):
    response = api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    resource_id = response.json().get("id")
    yield resource_id
    api_client.delete(f"{api_base_url}/api/users/{resource_id}")
```

---

## Application-Type Specific Fixtures

### REST API Fixtures

```python
import pytest
import requests

@pytest.fixture
def api_base_url():
    return "http://localhost:5000"

@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()

@pytest.fixture
def authenticated_client(api_client, api_base_url):
    response = api_client.post(f"{api_base_url}/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    token = response.json().get("token")
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client
```

### Flask Test Client Fixtures

```python
import pytest

@pytest.fixture
def flask_app():
    from app.sample_api import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app

@pytest.fixture
def flask_client(flask_app):
    with flask_app.test_client() as client:
        yield client
```

### CLI Application Fixtures

```python
import pytest
import subprocess
import os

@pytest.fixture
def cli_runner():
    def _run_command(args, input_text=None):
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            input=input_text
        )
        return result
    return _run_command

@pytest.fixture
def cli_executable():
    return "./myapp"
```

### GraphQL Fixtures

```python
import pytest
import requests

@pytest.fixture
def graphql_url():
    return "http://localhost:4000/graphql"

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

### gRPC Fixtures

```python
import pytest
import grpc

@pytest.fixture
def grpc_channel():
    channel = grpc.insecure_channel("localhost:50051")
    yield channel
    channel.close()

@pytest.fixture
def grpc_stub(grpc_channel):
    from generated import service_pb2_grpc
    return service_pb2_grpc.MyServiceStub(grpc_channel)
```

### WebSocket Fixtures

```python
import pytest
import websocket
import json

@pytest.fixture
def ws_url():
    return "ws://localhost:8080/ws"

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

### Database Fixtures

```python
import pytest

@pytest.fixture
def db_connection():
    import psycopg2
    conn = psycopg2.connect("dbname=test user=test password=test")
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()

@pytest.fixture
def db_cursor(db_connection):
    cursor = db_connection.cursor()
    yield cursor
    cursor.close()

@pytest.fixture
def mongodb_client():
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017")
    yield client
    client.close()

@pytest.fixture
def mongodb_collection(mongodb_client, unique_id):
    db = mongodb_client["test_db"]
    collection = db[f"test_collection_{unique_id}"]
    yield collection
    collection.drop()
```

### Message Queue Fixtures

```python
import pytest
import pika
import json

@pytest.fixture
def rabbitmq_channel():
    connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
    channel = connection.channel()
    yield channel
    connection.close()

@pytest.fixture
def test_queue(rabbitmq_channel, unique_id):
    queue_name = f"test_queue_{unique_id}"
    rabbitmq_channel.queue_declare(queue=queue_name, auto_delete=True)
    yield queue_name
```

---

## Parametrized Fixtures

```python
import pytest

@pytest.fixture(params=["admin", "user", "guest"])
def user_role(request):
    return request.param

@pytest.fixture(params=[200, 201, 204])
def success_status_code(request):
    return request.param

@pytest.fixture(params=[
    {"username": "valid_user", "expected": 201},
    {"username": "", "expected": 400},
    {"username": "a" * 256, "expected": 400}
])
def username_test_case(request):
    return request.param
```

---

## Helper Functions

```python
import uuid
import time

def generate_unique_id():
    return uuid.uuid4().hex[:8]

def generate_unique_email():
    return f"user_{generate_unique_id()}@example.com"

def generate_unique_username():
    return f"user_{generate_unique_id()}"

def wait_for_condition(condition_func, timeout=10, interval=0.5):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False

def retry_request(func, max_attempts=3, delay=1):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception:
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)
```

---

# Part 2: Test Best Practices

## Test Structure and Naming

```python
def test_create_user_with_valid_data_returns_201(api_client, api_base_url, test_user_data):
    response = api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    
    assert response.status_code == 201

def test_get_nonexistent_user_returns_404(api_client, api_base_url):
    response = api_client.get(f"{api_base_url}/api/users/99999")
    
    assert response.status_code == 404

def test_delete_user_removes_resource(api_client, api_base_url, created_resource):
    response = api_client.delete(f"{api_base_url}/api/users/{created_resource}")
    
    assert response.status_code == 200
    
    get_response = api_client.get(f"{api_base_url}/api/users/{created_resource}")
    assert get_response.status_code == 404
```

---

## Assertion Patterns

### Status Code Assertions

```python
def test_successful_creation(api_client, api_base_url, test_user_data):
    response = api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

def test_unauthorized_access(api_client, api_base_url):
    response = api_client.get(f"{api_base_url}/api/protected")
    
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
```

### Response Body Assertions

```python
def test_user_response_contains_required_fields(api_client, api_base_url, created_resource):
    response = api_client.get(f"{api_base_url}/api/users/{created_resource}")
    data = response.json()
    
    assert "id" in data, "Response missing 'id' field"
    assert "username" in data, "Response missing 'username' field"
    assert "email" in data, "Response missing 'email' field"
    assert "password" not in data, "Response should not expose password"

def test_list_users_returns_array(api_client, api_base_url):
    response = api_client.get(f"{api_base_url}/api/users")
    data = response.json()
    
    assert isinstance(data, list), f"Expected list, got {type(data)}"
```

### Value Assertions

```python
def test_created_user_matches_input(api_client, api_base_url, test_user_data):
    response = api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    data = response.json()
    
    assert data["username"] == test_user_data["username"], "Username mismatch"
    assert data["email"] == test_user_data["email"], "Email mismatch"
```

---

## Test Isolation

```python
def test_user_creation_is_isolated(api_client, api_base_url, unique_id):
    user_data = {
        "username": f"user_{unique_id}",
        "email": f"user_{unique_id}@example.com",
        "password": "password123"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code == 201

def test_another_user_creation_is_isolated(api_client, api_base_url, unique_id):
    user_data = {
        "username": f"user_{unique_id}",
        "email": f"user_{unique_id}@example.com",
        "password": "password123"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code == 201
```

---

## Using Fixtures Effectively

```python
def test_with_factory_fixture(api_client, api_base_url, user_data_factory):
    user1 = user_data_factory()
    user2 = user_data_factory(password="different_password")
    
    response1 = api_client.post(f"{api_base_url}/api/users", json=user1)
    response2 = api_client.post(f"{api_base_url}/api/users", json=user2)
    
    assert response1.status_code == 201
    assert response2.status_code == 201
    assert response1.json()["id"] != response2.json()["id"]

def test_with_authenticated_client(authenticated_client, api_base_url):
    response = authenticated_client.get(f"{api_base_url}/api/protected")
    
    assert response.status_code == 200

def test_database_rollback(db_cursor, unique_id):
    db_cursor.execute(
        "INSERT INTO users (username, email) VALUES (%s, %s)",
        (f"user_{unique_id}", f"user_{unique_id}@example.com")
    )
    
    db_cursor.execute("SELECT COUNT(*) FROM users WHERE username = %s", (f"user_{unique_id}",))
    count = db_cursor.fetchone()[0]
    
    assert count == 1
```

---

## Edge Case and Error Handling Tests

### Input Validation

```python
def test_empty_username_returns_400(api_client, api_base_url, unique_id):
    user_data = {
        "username": "",
        "email": f"user_{unique_id}@example.com",
        "password": "password123"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code == 400

def test_invalid_email_format_returns_400(api_client, api_base_url, unique_id):
    user_data = {
        "username": f"user_{unique_id}",
        "email": "not-an-email",
        "password": "password123"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code == 400

def test_missing_required_field_returns_400(api_client, api_base_url, unique_id):
    user_data = {
        "username": f"user_{unique_id}"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code == 400
```

### Boundary Conditions

```python
def test_username_at_max_length(api_client, api_base_url, unique_id):
    user_data = {
        "username": "a" * 50,
        "email": f"user_{unique_id}@example.com",
        "password": "password123"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code in [201, 400]

def test_username_exceeds_max_length(api_client, api_base_url, unique_id):
    user_data = {
        "username": "a" * 256,
        "email": f"user_{unique_id}@example.com",
        "password": "password123"
    }
    
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
    
    assert response.status_code == 400
```

### Error Response Validation

```python
def test_error_response_contains_message(api_client, api_base_url):
    response = api_client.get(f"{api_base_url}/api/users/invalid-id")
    
    assert response.status_code >= 400
    data = response.json()
    assert "error" in data or "message" in data

def test_duplicate_username_returns_conflict(api_client, api_base_url, test_user_data):
    api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    
    response = api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    
    assert response.status_code == 409
```

---

## CLI Application Tests

```python
def test_cli_help_displays_usage(cli_runner, cli_executable):
    result = cli_runner([cli_executable, "--help"])
    
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "Usage" in result.stdout

def test_cli_version_displays_version(cli_runner, cli_executable):
    result = cli_runner([cli_executable, "--version"])
    
    assert result.returncode == 0

def test_cli_invalid_command_returns_error(cli_runner, cli_executable):
    result = cli_runner([cli_executable, "nonexistent-command"])
    
    assert result.returncode != 0
```

---

## GraphQL Tests

```python
def test_graphql_query_returns_data(graphql_client, graphql_url, graphql_query):
    query = """
    query {
        users {
            id
            username
        }
    }
    """
    
    response = graphql_query(graphql_client, graphql_url, query)
    data = response.json()
    
    assert "data" in data
    assert "errors" not in data

def test_graphql_mutation_creates_resource(graphql_client, graphql_url, graphql_query, unique_id):
    mutation = """
    mutation CreateUser($username: String!, $email: String!) {
        createUser(username: $username, email: $email) {
            id
            username
        }
    }
    """
    variables = {
        "username": f"user_{unique_id}",
        "email": f"user_{unique_id}@example.com"
    }
    
    response = graphql_query(graphql_client, graphql_url, mutation, variables)
    data = response.json()
    
    assert "data" in data
    assert data["data"]["createUser"]["username"] == f"user_{unique_id}"
```

---

## WebSocket Tests

```python
def test_websocket_connection_established(ws_connection):
    assert ws_connection.connected

def test_websocket_message_exchange(ws_connection, ws_send_receive, unique_id):
    message = {"type": "ping", "id": unique_id}
    
    response = ws_send_receive(ws_connection, message)
    
    assert response["type"] == "pong"
```

---

## Anti-Patterns to Avoid

### Hardcoded Test Data

```python
def test_wrong_hardcoded_data(api_client, api_base_url):
    user_data = {
        "username": "testuser",
        "email": "test@example.com"
    }
    response = api_client.post(f"{api_base_url}/api/users", json=user_data)
```

### Missing Assertion Messages

```python
def test_wrong_no_message(api_client, api_base_url):
    response = api_client.get(f"{api_base_url}/api/users")
    assert response.status_code == 200
    assert response.json()
```

### Test Dependencies

```python
created_user_id = None

def test_wrong_create_user(api_client, api_base_url):
    global created_user_id
    response = api_client.post(f"{api_base_url}/api/users", json={"username": "test"})
    created_user_id = response.json()["id"]

def test_wrong_get_user(api_client, api_base_url):
    response = api_client.get(f"{api_base_url}/api/users/{created_user_id}")
    assert response.status_code == 200
```

---

## Key Principles Summary

1. Always use unique identifiers for test data
2. Use fixtures for setup, teardown, and shared resources
3. Clean up resources after tests using yield fixtures
4. Be specific in assertions with helpful error messages
5. Tests must be independent with no execution order dependencies
6. Use appropriate client libraries for the application type
7. Rollback database transactions to avoid test data pollution
8. Never use production data or credentials in tests
