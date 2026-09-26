# LOCAL-MODEL L0 — llama-server Transport Pre-registration

**Phase:** L0 — local transport foundation.
**Type:** PRE-REGISTRATION + implementation brief.
**Date:** 2026-08-17
**Status:** FROZEN BEFORE IMPLEMENTATION.
**Source-of-truth inputs:**
- `LOCAL-MODEL-VISION-PLAN.md`
- `CASSICORE-FOCUS-PLAN.md` §2
- `recon-oh-mypi-capabilities.md` §2.5
- `packages/model-pool/DELEGATE-SURFACE.md`
- `packages/spine/src/tools/mind-complete.ts`
- `packages/spine/src/channel/client.ts`

**Goal:** Add the smallest dependency-free adapter from the existing spine-owned `mind_complete` transport to an unmodified OpenAI-compatible `llama-server`, while preserving the focused architecture and proving an exact field-free HTTP completion contract.

---

## 1. Frozen scope

Ohmypi already auto-discovers keyless `llama.cpp` at `127.0.0.1:8080`; ordinary agent sessions should use that built-in provider. L0 addresses the narrower retained-mind case: pure single-completion loops use the existing injected `mind_complete` transport, whose production raw-completion hook is not otherwise wired.

L0 adds one optional transport factory under `@cassicore/spine`, exports it from the spine surface, and covers its observable HTTP behavior. It does not:

- change the active runtime default;
- bypass ohmypi for ordinary agent turns;
- edit Cassi field behavior;
- add a provider registry or model-routing layer;
- add a new workspace package;
- restore `@cassicore/providers` or `@cassicore/ai`;
- change `@cassicore/model-pool` transport semantics;
- modify `@cassicore/mind-runtime`;
- launch, discover, download, or quantize a model;
- add streaming, tools, embeddings, logprobs, hidden-state access, or training;
- add automatic fallback to a remote provider.

The factory remains explicitly injected through `SpineOptions.mindCompleteTransport`. Runtime environment selection belongs to L1 because enabling a local model before a real GGUF receipt would change behavior without evidence.

---

## 2. Ownership decision

`@cassicore/spine` owns the adapter because:

1. `mind_complete` is the only retained provider-adjacent surface;
2. the spine already resolves models and invokes an injected completion transport;
3. the spine already uses Node's built-in `fetch` for loopback HTTP;
4. `@cassicore/mind-runtime` is host-agnostic and must not gain provider dependencies;
5. `@cassicore/model-pool` is a transport-agnostic retained cast, not a provider implementation;
6. ohmypi remains the default provider owner outside this explicit local raw-completion capability.

The new source file is `packages/spine/src/tools/llama-server-transport.ts`. The existing spine `MindCompleteTransport` type from `mind-complete.ts` remains canonical.

---

## 3. Frozen public interface

```ts
export interface LlamaServerTransportConfig {
  baseUrl?: string
  apiToken?: string
  timeoutMs?: number
  fetch?: typeof globalThis.fetch
}

export function createLlamaServerTransport(
  config?: LlamaServerTransportConfig,
): MindCompleteTransport
```

Defaults:

- `baseUrl`: `http://127.0.0.1:8080`
- `timeoutMs`: `120_000`
- `apiToken`: absent
- `fetch`: `globalThis.fetch`

The injectable `fetch` is for deterministic contract coverage and embedding hosts; no HTTP dependency is introduced.

---

## 4. Frozen request mapping

For each transport call, send exactly one non-streaming request:

```http
POST {baseUrl}/v1/chat/completions
Content-Type: application/json
Authorization: Bearer {apiToken}   # only when configured
```

Body:

```json
{
  "model": "<resolved.id>",
  "messages": [{ "role": "...", "content": "..." }],
  "stream": false,
  "temperature": 0.0
}
```

Rules:

