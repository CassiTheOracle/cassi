# @cassicore/cognitive-feed

Observation-and-delivery feed subsystem extracted from CassiCore with git-history
preservation.

Migrated from `core/intelligence/cognitive-feed/` (D: read-only source).
Registry-discovered: `CognitiveFeedModule extends BaseCognitiveModule`
(name `cognitive-feed`, priority 5 — observation only, runs after everything else).

## What it does

- **Event curation** — `EventCurator` filters runtime events (`RuntimeEvent`) down
  to a curated feed.
- **Windowing** — `WindowManager` maintains rolling dashboard/activity/helix/corpus
  windows and renders them as formatted messages.
- **Delivery** — `DeliveryBatcher` + `RateLimiter` throttle Telegram delivery;
  `MessageFormatter` formats messages for display.
- **Chat handlers** — general chat (`GeneralChatHandler`), module chat
  (`ModuleChatHandler`), steering (`SteeringHandler`), and topic routing
  (`TopicManager`), backed by `TelegramClient`.
- **Transport** — `InteractiveToolSession` / `splitForTelegram` multi-turn parameter
  collection (vendored, re-pointed to `@cassicore/tools` at P6).

## Host wiring

Registry-discovered (see `@cassicore/thalamus` README). `index.ts` preserves the
`CognitiveFeedModule` class plus the handler/tools surface the host wires. There are
**no inbound vendor stubs** shadowing this package anywhere in the workspace.

## Dependencies

- `@cassicore/foundation` — `ILogger`, `RuntimeEvent`, `BaseCognitiveModule`.

## Vendor stubs

- `vendor/core/tools/interactive-tool-session.js` — **runtime** faithful copy
  (`InteractiveToolSession`, `splitForTelegram`, `ToolDefinition`); re-point to
  `@cassicore/tools` at P6.
- `vendor/core/intelligence/module-session-registry.js` — type-only stub for
  `ModuleSessionRegistry` / `ModuleRegistration`; re-point to `@cassicore/workspace`.
