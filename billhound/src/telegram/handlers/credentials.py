"""
Credential management handlers for Telegram.

/addcreds <service>  - start credential collection conversation
/mycreds             - list stored credentials (usernames only, NEVER passwords)
/deletecreds <service> - remove stored credentials

Security:
- Password messages are deleted from chat immediately after reading
- Passwords are encrypted before storage via AES-256-GCM
- Memory cleanup: del password after use
"""
from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.db.repositories.service_credential_repo import ServiceCredentialRepository
from src.telegram.handlers._common import get_user_or_reply
from src.trust.audit import AuditWriter
from src.trust.encryption import EncryptionService

logger = structlog.get_logger()

# ConversationHandler states
AWAITING_USERNAME, AWAITING_PASSWORD = range(2)


async def addcreds_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry point: /addcreds <service_name>."""
    parts = update.message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "Usage: /addcreds <service_name>\n"
            "Example: /addcreds netflix"
        )
        return ConversationHandler.END

    service_name = parts[1].strip().lower()
    context.user_data["cred_service"] = service_name

    await update.message.reply_text(
        f"Adding credentials for {service_name}.\n"
        "Please send your username/email for this service:"
    )
    return AWAITING_USERNAME


async def addcreds_username(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive username, ask for password."""
    username = update.message.text.strip()
    context.user_data["cred_username"] = username

    await update.message.reply_text(
        "Now send your password.\n"
        "I will delete your message immediately after reading it."
    )
    return AWAITING_PASSWORD


async def addcreds_password(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Receive password, encrypt and store, delete password message."""
    password = update.message.text.strip()

    # IMMEDIATELY delete the password message from chat
    try:
        await update.message.delete()
    except Exception:
        logger.warning("credentials.delete_message_failed")

    service_name = context.user_data.pop("cred_service", None)
    username = context.user_data.pop("cred_username", None)

    if not service_name or not username:
        await update.effective_chat.send_message(
            "Something went wrong. Please start over with /addcreds"
        )
        return ConversationHandler.END

    session_factory = context.bot_data["session_factory"]
    settings = context.bot_data["settings"]
    encryption = EncryptionService(settings.encryption_key.get_secret_value())

    try:
        async with session_factory() as session:
            user = await get_user_or_reply(update, session)
            if not user:
                return ConversationHandler.END

            repo = ServiceCredentialRepository(session, encryption)
            await repo.upsert_credential(
                user_id=user.id,
                service_name=service_name,
                username=username,
                password=password,
            )

            audit = AuditWriter(session)
            await audit.log(
                action="credential_stored",
                user_id=user.id,
                entity_type="service_credential",
                details={"service_name": service_name},
            )
            await session.commit()

        await update.effective_chat.send_message(
            f"Credentials for {service_name} stored securely.\n"
            "Your password message has been deleted from chat."
        )
    finally:
        del password

    return ConversationHandler.END


async def addcreds_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Allow user to /cancel the credential flow."""
    context.user_data.pop("cred_service", None)
    context.user_data.pop("cred_username", None)
    await update.message.reply_text("Credential setup cancelled.")
    return ConversationHandler.END


async def mycreds_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """List stored credentials (show service + username, NEVER password)."""
    session_factory = context.bot_data["session_factory"]
    settings = context.bot_data["settings"]
    encryption = EncryptionService(settings.encryption_key.get_secret_value())

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return

        repo = ServiceCredentialRepository(session, encryption)
        credentials = await repo.get_by_user(user.id)

        if not credentials:
            await update.message.reply_text(
                "No stored credentials.\n"
                "Use /addcreds <service> to add login credentials."
            )
            return

        lines = ["Stored credentials:\n"]
        for cred in credentials:
            username = repo.decrypt_username(cred)
            lines.append(f"  {cred.service_name}: {username}")
        lines.append("\nPasswords are encrypted and never displayed.")
        lines.append("Use /deletecreds <service> to remove credentials.")

        await update.message.reply_text("\n".join(lines))


async def deletecreds_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete stored credentials for a service."""
    parts = update.message.text.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "Usage: /deletecreds <service_name>\n"
            "Example: /deletecreds netflix"
        )
        return

    service_name = parts[1].strip().lower()
    session_factory = context.bot_data["session_factory"]
    settings = context.bot_data["settings"]
    encryption = EncryptionService(settings.encryption_key.get_secret_value())

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return

        repo = ServiceCredentialRepository(session, encryption)
        deleted = await repo.delete_by_service(user.id, service_name)

        if deleted:
            audit = AuditWriter(session)
            await audit.log(
                action="credential_deleted",
                user_id=user.id,
                entity_type="service_credential",
                details={"service_name": service_name},
            )
            await session.commit()
            await update.message.reply_text(
                f"Credentials for {service_name} deleted."
            )
        else:
            await update.message.reply_text(
                f"No credentials found for {service_name}."
            )


def build_addcreds_conversation() -> ConversationHandler:
    """Build the ConversationHandler for /addcreds multi-step flow."""
    return ConversationHandler(
        entry_points=[CommandHandler("addcreds", addcreds_start)],
        states={
            AWAITING_USERNAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, addcreds_username
                )
            ],
            AWAITING_PASSWORD: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, addcreds_password
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", addcreds_cancel)],
    )
