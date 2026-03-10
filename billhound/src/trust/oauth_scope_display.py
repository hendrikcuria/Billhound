"""
Human-readable OAuth scope descriptions.
Ensures users understand exactly what permissions Billhound requests.
"""
from __future__ import annotations

GMAIL_SCOPES = {
    "https://www.googleapis.com/auth/gmail.readonly": (
        "Read your email messages and settings (read-only, cannot send or modify)"
    ),
}

OUTLOOK_SCOPES = {
    "https://graph.microsoft.com/Mail.Read": (
        "Read your email messages (read-only, cannot send or modify)"
    ),
}


def format_scope_display(provider: str, scopes: list[str]) -> str:
    """Format OAuth scopes into a human-readable message for Telegram."""
    scope_map = GMAIL_SCOPES if provider == "gmail" else OUTLOOK_SCOPES

    lines = [f"Permissions requested for {provider.title()}:\n"]
    for scope in scopes:
        description = scope_map.get(scope, f"Unknown scope: {scope}")
        lines.append(f"  - {description}")

    lines.append(
        "\nBillhound will ONLY read subscription-related emails. "
        "It cannot send emails, delete messages, or access contacts."
    )
    return "\n".join(lines)
