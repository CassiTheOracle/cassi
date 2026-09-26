# Fixed-Signed-Charge Stability of the Carrier Parent

## Status: Derived conditional constrained-energy identities / Hypothesized physical parent—September 2026

## Abstract

The neutral stationary dilation restriction leaves charged states as a distinct possibility. This calculation tests whether the already qualified scalar profiles are radial energetic minima when embedded in the positive-inertia parent at fixed signed Noether charge. It releases the original fixed-population constraint and retains the temporal energy required by the actual parent charge. The calculation introduces no relaxed field, physical coefficient selection or particle identification. Existing spatial and continuum qualifications remain unchanged.

## 1. Exact constrained energy

Use the dimensionless, scale-independent, topologically trivial scalar sector of `foundations/particle-stationary-action-closure.md` §§8.7–8.9. Divide energies by the positive action factor $\mathcal N_Q$. Its value is not selected. The static functional is explicitly

$$
E_{\rm sc}[f,c]=\int d^3x\left[
\frac12|\nabla f|^2+\frac{k_{Cx}}2|\nabla c|^2+
\frac{u_\rho}{4}(f^2-1)^2+
[e_C-h_C(1-f^2)]c^2+\frac{u_C}{2}c^4\right].
$$

Keep $u_\rho=4$, $u_C=k_{Cx}=1$, $e_C=0.75$ and the Mapped support coefficient $h_C=2.9598260763447164$. Let $N=Q_C=\int c^2>0$ and let $\mathcal Q$ denote the fixed signed parent charge. Minimizing carrier temporal energy at fixed fields and charge, with zero mediator velocity, gives

$$
\mathscr E_{\mathcal Q}[f,c]
=E_{\rm sc}[f,c]+G(N),\qquad
G(N)=\frac{(N-\mathcal Q)^2}{4aN}.
$$

This is the original Hamiltonian minimum over velocities. The canonical Hamiltonian differs by the constant $\mathcal Q/(2a)$ on this constraint surface. The minimizer has $\dot\chi=i(N-\mathcal Q)\chi/(2aN)$.

For a stationary profile of $E_{\rm sc}-\omega_C N$, define

$$
D=1+4a\omega_C,\quad r=\sqrt D,\quad
\omega=\frac{2\omega_C}{1+r},\quad \mathcal Q=rN.
$$

Every embedding requires $D>0$. The calculation uses the positive signed-charge branch. Its charge-constrained amplitude Hessian in Euclidean mass-weighted coordinates is

$$
H_{\mathcal Q}=H_0+\gamma gg^T,
\qquad
\gamma=\frac{\mathcal Q^2}{2aN^3}=\frac{D}{2aN},
\qquad
g=\begin{pmatrix}0\\2\sqrt Vc\end{pmatrix},
$$

where $H_0$ is the full, unprojected Hessian of $E_{\rm sc}-\omega_C N$. The population direction is included. No fixed-$N$ tangent projection is applied to $H_{\mathcal Q}$.

If $H_0$ is invertible, the stationary linear response satisfies $H_0x=g$. Write $S=g^Tx$. Along an exact differentiable stationary branch, $S=dN/d\omega_C$. If $H_0$ has exactly one negative eigenvalue and no zero eigenvalue, the positive rank-one update is positive definite precisely when

$$
1+\gamma S<0,
\qquad\text{equivalently}\qquad
\frac{d\mathcal Q}{d\omega}=2aN+DS<0.
$$

The negative-index and invertibility conditions must be checked; the slope statement is not used as an unconditional rule. Finite-grid response is not automatically the derivative of a continuum branch.

Spatial dilation at fixed signed charge changes $N$ and the required temporal velocity. With $T$ and $U$ the static gradient and potential integrals,

$$
\mathscr E_{\mathcal Q}(\lambda)
=\lambda T+\lambda^3\left(U+\frac N{4a}\right)
-\frac{\mathcal Q}{2a}+\frac{\mathcal Q^2}{4aN}\lambda^{-3}.
$$

At a continuum stationary profile, its curvature is $-2T+9\mathcal Q^2/(2aN)$. When the canonical potential is nonnegative and $\mathcal Q\ne0$, the displayed one-parameter energy has strictly positive second derivative for every $\lambda>0$. This removes the neutral dilation obstruction along that family; it supplies no general stability theorem. The finite-volume scaling calculation below varies the domain radius with the profiles and does not assume finite-box stationarity under this dilation.

