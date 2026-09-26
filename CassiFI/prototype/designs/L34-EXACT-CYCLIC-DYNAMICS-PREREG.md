# L34 Exact Cyclic Dynamics — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L34 is frozen after preserving the L33 mechanical `FAIL` and before any L34 module, test, runner, verifier, smoke, or canonical execution. Its exact-integrator mechanism was specified as the third independent hypothesis before the L32/L33 outcomes. L34 branches directly from immutable L31 and does not import their mechanisms. L30–L33 sources and artifacts remain immutable.

## Measured motivation and question

The sole unresolved inherited functional gate is original-target long-horizon MRR `>= 0.05`; L31 measured `0.02615025059625695`. L34 tests one hypothesis only: phase and amplitude error from the approximate damped oscillator step makes retained field structure less continuously readable. It does not claim that numerical dispersion is the cause.

Question: with L31 layout, heartbeat, modulation, position-only readout, cyclic topology, constants, state bounds, projection, schedules, and gates unchanged, does an exact linear cyclic transition with a fixed nonlinear Strang split satisfy every inherited condition?

## Identities and files

Unchanged identities:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New operator identity: `cassi.qi-exact-cyclic-strang.v1`.

Evidence identities:

- traces: `cassi.l34.exact-cyclic-traces.v1`;
- board: `cassi.l34.exact-cyclic-board.v1`;
- verification: `cassi.l34.exact-cyclic-verification.v1`.

New files:

- `cassi_exact_cyclic_field.py`;
- `tests/test_cassi_exact_cyclic_field.py`;
- `verification/run_l34_exact_cyclic_field.py`;
- `verification/verify_l34_exact_cyclic_field.py`.

L34 may import frozen L30/L31 modules and evidence helpers. Its board binds every directly executed source. Earlier sources and artifacts must not be edited or overwritten.

## Sole changed mechanism: exact linear transition

The adaptive state remains the L31 native tensor `[7, 9*M, B]` with coordinates `C,D,VC,VD,epsilon2_ema`. Heartbeat, symbol modulation, energy accounting, bounds, codebook, readout, projection, and epsilon target are unchanged.

For each evolution substep, apply a half nonlinear velocity kick in physical channel space:

\[
VC \leftarrow VC-\frac{dt}{2}\lambda(|C|^2+|D|^2)C,
\qquad
VD \leftarrow VD-\frac{dt}{2}\lambda(|C|^2+|D|^2)D.
\]

Transform the seven channels with an orthonormal DFT. For channel harmonic `k`, the reciprocal cyclic coupling gives

\[
\Omega_{km}^2=\omega_m^2+4\kappa_m\sin^2(\pi k/7),
\qquad
\gamma_m=\frac{base\_damping}{\tau_m}.
\]

Let `alpha = gamma/2`, `nu = sqrt(max(Omega^2-alpha^2,0))`, `c = cos(nu*dt)`, `s = sin(nu*dt)/nu` with the analytic `dt` limit at `nu=0`, and `e = exp(-alpha*dt)`. Apply the exact underdamped linear transition independently to both `(C,VC)` and `(D,VD)`:

\[
Z' = e[(c+\alpha s)Z+sV],
\qquad
V' = e[-\Omega^2 s Z+(c-\alpha s)V].
\]

Inverse-transform to physical channels, recompute `|C|^2+|D|^2`, and apply the second identical half nonlinear velocity kick. Then update epsilon and apply the unchanged bound. This is a fixed Strang split; no fitted coefficient, adaptive timestep, protected lane, quadrature readout, temporal aggregation, or projection change is allowed.

## Focused numerical checks

Before canonical execution, CPU tests must demonstrate:

1. the exact linear helper matches an independent closed-form harmonic calculation;
2. its FFT round trip preserves shape, dtype, and finite values;
3. heartbeat and pre-evolution modulation/readout remain identical to L31;
4. blank float32 evolution keeps native differential planes exactly zero;
5. long evolution remains finite, bounded, and clamp-free.

These checks may repair implementation errors only; they may not tune equations or constants.

## Frozen board and gates

Canonical hardware, float32 dtype, dimensions, targets, distractors, read ticks, 8 steps per tick, 128-tick blank/stress paths, artifact rules, independent recomputation, mechanical tolerances, and the nine inherited functional conditions are unchanged from L31/L32.

Return `ADOPT` only if all mechanics and all conditions pass, including original-target long-horizon MRR `>= 0.05`. Return `REJECT` when mechanics pass but any functional condition fails, `FAIL` for evidence/mechanics, and `INCOMPLETE` only for unavailable/interrupted canonical evidence.

## Artifacts

Raw:

- `_diag/l34-exact-cyclic-field/l34-board.json`;
- `_diag/l34-exact-cyclic-field/l34-traces.npz`;
- `_diag/l34-exact-cyclic-field/l34-projection.png`.

Verification:

- `artifacts/l34-exact-cyclic-field/L34-EXACT-CYCLIC-DYNAMICS-REPORT.md`;
- `artifacts/l34-exact-cyclic-field/l34-verification.json`.

Writes use temporary siblings and atomic replacement. JSON is finite canonical JSON; NPZ loads with `allow_pickle=False`; raw references are sibling basenames.

## Stopping rule

Repeat small CPU checks only until the frozen equations and evidence plumbing conform. Then run one canonical RX 7900 XTX float32 board and one independent verifier. An infrastructure abort may retry only after repair with byte-identical bound sources. Preserve the first complete `ADOPT`, `REJECT`, or `FAIL`; any L34 mechanism change requires a new profile and preregistration.

After preservation, further creative expansion must use separately preregistered held-out mechanisms. No result from L34 permits editing or tuning L31–L34 evidence.
