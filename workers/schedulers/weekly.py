"""Backward-compatible entry for a weekly schedule. Firing goes through the dispatcher."""

from __future__ import annotations

from typing import Any

from core.context.subscriptions.models import Subscription
from core.context.subscriptions.store import SubscriptionStore
from workers.schedulers.dispatch import fire_schedule


async def fire_weekly_report(
    sub: Subscription,
    *,
    store: SubscriptionStore | None = None,
) -> dict[str, Any]:
    return await fire_schedule(sub, store=store)
