"""Runtime integration client for manager agent tool calls."""

from __future__ import annotations

import json
from typing import Any

from core.context.request import current_conversation_id, current_mission_id, current_user_id
from core.broker.executor import IntegrationExecutor
from core.broker.catalog import INTEGRATIONS, list_integrations
from core.broker.token_manager import TokenManager
from core.context.datetime_util import time_context_for_planner
from core.context.drafts.store import DraftStore
from pipelines.shared.streaming import emit


class IntegrationClient:
    def __init__(self, token_manager: TokenManager | None = None) -> None:
        self._tokens = token_manager or TokenManager()
        self._executor = IntegrationExecutor()

    def is_connected(self, user_id: str, integration_id: str) -> bool:
        return self._tokens.is_connected(user_id, integration_id)

    def capabilities_context(self, user_id: str) -> str:
        """Full tool inventory with connection status for planner and thinking agents."""
        from tools.web import search_provider_status

        connected = set(self._tokens.list_connected(user_id))
        conv_id = current_conversation_id.get() or ""
        draft_block = ""
        if conv_id:
            draft_ctx = DraftStore().draft_context_for_planner(conv_id)
            if draft_ctx:
                draft_block = f"\n{draft_ctx}\n"
        lines = [
            "=== Orchestrator capabilities ===",
            "",
            time_context_for_planner(user_id=user_id),
            draft_block,
            "Always available:",
            "- thinking: reason and answer directly (no external APIs)",
            "- time: current date/time in the user's timezone (action: now)",
            "- web: search the web and fetch/scrape pages (no OAuth required)",
            "  Actions: search {query, max_results?}; fetch_url {url}",
            f"  Search provider: {search_provider_status()}",
            "- recurring: run a task on a schedule in the background (no OAuth required)",
            "  Actions: subscribe {instruction, poll_interval_seconds?}; unsubscribe",
            "  Examples: every day / hourly / weekly tasks; say 'stop recurring' to cancel",
            "- roles: in-process specialists: researcher, reporter, follow_up, watcher, "
            "x_agent, reddit_agent, linkedin_agent",
            "  (coordinator plans a shared task board; specialists claim structured tasks)",
            "",
            "OAuth integrations (only usable when CONNECTED):",
        ]
        for spec in list_integrations():
            integration_id = spec["id"]
            if spec.get("coming_soon"):
                lines.append(f"- app:{integration_id}: {spec['name']} [COMING SOON]")
                lines.append(f"  {spec['description']}")
                lines.append(
                    f"  → Do NOT use app:{integration_id}. "
                    f"Tell the user {spec['name']} is coming soon."
                )
                lines.append("")
                continue
            is_on = integration_id in connected
            status = "CONNECTED" if is_on else "NOT CONNECTED"
            actions = ", ".join(spec["actions"])
            lines.append(f"- app:{integration_id}: {spec['name']} [{status}]")
            lines.append(f"  {spec['description']}")
            lines.append(f"  Actions: {actions}")
            if is_on:
                lines.append(f"  → You may plan subtasks with tool=app:{integration_id}")
                if integration_id == "google-drive":
                    lines.append(
                        "  Google Docs: create_document {name, content}; "
                        "write_document {document_id, content, mode, style:{bold, font_size, font_family}}. "
                        "The reporter role owns Doc drafts via docs.create / docs.write."
                    )
                if integration_id == "gmail":
                    lines.append(
                        "  Gmail: The follow_up role owns compose/revise/send via gmail.draft / "
                        "gmail.send (send is irreversible and may require approval). "
                        "Use app:gmail for inbox list/search/monitor and subscribe_inbox."
                    )
                    lines.append(
                        "  compose_email: draft for user review (always before send); "
                        "send_email {to}: send the approved pending draft only"
                    )
                    lines.append(
                        "  Gmail monitor: subscribe_inbox (notify on new mail); "
                        "unsubscribe_inbox (stop listening)"
                    )
                if integration_id == "x":
                    lines.append(
                        "  X: The x_agent role owns draft/publish via x.draft / x.post "
                        "(post is irreversible and may require approval)."
                    )
                    lines.append(
                        "  Draft text first; only x.post after the user approves."
                    )
                if integration_id == "reddit":
                    lines.append(
                        "  Reddit: The reddit_agent role owns draft/publish via reddit.draft / "
                        "reddit.post (post is irreversible and may require approval)."
                    )
                    lines.append(
                        "  Draft needs subreddit, title, and body; only reddit.post after approval."
                    )
                if integration_id == "linkedin":
                    lines.append(
                        "  LinkedIn: The linkedin_agent role owns draft/publish via linkedin.draft / "
                        "linkedin.post (post is irreversible and may require approval)."
                    )
                    lines.append(
                        "  Draft text first; only linkedin.post after the user approves."
                    )
            else:
                lines.append(
                    f"  → Do NOT use app:{integration_id}. "
                    f"Tell the user to connect {spec['name']} via /integrations/{integration_id}/connect first."
                )
            lines.append("")
        lines.append(
            "Decision rules: The coordinator assigns board tasks to in-process roles "
            "(researcher, reporter, follow_up, watcher, x_agent, reddit_agent, linkedin_agent): "
            "do not hire external agents. "
            "Use web search/fetch for current events and URLs. "
            "For email: follow_up drafts first; only send after approval. "
            "Never send_email on the first request: even if a recipient is given. "
            "For X / Reddit / LinkedIn: assign x_agent / reddit_agent / linkedin_agent; "
            "draft first, publish only after approval. "
            "For Docs and proposals: reporter owns drafts via docs.create / docs.write. "
            "Only route to app:* tools that are CONNECTED. "
            "If the user needs a disconnected integration, use thinking and explain how to connect."
        )
        return "\n".join(lines)

    def available_tools_text(self, user_id: str) -> str:
        """Connected tools only (legacy summary)."""
        lines = ["- thinking: answer directly with reasoning"]
        lines.append(
            "- roles: researcher, reporter, follow_up, watcher (in-process specialists)"
        )
        connected = self._tokens.list_connected(user_id)
        for spec in list_integrations():
            if spec.get("coming_soon") or spec["id"] not in connected:
                continue
            actions = ", ".join(spec["actions"])
            lines.append(f"- app:{spec['id']}: {spec['name']} (actions: {actions})")
        return "\n".join(lines)

    async def run(
        self,
        user_id: str,
        integration_id: str,
        action: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        spec = INTEGRATIONS.get(integration_id)
        if not spec:
            raise RuntimeError(f"Unknown integration: {integration_id}")
        if spec.get("coming_soon"):
            raise RuntimeError(f"{spec['name']} is coming soon")
        payload = dict(params or {})
        emit("tool_start", tool=f"app:{integration_id}", assignee=integration_id, action=action)

        if integration_id == "gmail" and action in {
            "subscribe_inbox",
            "unsubscribe_inbox",
            "check_inbox",
        }:
            from core.context.subscriptions.service import SubscriptionService

            service = SubscriptionService(integration_client=self)
            conversation_id = str(
                payload.get("conversation_id") or current_conversation_id.get() or ""
            ).strip()
            if action == "subscribe_inbox":
                if not conversation_id:
                    raise RuntimeError("conversation_id is required for subscribe_inbox")
                result = await service.subscribe_gmail_inbox(
                    user_id,
                    conversation_id=conversation_id,
                    query=str(payload.get("query", "")),
                    poll_interval_seconds=int(payload.get("poll_interval_seconds", 90)),
                    mission_id=current_mission_id.get() or None,
                )
            elif action == "unsubscribe_inbox":
                if not conversation_id:
                    raise RuntimeError("conversation_id is required for unsubscribe_inbox")
                result = await service.unsubscribe_gmail_inbox(
                    user_id,
                    conversation_id=conversation_id,
                    subscription_id=str(payload.get("subscription_id", "")).strip() or None,
                )
            else:
                sub_id = str(payload.get("subscription_id", "")).strip()
                if not sub_id:
                    raise RuntimeError("subscription_id is required for check_inbox")
                from core.context.subscriptions.store import SubscriptionStore

                sub = SubscriptionStore().get_subscription(sub_id)
                if not sub:
                    raise RuntimeError(f"Subscription not found: {sub_id}")
                new_emails = await service.check_gmail_subscription(sub)
                result = {"new_emails": new_emails, "count": len(new_emails)}
            emit("tool_done", tool=f"app:{integration_id}", assignee=integration_id, status="completed")
            return result

        token = await self._tokens.get_access_token(user_id, integration_id)
        result = await self._executor.execute(integration_id, token, action, payload)
        emit("tool_done", tool=f"app:{integration_id}", assignee=integration_id, status="completed")
        return result

    def summarize_result(self, integration_id: str, action: str, result: dict[str, Any]) -> str:
        try:
            return json.dumps(result, default=str)[:4000]
        except TypeError:
            return str(result)[:4000]
