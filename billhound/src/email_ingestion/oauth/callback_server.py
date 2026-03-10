"""
Minimal aiohttp server to receive OAuth callbacks.
Routes:
  GET /oauth/gmail/callback?code=...&state=...
  GET /oauth/outlook/callback?code=...&state=...

Uses session-per-request: each callback creates its own DB session,
commits on success, and closes automatically. This matches the
session-per-handler pattern used in all Telegram handlers.

On successful OAuth, fires a background backfill task to scan the last
90 days of email and deliver an instant subscription summary.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import structlog
from aiohttp import web
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.repositories.oauth_token_repo import OAuthTokenRepository
from src.email_ingestion.oauth.errors import OAuthError
from src.email_ingestion.oauth.gmail_oauth import GmailOAuthClient
from src.email_ingestion.oauth.outlook_oauth import OutlookOAuthClient
from src.trust.audit import AuditWriter
from src.trust.consent import ConsentTracker
from src.trust.encryption import EncryptionService

logger = structlog.get_logger()

SUCCESS_HTML = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2>Connected successfully!</h2>
<p>You can close this window and return to Telegram.</p>
</body></html>"""

ERROR_HTML = """<!DOCTYPE html>
<html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h2>Connection failed</h2>
<p>{message}</p>
<p>Please try again from Telegram.</p>
</body></html>"""

# Simple health check HTML
HEALTH_HTML = """<!DOCTYPE html>
<html><body><p>ok</p></body></html>"""


