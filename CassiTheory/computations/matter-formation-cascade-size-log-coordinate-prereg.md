# Conditional Cascade-Size Normalization Log-Coordinate Recovery

## Status: Hypothesized cascade assignment / Mapped empirical inputs—September 2026

## Abstract

The step-95 cascade-radius assignment is rejected analytically by its comparison with the empirical isoscalar electric radius. A conditional massive chiral calculation still determines what mass follows if that spatial assignment is imposed. The primary calculation qualifies, while independent collocation in both $F$ and $\theta=\pi-F$ encounters an origin-localized adaptive-residual floor. This protocol freezes a regular logarithmic radial coordinate for the independent solver before the full scan is executed. It retains every physical input, field equation, boundary value, scan point, threshold, comparison, verdict string, and stopping rule from the source protocols.

## 1. Source protocols and numerical boundary

The physical source protocol is `computations/matter-formation-cascade-size-prereg.md`, canonical-LF SHA-256 `dd9a961dc8777dee0249b4b7d0a15f02c96e2c92bf0d19a28822ff4a9e3f9e27`. Its primary output name is `runs/20260909_matter_formation_cascade_size`; its independent output name is `runs/20260909_matter_formation_cascade_size_verification`.

The theta-state recovery protocol is `computations/matter-formation-cascade-size-numerical-recovery-prereg.md`, canonical-LF SHA-256 `c4e6ad65a87797e50c5ae1169cd31355f081b22dff0b2f7e4d3be9b35e06e2d4`. Its immutable execution is retained at `runs/20260909_matter_formation_cascade_size_recovery3` and `runs/20260909_matter_formation_cascade_size_verification_recovery3`.

The primary theta calculation qualifies with one root. In the independent calculation, only one of the 33 canonical scan profiles qualifies. The other 32 terminate at the node budget, with maximum RMS residuals across the scan spanning $2.9990730302510507\times10^{-9}$ to $8.211031500765419\times10^{-4}$ and node counts spanning 2,698 to 139,043. The reference solve terminates at 88,052 nodes with maximum RMS residual $2.3382614151803006\times10^{-4}$. Its largest residual is immediately above $\epsilon=10^{-5}$.

Both retained independent methods solve the physical profile accurately enough to reconstruct the reference observables, but their adaptive collocation residuals do not satisfy the frozen status-zero and $3\times10^{-8}$ gates. The singular radial coordinate amplifies a local polynomial residual near the left boundary. The recovery below uses $z=\ln x$ and $p=d\theta/dz$ so that the regular-origin relation becomes $\theta-p=0$ and the collocation mesh resolves equal ratios in $x$ as equal intervals in $z$.

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

## 4. Frozen independent log-coordinate method

The primary program remains `computations/matter_formation_cascade_size.py`. It solves in $\theta=\pi-F$ on geometric $x$ meshes with SciPy `solve_bvp`, tolerance $10^{-8}$, and at most 100,000 nodes. It uses leading-order regular-origin quadrature followed by adaptive quadrature over the collocation spline.

The independent program remains `computations/verify_matter_formation_cascade_size.py`. It constructs the same independent mixed physical mesh: a geometric segment from $\epsilon$ to 1 with ratio 1.015, followed by a linear segment of maximum spacing 0.05 through $L$. The solver coordinate is

$$
z=\ln x,
$$

and each physical mesh point is transformed once to $z_j=\ln x_j$. The evolved states are

$$
\theta=\pi-F,\qquad p=\frac{d\theta}{dz}=x\theta_x.
$$

Define

$$
a=\frac{\sin\theta}{x},\qquad
b=\frac{\sin2\theta}{x},
$$

and evaluate their removable small-$\theta$ limits with $\operatorname{sinc}$. The exact transformed acceleration is

$$
\mathcal A_\theta=
\frac{2(b/2-\theta_x)-b(\theta_x-a)(\theta_x+a)-\mu^2x\sin\theta}
{x(1+2a^2)}.
$$

The logarithmic first-order system is

$$
\frac{d\theta}{dz}=p,\qquad
\frac{dp}{dz}=p+x^2\mathcal A_\theta\!\left(x,\theta,\frac px;\mu\right),
$$

with

$$
\theta(z_\epsilon)-p(z_\epsilon)=0,
\qquad \theta(z_L)=\pi.
$$

The fixed seed remains $\theta=2\arctan(x/a_0)$ with $a_0=1/\sqrt2$ and $p=x\,2a_0/(x^2+a_0^2)$, independent of $\mu$. SciPy `solve_bvp` retains tolerance $3\times10^{-9}$ and at most 150,000 nodes.

Every observable is integrated over physical $x$. The independent program evaluates its own spline at $z=\ln x$, reconstructs $F=\pi-\theta$ and $F_x=-p/x$, and uses $\sin F=\sin\theta$, $\sin2F=-\sin2\theta$, and $\cos F=-\cos\theta$. It retains fixed 24-point Gauss–Legendre quadrature on every refined physical panel, performs its own scan and bracketed root, and reconstructs all coefficients before reading primary predictions. It does not import or execute the primary program and does not read a primary field profile.

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

- primary: `runs/20260909_matter_formation_cascade_size_recovery4`;
- independent: `runs/20260909_matter_formation_cascade_size_verification_recovery4`;
- final-source missing-primary control: `runs/20260909_matter_formation_cascade_size_verification_missing_primary_control_recovery4`.

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
- `computations/matter-formation-cascade-size-numerical-recovery-prereg.md`—theta-state numerical recovery and frozen failure tree
- `computations/matter-formation-continuum-report.md`—matter-formation evidence record and completion boundary
- `foundations/matter-completion-boundary.md`—physical requirements for a complete matter mechanism
- `runs/20260909_matter_formation_cascade_size_verification_recovery3/verification.json`—retained theta-state numerical-failure receipt
