#!/usr/bin/env node
/**
 * GitNexus MCP Server wrapper for CassiCore
 *
 * Bootstraps the GitNexus MCP server on stdio transport with
 * the multi-repo LocalBackend. Lazily discovers repos from the
 * global registry — works from any directory.
 */
import { startMCPServer } from '../node_modules/gitnexus/dist/mcp/server.js';
import { LocalBackend } from '../node_modules/gitnexus/dist/mcp/local/local-backend.js';

process.on('uncaughtException', (err) => {
  process.stderr.write(`GitNexus MCP uncaughtException: ${err.stack || err}\n`);
  // Exit after flushing — uncaughtException means undefined state
  setTimeout(() => process.exit(1), 100);
});

process.on('unhandledRejection', (reason) => {
  const msg = reason instanceof Error ? reason.message : String(reason);
  process.stderr.write(`GitNexus MCP unhandledRejection: ${msg}\n`);
});

async function main() {
  const backend = new LocalBackend();
  await backend.init();
  const repos = await backend.listRepos();
  if (repos.length === 0) {
    process.stderr.write('GitNexus: No indexed repos yet. Run `gitnexus analyze` in a git repo — the server will pick it up automatically.\n');
  } else {
    process.stderr.write(`GitNexus: MCP server starting with ${repos.length} repo(s): ${repos.map(r => r.name).join(', ')}\n`);
  }
  await startMCPServer(backend);
}

main().catch((err) => {
  process.stderr.write(`GitNexus MCP fatal: ${err.stack || err}\n`);
  process.exit(1);
});
