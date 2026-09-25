# CassiQwen Model Receipt

## Status: L1 PASS—2026-08-18

This directory holds the local language-cortex artifact for the Cassi integration program. The model remains an external, frozen language model during the transport and baseline stages; Cassi-specific intervention is disabled until its separately pre-registered shadow evaluation.

## Artifact identity

| Field | Value |
|---|---|
| GGUF path | `Qwen3.8-27B-Q4_K_M.gguf` |
| SHA-256 | `7e78da5d7e3ae28d178121f58646953305f3e5bd3cb46f4a75584e8b6c6fe169` |
| Size | 17,106,775,008 bytes |
| GGUF magic/version | `GGUF` / 3 |
| GGUF architecture | `qwen35` |
| GGUF name | `Qwen3.8-27B` |
| GGUF size label | `27B` |
| GGUF tensors | 866 |
| GGUF key-value entries | 51 |

The architecture field was read directly from the GGUF header. It is the compatibility identifier that the local llama.cpp receipt accepted.

## Runtime baseline

| Field | Value |
|---|---|
| Inference runtime | llama.cpp `0.1.1-dev`, build `10472`, commit `60eeeb608` |
| Package | `llama-b10472-bin-win-vulkan-x64.zip` |
| Package source | [official llama.cpp b10472 release](https://github.com/ggml-org/llama.cpp/releases/tag/b10472) |
| Backend target | Vulkan on the RX 7900 XTX |
| Server endpoint | `http://127.0.0.1:8080/v1` |
| Binding | loopback only (`127.0.0.1`) |
| Context / slots | 32,768 tokens / 1 |
| Requested GPU offload | all layers (`--gpu-layers 99`) |
| Launcher | `start-llama-server.ps1` |

The server loaded the `qwen35` GGUF and reported `model loaded` before binding `http://127.0.0.1:8080`. Its model API reported `n_vocab=248320`, `n_ctx=32768`, `n_ctx_train=262144`, `n_embd=5120`, and the model path as the server identifier.

The Vulkan package is installed and launched with full-offload requested. This L1 receipt verifies model loading and completion service, not the exact allocation or per-layer backend placement; that is a distinct performance receipt.

## Frozen L1 receipt protocol and result

| Check | Result |
|---|---|
| `GET /health` | `200`, `{"status":"ok"}` |
| `GET /v1/models` | `200`; model identifier is the absolute GGUF path |
| Completion endpoint | `POST /v1/chat/completions`, `200` |
| Prompt | `Reply with exactly: CASSI_LOCAL_READY` |
| Determinism controls | `temperature: 0`, `max_tokens: 16`, `stream: false`, `chat_template_kwargs.enable_thinking: false` |
| Returned content | `CASSI_LOCAL_READY` |
| Token usage | 21 prompt + 6 completion = 27 total |
| Prompt evaluation | 191.435 ms, 109.70 tokens/s |
| Generation evaluation | 123.728 ms, 40.41 tokens/s |
| End-to-end server timing | 315.16 ms |

**L1 verdict: PASS.** The local server loads the artifact, exposes the OpenAI-compatible completion endpoint over loopback only, and returns the frozen deterministic completion.

### Thinking-mode observation

The initial request without `chat_template_kwargs.enable_thinking: false` used its 16-token budget entirely in `reasoning_content` and returned an empty final `content`. This is expected behavior for a reasoning-capable template under a constrained output budget, not a transport failure. The Cassi runtime must explicitly choose a thinking policy per request and account for reasoning tokens in its budget.

## Non-goals of this receipt

- It does not measure answer quality or a sustained throughput benchmark.
- It does not measure actual VRAM allocation or prove the GPU offload result beyond the requested runtime configuration.
- It does not modify model weights, prompts, KV cache, or quantization.
- It does not attach the two-fluid field, MnemicField, or a steering loop.
- It does not make the loopback server remotely reachable.

## Next gated step

Pre-register and run a baseline performance receipt: cold/warm prompt throughput, generated-token throughput, VRAM allocation, and quality-controlled baseline tasks. Only then pre-register the first default-off Cassi shadow/reranking comparison.
