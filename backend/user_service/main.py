# Run in current directory using: uvicorn main:app --reload --port 8003
import asyncpg
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator, HttpUrl, model_validator
from typing import List, Optional, Union

security = HTTPBearer()

load_dotenv()  # Load .env file
AUTH_DATABASE_URL = os.environ.get("AUTH_DATABASE_URL")
AUTH_SECRET_KEY = os.environ.get("AUTH_SECRET_KEY")
ALGORITHM = os.environ.get("AUTH_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pool: Optional[asyncpg.Pool] = None

class PostgresPool:
    async def connect(self):
        global pool
        pool = await asyncpg.create_pool(AUTH_DATABASE_URL)

    async def disconnect(self):
        if pool:
            await pool.close()

postgres_pool = PostgresPool()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await postgres_pool.connect()
    await init_db()

    yield

    await postgres_pool.disconnect()
        
app = FastAPI(title="Authentication Service",
              version="1.0.0",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class DeleteUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)

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
    
class SaveMessageRequest(BaseModel):
    role: str  # "user" or "assistant"
    content: list  # List[ContentItem]

async def init_db():
    async with pool.acquire() as conn:
        # Create table for user authentication details
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create table for chats
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create table for chat history
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER REFERENCES chats(id),
                role TEXT NOT NULL,  -- 'user' or 'assistant'
                content JSONB NOT NULL,  -- Array of ContentItem
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

async def get_user(username: str) -> Optional[dict]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)

        if row:
            return {"id": row["id"], "username": row["username"], "email": row["email"], "hashed_password": row["hashed_password"]}
        
        return None

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    encoded = jwt.encode(to_encode, AUTH_SECRET_KEY, ALGORITHM)

    return encoded

@app.post("/register", response_model=dict)
async def register(req: RegisterRequest):
    user = await get_user(req.username)

    if user:
        raise HTTPException(400, "Username already registered")
    
    hashed = hash_password(req.password)
    user_id = None

    async with pool.acquire() as conn:
        try:
            user_result = await conn.fetchrow(
                "INSERT INTO users (username, email, hashed_password) VALUES ($1, $2, $3) RETURNING id",
                req.username, req.email, hashed
            )

            user_id = user_result["id"]
            
            # Auto-create default chat
            await conn.execute(
                "INSERT INTO chats (user_id, title) VALUES ($1, $2)",
                user_id, "Welcome Chat"
            )

        except asyncpg.UniqueViolationError:
            raise HTTPException(400, "Username or email already registered")

    return {"user_id": user_id}

@app.post("/login")
async def login(req: LoginRequest):
    user = await get_user(req.username)

    if not user or not verify_password(req.password, user["hashed_password"]):  # Reject if invalid user or wrong password
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"user_id": user["id"]})
    
    return {"access_token": access_token, "token_type": "bearer", "user_id": user["id"]}

@app.delete("/users/{username}")
async def delete_user(username: str = Path(..., min_length=3, max_length=50)):
    """Delete user + all their chats/messages (cascade)."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Delete chat_messages
            await conn.execute("""
                DELETE FROM chat_messages 
                WHERE chat_id IN (
                    SELECT id FROM chats WHERE user_id = (SELECT id FROM users WHERE username = $1)
                )
            """, username)
            
            # Delete chats
            await conn.execute("""
                DELETE FROM chats 
                WHERE user_id = (SELECT id FROM users WHERE username = $1)
            """, username)
            
            # Delete user
            result = await conn.execute(
                "DELETE FROM users WHERE username = $1", username
            )
            
            if result == "DELETE 0":
                raise HTTPException(404, "User not found")
    
    return {"deleted": username}

@app.get("/chats/{user_id}")
async def get_user_chats(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
    async with pool.acquire() as conn:
        chats = await conn.fetch("""
            SELECT c.id, c.title, c.created_at, 
                COUNT(cm.id) as message_count
            FROM chats c LEFT JOIN chat_messages cm ON c.id = cm.chat_id 
            WHERE c.user_id = $1 GROUP BY c.id ORDER BY c.created_at DESC
        """, user_id)

    return {"chats": [dict(chat) for chat in chats]}

@app.post("/chats/{user_id}")
async def create_user_chat(
    user_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    async with pool.acquire() as conn:
        # Verify user exists
        user = await conn.fetchrow("SELECT id FROM users WHERE id = $1", user_id)

        if not user:
            raise HTTPException(404, "User not found")
        
        result = await conn.fetchrow(
            """
            INSERT INTO chats (user_id, title) 
            VALUES ($1, $2) 
            RETURNING id, title, created_at
            """, 
            user_id, "New Chat"
        )
        
        return {"id": result["id"], "title": result["title"], "created_at": result["created_at"]}
    
@app.get("/chat/{user_id}/{chat_id}")
async def get_chat_history(
    user_id: int,
    chat_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
    async with pool.acquire() as conn:
        # Verify ownership
        chat = await conn.fetchrow("SELECT * FROM chats WHERE id = $1 AND user_id = $2", chat_id, user_id)
        if not chat:
            raise HTTPException(404, "Chat not found")
        
        messages = await conn.fetch("""
            SELECT role, content, created_at as timestamp FROM chat_messages 
            WHERE chat_id = $1 ORDER BY created_at ASC
        """, chat_id)

        parsed_messages = []

        for m in messages:
            msg_dict = dict(m)
            msg_dict['content'] = json.loads(msg_dict['content'])
            parsed_messages.append(msg_dict)
        
    return {"messages": parsed_messages}

@app.post("/chat/{user_id}/{chat_id}/messages")
async def save_chat_message(
    user_id: int,
    chat_id: int,
    chat_message: ChatMessage,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    async with pool.acquire() as conn:
        chat = await conn.fetchrow(
            "SELECT id FROM chats WHERE id = $1 AND user_id = $2", 
            chat_id, user_id
        )

        if not chat:
            raise HTTPException(404, "Chat not found")

        content_serialized = [item.model_dump() for item in chat_message.content]
        content_json = json.dumps(content_serialized)

        # Insert message
        await conn.execute(
            """
            INSERT INTO chat_messages (chat_id, role, content)
            VALUES ($1, $2, $3)
            """,
            chat_id, chat_message.role, content_json
        )
    
    return {"status": "saved"}