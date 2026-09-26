"""Async WebSocket client for a local ATMOS WG1000 gateway."""

from __future__ import annotations

import asyncio
import gzip
import logging
import os
import ssl
from collections.abc import Sequence
from types import TracebackType
from typing import Protocol, Self

from websockets.asyncio.client import connect

from pyatmos_wg1000.errors import NotConnectedError, ProtocolError
from pyatmos_wg1000.protocol.data import (
    InfoChunk,
    InfoDump,
    assemble_info_chunks,
    decode_info_chunk,
    decode_own_text,
    encode_data_request,
)
from pyatmos_wg1000.protocol.enums import Channel, CommandCode, DataKind, LoginAction
from pyatmos_wg1000.protocol.files import decode_file_chunk, encode_file_ack, encode_file_request
from pyatmos_wg1000.protocol.frame import SESSION_ID_LENGTH, Command, Frame, decode_server_frame, encode_client_frame
from pyatmos_wg1000.protocol.login import LoginResult, encode_login, parse_login_result
from pyatmos_wg1000.protocol.params import ParamRecord, decode_param_read, encode_param_read

logger = logging.getLogger(__name__)

_WS_PATH = "/api/wss"


class Socket(Protocol):
    """The slice of a WebSocket connection this client uses."""

    async def send(self, message: bytes) -> None:
        """Send one binary frame."""

    async def recv(self) -> bytes | str:
        """Receive the next frame."""

    async def close(self) -> None:
        """Close the socket."""


