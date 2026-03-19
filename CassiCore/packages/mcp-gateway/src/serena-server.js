#!/usr/bin/env node
/**
 * Serena MCP Server wrapper for CassiCore
 * 
 * Serena is a Python-based code navigation and analysis tool.
 * Managed by uv. Automatically installs/updates on first run.
 *
 * Uses --project-from-cwd so Serena always roots itself in the daemon's
 * working directory rather than looking up a project name in the global
 * project list (which could resolve to a stale path from a previous install).
 */

import { spawn } from 'child_process';

// Pass --project-from-cwd so the project root is always the daemon's CWD,
// preventing stale project-name lookups in ~/.serena/serena_config.yml.
const child = spawn('uvx', [
  '--from', 'git+https://github.com/oraios/serena',
  'serena', 'start-mcp-server',
  '--project-from-cwd',
], {
  stdio: ['inherit', 'inherit', 'inherit'],
  env: { ...process.env },
  cwd: process.cwd(),
});

child.on('error', (err) => {
  console.error('Serena MCP server error:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code ?? 1);
});
