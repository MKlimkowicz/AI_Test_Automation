import pytest
import uuid
import requests

@pytest.fixture
def unique_id():
    return uuid.uuid4().hex[:8]

@pytest.fixture
def unique_email(unique_id):
    return f"user_{unique_id}@example.com"

@pytest.fixture
def unique_username(unique_id):
    return f"user_{unique_id}"

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
    response = api_client.post(f"{api_base_url}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    token = response.json().get("token")
    api_client.headers.update({"Authorization": f"Bearer {token}"})
    return api_client

@pytest.fixture
def created_resource(api_client, api_base_url, test_user_data):
    response = api_client.post(f"{api_base_url}/api/users", json=test_user_data)
    resource_id = response.json().get("id")
    yield resource_id
    api_client.delete(f"{api_base_url}/api/users/{resource_id}")
