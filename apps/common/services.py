from apps.common.models import AuditEvent


def record_audit_event(
    *,
    action: str,
    actor=None,
    target=None,
    request_id: str = "",
    metadata: dict | None = None,
) -> AuditEvent:
    target_type = target.__class__.__name__ if target is not None else ""
    target_id = str(getattr(target, "pk", "")) if target is not None else ""
    return AuditEvent.objects.create(
        action=action,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        target_type=target_type,
        target_id=target_id,
        request_id=request_id,
        metadata=metadata or {},
    )
