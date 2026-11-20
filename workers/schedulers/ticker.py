"""Background polling for active subscriptions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.context.subscriptions.models import SubscriptionStatus
from core.context.subscriptions.service import SubscriptionService
from core.context.subscriptions.store import SubscriptionStore

logger = logging.getLogger(__name__)

_last_success_at: str | None = None


def last_success_at() -> str | None:
    """UTC time of the last tick that returned. A raised tick leaves this unchanged."""
    return _last_success_at


async def tick_subscriptions(
    *,
    limit: int = 20,
    github_deliveries: list[dict] | None = None,
) -> int:
    """Poll due subscriptions; deliver notifications for new items. Returns count checked."""
    store = SubscriptionStore()
    service = SubscriptionService(sub_store=store)
    due = store.list_due(limit=limit)
    checked = 0
    for sub in due:
        checked += 1
        try:
            if sub.integration == "gmail" and sub.kind == "new_email":
                new_emails = await service.check_gmail_subscription(sub)
                if new_emails:
                    summary = await service.humanize_new_emails_notification(new_emails)
                    service.deliver_notification(
                        sub,
                        summary=summary,
                        payload={"emails": new_emails},
                    )
                    from workers.schedulers.watcher_events import (
                        enqueue_watcher_inbox_alert,
                    )

                    enqueue_watcher_inbox_alert(
                        user_id=sub.user_id,
                        conversation_id=sub.conversation_id,
                        emails=new_emails,
                        summary=summary,
                    )
                    logger.info(
                        "Delivered %s new email(s) for subscription %s",
                        len(new_emails),
                        sub.id,
                    )
            elif sub.integration == "task" and sub.kind == "recurring_task":
                run_result = await service.run_recurring_task(sub)
                logger.info(
                    "Recurring task run for subscription %s: %s",
                    sub.id,
                    run_result,
                )
            elif sub.integration == "schedule" or sub.kind in {"schedule", "weekly_report"}:
                if sub.status == SubscriptionStatus.PAUSED:
                    continue
                try:
                    from workers.schedulers.dispatch import fire_schedule

                    report = await fire_schedule(sub, store=store)
                    logger.info("Schedule for subscription %s: %s", sub.id, report)
                except Exception as exc:
                    logger.exception("Schedule tick failed for %s", sub.id)
                    store.set_error(sub.id, str(exc)[:500])
            else:
                interval = int(sub.config.get("poll_interval_seconds") or 90)
                store.update_cursor(sub.id, sub.cursor, poll_interval_seconds=interval)
        except Exception as exc:
            logger.exception("Subscription tick failed for %s", sub.id)
            store.set_status(sub.id, SubscriptionStatus.ERROR, error=str(exc)[:500])
    from core.context.projects.store import ProjectStore
    from workers.schedulers.github_events import note_github_delivery

    ProjectStore().note_deadline_crossings()
    for delivery in github_deliveries or []:
        note_github_delivery(
            str(delivery.get("organization_id") or ""),
            str(delivery.get("delivery_id") or ""),
            str(delivery.get("action") or ""),
            delivery.get("payload") if isinstance(delivery.get("payload"), dict) else None,
        )
    from workers.schedulers.detection import detect_alerts

    detect_alerts()
    global _last_success_at
    _last_success_at = datetime.now(timezone.utc).isoformat()
    return checked
