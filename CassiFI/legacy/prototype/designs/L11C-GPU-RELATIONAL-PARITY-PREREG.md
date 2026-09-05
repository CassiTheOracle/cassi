# CassiQwen L11c — Single-Engine GPU Relational Parity Successor Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Provenance and single lifecycle change

L11b reached engine initialization but closed `INVALID` because the probe called nonexistent `shutdown()` on the current engine source. L11c changes only lifecycle handling: it creates one engine node, reuses it for all four arms, calls the engine’s existing `_clear_field()` between arms, and frees the node after the receipt. No engine source or shader is changed.

The role positions, candidate features, relation relays, 16 steps, local-q readout, arms, decision tree, and one-launch stopping rule remain unchanged.

## Decision tree

- Parse/setup/readback/non-finite failure: `INVALID`.
- Aligned and shuffled answer/retrieve differences identical: `NULL`.
- Aligned differs from shuffled but equals channel-swapped: `NULL`.
- Aligned differs from both: `MECHANISM-DIFFERENCE`.

This measures only whether the unchanged GPU field state responds differently to the declared spatial controls. It does not establish action quality or authorize Qwen intervention.