## 2. Frozen field inputs and parent schedule

Read these eight completed arrays from `runs/20260906_matter_formation_radial/`, without relaxation, interpolation or alteration. The population-64 continuation remains excluded as unqualified. Each identifier has suffix `.npz`.

| Identifier | Raw SHA-256 |
|---|---|
| `q16_R12_n192_w2` | `52540cf2cc11fcb313ecf689ffb5115c72480813cb7c866f348050bee33ad777` |
| `q16_R12_n384_refine` | `2e21fa2158d7fc7f9bff65bf337558af1bc0ca76520ea441611b37ab91e9d770` |
| `q16_R12_n768_refine` | `335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be` |
| `q16_R24_n768_refine` | `92c49919d8fb748dffb7a9e3d4ba497214beb883fb837195dcc8a321ec06096b` |
| `q256_R12_n192_w2` | `ce3d7efcf133fd2fd5776203a86d53469f4b91b4919ca1bbdcce054dc02233ba` |
| `q256_R12_n384_refine` | `e450c22a6baf8312fa67ca58745ad593879bf6d18615a83ad0cbe8dacabb11d5` |
| `q256_R12_n768_refine` | `95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a` |
| `q256_R24_n768_refine` | `7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66` |

For every field use $a=1/64,1/32,1/16$, in that order: 24 parent witnesses. These are mathematical witnesses from the completed correspondence family. No temporal coefficient is fitted or selected physically.

Use exact spherical cell volumes, radial stiffness and half-cell outer Dirichlet conductance from the static action. The perturbations vanish at the outer radius and have no origin flux. Reconstruct the nonzero outer load in the mediator first variation; omitting it changes stationarity. Recompute $N$, $\omega_C$, energy and the mass-weighted source residuals directly. The source qualification is relative population error $<10^{-10}$ and normalized residuals $r_f,r_c<10^{-4}$. Define $\eta=\max(5\times10^{-4},10r_f,10r_c)$.

In blocked coordinates $(\sqrt V\delta f,\sqrt V\delta c)$, let $D_0=V^{-1/2}KV^{-1/2}$. The exact discrete amplitude Hessian is

$$
H_0=\begin{pmatrix}
D_0+u_\rho(3f^2-1)+2h_Cc^2&4h_Cfc\\
4h_Cfc&k_{Cx}D_0+2[e_C-h_C(1-f^2)-\omega_C]+6u_Cc^2
\end{pmatrix}.
$$

Field-dependent entries denote diagonal multiplication. Only the radial amplitude operator is measured in this campaign. Angular and phase sectors are unchanged by the rank-one charge term, but their complete qualification is not supplied by this radial calculation. In particular, the existing `INCONCLUSIVE—constrained smooth-branch spatial stability` verdict is retained.

## 3. Independent spectral calculations

The primary program, `computations/matter_formation_charged_stability.py`, uses independently assembled dense matrices and SciPy `eigh(driver="evr", subset_by_index=(0,5))`. It stores all six eigenpairs of $H_0$ and each $H_{\mathcal Q}$, the linear response $x$, and their residuals. It stores the spectral arrays in one `spectra_<identifier>.npz` per field, with each raw artifact hash recorded in `results.json`. It evaluates the charge-slope criterion only when the measured base spectrum qualifies exactly one negative direction and no zero direction. Six base eigenvalues are sufficient for that count only when the sixth exceeds $\eta$.

The verifier, `computations/verify_matter_formation_charged_stability.py`, imports no primary computational logic. It assembles the radial operator in interleaved $(\delta f_i,\delta c_i)$ order as a symmetric banded matrix of half-bandwidth two. It uses SciPy `eig_banded` for the complete base spectrum and `solve_banded((2,2), ...)` for the independent stationary response.

For a shifted base matrix $A=H_0-\lambda I$ with no zero eigenvalue, the rank-one inertia identity is

$$
n_-(H_{\mathcal Q}-\lambda I)
=n_-(A)-\mathbf1\{1+\gamma g^TA^{-1}g<0\}.
$$

The verifier uses this identity to bracket each reported parent eigenvalue. At $\lambda_j\pm\delta_j$, with $\delta_j=10^{-7}\max(1,|\lambda_j|)$ and $j=0,\ldots,5$, the negative counts must satisfy

