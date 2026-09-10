# Conditional Cascade-Size Normalization Numerical Recovery

## Status: Hypothesized cascade assignment / Mapped empirical inputs—September 2026

## Abstract

The step-95 cascade-radius assignment is already rejected by its analytic comparison with the empirical isoscalar electric radius. A conditional massive chiral calculation nevertheless supplies a useful description of what mass follows if that spatial assignment is imposed. The primary calculation completes this boundary-value problem, while the retained direct-$F$ independent executions encounter a binary64 collocation floor at the regular origin and therefore cannot verify it. This recovery freezes one numerical representation change before execution: the verifier evolves $\theta=\pi-F$ on its independently constructed mesh, reconstructs $F$ before evaluating observables, and retains every physical input, equation, scan point, threshold, comparison, verdict string, and stopping rule from the source protocol.

## 1. Source protocol and retained failure

The source protocol is `computations/matter-formation-cascade-size-prereg.md`, canonical-LF SHA-256 `dd9a961dc8777dee0249b4b7d0a15f02c96e2c92bf0d19a28822ff4a9e3f9e27`. Its primary output is `runs/20260909_matter_formation_cascade_size`; its independent output is `runs/20260909_matter_formation_cascade_size_verification`.

The direct-$F$ recovery execution is retained at `runs/20260909_matter_formation_cascade_size_verification_recovery2`. All 33 logarithmically spaced points on the $L=64$ scan terminate with SciPy solver status one. Their maximum RMS residuals span $7.827562275459977\times10^{-6}$ to $2.3190480776459215\times10^{-5}$ after 64,078 to 72,573 retained nodes. The reference solve terminates at 65,272 nodes with maximum RMS residual $1.1897223409514278\times10^{-5}$. A diagnostic locates the largest residual immediately above $\epsilon=10^{-5}$, where a direct binary64 representation stores $F$ as a small displacement from $\pi$ and adaptive mesh refinement differentiates nearly equal numbers.

The failure is numerical: it occurs for every mass parameter, before any root, coefficient, or withheld-mass comparison is available. Replacing the initial profile and algebraically factoring the direct-$F$ right-hand side leave the same origin-localized residual floor. The recovery changes no physical assumption and receives no numerical information from the primary profile.

## 2. Frozen physical inputs and analytic verdict

The recovery retains

$$
\varphi=\frac{1+\sqrt5}{2},\qquad
\ell_{95}=1.616255\times10^{-35}\ \mathrm m\,\varphi^{95},
$$

with $\hbar c=197.3269804\ \mathrm{MeV\,fm}$, $M_\pi=138.039\ \mathrm{MeV}$, the registered splitting literal $d=293.081246\ \mathrm{MeV}$, $M_N^{\rm obs}=938.918754\ \mathrm{MeV}$, $M_\Delta^{\rm obs}=1232.0\ \mathrm{MeV}$, and $r_{I=0}^{\rm obs}=0.769\ \mathrm{fm}$. The reference point remains $\mu_{\rm ref}=0.5266577616452649$.

The analytic precheck remains

$$
\frac{\ell_{95}}{r_{I=0}^{\rm obs}}-1
=0.5010991027235701.
$$

It fixes these verdicts before any profile solve:

- `cascade_radius_assignment=CONTRADICTS—step-95 radius misses the empirical isoscalar radius by 50.1099 percent`;
- `size_first_normalization=REJECT—step-95 isoscalar-radius assignment fails the analytic discriminator`.

No numerical recovery can change either verdict.

## 3. Field equation and conditional predictions

Both programs solve the same massive hedgehog equation

$$
(x^2+2\sin^2F)F_{xx}+2xF_x
+\sin2F\left(F_x^2-1-\frac{\sin^2F}{x^2}\right)
-\mu^2x^2\sin F=0,
$$

with

$$
F(\epsilon)-\epsilon F_x(\epsilon)=\pi,\qquad F(L)=0,
\qquad \epsilon=10^{-5}.
$$

For every profile they reconstruct $s$, $\Lambda$, $R_0^2$, $R_{M0}^2$, degree, $G_A^{\rm int}$, and

$$
G(\mu)=\frac{\hbar c\,\mu}{M_\pi}\sqrt{R_0^2(\mu)}-\ell_{95}.
$$

The scan remains $0.1\le\mu\le2.5$ on 33 logarithmically spaced points. A root is admissible only inside the single sign-changing adjacent pair with final absolute residual at most $10^{-10}\ \mathrm{fm}$.

At an admissible root,

$$
\lambda_B=\frac{\ell_{95}}{\sqrt{R_0^2}},\qquad
P=\frac{\hbar c}{\lambda_B}=\frac{M_\pi}{\mu},
$$

$$
A=\frac{9P^2}{2\pi\Lambda d},\qquad
e_B=\sqrt{\frac{P}{A}},\qquad
f_B=\sqrt{PA},\qquad
I_0=\frac{\pi A}{3P^2},
$$

and

$$
M_{\rm cl}=2sA,\qquad
M_N^{\rm pred}=M_{\rm cl}+\frac d4,\qquad
M_\Delta^{\rm pred}=M_{\rm cl}+\frac{5d}{4}.
$$

The magnetic radius, $g_A$, and $g_{\pi NN}$ remain descriptive outputs without decision weight.

## 4. Recovery method

The primary program remains `computations/matter_formation_cascade_size.py`. It solves in $\theta=\pi-F$ on geometric meshes with SciPy `solve_bvp`, tolerance $10^{-8}$, and at most 100,000 nodes. It uses leading-order regular-origin quadrature followed by adaptive quadrature over the collocation spline.

