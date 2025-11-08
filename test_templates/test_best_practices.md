# Universal Test Best Practices

## Overview

This guide provides universal best practices for writing pytest tests for applications written in **ANY programming language** (Python, JavaScript, Java, Go, Rust, C#, etc.). 

**Key Principle**: Tests are ALWAYS written in Python using pytest, but the application under test can be in any language.

---

## Core Principles (Apply to All Applications)

### 1. Test Isolation

**Every test must be independent and not affect other tests.**

✅ **Use unique identifiers for all test data:**
```python
import uuid

def test_create_user(api_client):
    unique_id = uuid.uuid4().hex[:8]
    username = f'user_{unique_id}'
    email = f'user_{unique_id}@example.com'
    # Now safe from conflicts with other tests
```

❌ **Never use hardcoded shared data:**
```python
def test_create_user(api_client):
    username = 'testuser'  # ❌ Will conflict with other tests!
```

### 2. Reusable Fixtures

**Use pytest fixtures for setup, teardown, and shared resources.**

```python
import pytest

@pytest.fixture
def unique_id():
    """Generate unique identifier for test data"""
    return uuid.uuid4().hex[:8]

@pytest.fixture
def test_user_data(unique_id):
    """Generate unique user data"""
    return {
        'username': f'user_{unique_id}',
        'email': f'user_{unique_id}@example.com',
        'password': 'securepass123'
    }

@pytest.fixture
def api_client():
    """HTTP client for API testing"""
    import requests
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    yield session
    session.close()
```

### 3. Unique Test Data

**Always generate unique data to avoid conflicts:**

- Usernames: `f'user_{uuid.uuid4().hex[:8]}'`
- Emails: `f'user_{uuid.uuid4().hex[:8]}@example.com'`
- IDs: `uuid.uuid4().hex[:8]`
- Filenames: `f'test_{uuid.uuid4().hex[:8]}.txt'`

### 4. Teardown/Cleanup

**Clean up resources after tests to avoid side effects.**

```python
@pytest.fixture
def temp_resource():
    """Create resource, cleanup after test"""
    resource = create_resource()
    yield resource
    # Cleanup runs after test
    cleanup_resource(resource)

@pytest.fixture
def database_transaction(db_connection):
    """Rollback database changes after test"""
    transaction = db_connection.begin()
    yield db_connection
    transaction.rollback()
```

### 5. Clear Assertions

**Be specific about what you're testing.**

✅ **Good - Specific with helpful messages:**
```python
assert response.status_code == 201, f"Expected 201, got {response.status_code}"
assert 'id' in data, "Response should contain user ID"
assert data['username'] == expected_username
```

❌ **Bad - Vague without context:**
```python
assert response.status_code == 201
assert data
```

---

## Application Type Examples

### REST API Testing (Any Language)

Test REST APIs written in Python (Flask, FastAPI), JavaScript (Express), Java (Spring Boot), Go (Gin), Rust (Actix), etc.

```python
import pytest
import requests
import uuid

@pytest.fixture
def api_base_url():
    """Base URL for the API"""
    return "http://localhost:8080"

@pytest.fixture
def api_client(api_base_url):
    """HTTP client for API testing"""
    session = requests.Session()
    session.headers.update({'Content-Type': 'application/json'})
    yield session
    session.close()

def test_create_user(api_client, api_base_url):
    """Test user creation endpoint"""
    unique_id = uuid.uuid4().hex[:8]
    user_data = {
        'username': f'user_{unique_id}',
        'email': f'user_{unique_id}@example.com',
        'password': 'securepass123'
    }
    
    response = api_client.post(f'{api_base_url}/api/users', json=user_data)
    
    assert response.status_code == 201
    data = response.json()
    assert 'id' in data
    assert data['username'] == user_data['username']

def test_get_user(api_client, api_base_url):
    """Test retrieving user by ID"""
    # Create user first
    unique_id = uuid.uuid4().hex[:8]
    user_data = {'username': f'user_{unique_id}', 'email': f'user_{unique_id}@example.com', 'password': 'pass123'}
    create_response = api_client.post(f'{api_base_url}/api/users', json=user_data)
    user_id = create_response.json()['id']
    
    # Get user
    response = api_client.get(f'{api_base_url}/api/users/{user_id}')
    
    assert response.status_code == 200
    assert response.json()['id'] == user_id

def test_authentication(api_client, api_base_url):
    """Test API authentication"""
    response = api_client.post(f'{api_base_url}/auth/login', json={
        'username': 'admin',
        'password': 'admin123'
    })
    
    assert response.status_code == 200
    assert 'token' in response.json()
```

---

### GraphQL API Testing (Any Language)

Test GraphQL APIs written in any language (Python Strawberry, JavaScript Apollo, Java GraphQL-Java, etc.).

```python
import pytest
import requests
import uuid

@pytest.fixture
def graphql_client():
    """GraphQL client"""
    return requests.Session()

def test_graphql_query(graphql_client):
    """Test GraphQL query"""
    query = """
    query GetUser($id: ID!) {
        user(id: $id) {
            id
            username
            email
        }
    }
    """
    
    response = graphql_client.post('http://localhost:4000/graphql', json={
        'query': query,
        'variables': {'id': '1'}
    })
    
    assert response.status_code == 200
    data = response.json()
    assert 'data' in data
    assert 'user' in data['data']

def test_graphql_mutation(graphql_client):
    """Test GraphQL mutation"""
    unique_id = uuid.uuid4().hex[:8]
    mutation = """
    mutation CreateUser($username: String!, $email: String!) {
        createUser(username: $username, email: $email) {
            id
            username
        }
    }
    """
    
    response = graphql_client.post('http://localhost:4000/graphql', json={
        'query': mutation,
        'variables': {
            'username': f'user_{unique_id}',
            'email': f'user_{unique_id}@example.com'
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert 'data' in data
    assert 'createUser' in data['data']
```

---

### CLI Application Testing (Any Language)

Test command-line applications written in any language (Python Click, Go Cobra, Rust Clap, etc.).

```python
import pytest
import subprocess
import uuid
import tempfile
import os

def test_cli_help_command():
    """Test CLI help output"""
    result = subprocess.run(['./myapp', '--help'], capture_output=True, text=True)
    
    assert result.returncode == 0
    assert 'Usage:' in result.stdout
    assert '--help' in result.stdout

def test_cli_create_user():
    """Test CLI user creation"""
    unique_id = uuid.uuid4().hex[:8]
    username = f'user_{unique_id}'
    
    result = subprocess.run(
        ['./myapp', 'user', 'create', '--username', username, '--email', f'{username}@example.com'],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert 'User created successfully' in result.stdout
    assert username in result.stdout

def test_cli_file_processing():
    """Test CLI file processing"""
    unique_id = uuid.uuid4().hex[:8]
    
    # Create temp input file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        input_file = f.name
        f.write('test data')
    
    output_file = f'/tmp/output_{unique_id}.txt'
    
    try:
        result = subprocess.run(
            ['./myapp', 'process', '--input', input_file, '--output', output_file],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert os.path.exists(output_file)
    finally:
        # Cleanup
        os.unlink(input_file)
        if os.path.exists(output_file):
            os.unlink(output_file)
```

---

### gRPC Service Testing (Any Language)

Test gRPC services written in any language (Python, Go, Java, C++, etc.).

```python
import pytest
import grpc
import uuid
from generated import user_service_pb2, user_service_pb2_grpc

@pytest.fixture
def grpc_channel():
    """gRPC channel"""
    channel = grpc.insecure_channel('localhost:50051')
    yield channel
    channel.close()

@pytest.fixture
def user_stub(grpc_channel):
    """User service stub"""
    return user_service_pb2_grpc.UserServiceStub(grpc_channel)

def test_create_user_grpc(user_stub):
    """Test gRPC user creation"""
    unique_id = uuid.uuid4().hex[:8]
    
    request = user_service_pb2.CreateUserRequest(
        username=f'user_{unique_id}',
        email=f'user_{unique_id}@example.com'
    )
    
    response = user_stub.CreateUser(request)
    
    assert response.id > 0
    assert response.username == f'user_{unique_id}'

def test_get_user_grpc(user_stub):
    """Test gRPC get user"""
    request = user_service_pb2.GetUserRequest(id=1)
    response = user_stub.GetUser(request)
    
    assert response.id == 1
    assert response.username != ''
```

---

### WebSocket Server Testing (Any Language)

Test WebSocket servers written in any language (Python, Node.js, Go, etc.).

```python
import pytest
import websocket
import json
import uuid

@pytest.fixture
def ws_connection():
    """WebSocket connection"""
    ws = websocket.create_connection('ws://localhost:8080/ws')
    yield ws
    ws.close()

def test_websocket_connection(ws_connection):
    """Test WebSocket connection"""
    assert ws_connection.connected

def test_websocket_message_exchange(ws_connection):
    """Test sending and receiving messages"""
    unique_id = uuid.uuid4().hex[:8]
    message = {'type': 'create_user', 'username': f'user_{unique_id}'}
    
    ws_connection.send(json.dumps(message))
    response = json.loads(ws_connection.recv())
    
    assert response['status'] == 'success'
    assert 'user_id' in response

def test_websocket_broadcast():
    """Test WebSocket broadcast"""
    ws1 = websocket.create_connection('ws://localhost:8080/ws')
    ws2 = websocket.create_connection('ws://localhost:8080/ws')
    
    try:
        # Send from ws1
        ws1.send(json.dumps({'type': 'broadcast', 'message': 'Hello'}))
        
        # Receive on ws2
        response = json.loads(ws2.recv())
        assert response['message'] == 'Hello'
    finally:
        ws1.close()
        ws2.close()
```

---

### Database Operations Testing (Any Database)

Test database operations for any database (PostgreSQL, MySQL, MongoDB, etc.).

```python
import pytest
import psycopg2
import uuid

@pytest.fixture
def db_connection():
    """Database connection with transaction rollback"""
    conn = psycopg2.connect("dbname=test user=test password=test")
    conn.autocommit = False
    yield conn
    conn.rollback()  # Rollback all changes after test
    conn.close()

def test_insert_user(db_connection):
    """Test inserting user into database"""
    unique_id = uuid.uuid4().hex[:8]
    cursor = db_connection.cursor()
    
    cursor.execute(
        "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
        (f'user_{unique_id}', f'user_{unique_id}@example.com')
    )
    
    user_id = cursor.fetchone()[0]
    assert user_id is not None

def test_query_user(db_connection):
    """Test querying user from database"""
    cursor = db_connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (1,))
    
    user = cursor.fetchone()
    assert user is not None
```

---

### Message Queue Testing (Any Language)

Test message queue producers/consumers written in any language (Python Celery, RabbitMQ, Kafka, etc.).

```python
import pytest
import pika
import json
import uuid
import time

@pytest.fixture
def rabbitmq_connection():
    """RabbitMQ connection"""
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    yield channel
    connection.close()

def test_publish_message(rabbitmq_connection):
    """Test publishing message to queue"""
    unique_id = uuid.uuid4().hex[:8]
    queue_name = f'test_queue_{unique_id}'
    
    rabbitmq_connection.queue_declare(queue=queue_name, auto_delete=True)
    
    message = {'user_id': unique_id, 'action': 'create'}
    rabbitmq_connection.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(message)
    )
    
    # Verify message was published
    method, properties, body = rabbitmq_connection.basic_get(queue=queue_name)
    assert body is not None
    assert json.loads(body)['user_id'] == unique_id

def test_consume_message(rabbitmq_connection):
    """Test consuming message from queue"""
    unique_id = uuid.uuid4().hex[:8]
    queue_name = f'test_queue_{unique_id}'
    
    rabbitmq_connection.queue_declare(queue=queue_name, auto_delete=True)
    
    # Publish message
    message = {'task': 'process_user', 'user_id': unique_id}
    rabbitmq_connection.basic_publish(
        exchange='',
        routing_key=queue_name,
        body=json.dumps(message)
    )
    
    # Consume message
    method, properties, body = rabbitmq_connection.basic_get(queue=queue_name, auto_ack=True)
    
    assert method is not None
    consumed_message = json.loads(body)
    assert consumed_message['user_id'] == unique_id
```

---

### Microservices Testing (Any Language)

Test microservices written in any language with service-to-service communication.

```python
import pytest
import requests
import uuid
from unittest.mock import patch, MagicMock

@pytest.fixture
def service_a_url():
    return "http://localhost:8001"

@pytest.fixture
def service_b_url():
    return "http://localhost:8002"

def test_service_integration(service_a_url, service_b_url):
    """Test integration between two services"""
    unique_id = uuid.uuid4().hex[:8]
    
    # Call service A
    response_a = requests.post(f'{service_a_url}/api/users', json={
        'username': f'user_{unique_id}',
        'email': f'user_{unique_id}@example.com'
    })
    
    assert response_a.status_code == 201
    user_id = response_a.json()['id']
    
    # Verify service B received the event
    response_b = requests.get(f'{service_b_url}/api/user-events/{user_id}')
    assert response_b.status_code == 200

@patch('requests.post')
def test_service_with_mock(mock_post):
    """Test service with mocked dependencies"""
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {'id': '123', 'status': 'success'}
    )
    
    # Test your service that calls external API
    result = my_service_function()
    
    assert result['status'] == 'success'
    mock_post.assert_called_once()
```

---

## Key Takeaways

1. **Always use unique identifiers** (`uuid.uuid4().hex[:8]`) for test data
2. **Use pytest fixtures** for setup, teardown, and shared resources
3. **Be specific in assertions** with helpful error messages
4. **Clean up resources** after tests (files, DB records, connections)
5. **Tests must be independent** - no execution order dependencies
6. **Use appropriate client libraries** (requests for HTTP, subprocess for CLI, grpc for gRPC, etc.)
7. **Mock external dependencies** when testing microservices
8. **Rollback database transactions** to avoid test data pollution

---

## Anti-Patterns to Avoid

❌ Hardcoded test data shared across tests
❌ Tests that depend on other tests running first
❌ Vague assertions without context
❌ Not cleaning up test resources
❌ Assuming empty/clean state
❌ Testing multiple unrelated things in one test
❌ Using production data or credentials in tests
