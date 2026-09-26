# Scalar–Fermion Static Vacuum Viability Criterion

## Status: Frozen conditional algebraic qualification—September 2026

## Abstract

This calculation tests a necessary energetic condition for global localized ground states in the specified static one-loop scalar energy. It retains the homogeneous vacuum remainder and harmonic scalar energy already declared in `foundations/sector-coupling-derivation.md` §§1.7–1.8. It adds no physical matching, source history, coupling scan or dynamical formation simulation. The output distinguishes local reference curvature, global lower boundedness of this functional, and the separate question of metastable localized states.

## 1. Fixed functional and scope

In the supplied dimensionless normalization, $m_0=1$, $y=1/4$ and $\Omega=3$. Write $d=m-1=yf$ and

$$
P(d)=2d+7d^2+\frac{26}{3}d^3+\frac{25}{6}d^4,
\qquad
\mathcal U(m)=72d^2-\frac{m^4\log(m^2)-P(d)}{16\pi^2}.
$$

The spatial diagnostic is the explicitly specified local static functional

$$
\mathcal E[f]=\int_{\mathbb R^3}\left[\frac12|\nabla f|^2+\mathcal U(1+yf)\right]d^3x,
\qquad f(x)\to0.
$$

The homogeneous one-loop potential is exact within its stated subtraction prescription. The displayed spatial functional retains the canonical scalar gradient term and omits the nonlocal fermionic determinant and higher derivative terms. No result for this local functional is automatically a result for a fully renormalized spatial quantum model. A completion with the same bulk energy and subextensive interface energy inherits the negative bulk-volume argument. Different physical finite parts or additional interactions require their own justification and qualification.

## 2. Exact predicates

The fixed predicates are:

1. $\mathcal U(1)=\mathcal U'(1)=0$ and $\mathcal U''(1)=144$ in mass coordinates, equivalently scalar curvature $y^2\mathcal U''(1)=9$.
2. $\lim_{m\to\infty}\mathcal U(m)/[m^4\log(m^2)]=-1/(16\pi^2)$.
3. A single algebraic witness is $m=64$, $d=63$, $f=252$. Strict convexity of $1/x$ on $[1,2]$ gives $\log2>2/3$, hence $\log4096>8$. The bound $\pi<22/7$ gives $\pi^2<10$. For $L=8\,64^4-P(63)>0$,

$$
\mathcal U(64)<72\,63^2-\frac{L}{160}=U_{\rm upper}.
$$

The sign of this exact rational upper bound is the qualification; the floating-point value of $\mathcal U(64)$ is descriptive only. There is no search for a zero crossing or preferred field amplitude.

4. For a radial plateau $f=A=252$ at $r\le R$, linear falloff to zero over width $w=\sqrt R$, and zero exterior, the gradient energy is

$$
E_\nabla=2\pi A^2\left(\frac{R^2}{w}+R+\frac w3\right).
$$

The core energy is $4\pi\mathcal U(64)R^3/3$. If $M=\max_{1\le m\le64}|\mathcal U(m)|$, the absolute shell potential is bounded by

$$
4\pi M(R^2w+Rw^2+w^3/3).
$$

Both the gradient energy and shell bound divided by $R^3$ tend to zero. The continuity of $\mathcal U$ on $[1,64]$ guarantees finite $M$; its value is not fitted or numerically maximized. The piecewise-linear radial field is an admissible finite-energy $H^1$ trial function. Each finite-$R$ field tends to the reference at infinity.

5. With the fermion loop omitted, the same functional has nonnegative gradient and harmonic terms. This zero-loop control must retain nonnegative potential at the witness and positive reference curvature.

## 3. Decision rule and limits

The script independently checks the large-field limit with SymPy and the negative witness with exact `fractions.Fraction` arithmetic. It also derives the gradient integral and verifies the two large-radius ratios symbolically. All named predicates must pass. Success returns `CONTRADICTS—global lower boundedness of the specified local static one-loop scalar energy`. Any failed check returns `INCONCLUSIVE`.

The result does not exclude local extrema, metastable lumps or their finite-time formation. Extending the global no-minimum statement to fixed nonzero fermion charge requires a charge-preserving finite-energy valence construction and cluster separation from the neutral bubble; that extension is a stated conditional requirement rather than a solved fermionic spectrum. No bounce action, lifetime, nonlinear stability, particle identity, canonical two-density closure or complete matter-formation claim is authorized.

## 4. Execution and evidence

`computations/verify_matter_formation_scalar_vacuum.py` runs once with `--output-dir runs/20260906_matter_formation_scalar_vacuum/`. It emits exclusive `results.json` with schema `cassi-scalar-vacuum-boundary-v1`, canonical CRLF-to-LF SHA-256 identities for itself, this preregistration and the unchanged continuum preregistration, exact rational values, descriptive floating-point values, named boolean checks, verdict and failures. JSON must be finite. A missing-preregistration control writes an empty scientific payload and exits one. Existing output is never overwritten. A source defect preserves the receipt and source revision; any repaired run uses a fresh directory.

This is an algebraic requirements qualification, with no PDE, eigenvalue, parameter scan or cutoff-production rerun.

## References

- `foundations/sector-coupling-derivation.md` §§1.7–1.9—supplied scalar–fermion model, static subtraction and localized-state requirements.
- `computations/matter-formation-continuum-admissibility-prereg.md` §3—fixed homogeneous static remainder.
- `computations/matter-formation-continuum-report.md` §15—verified continuum restrictions and two-body scope.
