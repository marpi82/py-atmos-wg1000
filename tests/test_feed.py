"""Lightweight poller publishes raw changes and ignores repeats."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pyatmos_wg1000.feed import AtmosFeed, InfoFeed
from pyatmos_wg1000.protocol.data import InfoDump, InfoItem
from pyatmos_wg1000.protocol.enums import Channel, ParamType
from pyatmos_wg1000.protocol.params import ParamRecord


class _Reader:
    def __init__(self, batches: list[tuple[ParamRecord, ...]]) -> None:
        self._batches = batches
        self.calls = 0

    async def read_registers(
        self,
        register_ids: Sequence[int],
        *,
        channel: Channel = Channel.PAGE_PARAM,
    ) -> tuple[ParamRecord, ...]:
        del register_ids, channel
        batch = self._batches[self.calls]
        self.calls += 1
        return batch


class _InfoReader:
    def __init__(self, dumps: list[InfoDump]) -> None:
        self._dumps = dumps
        self.calls = 0

    async def fetch_info(self, ac16: int = 0) -> InfoDump:
        del ac16
        dump = self._dumps[self.calls]
        self.calls += 1
        return dump


def _record(value: int, *, kind: ParamType = ParamType.READ_ONLY) -> ParamRecord:
    return ParamRecord(register_id=0x11000001, kind=kind, value=value)


def _dump(*values: bytes) -> InfoDump:
    items = tuple(
        InfoItem(typ=2, vzhled=0, skupina=1, text_a=1, text_b=0, caption=10 + i, value=value) for i, value in enumerate(values)
    )
    return InfoDump(ac16=0, items=items)


async def test_poll_publishes_the_first_sample_and_skips_the_same_word() -> None:
    """The store keeps the raw word and the bus stays quiet when it does not change."""
    reader = _Reader([(_record(0x8000138C),), (_record(0x8000138C),), (_record(0x800014CF),)])
    feed = AtmosFeed(reader, [0x11000001], interval=30)
    seen: list[int] = []

    async def collect() -> None:
        async for update in feed.bus.subscribe():
            seen.append(update.value)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    assert await feed.poll_once() == 1
    assert await feed.poll_once() == 0
    assert await feed.poll_once() == 1
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert seen == [0x8000138C, 0x800014CF]
    assert feed.store.get(0x11000001) == 0x800014CF


async def test_hidden_records_are_not_stored() -> None:
    """A register with no value does not enter the runtime store."""
    hidden = ParamRecord(register_id=1, kind=ParamType.UNAVAILABLE, value=None)
    feed = AtmosFeed(_Reader([(hidden,)]), [1])
    assert await feed.poll_once() == 0
    assert feed.store.get(1) is None


async def test_info_feed_publishes_only_when_dump_changes() -> None:
    """InfoFeed keeps the last dump and stays quiet on identical polls."""
    first = _dump(b"25,9 \xc2\xb0C\x00")
    second = _dump(b"26,0 \xc2\xb0C\x00")
    feed = InfoFeed(_InfoReader([first, first, second]), interval=30)
    seen: list[InfoDump] = []

    async def collect() -> None:
        async for update in feed.bus.subscribe():
            seen.append(update.dump)

    task = asyncio.create_task(collect())
    await asyncio.sleep(0)
    assert await feed.poll_once() is True
    assert await feed.poll_once() is False
    assert await feed.poll_once() is True
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert seen == [first, second]
    assert feed.dump == second
