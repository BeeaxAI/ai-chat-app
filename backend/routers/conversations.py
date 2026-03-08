"""Conversation management routes."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite

from backend.models.schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse, MessageResponse
)
from backend.services.auth import get_current_user
from backend.database import get_db

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    archived: bool = False,
    search: str = Query(default=None, max_length=200),
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    query = """
        SELECT c.*, COUNT(m.id) as message_count
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        WHERE c.user_id = ? AND c.is_archived = ?
    """
    params = [current_user["id"], int(archived)]

    if search:
        query += " AND (c.title LIKE ? OR c.id IN (SELECT conversation_id FROM messages WHERE content LIKE ?))"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " GROUP BY c.id ORDER BY c.updated_at DESC LIMIT 100"

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [
        ConversationResponse(
            id=r["id"], title=r["title"], provider=r["provider"],
            model=r["model"], system_prompt=r["system_prompt"] or "",
            created_at=str(r["created_at"]), updated_at=str(r["updated_at"]),
            is_archived=bool(r["is_archived"]), message_count=r["message_count"],
        )
        for r in rows
    ]


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO conversations (id, user_id, title, provider, model, system_prompt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (conv_id, current_user["id"], data.title, data.provider, data.model, data.system_prompt, now, now),
    )
    await db.commit()
    return ConversationResponse(
        id=conv_id, title=data.title, provider=data.provider,
        model=data.model, system_prompt=data.system_prompt or "",
        created_at=now, updated_at=now, is_archived=False, message_count=0,
    )


@router.get("/{conv_id}", response_model=ConversationResponse)
async def get_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    cursor = await db.execute(
        """SELECT c.*, COUNT(m.id) as message_count
        FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id
        WHERE c.id = ? AND c.user_id = ? GROUP BY c.id""",
        (conv_id, current_user["id"]),
    )
    r = await cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse(
        id=r["id"], title=r["title"], provider=r["provider"],
        model=r["model"], system_prompt=r["system_prompt"] or "",
        created_at=str(r["created_at"]), updated_at=str(r["updated_at"]),
        is_archived=bool(r["is_archived"]), message_count=r["message_count"],
    )


@router.patch("/{conv_id}", response_model=ConversationResponse)
async def update_conversation(
    conv_id: str,
    data: ConversationUpdate,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    # Build dynamic update
    updates = []
    params = []
    for field, value in data.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ?")
        params.append(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).isoformat())
    params.extend([conv_id, current_user["id"]])

    await db.execute(
        f"UPDATE conversations SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
        params,
    )
    await db.commit()
    return await get_conversation(conv_id, current_user, db)


@router.delete("/{conv_id}", status_code=204)
async def delete_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    result = await db.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, current_user["id"]),
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    # Verify ownership
    cursor = await db.execute(
        "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, current_user["id"]),
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Conversation not found")

    cursor = await db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conv_id,),
    )
    rows = await cursor.fetchall()
    return [
        MessageResponse(
            id=r["id"], conversation_id=r["conversation_id"],
            role=r["role"], content=r["content"],
            model=r["model"], created_at=str(r["created_at"]),
        )
        for r in rows
    ]
