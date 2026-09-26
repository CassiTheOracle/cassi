# Cassi P versus NP Crossover Preregistration

## Status: Frozen—September 9, 2026

## 1. Question

Can the bounded two-fluid coherence mechanism supply the clause-memory and
nonlocal escape needed for a polynomial-resource SAT algorithm, or does its
useful computation reduce to a fast-forwardable linear transport layer plus a
bounded local relaxation heuristic?

This probe can reject concrete mechanisms. Finite runs cannot prove either
`P = NP` or `P != NP`.

## 2. Live equations and exact structural claims

Let `u = (EY, EI)` be the source-free field on the periodic production grid and
let `L` be the symmetric negative-semidefinite 19-point grid Laplacian. With
the default production coupling,

```text
EY_tt = L EY - omega2 (EY - phi EI)
EI_tt = L EI + omega2 (EY - phi EI).
```

Define

```text
R       = EY + EI
 epsilon = EY - phi EI.
```

Then, exactly,

```text
R_tt       = L R
 epsilon_tt = L epsilon - phi^2 omega2 epsilon.
```

The inverse is

```text
EY = (phi R + epsilon) / phi^2
EI = (R - epsilon) / phi^2.
```

The fixed-source case has the same decoupled affine recurrence after adding
`source_R = source_EY + source_EI` and
`source_epsilon = source_EY - phi source_EI`. A spatial Fourier transform
reduces either case to independent scalar second-order recurrences. At fixed
numerical precision, a state after `T` steps can therefore be evaluated by
FFT plus independent constant-size matrix powers, without replaying `T`
field steps. This statement does not apply when moving particles change the
mass source or when an external controller changes the learned source.

The coupling matrix is self-adjoint under `H = diag(1, phi)`. For `K = -H A`,
where `A` is the full source-free acceleration operator, `K` is positive
semidefinite and the continuous weighted energy is

```text
E = 0.5 EY_t^T EY_t + 0.5 phi EI_t^T EI_t
  + 0.5 EY^T (-L) EY + 0.5 phi EI^T (-L) EI
  + 0.5 omega2 ||EY - phi EI||^2.
```

For the production kick-drift update

```text
v_next = v - dt H^-1 K u
u_next = u + dt v_next,
```

an exact discrete quadratic invariant in exact arithmetic is

```text
E_dt = 0.5 v^T H v + 0.5 u^T K u - 0.5 dt u^T K v.
```

It is positive definite on every positive-frequency mode when
`dt^2 lambda_max(H^-1 K) < 4` and semidefinite on gapless zero modes.

## 3. Autonomous feedback inventory

The measured interpretation is frozen before the run:

1. `compute/cassi_two_fluid.glsl` is linear in the field for a fixed mass
   density and fixed learned command. Its stored `q = EY^2 + EI^2` is a
   readout, not a source term.
2. `compute/cassi_nbody_gravity.glsl` uses the bounded coherence
   `q_coh = rho_field^2 / (rho_field^2 + phi^-2 + epsilon^2)` only through the
   bounded chord factor and particle acceleration. Particle motion then
   changes the next mass deposit, forming a real nonlinear loop.
3. Condensation and merge are thresholded, lossy topology changes. They can
   implement finite switching but do not provide an accumulating per-clause
   record. They are not used in the reduced SAT arm.
4. Field intelligence supplies bounded learned actuation and plasticity. Its
   reward selection, episode scheduling, target-setting, and readout are host
   algorithm work and must be included in any complexity claim.
5. The mind engine's deposits and projections are externally requested TCP
   operations. Treating the requester as free would move the SAT solver out of
   the field.

## 4. SAT encoding

A Boolean variable is represented by `s_i in [-1, 1]`, with `+1` meaning true.
For clause `m`, `c_mi = +1` for literal `x_i`, `-1` for literal `not x_i`, and
zero when absent. Its continuous violation is

```text
K_m(s) = product over literals i in m of (1 - c_mi s_i) / 2.
```

At a Boolean corner, `K_m = 0` exactly when the clause is satisfied.

The Cassi-shaped bounded coherence is

```text
q_m = 1 / (1 + beta K_m^2),
```

and the registered bounded landscape is

```text
V_q(s) = sum_m (1 - q_m)
       + boolean_lambda/4 sum_i (s_i^2 - 1)^2.
```

The candidate dynamics is damped second order:

```text
s_tt = -damping s_t - grad V_q(s),
```

integrated by kick-drift with the registered timestep and an `[-1, 1]` clamp.
A clamped outward velocity is zeroed. This is a reduced candidate, not a claim
that the production particle law already implements SAT.

## 5. Matched arms

Every satisfiable formula and initial state is run through:

- `coherence`: the bounded second-order `V_q` dynamics above;
- `static_gradient`: first-order descent on `sum K_m^2` with unit clause
  weights;
