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
The probe waves (briefs 68–71 of the spiral-gravity program) confirm the flow
factor's sign at the closure ($\bar f = 0.884 < 1$; the transport responds
with the predicted sign) and establish the quantitative content: the object is
$C = -\nabla\cdot J$ (the only candidate whose sign tracks), the transport
response is linear in $\kappa$—$dU/U = -36.05\,\kappa$ over
$[\varphi^{-2}, \varphi]$—with the linear-response magnitude still falsified
192× (the amplification is $\kappa$-independent: it lives in the measured
transport coupling $A = -36.05$, not in a $\kappa$ nonlinearity, and $\kappa$
itself is never fitted), and the phase boundary is measured at
$\lambda_{\text{gate}} = 0.0224$, rejecting the $\lambda/4$ candidate. The
surge form and the C2 density-transport leg stay open; the parity-odd force
channel is live at the $\chi = \varphi^{-1}$ scale with $\chi$ asserted, and
the rung-sum post-process is inconclusive with the multiscale reduction
confirmed. The sign question the law must answer is settled: the PDE's
field-level force $\mathbf{F} = +\Pi\nabla\Phi$ is $\Pi$-sign-following
(measured), and the point-particle sector's attraction is the
$-[1+(\varphi^{6}-1)q]$ convention.

**Epistemic tier: Hypothesized**—a candidate skeleton whose quantitative
content is now the object form $C = -\nabla\cdot J$, the linear response curve
($A = -36.05$, a measured transport constant), and the measured boundary
$\lambda_{\text{gate}} = 0.0224$; the surge form and the C2 leg remain open.

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
  `parameter-inventory.md` §10, row 521) and a parity-odd linear form is not
  sign-definite across a twist; the channel's presence at the $\chi =
  \varphi^{-1}$ scale is nonetheless measured (P3, §3.9—live, with $\chi$
  still asserted); the accumulated-kick surge model $P \sim \lambda^2$ is
  falsified by the measured surge (§3.2); the rung-summed law (C4) reduces to
  the single-window law $F = F_0(1 + O(\varphi^{-2}))$—C1/C2 at the resolved
  scale are the multiscale law's resolved reading (the reduction confirmed by
  P4, §3.10).

The law is a **candidate skeleton**. The wave-2 probes (§3) close the object
form—the flow factor's object is $C = -\nabla\cdot J$, with the response
linear in $\kappa$ and the transport coupling $A = -36.05$ measured—and the
phase boundary; the surge form and the C2 density-transport leg remain open.

---

## 3. The Measured Content (briefs 68–71, runs 2026-08-08/09)

Sections 3.1–3.4 carry the wave-1 record (brief 68 and its machine receipts
`run68_output.txt`, `run68_river_probes_results.json`), run on the
consolidated runner with the 12-check acceptance passing at $10^{-9}$. The
probe arms are the closure configuration: $\lambda = 0.02$, $\gamma = 0.01$,
$\sigma = 3\times10^{-5}$, $u = 0$, $\psi = \psi^*$, $N = 1440$, $t = 3.0$.
Sections 3.5–3.10 carry the wave-2 content (briefs 69–71, runs 2026-08-08/09).

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
what fails the gate. The two-point estimate suggested the candidate
coincidence

$$\lambda_{\text{gate}} \approx 0.0255 \approx \frac{\lambda}{4} = \frac{1}{8w} = 0.025
\qquad\text{(2\% off)},$$

which the fine scan (§3.7) resolves: the measured $\lambda_{\text{gate}} =
0.02242$ is 10.33% off the candidate—outside the pre-registered $\pm 10\%$
window—so the $\lambda/4$ reading is rejected at tolerance.

### 3.4 P2—the density-transport leg (C2): inconclusive

