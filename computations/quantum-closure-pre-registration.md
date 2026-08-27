# Quantum Closure Campaign Preregistration

## Status: Hypothesized—August 2026

## Abstract

This preregistration freezes the finite quantum-closure campaign for the
carrier-reservoir completion described in
`foundations/quantum-measurement-derivation.md` §8.4. Nine deterministic gates
check the modulus projection, exact-uncertainty/Madelung algebra, guidance and
equilibrium boundary, finite measurement instrument, carrier birth-death
completion, projected conversion drift, binomial fluctuation and transport
noise, two-cell diffusion, and operational equivalence. The computation uses
finite matrices and fixed samples. It certifies algebra conditional on the
listed premises. It does not identify CassiFI fields with nature's microscopic
configuration.

## 1. Purpose and source boundary

The purpose is to close the mathematical interfaces left explicit in the
finite carrier-reservoir proposal while retaining their epistemic boundaries.
The companion script is
`computations/verify_quantum_closure.py`. It implements
`certificate_qc1` through `certificate_qc9` and prints one numerical receipt for
every gate followed by the frozen documentary boundaries.

The source boundary is `foundations/quantum-measurement-derivation.md` §8.4,
with the quantum-sector definitions QF1–QF4 in §2 and the finite-volume noise
normalization in `foundations/physical-becoming-hierarchy.md` §4.4. The campaign
starts from the following explicit objects:

1. QF1, the regulated complex Hilbert space;
2. QF2, self-adjoint quantum dynamics or its exact-uncertainty ensemble form;
3. QF3, one actual configuration guided by the selected minimal current;
4. QF4, the quantum-equilibrium preparation condition
   $\rho_Q=|\Psi|^2$;
5. the exact-uncertainty premise with Fisher coefficient
   $\hbar^2/8$;
6. a finite carrier reservoir, a finite apparatus record, and a declared
   density projection;
7. finite-volume transport with positive upwind rates and a Lipschitz
   composition function $q$.

### 1.1 Conditional theorem

**Conditional theorem.** Given QF1–QF4, the exact-uncertainty ensemble action,
the finite CNOT instrument, the stated carrier reservoir, and the stated
finite-volume/hydrodynamic assumptions, the receipts establish a
Derived-conditional projection theorem: the finite carrier process is
completely positive and trace preserving, projects to the declared
conversion drift, has the stated binomial fluctuation law, and has the stated
symmetric transport-noise Fourier kernel. The two-cell calculation supplies
the discrete diffusion identity. The advection-diffusion-conversion PDE is a
limit statement with its own assumptions.

### 1.2 Declared premise

QF1–QF4 remain an explicit minimal premise set. QF3 selects the minimal
current, and QF4 selects the equilibrium ensemble. The exact-uncertainty
postulate supplies the unresolved momentum covariance and the Fisher term.
The apparatus interaction, retained record sectors, carrier reservoir, and
finite-volume bath normalization are also declared premises of this closure.
Each is named so that a later physical derivation can test it independently.

### 1.3 Scope boundary

The certificate is finite and regulated. The finite branch makes no interacting
continuum claim. QC8 states the additional finite-volume/hydrodynamic limit
needed for the full PDE, including positive upwind rates and a Lipschitz $q$;
the two-cell receipt itself is only a discrete conservation check. The
Standard Model spin, fermion, and gauge sectors are conventional tensor
factors in the quantum state space. They are not derived from CassiFI.

### 1.4 Failed promotion

The campaign does not promote the CassiFI physical-identification claim to
Derived. A numerical receipt for a conditional construction is evidence of
internal algebra only. The physical carrier reservoir remains Hypothesized
microphysics. QC9 records the operational-equivalence boundary: with QF4 and
the same CPTP instrument, a hidden-configuration/topological-record model has
the same tested outcome probabilities as ordinary quantum mechanics.

## 2. Frozen implementation and constants

The verifier uses Python's standard library and NumPy only. It uses IEEE-754
double-precision arithmetic, with no SciPy, random seed, optimizer, fit,
parameter search, calibration, or adaptive rerun. The script uses the exact
fixed values

