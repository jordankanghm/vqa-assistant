from backend.gateway import app
from fastapi.testclient import TestClient
from httpx import HTTPError
from unittest.mock import patch, AsyncMock

client = TestClient(app)

@patch("backend.gateway.client.post")
def test_gateway_proxy_inference_success(mock_post):  # mock_post simulates the inference service response
    # Create a mock response object to be returned by inference service
    mock_response = AsyncMock()
    mock_response.status_code = 200

    async def mock_json():
        return {"answer": "Result", "image": None}

    mock_response.json.side_effect = mock_json
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Check that response from gateway is as expected
    response = client.post("/inference", json={"text": "test_inference"})
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Result"

@patch("backend.gateway.client.post")
def test_gateway_proxy_inference_failure(mock_post):
    async def raise_http_error(*args, **kwargs):
        raise HTTPError("HTTP failure")

    mock_post.side_effect = raise_http_error

    # Check that gateway returns 502 on inference service failure
    response = client.post("/inference", json={"text": "test_failure"})
    assert response.status_code == 502
    data = response.json()
    assert "HTTP failure" in data["detail"]
