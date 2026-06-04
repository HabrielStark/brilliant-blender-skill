/**
 * node --test web/test/  (run after `npm run build`)
 * Builds a tiny in-memory GLB, writes it, and checks the validator output.
 * Skips gracefully if dependencies / build output are missing.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

let validateGlb;
let Document, NodeIO;
try {
  ({ validateGlb } = await import('../dist/web_validate_asset.js'));
  ({ Document, NodeIO } = await import('@gltf-transform/core'));
} catch (err) {
  test('web validator (skipped: build/deps missing)', { skip: true }, () => {});
}

async function makeGlb(path, withMesh) {
  const doc = new Document();
  const buffer = doc.createBuffer();
  const scene = doc.createScene('Scene');
  if (withMesh) {
    const pos = doc
      .createAccessor('POS')
      .setType('VEC3')
      .setBuffer(buffer)
      .setArray(new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]));
    const prim = doc.createPrimitive().setAttribute('POSITION', pos);
    const mesh = doc.createMesh('tri').addPrimitive(prim);
    const node = doc.createNode('triNode').setMesh(mesh);
    scene.addChild(node);
  }
  await new NodeIO().write(path, doc);
}

if (validateGlb) {
  test('valid GLB with a mesh passes', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'bcas-'));
    const glb = join(dir, 'ok.glb');
    await makeGlb(glb, true);
    const r = await validateGlb(glb, { maxMb: 20 });
    assert.equal(r.ok, true);
    assert.equal(r.meshes, 1);
    assert.equal(r.nodes, 1);
    assert.deepEqual(r.errors, []);
  });

  test('empty GLB (no nodes) fails', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'bcas-'));
    const glb = join(dir, 'empty.glb');
    await makeGlb(glb, false);
    const r = await validateGlb(glb, {});
    assert.equal(r.ok, false);
    assert.ok(r.errors.some((e) => e.includes('no nodes')));
  });

  test('oversize budget fails', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'bcas-'));
    const glb = join(dir, 'big.glb');
    await makeGlb(glb, true);
    const r = await validateGlb(glb, { maxMb: 0.00001 });
    assert.equal(r.ok, false);
    assert.ok(r.errors.some((e) => e.includes('exceeds budget')));
  });

  test('CLI direct invocation prints a JSON report', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'bcas-'));
    const glb = join(dir, 'cli.glb');
    await makeGlb(glb, true);
    const here = dirname(fileURLToPath(import.meta.url));
    const cli = join(here, '..', 'dist', 'web_validate_asset.js');

    const result = spawnSync(process.execPath, [cli, glb, '--max-mb', '20'], {
      encoding: 'utf8',
    });

    assert.equal(result.status, 0, result.stderr || result.stdout);
    const report = JSON.parse(result.stdout);
    assert.equal(report.ok, true);
    assert.equal(report.meshes, 1);
  });
}
