from backend.inference_service import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_inference_endpoint_success():
    response = client.post("/inference", json={"text": "Hello", "image": None})

    # Check that response is as expected for only text input
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "LangChain result for: Hello"
    assert data.get("image") is None

def test_inference_with_image():
    sample_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
    response = client.post("/inference", json={"text": "Describe image", "image": sample_image})
    
    # Check that response is as expected for text and image input
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "LangChain result for: Describe image"
    assert data["image"] == sample_image

def test_inference_with_only_image():
    sample_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA"
    response = client.post("/inference", json={"image": sample_image})

    # Check that response is as expected for only image input
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] == "LangChain result for: None"
    assert data["image"] == sample_image
