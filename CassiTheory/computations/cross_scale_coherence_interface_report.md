# Cross-Scale Coherence Interface Report

## Status: PASS—September 2026

## 1. Frozen Question

The EC1–EC7 receipt asks whether two positive Yang/Yin coherence fibres can be
joined by a finite cross-domain correlation block while preserving positivity,
independent relative-frame covariance, interface number and relative-charge
ledgers, and a separated two-sided attenuation law. It also asks whether the
resulting interface source can enter the finite-density coherence-support
budget without adding an unconstrained source directly to the interior fibre.

The protocol is
`computations/cross_scale_coherence_interface_prereg.md`. The executable is
`computations/cross_scale_coherence_interface_check.py`. The integrated theory
is `foundations/yin-yang-qi-dynamical-geometry.md`.

The result combines analytic identities with one deterministic frozen witness.
The positivity factorization, covariance law, interface ledgers, attenuation
bound, source bound, and unitary conservation statements are algebraic. The
reported floating-point values verify their implementation at the registered
matrices.

## 2. First Execution

Run from the CassiTheory repository root:

```text
python computations/cross_scale_coherence_interface_check.py
```

The first and only execution printed:

```text
CROSS-SCALE COHERENCE INTERFACE RECEIPT
phi=1.618033988749895 N=5 tolerance=1.0e-11
EC1: PASS—min_A=7.743e-01 min_B=8.961e-01 ||K0||op=2.641e-01 min_block=6.724e-01 min_Schur=7.370e-01 singular_support=0.000e+00 unsupported_support=5.000e-02 unsupported_min=-2.610e-03
EC2: PASS—K_error=1.694e-16 reconstruction_error=1.388e-16 source_in_error=7.758e-18 source_out_error=7.758e-18
EC3: PASS—Hermitian_error=0.000e+00 number_residual=0.000e+00 charge_residual=0.000e+00 intertwiner_error=0.000e+00
EC4: PASS—closed=1.000000000000 one_sided=0.300283106001 symmetric=0.090169943749 bound_excess=4.163e-17 power_residual=0.000e+00
EC5: PASS—source_norm=6.466e-02 bound=2.054e-01 gamma_c=0.033333333333 witness_error=0.000e+00 DG40_residual=1.084e-19 overlaps=(6.433e-04,0.000e+00,-6.433e-04) zero_errors=(0.000e+00,0.000e+00)
EC6: PASS—unitarity_error=4.441e-16 min_evolved=6.724e-01 trace_residual=2.168e-18 charge_residual=7.772e-16 energy_residual=3.469e-18
EC7: PASS—declared_false=6/6 selected=none
OVERALL: PASS
```

No gate, matrix, coefficient, tolerance, or interpretation changes after this
execution. The checker is not rerun.

## 3. Analytic Interface Closure

### 3.1 Positive enlarged state

Let

$$
A:=\Gamma_{\rm in}\succ0,
\qquad
B:=\Gamma_{\rm out}\succ0,
$$

and write the cross-domain block as

$$
\mathsf C_{\rm io}=A^{1/2}K_{\rm io}B^{1/2}.
$$

The enlarged state factorizes as

$$
\Gamma_{\rm io}
=
\begin{pmatrix}
A&\mathsf C_{\rm io}\\
\mathsf C_{\rm io}^\dagger&B
\end{pmatrix}
=
\begin{pmatrix}
A^{1/2}&0\\
0&B^{1/2}
\end{pmatrix}
\begin{pmatrix}
I&K_{\rm io}\\
K_{\rm io}^\dagger&I
\end{pmatrix}
\begin{pmatrix}
A^{1/2}&0\\
0&B^{1/2}
\end{pmatrix}.
$$

The middle block is positive exactly when every singular value of
$K_{\rm io}$ is at most one. Therefore

$$
\boxed{
\Gamma_{\rm io}\succeq0
\quad\Longleftrightarrow\quad
\|K_{\rm io}\|_{\rm op}\le1.}
$$

This factorization also covers unequal interior and exterior fibre dimensions:
$K_{\rm io}$ is rectangular and the two identity blocks have their compatible
dimensions.

For $B\succ0$, the equivalent Schur condition is

$$
A-\mathsf C_{\rm io}B^{-1}\mathsf C_{\rm io}^\dagger\succeq0.
$$

For singular $B\succeq0$, positivity additionally requires the support
condition

$$
(I-BB^+)\mathsf C_{\rm io}^\dagger=0
$$

and the generalized Schur condition

$$
A-\mathsf C_{\rm io}B^+\mathsf C_{\rm io}^\dagger\succeq0.
$$

The unsupported control demonstrates why the range condition is essential. A
cross block coupled into the null space of $B$ produces a negative enlarged
state eigenvalue.

### 3.2 Independent relative frames

Independent interior and exterior frame changes act through

