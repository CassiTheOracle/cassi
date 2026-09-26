# Qi-Flow Entanglement Verification Preregistration

## Status: Hypothesized—August 2026

## Abstract

This document freezes deterministic checks for the relation between
entanglement and Qi flow in the regulated CassiFI quantum sector. The proposed
relation has three parts. On a connected nonnodal product domain, a pure state
is separable exactly when its global configuration-space density-current
object factorizes across the declared subsystem split; Schmidt rank or
reduced-state purity supplies the global criterion across disconnected
support. CassiFI interaction terms can generate
entanglement by coupling subsystem coordinates. The classical signed link
current identifies an active exchange quadrature, while reduced-state purity
or entropy measures entanglement. This protocol is an internal mathematical
audit; identifying the CassiFI configuration with nature's microscopic
quantum configuration remains Hypothesized.

## 1. Frozen implementation

The companion script is `computations/verify_qi_flow_entanglement.py`. It uses Python's standard library and NumPy only. Every grid, matrix, state, coupling, threshold, and decision rule is fixed here for the recorded evidentiary execution.

The shared double-precision tolerance is

$$
\epsilon_{\rm num}=10^{-12}.
$$

The protocol is one deterministic evaluation with fixed inputs and without a
random seed, fit, optimizer, parameter search, or rerun rule.

## 2. Gate GQE1: density-current factorization

Use the fixed grid

$$
x=y=(-1.5,-1.0,-0.5,0,0.5,1.0,1.5)
$$

and normalize every coefficient matrix in the Euclidean discrete measure.

Construct three pure states:

$$
\Psi_{\rm product}(x,y)
\propto e^{-x^2/2}e^{-3y^2/4},
$$

$$
\Psi_{\rm phase}(x,y)
\propto e^{-x^2/2}e^{-3y^2/4}e^{i\chi xy},
\qquad \chi=0.4,
$$

and

$$
\Psi_{\rm amplitude}(x,y)
\propto
\exp\left[-\frac12\left(x^2+y^2+2\kappa xy\right)\right],
\qquad \kappa=0.35.
$$

For a normalized coefficient matrix $C$, its singular values are the discrete Schmidt coefficients. Define the density-factorization residual

$$
r_\rho=\max_{ij}|p_{ij}-p_i^{(A)}p_j^{(B)}|,
\qquad p_{ij}=|C_{ij}|^2,
$$

and the discrete mutual information

$$
I(A:B)=\sum_{ij:p_{ij}>0}p_{ij}
\ln\frac{p_{ij}}{p_i^{(A)}p_j^{(B)}}.
$$

The phase-coupled state has the analytic conditional velocities

$$
v_x=\chi y,
\qquad
v_y=\chi x,
\qquad
\partial_yv_x=\partial_xv_y=\chi.
$$

The real amplitude-coupled state has zero phase current and

$$
\partial_x\partial_y\ln|\Psi_{\rm amplitude}|^2=-2\kappa.
$$

Gate GQE1 passes iff:

1. the product state's second Schmidt coefficient and $r_\rho$ are at most $\epsilon_{\rm num}$;
2. the phase-coupled state's $r_\rho$ is at most $\epsilon_{\rm num}$, its second Schmidt coefficient exceeds $10^{-3}$, and both conditional-flow derivatives equal $\chi$ within $\epsilon_{\rm num}$;
3. the amplitude-coupled state's second Schmidt coefficient and $I(A:B)$ exceed $10^{-3}$, its current is exactly zero, and its mixed log-density derivative equals $-2\kappa$ within $\epsilon_{\rm num}$.

This gate separates two kinds of nonfactorizable Qi organization: cross-dependent phase flow and stationary amplitude correlation.

## 3. Gate GQE2: reciprocal-link ground-state entanglement

Use unit mass, $\hbar=1$, base frequency $\omega=1$, identity cell metrics,
and the scalar reciprocal-link Hamiltonian with
$g_{\mathrm{link}}:=w_Zg_{Z,s}$:

$$
H=\frac12(p_A^2+p_B^2)
+\frac12\omega^2(q_A^2+q_B^2)
+\frac{g_{\mathrm{link}}}{2}(q_B-q_A)^2.
$$

For $g_{\mathrm{link}}\ge0$, the normal frequencies are

$$
\omega_+=\omega,
\qquad
\omega_-=\sqrt{\omega^2+2g_{\mathrm{link}}}.
$$

The reduced one-mode symplectic eigenvalue, purity, and entropy are

$$
\nu_A
:=\frac14\sqrt{(\omega_++\omega_-)
\left(\omega_+^{-1}+\omega_-^{-1}\right)}.
$$

$$
\mu_A=\frac{1}{2\nu_A},
$$

