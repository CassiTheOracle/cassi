# Neutral-Vacuum and Localization Boundary of the Carrier Parent

## Status: Derived conditional scalar identities / Hypothesized physical parent—September 2026

## Abstract

The positive-inertia carrier parent permits a signed conserved charge, but a production channel alone does not establish a stable localized neutral state. This calculation checks the classical homogeneous vacuum boundary, the constrained kinetic-energy identity and the spatial dilation law of the same scalar action. The algebraic results concern the scale-independent, topologically trivial scalar sector with positive spatial stiffness and constant exterior vacuum data. Quantum corrections, charged soliton stability, multi-frequency states, additional gauge or scale sectors and physical parameter selection remain outside this calculation.

## 1. Action and analytic commitments

The parent is specified in `foundations/particle-stationary-action-closure.md` §8.8. All energies below are divided by the positive overall action factor $\mathcal N_Q$; its physical value remains unselected. The coefficients are

$$
u_\rho=4,\quad u_C=k_{Cx}=1,\quad e_C=0.75,
\quad h_C=2.9598260763447164,\quad a>0.
$$

The coefficient $h_C$ retains its Mapped status from the numerical support scan. No physical coefficient is selected by the present calculation. Write $z=f^2\ge0$, $n=|\chi|^2\ge0$, $B=e_C+1/(4a)$ and $s=\sqrt{u_\rho u_C/2}$. The canonical static potential is

$$
V_a(z,n)=\frac{u_\rho}{4}(z-1)^2+[B-h_C(1-z)]n+\frac{u_C}{2}n^2.
$$

Its exact factorization is

$$
V_a=\left[\frac{\sqrt{u_\rho}}2(1-z)-\sqrt{\frac{u_C}{2}}n\right]^2
+\left[B-(h_C-s)(1-z)\right]n.
$$

For positive $e_C,u_\rho,u_C,h_C,a$, the potential is nonnegative for every $z,n\ge0$ if and only if $h_C-B\le s$. When $h_C>e_C+s$, this is equivalent to

$$
0<a\le a_{\rm vac}:=\frac1{4(h_C-e_C-s)}.
$$

If $h_C\le e_C+s$, every positive $a$ satisfies the condition. The global minimum value is

$$
\min_{z,n\ge0}V_a=\min\left(0,\frac{u_\rho}{4}-\frac{[\max(h_C-B,0)]^2}{2u_C}\right).
$$

For $a>a_{\rm vac}$ at the specified coefficient point, the lower homogeneous phase has $z=0$ and $n=(h_C-B)/u_C$. At equality, it is degenerate with the exterior vacuum and has $n=\sqrt{u_\rho/(2u_C)}$. A lower homogeneous phase does not by itself establish nucleation, a formation rate or a finite bubble solution.

The carrier mass squared at a prescribed fully depleted mediator is

$$
M_a^2(0)=\frac1{4a^2}+\frac{e_C-h_C}{a}.
$$

Its sign changes at $a_{\rm dep}=1/[4(h_C-e_C)]$. This is a different criterion from global vacuum nonnegativity.

For a nonzero carrier norm $Q_C=\int|\chi|^2$, the signed charge and kinetic energy obey

$$
\mathcal Q_a=Q_C-2a\operatorname{Im}\int\chi^*\dot\chi,
\qquad
 a\int|\dot\chi|^2\ge\frac{(Q_C-\mathcal Q_a)^2}{4aQ_C}.
$$

The canonical phase rotation gives the exact Hamiltonian relation

$$
H_{\rm can}/\mathcal N_Q=H_{\rm original}/\mathcal N_Q+\frac{\mathcal Q_a}{2a}.
$$

A localized single-frequency stationary carrier $\chi=e^{-i\omega t}c(\mathbf x)$ with zero signed charge and $Q_C>0$ requires $\omega=-1/(2a)$. It is static in canonical variables. For regular finite-energy scalar profiles on $\mathbb R^d$ with the stated vacuum boundary, define $T\ge0$ as their spatial-gradient energy and $V=\int V_a$. Spatial dilation gives

$$
E(\lambda)=\lambda^{d-2}T+\lambda^dV,
\qquad (d-2)T+dV=0
$$

at a stationary state. For $d>2$, nonnegative $V_a$ excludes a nontrivial such state. If a nontrivial stationary state exists with a potential taking negative values, the same dilation has

$$
E''(1)=-2(d-2)T<0.
$$

The variation remains in the zero-signed-charge space. These statements concern a regular single-frequency scalar stationary ansatz. They make no nonexistence claim about charged states, oppositely charged separated excitations, multi-frequency dynamics, quantum bound states or additional topological sectors.

## 2. Frozen finite numerical schedule

The primary program is `computations/matter_formation_parent_vacuum.py`. The independent program is `computations/verify_matter_formation_parent_vacuum.py`; it must not import primary computational logic.

The parent values, in this order, are

$$
a\in\{1/64,1/32,1/16,1/8,1/4,0.9a_{\rm vac},a_{\rm vac},1.1a_{\rm vac},1/2,1\}.
$$

