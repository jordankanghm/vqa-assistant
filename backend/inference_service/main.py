# Run using: uvicorn inference_service.main:app --reload --port 8001
import base64
import httpx
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, field_validator, HttpUrl, model_validator
from typing import List, Union

client, llm = None, None
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global client, llm
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    # Instantiate LLM
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    llm = ChatOpenAI(model="o4-mini", openai_api_key=openai_api_key, temperature=1)

    yield

    # Shutdown
    await client.aclose()
    print("HTTP client closed")

system_msg = "You are a helpful visual question answering assistant."

app = FastAPI(lifespan=lifespan)

RAG_SERVICE_URL = os.getenv(
    "RAG_SERVICE_URL",
    "http://localhost:8002"
)

USER_SERVICE_URL = os.getenv(
    "USER_SERVICE_URL",
    "http://localhost:8003"
)

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

# Helper function to convert ChatMessage to LangChain HumanMessage
def convert_messages_to_langchain(messages: List[ChatMessage]):
    lc_messages = []
    for msg in messages:
        parts = []

        for c in msg.content:
            if c.type == "text":
                parts.append(c.text)

            elif c.type == "image_url":
                # Include image URL inline markdown for o4-mini to parse
                parts.append(f"![image]({c.image_url})")

            elif c.type == "image_base64":
                # Convert base64 string to inline markdown image
                parts.append(f"![image]({c.image_base64.base64})")

        full_content = "\n".join(parts)

        if msg.role == "user":
            lc_messages.append(HumanMessage(content=full_content))

        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=full_content))

    return lc_messages

async def rag(user_text, messages):
    rag_context = "No relevant context found."

    if user_text:  # No RAG for image-only queries
        try:
            rag_response = await client.post(
                f"{RAG_SERVICE_URL}/search",
                json={"query": user_text, "top_k": 3, "min_similarity": 0.5}
            )
            rag_response.raise_for_status()
            data = rag_response.json()

            if data["count"] > 0:
                rag_context = "\n\n".join([f"{chunk['text']}" for chunk in data["chunks"]])

        except Exception as e:
            print(f"RAG service error: {e}")
    
    # LLM with RAG context
    lc_msgs = convert_messages_to_langchain(messages)
    rag_prompt = system_msg + f"Use this context: {rag_context}\n\n"
    conversation = [SystemMessage(content=rag_prompt)] + lc_msgs
    response = await llm.ainvoke(conversation)
    
    return response

@app.post("/unauth-inference", response_model=InferenceResponse)
async def unauth_inference(req: UnauthInferenceRequest):
    # Extract user query from latest message
    user_query = ""
    for content in req.messages[-1].content:
        if content.type == "text":
            user_query += content.text

    try:
        response = await rag(user_query, req.messages)

    except Exception as e:
            print(f"RAG service error: {e}")
    
    return InferenceResponse(answer=response.content)

@app.post("/auth-inference", response_model=InferenceResponse)
async def auth_inference(
    req: AuthInferenceRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
    messages = [req.user_query]

    headers = {
        "Authorization": f"Bearer {credentials.credentials}"
    }
    
    history_response = await client.get(
        f"{USER_SERVICE_URL}/chat/{req.user_id}/{req.chat_id}", 
        headers=headers
    )

    history_response.raise_for_status()
    history_data = history_response.json()
    history_messages = history_data.get("messages", [])

    normalized_history = []

    for msg_dict in history_messages:
        normalized_history.append(ChatMessage.model_validate(msg_dict.copy()))
        
    messages = normalized_history + [req.user_query]

    # Save user query
    try:
        user_response = await client.post(
            f"{USER_SERVICE_URL}/chat/{req.user_id}/{req.chat_id}/messages",
            headers=headers,
            json=req.user_query.model_dump()
        )
        user_response.raise_for_status()

    except Exception as e:
        print(f"Failed to save user message: {e}")

    # Extract user query from latest message
    user_text = ""
    for content in req.user_query.content:
        if content.type == "text":
            user_text += content.text
    
    response = None
    
    try:
        response = await rag(user_text, messages)
    except Exception as e:
            print(f"RAG service error: {e}")

    # Save chatbot response
    assistant_msg = ChatMessage(
        role="assistant",
        content=[TextContent(type="text", text=response.content)]
    )

    try:
        assistant_response = await client.post(
            f"{USER_SERVICE_URL}/chat/{req.user_id}/{req.chat_id}/messages",
            headers=headers,
            json=assistant_msg.model_dump()
        )
        assistant_response.raise_for_status()

    except Exception as e:
        print(f"Failed to save assistant message: {e}")

    return InferenceResponse(answer=response.content)