The transport arm $-\lambda_t\partial_x(qJ_z/\rho)$ produces NaN at step 118
($t = 0.177$) at the left wall. The mechanism is the harness's
mirror-Neumann spectral derivative: its documented wall layer on the composite
flux $qJ_z/\rho$ (measured $\max|\partial_x(qJ_z/\rho)| \sim 20$–$570$ from
$t = 0$ onward, orders above the $O(0.05)$ smooth-region estimate) drives $\rho$
through zero. The $\lambda_t = 0$ no-op arm is bit-exact. **C2 stays open**;
the Pearson and drift statistics are undefined. The re-test with the
pre-registered wall-layer handling is the subject of §3.8.

### 3.5 P1b—the object form and the response curve (C1, brief 69): confirmed-object, linear response

The wave-2 object-form arms put the three candidate objects through 68's
pre-registered tree on the canonical arm ($\lambda = 0.02$, $\gamma = 0.01$,
$\sigma = 3\times10^{-5}$, $\kappa = \varphi^{-1} = 0.618034$, $\ell = x^* =
0.786151$; $\langle o\rangle_{Fw} = \langle\ell^2 O/\rho\rangle_{Fw}$, the
$|F\cdot dE/dx|$-weighted time-mean at $x^*$):

| $O$ | $\langle\ell^2 O/\rho\rangle_{Fw}$ | $dU/U$ | sign test | $\|\kappa\langle o\rangle_{Fw}\| < 1$ |
|---|---|---|---|---|
| $C = -\partial_z J_z$ | $-1.876952\times10^{-1}$ | $-22.218$ | **True** | 0.116 ✓ |
| $\|C\|$ | $+4.481817\times10^{0}$ | $-6.50\times10^{-2}$ | False | 2.77 ✗ violated |
| $(1-q)C$ | $+2.356657\times10^{-1}$ | $-6.92$ | False | 0.146 ✓ |

- **Only $C$'s sign tracks** (under 68's verbatim sign test—the tree the
  canonical arm's CONFIRMED content rests on): $|C|$ amplifies the force by a
  factor $\ge 1$ everywhere (mean factor 3.77) yet slightly *reduces* the flux
  ($-6.5\%$), and the gated object—whose weighted mean is positive
  ($+0.236$)—responds $-6.9$; neither tracks.
- **$|C|$ violates the sign-definiteness bound on its weighted mean**
  ($\|\kappa\langle o\rangle\| = 2.77 \ge 1$) and cannot be the object of a
  sign-definite river law. $C$'s and $(1-q)C$'s weighted means are inside the
  bound (0.116, 0.146).
- The $\kappa = 0$ no-op is bit-exact, and the provenance is bit-exact:
  mod-$C$ $u_{\text{flux}} = -4.7463675821\times10^{-3}$ reproduces 68's
  mod-ON receipt at $10^{-9}$—the canonical arm is 68's arm.

**CONFIRMED-object: the flow factor's object is $\boxed{C = -\nabla\cdot J}$.**

The response curve on $C$, full window, same weighting:

| $\kappa$ | $dU/U$ | bound-violation fraction (weighted steps at $x^*$) |
|---|---|---|
| $\varphi^{-2} = 0.381966$ | $-1.3684\times10^{1}$ | 84.98% |
| $\varphi^{-1} = 0.618034$ | $-2.2218\times10^{1}$ | 95.20% |
| 1 | $-3.6087\times10^{1}$ | 97.76% |
| $\varphi = 1.618034$ | $-5.8459\times10^{1}$ | 98.06% |

The power fit over the four points: $A = -36.05 \pm 0.02$, $m = 1.0050 \pm
0.0011$, max rel res 0.15% (the saturating form degenerates, $\kappa_0 \to
1.45\times10^4$—no saturation in $[\varphi^{-2}, \varphi]$). The measured law:

$$\boxed{dU/U \approx -36.05\,\kappa \quad \text{over } [\varphi^{-2}, \varphi]
\qquad (m = 1.005 \pm 0.001,\ \text{linear at the 0.5\% level})}$$

