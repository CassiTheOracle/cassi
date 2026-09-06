# Positive Spinor Observables and Canonical Conversion: Preregistration

## Status: Frozen conditional algebra and finite-dimensional witness protocol—September 2026

## Abstract

The existing Dirac helper supplies nonnegative component-quadratic observables. This calculation determines their chiral-current meaning and tests whether closed Dirac evolution, or Dirac evolution supplemented by the existing minimal conversion lift, supplies the canonical two-density law. The calculation includes positive-energy plane waves, phase-sensitive states, stationary reduced fibres and a positive-energy leakage diagnostic. Every mass, time and density normalization is a declared witness input. No microscopic production process, physical particle identity, reservoir, measured coupling or continuum stability result is inferred.

## 1. Source and execution boundary

The defining sources are `two-fluid/cassi_dirac_bridge.py` (`yang_yin_density`), `two-fluid/cassi_bridge_v2.py` (`_init_dirac`), `foundations/cassi-first-principles.md` §§1.3–2.1, and `foundations/geometric-manifold-completion.md` §4.4. The definitions tested below are transcribed explicitly, so mutable explanatory documents do not determine the numerical payload.

The primary program is `computations/matter_formation_spinor_closure.py`. The independent program is `computations/verify_matter_formation_spinor_closure.py`. Neither imports the other. Both bind their own source, the companion program, this preregistration and the two bridge source files by SHA-256 after CRLF-to-LF normalization. The verifier additionally binds the primary receipt's raw SHA-256 and reconstructs every scientific payload field.

The output directory is `runs/20260906_matter_formation_spinor_closure/`, with `results.json` and `verification.json`. Existing receipts are never overwritten. Computation uses CPU double precision, with no fitted parameters, random sampling or continuation through a failed result. The primary uses four-component matrix contractions and direct linear stationary solves. The independent program uses two-component contractions, component evolution identities and scalar stationary equations without importing primary functions.

The bridge runtime is a separate implementation smoke: execute `python two-fluid/cassi_dirac_bridge.py --test-init --grid 4` with CPU selected by `CUDA_VISIBLE_DEVICES=-1`. Its printed diagnostics establish execution of the edited descriptive surface; they do not certify physical fine-structure or matter formation. The matrix calculation tests the explicit map below and does not claim to execute the bridge's full grid propagator.

## 2. Representation and observable normalization

Set $\hbar=c=1$ in the finite-dimensional witnesses. The selected mass frequency is denoted $\mu$; no physical value is assigned. In the Dirac component convention,

$$
\alpha_i=\begin{pmatrix}0&\sigma_i\\\sigma_i&0\end{pmatrix},\qquad
\beta=\begin{pmatrix}1_2&0\\0&-1_2\end{pmatrix},\qquad
\gamma^5=\begin{pmatrix}0&1_2\\1_2&0\end{pmatrix}.
$$

For $\psi_D=(u,v)$, define

$$
L=(u-v)/\sqrt2,\qquad R=(u+v)/\sqrt2,\qquad
U=\frac1{\sqrt2}\begin{pmatrix}1_2&-1_2\\1_2&1_2\end{pmatrix}.
$$

The helper returns $Y_{\rm bridge}=2L^\dagger L$ and $I_{\rm bridge}=2R^\dagger R$. For this witness only, choose the bookkeeping normalization

$$
E_Y=Y_{\rm bridge}/2=L^\dagger L,\qquad
E_I=I_{\rm bridge}/2=R^\dagger R,\qquad
z=L^\dagger R.
$$

This factor of two defines the comparison convention. It supplies no conversion from spinor number density to a physical energy density. The corresponding projectors are $P_Y=(1-\gamma^5)/2$ and $P_I=(1+\gamma^5)/2$.

The primary records maximum absolute residuals for unitarity of $U$, projector idempotence/complementarity, $[\alpha_i,\gamma^5]=0$, $\{\beta,\gamma^5\}=0$, and the transformed Hamiltonian

$$
UH_D(\mathbf p)U^\dagger
=\begin{pmatrix}-\boldsymbol\sigma\cdot\mathbf p&\mu1_2\\\mu1_2&\boldsymbol\sigma\cdot\mathbf p\end{pmatrix},\qquad
H_D=\boldsymbol\alpha\cdot\mathbf p+\mu\beta.
$$

