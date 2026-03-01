#!/usr/bin/env node
/**
 * Serena MCP Server wrapper for CassiCore
 * 
 * Serena is a Rust-based code navigation and analysis tool.
 * Managed by uv. Automatically installs/updates on first run.
 */

import { spawn } from 'child_process';

// Use uvx to run serena without global installation
const child = spawn('uvx', ['--from', 'git+https://github.com/oraios/serena', 'serena', 'start-mcp-server'], {
  stdio: ['inherit', 'inherit', 'inherit'],
  env: { ...process.env }
});

child.on('error', (err) => {
  console.error('Serena MCP server error:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code ?? 1);
});
