# L47 Absorbing Harmonic Age Shift — Frozen Preregistration

## Status: FROZEN CORRECTED — 2026-08-30; no implementation or run

This protocol is grounded in the CassiMind collaboration message `01a05460-cdca-7161-bcb8-c2664472b558`. CassiMind identified the Brain limitation as a missing bounded retirement boundary: L39 retains only a static current/predecessor relation, while L42 advances harmonic age cyclically and therefore wraps the oldest harmonic back into the newest slot. CassiMind proposed a field-local unilateral shift that advances recent content and discards the oldest harmonic without learned state, tuning, damping changes, or a new readout rule.

L47 freezes that causal probe before any L47 module, test, runner, verifier, smoke, or canonical execution. L30–L44 source and evidence remain immutable. In particular, `cassi_harmonic_age_field.py` and every L42 artifact are hash-bound inputs and must not be edited or regenerated.

## Correction provenance and dependencies

- `supersedes-before-run`: `designs/L45-ABSORBING-HARMONIC-AGE-SHIFT-PREREG.md`, current SHA-256 `32bc4e741e08205d8badc4b9d307b27cd0681274d5a384b2ed63cd2182f46a44`;
- `preserved-prior-hash`: the same invalid analytic protocol before its ownership-only clarification had SHA-256 `97f4af8843a37ed7abf3fc01d9c85ce925eeb72d65ccdfaf1ded7a6f6a236abc`;
- `L45-status`: `SUPERSEDED_BEFORE_RUN`; no L45 module, test, smoke, raw board, receipt, verdict, implementation ownership, or execution exists;
- `reason`: CassiMind reviews `01a0546b-4332-7136-b65d-00c5e4ea5ac0` and `01a0546b-bc11-7408-be57-c5e4684f096a` established that the frozen codebook-shaped common carrier multiplies the requested write direction and makes the gate “N occupies age zero” false even for a correct operator;
- `profile-cutover`: L47 uses new operator identity `cassi.qi-absorbing-harmonic-age-write.v2`; L45 v1 remains reserved and invalid;
- `depends-on`: L47 implementation ownership and execution remain blocked until the frozen L46 causal crossover has a complete receipt and CassiMind has reviewed its raw arrays.

L45 remains byte-for-byte unchanged as an invalid preimplementation contract. L47 changes only the analytic common carrier and the identities/evidence namespace required by that correction. The absorbing operator, differential harmonic sentinels, schedule, gates, tolerances, and stopping rule are otherwise carried forward unchanged.

## Question

Can a fixed absorbing channel-harmonic shift provide the Brain with an energy-nonexpansive retirement boundary that advances the six newest age coordinates, removes age six instead of wrapping it into age zero, accepts a new current symbol through the unchanged Givens modulation, and remains bounded and clamp-free through 128 writes?

This probe isolates field writing. It does not claim long-horizon retention under evolution. If L47 passes, evolution coupling requires a separate frozen experiment.

## Identities and files

