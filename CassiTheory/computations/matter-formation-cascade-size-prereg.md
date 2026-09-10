# Conditional Cascade-Size Normalization Test

## Status: Hypothesized cascade assignment / Mapped empirical inputs—September 2026

## Abstract

The dimensionful cascade can be read as a hierarchy of candidate spatial coherence scales, while the energy of a localized object must be calculated from the field configuration that occupies a selected scale. This frozen calculation tests the mass implication of that interpretation in the existing conditional massive $SU(2)$ chiral benchmark. Cascade step $n=95$ fixes the isoscalar degree-density RMS radius, the pion mass fixes the dimensionless vacuum-mass coefficient, and the measured nucleon–Delta splitting fixes the remaining collective-rotation scale. Before any profile solve, the step-95 length differs from the empirical isoscalar radius by $50.1099\%$, so the radius assignment is already `CONTRADICTS` and the combined normalization is `REJECT`. The bounded numerical calculation asks only what absolute baryon mass this contradicted assignment would imply. The absolute mass origin is withheld from the coefficient extraction. The step-95 assignment is Mapped from QCD-scale data, and neither the chiral action nor its particle interpretation is derived from the registered real-density Cassi fields.

## 1. Question and scope

The calculation asks one narrow descriptive question:

> If cascade step 95 is treated as the physical RMS size of the conditional degree-one chiral configuration despite its preregistered radius contradiction, what absolute nucleon mass follows after using only the pion mass and a directly registered nucleon–Delta splitting to set the remaining dimensional scales?

The result can support or contradict the conditional mass implication. It cannot rescue the step-95 radius assignment, which fails before execution, and it cannot establish a universal integer size law, select the microscopic action, derive colour or QCD, supply a quantum vacuum or renormalization prescription, derive Finkelstein–Rubinstein statistics, or demonstrate formation from degree-zero initial data. The numerical run remains warranted only as the bounded scale-to-energy calculation requested by the size-first interpretation; it is not a second attempt to make the rejected normalization pass.

The primary and independent programs are written before either is executed. They never import each other. Any change to a constant, equation, radius definition, bracket, threshold, output directory, or verdict rule requires a new protocol and fresh output paths.

## 2. Frozen inputs and provenance

Use

$$
\varphi=\frac{1+\sqrt5}{2},\qquad
\ell_{\rm Pl}=1.616255\times10^{-35}\ \mathrm m,
\qquad
\ell_{95}=\ell_{\rm Pl}\varphi^{95}.
$$

The exact program value is computed from the displayed decimal Planck length and binary64 $\varphi$; it is expected to be approximately $1.15434521\ \mathrm{fm}$. Step 95 is the repository's Mapped QCD-scale assignment. It is not an independent prediction and must be labelled as an external scale-selection input in every receipt.

Use the displayed physical inputs

$$
\hbar c=197.3269804\ \mathrm{MeV\,fm},\qquad
M_\pi=138.039\ \mathrm{MeV},
$$

$$
d=293.081246\ \mathrm{MeV}.
$$

Treat this spectroscopy difference as the sole collective-rotation input. Do not calculate it from an absolute mass inside either program. The absolute comparison values

$$
M_N^{\rm obs}=938.918754\ \mathrm{MeV},
\qquad
M_\Delta^{\rm obs}=1232.0\ \mathrm{MeV}
$$

are withheld until $M_N^{\rm pred}$ and $M_\Delta^{\rm pred}$ have been fixed. The direct splitting shares experimental provenance with those masses and therefore does not make the absolute-mass check a statistically independent holdout; it withholds only the additive mass origin.

The empirical comparison radius is

$$
r_{I=0}^{\rm obs}=0.769\ \mathrm{fm}.
$$

This is the same rounded isoscalar electric-radius target used by the existing conditional benchmark. It is not fitted. The preregistered analytic comparison is

$$
\frac{\ell_{95}}{r_{I=0}^{\rm obs}}-1
=0.5010991027235701.
$$

Consequently, `cascade_radius_assignment` is fixed before numerical execution to `CONTRADICTS—step-95 radius misses the empirical isoscalar radius by 50.1099 percent`, and `size_first_normalization` is fixed to `REJECT—step-95 isoscalar-radius assignment fails the analytic discriminator`. Neither verdict can be changed by the BVP result. The comparison values and the step-95 assignment retain their external or Mapped provenance; no $\varphi$ derivation of QCD is claimed.

