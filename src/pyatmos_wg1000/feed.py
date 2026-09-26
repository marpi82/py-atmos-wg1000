"""Lightweight register and Info page acquisition.

The feed polls the gateway and keeps raw values. It does not load language
files or the UI bundle. Home Assistant runtime should use this module.
Build entity names earlier with :class:`pyatmos_wg1000.i18n.LanguageCatalog`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from typing import Protocol

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.data import InfoDump
from pyatmos_wg1000.protocol.enums import Channel, ParamType
from pyatmos_wg1000.protocol.params import ParamRecord

logger = logging.getLogger(__name__)


class RegisterSource(Protocol):
    """The read call :class:`AtmosFeed` needs from a client."""

    async def read_registers(
        self,
        register_ids: Sequence[int],
        *,
        channel: Channel = Channel.PAGE_PARAM,
    ) -> tuple[ParamRecord, ...]:
        """Read the given registers."""


class InfoSource(Protocol):
    """The Info fetch :class:`InfoFeed` needs from a client."""

    async def fetch_info(self, ac16: int = 0) -> InfoDump:
        """Download one complete Info dump."""


@dataclass(frozen=True)
class RegisterUpdate:
    """One raw register value that changed since the previous poll."""

    register_id: int
    value: int
    kind: ParamType
    minimum: int | None = None
    maximum: int | None = None
    ts: float = field(default_factory=time.time)
    seq: int = 0


@dataclass(frozen=True)
class InfoUpdate:
    """One complete Info dump that differs from the previous poll."""

    dump: InfoDump
    ts: float = field(default_factory=time.time)
    seq: int = 0


class EventBus:
    """Multicast bus for :class:`RegisterUpdate` only."""

    def __init__(self) -> None:
        """Create an empty subscriber list."""
        self._subs: list[asyncio.Queue[RegisterUpdate]] = []
        self._seq = 0
        self._lock = asyncio.Lock()

    def last_seq(self) -> int:
        """Return the sequence of the last published event, or -1."""
        return max(self._seq - 1, -1)

    async def publish(self, update: RegisterUpdate) -> None:
        """Publish ``update`` to every current subscriber.

        Args:
            update: The change to broadcast. ``seq`` is assigned here.
        """
        async with self._lock:
            event = replace(update, seq=self._seq)
            self._seq += 1
            targets = tuple(self._subs)
        for queue in targets:
            await queue.put(event)

    async def subscribe(self) -> AsyncGenerator[RegisterUpdate]:
        """Yield later updates until the consumer is cancelled.

        Yields:
            Register changes published after this call.
        """
        queue: asyncio.Queue[RegisterUpdate] = asyncio.Queue()
        async with self._lock:
            self._subs.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                with suppress(ValueError):
                    self._subs.remove(queue)


class InfoEventBus:
    """Multicast bus for :class:`InfoUpdate` only."""

    def __init__(self) -> None:
        """Create an empty subscriber list."""
        self._subs: list[asyncio.Queue[InfoUpdate]] = []
        self._seq = 0
        self._lock = asyncio.Lock()

    def last_seq(self) -> int:
        """Return the sequence of the last published event, or -1."""
        return max(self._seq - 1, -1)

    async def publish(self, update: InfoUpdate) -> None:
        """Publish ``update`` to every current subscriber.

        Args:
            update: The change to broadcast. ``seq`` is assigned here.
        """
        async with self._lock:
            event = replace(update, seq=self._seq)
            self._seq += 1
            targets = tuple(self._subs)
        for queue in targets:
            await queue.put(event)

    async def subscribe(self) -> AsyncGenerator[InfoUpdate]:
        """Yield later Info dumps until the consumer is cancelled.

        Yields:
            Info dumps published after this call.
        """
        queue: asyncio.Queue[InfoUpdate] = asyncio.Queue()
        async with self._lock:
            self._subs.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                with suppress(ValueError):
                    self._subs.remove(queue)


class ValueStore:
    """Raw register values for the runtime path.

    The key is the wire register id. The value is the unsigned word from the
    gateway. Decoding temperatures and translating labels stays outside.
    """

    def __init__(self) -> None:
        """Start with an empty map."""
        self._values: dict[int, int] = {}

    def upsert(self, register_id: int, value: int) -> None:
        """Store ``value`` for ``register_id``.

        Args:
            register_id: Wire register id.
            value: Raw 32-bit word.
        """
        self._values[register_id] = value

    def get(self, register_id: int) -> int | None:
        """Return the last raw value, or ``None`` when it was never stored.

        Args:
            register_id: Wire register id.
        """
        return self._values.get(register_id)


class AtmosFeed:
    """Poll a fixed set of registers and publish changes.

    The gateway does not push sensor values. This loop asks for the same ids
    on an interval. The first sample is published. Later samples are published
    only when the raw word changes. Hidden and unavailable records are skipped.

    Args:
        client: Connected and logged-in client.
        register_ids: Wire ids to read on every poll.
        interval: Seconds between polls. The panel reads circuit temperatures
            every 30 seconds.
        channel: Command channel. Live values use ``PAGE_PARAM``.
    """

    def __init__(
        self,
        client: RegisterSource,
        register_ids: Sequence[int],
        *,
        interval: float = 30.0,
        channel: Channel = Channel.PAGE_PARAM,
    ) -> None:
        """Store the poll set. Nothing is read until :meth:`poll_once` or :meth:`run`."""
        if not register_ids:
            raise ProtocolError("feed needs at least one register")
        if interval <= 0:
            raise ProtocolError("poll interval must be positive")
        self._client = client
        self._ids = tuple(register_ids)
        self._interval = interval
        self._channel = channel
        self.bus = EventBus()
        self.store = ValueStore()
        self._task: asyncio.Task[None] | None = None

    async def poll_once(self) -> int:
        """Read the configured registers and publish the ones that changed.

        Returns:
            How many updates were published.
        """
        records = await self._client.read_registers(self._ids, channel=self._channel)
        published = 0
        for record in records:
            if record.value is None or self.store.get(record.register_id) == record.value:
                continue
            self.store.upsert(record.register_id, record.value)
            await self.bus.publish(
                RegisterUpdate(
                    register_id=record.register_id,
                    value=record.value,
                    kind=record.kind,
                    minimum=record.minimum,
                    maximum=record.maximum,
                )
            )
            published += 1
        return published

    def start(self) -> asyncio.Task[None]:
        """Start the poll loop as a task.

        Returns:
            The running task. A second call returns the same task.
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="atmos-feed")
        return self._task

    async def stop(self) -> None:
        """Cancel the poll loop and wait until it finishes."""
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def run(self) -> None:
        """Poll until cancelled.

        Raises:
            Exception: Any poll error is logged and re-raised so the task
                does not die without a trace.
        """
        await self._loop()

    async def _loop(self) -> None:
        try:
            while True:
                await self.poll_once()
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("register poll failed")
            raise


