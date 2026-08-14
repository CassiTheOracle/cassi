/**
 * @cassicore/mcp-gateway public surface — the consolidated-tool barrel.
 *
 * The gateway's `src/gateway/index.ts` is the re-export barrel MCP tool
 * consumers import (the `index.ts` quoted in the P7 table §2.B / §6.B: the
 * consolidated code/filesystem/web/intelligence/memory/model/session/config/
 * context/training/browser tool surface + `CORE_TOOLS`/`executeCassiCoreTool`).
 * This root barrel re-exports it so `@cassicore/mcp-gateway` resolves the
 * consolidated-tool surface at the package root (e.g. helix's vendored
 * `vendor/mcp/gateway` stub re-point).
 *
 * The server entrypoints (`cassicore-gateway.ts`, `scip-server.ts`,
 * `gitnexus-server.js`, `serena-server.js`) are run as binaries, not exported
 * here.
 */
export * from './gateway/index.js'
