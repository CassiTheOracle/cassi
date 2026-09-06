# Smooth Density-Trap Stability Preregistration

## Status: Preregistered—September 2026

## Abstract

The continuum-consistent radial campaign contains a qualified bound branch at $Q_C=16$, reproduced by independent collocation. This calculation tests its constrained spatial Hessian and derives the relationship between that Hessian and the positive terms omitted by the scalar reduction. The measured question is linear energetic stability in the scale-independent, topologically trivial model. Microscopic creation, nonlinear formation, and physical particle identity remain outside this test.

## 1. Frozen inputs

Keep every coefficient in `computations/matter-formation-continuum-prereg.md`. Read these completed NPZ fields without relaxation or alteration:

| Identifier | SHA-256 |
|---|---|
| `q16_R12_n192_w2` | `52540cf2cc11fcb313ecf689ffb5115c72480813cb7c866f348050bee33ad777` |
| `q16_R12_n384_refine` | `2e21fa2158d7fc7f9bff65bf337558af1bc0ca76520ea441611b37ab91e9d770` |
| `q16_R12_n768_refine` | `335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be` |
| `q16_R24_n768_refine` | `92c49919d8fb748dffb7a9e3d4ba497214beb883fb837195dcc8a321ec06096b` |

Each path is `runs/20260906_matter_formation_radial/<identifier>.npz`. Selection of the qualified $Q_C=16$ branch follows the completed static campaign; this stability protocol is frozen before its eigenvalues are evaluated. No repeat of the inconclusive $Q_C=64$ optimization is permitted.

## 2. Operators and coordinates

Use the same exact spherical cell volumes $V$ and stiffness $K$ as the finite-volume variational action, with zero outer perturbations and no origin flux. Canonical Euclidean coordinates are $z=(\sqrt V\,\delta f,\sqrt V\,\delta c)$. For angular degree $\ell$, set

$$
D_\ell=V^{-1/2}KV^{-1/2}+\operatorname{diag}\left(\ell(\ell+1)\frac{4\pi\Delta r}{V_i}\right),
$$

where $4\pi\Delta r$ is the exact cell integral of the angular coefficient. The amplitude Hessian of $E-\omega Q_C$ is

$$
H_\ell=\begin{pmatrix}
D_\ell+u_\rho(3f^2-1)+2h_Cc^2 & 4h_Cfc\\
4h_Cfc&D_\ell+2[e_C-h_C(1-f^2)-\omega]+6u_Cc^2
\end{pmatrix}.
$$

Diagonal field terms denote multiplication operators. At $\ell=0$ impose $\sum_i\sqrt{V_i}c_i z_{c,i}=0$ exactly by an orthonormal null-space basis. At $\ell\ge1$ the angular integral enforces the charge tangent condition. The carrier imaginary-component operator is

$$
H_{\rm phase}=D_0+2[e_C-h_C(1-f^2)-\omega]+2u_Cc^2.
$$

Recompute $\omega=(c^T\partial E/\partial c)/(2Q_C)$ independently from each artifact. The continuum polar identity $|D(fu)|^2=|\nabla f|^2+f^2|Du|^2$ for $u^\dagger u=1$ and the analogous carrier identity identify additional nonnegative orientation, phase, curvature and adjoint terms. An independent derivation must check this decomposition, topology and boundary conditions, and distinguish spatial energy positivity from nonlinear or empirical stability.

## 3. Measurements and decision tree

Compute the six lowest algebraic eigenpairs of the constrained $H_0$, unconstrained $H_1$, and $H_{\rm phase}$ for each field. The primary uses dense symmetric eigensolution and a Householder constraint basis; the independent implementation uses a separately constructed stiffness matrix and a null-space/QR constraint basis. No primary functions may be imported by the independent verifier.

Record eigenvalues, relative eigenpair residuals, phase overlap with $\sqrt Vc$, translation overlap with $\sqrt V(f',c')$ using second-order sampled derivatives, and source stationary residuals. Normalize the symmetry vectors. The tolerance for separating an eigenvalue from zero is $\eta=\max(5\times10^{-4},10r_f,10r_c)$ using the preregistered mass-weighted stationary residuals. The two symmetry overlaps must exceed $0.99$. Every eigenpair residual $\|Hv-\lambda v\|/\max(1,|\lambda|)$ must be below $10^{-8}$. Independent eigenvalues must differ by less than $10^{-7}\max(1,|\lambda|)$. No noisy eigenvalue is relabelled by sign alone.

Finite-grid energetic support requires $\lambda_{\min}(H_0|_{T_Q})>\eta$, $\lambda_{\min}(H_1)\ge-\eta$, $\lambda_{\min}(H_{\rm phase})\ge-\eta$, symmetry eigenvalues within $\eta$ of zero and both overlaps above $0.99$. A qualified negative eigenvalue below $-\eta$ returns CONTRADICTS. Unmet residual, symmetry or qualification requirements return INCONCLUSIVE.

Compare the positive constrained $H_0$ minimum on the two finest $R=12$ grids and on the same-spacing pair $R=12,n=384$ versus $R=24,n=768$. Agreement must be within $\max(0.01\max(|\lambda_a|,|\lambda_b|),\eta_a,\eta_b)$. Every frozen input must pass its spectral gates and the independent comparisons before the combined verdict SUPPORTS. The ordering $H_\ell-H_1=[\ell(\ell+1)-2]\operatorname{diag}(4\pi\Delta r/V_i)$ handles $\ell\ge2$ within this discretization; its nonnegativity does not enlarge the measured continuum scope.

## 4. Receipts and stopping

Scripts `computations/matter_formation_stability.py` and `computations/verify_matter_formation_stability.py` write primary and independent receipts to `runs/20260906_matter_formation_stability/`. Hash raw NPZ bytes and source/preregistration text after CRLF-to-LF normalization. Preserve first-execution outputs and use a distinct directory for numerical corrections. Execute every frozen input once. No field relaxation, coefficient changes, threshold adjustment or selective omission after the eigenvalues are known.

The verifier reports spectral agreement separately from the scientific verdict. A passing numerical comparison cannot establish creation from zero carrier number, nonlinear orbital stability, infinite-volume existence, scale-dependent stability, physical mass, fermionic spin/statistics, or observed matter formation.

## References

- `foundations/particle-stationary-action-closure.md` §8.7—empty-sector invariant and scalar reduction.
- `computations/matter-formation-continuum-prereg.md`—frozen coefficients and stationary qualification.
- `runs/20260906_matter_formation_radial/results.json`—source endpoint evidence.
- `runs/20260906_matter_formation_radial/verification.json`—independent finite-volume and continuum checks.
