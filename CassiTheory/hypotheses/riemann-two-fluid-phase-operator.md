# The Two-Fluid Phase Operator: Step 1 of the Hilbert–Pólya Program

## Status: Speculative—August 2026

## Abstract

Step 1 of `hypotheses/riemann-two-fluid-spectral-program.md` is evaluated with an
optional reference-normalized polar extension of the canonical two-density
solver. The canonical state is the nonnegative real pair $E_Y,E_I$ with
$\rho = E_Y + E_I$, $\epsilon = E_Y - \varphi E_I$, gated rank-one
conversion, and one shared advection field; its state space carries no native
SO(2)/U(1) phase, periodic angle, phase current, chirality, or rung clock. The
extension introduces a fixed reference density $E_\star > 0$ and auxiliary
reference amplitudes $\Psi_0 = \sqrt{E_Y/E_\star}$,
$\Psi_1 = \sqrt{E_I/E_\star}$, with a compact SO(2) polar structure as an
explicit Hypothesized extension. The polar
variables and reference current are Hypothesized operators; the massive
phase-field model and its spectral construction are Speculative. The
canonical density-plane coordinate $\operatorname{atan2}(E_I,E_Y)$ remains
nonperiodic over the positive quadrant.

Under this extension, the linearized extension phase dynamics around the
Yang-Yin balanced state are written down, reduced to the scale variable
$u = \ln r$, and its spectral problems are solved. Three conditional results:
(i) the extension phase fluctuation around the $\varphi$-attractor is
**massive**, $m_\theta^2 = 4\lambda_\theta\varphi R_0^2$—the assumed SO(2) rotation
is explicitly broken by the attractor potential; (ii) in the extension's
massless (current-conserving) sector on the imposed, conditional self-similar
background ansatz $R_0 = A\,r^{-s}$, the radial reduction produces the normal
form
$\tilde\varphi'' + \left[E^2 e^{2u} - \kappa^2\right]\tilde\varphi = 0$ with
$\kappa = |s - \tfrac{1}{2}|$, and $\kappa = 1$ for the chosen scale-free
three-dimensional ansatz ($s = 3/2$, $D = 3$)—the Bessel index of this
ansatz is exactly $1$; (iii) the exact spectra of this operator are
**Bessel**: the interior cavity (regular at $r = 0$, wall at $r = L$) has
eigenvalues $E_n = j_{\kappa,n}/L$ (the zeros of $J_\kappa$), the exterior
problem has continuous spectrum, and the finite-box count is a staircase
with Weyl-linear leading term $N(E) \sim (E/\pi)(e^U - 1)$. The acceptance
test fails at leading order: the finite-box count has linear Weyl growth,
whereas the Riemann–von Mangoldt counting function grows as $E\log E$ (its
mean density is logarithmic). The $E\log E$ shape appears only
semiclassically—the truncated-hyperbola phase space gives
$N(E) = (E/2\pi)\ln(E/(L p_{\min})) - E/2\pi + Lp_{\min}/2\pi$, forcing
$Lp_{\min} = 2\pi$ (order-unity; zero $\varphi$-power) and leaving the constant
one-eighth above the theorem's $7/8$ (the corner phase; the displayed $9/8$
offset below is a chosen/Mapped ansatz coefficient). The listed ODE, cavity,
exterior, and count checks are verified numerically
(`experiments/riemann_phi_search/run_phase_operator_check.py`). The exact
realization of the zeros requires the energy-dependent boundary of the
Sierra–Rodríguez-Laguna type; Step 2b executes that investigation. On the
checked 300-point grid, the $\kappa=1$ convention uses the chosen asymptotic
moving-wall ansatz
$L(E) = \tfrac{1}{2}\ln(E/2\pi e) + 9\pi/(8E)$, whose argument is the
Riemann–Siegel $\Gamma$-phase ($E\,L(E) = \theta(E) + 5\pi/4$, verified).
This wall is unique only under the stated Bessel/count convention and is not
unique among admissible boundaries. The fixed-wall and bounded-mass statements
are analytic or conditional toy-map results, while the IIR comparison uses
the measured numerical null. The boundary is identified as external to the
canonical two-density dynamics.

---

## 1. Optional Polar Extension of the Two-Fluid Core

