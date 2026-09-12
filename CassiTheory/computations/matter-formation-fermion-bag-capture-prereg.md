# Three-Dimensional Radial Fermion-Bag Capture

## Status: Hypothesized conditional mechanism protocol—September 2026

## Abstract

This protocol tests whether a degree-zero, positive-energy fermion wave packet can deform an added three-dimensional scalar vacuum into a localized self-consistent bag and remain trapped in that configuration. The calculation uses a spherically symmetric partial-wave reduction of one supplied Dirac state coupled to a real scalar field. It is a three-dimensional radial continuum route, with three finite-volume resolutions and an independent full-state reconstruction. The action, state rule, boundary data, Cassi-variable map, observables, controls, and stopping rule are fixed here before execution.

A positive result qualifies localized capture in the declared radial $s$-wave model. It does not select this added action from the canonical two-fluid PDE, establish all angular sectors, create the fermion from the quantum vacuum, or identify a physical particle.

## 1. Question and scope

The question is whether a supplied degree-zero fermion packet can form a persistent localized field configuration through the reciprocal scalar source in one explicit $3+1$-dimensional continuum model. The calculation targets the missing real-time formation step between a dispersed carrier and a localized stationary state.

The added action is

$$
\mathcal L_{\mathrm{bag}}
=\frac12\partial_\mu\sigma\,\partial^\mu\sigma-U(\sigma)
+\bar\psi\left(i\gamma^\mu\partial_\mu-g\sigma\right)\psi,
$$

with

$$
U(\sigma)=\frac{\lambda}{4}(\sigma^2-v^2)^2,
\qquad
(v,\lambda,g)=(1,\tfrac14,6).
$$

The scalar vacuum is $\sigma=v$. The Dirac field is represented by one occupied positive-energy radial state in the $\kappa=-1$ channel. The state is a supplied incoming preparation, not a vacuum fluctuation. The scalar and fermion exchange energy through the Yukawa term; no damping, absorber, external trap, source term, clamping, or post-processing energy removal is used.

The extension is explicitly supplied. $\sigma$ is compared with the real mediator variable $f$ in the Cassi scalar parent, and $\psi$ is an added microscopic carrier. The coefficients $a,c_\Psi,u_\rho,u_C,h_C$ of the registered complex-carrier action are not silently identified with $(v,\lambda,g)$; no numerical value is mapped into the canonical parameter inventory. The action is a mechanism witness at the declared dimensionless reference scale.

## 2. Radial equations and three-dimensional measure

Use $r\in[0,R]$, $R=16$, cell centers $r_i=(i+\tfrac12)\,\Delta r$, and spherical cell volumes

$$
V_i=\frac{4\pi}{3}\left[(r_i+\tfrac12\Delta r)^3-(r_i-\tfrac12\Delta r)^3\right].
$$

The scalar equation is

$$
\dot\sigma=\pi,
\qquad
\dot\pi=\frac1{r^2}\partial_r(r^2\partial_r\sigma)-\lambda(\sigma^2-v^2)\sigma
-g\,s(r),
$$

where the finite-volume radial Laplacian uses zero flux at $r=0$ and the fixed vacuum value $\sigma(R)=v$. The source is the normalized radial Dirac scalar density

$$
 s(r_i)=\frac{|G_i|^2-|F_i|^2}{4\pi r_i^2}.
$$

The radial spinor $\Psi=(G,F)^T$ has inner product $\int_0^R(|G|^2+|F|^2)\,dr=1$. For $\kappa=-1$, use the Hermitian radial Hamiltonian

$$
H_\kappa(\sigma)=
\begin{pmatrix}
 g\sigma & -D+\kappa/r\\
 D+\kappa/r & -g\sigma
\end{pmatrix},
$$

where $D^\dagger=-D$ is the centered nearest-neighbour difference with the finite-box endpoint rows
$(Du)_0=u_1/(2\Delta r)$, $(Du)_i=(u_{i+1}-u_{i-1})/(2\Delta r)$ for
$0<i<N-1$, and $(Du)_{N-1}=-u_{N-2}/(2\Delta r)$. This skew-adjoint
endpoint stencil is the declared radial spinor boundary operator.

$$
\dot\Psi=-iH_\kappa(\sigma)\Psi.
$$

The discrete scalar gradient and total energy use the same spherical face areas and cell volumes as the equation. The fermion energy is $E_\psi=\langle\Psi,H_\kappa(\sigma)\Psi\rangle$.

## 3. Initial state, boundary, and schedule

At $t=0$, set

$$
\sigma_i=v,
\qquad \pi_i=0.
$$

On each grid, form a real radial trial $G_i\propto r_i\exp[-(r_i-r_0)^2/(2w^2)]$, $F_i=0$ with $(r_0,w)=(1.2,0.6)$. Project this trial onto the positive spectral subspace of $H_{-1}(v)$ and normalize in the radial inner product. This fixes the one-fermion state without fitting an evolution outcome. The preparation has degree zero in the scalar field and no topological winding.

