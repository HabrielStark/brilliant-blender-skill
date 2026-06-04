import { test, expect } from '@playwright/test';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, isAbsolute, join, relative, resolve } from 'node:path';
import sharp from 'sharp';
import { mkdirSync } from 'node:fs';

// Fully offline: vendored three.js (node_modules/three) + the real exported GLB,
// served by a tiny in-test static server. No CDN, no external webServer => the
// suite cannot hang on the network. Proves the GLB loads, renders on a live
// WebGL canvas, and animates via AnimationMixer in a real browser (SRS 17.4).

const ROOT = process.cwd();
const ROUTES = { '/three/': resolve(ROOT, 'node_modules', 'three'),
                 '/demo/': resolve(ROOT, 'examples', 'web-demo'),
                 '/': resolve(ROOT, 'web', 'e2e') };
const MIME = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.html': 'text/html',
               '.glb': 'model/gltf-binary', '.json': 'application/json', '.css': 'text/css' };
const SHOTS = join(ROOT, 'examples', 'web-demo', 'screenshots');
mkdirSync(SHOTS, { recursive: true });

let server, base;

function safeRouteFile(root, relPath) {
  const file = resolve(root, relPath);
  const rel = relative(root, file);
  if (rel === '' || (!rel.startsWith('..') && !isAbsolute(rel))) return file;
  return null;
}

test.beforeAll(async () => {
  server = createServer(async (req, res) => {
    try {
      const url = decodeURIComponent(req.url.split('?')[0]);
      let file = null;
      if (url.startsWith('/three/')) file = safeRouteFile(ROUTES['/three/'], url.slice('/three/'.length));
      else if (url.startsWith('/demo/')) file = safeRouteFile(ROUTES['/demo/'], url.slice('/demo/'.length));
      else file = safeRouteFile(ROUTES['/'], url === '/' ? 'offline.html' : url.slice(1));
      if (file === null) { res.writeHead(403).end(); return; }
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream' }).end(body);
    } catch { res.writeHead(404).end('not found'); }
  });
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});

test.afterAll(() => server && server.close());

async function canvasStdDev(page) {
  const buf = await page.locator('canvas').screenshot();
  const stats = await sharp(buf).stats();
  return Math.max(...stats.channels.map((c) => c.stdev));
}

async function waitForNonFlatCanvas(page, threshold = 3) {
  let stdev = 0;
  await expect
    .poll(async () => {
      stdev = await canvasStdDev(page);
      return stdev;
    }, { timeout: 8000, intervals: [150, 250, 500, 1000] })
    .toBeGreaterThan(threshold);
  return stdev;
}

async function loadHarness(page) {
  const errors = [];
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto(`${base}/offline.html`, { waitUntil: 'load', timeout: 15000 });
  await page.waitForFunction(() => window.__ready === true, { timeout: 15000 });
  expect(await page.evaluate(() => window.__error), 'GLB load error').toBeNull();
  return errors;
}

test('GLB renders on a live WebGL canvas (desktop) with no console errors', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  const errors = await loadHarness(page);
  const stdev = await waitForNonFlatCanvas(page);
  await page.screenshot({ path: join(SHOTS, 'desktop.png') });
  expect(stdev, 'canvas must not be blank/flat').toBeGreaterThan(3);
  expect(errors, errors.join(' | ')).toEqual([]);
});

test('static server rejects route traversal outside mount roots', async ({ request }) => {
  const demoEscape = await request.get(`${base}/demo/%2e%2e/prompts/product_hero_watch.json`);
  const rootEscape = await request.get(`${base}/%2e%2e/%2e%2e/package.json`);
  expect(safeRouteFile(ROUTES['/demo/'], '../prompts/product_hero_watch.json')).toBeNull();
  expect(safeRouteFile(ROUTES['/'], '../../package.json')).toBeNull();
  expect([403, 404]).toContain(demoEscape.status());
  expect([403, 404]).toContain(rootEscape.status());
});

test('animated GLB has clips and the AnimationMixer advances', async ({ page }) => {
  await loadHarness(page);
  expect(await page.evaluate(() => window.__clips)).toBeGreaterThanOrEqual(1);
  expect(await page.evaluate(() => window.__childCount)).toBeGreaterThan(0);
  const t0 = await page.evaluate(() => window.__mixerTime ?? 0);
  await page.waitForTimeout(1000);
  const t1 = await page.evaluate(() => window.__mixerTime ?? 0);
  expect(t1 - t0, 'AnimationMixer time should advance').toBeGreaterThan(0.5);
});

test('mobile viewport still renders', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loadHarness(page);
  expect(await waitForNonFlatCanvas(page)).toBeGreaterThan(3);
  await page.screenshot({ path: join(SHOTS, 'mobile.png') });
});
