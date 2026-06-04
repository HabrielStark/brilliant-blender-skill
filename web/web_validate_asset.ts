#!/usr/bin/env node
/**
 * Local-first GLB validator (SRS 12.4 web.validate_glb, 14.3).
 *
 * Loads a .glb with @gltf-transform/core and reports structure + size with no
 * browser and no paid service. Complements the pure-Python validator in
 * blender_cinematic/glb.py (the two cross-check each other).
 *
 * Usage: bcas-validate-glb <file.glb> [--max-mb 20] [--require-animation]
 */
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { realpathSync, statSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';

export interface GlbReport {
  ok: boolean;
  path: string;
  sizeBytes: number;
  sizeMb: number;
  nodes: number;
  meshes: number;
  materials: number;
  animations: number;
  animationNames: string[];
  cameras: number;
  textures: number;
  externalTextures: string[];
  generator: string | null;
  errors: string[];
  warnings: string[];
}

export async function validateGlb(
  path: string,
  opts: { maxMb?: number; requireAnimation?: boolean } = {},
): Promise<GlbReport> {
  const errors: string[] = [];
  const warnings: string[] = [];
  const sizeBytes = statSync(path).size;
  const sizeMb = +(sizeBytes / (1024 * 1024)).toFixed(3);

  const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
  const doc = await io.read(path);
  const root = doc.getRoot();

  const nodes = root.listNodes().length;
  const meshes = root.listMeshes().length;
  const materials = root.listMaterials().length;
  const animations = root.listAnimations();
  const cameras = root.listCameras().length;
  const textures = root.listTextures();

  const externalTextures = textures
    .map((t) => t.getURI())
    .filter((uri) => uri && !uri.startsWith('data:')) as string[];

  if (nodes === 0) errors.push('GLB has no nodes (empty scene)');
  if (meshes === 0) warnings.push('GLB has no meshes');
  if (opts.maxMb != null && sizeMb > opts.maxMb)
    errors.push(`GLB ${sizeMb}MB exceeds budget ${opts.maxMb}MB`);
  if (opts.requireAnimation && animations.length === 0)
    errors.push('animation required but GLB has no animation clips');
  if (externalTextures.length)
    errors.push(`GLB references external textures: ${externalTextures.join(', ')}`);

  return {
    ok: errors.length === 0,
    path,
    sizeBytes,
    sizeMb,
    nodes,
    meshes,
    materials,
    animations: animations.length,
    animationNames: animations.map((a) => a.getName()),
    cameras,
    textures: textures.length,
    externalTextures,
    generator: root.getAsset().generator ?? null,
    errors,
    warnings,
  };
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('usage: web_validate_asset <file.glb> [--max-mb N] [--require-animation]');
    process.exit(2);
  }
  const path = args[0];
  const maxIdx = args.indexOf('--max-mb');
  const maxMb = maxIdx >= 0 ? Number(args[maxIdx + 1]) : undefined;
  const requireAnimation = args.includes('--require-animation');
  try {
    const report = await validateGlb(path, { maxMb, requireAnimation });
    console.log(JSON.stringify(report, null, 2));
    process.exit(report.ok ? 0 : 1);
  } catch (err) {
    console.log(JSON.stringify({ ok: false, errors: [String(err)] }, null, 2));
    process.exit(1);
  }
}

function isDirectRun(): boolean {
  if (!process.argv[1]) return false;
  try {
    return realpathSync(fileURLToPath(import.meta.url)) === realpathSync(process.argv[1]);
  } catch {
    return import.meta.url === pathToFileURL(process.argv[1]).href;
  }
}

// Run only when invoked directly (not when imported by tests). Cross-platform.
if (isDirectRun()) {
  void main();
}