The independent program remains `computations/verify_matter_formation_cascade_size.py`. For this recovery it solves the transformed equation for $\theta=\pi-F$ on its separately constructed mixed geometric-linear meshes with tolerance $3\times10^{-9}$ and at most 150,000 nodes. Its implementation is independent of the primary: it constructs its own mesh and initial profile, reconstructs $F$ and $F_x$ from its own solution, evaluates every integral by fixed 24-point Gauss–Legendre quadrature on each refined panel, performs its own scan and bracketed root, and reconstructs all coefficients before reading primary predictions. It does not import or execute the primary program and does not read a primary field profile.

This representation change removes the subtraction of an $O(10^{-5})$ displacement from a stored $O(1)$ field inside the collocation state. It leaves the differential equation and boundary data invariant.

## 5. Frozen qualification thresholds

The canonical domain remains $L=64$. Full independent roots and observables are repeated at $L=48$ and $L=96$ only after the canonical scan has one qualifying root. Every scan and reference profile must have finite fields, slopes, residuals, and integrals; solver status zero; maximum RMS residual below $3\times10^{-8}$; degree within $2\times10^{-8}$ of one; and $|F(L)|\le2\times10^{-10}$.

The finite-domain virial residual remains

$$
\frac{|\mathcal E_2-\mathcal E_4+3\mathcal E_m+4\pi L^3F_x(L)^2|}
{\mathcal E_2+\mathcal E_4+\mathcal E_m}
\le2\times10^{-7}.
$$

Root coefficients must be positive and their four reconstruction residuals must remain below $2\times10^{-10}$. The two calculations must agree in $\mu$, $s$, $\Lambda$, $R_0^2$, $R_{M0}^2$, $P$, $A$, $e_B$, $f_B$, $M_N^{\rm pred}$, and $M_\Delta^{\rm pred}$ within $8\times10^{-5}$ relative. Each $L=48$ and $L=96$ value of $\mu$ and $M_N^{\rm pred}$ must lie within $3\times10^{-4}$ relative of the $L=64$ value. Reference $s$, $\Lambda$, and $R_0^2$ must agree with the immutable structure receipt within $8\times10^{-5}$ relative.

## 6. Execution and evidence

Run the final source identities into fresh directories:

- primary: `runs/20260909_matter_formation_cascade_size_recovery3`;
- independent: `runs/20260909_matter_formation_cascade_size_verification_recovery3`;
- final-source missing-primary control: `runs/20260909_matter_formation_cascade_size_verification_missing_primary_control_recovery3`.

The primary writes `results.json`, `frozen_protocol.txt`, and a conditional `root_profile.npz`. The verifier writes `verification.json`, `frozen_protocol.txt`, and a conditional `independent_root_profile.npz`. Each program refuses a nonempty destination. JSON contains no NaN or Infinity. Each NPZ contains only the declared finite float64 arrays and 30-scalar basis. Both receipts retain canonical source identities, artifact hashes and byte sizes, all scan rows, diagnostics, gates, verdicts, and `complete_physical_matter_formation=false`.

The verifier must reproduce the protocol text, validate the primary JSON and NPZ before scientific comparison, and preserve missing or malformed evidence as a typed nonzero failure. The final-source missing-primary control must exit nonzero with `numerical_pass=false`, `complete_physical_matter_formation=false`, and only `INCONCLUSIVE` scientific verdicts.

## 7. Frozen verdict tree

If any source, output, control, finiteness, BVP, virial, reference, domain, or independent-comparison gate fails, set `numerical_pass=false` and use plain `INCONCLUSIVE` for the root and both mass implications. The analytic `CONTRADICTS` and `REJECT` verdicts remain fixed.

A qualified scan with zero or multiple sign-changing adjacent pairs reports:

- `cascade_size_root=INCONCLUSIVE—size normalization is non-identifiable on the frozen scan`;
- `absolute_nucleon_mass=INCONCLUSIVE—no unique size-implied mass`;
- `absolute_delta_mass=INCONCLUSIVE—no unique size-implied mass`.

If the unique bracketed solver fails, all three use `INCONCLUSIVE—root solver failed its frozen numerical condition`.

If every gate passes and the scan contains one qualifying root, report:

- `cascade_size_root=SUPPORTS—unique size-normalization root on the frozen scan`;
- `absolute_nucleon_mass=SUPPORTS—conditional size-implied nucleon mass agrees within 10 percent` when the relative deviation is at most 0.10, otherwise `CONTRADICTS—conditional size-implied nucleon mass misses 10 percent`;
- `absolute_delta_mass=SUPPORTS—conditional size-implied Delta mass agrees within 10 percent` when the relative deviation is at most 0.10, otherwise `CONTRADICTS—conditional size-implied Delta mass misses 10 percent`.

Under every branch, `matter_formation=INCONCLUSIVE—conditional normalization does not select or form physical matter` and `complete_physical_matter_formation=false`. The calculation stops after this recovery. No threshold, interval, scale assignment, observable target, or solver budget may be changed in response to its result.

## References

- `computations/matter-formation-cascade-size-prereg.md`—source physical protocol and direct-$F$ numerical specification
- `computations/matter-formation-continuum-report.md`—matter-formation evidence record and completion boundary
- `foundations/matter-completion-boundary.md`—physical requirements for a complete matter mechanism
- `runs/20260909_matter_formation_cascade_size_verification_recovery2/verification.json`—retained direct-$F$ numerical-failure receipt
