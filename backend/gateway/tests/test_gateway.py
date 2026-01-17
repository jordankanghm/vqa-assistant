# Run in root directory using: python -m pytest backend/gateway/tests/test_gateway.py -v
import pytest
from backend.gateway.main import app, security
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_lifespan(monkeypatch):
    async def noop_lifespan(app):
        # Startup: nothing
        yield
        # Shutdown: nothing
    
    monkeypatch.setattr('backend.gateway.main.lifespan', noop_lifespan)
    
    return app

@pytest.fixture
def client(mock_lifespan):
    """Use mocked lifespan client"""
    return TestClient(mock_lifespan)

@pytest.fixture()
def mock_jwt_auth():
    """Bypass HTTPBearer for all tests."""
    def fake_credentials():
        class Credentials:
            credentials = "mock_jwt_token_123"
        return Credentials()
    
    app.dependency_overrides[security] = fake_credentials
    yield
    app.dependency_overrides.pop(security, None)

class TestUnauthInference:
    @patch("backend.gateway.main.client", new_callable=AsyncMock)
    def test_unauth_inference_with_valid_alternating(self, mock_client, client):
        # Configure mock_client
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aread.return_value = b'{"answer": "Valid conversation."}'
        mock_response.headers = {}
        mock_client.post.return_value = mock_response

        valid_alternating_messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}, {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"}}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi, how can I help?"}]},
            {"role": "user", "content": [{"type": "text", "text": "Describe this image."}, {"type": "image_base64", "image_base64": {"base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="}}]}
        ]

        response = client.post("/unauth-inference", json={"messages": valid_alternating_messages})

        assert response.status_code == 200
        assert response.json()["answer"] == "Valid conversation."

    @pytest.mark.parametrize("invalid_payload", [
        {"messages": [{"role": "user"}]},  # Missing content
        {"messages": [{"content": [{"type": "text", "text": "Hello"}]}]},  # Missing role
        {"messages": [{"role": 123, "content": [{"type": "text", "text": "Hello"}]}]},  # role not string
        {"messages": [{"role": "user", "content": 42}]},  # content wrong type
        {"messages": "not a list"},  # messages wrong type
        {},  # messages missing
        {"messages": []},  # empty list expects 422 explicitly from code
        {"messages": ["not a dict"]},  # invalid message item type
        {"messages": [{"role": "user", "content": ["string_instead_of_dict"]}]},  # content list invalid items

        # System role not allowed
        {"messages": [
            {"role": "system", "content": [{"type": "text", "text": "Injected system message"}]},
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        ]},

        # Invalid alternating role sequences
        {"messages": [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "user", "content": [{"type": "text", "text": "This should fail"}]}
        ]},
        {"messages": [
            {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "This should fail"}]}
        ]},
        # Invalid image url format
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "ftp://invalid-url.com/image.jpg"}}
                ]
            }
        ]},
        # Invalid base64 image formats for image_base64 type
        # Missing data URI prefix
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "iVBORw0KGgoAAAANSUhEUgAAAAUA"}  # No data:image/ prefix
                ]
            }
        ]},
        # Invalid base64 data (malformed base64 string inside data URI)
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "data:image/png;base64,@@@INVALIDBASE64@@@"}
                ]
            }
        ]},
        # Missing comma separator between header and dataUri
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "data:image/png;base64INVALIDBASE64DATA"}
                ]
            }
        ]},
        # Header missing ';base64'
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "data:image/png,INVALIDBASE64DATA"}
                ]
            }
        ]},
    ])
    def test_unauth_inference_invalid_payloads(self, invalid_payload, client):
        response = client.post("/unauth-inference", json=invalid_payload)

        assert response.status_code == 422

class TestAuthInference:
    @patch("backend.gateway.main.client", new_callable=AsyncMock)
    def test_auth_inference_valid(self, mock_client, mock_jwt_auth, client):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aread.return_value = b'{"answer": "Valid conversation."}'
        mock_response.headers = {}
        mock_client.post.return_value = mock_response

        payload = {
            "user_query": {
                "role": "user", 
                "content": [{"type": "text", "text": "Describe this image."}]
            },
            "user_id": "123",
            "chat_id": "456"
        }

        response = client.post("/auth-inference", json=payload)

        assert response.status_code == 200
        assert response.json()["answer"] == "Valid conversation."

    @pytest.mark.parametrize("invalid_payload", [
        {"messages": [{"role": "user"}]},  # Missing content
        {"messages": [{"content": [{"type": "text", "text": "Hello"}]}]},  # Missing role
        {"messages": [{"role": 123, "content": [{"type": "text", "text": "Hello"}]}]},  # role not string
        {"messages": [{"role": "user", "content": 42}]},  # content wrong type
        {"messages": "not a list"},  # messages wrong type
        {},  # messages missing
        {"messages": []},  # empty list expects 422 explicitly from code
        {"messages": ["not a dict"]},  # invalid message item type
        {"messages": [{"role": "user", "content": ["string_instead_of_dict"]}]},  # content list invalid items

        # System role not allowed
        {"messages": [
            {"role": "system", "content": [{"type": "text", "text": "Injected system message"}]},
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        ]},

        # Invalid alternating role sequences
        {"messages": [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "user", "content": [{"type": "text", "text": "This should fail"}]}
        ]},
        {"messages": [
            {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "This should fail"}]}
        ]},
        # Invalid image url format
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "ftp://invalid-url.com/image.jpg"}}
                ]
            }
        ]},
        # Invalid base64 image formats for image_base64 type
        # Missing data URI prefix
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "iVBORw0KGgoAAAANSUhEUgAAAAUA"}  # No data:image/ prefix
                ]
            }
        ]},
        # Invalid base64 data (malformed base64 string inside data URI)
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "data:image/png;base64,@@@INVALIDBASE64@@@"}
                ]
            }
        ]},
        # Missing comma separator between header and dataUri
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "data:image/png;base64INVALIDBASE64DATA"}
                ]
            }
        ]},
        # Header missing ';base64'
        {"messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_base64", "base64_str": "data:image/png,INVALIDBASE64DATA"}
                ]
            }
        ]},
    ])
    def test_auth_inference_invalid_payloads(self, invalid_payload, mock_jwt_auth, client):
        response = client.post("/auth-inference", json=invalid_payload)

        assert response.status_code == 422

