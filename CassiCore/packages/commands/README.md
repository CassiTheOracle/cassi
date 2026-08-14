# @cassicore/commands

The `CommandDispatcher` (`core/commands.ts`) and the command-module family
(`commands/`) extracted from CassiCore. History-preserved import splice.

## Surface

- `src/commands.ts` — the `CommandDispatcher` class (host instantiates)
- `src/commands/` — `index.ts` (barrel), `universal-processor.ts`, `cassi-commands.ts`,
  `cassicore-commands.ts`, `git-commands.ts`, `qwen-commands.ts`, `team-commands.ts`,
  `tool-commands.ts`

The dispatcher consumes `@cassicore/tools` (`InteractiveToolSession`,
`splitForTelegram`, `ExecutionResult`, `ToolDefinition`) plus the `IntelligenceLayer`
type.

## Vendored

- `src/vendor/core/model-routing/{index,model-directive}.ts` — faithful runtime copies
  of `core/model-routing/` (`ModelDirective` class) until a landed package owns the
  module (host-routing control); re-point to its home when it publishes.
- `src/vendor/core/intelligence/index.ts` — type-only vendor of the
  `core/intelligence/index.ts` `IntelligenceLayer` aggregate interface (commands.ts
  uses it for truthiness checks only); re-point to its canonical home when it publishes.

Depends on `@cassicore/foundation`, `@cassicore/events`, `@cassicore/tools`.

