# Run using uvicorn main:app --reload --port 8000
import base64
import httpx
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, field_validator, HttpUrl, model_validator
from starlette.responses import Response
from typing import List, Union

client = None
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global client
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    yield

    # Shutdown
    await client.aclose()
    print("HTTP client closed")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INFERENCE_SERVICE_URL = os.getenv(
    "INFERENCE_SERVICE_URL",
    "http://localhost:8001"
)

USER_SERVICE_URL = os.getenv(
    "USER_SERVICE_URL",
    "http://localhost:8003"
)

# Inference models
class TextContent(BaseModel):
    type: str
    text: str

    @field_validator("type")
    def type_must_be_text(cls, v):
        if v != "text":
            raise ValueError('type must be "text"')
        
        return v

class ImageUrlInner(BaseModel):
    url: HttpUrl

class ImageUrlContent(BaseModel):
    type: str
    image_url: ImageUrlInner

    @field_validator("type")
    def must_be_image_url(cls, v):
        if v != "image_url":
            raise ValueError('type must be "image_url"')
        
        return v

class ImageBase64Inner(BaseModel):
    base64: str
    @field_validator("base64")
    def must_be_valid_base64_image(cls, v):
        if not v.startswith("data:image/"):
            raise ValueError("base64_str must start with 'data:image/' prefix")
        
        try:
            # Separate metadata and base64 data parts
            header, base64_data = v.split(",", 1)

        except ValueError:
            raise ValueError("base64_str must contain a comma separating header and data")

        # Verify mime type part e.g., data:image/png;base64
        if not header.endswith(";base64"):
            raise ValueError("base64_str header must end with ';base64'")

        # Validate base64 encoding correctness by decoding
        try:
            base64.b64decode(base64_data, validate=True)

        except Exception:
            raise ValueError("base64_str contains invalid base64 encoded data")
        
        return v

class ImageBase64Content(BaseModel):
    type: str
    image_base64: ImageBase64Inner

    @field_validator("type")
    def must_be_base64_image(cls, v):
        if v != "image_base64":
            raise ValueError('type must be "image_base64"')
        
        return v

ContentItem = Union[TextContent, ImageUrlContent, ImageBase64Content]

class ChatMessage(BaseModel):
    role: str
    content: List[ContentItem]

    @model_validator(mode="after")
    def check_content_not_empty(cls, model):
        if not model.content or len(model.content) == 0:
            raise ValueError("content must have at least one item")
        
        return model

class UnauthInferenceRequest(BaseModel):
    messages: List[ChatMessage]

    @model_validator(mode="after")
    def validate_messages(cls, model):
        messages = model.messages
        if not messages or len(messages) == 0:
            raise ValueError("At least one message is required.")
        
        # No system role allowed
        if any(m.role == "system" for m in messages):
            raise ValueError("Messages with role 'system' are not allowed in the request.")
        
        # Enforce alternating roles: user -> assistant -> user -> assistant ...
        for i, m in enumerate(messages):
            if i % 2 == 0 and m.role != "user":
                raise ValueError(f"Message at position {i} should have role 'user'.")
            
            if i % 2 == 1 and m.role != "assistant":
                raise ValueError(f"Message at position {i} should have role 'assistant'.")
            
        return model

class AuthInferenceRequest(BaseModel):
    user_query: ChatMessage
    user_id: int
    chat_id: int

    @model_validator(mode="after")
    def validate_user_query(cls, model):
        if model.user_query.role != "user":
            raise ValueError("user_query must have role 'user'")
        
        return model

class InferenceResponse(BaseModel):
    answer: str

# User authentication models
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
@app.post("/unauth-inference")
async def proxy_unauth_inference(req: UnauthInferenceRequest): 
    response = await client.post(f"{INFERENCE_SERVICE_URL}/unauth-inference", json=req.model_dump(mode="json"))

    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )

@app.post("/auth-inference")
async def proxy_auth_inference(
    req: AuthInferenceRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
    headers = {
        "Authorization": f"Bearer {credentials.credentials}"
    }
    
    response = await client.post(
        f"{INFERENCE_SERVICE_URL}/auth-inference", 
        headers=headers,
        json=req.model_dump()
    )
    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
        )

@app.get("/chats/{user_id}")
async def get_user_chats(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
    headers = {
        "Authorization": f"Bearer {credentials.credentials}"
    }

    response = await client.get(
        f"{USER_SERVICE_URL}/chats/{user_id}", 
        headers=headers
    )

    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
        )

@app.post("/chats/{user_id}")
async def create_user_chat(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    headers = {
        "Authorization": f"Bearer {credentials.credentials}"
    }

    response = await client.post(
        f"{USER_SERVICE_URL}/chats/{user_id}", 
        headers=headers
    )

    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )

@app.get("/chat/{user_id}/{chat_id}")
async def get_chat_history(
    user_id: int, 
    chat_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    headers = {
        "Authorization": f"Bearer {credentials.credentials}"
    }

    response = await client.get(
        f"{USER_SERVICE_URL}/chat/{user_id}/{chat_id}", 
        headers=headers
    )
    
    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )

@app.post("/auth/register")
async def proxy_register(req: RegisterRequest):
    response = await client.post(f"{USER_SERVICE_URL}/register", json=req.model_dump())

    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )

@app.post("/auth/login", response_model=Token)
async def proxy_login(req: LoginRequest):
    response = await client.post(f"{USER_SERVICE_URL}/login", json=req.model_dump())

    return Response(
        content=await response.aread(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )