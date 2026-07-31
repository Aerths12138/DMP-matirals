"""Authenticated AI assistant endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_approved_user, get_db
from app.config import settings
from app.models.assistant import AssistantActionExecution
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.assistant import (
    AssistantActionConfirmRequest,
    AssistantActionConfirmResponse,
    AssistantBackupResponse,
    AssistantBackupRestoreResponse,
    AssistantChatRequest,
    AssistantChatResponse,
)
from app.services import assistant_backup_service, assistant_service

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    body: AssistantChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Answer a question and prepare any requested mutations for confirmation."""
    message, pending_actions = await assistant_service.chat(
        [item.model_dump() for item in body.messages],
        body.context_path,
        db,
        current_user,
    )
    return AssistantChatResponse(
        message=message,
        pending_actions=pending_actions,
        model=settings.assistant_model,
    )


@router.post("/actions/confirm", response_model=AssistantActionConfirmResponse)
async def confirm_assistant_action(
    body: AssistantActionConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Execute one signed action once, backing up updates and deletes first."""
    payload = assistant_service.decode_action_token(body.token, current_user)
    action_id = uuid.UUID(payload["jti"])

    existing = await db.scalar(
        select(AssistantActionExecution.id).where(AssistantActionExecution.id == action_id)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This action has already been executed",
        )

    try:
        normalized, operation, entity_type, _summary, known_id = (
            await assistant_service.prepare_write_action(
                payload["tool"],
                payload["arguments"],
                db,
                current_user,
            )
        )
    except HTTPException as exc:
        if exc.status_code != status.HTTP_403_FORBIDDEN:
            raise

        if exc.detail == "Insufficient project access":
            reason_code = "insufficient_project_access"
        elif (
            isinstance(exc.detail, str)
            and exc.detail.startswith("Insufficient permissions")
        ):
            reason_code = "insufficient_global_permission"
        else:
            reason_code = "permission_recheck_failed"

        try:
            session_factory = request.app.state.audit_session_factory
            async with session_factory() as audit_db:
                audit_db.add(
                    AuditLog(
                        user_id=current_user.id,
                        action="DENY",
                        entity_type=payload["tool"].split("_", 1)[1],
                        changes={
                            "source": "ai_assistant",
                            "stage": "confirmation",
                            "tool": payload["tool"],
                            "reason_code": reason_code,
                        },
                        request_id=action_id,
                    )
                )
                await audit_db.commit()
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.detail,
            headers={"X-Request-ID": str(action_id)},
        ) from exc
    receipt = AssistantActionExecution(
        id=action_id,
        user_id=current_user.id,
        tool_name=payload["tool"],
        entity_type=entity_type,
        arguments=normalized,
    )
    db.add(receipt)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This action has already been executed",
        ) from exc

    backup = None
    if known_id is not None:
        backup = await assistant_backup_service.create_backup(
            action_execution_id=action_id,
            tool_name=payload["tool"],
            operation=operation,
            entity_type=entity_type,
            entity_id=uuid.UUID(known_id),
            db=db,
            current_user=current_user,
        )

    operation, entity_id, data = await assistant_service.execute_write_action(
        payload["tool"],
        normalized,
        db,
        current_user,
    )
    await assistant_backup_service.finalize_backup(backup, db)
    receipt.entity_id = uuid.UUID(entity_id)
    db.add(
        AuditLog(
            user_id=current_user.id,
            action=operation.upper(),
            entity_type=entity_type,
            entity_id=uuid.UUID(entity_id),
            changes={
                "source": "ai_assistant",
                "tool": payload["tool"],
                "arguments": normalized,
                "backup_id": str(backup.id) if backup else None,
            },
            request_id=action_id,
        )
    )
    await db.flush()

    action_text = {"create": "创建", "update": "更新", "delete": "删除"}[operation]
    entity_label = {
        "material": "材料",
        "project": "项目",
        "experiment": "实验",
        "sample": "样品",
        "property": "性能属性",
        "test": "测试记录",
        "test_measurement": "测试测量值",
        "characterization": "表征记录",
    }[entity_type]
    return AssistantActionConfirmResponse(
        message=f"已{action_text}{entity_label}。",
        entity_type=entity_type,
        entity_id=entity_id,
        data=data,
        backup=(AssistantBackupResponse.model_validate(backup) if backup else None),
    )


@router.get("/backups", response_model=list[AssistantBackupResponse])
async def list_assistant_backups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """List the current user's non-expired, unrestored AI backups."""
    backups = await assistant_backup_service.list_available_backups(db, current_user)
    return [AssistantBackupResponse.model_validate(item) for item in backups]


@router.post(
    "/backups/{backup_id}/restore",
    response_model=AssistantBackupRestoreResponse,
)
async def restore_assistant_backup(
    backup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Restore a temporary backup once, with current permissions rechecked."""
    backup = await assistant_backup_service.restore_backup(
        backup_id,
        db,
        current_user,
    )
    request_id = uuid.uuid4()
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="RESTORE",
            entity_type=backup.entity_type,
            entity_id=backup.entity_id,
            changes={
                "source": "ai_assistant",
                "backup_id": str(backup.id),
                "original_operation": backup.operation,
            },
            request_id=request_id,
        )
    )
    await db.flush()
    return AssistantBackupRestoreResponse(
        message=f"已回退到“{backup.entity_name}”操作前的版本。",
        backup_id=backup.id,
        entity_type=backup.entity_type,
        entity_id=backup.entity_id,
    )
