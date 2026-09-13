# Smooth Vacuum-to-Bound-State Formation in a Radial Yukawa Bag

## Status: Frozen conditional continuum-oriented protocol—September 2026

## Abstract

The sudden and square-pulse scalar histories in the registered scalar–fermion
continuum witness produce ultraviolet-divergent pair number and excitation
energy. This protocol tests a different, explicitly admissible time history:
a prescribed spatial Yukawa bag is switched on by a compact $C^\infty$
transition, and a finite-box negative-energy Dirac covariance is evolved from
the homogeneous vacuum. The final static bag has a positive-energy localized
bound mode. The calculation asks whether the smooth transition produces a
nonzero occupation of that bound mode with convergent finite-box observables.

This is a scoped vacuum-to-bound-state result for a prescribed background. The
background is not evolved by reciprocal scalar backreaction, so the protocol
does not claim a closed Cassi matter mechanism, a renormalized interacting QFT,
all angular sectors, a physical normalization, or an observed particle map.
It is intended to separate the ultraviolet failure of a sudden source from the
independent question of localized quantum-state formation.

## 1. Action, channel and fixed background

Use the dimensionless Yukawa action

$$
\mathcal L=\frac12\partial_\mu\sigma\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi,
$$

with the unchanged inputs

$$
(v,\lambda,g,R,A,w,T_s)=(1,\tfrac14,6,16,1.5,2.5,2).
$$

Only the spherical $\kappa=-1$ radial channel is retained. The prescribed
background is

$$
\sigma(t,r)=v-A\,b(t/T_s)\exp[-r^2/(2w^2)],
$$

where

$$
 b(s)=\begin{cases}
0,&s\le0,\\
\displaystyle\frac{e^{-1/s}}{e^{-1/s}+e^{-1/(1-s)}},&0<s<1,\\
1,&s\ge1.
\end{cases}
$$

The function $b$ is $C^\infty$, exactly constant before and after the
transition, and has no fitted or scanned parameters. The final static profile
has a lowest positive radial eigenvalue below the vacuum mass threshold
$gv=6$; that mode is the registered target bound state.

The background is prescribed rather than dynamically solved. Its work is not
mistaken for a conserved closed-system energy balance.

## 2. Regulator and quantum state

For each grid, use cell centres $r_i=(i+1/2)\Delta r$ and the same Hermitian
finite-box radial Hamiltonian as the registered bag calculation,

$$
H(t)=\begin{pmatrix}
g\sigma(t,r)&-D-1/r\\
D-1/r&-g\sigma(t,r)
\end{pmatrix},
$$

with the centred skew-adjoint endpoint stencil. Let $U_0$ contain all
negative-energy eigenvectors of $H(0)=H(v)$, scaled to the radial $dr$ metric.
Evolve every occupied negative-energy mode by

$$
\dot U=-iH(t)U,\qquad U(0)=U_0.
$$

The primary uses fixed-step RK4 and stores $U$ at the checkpoints
$t\in\{0,2,4,8,12\}$. The independent verifier uses a separately assembled
Hamiltonian and DOP853 integration of the matrix equation at the same
checkpoints. The verifier never imports the primary program.

Use the fixed grid sequence

| grid | $N$ | $\Delta r$ | $\Delta t$ | final time |
|---|---:|---:|---:|---:|
| G0 | 48 | $1/3$ | $0.002$ | $12$ |
| G1 | 72 | $2/9$ | $0.001$ | $12$ |
| G2 | 96 | $1/6$ | $0.0005$ | $12$ |

No cutoff fitting, coupling scan, amplitude scan, transition-time scan,
source damping, state reset, or post-processing occupation is permitted.

## 3. Observables and frozen qualification

Let $P_+$ and $P_-$ be the positive- and negative-energy projectors of the
final static Hamiltonian $H(T_s)$. Let $b_+$ and $b_-$ be the normalized
positive and negative eigenvectors with the smallest positive and largest
negative absolute eigenvalues, respectively. Define

$$
N_{\rm pair}=\operatorname{Tr}(P_+UU^\dagger),\qquad
n_b=\sum_a|\langle b_+,U_a\rangle_{dr}|^2,
$$

and

$$
h_b=N-\sum_a|\langle b_-,U_a\rangle_{dr}|^2.
$$

The bound-mode core probability and RMS radius are computed from $b_+$ in
$r<4$ and the full radial grid. The final background's lowest positive
energy, its core probability and its RMS radius are also recorded.

A candidate grid passes when

1. $N_{\rm pair}>0.05$, $n_b>0.10$, and $|n_b-h_b|<0.02$;
2. the bound mode has core probability $>0.50$ and RMS radius $<5$;
3. the primary and independent final summaries agree within $2\times10^{-3}$
   absolute for $N_{\rm pair}$ and $n_b$, and within $10^{-2}$ for the spatial
   observables;
4. adjacent-grid differences of $N_{\rm pair}$ and $n_b$ are below $0.15$,
   and adjacent-grid differences of core probability and RMS radius are below
   $0.10$ and $0.25$;
5. the final-state mode metric error and the verifier's DOP853 integration
   success checks pass; and
6. the static control $A=0$ gives $N_{\rm pair}<10^{-10}$ and $n_b<10^{-10}$
   on G1.

The scientific verdict is

- `CAPTURED—conditional smooth vacuum-to-bound-state formation` if every
  grid and every control/independent check passes;
- `DOES NOT EMERGE—conditional smooth vacuum-to-bound-state formation` if
  the numerical contract passes but a formation predicate fails; or
- `INCONCLUSIVE` for provenance, integration, finiteness or reconstruction
  failure.

The result is deliberately scoped: a passing result shows that a smooth
background can create a localized fermionic bound-state occupation from the
regulated vacuum without the sudden-source ultraviolet divergence. It does
not show that the Cassi action selects this Yukawa model, that the scalar
background is dynamically generated, that the result survives continuum
renormalization and all angular sectors, or that the bound state is a physical
particle.

## 4. Immutable evidence

The primary is `computations/matter_formation_smooth_bag_transition.py`; the
independent program is
`computations/verify_matter_formation_smooth_bag_transition.py`. Both programs
write exclusive receipts and source identities. The primary receipt is
`results.json`; the verifier receipt is `verification.json`. Each receipt
contains the fixed protocol identity, grid summaries, control summary,
qualification checks, verdict and failure list. Existing output files are
never overwritten.
