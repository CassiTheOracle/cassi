# CassiFI Quantum Bridge Verification Preregistration

## Status: Hypothesized—August 2026

## Abstract

This document freezes the deterministic checks for the regulated CassiFI quantum bridge in `foundations/quantum-measurement-derivation.md`. The computation checks finite-dimensional unitarity, free-particle dispersion with the published sodium-cluster anchors, composite-system entanglement and operational no-signalling, Born-density equivariance, and the absence of an intrinsic macrorealist visibility multiplier. The calculation audits the stated mathematics; it does not test the hypothesis that the CassiFI field is nature's microscopic configuration.

## 1. Frozen implementation

The companion script is `computations/verify_cassifi_quantum_bridge.py`. It uses Python's standard library and NumPy only. All matrices, state vectors, constants, tolerances, and candidate exponents are fixed here before the first execution.

The computation uses IEEE-754 double precision and the following common tolerance:

$$
\epsilon_{\rm num}=10^{-12}.
$$

There is no random seed, optimization, fit, parameter search, or apparatus calibration.

## 2. Gate GQ1: finite regulated Hamiltonian evolution

Use the positive CassiFI configuration metric

$$
G=\operatorname{diag}(w_D,w_D,w_C,w_C),
\qquad
w_D=\frac{1}{1+\varphi^2},
\qquad
w_C=1+\varphi^2,
$$

and the fixed Hermitian matrix

$$
H=\begin{pmatrix}
0.7&0.2+0.1i&0&-0.05i\\
0.2-0.1i&1.1&0.15&0\\
0&0.15&1.6&0.12+0.04i\\
0.05i&0&0.12-0.04i&2.0
\end{pmatrix}.
$$

Propagate the normalized fixed state

$$
\Psi_0\propto(1,\,i,\,-0.4+0.2i,\,0.3)^T
$$

for $t=3.7$ with $\hbar=1$ by diagonalizing $H$ and applying $\exp(-iHt)$. Gate GQ1 passes iff:

1. every eigenvalue of $G$ is positive;
2. $\|H-H^\dagger\|_\infty\leq\epsilon_{\rm num}$;
3. $|\|\Psi(t)\|_2^2-1|\leq\epsilon_{\rm num}$.

## 3. Gate GQ2: Schrödinger dispersion and sodium-cluster scales

Use CODATA exact constants

$$
h=6.62607015\times10^{-34}\ {\rm J\,s},
\qquad
1\ {\rm Da}=1.66053906660\times10^{-27}\ {\rm kg},
$$

with the experiment's central values

$$
M=172{,}000\ {\rm Da},\qquad
v=160\ {\rm m\,s^{-1}},\qquad
d=133\ {\rm nm},\qquad L=0.983\ {\rm m}.
$$

The frozen derived quantities are

$$
\lambda_{\rm dB}=\frac{h}{Mv},
\qquad
L_T=\frac{d^2}{\lambda_{\rm dB}},
\qquad
\xi=\frac{L}{L_T},
\qquad
t_{13}=\frac{2L}{v}.
$$

For fixed wave numbers $k=(0.2,0.7,1.3,2.1)$ and mass $M_*=3.4$ in dimensionless audit units with $\hbar=1$, compare the Hamiltonian eigenvalue $\hbar^2k^2/(2M_*)$ with the energy equivalent $\hbar\omega$ from $\omega=\hbar k^2/(2M_*)$.

Gate GQ2 passes iff the dispersion residual is at most $\epsilon_{\rm num}$ and all experimental anchors lie in these frozen intervals:

$$
14\ {\rm fm}\leq\lambda_{\rm dB}\leq15\ {\rm fm},
$$

$$
1.20\ {\rm m}\leq L_T\leq1.24\ {\rm m},
\qquad
0.79\leq\xi\leq0.82,
\qquad
12.0\ {\rm ms}\leq t_{13}\leq12.6\ {\rm ms}.
$$

## 4. Gate GQ3: entanglement and operational no-signalling

Use the Bell state

$$
|\Phi^+\rangle=\frac{|00\rangle+|11\rangle}{\sqrt2}
$$