$$
n_-(H_{\mathcal Q}-(\lambda_j-\delta_j)I)\le j
<n_-(H_{\mathcal Q}-(\lambda_j+\delta_j)I).
$$

This permits genuine degeneracy and rejects a missed lower eigenvalue. The shifted banded solves must have relative residual $<10^{-8}$. A singular or unresolved solve is a numerical qualification failure; it is not replaced by a different shift or method after execution. All bracket counts, scalar inertia factors and solve residuals are retained. The verifier also reconstructs every stored eigenpair residual and orthonormality directly from its own operator.

For each parent row, evaluate the finite-volume dilation energy at $\lambda=1/2,3/4,1,5/4,3/2$. Primary evaluation rescales $K\mapsto\lambda K$, $V\mapsto\lambda^3V$ and the outer conductance by $\lambda$, recomputes $N$ and minimizes temporal energy at the same $\mathcal Q$. The verifier independently evaluates the closed scaling law. This is an exact discrete scaling identity with a changing domain, not a continuum stationarity claim.

## 4. Frozen criteria and stopping

Every source, coefficient, identifier, array shape and schedule entry must match exactly, and every reported float must be finite. Require eigenpair relative residuals and orthonormality errors below $10^{-8}$, independent base-eigenvalue differences below $10^{-7}\max(1,|\lambda|)$, and relative response-solve residuals below $10^{-8}$. Independent scalar quantities and dilation energies must agree within $10^{-8}\max(1,|\mathrm{primary}|,|\mathrm{independent}|)$. Every parent eigenvalue must pass the independent inertia bracket. No failed identity, source-qualification or independent numerical check can coexist with a numerical `PASS`. Domain/resolution disagreements are reported separately as scientific qualification failures.

A qualified radial minimum $\lambda_{\min}(H_{\mathcal Q})>\eta$ returns `SUPPORTS—finite-grid radial fixed-charge energetic stability`. A qualified minimum below $-\eta$ returns `CONTRADICTS—finite-grid radial fixed-charge energetic stability`. Qualification requires a qualified source, resolved base inertia (sixth eigenvalue above $\eta$ and no base eigenvalue within $[-\eta,\eta]$), and successful numerical requirements for the base response and parent spectrum. Unqualified sources, unresolved zeros or failed numerical requirements return `INCONCLUSIVE—finite-grid radial fixed-charge energetic stability`. An aggregate SUPPORTS requires every frozen row to support; a qualified contradiction takes precedence over unresolved rows.

Report the two finest same-domain and same-spacing larger-domain minimum comparisons for each population and parent coefficient. Their frozen agreement tolerance is $\max(0.01\max(|\lambda_a|,|\lambda_b|),\eta_a,\eta_b)$, matching the existing spatial protocol. Passing these comparisons qualifies only the measured radial discretization. Failed comparisons return `INCONCLUSIVE—radial domain/resolution qualification` independently of positive finite-grid curvature. The calculation supplies no all-sector, real-time, nonlinear, infinite-volume or physical-particle stability verdict.

Execute the complete schedule once. Preserve unsuccessful evidence. No field relaxation, coefficient change, tolerance adjustment, omitted row, adaptive shift or preferred mass/size inference is permitted after execution. An implementation repair requires an explicit execution record and a new output directory. Neither source nor this preregistration may be changed within an accepted identity chain.

Default output directory: `runs/20260906_matter_formation_charged_stability/`. Primary output: `results.json` and eight spectral NPZs. Independent output: `verification.json`. Both sources and this preregistration are pinned by canonical CRLF-to-LF SHA-256; the verifier also records the raw primary receipt and spectral hashes. Both programs refuse existing own receipts or primary spectral artifacts. An existing output cannot be overwritten during a reproduction.

## References

- `foundations/particle-stationary-action-closure.md` §§8.7–8.9—static scalar action, temporal parent and neutral dilation boundary.
- `computations/matter-formation-stability-prereg.md`—mass-weighted operators, source qualification and spatial comparison criteria.
- `computations/matter_formation_stability_execution.json`—accepted prior spatial evidence chain; it remains unchanged.
- `computations/matter-formation-hyperbolic-parent-prereg.md`—signed-charge embeddings and frozen parent coefficient witnesses.
- `computations/matter-formation-parent-vacuum-prereg.md`—classical parent potential and charge-energy identities.
- `computations/matter-formation-continuum-report.md`—current prepared-binding and stability evidence boundaries.
