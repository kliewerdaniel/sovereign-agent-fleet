"""E2 integration: event bus + SSE tokenizer over real matching-engine fills."""
from exchange.core import (
    ExchangeBus,
    MatchingEngine,
    OrderBook,
    OrderSide,
    bus_stream_gen,
    make_limit_order,
    sse_frame,
    trade_event,
)
from exchange.core.events import EventType
from exchange.core.sse import bus_stream_gen_async

import asyncio
import json


def _wire():
    bus = ExchangeBus()
    book = OrderBook(1)
    eng = MatchingEngine(book, bus=bus)
    return bus, book, eng


def test_bus_emits_trade_on_fill():
    bus, book, eng = _wire()
    seen = []
    bus.subscribe(lambda e: seen.append(e))
    book.add(make_limit_order(1, OrderSide.SELL, 50, 0.50, subaccount_id="m", order_id="a"))
    res = eng.match(make_limit_order(1, OrderSide.BUY, 50, 0.55, subaccount_id="t", order_id="taker"))
    assert len(res.fills) == 1
    trade_events = [e for e in seen if e.type == EventType.TRADE]
    assert len(trade_events) == 1
    te = trade_events[0]
    assert te.payload["price_cents"] == 50
    assert te.payload["qty"] == 50
    assert te.payload["taker_side"] == "BUY"
    assert te.payload["maker_subaccount"] == "m"
    # a BOOK snapshot is always published at the end
    assert any(e.type == EventType.BOOK for e in seen)


def test_sse_frame_shape():
    ev = trade_event(1, 50, 30, OrderSide.BUY, "t", "m", "t0", "m0")
    frame = sse_frame(ev)
    assert frame.startswith("event: trade\n")
    assert "data: " in frame
    body = json.loads(frame.split("data: ", 1)[1].split("\n\n", 1)[0])
    assert body["type"] == "trade"
    assert body["payload"]["qty"] == 30


def test_sse_generator_replays_backlog_and_streams_new():
    bus, book, eng = _wire()
    # seed one fill before subscribing
    book.add(make_limit_order(1, OrderSide.SELL, 50, 0.50, subaccount_id="m", order_id="a"))
    eng.match(make_limit_order(1, OrderSide.BUY, 50, 0.55, subaccount_id="t", order_id="t1"))
    gen = bus_stream_gen(bus)
    # backlog frame present
    first = next(gen)
    assert "event: trade" in first or "event: book" in first
    # now a live fill is published after subscription
    book.add(make_limit_order(1, OrderSide.SELL, 50, 0.49, subaccount_id="m2", order_id="b"))
    eng.match(make_limit_order(1, OrderSide.BUY, 50, 0.55, subaccount_id="t", order_id="t2"))
    # drain until we see the new trade (keep-alive frames may interleave)
    got = ""
    for _ in range(20):
        got += next(gen)
        if "t2" in got:
            break
    assert "taker_order_id" in got and "t2" in got


def test_async_sse_emits_event():
    async def run():
        bus, book, eng = _wire()
        gen = bus_stream_gen_async(bus)
        agen = gen.__aiter__()
        # prime the generator so it subscribes to the bus before we publish
        await agen.__anext__()
        book.add(make_limit_order(1, OrderSide.SELL, 50, 0.50, subaccount_id="m", order_id="a"))
        eng.match(make_limit_order(1, OrderSide.BUY, 50, 0.55, subaccount_id="t", order_id="tk"))
        collected = ""
        for _ in range(40):
            chunk = await agen.__anext__()
            collected += chunk
            if "tk" in collected:
                break
        return collected

    out = asyncio.run(run())
    assert "event: trade" in out
    assert "tk" in out
