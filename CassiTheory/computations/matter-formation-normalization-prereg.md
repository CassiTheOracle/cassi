# Physical Normalization and Microscopic Carrier Identification

## Status: Derived conditional normalization and projection identities / Hypothesized physical assignments—September 2026

## Abstract

This calculation asks whether the selected scalar carrier parent can be assigned a physical mass, a physical core length and one unit of its own conserved charge, and whether the existing chiral-scalar Dirac correspondence supplies nonnegative Yang/Yin densities. It fixes all dimensionless scalar coefficients and uses one immutable, finest-resolution population-256 profile. It introduces no new fitted interaction, relaxes no profile and changes no accepted stability verdict. A mass-unit assignment is distinguished from a physical particle identification.

## 1. Questions and execution rule

The two questions are (i) which normalizations follow from a declared physical mass and common propagation speed, and (ii) whether a common dimensional bridge could make the displayed Dirac chiral-scalar correspondence a real, nonnegative density map with a nonzero golden ratio. Both are mathematical identification questions. No production evolution, quantum backreaction, nonlinear stability or empirical particle prediction is claimed.

The canonical calculation runs once centrally after both sources are final. Workers implement without running or importing either source. Algebraic derivation and code inspection may precede execution. The primary and independent verifier use distinct constructions and never import each other. Any source repair after execution requires a distinct output directory and an explicit execution record. Accepted scalar and spatial sources and receipts remain immutable.

Primary: `computations/matter_formation_normalization.py`.
Independent verifier: `computations/verify_matter_formation_normalization.py`.
Canonical output: `runs/20260906_matter_formation_normalization/`.

## 2. Immutable evidence and declared inputs

The accepted spatial primary is `runs/20260906_matter_formation_parent_spatial/results.json`, raw SHA-256 `9445ff33b33b664bf15e09b499bb185f18bfeb9f8a9393c388afef7c7affa79c`. Its independent receipt is `runs/20260906_matter_formation_parent_spatial/verification.json`, raw SHA-256 `2994e44ee2566ecc4e7ce660dc5d0510a088b694e0224086792eda2854f148dd`. Both must have `numerical_pass: true`, empty failures, matching primary-input linkage and matching canonical source identities. Their scientific `INCONCLUSIVE` parent verdict is retained.

The single field is `runs/20260906_matter_formation_radial/q256_R12_n768_refine.npz`, raw SHA-256 `95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a`. Require exactly the six keys `r,volumes,f,c,R,q`, finite float64 radial vectors, and scalar geometry matching the selected accepted spatial row. The script uses $u_\rho=4$, $u_C=1$, $k_{Cx}=1$, $e_C=0.75$, $h_C=2.9598260763447164$. These are existing selected dimensionless coefficients. The stationary multiplier $\omega_C$ is inherited from the hash-bound primary and independently matched spatial row; the profile population and energy are recomputed. The temporal witnesses are exactly $a=1/64,1/32,1/16$.

External unit inputs are the registered $c=299792458\ \mathrm{m/s}$, $\hbar=1.054571817\times10^{-34}\ \mathrm{J\,s}$ and electron rest-energy target $\mathscr E_*=0.511\ \mathrm{MeV}$. The SI conversion $1\ \mathrm{MeV}=1.602176634\times10^{-13}\ \mathrm J$ is exact. The cascade comparison uses the declared $M_{\rm Pl}c^2=1.2209\times10^{22}\ \mathrm{MeV}$ and $\varphi=(1+\sqrt5)/2$. Define $\lambda_*=\hbar c/\mathscr E_*$ and $n_*=\log_\varphi(M_{\rm Pl}c^2/\mathscr E_*)$. Use the displayed input precision; do not substitute a newer mass or a different Planck convention. The cell endpoints are $\ell_j=\hbar c/(M_{\rm Pl}c^2\varphi^{-j})$, $j=107,108$.

The numerical target is a mass calibration of a hypothetical scalar. The electron label identifies the source of the external number and cell assignment. The scalar's conserved $U(1)$ generator is normalized to one unit for the demonstrator; no identification with electric charge is made. The mass anchor, one-charge choice and attempted core-cell map must be recorded in the Fit-Status Ledger. No $h_C$ refit is permitted.

## 3. Conditional normalization identities

The source action has $t_Q=\hbar\ell_Q^2/K_x$, $\mathcal N_Q=\rho_0\ell_Q^3$, and $E_Q=K_x\rho_0\ell_Q=\hbar\mathcal N_Q/t_Q$. The canonical carrier rotation is $\chi=e^{i\widehat t/(2a)}u$. Its wave speed, vacuum frequency and stationary frequency are

