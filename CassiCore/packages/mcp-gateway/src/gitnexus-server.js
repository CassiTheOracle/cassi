#!/usr/bin/env node
/**
 * GitNexus MCP Server wrapper for CassiCore
 * 
 * GitNexus provides code analysis and navigation tools.
 * Before using, run: npx gitnexus analyze
 */

import { spawn } from 'child_process';

const child = spawn('npx', ['-y', 'gitnexus@latest', 'mcp'], {
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
