# Second-Order Field Energy and Navier–Stokes: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This fixed analytical check asks whether the second-order field equations used by Cassi supply a positive quantity relevant to the original unforced three-dimensional incompressible Navier–Stokes equation. It separates two systems. The live Yang/Yin scalar wave pair is tested for its exact mass-metric symmetrizer and source-free energy. The second-order spatial gauge connection is then restricted to one color direction, where its electric and magnetic curvatures become a scaled velocity time derivative and vorticity.

The Navier–Stokes calculation tests a time–curl residual

$$
g_c:=\omega-\sigma_c c^{-1}u_t,
\qquad
\sigma_c(x,t)\in\{-1,+1\},
$$

with the sign chosen pointwise to minimize the residual. A finite critical mixed norm of this residual is the proposed continuation hypothesis. The check evolves no candidate singular trajectory, searches no coefficient, and assigns no literature priority. Earlier frozen protocols and numerical verdicts remain fixed.

## 1. Fixed source equations

### 1.1 Live Yang/Yin scalar pair

Use the source-free, constant-coefficient continuum form of `CassiCosmos/compute/cassi_two_fluid.glsl`:

$$
\begin{aligned}
\partial_t^2E_Y
&=c_s^2\Delta E_Y-\omega_0^2(E_Y-\varphi E_I),\\
\partial_t^2E_I
&=c_s^2\Delta E_I+\omega_0^2(E_Y-\varphi E_I),
\end{aligned}
\tag{SO1}
$$

where $c_s>0$, $\omega_0\ge0$, and $\varphi^2=\varphi+1$. Define

$$
U=\begin{pmatrix}E_Y\\E_I\end{pmatrix},
\quad
M=\begin{pmatrix}1&-\varphi\\-1&\varphi\end{pmatrix},
\quad
K=\operatorname{diag}(1,\varphi),
\quad
v=\begin{pmatrix}1\\-\varphi\end{pmatrix}.
\tag{SO2}
$$

The default-off U1 branch replaces $M$ by $M_1=vv^\mathsf T$. The fixed question is whether the default matrix is already self-adjoint in the positive metric $K$, and what U1 changes when both systems are written with their correct kinetic metrics.

### 1.2 Second-order gauge connection

Use the gauge-curvature terms in `foundations/particle-stationary-action-closure.md`:

$$
\mathcal L_{\mathcal A}
=
\frac{\epsilon_x}{2}\mathcal F_{ti}^a\mathcal F_{ti}^a
-
\frac{1}{4\mu_x}\mathcal F_{ij}^a\mathcal F_{ij}^a,
\qquad
c_g^2=(\epsilon_x\mu_x)^{-1},
\tag{SO3}
$$

with positive $\epsilon_x,\mu_x$. Restrict to temporal gauge and one fixed color direction:

$$
\mathcal A_0^a=0,
\qquad
\mathcal A_i^a=\delta^{a3}u_i.
\tag{SO4}
$$

The commutator vanishes because $\epsilon^{a33}=0$. The verifier tests the resulting curvature, Gauss constraint, and positive energy directly. This restriction is an algebraic map of variables and constraints; it does not assert that a Navier–Stokes velocity solves the source-free gauge equation.

### 1.3 Navier–Stokes conventions

Use a smooth mean-zero divergence-free solution on the volume-normalized $2\pi$ torus while its maximal smooth interval exists:

$$
\nu>0,
\qquad
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0.
\tag{SO5}
$$

Define

$$
u_t:=\partial_tu.
\tag{SO6}
$$

Set

$$
\omega=\nabla\times u,
\qquad
S=\frac12(\nabla u+\nabla u^\mathsf T),
\qquad
q_c=c^{-1}u_t,
\tag{SO7}
$$

for a fixed $c>0$. Choose the measurable sign

$$
\sigma_c(x,t)=
\begin{cases}
+1,&\omega\cdot q_c\ge0,\\
-1,&\omega\cdot q_c<0,
\end{cases}
\qquad
g_c=\omega-\sigma_cq_c.
\tag{SO8}
$$

Thus $|g_c|=\min_{\sigma=\pm1}|\omega-\sigma q_c|$. The proof differentiates no sign field.