1. `model` is the already resolved model ID supplied by `ctx.models.resolve`; the adapter does not parse or reroute provider/model specs.
2. `temperature` is included only when finite and provided.
3. `effort` is ignored in L0 because the OpenAI-compatible llama-server request has no stable cross-model equivalent. It must not be translated into an undocumented Qwen parameter.
4. Messages pass through without role rewriting.
5. No tools are sent in L0.
6. `stream` is always `false`.

---

## 5. Frozen response mapping

A successful response must contain:

```json
{
  "choices": [{ "message": { "content": "..." } }]
}
```

The transport returns the exact spine contract:

```ts
{
  content: choices[0].message.content,
  usage: response.usage,
}
```

Content must be a string. Empty string is valid; absent or non-string content is malformed. The usage object is preserved without reinterpretation.

---

## 6. Error and timeout contract

1. The configured timeout aborts the request.
2. Caller cancellation is not present in the existing spine `MindCompleteTransport` signature; adding it requires a separate retained-contract gate.
3. A non-2xx response throws an error containing the status code and a bounded response-body excerpt.
4. Invalid JSON throws an error identifying malformed llama-server JSON.
5. A JSON success body without string content throws an error identifying missing completion content.
6. Network errors throw with `llama-server request failed` context.
7. An abort throws a timeout-specific error including the configured duration.
8. No error triggers a remote fallback or fabricated content.

The response-body excerpt is capped at 512 characters to avoid injecting a large or sensitive server response into logs.

---

## 7. Pre-registered contract cases

The focused contract suite must exercise:

| Case | Expected observation |
|---|---|
| Minimal success | POST path, headers, resolved model, messages, `stream:false`, content/usage mapped |
| Temperature absent | property omitted |
| Temperature present | finite value passed unchanged |
| API token absent | Authorization header omitted |
| API token present | Bearer header present |
| Non-2xx | throws with status and bounded body |
| Malformed JSON | throws a malformed-JSON error |
| Missing content | throws a missing-content error |
| Timeout | request aborts and throws timeout error |
| URL normalization | one slash joins base URL and endpoint |
| Spine injection | `SpineOptions.mindCompleteTransport` executes the adapter after `ctx.models.resolve` |

No source-text assertions are permitted. Cases must exercise the transport as a caller would.

---

## 8. Gate statistic and decision tree

### Gate statistic

L0 is a binary contract gate over the eleven cases in §7, followed by package typecheck, package tests, the focus gate, and a loopback HTTP smoke using the real built JavaScript transport against a temporary local server.

### Decision tree

1. If source typecheck fails: **FAIL L0**. Correct the implementation without widening scope, then run the frozen gate again.
2. If any §7 contract case fails: **FAIL L0**. Correct only the mapped defect and rerun the unchanged suite.
3. If `npm run verify:focus` fails: **REJECT the location or dependency choice**. Do not weaken the focus gate.
4. If the temporary-server smoke does not observe a real HTTP request and mapped completion: **FAIL L0**.
5. If all checks pass: **PASS L0 transport foundation**. This licenses L1 model receipt; it does not license Cassi steering or production default changes.

### Stopping rule

One implementation pass and one full frozen verification pass. A defect correction reruns the same gate. No feature additions or threshold changes are allowed during L0.

---

## 9. Expected verification commands

From the CassiCore root:

```text
npm run typecheck --workspace=@cassicore/spine
npm run test --workspace=@cassicore/spine
npm run verify:focus
```

The loopback smoke uses the package's built JavaScript output and a temporary Node HTTP server. It must not require `llama-server` or a model; L1 owns the real-model receipt.

---

## 10. Follow-on boundary

L0 does not answer whether Qwen 27B runs well on this workstation or whether Cassi improves it. It proves only that the focused mind has a clean raw-completion path for an already-running local server. L1 pins the actual GGUF and backend. L2 adds bit-identical shadow field observation. Any active field influence requires a fresh pre-registration.

<!-- End of LOCAL-MODEL-LLAMA-SERVER-PREREG. Frozen before implementation. -->
