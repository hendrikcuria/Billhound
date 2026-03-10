"""
Prompt templates for subscription extraction.
Kept separate from provider logic for easy iteration.
"""
from __future__ import annotations

from src.email_ingestion.types import SubscriptionSignal

SYSTEM_PROMPT = """\
You are a subscription detection assistant. Given email or bank statement text, \
extract subscription/recurring charge information.

For each subscription found, return a JSON object with a "subscriptions" key \
containing an array of objects with these fields:
- service_name: string (the service/company name)
- amount: number (the charge amount)
- currency: string (3-letter code, default "MYR")
- billing_cycle: string (weekly | monthly | quarterly | semi_annual | annual | unknown)
- next_renewal_date: string or null (ISO date YYYY-MM-DD if determinable)
- trial_end_date: string or null (ISO date if this is a trial)
- confidence_score: number 0.0-1.0 (how confident this is a real subscription)
- cancellation_url: string or null (if a cancellation link is found)
- category: string or null (streaming | music | saas | fitness | gaming | news | \
cloud_storage | productivity | education | food_delivery | finance | vpn | other)

Rules:
- Only extract recurring charges, not one-time purchases
- If the amount or service name is unclear, set confidence_score below 0.70
- For bank statements, look for recurring merchant names appearing monthly
- Return valid JSON only, no markdown formatting
- If no subscriptions found, return {"subscriptions": []}
"""


def build_extraction_prompt(signals: list[SubscriptionSignal]) -> str:
    """Build the user message from collected signals."""
    parts: list[str] = []
    for i, signal in enumerate(signals, 1):
        parts.append(f"--- Source {i} ({signal.source}) ---")
        if signal.subject:
            parts.append(f"Subject: {signal.subject}")
        parts.append(f"From: {signal.sender}")
        parts.append(signal.raw_text)
        parts.append("")
    return "\n".join(parts)
