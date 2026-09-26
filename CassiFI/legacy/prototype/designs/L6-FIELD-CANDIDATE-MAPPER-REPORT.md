# CassiQwen L6 — Field Candidate Mapper Report

## Status: PASS—2026-08-18

## Protocol

This report executes `L6-FIELD-CANDIDATE-MAPPER-PREREG.md`. The implementation is the pure offline module `cassi-field-candidate-mapper.mjs`; verification is `cassi-field-candidate-mapper.test.mjs`.

No field engine, Qwen server, TCP connection, prompt, model weight, logit processor, sampler, or KV cache participated in the test run.

## Implementation boundary

The mapper is default-off. Disabled mode returns the original caller sequence unchanged without inspecting the projection.

Enabled mode validates non-empty unique candidate IDs and 1–8 finite cells with non-negative $q$. It reconstructs the L5d grid coordinates using the calibrated inverse vertex map, hashes `(gx, gy, gz, rank)`, accumulates each cell’s $q$ into one canonical candidate bucket, then returns candidates in descending accumulated score with original caller order as the tie-breaker.

The function labels its output as an ordering permutation. It makes no assertion that the resulting order denotes truth, factuality, relevance, safety, response quality, or a selected answer.

## Verification

The frozen contract suite completed with 6 passing tests and 0 failures:

| Check | Result |
|---|---|
| Disabled mode preserves caller order with malformed projection | `PASS` |
| Enabled output is a complete deterministic permutation | `PASS` |
| Score ties preserve caller order | `PASS` |
| Projection rank affects constructed fingerprint fixture | `PASS` |
| Invalid input and duplicate IDs fail closed | `PASS` |
| Recorded L5d projection maps offline without model/socket dependency | `PASS` |

## Terminal verdict

**PASS.** CassiQwen now has a deterministic, bounded, default-off transformation from an L5d-compatible top-$q$ projection to a candidate ordering. It remains disconnected from Qwen.

## Interpretation

- **T1 measured:** mapping behavior and six contract-test outcomes.
- **T2 inferred:** the mapper can serve as the single varied component of a future field-vs-baseline retrieval test.
- **T3 speculative:** that this arbitrary, geometry-derived permutation improves retrieval or language-model output. The next experiment must test that claim against a fixed baseline and may reject it.

## Next gated step

Pre-register a compact retrieval board with a fixed candidate set, a baseline ordering, fixed Qwen request format, exact task score, and this mapper as the only enabled-variable arm. The evaluation must include the default-off baseline and treat no gain or degradation as a terminal `REJECT` result for this mapping.
