# @cassicore/mcp-gateway

Server-side MCP gateway for CassiCore, extracted from `mcp/`. History-preserved
import splice. The MCP client (`core/mcp/*`) stays in `@cassicore/mcp` (P6).

## Surface

- `src/cassicore-gateway.ts` — the MCP server (stdio default, HTTP `--port 3000`)
- `src/scip-server.ts`, `src/gitnexus-server.js`, `src/serena-server.js` — servers
- `src/gateway/` — 38 files: `index.ts` (the consolidated-tool re-export barrel —
  `GATEWAY_VERSION`, `CORE_TOOLS`, `executeCassiCoreTool`, `SESSION_TOOLS`,
  `MEMORY_TOOLS`, `CONFIG_ADMIN_TOOLS`, …), `helpers.ts`, `tool-management.ts`
  (`executeCassiCoreTool`, `CORE_TOOLS`), plus the `*-tools.ts` consolidated tool
  modules (code/filesystem/web/intelligence/memory/model/session/config/context/
  training/browser), `query-intelligence.ts`, `blackboard-format.ts`,
  `tool-aliases.ts`, `serena-onboarding.ts`, `resources.ts`, `context-enrichment.ts`.

The `index.ts` barrel is the re-point target for constellation's vendored
`mcp-consolidated-tools` port and admin-api's `tools.ts`.

## Vendored / deferred

- `src/vendor/core/version.ts` — `GATEWAY_VERSION` (= `CASSICORE_VERSION`) from
  `core/version.ts`. Re-point to `@cassicore/host` when the host publishes
  `version` (P7 host turn / P8), per P7 table §3.
- `src/vendor/core/model-routing/model-directive.ts` — `ALL_TIER_NAMES` from
  `core/model-routing/model-directive.ts` (not yet a landed package). Re-point to
  its canonical home (host) when it publishes.

Depends on `@cassicore/foundation`, `@cassicore/thalamus`, `@cassicore/workspace`,
`@modelcontextprotocol/sdk`, `gitnexus`.