$\kappa = \varphi^{-1}$ lands at $dU/U = -22.22$—68's datum, reproduced
bit-identically—and the 192× magnitude amplification is **$\kappa$-independent**: it
lives in the transport coupling $A = -36.05$ (a measured transport constant of
the closure arm, not a parameter and not a derived value), not in a $\kappa$
nonlinearity. The sign-definiteness bound holds on the weighted mean
($\|\kappa\langle o\rangle_{Fw}\| = 0.116 < 1$) but is violated on **95.2% of
the weighted steps at $x^*$** at $\kappa = \varphi^{-1}$—the momentary-reversal
structure, now measured. $\kappa$ itself is not fitted ($\varphi^{-1}$ by
construction, the derived per-rung damping).

### 3.6 P5b—the surge form, extended set (brief 69): undetermined

On the 14-point set $\{0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05,
0.07, 0.1, 0.15, 0.2, 0.25, 0.3\}$ (the receipts reproduce 68/66 exactly at
the overlapping points), none of the six pre-registered families meets its
bar (2-parameter 5%, 3-parameter 2%):

| model | params | max rel res | bar |
|---|---|---|---|
| $P = A(1-e^{-\lambda/\lambda_0})^2$ | $A = 0.06909$, $\lambda_0 = 0.1492$ | 84.73% | FAIL |
| $P = A(1-e^{-\lambda/\lambda_0})^m$ | $A = 0.13301$, $\lambda_0 = 0.4312$, $m = 1.3188$ | 51.88% | FAIL |
| $P = c\lambda^a e^{-\lambda/0.1}$ | $c = 32.76$, $a = 2.920$ | 97.75% | FAIL |
| $P = c\lambda^a e^{-\kappa\lambda}$ | $c = 0.3848$, $a = 1.3061$, $\kappa = 1.3361$ | 51.23% | FAIL |
| $P = c\lambda/(1-\kappa\lambda)$ | $c = 0.15856$, $\kappa = 0.42876$ | 70.99% | FAIL |
| $P = A(1-e^{-\lambda/\lambda_0})(1-\bar q(\lambda))$ | $A = 29.21$, $\lambda_0 = 50.0$ | 94.67% | FAIL |

**The surge's form stays undetermined**—the best is the 3-parameter damped
power at 51.2%, still 25× above the 2% bar, and the 7-point set's
$\lambda_0 \approx 0.1$ saturation family does not survive the extended set
(the two-parameter saturation fit now needs $\lambda_0 = 0.149$ and leaves
84.7%).

New structure on the extended set:

- **A small-$\lambda$ dip**: $P$ decreases over $[0.01, 0.02]$ ($1.9012\times
  10^{-3} \to 1.8706\times10^{-3}$; the first two local log-log slopes are
  $-0.020$ and $-0.028$) before rising steeply (local slope peaking at 1.625
  over $0.025 \to 0.03$).
- **The saturation tail**: the local slope falls monotonically thereafter, to
  0.965 at $\lambda = 0.3$—the large-$\lambda$ saturation trend is visible; its
  form is not. Slope variation over the set: 1.653.

The W7 zero-crossing (context): $\lambda^* = 0.0443$ on the extended set.

### 3.7 P5c—the phase boundary, fine scan (brief 69): measured; the $\lambda/4$ candidate rejected

The fine scan $\{0.021 \ldots 0.030\}$ with $m(\lambda) = |W7|/(3\cdot
\text{OFFmax}_{\text{neg}})$:

| $\lambda$ | $m(\lambda)$ | gate ($m \ge 1$) |
|---|---|---|
| 0.021 | 1.123 | True |
| 0.022 | 1.034 | True |
| 0.023 | 0.952 | False |
| 0.024 | 0.875 | False |
| 0.025 | 0.803 | False |
| 0.026 | 0.736 | False |
| 0.027 | 0.673 | False |
| 0.028 | 0.614 | False |
| 0.029 | 0.559 | False |
| 0.030 | 0.507 | False |

The crossing between the straddling pair ($\lambda = 0.022$, $m = 1.034$) and
($\lambda = 0.023$, $m = 0.952$) is crisp—$m$ falls 0.08 per 0.001 of
$\lambda$—and linear interpolation gives

$$\boxed{\lambda_{\text{gate}} = 0.02242 \quad
\text{(measured; the gate holds at 0.021–0.022 and fails from 0.023)}}$$