$$
\begin{aligned}
\varphi&=\frac{1+\sqrt 5}{2}, & N&=16, & \rho&=1.7,\\
\gamma&=0.23, & \lambda&=0.41, & \hbar&=1,\\
\epsilon_{\rm num}&=10^{-11}, & \Delta t&=10^{-3}.
\end{aligned}
$$

The transport-noise extension uses a periodic ring with

$$
M=8,
\qquad D=0.37,
\qquad h=0.8,
\qquad m=3,
\qquad q_{\rm frozen}=\frac{\varphi^2}{3}.
$$
The identity
$q_{\rm frozen}=1-1/(3\varphi^2)$ follows from
$\varphi^2=\varphi+1$.

The ring mode uses the explicit discrete symbol

$$
\widehat{k}^{\,2}_m
=\frac{4}{h^2}\sin^2\left(\frac{\pi m}{M}\right).
$$

A residual is a maximum absolute difference unless a gate states a strict
positivity or separation inequality. Residual checks pass when they are at
most $\epsilon_{\rm num}$. The verifier labels its receipts
`NUMERICAL PASS` or `NUMERICAL FAIL`; documentary boundaries never count as
numerical passes.

## 3. QC1—non-injective modulus projection

QC1 fixes two normalized microscopic complex states with the same projected
moduli,

$$
z^{(0)}=(\sqrt{0.7},\sqrt{0.3}),
\qquad
z^{(1)}=(\sqrt{0.7},i\sqrt{0.3}).
$$

The projection is

$$
\mu(z)=(|z_0|^2,|z_1|^2).
$$

The verifier checks the projection residual
$\|\mu(z^{(0)})-\mu(z^{(1)})\|_\infty$, the state separation, the
relative phase gap, and the change in the two-site current

$$
K(z)=\operatorname{Im}(z_0^*z_1).
$$

It also checks the change in the fixed $|+\rangle$ interference probability
$|\langle +|z\rangle|^2$. The same moduli with separated states and a
phase-dependent current/interference value certify non-injectivity.

QC1 passes iff the modulus residual is at most $10^{-11}$ and the phase gap,
state separation, current gap, and interference gap each exceed $10^{-3}$.
The microscopic phase is independent and never derived by this gate.

## 4. QC2—exact-uncertainty/Madelung algebra

QC2 uses the fixed sample points

$$
x=(-1.2,-0.4,0.3,1.1),
\qquad a=0.7,
\qquad b=0.2,
$$

and the positive analytic density

$$
\rho(x)=\exp(-a x^2+b x),
\qquad R=\sqrt{\rho}.
$$

The derivatives are evaluated analytically from

$$
\partial_x\ln\rho=-2ax+b,
\qquad
\partial_x^2\rho=\rho\left[(-2ax+b)^2-2a\right],
$$

and the action's fixed Fisher coefficient is

$$
 c_{\rm F}=\frac{\hbar^2}{8}=\frac18.
$$

The verifier checks the exact identity

$$
\rho(\partial_x\ln\rho)^2
=4(\partial_x\sqrt{\rho})^2,
$$

the variational identity

$$
 c_{\rm F}\left[-2\frac{\partial_x^2\rho}{\rho}
+\left(\frac{\partial_x\rho}{\rho}\right)^2\right]
=-\frac{\hbar^2}{2}\frac{\partial_x^2R}{R},
$$

and the kinetic Madelung split for the fixed phase gradient

$$
\partial_xS=0.37-0.23x,
\qquad
|\partial_x(R e^{iS/\hbar})|^2
=(\partial_xR)^2+R^2(\partial_xS)^2/\hbar^2.
$$

QC2 passes iff all three residuals and the coefficient residual are at most
$10^{-11}$. The result is conditional on the ensemble action and the
exact-uncertainty premise. It is not a derivation of that premise from the
canonical real density pair.

## 5. QC3—guidance and equilibrium boundary

QC3 uses the periodic $8\times8$ torus grid

$$
 x_j=y_j=\frac{2\pi j}{8},
 \qquad j=0,\ldots,7,
$$

with fixed equilibrium density $\rho=1$ and base velocity

$$
 v_0=(0.31,-0.22).
$$

The base current is $J_0=\rho v_0$. The fixed current addition is