class OAuthCallbackServer:
    def __init__(
        self,
        gmail_client: GmailOAuthClient,
        outlook_client: OutlookOAuthClient,
        session_factory: async_sessionmaker[AsyncSession],
        encryption: EncryptionService,
        backfill: object | None = None,
    ) -> None:
        self._gmail = gmail_client
        self._outlook = outlook_client
        self._session_factory = session_factory
        self._encryption = encryption
        self._backfill = backfill  # BackfillOrchestrator (optional)
        self._app = web.Application()
        self._app.router.add_get("/health", self._handle_health)
        self._app.router.add_get("/oauth/gmail/callback", self._handle_gmail)
        self._app.router.add_get("/oauth/outlook/callback", self._handle_outlook)
        self._runner: web.AppRunner | None = None

    async def start(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host, port)
        await site.start()
        logger.info("oauth_callback_server.started", host=host, port=port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            logger.info("oauth_callback_server.stopped")

    @staticmethod
    async def _handle_health(request: web.Request) -> web.Response:
        return web.Response(text=HEALTH_HTML, content_type="text/html")

    async def _handle_gmail(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")

        if error:
            logger.warning("oauth.gmail.denied", error=error)
            return web.Response(
                text=ERROR_HTML.format(message=error),
                content_type="text/html",
            )

        if not code or not state:
            return web.Response(
                text=ERROR_HTML.format(message="Missing code or state"),
                content_type="text/html",
                status=400,
            )

        user_id_str = self._gmail.verify_state(state)
        if not user_id_str:
            return web.Response(
                text=ERROR_HTML.format(message="Invalid state parameter"),
                content_type="text/html",
                status=400,
            )

        try:
            tokens = await self._gmail.exchange_code(code)
            user_id = uuid.UUID(user_id_str)
            expiry = datetime.now(timezone.utc) + timedelta(
                seconds=tokens.get("expires_in", 3600)
            )

            # Fetch the user's email address from Google
            email = await self._fetch_gmail_email(tokens["access_token"])

            # Session-per-request: create a fresh session for this callback
            async with self._session_factory() as session:
                token_repo = OAuthTokenRepository(session, self._encryption)
                audit = AuditWriter(session)
                consent = ConsentTracker(audit)

                await token_repo.store_token(
                    user_id=user_id,
                    provider="gmail",
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token", ""),
                    token_expiry=expiry,
                    scopes_granted=" ".join(GmailOAuthClient.SCOPES),
                    email_address=email,
                )

                await consent.record_grant(
                    user_id=user_id,
                    provider="gmail",
                    scopes=GmailOAuthClient.SCOPES,
                    email=email,
                )

                await session.commit()

            logger.info("oauth.gmail.connected", user_id=str(user_id), email=email)

            # Fire-and-forget: 90-day historical backfill
            if self._backfill:
                asyncio.create_task(
                    self._safe_backfill(user_id, "gmail"),
                    name=f"backfill-{user_id}-gmail",
                )

            return web.Response(text=SUCCESS_HTML, content_type="text/html")

        except OAuthError as e:
            logger.error("oauth.gmail.exchange_failed", error=str(e))
            return web.Response(
                text=ERROR_HTML.format(message=str(e)),
                content_type="text/html",
                status=500,
            )

    async def _handle_outlook(self, request: web.Request) -> web.Response:
        code = request.query.get("code")
        state = request.query.get("state")
        error = request.query.get("error")

        if error:
            logger.warning("oauth.outlook.denied", error=error)
            return web.Response(
                text=ERROR_HTML.format(message=error),
                content_type="text/html",
            )

        if not code or not state:
            return web.Response(
                text=ERROR_HTML.format(message="Missing code or state"),
                content_type="text/html",
                status=400,
            )

        user_id_str = self._outlook.verify_state(state)
        if not user_id_str:
            return web.Response(
                text=ERROR_HTML.format(message="Invalid state parameter"),
                content_type="text/html",
                status=400,
            )

        try:
            tokens = await self._outlook.exchange_code(code)
            user_id = uuid.UUID(user_id_str)
            expiry = datetime.now(timezone.utc) + timedelta(
                seconds=tokens.get("expires_in", 3600)
            )

            email = await self._fetch_outlook_email(tokens["access_token"])

            # Session-per-request: create a fresh session for this callback
            async with self._session_factory() as session:
                token_repo = OAuthTokenRepository(session, self._encryption)
                audit = AuditWriter(session)
                consent = ConsentTracker(audit)

                await token_repo.store_token(
                    user_id=user_id,
                    provider="outlook",
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token", ""),
                    token_expiry=expiry,
                    scopes_granted=" ".join(OutlookOAuthClient.SCOPES),
                    email_address=email,
                )

                await consent.record_grant(
                    user_id=user_id,
                    provider="outlook",
                    scopes=OutlookOAuthClient.SCOPES,
                    email=email,
                )

                await session.commit()

            logger.info("oauth.outlook.connected", user_id=str(user_id), email=email)

            # Fire-and-forget: 90-day historical backfill
            if self._backfill:
                asyncio.create_task(
                    self._safe_backfill(user_id, "outlook"),
                    name=f"backfill-{user_id}-outlook",
                )

            return web.Response(text=SUCCESS_HTML, content_type="text/html")

        except OAuthError as e:
            logger.error("oauth.outlook.exchange_failed", error=str(e))
            return web.Response(
                text=ERROR_HTML.format(message=str(e)),
                content_type="text/html",
                status=500,
            )

    async def _safe_backfill(self, user_id: uuid.UUID, provider: str) -> None:
        """Run backfill in background, catching all errors so the server never crashes."""
        try:
            result = await self._backfill.run_backfill(user_id, provider)  # type: ignore[union-attr]
            logger.info(
                "backfill.completed",
                user_id=str(user_id),
                provider=provider,
                subscriptions=result.subscriptions_found,
                monthly_total=str(result.total_monthly),
            )
        except Exception:
            logger.exception(
                "backfill.failed", user_id=str(user_id), provider=provider
            )

    @staticmethod
    async def _fetch_gmail_email(access_token: str) -> str:
        """Fetch user's email address from Google userinfo endpoint."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("email", "unknown@gmail.com")
                return "unknown@gmail.com"

    @staticmethod
    async def _fetch_outlook_email(access_token: str) -> str:
        """Fetch user's email from Microsoft Graph /me endpoint."""
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("mail", data.get("userPrincipalName", "unknown@outlook.com"))
                return "unknown@outlook.com"
