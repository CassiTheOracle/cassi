# Qi-flow loop mass-cascade pre-registration

## Status: Preregistered—August 2026

## 1. Question

The candidate identifies Qi with organized Yang–Yin flow while retaining $q$
as its scalar coherence diagnostic. The two fluids may exchange energy and may
phase-lock under coupling, so the physical de-resonance proposal assigns their
preferred phase-gradient ratio the conventional positive representative of the
Hurwitz/Lagrange worst-approximable class,

\[
\alpha=\varphi=\frac{1+\sqrt5}{2}.
\]

The same dilation separates adjacent cascade scales. This probe asks two
questions:

1. Does a conservative closed two-fluid phase loop with $\alpha=\varphi$
   possess stable, undriven circulating sectors whose distinguished
   near-closure branch scales by $\varphi$?
2. Does de-resonance plus loop closure determine unique dimensionless mass
   positions inside those scale intervals?

The ring topology and its phase-only Hamiltonian are supplied test
architecture. A positive result establishes no spontaneous ring formation,
open-space localization, Standard Model particle identification, or physical
mass normalization.

## 2. Frozen arithmetic sector

Let $p,q_{\mathrm w}\in\mathbb Z_{>0}$ be Yang and Yin winding numbers.
Their preferred phase-gradient ratio is $q_{\mathrm w}/p=\alpha$. Here
$q_{\mathrm w}$ denotes an integer winding and is distinct from the canonical
scalar coherence diagnostic $q$. Define

\[
d_\alpha(p,q_{\mathrm w})=|q_{\mathrm w}-\alpha p|,
\qquad
h_\alpha(p,q_{\mathrm w})=p\,d_\alpha(p,q_{\mathrm w}).
\]

For each denominator $1\le p\le144$, choose the nearest positive integer
$q_{\mathrm w}$, selecting the larger integer at an exact half-integer, and
retain a record when $d_\alpha$ is strictly smaller than every preceding record
by more than $10^{-15}$.

For $\alpha=\varphi$, the frozen expected record list is

\[
(1,2),(2,3),(3,5),(5,8),(8,13),(13,21),(21,34),
(34,55),(55,89),(89,144),(144,233).
\]

For consecutive Fibonacci numbers,

\[
F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}.
\]

Controls use

\[
\alpha_R=\frac32,
\qquad
\alpha_I=\sqrt2.
\]

The rational control has exact closure at $(p,q_{\mathrm w})=(2,3)$. The
final $\sqrt2$ record under the denominator cap is $(70,99)$.

### Stage A gates

- **A1—Fibonacci identity:** for $n=2,\ldots,12$, the maximum absolute
  residual in

  \[
  F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}
  \]

  is below $10^{-12}$.
- **A2—record sequence:** the computed $\varphi$ record list equals the
  frozen list exactly.
- **A3—rational closure:** $d_{3/2}(2,3)<10^{-15}$ (absolute).
- **A4—finite de-resonance control:** at the final declared records,

  \[
  h_\varphi(144,233)-h_{\sqrt2}(70,99)\ge0.08.
  \]

Stage A is `PASS` only when A1–A4 pass.

## 3. Frozen conservative loop

Let $s\in[0,L]$ parameterize a closed loop. The two compact phases satisfy

\[
\theta_Y(s+L)=\theta_Y(s)+2\pi p,
\qquad
\theta_I(s+L)=\theta_I(s)+2\pi q_{\mathrm w}.
\]

The supplied positive phase-only Hamiltonian is

\[
\begin{aligned}
H_\alpha[\theta_Y,\theta_I,L]
={}&T L\\
&+\frac12\int_0^L\left[
K_Y(\partial_s\theta_Y)^2
+K_I(\partial_s\theta_I)^2
+K_\Delta(\partial_s\theta_I-\alpha\partial_s\theta_Y)^2
\right]ds.
\end{aligned}
\]

$T$ has energy-per-length units and each $K$ has energy-times-length
units. The probe uses dimensionless normalized units

\[
T=K_Y=K_I=K_\Delta=1.
\]

These values define the test architecture and are not adopted Cassi
parameters.

The uniform winding solution is

\[
\theta_Y=\frac{2\pi p}{L}s,
\qquad
\theta_I=\frac{2\pi q_{\mathrm w}}{L}s.
\]

