# Balance-Built Qi Spiral — Four-Arm Confirmation Pre-registration

## Status: Plan—pre-registered 2026-08-17, before any confirmation run

This protocol tests whether cadence steering can improve canonical balance, organize a phase-current proxy, or do both without merely adding field power. It follows the completed observability calibration in `balance_spiral_observability_prereg.md`. Nothing below is a measured confirmation result.

## 1. Fixed execution

- Scene: `scenes/mind_engine_cache.tscn`, $N=32$, `auto_step=false`.
- Seeds: `20260817`, `20260819`, `20260821`.
- Each arm begins with `clear`, the same 10-deposit IC generated for its seed, and one flush step.
- Eight intervals: $[1,2,3,4,7,11,18,29]$ steps.
- Steering occurs once before each interval and never per PDE step.
- Strength: 0.25. Per-interval total absolute charge is capped at 0.25.
- Deposit locations: the eight cells returned by `project k=8`; charge is divided equally among them.
- All arms use the same locations and cadence for a given seed.

## 2. Shared observables

Definitions and implementations are reused byte-for-byte from `tools/balance_spiral_observability.py`:

$$P=E_Y^2+E_I^2,\quad \rho=E_Y+E_I,\quad \varepsilon=E_Y-\varphi E_I,$$
$$q_{\rm coh}=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},$$
$$\mathbf J_{\rm proxy}=E_Y\nabla E_I-E_I\nabla E_Y.$$

The mechanism statistics are:

- balance: endpoint $\varepsilon_{\rm RMS}$ and its integrated sum across readouts;
- spiral: nonzero-mode $H_*$ and its integrated sum;
- current: $J_{\rm proxy,RMS}$, descriptive only;
- efficacy: localized field-power gain relative to control, normalized by injected absolute charge;
- stability: all arrays finite, maximum field power finite, no more than 100× the seed's baseline maximum, and canonical coherence remains in $[0,1]$.

Matched spatial-shuffle and Fourier phase-scramble controls are computed at every readout. A spiral mechanism passes only when live nonzero-mode $H_*$ exceeds both controls.

## 3. Frozen arms

### D—unchanged

No steering deposits after the IC.

### A—balance only

At each target cell, deposit the minimum capped correction in the direction that reduces local

$$\varepsilon=E_Y-\varphi E_I.$$

For $\varepsilon>0$, add Yin only; for $\varepsilon<0$, add Yang only. The unsigned requested correction is $0.25|\varepsilon|/(1+|\varepsilon|)$, divided across target cells and capped by the shared charge budget.

### B—spiral only

At each projected target cell, use the calibrated live winning axis/mode from the immediately preceding readout and deposit a small phase-patterned doublet:

$$c_Y=a\cos(2\pi m x_a/N),\qquad c_I=a\sin(2\pi m x_a/N),$$

with common amplitude scaled to the shared absolute-charge budget. The mode is measured from the current live field; no fixed physical pitch is claimed.

### C—combined

Use half the shared budget for A and half for B. No adaptive reweighting is allowed.

## 4. Anti-noise reference

For B and C, the same total charge is also scored against a deterministic phase-scrambled deposit pattern offline. It is not injected as a fifth live arm. If the live arm's helical improvement does not exceed the matched shuffled/scrambled field controls, the spiral mechanism is not supported.

## 5. Paired statistics

For seed $s$, define endpoint improvements relative to D:

$$I_A^{(s)}=\varepsilon_{{\rm RMS},D}^{\rm end}-\varepsilon_{{\rm RMS},A}^{\rm end},$$
$$I_B^{(s)}=H_{*,B}^{\rm end}-H_{*,D}^{\rm end},$$
$$I_{C,\varepsilon}^{(s)}=\varepsilon_{{\rm RMS},D}^{\rm end}-\varepsilon_{{\rm RMS},C}^{\rm end},$$
$$I_{C,H}^{(s)}=H_{*,C}^{\rm end}-H_{*,D}^{\rm end}.$$

