import subprocess
import time
import requests
import pytest

GATEWAY_URL = "http://localhost:8000/inference"

@pytest.fixture(scope="session", autouse=True)
def wait_for_backend_ready():
    # Wait for backend services to be ready before running tests
    for _ in range(60):  # wait up to 30 secs
        try:
            res1 = requests.get("http://localhost:8000/docs", timeout=2)
            res2 = requests.get("http://localhost:8001/docs", timeout=2)
            if res1.ok and res2.ok:
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    pytest.fail("Backend services not ready")

def test_only_text(wait_for_backend_ready):
    payload = {"text": "Hello"}
    response = requests.post(GATEWAY_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "LangChain result for: Hello"
    assert data["image"] is None


def test_only_image(wait_for_backend_ready):
    img_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII="
    payload = {"image": img_data}
    response = requests.post(GATEWAY_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "LangChain result for:" in data["answer"]
    assert data["image"] == img_data

def test_text_and_image(wait_for_backend_ready):
    img_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8Xw8AAoMBgQLOSTgAAAAASUVORK5CYII="
    payload = {"text": "Hello", "image": img_data}
    response = requests.post(GATEWAY_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "LangChain result for: Hello"
    assert data["image"] == img_data
