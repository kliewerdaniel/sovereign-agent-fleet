import json, sys, subprocess, os
from pathlib import Path
sys.path.insert(0, "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet/demo/hackathon")
import capture as C

HERE = Path("/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet/demo/hackathon")
DUR_PATH = HERE / "durations.json"
NEW_B2_DUR = 13.44

# 1) update durations.json so assemble's total check + clip timing agree
d = json.load(open(DUR_PATH))
d["b2"] = NEW_B2_DUR
json.dump(d, open(DUR_PATH, "w"), indent=2)
print("durations.json b2 ->", d["b2"])

# 2) re-capture ONLY b2 with the new narration duration (needs its own playwright ctx)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    # monkeypatch capture's module-global `p` so record_paper_beat can launch
    C.p = p
    for beat in C.SCRIPT["beats"]:
        if beat["id"] != "b2":
            continue
        print("RE-CAPTURING b2 clip at", NEW_B2_DUR, "s")
        C.record_paper_beat(beat["id"], beat["route"], C.TARGETS.get(beat["id"], ""), NEW_B2_DUR)

clip = HERE / "clips" / "b2.mp4"
clen = subprocess.run([C.FF, "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=noprint_wrappers=1:nokey=1", str(clip)],
                      capture_output=True, text=True).stdout.strip()
print("b2 clip length:", clen, "s (expected ~13.44)")

# 3) re-assemble final video from all clips + regenerated audio
print("ASSEMBLING final video...")
C.assemble if False else None
# call assemble via subprocess to reuse assemble.py exactly
r = subprocess.run([sys.executable, str(HERE / "assemble.py")], capture_output=True, text=True)
print(r.stdout)
print(r.stderr[-500:] if r.stderr else "")
print("DONE")
