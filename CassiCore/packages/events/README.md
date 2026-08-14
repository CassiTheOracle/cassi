# @cassicore/events

In-memory `ILogger`/`IEventBus` runtime defaults plus the event protocol/API,
Cassandra client and context-window debugger, extracted from CassiCore
(`core/logger.ts`, `core/event-bus.ts`, `core/events/*`). History-preserved
import splice.

## Resolves P1 ASK-2

Foundation ships the **interfaces only** (`ILogger`, `IEventBus`, `LogLevel`,
`RuntimeEvent`, `EventOf`, `Unsubscribe`, `Message`, …). The default runtime
implementations live here:

- `Logger` / `rootLogger` (`logger.ts`) — file transport, level priority, ANSI
  styling, thought logs, version-based rotation.
- `EventBus` / `bus` (`event-bus.ts`) — ring-buffer bus wired to `rootLogger`.

Export names preserved verbatim (consumers repo-wide import `rootLogger` /
`bus` / `getEventBus`).

## Protocol & clients

- `events/event-types.ts`, `events/event-api.ts`, `events/cassandra-event-client.ts`,
  `events/context-window-debug.ts` (under `src/events/`), barrel `index.ts`.

## Vendored

- `src/vendor/core/config/resource-limits.ts` — faithful runtime copy of
  `core/config/resource-limits.ts` (`DEFAULT_RESOURCE_LIMITS`, self-contained),
  imported by `events/event-api.ts`. Absorbed into foundation (single config
  home) or re-pointed at P7.

Depends on `@cassicore/foundation` only.