The operator check keys are `unitarity`, `projectors`, `kinetic_commutator`, `mass_anticommutator`, and `hamiltonian_transform`.

## 3. Closed evolution and phase-sensitive witnesses

For a classical complex Dirac amplitude with a common real scalar potential, the chiral continuity equations are

$$
\partial_t E_Y+\nabla\cdot\mathbf j_Y=2\mu\operatorname{Im}z,\qquad
\partial_t E_I+\nabla\cdot\mathbf j_I=-2\mu\operatorname{Im}z,
$$

$$
\mathbf j_Y=-L^\dagger\boldsymbol\sigma L,\qquad
\mathbf j_I=R^\dagger\boldsymbol\sigma R.
$$

The witnesses are plane waves with constant bilinears, so both current divergences vanish. The spinor amplitudes are $L=\sqrt p(1,0)$ and $R=e^{i\theta}\sqrt{1-p}(1,0)$. Use $\mu=1$, $p\in\{1/2,\varphi^{-1}\}$, $\theta\in\{-\pi/2,+\pi/2\}$, and momenta $(0,0,0)$ and $(0.3,-0.2,0.4)$: eight ordered rows, with momentum outermost, then $p$, then $\theta$.

For each row, compute the projective densities, $z$, both currents and the direct Dirac density derivative. Compare with the continuity source and with the selected canonical law

$$
\rho=E_Y+E_I,\quad \varepsilon=E_Y-\varphi E_I,\quad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},\quad
\kappa=\lambda(1-q),\quad \lambda=0.02,
$$

$$
(\dot E_Y,\dot E_I)_{\rm can}=(-\kappa\varepsilon,+\kappa\varepsilon).
$$

The $\pm\pi/2$ pair must have the same densities, $q$ and currents but opposite nonzero Dirac sources. At $p=\varphi^{-1}$ the canonical source is zero. These phase-sensitive spinors are general classical Dirac amplitudes; no positive-energy restriction is imposed on them. Section 4 supplies that restriction separately.

Each `phase_witnesses` row contains `momentum`, `p`, `theta`, `E_Y`, `E_I`, `coherence_re`, `coherence_im`, `q`, `dirac_rhs` (two scalars), `canonical_rhs` (two scalars), `j_Y`, `j_I`, `helper_density_residual`, and `continuity_residual`.

For a fixed Hermitian Hamiltonian and a fixed orthogonal density projector, $i[H,P_Y]$ has zero diagonal blocks in the projector decomposition. A derivative depending only on the two populations for every density matrix would require this operator to lie in the span of the two projectors, forcing it to vanish. This is a conditional closure obstruction for autonomous projected closed-unitary dynamics. It leaves environment reduction, restricted preparations and additional dynamical state as separate possibilities.

## 4. Positive-energy stationary witnesses and leakage

Use $\mu=1$, momenta $(0,0,p_z)$, and the ordered pairs $(p_z,h)=(0,+1),(0.5,-1),(0.5,+1),(1,-1),(1,+1)$. The spin vector $w_h$ obeys $\sigma_z w_h=h w_h$. Let $E=\sqrt{1+p_z^2}$ and prepare

$$
u=\sqrt{\frac{E+1}{2E}}w_h,\qquad
v=\frac{h p_z}{\sqrt{2E(E+1)}}w_h.
$$

These are normalized positive-energy eigenspinors. Their densities obey

$$
E_Y=\frac{1-hp_z/E}{2},\qquad E_I=\frac{1+hp_z/E}{2}.
$$

Their closed Dirac density derivative vanishes. Their canonical source is evaluated without changing the preparation, gate or rate. The zero-momentum state has $E_Y=E_I=1/2$ and a nonzero canonical source for the selected positive $\lambda$.

In the Weyl basis extend the existing conversion jumps to both spin orientations:

$$
J_{Y\to I}=\sqrt\kappa\begin{pmatrix}0&0\\1_2&0\end{pmatrix},\qquad
J_{I\to Y}=\sqrt{\varphi\kappa}\begin{pmatrix}0&1_2\\0&0\end{pmatrix},
$$

