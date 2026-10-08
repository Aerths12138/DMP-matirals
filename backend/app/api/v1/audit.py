"""Audit log viewer (admin only)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_admin
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=PaginatedResponse[dict])
async def list_audit_logs(
    pagination: PaginationParams = Depends(),
    action: str | None = Query(default=None, description="Filter by action"),
    entity_type: str | None = Query(default=None, description="Filter by entity type"),
    request_id: uuid.UUID | None = Query(
        default=None,
        description="Filter by exact request correlation ID",
    ),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """List audit logs with pagination and optional filters."""
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if request_id:
        query = query.where(AuditLog.request_id == request_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (pagination.page - 1) * pagination.size
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(pagination.size)
    result = await db.execute(query)
    logs = result.scalars().all()

    items = [
        {
            "id": str(log.id),
            "user_id": str(log.user_id) if log.user_id else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "request_id": str(log.request_id) if log.request_id else None,
            "changes": log.changes,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        size=pagination.size,
        pages=(total + pagination.size - 1) // pagination.size if total > 0 else 0,
    )