For context only, reconstruct the frozen three-mass-calibrated reference profile at

$$
\mu_{\rm ref}=0.5266577616452649
$$

and compare its recomputed profile integrals with `runs/20260907_matter_formation_chiral_lattice/structure_recovery1/results.json`. The reference receipt is not an input to either numerical solution and cannot substitute for a failed reconstruction.

## 3. Conditional profile and size equation

Use the added leading massive chiral hedgehog from `computations/matter-formation-conditional-baryon-prereg.md`. In dimensionless radius $x=e_Bf_Br$, solve

$$
F_{xx}=
\frac{-2xF_x-\sin(2F)\left(F_x^2-1-\sin^2F/x^2\right)
+\mu^2x^2\sin F}
{x^2+2\sin^2F},
$$

with

$$
F(\epsilon)-\epsilon F_x(\epsilon)=\pi,
\qquad F(L)=0,
\qquad \epsilon=10^{-5}.
$$

For every converged profile compute

$$
\begin{aligned}
\mathcal E_2&=4\pi\int_0^L\left(x^2F_x^2+2\sin^2F\right)dx,\\
\mathcal E_4&=4\pi\int_0^L\left(2\sin^2F\,F_x^2+\frac{\sin^4F}{x^2}\right)dx,\\
\mathcal E_m&=8\pi\int_0^L\mu^2x^2(1-\cos F)dx,\\
s&=\frac{\mathcal E_2+\mathcal E_4+\mathcal E_m}{4},\\
\Lambda&=8\int_0^L x^2\sin^2F\left(1+F_x^2+\frac{\sin^2F}{x^2}\right)dx,\\
R_0^2&=-\frac{2}{\pi}\int_0^Lx^2\sin^2F\,F_x\,dx,\\
R_{M0}^2&=
\frac{\int_0^Lx^4\sin^2F\,F_x\,dx}
{\int_0^Lx^2\sin^2F\,F_x\,dx}.
\end{aligned}
$$

The degree-density RMS radius is

$$
r_{I=0}=\lambda_B\sqrt{R_0^2},
\qquad
\lambda_B=\frac{\hbar c}{e_Bf_B}.
$$

The size-first hypothesis imposes $r_{I=0}=\ell_{95}$, while the pion mass relation is $M_\pi=\mu e_Bf_B$. Eliminate $e_Bf_B$ and solve the single implicit equation

$$
\boxed{
G(\mu)=\frac{\hbar c\,\mu}{M_\pi}\sqrt{R_0^2(\mu)}-\ell_{95}=0.
}
$$

Search only the frozen interval $0.1\le\mu\le2.5$. Evaluate $G$ on 33 logarithmically spaced points including both endpoints. The calculation qualifies a unique numerical root only if every scan profile converges, the finite scan has exactly one sign-changing adjacent pair, Brent's method remains inside that pair, and the final absolute size residual is at most $10^{-10}\ \mathrm{fm}$. This is numerical uniqueness on the declared scan, not a continuum theorem. A well-resolved scan with zero or multiple sign-changing pairs is a valid negative identifiability result: do not choose a root, do not calculate size-implied masses, and report the root and mass implications as `INCONCLUSIVE`. If there is exactly one sign-changing pair but Brent's method fails, leaves that pair, or returns a final size residual above the threshold, treat it as a numerical failure rather than inventing a scientific verdict.

## 4. Size-first coefficient extraction and predictions

At the root define

$$
\lambda_B=\frac{\ell_{95}}{\sqrt{R_0^2}},
\qquad
P=e_Bf_B=\frac{\hbar c}{\lambda_B}=\frac{M_\pi}{\mu}.
$$

Let $A=f_B/e_B$. The collective-coordinate splitting is

$$
d=\frac{9P^2}{2\pi A\Lambda}.
$$

Use the measured splitting once to determine

$$
A=\frac{9P^2}{2\pi\Lambda d},
\qquad
e_B=\sqrt{\frac{P}{A}},
\qquad
f_B=\sqrt{PA},
\qquad
I_0=\frac{\pi A}{3P^2}.
$$

No absolute baryon mass enters these equations. Predict

$$
M_{\rm cl}=2sA,
\qquad
M_N^{\rm pred}=M_{\rm cl}+\frac d4,
\qquad
M_\Delta^{\rm pred}=M_{\rm cl}+\frac{5d}{4}.
$$

