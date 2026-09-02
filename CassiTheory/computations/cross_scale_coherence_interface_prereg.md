# Cross-Scale Coherence Interface Preregistration

## Status: Preregistered—September 2026

## 1. Question

Can two positive Yang/Yin coherence fibres be joined by a finite cross-domain
correlation block so that the enlarged state remains positive, independent
relative-frame covariance is exact, interface exchange closes its number and
relative-charge ledgers, and cross-scale attenuation reaches the interior
support budget through a two-sided transfer law?

The receipt tests the mathematical interface only. A physical exterior bubble,
cosmological boundary, carrier field, reservoir reduction, stress tensor, and
geometry backreaction remain unselected.

## 2. Source Boundary

The frozen authorities are:

- `foundations/yin-yang-qi-dynamical-geometry.md` DG29 and DG39–DG41—the open
  matrix balance, transverse source equation, stationary support budget, and
  source-norm lower bound;
- `foundations/geometric-manifold-completion.md` GM44–GM51—the conditional
  conservative scale action, matrix continuity ansatz, canonical conversion,
  and positive Hermitian fibre;
- `foundations/endpoint-link-and-localization-boundary.md` ELR26–ELR35—the
  Wilson transformation, endpoint exchange, relative-charge ledger, and
  capacity boundary;
- `foundations/interscale-stress-attenuation-boundary.md` §§4.5–4.7—the
  distinction between closed coherent propagation and routed non-re-entry,
  including forward amplitude $\varphi^{-N/2}$ and quadratic forward flux
  $\varphi^{-N}$;
- `foundations/cascade-suppression-formula.md` §§1.2–1.3—the separate uniform
  signal and simultaneous-coherence attenuation families;
- `foundations/physical-becoming-hierarchy.md` OS1–OS3—the conditional
  Markov-bath boundary and the unresolved microscopic reservoir.

The supplied graph in
`field-experience/toroidal-connected-hierarchy-report.md` establishes energy
redistribution within that registered proxy. It does not establish
nested-domain exchange, an exterior reservoir, or a physical cross-domain
coherence channel and supplies no evidence gate for this receipt.

## 3. Enlarged Positive State

Let the interior and exterior Yang/Yin fibres be

$$
A:=\Gamma_{\rm in}\in\operatorname{Herm}_2^+,
\qquad
B:=\Gamma_{\rm out}\in\operatorname{Herm}_2^+.
$$

The cross-domain coherence block is denoted $\mathsf C_{\rm io}\in
\mathbb C^{2\times2}$. The enlarged state is

$$
\boxed{
\Gamma_{\rm io}
:=
\begin{pmatrix}
A&\mathsf C_{\rm io}\\
\mathsf C_{\rm io}^\dagger&B
\end{pmatrix}
\succeq0.}
\tag{EC1}
$$

The symbol $\mathsf C_{\rm io}$ avoids collision with the compact phase,
chemotactic mobility, and core-carrier symbols already denoted by variants of
$\chi$ elsewhere in the repository.

For positive-definite $B$, block positivity is equivalent to

$$
\boxed{
A-\mathsf C_{\rm io}B^{-1}\mathsf C_{\rm io}^\dagger\succeq0.}
\tag{EC2}
$$

For singular $B\succeq0$, the frozen support and pseudoinverse conditions are

$$
\boxed{
\left(I-BB^+\right)\mathsf C_{\rm io}^\dagger=0,
\qquad
A-\mathsf C_{\rm io}B^+\mathsf C_{\rm io}^\dagger\succeq0,}
\tag{EC3}
$$

where $B^+$ is the Moore–Penrose pseudoinverse.

When $A$ and $B$ are positive definite, define normalized cross-coherence

$$
\boxed{
K_{\rm io}
:=A^{-1/2}\mathsf C_{\rm io}B^{-1/2}.}
\tag{EC4}
$$

Then

$$
\Gamma_{\rm io}\succeq0
\quad\Longleftrightarrow\quad
\|K_{\rm io}\|_{\rm op}\le1.
\tag{EC5}
$$

This separates local fibre support from the fraction that remains correlated
across the interface.

## 4. Independent Relative-Frame Covariance

Interior and exterior relative frames may rotate independently:

$$
U_{\rm in}
:=\exp\!\left(-\frac{i\alpha}{2}\sigma_3\right),
\qquad
U_{\rm out}
:=\exp\!\left(-\frac{i\beta}{2}\sigma_3\right).
\tag{EC6}
$$

The blocks and interface coupling transform as

