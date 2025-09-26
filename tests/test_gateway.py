import pytest
from backend.gateway import app
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock

client = TestClient(app)

@patch("backend.gateway.client.post", new_callable=AsyncMock)
def test_gateway_with_valid_alternating(mock_post):
    mock_response = AsyncMock()
    mock_response.json = lambda: {"answer": "Valid conversation."}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    valid_alternating_messages = [
        {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Hi, how can I help?"}]},
        {"role": "user", "content": [{"type": "text", "text": "Describe this image."}]}
    ]

    response = client.post("/inference", json={"messages": valid_alternating_messages})

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
])
@patch("backend.gateway.client.post", new_callable=MagicMock)
def test_gateway_invalid_payloads(mock_post, invalid_payload):
    mock_post.return_value = MagicMock(choices=[])
    response = client.post("/inference", json=invalid_payload)
    assert response.status_code == 422