Also report

$$
r_{M,I=0}=\lambda_B\sqrt{R_{M0}^2},
$$

and, using the same leading-order formulas and the predicted nucleon mass,

$$
g_A=-\frac{\pi G_A^{\rm int}}{3e_B^2},
\qquad
g_{\pi NN}=\frac{M_N^{\rm pred}}{f_B}g_A,
$$

where

$$
G_A^{\rm int}=4\int_0^Lx^2\left[
F_x+\frac{\sin2F}{x}+\frac{\sin2F}{x}F_x^2
+\frac{2\sin^2F}{x^2}F_x
+\frac{\sin^2F\sin2F}{x^3}
\right]dx.
$$

The magnetic radius, $g_A$, and $g_{\pi NN}$ are descriptive out-of-fit outputs. No decision depends on them because this protocol is designed to isolate the radius-to-mass question.

## 5. Primary and independent calculations

The primary program is `computations/matter_formation_cascade_size.py`. It solves in $\theta=\pi-F$ on geometric meshes with SciPy `solve_bvp`, tolerance $10^{-8}$ and at most 100,000 nodes. It evaluates the regular-origin segment analytically to leading order and all remaining integrals by adaptive quadrature over the collocation spline. Brent's method solves the implicit size equation. The canonical domain is $L=64$; the full root and all observables are independently repeated at $L=48$ and $L=96$.

The independent program is `computations/verify_matter_formation_cascade_size.py`. It does not import or execute the primary. It solves directly for $F$ with the regular boundary condition on separately constructed mixed linear/geometric meshes, tolerance $3\times10^{-9}$ and at most 150,000 nodes. It evaluates integrals by fixed 24-point Gauss–Legendre quadrature on every mesh panel and performs its own logarithmic scan and bracketed root. It reconstructs all coefficients and predictions from its own profiles before reading scalar predictions from the primary receipt.

Both methods must satisfy items 1–5 at every scan profile and the reference point, and item 10 at the reference point. Items 6–9 apply only if the scan has exactly one sign-changing pair and a root is solved:

1. finite fields, slopes, residuals and profile integrals, together with finite coefficients wherever coefficient extraction applies;
2. BVP solver status zero and maximum reported RMS residual below $3\times10^{-8}$;
3. degree within $2\times10^{-8}$ of one;
4. $|F(L)|\le2\times10^{-10}$;
5. the massive finite-domain virial residual
   $$
   \frac{|\mathcal E_2-\mathcal E_4+3\mathcal E_m+4\pi L^3F_x(L)^2|}
   {\mathcal E_2+\mathcal E_4+\mathcal E_m}
   \le2\times10^{-7};
   $$
6. positive $R_0^2$, $R_{M0}^2$, $s$, $\Lambda$, $A$, $e_B$, $f_B$, and $I_0$;
7. relative reconstruction residuals below $2\times10^{-10}$ for $e_Bf_B=P$, $f_B/e_B=A$, $M_\pi=\mu P$, and the input splitting;
8. agreement between primary and independent $\mu$, $s$, $\Lambda$, $R_0^2$, $R_{M0}^2$, $P$, $A$, $e_B$, $f_B$, $M_N^{\rm pred}$, and $M_\Delta^{\rm pred}$ within $8\times10^{-5}$ relative;
9. $L=48$ and $L=96$ values of $\mu$ and $M_N^{\rm pred}$ each within $3\times10^{-4}$ relative of the $L=64$ value in each method;
10. reference-point $s$, $\Lambda$, and $R_0^2$ within $8\times10^{-5}$ relative of the immutable structure receipt values.

## 6. Evidence contract and controls

The primary writes `results.json` and `frozen_protocol.txt` under `runs/20260909_matter_formation_cascade_size/`; when and only when the frozen scan has one qualifying root, it also writes `root_profile.npz`. The independent program writes `verification.json` and `frozen_protocol.txt` under `runs/20260909_matter_formation_cascade_size_verification/`; under the same condition it also writes `independent_root_profile.npz`. Each program refuses to overwrite a nonempty output directory. JSON contains no NaN or Infinity. NPZ files contain only finite float64 arrays and a fixed scalar basis.