$$
v_{\rm car}=\frac{\ell_Q}{t_Q}\sqrt{\frac{k_{Cx}}{2a}},\qquad
M_a^2(1)=\frac{1}{4a^2}+\frac{e_C}{a},\qquad
\Omega=\frac{\sqrt{1+4a\omega_C}}{2a}.
$$

The physical normalization branch explicitly imposes $v_{\rm car}=c$ and the *vacuum canonical scalar mass* $\hbar M_a(1)/t_Q=\mathscr E_*$. This gives

$$
\frac{\ell_Q(a)}{\lambda_*}=\sqrt{\frac{1/(2a)+2e_C}{k_{Cx}}},\qquad
t_Q=\frac{\ell_Q}{c}\sqrt{\frac{k_{Cx}}{2a}},\qquad
K_x=\frac{\hbar\ell_Q^2}{t_Q}.
$$

With $N=\int c^2\,d^3\widehat x$, $D=1+4a\omega_C>0$ and $\mathcal Q=\sqrt D\,N$, the declared single-unit generator normalization is

$$
\mathcal N_Q=1/\mathcal Q,\qquad
\rho_0=\mathcal N_Q/\ell_Q^3.
$$

These equations leave $a$ free and do not select any dimensionless static coefficient. Distinct admissible $a$ giving the same mass, speed and generator normalization are an identifiability witness.

The carrier decay length is a separate quantity:

$$
\ell_{\rm tail}=\ell_Q\sqrt{\frac{k_{Cx}}{2(e_C-\omega_C)}}.
$$

Do not identify $\ell_Q$, $\ell_{\rm tail}$, $\lambda_*$ or the profile radius with each other without an additional physical assignment. In this mass-normalized branch, $\ell_{\rm tail}/\lambda_*=M_a(1)/\sqrt{M_a^2(1)-\Omega^2}>1$ for $D>0$. The exact assignment $\ell_Q=\lambda_*$ would require $a=1/[2(k_{Cx}-2e_C)]$. Check the sign before evaluating a putative positive root.

The existing classical global-vacuum inequality is retained. For these coefficients $a\leq a_{\rm vac}=1/[4(h_C-e_C-\sqrt{u_\rho u_C/2})]$. Since $\ell_Q(a)$ decreases with $a$, its infimum over this allowed interval occurs at $a_{\rm vac}$. Compare this length and its cascade coordinate with the cell $[107,108]$; do not vary the coefficients to enter the cell. The witnesses are additionally checked against the existing depleted-mediator bound $a_{\rm dep}=1/[4(h_C-e_C)]$.

### 3.1 Frequency, energy and charge

A soliton's phase frequency is a chemical potential. It cannot be silently substituted for its total rest energy. Recompute the selected profile's static energy $E_{\rm sc}$ by the spherical finite-volume functional, using exact shell volumes, interior face conductances $4\pi r_{i+1/2}^2/\Delta r$, and the outer half-cell conductance. The mediator has outer value 1 and the carrier outer value 0. The gradient energy is half the squared jump sum, with carrier factor $k_{Cx}$; the local potential is the registered scalar potential.

For each witness, report

$$
\omega=\Omega-\frac1{2a},\quad
H_{\rm orig}=E_{\rm sc}+a\omega^2N,\quad
H_{\rm can}=E_{\rm sc}+\left(\frac1{2a}+\omega_C\right)N,
$$

$$
H_{\rm can}-H_{\rm orig}=\frac{\mathcal Q}{2a},\qquad
H_{\rm can}-\Omega\mathcal Q=E_{\rm sc}-\omega_CN.
$$

The physical canonical energy is $E_QH_{\rm can}$. Its ratio to the imposed vacuum mass target is reported, with no decision threshold equating it to that target. For an exact localized stationary continuum solution, the frequency functional obeys $E_{\rm sc}-\omega_CN=2T/3>0$ by three-dimensional dilation. This last continuum identity is derived conditionally; the finite-box profile does not certify it exactly.

### 3.2 Unit changes and the accepted spatial comparison

Use the accepted failed domain comparison for `amp1_gap` without a new eigensolve. Multiply both endpoint eigenvalues and its tolerance by each of $10^{-12},1,10^{12}$, representing a common change of units. Check that the difference/tolerance ratio and pass/fail decision are invariant. A different normalization for each box is forbidden. Changing $h_C$, $k_{Cx}$, $e_C$ or the profile is a different physical model, outside this calculation.

## 4. Chiral-scalar density and microscopic identity checks

Use the Weyl convention $\gamma^0=\begin{pmatrix}0&I_2\\I_2&0\end{pmatrix}$ and $\gamma^5=\operatorname{diag}(-I_2,I_2)$, with $P_R=(1+\gamma^5)/2$, $P_L=(1-\gamma^5)/2$. The primary uses these four-component matrices. The independent verifier uses two-component contractions, $\psi=(L,R)$:

