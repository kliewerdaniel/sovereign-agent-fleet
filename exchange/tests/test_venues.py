"""E3 venue adapter tests: honest stub contract + normalization."""
from exchange.venues import KalshiStub, NormalizedOrder, RoutingStatus


def test_stub_is_not_live():
    assert KalshiStub().is_live() is False


def test_stub_records_intent_and_simulates_fill():
    k = KalshiStub(simulate=True)
    order = NormalizedOrder(exchange_id=1, side="BUY", qty=40, limit_cents=55)
    res = k.route(order)
    # never live
    assert res.status == RoutingStatus.NOT_LIVE
    # intent recorded
    assert len(k.routed) == 1
    # simulated fill present at limit price
    assert len(res.fills) == 1
    f = res.fills[0]
    assert f.price_cents == 55
    assert f.qty == 40
    assert f.side == "BUY"
    assert res.venue_order_id is not None


def test_stub_no_sim_returns_no_fills():
    k = KalshiStub(simulate=False)
    res = k.route(NormalizedOrder(exchange_id=1, side="SELL", qty=10, limit_cents=49))
    assert res.status == RoutingStatus.NOT_LIVE
    assert res.fills == []
    assert "intent only" in res.detail


def test_stub_cancel_tracks_state():
    k = KalshiStub()
    res = k.route(NormalizedOrder(exchange_id=1, side="BUY", qty=5, limit_cents=50))
    vid = res.venue_order_id
    assert vid is not None
    cancel = k.cancel(vid)
    assert cancel.status == RoutingStatus.NOT_LIVE
    assert k._orders[vid] == "cancelled"
    # unknown id rejected
    assert k.cancel("nope").status == RoutingStatus.REJECTED
