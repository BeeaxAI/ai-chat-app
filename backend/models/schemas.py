"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# --- Auth ---
class UserCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Conversations ---
class ConversationCreate(BaseModel):
    title: Optional[str] = "New Chat"
    provider: Optional[str] = "anthropic"
    model: Optional[str] = "claude-sonnet-4-20250514"
    system_prompt: Optional[str] = ""


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    is_archived: Optional[bool] = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    provider: str
    model: str
    system_prompt: str
    created_at: str
    updated_at: str
    is_archived: bool
    message_count: Optional[int] = 0


# --- Messages ---
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    model: Optional[str] = None
    created_at: str


# --- Chat ---
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=100000)
    conversation_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=4096, ge=1, le=8192)


# --- Provider Info ---
class ProviderModel(BaseModel):
    id: str
    name: str
    max_tokens: int


class ProviderInfo(BaseModel):
    id: str
    name: str
    available: bool
    models: List[ProviderModel]
