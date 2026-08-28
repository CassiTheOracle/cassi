# The Riemann Hypothesis and the De-Resonance of Primes

## Status: Speculative—August 2026

## Abstract

Wei et al. (Nature Communications, 2026) establish a direct correspondence
between the nontrivial zeros of the Riemann zeta function and dynamical quantum
phase transitions in two engineered quantum many-body systems, recasting the
Riemann Hypothesis (RH) as the occurrence of a phase transition at a unique
temperature. This document reads that correspondence through the Cassi lens:
by the explicit formula, RH is exactly the claim that the primes carry no
resonant component, and the critical line $\operatorname{Re} s = \frac{1}{2}$
is the Yang-Yin balance axis of the functional equation
$\zeta(s) \leftrightarrow \zeta(1-s)$. The framework's universal fingerprint—
log-periodic modulation at period $\ln\varphi \approx 0.4812$—is tested
against the first 100,000 zeros (Odlyzko's table) with the repo's calibrated
protocol: the result is null at $\omega_0 = 2\pi/\ln\varphi$ on both spacing
and density statistics, with demonstrated sensitivity to a 1–3% modulation.
The null is the expected outcome under the de-resonance reading, which
predicts maximal featurelessness (GUE statistics) rather than a $\varphi$
signature. The mapping is interpretation, not derivation: no proof of RH is
claimed, and no mechanism from the two-fluid PDE yet reaches the zeros.

---

## 1. The Correspondence

Wei, Zhai, Lu, Yang, Gao, Wei, Song, Nori, Xin and Long construct two
complementary engineered quantum many-body systems—characterized by the
average accumulated phase factor and the Loschmidt amplitude—whose dynamical
phase transitions occur exactly at the points where $\zeta$ has a nontrivial
zero. The correspondence recasts RH as the statement that these systems
undergo phase transitions at a **unique temperature**, and identifies a
transition mechanism new to the literature. The construction was demonstrated in
proof-of-principle on a quantum processor, with a polynomial-resource quantum
computational framework proposed for probing the hypothesis.

The result is a reformulation and a probe, not a proof. It sits in the
tradition of Hilbert–Pólya (zeros as eigenvalues of a physical operator) and
of the number-theoretic Bose gas (the Riemann gas, where the partition
function is $\zeta(\beta)$ and RH governs the absence of phase transitions
above a critical temperature). Its value is twofold: it gives a falsification
channel in principle (a zero off the line would appear as a missing or extra
transition), and it places the zeros inside physical dynamics where operator
techniques might eventually reach them. No finite experiment, classical or
quantum, certifies an infinite statement; RH itself is untouched as a theorem.

## 2. RH as a De-Resonance Statement

The explicit formula makes the connection to the framework's core principle
literal. For the Chebyshev function $\psi(x) = \sum_{p^k \le x} \ln p$,

$$\boxed{\psi(x) = x - \sum_{\rho} \frac{x^{\rho}}{\rho} - \frac{\zeta'(0)}{\zeta(0)} - \frac{1}{2}\ln(1 - x^{-2})}$$

where the sum runs over nontrivial zeros $\rho$. Each zero contributes an
oscillation

$$x^{\operatorname{Re}\rho}\,\cos\!\big(\operatorname{Im}\rho \cdot \ln x\big)$$

to the prime distribution. A zero off the critical line, with
$\operatorname{Re}\rho > \frac{1}{2}$, injects a component that grows faster
than $\sqrt{x}$ and oscillates at the fixed log-frequency
$\operatorname{Im}\rho$—a **resonance in the primes**. RH is the statement
that no such component exists:

$$\boxed{\text{RH} \iff \text{the primes carry no resonant component}}$$

This is the vocabulary of `principles/de-resonance-principle.md`: nature's
structures avoid resonance, and $\varphi$ is the attractor because it is the
maximally irrational number—the hardest frequency to lock onto. The primes are
then the archetypal de-resonant sequence: the explicit formula shows that the
critical line is not a coincidence of analysis but the balance axis of the
functional equation, the Yang-Yin symmetric point where the two sides of
$\zeta(s) \leftrightarrow \zeta(1-s)$ exchange roles. In framework language,
a zero off the line would be a symmetry-breaking resonance in the most
de-resonant object in mathematics.

## 3. The Unique-Temperature Reading

The correspondence's "phase transition at a unique temperature" has a cascade
reading. Physical systems in the Cassi framework carry a ladder of critical
scales—every rung $\ell_n = \ell_{\text{Pl}} \varphi^n$ of
`foundations/dimensionful-cascade.md` is a possible transition scale. The
number-theoretic system is the degenerate limit: exactly one critical point.
In the Riemann gas the critical temperature is dimensionless $T_c = 1$, the
identity rung $\varphi^0$; a single phase transition is a single-rung system.
Under this reading the primes are the maximally de-resonated limit of the
cascade—the one-rung system left standing when all structure has been
suppressed. This is interpretation: it reorganizes the paper's vocabulary but
derives nothing new.

## 4. Falsifiable Test: the φ-Periodicity Protocol on ζ Zeros

The framework's universal experimental signature is log-periodic modulation
at period $\ln\varphi \approx 0.4812$ in physical spectra—Prediction 5 of
`predictions/falsifiable-predictions.md`
($\Delta(\ln k) = \ln\varphi$ in the matter power spectrum). If the
de-resonance reading of §2 were literal enough to leave a fingerprint, the
zeros themselves would show it: a log-periodic clustering of zeros at period
$\ln\varphi$ in $\ln T$, or a modulation of the unfolded spacing sequence at
$\omega_0 = 2\pi/\ln\varphi \approx 13.057$ radians per log-unit.

The test follows the repo's calibration protocol
(`experiments/riemann_phi_search/run_zeta_phi_periodicity_test.py`, which
reproduces every number below): $\omega_0$ fixed with zero fitted parameters,
linear cos/sin basis (no phase grid), both dAIC and the $\omega$-specificity
percentile $p_{\text{spec}}$ reported, planted-signal power check, and
scrambled-data null check. Data: Odlyzko's table of the first 100,000 zeros
(imaginary parts; $\gamma_1 = 14.134725142$, $\gamma_{100000} = 74920.8275$),
covering 17.8 log-periods of $\varphi$.

| Test | dAIC at $\omega_0$ | $p_{\text{spec}}$ | Verdict |
|------|--------------------|--------------------|---------|
| Unfolded spacings (n = 99,999) | +4.00 | 0.678 | null |
| Density deviation $D(u)$ (n = 1000) | +3.73 | 0.912 | null |
| Planted A = 0.01 (1% of noise) | −25.3 | 0.000 | machinery fires |
| Planted A = 0.03 / 0.10 | −260 / −2890 | 0.000 | strongly fires |
| Scrambled nulls | −1.56 / +3.63 | 0.129 / 0.860 | clean |

Both tests are null: the oscillation model is *worse* than the linear baseline
(positive dAIC), and $\omega_0$ is not an outlier among grid frequencies. The
planted-signal checks show the null is not a sensitivity failure—a modulation
of 1–3% of the noise level would have been detected at $p < 0.001$. Windowed
spacing tests (four windows) are null at $\omega_0$ in every window.

One apparent outlier on the density series, $\omega \approx 25.4$ with
dAIC = −9.2, is the documented smooth-data trap: its dAIC is
non-stationary across windows (ranging −5.1 to +3.5), and the spectrum of
$D(u)$ is dominated by high-frequency mass (peak at $\omega \approx 206$)—the
chirp of the argument-fluctuation function $S(T)$, whose local oscillation
frequency grows with $T$. It is not a $\varphi$ signature and not a stationary
signal.

## 5. What the Null Means

The null is the correct outcome under the framework's own mature logic. The
naive expectation—a $\varphi$-signature appearing in every spectrum, as the
wake-wave prediction supplies for cosmological $P(k)$—is ruled out for the
zeros. But the de-resonance principle does not predict a $\varphi$ pattern in
primes; it predicts the *absence* of all patterns. The zeros' statistical
behavior is known to match random-matrix (GUE) predictions
(Montgomery–Odlyzko), and featureless GUE statistics are precisely what a
maximally de-resonant sequence should show. The test therefore sharpens the
framework's claim: the wake-wave fingerprint is a signature of Yang-Yin
interference in *physical* fields, not of the de-resonance principle as such.
Prime statistics sit on the de-resonance side, and they are clean.

## 6. What a Proof Would Require

A proof of RH is an infinite statement; no measurement reaches it. The one
route physics offers is Hilbert–Pólya: exhibit an operator whose spectrum is
the zeros and prove its spectrum is confined to the critical line (the
Berry–Keating program). The Nature correspondence supplies an engineered
Hamiltonian of exactly this kind, but engineered equivalence is not a proof of
confinement. A Cassi contribution would be a *derived* spectral problem: the
two-fluid PDE linearized around its Yang-Yin balanced state, with a proof that
the linearized operator is (unitarily equivalent to something) self-adjoint
with spectrum on the symmetry axis. Nothing in the current framework
(`foundations/cassi-first-principles.md`) contains that result; the
research sketch with the candidate operator, the boundary constraint, and the
measured fluctuation probes lives in `riemann-two-fluid-spectral-program.md`.

## 7. Open Issues

- The de-resonance mapping of §2 is interpretation. It restates RH in the
  framework's vocabulary without deriving anything about the zeros.
- The unique-temperature reading of §3 is a parallel to the Riemann-gas
  tradition, not an independent derivation; $T_c = 1$ is the identity rung
  trivially.
- The null test of §4 covers 100,000 zeros. It constrains the naive
  fingerprint claim, not RH: the hypothesis is consistent with all 100,000
  zeros and with every independently verified zero.
- The tier is **Speculative** because no mechanism from the two-fluid PDE has
  been shown to act on the zeros. The recorded null and the reproduced
  protocol are the durable content; the mapping is a prompt for future work.

---

## References

- Wei, S., Zhai, Y., Lu, Q. et al., "The Riemann Hypothesis manifested in dynamical quantum phase transitions," Nature Communications (2026), https://doi.org/10.1038/s41467-026-74935-8
- Odlyzko, A., tables of zeros of the Riemann zeta function (first 100,000), http://www.dtc.umn.edu/~odlyzko/zeta_tables/zeros1
- `principles/de-resonance-principle.md`—why $\varphi$ is the attractor (maximally irrational)
- `foundations/dimensionful-cascade.md`—the 292-step ladder
- `predictions/falsifiable-predictions.md`—Prediction 5, φ-periodic $P(k)$ at $\Delta\ln k = \ln\varphi$
- `foundations/cassi-first-principles.md`—two-fluid PDE and governing equations
- `experiments/riemann_phi_search/run_zeta_phi_periodicity_test.py`—reproduces the §4 table