$$
B_R=\bar\psi P_R\psi=L^\dagger R,\qquad
B_L=\bar\psi P_L\psi=R^\dagger L=B_R^*.
$$

The bilinears are Lorentz chiral scalars, not the positive frame densities $n_R=R^\dagger R$, $n_L=L^\dagger L$. Matrix adjunction must give $(\gamma^0P_R)^\dagger=\gamma^0P_L$. A common positive real mass bridge does not change this conjugacy. If both mapped values are real and nonnegative, they are equal; requiring $B_R=\varphi B_L$ then forces both to vanish.

Use exactly five ordinary complex spinors as algebraic witnesses, written $(L_1,L_2,R_1,R_2)$:

- `complex`: $(1,0,i,0)$;
- `negative`: $(1,0,-1,0)$;
- `equal_positive`: $(1,0,1,0)$;
- `pure_left`: $(1,0,0,0)$;
- `positive_frame_ratio`: $(1,0,\sqrt\varphi,0)$.

These are finite-dimensional bilinear counterexamples, not sampled quantum states or fermion-production simulations. The operator adjoint identity also constrains quantum expectations; normal ordering supplies no Hermiticity repair.

After a hypothetical common positive dimensional bridge, factor out its units and test real density targets $A=\varphi$, $B=1$ with the `complex` witness and unit real coefficient. Evaluate the formal linear term $AB_R+BB_L$ and the formal squared enforcement term $[(B_R-A)^2+(B_L-B)^2]/2$. Record their imaginary parts. An ordinary square is used because that is the displayed ansatz; silently substituting an absolute square would change the interaction. A nonzero imaginary part contradicts a real/Hermitian interaction for general fields. Merely supplying a mass scale cannot repair it.

A local invertible normalization of Lorentz scalar fields preserves their transformation under a $2\pi$ rotation. Record scalar phase $+1$ and the Dirac spin-representation phase $-1$. This is an obstruction to identifying the elementary scalar carrier with a Dirac fermion by normalization. It is not a general prohibition of fermionic topological solitons; such sectors and their quantization are absent from this scalar restriction.

## 5. Output and decision contract

Both programs accept `--source-dir` (default radial source directory), `--spatial-dir` (default accepted spatial directory), and `--output-dir` (default canonical normalization directory). The verifier additionally accepts `--input-dir`, defaulting to the canonical normalization directory. The primary writes only `results.json`; the verifier writes only `verification.json`. Refuse to overwrite either program's own existing receipt or temporary file. Write atomically through an exclusively created sibling temporary file; never delete a pre-existing temporary file.

Primary schema: `cassi.matter-formation.normalization.v1`. Independent schema: `cassi.matter-formation.normalization.verification.v1`. Both receipts contain `schema`, canonical `identities` with keys `primary,verifier,prereg` (each `path,sha256`), `inherited_spatial` with raw `results,verification` identities, `source` with `path,sha256,id`, `constants`, `source_summary`, `unit_family`, `core_assignment`, `unit_rescaling`, `dirac`, `verdicts`, `numerical_pass`, and `failures`. The verifier also records the primary's `input_sha256` and `independent_checks`. Canonical source hashes normalize CRLF to LF. Raw JSON and NPZ hashes never normalize bytes.

`source_summary` records `R,n,N,omega_C,static_energy,gradient_energy`. Each `unit_family` row records `a,D,charge,N_Q,ell_Q_m,t_Q_s,K_x,rho_0,E_Q_J,ell_tail_m,canonical_frequency,exterior_mass,original_frequency,H_original,H_canonical,canonical_energy_over_target,mass_residual,speed_residual,charge_residual,energy_shift_residual,chemical_energy_residual`. The last five are normalized residuals. `core_assignment` records `a_depleted,a_vacuum,lambda_target_m,target_cascade_coordinate,cell_lower_m,cell_upper_m,exact_core_root_denominator,minimum_core_length_m,minimum_core_cascade_coordinate`. `unit_rescaling` contains the original accepted comparison and three rows `factor,ratio,pass`.

`dirac` records the convention, five witness rows (`id,B_R,B_L,n_R,n_L`, complex quantities serialized `[real,imag]`), `adjoint_residual`, `golden_ratio_determinant=1-varphi^2`, the complex linear and squared interaction values, and the two rotation phases. The independent verifier must recompute all numerical payload fields, rather than echoing the primary. Expected discrete structures and values must match exactly; finite floating values agree within $10^{-10}\max(1,|x|,|y|)$. Physical scales and energies smaller than one use a relative tolerance $10^{-10}\max(|x|,|y|,10^{-300})$. Normalization identity residuals must be below $10^{-10}$. Complex-pair comparisons obey the same scaled rule. No NaN or Infinity is accepted.

