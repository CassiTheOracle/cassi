# Gravity from Flow: The River Law's Measured State

## Status: Hypothesized—August 2026

## Abstract

The river law is the candidate statement that gravitational acceleration is the
gradient of the **flow-modulated chord**

$$
\boxed{
G_{\text{eff}}(x) = G\,\frac{\pi}{\rho}\,\Big(1 + (\varphi^{6}-1)\,q(x)\,f(x)\Big),\qquad
f(x) = 1 + \varphi^{-1}\,\ell^2\,\frac{C}{\rho},\qquad
C = -\nabla\cdot J
}
$$

built on the phase current $J = \Psi_Y\nabla\Psi_I - \Psi_I\nabla\Psi_Y = \rho\nabla\theta$.
The skeleton is derived: the coherence-gradient force's coefficient $(\varphi^{6}-1)$
comes from the chord law of `foundations/cassi-theory-reference.md` §4.3, and
$\kappa = \varphi^{-1}$ is an application of the derived per-rung damping of
`foundations/cascade-suppression-formula.md` §1—no free constant enters. The
probe wave (brief 68 of the spiral-gravity program) confirms the flow factor's
sign at the closure ($\bar f = 0.884 < 1$; the transport responds with the
predicted sign) while falsifying the linear-response magnitude (192×), so
$\kappa$'s value is undetermined; the surge form and the C2 density-transport
leg stay open. The sign question the law must answer is settled: the PDE's
field-level force $\mathbf{F} = +\Pi\nabla\Phi$ is $\Pi$-sign-following
(measured), and the point-particle sector's attraction is the
$-[1+(\varphi^{6}-1)q]$ convention.

**Epistemic tier: Hypothesized**—a candidate skeleton with measured sign
content. The quantitative content ($\kappa$'s value, the surge form, the
boundary scale) is explicitly undetermined.

---

## 1. Field Content and the Sign Question

### 1.1 The Poisson convention and the field-level force

The solver's field content is linear: $\rho = E_Y + E_I$ and $\Pi = E_Y - E_I$.
The Poisson solve is $\hat\Phi = -\hat\rho/k^2$ with the $k = 0$ mode nulled
(`two-fluid/cassi_two_fluid_3d_gpu.py`), so $\nabla^2\Phi = \rho$ and a point
mass gives $\Phi = -M/(4\pi r)$: **in the far field $\nabla\Phi$ points outward
from an overdensity**. The momentum source is

$$
\mathbf{F} = +\Pi\,\nabla\Phi
$$

applied to both fluids (the 1D harness's equivalence-principle convention).

The measured record makes the force's sign content explicit
(`hypotheses/two-strand-five-channel-matter-organization.md` §3.3, §3.5):

- **Yang excess repels**: the TS1 pair with $\Pi > 0$ escapes ($d$ 9.90 → 15.73).
- **Yin excess attracts**: the exchanged pair with $\Pi < 0$ contracts and
  coalesces ($d$ 9.90 → 7.51, $t \approx 47$).
- The closure's raw force is reproduced at $t = 0$ from the documented init:
  $F_0(x^*) = -4.0447\times10^{-3}$ with $\Pi(x^*) = +0.2834$ and
  $\nabla\Phi(x^*) = -0.0143$ (the spiral-gravity program's brief 67, Stage 0;
  compute record `run67_output.txt`). The closure is Yang-excess, and the
  gradient points back toward the source because the near field dominates
  there.

The inward reading of $\nabla\Phi$ is therefore the **local near-field statement**, not a general one: the
direction of $\nabla\Phi$ is set by the Poisson convention, and the force
$\Pi\nabla\Phi$ follows the sign of $\Pi$.

### 1.2 The point-particle sector's convention

The point-particle reduction (`gravity/three-body-analytical.md` §2.2–§2.3)
starts from $\Phi = -G\sum_i M_i/|\mathbf{x}-\mathbf{X}_i|$, whose gradient at
$\mathbf{X}_j$ is **outward**,

$$
\nabla\Phi(\mathbf{X}_j) = +G\sum_{i\neq j} M_i\,\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3},
$$