The $\lambda/4 = 1/(8w) = 0.025$ candidate: $|\lambda_{\text{gate}} - 0.025|/0.025 =
10.33\%$—outside the pre-registered $\pm 10\%$ window, so **the candidate is
rejected at tolerance** (the margin is 0.33 points; the measured number
stands). The two-point estimate of §3.3 (0.0255) is 12% high of the fine scan.
The ON-side scale is confirmed **not** the limiter: $\lambda^* = 0.0443$,
$\lambda^*/\lambda_{\text{gate}} = 1.98$—the gate fails at less than half the
ON-side crossing.

### 3.8 P2b—C2's re-test with the wall-layer handling (brief 69): inconclusive; the mechanism corrected

The re-test applied the pre-registered half-cosine window (width $W = 16$
cells at each wall—the wave brief's $W = 4$ was disclosed as a deviation, with
the measured rationale: $\max|\partial_x(qJ_z/\rho)|$ at $t = 0$ falls 22.76
(unwindowed) → 11.55 ($W = 4$) → 7.84 ($W = 16$), the last equal to the
interior physical feature). The wall layer is removed—**and is not the limiting
factor**. The transport arm at the pre-registered rate $\lambda_t = 0.1$ is
unstable on the harness's interior field content:

- The interior composite flux has intrinsic $|\partial_x(qJ_z/\rho)| \sim O(8)$
  from $t = 0$ (the product-wavenumber structure of $J_z = E_Y\partial_zE_I -
  E_I\partial_zE_Y$, not the $O(0.05)$ smooth-region estimate of the wave-1
  record).
- The transport's own feedback grows it: 7.75 ($t = 0$) → 9.0 ($t = 0.075$) →
  106.9 ($t = 0.15$, interior, $x = -0.89$), driving $\rho$ through zero.
- First NaN at step 141 ($t = 0.211$), EY, cell 1, $x = -3.192$—the left-wall
  window edge, the runaway's arrival point, not a wall-layer failure.
- The force is not the driver: the force-OFF variant crashes at step 140
  ($t = 0.210$).
- The instability scales with $\lambda_t$: $\lambda_t = 0.05$ and 0.01 survive
  $t = 0.3$; the crash threshold is $\lambda_t \gtrsim 0.05$ on this field
  content.

The $\lambda_t = 0$ no-op is bit-exact, and the copied runner's base path is
bit-exact vs `run_r3`. **C2 stays open.** A re-test needs a pre-registered
change of the term's regularization—a flux-limited (positivity-preserving)
form, or a rate $\lambda_t \le 0.05$—before the Pearson and conservation
statistics can be defined on this harness.

### 3.9 P3—the parity-odd force channel (brief 70): live

The 3D probe tested the C3 linear form
$F_{\text{mod}} = \Pi\nabla\Phi(1 - \chi G/J_{\text{scale}})$ on the TS6 helix
geometry ($\pm\Omega_0$, $N = 48$, $\lambda = 0.05$, $t = 40 = 2/\lambda$, gate
`five`), with $G = (\nabla\times J)_z$ in box labels (the axial component; the
sign convention recorded and verified bit-exact) and $\chi = \varphi^{-1}$
**asserted**—C3 remains non-closable as doctrine, and the probe is a
falsifier, not an adoption. The dimensional analysis closed on the
state-built normalization: $J_{\text{scale}} = \lambda\rho\ell$ and
$\lambda\rho$ fail on dimension, $\rho^2/\ell^2$ closes, and the chosen form
$J_{\text{scale}} = \max|G|$ at $t = 0$—$0.1718\ [\rho^2]/[L^2]$—is the
$\rho^2/\ell^2$ object at the wake scale up to an $O(1)$ prefactor
(mirror-invariant; no new constant). The pointwise twist-per-rung object
$G\ell^2/R^2$ stays $O(1)$ throughout (time-max 4.078 in every arm).