Use the skew-adjoint endpoint stencil above for the spinor and the scalar outer
condition $\sigma(R)=v$ with zero outer scalar velocity. The fixed schedule is

| Grid | $N$ | $\Delta r$ | $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| `G0` | 160 | $0.1$ | $0.02$ | $24$ |
| `G1` | 240 | $1/15$ | $0.01$ | $24$ |
| `G2` | 320 | $0.05$ | $0.005$ | $24$ |

Archive every $0.1$ time unit and fields at the initial and final times. The primary uses fixed-step classical RK4. The independent implementation uses an independently assembled right-hand side with adaptive DOP853 and the same declared tolerances, then samples at the primary times.

The controls are `g_zero` on `G1`, with $g=0$ and the same packet, and `packet_zero` on `G1`, with the scalar vacuum and $\Psi=0$. The controls are not candidates for capture.

## 4. Formation and persistence observables

Define the vacuum mass $m_\infty=gv=6$, fermion probability density $p_i=|G_i|^2+|F_i|^2$, core probability $P_4=\sum_{r_i<4}p_i\Delta r$, and radial RMS radius

$$
R_\psi^2=\sum_i r_i^2p_i\Delta r.
$$

Define the scalar core deficit $d_0=1-\sigma_0$, the scalar and fermion energies from the declared discrete Hamiltonian, and the relative total-energy drift from the initial value. The late window is $16\le t\le24$.

A candidate row qualifies as `CAPTURED` only if all three candidate grids satisfy

$$
\overline{P_4}\ge0.50,
\qquad
\overline{E_\psi}\le0.95m_\infty,
\qquad
\overline{R_\psi}\le5,
$$

with late-window standard deviations $\operatorname{sd}(P_4)\le0.10$ and $\operatorname{sd}(R_\psi)\le0.75$, mean scalar core deficit $\overline d_0\ge0.05$, total-energy relative drift at most $2\times10^{-3}$, and outer scalar-energy fraction below $0.10$. The resolution differences in the late means of $(P_4,R_\psi,E_\psi,d_0)$ must be at most $0.10$ in absolute value for adjacent grids.

The `g_zero` control must have $\max_t|\sigma-v|<10^{-10}$ and must fail the candidate capture predicate. The `packet_zero` control must have $\max_t|\sigma-v|<10^{-10}$ and zero fermion norm to the same numerical tolerance. A candidate failure returns `DOES NOT EMERGE` within this supplied radial model; a numerical or provenance failure returns `INCONCLUSIVE`.

## 5. Verification and stopping rule

The primary and independent verifier must agree on source identities, grid schedules, initial projections, raw sampled arrays, conservation diagnostics, late observables, and the verdict. The verifier must reconstruct the trajectory with its own DOP853 right-hand side and must not import the primary solver or trust stored summaries.
For independent comparison, every sampled time and array shape must match.
The maximum absolute difference between primary and DOP853 `sigma`, `pi`,
`psi_re`, and `psi_im` arrays must be at most $2\times10^{-4}$, and every
late-window scalar observable must agree to $5\times10^{-4}$ absolute. These
are fixed numerical reconstruction tolerances, not scientific thresholds.

The primary writes exclusive-create `result.json` plus one archive per arm. Archives contain only finite float64 arrays with explicit shapes: `time`, `sigma`, `pi`, `psi_re`, and `psi_im`. The verifier writes exclusive-create `verification.json` and independent state archives. Missing inputs, altered source bytes, omitted arms, nonfinite arrays, and copied scientific summaries are rejection controls.

No parameter, grid, packet, threshold, final time, or verdict rule may be changed after the first scientific run. An implementation defect permits a repair under a new output directory while preserving the failed attempt and protocol. A numerical or scientific failure defines the next boundary; it does not authorize tuning this protocol.

The result is a mechanism witness, not a complete Cassi matter identification. It addresses localized real-time formation from a supplied degree-zero carrier. Quantum-vacuum creation, all angular sectors, renormalized sea contributions, physical calibration, particle identity, and the canonical Cassi action remain separate requirements.

## References

- `foundations/matter-completion-boundary.md`—physical requirements and current formation boundary.
- `computations/matter-formation-continuum-report.md` §§29, 35–36—microscopic non-identifiability, charged condensation, and continuum minimizer-set stability.
- `computations/matter-formation-fermion-production-prereg.md`—finite-mode fermion vacuum production and energy-accounting conventions.
- Farhi, Graham, Jaffe and Weigel, [*Searching for Quantum Solitons in a 3+1 Dimensional Chiral Yukawa Model*](https://arxiv.org/abs/hep-th/0112217)—localized fermion energy and renormalized sea boundary.
- Friedberg and Lee, [*QCD and the soliton model of hadrons*](https://doi.org/10.1103/PhysRevD.15.1694)—scalar bag mechanism with localized fermion states.