$$
 K(x,y)=(0.17\sin y,-0.11\sin x),
$$

whose periodic divergence is zero. The verifier checks that
$\operatorname{div}(J_0+K)=\operatorname{div}J_0$ while the velocity
changes by $K/\rho$.

The nonequilibrium ratio is evaluated at $t=1.3$:

$$
 r(x,y,t)=1+0.15\sin(x-0.31t)+0.11\cos(y+0.22t),
 \qquad \sigma=\rho r.
$$

It obeys the fixed transport identity

$$
(\partial_t+0.31\partial_x-0.22\partial_y)r=0,
$$

while $r$ remains positive and differs from one. The divergence, continuity,
transport, and positivity residuals are computed on the frozen grid.

QC3 passes iff the divergence, continuity, and transport residuals are at most
$10^{-11}$, the altered velocity and nonequilibrium gap each exceed $10^{-3}$,
and $\min r>0$. A divergence-free current addition preserves the continuity
equation, so QF3's minimal-current choice remains a declared premise. The
transported ratio shows that QF4 is a preparation condition rather than an
attractor.

## 6. QC4—finite CNOT measurement instrument

QC4 uses the Bell state on system $A$ and remote qubit $B$,

$$
|\Phi^+\rangle=\frac{|00\rangle+|11\rangle}{\sqrt2},
\qquad
\varrho_{AB}=|\Phi^+\rangle\langle\Phi^+|,
$$

and a ready record qubit $R$ in $|0\rangle$. The ordered basis is
$(A,B,R)$. A finite CNOT maps the record bit as

$$
|a,b,r\rangle\longmapsto|a,b,r\oplus a\rangle.
$$

The two system Kraus operators are the fixed computational projectors

$$
M_0=|0\rangle\langle0|,
\qquad M_1=|1\rangle\langle1|,
\qquad
M_0^\dagger M_0+M_1^\dagger M_1=\mathbf1.
$$

For the CNOT output, each record branch is projected with
$P_k=|k\rangle_R\langle k|$. The verifier checks:

1. CNOT unitarity and Kraus completeness;
2. branch weights from the finite interaction against
   $p_k=\operatorname{Tr}(M_k\rho_A M_k^\dagger)$;
3. the reduced branch on $AB$ against
   $(M_k\otimes\mathbf1_B)\varrho_{AB}(M_k^\dagger\otimes\mathbf1_B)$;
4. each retained record state against $p_k|k\rangle\langle k|$;
5. the remote state before and after outcome averaging.

QC4 passes iff every residual is at most $10^{-11}$. The Born branch weights
are conditional on QF4. The finite instrument supplies a retained record
within the declared apparatus construction; it does not derive the outcome
basis from the CassiFI density variables.

## 7. QC5—finite two-species Lindblad birth-death completion

The carrier-count basis is $|k\rangle$ for $k=0,\ldots,N$, where $k$ counts
Yang carriers. The fixed jump operators are

$$
(L_{\downarrow})_{k-1,k}=\sqrt{\gamma k}
\quad (k=1,\ldots,N),
$$

$$
(L_{\uparrow})_{k+1,k}=\sqrt{\varphi\gamma(N-k)}
\quad (k=0,\ldots,N-1).
$$

Set

$$
A=L_{\downarrow}^\dagger L_{\downarrow}
 +L_{\uparrow}^\dagger L_{\uparrow},
\qquad
\Delta t=10^{-3}.
$$

The finite Kraus/Euler step is

$$
K_0=\sqrt{\mathbf1-\Delta t A},
\qquad
K_{\downarrow}=\sqrt{\Delta t}L_{\downarrow},
\qquad
K_{\uparrow}=\sqrt{\Delta t}L_{\uparrow}.
$$

Here $A$ is diagonal, so the square root in $K_0$ is the componentwise
positive square root. The verifier uses the fixed normalized pure state with
components

$$
\psi_k\propto\sqrt{k+1}e^{0.17ik},
\qquad
\varrho_0=|\psi\rangle\langle\psi|,
$$

and evolves it by

$$
\varrho_1=K_0\varrho_0K_0^\dagger
 +K_{\downarrow}\varrho_0K_{\downarrow}^\dagger
 +K_{\uparrow}\varrho_0K_{\uparrow}^\dagger.
