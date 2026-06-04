#!/usr/bin/env node
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const packageRoot = path.resolve(__dirname, '..');
const skillName = 'blender-cinematic-scene';

const installEntries = [
  'SKILL.md',
  'AGENTS.md',
  'README.md',
  'LICENSE',
  'THIRD_PARTY_NOTICES.md',
  'SECURITY.md',
  'CONTRIBUTING.md',
  'RUNBOOK.md',
  'CHANGELOG.md',
  '.env.example',
  'docs',
  'references',
  'scripts',
  'benchmarks',
  'blender_cinematic',
  'mcp_server',
  'addon',
  'web',
  'examples',
  'pyproject.toml',
  'package.json',
  'tsconfig.json',
  'playwright.config.mjs',
];

function usage() {
  console.log(`brilliant-blender-skill

Commands:
  install [--target <dir>] [--codex-home <dir>]
      Install the Blender Cinematic Scene skill into Codex skills.

  doctor
      Check that this npm package contains the required skill files.

  where
      Print the default install target.

Examples:
  npm install -g github:HabrielStark/brilliant-blender-skill
  brilliant-blender-skill install
  brilliant-blender-skill install --target C:\\tmp\\blender-cinematic-scene
`);
}

function parseOptions(argv) {
  const opts = { command: argv[0] || 'help' };
  for (let i = 1; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--target') {
      opts.target = argv[++i];
    } else if (arg === '--codex-home') {
      opts.codexHome = argv[++i];
    } else if (arg === '--help' || arg === '-h') {
      opts.help = true;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return opts;
}

function defaultCodexHome(opts) {
  return opts.codexHome || process.env.CODEX_HOME || path.join(homedir(), '.codex');
}

function defaultTarget(opts) {
  return path.resolve(opts.target || path.join(defaultCodexHome(opts), 'skills', skillName));
}

function assertPackageReady() {
  const missing = [];
  for (const entry of installEntries) {
    if (!existsSync(path.join(packageRoot, entry))) {
      missing.push(entry);
    }
  }
  const skill = path.join(packageRoot, 'SKILL.md');
  if (existsSync(skill)) {
    const text = readFileSync(skill, 'utf8');
    if (!text.includes('name: blender-cinematic-scene')) {
      missing.push('SKILL.md frontmatter name');
    }
  }
  if (missing.length) {
    throw new Error(`package is missing required skill files: ${missing.join(', ')}`);
  }
}

function copyEntry(entry, target) {
  const src = path.join(packageRoot, entry);
  const dest = path.join(target, entry);
  const stat = statSync(src);
  mkdirSync(path.dirname(dest), { recursive: true });
  if (stat.isDirectory()) {
    cpSync(src, dest, { recursive: true, force: true, dereference: false });
  } else {
    copyFileSync(src, dest);
  }
}

function install(opts) {
  assertPackageReady();
  const target = defaultTarget(opts);
  mkdirSync(target, { recursive: true });
  for (const entry of installEntries) {
    copyEntry(entry, target);
  }
  console.log(`Installed ${skillName} to ${target}`);
  console.log('Next: start a new Codex session and ask it to use blender-cinematic-scene.');
  console.log(`Optional validation: python "${path.join(target, 'scripts', 'validate_skill.py')}"`);
}

function main(argv) {
  const opts = parseOptions(argv);
  if (opts.help || opts.command === 'help') {
    usage();
    return 0;
  }
  if (opts.command === 'install') {
    install(opts);
    return 0;
  }
  if (opts.command === 'doctor') {
    assertPackageReady();
    console.log('brilliant-blender-skill package is complete');
    return 0;
  }
  if (opts.command === 'where') {
    console.log(defaultTarget(opts));
    return 0;
  }
  throw new Error(`unknown command: ${opts.command}`);
}

try {
  process.exitCode = main(process.argv.slice(2));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
