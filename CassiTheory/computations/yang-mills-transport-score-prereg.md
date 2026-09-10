# Yang–Mills Conditional Transport-Score Recurrence Preregistration

## Status: Frozen protocol v2—September 2026

## 1. Question and scope

Can the transported-score term in the exact two-scale vacuum-measure recurrence be controlled in a weaker norm that retains vertical cancellations and yields a scale-resolved physical-margin criterion?

The starting point is `foundations/loop-to-bubble-projection-theorem.md` §9.20. For an exact factor-two path block, the fine electric form is

\[
\Gamma_f(F)=2|\nabla_HF|^2+\frac12|\nabla_VF|^2,
\]

and the exact vacuum disintegrates as

\[
d\mu_f=d\bar\mu(V)\,d\nu_V(R).
\]

The existing recurrence uses the conditional fibre rate \(\lambda_{\mathrm{fib}}\), coarse rate \(\lambda_c\), and an \(L^2(\nu_V)\) covariance bound \(\kappa\) for the transported score. This protocol replaces the Cauchy–Schwarz estimate on the score by its exact conditional \(H^{-1}\) norm. It does not assume a microscopic Cassi identification, a Yang–Mills vacuum formula, a volume-uniform estimate, or a continuum measure.

## 2. Frozen analytical obligations

### YMTS1. Conditional Poisson and transport norm

For each coarse configuration \(V\), let \(\mathcal L_V\) be the nonnegative Friedrichs operator associated with the vertical Dirichlet form

\[
\langle u,\mathcal L_Vv\rangle_{\nu_V}
=
\mathbb E_{\nu_V}\langle\nabla_Vu,\nabla_Vv\rangle.
\]

For a unit coarse tangent vector \(\xi\), write

\[
s_{V,\xi}=\langle s_V,\xi\rangle,
\qquad
\mathbb E_{\nu_V}s_{V,\xi}=0.
\]

Define

\[
\vartheta^2
:=
\mathop{\mathrm{ess\,sup}}_V
\sup_{|\xi|=1}
\langle s_{V,\xi},\mathcal L_V^{-1}s_{V,\xi}\rangle_{\nu_V}.
\]

The inverse is on the centered form domain. The theorem must derive both equivalent descriptions

\[
\|s_{V,\xi}\|_{H^{-1}(\nu_V)}^2
=
\sup_f
\frac{\bigl(\mathbb E_{\nu_V}[(f-\mathbb E_{\nu_V}f)s_{V,\xi}]\bigr)^2}
{\mathbb E_{\nu_V}|\nabla_Vf|^2}
\]

and

\[
\|s_{V,\xi}\|_{H^{-1}(\nu_V)}^2
=
\inf_{u:\,-\operatorname{div}_{\nu_V}u=s_{V,\xi}}
\mathbb E_{\nu_V}|u|^2.
\]

The minimizing field is \(u=\nabla_V\mathcal L_V^{-1}s_{V,\xi}\). The second formula interprets \(\vartheta\) as the minimum vertical kinetic cost needed to transport the conditional law when the coarse variable moves.

### YMTS2. Sharpened recurrence

The transported differentiated-expectation identity must give

\[
\left\|
\mathbb E_{\nu_V}
\left[(F-\mathbb E_{\nu_V}F)s_V\right]
\right\|_{L^2(\bar\mu)}
\le
\vartheta
\left(\mathbb E_{\mu_f}|\nabla_VF|^2\right)^{1/2}.
\]

With

\[
X^2=\mathbb E_{\mu_f}|\nabla_HF|^2,
\qquad
Y^2=\mathbb E_{\mu_f}|\nabla_VF|^2,
\]

total variance must then yield

\[
\operatorname{Var}_{\mu_f}F
\le
\frac{Y^2}{\lambda_{\mathrm{fib}}}
+
\frac1{\lambda_c}(X+\vartheta Y)^2.
\]

Against \(2X^2+Y^2/2\), define

\[
A=\frac1{2\lambda_c},
\qquad
B=\frac{\vartheta}{\lambda_c},
\qquad
D=2\left(\frac1{\lambda_{\mathrm{fib}}}
+\frac{\vartheta^2}{\lambda_c}\right),
\]

