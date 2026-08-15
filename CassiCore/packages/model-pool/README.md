# @cassicore/model-pool

The retained `ModelHandle` seam + acquire-shim for the focused mind. After the
CASSICORE-FOCUS P4 model-access cutover, the delegate `ModelPool` class (fallback
chains, budget scopes, provider map, capability cache, billing) and its test suite
are deleted. ohmypi owns provider routing/quota/fallback; this package is the mind's
**cast over an ohmypi completion** (`mind_complete` transport).

Depends only on `@cassicore/foundation` and `@cassicore/utils`.

## Surface

- `ModelHandle`, `ModelCompletionOpts`, `ModelCapabilities` (re-exported from
  `./ports`) — the retained handle contract helix / constellation / mini-helix inject.
- `ModelHandleImpl` — the retained completion runtime, `mind_complete`-backed.
- `ModelPool` (type) — the acquire-shim contract the mind injects via `setModelPool`.
- `createMindCompleteAcquirer({ logger, transport, defaultModel?, defaultCapabilities? })`
  — the host-facing factory that builds a `ModelPool`-shaped acquirer over an
  injected `mind_complete` transport.
- `MindCompleteTransport` / `ResolvedModel` / `defaultMindCompleteTransport` — the
  transport seam the spine's `mind_complete` bridge fulfils.

The pre-P4 `billing-models.ts` / vendored `CostClassifier` and the provider-SDK
"pulls no provider client SDKs" surface were removed with the pool machinery at P4.
