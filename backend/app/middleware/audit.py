"""Audit logging middleware — captures mutating requests for compliance."""

import uuid
from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.models.audit import AuditLog


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs CREATE/UPDATE/DELETE operations to the audit_logs table."""

    async def dispatch(self, request: Request, call_next):
        # Only audit mutating methods
        should_audit = request.method in ("POST", "PUT", "PATCH", "DELETE")

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
                        request_id=uuid.uuid4(),
                    )
                    session.add(log)
                    await session.commit()
            except Exception:
                pass  # Never let audit failure affect the main response

        return response
