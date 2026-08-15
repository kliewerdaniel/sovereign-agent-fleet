from PIL import ImageFont
for p in ["/System/Library/Fonts/Helvetica.ttc",
          "/System/Library/Fonts/HelveticaBold.ttc",
          "/System/Library/Fonts/Menlo.ttc",
          "/System/Library/Fonts/Monaco.ttf",
          "/System/Library/Fonts/Supplemental/Menlo.ttc",
          "/Library/Fonts/Courier New.ttf",
          "/System/Library/Fonts/Supplemental/Courier New.ttf"]:
    try:
        ImageFont.truetype(p, 24); print("OK   ", p)
    except Exception as e:
        print("FAIL ", p, "->", str(e)[:60])