Acceptance 6/6: the $\chi = 0$ layer is a bit-exact no-op over 40,000 steps
($\max|\Delta| = 0.0$); $G$ agrees with the analytic curl to 2.5e-14 and is
bit-equal to $-g_{\text{axial}}$; the derived mirror baselines hold at
4.3e-16 / 3.2e-14 / 1.75e-14. The statistic $T$ (the $E$-weighted mean axial
flux through the mid-plane):

| arm | $T$ |
|---|---|
| base | $+5.421\times10^{-14}$ |
| mod(+) | $-3.016152\times10^{-6}$ |
| mod(−) | $+3.016152\times10^{-6}$ |
| OFF | $+9.78\times10^{-25}$ |

$dT(+) = -3.0161524\times10^{-6}$, $dT(-) = +3.0161524\times10^{-6}$:
presence holds on both sides, and $r_{\text{mir}} = -dT(-)/dT(+) =
0.99999999996$—mirror-antisymmetric to 4e-11, inside the $\pm 20\%$ band.
$\max|\chi G/J_{\text{scale}}| = 0.618 \le \chi$ throughout, with **0 cells
beyond the sign-definiteness bound** in either mod arm.

**Verdict: LIVE**—the parity-odd force channel exists at the
$\chi = \varphi^{-1}$ one-rung scale on the TS6 geometry. $|dT(\pm)| =
3.02\times10^{-6}$ exceeds the canonical null floor (the base arm's own drift,
$5.4\times10^{-14}$) by 8 orders of magnitude ($5.6\times10^7\times$); the OFF
arm is a degenerate zero-null (the 3D solver freezes $u$ exactly without the
force), so the base floor is the discriminating one, and the $\chi = 0$ no-op
being bit-exact places the response entirely in the layer term. The
antisymmetry is construction-level: the mod(−) trajectory is the mirror of
mod(+), and $r_{\text{mir}}$ certifies the construction's mirror consistency
at 4e-11—the strongest mirror reading in the lineage (11 digits vs the
conversion sector's 4e-7). The filament observables are
modulation-insensitive ($\text{Tw}_{\text{end}}$ 0.44795 vs 0.44796;
$d_{\text{end}}$ 14.2835 vs 14.2824; the pair's escape proceeds identically in
the force arms, while the OFF arm holds $d$ at 12.03)—the axial flux is the
force-side probe. **$\chi$ remains asserted; the coupling is not derived.**

### 3.10 P4—the rung-sum post-process (brief 71): inconclusive; the reduction confirmed

From the canonical lattice-stack records (`runs/20260807_152844_lattice_stack/`;
baseline reproduced bit-for-bit: Pearson $+0.5132$ / Spearman $+0.7714$,
$n = 6$, $R > 0$ arms), the rung-summed force reading
$F_{\text{tot}}(W) = \sum_j \varphi^{-j}F_j$ (double-suppression reading,
matching the cell-mean refinement) does not meet its pre-registered bar:

- Spearman$(F_{\text{tot}}(8), r) = +0.6000$ vs the bar 0.72 (the "within
  0.05" window around the baseline); Pearson $+0.698$—the linear reading is
  stronger than the baseline's, the rank order worse. The rank disagreements
  are m4_2pi5 (highest retention 0.9891 with mid $F_{\text{tot}}$) and
  m8_pi5. Bootstrap 95% CI $[-0.800, +1.000]$ overlaps zero. The $W$
  sensitivity is flat (4/8/16 all $+0.600$).
- **The C2 direction is not visible in the stack-mean object**:
  Spearman$(\langle C\rangle_{\text{stack}}, r) = -0.0286$ (Pearson
  $+0.264$); the unweighted coverage-mean of $-\partial_zJ_z$ vanishes
  identically on the periodic box (a boundary term—the documented trap), and
  the per-layer $C_j$ alternate convergence and divergence within every stack,
  so the C2 statement is genuinely local; a stack-mean reduction may be the
  wrong object—a future probe's question.
- **The multiscale sum adds no rank information over the resolved window**:
  Spearman$(F_0, r) = +0.6571$, slightly above $F_{\text{tot}}$'s $+0.6000$,
  with the per-stack fractional difference $|F_{\text{tot}}(8) - F_0|/F_{\text{tot}}(8)
  = 0.28$–$0.54$.

The 67-P4 convergence check is **CONFIRMED**: the deep-rung correction at
$W = 8$ is 4.99e-5 (m16_2pi5; 0.000 on the other arms) against the arm-to-arm
scatter of $F_{\text{tot}}(8)$, 0.462—four orders below; share$(W = 8) =
0.98684$ and $T_{\text{inc}}/S = 0.65\%$—the multiscale-law reduction (the
resolved window dominates) is supported at $n = 6$. **Verdict: INCONCLUSIVE**
(not supported, not refuted: the correlation is genuinely positive, just
sub-bar).

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

C2's prediction for the lattice-stack retention record (the envelope-retention
correlation with $|J_z|(0)$: Pearson $+0.51$, Spearman $+0.77$, $n = 6$;
`hypotheses/two-strand-five-channel-matter-organization.md` §3.8) is

$$\text{retention} \sim \frac{1 + c_2\langle C\rangle_{\text{stack}}\,t}{1 + c_2\langle C\rangle_{\text{base}}\,t},$$

with convergence ($C > 0$) piling density at the accumulating sites. The
measured test (P4, §3.10) is inconclusive at the stack-mean level: the C2
direction is not visible in the stack-mean object (Spearman $-0.03$), the
unweighted coverage-mean of $-\partial_zJ_z$ vanishes identically on the
periodic box, and the per-layer $C_j$ alternate convergence and divergence
within every stack—so the C2 statement is genuinely local, and a stack-mean
reduction may be the wrong object. The rung-summed force reading adds no rank
information over the resolved window ($F_{\text{tot}}(8)$ ranks $+0.60$ vs
$F_0$'s $+0.66$), while the multiscale reduction itself is confirmed (the
deep-rung correction at $W = 8$ is four orders below the arm scatter).
C2 is mass-conserving—it redistributes density, it cannot create a potential
well—consistent with the no-binding records (the TS1 escape and the wake-binding
and lattice-stack nulls).

---

## 5. Open Items

1. **The object form and the response curve—closed, measured.** The flow
   factor's object is $C = -\nabla\cdot J$ (CONFIRMED-object, §3.5: only $C$'s
   sign tracks under 68's tree; $|C|$ violates the sign-definiteness bound on
   its weighted mean, 2.77 ≥ 1, and responds with the wrong sign; the gated
   $(1-q)C$ responds −6.9 with a positive mean). The response curve is linear:
   $dU/U = -36.05\,\kappa$ over $[\varphi^{-2}, \varphi]$ ($m = 1.005 \pm
   0.001$, $A = -36.05 \pm 0.02$, max rel res 0.15%, no saturation), with
   $\kappa = \varphi^{-1}$ landing at $dU/U = -22.22$ (68's datum, reproduced
   bit-identically). The 192× magnitude amplification is $\kappa$-independent—it
   lives in the transport coupling $A$, a **measured transport constant** of
   the closure arm, not a parameter and not a derived value. The
   sign-definiteness bound holds on the weighted mean (0.116 < 1) but is
   violated on 95.2% of the weighted steps at $x^*$ at $\kappa = \varphi^{-1}$.
   $\kappa$ itself is not fitted.