\[
C_{-1}
=
\frac12\left[A+D+\sqrt{(A-D)^2+4B^2}\right].
\]

The required all-function conclusion is

\[
\boxed{\lambda_f\ge C_{-1}^{-1}.}
\]

If the existing score covariance obeys

\[
\mathbb E_{\nu_V}s_{V,\xi}^2\le\kappa^2|\xi|^2,
\]

the fibre Poincaré inequality must imply

\[
\boxed{\vartheta^2\le\frac{\kappa^2}{\lambda_{\mathrm{fib}}}.}
\]

Thus the new recurrence is no weaker than the covariance recurrence in §9.20. Strict improvement requires score components whose conditional \(H^{-1}\) norm is smaller than the spectral-gap relaxation of their \(L^2\) norm.

### YMTS3. Exact physical-margin transfer

For the physical target

\[
r_f=\frac{2a_fm_*}{g_f^2},
\qquad
r_c=\frac{r_f}{2},
\]

and a desired fine relative margin \(\delta_f\ge0\), define

\[
h=\frac{r_f}{2\lambda_c}=\frac{r_c}{\lambda_c},
\qquad
v=\frac{2r_f}{\lambda_{\mathrm{fib}}},
\qquad
t_f=\frac1{1+\delta_f}.
\]

The normalized recurrence matrix is

\[
r_f
\begin{pmatrix}A&B\\B&D\end{pmatrix}
=
\begin{pmatrix}
h&2h\vartheta\\
2h\vartheta&v+4h\vartheta^2
\end{pmatrix}.
\]

The recurrence certifies

\[
\lambda_f\ge(1+\delta_f)r_f
\]

if and only if

\[
\boxed{
h\le t_f,
\qquad
v\le t_f,
\qquad
\vartheta^2
\le
\frac{(t_f-h)(t_f-v)}{4ht_f}.
}
\]

For

\[
\delta_c=\frac{\lambda_c}{r_c}-1,
\qquad
\delta_v=\frac{\lambda_{\mathrm{fib}}}{2r_f}-1,
\]

the same conditions must reduce to

\[
\boxed{
\delta_c\ge\delta_f,
\qquad
\delta_v\ge\delta_f,
\qquad
\vartheta^2
\le
\frac{(\delta_c-\delta_f)(\delta_v-\delta_f)}
{4(1+\delta_f)(1+\delta_v)}.
}
\]

A nonzero transport score consumes both coarse and vertical margin. Equality of either input margin with the requested output margin leaves zero score budget.

### YMTS4. Exact Gaussian transport control

For a positive block precision

\[
Q=
\begin{pmatrix}
Q_{VV}&Q_{VR}\\
Q_{RV}&Q_{RR}
\end{pmatrix},
\qquad
d\mu(v,r)\propto e^{-(v,r)^TQ(v,r)}\,dv\,dr,
\]

define

\[
T=-Q_{RR}^{-1}Q_{RV},
\qquad
Q_{\mathrm{eff}}
=Q_{VV}-Q_{VR}Q_{RR}^{-1}Q_{RV}.
\]

The conditional law has mean \(Tv\) and precision \(Q_{RR}\). The exact quantities to derive are

\[
\lambda_c=2\lambda_{\min}(Q_{\mathrm{eff}}),
\qquad
\lambda_{\mathrm{fib}}=2\lambda_{\min}(Q_{RR}),
\qquad
\vartheta^2=\|T\|_{\mathrm{op}}^2,
\]

\[
\kappa^2
=2\|Q_{VR}Q_{RR}^{-1}Q_{RV}\|_{\mathrm{op}},
\qquad
\vartheta^2\le\frac{\kappa^2}{\lambda_{\mathrm{fib}}}.
\]

For the anisotropic form with

\[
G=\operatorname{diag}(2I_V,I_R/2),
\]

the exact Gaussian Poincaré rate is

\[
\lambda_{\mathrm{exact}}
=2\lambda_{\min}(G^{1/2}QG^{1/2}).
\]

