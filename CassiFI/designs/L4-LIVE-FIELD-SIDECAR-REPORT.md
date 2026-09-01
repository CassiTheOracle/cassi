# CassiQwen L4 — Live Field Sidecar Receipt

## Status: PASS—2026-08-18

## Protocol

This report executes `L4-LIVE-FIELD-SIDECAR-PREREG.md` using the unchanged `CassiCosmos/scenes/mind_engine_cache.tscn` scene and the L3 read-only adapter.

## Startup receipt

The windowed Godot 4.7.1 Mono console process started successfully on the AMD Radeon RX 7900 XTX Vulkan device and emitted:

```text
[MindEngine] ready N=32 dt=0.0050 bridge=true port=7599
```

The managed process bound loopback port 7599. It was stopped after the one required observation.

## Single read-only observation

The L3 adapter sent exactly `ping`, `state`, and `project k=8`. It returned an available observation:

| Field | Measured value |
|---|---:|
| Field step | 0 |
| Field time | 0 |
| Mean Yang field (`meanEy`) | 0 |
| Mean Yin field (`meanEi`) | 0 |
| Maximum imbalance squared (`maxEps2`) | 0 |
| Projection cells | 8 |
| Finite projection values | yes |
| First projected `q` | 0 |
| Last projected `q` | 0 |

The zero-valued projection is the expected empty-field state for this scene: `auto_step=false` and the protocol did not clear, deposit into, or step the field. The top-k result is deterministically tied at zero and follows the engine’s flat-index order.

## Terminal verdict

**PASS.** The independently running windowed sidecar produced one bounded, finite, read-only projection through the CassiQwen adapter. The sidecar was then stopped as specified.

## Interpretation

- **T1 measured:** startup on the RX 7900 XTX Vulkan device; a live port-7599 observation containing eight finite cells; and the all-zero initial field state.
- **T2 inferred:** CassiQwen can acquire a live field observation without changing the model or writing to the solver.
- **T3 speculative:** that a field observation can improve any Qwen task. This protocol included no nonzero seed and no model call, so it cannot establish that claim.

## Next gated step

A meaningful shadow experiment needs an independently defined, reproducible nonzero field state. Because L4 deliberately prohibited mutable field commands, that requires a separate pre-registered scene or protocol before testing whether a projection-derived signal has any useful relationship to a local-model retrieval task.
