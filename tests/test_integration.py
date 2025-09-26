import pytest
import requests
import time

GATEWAY_URL = "http://localhost:8000/inference"
INFERENCE_URL = "http://localhost:8001/inference"
QUERY_MODEL_URL = "http://localhost:8002/query_model"

@pytest.fixture(scope="session", autouse=True)
def wait_for_backend_ready():
    # Wait for backend services to be ready before running tests
    for _ in range(30):  # wait up to 30 secs
        try:
            res_gateway = requests.get("http://localhost:8000/docs", timeout=10)
            res_inference = requests.get("http://localhost:8001/docs", timeout=10)
            res_query_model = requests.get("http://localhost:8002/docs", timeout=10)
            if res_gateway.ok and res_inference.ok and res_query_model.ok:
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
                    "text": "What is your name?"
                }]
            }
        ]
    }

    response = requests.post(GATEWAY_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "grok" in data["answer"].lower()

def test_only_image_gateway(wait_for_backend_ready):
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
def test_gateway_invalid_payloads(invalid_payload):
    response = requests.post(GATEWAY_URL, json=invalid_payload)
    assert response.status_code == 422

# Inference Service tests
def test_only_text_inference_service(wait_for_backend_ready):
    payload = {
        "messages": [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": "What is your name?"
            }]
        }]
    }
    response = requests.post(INFERENCE_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "grok" in data["answer"].lower()

def test_only_image_inference_service(wait_for_backend_ready):
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
def test_inference_service_invalid_payloads(invalid_payload):
    response = requests.post(INFERENCE_URL, json=invalid_payload)
    assert response.status_code == 422

# Query Model Service tests
def test_only_text_query_model(wait_for_backend_ready):
    payload = {
        "messages": [{
            "role": "user",
            "content": [{
                "type": "text",
                "text": "What is your name?"
            }]
        }]
    }
    response = requests.post(QUERY_MODEL_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "grok" in data["answer"].lower()

def test_only_image_query_model(wait_for_backend_ready):
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

    response = requests.post(QUERY_MODEL_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)

def test_text_and_image_query_model(wait_for_backend_ready):
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

    response = requests.post(QUERY_MODEL_URL, json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert "green" in data["answer"].lower()

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
def test_query_model_invalid_payloads(invalid_payload):
    response = requests.post(QUERY_MODEL_URL, json=invalid_payload)
    assert response.status_code == 422
