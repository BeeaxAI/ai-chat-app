"""Chat streaming route with multi-provider support."""
import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import aiosqlite

from backend.models.schemas import ChatRequest
from backend.services.auth import get_current_user
from backend.services.llm_providers import stream_chat, get_available_providers, get_api_key
from backend.database import get_db
from backend.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/providers")
async def list_providers():
    return get_available_providers()


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: aiosqlite.Connection = Depends(get_db),
):
    provider = request.provider or settings.DEFAULT_PROVIDER
    model = request.model or settings.DEFAULT_MODEL

    # Validate provider has API key
    if not get_api_key(provider):
        raise HTTPException(
            status_code=400,
            detail=f"No API key configured for provider: {provider}. Set the appropriate env variable.",
        )

    # Get or create conversation
    conv_id = request.conversation_id
    system_prompt = request.system_prompt or ""

    if conv_id:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, current_user["id"]),
        )
        conv = await cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if not system_prompt:
            system_prompt = conv["system_prompt"] or ""
    else:
        conv_id = str(uuid.uuid4())
        # Auto-title from first message (truncated)
        title = request.message[:80].strip()
        if len(request.message) > 80:
            title += "..."
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO conversations (id, user_id, title, provider, model, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (conv_id, current_user["id"], title, provider, model, system_prompt, now, now),
        )
        await db.commit()

    # Save user message
    user_msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, 'user', ?, ?)",
        (user_msg_id, conv_id, request.message, now),
    )
    await db.commit()

    # Load conversation history
    cursor = await db.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
        (conv_id,),
    )
    rows = await cursor.fetchall()
    messages = [{"role": r["role"], "content": r["content"]} for r in rows]

    # Prepare streaming response
    async def generate():
        full_response = []
        assistant_msg_id = str(uuid.uuid4())

        # Send conversation metadata first
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conv_id})}\n\n"

        async for chunk in stream_chat(
            provider=provider,
            messages=messages,
            model=model,
            system_prompt=system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            parsed = json.loads(chunk)
            if parsed["type"] == "text":
                full_response.append(parsed["content"])
            yield f"data: {chunk}\n\n"

        # Save assistant message
        content = "".join(full_response)
        if content:
            msg_now = datetime.now(timezone.utc).isoformat()
            async with aiosqlite.connect(db._connector if hasattr(db, '_connector') else str(db)) as save_db:
                # Use a new connection for saving to avoid issues with the generator
                pass

            await db.execute(
                "INSERT INTO messages (id, conversation_id, role, content, model, created_at) VALUES (?, ?, 'assistant', ?, ?, ?)",
                (assistant_msg_id, conv_id, content, model, msg_now),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (msg_now, conv_id),
            )
            await db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
