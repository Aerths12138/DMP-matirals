"""Authenticated AI assistant endpoints."""

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File as FastAPIFile,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_approved_user, get_db, require_permission
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
    AssistantHistoryResponse,
)
from app.services import (
    assistant_backup_service,
    assistant_excel_service,
    assistant_history_service,
    assistant_service,
)

router = APIRouter(prefix="/assistant", tags=["AI Assistant"])
logger = logging.getLogger(__name__)


def _log_audit_failure(
    request_id: uuid.UUID,
    stage: str,
    error: Exception,
) -> None:
    logger.error(
        "AI assistant audit persistence failed",
        extra={
            "request_id": str(request_id),
            "audit_stage": stage,
            "error_type": type(error).__name__,
        },
    )

class ImportAlignmentRequest(BaseModel):
    headers: list[str]
    rows: list[list[str | int | float | None]] = Field(default_factory=list)



async def _run_assistant_chat(
    body: AssistantChatRequest,
    db: AsyncSession,
    current_user: User,
    attachments: list[dict] | None = None,
    attachment_import: dict | None = None,
) -> AssistantChatResponse:
    message, pending_actions, pending_import = await assistant_service.chat(
        [item.model_dump() for item in body.messages],
        body.context_path,
        db,
        current_user,
        attachments=attachments,
        attachment_import=attachment_import,
    )
    await assistant_history_service.replace_history(
        db,
        current_user.id,
        [
            *[item.model_dump() for item in body.messages],
            {"role": "assistant", "content": message},
        ],
    )
    return AssistantChatResponse(
        message=message,
        pending_actions=pending_actions,
        pending_import=pending_import,
        model=settings.assistant_model,
    )


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    body: AssistantChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Answer a question and prepare any requested mutations for confirmation."""
    return await _run_assistant_chat(body, db, current_user)


@router.post("/chat/excel", response_model=AssistantChatResponse)
async def assistant_excel_chat(
    request: str = Form(...),
    file: UploadFile = FastAPIFile(...),
    sheet_name: str | None = Form(default=None, max_length=31),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Read a bounded Excel preview for this chat request without storing the file."""
    try:
        body = AssistantChatRequest.model_validate_json(request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid assistant chat request",
        ) from exc
    workbook = await assistant_excel_service.parse_excel_upload_bundle(
        file,
        sheet_name,
    )
    return await _run_assistant_chat(
        body,
        db,
        current_user,
        [workbook["preview"]],
        workbook["import_data"],
    )


@router.get("/history", response_model=AssistantHistoryResponse)
async def get_assistant_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Load the current user's latest assistant conversation."""
    history = await assistant_history_service.get_history(db, current_user.id)
    if history is None:
        return AssistantHistoryResponse()
    return AssistantHistoryResponse(
        messages=history.messages,
        updated_at=history.updated_at,
    )


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_assistant_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_approved_user),
):
    """Clear only the current user's saved assistant conversation."""
    await assistant_history_service.clear_history(db, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import/align")
async def align_assistant_import(
    body: ImportAlignmentRequest,
    _current_user: User = Depends(require_permission("import:create")),
):
    """Return a deterministic import-alignment preview without writing data."""
    return assistant_service.align_import_data(body.headers, body.rows)


@router.post("/actions/confirm", response_model=AssistantActionConfirmResponse)
async def confirm_assistant_action(
    body: AssistantActionConfirmRequest,
    request: Request,
    response: Response,
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
        except Exception as audit_error:
            _log_audit_failure(action_id, "permission_denied", audit_error)

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
    try:
        db.add(
            AuditLog(
                user_id=current_user.id,
                action=operation.upper(),
                entity_type=entity_type,
                entity_id=uuid.UUID(entity_id),
                changes={
                    "source": "ai_assistant",
                    "tool": payload["tool"],
                    "backup_id": str(backup.id) if backup else None,
                },
                request_id=action_id,
            )
        )
        await db.flush()
    except Exception as audit_error:
        await db.rollback()
        _log_audit_failure(action_id, "action_execution", audit_error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI action was not applied because audit persistence failed",
            headers={"X-Request-ID": str(action_id)},
        ) from audit_error

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
    response_message = f"已{action_text}{entity_label}。"
    await assistant_history_service.append_message(
        db,
        current_user.id,
        "assistant",
        response_message,
    )
    response.headers["X-Request-ID"] = str(action_id)
    return AssistantActionConfirmResponse(
        message=response_message,
        request_id=action_id,
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
    response_message = f"已回退到“{backup.entity_name}”操作前的版本。"
    await assistant_history_service.append_message(
        db,
        current_user.id,
        "assistant",
        response_message,
    )
    return AssistantBackupRestoreResponse(
        message=response_message,
        backup_id=backup.id,
        entity_type=backup.entity_type,
        entity_id=backup.entity_id,
    )
