from PIL import ImageFont
cands = [
  "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
  "/System/Library/Fonts/Supplemental/Arial.ttf",
  "/System/Library/Fonts/HelveticaNeue.ttc",
  "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
  "/System/Library/Fonts/Supplemental/Futura.ttc",
  "/Library/Fonts/Arial Bold.ttf",
]
for p in cands:
    try:
        ImageFont.truetype(p, 24); print("OK   ", p)
    except Exception as e:
        print("FAIL ", p, "->", str(e)[:50])
# Try Helvetica.ttc index 1 (usually bold)
for idx in [0,1,2]:
    try:
        ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24, index=idx); print("OK   Helvetica.ttc idx", idx)
    except Exception as e:
        print("FAIL Helvetica.ttc idx", idx, str(e)[:50])
