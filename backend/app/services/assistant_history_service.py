"""Persistence helpers for each user's latest AI assistant conversation."""

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assistant_conversation import AssistantConversation


MAX_HISTORY_MESSAGES = 30


async def get_history(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> AssistantConversation | None:
    return await db.scalar(
        select(AssistantConversation).where(AssistantConversation.user_id == user_id)
    )


async def replace_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    messages: list[dict[str, str]],
) -> AssistantConversation:
    history = await get_history(db, user_id)
    normalized = messages[-MAX_HISTORY_MESSAGES:]
    if history is None:
        history = AssistantConversation(user_id=user_id, messages=normalized)
        db.add(history)
    else:
        history.messages = normalized
        history.updated_at = datetime.utcnow()
    await db.flush()
    return history


async def append_message(
    db: AsyncSession,
    user_id: uuid.UUID,
    role: str,
    content: str,
) -> AssistantConversation:
    history = await get_history(db, user_id)
    messages = list(history.messages) if history is not None else []
    messages.append({"role": role, "content": content})
    return await replace_history(db, user_id, messages)


async def clear_history(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        delete(AssistantConversation).where(AssistantConversation.user_id == user_id)
    )
    await db.flush()
