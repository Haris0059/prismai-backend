import asyncio
import uuid
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
import structlog

from app.db.models import Conversation
from app.db.session import async_session
from app.core.auth import get_current_user
import app.store as store

from app.providers.registry import PROVIDERS
from app.providers.base import ProviderError

logger = structlog.get_logger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    model: str
    message: str
    conversation_id: uuid.UUID | None = None

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
    except Exception as e:
        logger.warning("Failed to generate title", conversation_id=str(conversation_id), error=str(e))

@router.post("/chat/{provider}")
async def chat(provider: str, request: ChatRequest, user: dict = Depends(get_current_user)) -> StreamingResponse:
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

    async def generate() -> AsyncGenerator[str, None]:
        chunks = []
        try:
            # Yield conversation ID first so the client has it
            yield f"data: {json.dumps({'conversation_id': str(conv_id)})}\n\n"

            async for chunk in adapter.stream(request.model, history):
                chunks.append(chunk)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        except ProviderError as e:
            yield f"data: {json.dumps({'error': e.message})}\n\n"
            return
        except Exception as e:
            logger.error("stream_error", error=str(e), conversation_id=str(conv_id))
            yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
            return

        assistant_text = "".join(chunks)

        # Persist full message upon completion
        async with async_session() as session:
            conv = await session.get(Conversation, conv_id)
            await store.append_message(session, conversation=conv, role="assistant", content=assistant_text)
            conv.updated_at = func.now()
            await session.commit()

        if is_first_exchange:
            asyncio.create_task(
                _generate_title(provider, request.model, request.message, assistant_text, conv_id, user_id)
            )

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