$$
A\mapsto U_{\rm in}AU_{\rm in}^\dagger,
\qquad
B\mapsto U_{\rm out}BU_{\rm out}^\dagger,
$$

and

$$
\boxed{
\mathsf C_{\rm io}
\mapsto
U_{\rm in}\mathsf C_{\rm io}U_{\rm out}^\dagger.}
$$

Principal matrix square roots transform by conjugation, so normalized
cross-coherence obeys

$$
\boxed{
K_{\rm io}
\mapsto
U_{\rm in}K_{\rm io}U_{\rm out}^\dagger.}
$$

The interface is therefore a two-index object. A scale map must act on both
indices through $K_{a+1}=L_aK_aR_a^\dagger$, or through a covariant
superoperator with the same transformation property.

### 3.3 Conservative exchange ledgers

For

$$
H_{\rm io}
=
\begin{pmatrix}
H_{\rm in}&V\\
V^\dagger&H_{\rm out}
\end{pmatrix}
=H_{\rm io}^\dagger,
$$

the commutator equation gives the diagonal interface sources

$$
\mathcal S_{\rm in}
=-\frac{i}{\hbar}
\left(V\mathsf C_{\rm io}^\dagger
-\mathsf C_{\rm io}V^\dagger\right),
$$

$$
\mathcal S_{\rm out}
=-\frac{i}{\hbar}
\left(V^\dagger\mathsf C_{\rm io}
-\mathsf C_{\rm io}^\dagger V\right).
$$

Both sources are Hermitian. Cyclicity of the trace gives

$$
\boxed{
\operatorname{tr}\mathcal S_{\rm in}
+
\operatorname{tr}\mathcal S_{\rm out}=0.}
$$

When the relative-charge generators satisfy

$$
Q_{\rm in}V=VQ_{\rm out},
$$

the same cyclic rearrangement gives

$$
\boxed{
\operatorname{tr}(Q_{\rm in}\mathcal S_{\rm in})
+
\operatorname{tr}(Q_{\rm out}\mathcal S_{\rm out})=0.}
$$

These are exchange ledgers for the enlarged closed system. Sustained interior
support requires exterior state, boundary data, or reservoir dynamics capable
of maintaining the relevant cross block.

### 3.4 Separated attenuation families

Iteration of the two-sided transfer law gives

$$
K_N
=
(L_{N-1}\cdots L_0)K_0
(R_{N-1}\cdots R_0)^\dagger.
$$

Submultiplicativity gives the general bound

$$
\boxed{
\|K_N\|_F
\le
\left(
\prod_{a=0}^{N-1}
\|L_a\|_{\rm op}\|R_a\|_{\rm op}
\right)
\|K_0\|_F.}
$$

Three assignments have distinct consequences:

1. Unitary $L_a$ and $R_a$ preserve every unitarily invariant norm.
2. $L_a=\sqrt{T_\varphi}U_a$ and unitary $R_a$ give
   $\|K_N\|_F/\|K_0\|_F=\varphi^{-N/2}$.
3. $L_a=\sqrt{T_\varphi}U_a$ and
   $R_a=\sqrt{T_\varphi}W_a$ give
   $\|K_N\|_F/\|K_0\|_F=\varphi^{-N}$.

Here $T_\varphi=\varphi^{-1}$ is the declared routed forward-power fraction.
The separate routed-power ledger is

$$
P_N^{\rm fwd}=\varphi^{-N}P_0^{\rm fwd},
\qquad
\sum_{a=0}^{N-1}P_a^{\rm ret}
=(1-\varphi^{-N})P_0^{\rm fwd}.
$$

Matching exponents across these formulas carries no identification between the
Frobenius norm of $K$ and transported physical power. Such an identification
requires a declared carrier and normalization.

### 3.5 Source capacity and phase

The triangle inequality and the mixed operator/Frobenius norm inequality give

$$
\begin{aligned}
\|\mathcal S_{\rm in}\|_F
&\le
\frac{1}{\hbar}
\left(
\|V\mathsf C_{\rm io}^\dagger\|_F
+
\|\mathsf C_{\rm io}V^\dagger\|_F
\right)\\
&\le
\frac{2}{\hbar}
\|V\|_{\rm op}\|\mathsf C_{\rm io}\|_F.
\end{aligned}
$$

Combining this result with the interior support bound gives the necessary
capacity condition

$$
\boxed{
\frac{2}{\hbar}
\|V\|_{\rm op}\|\mathsf C_{\rm io,N}\|_F
\ge
\gamma_{c,\min}\|c_{\rm in}\|_2.}
$$

The condition is necessary. The stationary transverse ledger also requires
phase alignment:

$$
\operatorname{Re}
\int c_{\rm in}^*S_c^{\rm ext}
=
\int\gamma_c|c_{\rm in}|^2.
$$

The frozen witness separates capacity from phase. Its aligned source produces
positive support overlap, a quadrature interior coherence produces zero real
overlap, and an anti-aligned coherence produces negative overlap.