on $\mathbb C^2\otimes\mathbb C^2$. Compute both reduced density matrices. Apply the fixed unitary

$$
U_B=\frac{1}{\sqrt2}
\begin{pmatrix}1&1\\-1&1\end{pmatrix}
$$

on subsystem $B$, then recompute subsystem $A$'s reduced state.

Gate GQ3 passes iff:

1. both initial reduced states equal $I/2$ within $\epsilon_{\rm num}$;
2. $\rho_A$ is unchanged by $I\otimes U_B$ within $\epsilon_{\rm num}$;
3. the Bell-state purity is one and the reduced-state purity is one half within $\epsilon_{\rm num}$.

## 5. Gate GQ4: Born density and local equivariance identity

Use the normalized fixed coefficient vector

$$
c\propto(1,\,2i,\,-0.5+0.25i,\,0.3)^T.
$$

The outcome probabilities are $p_k=|c_k|^2$. Gate GQ4 requires $p_k\geq0$ and $|\sum_kp_k-1|\leq\epsilon_{\rm num}$.

For a local candidate density $f(u)=u^\alpha$, common transport with $u=|\Psi|^2$ requires

$$
u f'(u)-f(u)=0
$$

for every $u>0$. Evaluate the relative identity residual

$$
r_\alpha(u)=\frac{|u f'(u)-f(u)|}{f(u)}=|\alpha-1|
$$

on $u=(0.01,0.2,0.7,1.4)$ for the frozen candidates $\alpha=(0.5,1,2)$. Gate GQ4 passes iff $\alpha=1$ is the unique candidate with maximum residual at most $\epsilon_{\rm num}$.

This numerical gate checks the algebraic identity at representative positive values. The analytic derivation in `foundations/quantum-measurement-derivation.md` establishes the general local result.

## 6. Gate GQ5: nanoparticle visibility constraint

Use the published macrorealist bound

$$
\tau_e=2.84\times10^{15}\ {\rm s}
$$

and compute

$$
\mu=\log_{10}(\tau_e/1\ {\rm s}).
$$

The CassiFI quantum bridge contains no intrinsic stochastic-collapse or macrorealist localization term. Its Talbot-Lau multiplier is therefore

$$
R_\ell^{\rm CassiFI}=1
$$

for every integer harmonic $\ell$ before ordinary environmental and apparatus factors are applied.

Gate GQ5 passes iff $|\mu-15.45|\leq0.01$, $R_0=1$ exactly, and the frozen harmonics $\ell=(-3,-2,-1,0,1,2,3)$ all return $R_\ell^{\rm CassiFI}=1$ exactly.

## 7. Frozen decision tree and stopping rule

The script executes GQ1 through GQ5 once and prints each gate's measured residuals and derived anchors.

- **PASS**: every gate passes; the final line is `ALL CHECKS PASSED`.
- **FAIL**: any gate fails; the script reports the failing gate and exits nonzero.

Execution stops after the single deterministic evaluation. Any change to a matrix, state, constant, interval, tolerance, candidate exponent, or decision rule requires a new preregistration revision before another evidentiary run.

## 8. Interpretation boundary

A PASS establishes internal agreement among the finite Hamiltonian construction, Schrödinger dispersion, tensor-product state space, Born equivariance identity, and the stated no-collapse nanoparticle limit. It supplies no empirical evidence for the CassiFI physical-identification postulate, no derivation of quantum equilibrium from topology alone, and no apparatus-specific fit to the sodium-cluster visibility data.

## References

- `foundations/quantum-measurement-derivation.md`—regulated CassiFI quantum dynamics and measurement derivation.
- `open-questions-cassi-answers.md` Q7—canonical registry entry for the quantum bridge.
- Fein et al., “Quantum superposition of molecules beyond 25 kDa,” *Nature Physics* 15, 1242–1245 (2019), https://doi.org/10.1038/s41567-019-0663-9.
- “Quantum interference of sodium nanoparticles,” *Nature* (2026), https://doi.org/10.1038/s41586-025-09917-9.
