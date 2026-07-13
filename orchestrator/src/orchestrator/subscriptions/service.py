"""Subscription lifecycle: create, check, stop, notify."""

from __future__ import annotations

import re
from typing import Any

from orchestrator.conversations.store import ConversationStore
from orchestrator.integrations.client import IntegrationClient
from orchestrator.missions.session_type import SessionType
from orchestrator.missions.store import MissionStore
from orchestrator.subscriptions.models import Subscription, SubscriptionStatus
from orchestrator.subscriptions.recurring_params import format_interval
from orchestrator.subscriptions.recurring_runner import run_recurring_instruction
from orchestrator.subscriptions.session_sync import cancel_mission_for_subscription
from orchestrator.subscriptions.store import SubscriptionStore

DEFAULT_POLL_SECONDS = 90


class SubscriptionService:
    def __init__(
        self,
        *,
        sub_store: SubscriptionStore | None = None,
        conv_store: ConversationStore | None = None,
        integration_client: IntegrationClient | None = None,
    ) -> None:
        self._subs = sub_store or SubscriptionStore()
        self._conv = conv_store or ConversationStore()
        self._integrations = integration_client or IntegrationClient()

    async def subscribe_gmail_inbox(
        self,
        user_id: str,
        *,
        conversation_id: str,
        query: str = "",
        poll_interval_seconds: int = DEFAULT_POLL_SECONDS,
        mission_id: str | None = None,
    ) -> dict[str, Any]:
        if not self._integrations.is_connected(user_id, "gmail"):
            raise RuntimeError("gmail is not connected — connect it on the Integrations page")

        existing = [
            s
            for s in self._subs.list_active_for_conversation(conversation_id)
            if s.integration == "gmail" and s.kind == "new_email"
        ]
        for sub in existing:
            self._subs.set_status(sub.id, SubscriptionStatus.STOPPED)
            cancel_mission_for_subscription(sub)

        baseline = await self._integrations.run(
            user_id,
            "gmail",
            "list_emails",
            {"max_results": 20},
        )
        seen_ids = [e.get("id") for e in baseline.get("emails", []) if e.get("id")]
        config = {
            "query": query,
            "poll_interval_seconds": poll_interval_seconds,
        }
        sub = self._subs.create_subscription(
            user_id=user_id,
            conversation_id=conversation_id,
            integration="gmail",
            kind="new_email",
            config=config,
            cursor={"seen_ids": seen_ids},
            poll_interval_seconds=poll_interval_seconds,
            created_from_mission_id=mission_id,
        )
        if mission_id:
            mission_store = MissionStore()
            mission = mission_store.get_mission(mission_id)
            if mission and mission.session_type != SessionType.RECURRING:
                mission_store.update_session_type(mission_id, SessionType.RECURRING)
        return {
            "subscription_id": sub.id,
            "integration": sub.integration,
            "kind": sub.kind,
            "status": sub.status.value,
            "poll_interval_seconds": poll_interval_seconds,
            "baseline_count": len(seen_ids),
            "message": (
                f"I'm listening for new Gmail messages and will check every "
                f"{poll_interval_seconds} seconds. Say 'stop listening' when you want me to stop."
            ),
        }

    async def unsubscribe_gmail_inbox(
        self,
        user_id: str,
        *,
        conversation_id: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        stopped = 0
        stopped_subs: list[Subscription] = []
        if subscription_id:
            sub = self._subs.get_subscription(subscription_id)
            if sub and sub.user_id == user_id:
                self._subs.set_status(subscription_id, SubscriptionStatus.STOPPED)
                stopped = 1
                stopped_subs = [sub]
        else:
            active = [
                s
                for s in self._subs.list_active_for_conversation(conversation_id)
                if s.integration == "gmail" and s.kind == "new_email"
            ]
            for sub in active:
                self._subs.set_status(sub.id, SubscriptionStatus.STOPPED)
                stopped_subs.append(sub)
            stopped = len(stopped_subs)
        for sub in stopped_subs:
            cancel_mission_for_subscription(sub)
        return {
            "stopped": stopped,
            "message": "Stopped listening for new emails."
            if stopped
            else "No active email listener was found for this conversation.",
        }

    async def subscribe_recurring_task(
        self,
        user_id: str,
        *,
        conversation_id: str,
        instruction: str,
        poll_interval_seconds: int = 86_400,
        mission_id: str | None = None,
    ) -> dict[str, Any]:
        instruction = instruction.strip()
        if not instruction:
            raise RuntimeError("instruction is required for recurring tasks")
        poll_interval_seconds = max(300, int(poll_interval_seconds))

        existing = [
            s
            for s in self._subs.list_active_for_conversation(conversation_id)
            if s.integration == "task" and s.kind == "recurring_task"
        ]
        for sub in existing:
            self._subs.set_status(sub.id, SubscriptionStatus.STOPPED)
            cancel_mission_for_subscription(sub)

        config = {
            "instruction": instruction,
            "poll_interval_seconds": poll_interval_seconds,
        }
        sub = self._subs.create_subscription(
            user_id=user_id,
            conversation_id=conversation_id,
            integration="task",
            kind="recurring_task",
            config=config,
            cursor={"run_count": 0, "last_run_at": None},
            poll_interval_seconds=poll_interval_seconds,
            created_from_mission_id=mission_id,
        )
        if mission_id:
            mission_store = MissionStore()
            mission = mission_store.get_mission(mission_id)
            if mission and mission.session_type != SessionType.RECURRING:
                mission_store.update_session_type(mission_id, SessionType.RECURRING)

        interval_label = format_interval(poll_interval_seconds)
        return {
            "subscription_id": sub.id,
            "integration": sub.integration,
            "kind": sub.kind,
            "status": sub.status.value,
            "poll_interval_seconds": poll_interval_seconds,
            "instruction": instruction,
            "message": (
                f"I'll run this every {interval_label}: {instruction[:120]}"
                f"{'…' if len(instruction) > 120 else ''} "
                f"Say 'stop recurring' to cancel."
            ),
        }

    async def unsubscribe_recurring_task(
        self,
        user_id: str,
        *,
        conversation_id: str,
        subscription_id: str | None = None,
    ) -> dict[str, Any]:
        stopped = 0
        stopped_subs: list[Subscription] = []
        if subscription_id:
            sub = self._subs.get_subscription(subscription_id)
            if (
                sub
                and sub.user_id == user_id
                and sub.integration == "task"
                and sub.kind == "recurring_task"
            ):
                self._subs.set_status(subscription_id, SubscriptionStatus.STOPPED)
                stopped = 1
                stopped_subs = [sub]
        else:
            active = [
                s
                for s in self._subs.list_active_for_conversation(conversation_id)
                if s.integration == "task" and s.kind == "recurring_task"
            ]
            for sub in active:
                self._subs.set_status(sub.id, SubscriptionStatus.STOPPED)
                stopped_subs.append(sub)
            stopped = len(stopped_subs)
        for sub in stopped_subs:
            cancel_mission_for_subscription(sub)
        return {
            "stopped": stopped,
            "message": "Stopped the recurring background task."
            if stopped
            else "No active recurring task was found for this conversation.",
        }

    async def run_recurring_task(self, sub: Subscription) -> dict[str, Any]:
        instruction = str(sub.config.get("instruction") or "").strip()
        if not instruction:
            self._subs.set_status(sub.id, SubscriptionStatus.ERROR, error="missing instruction")
            return {"ran": False, "error": "missing instruction"}

        result = await run_recurring_instruction(
            user_id=sub.user_id,
            conversation_id=sub.conversation_id,
            instruction=instruction,
            mission_id=sub.created_from_mission_id,
        )

        interval = int(sub.config.get("poll_interval_seconds") or 86_400)
        run_count = int(sub.cursor.get("run_count") or 0) + 1
        from datetime import datetime, timezone

        cursor = {
            "run_count": run_count,
            "last_run_at": datetime.now(timezone.utc).isoformat(),
        }

        if result.get("had_error"):
            self._subs.update_cursor(sub.id, cursor, poll_interval_seconds=interval)
            summary = f"Scheduled task failed: {result.get('error') or 'Unknown error'}"
            self.deliver_notification(
                sub,
                summary=summary,
                payload={"error": result.get("error"), "run_count": run_count},
            )
            return {"ran": True, "error": result.get("error"), "run_count": run_count}

        text = str(result.get("text") or "").strip()
        if not text:
            text = "Scheduled task completed (no summary returned)."
            self._subs.update_cursor(sub.id, cursor, poll_interval_seconds=interval)
            return {"ran": True, "empty": True, "run_count": run_count}

        summary = f"Scheduled update: {text}"
        self._subs.update_cursor(sub.id, cursor, poll_interval_seconds=interval)
        self.deliver_notification(
            sub,
            summary=summary,
            payload={"text": text, "run_count": run_count},
        )
        return {"ran": True, "text": text, "run_count": run_count}

    async def check_gmail_subscription(self, sub: Subscription) -> list[dict[str, Any]]:
        if not self._integrations.is_connected(sub.user_id, "gmail"):
            self._subs.set_status(sub.id, SubscriptionStatus.ERROR, error="gmail disconnected")
            return []

        result = await self._integrations.run(
            sub.user_id,
            "gmail",
            "list_emails",
            {"max_results": 20},
        )
        emails = result.get("emails") or []
        seen = set(sub.cursor.get("seen_ids") or [])
        new_emails = [e for e in emails if e.get("id") and e["id"] not in seen]
        if not new_emails:
            interval = int(sub.config.get("poll_interval_seconds") or DEFAULT_POLL_SECONDS)
            self._subs.update_cursor(
                sub.id,
                {"seen_ids": list(seen)},
                poll_interval_seconds=interval,
            )
            return []

        for email in new_emails:
            if email.get("id"):
                seen.add(email["id"])

        interval = int(sub.config.get("poll_interval_seconds") or DEFAULT_POLL_SECONDS)
        self._subs.update_cursor(
            sub.id,
            {"seen_ids": list(seen)},
            poll_interval_seconds=interval,
        )
        return new_emails

    def deliver_notification(
        self,
        sub: Subscription,
        *,
        summary: str,
        payload: dict[str, Any],
    ) -> int:
        notification_id = self._subs.append_notification(
            sub.conversation_id,
            subscription_id=sub.id,
            integration=sub.integration,
            kind=sub.kind,
            summary=summary,
            payload=payload,
        )
        self._conv.append_message(sub.conversation_id, role="assistant", content=summary)
        return notification_id

    @staticmethod
    def _parse_sender(from_field: str) -> str:
        raw = (from_field or "").strip()
        if not raw:
            return "someone"
        match = re.match(r'^"?(.*?)"?\s*<[^>]+>', raw)
        if match and match.group(1).strip():
            return match.group(1).strip()
        if "<" in raw:
            name = raw.split("<", 1)[0].strip().strip('"')
            if name:
                return name
        if "@" in raw:
            return raw.split("@", 1)[0]
        return raw

    @staticmethod
    def format_new_emails_notification(emails: list[dict[str, Any]]) -> str:
        if len(emails) == 1:
            email = emails[0]
            subject = (email.get("subject") or "").strip() or "a message with no subject"
            sender = SubscriptionService._parse_sender(str(email.get("from") or ""))
            return f'Heads up — {sender} just emailed you about "{subject}".'
        latest = emails[0]
        latest_sender = SubscriptionService._parse_sender(str(latest.get("from") or ""))
        latest_subject = (latest.get("subject") or "").strip() or "a message with no subject"
        if len(emails) == 2:
            return (
                f"You've got 2 new emails. The latest is from {latest_sender}: "
                f'"{latest_subject}".'
            )
        return (
            f"You've got {len(emails)} new emails. The latest is from {latest_sender}: "
            f'"{latest_subject}".'
        )

    async def humanize_new_emails_notification(
        self,
        emails: list[dict[str, Any]],
    ) -> str:
        fallback = self.format_new_emails_notification(emails)
        if not emails:
            return fallback
        try:
            from orchestrator.llm import get_llm

            facts = []
            for email in emails[:5]:
                facts.append(
                    {
                        "from": self._parse_sender(str(email.get("from") or "")),
                        "subject": (email.get("subject") or "").strip() or "(no subject)",
                        "snippet": (email.get("snippet") or "").strip()[:160],
                    }
                )
            llm = get_llm(temperature=0.4)
            response = await llm.ainvoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "Write a brief, friendly inbox notification as if texting the user. "
                            "One or two sentences. Use their name for the sender when natural. "
                            "No markdown, no bullet lists, no tool talk."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"New emails:\n{facts}",
                    },
                ]
            )
            content = response.content
            text = content if isinstance(content, str) else str(content)
            return text.strip() or fallback
        except Exception:
            return fallback
