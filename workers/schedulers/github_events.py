"""Record a GitHub delivery. A replay uses the same idempotency key."""

from __future__ import annotations

from typing import Any

from core.context.orgs.store import OrgStore

_EVENT_TYPES = {
    "opened": "github.pull_request_opened",
    "merged": "github.pull_request_merged",
    "issue": "github.issue_seen",
}


def note_github_delivery(
    organization_id: str,
    delivery_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    event_type = _EVENT_TYPES.get(str(action or "").strip())
    delivery = str(delivery_id or "").strip()
    if not organization_id or not delivery or event_type is None:
        return False
    body = dict(payload or {})
    body.setdefault("action", action)
    body.setdefault("delivery_id", delivery)
    return OrgStore().record_event(
        organization_id,
        event_type,
        source_id=delivery,
        payload=body,
        idempotency_key=f"github:{delivery}:{action}",
    )
