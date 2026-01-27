# Run in root directory using: pytest backend/integration/test_integration.py -v

import os
import pytest
import requests
import time

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8000")
INFERENCE_SERVICE_URL = os.environ.get("INFERENCE_SERVICE_URL", "http://localhost:8001")
RAG_SERVICE_URL = os.environ.get("RAG_SERVICE_URL", "http://localhost:8002")
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://localhost:8003")

# User authentication test variables
TEST_USER = "integration_test_user"
TEST_EMAIL = "integration_test@example.com"
TEST_PASSWORD = "testpass123"

@pytest.fixture(scope="module", autouse=True)
def setup():
    """Wait for services + insert test data."""
    
    # Wait for services
    for _ in range(30):
        try:
            if (requests.get(f"{GATEWAY_URL}/docs", timeout=2).ok and
                requests.get(f"{INFERENCE_SERVICE_URL}/docs", timeout=2).ok and
                requests.get(f"{RAG_SERVICE_URL}/docs", timeout=2).ok and
                requests.get(f"{USER_SERVICE_URL}/docs", timeout=2).ok):
                break

        except:
            pass
        time.sleep(1)
    
    yield

@pytest.fixture
def auth_setup():
    """Register user once per test."""
    requests.post(f"{GATEWAY_URL}/auth/register", json={
        "username": TEST_USER,
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }, timeout=10)
    
    yield
    
    # Cleanup
    try:
        requests.delete(f"{USER_SERVICE_URL}/users/{TEST_USER}", timeout=3)
    except:
        pass
    
