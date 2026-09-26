# Quantum Free-Fall Closure Checks

## Status: Pre-registered—September 4, 2026

## Abstract

The checks fix the physical domain and information content of the canonical
Qi diagnostic, and test a necessary condition for the Gaussian propagator's
standard positive physical-covariance interpretation. The identities and
witnesses are specified before execution; they supply no fit or atomic
response model.

## 1. Scope

These algebraic checks determine what information the canonical Qi diagnostic retains and whether the displayed Gaussian propagator admits the standard positive spectral interpretation. They introduce no data fit, atomic state map, physical coupling, or new parameter. The ideal-QGI obligations in `computations/quantum_free_fall_correspondence_prereg.md` remain a separate calculation.

## 2. Frozen objects

Use only $\varphi=(1+\sqrt5)/2$, nonnegative $E_Y,E_I$, $\rho=E_Y+E_I>0$, $\varepsilon=E_Y-\varphi E_I$, $\rho_\star>0$, and

$$
q=\frac{\rho^2}{\rho^2+\varphi^{-2}\rho_\star^2+\varepsilon^2},\qquad
s=\frac{E_Y-E_I}{\rho},\qquad
\mathcal G_C=s[1+(\varphi^6-1)q].
$$

The spectral candidate is $G_E(x)=e^{-ax}/x$ for $x=k_E^2>0$ and $a=\sigma^2/2>0$. The interpretation being assessed is an unsubtracted scalar Källén–Lehmann covariance $G_E(x)=\int_{[0,\infty)}d\mu(u)/(x+u)$ with nonnegative measure, finite for every $x>0$. It is the standard positive-metric, translation- and Euclidean-rotation-invariant physical two-point interpretation. No extra contact term, gauge-fixed indefinite propagator, alternative inner product, or altered continuation is included in this claim.

## 3. Proof obligations and stopping rule

- **QFC1—Physical Qi interval.** Solve for the two densities in terms of $(\rho,\varepsilon)$. Nonnegativity must give $-\varphi\rho\leq\varepsilon\leq\rho$. At fixed density, verify
  $$
  \frac{\rho^2}{(1+\varphi^2)\rho^2+\varphi^{-2}\rho_\star^2}
  \leq q\leq
  \frac{\rho^2}{\rho^2+\varphi^{-2}\rho_\star^2}<1.
  $$
  The lower endpoint is $E_Y=0$; the upper endpoint is $\varepsilon=0$. Verify the positive-denominator factorizations of both differences, and the dilute and high-density lower-endpoint limits. The claim excludes optional memory-replaced $\varepsilon^2$.
- **QFC2—State non-identifiability.** Set $\rho=\rho_\star=1$ and $\varepsilon=\pm1/2$. Both density pairs must be nonnegative, have identical $q$, and have opposite signs of $s$ and $\mathcal G_C$. Print both density pairs, $q$, $s$, and $\mathcal G_C$. This is a diagnostic counterexample; neither coupling value is a physical gravitational response.
- **QFC3—Coarse-graining.** Average the two equal-volume cells in QFC2. Verify that $q$ evaluated on the averaged fields differs from the average of the two local $q$ values. Print both quantities and their difference. No state-independent closure from averaged fields alone may be inferred.
- **QFC4—Positive spectral obstruction.** For $x_2>x_1>0$ and $u\geq0$, verify
  $$
  \frac{x_2}{x_2+u}-\frac{x_1}{x_1+u}
  =\frac{u(x_2-x_1)}{(x_2+u)(x_1+u)}\geq0.
  $$
  Integrating against a nonnegative measure makes $xG_E(x)$ nondecreasing. Verify that the Gaussian candidate instead has $d[xG_E(x)]/dx=-ae^{-ax}<0$. Print the dimensionless witness $ax_1=1,ax_2=2$, and verify the $a=0$ massless control. The witness illustrates the exact all-$a>0$ proof; it is not a momentum scan or numerical positivity test.

Run once to algebraic completion. A nonzero identity residual, invalid witness, or failed sign/control is **FAIL**; all four obligations established is **PASS**. **ADOPT** requires an independent calculation that does not import the verifier. The adopted scope is the physical-domain/information boundary and rejection of the specified positive-spectral interpretation at nonzero $\sigma$. It is not rejection of all nonlocal theories, a gauge-fixed auxiliary line, a regulator used only during calculation, or the independently derived ideal-QGI phase.

## 4. Output and sources

`computations/verify_quantum_free_fall_closure.py` must print every obligation, the declared numerical witnesses, the aggregate verdict, and `ALL CHECKS PASSED` only on success. The derivations and measured output belong to `foundations/quantum-free-fall-correspondence.md` §§9,11–12 and `gravity/quantum-gravity.md` §3.1.

## References

- `foundations/cassi-first-principles.md` §2.1—canonical normalization.
- H. Lehmann, *Il Nuovo Cimento* **11**, 342–357 (1954), [doi:10.1007/BF02783624](https://doi.org/10.1007/BF02783624)—positive spectral framework.
- K. Osterwalder and R. Schrader, *Communications in Mathematical Physics* **31**, 83–112 (1973), [doi:10.1007/BF01645738](https://doi.org/10.1007/BF01645738)—Euclidean reconstruction assumptions.