The schedule tests both boundaries. It does not scan for a preferred physical coefficient. Each primary row records $a,B,h_C-B$, the global minimum value, the fully depleted mass squared, the factorization residual and the diagnostics below. The primary evaluates the factorization directly on the 20 pairs $z\in\{0,1/4,1,2\}$ and $n\in\{0,1/4,\sqrt2,4,8\}$.

### 2.1 Independent homogeneous minimization

The verifier minimizes the unreduced two-variable polynomial on $0\le z\le2$, $0\le n\le8$ using SciPy L-BFGS-B and its analytic gradient, with `ftol=1e-14`, `gtol=1e-10`, `maxiter=2000` and `maxls=40`. All 25 starts from $z\in\{0,1/4,1/2,1,2\}$ and $n\in\{0,1/2,1,3,8\}$ are retained. Boundary evaluations at $(z,n)=(1,0)$ and $(0,\max(h_C-B,0)/u_C)$ are included. At least one numerically successful endpoint must attain the predicted minimum; reporting only the analytic boundary evaluation cannot pass this comparison. An optimizer failure is retained and fails execution qualification if its projected gradient exceeds $10^{-7}$; a small projected gradient can qualify independently of the optimizer message.

The compact domain contains every negative global minimum: $z\ge1$ has nonnegative potential, and $n\ge2h_C/u_C$ has nonnegative potential by the original polynomial. At the specified coefficients $2h_C/u_C<8$. The algebra establishes this bound; finite starts alone supply no global-optimization theorem.

### 2.2 Charge and Hamiltonian witnesses

Use the three complex carrier values $(1+0.5i,-0.25+0.75i,0.4-0.3i)$, positive integration weights $(1,0.7,1.3)$ and mediator values $(0.2,0.8,1.1)$. For each $a$ and target signed charge $\mathcal Q_a\in\{-2,0,3\}$, set

$$
\kappa=\frac{Q_C-\mathcal Q_a}{2aQ_C},\qquad
\dot\chi=i\kappa\chi+\eta.
$$

Evaluate both $\eta=0$ and the projection of $\eta_0=(-0.2+0.1i,0.3-0.4i,0.7+0.2i)$ onto $\operatorname{Im}\sum_jw_j\chi_j^*\eta_j=0$. The primary retains all 60 witnesses. The verifier reconstructs the complex vectors from the declared constants, checks the signed charge and Hamiltonian shift directly, and checks that the kinetic excess over the bound equals $a\sum_jw_j|\eta_j|^2$. These are finite algebraic witnesses of the continuum Cauchy–Schwarz proof.

### 2.3 Spatial dilation witnesses

Use the smooth three-dimensional profiles

$$
f(r)=1-\tfrac12e^{-r^2/2},\qquad c(r)=e^{-r^2/8}.
$$

For every $a$, record $T$, $V$ and $E(\lambda)$ at $\lambda\in\{1/2,3/4,1,5/4,3/2\}$, with both profile widths multiplied by $\lambda$. The primary uses closed Gaussian integrals. The verifier independently integrates the original radial gradient and potential densities on $[0,\infty)$ with SciPy `quad`, `epsabs=1e-10`, `epsrel=1e-10`, `limit=300`. It compares the direct energy with $\lambda T+\lambda^3V$. These profiles are integration witnesses, not stationary states. The stationary negative-dilation statement follows from the variational identity, not from declaring these profiles stationary.

## 3. Criteria and stopping rule

Every algebraic factorization, charge, Hamiltonian and kinetic-bound residual must be at most $10^{-11}$ after division by the maximum of one and the absolute terms being compared. Every independent homogeneous minimum must agree within $10^{-8}\max(1,|V_{\min}|)$. Every independent Gaussian energy must agree within $10^{-8}\max(1,|E|,T,|V|)$. All floats must be finite and the complete frozen schedule must be present exactly once. The verifier must reject changed reported values, missing rows and source/specification identity mismatches.

The finite numerical verdict is `PASS` only if every declared check passes; otherwise it is `FAIL`. This verdict qualifies implementation of the conditional identities. It supplies no physical vacuum selection, dynamical or quantum stability verdict. No coefficient, tolerance, initial point or optimizer setting changes after execution. An implementation error requires an explicit source-repair record and a new output directory; it cannot be hidden by overwriting a receipt.

Default primary and independent output directory: `runs/20260906_matter_formation_parent_vacuum/`. Primary output is `results.json`; independent output is `verification.json`. Both programs refuse to overwrite an existing receipt. The primary records canonical CRLF-to-LF SHA-256 identities of both sources and this preregistration. The verifier checks those identities before calculations and records the raw primary receipt SHA-256. Every reported row and comparison is reconstructed independently. All raw numerical rows and minimizer endpoints are retained. Reproduction in a new directory leaves the frozen schedule unchanged.

## References

- `foundations/particle-stationary-action-closure.md` §8.8—positive-inertia parent, charge and canonical field normalization.
- `computations/matter-formation-hyperbolic-parent-prereg.md`—Gaussian correspondence family and coefficient provenance.
- `computations/matter-formation-continuum-report.md` §§6–8—prepared binding, constrained spatial scope and conditional pair correspondence.
- `parameter-inventory.md`—Mapped interaction coefficient and unselected temporal/action normalization.
