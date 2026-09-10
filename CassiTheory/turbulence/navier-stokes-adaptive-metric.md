# Adaptive Positive Metrics for Navier–Stokes Vortex Stretching

## Status: Derived conditional—September 2026

## Abstract

A positive time-dependent metric can cancel three-dimensional Navier–Stokes vortex stretching exactly. The cancellation is available as a scalar integrating factor, a material branch metric, a terminal adjoint metric, and a forward-parabolic projected metric. The forward construction preserves positive definiteness and gives an exact nonincreasing weighted enstrophy. Its unscaled determinant satisfies a favorable minimum-principle inequality.

The same calculation isolates the remaining theorem obligation. Exact cancellation transfers amplification into metric distortion. A volume-preserving extensional control keeps determinant one while its expanding-state metric weight tends to zero. The implemented CassiFI covariance law has the same boundary: its spectral bounds require a declared observation-amplitude bound, while an unbounded stretching coordinate either drives the covariance condition number to infinity or leaves the omitted physical scale uncontrolled. Smooth periodic shear and Beltrami heat flows remain benign, so the metric does not assign concentration danger merely from large frequency or covariance.

For the forward metric, the weakest direct continuation target is a data-controlled upper bound on the ratio of Euclidean enstrophy to active weighted enstrophy. Such a bound would continue every smooth periodic solution. No estimate of that ratio from only viscosity, finite time, and the initial $H^3$ norm is derived here. The construction supplies an exact solutionwise distortion diagnostic and a concrete sufficient proof target; arbitrary-data global regularity remains **UNRESOLVED**.

## 1. Scope and conventions

Work on the normalized three-torus with a sufficiently regular mean-zero solution of

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad \nu>0.
\tag{1}
$$

Write

$$
\omega=\nabla\times u,
\qquad
A=\nabla u,
\qquad
S=\frac12(A+A^{\mathsf T}),
\qquad
D_t=\partial_t+u\cdot\nabla.
\tag{2}
$$

Then

$$
D_t\omega=A\omega+\nu\Delta\omega.
\tag{3}
$$

Define the volume-normalized enstrophy, palinstrophy, and vortex-stretching production

$$
W=\int|\omega|^2dx,
\qquad
D=\int|\nabla\omega|^2dx,
\qquad
P=\int\omega^{\mathsf T}S\omega\,dx.
\tag{4}
$$

Their standard balance is

$$
\frac12W'+\nu D=P.
\tag{5}
$$

The analysis concerns the original unforced equation. Every metric below is an auxiliary functional of an already smooth Navier–Stokes solution. Its existence through a smooth interval does not by itself continue that solution.

The Cassi connection is specific. CassiFI uses positive covariance and precision geometry to couple memory and inference through one potential. That geometry motivates the adaptive metric calculation. The canonical Cassi two-fluid scalar $q$ measures density and composition rather than vorticity-direction geometry, so no identification of $q$ with the metric in this paper is made.

## 2. General positive-metric balance

Let $G(x,t)=G(x,t)^{\mathsf T}\succ0$ be a smooth matrix field and set

$$
\mathcal E_G(t)=\frac12\int\omega^{\mathsf T}G\omega\,dx,
\qquad
\mathcal D_G(t)=\sum_k\int
(\partial_k\omega)^{\mathsf T}G(\partial_k\omega)\,dx.
\tag{6}
$$

Periodic integration by parts gives

$$
\int\omega^{\mathsf T}G\Delta\omega\,dx
=-\mathcal D_G
+\frac12\int\omega^{\mathsf T}(\Delta G)\omega\,dx.
\tag{7}
$$

Consequently

$$
\boxed{
\mathcal E_G'+\nu\mathcal D_G
=\frac12\int\omega^{\mathsf T}\mathcal R_G\omega\,dx,}
\tag{8}
$$

where

$$
\mathcal R_G
=D_tG+A^{\mathsf T}G+GA+\nu\Delta G.
\tag{9}
$$

Equation (8) is the central identity. Material deformation enters through $A^{\mathsf T}G+GA$, spatial variation of the metric enters through $\nu\Delta G$, and all selected metric dynamics enter through $D_tG$.

