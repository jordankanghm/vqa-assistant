# Run in root directory using: pytest backend/integration/test_integration.py -v

import pytest
import requests
import time

GATEWAY_URL = "http://localhost:8000/inference"
INFERENCE_URL = "http://localhost:8001/inference"
DB_URL = "http://localhost:8002/search"

@pytest.fixture(scope="session", autouse=True)
def wait_for_backend_ready():
    # Wait for backend services to be ready before running tests
    for _ in range(30):  # wait up to 30 secs
        try:
            res_gateway = requests.get("http://localhost:8000/docs", timeout=10)
            res_inference = requests.get("http://localhost:8001/docs", timeout=10)
            res_db = requests.get("http://localhost:8002/docs", timeout=10)

            if res_gateway.ok and res_inference.ok and res_db.ok:
                return
            
        except requests.exceptions.RequestException:
            pass

        time.sleep(1)

    pytest.fail("Backend services not ready")

# Gateway tests
def test_only_text_gateway(wait_for_backend_ready):
    payload = {
        "messages": [
            {
                "role": "user", 
                "content": [{
                    "type": "text",
                    "text": "What is the capital of France?"
                }]
            }
        ]
    }

    response = requests.post(GATEWAY_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "paris" in data["answer"].lower()

def test_only_image_url_gateway(wait_for_backend_ready):
    img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    payload = {
        "messages": [{
            "role": "user", 
            "content": [{
                "type": "image_url", 
                "image_url": {
                    "url": img_url
                }
            }]
        }]
    }

    response = requests.post(GATEWAY_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)

def test_only_image_base64_gateway(wait_for_backend_ready):
    img_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    payload = {
        "messages": [{
            "role": "user", 
            "content": [{
                "type": "image_base64", 
                "image_base64": {
                    "base64": img_base64
                }
            }]
        }]
    }

    response = requests.post(GATEWAY_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)

def test_text_and_image_gateway(wait_for_backend_ready):
    img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    payload = {
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text", 
                    "text": "Name me the main colours present in this image."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_url
                    }
                }
            ]
        }]
    }

    response = requests.post(GATEWAY_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "green" in data["answer"].lower()

# Inference Service tests
def test_only_text_inference_service(wait_for_backend_ready):
    payload = {
        "messages": [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": "What is the capital of France?"
            }]
        }]
    }

    response = requests.post(INFERENCE_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "paris" in data["answer"].lower()

def test_only_image_url_inference_service(wait_for_backend_ready):
    img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    payload = {
        "messages": [{
            "role": "user", 
            "content": [{
                "type": "image_url",
                "image_url": {
                    "url": img_url
                }
            }]
        }]
    }

    response = requests.post(INFERENCE_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)

def test_only_image_base64_inference_service(wait_for_backend_ready):
    img_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    payload = {
        "messages": [{
            "role": "user", 
            "content": [{
                "type": "image_base64",
                "image_base64": {
                    "base64": img_base64
                }
            }]
        }]
    }

    response = requests.post(INFERENCE_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)

def test_text_and_image_inference_service(wait_for_backend_ready):
    img_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    payload = {
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Name me the main colours present in this image."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": img_url
                    }
                }
            ]
        }]
    }

    response = requests.post(INFERENCE_URL, json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "green" in data["answer"].lower()

# DB Service tests
def test_db_returns_chunks(wait_for_backend_ready):
    """Test DB service returns searchable chunks."""
    payload = {"query": "machine learning", "top_k": 3, "min_similarity": 0.1}
    response = requests.post(DB_URL, json=payload, timeout=10)
    
    assert response.status_code == 200
    data = response.json()
    assert "chunks" in data
    assert "count" in data
    assert data["count"] >= 0
    assert len(data["chunks"]) == data["count"]
    
    if data["count"] > 0:
        assert all("similarity" in chunk and "text" in chunk for chunk in data["chunks"])
        assert all(0.0 < chunk["similarity"] <= 1.0 for chunk in data["chunks"])


def test_db_min_similarity_filtering(wait_for_backend_ready):
    """Test DB respects min_similarity threshold."""
    payload_high = {"query": "machine learning", "top_k": 5, "min_similarity": 0.8}
    payload_low = {"query": "machine learning", "top_k": 5, "min_similarity": 0.2}

    resp_high = requests.post(DB_URL, json=payload_high, timeout=10).json()
    resp_low = requests.post(DB_URL, json=payload_low, timeout=10).json()
    
    assert resp_high["count"] <= resp_low["count"]