$$

The gate checks the nonnegative square-root arguments, Kraus completeness,
trace preservation, Hermiticity, positivity of $\varrho_1$ by its smallest
eigenvalue, and the exact diagonal first-order master equation. For
$p_k=(\varrho_0)_{kk}$, the tested equation is

$$
\dot p_k
=\gamma(k+1)p_{k+1}
 +\varphi\gamma(N-k+1)p_{k-1}
 -\left[\gamma k+\varphi\gamma(N-k)\right]p_k,
$$

with out-of-range populations set to zero. The diagonal of $\varrho_1$ must
equal $p_k+\Delta t\dot p_k$ to tolerance.

QC5 passes iff the Kraus square-root arguments are nonnegative, the
completeness, trace, Hermiticity, diagonal, and diagonal-imaginary residuals
are at most $10^{-11}$, and the minimum eigenvalue is at least
$-10^{-11}$. The finite Kraus construction is positivity preserving by
construction. It certifies the regulated Lindblad structure; it is not an
interacting continuum limit.

## 8. QC6—projected conversion drift

For the same carrier count $k$ and fixed total density $\rho$, define

$$
E_Y(k)=\rho\frac{k}{N},
\qquad
E_I(k)=\rho\frac{N-k}{N},
\qquad
\varepsilon(k)=E_Y-\varphi E_I
=\rho\left[\frac{(1+\varphi)k}{N}-\varphi\right].
$$

The birth and death rates give

$$
\mathbb E[\dot k\mid k]
=\varphi\gamma(N-k)-\gamma k.
$$

The verifier computes the projected drifts

$$
\dot E_Y=\frac{\rho}{N}\mathbb E[\dot k\mid k],
\qquad
\dot E_I=-\dot E_Y,
$$

for every $k=0,\ldots,N$. QC6 passes iff

$$
\dot E_Y=-\gamma\varepsilon,
\qquad
\dot E_I=+\gamma\varepsilon,
\qquad
E_Y+E_I=\rho,
\qquad
\dot E_Y+\dot E_I=0
$$

all hold to $10^{-11}$ in the maximum residual. The signs use $k$ as the
Yang-carrier count.

## 9. QC7—binomial equilibrium, decay, and transport-noise mode

The stationary law for the Yang count is fixed as

$$
\pi_k=\binom Nk p_Y^k p_I^{N-k},
\qquad
p_Y=\frac{\varphi}{1+\varphi}=\varphi^{-1},
\qquad
p_I=\frac{1}{1+\varphi}=\varphi^{-2}.
$$

The verifier checks normalization and detailed balance for every adjacent
pair,

$$
\pi_k\,\varphi\gamma(N-k)
=\pi_{k+1}\,\gamma(k+1).
$$

Using the QC6 imbalance, it checks

$$
\mathbb E_\pi[\varepsilon]=0,
\qquad
\operatorname{Var}_\pi(\varepsilon)
=\frac{\varphi\rho^2}{N},
$$

and checks the pointwise linear decay identity

$$
\mathbb E[\dot\varepsilon\mid k]
=-\Gamma\varepsilon(k),
\qquad
\Gamma=\varphi^2\gamma.
$$

At the canonical frozen background, use the fixed $\lambda$ and

$$
\gamma_{\rm bg}=\frac{\lambda}{3\varphi^2},
\qquad
q_{\rm frozen}=q_{\rm eq}=\frac{\varphi^2}{3},
$$

so that

$$
\Gamma_{\rm bg}=\varphi^2\gamma_{\rm bg}
=\lambda(1-q_{\rm eq})=\frac{\lambda}{3},
$$

and

$$
B_\varepsilon^2
=2\Gamma_{\rm bg}\operatorname{Var}(\varepsilon)
=\frac{2\lambda\varphi\rho^2}{3N}.
$$

### 9.1 Homogeneous periodic transport-noise certificate

The frozen-$q$ extension uses the periodic $M=8$ ring, $D=0.37$, $h=0.8$,
and Fourier mode $m=3$. Its symmetric carrier-hopping generator has rate
$D/h^2$ to each neighbor and diagonal $-2D/h^2$. For the complex mode
$e_j=\exp(2\pi i m j/M)$, the verifier checks

