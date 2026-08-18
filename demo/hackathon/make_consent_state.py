import json
from playwright.sync_api import sync_playwright

STATE_PATH = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet/demo/hackathon/consent_state.json"

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto("http://localhost:8099/paper", wait_until="domcontentloaded")
    pg.wait_for_timeout(9000)
    # click Reject All (real React click sets localStorage cookie_consent)
    pg.evaluate("""() => {
      var all = Array.prototype.slice.call(document.querySelectorAll('button'));
      for (var b of all){
        var t=(b.textContent||'').toLowerCase();
        if (t.indexOf('reject all')>=0){ b.click(); return; }
      }
    }""")
    pg.wait_for_timeout(2000)
    # verify gone
    present = pg.evaluate("""() => {
      var all = document.querySelectorAll('*');
      for (var el of all){ var t=(el.textContent||'').toLowerCase(); if (t.indexOf('cookie preferences')>=0) return true; }
      return false;
    }""")
    # save storage state (carries localStorage + cookies)
    state = ctx.storage_state(path=STATE_PATH)
    print("BANNER PRESENT BEFORE SAVE:", present)
    print("SAVED STATE ->", STATE_PATH)
    browser.close()
