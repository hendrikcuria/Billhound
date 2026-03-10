"""
Static merchant database for category mapping.
MVP: hardcoded dict. Future: load from JSON or database table.
"""
from __future__ import annotations

MERCHANT_CATEGORIES: dict[str, str] = {
    # Streaming
    "netflix": "streaming",
    "disney+": "streaming",
    "disney plus": "streaming",
    "hbo": "streaming",
    "hbo max": "streaming",
    "youtube premium": "streaming",
    "youtube music": "music",
    "hulu": "streaming",
    "amazon prime": "streaming",
    "apple tv": "streaming",
    "viu": "streaming",
    # Music
    "spotify": "music",
    "apple music": "music",
    "tidal": "music",
    "deezer": "music",
    # SaaS / Productivity
    "adobe": "saas",
    "adobe creative cloud": "saas",
    "microsoft 365": "productivity",
    "office 365": "productivity",
    "google one": "cloud_storage",
    "google workspace": "productivity",
    "dropbox": "cloud_storage",
    "icloud": "cloud_storage",
    "notion": "productivity",
    "slack": "productivity",
    "zoom": "productivity",
    "canva": "saas",
    "figma": "saas",
    "github": "saas",
    "chatgpt": "saas",
    "openai": "saas",
    "claude": "saas",
    "grammarly": "productivity",
    # VPN
    "nordvpn": "vpn",
    "expressvpn": "vpn",
    "surfshark": "vpn",
    # Gaming
    "xbox game pass": "gaming",
    "playstation plus": "gaming",
    "ps plus": "gaming",
    "nintendo": "gaming",
    "ea play": "gaming",
    # Fitness
    "gym": "fitness",
    "fitness first": "fitness",
    "anytime fitness": "fitness",
    "peloton": "fitness",
    # Food Delivery
    "grabfood": "food_delivery",
    "foodpanda": "food_delivery",
    "grab": "food_delivery",
    "shopee food": "food_delivery",
    # News
    "the star": "news",
    "nyt": "news",
    "new york times": "news",
    "wall street journal": "news",
    "wsj": "news",
    # Education
    "coursera": "education",
    "udemy": "education",
    "skillshare": "education",
    "duolingo": "education",
    # Finance
    "ynab": "finance",
}


# ---------------------------------------------------------------------------
# Known merchant sender email addresses for backfill filtering.
# Maps sender address → normalized service name.
# ---------------------------------------------------------------------------
MERCHANT_SENDERS: dict[str, str] = {
    # Netflix
    "info@account.netflix.com": "netflix",
    "info@members.netflix.com": "netflix",
    # Spotify
    "no-reply@spotify.com": "spotify",
    "noreply@spotify.com": "spotify",
    # Adobe
    "noreply@email.adobe.com": "adobe",
    "adobe@adobesystems.com": "adobe",
    # Canva
    "noreply@canva.com": "canva",
    # Amazon Prime
    "auto-confirm@amazon.com": "amazon prime",
    "digital-no-reply@amazon.com": "amazon prime",
    "no-reply@amazon.com": "amazon prime",
    # Disney+
    "disneyplus@mail.disneyplus.com": "disney+",
    "no-reply@disneyplus.com": "disney+",
    # YouTube Premium / Google
    "noreply-purchases@youtube.com": "youtube premium",
    "googleplay-noreply@google.com": "youtube premium",
    # Hulu
    "huluinfo@hulu.com": "hulu",
    "no-reply@hulu.com": "hulu",
    # Microsoft 365
    "microsoft365@microsoft.com": "microsoft 365",
    "msa@communication.microsoft.com": "microsoft 365",
    # NordVPN
    "noreply@nordaccount.com": "nordvpn",
    "support@nordvpn.com": "nordvpn",
    # Google One / Workspace
    "googleone-noreply@google.com": "google one",
    "payments-noreply@google.com": "google one",
    # Apple (iCloud, Apple TV, Apple Music)
    "no_reply@email.apple.com": "apple",
    "apple@insideapple.apple.com": "apple",
    # Dropbox
    "no-reply@dropbox.com": "dropbox",
    # Grab / GrabFood
    "noreply@grab.com": "grab",
    # ExpressVPN
    "support@expressvpn.com": "expressvpn",
}


def get_known_sender_addresses() -> list[str]:
    """Return all known merchant sender email addresses for backfill filtering."""
    return list(MERCHANT_SENDERS.keys())


def lookup_category(service_name: str) -> str | None:
    """Case-insensitive lookup in merchant database."""
    normalized = service_name.lower().strip()
    if not normalized:
        return None
    # Exact match first
    if normalized in MERCHANT_CATEGORIES:
        return MERCHANT_CATEGORIES[normalized]
    # Substring match
    for merchant, category in MERCHANT_CATEGORIES.items():
        if merchant in normalized or normalized in merchant:
            return category
    return None
