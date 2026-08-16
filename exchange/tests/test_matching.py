"""Tests for the exchange core: matching engine + shadow ledger (Phase E1)."""
from __future__ import annotations

import uuid

import pytest

from exchange.core.instrument import InstrumentRegistry
from exchange.core.order import Order, OrderSide, OrderType, TimeInForce, make_limit_order
from exchange.core.book import OrderBook
from exchange.core.matching import MatchingEngine, Fill
from exchange.core.settlement import ShadowLedger


def _ob(exchange_id: int = 1) -> OrderBook:
    return OrderBook(exchange_id)


def _mk(side, qty, price, sub="default", tif=TimeInForce.GTC, oid=None):
    return make_limit_order(
        exchange_id=1, side=side, qty=qty, price=price,
        subaccount_id=sub, time_in_force=tif, order_id=oid or f"o_{uuid.uuid4().hex[:8]}",
    )


def test_cross_at_passive_price_and_price_improvement():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 100, 0.50, sub="maker"))  # ask 0.50
    eng = MatchingEngine(book)
    # BUY with limit 0.55 should execute at 0.50 (price improvement to taker)
    res = eng.match(_mk(OrderSide.BUY, 40, 0.55, sub="taker"))
    assert len(res.fills) == 1
    f = res.fills[0]
    assert f.price_cents == 50
    assert f.qty == 40
    assert not res.rested
    # maker still has 60 remaining
    assert book.depth() == 1
    snap = book.snapshot()
    assert snap.asks[0].size == 60


def test_price_time_priority():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 50, 0.50, sub="m1", oid="a"))
    book.add(_mk(OrderSide.SELL, 50, 0.50, sub="m2", oid="b"))  # later
    book.add(_mk(OrderSide.SELL, 50, 0.51, sub="m3", oid="c"))  # worse price
    eng = MatchingEngine(book)
    res = eng.match(_mk(OrderSide.BUY, 80, 0.55, sub="t"))
    # fills m1 fully (50) then m2 (30) — never touches m3
    assert [f.maker_order_id for f in res.fills] == ["a", "b"]
    assert sum(f.qty for f in res.fills) == 80
    # m2 still has 20 resting at 0.50; m3 untouched at 0.51 -> best ask 0.50
    assert book.best_ask() == 50
    assert book.depth() == 2


def test_no_overfill_invariants():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 30, 0.40, sub="m", oid="a"))
    eng = MatchingEngine(book)
    res = eng.match(_mk(OrderSide.BUY, 100, 0.45, sub="t", tif=TimeInForce.IOC))
    total = sum(f.qty for f in res.fills)
    assert total == 30  # cannot take more than maker has
    # aggressor remainder cancelled (IOC), maker fully consumed
    assert book.depth() == 0


def test_self_trade_prevention():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 50, 0.50, sub="same"))
    eng = MatchingEngine(book, prevent_self_trade=True)
    res = eng.match(_mk(OrderSide.BUY, 50, 0.55, sub="same"))
    assert res.fills == []  # cannot trade against own book
    # the resting SELL stays, and the taker BUY rests as a bid at its limit (no cross)
    assert book.depth() == 2
    assert book.snapshot().asks[0].size == 50


def test_gtc_rests_remainder():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 30, 0.50, sub="m", oid="a"))
    eng = MatchingEngine(book)
    res = eng.match(_mk(OrderSide.BUY, 80, 0.50, sub="t", tif=TimeInForce.GTC))
    assert res.rested
    # 30 filled from ask; 50 BUY remainder rests as a bid at 0.50 -> 1 level (bids)
    assert book.best_bid() == 50
    assert book.depth() == 1


def test_fok_all_or_nothing_rolls_back():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 30, 0.50, sub="m", oid="a"))
    eng = MatchingEngine(book)
    res = eng.match(_mk(OrderSide.BUY, 100, 0.55, sub="t", tif=TimeInForce.FOK))
    assert res.fills == []  # not enough liquidity -> nothing executes
    assert book.depth() == 1  # maker fully intact
    assert book.snapshot().asks[0].size == 30


def test_fok_fills_when_liquidity_sufficient():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 30, 0.50, sub="m", oid="a"))
    book.add(_mk(OrderSide.SELL, 30, 0.51, sub="m2", oid="b"))
    eng = MatchingEngine(book)
    res = eng.match(_mk(OrderSide.BUY, 60, 0.55, sub="t", tif=TimeInForce.FOK))
    assert sum(f.qty for f in res.fills) == 60
    assert book.depth() == 0


def test_market_sweeps_book():
    book = _ob()
    book.add(_mk(OrderSide.SELL, 20, 0.40, sub="m", oid="a"))
    book.add(_mk(OrderSide.SELL, 20, 0.45, sub="m2", oid="b"))
    mkt = Order(order_id="mkt", exchange_id=1, side=OrderSide.BUY,
                order_type=OrderType.MARKET, qty=35)
    eng = MatchingEngine(book)
    res = eng.match(mkt)
    assert sum(f.qty for f in res.fills) == 35
    assert res.fills[0].price_cents == 40
    assert res.fills[1].price_cents == 45
    assert not res.rested  # market never rests


def test_shadow_ledger_realized_pnl():
    ledger = ShadowLedger()
    # default sub buys 100 @ 0.40, sells 100 @ 0.60 => +2000 cents realized
    ledger.record_fill("desk", 1, OrderSide.BUY, 40, 100)
    ledger.record_fill("desk", 1, OrderSide.SELL, 60, 100)
    pnl = ledger.pnl("desk")
    assert pnl.realized_cents == 2000
    assert ledger.position("desk", 1).side.value == "FLAT"


def test_shadow_ledger_per_subaccount_isolation():
    ledger = ShadowLedger()
    ledger.record_fill("alpha", 1, OrderSide.BUY, 50, 50)
    ledger.record_fill("beta", 1, OrderSide.BUY, 50, 50)
    assert ledger.position("alpha", 1).net_qty == 50
    assert ledger.position("beta", 1).net_qty == 50
    assert ledger.pnl("alpha").total_cents == 0  # no realized


def test_instrument_registry_alias_resolution():
    reg = InstrumentRegistry()
    inst = reg.register("Fed cut Jun 2026", "kalshi", "KXFEDDECISION-26JUN-C25")
    assert inst.exchange_id == 1
    assert reg.resolve_venue("kalshi", "KXFEDDECISION-26JUN-C25") == 1
    assert reg.get(1).title == "Fed cut Jun 2026"
