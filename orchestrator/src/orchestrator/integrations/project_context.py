"""Static project context for content composition (emails, docs)."""

from __future__ import annotations

COGNILANCE_DESCRIPTION = """
Cognilance is an AI orchestrator that connects to the tools people already use —
Gmail, Google Calendar, Google Drive, Slack, GitHub, and more — and completes real
tasks on their behalf. Users chat in natural language; Cognilance plans the work,
uses connected integrations, and can hire specialized marketplace agents for advanced
workflows. It supports background listeners (e.g. notify when new email arrives),
scheduled recurring tasks, web research, and rich document creation — all with
user review before sensitive actions like sending email.
""".strip()


def project_context_for_composition(topic_hint: str = "") -> str:
    """Return project blurb when the topic relates to Cognilance."""
    hint = topic_hint.lower()
    if any(
        term in hint
        for term in ("cognilance", "orchestrator", "this product", "this platform", "our product")
    ):
        return f"\n\nProject context (use when relevant):\n{COGNILANCE_DESCRIPTION}\n"
    return ""