class InfoFeed:
    """Poll the Info page dump and publish when rows change.

    Args:
        client: Connected and logged-in client that implements :meth:`fetch_info`.
        ac16: Controller index. ``0`` is the first regulator.
        interval: Seconds between full dumps.
    """

    def __init__(
        self,
        client: InfoSource,
        *,
        ac16: int = 0,
        interval: float = 30.0,
    ) -> None:
        """Store poll settings. Nothing is fetched until :meth:`poll_once` or :meth:`run`."""
        if interval <= 0:
            raise ProtocolError("poll interval must be positive")
        if not 0 <= ac16 <= 0xFF:
            raise ProtocolError(f"ac16 out of range: {ac16}")
        self._client = client
        self._ac16 = ac16
        self._interval = interval
        self.bus = InfoEventBus()
        self.dump: InfoDump | None = None
        self._task: asyncio.Task[None] | None = None

    async def poll_once(self) -> bool:
        """Fetch one Info dump and publish when it differs from the last one.

        Returns:
            ``True`` when a new dump was published.
        """
        dump = await self._client.fetch_info(self._ac16)
        if self.dump == dump:
            return False
        self.dump = dump
        await self.bus.publish(InfoUpdate(dump=dump))
        return True

    def start(self) -> asyncio.Task[None]:
        """Start the poll loop as a task.

        Returns:
            The running task. A second call returns the same task.
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="atmos-info-feed")
        return self._task

    async def stop(self) -> None:
        """Cancel the poll loop and wait until it finishes."""
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def run(self) -> None:
        """Poll until cancelled.

        Raises:
            Exception: Any poll error is logged and re-raised.
        """
        await self._loop()

    async def _loop(self) -> None:
        try:
            while True:
                await self.poll_once()
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("info poll failed")
            raise
