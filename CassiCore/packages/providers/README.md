# @cassicore/providers

Model provider SDK clients extracted from CassiCore's `core/providers/`
(live set). History-preserved import splice. Excluded (DEAD): `claude-code-bridge/`
mjs hooks, `openai-compatible-base.js`, `pi-bridge.ts`, `qwen-coder.ts`; quarantined
(UNCERTAIN): `copilot-sdk/index.ts`, `hermes-bridge.ts`, `opencode-go.{js,ts}`.

## Surface

- `createModelRouter` / `getModelRouter` / `ModelRouter` — budget-aware routing (`model-router.ts`)
- `createBudgetTracker` / `getBudgetTracker` / `BudgetTracker` — provider budgets (`budget-tracker.ts`)
- `CostClassifier` / `getCostClassifier` / `DEFAULT_COST_RULES` — canonical home, resolves P6 Open-1 (`cost-classifier.ts`)
- `CentralizedProvider` / `wrapProvidersWithCentralized` — centralized wrap (`centralized.ts`)
- `ClaudeCodeProvider` — claude-code spawn (`claude-code.ts`)
- `GitHubCopilotProvider`, `GitHubCopilotLoadBalancer` (`github-copilot*.ts`)
- `GoogleAntigravityProvider` (`google-antigravity.ts`)
- `QwenLoadBalancer` / `createQwenLoadBalancer` (`qwen-loadbalancer.ts`)
- `RateLimitStore` (`rate-limit-store.ts`)
- `copilot-sdk/` — `client-manager`, `event-mapper`, `finished-tool`, `provider`,
  `tool-bridge`, `warm-provider-manager` (github-copilot-sdk integration)

Wraps `@github/copilot-sdk` internally and uses `better-sqlite3` for the rate-limit store.

## Vendored / deferred

- `src/vendor/ai/providers/cassicore/index.ts` — faithful **type** stub for the
  `ai/` provider SDK surface (`QwenProvider`, `AlibabaCodingProvider`, etc.). The whole
  `ai/` tree stays in `D:` until P8 `@cassicore/ai` — **P8-deferred**; re-point this
  vendor to `@cassicore/ai` and delete it at P8.

Depends on `@cassicore/foundation`, `@cassicore/events`, `@cassicore/utils`,
`@cassicore/tools`, `@cassicore/thalamus`.