## 4. Gate Results

### EC1—Positive Block and Schur Controls: PASS

The frozen local blocks are positive, with minimum eigenvalues $0.7743$ and
$0.8961$. The normalized cross-coherence has

$$
\|K_0\|_{\rm op}=0.2641<1.
$$

The enlarged block and Schur complement have minimum eigenvalues $0.6724$ and
$0.7370$. The supported singular control has zero support residual and remains
positive within tolerance. Adding the unsupported entry produces support
residual $0.05$ and minimum enlarged-state eigenvalue
$-2.610\times10^{-3}$.

### EC2—Independent-Frame Covariance: PASS

The transformed normalized block agrees with
$U_{\rm in}K_0U_{\rm out}^\dagger$ to $1.694\times10^{-16}$. Cross-block
reconstruction agrees to $1.388\times10^{-16}$. The interior and exterior
source covariance residuals are each $7.758\times10^{-18}$.

### EC3—Interface Ledgers: PASS

Hermiticity, total number exchange, total relative-charge exchange, and the
frozen intertwiner condition all close with zero residual at the reported
precision.

### EC4—Two-Sided Attenuation: PASS

At $N=5$, the measured Frobenius-norm ratios are

$$
1.000000000000,
\qquad
0.300283106001=\varphi^{-5/2},
\qquad
0.090169943749=\varphi^{-5}.
$$

The largest apparent bound excess is $4.163\times10^{-17}$, below the frozen
tolerance. The forward-plus-return routed-power residual is zero.

### EC5—Reduced Source and Support Witness: PASS

The base source norm is $6.466\times10^{-2}$ against the analytic upper bound
$2.054\times10^{-1}$. The canonical witness gives

$$
\gamma_c=\frac{1}{30}=0.0333333333333
$$

and

$$
S_c^{\rm ext}=\gamma_cc_{\rm test}
$$

with zero source residual. The one-point DG40 residual is
$1.084\times10^{-19}$. The aligned, quadrature, and anti-aligned real overlaps
are respectively

$$
6.433\times10^{-4},
\qquad
0,
\qquad
-6.433\times10^{-4}.
$$

Setting either $V$ or $\mathsf C_{\rm io}$ to zero makes both interface sources
zero at the reported precision.

### EC6—Full Conservative Evolution: PASS

Exact spectral exponentiation of the frozen block Hamiltonian gives unitarity
error $4.441\times10^{-16}$. The evolved state remains positive with minimum
eigenvalue $0.6724$. Trace, total relative charge, and energy residuals are
$2.168\times10^{-18}$, $7.772\times10^{-16}$, and
$3.469\times10^{-18}$.

### EC7—Scope Controls: PASS

All six excluded sectors remain unselected in the receipt:

- a $q$-dependent cross-coherence transfer law;
- a cosmological-bubble interpretation;
- geometry backreaction;
- a mixed-stress constitutive map;
- microscopic reservoir dynamics;
- an import from the local-$SU(2)_Q$ particle branch.

## 5. Verdict

The frozen verdict is

$$
\boxed{\mathrm{PASS}.}
$$

The result establishes a conditional mathematical interface with five useful
properties:

1. local positive fibres admit a bounded cross-domain coherence block;
2. independent relative frames require a two-sided bimodule transformation;
3. reciprocal Hamiltonian exchange closes total number and relative charge;
4. routed attenuation exponents follow only after assigning left and right
   port factors;
5. the induced transverse source obeys a finite capacity bound and must also
   satisfy the phase-sensitive stationary support ledger.

The following physical sectors remain open:

- the identity and dynamics of an exterior domain;
- the origin of the interface coupling $V$;
- selection among closed, one-sided routed, and symmetric routed transfer;
- the microscopic carrier and normalization of routed power;
- the reservoir or boundary dynamics that sustain cross-coherence;
- the mixed Noether stress and any geometry response;
- coupling to the fixed-charge particle branch;
- a finite-energy stationary matter solution and its stability spectrum.

The supplied connected-hierarchy experiment remains evidence for energy
redistribution on its registered graph. It supplies no nested-domain or
exterior-coupling evidence for this interface.

## References

- `computations/cross_scale_coherence_interface_prereg.md`—frozen EC1–EC7
  protocol.
- `computations/cross_scale_coherence_interface_check.py`—deterministic
  first-execution witness.
- `foundations/yin-yang-qi-dynamical-geometry.md`—open matrix balance and
  finite-density support budget.
- `foundations/geometric-manifold-completion.md`—positive fibre and conditional
  scale action.
- `foundations/endpoint-link-and-localization-boundary.md`—relative-frame
  covariance and endpoint exchange ledgers.
- `foundations/interscale-stress-attenuation-boundary.md`—closed and routed
  attenuation families.
- `foundations/cascade-suppression-formula.md`—conditional attenuation
  families.
- `foundations/physical-becoming-hierarchy.md`—conditional bath boundary.
