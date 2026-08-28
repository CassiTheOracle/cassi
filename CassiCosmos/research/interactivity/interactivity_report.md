# Interactive Field Workbench—vertical-slice report

## Status: Implemented and focused-gate verified—August 2026

## 1. Delivered surface

CassiCosmos now contains a first Interactive Field Workbench vertical slice. It provides a deterministic paused-state command layer, a dedicated Workbench operator-rail page, selected-region measurements, and versioned scenario save/replay.

The delivered controls are:

- Pause / Resume;
- one explicit physics step;
- spherical world-space region center and radius;
- balanced Yang/Yin field deposit;
- coherence alignment toward $E_Y=\phi E_I$;
- directional particle impulse;
- selected-region measurement;
- Qi, balance, density, and flow lens selection;
- command status and ordered ledger;
- scenario save and replay at `user://workbench_scenario.json`.

Selecting a tool or lens does not mutate simulation state. Apply is explicit and paused-only. Decoupled-worker mutation is rejected because the local RenderingDevice belongs to the worker thread.

## 2. Implementation map

| Artifact | Role |
|---|---|
| `scripts/field_workbench.gd` | Deterministic command queue, operations, measurements, accounting, baseline capture, checksum-protected scenario replay |
| `scripts/cassi_sim.gd` | Public workbench transport and operation API over canonical simulator state |
| `scripts/sim_ui.gd` | Fourth operator-rail Workbench page and controls |
| `scripts/verify_field_workbench.gd` | Focused G0–G7 verification arm |
| `scenes/verify_field_workbench.tscn` | Windowed GPU fixture |
| `research/interactivity/interactivity_prereg.md` | Frozen statistics, gates, decision tree, and stopping rule |
| `research/interactivity/interactivity_design.md` | Command, state-machine, UI, scenario, and next-stage design |

## 3. Focused verification result

The frozen focused arm ran windowed on the RX 7900 XTX with fixed seed 1729, a $64^3$ grid, eight particles, inline/global-RD ownership, and paused operations.

Final result:

```text
PASS G0: paused initial state
PASS G0: operation rejected while playing
PASS G0: paused operation accepted
PASS G1: deposit
PASS G2: align
PASS G3: impulse
PASS G4: command order and sequential ids
PASS G5: versioned scenario save/replay exactness
PASS G6: paused explicit single-step
PASS G6: pause/resume seam
PASS G7: no-op identity
PASS G7: selected readout/lens formulas
[Workbench] 12 checks, 0 failures
```

Scenario save and replay produced the same SHA-256 digest:

```text
9faab796625cc61c62aec340a5d2fd8b8b84c27dec5caa4067c4c9fd965904d0
```

The focused result therefore reaches **ADOPT VERTICAL SLICE** under the pre-registered decision tree.

## 4. UI smoke result

`scenes/validate_sim_ui.tscn` completed:

```text
RESULT: 9/9 checks passed, 0 failed
```

The first smoke exposed and repaired two integration defects: a status-label type mismatch and two missing pre-existing RealSim parameter registry entries. The rerun contained no script errors.

## 5. Regression-battery result

The existing 33-arm battery was launched once. It did not complete within the 20-minute harness limit. Through arm 17 it produced a mixed result: five arms passed and twelve failed or timed out.

Passed arms observed before timeout:

- `verify_fft`;
- `validate_sim_ui`;
- `verify_survey`;
- `verify_volumetric`;
- `verify_meshless_gravity`.

The failures were not localized to the new workbench. They included pre-existing battery/fixture defects:

- four arms classified as headless attempted a local RenderingDevice and immediately instructed the runner to use a windowed launch;
- `verify_gravity_modes`, `verify_meshless_sim`, `verify_meshless_stability`, and `verify_particle_vfx` exposed unrelated engine/fixture errors or missing symbols;
- several arms timed out or failed during decoupled-engine shutdown.

Because the full battery did not finish green, the report does not claim whole-simulator regression clearance. The focused command, replay, transport, measurement, default no-op, and UI contracts are verified; broader CassiCosmos battery health remains an independent repository concern.

## 6. Current boundaries

The vertical slice deliberately does not include:

- a viewport raycast or visible spherical brush cursor;
- continuous painting while the solver runs;
- decoupled-worker field mutation;
- timeline checkpoints or counterfactual branches;
- editable procedural initial-condition stacks;
- presentation storyboards or sonification;
- cross-version scenario migration;
- human-mechanism claims.

Human-experience presentation remains an interpretive layer over measured field behavior. It is not evidence that the demonstrated field equation is a biological or psychological mechanism.

## 7. Next frontier

The next stage should preserve this operation and provenance layer while replacing numeric-only placement with direct spatial interaction:

1. add a viewport raycast and visible spherical cursor;
2. add GPU-native bounded kernels so drag strokes do not require full-buffer readback;
3. add checkpoints and active/control branching;
4. add editable initial-condition operation stacks, including rings, vortices, shells, filaments, and $\phi$-cascade primitives;
5. add synchronized difference lenses and fixed-scale comparisons;
6. add guided concept scenarios such as “Energy is not coherence,” with explicit simulation/interpretation labels.

Those stages require new frozen protocols. The current vertical slice supplies their stable command, ledger, measurement, and scenario foundation.