A pointwise lower bound $G\succeq mI$ gives

$$
\mathcal E_G\ge\frac m2W,
\qquad
\mathcal D_G\ge mD.
\tag{10}
$$

Exact cancellation of the right side of (8) is useful only while a data-controlled relation between $\mathcal E_G$ and $W$ survives. Sections 3–9 make that requirement explicit.

## 3. Scalar adaptive metric

Take $G=a_s(t)I$ with $a_s(0)=1$. Equation (8) becomes

$$
\frac12(a_sW)'+\nu a_sD=a_sP+\frac12a_s'W.
\tag{11}
$$

Whenever $W>0$, choose

$$
\frac{a_s'}{a_s}=-2\frac PW.
\tag{12}
$$

Then

$$
\boxed{
\frac12(a_sW)'+\nu a_sD=0,}
\tag{13}
$$

and

$$
a_s(t)=
\exp\left[-2\int_0^t\frac{P(s)}{W(s)}ds\right]>0.
\tag{14}
$$

Dividing (5) by $W$ yields the exact signed-production identity

$$
\int_0^t\frac PWds
=\frac12\log\frac{W(t)}{W(0)}
+\nu\int_0^t\frac DWds.
\tag{15}
$$

Bounds on $a_s$ control this signed integral on each time interval, but not its positive part: intervals of negative normalized production can cancel positive normalized production. The scalar cancellation changes the coordinate used to record production and supplies no independent estimate of (14).

A smooth periodic datum demonstrates the immediate response. For

$$
 u_*=
\bigl(
\cos y+\sin(x+y),
\cos x-\sin(x+y),
\cos x+\cos y+\sin(x+y)
\bigr),
\tag{16}
$$

one has

$$
\nabla\cdot u_*=0,
\qquad
W(0)=5,
\qquad
P(0)=\frac12,
\qquad
\frac{a_s'(0)}{a_s(0)}=-\frac15.
\tag{17}
$$

The scalar metric begins losing coercivity along an admissible positive-production trajectory.

## 4. Branch metrics and the finite-dimensional obstruction

The local stretching subsystem has the form

$$
z'=Lz.
\tag{18}
$$

A symmetric positive branch metric $M$ gives

$$
\frac d{dt}(z^{\mathsf T}Mz)
=z^{\mathsf T}(M'+L^{\mathsf T}M+ML)z.
\tag{19}
$$

Exact cancellation follows from the Lyapunov equation

$$
M'=-L^{\mathsf T}M-ML.
\tag{20}
$$

For the trace-free extensional generator

$$
L_a=\operatorname{diag}(a,-a,0),
\qquad a>0,
\tag{21}
$$

and $M(0)=I$,

$$
M_a(t)=\operatorname{diag}(e^{-2at},e^{2at},1),
\qquad
\det M_a=1.
\tag{22}
$$

The expanding state $z=e^{at}e_1$ has constant weighted energy and exponentially growing Euclidean norm:

$$
z^{\mathsf T}M_az=1,
\qquad
|z|^2=e^{2at},
\qquad
\lambda_{\min}(M_a)=e^{-2at}.
\tag{23}
$$

This conclusion does not require a diagonal ansatz. If any positive $M(t)$ keeps the weighted energy of $e^{at}e_1$ equal to its initial value, then

$$
e^{2at}e_1^{\mathsf T}M(t)e_1=e_1^{\mathsf T}M(0)e_1,
\tag{24}
$$

so its quadratic weight in the active direction must decay as $e^{-2at}$.

A fixed positive symmetrizer cannot cancel every trace-free strain. For $M\succ0$ and $L_a$ above,

$$
e_1^{\mathsf T}(L_a^{\mathsf T}M+ML_a)e_1=2aM_{11}>0.
\tag{25}
$$

An augmented nonnegative metric penalty has the same boundary. If a total functional $V(z,M)$ satisfies $V\ge m|z|^2$ for one fixed $m>0$ and is nonincreasing for every extensional trajectory, then (23) gives the contradiction $me^{2at}\le V(0)$. Exact algebraic cancellation of arbitrary stretching therefore forces either metric degeneration, retained positive production, or external control of the admissible strain history.

The affine velocity generating (21) lies outside the periodic and finite-energy Euclidean data classes. It is a local algebraic control. The original Navier–Stokes equation may constrain persistent extension in ways absent from (18); proving such a constraint is the PDE task.

## 5. CassiFI covariance adaptation

The implemented CassiFI variational field assigns an SPD covariance $\Sigma$ and precision $\Sigma^{-1}$ to each factor. Its fixed-observation potential is

$$
F(\Sigma,z)=\frac12
\left[
\log\det\frac{\Sigma}{\lambda I}
+\lambda\operatorname{tr}\Sigma^{-1}
-k+z^{\mathsf T}\Sigma^{-1}z
\right].
\tag{26}
$$

For a fixed observed vector $x$, the covariance update is

$$
\Sigma'=xx^{\mathsf T}+\lambda I-\Sigma.
\tag{27}
$$

The implementation declares an observation bound $\|x\|\le B$. Starting from

$$
\lambda I\preceq\Sigma(0)\preceq(\lambda+B^2)I,
\tag{28}
$$

(27) preserves the same spectral bounds. This is a valid finite-dimensional coercivity theorem for the declared input domain.

A formal expanding observation isolates the regularity boundary. Let

$$
x(t)=e^{at}e_1,
\qquad
\Sigma(0)=\lambda I.
\tag{29}
$$

Then

$$
\Sigma(t)=
\operatorname{diag}
\left(
\lambda+\frac{e^{2at}-e^{-t}}{2a+1},
\lambda,
\lambda
\right).
\tag{30}
$$

The precision-weighted live amplitude remains finite,

$$
 x^{\mathsf T}\Sigma^{-1}x\longrightarrow2a+1,
\tag{31}
$$

while

$$
\lambda_{\min}(\Sigma^{-1})\longrightarrow0,
\qquad
\operatorname{cond}\Sigma\longrightarrow\infty.
\tag{32}
$$

Normalizing $x=e^{at}y$ with $y=e_1$ keeps the learned covariance bounded, but the omitted scale $e^{at}$ remains unbounded. The implemented field instead rejects observations beyond $B$. Choosing $B$ as a prospective vorticity bound would assume the conclusion needed for regularity.

The potential (26) also records a log-determinant cost, and the source implementation states that changing observed coordinates supplies boundary work before fixed-observation descent. A Navier–Stokes trajectory continually changes the proposed observation. Covariance descent at frozen input therefore supplies no monotonicity theorem for the combined fluid-plus-metric trajectory.

This comparison identifies a useful role for CassiFI geometry: it can learn anisotropy and retain a well-conditioned metric on a genuinely bounded domain. The arbitrary-amplitude bound must come from the fluid equation rather than from covariance adaptation.

## 6. Spatial metric curvature

A spatially varying metric introduces the curvature term in (7). Its sign has no general positivity. In one periodic coordinate, use the divergence-free field

$$
\omega(x)=(0,\sin x,0),
\qquad
G_\pm(x)=\operatorname{diag}
\left(2,2\pm\epsilon\cos2x,2\right),
\qquad 0<\epsilon<2.
\tag{33}
$$

Both matrix fields are positive, but

$$
\frac12\int\omega^{\mathsf T}\Delta G_+\,\omega\,dx
=\frac\epsilon2,
\qquad
\frac12\int\omega^{\mathsf T}\Delta G_-\,\omega\,dx
=-\frac\epsilon2.
\tag{34}
$$

Spatial positivity of $G$ does not determine the sign of
$\int\omega^{\mathsf T}\Delta G\,\omega$. A material cancellation law which omits $\nu\Delta G$ leaves this term behind. The full adjoint law in the next section removes it exactly.

## 7. Terminal adjoint metric

Fix a smooth solution on $[0,T]$ and solve the terminal-value problem

$$
D_tG_T+A^{\mathsf T}G_T+G_TA+\nu\Delta G_T=0,
\qquad
G_T(x,T)=I.
\tag{35}
$$

Equation (8) gives

$$
\frac12W(T)
+\nu\int_0^T\mathcal D_{G_T}(t)dt
=\frac12\int\omega_0^{\mathsf T}G_T(x,0)\omega_0dx.
\tag{36}
$$

This is an exact endpoint representation. A regularity estimate would require an initial operator bound for the terminal metric depending only on the prescribed data class.

The extensional control (21) gives

$$
G_T(t)=
\operatorname{diag}
\left(
e^{2a(T-t)},e^{-2a(T-t)},1
\right),
\tag{37}
$$

and hence

$$
\|G_T(0)\|_{\mathrm{op}}=e^{2aT}.
\tag{38}
$$

The terminal construction moves amplification into the initial adjoint norm. Solving (35) backward from $T$ is parabolic in reverse-time coordinates; evolving the same equation from initial data would have the anti-diffusive sign. The terminal identity is exact, while the required data-controlled propagator estimate remains open.

## 8. Forward-parabolic projected metric

A forward construction avoids the terminal problem. Let $H$ solve

$$
D_tH+A^{\mathsf T}H+HA-\nu\Delta H=0,
\qquad H(x,0)=I.
\tag{39}
$$

This system preserves symmetry and positive definiteness through every smooth interval. At a first zero eigenvalue, the congruence reaction vanishes in its null direction and the forward diffusion satisfies the matrix minimum-principle sign.

Define

$$
Z_H=\int\omega^{\mathsf T}H\omega\,dx,
\qquad
J_H=\int\omega^{\mathsf T}\Delta H\,\omega\,dx,
\qquad
c_H=\frac{J_H}{Z_H},
\tag{40}
$$

for a nonzero-vorticity solution, and let

$$
\frac{\beta'}{\beta}=-2\nu c_H,
\qquad
\beta(0)=1,
\qquad
G=\beta H.
\tag{41}
$$

Then $\beta>0$ and

$$
D_tG+A^{\mathsf T}G+GA-\nu\Delta G+2\nu c_HG=0.
\tag{42}
$$

Its defect in (9) is

$$
\mathcal R_G=2\nu(\Delta G-c_HG).
\tag{43}
$$

Because $\Delta G=\beta\Delta H$,

$$
\int\omega^{\mathsf T}\mathcal R_G\omega\,dx
=2\nu\beta(J_H-c_HZ_H)=0.
\tag{44}
$$

Thus the forward metric obeys the exact law

$$
\boxed{
Z_G(t)+2\nu\int_0^t\mathcal D_G(s)ds=W(0),
\qquad
Z_G(t):=\int\omega^{\mathsf T}G\omega\,dx.}
\tag{45}
$$

### 8.1 Determinant inequality

The unscaled metric $H$ has

$$
(D_t-\nu\Delta)\log\det H
=\nu\sum_k
\operatorname{tr}
\left[(H^{-1}\partial_kH)^2\right]
\ge0.
\tag{46}
$$

Incompressibility removes the reaction trace. Each term on the right is the trace of the square of a matrix similar to the symmetric matrix
$H^{-1/2}(\partial_kH)H^{-1/2}$. Since $H(0)=I$, the periodic minimum principle gives

$$
\det H(x,t)\ge1.
\tag{47}
$$

If $0<\lambda_1\le\lambda_2\le\lambda_3$ are the eigenvalues of $H$, then

$$
\lambda_1
=\frac{\det H}{\lambda_2\lambda_3}
\ge\frac{4\det H}{(\operatorname{tr}H)^2}
\ge\frac4{(\operatorname{tr}H)^2}.
\tag{48}
$$

A data-controlled upper bound on $\operatorname{tr}H$ and lower bound on $\beta$ would therefore imply full coercivity of $G$. The trace satisfies

$$
(D_t-\nu\Delta)\operatorname{tr}H=-2\operatorname{tr}(HS).
\tag{49}
$$

The immediate maximum-principle estimate depends on
$\int_0^T\|S(t)\|_\infty dt$, a standard continuation-level quantity. Equation (47) alone permits the determinant-one degeneration in (22).

### 8.2 Active metric distortion

Full pointwise coercivity is stronger than the weighted energy requires. Define the active distortion

$$
\mathfrak A_G(t)=
\frac{W(t)}{Z_G(t)}
\tag{50}
$$

for $W(t)>0$, with $\mathfrak A_G=1$ for the zero solution. Equation (45) gives

$$
W(t)\le\mathfrak A_G(t)W(0).
\tag{51}
$$

The metric may lose an eigenvalue in a direction orthogonal to vorticity without increasing $\mathfrak A_G$. The exact periodic shear in §9.2 illustrates this distinction.

## 9. Exact controls

### 9.1 Extensional and periodic local-strain controls

Under the spatially homogeneous algebraic specialization $A=L_a$, the forward law (39) reduces to (20), so $H=M_a$, $J_H=c_H=0$, and $G=H$. For the expanding state in (23), define the corresponding finite-dimensional directional distortion by

$$
\mathfrak a_{M_a}^{\mathrm{loc}}(t)
:=\frac{|z(t)|^2}{z(t)^{\mathsf T}M_a(t)z(t)}
=e^{2at}.
\tag{52}
$$

This is a local finite-dimensional algebraic obstruction, not a Navier–Stokes trajectory or the vorticity-weighted ratio (50). The affine field with gradient (21) is curl-free, nonperiodic, and has infinite Euclidean energy, while the selected state is independent of that curl. The control therefore refutes coercivity inferred from metric positivity, determinant, or unrestricted strain-history algebra alone; it does not refute an estimate exploiting the coupled Navier–Stokes dynamics.

An admissible periodic datum produces the same initial direction without asserting persistent affine strain. Let

$$
u_c=(\sin y,\sin z,\sin x).
\tag{53}
$$

At the origin,

$$
S_c(0)=\frac12
\begin{pmatrix}
0&1&1\\
1&0&1\\
1&1&0
\end{pmatrix},
\qquad
\operatorname{spec}S_c(0)=\left\{1,-\frac12,-\frac12\right\}.
\tag{54}
$$

Since $H(0)=I$ is spatially constant,

$$
\partial_tH(0,0)=-2S_c(0),
\qquad
\operatorname{spec}\partial_tH(0,0)=\{-2,1,1\}.
\tag{55}
$$

The least metric eigenvalue starts decreasing along a smooth periodic strain direction. The later Navier–Stokes evolution determines whether this decrease persists.

### 9.2 Periodic shear heat flow

For

$$
 u=a e^{-\nu n^2t}(\sin ny,0,0),
\qquad a\in\mathbb R,\quad n\in\mathbb Z\setminus\{0\},
\tag{56}
$$

vorticity is parallel to $e_3$ and

$$
A\omega=S\omega=0.
\tag{57}
$$

In (39), the subspace

$$
H_{13}=H_{23}=0,
\qquad H_{33}=1
\tag{58}
$$

is invariant from $H(0)=I$. Therefore $J_H=0$, $c_H=0$, and

$$
Z_G=W,
\qquad
\mathfrak A_G=1.
\tag{59}
$$

The metric leaves the active vorticity direction unchanged even though its orthogonal block can adapt to shear. High frequency in this globally smooth family causes no false concentration signal.

### 9.3 Periodic Beltrami heat flow

For

$$
 u=a e^{-\nu n^2t}(\sin nz,\cos nz,0),
\qquad a\in\mathbb R,\quad n\in\mathbb Z\setminus\{0\},
\tag{60}
$$

one has

$$
\omega=nu,
\qquad
(u\cdot\nabla)u=0,
\qquad
S\omega=0.
\tag{61}
$$

Hence $P=0$ and the scalar metric in §3 remains $a_s=1$. This exact smooth family separates large vorticity or frequency from positive vortex stretching.

### 9.4 Nonlinear invariant shear mixing

The exact class

$$
 u=(Ae^{-\nu t}\sin y,0,bv(x,y,t)),
\qquad
v_t+Ae^{-\nu t}\sin y\,v_x=\nu\Delta v
\tag{62}
$$

is a three-component, two-coordinate unforced Navier–Stokes family. Its Sobolev norms have finite bounds with factors of the form
$\exp(C_m|A|/\nu)$, and its critical transfer has a finite initial-data-controlled bound. This family permits substantial transient mixing while remaining globally smooth. It shows that a valid metric estimate may be large and strongly dependent on the prescribed data while still meeting the all-data requirement.

## 10. Continuation theorem obligation

The forward metric produces the following exact conditional result.

**Proposition 1.** Fix $\nu>0$, finite $T>0$, and $R\ge0$. Suppose every smooth mean-zero periodic datum with

$$
\|u_0\|_{H^3}\le R
\tag{63}
$$

generates the metric (39)–(41) and satisfies

$$
\boxed{
\sup_{0\le t<\min(T,T_*)}
\mathfrak A_G(t)
\le C_G(\nu,T,R)<\infty.}
\tag{64}
$$

Then every such solution continues through $T$.

**Proof.** Equations (45), (50), and (64) give

$$
\sup_{t<\min(T,T_*)}W(t)
\le C_G(\nu,T,R)W(0)<\infty.
\tag{65}
$$

On the mean-zero periodic divergence-free subspace, the Fourier curl identity and Poincaré inequality bound $\|u(t)\|_{H^1}$ by $W(t)^{1/2}$. The standard local $H^1$ restart therefore extends the strong solution at a finite endpoint. $\square$

A pointwise lower bound $G\succeq C_G^{-1}I$ implies (64), but (64) only controls the metric in the actual vorticity distribution. It is the weakest direct obligation furnished by (45).

Conversely, finite-time loss of regularity forces active metric degeneration. A maximal strong solution approaching a finite endpoint must have unbounded enstrophy. Since (45) gives $Z_G(t)\le W(0)$, there is then a sequence $t_j\uparrow T_*$ with

$$
\mathfrak A_G(t_j)\longrightarrow\infty.
\tag{66}
$$

The metric construction therefore converts finite-time breakdown along each smooth solution into a precise distortion question. It resolves the arbitrary-data problem only if a uniform estimate such as (64) follows from the original equation with the displayed dependence.

For a generic matrix parabolic equation, the basic kinetic-energy estimate supplies

$$
A=\nabla u\in L^2_tL^2_x.
\tag{67}
$$

A potential with Navier–Stokes scaling is parabolically critical at

$$
\frac2p+\frac3q=2.
\tag{68}
$$
The exponent relation is the formal Euclidean or simultaneously rescaled-domain scaling. The fixed normalized torus has no exact continuous dilation symmetry; here the relation diagnoses the coefficient class under local parabolic scaling.

The pair $(p,q)=(2,2)$ gives $5/2>2$, so generic coefficient estimates are supercritical. A proof of (64) must exploit the self-generated relation among $A$, $\omega$, pressure, incompressibility, and metric diffusion. Replacing that relation by an arbitrary strain history loses the needed information.

Three concrete routes remain mathematically distinct:

1. prove active-direction control (64) directly, allowing unused metric eigenvalues to degenerate;
2. prove the stronger trace-and-gauge bounds suggested by (48),
   $$
   \sup_{t,x}\operatorname{tr}H(x,t)<\infty,
   \qquad
   \inf_t\beta(t)>0;
   $$
3. establish a stochastic-flow or matrix-weight estimate for (39) that bounds active distortion from the initial $H^3$ ball without introducing $\int\|S\|_\infty dt$ or another continuation-level norm on the right.

No one of these estimates is presently established.

## 11. Relation to the existing Navier–Stokes program

The current strain-departure program seeks a uniform bound on cumulative positive critical production over bounded initial $H^3$ balls. The scalar metric (14) is an integrating-factor form of the same amplification. The matrix metric adds directional information and a forward parabolic evolution, so (64) is an alternate theorem target rather than an estimate already implied by the scalar program.

The stress-geometry results show that local vorticity does not determine local strain and that prescribed covariance shapes need dynamical control. Equations (22), (30), and (55) reproduce that boundary in adaptive-metric language. The second-order field-energy results supply positive symmetrizers and conditional continuation criteria; equation (25) shows why one fixed positive symmetrizer cannot remove all trace-free strain production.

A future Cassi contribution would need a derived dynamical constraint on active metric distortion. Adding a positive covariance, a golden coordinate, a finite cutoff, or an extra damping term changes the auxiliary model or assumes the missing amplitude bound. Such changes can produce useful regularized solvers, while the original Navier–Stokes theorem still requires (64) or another estimate of equal strength.

## 12. Verification evidence

The fixed parent protocol is
`computations/navier-stokes-adaptive-metric-prereg.md`. Its verifier,
`computations/verify_navier_stokes_adaptive_metric.py`, executes 32 exact fixed-control checks covering the branch metric, scalar weight, CassiFI-motivated covariance analogue, divergence-free spatial-curvature fixture, and terminal metric. The general weighted balance and terminal positivity statement are analytical derivations rather than generic matrix-PDE integrations. The qualified receipt is
`runs/navier_stokes_adaptive_metric/verification-audit-recheck.json`. It reports:

- **SUPPORTS** exact adaptive cancellation for the displayed balance and fixed controls;
- **CONTRADICTS** uniform coercivity inferred from the fixed algebraic strain and covariance controls alone, without classifying the Navier–Stokes-specific bound;
- **UNRESOLVED** arbitrary-data Navier–Stokes regularity.

The forward protocol is
`computations/navier-stokes-forward-adaptive-metric-prereg.md`. Its verifier,
`computations/verify_navier_stokes_forward_adaptive_metric.py`, executes 16 exact algebraic and fixed-control checks. The qualified receipt is
`runs/navier_stokes_forward_adaptive_metric/verification-audit-qualified.json`. It reports:

- **SUPPORTS** forward exact cancellation;
- **SUPPORTS** the analytic positive-metric propagation claim conditional on a smooth interval, with the executable schedule supplying spot checks rather than a generic matrix-PDE trajectory;
- **CONTRADICTS** uniform lower coercivity inferred from positivity and determinant alone, without classifying the coupled Navier–Stokes estimate;
- **UNRESOLVED** arbitrary-data Navier–Stokes regularity.

Both schedules integrate no Navier–Stokes trajectory and make no singularity claim. The parent receipt snapshots `CassiFI/cassi_variational_field.py` for provenance and reconstructs its covariance equation independently; it does not execute that implementation. The focused sibling test `CassiFI/test_variational_field.py::test_learning_uses_the_metric_flow_and_preserves_unaddressed_memory` exercises the actual fixed-exposure covariance update. The exact periodic flow controls in §9 use established analytical solutions already recorded in this directory.

## 13. Conclusion

Cassi's adaptive positive geometry yields an exact auxiliary construction for smooth Navier–Stokes solutions. A forward-parabolic SPD metric can absorb every term in the weighted enstrophy balance, and its unscaled determinant cannot fall below one. The result identifies a concrete auxiliary PDE and a sufficient continuation criterion whose required bound remains open.

The local extensional, covariance, curvature, terminal, shear, and Beltrami controls locate the algebraic boundary. Stretching can be absorbed by a collapsing selected metric direction; bounded covariance assumes bounded observations; determinant controls volume rather than condition number; terminal cancellation can require an exponentially large adjoint norm; smooth high-frequency flows can remain benign. The remaining all-data statement is the active-distortion bound (64). Proving that estimate from the coupled Navier–Stokes and metric equations would constitute substantive progress. The present calculation leaves it **UNRESOLVED**.

## References

- `turbulence/navier-stokes-strain-departure.md`—current initial-$H^3$ all-data target, exact invariant shear-mixing family, and critical production estimates.
- `turbulence/navier-stokes-stress-geometry.md`—local strain freedom, covariance geometry, and conditional depletion boundaries.
- `turbulence/navier-stokes-second-order-field-energy.md`—positive field energies and local $H^1$ restart argument.
- `CassiFI/cassi_variational_field.py` in the unified workspace—implemented covariance potential, spectral bounds, observation admission, and boundary-work statement.
- `CassiFI/test_variational_field.py` in the unified workspace—focused executable check of the fixed-exposure covariance update and untouched-memory invariant.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—official domains, data, and regularity problem.
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the 3-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—stochastic flow representation of viscous transport and stretching.
- E. Miller, [A regularity criterion for the Navier–Stokes equation involving only the middle eigenvalue of the strain tensor](https://arxiv.org/abs/1710.05569)—strain-eigenvalue continuation criterion.
- E. Miller, [On the interaction of strain and vorticity for solutions of the Navier–Stokes equation](https://arxiv.org/abs/2407.02691)—strain–vorticity orthogonality and conditional regularity criteria.
