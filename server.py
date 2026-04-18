import asyncio
import os
import uuid

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel

load_dotenv()

from sqlalchemy import func  # noqa: E402

from db import Conversation, async_session  # noqa: E402
import store  # noqa: E402

app = FastAPI()


# TODO: Firebase auth — re-enable once service account is provisioned
async def verify_firebase_token(authorization: str | None = Header(default=None)) -> dict:
    return {"uid": "dev-user"}


class ChatRequest(BaseModel):
    model: str
    message: str
    conversation_id: uuid.UUID | None = None


class TitleUpdate(BaseModel):
    title: str


PROVIDERS = {
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "key": os.getenv("ANTHROPIC_API_KEY"),
        "headers": lambda key: {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        "build_body": lambda model, messages: {
            "model": model,
            "max_tokens": 1024,
            "messages": messages,
        },
        "extract_text": lambda data: data["content"][0]["text"],
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key": os.getenv("OPENAI_API_KEY"),
        "headers": lambda key: {
            "Authorization": f"Bearer {key}",
            "content-type": "application/json",
        },
        "build_body": lambda model, messages: {
            "model": model,
            "messages": messages,
        },
        "extract_text": lambda data: data["choices"][0]["message"]["content"],
    },
}


async def _call_provider(provider: str, model: str, messages: list[dict]) -> tuple[dict, str]:
    config = PROVIDERS[provider]
    key = config["key"]
    if not key:
        raise HTTPException(status_code=500, detail=f"API key not configured for {provider}")

    headers = config["headers"](key)
    body = config["build_body"](model, messages)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(config["url"], json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data, config["extract_text"](data)
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)


async def _generate_title(provider: str, model: str, user_msg: str, assistant_msg: str, conversation_id: uuid.UUID, user_id: str) -> None:
    prompt = (
        "Summarize this conversation as a short title of 6 words or fewer. "
        "Reply with the title only, no quotes, no punctuation at the end.\n\n"
        f"User: {user_msg}\nAssistant: {assistant_msg}"
    )
    try:
        _, title = await _call_provider(provider, model, [{"role": "user", "content": prompt}])
        title = title.strip().strip('"').strip("'")[:80] or "New chat"
        async with async_session() as session:
            await store.update_title(session, conversation_id=conversation_id, user_id=user_id, title=title)
            await session.commit()
    except Exception:
        pass


@app.post("/chat/{provider}")
async def chat(provider: str, request: ChatRequest, user: dict = Depends(verify_firebase_token)):
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

    data, assistant_text = await _call_provider(provider, request.model, history)

    async with async_session() as session:
        conv = await session.get(Conversation, conv_id)
        await store.append_message(session, conversation=conv, role="assistant", content=assistant_text)
        conv.updated_at = func.now()
        await session.commit()

    if is_first_exchange:
        asyncio.create_task(
            _generate_title(provider, request.model, request.message, assistant_text, conv_id, user_id)
        )

    return {"conversation_id": str(conv_id), "response": data}


@app.get("/conversations")
async def list_conversations_endpoint(user: dict = Depends(verify_firebase_token)):
    async with async_session() as session:
        rows = await store.list_conversations(session, user_id=user["uid"])
        return [
            {
                "id": str(c.id),
                "title": c.title,
                "provider": c.provider,
                "model": c.model,
                "updated_at": c.updated_at.isoformat(),
            }
            for c in rows
        ]


@app.get("/conversations/{conversation_id}")
async def get_conversation_endpoint(conversation_id: uuid.UUID, user: dict = Depends(verify_firebase_token)):
    async with async_session() as session:
        conv = await store.get_conversation(session, conversation_id=conversation_id, user_id=user["uid"])
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {
            "id": str(conv.id),
            "title": conv.title,
            "provider": conv.provider,
            "model": conv.model,
            "created_at": conv.created_at.isoformat(),
            "updated_at": conv.updated_at.isoformat(),
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in conv.messages
            ],
        }


@app.patch("/conversations/{conversation_id}")
async def rename_conversation_endpoint(conversation_id: uuid.UUID, body: TitleUpdate, user: dict = Depends(verify_firebase_token)):
    async with async_session() as session:
        conv = await store.update_title(session, conversation_id=conversation_id, user_id=user["uid"], title=body.title)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await session.commit()
        return {"id": str(conv.id), "title": conv.title}


@app.delete("/conversations/{conversation_id}")
async def delete_conversation_endpoint(conversation_id: uuid.UUID, user: dict = Depends(verify_firebase_token)):
    async with async_session() as session:
        ok = await store.delete_conversation(session, conversation_id=conversation_id, user_id=user["uid"])
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await session.commit()
        return {"deleted": True}
