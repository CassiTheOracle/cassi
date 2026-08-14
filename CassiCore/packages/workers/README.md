# @cassicore/workers

Channel worker modules for the CassiCore plugin host, extracted from CassiCore's
`workers/`. History-preserved import splice.

## Surface

- `src/echo-channel.ts` — echo worker
- `src/channels/cli.ts`, `src/channels/telegram.ts`, `src/channels/webchat.ts` —
  channel workers the host loads via `resolveWorker('@cassicore/workers/channels/…')`
- `src/channels/telegram-common.ts` — telegram shared helpers
- `src/channels/markdown/{format,ir,render}.ts` — markdown rendering (via `markdown-it`)

> **Note:** `resolveWorker('../workers/channels/opencode')` in the daemon is a **ghost
> reference** — no `opencode` worker exists; the null-guard is preserved.

## Vendored

- `src/vendor/core/worker-ipc.ts` — faithful runtime copy of `core/worker-ipc.ts`
  (`workerPort` + IPC message types) — self-contained; no landed package owns it yet
  (`@cassicore/plugins` references but does not export it). Re-point to its home when
  it publishes.

Depends on `@cassicore/foundation`, `@cassicore/events`, `markdown-it`.
