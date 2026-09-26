# Passive common-lapse process-time pre-registration

Date: 2026-08-27  
Owner: Carina  
Status: PRE-REGISTERED (frozen before the verification scene)  
Series: process-time / common-lapse campaign

## 1. Scope and epistemic boundary

This pre-registration defines one **passive CPU implementation lab**. It compares a
canonical conversion-flow age with two independently calibrated non-conversion
clocks while coordinate time remains the integration ground truth. The scene is
`scenes/verify_process_clock.tscn`; its only script is
`scripts/verify_process_clock.gd`.

A passing run means only that the stated scalar reparameterization and cross-clock
contracts are implemented by this deterministic lab. It is **not evidence for a
universal physical time**, a physical common lapse, or a claim that all sectors of
the production simulation must share one clock. The universal normalized lapse

$$
N_q=\frac{1-q}{1-q_{\rm ref}}
$$

is a hypothesis/diagnostic here, never an established physical time.

The arm is deliberately passive:

- no production shader, engine, simulation, or buffer is imported or changed;
- no GPU, RenderingDevice, shader compilation, or readback is required;
- `dt` is coordinate time and is authoritative for every update;
- the frozen local source schedule cannot receive feedback from any arm;
- the raw JSON receipt is written only under `res://_diag/process_time/`.

## 2. Frozen constitutive source and reference gauge

The lab uses the explicit bounded local constitutive source

$$
q_{\rm lab}(\rho,\varepsilon)
 = \frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},
\qquad
K=1-q_{\rm lab}
 = \frac{\varphi^{-2}+\varepsilon^2}
        {\rho^2+\varphi^{-2}+\varepsilon^2}.
$$

Here $\varphi=1.618033988749895$, so $\varphi^{-2}=0.3819660112501051$.
The denominator is strictly positive for the frozen trajectories below, hence
$0<q_{\rm lab}<1$ and $K>0$ are expected. This $q_{\rm lab}$ is a lab variable,
not a reinterpretation of the production buffer: production CassiCosmos `q` is
raw $EY^2+EI^2$ and is not bounded or relabeled by this arm.

The reference is frozen to the open-gate gauge

$$
q_{\rm ref}=0,\qquad 1-q_{\rm ref}=1.
$$

The generator scalar used by the shared arm is therefore

$$
N_q=\frac{K}{1-q_{\rm ref}}=K.
$$

The receipt still reports both `n_q = K/(1-q_ref)` and
`tau_F/(1-q_ref)`. Those are explicit relative-reference diagnostics: because
$q_{\rm ref}$ is fixed, they are a constant rescaling of the raw values and are
not a different dynamical clock and cannot improve a gate.

`q` is **recomputed** at each coordinate-time midpoint from the frozen
$\rho(t),\varepsilon(t)$ functions. It is not frozen to one scalar for a run,
and it is not recomputed from any arm state. The canonical conversion identity
is applied at every such midpoint:

$$
d\tau_F=K\,dt=(1-q)\,dt.
$$

## 3. Frozen trajectories and stopping rule

Two source trajectories are fixed before execution:

| trajectory | $\rho(t)$ | $\varepsilon(t)$ |
|---|---|---|
| A | $0.75+0.08\sin(0.31t+0.20)$ | $0.09+0.01\cos(0.27t-0.10)$ |
| B | $1.30+0.10\cos(0.23t-0.40)$ | $0.15+0.02\sin(0.19t+0.70)$ |

The ranges keep both inputs positive and keep $q$ bounded away from both
singular endpoints. They are intentionally different, so equal conversion age
must not be confused with equal coordinate time or equal source state.

Numerical constants are frozen:

- coordinate step $dt=0.005$;
- target conversion age $\tau_F^*=4.0$;
- maximum 10,000 steps per arm/trajectory;
- midpoint evaluation for $q$, with one final fractional step when the target is
  crossed;
- phase generator $\omega=1.75$;
- translation generator speed $v=0.85$.

Each arm stops exactly at the first target crossing (using the final fractional
coordinate step). A non-finite value, non-positive $K$, or failure to reach the
target within the fixed maximum is an immediate failure for that run. There are
no adaptive retries, alternate thresholds, trajectory selection, or post-hoc
rescaling to rescue a failing arm.

## 4. Three frozen arms

The conversion clock is integrated in all arms as

$$
\tau_F\leftarrow\tau_F+K\,dt.
$$

The two non-conversion observables are complete first-order generators, not
post-processed clocks:

$$
\frac{d\theta}{dt}=\omega N_\theta,
\qquad
\frac{dx}{dt}=vN_x.
$$

Their inferred ages are $\theta/\omega$ and $x/v$.

### 4.1 Coordinate baseline / default-off arm

