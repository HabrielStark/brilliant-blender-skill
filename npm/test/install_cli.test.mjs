import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const cliPath = fileURLToPath(new URL('../cli.mjs', import.meta.url));

function runCli(args) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    encoding: 'utf8',
    cwd: path.resolve(fileURLToPath(new URL('../..', import.meta.url))),
  });
}

test('doctor verifies the npm package contains skill files', () => {
  const result = runCli(['doctor']);

  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /package is complete/);
});

test('install copies the skill into a target directory', () => {
  const target = mkdtempSync(path.join(tmpdir(), 'brilliant-blender-skill-'));
  try {
    const result = runCli(['install', '--target', target]);

    assert.equal(result.status, 0, result.stderr);
    assert.ok(existsSync(path.join(target, 'SKILL.md')));
    assert.ok(existsSync(path.join(target, 'docs', 'VISUAL_ACCEPTANCE_REPORT.md')));
    assert.ok(existsSync(path.join(target, 'references', 'lighting-materials.md')));
    assert.ok(existsSync(path.join(target, 'benchmarks', 'live_agent_runs', 'watch_live_agent_forward_v6_20260604.json')));
    assert.ok(existsSync(path.join(target, 'web', 'dist', 'web_validate_asset.js')));
    assert.match(readFileSync(path.join(target, 'SKILL.md'), 'utf8'), /name: blender-cinematic-scene/);
  } finally {
    rmSync(target, { recursive: true, force: true });
  }
});
