# Run using: python -m pytest path_to_test_inference_service.py -v
import pytest
from inference_service.main import app, security
from fastapi.testclient import TestClient
from unittest.mock import ANY, AsyncMock, MagicMock, patch

USER_SERVICE_URL = "http://localhost:8003"

@pytest.fixture
def mock_lifespan(monkeypatch):
    async def noop_lifespan(app):
         # Startup: nothing
        yield 
        # Shutdown: nothing
    
    monkeypatch.setattr('inference_service.main.lifespan', noop_lifespan)
    
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
    @patch("inference_service.main.rag", new_callable=AsyncMock)
    def test_unauth_inference_valid(self, mock_rag, client):
        mock_response = AsyncMock()
        mock_response.content = "Valid conversation."
        mock_rag.return_value = mock_response

        payload = {
            "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}, {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"}}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi, how can I help?"}]},
            {"role": "user", "content": [{"type": "text", "text": "Describe this image."}, {"type": "image_base64", "image_base64": {"base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="}}]}
            ]
        }

        response = client.post("/unauth-inference", json=payload)

        assert response.status_code == 200
        assert response.json()["answer"] == "Valid conversation."
        mock_rag.assert_called_once_with("Describe this image.", ANY)

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
    def test_unauth_inference_invalid_payloads(self, client, invalid_payload):
        response = client.post("/unauth-inference", json=invalid_payload)

        assert response.status_code == 422

class TestAuthInference:
    @patch("inference_service.main.client", new_callable=AsyncMock)
    @patch("inference_service.main.rag", new_callable=AsyncMock)
    def test_auth_inference_valid(self, mock_rag, mock_client, mock_jwt_auth, client):
        mock_rag_resp = AsyncMock()
        mock_rag_resp.content = "Valid conversation."
        mock_rag.return_value = mock_rag_resp

        mock_history_resp = MagicMock()
        mock_history_resp.status_code = 200
        mock_history_resp.json.return_value = {
            "messages": [
                {"role": "assistant", "content": [{"type": "text", "text": "Past message"}]}
            ]
        }
        mock_history_resp.raise_for_status.return_value = None
        mock_history_resp.headers = {}
        mock_client.get.return_value = mock_history_resp

        mock_save_message_resp = MagicMock()
        mock_save_message_resp.status_code = 200
        mock_save_message_resp.raise_for_status.return_value = None  # Sync mock
        mock_client.post.return_value = mock_save_message_resp

        payload = {
            "user_query": {"role": "user", "content": [{"type": "text", "text": "Describe this image."}]},
            "user_id": "123",
            "chat_id": "456"
        }

        response = client.post("/auth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["answer"] == "Valid conversation."
        
        mock_rag.assert_called_once()
        mock_client.get.assert_called_once_with(
            f"{USER_SERVICE_URL}/chat/123/456",
            headers=ANY
        )
        assert mock_client.post.call_count == 2

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