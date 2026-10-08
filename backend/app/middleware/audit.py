"""Audit logging middleware — captures mutating requests for compliance."""

import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs CREATE/UPDATE/DELETE operations to the audit_logs table."""

    async def dispatch(self, request: Request, call_next):
        # Only audit mutating methods
        endpoint_owns_audit = request.url.path == "/api/v1/assistant/actions/confirm"
        should_audit = (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            and not endpoint_owns_audit
        )

        response = await call_next(request)

        if should_audit and 200 <= response.status_code < 400:
            # Extract entity info from path
            # Expected pattern: /api/v1/{entity_type}/{entity_id}
            path_parts = request.url.path.strip("/").split("/")
            entity_type = path_parts[2] if len(path_parts) > 2 else "unknown"
            entity_id = path_parts[3] if len(path_parts) > 3 else None
            try:
                parsed_entity_id = uuid.UUID(entity_id) if entity_id else None
            except ValueError:
                parsed_entity_id = None


            action = {
                "POST": "CREATE",
                "PUT": "UPDATE",
                "PATCH": "UPDATE",
                "DELETE": "DELETE",
            }.get(request.method, request.method)

            # Get user from request state if set by auth middleware
            user_id = getattr(request.state, "user_id", None)

            # Fire-and-forget: don't block the response for audit
            request_id = uuid.uuid4()
            try:
                session_factory = request.app.state.audit_session_factory
                async with session_factory() as session:
                    log = AuditLog(
                        user_id=uuid.UUID(user_id) if user_id else None,
                        action=action,
                        entity_type=entity_type,
                        entity_id=parsed_entity_id,
                        ip_address=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        request_id=request_id,
                    )
                    session.add(log)
                    await session.commit()
            except Exception as audit_error:
                logger.error(
                    "Request audit persistence failed",
                    extra={
                        "request_id": str(request_id),
                        "audit_stage": "middleware",
                        "request_method": request.method,
                        "entity_type": entity_type,
                        "error_type": type(audit_error).__name__,
                    },
                )

        return response
