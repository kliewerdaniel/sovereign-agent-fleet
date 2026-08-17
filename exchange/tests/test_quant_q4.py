"""Q4: temporal event graph + information gain — tests (Layer-1 evidence).

Verifies: Bernoulli entropy / information-gain math, the EventGraph analytics
(total/cumulative/most-informative/conditional), the local-first series builder,
folding into evaluate_quant, orchestrator determinism, M0 (no authority fields),
and import-wall purity.
"""
from __future__ import annotations

from exchange.quant.eventgraph import (
    EventGraph,
    MarketEvent,
    bernoulli_entropy,
    information_gain,
    info_gain_from_series,
)
from exchange.quant.orchestrator import QuantContext, evaluate_quant


def test_entropy_max_at_half_min_at_ends():
    assert bernoulli_entropy(0.0) == 0.0
    assert bernoulli_entropy(1.0) == 0.0
    h = bernoulli_entropy(0.5)
    assert abs(h - 1.0) < 1e-9           # H(0.5) = 1 bit
    assert bernoulli_entropy(0.5) > bernoulli_entropy(0.7) > 0.0


def test_information_gain_never_negative_and_monotone():
    # Moving 0.50 -> 0.80 removes more uncertainty than 0.50 -> 0.60.
    g1 = information_gain(0.50, 0.80)
    g2 = information_gain(0.50, 0.60)
    assert g1 > g2 > 0.0
    # An unchanged belief (p -> p) adds exactly 0 bits: no new information.
    assert information_gain(0.99, 0.99) == 0.0
    assert information_gain(0.50, 0.50) == 0.0
    # Float dust can never flip the sign.
    assert information_gain(0.50000001, 0.49999999) >= 0.0


def test_event_captures_own_gain():
    e = MarketEvent("e1", 1, "SETTLE", "KX", 0.5, 0.8)
    assert abs(e.gain - information_gain(0.5, 0.8)) < 1e-12


def test_graph_totals_and_most_informative():
    g = EventGraph.from_events(101, [
        MarketEvent("a", 1, "OBS", "KX", 0.50, 0.55),
        MarketEvent("b", 2, "OBS", "KX", 0.55, 0.80),   # big move -> top
        MarketEvent("c", 3, "OBS", "KX", 0.80, 0.82),
    ])
    assert g.event_count() == 3
    total = g.total_information_gain()
    manual = sum(information_gain(e.p_yes_before, e.p_yes_after) for e in g._events)
    assert abs(total - manual) < 1e-12
    assert g.most_informative_event().event_id == "b"  # type: ignore[union-attr]
    assert abs(g.cumulative_entropy() - bernoulli_entropy(0.82)) < 1e-12


def test_graph_empty_is_safe():
    g = EventGraph(101)
    assert g.event_count() == 0
    assert g.total_information_gain() == 0.0
    assert g.cumulative_entropy() == 0.0
    assert g.most_informative_event() is None
    assert g.compute_hash()  # still hashes (deterministic)


def test_conditional_gain_chain():
    g = EventGraph.from_events(101, [
        MarketEvent("p", 1, "NEWS", "KX", 0.50, 0.90),
        MarketEvent("c", 2, "REACT", "KX", 0.80, 0.95, parent_id="p"),
    ])
    # Given parent already moved to 0.90, the child's additional move is small.
    cg = g.conditional_gain("c")
    assert cg is not None
    assert 0.0 <= cg < information_gain(0.50, 0.95)
    # No parent -> None
    assert g.conditional_gain("p") is None


def test_local_first_series_builder():
    series = [0.50, 0.55, 0.80, 0.81]
    g = info_gain_from_series(101, series, ticker="KX")
    # n snapshots -> n-1 events
    assert g.event_count() == len(series) - 1
    # the largest single step (0.55 -> 0.80) is the most informative
    assert g.most_informative_event().event_id == "KX-2"
    assert g.total_information_gain() > 0.0


def test_event_exchange_id_enforced():
    g = EventGraph(101)
    bad = MarketEvent("x", 1, "OBS", "KX", 0.5, 0.6, exchange_id=999)
    try:
        g.add_event(bad)
        raise AssertionError("expected exchange_id mismatch to be rejected")
    except ValueError:
        pass


def test_q4_folds_into_evaluate_quant():
    from fleet.crypto.foundation import Ed25519PrivateKey, AgentCert
    key = Ed25519PrivateKey.generate()
    producer = AgentCert(
        agent_id="quant-advisor-test", role="tool",
        capabilities=["quant_compute"], pubkey_pem="",
        issued_at=0, expires_at=2_000_000_000, cert_seq=1, root_sig="self",
    )
    ctx = QuantContext(
        exchange_id=101, model_p_yes=0.72, bid_cents=60, ask_cents=62,
        side="BUY_YES", event_p_yes_series=(0.50, 0.55, 0.72, 0.70),
    )
    d = evaluate_quant(ctx, producer, key)
    assert d.graph.event_count() == 3
    assert d.graph.total_information_gain() > 0.0
    # Q4 shows up in to_dict under event_graph
    gd = d.to_dict()["event_graph"]
    assert gd["event_count"] == 3
    assert gd["graph_hash"] == d.graph.compute_hash()


def test_orchestrator_determinism_with_q4():
    from fleet.crypto.foundation import Ed25519PrivateKey, AgentCert
    key = Ed25519PrivateKey.generate()
    producer = AgentCert(
        agent_id="quant-advisor-test", role="tool",
        capabilities=["quant_compute"], pubkey_pem="",
        issued_at=0, expires_at=2_000_000_000, cert_seq=1, root_sig="self",
    )
    ctx = QuantContext(
        exchange_id=101, model_p_yes=0.72, bid_cents=60, ask_cents=62,
        event_p_yes_series=(0.50, 0.55, 0.72),
    )
    a = evaluate_quant(ctx, producer, key)
    b = evaluate_quant(ctx, producer, key)
    assert a.graph.compute_hash() == b.graph.compute_hash()
    assert a.to_dict()["event_graph"] == b.to_dict()["event_graph"]


def test_m0_no_authority_fields_in_q4():
    from fleet.crypto.foundation import Ed25519PrivateKey, AgentCert
    key = Ed25519PrivateKey.generate()
    producer = AgentCert(
        agent_id="quant-advisor-test", role="tool",
        capabilities=["quant_compute"], pubkey_pem="",
        issued_at=0, expires_at=2_000_000_000, cert_seq=1, root_sig="self",
    )
    # Q4 output carries NO verdict / authorization fields.
    d = evaluate_quant(
        QuantContext(exchange_id=101, model_p_yes=0.7, bid_cents=60, ask_cents=62,
                     event_p_yes_series=(0.5, 0.7)),
        producer, key,
    )
    for forbidden in ("verdict", "authorization", "tier", "executed_qty", "allow"):
        assert forbidden not in d.to_dict(), f"Q4 leaked authority field: {forbidden}"


def test_import_wall_purity():
    import ast, inspect
    mod = __import__("exchange.quant.eventgraph", fromlist=["x"])
    src = inspect.getsource(mod)
    tree = ast.parse(src)
    # The only real wall: exchange/quant may NOT import authority/execution modules.
    forbidden = ("fleet.fin", "fleet.layers", "fleet.cognition", "exchange.governance")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert not _bad(n.name, forbidden), f"eventgraph.py imports forbidden {n.name}"
        elif isinstance(node, ast.ImportFrom):
            assert not _bad(node.module or "", forbidden), \
                f"eventgraph.py from-imports forbidden {node.module}"


def _bad(name: str, prefixes) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)