The canonical two-fluid state is the nonnegative real density pair $E_Y,E_I$
with $\rho = E_Y + E_I$, $\epsilon = E_Y - \varphi E_I$, gated rank-one
conversion, and one shared advection field. Its density plane is the positive
quadrant with coordinate
$\alpha = \operatorname{atan2}(E_I,E_Y) \in [0,\pi/2]$, a nonperiodic
coordinate; the canonical equations carry no native SO(2)/U(1) phase, periodic
angle, phase current, chirality, or rung clock.
The operator formulas below use natural units ($c=\hbar=1$) and metric
signature $(+,-,-,-)$. The separation parameter $E$ is an angular frequency
(radians per unit time in these units), rather than a cyclic frequency; products
such as $Er$ are dimensionless. The amplitude normalization $A$ and reference
density $E_\star$ remain explicit.

For this exploratory operator, choose a fixed reference density $E_\star > 0$
and define the auxiliary reference amplitudes
$\Psi_0 = \sqrt{E_Y/E_\star}$, $\Psi_1 = \sqrt{E_I/E_\star}$. Their squared
combinations track the canonical variables:
$\Psi_0^2 + \Psi_1^2 = \rho/E_\star$ and
$\Psi_0^2 - \varphi\Psi_1^2 = \epsilon/E_\star$. The optional reference
kinetic term is $\tfrac{1}{2}(\partial\Psi)^2$, and the optional attractor
potential is
$V = \frac{\lambda_\theta}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$. The Hypothesized
extension assumes a compact SO(2) target structure for this pair and uses the
polar chart
$\Psi_0 = R\cos\theta$, $\Psi_1 = R\sin\theta$:

$$L_{\text{TF}} = \frac{1}{2}(\partial R)^2 + \frac{R^2}{2}(\partial\theta)^2
- \frac{\lambda_\theta}{2}R^4\left(\cos^2\theta - \varphi\sin^2\theta\right)^2$$

The polar variables and this Lagrangian are reference operators at the
Hypothesized tier; the induced phase-field model and spectral construction
carry the document's Speculative tier. The extension attractor
$\Psi_0^2 = \varphi\Psi_1^2$, equivalently $\epsilon = 0$, fixes the
equilibrium angle

$$\boxed{\theta_{\text{eq}} = \arctan\varphi^{-1/2} \approx 0.6662394\ \text{rad}}$$

Within the extension, $R$ is the Euclidean auxiliary amplitude with
$R^2 = \Psi_0^2 + \Psi_1^2 = \rho/E_\star$; the canonical density variable
remains $\rho = E_Y + E_I$. The optional reference current operator is
$J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0 = R^2\nabla\theta$.
`foundations/cassi-first-principles.md` §2.2 supplies the reference form for
this extension current.

## 2. Optional Extension Phase Fluctuation Is Massive

Within the optional reference-normalized extension, linearize its $\theta$
equation of motion
$\partial_\mu(R^2\partial^\mu\theta) = -\lambda_\theta R^4 f(\theta) f'(\theta)$,
$f = \cos^2\theta - \varphi\sin^2\theta$, around $\theta_{\text{eq}}$
($f(\theta_{\text{eq}}) = 0$, $f'(\theta_{\text{eq}}) = -2\sqrt{\varphi}$):

$$\boxed{\partial_\mu\!\left(R_0^2\,\partial^\mu\delta\theta\right)
+ 4\lambda_\theta\varphi R_0^4\,\delta\theta = 0}$$

or in standard form, dividing by $R_0^2$,

$$\partial_t^2\delta\theta - \Delta\delta\theta
- 2(\nabla\ln R_0)\cdot\nabla\delta\theta
+ 4\lambda_\theta\varphi R_0^2\,\delta\theta = 0
\qquad\Rightarrow\qquad
m_\theta^2 = 4\lambda_\theta\varphi R_0^2$$

Within the extension, the $\varphi$-attractor potential explicitly breaks the
assumed SO(2) rotation, giving the phase fluctuation a mass and removing the
Goldstone limit. The PDE conversion coefficient
$\lambda_{\mathrm{PDE}}=0.1$ is a separate solver-time parameter and does not
set the optional action-potential coefficient $\lambda_\theta$, whose
normalization remains symbolic here. The conditional mass consequence is
small at low $R_0$ but structurally present; the spectral machinery of the
program lives in the extension's massless sector.

## 3. Optional Extension Massless Sector: Reduction to the Scale Operator

Set $\lambda_\theta = 0$ (the current-conserving limit of the optional
extension $\partial_\mu(R_0^2\partial^\mu\theta) = 0$) on the imposed,
conditional static self-similar ansatz $R_0 = A\,r^{-s}$. This background
profile is not derived from the canonical PDE. For the extension's s-wave,
$\theta = e^{-iEt}\psi(u)$, $u = \ln r$:

$$\psi'' + (1 - 2s)\,\psi' + E^2 e^{2u}\psi = 0$$

Removing the first-derivative term with
$\psi = e^{(2s-1)u/2}\,\tilde\varphi$ gives the normal form

$$\boxed{\tilde\varphi'' + \left[E^2 e^{2u} - \kappa^2\right]\tilde\varphi = 0,
\qquad \kappa = \left|s - \tfrac{1}{2}\right|}$$

The constant $\kappa$ is the Bessel index of the operator. For the scale-free
background in three dimensions—the extension amplitude profile
$R_0^2 \propto r^{-3}$, so
$s = D/2 = 3/2$ (`foundations/why-three-dimensions.md`)—

$$\boxed{\kappa = 1 \quad (D = 3)}$$

The Bessel index is exactly $1$ in the extension's natural background. (The
$s = 0$ free-wave limit gives $\kappa = 1/2$: solutions
$J_{1/2}(Ee^u) \propto \sin(Ee^u)/\sqrt{Ee^u}$, the standard radial wave,
correctly reproduced.)

