// Playwright 1920x1080 capture for the fleet control-surface demo.
// Pre-warms routes via curl, then drives the LIVE dev server and screenshots
// each scene (retries until the route returns 200, to survive on-demand compile).
import { chromium } from 'playwright';
import fs from 'fs';
import { execSync } from 'child_process';

const BASE = 'http://localhost:3001';
const BRIDGE = 'http://127.0.0.1:8787';
const OUT = './shots';
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Pre-warm every route so Next has compiled them before the browser hits them.
const WARM = [
  '/', '/audit', '/audit/000000000005', '/pipelines',
  '/domains/incident', '/domains/sales', '/domains/financial', '/console',
];
for (const r of WARM) {
  try { execSync(`curl -s -o /dev/null "${BASE}${r}"`); } catch {}
}
sleep(1500);

(async () => {
  const browser = await chromium.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  async function goAndShot(path, name, postWait = 1500) {
    let ok = false;
    for (let attempt = 0; attempt < 4 && !ok; attempt++) {
      const resp = await page.goto(`${BASE}${path}`, { waitUntil: 'load', timeout: 30000 });
      const status = resp ? resp.status() : 0;
      await sleep(postWait);
      // bail out if Next threw a compile error
      const txt = await page.evaluate(() => document.body.innerText.slice(0, 60));
      if (status === 200 && !/Application error|This page could not be found/.test(txt)) {
        ok = true;
      } else {
        await sleep(1200);
      }
    }
    if (!ok) console.log('WARN not 200:', name, path);
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log('shot', name, ok ? '(ok)' : '(WARN)');
  }

  await goAndShot('/', 's1', 1600);
  await goAndShot('/audit', 's2', 1800);
  await goAndShot('/audit/000000000005', 's3', 1700);
  await goAndShot('/pipelines', 's4', 1600);

  // s5 — a real ASSERTED run detail (HUMAN escalation + sign CTA)
  const runId = await page.evaluate(async () => {
    const r = await fetch('http://127.0.0.1:8787/api/run/incident?verification=ASSERTED&severity=MEDIUM&workload_id=web-edge&action=block_egress');
    const j = await r.json();
    return j.run_id;
  });
  await goAndShot(`/pipelines/${runId}`, 's5', 2000);

  await goAndShot('/domains/incident', 's6', 1700);

  // s7 — live console; trigger a run so WS events flow in
  await goAndShot('/console', 's7', 1500);
  await page.evaluate(async () => {
    await fetch('http://127.0.0.1:8787/api/run/incident?verification=VERIFIED&severity=LOW&workload_id=web-edge&action=block_egress');
  });
  await sleep(2400);
  await page.screenshot({ path: `${OUT}/s7.png` });
  console.log('shot s7 (ok)');

  await browser.close();
  console.log('CAPTURE DONE', fs.readdirSync(OUT));
})().catch((e) => { console.error(e); process.exit(1); });