and the sector's equation of motion adopts the Newtonian $-\nabla\Phi$ form,

$$
\boxed{
\ddot{\mathbf{X}}_j = -\alpha_j\,(1+(\varphi^{6}-1)q_j)\,\nabla\Phi(\mathbf{X}_j)
}
\qquad
\alpha_j = \Pi_j/M_j,
$$

whose own leading minus inverts the outward gradient and produces the boxed
attractive law of that document. With $\alpha_j = \Pi_j/M_j$, the sector's
implied field force is the **negative** of the solver's $+\Pi\nabla\Phi$ for
$\Pi > 0$ blobs—the attraction is a sector convention, not a consequence of the
PDE force.

### 1.3 The sign-definiteness requirement

The two sectors cannot both be the field-level physics for a
$\varphi$-equilibrium blob ($\Pi/\rho = \varphi^{-3} > 0$ at the fixed point):
the PDE force repels it, the point-particle law attracts it. The measured
record supports $+\Pi\nabla\Phi$ as the field-level force, and the point-particle
attraction as the sector convention. A river law that is attractive for all
matter must therefore be built from a **positive-definite** flow object with a
definite sign—not a $\Pi$-sign-ambiguous one. The flow factor $f$ keeps the
modulated chord positive under the bound $|\kappa\ell^2 C/\rho| < 1$ (§2), and
the coherence-gradient force (§2.2) is unconditionally attractive toward high
$q$.

---

## 2. The Candidate Law—the Flow-Modulated Chord

### 2.1 The boxed law

The closing structure of the spiral-gravity program's derivation wave (brief 67,
Stage D) is the flow-modulated chord of the Abstract:

$$
\boxed{
G_{\text{eff}}(x) = G\,\frac{\pi}{\rho}\,\Big(1 + (\varphi^{6}-1)\,q(x)\,f(x)\Big),\qquad
f(x) = 1 + \varphi^{-1}\,\ell^2\,\frac{C}{\rho},\qquad
C = -\nabla\cdot J
}
$$

with $J = \Psi_Y\nabla\Psi_I - \Psi_I\nabla\Psi_Y = \rho\nabla\theta$,
$\theta = \operatorname{atan2}(\Psi_I, \Psi_Y)$, and $\ell$ the local rung
scale (the probe's own geometry: $\ell = x^*$, the closure rung's distance; in
the 3D solver, the resolved-window scale).

**The river is the gradient of the flow-modulated chord.** Under the
static-potential sector convention $\Phi_{\text{eff}} = -G_{\text{eff}}(x)M/r$,
$\mathbf{a} = -\nabla\Phi_{\text{eff}} = (M/r)\nabla G_{\text{eff}} -
G_{\text{eff}}M\,\hat r/r^2$, and the coherence part of $\nabla G_{\text{eff}}$
splits into two terms:

$$
\boxed{
\mathbf{a}_q = \frac{GM}{r}\,\frac{\pi}{\rho}\,(\varphi^{6}-1)\,\nabla q
}
$$

— the coherence-gradient force, unconditionally toward higher $q$—plus the
flow term

$$
\frac{GM}{r}\,\frac{\pi}{\rho}\,(\varphi^{6}-1)\,q\,\nabla f,
$$

the flow factor's gradient acting on the coherence itself.

### 2.2 Derivation status of each piece

- **$J = \rho\nabla\theta$**: the phase-current identity, verified symbolically
  in the program. At the $\varphi$-attractor ($E_Y = \varphi E_I$, any spatial
  variation) $\theta = \operatorname{atan2}(1,\varphi) = \text{const}$, so
  $J \equiv 0$ there—every candidate built on $J$ or its derivatives vanishes
  at the attractor with no extra assumption. The off-attractor content is the
  object $C/\rho$.
- **$\kappa = \varphi^{-1}$**: an application of the derived per-rung signal
  damping $d_i \approx \varphi^{-1}$ (`foundations/cascade-suppression-formula.md`
  §1.2) as a one-rung coupling—**not a new constant**.