$$
\begin{aligned}
A&\longmapsto U_{\rm in}AU_{\rm in}^\dagger,\\
B&\longmapsto U_{\rm out}BU_{\rm out}^\dagger,\\
\mathsf C_{\rm io}&\longmapsto
U_{\rm in}\mathsf C_{\rm io}U_{\rm out}^\dagger,\\
V&\longmapsto U_{\rm in}VU_{\rm out}^\dagger,\\
K_{\rm io}&\longmapsto
U_{\rm in}K_{\rm io}U_{\rm out}^\dagger.
\end{aligned}
\tag{EC7}
$$

A single left Wilson matrix does not define this bimodule transformation. Any
cross-scale transfer must act on both indices or be supplied as a covariant
superoperator.

## 5. Conservative Interface and Reduced Source

Use the time-independent block Hamiltonian

$$
\boxed{
H_{\rm io}
:=
\begin{pmatrix}
H_{\rm in}&V\\
V^\dagger&H_{\rm out}
\end{pmatrix}
=H_{\rm io}^\dagger.}
\tag{EC8}
$$

The enlarged conservative equation is

$$
\dot\Gamma_{\rm io}
=-\frac{i}{\hbar}[H_{\rm io},\Gamma_{\rm io}].
\tag{EC9}
$$

Its interior and exterior interface sources are

$$
\boxed{
\begin{aligned}
\mathcal S_{\rm in}
&:=-\frac{i}{\hbar}
\left(V\mathsf C_{\rm io}^\dagger
-\mathsf C_{\rm io}V^\dagger\right),\\
\mathcal S_{\rm out}
&:=-\frac{i}{\hbar}
\left(V^\dagger\mathsf C_{\rm io}
-\mathsf C_{\rm io}^\dagger V\right).
\end{aligned}}
\tag{EC10}
$$

They obey

$$
\mathcal S_{\rm in}=\mathcal S_{\rm in}^\dagger,
\qquad
\mathcal S_{\rm out}=\mathcal S_{\rm out}^\dagger,
\qquad
\operatorname{tr}\mathcal S_{\rm in}
+\operatorname{tr}\mathcal S_{\rm out}=0.
\tag{EC11}
$$

Let $Q_{\rm in}=Q_{\rm out}:=\sigma_3/2$. If

$$
Q_{\rm in}V=VQ_{\rm out},
\tag{EC12}
$$

then the interface also obeys

$$
\boxed{
\operatorname{tr}(Q_{\rm in}\mathcal S_{\rm in})
+
\operatorname{tr}(Q_{\rm out}\mathcal S_{\rm out})
=0.}
\tag{EC13}
$$

The reduced transverse source is

$$
S_c^{\rm ext}:=(\mathcal S_{\rm in})_{IY}.
\tag{EC14}
$$

It is derived from the enlarged state and interface. The receipt does not add
an unconstrained off-diagonal source directly to $A$.

## 6. Two-Sided Cross-Scale Transfer

One scale interface acts on normalized cross-coherence through

$$
\boxed{
K_{a+1}=L_aK_aR_a^\dagger.}
\tag{EC15}
$$

The frozen receipt uses two-dimensional interior and exterior fibres. For
different fibre dimensions, $K_a$ is rectangular and $L_a$ and $R_a$ act on
its compatible left and right spaces; equations (EC15)–(EC17) are unchanged.

Iteration gives

$$
K_N
=
\left(L_{N-1}\cdots L_0\right)
K_0
\left(R_{N-1}\cdots R_0\right)^\dagger,
\tag{EC16}
$$

and therefore

$$
\boxed{
\|K_N\|_F
\le
\left(\prod_{a=0}^{N-1}\|L_a\|_{\rm op}\|R_a\|_{\rm op}\right)
\|K_0\|_F.}
\tag{EC17}
$$

Three separate frozen cases are tested:

1. **Closed coherent control:** $L_a$ and $R_a$ are unitary, so every unitarily
   invariant norm of $K$ is preserved.
2. **One-sided routed case:**
   $\|L_a\|_{\rm op}=\sqrt{T_\varphi}=\varphi^{-1/2}$ and
   $\|R_a\|_{\rm op}=1$, giving
   $\|K_N\|_F/\|K_0\|_F=\varphi^{-N/2}$.
3. **Symmetric routed case:** both operator norms equal
   $\sqrt{T_\varphi}$, giving
   $\|K_N\|_F/\|K_0\|_F=\varphi^{-N}$.

Here $T_\varphi=\varphi^{-1}$ is the declared golden forward-power fraction.
The routed forward-power and complementary-return ledger remains

$$
P_N^{\rm fwd}=\varphi^{-N}P_0^{\rm fwd},
\qquad
\sum_{a=0}^{N-1}P_a^{\rm ret}
=(1-\varphi^{-N})P_0^{\rm fwd}.
\tag{EC18}
$$

The cases do not select a physical law for $\mathsf C_{\rm io}$. They expose
which exponent follows after the left/right port assignment is declared.

