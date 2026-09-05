# CassiQwen L11 — GPU Relational Field Parity Probe Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Scope

This probe uses the unchanged CassiCosmos two-fluid GPU engine to measure whether spatially encoded candidate and relation deposits yield a candidate-local ordering difference from field-off and relation-shuffled controls. It is a mechanism probe, not an action-quality experiment, and it makes no Qwen call.

## Fixed field construction

A new isolated verification scene creates `cassi_mind_engine.gd` with `N=32`, `auto_step=false`, no TCP bridge, and one local RenderingDevice. It deposits seven L9 candidates at their fixed role coordinates with the fixed L10b `retrieve-1` features. Candidate channels use the exact L9 formulas.

It creates two additional relation relays at the midpoint between source and target:

- `retrieve → answer` resolve relay: $(c_Y,c_I)=(0.62,0.05)$;
- `retrieve → answer` block relay: $(c_Y,c_I)=(0.05,0.62)$.

The field evolves for exactly 16 steps. Candidate-local readout is the sum of $q=E_Y^2+E_I^2$ over the 3×3×3 TSC neighborhood centered on each candidate’s known scatter anchor.

## Arms

1. `field_off`: deposits candidates, no relation relays, zero PDE steps.
2. `relation_aligned`: deposits candidates and both fixed relation relays, 16 PDE steps.
3. `relation_shuffled`: identical candidate deposits and PDE steps, but both relays are moved to the `retrieve → stop` midpoint.
4. `channel_swapped`: same aligned geometry/steps, relay Yang/Yin amplitudes swapped.

## Measurements

For each arm record finite/bounded state, candidate-local $q$ for all seven roles, and the answer/retrieve local-$q$ difference.

## Decision tree

1. Engine/pipeline/readback/non-finite failure: `INVALID`.
2. If aligned and shuffled answer/retrieve differences are bit-identical: `NULL`; geometry relay has no detected effect.
3. If aligned differs from shuffled, but channel-swapped is identical to aligned: `NULL`; channel assignment has no detected effect.
4. If aligned differs from both controls: `MECHANISM-DIFFERENCE`; this establishes only a field-state difference, not action quality or a field advantage.

Exactly one windowed scene launch that runs all four arms internally and writes one JSON receipt. No retries, seed changes, added steps, or engine/shader changes.