- **$(\varphi^{6}-1)$**: the chord's own coefficient
  (`foundations/cassi-theory-reference.md` §4.3), with $\xi = \varphi^6$ the
  derived rung identity whose empirical pin is Calibrated on the Milky Way
  rotation curve (`parameter-inventory.md` §10, row 498). Under the
  static-potential sector convention the coefficient is **not free**.
- **C1 (the force-side member)**: $\mathbf{F}_{C1} = \Pi\nabla\Phi\,(1 +
  \kappa\ell^2 C/\rho)$, sign-definite iff $|\kappa\ell^2 C/\rho| < 1$; in the
  limit $J \to 0$ the base force is restored.
- **C2 (the continuity-side member)**: $\partial_t\rho \supset
  -\lambda\nabla\cdot(qJ/\rho)$—a pure divergence on the mirror-Neumann domain,
  so total mass is conserved exactly; density piles up where the gated phase
  current converges. C2 is a redistribution, not a source: the conversion term
  of `foundations/cassi-first-principles.md` remains the density source.
- **The excluded alternatives**: the vorticity-modulated force (C3) fails
  closure—its coupling $\chi$ has no derived value (a free scratch constant,
  `parameter-inventory.md` §10, row 521) and a parity-odd linear form breaks
  sign-definiteness; the accumulated-kick surge model $P \sim \lambda^2$ is
  falsified by the measured surge (§3.2); the rung-summed law (C4) reduces to
  the single-window law $F = F_0(1 + O(\varphi^{-2}))$—C1/C2 at the resolved
  scale are the multiscale law's resolved reading.

The law is a **candidate skeleton**: the exact minimal missing structure is the
measured value and object form of the flow factor's coefficient—$\kappa$'s
magnitude, and whether the object is $C = -\nabla\cdot J$, $|C|$, or the gated
$(1-q)C$.

---

## 3. The Measured Content (brief 68, run 2026-08-08)

All numbers below are from the spiral-gravity program's brief 68 (`68-river-probes.md`)
and its machine receipts (`run68_output.txt`, `run68_river_probes_results.json`),
run on the consolidated runner with the 12-check acceptance passing at $10^{-9}$.
The probe arms are the closure configuration: $\lambda = 0.02$, $\gamma = 0.01$,
$\sigma = 3\times10^{-5}$, $u = 0$, $\psi = \psi^*$, $N = 1440$, $t = 3.0$.

### 3.1 P1—the closure arm (C1): the flow factor's sign is confirmed

The weighted object is the $|F\cdot dE/dx|$-weighted time-mean of the flow
factor's argument at $x^*$:

$$\langle \ell^2 \partial_z J_z/\rho\rangle_{Fw} = +0.18770,
\qquad \kappa = \varphi^{-1} = 0.618034,\qquad \ell = x^* = 0.786151.$$

- The flow factor's time-mean: $\bar f = 1 - \varphi^{-1}\langle\ell^2\partial_z
  J_z/\rho\rangle_{Fw} = 0.884 < 1$—the chord's factor **reduces** the force at
  the closure, on average.
- The prediction: $dU/U \approx -\kappa\langle\ell^2\partial_z J_z/\rho\rangle_{Fw}
  = -0.1160$.
- The measurement: $dU/U = (u_{\text{flux}}^{\text{mod}} - u_{\text{flux}}^{\text{base}})
  /u_{\text{flux}}^{\text{base}} = -22.22$, with $u_{\text{flux}}$ going
  $+2.2369\times10^{-4} \to -4.7464\times10^{-3}$.
- The sign-definiteness bound holds on the weighted mean:
  $|\kappa\langle\ell^2\partial_z J_z/\rho\rangle_{Fw}| = 0.116 < 1$ (the
  instantaneous values at $x^*$ exceed it—the momentary-reversal structure).
- The $\kappa = 0$ arm is bit-exact, and the runner's acceptance passes.