## 4. The Exact Spectra of the Optional Extension Operator

The eigenfunctions are Bessel functions of the scale variable,
$\tilde\varphi(u) = J_\kappa(Ee^u)$ and $Y_\kappa(Ee^u)$. Three boundary
problems exhaust the natural options:

1. **Interior cavity** (regular at $r \to 0$, Dirichlet wall at $r = L$):
   only $J_\kappa$ survives regularity, and the wall quantizes
   $$E_n = \frac{j_{\kappa,n}}{L}, \qquad J_\kappa(j_{\kappa,n}) = 0$$
   with $j_{1,1} = 3.8317$, $j_{1,2} = 7.0156$, $j_{1,3} = 10.1735$. The
   exact count is a staircase with leading Weyl term
   $N(E) \approx EL/\pi$.
2. **Exterior walled problem** ($r \ge L$, the UV wall): $J_\kappa(Ee^u)$
   oscillates as $u \to \infty$ without decay—no $L^2$ eigenstates;
   continuous spectrum. The finite-box approximation has eigenvalues with
   mean spacing $\pi/(e^U - 1) \to 0$ as the box widens: the spectrum
   collapses to the continuum.
3. **Box** $[0, U]$ in $u$: Weyl-linear counting
   $N(E) \approx (E/\pi)(e^U - 1)$, verified to $0.2\%$ at $E = 100$.

The three cases yield Bessel, continuous, and Weyl-linear spectra; the zero
spectrum lies outside these realizations.
The ansatz fixes only the radial shape; $A$ remains free. The numerical checks
use a unit inner radial scale $r=1$; if a dimensionless implementation also
sets the auxiliary amplitude to $R=1$, that is a reference normalization only,
not a physical prediction.

## 5. The Acceptance Test: Linear vs Logarithmic

The program's Step 2 requires the counting function to reproduce
Riemann–von Mangoldt. The exact counting of every spectral realization of
§4 is a staircase whose leading Weyl term is **linear** in $E$. The
Riemann–von Mangoldt count grows as $E\log E$; its mean density is
logarithmic:

| $E$ | box count (exact) | Weyl linear | R-vM logarithmic |
|-----|-------------------|-------------|------------------|
| 25 | 50 | 50.8 | 2.4 |
| 50 | 101 | 101.7 | 9.4 |
| 100 | 203 | 203.4 | 29.0 |

The reference-normalized extension phase operator **fails the acceptance test
at leading order**—by a factor of 7–20 across this range. The mismatch is
structural: a linear density of states yields a density proportional to $E$,
whereas the zeros follow $(1/2\pi)\ln(E/2\pi)$.

## 6. The Semiclassical Constraint

The logarithmic shape survives in the semiclassical (phase-space) count of
the truncated hyperbola $xp \le E$ with the lower walls $x \ge L$, $p \ge
p_{\min}$:

