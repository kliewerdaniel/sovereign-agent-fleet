"""SSE serialization of exchange market events.

The frames are plain ``text/event-stream`` chunks:

    event: trade
    data: {"type":"trade","exchange_id":1,"seq":7,"ts":...,"payload":{...}}

Mirrors the streaming contract used by ``fleet/api`` so the control surface
(``ui/``) can consume both audit-ledger and market feeds with one parser.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Iterator, Optional

from .events import EventType, ExchangeBus, MarketEvent


def sse_frame(event: MarketEvent) -> str:
    """Render one :class:`MarketEvent` as a Server-Sent-Events frame."""
    body = json.dumps(event.to_dict(), separators=(",", ":"))
    return f"event: {event.type.value}\ndata: {body}\n\n"


def bus_stream_gen(bus: ExchangeBus, since_seq: int = 0) -> Iterator[str]:
    """Yield SSE frames for every event published after ``since_seq``.

    Suitable for FastAPI ``StreamingResponse`` (synchronous generator). Emits the
    backlog first, then a keep-alive comment between publishes.
    """
    queue: list[str] = []
    counter = {"n": 0}

    def _on_event(evt: MarketEvent) -> None:
        if evt.seq <= since_seq:
            return
        counter["n"] += 1
        queue.append(sse_frame(evt))

    unsub = bus.subscribe(_on_event)
    # emit any backlog first
    for evt in bus.replay(since_seq):
        yield sse_frame(evt)
    try:
        while True:
            if queue:
                yield queue.pop(0)
            else:
                yield ": keep-alive\n\n"
    finally:
        unsub()


async def bus_stream_gen_async(bus: ExchangeBus, since_seq: int = 0) -> AsyncIterator[str]:
    """Async variant for ASGI ``StreamingResponse`` (awaitable generator).

    Buffers events via the synchronous bus and yields them as they arrive using
    a simple polling loop. Kept dependency-free (no extra async queue lib).
    """
    import asyncio

    state = {"seq": since_seq, "buf": []}

    def _on_event(evt: MarketEvent) -> None:
        state["buf"].append(sse_frame(evt))

    unsub = bus.subscribe(_on_event)
    try:
        while True:
            if state["buf"]:
                yield state["buf"].pop(0)
            else:
                yield ": keep-alive\n\n"
                await asyncio.sleep(0.25)
    finally:
        unsub()


__all__ = ["sse_frame", "bus_stream_gen", "bus_stream_gen_async", "EventType", "ExchangeBus", "Optional"]