2. **The surge form—open.** UNDETERMINED on the 14-point set (§3.6): all six
   pre-registered families fail their bars (best: the 3-parameter damped power
   at 51.2%, 25× above the 2% bar); the $\lambda_0 \approx 0.1$ saturation
   family does not survive the extended set. New structure: the small-$\lambda$ dip
   ($P$ decreases over $[0.01, 0.02]$; local slopes −0.020/−0.028) and the
   large-$\lambda$ slope falling to 0.965 (the saturation tail is visible; the form is
   not).
3. **The boundary scale—closed, measured number.** $\lambda_{\text{gate}} =
   0.02242$ (§3.7, fine-scan zero crossing of $m(\lambda)$, tight straddle
   0.022 → 0.023; the gate holds at 0.021–0.022 and fails from 0.023, crisp).
   The $\lambda/4 = 1/(8w)$ candidate is **rejected** at the pre-registered
   tolerance (10.33% outside the ±10% window; margin 0.33 points). The ON-side
   scale is confirmed not the limiter: $\lambda^* = 0.0443$,
   $\lambda^*/\lambda_{\text{gate}} = 1.98$.
4. **C2's density-transport leg—open.** INCONCLUSIVE with the mechanism
   corrected (§3.8): the wall layer was not the limiting factor (the W = 16
   half-cosine window removes it: 22.76 → 7.84 at $t = 0$); the C2 term at
   $\lambda_t = 0.1$ is unstable on the interior field content
   ($|\partial_x(qJ_z/\rho)| \sim O(8)$ intrinsic, grown 14× by $t = 0.15$;
   first NaN at step 141, $t = 0.211$, EY, cell 1, $x = -3.192$; the force-OFF
   variant crashes at step 140—the force is not the driver; $\lambda_t = 0.05$
   and 0.01 survive $t = 0.3$—the instability scales with $\lambda_t$). A
   re-test needs a pre-registered regularization change: a flux-limited form
   or $\lambda_t \le 0.05$.
