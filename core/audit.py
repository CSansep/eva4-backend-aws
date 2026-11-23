"""
Audit logging utility for tracking security and business events.
"""

from typing import Any, Dict, Optional
from core.models import AuditLog, AuditActionChoices


def get_client_ip(request) -> Optional[str]:
    """Extract client IP address from HTTP request headers."""
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def record_audit_log(
    user,
    action: str,
    entity_name: str,
    entity_id: Any,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> AuditLog:
    """
    Create a persistent audit log entry.
    Handles anonymous/unauthenticated users safely.
    """
    audit_user = user if (user and user.is_authenticated) else None
    return AuditLog.objects.create(
        user=audit_user,
        action=action,
        entity_name=entity_name,
        entity_id=str(entity_id),
        details=details or {},
        ip_address=ip_address
    )
