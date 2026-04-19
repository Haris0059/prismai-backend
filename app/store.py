import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message


async def create_conversation(session: AsyncSession, *, user_id: str, provider: str, model: str) -> Conversation:
    conv = Conversation(user_id=user_id, provider=provider, model=model)
    session.add(conv)
    await session.flush()
    return conv


async def get_conversation(session: AsyncSession, *, conversation_id: uuid.UUID, user_id: str) -> Conversation | None:
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .options(selectinload(Conversation.messages))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_conversations(session: AsyncSession, *, user_id: str) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def append_message(session: AsyncSession, *, conversation: Conversation, role: str, content: str) -> Message:
    msg = Message(conversation_id=conversation.id, role=role, content=content)
    session.add(msg)
    await session.flush()
    return msg


async def update_title(session: AsyncSession, *, conversation_id: uuid.UUID, user_id: str, title: str) -> Conversation | None:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:
        return None
    conv.title = title
    await session.flush()
    return conv


async def delete_conversation(session: AsyncSession, *, conversation_id: uuid.UUID, user_id: str) -> bool:
    result = await session.execute(
        delete(Conversation)
        .where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    return result.rowcount > 0