5. **The parity-odd channel (P3)—run, live.** The C3 force modulation exists
   at the $\chi = \varphi^{-1}$ one-rung scale on the TS6 geometry (§3.9):
   $|dT| = 3.02\times10^{-6}$, 8 orders above the canonical floor, with
   $r_{\text{mir}} = 0.99999999996$ and the sign-definiteness bound respected
   everywhere. $\chi$ remains **asserted**—the probe measured the channel, not
   the coupling; C3 stays non-closable as doctrine.
   **The rung-sum reading (P4)—run, inconclusive.** $F_{\text{tot}}(8)$ ranks
   below the pre-registered bar (0.60 vs 0.72), the C2 direction is not visible
   in the stack-mean object (−0.03), and the multiscale sum adds no rank
   information over the resolved window ($F_0$ alone ranks 0.66); the
   multiscale-law reduction itself is confirmed (deep-rung correction 4.99e-5
   vs the arm scatter 0.462 at $W = 8$; share 0.98684; $T_{\text{inc}}/S =
   0.65\%$).
6. The law remains a candidate skeleton: the quantitative content is now the
   object form, the linear response curve, and the measured boundary, with the
   surge form and the C2 leg open. $\kappa$ is never fitted; $A = -36.05$ is a
   measured transport constant, not a parameter and not a derived value.

---

## References

- `foundations/cassi-first-principles.md`—two-fluid PDE, the conversion term, the $\varphi$-attractor
- `foundations/cassi-theory-reference.md` §4.3—the chord law $G_{\text{eff}} = G(\pi/\rho)(1+(\varphi^{6}-1)q)$
- `foundations/spiral-dynamics.md` §3—gravity as $\Pi\nabla\Phi$ gradient descent; the field force and its sign
- `foundations/cascade-suppression-formula.md` §1—the derived per-rung damping $d_i \approx \varphi^{-1}$ ($\kappa$'s receipt)
- `gravity/three-body-analytical.md` §2—the point-particle reduction; the attractive convention
- `hypotheses/two-strand-five-channel-matter-organization.md` §3—the sign-following measurements (TS1, Yin-excess) and the lattice-stack records
- `gravity/quantum-gravity.md`—the $\sigma$-regularized black-hole sector (registry G3)

The derivation and probe record is the spiral-gravity program's briefs 67–71
(`67-gravity-from-flow-laws.md`, `68-river-probes.md`, `69-river-wave2.md`,
`70-parity-odd-force.md`, `71-rung-sum.md`, with the machine receipts
`run67_output.txt`, `run68_output.txt`, `run68_river_probes_results.json`,
`run69_output.txt`, `run69_river_wave2_results.json`, `run70_output.txt`,
`run70_parity_odd_results.json`, `run71_output.txt`,
`run71_rung_sum_results.json`). Those briefs live outside this repo
(cassi-toe-rewrite-briefs/) and are cited by name; every measured number in
§3 traces to them.
