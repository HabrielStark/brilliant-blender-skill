import { test, expect } from '@playwright/test';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, isAbsolute, join, relative, resolve } from 'node:path';
import { mkdirSync } from 'node:fs';
import { inflateSync } from 'node:zlib';

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
  return pngLumaStdDev(buf);
}

function pngLumaStdDev(buf) {
  const signature = '89504e470d0a1a0a';
  if (buf.subarray(0, 8).toString('hex') !== signature) throw new Error('not a PNG');
  let offset = 8;
  let width = 0;
  let height = 0;
  let bitDepth = 0;
  let colorType = 0;
  const idat = [];
  while (offset < buf.length) {
    const length = buf.readUInt32BE(offset);
    const type = buf.subarray(offset + 4, offset + 8).toString('ascii');
    const data = buf.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    offset += 12 + length;
  }
  if (bitDepth !== 8) throw new Error(`unsupported PNG bit depth ${bitDepth}`);
  const channels = colorType === 6 ? 4 : colorType === 2 ? 3 : colorType === 0 ? 1 : 0;
  if (!channels) throw new Error(`unsupported PNG color type ${colorType}`);
  const raw = inflateSync(Buffer.concat(idat));
  const stride = width * channels;
  const pixels = Buffer.alloc(height * stride);
  let input = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = raw[input];
    input += 1;
    const rowStart = y * stride;
    const prevStart = (y - 1) * stride;
    for (let x = 0; x < stride; x += 1) {
      const left = x >= channels ? pixels[rowStart + x - channels] : 0;
      const up = y > 0 ? pixels[prevStart + x] : 0;
      const upLeft = y > 0 && x >= channels ? pixels[prevStart + x - channels] : 0;
      let predictor = 0;
      if (filter === 1) predictor = left;
      else if (filter === 2) predictor = up;
      else if (filter === 3) predictor = Math.floor((left + up) / 2);
      else if (filter === 4) predictor = paeth(left, up, upLeft);
      else if (filter !== 0) throw new Error(`unsupported PNG filter ${filter}`);
      pixels[rowStart + x] = (raw[input + x] + predictor) & 0xff;
    }
    input += stride;
  }
  let sum = 0;
  let sumSquares = 0;
  let count = 0;
  for (let i = 0; i < pixels.length; i += channels) {
    const r = pixels[i];
    const g = channels >= 3 ? pixels[i + 1] : r;
    const b = channels >= 3 ? pixels[i + 2] : r;
    const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
    sum += luma;
    sumSquares += luma * luma;
    count += 1;
  }
  const mean = sum / count;
  return Math.sqrt(Math.max(0, sumSquares / count - mean * mean));
}

function paeth(a, b, c) {
  const p = a + b - c;
  const pa = Math.abs(p - a);
  const pb = Math.abs(p - b);
  const pc = Math.abs(p - c);
  if (pa <= pb && pa <= pc) return a;
  if (pb <= pc) return b;
  return c;
}

async function waitForNonFlatCanvas(page, threshold = 8) {
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
  expect(stdev, 'canvas must contain a readable subject silhouette').toBeGreaterThan(8);
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
  expect(await waitForNonFlatCanvas(page)).toBeGreaterThan(8);
  await page.screenshot({ path: join(SHOTS, 'mobile.png') });
});
