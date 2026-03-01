# @cassicore/ai

Tightly integrated AI provider layer for CassiCore, forked from pi-ai.

## Overview

This module replaces CassiCore's custom provider implementations with a unified,
tightly integrated provider system based on pi-ai. It provides:

- **Unified API**: Single interface for all LLM providers (Anthropic, OpenAI, Google, etc.)
- **CassiCore Integration**: Direct compatibility with CassiCore's `IProvider` interface
- **Custom Providers**: Extended support for Kimi, Qwen, and OpenRouter
- **Type Safety**: Full TypeScript support with shared type definitions

## Structure

```
ai/
├── src/
│   ├── cassicore-compat.ts         # Main integration layer
│   ├── cassicore-types/            # CassiCore type definitions
│   │   ├── runtime.ts              # IProvider, Message, etc.
│   │   └── interfaces.ts           # ILogger, IConfig, etc.
│   ├── providers/
│   │   ├── anthropic.ts            # Anthropic provider (from pi-ai)
│   │   ├── openai-completions.ts   # OpenAI provider (from pi-ai)
│   │   ├── google*.ts              # Google providers (from pi-ai)
│   │   └── cassicore/              # CassiCore-specific providers
│   │       ├── kimi-coding.ts      # Moonshot Kimi models
│   │       ├── qwen.ts             # Alibaba Qwen models
│   │       └── openrouter.ts       # OpenRouter gateway
│   ├── types.ts                    # Core pi-ai types
│   └── index.ts                    # Public exports
├── dist/                           # Compiled output
├── package.json
└── tsconfig.json
```

## Usage

### In CassiCore

```typescript
import { createProviders } from '@cassicore/ai';

const providers = createProviders(config, logger);

// Use like any CassiCore provider
const provider = providers.get('kimi-coding/k2.5');
for await (const chunk of provider.complete(messages, opts)) {
  // Handle chunks
}
```

### Supported Providers

| Provider | Environment Variable | Models |
|----------|---------------------|--------|
| kimi-coding | `KIMI_API_KEY` | k2.5, k2.5-long, k2.5-vision |
| qwen | `QWEN_API_KEY` or `DASHSCOPE_API_KEY` | qwen3-coder-plus, qwen3-coder-flash, qwen3-vl-plus, qwen-max |
| openrouter | `OPENROUTER_API_KEY` | Various (Claude, GPT, Gemini, etc.) |
| anthropic | `ANTHROPIC_API_KEY` | Claude models |
| google-gemini-cli | `GEMINI_API_KEY` | Gemini models |
| openai-completions | `OPENAI_API_KEY` | GPT models |

## Architecture

### CassiCoreProviderAdapter

The `CassiCoreProviderAdapter` class bridges pi-ai's streaming API with CassiCore's `IProvider` interface:

- Converts CassiCore `Message` format to pi-ai `Context`
- Maps `CompletionOpts` to pi-ai `SimpleStreamOptions`
- Transforms pi-ai `AssistantMessageEvent` to CassiCore `CompletionChunk`
- Handles thinking levels, tool calls, and error events

### Type Mapping

| CassiCore | pi-ai |
|-----------|-------|
| `IProvider.complete()` | `streamSimple*()` functions |
| `Message` | `Context.messages` |
| `CompletionOpts` | `SimpleStreamOptions` |
| `CompletionChunk` | `AssistantMessageEvent` |
| `ThinkingLevel` | `ThinkingLevel` |

## Building

```bash
# Build ai module only
npm run build --workspace=ai

# Build all (ai + cassicore)
npm run build
```

## Future Work

- [ ] GitHub Copilot provider integration
- [ ] Qwen multi-account load balancer
- [ ] Provider health checking and failover
- [ ] Token counting per provider
- [ ] Cost tracking and optimization

## License

MIT (same as pi-ai)
