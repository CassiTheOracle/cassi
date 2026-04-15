#!/usr/bin/env node
/**
 * GitNexus MCP Server wrapper for CassiCore
 * 
 * Uses the locally installed gitnexus package (node_modules/.bin/gitnexus)
 * instead of npx @latest to avoid slow npm registry checks on every startup.
 * Before using, run: npx gitnexus analyze
 */

import { spawn } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');

// Prefer local node_modules/.bin/gitnexus, fall back to global
const localBin = resolve(repoRoot, 'node_modules', '.bin', 'gitnexus');
const command = existsSync(localBin) ? localBin : 'gitnexus';

const child = spawn(command, ['mcp'], {
  stdio: ['inherit', 'inherit', 'inherit'],
  env: { ...process.env }
});

child.on('error', (err) => {
  console.error('GitNexus MCP server error:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code ?? 1);
});
