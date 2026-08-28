# Qi-Native Field-Dependence Preregistration

## Status: FROZEN—2026-08-25

## Question

Does changing only the prompt-conditioned `QiFieldState [S,9M,B]` change the direct field emission decision, without a learned head, feature encoder, logits, or sampler?

## Frozen inputs

- Script: `measure_cassi_field_language_dependence.py`
- Script SHA-256: `b62a811e4cd31f35d671f29a7197d47ed4d5082de564329fc6c8a241a13a157d`
- Qi configuration: `cassi-qi-language.json`
- Configuration SHA-256: `04e78f7752bc7b1c4662b58fc54aae32bfc2f70e353edadd31a75355f07aac68`
- Prompt: one user message with exact content `Cassi field state counterfactual.`
- Maximum committed output symbols per arm: 16
- Device and dtype: CPU `torch.float32`

## Arms

1. `live`: the unmodified prompt-conditioned Qi state.
2. `qi_zeroed`: every value in the prompt-conditioned Qi state is replaced by zero.
3. `scale_phase`: the scale-0 Yang real/imaginary plane is rotated by exactly 1.0 radian while preserving its magnitude.

Every arm uses the same fixed codec and the same `QiFieldController.emit → sense_symbols → evolve → consolidate` loop. No output masking, resampling, retries, or parameter changes are permitted.

## Primary statistic

For each counterfactual, compare with `live`:

- the exact committed symbol sequence; and
- whether the field abstained.

State hashes, output-byte hashes, stop reasons, and receipt-chain hashes are diagnostic only. They do not change the primary verdict.

## Decision tree

- `FIELD_DEPENDENT` if at least one counterfactual changes the exact committed symbol sequence or the abstention status.
- `NULL_NO_SYMBOL_OR_ABSTENTION_CHANGE` otherwise.
- The run is invalid if a counterfactual does not change the initial Qi-state hash, any state becomes invalid/non-finite, an output lacks a field-owned receipt, or the artifact cannot be self-hashed canonically.

Neither verdict is a language-quality, semantic-competence, or consciousness claim.

## Stopping rule

Run the three frozen arms once. Do not tune the prompt, phase angle, Qi configuration, emission budget, or verdict rule after observing the output. A protocol or implementation failure may be fixed only by changing the preregistration status and freezing new source hashes before another run.

## Artifact

The run writes the self-hashed receipt to `_diag/qwen-displacement/qi-field-dependence.json`.