**Verdict: sign confirmed, magnitude falsified.** The pre-registered tree
(sign, presence, no-op, acceptance) fires on this run; the same data falsify
the linear-response magnitude—the response is **192×** the first-order
prediction. The implied coupling under the falsified linear ansatz would be
$\kappa_{\text{eff}} \approx 118$, which is **not** a derived value and is not
claimed. The robust content: the flow factor's sign structure at $x^*$, and the
presence of the transport response with the predicted sign. **$\kappa$'s value
is undetermined.**

### 3.2 P5—the surge form: undetermined

On the 7-point set $\{0.02, 0.03, 0.05, 0.07, 0.1, 0.15, 0.2\}$, none of the
four pre-registered two-parameter forms meets the 2% bar:

| model | best fit | max rel. resid. |
|---|---|---|
| $P = c\lambda^a$ | $c = 0.23031$, $a = 1.14816$ | 37.92% |
| $P = c\lambda/(1-k\lambda)$ | $c = 0.14765$, $k = 0.93405$ | 60.87% |
| $P = c\lambda(1+k\lambda)$ | $c = 0.14311$, $k = 1.35163$ | 57.15% |
| $P = A(1-e^{-\lambda/0.1})^2$ | $A = 0.04569$ | 19.75% |

The local log-log slopes fall monotonically, 1.566 → 1.056 (variation 0.510
against the pre-registered 0.15 bar). **The surge's form stays undetermined.**
The $\lambda_0 = 0.1$ saturation family is the closest form, with
$\lambda_0 \approx 0.1 \approx \lambda$ a candidate coincidence of that family,
**not a claim**.

### 3.3 P5—the phase boundary: the OFF-side margin

The sharpened gate (late-window $|u_{\text{flux}}| \geq 3\times
\text{OFFmax}_{\text{neg}}$) fails already at $\lambda = 0.03$ (margin 0.507)
and at $\lambda = 0.04$ (margin 0.116). The pre-registered branch therefore
reads the **OFF-side margin as the limiter**:

$$\lambda_{\text{gate}} \approx 0.0255.$$

The ON-side scale $\lambda^* \approx 0.048 \approx \lambda/2$ is context only:
the W7 zero-crossing refines to $\lambda^* \approx 0.044$–$0.048$, but it is not
what fails the gate. A candidate coincidence is on record with its
interpolation caveat, not as a claim:

$$\lambda_{\text{gate}} \approx 0.0255 \approx \frac{\lambda}{4} = \frac{1}{8w} = 0.025
\qquad\text{(2\% off)}.$$

### 3.4 P2—the density-transport leg (C2): inconclusive

The transport arm $-\lambda_t\partial_x(qJ_z/\rho)$ produces NaN at step 118
($t = 0.177$) at the left wall. The mechanism is the harness's
mirror-Neumann spectral derivative: its documented wall layer on the composite
flux $qJ_z/\rho$ (measured $\max|\partial_x(qJ_z/\rho)| \sim 20$–$570$ from
$t = 0$ onward, orders above the $O(0.05)$ smooth-region estimate) drives $\rho$
through zero. The $\lambda_t = 0$ no-op arm is bit-exact. **C2 stays open**;
the Pearson and drift statistics are undefined. A re-test requires a
pre-registered wall-layer handling (e.g., a windowed flux or a smoothed
derivative) and is future work.

---

## 4. Consequences

### 4.1 The Godot formula

The one-line point-mass formula for the Godot simulation (the static-potential
sector reading of the chord law):

$$
\boxed{
\mathbf{a} = -G\,\frac{\pi}{\rho}\,(1+(\varphi^{6}-1)q)\,
\sum_i M_i\,\frac{\hat r_i}{r_i^2}
\;+\;
G\,\frac{\pi}{\rho}\,(\varphi^{6}-1)\,
\Big(\sum_i \frac{M_i}{r_i}\Big)\,\nabla q
}
$$

with $(\pi/\rho)$ the sim's clamped Yang fraction. The formula is conditional
on the Calibrated chord pin (row 498 of `parameter-inventory.md` §10) and the
static-potential sector convention of §1.2; $(\varphi^{6}-1)$ is the chord's
coefficient, not a tuning dial.

### 4.2 Black holes

