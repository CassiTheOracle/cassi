# The Two-Fluid Phase Operator: Step 1 of the Hilbert–Pólya Program

## Status: Speculative—August 2026

## Abstract

Step 1 of `riemann-two-fluid-spectral-program.md` is executed: the linearized
phase dynamics of the two-fluid core around the Yang-Yin balanced state is
written down, reduced to the scale variable $u = \ln r$, and its spectral
problems are solved. Three derived facts: (i) the Yang-Yin phase fluctuation
around the $\varphi$-attractor is **massive**, $m_\theta^2 = 4\lambda\varphi
R_0^2$—the attractor potential explicitly breaks the SO(2) rotation, so the
phase is not a Goldstone mode; (ii) in the massless (current-conserving)
sector on the self-similar background $R_0 = A\,r^{-s}$, the radial reduction
produces the normal form
$\tilde\varphi'' + \left[E^2 e^{2u} - \kappa^2\right]\tilde\varphi = 0$ with
$\kappa = |s - \tfrac{1}{2}|$, and $\kappa = 1$ for the scale-free
three-dimensional background ($s = 3/2$, $D = 3$)—the Bessel index of the
operator is exactly $1$ in the framework's natural background; (iii) the
exact spectra of this operator are **Bessel**: the interior cavity (regular at
$r = 0$, wall at $r = L$) has eigenvalues $E_n = j_{\kappa,n}/L$ (the zeros of
$J_\kappa$), the exterior problem has continuous spectrum, and the box counts
Weyl-linearly, $N(E) \sim (E/\pi)(e^U - 1)$. The acceptance test fails at
leading order: all exact counting functions are linear in $E$, while the
Riemann–von Mangoldt count is logarithmic. The logarithmic shape appears only
semiclassically—the truncated-hyperbola phase space gives
$N(E) = (E/2\pi)\ln(E/(L p_{\min})) - E/2\pi + Lp_{\min}/2\pi$, forcing
$Lp_{\min} = 2\pi$ (order-unity; no $\varphi$-power) and leaving the constant
one-eighth above the theorem's $7/8$ (the corner phase). Every claim is
verified numerically (`run_phase_operator_check.py`). The exact realization
of the zeros requires the energy-dependent boundary of the
Sierra–Rodríguez-Laguna type; Step 2b executes that investigation. The unique
moving wall reproducing R-vM is $L(E) = \tfrac{1}{2}\ln(E/2\pi e) +
9\pi/(8E)$, whose argument is the Riemann–Siegel $\Gamma$-phase
($E\,L(E) = \theta(E) + 5\pi/4$, verified); all three framework candidates
for supplying it—fixed rung walls, Qi-gated masses, and the IIR
$\tau = \varphi^{-1}$ boundary (a $\varphi$-locked lattice $E_n = n\omega_0$)—
are excluded by computation and by the measured null. The boundary is
identified, and it is external to the two-fluid dynamics.

---

## 1. The Polar Reduction of the Two-Fluid Core

The two-fluid core of `foundations/unified-lagrangian.md` is a real SO(2)
doublet $\Psi = (\Psi_0, \Psi_1)$ with kinetic term $\tfrac{1}{2}(\partial\Psi)^2$
and the $\varphi$-attractor potential
$V = \tfrac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$. In polar form
$\Psi_0 = R\cos\theta$, $\Psi_1 = R\sin\theta$:

$$L_{\text{TF}} = \frac{1}{2}(\partial R)^2 + \frac{R^2}{2}(\partial\theta)^2
- \frac{g}{4}R^4 - \frac{\lambda}{2}R^4\left(\cos^2\theta - \varphi\sin^2\theta\right)^2$$

The attractor $\Psi_0^2 = \varphi\Psi_1^2$ fixes the equilibrium angle

$$\boxed{\theta_{\text{eq}} = \arctan\varphi^{-1/2} \approx 0.6577\ \text{rad}}$$