## 2. Fixed exact targets

### 2.1 Scalar symmetrizer and energy

The verifier must establish all of the following:

1. $K$ is positive definite and
   $$
   KM=M^\mathsf TK=vv^\mathsf T.
   \tag{SO9}
   $$
2. The default system has eigenvalues $0$ and $1+\varphi=\varphi^2$, with kernel spanned by $(\varphi,1)^\mathsf T$.
3. On a periodic domain, or with boundary conditions that remove the flux, (SO1) conserves
   $$
   \boxed{
   \mathcal E_K=
   \frac12\int
   \left[
   (\partial_tU)^\mathsf TK(\partial_tU)
   +c_s^2\partial_jU^\mathsf TK\partial_jU
   +\omega_0^2(E_Y-\varphi E_I)^2
   \right]dx.}
   \tag{SO10}
   $$
4. With $\rho=E_Y+E_I$ and $\varepsilon=E_Y-\varphi E_I$,
   $$
   \rho_{tt}=c_s^2\Delta\rho,
   \qquad
   \varepsilon_{tt}=c_s^2\Delta\varepsilon-
   \varphi^2\omega_0^2\varepsilon,
   \tag{SO11}
   $$
   and
   $$
   \mathcal E_K=\frac12\int\left[
   \varphi^{-1}(\rho_t^2+c_s^2|\nabla\rho|^2)
   +\varphi^{-2}(\varepsilon_t^2+c_s^2|\nabla\varepsilon|^2)
   +\omega_0^2\varepsilon^2
   \right]dx.
   \tag{SO12}
   $$
5. The equal-inertia quadratic used in the U1 probes has derivative
   $$
   \frac{d\mathcal E_{\mathrm{equal}}}{dt}
   =(1-\varphi)\omega_0^2
   \int E_{I,t}(E_Y-\varphi E_I)\,dx
   \tag{SO13}
   $$
   under the default equations. Its measured oscillation therefore diagnoses a metric mismatch.
6. The U1 matrix $M_1=vv^\mathsf T$ is symmetric, has eigenvalues $0$ and $1+\varphi^2=\varphi+2$, and conserves the equal-inertia quadratic. Its frequency ratio relative to the default system remains
   $$
   \sqrt{\frac{1+\varphi^2}{1+\varphi}}.
   \tag{SO14}
   $$

The expected classification is that both source-free systems are Hamiltonian with different positive kinetic metrics. U1 changes the inertia convention and anti-phase frequency; it does not create the first positive Hamiltonian structure.

### 2.2 Abelian gauge map

Under (SO4), the verifier must establish

$$
\mathcal F_{ti}^3=u_{t,i},
\qquad
\mathcal F_{ij}^3=\partial_i u_j-\partial_j u_i,
\qquad
\sum_{i,j}(\mathcal F_{ij}^3)^2=2|\omega|^2.
\tag{SO15}
$$

The source-free Gauss law reduces to

$$
\epsilon_x\partial_i u_{t,i}=0,
\tag{SO16}
$$

which follows from incompressibility. The normalized gauge energy is

$$
\boxed{
\mu_x\mathcal H_{\mathcal A}
=\frac12\left(\|\omega\|_2^2+c_g^{-2}\|u_t\|_2^2\right).}
\tag{SO17}
$$

The live default-off field-particle runtime contains the three spatial $SU(2)$ connection components and their second-order velocities. Source hashes pin the exact runtime and theory definitions used by this check.

### 2.3 Exact Navier–Stokes balance

For fixed $c>0$, define

$$
H_c=\|\omega\|_2^2+c^{-2}\|u_t\|_2^2,
\qquad
D_c=\|\nabla\omega\|_2^2+c^{-2}\|\nabla u_t\|_2^2.
\tag{SO18}
$$

Differentiating the momentum equation and pairing with $u_t$ gives

$$
\frac12\frac{d}{dt}\|u_t\|_2^2
+\nu\|\nabla u_t\|_2^2
=-\int u_t\cdot S u_t\,dx.
\tag{SO19}
$$

Adding $c^{-2}$ times (SO19) to the enstrophy identity must give