Every receipt records the canonical-LF SHA-256 identities and root-relative paths of this preregistration and both source programs, raw hashes and byte sizes for artifacts, constants, scan rows, solver diagnostics, domain rows, reference reconstruction, coefficient extraction, predictions, individual gates, verdict strings, and `complete_physical_matter_formation=false`. The frozen protocol file is the exact text of this preregistration between the H1 and References heading, with LF line endings. The verifier checks source hashes, the primary JSON and NPZ schemas, raw artifact hashes, shapes, keys and finiteness before scientific comparison. Duplicate gate names or omitted required keys fail the evidence contract.

Run one missing-preregistration primary control and one missing-primary verifier control in fresh directories. Each actual CLI must exit nonzero, retain a typed failure receipt, and carry only `INCONCLUSIVE` scientific verdicts. The controls cannot count as scientific runs.

## 7. Frozen verdict tree and stopping rule

The analytic `cascade_radius_assignment` and `size_first_normalization` verdicts in §2 remain `CONTRADICTS` and `REJECT` under every execution outcome. They depend only on frozen constants and must be reproduced before either program starts a profile solve.

If any source identity, output contract, control, finiteness, BVP, virial, reference-reconstruction, applicable domain, or independent-comparison gate fails, set `numerical_pass=false`; set the root and mass-implication verdicts to `INCONCLUSIVE`; and stop without interpreting the numerical prediction. The prior analytic rejection remains valid.

If all 33 scan profiles are numerically qualified but the finite scan has zero or multiple sign-changing adjacent pairs, set `numerical_pass=true`, `cascade_size_root=INCONCLUSIVE—size normalization is non-identifiable on the frozen scan`, and both absolute-mass verdicts to `INCONCLUSIVE—no unique size-implied mass`. Write no root-profile NPZ and stop. If the scan has exactly one sign-changing pair but the bracketed solver or final residual condition fails, set `numerical_pass=false` and use `INCONCLUSIVE—root solver failed its frozen numerical condition` for the root and both mass implications. The prior analytic rejection remains valid in either branch.

If every numerical and evidence gate passes and the scan has exactly one qualifying root:

1. `cascade_size_root` is `SUPPORTS—unique size-normalization root on the frozen scan`.
2. `absolute_nucleon_mass` is `SUPPORTS—conditional size-implied nucleon mass agrees within 10 percent` when
   $$
   |M_N^{\rm pred}/M_N^{\rm obs}-1|\le0.10;
   $$
   otherwise it is `CONTRADICTS—conditional size-implied nucleon mass misses 10 percent`.
3. `absolute_delta_mass` is `SUPPORTS—conditional size-implied Delta mass agrees within 10 percent` when
   $$
   |M_\Delta^{\rm pred}/M_\Delta^{\rm obs}-1|\le0.10;
   $$
   otherwise it is `CONTRADICTS—conditional size-implied Delta mass misses 10 percent`. Because the measured splitting is an input, this is a consistency translation of the nucleon result rather than an independent discriminator.
4. `cascade_radius_assignment` remains `CONTRADICTS—step-95 radius misses the empirical isoscalar radius by 50.1099 percent`.
5. `size_first_normalization` remains `REJECT—step-95 isoscalar-radius assignment fails the analytic discriminator`.
6. `matter_formation` remains `INCONCLUSIVE—conditional normalization does not select or form physical matter`, and `complete_physical_matter_formation` remains false under every result.

Stop after the primary, independent verifier, and two rejection controls. Do not alter the cascade step, radius definition, splitting input, root interval, model terms, domain thresholds, or 10-percent descriptive mass threshold in response to the outcome.

## References

- `foundations/dimensionful-cascade.md` §§1–3—the Planck-anchored dimensionful cascade and the status of step assignments.
- `foundations/quark-confinement.md` §3—the Mapped step-95 QCD-scale assignment and its empirical provenance.
- `computations/matter-formation-conditional-baryon-prereg.md` §§1–4—the conditional massive chiral action, collective-coordinate formulas and radius definitions.
- `computations/matter-formation-continuum-report.md` §§29, 32, 76—the microscopic non-identifiability result, the massive chiral benchmark and the current formation boundary.
- `foundations/matter-completion-boundary.md` §§12–16—the physical matter completion requirements and conditional baryon scope.
- `runs/20260907_matter_formation_chiral_lattice/structure_recovery1/results.json`—immutable three-mass-calibrated reference profile used only for reconstruction checks.