Report every seed and paired median. With three frozen seeds, a mechanism has directional replication only if its improvement is positive in at least 2/3 seeds. This is a program decision rule, not a population-significance claim.

## 6. Decision tree

1. Protocol/shape/finite/identity failure → **INVALID**.
2. Stability violation → **UNSAFE/DIVERGENCE** for that arm.
3. Arm A: $I_A>0$ in fewer than 2/3 seeds → **BALANCE OBJECTIVE DOES NOT SUPPORT**; otherwise **BALANCE SUPPORTED**.
4. Arm B: $I_B>0$ in at least 2/3 seeds and endpoint live $H_*$ exceeds both controls in at least 2/3 seeds → **SPIRAL SUPPORTED**; positive $I_B$ without control separation → **NOISE-COMPATIBLE / MECHANISM NOT SUPPORTED**; otherwise **SPIRAL OBJECTIVE DOES NOT SUPPORT**.
5. Arm C: both $I_{C,\varepsilon}>0$ and $I_{C,H}>0$ in at least 2/3 seeds, with the same spiral control gate, → **BALANCE-BUILT QI SPIRAL SUPPORTED**. Otherwise **COMBINED OBJECTIVE DOES NOT SUPPORT**.
6. If an arm improves localized field-power efficacy but fails its mechanism gate → **GENERIC STEERING ONLY**.

No post-run changes to strength, cadence, seeds, budget split, target count, metrics, or decision rule are permitted.

## 7. Stopping rule

Every valid arm completes all eight intervals. Stop only on protocol failure, non-finite state, engine failure, or the frozen 100× field-power safety ceiling. Weak or adverse trends never permit early stopping.

## 8. Artifacts

- Runner: `tools/balance_spiral_confirmation.py`
- Raw result: `_diag/balance_spiral_confirmation.json`

## 9. Confirmation ledger

### Run 2026-08-17—three seeds, arms D/A/B/C

All twelve arms completed the eight frozen intervals without a protocol,
finite-value, or 100× field-power safety failure.

#### Arm A—balance only

Endpoint $\varepsilon_{\rm RMS}$ improvement relative to unchanged:

- seed 20260817: $+4.4798\times10^{-5}$
- seed 20260819: $+7.7199\times10^{-5}$
- seed 20260821: $+1.1612\times10^{-4}$

Directional replication is 3/3. Verdict: **BALANCE SUPPORTED**.

#### Arm B—spiral only

Endpoint $H_*$ improvement relative to unchanged:

- seed 20260817: $-0.0050135$
- seed 20260819: $-0.0011031$
- seed 20260821: $-0.0183067$

Directional replication is 0/3. Verdict:
**SPIRAL OBJECTIVE DOES NOT SUPPORT**. The phase-patterned deposits reduced
the measured helical order at every frozen seed despite live/control
separation in two seeds.

#### Arm C—combined

Endpoint balance improvements were positive in all three seeds:
$+1.4161\times10^{-5}$, $+1.5266\times10^{-4}$, and
$+9.5590\times10^{-5}$. Endpoint helical improvements were
$-0.0018376$, $+0.0023615$, and $-0.0122597$, so the joint criterion passed
only 1/3 seeds and that seed did not pass the live/control separation gate.
Verdict: **COMBINED OBJECTIVE DOES NOT SUPPORT**.

#### Program verdict

The tested balance correction is a reproducible steering direction. Directly
depositing the currently measured modal phase pattern does not build the Qi
spiral and weakens its order in this protocol. The combined arm inherits the
balance improvement but not the spiral mechanism. This wave therefore adopts
**balance as a steering constraint/objective** and rejects this direct
phase-pattern construction as the spiral objective. It does not reject Qi
phase-current as a diagnostic or a future emergent response.

Raw result: `_diag/balance_spiral_confirmation.json`.