with $\kappa=\lambda(1-q)$ evaluated on the prepared state. Transform these to the Dirac basis when constructing the primary matrices. For $\varrho_+=|\psi_+\rangle\langle\psi_+|$ and $P_-=(1-H_D/E)/2$, measure

$$
\ell_-=\operatorname{tr}\!\left[P_-\sum_a\left(J_a\varrho_+J_a^\dagger-\tfrac12\{J_a^\dagger J_a,\varrho_+\}\right)\right].
$$

The independent construction uses $\ell_-=\sum_a\|P_-J_a\psi_+\|^2$. At rest the exact value is $\kappa(1+\varphi)/4$. Positive leakage means this specified channel does not preserve the chosen positive-energy one-particle subspace. It is not a QFT pair-production rate: the calculation contains no filled sea, Fock-space occupation, charge ledger or Pauli blocking.

Each `positive_energy_witnesses` row contains `p_z`, `helicity`, `energy`, `E_Y`, `E_I`, `q`, `kappa`, `eigenstate_residual`, `dirac_rhs`, `canonical_rhs`, `negative_energy_leakage`, and `leakage_residual` (against the independent transition-amplitude formula, or the rest formula at rest).

## 5. Massive Dirac field plus the minimal conversion lift

Restrict to a homogeneous spin sector at zero momentum and write the positive Hermitian bookkeeping fibre as

$$
\Gamma=\begin{pmatrix}E_Y&z^*\\z&E_I\end{pmatrix},\qquad
\operatorname{tr}\Gamma=\rho.
$$

The candidate equation combines $H=\mu\sigma_x$ with the same two directed conversion jumps:

$$
\dot\Gamma=-i[\mu\sigma_x,\Gamma]+\mathcal L_{\rm conv}[\Gamma].
$$

Its component equations are

$$
\dot E_Y=2\mu\operatorname{Im}z-\kappa\varepsilon,\quad
\dot E_I=-\dot E_Y,\quad
\dot z=-i\mu(E_Y-E_I)-\frac{1+\varphi}{2}\kappa z.
$$

Define $\delta=E_Y-E_I$, $s=1+\varphi$, and $\delta_*=(\varphi-1)\rho/s$. For frozen positive $\kappa$, the stationary solution is

$$
\delta_{\rm st}=\frac{\delta_*}{1+8\mu^2/(s^2\kappa^2)},\quad
z_{\rm st}=-\frac{2i\mu\delta_{\rm st}}{s\kappa},\quad
E_{Y,I}=\frac{\rho\pm\delta_{\rm st}}2.
$$

The primary obtains this state from a directly assembled linear system and trace constraint. The independent program evaluates the displayed scalar formula. Use $\rho=1$, $\kappa=0.02$ and $\mu\in\{0,0.01,0.1\}$, in that order: three `fixed_stationary` rows.

For the state-dependent gate, impose $\kappa=\lambda[1-q(E_Y,E_I)]$. Use $\rho\in\{1,4\}$ outermost, then the same three masses, with $\lambda=0.02$: six `gated_stationary` rows. The primary bisects the rate on $[\lambda(1-q_*),\lambda]$, solving the linear stationary problem at each rate; $q_*=\rho^2/(\rho^2+\varphi^{-2})$. The independent program bisects $\delta\in[0,\delta_*]$ in the scalar stationary equation. Use 90 bisection iterations with exact endpoint handling for $\mu=0$. No optimizer-selected branch is allowed.

For $\mu>0$, the scalar root is strictly between zero and $\delta_*$. On this interval the gate rate decreases with $\delta$, while the left-hand side of the stationary equation increases, giving a unique root. A nonzero Dirac mass therefore changes the population fixed point of this specified combined model. The massless control reproduces the canonical golden ratio. A channel and Hamiltonian with a state-dependent rate do not share the scalar-only fixed-generator time-reparametrization proof; this campaign checks the stated stationary states and makes no all-time nonlinear stability claim.

Each stationary row contains `rho`, `mu`, `kappa`, `E_Y`, `E_I`, `coherence_re`, `coherence_im`, `imbalance`, `target_imbalance`, `ratio`, `suppression` ($\delta/\delta_*$), `q`, `generator_residual`, `trace_residual`, `min_eigenvalue`, and `gate_residual`. For frozen-rate rows `gate_residual` is null; for gated rows it is $|\kappa-\lambda(1-q)|$.

