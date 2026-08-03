# The Two-Fluid Hilbert–Pólya Program

## Status: Speculative—August 2026

## Abstract

The Riemann Hypothesis is equivalent to the existence of a self-adjoint
operator whose spectrum is the imaginary parts of the nontrivial zeros
(Hilbert–Pólya): self-adjoint operators have real spectra, so the zeros would
all lie on the critical line by construction. Exact spectral realizations
already exist in the literature—Berry–Keating's $xp$ model reproduces the
smooth zero-counting asymptotics, and Sierra–Rodríguez-Laguna construct a
Hermitian Hamiltonian whose eigenvalues are the zeros numerically. The open
problem is not existence but naturalness: no construction is *derived* from a
physical dynamics, and none is proven. This document sketches the program that
would make the two-fluid framework the source of that operator. The candidate
is the linearized phase dynamics of the Yang-Yin fields around their balanced
state, whose dilation covariance makes the scale operator $x\partial_x$ the
natural free generator; the matching constraint to the Riemann–von Mangoldt
counting function pins the spectral boundary at the order-unity scale $2\pi e$
(no cascade rung $\varphi^n$ enters), and the de-resonance principle becomes
the claim that the zero-counting fluctuation is minimal—a claim with one
unconditional theorem behind it (Selberg's mean-square law) and two measured
data points recorded here. The tier is Speculative: step zero of the program,
nothing derived yet.

---

## 1. The Target

Hilbert–Pólya: exhibit an operator $H$, self-adjoint on some Hilbert space,
whose discrete spectrum is $\{\gamma_n\}$, the imaginary parts of the zeros
with $\zeta(\tfrac{1}{2} + i\gamma_n) = 0$. Then RH follows: a self-adjoint
operator has only real eigenvalues, and the functional equation
$\zeta(s) \leftrightarrow \zeta(1-s)$ plus the symmetry of the construction
places the spectrum on the critical line.

The zeros are already spectral in character, independently of any conjecture.
The explicit formula is a trace formula:

$$\psi(x) = x - \sum_{\rho} \frac{x^{\rho}}{\rho} - \frac{\zeta'(0)}{\zeta(0)} - \frac{1}{2}\ln(1 - x^{-2})$$

Each zero contributes an oscillation at log-frequency $\gamma_n$; the primes
are the "spectral density" dual to the zeros, exactly as a classical trace
formula pairs a spectrum with a length spectrum. The framework's reading of
this duality is developed in
`riemann-hypothesis-de-resonance.md`: RH is the statement that the primes
carry no resonant component, and the critical line is the Yang-Yin balance
axis of the functional equation. The spectral program is the attempt to make
that reading constructive.

## 2. What Already Exists

- **Berry–Keating (1999).** The classical Hamiltonian $H = xp$ on the
  half-line with a boundary wall: its WKB counting function reproduces the
  smooth part of the zero count, including the famous $7/8$ constant of
  Riemann–von Mangoldt. The wall position is not free: matching the phase-space
  area $(E/2\pi)\ln(E/L)$ to the theorem
  $N(T) = (T/2\pi)\ln(T/2\pi) - T/2\pi + 7/8 + S(T) + O(1/T)$ pins the
  cutoff product at $2\pi e$ (in $\hbar = 1$ units with unit momentum
  cutoff). This is a model-interpretation constraint, not a fit: the
  arithmetic boundary sits at the order-unity scale, and no cascade rung
  $\varphi^n$ appears anywhere in the smooth asymptotics.
- **Sierra–Rodríguez-Laguna (2011).** A Hermitian Hamiltonian whose
  eigenvalues reproduce the zeros to numerical precision, built from the
  phase-space geometry of the $xp$ model with a sawtooth boundary. Existence
  of the Hilbert–Pólya operator is therefore not in doubt in practice; what
  is missing is a *derivation*—a dynamics that produces this operator—and a
  *proof* of self-adjointness with confinement to the line.

The engineering exists; the physics does not. That is the gap this program
addresses.

## 3. The Two-Fluid Candidate Operator

The framework's governing equations (`../foundations/cassi-first-principles.md`)
are a nonlinear two-fluid wave system for the Yang and Yin fields with a
conversion coupling. Three structural facts make a spectral derivation
plausible:

1. **Dilation covariance.** The balanced Yang-Yin state is self-similar
   (the cascade `../foundations/dimensionful-cascade.md` is a discrete
   dilation structure). Linearizing the phase degree of freedom around that
   state produces an equation in the scale variable $u = \ln x$ whose free
   kinetic term is the dilation generator $x\partial_x$—the $xp$ of the
   Berry–Keating model. In the framework the $xp$ operator is not an ad hoc
   choice; it is the generator of the theory's own symmetry.
2. **The boundary condition.** The linearized problem needs a boundary at the
   ultraviolet end. The framework's $\sigma$-regularization
   (`../foundations/unified-lagrangian.md`) supplies one at the Planck rung;
   the matching constraint of §2 then determines the effective wall scale.
   The constraint is *negative but decisive*: whatever the UV completion, the
   smooth counting function must come out as the theorem, which fixes the
   wall at $2\pi e$ in natural units—an order-unity scale. The cascade rungs
   $\varphi^n$, $n \ge 1$, are excluded by the asymptotics; the number-theoretic
   system is the one-rung ($\varphi^0 = 1$) limit, consistent with the
   unique-temperature reading in `riemann-hypothesis-de-resonance.md` §3.
3. **De-resonance as the spectral condition.** The fluctuation $S(T)$ of the
   zero count around its smooth average is the "arithmetic term" the operator
   must leave minimal. The de-resonance principle
   (`../principles/de-resonance-principle.md`) states that the primes' spectrum
   is maximally featureless: minimal fluctuation, no locked frequencies. The
   measurable content of that statement is the subject of §4–§5.

None of these steps is a derivation yet. The operator has not been written
down from the PDE source; §6 lists the order of operations for doing so.

## 4. De-Resonance as Minimality

The fluctuation of the zero count is the resonance content of the primes.
Two facts frame it:

- **Selberg's theorem (1946, unconditional).** The mean square of $S(t)$
  satisfies
  $$\boxed{\frac{1}{T}\int_0^T S(t)^2\,dt \;\sim\; \frac{1}{\pi^2}\,\ln\ln T}$$
  The primes' resonance is *provably minimal in mean square*—the theorem, not
  a conjecture. The framework's de-resonance reading is the claim that this
  minimality is the whole story: RH is its maximal-deviation companion, the
  statement that the fluctuation never exceeds the minimal scale
  ($S(T) \ll \ln T / \ln\ln T$ under RH, against the trivial $O(\ln T)$).
- **The measured fluctuation.** On Odlyzko's first 100,000 zeros
  ($T \le 7.5\times10^4$), the empirical mean square and the maximal deviation
  are recorded in §5. The data are consistent with the minimal-fluctuation
  picture at the level of magnitude and trend; the slow-convergence regime of
  the $\ln\ln T$ law prevents a sharper statement at this height.

## 5. Measured Probes

Script: `../experiments/riemann_phi_search/run_zeta_fluctuation_probes.py`
(reproduces every number below from the cached Odlyzko table).

**Probe 1—Selberg mean square of $S(T)$** (computed at gap midpoints, where
$N(T)$ is exact; $S = N - \bar N - O(1/T)$):

| Band (T range) | measured $(1/\Delta T)\!\int S^2$ | $(1/\pi^2)\ln\ln T$ (theorem) | max $|S|$ |
|---|---|---|---|
| 18 – 1.8×10⁴ | 0.0482 | 0.2313 | 0.71 |
| 1.8×10⁴ – 3.3×10⁴ | 0.0562 | 0.2374 | 0.70 |
| 3.3×10⁴ – 4.8×10⁴ | 0.0585 | 0.2408 | 0.74 |
| 4.8×10⁴ – 6.1×10⁴ | 0.0601 | 0.2432 | 0.77 |
| 6.1×10⁴ – 7.5×10⁴ | 0.0612 | 0.2450 | 0.80 |

The trend is upward as the theorem requires, but at $T \approx 7.5\times10^4$
the measured mean square sits a factor $\sim 4$ below the asymptotic—the
documented slow-convergence regime of the $\ln\ln T$ law, where error terms
dominate. The durable content is the magnitude of the fluctuation itself:
$\max|S| = 0.80$ over 100,000 zeros, against the trivial bound
$\ln T \approx 11.2$ at this height and the RH-conditional shape
$\ln T/\ln\ln T \approx 4.6$—a factor 6–14 of headroom, in the direction the
minimality claim requires.

**Probe 2—Gram's law.** With $\theta(g_n) = n\pi$, the Gram intervals
$[g_n, g_{n+1}]$ usually contain exactly one zero ($g_0 = 17.845600$,
$g_1 = 23.170283$, matching the known values to six digits):

| Statistic | measured |
|---|---|
| Intervals with exactly one zero | 79.4% |
| Intervals with zero zeros | 10.33% |
| Intervals with two zeros | 10.16% |
| Intervals with three zeros | 0.09% |
| Mean $\|$zero $-$ nearest Gram point$\|$ | 0.275 of an interval |

The zeros sit close to, but not locked to, a perfectly regular lattice—the
de-resonant mean with the minimal fluctuation around it. (The φ-periodicity
null of `riemann-hypothesis-de-resonance.md` §4 is the companion measurement:
no log-periodic locking at $\ln\varphi$ in either spacing or density.)

## 6. The Program's Steps

1. **Write the operator.** Linearize the two-fluid phase dynamics
   (`../foundations/cassi-first-principles.md`) around the balanced
   self-similar state; obtain the explicit spectral problem in
   $u = \ln x$. *Status: not started—the concrete first task.*
2. **Check the asymptotics.** Verify the WKB count of the candidate
   reproduces Riemann–von Mangoldt with the $7/8$; the wall-scale constraint
   of §2 is the acceptance test. *Status: not started.*
3. **Find the natural extension.** Identify the self-adjoint extension
   selected by the $\sigma$-regularized boundary. *Status: not started.*
4. **Attack minimality.** Prove (or sharpen) the $S(T)$ bound for the
   operator's spectral fluctuation—the step that would constitute RH.
   *Status: the deep problem; Selberg's theorem is the existing anchor.*

Every step is open, and the tier is Speculative accordingly. What is already
measured—the φ-periodicity null, the fluctuation magnitudes, Gram's law—are
constraints any candidate operator must respect; they are the durable output
of this document.

## 7. Open Issues

- No operator has been derived from the two-fluid equations; §3 is a
  structural sketch, not a derivation.
- The wall-scale constraint ($2\pi e$, order-unity) is an interpretation of a
  theorem about $\zeta$, not an output of the framework.
- The Selberg probe is consistent with minimality but sits in the slow
  convergence regime; nothing here constrains RH beyond the direction of the
  data.
- Existence results (Sierra–Rodríguez-Laguna) show the spectral problem has
  solutions; they do not make the framework's candidate natural.

---

## References

- Berry, M. V. and Keating, J. P., "The Riemann zeros and eigenvalue asymptotics," SIAM Review 41 (1999) 236–266
- Sierra, G. and Rodríguez-Laguna, J., "The Riemann zeros as spectrum of a Hamiltonian," J. Phys. A 44 (2011) 305204
- Selberg, A., "Contributions to the theory of the Riemann zeta-function," Arch. Math. Naturvid. 48 (1946)
- Wei, S. et al., "The Riemann Hypothesis manifested in dynamical quantum phase transitions," Nature Communications (2026), https://doi.org/10.1038/s41467-026-74935-8
- `riemann-hypothesis-de-resonance.md`—the de-resonance reading and the φ-periodicity null test
- `../principles/de-resonance-principle.md`—why $\varphi$ is the attractor (maximally irrational)
- `../foundations/cassi-first-principles.md`—two-fluid PDE and governing equations
- `../foundations/unified-lagrangian.md`—$\sigma$-regularization
- `../foundations/dimensionful-cascade.md`—the 292-step ladder
- `../experiments/riemann_phi_search/run_zeta_fluctuation_probes.py`—Selberg mean-square and Gram's law probes
- `../experiments/riemann_phi_search/run_zeta_phi_periodicity_test.py`—the φ-periodicity null test