Unchanged layout and projection:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`;
- shared codebook: unchanged L30/L31 fixed 260-symbol phase codebook.

New identities:

- operator: `cassi.qi-absorbing-harmonic-age-write.v2`;
- board: `cassi.l47.absorbing-harmonic-age-shift-board.v1`;
- traces: `cassi.l47.absorbing-harmonic-age-shift-traces.v1`;
- verification: `cassi.l47.absorbing-harmonic-age-shift-verification.v1`.

New files:

- `cassi_absorbing_harmonic_age_field.py`;
- `tests/test_l47_absorbing_harmonic_age_field.py`;
- `verification/run_l47_absorbing_harmonic_age_shift.py`;
- `verification/verify_l47_absorbing_harmonic_age_shift.py`.

Raw evidence:

- `_diag/l47-absorbing-harmonic-age-shift/l47-board.json`;
- `_diag/l47-absorbing-harmonic-age-shift/l47-traces.npz`.

Verification evidence:

- `artifacts/l47-absorbing-harmonic-age-shift/L47-ABSORBING-HARMONIC-AGE-SHIFT-REPORT.md`;
- `artifacts/l47-absorbing-harmonic-age-shift/l47-verification.json`.

The new profile is opt-in and default-off: no existing controller, runtime, training path, or verifier selects it. The unchanged L42 source remains the baseline. No L47 change may be made in `cassi_harmonic_age_field.py`.

## Ownership and integration

This CassiBrain session owns only the L47 preregistration, causal runner, source-independent verifier, and final evidence integration. Ownership of the new L47 operator module and focused implementation tests will be assigned after CassiMind reviews this frozen contract; no concurrent session may edit a file after that assignment.

All L42–L44 field modules, runners, verifiers, raw boards, reports, and receipts are immutable inputs. They may be read and hash-bound but never regenerated, edited, or relabeled by L47.

CassiMind reviews the raw L47 arrays, causal assumptions, and behavioral interpretation independently. CassiMind is not the formal verifier and does not supply verdict fields to the L47 receipt. The formal verifier is `verification/verify_l47_absorbing_harmonic_age_shift.py`; it reconstructs the operator and gates from raw evidence without importing L47 mathematics. This CassiBrain session is the sole integration lane and reconciles CassiMind's review with the formal receipt without changing either.

The ownership boundary changes no operator or evidence gate. The substantive L47 correction is limited to the wave-flat common carrier, recomputed analytic energy anchors, v2 operator profile, and L47 evidence namespace declared above.

## Frozen field operator

The adaptive state remains the native tensor `[7,9M,B]`. For channel index `j=0,...,6`, define

\[
p_j=\exp(2\pi i j/7).
\]

For either differential position `D` or differential velocity `VD`, define the orthonormal channel DFT

\[
z_k=\frac{1}{\sqrt 7}\sum_{j=0}^{6}p_j^{-k}D_j,
\qquad k=0,\ldots,6.
\]

Age `a=0,...,6` uses physical harmonic

\[
k_a=(a+1)\bmod 7,
\]

so age zero is harmonic one and age six is harmonic zero. The absorbing age shift is

\[
z'_{k_0}=0,
\qquad
z'_{k_{a+1}}=z_{k_a}\quad(a=0,\ldots,5).
\]

Thus physical harmonics map

\[
1\to2,\ 2\to3,\ 3\to4,\ 4\to5,\ 5\to6,\ 6\to0,
\]

while old harmonic zero is discarded rather than mapped to harmonic one.

The implementation must use the equivalent minimum native-coordinate form

\[
P(D)_j=p_j\left(D_j-\frac1{7}\sum_{r=0}^{6}D_r\right),
\]

and the same equation for `VD`. `C`, `VC`, epsilon, inactive packed coordinates, the codebook, heartbeat, bounds, and every solver equation remain unchanged. Explicit DFT matrices, learned weights, time counters, history buffers, protected lanes, and fitted coefficients are prohibited.

`P` is an orthogonal projection followed by a unitary phase multiplication. Therefore

\[
\|P(D)\|_2\le\|D\|_2,
\]

and the predicted removed energy is exactly the energy of physical harmonic zero in `D` and `VD`. `P` is not componentwise nonexpansive in the maximum norm; L47 must therefore measure the immutable amplitude bound directly and may not call a clamp to conceal an overshoot.

The operator runs exactly once immediately before an actual symbol modulation. The unchanged cyclic controller's Givens modulation is then called directly so the L42 cyclic lift is not applied a second time. The cleared physical harmonic one is the new age-zero slot. No-symbol calls do not apply `P` and must remain bit-identical to the unchanged L42 no-symbol path.

## Frozen deterministic state

Canonical execution uses the RX 7900 XTX through PyTorch/ROCm, float32, `mode_count=2048`, `alphabet_size=260`, batch size eight, trust `1`, seven channels, and the unchanged L42 constants.

Let

`B = (0, 37, 74, 111, 148, 185, 222, 259)`.

For every batch row, define symbol vectors modulo 260:

- age zero: `Q0 = B + 0`;
- age one: `Q1 = B + 53`;
- age two: `Q2 = B + 97`;
- age three: `Q3 = B + 149`;
- age six: `Q6 = B + 223`;
- new deposit: `N = B + 181`.

All six symbols are distinct within every row.

Construct one analytic field state in harmonic coordinates. For the fixed codebook vector `u_s`, set differential coefficients

\[
z^D_{k_a}=A_a u_{Q_a},
\qquad
z^{VD}_{k_a}=\frac{iA_a}{2}u_{Q_a},
\]

for ages `a in {0,1,2,3,6}`, with

\[
(A_0,A_1,A_2,A_3,A_6)=(0.08,0.07,0.06,0.05,0.09).
\]

All other differential harmonics are exact zero. Construct `D` and `VD` by the orthonormal inverse DFT. Keep those differential sentinels unchanged from L45.

Let the unchanged normalized channel-white vector be

\[
w_j=1/\sqrt7,
\]

let `1_W` be the wave-flat complex vector of 1024 ones, and freeze the uniform complex carrier scalars

\[
c=0.02+0i,\qquad v=0+0.01i.
\]

For every active wave mode and batch row, set

\[
C_{j,:,b}=w_j c\,\mathbf 1_W,\qquad
VC_{j,:,b}=w_j v\,\mathbf 1_W.
\]

The unchanged common-carrier projection therefore returns exactly `c*1_W` and `v*1_W`. Under the unchanged trust-one Givens write, the cleared age-zero differential direction is consequently proportional to `u_N` rather than `u_N*u_(B+17)`; the frozen “N occupies age zero” gate is now structurally valid.

With `phi=(1+sqrt(5))/2`, the independently reconstructed analytic mean dynamic-energy anchors per batch row are

\[
E_{common}=\frac{|c|^2+|v|^2}{7(1+\phi^2)}
=1.9742371589287215\times10^{-5},
\]

\[
E_{differential}=\frac{1.25\sum_{a\in\{0,1,2,3,6\}}A_a^2}{7(1+\phi^2)}
=0.00125857618881706,
\]

and
\[
E_{total}=E_{common}+E_{differential}
=0.0012783185604063473.
\]

Epsilon is excluded from this declared dynamic energy. Set active epsilon coordinates to the deterministic nonzero sentinel `1e-4*(j+1)/7`. Inactive packed coordinates remain exact zero.

The runner records the canonical pre-state field SHA-256. Every fork must begin from a byte-identical clone with the same SHA-256, shape, dtype, device, and profile. No fork may change the symbol vector, codebook, trust, or checkpoint.

## Causal fork

### Fork 1: operator-only

From byte-identical clones of the analytic state:

- branch `I` applies exact identity/off;
- branch `P` applies exactly one absorbing age shift;
- neither branch performs heartbeat, deposit, bound, evolution, or readout before raw coordinates are captured.

The expected `P` coordinates are computed from the frozen native equation above before execution. The runner stores pre-state, both post-states, all active coordinates, DFT coefficients, dynamic energies, predicted removed energy, maximum amplitudes, and inactive tails.

### Fork 2: one write

Start again from fresh byte-identical clones of the same analytic state. Both branches use the identical deposit vector `N`, trust `1`, codebook, and checkpoint:

- branch `cyclic-write` performs the unchanged L42 cyclic lift followed by the unchanged Givens modulation;
- branch `absorbing-write` performs `P` followed by that same Givens modulation.

There is no heartbeat or evolution in this fork. Capture the post-shift state before modulation and the post-modulation state. This makes symbol/codebook and checkpoint divergence impossible explanations for a branch difference.

### Fork 3: 128-write retirement stress

Start both branches from byte-identical blank states. For write index `t=0,...,127`, use the identical symbol vector

\[
X_t[b]=(B[b]+37t)\bmod260.
\]

Every write consists of one unchanged heartbeat followed by modulation, with no evolution. The control uses the unchanged L42 cyclic lift; the intervention uses `P`. The two branches have identical initial state hashes and identical symbols at every write; their later state hashes are recorded but are expected to diverge because their operators differ. Record every symbol vector, post-heartbeat, post-shift, and post-write harmonic coefficient, readout, heartbeat receipt, modulation drift, clamp count, dynamic energy, maximum amplitude, and per-branch state hash.

After write 63, atomically serialize only the intervention `QiFieldState.field` tensor plus the frozen layout/operator/config identities, reload it into a fresh L47 controller, and continue writes 64–127. An uninterrupted intervention branch runs beside it. Reloaded and uninterrupted fields, native coefficients, readouts, and receipts must remain byte-identical after every remaining write. The serialized checkpoint is evidence only, never parallel adaptive state.

## Focused controls

Before any evidence run, CPU float64 contracts must establish:

1. branch `I` returns a byte-identical state and does not allocate or retain adaptive state;
2. direct DFT construction followed by inverse DFT reconstructs the analytic state within `2e-12`;
3. one `P` application equals the frozen native-coordinate equation, moves ages zero through five forward, clears age zero, removes age six, and leaves off-slot leakage below `2e-12`;
4. seven successive `P` applications reduce `D` and `VD` to zero within `2e-12`;
5. observed energy loss equals the independently reconstructed discarded harmonic-zero energy within `2e-12` and energy never increases;
6. nonzero `C`, `VC`, and epsilon sentinels and inactive packed coordinates remain bit-identical;
7. the no-symbol path is bit-identical to unchanged L42 for eight blank evolution steps and performs no absorbing shift;
8. cyclic and absorbing one-write branches start from byte-identical fields and use the same `N`, trust, and codebook;
9. one absorbing write places `N` in age zero and moves `Q0` to age one without a `Q6` wrap contribution;
10. serialization into a fresh controller returns a byte-identical field and rejects a mismatched profile;
11. no model, optimizer, learned embedding, counter, history buffer, parallel policy, or auxiliary adaptive state exists;
12. focused verifier mutations reject a changed clone hash, symbol vector, native coordinate, removed-energy record, inactive tail, clamp count, and resume field.

## Frozen reconstruction and tolerances

The independent verifier must not import L47 operator or readout mathematics. It reconstructs the DFT, `P`, inverse DFT, Givens write expectations, energies, codebook coefficients, availability, and winners from raw arrays.

Focused CPU float64 controls use zero relative tolerance and absolute tolerance `2e-12` for transformed differential coordinates, inverse reconstruction, off-slot leakage, predicted energy loss, and repeated absorbing-shift checks. Exact identity and untouched-plane checks remain bitwise.

Canonical float32 checks use:

- native coordinate, DFT, inverse-DFT, and energy reconstruction: `atol=3e-6`, `rtol=3e-6`;
- codebook/readout score reconstruction: `atol=3e-5`, `rtol=2e-4`;
- maximum per-write modulation energy drift: `2e-6`;
- maximum total mean dynamic energy: `1.05`;
- active component amplitude: at most the immutable `8.0` bound;
- epsilon: within `[0,4096]`;
- inactive packed coordinates: exact zero;
- all clamp counts: exact zero.

Availability is reconstructed before winner comparison. Winners are compared only where availability is true; unavailable winner indices have no semantic meaning. These tolerances are frozen before implementation and may not be widened after any run.

## Mechanical gates

The independent verifier must establish:

1. preregistration, source, schema, board, trace, and checkpoint hashes match;
2. execution used a real AMD ROCm GPU and float32;
3. all required arrays have frozen shape and dtype and contain finite values;
4. both branches of the operator-only and one-write forks begin from byte-identical field clones and use the identical frozen symbol vector; the stress branches share an identical initial field and use identical symbol vectors at every write;
5. branch `I` is byte-identical to the analytic pre-state;
6. `P` changes only `D` and `VD`; `C`, `VC`, epsilon, inactive tails, and profile identities are exact;
7. independent native-coordinate and inverse-DFT reconstructions match within the frozen tolerances;
8. observed energy after `P` equals pre-energy minus independently reconstructed harmonic-zero energy within tolerance and never exceeds pre-energy beyond tolerance;
9. `P` does not hide an amplitude overshoot behind a bound or clamp;
10. the unchanged Givens write reconstructs independently and every input-energy drift is within `2e-6`;
11. readout does not mutate any field;
12. the 64-write save/reload continuation is byte-identical to uninterrupted execution;
13. all active values obey immutable amplitude/epsilon/energy bounds, all inactive modes remain zero, and all clamp counts are zero.

Any mechanical failure returns `FAIL`; it is not a functional rejection.

## Functional gates

Every row must pass; averaging may not hide a failed row.

1. In the operator-only fork, ages zero through three move exactly to ages one through four.
2. The original age-six coefficient is removed and does not appear in the new age-zero harmonic.
3. The new age-zero harmonic is zero before a deposit.
4. The intervention's differential-plus-velocity energy is nonincreasing and loses exactly the independently reconstructed age-six energy.
5. After `absorbing-write`, `N` occupies age zero and the original `Q0` occupies age one.
6. The original `Q6` contribution is absent from every post-shift harmonic; the cyclic control demonstrates its wrap into age zero before the same deposit.
7. During all 128 intervention writes, the newest available age winners equal `[X_t,X_(t-1),...,X_(t-min(t,6))]` in order.
8. For `t>=6`, exactly seven age slots are available and no symbol older than `X_(t-6)` occupies an age slot.
9. Immediately after `P` and before each new deposit, physical harmonic one—the cleared new age-zero slot—is below the frozen availability floor, the pre-shift age-six coefficient is absent from the independently reconstructed post-shift field, and physical harmonic zero contains the advanced pre-shift age-five coefficient rather than the evicted age-six coefficient.
10. The intervention remains finite, within energy and amplitude bounds, clamp-free, and save/reload identical through write 127.

The public readout is checked independently but cannot conceal native-coordinate failure. Diagnostic causal classification is:

- `OPERATOR_FAILURE` if the operator-only native gates fail;
- `DEPOSIT_COUPLING_FAILURE` if the operator-only gates pass but the one-write gates fail;
- `READOUT_FAILURE` if native coefficients pass while availability-qualified public readout differs;
- `RETIREMENT_STRESS_FAILURE` if the one-write gates pass but any 128-write retirement gate fails;
- `SUPPORTED` only if every native, write, readout, stress, and persistence gate passes.

## Decision and stopping rule

Return:

- `ADOPT` only when all mechanical and functional gates pass and causal classification is `SUPPORTED`;
- `REJECT` when mechanics pass but one or more functional gates fail;
- `FAIL` for integrity, independence, reconstruction, source-binding, schema, nonfinite, tolerance, clone, persistence, bound, or clamp failure;
- `INCOMPLETE` only when canonical evidence is interrupted or unavailable.

`ADOPT` authorizes the absorbing operator as the Brain's bounded write/retirement primitive for a separately preregistered evolution-coupling experiment. It does not replace the live Mind runtime or establish long-horizon working memory by itself.

Run focused CPU contracts, syntax checks, and one disposable CPU smoke. Delete smoke artifacts. Then run exactly one canonical RX 7900 XTX board and one independent verifier. Preserve the first complete board and receipt. Stop after the first complete verdict. Any change to the operator, analytic state, symbols, amplitudes, schedule, heartbeat/write ordering, save/reload boundary, gates, thresholds, tolerances, or source dependencies requires a new preregistration and profile identity.