$$
N_\theta=N_x=1.
$$

This arm checks the exact default-off coordinate identity
$\theta=\omega t$ and $x=vt$. It is the control, not a common-lapse claim.

### 4.2 Shared normalized-lapse arm

$$
N_\theta=N_x=N_q=\frac{K}{1-q_{\rm ref}}=K.
$$

The same scalar is applied to each complete first-order generator. With
$q_ref=0$, the raw conversion age and both inferred generator ages should
collapse to the same normalized process age at the stopping target.

### 4.3 Deliberately independent per-sector arm

$$
N_\theta=1.35K,
\qquad
N_x=0.65K.
$$

The conversion clock remains canonical $K$; only the non-conversion sectors are
assigned distinct lapses. This is the pre-registered falsifier: independent
sector lapses must reject the shared-age collapse, rather than being hidden by a
single post-hoc clock.

## 5. Gates and stopping rule

The scene prints each gate and exits `0` only if every gate passes. It writes one
raw JSON receipt regardless of pass/fail. Receipt `result` and console `PASS` /
`FAIL` labels are implementation status only.

1. **Bounds/positivity (G1).** `q_ref < 1`, $1-q_ref>0$, every sampled
   $0\le q<1$, and every $K>0$; all arms reach the fixed target with finite
   state.
2. **Analytic/numerical closure (G2).** At every midpoint, compare
   $K=1-q$ with the independently evaluated rational complement above; compare
   their accumulated conversion ages. Both residuals must be $\le10^{-12}$.
3. **Default-off identity (G3).** In the baseline arm, require
   $\theta=\omega t$ and $x=vt$ to $10^{-10}$, inferred phase and translation
   ages to agree to the same tolerance, and both baseline lapses to remain
   exactly one.
4. **Shared generator/common age (G4).** Require $N_\theta=N_x=K$ at every
   update, and require conversion, phase, and translation inferred ages to
   collapse with spread/error $\le10^{-10}$. The reported
   $N_q=K/(1-q_ref)$ and $\tau_F/(1-q_ref)$ are diagnostics of this same update,
   not replacement clocks.
5. **Independent-arm falsifier (G5).** Require the three inferred ages to have
   spread $>1.0$ at the common conversion target, with phase/translation ratios
   equal to the frozen factors $1.35$ and $0.65$ within $10^{-10}$.
6. **Equal-$\tau_F$ discriminator (G6).** The two shared-arm trajectories must
   end at the same $\tau_F^*=4.0$ within $10^{-12}$ while their coordinate times
   differ by more than $1.0$ and their sampled mean $q$ values differ by more
   than $0.05$. This demonstrates only distinct coordinate parameterizations of
   the lab's same conversion-age target.
7. **Passive/backreaction control (G7).** Re-evaluation of the immutable source
   at each midpoint must match the original sample, and each trajectory's
   coordinate-time, $q$, and $K$ summaries must match across all three arms,
   with residuals $\le10^{-12}$. No arm may mutate or feed back into
   $\rho$, $\varepsilon$, or $q$.
8. **Receipt emission (G8).** The complete raw JSON receipt must be created at
   `res://_diag/process_time/common_lapse_receipt.json`. A write failure fails
   the scene.

The fixed stopping rule is part of the preregistration: once a trajectory reaches
$\tau_F^*$, that arm stops; a non-finite sample or non-positive $K$ stops that
arm as a failure. The complete preregistered arm/trajectory matrix is executed
once, with no adaptive retries, extra samples, alternate thresholds, trajectory
selection, or post-hoc rescaling after any failure.

## 6. Expected receipt and interpretation

The receipt records the frozen constants, q provenance and reference gauge,
trajectory/arm states, coordinate times, raw $\tau_F$, relative diagnostic
$\tau_F/(1-q_ref)$, $N_q$ extrema, inferred ages, closure residuals,
backreaction residuals, and the equal-$\tau_F$ summary. It must explicitly retain
these labels:

- coordinate `dt` is authoritative;
- `q_ref=0` is the open-gate reference;
- $N_q$ and relative age are constant-reference diagnostics;
- the source is local deterministic lab data, not the production raw q buffer;
- PASS/FAIL is an implementation/reparameterization result only;
- no result establishes universal physical time.

A PASS means the baseline identity, shared scalar reparameterization, and
independent-sector falsifier all behaved as frozen. The independent arm is
important: if its sectors nevertheless collapse, the implementation is not
actually testing a shared generator. Conversely, a shared-arm collapse is not a
measurement of nature; it is the expected algebra of applying one scalar to
complete first-order generators.

Any change to the formulas, trajectories, constants, arm definitions, thresholds,
or interpretation above requires a new pre-registration version before rerunning.
