import base64
import httpx
import os
from fastapi import FastAPI
from langchain.chat_models import ChatOpenAI
from langchain.schema.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, field_validator, model_validator, HttpUrl
from typing import List, Union

# Instantiate LLM
openai_api_key = os.environ.get("OPENAI_API_KEY")
llm = ChatOpenAI(model="o4-mini", openai_api_key=openai_api_key, temperature=1)

system_msg = SystemMessage(content="You are a helpful visual question answering assistant.")

app = FastAPI()

client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

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

class InferenceRequest(BaseModel):
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

@app.post("/inference", response_model=InferenceResponse)
async def inference(req: InferenceRequest):
    lc_msgs = convert_messages_to_langchain(req.messages)
    conversation = [system_msg] + lc_msgs
    response = llm(conversation)

    return InferenceResponse(answer=response.content)

# Run using uvicorn inference_service:app --reload --port 8001
