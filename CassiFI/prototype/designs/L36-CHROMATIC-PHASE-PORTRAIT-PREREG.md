# L36 Chromatic Phase Portrait — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L36 is frozen after preserving the L35 `CONTRADICTS` outcome and before any L36 module, test, runner, verifier, smoke, or canonical execution. It changes one read-only diagnostic mechanism. L31–L35 field laws, readouts, schedules, sources, and evidence remain immutable.

## Question

Can a phase-space portrait expose the four live cyclic coordinates without the pale common-intensity washout of the existing presentation projection, while remaining deterministic, bounded, field-owned, and exactly read-only?

L36 is diagnostic only. It cannot improve recall, alter a field profile, or turn hidden state difference into usable capacity.

## Identity and files

Projection identity: `cassi.qi-chromatic-phase-portrait.v1`.

Evidence identities:

- board: `cassi.l36.chromatic-phase-portrait-board.v1`;
- traces: `cassi.l36.chromatic-phase-portrait-traces.v1`;
- verification: `cassi.l36.chromatic-phase-portrait-verification.v1`.

New files:

- `cassi_chromatic_phase_portrait.py`;
- `tests/test_cassi_chromatic_phase_portrait.py`;
- `verification/run_l36_chromatic_phase_portrait.py`;
- `verification/verify_l36_chromatic_phase_portrait.py`.

## Sole changed mechanism: four-panel phase portrait

Read native L31 coordinates `(C,D,VC,VD)` without mutation. Collapse channels into the declared white carrier for `C,VC` and the first chromatic channel harmonic for `D,VD`. Select `panel_side^2` uniformly spaced active-mode indices and apply an orthonormal two-dimensional inverse FFT independently to the four collapsed spectra.

For every complex panel wave `z`, retain bounded diagnostics

- amplitude `a=|z|`;
- phase `theta=arg(z)` in `[-pi,pi]`;
- absolute panel peak `p=max(a)`.

Display brightness is `sqrt(a/max(p,tiny))`, with an exactly black panel when `p=0`. Hue is the smooth cyclic basis

`0.5 + 0.5*cos(2*pi*(theta/(2*pi) + (0,-1/3,+1/3)))`.

Multiply hue by brightness. Arrange the panels as `C | D` above `VC | VD`, separated by one black pixel. With `panel_side=16`, output is `[B,3,33,33]`. Display normalization is local to each panel; absolute peaks remain in the receipt so the image cannot be cited as relative-energy evidence.

No learned color map, running normalization, histogram state, lookup table, temporal aggregation, altered coordinate, altered readout, or field write is allowed.

## Focused checks

Before canonical execution, CPU checks must establish:

1. exact input-state immutability and deterministic repeatability;
2. shape, dtype, finite range `[0,1]`, phase range, and black separators;
3. coordinate isolation: a pure `C`, `D`, `VC`, or `VD` fixture activates only its corresponding panel peak;
4. multiplying a fixture by `i` preserves amplitude and rotates phase/color;
5. no model, optimizer, history, time counter, or adaptive normalization state exists.

Checks may repair conformance only; projection equations and thresholds stay frozen.

## Frozen canonical fixture and gates

Use the immutable L31 field at `mode_count=2048`, batch size 2, float32, trust 1.0, and eight steps per tick on the canonical RX 7900 XTX. The two L35 depth-2 histories are fixed as `(252,139)` and `(132,139)`.

Capture portraits after the distinct first symbols and after the shared tail. Preserve both states, portrait arrays, and a comparison PNG whose columns are histories and rows are before/after the shared tail. An independent NumPy oracle recomputes every collapsed spectrum, selected index, inverse FFT, amplitude, phase, peak, hue, and mosaic from the stored field tensors.

Mechanical gates require exact source/schema/hash/shape/device identity, finite arrays, RGB in `[0,1]`, phase in `[-pi,pi]`, black separators, unchanged source states, zero field clamps, maximum dynamic energy at most `1.05`, and maximum oracle absolute error at most `5e-5`.

Functional presentation gates require, across the four captured portraits:

- RGB global range at least `0.50`;
- minimum per-portrait RGB standard deviation at least `0.05`;
- at least one nonzero peak in each of `C,D,VC,VD` across the fixture.

Return `ADOPT` only if all mechanical and presentation gates pass, `REJECT` if mechanics pass but a presentation condition fails, `FAIL` for integrity/mechanics, and `INCOMPLETE` only for unavailable/interrupted canonical evidence. The after-tail paired image distance is reported but is not a gate.

## Artifacts and stopping rule

Raw:

- `_diag/l36-chromatic-phase-portrait/l36-board.json`;
- `_diag/l36-chromatic-phase-portrait/l36-traces.npz`;
- `_diag/l36-chromatic-phase-portrait/l36-comparison.png`.

Verification:

- `artifacts/l36-chromatic-phase-portrait/L36-CHROMATIC-PHASE-PORTRAIT-REPORT.md`;
- `artifacts/l36-chromatic-phase-portrait/l36-verification.json`.

Writes are atomic, JSON is finite canonical JSON, NPZ loads with `allow_pickle=False`, and raw references are sibling basenames. Small CPU runs may repair plumbing only. Then run one canonical GPU board and one independent verifier; preserve the first complete verdict. Any projection equation or fixture change requires a new preregistration.
