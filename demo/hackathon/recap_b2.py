import json, sys
sys.path.insert(0, "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet/demo/hackathon")
import capture as C

# update durations.json b2 -> new narration length
DUR_PATH = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet/demo/hackathon/durations.json"
d = json.load(open(DUR_PATH))
d["b2"] = 13.44
json.dump(d, open(DUR_PATH, "w"), indent=2)
print("durations.json b2 ->", d["b2"])

# re-capture only b2
SCRIPT = C.SCRIPT
for beat in SCRIPT["beats"]:
    if beat["id"] != "b2":
        continue
    C.record_paper_beat(beat["id"], beat["route"], C.TARGETS.get(beat["id"], ""), float(d["b2"]))
print("B2 CLIP RE-CAPTURED")
