"""Background polling for active subscriptions."""

from __future__ import annotations

import logging

from orchestrator.subscriptions.models import SubscriptionStatus
from orchestrator.subscriptions.service import SubscriptionService
from orchestrator.subscriptions.store import SubscriptionStore

logger = logging.getLogger(__name__)


async def tick_subscriptions(*, limit: int = 20) -> int:
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
            else:
                interval = int(sub.config.get("poll_interval_seconds") or 90)
                store.update_cursor(sub.id, sub.cursor, poll_interval_seconds=interval)
        except Exception as exc:
            logger.exception("Subscription tick failed for %s", sub.id)
            store.set_status(sub.id, SubscriptionStatus.ERROR, error=str(exc)[:500])
    return checked