$$
\boxed{
\frac12H_c'+\nu D_c
=\int S:\left(\omega\otimes\omega-q_c\otimes q_c\right)dx.}
\tag{SO20}
$$

Since $(\sigma_cq_c)\otimes(\sigma_cq_c)=q_c\otimes q_c$, the exact difference-of-squares factorization is

$$
\omega\otimes\omega-q_c\otimes q_c
=g_c\otimes\omega+(\sigma_cq_c)\otimes g_c.
\tag{SO21}
$$

For every spatial exponent $r\in[3,\infty]$, set

$$
\theta_r=\frac3r,
\qquad
a_r=\frac{2r}{r-2},
\qquad
p_r=\frac{2r}{2r-3},
\tag{SO22}
$$

with $(\theta_\infty,a_\infty,p_\infty)=(0,2,1)$. Hölder, the torus Biot–Savart multiplier, interpolation between $L^2$ and $L^6$, and Young's inequality must yield

$$
\left|\int S:(\omega\otimes\omega-q_c\otimes q_c)dx\right|
\le
C_{r}\|g_c\|_r
H_c^{1-\theta_r/2}D_c^{\theta_r/2},
\tag{SO23}
$$

and hence

$$
\boxed{
H_c(t)\le H_c(0)
\exp\left[
C_{r,\Omega}\nu^{-3/(2r-3)}
\int_0^t\|g_c(s)\|_r^{p_r}ds
\right]}
\tag{SO24}
$$

for finite $r$, with the viscosity factor interpreted as $1$ at $r=\infty$. Therefore

$$
\boxed{
g_c\in L^{p_r}(0,T;L^r),
\qquad
\frac2{p_r}+\frac3r=2,
\qquad
3\le r\le\infty}
\tag{SO25}
$$

is a conditional continuation criterion. The canonical endpoint used for the Cassi comparison is

$$
\int_0^T\|g_c(t)\|_3^2dt<\infty.
\tag{SO26}
$$

A bound on $H_c$ bounds enstrophy and continues the smooth solution by the standard strong-solution criterion.

### 2.4 Scaling and all-data target

Under Navier–Stokes scaling

$$
 u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t),
 \qquad c_\lambda=\lambda c,
\tag{SO27}
$$

both $\omega_\lambda$ and $c_\lambda^{-1}\partial_tu_\lambda$ scale as $\lambda^2$. The verifier must check

$$
\|g_{c_\lambda,\lambda}\|_r
=\lambda^{2-3/r}\|g_c\|_r,
\qquad
\|g_{c_\lambda,\lambda}\|_r^{p_r}dt_\lambda
=\|g_c\|_r^{p_r}dt.
\tag{SO28}
$$

Thus the criterion is scale-critical when the field speed is transformed with its physical velocity dimension.

For

$$
R_0=\|u_0-\langle u_0\rangle\|_{H^3(\mathbb T^3)},
\tag{SO29}
$$

smooth data with $R_0\le R$ have a data-controlled $H_c(0)$ because

$$
u_t(0)=\nu\Delta u_0-\mathbb P[(u_0\cdot\nabla)u_0].
\tag{SO30}
$$

The sufficient endpoint all-data target is consequently

$$
\boxed{
\text{for every }\nu,T,R>0\text{, find }c(\nu,T,R)>0
\text{ and }M(\nu,T,R)<\infty
}
\tag{SO31}
$$

such that

$$
\boxed{
\sup_{R_0\le R}
\int_0^{\min(T,T_*)}
\left\|\omega-\sigma_c c^{-1}u_t\right\|_3^2dt
\le M(\nu,T,R).}
\tag{SO32}
$$

No estimate of the form (SO32) is assumed or inferred from the positive field energy.

## 3. Fixed exact controls

### 3.1 Beltrami heat flow

For integer $n\ge1$,

$$
u=a e^{-\nu n^2t}(\sin nz,\cos nz,0)
\tag{SO33}
$$

must satisfy the unforced equation with zero nonlinearity, $\omega=n u$, and

$$
g_{\nu n}=0
\tag{SO34}
$$

using $\sigma=-1$. The Lorentzian source-free gauge-wave defect remains nonzero:

$$
u_{tt}+c_g^2\nabla\times\nabla\times u
=2\nu^2n^4u
\tag{SO35}
$$

