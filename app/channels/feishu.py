"""
Feishu (Lark) channel adapter.

Uses the official lark-oapi SDK with WebSocket long-connection mode,
so no public URL / webhook endpoint is needed. The lark WS client runs
in a daemon thread; inbound messages are bridged to the async event loop
via ``asyncio.run_coroutine_threadsafe``.

Required environment variables:
    FEISHU_APP_ID      - Feishu app ID
    FEISHU_APP_SECRET  - Feishu app secret

Feishu app permissions needed:
    im:message            - Send messages
    im:message.receive_v1 - Receive messages (event subscription)
"""

import asyncio
import json
import logging
from typing import Optional

import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
from lark_oapi.event.dispatcher_handler import P2ImMessageReceiveV1

from app.channels.base import ChannelAdapter, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class FeishuAdapter(ChannelAdapter):
    """Feishu / Lark messaging adapter.

    Connects via WebSocket (``lark.ws.Client``), receives ``im.message.receive_v1``
    events and sends replies through ``im.v1.message.create``.
    """

    channel_type = "feishu"

    def __init__(self, app_id: str, app_secret: str):
        self._app_id = app_id
        self._app_secret = app_secret
        self._client: Optional[lark.Client] = None
        self._ws_client = None
        self._connected = False
        self._bot_open_id: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Start the Feishu WebSocket connection."""
        # Capture the current event loop so the WS thread can schedule coroutines
        self._loop = asyncio.get_running_loop()

        # Build the API client (used for sending messages)
        self._client = (
            lark.Client.builder()
            .app_id(self._app_id)
            .app_secret(self._app_secret)
            .build()
        )

        # Fetch bot's own open_id so we can filter self-sent messages
        self._bot_open_id = await self._get_bot_open_id()
        if self._bot_open_id:
            logger.info(f"Feishu bot open_id: {self._bot_open_id}")
        else:
            logger.warning("Could not retrieve Feishu bot open_id; self-message filtering disabled")

        # Build event dispatcher (encryption/verification tokens left empty for WS mode)
        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_message)
            .build()
        )

        # Start the WebSocket client in a separate thread.
        #
        # The lark SDK captures a MODULE-LEVEL event loop at import time:
        #   lark_oapi/ws/client.py:  loop = asyncio.get_event_loop()
        # Then start() calls loop.run_until_complete() on this captured loop.
        # Under uvicorn, this is the running uvloop → RuntimeError.
        #
        # Fix: monkey-patch the module-level `loop` variable in the SDK
        # with a fresh stdlib event loop before calling start().
        import threading
        import lark_oapi.ws.client as _lark_ws_mod

        def _run_ws():
            # Create a clean stdlib event loop for this thread
            fresh_loop = asyncio.SelectorEventLoop()
            asyncio.set_event_loop(fresh_loop)
            # Patch the SDK's module-level loop so start() uses ours
            _lark_ws_mod.loop = fresh_loop

            ws_client = lark.ws.Client(
                self._app_id,
                self._app_secret,
                event_handler=handler,
                log_level=lark.LogLevel.WARNING,
            )
            self._ws_client = ws_client

            while self._connected:
                try:
                    ws_client.start()
                except Exception as e:
                    logger.error(f"Feishu WS client error: {e}", exc_info=True)
                if self._connected:
                    import time
                    time.sleep(5)  # reconnect backoff

        self._ws_thread = threading.Thread(
            target=_run_ws,
            daemon=True,
            name="feishu-ws",
        )
        self._ws_thread.start()
        self._connected = True
        logger.info("Feishu adapter connected via WebSocket")

    async def disconnect(self) -> None:
        """Stop the Feishu connection."""
        self._connected = False
        # The lark WS client does not expose a clean shutdown API;
        # dropping the reference lets the daemon thread exit with the process.
        self._ws_client = None
        self._client = None
        logger.info("Feishu adapter disconnected")

    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    async def send_message(self, message: OutboundMessage) -> None:
        """Send a text message to a Feishu chat."""
        if not self._client:
            raise RuntimeError("Feishu adapter not connected")

        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(message.external_id)
                .msg_type("text")
                .content(json.dumps({"text": message.content}))
                .build()
            )
            .build()
        )

        response = self._client.im.v1.message.create(request)
        if not response.success():
            logger.error(
                f"Failed to send Feishu message: code={response.code} msg={response.msg}"
            )

    # ------------------------------------------------------------------
    # Inbound (called from lark WS daemon thread)
    # ------------------------------------------------------------------

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        """Handle an inbound message event from the Feishu WebSocket.

        This callback is invoked on the lark WS daemon thread, so we bridge
        to the main asyncio loop via ``run_coroutine_threadsafe``.
        """
        try:
            event = data.event
            msg = event.message
            sender = event.sender

            # Only process text messages
            if msg.message_type != "text":
                return

            # Derive sender open_id
            sender_id = ""
            if sender and sender.sender_id:
                sender_id = sender.sender_id.open_id or ""

            # Skip messages sent by the bot itself
            if self._bot_open_id and sender_id == self._bot_open_id:
                return

            # Parse message content (Feishu wraps text as {"text": "..."})
            try:
                content = json.loads(msg.content).get("text", "")
            except (json.JSONDecodeError, TypeError):
                content = ""
            if not content:
                return

            # Build the platform-agnostic InboundMessage
            inbound = InboundMessage(
                channel_type="feishu",
                external_id=msg.chat_id,
                sender_id=sender_id,
                sender_name=sender_id,  # Feishu doesn't expose name in event; use ID
                content=content,
                message_type="text",
                external_message_id=msg.message_id,
            )

            # Bridge from the WS thread into the async event loop
            if self._message_handler and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._message_handler(inbound),
                    self._loop,
                )
        except Exception as e:
            logger.error(f"Error handling Feishu message: {e}", exc_info=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_bot_open_id(self) -> Optional[str]:
        """Fetch the bot's own ``open_id`` via the Feishu REST API.

        This is used to filter out messages the bot sends to itself.
        Uses ``httpx`` (already a project dependency) to obtain a
        tenant_access_token and then call ``GET /bot/v3/info``.
        """
        try:
            import httpx

            base_url = "https://open.feishu.cn/open-apis"

            async with httpx.AsyncClient(timeout=10) as http:
                # Step 1: obtain tenant access token
                token_resp = await http.post(
                    f"{base_url}/auth/v3/tenant_access_token/internal",
                    json={
                        "app_id": self._app_id,
                        "app_secret": self._app_secret,
                    },
                )
                token_data = token_resp.json()
                tenant_token = token_data.get("tenant_access_token")
                if not tenant_token:
                    logger.warning(
                        f"Failed to get tenant_access_token: {token_data.get('msg')}"
                    )
                    return None

                # Step 2: fetch bot info
                bot_resp = await http.get(
                    f"{base_url}/bot/v3/info",
                    headers={"Authorization": f"Bearer {tenant_token}"},
                )
                bot_data = bot_resp.json()
                return bot_data.get("bot", {}).get("open_id")

        except Exception as e:
            logger.warning(f"Failed to get Feishu bot open_id: {e}")
            return None
