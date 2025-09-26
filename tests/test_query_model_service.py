import pytest
from backend.query_model_service import app
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

client = TestClient(app)

@patch("backend.query_model_service.client.chat.completions.create", new_callable=MagicMock)
def test_query_model_with_valid_alternating(mock_create):
    valid_alternating_messages = [
        {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Hi, how can I help?"}]},
        {"role": "user", "content": [{"type": "text", "text": "Describe this image."}]}
    ]
    
    mock_choice = MagicMock()
    mock_choice.message.content = "Valid conversation."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_create.return_value = mock_response

    response = client.post("/query_model", json={"messages": valid_alternating_messages})

    assert response.status_code == 200
    assert response.json()["answer"] == "Valid conversation."


@pytest.mark.parametrize("invalid_payload", [
    {"messages": [{"role": "user"}]},  # Missing content
    {"messages": [{"content": [{"type": "text", "text": "Hello"}]}]},  # Missing role
    {"messages": [{"role": 123, "content": [{"type": "text", "text": "Hello"}]}]},  # role not string
    {"messages": [{"role": "user", "content": 42}]},  # content wrong type
    {"messages": "not a list"},  # messages wrong type
    {},  # messages missing
    {"messages": []},  # empty list
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
    {"messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "ftp://invalid-url.com/image.jpg"}}
            ]
        }
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
@patch("backend.query_model_service.client.chat.completions.create", new_callable=MagicMock)
def test_query_model_invalid_payloads(mock_create, invalid_payload):
    mock_create.return_value = MagicMock(choices=[])
    response = client.post("/query_model", json=invalid_payload)
    assert response.status_code == 422
