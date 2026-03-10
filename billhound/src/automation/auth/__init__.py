"""
Authentication strategies for browser-based service login.

Public API:
    BaseAuthStrategy  - abstract base for auth strategies
    AuthResult        - immutable result dataclass
    DecryptedCredential - plaintext credential transfer object
    get_auth_strategy - look up auth strategy by service name
    has_auth_strategy - check if auth strategy exists
"""
from src.automation.auth.base_auth_strategy import (
    BaseAuthStrategy,
    DecryptedCredential,
)
from src.automation.auth.auth_registry import get_auth_strategy, has_auth_strategy
from src.automation.auth.models import AuthResult

# Import auth flows to trigger registration
import src.automation.auth.flows  # noqa: F401

__all__ = [
    "AuthResult",
    "BaseAuthStrategy",
    "DecryptedCredential",
    "get_auth_strategy",
    "has_auth_strategy",
]