class AtmosClient:
    """One WG1000 session.

    The gateway answers requests on the same socket. It does not push sensor
    values on its own. Call :meth:`read_registers` on the poll interval you want.

    The device certificate is signed by a private CA that the web UI downloads
    after connect (``Atmos-Device-CA.crt``). Pass ``verify_tls=False`` only
    when you accept that, or load the CA into the SSL context yourself later.

    Args:
        host: Gateway host name or IP address, without a scheme.
        port: TLS port. The UI uses 443.
        verify_tls: Verify the gateway certificate. Defaults to true.
        session_id: 32-byte client session id. Generated when omitted.
    """

    def __init__(
        self,
        host: str,
        *,
        port: int = 443,
        verify_tls: bool = True,
        session_id: bytes | None = None,
    ) -> None:
        """Store connection settings. The socket stays closed until :meth:`connect`."""
        if not host:
            raise ProtocolError("host is empty")
        if session_id is not None and len(session_id) != SESSION_ID_LENGTH:
            raise ProtocolError(f"session id must be {SESSION_ID_LENGTH} bytes")
        self._host = host
        self._port = port
        self._verify_tls = verify_tls
        self.session_id = session_id if session_id is not None else os.urandom(SESSION_ID_LENGTH)
        self._socket: Socket | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> Self:
        """Open the WebSocket and return this client."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the WebSocket."""
        await self.aclose()

    async def connect(self) -> None:
        """Open ``wss://<host>:<port>/api/wss``.

        SSL context construction is run in a worker thread so Home Assistant
        does not see blocking ``load_default_certs`` on the event loop.
        """
        if self._socket is not None:
            return
        ssl_context = await asyncio.to_thread(self._ssl_context)
        self._socket = await connect(self.url, ssl=ssl_context)
        logger.debug("connected to %s", self.url)

    async def aclose(self) -> None:
        """Close the WebSocket. Safe to call more than once."""
        socket = self._socket
        self._socket = None
        if socket is not None:
            await socket.close()

    @property
    def url(self) -> str:
        """WebSocket URL for this client."""
        return f"wss://{self._host}:{self._port}{_WS_PATH}"

    async def hello(self) -> int:
        """Send Hello and return the login-state byte.

        Returns:
            ``0`` when nobody is logged in on this session. ``1`` is a user
            and ``2`` is a technician, matching the UI ``LOGIN`` enum.
        """
        frame = await self.exchange([Command(channel=Channel.WS, code=CommandCode.HELLO)])
        payload = _only_payload(frame, CommandCode.HELLO)
        if len(payload) != 1:
            raise ProtocolError(f"hello payload is {len(payload)} bytes, expected 1")
        return payload[0]

    async def login(self, username: str, password: str, *, stay: bool = False) -> LoginResult:
        """Log in with the same payload the web UI sends.

        Args:
            username: Gateway user name.
            password: Gateway password.
            stay: Ask the gateway to keep the session after disconnect.

        Returns:
            The role and lockout fields from the response.
        """
        payload = encode_login(username, password, stay=stay)
        frame = await self.exchange([Command(channel=Channel.PAGE_BODY, code=CommandCode.LOGIN, payload=payload)])
        return parse_login_result(_only_payload(frame, CommandCode.LOGIN))

    async def logout(self) -> None:
        """Send the UI logout command."""
        await self.exchange([Command(channel=Channel.PAGE_BODY, code=CommandCode.LOGIN, payload=bytes((LoginAction.LOGOUT,)))])

    async def read_registers(
        self,
        register_ids: Sequence[int],
        *,
        channel: Channel = Channel.PAGE_PARAM,
    ) -> tuple[ParamRecord, ...]:
        """Read registers and return one record per id in the response.

        Args:
            register_ids: Wire register ids.
            channel: ``PAGE_PARAM`` for values after login. The UI reads
                language and skin on ``WS`` before login.

        Returns:
            Decoded records. Order follows the gateway payload.
        """
        frame = await self.exchange([Command(channel=channel, code=CommandCode.PARAM, payload=encode_param_read(register_ids))])
        return decode_param_read(_only_payload(frame, CommandCode.PARAM))

    async def fetch_own_text(self, ac16: int = 0) -> tuple[str, ...]:
        """Download custom panel names (OwnText) for one AC16.

        Args:
            ac16: Controller index. ``0`` is the first regulator.

        Returns:
            NUL-separated UTF-8 slots from the gateway, in order.
        """
        payload = encode_data_request(DataKind.OWN_TEXT, ac16, 0)
        frame = await self.exchange([Command(channel=Channel.PAGE_DATA, code=CommandCode.DATA, payload=payload)])
        return decode_own_text(_only_payload(frame, CommandCode.DATA))

    async def fetch_info(self, ac16: int = 0) -> InfoDump:
        """Download one complete Info page dump for an AC16.

        Sends ``req=1`` to start, then ``req=0`` until the gateway sets the
        last-chunk flag. Login is required for regulator Info rows.

        Args:
            ac16: Controller index. ``0`` is the first regulator.

        Returns:
            Assembled Info rows for that controller.
        """
        chunks: list[InfoChunk] = []
        first = True
        while True:
            req = 1 if first else 0
            payload = encode_data_request(DataKind.INFO, ac16, req)
            frame = await self.exchange([Command(channel=Channel.PAGE_DATA, code=CommandCode.DATA, payload=payload)])
            chunk = decode_info_chunk(_only_payload(frame, CommandCode.DATA))
            chunks.append(chunk)
            first = False
            if chunk.last:
                break
            if len(chunks) > 256:
                raise ProtocolError("info dump exceeded 256 chunks without a last flag")
        return assemble_info_chunks(chunks)

    async def download_file(self, name: str) -> bytes:
        """Download one UI bundle file and decompress it when the gateway gzipped it.

        Language tables (``Lang.json``, ``texty_brana.json``) are available
        before login. The gateway picks the file id; this method acks each
        chunk with that id.

        Args:
            name: File name, for example ``Lang.json``.

        Returns:
            File bytes after gzip decompression.

        Raises:
            ProtocolError: A chunk is out of order or flagged as an error.
        """
        frame = await self.exchange([Command(channel=Channel.WS, code=CommandCode.FILE, payload=encode_file_request(name))])
        blob = bytearray()
        gzipped = False
        while True:
            chunk = decode_file_chunk(_only_payload(frame, CommandCode.FILE))
            if chunk.error:
                raise ProtocolError(f"gateway reported an error while sending {name}")
            if chunk.offset != len(blob):
                raise ProtocolError(f"{name} chunk offset {chunk.offset} does not follow {len(blob)}")
            gzipped = gzipped or chunk.gzip
            blob += chunk.data
            if chunk.end:
                break
            frame = await self.exchange(
                [Command(channel=Channel.WS, code=CommandCode.FILE, payload=encode_file_ack(chunk.file_id, len(blob)))]
            )
        raw = bytes(blob)
        return gzip.decompress(raw) if gzipped else raw

    async def exchange(self, commands: Sequence[Command]) -> Frame:
        """Send one client frame and wait for the server frame.

        The UI keeps a single request in flight. This method does the same
        with an asyncio lock.

        Args:
            commands: Commands to place in the frame.

        Returns:
            The decoded server frame.

        Raises:
            NotConnectedError: :meth:`connect` has not been called.
            ProtocolError: The gateway sent a text frame.
        """
        socket = self._socket
        if socket is None:
            raise NotConnectedError("WebSocket is not open")
        async with self._lock:
            await socket.send(encode_client_frame(commands, self.session_id))
            message = await socket.recv()
        if isinstance(message, str):
            raise ProtocolError("gateway sent a text WebSocket frame")
        return decode_server_frame(message)

    def _ssl_context(self) -> ssl.SSLContext:
        """Build an SSL context for the WebSocket.

        When verification is disabled (typical for the private device CA),
        skip ``create_default_context`` so the system CA store is never loaded.
        """
        if not self._verify_tls:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE  # nosec B503
            return context
        return ssl.create_default_context()


def _only_payload(frame: Frame, code: CommandCode) -> bytes:
    if len(frame.commands) != 1 or frame.commands[0].code != code:
        raise ProtocolError(f"expected one {code.name} command, got {len(frame.commands)}")
    return frame.commands[0].payload
