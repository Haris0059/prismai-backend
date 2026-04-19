import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from app.db.models import Conversation
from app.db.session import async_session
from app.core.auth import get_current_user
import app.store as store

from app.providers.registry import PROVIDERS
from app.providers.base import ProviderError

router = APIRouter()

class ChatRequest(BaseModel):
    model: str
    message: str
    conversation_id: uuid.UUID | None = None

class ChatResponse(BaseModel):
    conversation_id: str
    response: dict[str, Any]

async def _generate_title(provider: str, model: str, user_msg: str, assistant_msg: str, conversation_id: uuid.UUID, user_id: str) -> None:
    prompt = (
        "Summarize this conversation as a short title of 6 words or fewer. "
        "Reply with the title only, no quotes, no punctuation at the end.\n\n"
        f"User: {user_msg}\nAssistant: {assistant_msg}"
    )
    try:
        adapter = PROVIDERS[provider]
        _, title = await adapter.complete(model, [{"role": "user", "content": prompt}])
        title = title.strip().strip('"').strip("'")[:80] or "New chat"
        async with async_session() as session:
            await store.update_title(session, conversation_id=conversation_id, user_id=user_id, title=title)
            await session.commit()
    except Exception:
        pass

@router.post("/chat/{provider}", response_model=ChatResponse)
async def chat(provider: str, request: ChatRequest, user: dict = Depends(get_current_user)) -> ChatResponse:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    user_id = user["uid"]

    async with async_session() as session:
        if request.conversation_id is None:
            conv = await store.create_conversation(session, user_id=user_id, provider=provider, model=request.model)
            history: list[dict] = []
        else:
            conv = await store.get_conversation(session, conversation_id=request.conversation_id, user_id=user_id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            history = [{"role": m.role, "content": m.content} for m in conv.messages]

        is_first_exchange = len(history) == 0
        history.append({"role": "user", "content": request.message})
        await store.append_message(session, conversation=conv, role="user", content=request.message)
        await session.commit()
        conv_id = conv.id

    adapter = PROVIDERS[provider]
    try:
        data, assistant_text = await adapter.complete(request.model, history)
    except ProviderError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    async with async_session() as session:
        conv = await session.get(Conversation, conv_id)
        await store.append_message(session, conversation=conv, role="assistant", content=assistant_text)
        conv.updated_at = func.now()
        await session.commit()

    if is_first_exchange:
        asyncio.create_task(
            _generate_title(provider, request.model, request.message, assistant_text, conv_id, user_id)
        )

    return ChatResponse(conversation_id=str(conv_id), response=data)