class TestGateway:
    # Unauthorized inference
    def test_only_text_gateway(self):
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

        response = requests.post(f"{GATEWAY_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert "paris" in data["answer"].lower()

    def test_only_image_url_gateway(self):
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

        response = requests.post(f"{GATEWAY_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_only_image_base64_gateway(self):
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

        response = requests.post(f"{GATEWAY_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_text_and_image_gateway(self):
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

        response = requests.post(f"{GATEWAY_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert "green" in data["answer"].lower()

    # Authorized inference
    def test_auth_inference_gateway(self, auth_setup):
        login_resp = requests.post(f"{GATEWAY_URL}/auth/login", json={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        }, timeout=20)
        login_json = login_resp.json()
        token = login_json["access_token"]
        user_id = login_json["user_id"]
        
        headers = {"Authorization": f"Bearer {token}"}

        chats_resp = requests.get(
            f"{GATEWAY_URL}/chats/{user_id}",
            headers=headers,
            timeout=10
        )

        assert chats_resp.status_code == 200
        chat_data = chats_resp.json()
        
        chats_list = chat_data["chats"]
        assert len(chats_list) > 0, "No chats found - check registration auto-chat creation"
        chat_id = chats_list[0]["id"]  # Use first chat

        # Auth inference test
        payload = {
            "user_query": {
                "role": "user",
                "content": [{"type": "text", "text": "What is machine learning?"}]
            },
            "user_id": user_id,
            "chat_id": chat_id
        }
        
        response = requests.post(
            f"{GATEWAY_URL}/auth-inference",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 10
        
    def test_auth_inference_no_token(self, auth_setup):
        payload = {
            "user_query": {"role": "user", "content": [{"type": "text", "text": "test"}]},
            "user_id": TEST_USER,
            "chat_id": "chat123"
        }
        
        response = requests.post(f"{GATEWAY_URL}/auth-inference", json=payload, timeout=10)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    # Login/Register
    def test_register_gateway(self, auth_setup):
        # Delete user if they exist
        requests.delete(f"{USER_SERVICE_URL}/users/{TEST_USER}", timeout=3)

        payload = {
            "username": TEST_USER,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(f"{GATEWAY_URL}/auth/register", json=payload, timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["user_id"], int)

    def test_register_duplicate_gateway(self, auth_setup):
        payload = {
            "username": TEST_USER,  # Already exists from fixture
            "email": "duplicate@example.com",
            "password": "testpass123"
        }
        
        response = requests.post(f"{GATEWAY_URL}/auth/register", json=payload, timeout=10)
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_login_gateway(self, auth_setup):
        payload = {
            "username": TEST_USER,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(f"{GATEWAY_URL}/auth/login", json=payload, timeout=20)
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 100

    def test_login_wrong_creds_gateway(self):
        # Delete user if they exist
        requests.delete(f"{USER_SERVICE_URL}/users/wronguser", timeout=3)

        payload = {
            "username": "wronguser",
            "password": "wrongpass"
        }
        
        response = requests.post(f"{GATEWAY_URL}/auth/login", json=payload, timeout=20)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

class TestInference:
    # Unauthorized inference
    def test_only_text_inference_service(self):
        payload = {
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "text",
                    "text": "What is the capital of France?"
                }]
            }]
        }

        response = requests.post(f"{INFERENCE_SERVICE_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert "paris" in data["answer"].lower()

    def test_only_image_url_inference_service(self):
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

        response = requests.post(f"{INFERENCE_SERVICE_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_only_image_base64_inference_service(self):
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

        response = requests.post(f"{INFERENCE_SERVICE_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_text_and_image_inference_service(self):
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

        response = requests.post(f"{INFERENCE_SERVICE_URL}/unauth-inference", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert "green" in data["answer"].lower()

    # Authorized inference
    def test_auth_inference_inference(self, auth_setup):
        login_resp = requests.post(f"{GATEWAY_URL}/auth/login", json={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        }, timeout=20)
        login_json = login_resp.json()
        token = login_json["access_token"]
        user_id = login_json["user_id"]
        
        headers = {"Authorization": f"Bearer {token}"}

        chats_resp = requests.get(
            f"{GATEWAY_URL}/chats/{user_id}",
            headers=headers,
            timeout=10
        )

        assert chats_resp.status_code == 200
        chat_data = chats_resp.json()
        
        chats_list = chat_data["chats"]
        assert len(chats_list) > 0, "No chats found - check registration auto-chat creation"
        chat_id = chats_list[0]["id"]  # Use first chat

        # Auth inference test
        payload = {
            "user_query": {
                "role": "user",
                "content": [{"type": "text", "text": "What is machine learning?"}]
            },
            "user_id": user_id,
            "chat_id": chat_id
        }
        
        response = requests.post(
            f"{INFERENCE_SERVICE_URL}/auth-inference",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 10
        
    def test_auth_inference_no_token(self, auth_setup):
        payload = {
            "user_query": {"role": "user", "content": [{"type": "text", "text": "test"}]},
            "user_id": TEST_USER,
            "chat_id": "chat123"
        }
        
        response = requests.post(f"{INFERENCE_SERVICE_URL}/auth-inference", json=payload, timeout=10)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

class TestRAG:
    @pytest.fixture
    def setup_test_wikipedia_data(self):
        """Insert predictable test data via your endpoints."""
        
        # Ingest test Wikipedia data
        ingest_payload = {
            "categories": ["Machine learning"],
            "limit_pages": 2
        }
        requests.post(f"{RAG_SERVICE_URL}/ingest-wikipedia", json=ingest_payload, timeout=60)
        
        time.sleep(10)
        
        # Verify data ingested
        test_query = {"query": "machine learning", "top_k": 1, "min_similarity": 0.1}
        response = requests.post(f"{RAG_SERVICE_URL}/search", json=test_query, timeout=60)
        
        if response.status_code != 200 or response.json()["count"] == 0:
            print("⚠️  Warning: Test data ingestion may have failed")
        
        print("✅ Wikipedia test data ready!")

    def test_rag_returns_chunks(self, setup_test_wikipedia_data):
        payload = {"query": "machine learning", "top_k": 3, "min_similarity": 0.1}
        response = requests.post(f"{RAG_SERVICE_URL}/search", json=payload, timeout=60)
        
        assert response.status_code == 200
        data = response.json()
        assert "chunks" in data
        assert "count" in data
        assert data["count"] >= 0
        assert len(data["chunks"]) == data["count"]

        if data["count"] > 0:
            assert all("similarity" in chunk and "text" in chunk for chunk in data["chunks"])
            assert all(0.0 < chunk["similarity"] <= 1.0 for chunk in data["chunks"])

    def test_rag_min_similarity_filtering(self):
        payload_high = {"query": "machine learning", "top_k": 5, "min_similarity": 0.8}
        payload_low = {"query": "machine learning", "top_k": 5, "min_similarity": 0.2}

        resp_high = requests.post(f"{RAG_SERVICE_URL}/search", json=payload_high, timeout=60).json()
        resp_low = requests.post(f"{RAG_SERVICE_URL}/search", json=payload_low, timeout=60).json()

        assert resp_high["count"] <= resp_low["count"]

class TestUser:
    def test_register_user(self):
        payload = {
            "username": TEST_USER,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        resp = requests.post(f"{GATEWAY_URL}/auth/register", json=payload, timeout=10)
        
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["user_id"], int)
        
        # Cleanup
        requests.delete(f"{USER_SERVICE_URL}/users/{TEST_USER}")

    def test_login_user(self, auth_setup):
        resp = requests.post(f"{GATEWAY_URL}/auth/login", json={
            "username": TEST_USER,
            "password": TEST_PASSWORD
        }, timeout=20)
        
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 100

    def test_register_duplicate(self, auth_setup):   
        resp = requests.post(f"{GATEWAY_URL}/auth/register", json={
            "username": TEST_USER,  # Same username
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"].lower()

    def test_login_wrong_username(self):
        # Delete user if they exist
        requests.delete(f"{USER_SERVICE_URL}/users/wronguser", timeout=3)
        
        resp = requests.post(f"{GATEWAY_URL}/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        }, timeout=20)
        
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect username or password"

    def test_login_wrong_password(self, auth_setup):
        resp = requests.post(f"{GATEWAY_URL}/auth/login", json={
            "username": TEST_USER,
            "password": "wrongpass"
        }, timeout=20)
        
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect username or password"
