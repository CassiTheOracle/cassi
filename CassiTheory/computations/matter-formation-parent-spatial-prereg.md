# Scalar Parent Angular and Phase Qualification

## Status: Derived conditional spatial identities / Preregistered numerical qualification / Hypothesized physical parent—September 2026

## Abstract

The positive-inertia scalar parent has independently verified positive radial fixed-signed-charge curvature on twelve population-256 embeddings and passing radial domain/resolution comparisons for that subset. This calculation tests the remaining angular and phase sectors on the same four immutable spatial profiles. It derives the scalar operators from the parent constraint, distinguishes finite-box symmetry errors from exact continuum identities, and freezes a combined scalar spatial decision without claiming nonlinear persistence or physical matter formation. The population-16 campaign retains its separate inconclusive domain verdict and is not repeated.

## 1. Parent constraint and exact continuum identities

Use the scale-independent, topologically trivial scalar energy with real mediator amplitude $f$, complex carrier $\chi$ and $k=k_{Cx}>0$. Let $N=\int|\chi|^2$ vary at fixed signed parent charge $\mathcal Q$. The minimized Hamiltonian is $E_{\rm sc}+G(N)$, where $G=(N-\mathcal Q)^2/(4aN)$. At the prepared stationary profile $\chi=c>0$, $G'=-\omega_C$ and $\omega_C=\omega+a\omega^2$. Only the spherically symmetric real amplitude has the rank-one $G''\nabla N\nabla N^T$ correction. The other second variations contain $\omega_C$, including its $a\omega^2$ term.

With $U=e_C-h_C(1-f^2)$ and $D_\ell=-\partial_r^2-2r^{-1}\partial_r+\ell(\ell+1)/r^2$, the operators are

$$
H_\ell=\begin{pmatrix}
D_\ell+u_\rho(3f^2-1)+2h_Cc^2&4h_Cfc\\
4h_Cfc&kD_\ell+2(U-\omega_C)+6u_Cc^2
\end{pmatrix},\quad \ell\ge1,
$$

$$
L_\ell=kD_\ell+2(U-\omega_C)+2u_Cc^2,\quad \ell\ge0.
$$

For exact regular nodeless stationary fields, $L_0c=0$. The identity for $b=c\vartheta$ is