- `capped_ctds`: the Ercsey-Ravasz--Toroczkai clause dynamics with
  `a_m <= 64`;
- `exp_ctds`: the same clause dynamics with `a_m <= 1e12`, recording the
  largest weight rather than treating it as free.

For the CTDS arms,

```text
ds_i/dt = sum_m a_m D_mi,
da_m/dt = a_m K_m,
D_mi = 2 K_m c_mi product_{j in m, j != i}(1 - c_mj s_j)/2.
```

The Euler step is reduced as necessary so no proposed variable displacement
exceeds `0.02`; the physical time actually taken is recorded. State is clamped
to `[-1, 1]` only for floating-point guard error.

Every candidate assignment is certified directly against the CNF. Failure to
find an assignment is never interpreted as UNSAT.

## 6. Frozen corpus

The seed is `20260909`. The corpus is generated once by the probe and written
verbatim into the raw receipt.

1. Every subset of the eight width-3 clauses on three variables, excluding the
   empty formula. Exact enumeration labels each formula SAT or UNSAT.
2. Twelve planted 2-SAT formulas with `n = 8`, `m = 16`.
3. Eight planted random 3-SAT formulas at each
   `n in {6, 8, 10, 12}`, with `m = round(4.2 n)`.
4. Eight planted balanced 3-XOR systems converted to four 3-CNF clauses per
   XOR, two each at `n in {6, 8, 10, 12}`.
5. One adversarial planted formula at each `n in {6, 8, 10, 12}`. For each
   size, generate 128 planted random candidates at density `4.2`; enumerate
   the Boolean cube; select the candidate with the largest number of
   non-solution one-flip local minima in violated-clause count. Ties go to the
   earliest generated candidate.
6. One pigeonhole contradiction for three pigeons and two holes and one
   inconsistent 3-XOR system. These are false-positive controls only.
7. One variable permutation, one clause permutation, and eight irrelevant
   variables are applied to a registered planted formula. The vector field is
   checked after mapping the state back; solver success rates are descriptive.

All SAT/UNSAT labels for `n <= 12` are certified by exhaustive enumeration.

## 7. Frozen numerical parameters

```text
beta                 = phi^2
boolean_lambda       = 0.25
damping              = 0.35
coherence_dt         = 0.01
static_gradient_dt   = 0.02
ctds_base_dt         = 0.01
max_variable_delta   = 0.02
max_steps            = 12000
starts_per_formula   = 4
structural_grid_n    = 4
structural_steps     = 2000
structural_dt        = 0.001
structural_omega2    = 20
```

Initial `s_i` values are uniform in `[-0.5, 0.5]`; second-order velocities are
zero; CTDS weights start at one. A Boolean readout maps zero to true.

## 8. Metrics and resource ledger

For every run record:

- certified success and first solution step;
- physical time, integration steps, derivative evaluations, and clamp count;
- state dimension and clause count;
- maximum `|s|`, `|velocity|`, `|gradient|`, `a_m`, and `log2(a_m)`;
- smallest absolute variable margin at successful readout;
- final violated-clause count.

Aggregate by arm, family, and size. Report medians and maxima without fitting a
polynomial or exponential law from these small sizes.

The structural arm records normal-mode parity, superposition residual,
fixed-source affine fast-forward residual, and weighted-invariant drift.

## 9. Decision tree

### S1—linear structure

`PASS` only if all four structural residuals are at most `1e-9` in float64.
Otherwise `FAIL`.

### S2—bounded coherence SAT mechanism

`SUPPORTS` only if `coherence` certifies every satisfiable corpus formula from
all four starts within `max_steps`, emits no false positive on either UNSAT
control, and has minimum successful readout margin at least `1e-3`.
Any missed satisfiable run, false positive, or smaller margin is
`CONTRADICTS`.

### S3—bounded clause memory

`SUPPORTS` only if `capped_ctds` matches `exp_ctds` on every certified SAT run,
with no case in which the exponential arm succeeds only after a weight exceeds
64. Otherwise `CONTRADICTS`.

### S4—representation invariance

`PASS` only if the permuted coherence vector fields map back with maximum
absolute residual at most `1e-12` and irrelevant variables do not change the
original-variable vector field above `1e-12`. Otherwise `FAIL`.

### Overall stage

`ADOPT` as a candidate P-equals-NP route only if S1, S2, S3, and S4 all pass,
all recorded resources are finite, and no resource exceeds the frozen caps.
Otherwise `REJECT`. A rejection applies only to this registered bounded
coherence mechanism, not to every possible Cassi-derived algorithm.

## 10. Stopping and artifact rule

The first complete run is final. Crashes or schema errors may be repaired, but
parameters, corpus rules, thresholds, and verdicts are not changed. The raw
receipt path is `_diag/p_vs_np_probe.json`. The independent verifier reads only
that receipt and recomputes all gates.