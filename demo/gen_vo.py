#!/usr/bin/env python3
# edge-tts per-scene British narration + ffprobe durations.
import subprocess, json, os
from pathlib import Path

VOICE = "en-GB-RyanNeural"   # British male, professional
EDGE = "/Users/danielkliewer/.hermes/hermes-agent/venv/bin/edge-tts"
OUT = Path("vo"); OUT.mkdir(parents=True, exist_ok=True)

SCENES = {
    "s1": "This is the control surface for a sovereign agent fleet. Notice what it is NOT: it never decides. The fleet decides. This surface only receives signed artifacts and lets you verify them. The banner at the top is server-computed trust state, and the client never checks the crypto itself. The rule is simple: do not trust the model. Trust the execution protocol.",
    "s2": "Every action the fleet takes lands here, in an immutable, append-only ledger. Each entry is signed with Ed25519, and the edges in this graph are genuine parent-hash links. That means if anyone tampers with a single entry, every downstream signature breaks. The chain is the product; observability is the operating system.",
    "s3": "Open any entry and you see the canonical signed bytes, the previous hash, and the signature itself, alongside the ledger public key that verifies it. Nothing here is a screenshot of a log file. This is the actual payload the fleet committed, and you can prove it came from the fleet and was never altered.",
    "s4": "Here are the pipeline runs. Each one is a real researcher-to-analyst-to-operator flow. There are exactly three governance outcomes: a verified claim runs autonomously, an asserted claim escalates to a human, and a hallucinated claim is blocked at the boundary. The model is never the authority.",
    "s5": "This run was asserted evidence, so it escalated to a human. The policy engine granted a capability, but execution waits for a real signature. That signature is a genuine Ed25519 approval from a human certificate, bound to this specific action. Authority is delegated by a person, and it is verifiable.",
    "s6": "The incident domain is the only one fully wired, against a real digital range: web-edge, app-db, revenue-svc, and identity-svc. Note the honest edge: identity-svc refuses containment entirely, because isolating your own identity provider is a self-inflicted denial of service. Sales and financial exist in the schema but are not yet wired, and the surface says so plainly rather than inventing data.",
    "s7": "And this is the fleet talking, live. The console subscribes to the bridge over a WebSocket and shows real audit entries and approval events the moment the fleet produces them. No polling, no replay. You are watching the signed, hash-chained protocol execute in real time.",
}

for sid, text in SCENES.items():
    mp3 = OUT / f"{sid}.mp3"
    subprocess.run([EDGE, "--voice", VOICE, "--rate=-4%",
                    "--text", text, "--write-media", str(mp3)], check=True)

durations = {}
for sid in SCENES:
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(OUT / f"{sid}.mp3")],
                       capture_output=True, text=True).stdout.strip()
    durations[sid] = round(float(d), 2)
    print(sid, durations[sid])
json.dump(durations, open(OUT / "durations.json", "w"), indent=2)
print("VO DONE ->", OUT / "durations.json")
