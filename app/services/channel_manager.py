"""
Channel Manager service.

Manages channel adapter lifecycle and routes inbound messages to agents.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

from app.channels.base import ChannelAdapter, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class ChannelManager:
    """Singleton that manages all channel adapters and routes messages."""

    _instance = None
    _adapters: dict[str, ChannelAdapter]

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._adapters = {}
            cls._instance = inst
        return cls._instance

    async def start(self):
        """Start all adapters that have credentials configured."""
        from app.config import settings

        # Feishu adapter
        if settings.feishu_app_id and settings.feishu_app_secret:
            try:
                from app.channels.feishu import FeishuAdapter
                adapter = FeishuAdapter(settings.feishu_app_id, settings.feishu_app_secret)
                adapter.set_message_handler(self._handle_inbound)
                await adapter.connect()
                self._adapters["feishu"] = adapter
                logger.info("Feishu adapter started")
            except ImportError:
                logger.info("Feishu adapter not available (lark-oapi not installed)")
            except Exception as e:
                logger.warning(f"Failed to start Feishu adapter: {e}")

        # Telegram adapter
        if settings.telegram_bot_token:
            try:
                from app.channels.telegram import TelegramAdapter
                adapter = TelegramAdapter(settings.telegram_bot_token)
                adapter.set_message_handler(self._handle_inbound)
                await adapter.connect()
                self._adapters["telegram"] = adapter
                logger.info("Telegram adapter started")
            except ImportError:
                logger.info("Telegram adapter not available (python-telegram-bot not installed)")
            except Exception as e:
                logger.warning(f"Failed to start Telegram adapter: {e}")

    async def stop(self):
        """Stop all adapters."""
        for name, adapter in self._adapters.items():
            try:
                await adapter.disconnect()
                logger.info(f"Channel adapter '{name}' stopped")
            except Exception as e:
                logger.warning(f"Error stopping adapter '{name}': {e}")
        self._adapters.clear()

    def get_adapter_status(self) -> dict[str, bool]:
        """Get connection status of all adapters."""
        return {name: adapter.is_connected() for name, adapter in self._adapters.items()}

    async def restart_adapter(self, adapter_type: str) -> bool:
        """Restart a specific adapter."""
        adapter = self._adapters.get(adapter_type)
        if not adapter:
            return False

        try:
            await adapter.disconnect()
            await adapter.connect()
            return True
        except Exception as e:
            logger.error(f"Failed to restart adapter '{adapter_type}': {e}")
            return False

    async def _handle_inbound(self, msg: InboundMessage):
        """Handle an inbound message from a channel adapter."""
        from sqlalchemy import select
        from app.db.database import AsyncSessionLocal
        from app.db.models import (
            ChannelBindingDB, ChannelMessageDB, AgentPresetDB,
            PublishedSessionDB, AgentTraceDB, generate_uuid,
        )

        try:
            async with AsyncSessionLocal() as session:
                # Find matching binding
                result = await session.execute(
                    select(ChannelBindingDB).where(
                        ChannelBindingDB.channel_type == msg.channel_type,
                        ChannelBindingDB.external_id == msg.external_id,
                        ChannelBindingDB.enabled == True,
                    )
                )
                binding = result.scalar_one_or_none()

                if not binding:
                    logger.debug(f"No binding for {msg.channel_type}:{msg.external_id}")
                    return

                # Check trigger pattern
                if binding.trigger_pattern:
                    if not re.search(binding.trigger_pattern, msg.content):
                        return

                # Record inbound message
                inbound_record = ChannelMessageDB(
                    id=generate_uuid(),
                    channel_binding_id=binding.id,
                    direction="inbound",
                    external_message_id=msg.external_message_id,
                    sender_id=msg.sender_id,
                    sender_name=msg.sender_name,
                    content=msg.content,
                    message_type=msg.message_type,
                    msg_metadata=msg.metadata,
                )
                session.add(inbound_record)

                # Generate deterministic session_id
                session_key = f"{msg.channel_type}:{msg.external_id}"
                session_id = hashlib.sha256(session_key.encode()).hexdigest()[:36]

                # Load agent preset
                preset = await session.execute(
                    select(AgentPresetDB).where(AgentPresetDB.id == binding.agent_id)
                )
                preset = preset.scalar_one_or_none()
                if not preset:
                    logger.error(f"Agent preset {binding.agent_id} not found for binding {binding.id}")
                    return

                # Load or create session
                pub_session = await session.execute(
                    select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
                )
                pub_session = pub_session.scalar_one_or_none()

                conversation_history = None
                if pub_session and pub_session.agent_context:
                    conversation_history = pub_session.agent_context
                elif not pub_session:
                    pub_session = PublishedSessionDB(
                        id=session_id,
                        agent_id=binding.agent_id,
                        messages=[],
                    )
                    session.add(pub_session)

                await session.commit()

            # Run agent (outside DB session)
            answer = await self._run_agent(
                preset, msg.content, conversation_history, session_id
            )

            # Record outbound and update session
            async with AsyncSessionLocal() as session:
                outbound_record = ChannelMessageDB(
                    id=generate_uuid(),
                    channel_binding_id=binding.id,
                    direction="outbound",
                    content=answer or "",
                    message_type="text",
                )
                session.add(outbound_record)
                await session.commit()

            # Send response via adapter
            if answer:
                adapter = self._adapters.get(msg.channel_type)
                if adapter and adapter.is_connected():
                    await adapter.send_message(OutboundMessage(
                        external_id=msg.external_id,
                        content=answer,
                    ))

        except Exception as e:
            logger.error(f"Error handling inbound message: {e}", exc_info=True)

    async def _run_agent(
        self,
        preset,
        prompt: str,
        conversation_history: Optional[list] = None,
        session_id: Optional[str] = None,
    ) -> Optional[str]:
        """Run a SkillsAgent with the given preset config."""
        from app.agent import SkillsAgent

        try:
            agent = SkillsAgent(
                model=preset.model_name,
                model_provider=preset.model_provider,
                max_turns=preset.max_turns or 60,
                verbose=False,
                allowed_skills=preset.skill_ids,
                allowed_tools=preset.builtin_tools,
                equipped_mcp_servers=preset.mcp_servers,
                custom_system_prompt=preset.system_prompt,
                executor_name=preset.executor_name,
                workspace_id=session_id,
            )

            result = await agent.run(prompt, conversation_history=conversation_history)

            # Update session context
            if session_id and result.final_messages:
                from app.db.database import AsyncSessionLocal
                from app.db.models import PublishedSessionDB
                from sqlalchemy import select

                async with AsyncSessionLocal() as session:
                    pub = await session.execute(
                        select(PublishedSessionDB).where(PublishedSessionDB.id == session_id)
                    )
                    pub = pub.scalar_one_or_none()
                    if pub:
                        pub.agent_context = result.final_messages
                        # Append display messages
                        display = pub.messages or []
                        display.append({"role": "user", "content": prompt})
                        if result.answer:
                            display.append({"role": "assistant", "content": result.answer})
                        pub.messages = display
                        pub.updated_at = datetime.utcnow()
                        await session.commit()

            return result.answer

        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            return f"Error: {str(e)}"

    async def send_to_channel(self, binding_id: str, content: str):
        """Send a message to a channel binding (used by scheduler)."""
        from sqlalchemy import select
        from app.db.database import AsyncSessionLocal
        from app.db.models import ChannelBindingDB, ChannelMessageDB, generate_uuid

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ChannelBindingDB).where(ChannelBindingDB.id == binding_id)
            )
            binding = result.scalar_one_or_none()
            if not binding:
                logger.warning(f"Channel binding {binding_id} not found")
                return

            adapter = self._adapters.get(binding.channel_type)
            if not adapter or not adapter.is_connected():
                logger.warning(f"No connected adapter for {binding.channel_type}")
                return

            # Send message
            await adapter.send_message(OutboundMessage(
                external_id=binding.external_id,
                content=content,
            ))

            # Record outbound
            msg_record = ChannelMessageDB(
                id=generate_uuid(),
                channel_binding_id=binding.id,
                direction="outbound",
                content=content,
                message_type="text",
            )
            session.add(msg_record)
            await session.commit()
