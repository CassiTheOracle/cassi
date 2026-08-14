# @cassicore/mcp

Client-side MCP integration extracted from CassiCore `core/mcp/*`.
History-preserved import splice. Speaks to **external** MCP servers via
`@modelcontextprotocol/sdk`.

## Surface

- `MCPClient` (`client.ts`) — connects to external MCP servers
  (`MCPServerConfig` from `types.ts`).
- `MCPRegistry` (`registry.ts`) — manages MCP server connections (type-links
  `@cassicore/tools` `ToolRegistry`/`ToolDefinition`).
- `types.ts` — `MCPServerConfig`, `MCPServerStatus`, `MCPConnectionState`,
  `MCPToolInfo`.
- `index.ts` — barrel.

The **server-side** stdio/HTTP gateway (`mcp/cassicore-gateway.ts` +
`mcp/gateway/*`) is NOT here — it is `@cassicore/mcp-gateway` at P7.

## Vendored

- `src/vendor/core/version.ts` — pure `CASSICORE_VERSION` constant (source
  `core/version.ts`), imported by `client.ts` (the D: import came from
  `core/daemon.js`). Owned by a future `@cassicore/version` at P7/P8.

Depends on `@cassicore/foundation`, `@cassicore/tools`,
`@modelcontextprotocol/sdk`.