when $c_g=\nu n$. This control separates the residual criterion from an assertion that the heat flow solves the gauge equation.

### 3.2 Shear heat flow

The exact solution

$$
u=a e^{-\nu n^2t}(\sin ny,0,0)
\tag{SO36}
$$

has $u_t\perp\omega$ pointwise. Consequently

$$
|g_c|^2=|\omega|^2+c^{-2}|u_t|^2
\tag{SO37}
$$

for either sign. Its initial kinetic energy is $a^2/4$, independent of $n$, while

$$
\int_0^T\|g_c\|_3^2dt
\ge
\left(\frac4{3\pi}\right)^{2/3}
\frac{a^2\nu n^2}{2c^2}
\left(1-e^{-2\nu n^2T}\right).
\tag{SO38}
$$

This family excludes a bound of the critical residual work by kinetic energy alone. Every member is globally smooth, so a large finite residual is not a danger score.

### 3.3 Fixed nonlinear Fourier datum

At $t=0$, use

$$
u=(0,1,1)\cos x
+(1,0,1)\cos y
+(1,-1,1)\sin(x+y),
\tag{SO39}
$$

with $\nu=0.37$ and $c=1.7$. A direct $32^3$ Fourier reconstruction must verify divergence freedom, the Leray-projected $u_t$ and $u_{tt}$ equations, the separate enstrophy and time-derivative balances, (SO20), and the pointwise tensor factorization (SO21). The known stretching integral is $1/2$ in the volume-normalized convention. No random seed or coefficient search is permitted.

## 4. Verification implementation

Create `computations/verify_navier_stokes_second_order_field_energy.py`. It must:

1. use exact SymPy algebra for (SO9)–(SO14), (SO15)–(SO17), the tensor cancellation, and every exponent identity in (SO22), (SO25), and (SO28);
2. evaluate the two exact heat-flow controls symbolically;
3. reconstruct the fixed nonlinear datum independently with NumPy FFTs on the declared $32^3$ grid;
4. inspect the live scalar shader equations and field-particle state declaration without importing runtime code;
5. record SHA-256 hashes for this protocol, the verifier, both live shaders, and `foundations/particle-stationary-action-closure.md`;
6. write `runs/navier_stokes_second_order_field_energy/verification.json` with schema `cassi.navier-stokes.second-order-field-energy.verification.v1`;
7. print every named check and end with `ALL CHECKS PASSED` only when every check passes.

Exact symbolic expressions must simplify to zero. Floating Fourier identities use absolute tolerance $2\times10^{-10}$ and relative tolerance $2\times10^{-10}$. Finiteness checks are mandatory. The verifier runs once after implementation. A failed check produces `FAIL—SECOND-ORDER FIELD ENERGY` and blocks integration.

## 5. Fixed interpretation

All checks passing supports three separate classifications:

1. **CORRECTED EXACT STRUCTURE:** the live source-free Yang/Yin scalar pair has the positive weighted energy (SO10); U1 is an equal-inertia alternative with a different anti-phase frequency.
2. **DERIVED CONDITIONAL REDUCTION:** the Abelian gauge-energy map yields $H_c$, and finite critical time–curl residual work in (SO25) continues an original unforced Navier–Stokes solution.
3. **UNRESOLVED:** the original Navier–Stokes dynamics, Cassi's whole-field initial-state selection, and the live field-particle evolution supply no established arbitrary-data bound on (SO32).

The result does not add a force, viscosity, gauge equation, cutoff, or constitutive term to Navier–Stokes. A proof of (SO32), or a stronger estimate implying it for every bounded $H^3$ data set, is required for the Millennium statement.

## References

- `CassiCosmos/compute/cassi_two_fluid.glsl`—live second-order Yang/Yin scalar update.
- `CassiCosmos/compute/cassi_field_particle.glsl`—default-off field-particle connection coordinates and second-order velocities.
- `foundations/particle-stationary-action-closure.md` §§3–4—second-order gauge action, positive energy, and Gauss constraint.
- `turbulence/navier-stokes-strain-departure.md` §10—signed helical residual criterion and first-order phase-energy boundary.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—original problem alternatives.
