"""E4 router tests: venue ranking, basket split invariants, price improvement."""
from exchange.routing import Router
from exchange.venues import KalshiStub, NormalizedOrder, RoutingStatus


def _router():
    return Router({"kalshi": KalshiStub(simulate=True)})


def test_single_venue_route():
    r = _router()
    order = NormalizedOrder(exchange_id=1, side="BUY", qty=40, limit_cents=55)
    plan = r.route(order)
    assert plan.total_routed == 40
    assert len(plan.legs) == 1
    assert plan.legs[0].venue == "kalshi"
    # stub -> not live, but route still produces a simulated fill
    res0 = plan.legs[0].result
    assert res0 is not None
    assert res0.status == RoutingStatus.NOT_LIVE
    assert len(res0.fills) == 1


def test_basket_split_sums_exactly():
    # two stub venues: split must sum to parent qty exactly
    r = Router({"k1": KalshiStub(), "k2": KalshiStub()})
    order = NormalizedOrder(exchange_id=1, side="SELL", qty=100, limit_cents=49)
    plan = r.route(order, basket=True)
    assert len(plan.legs) == 2
    child_qty = sum(leg.order.qty for leg in plan.legs)
    assert child_qty == 100  # no over/under-fill at routing layer
    assert plan.total_routed == 100
    assert plan.note == "basket split across venues"


def test_split_remainder_distribution():
    r = Router({"a": KalshiStub(), "b": KalshiStub(), "c": KalshiStub()})
    parts = r._split(100, 3)
    assert sum(parts) == 100
    assert parts == [34, 33, 33]  # remainder distributed to earliest legs


def test_live_venue_ranked_first():
    # craft two quotes: a live one should win
    class LiveStub(KalshiStub):
        def is_live(self):  # type: ignore[override]
            return True

    r = Router({"stub": KalshiStub(), "live": LiveStub()})
    order = NormalizedOrder(exchange_id=1, side="BUY", qty=10, limit_cents=50)
    ranked = r.rank_venues(order)
    assert ranked[0].live is True
    assert ranked[0].venue == "live"


def test_price_improvement_computed():
    r = _router()
    # limit 55, simulated fill at 55 -> 0 improvement
    order = NormalizedOrder(exchange_id=1, side="BUY", qty=10, limit_cents=55)
    plan = r.route(order)
    # stub fills at limit, so improvement is 0
    assert plan.price_improvement_cents == 0