$$
L_D e=-D\widehat{k}^{\,2}_m e,
\qquad
\widehat{k}^{\,2}_m
=\frac{4}{h^2}\sin^2\left(\frac{\pi m}{M}\right),
$$

and therefore checks the linear-noise decay

$$
\Gamma_m=\Gamma_{\rm bg}+D\widehat{k}^{\,2}_m.
$$

The homogeneous per-cell carrier count is $\bar N=N$ and the homogeneous
density is $\rho_0=\rho$. The mode variance and noise power are fixed as

$$
V_\varepsilon=\frac{\varphi\rho_0^2}{\bar N},
\qquad
\mathcal N_\varepsilon(m)=2\left(\Gamma_{\rm bg}
+D\widehat{k}^{\,2}_m\right)V_\varepsilon.
$$

The verifier checks the Fourier residual, ring column-sum conservation, the
variance against $\varphi\rho_0^2/\bar N$, and the noise power against the
last expression. This is a homogeneous/frozen-$q$ finite-regulator
certificate. It does not select a state-dependent stochastic calculus or a
continuum bath kernel.

QC7 passes iff every probability, detailed-balance, variance, decay,
canonical-background, Fourier, column-sum, and noise-power residual is at most
$10^{-11}$.

## 10. QC8—two-cell symmetric carrier hopping

Use two cells with the fixed diffusion coefficient $D=0.37$, spacing $h=0.8$,
and hopping rate $r=D/h^2$. The generator acting on column densities is

$$
L_2=r\begin{pmatrix}-1&1\\1&-1\end{pmatrix}.
$$

Use the fixed species vectors

$$
E_Y=(1.2,0.7),
\qquad E_I=(0.5,0.9).
$$

The verifier checks positive off-diagonal rate $r$, zero column sums, and the
finite-volume drift for each species,

$$
(L_2E)_1=r(E_2-E_1),
\qquad
(L_2E)_2=r(E_1-E_2),
\qquad
\mathbf1^{\mathsf T}L_2E=0.
$$

QC8 passes iff the rate is positive and the generator, drift, and species
conservation residuals are at most $10^{-11}$. The complete
advection-diffusion-conversion PDE requires a declared finite-volume sequence,
positive upwind advection rates, consistent cell-volume scaling, a
hydrodynamic limit, and a Lipschitz $q$. Those are documentary conditions and
are printed separately from the numerical pass.

## 11. QC9—operational equivalence

Use the fixed density matrix

$$
\varrho=\begin{pmatrix}
0.7&0.18-0.11i\\
0.18+0.11i&0.3
\end{pmatrix}.
$$

The two fixed projective settings are the computational pair
$(|0\rangle,|1\rangle)$ and the Hadamard pair
$(|+\rangle,|-\rangle)$. For each setting, the effects are $E_k$ and the
CPTP instrument uses the projectors as Kraus operators. Ordinary quantum
mechanics assigns

$$
p_k^{\rm QM}=\operatorname{Tr}(E_k\varrho).
$$

The hidden-configuration/topological-record model uses the same $\varrho$,
the same CPTP instruments, and QF4 to assign the configuration weights
$q_k=p_k^{\rm QM}$. Its topological record map is the fixed one-hot map
$T_{rk}=\delta_{rk}$. Thus the recorded probability is

$$
p_r^{\rm hidden}=\sum_kT_{rk}q_k.
$$

The verifier checks density-matrix positivity, trace and Hermiticity, CPTP
completeness, one-hot record sectors, normalized probabilities, and

$$
\max_{s,r}|p_{r,s}^{\rm hidden}-p_{r,s}^{\rm QM}|.
$$

QC9 passes iff all residuals are at most $10^{-11}$. Operational equivalence
means that this hidden/topological record construction has the same tested
finite outcome probabilities as ordinary quantum mechanics. A Cassi-specific
discriminator requires altered operational dynamics, nonequilibrium, or a new
observable.

## 12. Output, stopping rule, and decision tree