$$
S_A=
\left(\nu_A+\frac12\right)
\ln\left(\nu_A+\frac12\right)
-
\left(\nu_A-\frac12\right)
\ln\left(\nu_A-\frac12\right),
$$

with the continuous limit $0\ln0=0$.

Independently construct the oscillator stiffness and ground-state covariance
matrices

$$
\mathbf K_{\mathrm{osc}}
=
\begin{pmatrix}
\omega^2+g_{\mathrm{link}}&-g_{\mathrm{link}}\\
-g_{\mathrm{link}}&\omega^2+g_{\mathrm{link}}
\end{pmatrix},
\qquad
V_q=\frac12\mathbf K_{\mathrm{osc}}^{-1/2},
\qquad
V_p=\frac12\mathbf K_{\mathrm{osc}}^{1/2},
$$

and compute

$$
\nu_A^{(\mathrm{cov})}
:=\sqrt{(V_q)_{AA}(V_p)_{AA}}.
$$

Evaluate the link-off control $g_{\mathrm{link}}=0$ and the frozen link-on value $g_{\mathrm{link}}=1.5$. Gate GQE2 passes iff $\nu_A^{(\mathrm{cov})}$ agrees with the normal-mode formula within $\epsilon_{\rm num}$ for both cases; the control has $\nu_A=1/2$, $\mu_A=1$, and $S_A=0$ within $\epsilon_{\rm num}$; and the link-on state has $\nu_A>1/2$, $\mu_A<0.99$, and $S_A>0.05$.

## 4. Gate GQE3: direct entangling-channel rank

Use identity cell metrics and the frozen scale map and coupling

$$
P=
\begin{pmatrix}
1&0\\
0&0.5\\
0&0
\end{pmatrix},
\qquad g_{\mathrm{link}}=0.8.
$$

For the quadratic link energy $g_{\mathrm{link}}\|Q_B-PQ_A\|^2/2$, the cross-Hessian block is $-g_{\mathrm{link}}P$ and its short-time phase contribution is $+\delta t\,g_{\mathrm{link}}P$. Gate GQE3 passes iff the cross-Hessian singular values are $(0.8,0.4)$ within $\epsilon_{\rm num}$ and its numerical rank is two. This checks that the nonzero singular directions of the metric-aware CassiFI reciprocal map enumerate the directly coupled mode pairs; null directions carry no direct interaction through this link.

## 5. Gate GQE4: exchange flow creates entanglement

Use the basis $(|00\rangle,|01\rangle,|10\rangle,|11\rangle)$, the frozen coupling $g_{\mathrm{link}}=0.7$, and

$$
H_{\rm exchange}
=-g_{\mathrm{link}}\left(|01\rangle\langle10|+|10\rangle\langle01|\right).
$$

Evolve the initial product state $|10\rangle$ to

$$
t_*:=\frac{\pi}{4g_{\mathrm{link}}}.
$$

For amplitudes $a=\langle10|\Psi(t_*)\rangle$ and $b=\langle01|\Psi(t_*)\rangle$, compute

$$
C=2|ab|,
\qquad
K=2g_{\mathrm{link}}|\operatorname{Im}(a^*b)|,
$$

and the reduced purity $\operatorname{Tr}\rho_A^2$. Gate GQE4 passes iff norm is conserved within $\epsilon_{\rm num}$, $C=1$, $K/g_{\mathrm{link}}=1$, and the reduced purity is $1/2$, all within $\epsilon_{\rm num}$.

The current $K$ uses the same imaginary cross-amplitude quadrature as the CassiFI signed link current. The factor of two belongs to this two-state Hamiltonian convention.

## 6. Frozen decision tree and stopping rule

The script executes GQE1 through GQE4 once and prints every diagnostic.

- **PASS**: every gate passes; the final line is `ALL CHECKS PASSED`.
- **FAIL**: any gate fails; the script identifies the gate and exits nonzero.

Execution stops after this deterministic evaluation. Any change to a grid, state, coupling, matrix, formula, tolerance, threshold, or decision rule requires a new preregistration revision before another evidentiary run.

## 7. Interpretation boundary

A PASS checks the declared product-state factorization, the two frozen
nonfactorizable controls, and the entangling capacity of reciprocal CassiFI
links after quantization. Its scope is internal mathematics. The classical
scalar $q$ remains a local-coherence diagnostic, $\mathcal K$ remains an
exchange-current diagnostic, and the nature-level identification remains
Hypothesized. Ordinary quantum-mechanical predictions remain unchanged in
this construction.

## References

- `foundations/quantum-measurement-derivation.md`—regulated CassiFI quantum dynamics and configuration-space guidance.
- `computations/cassifi-quantum-bridge-pre-registration.md`—parent quantum-bridge verification contract.
- `computations/verify_cassifi_quantum_bridge.py`—parent quantum-bridge verifier.