Define

\[
A_\alpha(p,q_{\mathrm w})
:=K_Yp^2+K_Iq_{\mathrm w}^2+K_\Delta(q_{\mathrm w}-\alpha p)^2.
\]

Then

\[
H_\alpha(L;p,q_{\mathrm w})=TL+\frac{2\pi^2A_\alpha(p,q_{\mathrm w})}{L},
\]

with stationary length and energy

\[
L_*=\sqrt{\frac{2\pi^2A_\alpha}{T}},
\qquad
H_*=2\sqrt{2\pi^2T A_\alpha},
\]

and

\[
\left.\frac{\partial^2H}{\partial L^2}\right|_{L_*}
=\frac{4\pi^2A_\alpha}{L_*^3}>0.
\]

The phase-gradient Hessian is

\[
G_\alpha=
\begin{pmatrix}
K_Y+\alpha^2K_\Delta & -\alpha K_\Delta\\
-\alpha K_\Delta & K_I+K_\Delta
\end{pmatrix}.
\]

The two conjugate phase currents are

\[
J_Y=(K_Y+\alpha^2K_\Delta)\partial_s\theta_Y
-\alpha K_\Delta\partial_s\theta_I,
\]

\[
J_I=(K_I+K_\Delta)\partial_s\theta_I
-\alpha K_\Delta\partial_s\theta_Y.
\]

They are spatially constant on the uniform solution. Their divergences vanish
while their joint Euclidean norm remains nonzero for every declared winding
pair.

For a conditional scale-covariance arm, set

\[
T_N=\varphi^{-2N}T_0,
\qquad
K_{Y,N}=K_{Y,0},
\qquad
K_{I,N}=K_{I,0},
\qquad
K_{\Delta,N}=K_{\Delta,0}.
\]

This supplied scaling predicts

\[
L_{*,N}=\varphi^N L_{*,0},
\qquad
H_{*,N}=\varphi^{-N}H_{*,0}.
\]

### Stage B gates

Evaluate every $\varphi$ record pair and both control record lists.

- **B1—stationarity:**

  \[
  \frac{|T-2\pi^2A/L_*^2|}{\max(T,2\pi^2A/L_*^2)}<10^{-12}.
  \]
- **B2—radial stability:** $\partial_L^2H|_{L_*}>0$, and both
  $H(0.99L_*)$ and $H(1.01L_*)$ exceed $H(L_*)$.
- **B3—phase stability:** the minimum eigenvalue of $G_\alpha$ is positive.
- **B4—stationary circulation:** the maximum absolute finite-difference
  divergence of $(J_Y,J_I)$ on a 256-point periodic ring is below $10^{-12}$,
  while the minimum current norm is above $10^{-12}$.
- **B5—conditional scale covariance:** for $N=0,\ldots,8$, the maximum
  relative residuals in the displayed $L_{*,N}$ and $H_{*,N}$ laws are below
  $10^{-12}$.

Stage B is `PASS` only when B1–B5 pass. A pass establishes stability inside
the supplied ring topology. It supplies no open-space binding result because
the phase-staggered scale-gap campaign finds phase-only coupling gapless.

## 4. Frozen mass-position sufficiency test

In normalized units, define the loop mass proxy

\[
m^{\rm loop}_{p,q_{\mathrm w}}=H_*(p,q_{\mathrm w}).
\]

This is a classical rest-energy proxy with $c=1$. The probe makes no
single-quantum identification $H_*=\hbar\Omega$.

### 4.1 Topological multiplicity

Enumerate every primitive pair

\[
1\le p\le34,
\qquad
1\le q_{\mathrm w}\le55,
\qquad
\gcd(p,q_{\mathrm w})=1.
\]

Let $H_{\min}$ be the smallest mass proxy in this set and assign the scale-cell
coordinate

\[
x_{p,q_{\mathrm w}}=\log_\varphi\!\left(\frac{H_*(p,q_{\mathrm w})}{H_{\min}}\right),
\qquad
c_{p,q_{\mathrm w}}=\lfloor x_{p,q_{\mathrm w}}\rfloor.
\]

Count the number of stable primitive modes in every occupied cell $c$.