The verifier calls QC1 through QC9 exactly once in namespace order. It prints
every numerical receipt, then prints all frozen documentary boundary and
decision lines. The final line is `ALL CHECKS PASSED` only when every numerical
contract passes and every documentary line has been printed. Any failed
numerical contract ends with `CHECKS FAILED` after all receipts have been
shown.

The protocol is a single deterministic evaluation. Execution stops after that
receipt. A change to any constant, grid, state, matrix, rate, sample,
tolerance, equation, documentary boundary, or pass condition requires a new
preregistration before another evidentiary run. The verifier is intentionally
left unexecuted in this source artifact; the first run belongs to the locked
protocol owner.

The decision tree is:

1. If QC1–QC9 all pass numerically and every boundary line is printed, record
   the finite algebraic campaign as complete.
2. **ADOPT** the minimal finite-regulator reservoir completion as
   **Hypothesized microphysics** with a **Derived-conditional projection
   theorem**.
3. **REJECT** promotion of CassiFI physical identification to **Derived**.
4. **RETAIN** QF1–QF4 as the explicit minimal premise set.
5. Keep the finite branch separate from any interacting continuum claim.
6. Keep SM spin/fermion/gauge sectors as conventional tensor factors rather
   than derived CassiFI sectors.

A numerical failure returns the associated algebraic constraint without
changing these epistemic decisions. A documentary condition is reported as a
boundary, never as a numerical PASS.

## 13. Epistemic ledger

| Item | Status fixed by this protocol |
|---|---|
| QC1 modulus projection and independent phase | Algebraic receipt; microscopic phase remains independent and never derived |
| QC2 Fisher/Madelung equivalence | Derived conditional on the ensemble action and $\hbar^2/8$ |
| QC3 guidance and equilibrium | QF3 and QF4 remain declared premises |
| QC4 CNOT instrument | Derived conditional finite instrument; Born weights conditional on QF4 |
| QC5 birth-death channel | Derived conditional finite CPTP completion |
| QC6 conversion projection | Derived conditional on carrier rates and density map |
| QC7 equilibrium and frozen-$q$ noise | Derived conditional finite-regulator identities |
| QC8 diffusion | Derived conditional two-cell finite-volume identity; PDE limit remains conditional |
| QC9 hidden/topological operational model | Operationally equivalent on the tested CPTP instruments |
| Minimal finite-regulator reservoir | **Hypothesized microphysics** |
| CassiFI physical identification | **Failed promotion** to Derived |
| QF1–QF4 | Explicit minimal premise set retained |
| Interacting continuum | Scope excluded from the finite branch |
| SM spin/fermion/gauge sectors | Conventional tensor factors |

## 14. Protocol lock

The following clauses are locked before execution:

- the gate names QC1–QC9 and their order;
- $\varphi$, $N=16$, $\rho=1.7$, $\gamma=0.23$, $\lambda=0.41$,
  $\hbar=1$, $\Delta t=10^{-3}$, and $\epsilon_{\rm num}=10^{-11}$;
- all vectors, matrices, grids, ring mode, rates, and sample points above;
- the positive Kraus/Euler construction in QC5;
- the Yang-count convention $E_Y=\rho k/N$ and the sign of $\varepsilon$;
- $q_{\rm eq}=\varphi^2/3$, $\gamma_{\rm bg}=\lambda/(3\varphi^2)$,
  and $\Gamma_{\rm bg}=\lambda/3$;
- the finite-volume and frozen-$q$ qualifications;
- the boundary language and the final ADOPT/REJECT/RETAIN decisions;
- the one-run stopping rule and the requirement that documentary boundaries
  never be reported as numerical passes.

## References

- `foundations/quantum-measurement-derivation.md`—QF1–QF4, exact-uncertainty action, finite instrument, and carrier-reservoir completion.
- `foundations/physical-becoming-hierarchy.md`—finite-volume Markov bath, conversion noise, and frozen-background transport response.
- `computations/verify_quantum_closure.py`—companion deterministic QC1–QC9 verifier.
- G. Lindblad, “On the generators of quantum dynamical semigroups,” *Communications in Mathematical Physics* **48**, 119–130 (1976).
- J. E. Hall and M. Reginatto, “Interacting particles in an exact uncertainty approach to quantum theory,” *Journal of Physics A* **35**, 3289–3303 (2002).