Both conditional recurrences must remain below this exact rate, and the \(H^{-1}\) recurrence must be no weaker than the \(L^2\)-score recurrence.

Use two fixed three-dimensional controls. The equality control is

\[
Q^{(=)}=
\begin{pmatrix}
2&-1&0\\
-1&2&0\\
0&0&2
\end{pmatrix},
\]

with the first coordinate coarse. It has
\(\vartheta^2=\kappa^2/\lambda_{\mathrm{fib}}=1/4\).
The strict control is

\[
Q^{(<)}=
\begin{pmatrix}
4&0&-3\\
0&1&0\\
-3&0&9
\end{pmatrix},
\]

again with the first coordinate coarse. It has
\(\vartheta^2=1/9\),
\(\kappa^2/\lambda_{\mathrm{fib}}=1\), and strict improvement factor nine in the squared score coefficient.

### YMTS5. Weak-field chain diagnostic

For even \(N\in\{4,8,16,32,64\}\) and
\(m\in\{0,1/2\}\), use

\[
D_N(m)=\operatorname{tridiag}(-1,2+m^2,-1),
\qquad
Q_N(m)=\sqrt{D_N(m)},
\]

with even zero-based coordinates coarse and odd coordinates fibre. These are Gaussian controls and are not an interacting Yang–Mills vacuum.

For the infinite translation-invariant chain, fix

\[
q_m(k)=\sqrt{m^2+4\sin^2(k/2)},
\]

\[
a_m(K)=\frac{q_m(K/2)+q_m(K/2+\pi)}2,
\qquad
|b_m(K)|=\frac{|q_m(K/2)-q_m(K/2+\pi)|}{2}.
\]

The fibre and transport limits are

\[
\lambda_{\mathrm{fib},\infty}=2\inf_Ka_m(K),
\qquad
\vartheta_\infty=\sup_K\frac{|b_m(K)|}{a_m(K)},
\]

and the coarse Schur symbol is

\[
q_{\mathrm{eff},m}(K)
=a_m(K)-\frac{|b_m(K)|^2}{a_m(K)}
=\frac{q_m(K/2)q_m(K/2+\pi)}{a_m(K)}.
\]

At \(m=0\), the required closed values are

\[
\lambda_{\mathrm{fib},\infty}=2,
\qquad
\vartheta_\infty=1,
\qquad
q_{\mathrm{eff},0}(0)=0.
\]

For \(m>0\), writing \(s_m=\sqrt{m^2+4}\), the required endpoint values are

\[
\lambda_{\mathrm{fib},\infty}=m+s_m,
\qquad
\vartheta_\infty=\frac{s_m-m}{s_m+m},
\qquad
q_{\mathrm{eff},m}(0)=\frac{2ms_m}{m+s_m}>0.
\]

The massless control therefore retains a positive fibre rate and bounded transport norm while its coarse rate vanishes. It is a free Gaussian infrared diagnostic, not evidence for a non-Abelian mass gap.

## 3. Fixed computational schedule

Two implementations are required:

1. `computations/verify_yang_mills_transport_score.py` is the primary NumPy verifier.
2. `computations/verify_yang_mills_transport_score_independent.mjs` reconstructs the schedule in JavaScript without importing the Python source or consuming its generated matrices.

The primary schedule contains:

- exactly 10 finite-chain rows: the Cartesian product of the five fixed even sizes and two fixed masses in YMTS5;
- exactly 2 three-dimensional Gaussian fixture rows from YMTS4;
- exactly 10 margin rows
  \[
  (\delta_c,\delta_v,\delta_f,\vartheta^2)\in
  \left\{
  \begin{array}{l}
  (0,0,0,0),\ (0,1,0,0),\ (0,1,0,10^{-6}),\\
  (1,3,0,3/16),\ (1,3,0,0.19),\\
  (2,4,1/2,0.175),\ (2,4,1/2,0.18),\\
  (1/2,3,1,0),\ (3,1/2,1,0),\ (3,10,1,0.1)
  \end{array}
  \right\};
  \]