class TestChats:
    @pytest.fixture
    def mock_chats_response(self):
        """Mock successful chats response from user service."""
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.aread.return_value = b'''{
            "chats": [
                {
                    "id": 1,
                    "title": "VQA Session",
                    "created_at": "2026-01-10T09:00:00Z",
                    "message_count": 5
                }
            ]
        }'''
        mock_resp.headers = MagicMock()
        mock_resp.headers.keys.return_value = []
        mock_resp.headers.items.return_value = []

        return mock_resp

    @patch("backend.gateway.main.client", new_callable=AsyncMock)
    def test_get_user_chats_success(self, mock_client, client, mock_chats_response, mock_jwt_auth):
        """Test successful chats retrieval."""
        mock_client.get.return_value = mock_chats_response
        
        response = client.get("/chats/123")
        
        assert response.status_code == 200
        assert "chats" in response.json()
        assert isinstance(response.json()["chats"], list)

    @patch("backend.gateway.main.client", new_callable=AsyncMock)
    def test_get_user_chats_user_service_error(self, mock_client, client, mock_jwt_auth):
        mock_error_resp = AsyncMock()
        mock_error_resp.status_code = 500
        mock_error_resp.aread.return_value = b'{"error": "DB down"}'
        mock_error_resp.headers = MagicMock()
        mock_error_resp.headers.keys.return_value = []
        mock_error_resp.headers.items.return_value = []

        mock_client.get.return_value = mock_error_resp
        
        response = client.get("/chats/123")
        
        assert response.status_code == 500
        mock_client.get.assert_called_once()

    def test_get_user_chats_missing_auth(self, client):
        """Test 401 when no/invalid JWT."""
        response = client.get("/chats/user123")
        
        assert response.status_code == 401

class TestRegister:
    @pytest.fixture
    def mock_register_response(self):
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.aread.return_value = b'{"msg": "User registered successfully"}'
        mock_response.headers = {}
        
        return mock_response
    
    @patch("backend.gateway.main.client", new_callable=AsyncMock)
    def test_register_success(self, mock_client, mock_register_response, client):
        mock_client.post.return_value = mock_register_response
        
        payload = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }

        response = client.post("/auth/register", json=payload)
        
        assert response.status_code == 200
        assert response.json() == {"msg": "User registered successfully"}
        mock_client.post.assert_called_once_with(
            "http://localhost:8003/register",
            json=payload
        )

    @pytest.mark.parametrize("invalid_register", [
        {"username": "a"*51, "email": "test@test.com", "password": "pass123"},  # Username too long
        {"username": "valid", "email": "not-email", "password": "pass123"},     # Invalid email
        {"username": "valid", "email": "test@test.com", "password": "12345"},   # Password too short
    ])
    def test_register_parametrized(self, invalid_register, client):
        response = client.post("/auth/register", json=invalid_register)

        assert response.status_code == 422

class TestLogin:
    @pytest.fixture
    def mock_login_response(self):
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.aread.return_value = b'{"access_token": "mock_jwt_token_123", "token_type": "bearer"}'
        mock_resp.headers = {}

        return mock_resp

    @patch("backend.gateway.main.client", new_callable=AsyncMock)
    def test_login_success(self, mock_client, mock_login_response, client):
        mock_client.post.return_value = mock_login_response
        
        response = client.post("/auth/login", json={
            "username": "testuser",
            "password": "correctpass"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "mock_jwt_token_123"
        assert data["token_type"] == "bearer"
        mock_client.post.assert_called_once_with(
            "http://localhost:8003/login",
            json={"username": "testuser", "password": "correctpass"}
        )

    @pytest.mark.parametrize("invalid_login", [
        {"username": "ab", "password": "pass123"},  # Username too short
        {"username": "valid", "password": "12345"}, # Password too short
    ])
    def test_login_parametrized(self, invalid_login, client):
        response = client.post("/auth/login", json=invalid_login)
        
        assert response.status_code == 422