## 7. Support Bound

Equation (EC10) gives the Frobenius-norm bound

$$
\boxed{
\|\mathcal S_{\rm in}\|_F
\le
\frac{2}{\hbar}
\|V\|_{\rm op}
\|\mathsf C_{\rm io}\|_F.}
\tag{EC19}
$$

Combining this with DG41 yields the necessary cross-domain support condition

$$
\boxed{
\frac{2}{\hbar}
\|V\|_{\rm op}
\|\mathsf C_{\rm io,N}\|_F
\ge
\gamma_{c,\min}\|c_{\rm in}\|_2.}
\tag{EC20}
$$

This norm condition is necessary and is not sufficient. Stationary support
also requires the phase-sensitive overlap

$$
\boxed{
\operatorname{Re}
\int c_{\rm in}^*S_c^{\rm ext}
=
\int\gamma_c|c_{\rm in}|^2.}
\tag{EC21}
$$

No $q$ dependence is assigned to $L_a$, $R_a$, $V$, or
$\mathsf C_{\rm io}$. The canonical scalar enters only through the existing
local rate

$$
\gamma_c
=
\frac{\varphi^2}{2}\lambda(1-q).
\tag{EC22}
$$

## 8. Frozen Constants and Matrices

The executable uses NumPy complex128 arithmetic and

$$
\varphi:=\frac{1+\sqrt5}{2},
\qquad
\hbar:=1,
\qquad
N:=5,
\qquad
T_\varphi:=\varphi^{-1},
\qquad
\mathrm{tol}:=10^{-11}.
\tag{EC23}
$$

The positive-definite blocks are

$$
A=
\begin{pmatrix}
1.25&0.18-0.06i\\
0.18+0.06i&0.85
\end{pmatrix},
\qquad
B=
\begin{pmatrix}
0.95&-0.11+0.04i\\
-0.11-0.04i&1.15
\end{pmatrix}.
\tag{EC24}
$$

The normalized seed is

$$
K_0=
\begin{pmatrix}
0.22+0.04i&-0.09+0.05i\\
0.07-0.03i&0.18-0.02i
\end{pmatrix},
\tag{EC25}
$$

and

$$
\mathsf C_{\rm io}:=A^{1/2}K_0B^{1/2}.
\tag{EC26}
$$

The independent frame angles are

$$
\alpha:=0.37,
\qquad
\beta:=-0.61.
\tag{EC27}
$$

For charge-ledger and unitary-evolution checks,

$$
H_{\rm in}:=\operatorname{diag}(0.70,-0.20),
\qquad
H_{\rm out}:=\operatorname{diag}(-0.10,0.50),
\qquad
V:=\operatorname{diag}(0.31,0.19),
\qquad
\Delta t:=0.17.
\tag{EC28}
$$

The singular control uses

$$
A_s:=\operatorname{diag}(1,0.8),
\qquad
B_s:=\operatorname{diag}(0.9,0),
\qquad
\mathsf C_s:=
\begin{pmatrix}
0.20&0\\
0.10i&0
\end{pmatrix}.
\tag{EC29}
$$

The unsupported control changes only
$(\mathsf C_s)_{12}$ from $0$ to $0.05$.

For the DG40 witness,

$$
E_Y:=1,
\qquad
E_I:=\varphi^{-1},
\qquad
c_{\rm test}:=0.12+0.07i,
\qquad
\lambda:=0.20,
\qquad
v:=0.30,
\tag{EC30}
$$

The checker evaluates the canonical scalar directly from

$$
\rho_{\rm test}:=E_Y+E_I,
\qquad
\varepsilon_{\rm test}:=E_Y-\varphi E_I,
\qquad
q_{\rm test}
:=
\frac{\rho_{\rm test}^2}
{\rho_{\rm test}^2+\varphi^{-2}+\varepsilon_{\rm test}^2},
$$

and uses $q=q_{\rm test}$ in (EC22).

with

$$
A_{\rm test}:=
\begin{pmatrix}
E_Y&c_{\rm test}^*\\
c_{\rm test}&E_I
\end{pmatrix},
\qquad
B_{\rm test}:=I,
\qquad
V_{\rm test}:=vI.
\tag{EC31}
$$

After computing $q$ and $\gamma_c$ from (EC22), set

$$
\mathsf C_{\rm test}:=
\begin{pmatrix}
0&0\\
-i\gamma_cc_{\rm test}/v&0
\end{pmatrix}.
\tag{EC32}
$$

Equation (EC10) must then give

$$
(S_c^{\rm ext})_{\rm test}=\gamma_cc_{\rm test}
\tag{EC33}
$$