$$N(E) = \frac{E}{2\pi}\ln\frac{E}{L p_{\min}} - \frac{E}{2\pi}
+ \frac{L p_{\min}}{2\pi}$$

Matching the logarithm to the theorem pins the cutoff product:

$$\boxed{L\,p_{\min} = 2\pi}$$

an order-unity constraint with **zero $\varphi$-power**; the arithmetic
boundary is independent of the cascade rung (consistent with the one-rung
reading of `hypotheses/riemann-hypothesis-de-resonance.md` §3). The constant term comes
out at $Lp_{\min}/2\pi = 1$, one-eighth above the theorem's $7/8$ for this
phase-space bookkeeping: the $9/8$ offset used in §8 is a chosen/Mapped
corner-phase coefficient, and no independent derivation of that coefficient
is retained here. The difference is the corner/reflection phase, repaired by
the exact spectral construction in the Berry–Keating/Sierra–Rodríguez-Laguna
treatment—a known mechanism with zero $\varphi$ content.
For general $\kappa$, the Bessel phase contributes at order $E^0$ to the
cavity count:
$N(E)=EL/\pi-(\kappa/2-1/4)+o(1)$. The quoted $7/8$ bookkeeping and the
moving-wall correction use $\kappa=1$; they do not remain unchanged when
$\kappa$ varies. For the chosen $D=3$ ansatz, $\kappa=1$ and the displayed
$7/8$ comparison is the applicable one.

## 7. Numerical Verification of the Optional Extension Operator

The targeted script check is limited to the following ODE, cavity, exterior,
and count checks:

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
  law $50.8/101.7/203.4$; the Riemann–von Mangoldt values 2.4/9.4/29.0 remain
  below the corresponding box counts.

## 8. Step 2b: The Energy-Dependent Boundary

Fixed walls give linear counting. The $E\log E$ shape requires a wall whose
position depends on the energy. In the tested $\kappa=1$ cavity construction,
the chosen asymptotic wall form that matches the Riemann–von Mangoldt count is
evaluated on the checked 300-point grid. With the cavity counting
$N(E) = \#\{n : j_{1,n} \le E\,L(E)\}$ and the Bessel asymptotics
$j_{1,n} \approx \pi(n + \tfrac{1}{4})$, the stated Bessel/count convention
selects the displayed ansatz:

$$\boxed{L(E) = \frac{1}{2}\ln\frac{E}{2\pi e} + \frac{9\pi}{8E}}$$

The $9/8$ is a chosen/Mapped corner-phase offset in this ansatz, not an
independently derived framework coefficient; the $\tfrac{1}{4}$ is the Bessel
phase ($\kappa/2 - 1/4$ with $\kappa = 1$). Together they give the theorem's
$7/8$ bookkeeping under this convention. The wall argument is the
Riemann–Siegel theta:

$$E\,L(E) = \theta(E) + \frac{5\pi}{4}$$

verified to $2\times10^{-4}$ at $E = 100$ and $10^{-5}$ at $E = 2000$; the
counting tracks $\bar N(E)$ to within one state over $E \in [20, 2000]$
(`experiments/riemann_phi_search/run_phase_boundary_check.py`). The
boundary-check script evaluates this expression only on that interval, where
$L(E)>0$; no unrestricted extension to other energies or physical wall
realization is asserted. Within the optional extension's operator language,
the Sierra–Rodríguez-Laguna construction identifies **the boundary phase of
the zero problem as the $\Gamma$-phase**. The moving wall encodes the
Riemann–Siegel theta as an external boundary condition.

The following are conditional exclusions of explicit fixed-wall,
bounded-potential mass-perturbation, and periodic-boundary toy maps; they do
not exclude an unconstructed canonical embedding. The fixed-wall statement is
analytic, the bounded-mass statement is a conditional perturbative argument,
and the IIR statement is the numerical null comparison:

1. **$\sigma$-regularization at a cascade rung** (any fixed wall): the
   analytic fixed-wall result has linear leading Weyl growth and fails the
   Step-1 acceptance test.
2. **Qi-gated, energy-dependent conversion** (bounded potential
   $m_\theta(E)$): in the specified mass-perturbation map, the conditional
   perturbative argument gives a Weyl-law correction at order $V/E^2$; the
   leading Weyl growth remains linear and the wall position stays fixed. This
   result does not cover other energy-dependent mass operators or domains.
