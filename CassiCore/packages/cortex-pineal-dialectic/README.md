# @cassicore/cortex-pineal-dialectic

The field-processing cluster extracted from CassiCore with git-history
preservation: the six-region cortical field (`cortex/`), the pineal identity
module (`pineal/`), and the dialectic reasoning system (`dialectic/`) as ONE
package (plan §5-P5 "field-processing cluster").

Migrated from `core/intelligence/{cortex,pineal,dialectic}/` (D:, read-only).
**Mixed wiring surfaces:**

- `PinealModule` — registry-discovered (extends `BaseCognitiveModule`, priority 90).
- `CorticalField` — explicit library (NOT a cognitive module); daemon calls
  `startOscillation()` / `setAffectRegister()` / `setConsolidationCallback()`.
- `DialecticSystem` / `createDialecticSystem` — explicit (implements `IDialecticSystem`).

## What it does

- **Cortex** — six-region field (`sensory/association/executive/motor/limbic/monitor`)
  with tract dynamics, signal→engram consolidation, and sessions.
- **Pineal** — identity/facet store, skill parsing/loading, facet assembly.
- **Dialectic** — yang/yin observers, serenity synthesis, dialectic engine,
  thought formatting.

## Dependencies

- `@cassicore/foundation` — `ILogger`, `IEventBus`, `IProvider`, the dialectic types
  (`IDialecticSystem`, `DialecticResult`, `YangOutput`, ...), `getModelSpec`,
  `BaseCognitiveModule`, `getDataDir`.
- `@cassicore/mnemic-field` — `Affect`, `AffectLabel`, `EngramType`, `Engram`,
  `ConsolidationTarget`, `MnemicField`, `AffectRegister` (types).
- `@cassicore/flux-team` — `GlobalBlackboardRegistry` (type).
- `better-sqlite3` — `pineal/store`, `dialectic/index`.

## Vendor stubs

- `vendor/core/intelligence/module-session-registry.ts` — type-only
  (`ModuleSessionRegistry`); re-point to `@cassicore/workspace`.
- `vendor/core/intelligence/shared/posture-store.ts` — **runtime** faithful copy
  (`composeSystemPrompt`); re-point to `@cassicore/workspace`.
- `vendor/core/utils/activity-timeout.ts` — **runtime** faithful copy
  (`ActivityTimeout`); re-point to `@cassicore/utils`.
