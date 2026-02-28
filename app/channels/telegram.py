"""
Telegram channel adapter using python-telegram-bot (v21+).

Uses long polling mode — no public URL or webhook needed.
Telegram chat_id can be negative (group chats); stored as string in external_id.
"""

import asyncio
import logging
from typing import Optional

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from app.channels.base import ChannelAdapter, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)

# Telegram message length limit
_MAX_MESSAGE_LENGTH = 4096


class TelegramAdapter(ChannelAdapter):
    """Adapter for Telegram Bot API via long polling."""

    channel_type = "telegram"

    def __init__(self, bot_token: str):
        self._bot_token = bot_token
        self._application: Optional[Application] = None
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        self._application = (
            Application.builder()
            .token(self._bot_token)
            .build()
        )

        # Register handler for plain text messages (skip commands)
        self._application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._on_message,
            )
        )

        # Initialize and start long polling
        await self._application.initialize()
        await self._application.start()
        await self._application.updater.start_polling(
            drop_pending_updates=True,
        )

        self._connected = True
        logger.info("Telegram adapter connected via long polling")

    async def disconnect(self) -> None:
        self._connected = False
        if self._application:
            try:
                if self._application.updater and self._application.updater.running:
                    await self._application.updater.stop()
                if self._application.running:
                    await self._application.stop()
                await self._application.shutdown()
            except Exception as e:
                logger.warning(f"Error stopping Telegram adapter: {e}")
            self._application = None

    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    async def send_message(self, message: OutboundMessage) -> None:
        if not self._application or not self._application.bot:
            raise RuntimeError("Telegram adapter not connected")

        try:
            chat_id = int(message.external_id)
        except ValueError:
            logger.error(f"Invalid Telegram chat_id: {message.external_id}")
            return

        content = message.content
        if len(content) <= _MAX_MESSAGE_LENGTH:
            await self._application.bot.send_message(
                chat_id=chat_id,
                text=content,
            )
        else:
            # Split into chunks to stay within the 4096-char limit
            for i in range(0, len(content), _MAX_MESSAGE_LENGTH):
                chunk = content[i : i + _MAX_MESSAGE_LENGTH]
                await self._application.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                )

    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------

    async def _on_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle an inbound text message from Telegram."""
        try:
            message = update.effective_message
            if not message or not message.text:
                return

            chat = update.effective_chat
            user = update.effective_user

            inbound = InboundMessage(
                channel_type="telegram",
                external_id=str(chat.id),
                sender_id=str(user.id) if user else "unknown",
                sender_name=user.full_name if user else "unknown",
                content=message.text,
                message_type="text",
                external_message_id=str(message.message_id),
            )

            if self._message_handler:
                await self._message_handler(inbound)
        except Exception as e:
            logger.error(f"Error handling Telegram message: {e}", exc_info=True)
