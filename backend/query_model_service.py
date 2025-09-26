import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl, model_validator, field_validator
from typing import List, Union, Dict
from openai import OpenAI

load_dotenv()  # Load environment variables

api_key = os.getenv("OPENROUTER_API_KEY")

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=api_key,
)

app = FastAPI()

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
    def type_must_be_image_url(cls, v):
        if v != "image_url":
            raise ValueError('type must be "image_url"')
        return v

ContentItem = Union[TextContent, ImageUrlContent]

class ChatMessage(BaseModel):
    role: str
    content: List[ContentItem]

    @model_validator(mode="after")
    def check_content_not_empty(cls, model):
        if not model.content or len(model.content) == 0:
            raise ValueError("content must have at least one item")
        return model

class QueryRequest(BaseModel):
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


class QueryResponse(BaseModel):
    answer: str

@app.post("/query_model", response_model=QueryResponse)
async def query_model(req: QueryRequest):    
    system_message = ChatMessage(
        role="system",
        content=[{"type": "text", "text": "You are a helpful assistant that answers questions about images."}]
    )

    # Prepend system message to the conversation
    messages = [system_message.model_dump(mode="json")] + [m.model_dump(mode="json") for m in req.messages]

    # Pass full chat history to LLM
    completion = client.chat.completions.create(
        extra_body={},
        model="x-ai/grok-4-fast:free",
        messages=messages
    )
    answer = completion.choices[0].message.content

    return QueryResponse(answer=answer)

# Run using uvicorn query_model_service:app --reload --port 8002