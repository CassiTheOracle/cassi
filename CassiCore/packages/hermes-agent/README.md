# @cassicore/hermes-agent-gateway

Hermes Agent MCP gateway integration, migrated history-preserved from
`D:\carina\workspaces\cassicore\integrations\hermes-agent` (committed
`d63358da`).

## Package identity

This is an **external-facing bridge** registered into the Hermes agent runtime.
Its npm `name` (`@cassicore/hermes-agent-gateway`) and `bin`
(`cassicore-hermes`) are preserved **as-is** for external tooling.

> **External re-pointing pending owner confirmation.** Anything external that
> references this package's location is intentionally **NOT** re-pointed here —
> it requires the owner's confirmation. See `MIGRATION-STATUS.md` §Remaining
> work.

## What lives here

The full tracked `integrations/hermes-agent/` tree — MCP server entry
(`src/server.ts`, `src/helpers.ts`, `src/state-db.ts`, `src/tools/sessions.ts`),
Hermes context-engine + plugin (`context_engine/*`, `plugin/*`), and the
manifest (`package.json`, `tsconfig.json`, `AGENTS.md`).

Per recon-architecture §4.3 these are **live external adapters** (separate
processes launched by the Hermes host), not dead code; the whole subtree is
migrated as a live standalone package.