The field $R$ is the magnitude (the framework's $\rho$), and the angle
$\theta$ is the Yang-Yin phase—the phase current
$J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0 = R^2\nabla\theta$ of
`foundations/cassi-first-principles.md` §2.2 is the gradient of this
phase.

## 2. The Phase Fluctuation Is Massive

Linearize the $\theta$ equation of motion
$\partial_\mu(R^2\partial^\mu\theta) = -\lambda R^4 f(\theta) f'(\theta)$,
$f = \cos^2\theta - \varphi\sin^2\theta$, around $\theta_{\text{eq}}$
($f(\theta_{\text{eq}}) = 0$, $f'(\theta_{\text{eq}}) = -2\sqrt{\varphi}$):

$$\boxed{\partial_\mu\!\left(R_0^2\,\partial^\mu\delta\theta\right)
+ 4\lambda\varphi R_0^4\,\delta\theta = 0}$$

or in standard form, dividing by $R_0^2$,

$$\partial_t^2\delta\theta - \Delta\delta\theta
- 2(\nabla\ln R_0)\cdot\nabla\delta\theta
+ 4\lambda\varphi R_0^2\,\delta\theta = 0
\qquad\Rightarrow\qquad
m_\theta^2 = 4\lambda\varphi R_0^2$$

The phase fluctuation is massive: the $\varphi$-attractor potential breaks the
SO(2) rotation explicitly, so $\theta$ is not a Goldstone mode. With the
framework's derived $\lambda = 0.1$ the mass is small at low $R_0$ but
structurally present; the spectral machinery of the program lives in the
massless sector.

## 3. The Massless Sector: Reduction to the Scale Operator

Set $\lambda = 0$ (the current-conserving limit $\partial_\mu(R_0^2
\partial^\mu\theta) = 0$) on the static self-similar background
$R_0 = A\,r^{-s}$. For the s-wave, $\theta = e^{-iEt}\psi(u)$, $u = \ln r$:

$$\psi'' - (1+2s)\,\psi' + \left(2s + E^2 e^{2u}\right)\psi = 0$$

Removing the first-derivative term with $\psi = e^{(1+2s)u/2}\,\tilde\varphi$
gives the normal form

$$\boxed{\tilde\varphi'' + \left[E^2 e^{2u} - \kappa^2\right]\tilde\varphi = 0,
\qquad \kappa = \left|s - \tfrac{1}{2}\right|}$$

The constant $\kappa$ is the Bessel index of the operator. For the scale-free
background in three dimensions—energy density $R_0^2 \propto r^{-3}$, so
$s = D/2 = 3/2$ (`foundations/why-three-dimensions.md`)—

$$\boxed{\kappa = 1 \quad (D = 3)}$$

The Bessel index is exactly $1$ in the framework's natural background. (The
$s = 0$ free-wave limit gives $\kappa = 1/2$: solutions
$J_{1/2}(Ee^u) \propto \sin(Ee^u)/\sqrt{Ee^u}$, the standard radial wave,
correctly reproduced.)

## 4. The Exact Spectra

The eigenfunctions are Bessel functions of the scale variable,
$\tilde\varphi(u) = J_\kappa(Ee^u)$ and $Y_\kappa(Ee^u)$. Three boundary
problems exhaust the natural options:

1. **Interior cavity** (regular at $r \to 0$, Dirichlet wall at $r = L$):
   only $J_\kappa$ survives regularity, and the wall quantizes
   $$E_n = \frac{j_{\kappa,n}}{L}, \qquad J_\kappa(j_{\kappa,n}) = 0$$
   with $j_{1,1} = 3.8317$, $j_{1,2} = 7.0156$, $j_{1,3} = 10.1735$. The
   counting is linear, $N(E) \approx EL/\pi$ (Weyl).
2. **Exterior walled problem** ($r \ge L$, the UV wall): $J_\kappa(Ee^u)$
   oscillates as $u \to \infty$ without decay—no $L^2$ eigenstates;
   continuous spectrum. The finite-box approximation has eigenvalues with
   mean spacing $\pi/(e^U - 1) \to 0$ as the box widens: the spectrum
   collapses to the continuum.
3. **Box** $[0, U]$ in $u$: Weyl-linear counting
   $N(E) \approx (E/\pi)(e^U - 1)$, verified to $0.2\%$ at $E = 100$.

None of the three is the zero spectrum.

## 5. The Acceptance Test: Linear vs Logarithmic

The program's Step 2 requires the counting function to reproduce
Riemann–von Mangoldt. The exact counting of every spectral realization of
§4 is **linear** in $E$. The zero count is **logarithmic**:

| $E$ | box count (exact) | Weyl linear | R-vM logarithmic |
|-----|-------------------|-------------|------------------|
| 25 | 50 | 50.8 | 2.4 |
| 50 | 101 | 101.7 | 9.4 |
| 100 | 203 | 203.4 | 29.0 |

The naive two-fluid phase operator **fails the acceptance test at leading
order**—by a factor of 7–20 across this range. The failure is structural,
not numerical: a linear density of states cannot produce the
$(1/2\pi)\ln(E/2\pi)$ density of the zeros.

## 6. The Semiclassical Constraint

The logarithmic shape survives in the semiclassical (phase-space) count of
the truncated hyperbola $xp \le E$ with the lower walls $x \ge L$, $p \ge
p_{\min}$:

$$N(E) = \frac{E}{2\pi}\ln\frac{E}{L p_{\min}} - \frac{E}{2\pi}
+ \frac{L p_{\min}}{2\pi}$$

Matching the logarithm to the theorem pins the cutoff product:

$$\boxed{L\,p_{\min} = 2\pi}$$

an order-unity constraint with **no $\varphi$-power**—no cascade rung enters
the arithmetic boundary (consistent with the one-rung reading of
`riemann-hypothesis-de-resonance.md` §3). The constant term comes out at
$Lp_{\min}/2\pi = 1$, one-eighth above the theorem's $7/8$: the difference is
the corner/reflection phase, repaired by the exact spectral construction in
the Berry–Keating/Sierra–Rodríguez-Laguna treatment—a known mechanism with no
$\varphi$ content. The framework's $\kappa$ enters only at order $E^{-1}$
through the wall reflection phase; it does not reach the $7/8$.

## 7. Numerical Verification

Script `experiments/riemann_phi_search/run_phase_operator_check.py`
(reproduces every number above):

- **ODE residual**: $J_\kappa(Ee^u)$ solves the normal form to machine
  precision ($10^{-12}$–$10^{-14}$) for $\kappa \in \{\frac{1}{2}, 1, 2\}$.
- **Interior cavity**: residual $2\times10^{-15}$ at $E = j_{1,1}$; the
  eigenvalue formula $E_n = j_{\kappa,n}/L$ is analytic (regularity at $r=0$
  kills $Y_\kappa$), and the Bessel zeros match
  $\pi(n + \kappa/2 - 1/4)$ asymptotically.
- **Exterior box**: independent shooting of the radial ODE
  $\psi'' + 2(1-s)\psi'/r + E^2\psi = 0$ ($s = 3/2$) matches the
  characteristic equation to $10^{-13}$; first eigenvalues
  $\{0.5448, 1.0217, 1.5042\}$; spacing $\to 0$ as the box widens
  ($0.484 \to 0.058$ for $U = 2 \to 4$, against $\pi/(e^U - 1)$).
- **Counting**: box counts 50/101/203 at $E = 25/50/100$, matching the Weyl
  law $50.8/101.7/203.4$; the Riemann–von Mangoldt values 2.4/9.4/29.0 are
  not approached.

## 8. Step 2b: The Energy-Dependent Boundary

Step 1 established that fixed walls count linearly. The logarithmic shape
requires a wall whose position depends on the energy. The unique moving wall
that reproduces Riemann–von Mangoldt is determined by the acceptance test
itself. With the cavity counting $N(E) = \#\{n : j_{1,n} \le E\,L(E)\}$ and
the Bessel asymptotics $j_{1,n} \approx \pi(n + \tfrac{1}{4})$, the condition
$N(E) = \bar N(E)$ fixes

$$\boxed{L(E) = \frac{1}{2}\ln\frac{E}{2\pi e} + \frac{9\pi}{8E}}$$

The $9/8$ is the corner phase; the $\tfrac{1}{4}$ is the Bessel phase
($\kappa/2 - 1/4$ with $\kappa = 1$); together they land exactly on the
theorem's $7/8$: $\tfrac{9}{8} - \tfrac{1}{4} = \tfrac{7}{8}$. The wall
argument is the Riemann–Siegel theta:

$$E\,L(E) = \theta(E) + \frac{5\pi}{4}$$

verified to $2\times10^{-4}$ at $E = 100$ and $10^{-5}$ at $E = 2000$; the
counting tracks $\bar N(E)$ to within one state over $E \in [20, 2000]$
(`experiments/riemann_phi_search/run_phase_boundary_check.py`). This is the Sierra–Rodríguez-Laguna insight
restated in the framework's operator language: **the boundary phase of the
zero problem is the $\Gamma$-phase**. The moving wall is not a framework
structure—it is the Riemann–Siegel theta in disguise.

The three framework candidates for supplying this boundary are excluded:

1. **$\sigma$-regularization at a cascade rung** (any fixed wall): linear
   counting, Step-1 acceptance test. Excluded.
2. **Qi-gated, energy-dependent conversion** (mass $m_\theta(E)$): a mass
   term perturbs the Weyl law of a fixed domain at order $V/E^2$; it cannot
   change the leading linear counting, and it does not move the wall.
   Excluded.
3. **IIR memory timescale $\tau = \varphi^{-1}$** as a boundary period in
   $u$ of length $\ln\varphi$ (the identification $x \to \varphi x$): the
   spectrum is the $\varphi$-locked lattice $E_n = n\,\omega_0$,
   $\omega_0 = 2\pi/\ln\varphi = 13.057$, with density $1/\omega_0 = 0.0766$.
   The zeros' measured density is $1.335$—a factor 17 denser—and only 2.6%
   of the first 100,000 zeros lie within 0.2 of the lattice, statistically
   identical to a phase-shifted control (3.3%). The $\tau$ candidate is
   excluded on density and by measurement; it is also exactly the
   log-periodic structure the null test of `riemann-hypothesis-de-resonance.md`
   §4 rejects ($dAIC = +4.00$, $p_{\text{spec}} = 0.68$).

What remains is a selection rule, not a derivation: among all boundary
phases, the one the zeros actually realize is the $\Gamma$-phase of
$\theta(E)$—the phase that makes the spectrum maximally de-resonant (no
locked frequency, minimal fluctuation). The framework's de-resonance
principle says the arithmetic boundary is the maximally de-resonant one; its
measured signatures are the GUE featurelessness of the spacings, Selberg's
mean-square minimality, and Gram's law at 79.4%.

## 9. Status of the Program

- **Step 1 (write the operator): done.** The massless phase fluctuation on
  the balanced self-similar background reduces to the Bessel-index-1 scale
  operator in $D = 3$. The phase is massive in general ($m_\theta^2 =
  4\lambda\varphi R_0^2$); the massless sector is the spectral candidate.
- **Step 2 (acceptance test): done, failed at leading order.** All exact
  spectra count linearly; the zeros count logarithmically. The logarithmic
  shape is semiclassical and requires the energy-dependent boundary of the
  Sierra–Rodríguez-Laguna construction.
- **Step 2b (the energy-dependent boundary): done, negative.** The unique
  moving wall reproducing R-vM is $L(E) = \tfrac{1}{2}\ln(E/2\pi e) +
  9\pi/(8E)$—the boundary phase is the Riemann–Siegel $\Gamma$-phase
  ($E\,L(E) = \theta(E) + 5\pi/4$, verified). None of the framework's
  structures supplies it: fixed rung walls and Qi-gated masses keep linear
  counting; the IIR $\tau = \varphi^{-1}$ boundary gives a $\varphi$-locked
  lattice $E_n = n\omega_0$ excluded by density and by the measured null.
  The de-resonance selection rule (the boundary is the maximally de-resonant
  phase) remains a research statement, not a derivation.
- **The durable content:** the operator, its Bessel spectrum, the
  semiclassical pinning $Lp_{\min} = 2\pi$ with the $1/8$ corner-phase gap,
  and now the explicit form of the required boundary with the three
  candidate exclusions. The naive routes through the framework's existing
  structures are excluded by verified computation; the $\Gamma$-phase
  boundary itself is identified, and it is external to the two-fluid
  dynamics.

---

## References

- `riemann-two-fluid-spectral-program.md`—the program this document executes (Step 1)
- `riemann-hypothesis-de-resonance.md`—the de-resonance reading and the φ-periodicity null test
- `foundations/unified-lagrangian.md`—the two-fluid core Lagrangian
- `foundations/cassi-first-principles.md`—field equations, phase current, attractor
- `foundations/why-three-dimensions.md`—$D = 3$ (hence $s = 3/2$, $\kappa = 1$)
- Berry, M. V. and Keating, J. P., "The Riemann zeros and eigenvalue asymptotics," SIAM Review 41 (1999) 236–266
- Sierra, G. and Rodríguez-Laguna, J., "The Riemann zeros as spectrum of a Hamiltonian," J. Phys. A 44 (2011) 305204
- `experiments/riemann_phi_search/run_phase_operator_check.py`—verification of every claim in §§3–7
- `experiments/riemann_phi_search/run_phase_boundary_check.py`—moving-wall theorem and candidate exclusions (§8)