A horizon exists for any positive $G_{\text{eff}}$: $r_s =
2G_{\text{eff}}M/c^2$. The collapse threshold scales as
$G_{\text{eff}}^{-3/2}$, so the chord's range
$G_{\text{eff}}/G \in [0.236,\,4.24]$ at the equilibrium Yang fraction
$\alpha = \varphi^{-3}$ (up to $\approx 12.6$ with a halo's $\alpha \approx
0.7$) shifts stellar black-hole masses by roughly an order of magnitude. The
framework's black-hole sector itself is $\sigma$-regularized harmonic cores
with the GR exterior (registry G3, Derived; `gravity/quantum-gravity.md` §7.1),
so the river law's consequences act on the collapse threshold and the horizon
radius, not on the core structure. The $\nabla q$ force is unconditionally
attractive toward high-$q$ sites, so coherence-convergence regions
($C > 0$) are black-hole-favorable.

### 4.3 The two-strand and lattice-stack reading

C2 makes a definite-sign prediction for the lattice-stack retention record: the
envelope-retention correlation with $|J_z|(0)$ (Pearson $+0.51$, Spearman
$+0.77$; `hypotheses/two-strand-five-channel-matter-organization.md` §3.8)
should follow

$$\text{retention} \sim \frac{1 + c_2\langle C\rangle_{\text{stack}}\,t}{1 + c_2\langle C\rangle_{\text{base}}\,t},$$

with convergence ($C > 0$) piling density at the accumulating sites. C2 is
mass-conserving—it redistributes density, it cannot create a potential
well—consistent with the no-binding records (the TS1 escape and the wake-binding
and lattice-stack nulls).

---

## 5. Open Items

1. **$\kappa$'s value and the object form.** The flow factor's sign is
   measured at $x^*$; its magnitude is not. Whether the object is
   $C = -\nabla\cdot J$, $|C|$, or the gated $(1-q)C$ is unmeasured. The
   linear-response ansatz is falsified 192×; nothing about $\kappa$'s value
   follows from the measured magnitude.
2. **The surge form.** The 7-point residual table stands; the
   $\lambda_0 \approx 0.1$ saturation family is the closest form at 19.75%,
   an order of magnitude above the 2% bar.
3. **The boundary scale.** $\lambda_{\text{gate}} \approx 0.0255$, with the
   $\lambda/4 = 1/(8w)$ candidate (2% off) recorded with its interpolation
   caveat; a finer boundary scan replaces the interpolation.
4. **C2's re-test** needs a pre-registered wall-layer handling on the
   mirror-Neumann spectral derivative.
5. **The parity-odd probe (P3, 3D) and the rung-sum post-process (P4)** from
   the program's ranked probe list are unrun.
6. The law is not closed: the flow-modulated chord remains a candidate
   skeleton with measured sign content, and every quantitative claim above is
   tiered accordingly.

---

## References

- `foundations/cassi-first-principles.md`—two-fluid PDE, the conversion term, the $\varphi$-attractor
- `foundations/cassi-theory-reference.md` §4.3—the chord law $G_{\text{eff}} = G(\pi/\rho)(1+(\varphi^{6}-1)q)$
- `foundations/spiral-dynamics.md` §3—gravity as $\Pi\nabla\Phi$ gradient descent; the field force and its sign
- `foundations/cascade-suppression-formula.md` §1—the derived per-rung damping $d_i \approx \varphi^{-1}$ ($\kappa$'s receipt)
- `gravity/three-body-analytical.md` §2—the point-particle reduction; the attractive convention
- `hypotheses/two-strand-five-channel-matter-organization.md` §3—the sign-following measurements (TS1, Yin-excess) and the lattice-stack records
- `gravity/quantum-gravity.md`—the $\sigma$-regularized black-hole sector (registry G3)

The derivation and probe record is the spiral-gravity program's briefs 67–68
(`67-gravity-from-flow-laws.md`, `68-river-probes.md`, with the machine
receipts `run67_output.txt`, `run68_output.txt`,
`run68_river_probes_results.json`). Those briefs live outside this repo
(cassi-toe-rewrite-briefs/) and are cited by name; every measured number in
§3 traces to them.