while the same source paired with $ic_{\rm test}$ has zero real support
overlap and with $-c_{\rm test}$ has negative overlap.

## 9. Frozen Gates

### EC1—Positive block and Schur controls

Pass only if:

1. $A$ and $B$ are positive definite;
2. $\|K_0\|_{\rm op}<1$;
3. $\Gamma_{\rm io}$ and its Schur complement are positive within tolerance;
4. the singular supported control satisfies (EC3) and is positive;
5. the unsupported singular control violates its support condition and has a
   negative enlarged-state eigenvalue below $-10^{-6}$.

### EC2—Independent-frame covariance

Pass only if the transformed normalized block, reconstructed cross block,
interior source, and exterior source agree with (EC7) and (EC10) to tolerance
for independent $\alpha$ and $\beta$.

### EC3—Interface ledgers

Pass only if both sources are Hermitian and the total-number and relative-charge
residuals in (EC11) and (EC13) are at most tolerance. The frozen diagonal $V$
must satisfy (EC12).

### EC4—Two-sided attenuation

Pass only if:

1. the closed coherent control preserves $\|K\|_F$ to tolerance;
2. the one-sided routed ratio agrees with $\varphi^{-N/2}$;
3. the symmetric routed ratio agrees with $\varphi^{-N}$;
4. all ratios satisfy (EC17);
5. the forward-plus-return power residual in (EC18) is at most tolerance.

### EC5—Reduced source and support witness

Pass only if:

1. the computed source satisfies (EC19);
2. the witness gives $S_c^{\rm ext}=\gamma_cc_{\rm test}$ to tolerance;
3. the DG40 residual is at most tolerance;
4. the aligned overlap is positive, the quadrature overlap has magnitude at
   most tolerance, and the anti-aligned overlap is negative;
5. $V=0$ and $\mathsf C_{\rm io}=0$ independently give zero interface source.

### EC6—Full conservative evolution

Construct

$$
U_{\Delta t}:=e^{-iH_{\rm io}\Delta t/\hbar},
\qquad
\Gamma_{\rm io}'
:=U_{\Delta t}\Gamma_{\rm io}U_{\Delta t}^\dagger.
\tag{EC34}
$$

Pass only if $U_{\Delta t}$ is unitary, $\Gamma_{\rm io}'$ remains positive,
and trace, total relative charge, and
$\operatorname{tr}(H_{\rm io}\Gamma_{\rm io})$ are preserved to tolerance.

### EC7—Scope controls

Pass only if the implementation declares all of the following false and does
not use them in any gate:

- a $q$–$\mathsf C_{\rm io}$ transfer coupling;
- a selected cosmological-bubble interpretation;
- a geometry-backreaction equation;
- a mixed-stress constitutive map;
- a microscopic reservoir;
- an import from the separate local-$SU(2)_Q$ particle branch.

The absence of those sectors is a scope assertion. It is not evidence against
them.

## 10. Decision Tree and Stopping Rule

The checker prints one line for each gate, followed by `OVERALL: PASS` only when
EC1–EC7 all pass. Any failed gate gives `OVERALL: FAIL` and the checker exits
nonzero.

The first execution after this preregistration is the frozen receipt. No
constant, matrix, tolerance, gate, or interpretation may change after that
execution. A protocol or implementation error requires a new preregistration
and a separately named checker. The checker is not rerun to improve a result.

A PASS establishes only the conditional algebra and deterministic witness in
§9. It does not establish a physical exterior sector, select either routed
attenuation case, derive a reservoir or stress tensor, or demonstrate a
stationary matter solution.

## 11. Output Contract

The checker prints:

```text
CROSS-SCALE COHERENCE INTERFACE RECEIPT
phi=... N=... tolerance=...
EC1: PASS|FAIL—...
EC2: PASS|FAIL—...
EC3: PASS|FAIL—...
EC4: PASS|FAIL—...
EC5: PASS|FAIL—...
EC6: PASS|FAIL—...
EC7: PASS|FAIL—...
OVERALL: PASS|FAIL
```

The report must record the exact first-execution output and distinguish analytic
statements from frozen numerical witnesses.

## References

- `foundations/yin-yang-qi-dynamical-geometry.md`—open matrix balance and
  finite-density support budget.
- `foundations/geometric-manifold-completion.md`—positive coherence fibre,
  conservative graph action, and exact canonical reduction.
- `foundations/endpoint-link-and-localization-boundary.md`—Wilson covariance
  and endpoint ledgers.
- `foundations/interscale-stress-attenuation-boundary.md`—coherent/routed
  propagation boundary and attenuation ledgers.
- `foundations/cascade-suppression-formula.md`—conditional attenuation
  families.
- `foundations/physical-becoming-hierarchy.md`—conditional Markov bath and
  reservoir boundary.
