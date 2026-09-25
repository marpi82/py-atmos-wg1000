"""Lightweight poller publishes raw changes and ignores repeats."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from pyatmos_wg1000.feed import AtmosFeed
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


def _record(value: int, *, kind: ParamType = ParamType.READ_ONLY) -> ParamRecord:
    return ParamRecord(register_id=0x11000001, kind=kind, value=value)


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
