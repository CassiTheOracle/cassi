# CassiQwen L11b — Typed GPU Relational Parity Successor Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Provenance and single change

L11 closed `INVALID` before engine construction because GDScript could not infer the local `invalid` expression type. L11b changes only that declaration to:

```gdscript
var invalid: bool = ...
```

The scene, engine, deposits, role coordinates, relation relays, four arms, 16-step evolution, local-q measurement, decision tree, and one-launch stopping rule remain exactly those frozen in `L11-GPU-RELATIONAL-PARITY-PREREG.md`.

## Decision tree

- Parse/setup/readback/non-finite failure: `INVALID`.
- Aligned and shuffled difference identical: `NULL`.
- Aligned differs from shuffled but equals channel-swapped: `NULL`.
- Aligned differs from both: `MECHANISM-DIFFERENCE`.

This successor is a GPU field-state mechanism measurement only. It does not establish action-quality improvement or authorize Qwen intervention.