3. **IIR memory timescale $\tau = \varphi^{-1}$** as a boundary period in
   $u$ of length $\ln\varphi$ (the identification $x \to \varphi x$): in the
   tested periodic-boundary map, the spectrum is the $\varphi$-locked lattice
   $E_n = n\,\omega_0$,
   $\omega_0 = 2\pi/\ln\varphi = 13.057$, with density $1/\omega_0 = 0.0766$.
   The zeros' measured density is $1.335$—a factor 17 denser—and only 2.6%
   of the first 100,000 zeros lie within 0.2 of the lattice, compared with
   3.3% for a phase-shifted control. The periodic-boundary map fails on
   density and by measurement; it is also the log-periodic structure the
   null test of `hypotheses/riemann-hypothesis-de-resonance.md` §4 rejects
   ($dAIC = +4.00$, $p_{\text{spec}} = 0.68$).

The tested boundary map yields a $\Gamma$-phase form over the stated energy
interval; it does not establish a unique boundary among all admissible
operators. The de-resonance reading remains a research statement. The
comparison reports raw proportions (2.6% versus 3.3%); no significance test is
retained here, so the two proportions are not described as statistically
identical. Selberg's mean-square result is an asymptotic trend with slow
convergence, and no GUE-spacing or other additional selection claim is used.

## 9. Status of the Program

- **Step 1 (write the optional reference-normalized operator): done.** The
  optional extension's massless phase fluctuation on the balanced self-similar
  background reduces to the Bessel-index-1 scale operator in $D = 3$. Within
  the extension, the phase is massive in general ($m_\theta^2 =
  4\lambda_\theta\varphi R_0^2$); the massless sector is the spectral candidate.
- **Step 2 (acceptance test): done, failed at leading order.** All exact
  spectra count linearly; the zeros count logarithmically. The logarithmic
  shape is semiclassical and requires the energy-dependent boundary of the
  Sierra–Rodríguez-Laguna construction.
- **Step 2b (the energy-dependent boundary): done, negative.** On the checked
  300-point grid, the stated $\kappa=1$ Bessel/count convention selects the
  chosen asymptotic moving-wall ansatz $L(E) = \tfrac{1}{2}\ln(E/2\pi e) +
  9\pi/(8E)$; this selection is unique only under that convention and is not
  unique among admissible boundaries. The boundary phase is the
  Riemann–Siegel $\Gamma$-phase ($E\,L(E) = \theta(E) + 5\pi/4$, verified).
  Framework structures remain external: fixed rung walls and the bounded-mass
  toy map fail by analytic/conditional arguments, while the IIR
  $\tau = \varphi^{-1}$ periodic map is disfavored by density and the measured
  null. The de-resonance selection rule (the boundary is the maximally
  de-resonant phase) remains a research statement.
- **The durable content:** the optional reference-normalized operator, its
  Bessel spectrum, the semiclassical pinning $Lp_{\min} = 2\pi$ with the
  $1/8$ corner-phase gap, and the chosen/Mapped wall ansatz with its
  conditional toy-map comparisons. The boundary itself remains external to
  the canonical two-density dynamics.

---

## References

- `hypotheses/riemann-two-fluid-spectral-program.md`—the program this document executes (Step 1)
- `hypotheses/riemann-hypothesis-de-resonance.md`—the de-resonance reading and the φ-periodicity null test
- `foundations/unified-lagrangian.md`—two-fluid core Lagrangian; source referenced by the optional polar extension
- `foundations/cassi-first-principles.md`—field equations and attractor; reference form for the optional current operator
- `foundations/why-three-dimensions.md`—$D = 3$ (hence $s = 3/2$, $\kappa = 1$)
- Berry, M. V. and Keating, J. P., "The Riemann zeros and eigenvalue asymptotics," SIAM Review 41 (1999) 236–266
- Sierra, G. and Rodríguez-Laguna, J., "The Riemann zeros as spectrum of a Hamiltonian," J. Phys. A 44 (2011) 305204
- `experiments/riemann_phi_search/run_phase_operator_check.py`—listed ODE, cavity, exterior, and count checks (§7)
- `experiments/riemann_phi_search/run_phase_boundary_check.py`—checked moving-wall grid and conditional comparisons (§8)
