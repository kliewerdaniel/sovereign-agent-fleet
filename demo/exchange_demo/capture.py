"""Capture REAL output for the exchange/live-ticker demo.

Boots the real Exchange (live Kalshi ticker stream) via the app's TestClient,
waits for live ticks, and dumps genuine endpoint JSON into this dir's data/.
Also dumps a sim-only status and a REAL fleet gate-decision matrix for the
supporting beat. No fabricated output.
"""
import json
import os
import time

from fastapi.testclient import TestClient

from exchange.api import Exchange, app, _state

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)


def dump(name, obj):
    with open(os.path.join(DATA, name), "w") as f:
        json.dump(obj, f, indent=2, default=str)
    print(f"wrote data/{name}")


# --- 1) LIVE exchange: subscribe-all ticker stream -------------------------
_state.clear()
live = Exchange(1, live_feed=True)
_state[1] = live
c = TestClient(app)
print("waiting for live ticks...")
time.sleep(8)
dump("stream_status_live.json", c.get("/stream/status").json())
dump("quotes_live.json", c.get("/quotes").json())

# --- 2) SIM-ONLY exchange (honesty: never fabricates liveness) -------------
_state.clear()
sim = Exchange(2)  # default: no live_feed
_state[2] = sim
cs = TestClient(app)
dump("stream_status_sim.json", cs.get("/stream/status").json())
dump("quotes_sim.json", cs.get("/quotes").json())

live.close()
sim.close()

# --- 3) REAL fleet gate matrix (supporting beat) ---------------------------
from fleet.layers.incident import required_authorization, Severity

# real workload -> asset class; real actions map to blast radius
cases = []
workloads = [("web-edge", "LOW"), ("app-db", "MEDIUM"),
             ("revenue-svc", "HIGH"), ("identity-svc", "PROTECTED")]
# verification verb per severity band we want to showcase. The "critical"
# band is represented by a HALLUCINATION verification verb, which the policy
# rejects at ANY severity (see fleet/layers/incident.py).
vmap = {"low": "VERIFIED", "medium": "VERIFIED", "high": "ASSERTED", "critical": "HALLUCINATION"}
for sev in ("low", "medium", "high", "critical"):
    sev_enum = Severity[sev.upper()] if sev != "critical" else Severity.LOW
    for wid, cls in workloads:
        for action in ("block_egress", "isolate", "quarantine"):
            auth = required_authorization(vmap[sev], sev_enum, action, wid)
            cases.append({"severity": sev, "action": action, "workload": wid,
                          "asset_class": cls, "verification": vmap[sev],
                          "authorization": auth.value})
dump("fleet_gov.json", cases)

print("DONE")
