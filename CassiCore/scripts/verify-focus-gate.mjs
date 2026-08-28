#!/usr/bin/env node
/**
 * verify-focus-gate.mjs — CASSICORE-FOCUS acceptance gate (P7).
 *
 * Fails (exit 1) if ANY retained package (packages/(name)/src) imports a deleted /
 * standalone-surface `@cassicore/*` package, or references the pre-migration
 * standalone bare layout (`core/intelligence`, `core/daemon`) as an import
 * specifier. Also asserts the mind-runtime/spine dependency contract.
 *
 * Zero-import guard (CASSICORE-FOCUS-PLAN §6 P7): the focused mind is 22 retained
 * packages; no retained package may reach across the seam into the ohmypi-owned /
 * deleted surface. Deleted at P4/P5/P6 + host at P7:
 *   host, providers, ai, admin-api, mcp-gateway, mcp, pipeline, commands,
 *   workers, plugins, jobs, cassi-tui, cassi-watch, prism, webui,
 *   claude-code-mcp, hermes-agent-gateway, opencode
 *
 * Node, no deps. Run: `npm run verify:focus` (or `node scripts/verify-focus-gate.mjs`).
 */

import { execFileSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)));
const PACKAGES = join(ROOT, 'packages');

const FORBIDDEN = [
  'host', 'providers', 'ai', 'admin-api', 'mcp-gateway', 'mcp', 'pipeline',
  'commands', 'workers', 'plugins', 'jobs', 'cassi-tui', 'cassi-watch',
  'prism', 'webui', 'claude-code-mcp', 'hermes-agent-gateway', 'opencode',
];

// Bare standalone-layout path prefixes (the pre-migration `core/` tree). Relative
// specifiers like ./vendor/core/intelligence/... are vendored in-process copies and
// are NOT part of the standalone layout — excluded.
const STANDALONE_PATH = /^core\/(?:intelligence|daemon)(?:\/|$)/;

function log(...args) {
  console.log(...args);
}

/**
 * Enumerate the RETAINED (git-tracked) package names under packages/*.
 * Uses `git ls-tree HEAD packages/` so stale untracked leftovers in the working
 * tree (deleted packages' empty dirs, vendor tmp) are never scanned.
 */
function retainedPackages() {
  const out = execFileSync('git', ['ls-tree', '--name-only', 'HEAD', 'packages/'], {
    cwd: ROOT, encoding: 'utf8',
  });
  return out
    .split('\n')
    .map((l) => l.trim().replace(/^packages\//, ''))
    .filter((p) => p && /^[a-z0-9-]+$/.test(p));
}

/**
 * Walk a directory recursively, returning relative file paths.
 */
function walkFiles(dir, base) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const rel = base ? join(base, entry) : entry;
    const st = statSync(p);
    if (st.isDirectory()) out.push(...walkFiles(p, rel));
    else out.push(rel);
  }
  return out;
}

/**
 * Scan file text for import/require/from specifier strings.
 * Returns [{ line, specifier }] for every module specifier appearing in an
 * import/export/require context (ES static, dynamic import(), require, re-export).
 */
function importSpecifiers(text) {
  const out = [];
  // Matches: `from 'spec'`, `import 'spec'`, `import('spec')`,
  //          `require('spec')`, `require.resolve('spec')`, `export ... from 'spec'`
  const re = /(?:from\s+|import\s*\(|require\s*(?:\.resolve)?\s*\(|import\s+)(['"])(.*?)\1/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    out.push({ line: text.slice(0, m.index).split('\n').length, specifier: m[2] });
  }
  return out;
}

let failures = 0;

function fail(where, msg) {
  failures += 1;
  log(`  [FAIL] ${where}: ${msg}`);
}

const pkgs = retainedPackages();
log(`Focus gate — scanning ${pkgs.length} retained packages under packages/*/src`);
log('  forbidden @cassicore/*:', FORBIDDEN.join(', '));
log('  standalone bare layout: core/intelligence/**, core/daemon');
log('');

// --- 1. package-name → fixed forbidden specifier mapping ---
const forbiddenSpecifiers = new Set(FORBIDDEN.map((n) => `@cassicore/${n}`));

// --- 2. scan every retained package's src/ tree ---
for (const pkg of pkgs) {
  const srcDir = join(PACKAGES, pkg, 'src');
  if (!existsSync(srcDir)) continue; // substrate packages may have no src/ (embed/provider)
  const files = walkFiles(srcDir);
  if (files.length === 0) continue;
  for (const rel of files) {
    if (!/\.(m?[jt]sx?|c[jt]s)$/.test(rel)) continue;
    const filePath = join(srcDir, rel);
    let text;
    try {
      text = readFileSync(filePath, 'utf8');
    } catch {
      continue;
    }
    for (const { line, specifier } of importSpecifiers(text)) {
      // exact forbidden @cassicore/* match
      if (forbiddenSpecifiers.has(specifier)) {
        fail(
          `${pkg}/src/${rel}:${line}`,
          `imports deleted/standalone package '${specifier}'`,
        );
      }
      // bare standalone-layout path (non relative)
      if (STANDALONE_PATH.test(specifier) && !specifier.startsWith('.')) {
        fail(
          `${pkg}/src/${rel}:${line}`,
          `imports pre-migration bare standalone path '${specifier}'`,
        );
      }
    }
  }
}

// --- 3. mind-runtime dependency contract: no host/spine dep ---
const mindRuntimePkg = join(PACKAGES, 'mind-runtime', 'package.json');
if (existsSync(mindRuntimePkg)) {
  const deps = {
    ...JSON.parse(readFileSync(mindRuntimePkg, 'utf8')).dependencies,
  };
  for (const bad of ['@cassicore/host', '@cassicore/spine']) {
    if (Object.prototype.hasOwnProperty.call(deps, bad)) {
      fail('mind-runtime/package.json', `must not depend on '${bad}'`);
    }
  }
} else {
  fail('mind-runtime', 'package.json missing — cannot verify dependency contract');
}

// --- 4. spine dependency contract: must depend on mind-runtime + tools ---
const spinePkg = join(PACKAGES, 'spine', 'package.json');
if (existsSync(spinePkg)) {
  const deps = { ...JSON.parse(readFileSync(spinePkg, 'utf8')).dependencies };
  for (const need of ['@cassicore/mind-runtime', '@cassicore/tools']) {
    if (!Object.prototype.hasOwnProperty.call(deps, need)) {
      fail('spine/package.json', `must depend on '${need}'`);
    }
  }
} else {
  fail('spine', 'package.json missing — cannot verify dependency contract');
}

log('');
if (failures > 0) {
  log(`FOCUS GATE FAILED — ${failures} issue(s) found.`);
  process.exit(1);
}
log(`FOCUS GATE PASSED — ${pkgs.length} retained packages: zero standalone-surface imports, `
  + 'mind-runtime/spine dependency contracts valid.');
process.exit(0);
