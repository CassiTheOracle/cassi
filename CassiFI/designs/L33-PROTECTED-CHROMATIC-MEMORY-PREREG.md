# L33 Protected Chromatic Memory — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L33 is frozen after preserving the complete canonical L32 `REJECT` and before any L33 module, test, runner, verifier, smoke, or canonical execution. Its protected-lane mechanism was specified as the second independent hypothesis before the L32 outcome; no L32 coefficient or behavior is imported. L30, L31, and L32 source files and artifacts remain immutable.

## Measured motivation and question

The sole unresolved inherited gate remains original-target long-horizon MRR `>= 0.05`. L31 measured `0.02615025059625695`; the independent L32 quadrature-only readout measured `0.022649159894934923`. L33 does not tune either profile. It tests one different hypothesis: the later deposit overwrites or dynamically exposes the same chromatic lane, so the previous deposit requires an energy-preserving protected lane inside the existing field tensor.

Question: does a fixed two-lane current/retained chromatic operator satisfy every inherited gate without any external or parallel adaptive state?

## Identities and files

New identities:

- layout: `cassi.qi-protected-chromatic-memory-lane.v1`;
- operator/readout: `cassi.qi-protected-chromatic-heartbeat.v1`;
- trace schema: `cassi.l33.protected-chromatic-traces.v1`;
- board schema: `cassi.l33.protected-chromatic-board.v1`;
- verifier schema: `cassi.l33.protected-chromatic-verification.v1`.

The unchanged L31 projection equation retains profile identity `cassi.qi-cyclic-chromatic-projection.v1` and reads the current `D` lane only.

New files:

- `cassi_protected_chromatic_field.py`;
- `tests/test_cassi_protected_chromatic_field.py`;
- `verification/run_l33_protected_chromatic_field.py`;
- `verification/verify_l33_protected_chromatic_field.py`.

L33 may import frozen L30/L31 modules and evidence helpers. Its board binds every directly executed source. It must not modify or overwrite an earlier profile or artifact.

## Sole changed mechanism: protected chromatic lane

The sole adaptive state remains `[7, 9*M, B]`. Active planes are reinterpreted under the new incompatible layout identity as

`C_re, C_im, D_re, D_im, VC_re, VC_im, M_re, M_im, epsilon2_ema`,

where `D` is the current chromatic lane and `M` is the retained chromatic lane. No tensor, cache, counter, history, learned weight, model, optimizer, or checkpoint sidecar is added.

### Input rotation

Immediately before the unchanged L31 white-carrier-to-chromatic unitary deposit, rotate `D` and `M` for each batch item using the already validated input trust `t`:

\[
\theta=\frac{\pi}{2}t,
\qquad
D'=\cos\theta\,D+\sin\theta\,M,
\qquad
M'=\cos\theta\,M-\sin\theta\,D.
\]

At trust zero this is identity. At trust one it moves the current lane into the retained lane without changing norm. The unchanged chromatic deposit then writes the new white-carrier direction into `D`; its paired common-velocity rotation acts on `M` under the new layout semantics. Reported input-energy drift is recomputed from the original pre-rotation state to the final bounded state.

### Protected evolution

Between deposits, `D` and `M` retain their complex patterns exactly except for a uniform field-energy bound when required. Only the common pair `C, VC` follows the frozen L31 damped nonlinear cyclic update:

\[
F_C=-\omega^2 C-\lambda(|C|^2+|D|^2)C
+\kappa(C_{s-1}+C_{s+1}-2C_s),
\]

followed by the unchanged velocity and position step. The epsilon EMA remains derived from the updated `C,D` Yang/Yin positions. Heartbeat, total-energy budget, direct native storage, inactive-mode zeros, codebook, channel phase, constants, and bounds remain unchanged.

### Readout

Define one fixed effective retrieval coordinate

\[
D_{eff}=D-\frac{1}{2}M.
\]

The sign compensates the full-trust protected-lane rotation, and the fixed gain `1/2` gives the current lane a preregistered 2:1 amplitude priority over retained memory. Apply the unchanged L31 position readout to `D_eff`. No quadrature-energy sum, temporal aggregation, learned gain, adaptive recency, exact integrator, or projection change is allowed.

The trace adds `task_read_effective_d` and `pre_read_effective_d` solely for independent readout reconstruction. They are evidence, not persistent state.

## Frozen board and gates

The canonical RX 7900 XTX float32 hardware contract, field dimensions, target/distractor symbols, read ticks, 8 evolution steps, 128-tick blank/stress schedules, artifact rules, mechanical gates, tolerances, and nine functional conditions are inherited verbatim from L31/L32.

Return `ADOPT` only if every mechanical gate passes and all functional conditions pass, including:

- exact pre-target accuracy `1.0`;
- tick-0 target accuracy `>= 0.875`;
- pre-distractor target MRR `>= 0.75`;
- tick-8 distractor accuracy `>= 0.75`;
- long distractor MRR `>= 0.25`;
- original-target long-horizon MRR `>= 0.05`;
- tick-0 white coherence `>= 0.90`;
- blank `max abs(D) <= 1e-6`;
- finite clamp-free bounded stress.

Return `REJECT` when mechanics pass and any functional gate fails. Return `FAIL` for evidence or mechanics and `INCOMPLETE` only for an interrupted/unavailable canonical board.

## Artifacts

Raw:

- `_diag/l33-protected-chromatic-field/l33-board.json`;
- `_diag/l33-protected-chromatic-field/l33-traces.npz`;
- `_diag/l33-protected-chromatic-field/l33-projection.png`.

Verification:

- `artifacts/l33-protected-chromatic-field/L33-PROTECTED-CHROMATIC-MEMORY-REPORT.md`;
- `artifacts/l33-protected-chromatic-field/l33-verification.json`.

All writes use temporary siblings and atomic replacement. JSON is finite canonical JSON; NPZ loads with `allow_pickle=False`; raw references are sibling basenames.

## Stopping rule

Small CPU implementation checks may repeat only until these frozen equations and evidence plumbing conform. They may not tune the `1/2` gain, rotation, dynamics, schedule, target set, or gates. Then execute one canonical RX 7900 XTX float32 board and one independent verifier. An infrastructure abort may retry only after repair with byte-identical bound sources. Preserve the first complete `ADOPT`, `REJECT`, or `FAIL`; any L33 operator change afterward requires a new profile and preregistration.

After preserving the complete L33 result, this rule permits the separately preregistered L34 exact-integrator experiment requested by the owner. L34 must start from frozen L31, not combine with or tune L32/L33.
