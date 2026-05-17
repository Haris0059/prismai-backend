import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db.session import async_session
from app.core.auth import get_current_user
import app.store as store

router = APIRouter()

class TitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

class ConversationListResponse(BaseModel):
    id: str
    title: str
    provider: str
    model: str
    updated_at: str

class MessageResponse(BaseModel):
    role: str
    content: str
    created_at: str

class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    provider: str
    model: str
    created_at: str
    updated_at: str
    messages: list[MessageResponse]

class ConversationRenameResponse(BaseModel):
    id: str
    title: str

class ConversationDeleteResponse(BaseModel):
    deleted: bool

@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations(user: dict = Depends(get_current_user)) -> list[ConversationListResponse]:
    async with async_session() as session:
        rows = await store.list_conversations(session, user_id=user["uid"])
        return [
            ConversationListResponse(
                id=str(c.id),
                title=c.title,
                provider=c.provider,
                model=c.model,
                updated_at=c.updated_at.isoformat(),
            )
            for c in rows
        ]

@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: uuid.UUID, user: dict = Depends(get_current_user)) -> ConversationDetailResponse:
    async with async_session() as session:
        conv = await store.get_conversation(session, conversation_id=conversation_id, user_id=user["uid"])
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return ConversationDetailResponse(
            id=str(conv.id),
            title=conv.title,
            provider=conv.provider,
            model=conv.model,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            messages=[
                MessageResponse(role=m.role, content=m.content, created_at=m.created_at.isoformat())
                for m in conv.messages
            ],
        )

@router.patch("/conversations/{conversation_id}", response_model=ConversationRenameResponse)
async def rename_conversation(conversation_id: uuid.UUID, body: TitleUpdate, user: dict = Depends(get_current_user)) -> ConversationRenameResponse:
    async with async_session() as session:
        conv = await store.update_title(session, conversation_id=conversation_id, user_id=user["uid"], title=body.title)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await session.commit()
        return ConversationRenameResponse(id=str(conv.id), title=conv.title)

@router.delete("/conversations/{conversation_id}", response_model=ConversationDeleteResponse)
async def delete_conversation(conversation_id: uuid.UUID, user: dict = Depends(get_current_user)) -> ConversationDeleteResponse:
    async with async_session() as session:
        ok = await store.delete_conversation(session, conversation_id=conversation_id, user_id=user["uid"])
        if not ok:
            raise HTTPException(status_code=404, detail="Conversation not found")
        await session.commit()
        return ConversationDeleteResponse(deleted=True)