The primary uses NumPy mass-weighted shell quadrature and matrix bilinears. The independent verifier computes scalar population and energy with direct face/local loops and two-component bilinears. It independently validates the inherited raw hashes, schemas, linked primary hash, canonical spatial identities, selected row, field hash and source geometry before numerical comparison.

The exact `constants` keys are `c_m_s,hbar_J_s,MeV_J,target_energy_MeV,planck_energy_MeV,varphi,coefficients`; the coefficient keys are `u_rho,u_C,k_Cx,e_C,h_C`. Family `canonical_frequency,exterior_mass,original_frequency` are dimensionless $\Omega,M_a(1),\omega$; physical frequencies divide by `t_Q_s`. `charge` is dimensionless $\mathcal Q$, while `N_Q` is $\mathcal N_Q$. Define the five absolute normalized residuals as $|\hbar M/(t_Q\mathscr E_*)-1|$, $|\ell_Q\sqrt{k/(2a)}/(ct_Q)-1|$, $|\mathcal N_Q\mathcal Q-1|$, $|H_{\rm can}-H_{\rm orig}-\mathcal Q/(2a)|/\max(1,|H_{\rm can}|,|H_{\rm orig}|,|\mathcal Q/(2a)|)$, and $|H_{\rm can}-\Omega\mathcal Q-E_{\rm sc}+\omega_CN|/\max(1,|H_{\rm can}|,|\Omega\mathcal Q|,|E_{\rm sc}|,|\omega_CN|)$. `exact_core_root_denominator` is $2(k_{Cx}-2e_C)$. `unit_rescaling` has keys `comparison,rows`. The exact `dirac` keys are `convention,witnesses,adjoint_residual,golden_ratio_determinant,linear_interaction,squared_interaction,scalar_rotation_phase,dirac_rotation_phase`, with convention string `Weyl; gamma5=(-I2,+I2); psi=(L,R)`. Rotation phases are real scalars. `verdicts` has keys `normalization,core_assignment,density_identification,projection_action,spatial_parent`, in the order of the five scientific outcomes above. On failed input, use empty `source_summary,core_assignment,unit_rescaling,dirac` objects, empty `unit_family`, and `INCONCLUSIVE` for every verdict; do not fabricate partially valid rows. No timestamp or ephemeral field belongs in the compared payload. The verifier may add its own diagnostics only inside `independent_checks`.

Scientific verdicts are separate from numerical validity:

1. If any source, identity, finiteness or independent numerical check fails, `numerical_pass=false`, exit 1, and all scientific verdicts are `INCONCLUSIVE`.
2. If all three distinct admissible witnesses reproduce the imposed vacuum mass, speed and unit generator and retain distinct core lengths, report `SUPPORTS—conditional one-mass normalization nonuniqueness`; otherwise `INCONCLUSIVE—normalization identifiability`.
3. If $k_{Cx}-2e_C\le0$ and the allowed minimum core length exceeds the cell's upper endpoint, report `CONTRADICTS—selected scalar electron-core assignment`; otherwise `INCONCLUSIVE—selected scalar electron-core assignment`. This verdict concerns that additional assignment at these fixed coefficients.
4. If the registered witnesses exhibit complex and negative chiral-scalar values and the golden-ratio determinant is nonzero, report `CONTRADICTS—chiral-scalar nonnegative-density identification`; otherwise `INCONCLUSIVE—chiral-scalar density identification`.
5. If either displayed interaction has a nonzero imaginary part above $10^{-10}$, report `CONTRADICTS—displayed chiral projection interaction as a physical real action`; otherwise `INCONCLUSIVE—chiral projection action`.
6. The accepted scalar-parent spatial verdict remains its exact inherited `INCONCLUSIVE` string. No output may claim matter formation or an electron solution.

An empty-source control is run centrally after the canonical pair, against `runs/20260906_matter_formation_normalization/control_missing_sources/empty_sources/`, with outputs in its parent directory. Both actual CLIs must exit nonzero and preserve their own failed receipt without family/witness rows; the independent invocation points both input and output to the control directory. A failed-input control carries no scientific conclusion. No concurrent worker executes it.

## References

- `foundations/particle-stationary-action-closure.md` §§7–8—declared scales, scalar restriction, temporal parent, charge and exterior identities.
- `computations/matter-formation-continuum-report.md` §11—accepted spatial evidence and immutable receipt identities.
- `foundations/sector-coupling-derivation.md` §1—displayed chiral-scalar projection and dimensional boundary.
- `foundations/unified-lagrangian.md` §2 and §5.2—Dirac density assignment and interaction expressions.
- `particles/matter-organization.md` §3.4—mapped electron Compton cell and external mass provenance.
- `parameter-inventory.md` §§4, 9–10—external constants, parent groups and Fit-Status Ledger.
