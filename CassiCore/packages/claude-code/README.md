# @cassicore/claude-code-mcp

Claude Code integration bridge (MCP server + HTTP proxy + hooks), migrated
history-preserved from `D:\carina\workspaces\cassicore\integrations\claude-code`
(committed `d63358da`).

## Package identity

This is an **external-facing bridge** installed by Claude Code tooling. Its npm
`name` (`@cassicore/claude-code-mcp`) and `bin` (`cassicore-mcp`) are preserved
**as-is** so external installers/hooks keep working.

> **External re-pointing pending owner confirmation.** External tooling or
> symlink targets referencing this package's D:/ location are intentionally
> **NOT** re-pointed in this migration — they require the owner's explicit
> confirmation before changing. See `MIGRATION-STATUS.md` §Remaining work.

## What lives here

The full tracked `integrations/claude-code/` tree — MCP bridge surface
(`src/bridge.ts`, `src/context-builder.ts`, `src/provider-registry.ts`,
`src/state.ts`, `src/model-router.ts`), runtime proxy + hook entries
(`src/proxy.ts`, `src/hook-server.ts`, `src/hook-command.cjs`, `src/server.ts`,
`src/settings-sync.ts`, `src/logger.ts`), and manifest (`package.json`,
`tsconfig.json`, `.env.example`, `settings.example.json`, `CLAUDE.md`).

Per recon-architecture §4.3 these are **live external adapters** (separate
processes launched by the Claude Code host via hooks/proxy), not dead code; the
whole subtree is migrated as a live standalone package.
