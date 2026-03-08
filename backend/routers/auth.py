"""Authentication routes: register, login, me."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from backend.models.schemas import UserCreate, UserLogin, UserResponse, Token
from backend.services.auth import (
    hash_password, verify_password, create_access_token, get_current_user, generate_user_id
)
from backend.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=201)
async def register(user: UserCreate, db: aiosqlite.Connection = Depends(get_db)):
    # Check existing
    cursor = await db.execute(
        "SELECT id FROM users WHERE email = ? OR username = ?",
        (user.email, user.username),
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=409, detail="Email or username already exists")

    user_id = generate_user_id()
    hashed = hash_password(user.password)
    await db.execute(
        "INSERT INTO users (id, email, username, hashed_password) VALUES (?, ?, ?, ?)",
        (user_id, user.email, user.username, hashed),
    )
    await db.commit()

    token = create_access_token(user_id, user.username)
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, username, hashed_password, is_active FROM users WHERE username = ?",
        (credentials.username,),
    )
    row = await cursor.fetchone()
    if not row or not verify_password(credentials.password, row["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(row["id"], row["username"])
    return Token(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    cursor = await db.execute(
        "SELECT id, email, username, created_at FROM users WHERE id = ?",
        (current_user["id"],),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=row["id"], email=row["email"],
        username=row["username"], created_at=str(row["created_at"]),
    )