## 6. Receipt, tolerance and decision rules

The primary schema is `cassi.matter-formation.spinor-closure.v1`; the independent schema is `cassi.matter-formation.spinor-closure.verification.v1`. Both receipts have `identities` keyed by `primary`, `verifier`, `prereg`, `bridge`, `bridge_base`; each identity has `path` (root-relative) and `sha256`. Scientific payload keys are `constants`, `operators`, `phase_witnesses`, `positive_energy_witnesses`, `fixed_stationary`, `gated_stationary`, and `verdicts`. The constants object contains exactly `phi`, `lambda`, `phase_mu`, `phase_p_values`, `phase_theta_values`, `phase_momenta`, `positive_energy_cases`, `stationary_mu_values`, `stationary_rho_values`, and `fixed_kappa`, with the values and order declared above. The verifier adds `input_sha256` and `independent_checks` containing `comparisons` and `mismatches`.

Both receipts contain `numerical_pass` and `failures`. Use JSON-native finite scalars and arrays; no NaN or infinity. A numerical identity residual must be at most $10^{-12}$. Independent scalar comparison uses $|x-y|\le10^{-10}\max(1,|x|,|y|)$; dictionaries and arrays require the exact declared keys and ordering. Positive-state eigenvalues must be at least $-10^{-12}$. Nonzero phase sources, the rest canonical-source magnitude and positive-energy leakage must exceed $10^{-6}$. Every massive stationary row must have $0<\delta<\delta_*$; massless rows must match $\delta_*$ and ratio $\varphi$ to the identity tolerance.

If all applicable identities, controls and inequalities pass, record these exact scoped verdicts:

- `observable_map`: `SUPPORTS—nonnegative chiral-current interpretation of the component map`;
- `closed_conversion`: `CONTRADICTS—closed Dirac realization of canonical two-density conversion`;
- `massive_fixed_point`: `CONTRADICTS—golden population fixed point for the specified massive Dirac and minimal conversion lift`;
- `positive_energy_channel`: `CONTRADICTS—positive-energy invariance of the specified chiral conversion channel`.

A failed relevant identity or inequality yields `INCONCLUSIVE` for its affected verdict, `numerical_pass: false`, a named failure and process exit 1. Successful numerical execution exits 0. Physical verdicts describe the specified definitions and state classes only; no exclusion of every interacting or coarse-grained fermionic completion is permitted.

## 7. Failed-input controls and stopping rule

Both programs accept `--output-dir`; the verifier also accepts `--input-dir`. Both accept `--bridge-source`, defaulting to `two-fluid/cassi_dirac_bridge.py`, solely for the recorded source identity. The primary and verifier must fail closed when a required identity or primary input is absent, malformed or inconsistent. Input failure leaves `constants`, `operators` and `verdicts` empty and all four row arrays empty, writes a failure receipt when the destination is new, and exits 1.

Run one primary missing-bridge control in `runs/20260906_matter_formation_spinor_closure/control_missing_bridge/` and one verifier missing-primary control in `runs/20260906_matter_formation_spinor_closure/control_missing_primary/`. Neither control may overwrite the canonical receipts or report scientific success.

Execute the canonical primary once, then the independent verifier once. Preserve every resulting receipt. Stop after these two calculations, the two failed-input controls and the bridge initialization smoke. A failed implementation requires an explicitly recorded defect and a new output directory; parameters, witnesses, acceptance thresholds and physical hypotheses remain fixed.

## References

- `foundations/sector-coupling-derivation.md` §1—chiral-scalar obstruction and alternative positive observables.
- `foundations/cassi-first-principles.md` §§1.3–2.1—canonical conversion and scalar gate.
- `foundations/geometric-manifold-completion.md` §4.4—minimal two-jump positive-fibre lift.
- `foundations/yin-yang-qi-dynamical-geometry.md` §§5–7—off-diagonal evolution and its scope.
- `foundations/matter-completion-boundary.md` §12—microscopic formation requirements.
- `computations/matter-formation-continuum-report.md`—integrated matter-formation evidence.
- `two-fluid/cassi_dirac_bridge.py`—component density diagnostics.
- `two-fluid/cassi_bridge_v2.py`—Dirac matrix convention.