- exactly 2 infinite-symbol rows, at \(m=0\) and \(m=1/2\), evaluated on the fixed 17-point grid \(K_j=-\pi+j\pi/8\), \(j=0,\ldots,16\), plus the analytic endpoint formulas.

The primary has exactly 86 checks:

- five checks for each finite-chain row: square-root reconstruction, Schur/block-inverse identity, transport-score identities, recurrence ordering, and comparison with the exact anisotropic Gaussian gap;
- four checks for each Gaussian fixture: expected \(\vartheta^2\), expected \(\kappa^2/\lambda_{\mathrm{fib}}\), expected comparison factor, and recurrence/exact-gap ordering;
- two checks for each margin row: direct largest-eigenvalue reconstruction and equivalence of the matrix and closed margin decisions;
- four checks for each infinite-symbol row: fibre endpoint, transport endpoint, coarse endpoint, and the symbol determinant identity on the fixed grid.

The independent verifier has exactly 32 checks:

- eight protocol, source, tolerance, primary-check and row-integrity controls;
- one complete reconstruction check for each of the 10 chain rows;
- one complete reconstruction check for each of the 2 Gaussian fixtures;
- one complete reconstruction check for each of the 10 margin rows;
- one complete reconstruction check for each of the 2 symbol rows.

The primary constructs \(Q_N\) by symmetric eigendecomposition. The independent implementation constructs it from the explicit discrete-sine eigenvectors and uses its own symmetric Jacobi eigensolver and pivoted Gaussian elimination. Neither implementation reads `runs/yang_mills_vacuum_blocks/verification.json`.

For matrices, the normalized error is
\[
\operatorname{err}_{\mathrm{mat}}(A,B)
=\frac{\|A-B\|_{\mathrm{op}}}{\max\{1,\|B\|_{\mathrm{op}}\}}.
\]
For scalars, it is
\[
\operatorname{err}_{\mathrm{sc}}(a,b)
=\frac{|a-b|}{\max\{1,|b|\}}.
\]
The primary matrix tolerance is \(10^{-10}\), its scalar algebraic tolerance is \(10^{-11}\), and the independent comparison tolerance for both normalized errors is \(10^{-9}\). Each aggregate row check passes only when every identity or inequality named for that check passes. No tolerance, row, matrix, mass, margin, or momentum-grid value may change after execution.

The primary receipt is

`runs/yang_mills_transport_score/verification.json`.

The independent receipt is

`runs/yang_mills_transport_score/verification-independent.json`.

Both receipts must bind the protocol and their own sources by SHA-256. The independent receipt must also bind the primary source and primary receipt, assert the fixed tolerances and exact row/check counts, and reject any failed or duplicate primary check.

## 4. Decision rule

- **PASS:** all 86 primary and 32 independent checks pass at the frozen tolerances.
- **FAIL:** an analytical formula, fixed expected fixture value, margin decision, Gaussian ordering, source identity, count, or numerical reconstruction disagrees.
- **INCONCLUSIVE:** execution or a required evidence identity is absent.

A PASS supports the implementation and the fixed Gaussian controls. Analytical adoption of YMTS1–YMTS5 additionally requires a direct proof and independent review. No finite row proves a volume-uniform Yang–Mills estimate.

## 5. Stopping rule

Run the primary once after the protocol, both implementations and analytical review are complete. Run the independent verifier once against that primary receipt. Preserve any failure and do not alter the frozen schedule or tolerances without a new protocol version.

## 6. Sources fixed before execution

- `foundations/loop-to-bubble-projection-theorem.md` §§9.13–9.16, 9.20—exact vacuum transform, Gaussian controls and conditional-score recurrence.
- `computations/yang-mills-vacuum-block-prereg.md` §§1, 4—exact finite-vacuum and Gaussian block obligations.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*: https://www.claymath.org/wp-content/uploads/2022/06/yangmills.pdf
- D. Bakry, I. Gentil and M. Ledoux, *Analysis and Geometry of Markov Diffusion Operators*—Poincaré, Poisson and carré-du-champ framework.
- C. Villani, *Optimal Transport: Old and New*—continuity-equation and minimum-kinetic-energy characterization of tangent transport.