- **C1—unique-mode sufficiency:** C1 passes only if every occupied cell
  contains exactly one stable primitive mode.

### 4.2 Constitutive sensitivity

For the frozen $\varphi$ record branch, use

\[
K_\Delta\in\{0,0.25,1,4\},
\qquad
T=K_Y=K_I=1.
\]

Anchor every arm at $(p,q_{\mathrm w})=(13,21)$ and define

\[
y_{p,q_{\mathrm w}}(K_\Delta)
:=\log_\varphi\!\left[
\frac{H_*(p,q_{\mathrm w};K_\Delta)}{H_*(13,21;K_\Delta)}
\right].
\]

For each record pair, compute the span of $y$ across the four declared
$K_\Delta$ values.

- **C2—coefficient independence:** C2 passes only if the maximum span is no
  greater than $0.01$ rung.

### 4.3 Distinguished Fibonacci skeleton

At the baseline normalized coefficients, use consecutive record pairs
starting at $(13,21)$.

- **C3—asymptotic $\varphi$ spacing:** the maximum relative residual of
  $H_{*,n+1}/H_{*,n}$ from $\varphi$ is below $10^{-4}$.
- **C4—in-cell collapse:** after anchoring $(13,21)$ at zero, the maximum
  distance of the later record-branch $y_{p,q_{\mathrm w}}$ values from their consecutive
  integer labels is below $10^{-4}$ rung.

### Stage C decisions

- The distinguished closed-loop cascade skeleton is `SUPPORTS` if C3 and C4
  pass.
- De-resonance plus loop closure is `SUPPORTS` as a sufficient unique
  mass-position law only if C1 and C2 both pass.
- It is `CONTRADICTS` as a sufficient unique mass-position law if C1 or C2
  fails while all quality gates and Stages A–B pass.

The multiplicity and coefficient tests are structural. No particle mass,
particle name, catalog offset, fitted anchor, or post-run mode assignment may
enter the decision.

## 5. Quality gates and independent verification

- **Q1—finite:** every reported scalar and array entry is finite.
- **Q2—closed forms:** direct numerical evaluations of $L_*$, $H_*$,
  stationarity, and Hessian relations satisfy their displayed tolerances.
- **Q3—deterministic:** the primary probe uses no randomness, optimizer,
  adaptive cutoff, or parameter fit.
- **Q4—source record:** the receipt contains SHA-256 hashes of this protocol,
  the primary script, and the independent verifier.
- **Q5—independent recomputation:** the verifier imports no primary-probe
  function and recomputes every gate from this protocol. Every Boolean must
  match, and every compared finite scalar must agree within
  $10^{-12}\max(1,|x|)$.

A Q1–Q4 failure makes the primary result `INCONCLUSIVE`. A Q5 failure makes the
combined campaign `INCONCLUSIVE`.

## 6. Frozen verdict tree

The terminal outcomes are assigned separately with this exhaustive tree:

- **Closed Qi-loop skeleton:** `EMERGES CONDITIONAL` if Q1–Q5, Stages A–B,
  and C3–C4 all pass; `DOES NOT EMERGE` if Q1–Q5 pass while any of Stages A–B,
  C3, or C4 fails; otherwise `INCONCLUSIVE`.
- **Unique mass positions:** `EMERGES CONDITIONAL` if Q1–Q5, Stages A–B,
  and C1–C4 all pass; `DOES NOT EMERGE` if Q1–Q5 and Stages A–B pass while
  C1 or C2 fails; otherwise `INCONCLUSIVE`.

A closed-loop skeleton can emerge while unique mass selection does not.

## 7. Artifacts and stopping rule

The primary script is

```text
field-experience/qi_loop_mass_cascade_probe.py
```

and writes once to

```text
runs/<UTC timestamp>_qi_loop_mass_cascade/results.json
```

The independent script is

```text
field-experience/verify_qi_loop_mass_cascade.py
```

and writes beside the primary receipt as

```text
runs/<same directory>/verification.json
```

Permitted preflight is limited to source inspection and `python -m py_compile`
for both scripts. The primary probe runs exactly once. The verifier runs
exactly once against that receipt. No replacement run, threshold change,
coefficient change, winding reassignment, or catalog comparison is permitted.