$$
\langle b,L_\ell b\rangle=4\pi k\int_0^\infty
[r^2c^2(\vartheta')^2+\ell(\ell+1)c^2\vartheta^2]dr\ge0.
$$

If also $f'>0$ and $c'<0$ on $0<r<\infty$, differentiation gives $H_1(f',c')^T=0$. Write $v=(f',-c')^T$, $B=4h_Cfc>0$, $J=\operatorname{diag}(1,-1)$ and $y=(v_1\xi_1,v_2\xi_2)^T$. Then

$$
\langle y,JH_1Jy\rangle=4\pi\int_0^\infty r^2
[v_1^2(\xi_1')^2+k v_2^2(\xi_2')^2+Bv_1v_2(\xi_1-\xi_2)^2]dr\ge0.
$$

Both statements start on compactly supported regular perturbations and extend only with vanishing boundary terms. Exact continuum monotonicity, coercivity and translation symmetry are hypotheses; they are not inferred from sampled finite-box differences. Positive angular ordering gives $H_\ell-H_1=[\ell(\ell+1)-2]\operatorname{diag}(1,k)/r^2$ for $\ell\ge2$. The specification in `computations/matter-formation-stability-prereg.md` is the $k_{Cx}=1$ specialization of the general stiffness.

The exterior spatial gaps are $2u_\rho$ and $2(e_C-\omega_C)$. In canonical carrier variables, $\Omega=\sqrt{1+4a\omega_C}/(2a)$ and $M_a^2(1)-\Omega^2=(e_C-\omega_C)/a$. The completely depleted-mediator carrier mass squared is $M_a^2(0)=1/(4a^2)+(e_C-h_C)/a$; it is not a mediator mass. Record these quantities rather than impose an unrelated $\omega<m$ rule.

## 2. Immutable inputs and selection

Keep exactly $u_\rho=4$, $u_C=k_{Cx}=1$, $e_C=0.75$, $h_C=2.9598260763447164$. The coupling remains Mapped. Read these source files from `runs/20260906_matter_formation_radial/` without relaxation, interpolation or alteration:

| Identifier | Radius | Cells | Raw SHA-256 |
|---|---:|---:|---|
| `q256_R12_n192_w2` | 12 | 192 | `ce3d7efcf133fd2fd5776203a86d53469f4b91b4919ca1bbdcce054dc02233ba` |
| `q256_R12_n384_refine` | 12 | 384 | `e450c22a6baf8312fa67ca58745ad593879bf6d18615a83ad0cbe8dacabb11d5` |
| `q256_R12_n768_refine` | 12 | 768 | `95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a` |
| `q256_R24_n768_refine` | 24 | 768 | `7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66` |

Every prepared source has $Q_C=256$. This subset is selected because its completed charged radial domain/resolution comparisons qualify. No angular or phase spectrum of this subset is used for selection. The population-64 unqualified source and the population-16 domain-inconclusive subset remain outside the calculation.

Reuse, without recomputation, the accepted radial evidence in `runs/20260906_matter_formation_charged_stability/`:

- `results.json`: raw SHA-256 `540bf259441b42ac476189dcd8593ae3b57a4fe25bb8fe17c846d5465068b0bc`.
- `verification.json`: raw SHA-256 `7f299ed6401014760b174895781d253ffebe6fad3c2a11e801506c9759e2d255`.

Both files must have numerical pass and empty failures. Their input identity link must agree. The three canonical source identities in the primary radial receipt must match the current read-only files. All twelve population-256 parent rows at $a=1/64,1/32,1/16$ must carry radial SUPPORTS with their minima above their source thresholds. All six population-256 radial comparisons must pass. The population-16 aggregate is not transferred to this selected subset, and its verdict is not changed.

## 3. Finite-volume reconstruction and measurements

Use exact spherical cell volumes $V_i=4\pi(r_{i+1/2}^3-r_{i-1/2}^3)/3$, uniform $\Delta r=R/n$, interior face conductance $4\pi r_{i+1/2}^2/\Delta r$, and outer half-cell Dirichlet conductance $8\pi R^2/\Delta r$. Perturbations vanish at the outer boundary and have zero origin flux. Preserve the nonzero outer mediator load in the first variation. In mass-weighted coordinates,

$$
D_\ell=V^{-1/2}KV^{-1/2}+\ell(\ell+1)\operatorname{diag}(4\pi\Delta r/V_i).
$$

Recompute $N=\sum_i V_ic_i^2$, $\omega_C=c^T\nabla_cE_{\rm sc}/(2N)$ and the source residuals. Use

$$
r_f=\frac{\|V^{-1/2}\nabla_fE_{\rm sc}\|}{\max(1,\|\sqrt V(1-f)\|)},\qquad
r_c=\frac{\|V^{-1/2}(\nabla_cE_{\rm sc}/2-\omega_CVc)\|}{\sqrt N}.
$$

Source qualification requires relative population error below $10^{-10}$, $r_f,r_c<10^{-4}$, positive $N$, and nonnegative sampled amplitudes $f_i,c_i\ge0$. Let $\eta=\max(5\times10^{-4},10r_f,10r_c)$. Record minimum sampled $f,c$, minimum consecutive $f$ difference and maximum consecutive $c$ difference as descriptive quantities only. The strict continuum positivity and monotonicity assumptions in §1 are not inferred from these finite samples and are not substituted for spectral qualification.

For every source compute the six lowest algebraic eigenpairs of $H_1,H_2,L_0,L_1$. The primary uses dense SciPy EVR. Its vectors use blocked amplitude coordinates $(\sqrt V\delta f,\sqrt V\delta c)$ and ordinary mass-weighted phase coordinates. The independent verifier reconstructs an interleaved two-field symmetric banded matrix, uses SciPy `eig_banded` for each amplitude operator and `eigh_tridiagonal` for each phase operator, and directly checks the primary vectors against its own operators. It imports no primary or other campaign computational function.

Normalize $p=\sqrt Vc$ and $t=(\sqrt Vf',\sqrt Vc')$, with second-order centered interior derivatives and second-order one-sided endpoint derivatives at the sampled cell centers. The symmetry index is the index of maximum absolute overlap among the six computed vectors; use the first index on an exact tie. Record its overlap, eigenvalue and direct operator residual $\|L_0p\|$ or $\|H_1t\|$. Define `amp1_gap` and `phase0_gap` as the smallest eigenvalue among the five vectors other than the identified symmetry index. Do not project or remove an eigenpair before checking its sign.

Record exterior spatial gaps and, for each of the three parent coefficients, the inherited radial minimum/verdict, $\omega$, $\Omega$, $M_a^2(1)$, $(e_C-\omega_C)/a$ and $M_a^2(0)$. Compare the positive $a$ schedule explicitly with $a_{\rm dep}=1/[4(h_C-e_C)]$ and $a_{\rm vac}=1/[4(h_C-e_C-\sqrt{u_\rho u_C/2})]$. These thresholds are defined at the fixed coefficient point and select no physical value.

## 4. Numerical and scientific decisions

Every retained value must be finite. Each normalized eigenpair residual $\|Av-\lambda v\|/\max(1,|\lambda|)$ and maximum-entry orthonormality error must be below $10^{-8}$. Independent eigenvalues must agree within $10^{-7}\max(1,|\lambda|)$; every other reported scalar must agree within $10^{-8}\max(1,|x|,|y|)$. Identity, schedule, shape, dtype, source-qualification or numerical-check failures give numerical FAIL. Failed scientific comparisons do not change the numerical verdict.

A source's scientific sector verdict uses this fixed order:

1. A source or numerical qualification failure gives `INCONCLUSIVE—finite-grid scalar angular and phase energetic qualification`.
2. Any of the four operators having a lowest eigenvalue below $-\eta$ gives `CONTRADICTS—finite-grid scalar angular and phase energetic qualification`. This includes a negative mode with large translation overlap; it is a finite-grid conclusion with no automatic continuum instability inference.
3. Support requires both symmetry overlaps strictly above $0.99$, both symmetry eigenvalues within $\eta$ of zero, both nonsymmetry gaps above $\eta$, and the minima of $H_2,L_1$ above $\eta$. Otherwise return INCONCLUSIVE.
4. When all support requirements hold, return `SUPPORTS—finite-grid scalar angular and phase energetic qualification`.

The sector aggregate gives contradiction precedence, support only when all four sources support, and inconclusive otherwise.

Compare four metrics (`amp1_gap`, the minimum of $H_2$, `phase0_gap`, and the minimum of $L_1$) on the resolution pair $(R,n)=(12,384),(12,768)$ and the same-spacing domain pair $(12,384),(24,768)$. These are eight comparisons. Each tolerance is $\max(0.01\max(|x|,|y|),\eta_x,\eta_y)$. The comparison aggregate is `SUPPORTS—scalar spatial domain/resolution qualification` only if all eight pass, and INCONCLUSIVE otherwise.

The combined scalar-parent verdict is `SUPPORTS—finite-grid scalar parent spatial energetic qualification` only if radial inheritance qualifies, all four source sector verdicts support and all eight new comparisons pass. A qualified sector contradiction gives combined CONTRADICTS; other cases give combined INCONCLUSIVE. The positive angular ordering of $H_\ell$ above $H_2$ and $L_\ell$ above $L_1$ supplies the remaining angular degrees within this discretization. This does not add scale-dependent, gauge, topological, quantum, dynamical or nonlinear claims. It does not establish exact continuum monotonicity, infinite-volume coercivity or matter formation.

## 5. Receipt contract and unsuccessful evidence

Programs are `computations/matter_formation_parent_spatial.py` and `computations/verify_matter_formation_parent_spatial.py`. Default source directory is the radial field directory in §2, inherited radial directory is the charged-stability directory, and output directory is `runs/20260906_matter_formation_parent_spatial/`. Both programs expose `--source-dir`, `--radial-dir` and `--output-dir`; the verifier additionally exposes `--input-dir`, defaulting to the new output directory. Source paths in receipts are repo-relative when possible. Spectral paths are filenames relative to the actual primary output directory.

The primary JSON schema is `cassi.matter-formation.parent-spatial.v1`. Its fields are `schema`, `identities`, `inherited_radial`, `coefficients`, `temporal_bounds`, `rows`, `comparisons`, `numerical_pass`, `sector_verdict`, `comparison_verdict`, `parent_verdict`, `failures`. `identities` has `primary`, `verifier`, `prereg`, each containing `path` and canonical `sha256`. `inherited_radial` contains raw `results` and `verification` path/hash pairs and `qualified`.

Each successful row has `id`, `artifact`, `artifact_sha256`, `R`, `n`, `target_population`, `population`, `omega_C`, `population_relative_error`, `residual_f`, `residual_c`, `eta`, `source_qualified`, `profile`, `asymptotic`, `parents`, `operators`, `symmetries`, `metrics`, `spectra`, `sector_verdict`. `profile` contains `min_f`, `min_c`, `min_f_difference`, `max_c_difference`. `asymptotic` contains `mediator_spatial_gap`, `carrier_spatial_gap`. Each parent has `a`, `radial_minimum`, `radial_verdict`, `omega`, `canonical_frequency`, `exterior_mass_squared`, `exterior_frequency_gap_squared`, `depleted_mass_squared`. `temporal_bounds` contains `a_dep`, `a_vac`.

`operators` has keys `amp1`, `amp2`, `phase0`, `phase1`, each with six `eigenvalues`, six `eigenpair_residuals`, and `orthonormality_error`. `symmetries` has `translation` and `phase`, each containing `index`, `overlap`, `eigenvalue`, `operator_residual`. `metrics` has `amp1_gap`, `amp2_minimum`, `phase0_gap`, `phase1_minimum`. `spectra` has `path` and raw `sha256`. Each `spectra_<id>.npz` has exactly the float64 arrays `<operator>_values` and `<operator>_vectors`; values have shape `(6,)`, amplitude vectors `(2*n,6)`, phase vectors `(n,6)`. Each comparison has `metric`, `pair` (`resolution` or `domain`), `left`, `right`, `absolute_difference`, `tolerance`, `pass`; order is metric order above, then resolution/domain.

The independent schema is `cassi.matter-formation.parent-spatial.verification.v1`. It records the same independently recomputed quantities and scientific verdicts, canonical identities, the raw `input_sha256`, numerical pass and explicit failures; it additionally records independent residual/orthonormality checks of the primary arrays. It must verify the primary's exact source schedule, all named arrays, claimed metrics, gates, parent embeddings, inherited radial scope and scientific verdicts.

Initialization refuses existing own receipts or own spectral artifacts. Hash all canonical source/preregistration text after CRLF-to-LF normalization before numerical work. Each source is processed inside a failure-recording boundary: an invalid source or failed solve records the identifier and error, preserves completed rows and spectra, and continues the remaining fixed schedule. An unavailable successful-row field is never fabricated; the row is omitted and schedule completeness fails. Comparison records are omitted when a required row is absent; missing comparisons are explicit failures. An input identity failure writes a failed receipt without eigensolves. Nonfinite numerical fields in failed diagnostic details are encoded as null with an accompanying failure, never as a successful row. Both programs exit nonzero on numerical failure, including receipt-write failure. Scientific INCONCLUSIVE or CONTRADICTS with numerical PASS does not change process success.

Execute the canonical schedule once after both sources are final. Preserve first-execution receipts. Source repairs require a distinct output directory and explicit execution record; the accepted charged-radial sources and receipts are read-only. No retry, coefficient change, selective omission, profile relaxation or threshold adjustment follows an observed spectrum.

A separate missing-source failure control uses an empty input directory and a fresh output directory at `runs/20260906_matter_formation_parent_spatial/control_missing_sources/`. It must leave failed primary and independent receipts, return nonzero for both, retain source errors and complete no eigenvalue rows. This is a numerical failure-path check and carries no scientific spectrum or stability verdict. The control does not consume or overwrite canonical primary output.

## References

- `foundations/particle-stationary-action-closure.md` §§8.7–8.11—scalar action, signed-charge constraint and conditional spatial identities.
- `computations/matter-formation-charged-stability-prereg.md`—immutable radial source selection, parent embeddings and accepted radial criteria.
- `computations/matter-formation-continuum-report.md` §§7, 10—fixed-population spatial and fixed-signed-charge radial evidence with distinct scopes.
- `computations/matter-formation-stability-prereg.md`—unit carrier stiffness and symmetry-vector conventions.
