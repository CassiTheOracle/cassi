# @cassicore/ai

CassiCore's standalone AI provider layer (forked from pi-ai for tight
integration). Migrated (history-preserved) from the D: `ai/` npm package,
committed at cassicore `d63358da`.

## What lives here

The whole D: `ai/` tree — 46 tracked files — lands under `src/` with full
provenance:

| source (D:) | dest (here) | note |
|---|---|---|
| `ai/src/index.ts` | `src/index.ts` | package barrel (re-exports providers + oauth + models) |
| `ai/src/cli.ts` | `src/cli.ts` | CLI entry |
| `ai/src/models.generated.ts` | `src/models.generated.ts` | 325 KB auto-generated model registry (`MODELS`) |
| `ai/src/providers/*` | `src/providers/` | SDK provider clients (openai, anthropic, google, bedrock, gemini-cli, vertex, codex, completions, responses) |
| `ai/src/providers/cassicore/*` | `src/providers/cassicore/` | CassiCore-specific providers (opencode-go, qwen, alibaba, deepseek, kimi, openrouter, zai + openai-compatible base) |
| `ai/src/utils/*` | `src/utils/` | oauth flows, event-stream, http-proxy, overflow, validation, typebox helpers |
| `ai/src/cassicore-types/*` | `src/cassicore-types/` | shared local type layer |
| `ai/src/api-registry.ts` | `src/api-registry.ts` | API provider registry |
| `ai/src/env-api-keys.ts` | `src/env-api-keys.ts` | env key resolution |
| `ai/package.json` | `package.json` | own manifest (renamed to `@cassicore/ai`) |
| `ai/tsconfig.json` | `tsconfig.json` | NodeNext / strict |

The package keeps its **own package.json and tsconfig**; it is a full workspace
member so model-pool and providers can depend on it.

## Provider SDK surface

Exposes the CassiCore provider classes the daemon and providers package wire at
boot: `OpenCodeGoProvider`, `AlibabaCodingProvider`, `DeepSeekProvider`,
`KimiCodingProvider`, `OpenRouterProvider`, `ZaiProvider`, `QwenProvider`
(+ `QwenOAuthCredentials`, `QwenAccount`, `QwenLoadBalancer`), backed by
`OpenAICompatibleBase`.

`ai/src/providers/cassicore/{opencode-go,alibaba-coding,deepseek,kimi-coding,
openrouter,zai,qwen,openai-compatible-base}.ts` were deleted from the D: tree at
`4f06418d` (moved out of the ai path) leaving dangling re-exports; P8 restores
them **from the ai path's own imported history** (self-contained, no D:
`core/` deps) so the barrel resolves and the provider contract is real.
