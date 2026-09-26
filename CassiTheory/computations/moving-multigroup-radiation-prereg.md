# Moving Multigroup Radiation: Fixed Frequency-Space Controls

## Status: Preregistered—September 2026

## Abstract

This schedule verifies the moving-frequency completion used by `turbulence/moving-multigroup-radiation-closure.md`. The state is spectral radiation measured on material-frame frequency surfaces in flat spacetime. The covariant equation carries Doppler shift, acceleration and angular aberration through a third angular moment. Its group integral exposes one shared four-momentum flux at every frequency boundary. The numerical controls cover telescoping group exchange, material/radiation work, homogeneous expansion and compression, Lorentz spectral conversion, positivity and refinement. They use dimensionless spectra and prescribed velocities. Cassi material identification, production spatial transport and live CassiCosmos integration remain outside this schedule.

## 1. Frozen conventions and equations

Use metric signature $(-,+,+,+)$ and retain $c_\gamma$ in frame conversions. Covariant transport equations use coordinates $x^0=c_\gamma t$ and the dimensionless material velocity $U^\mu/c_\gamma$. The material-frame photon frequency is

$$
\nu_0:=-\frac{p_\mu U^\mu}{h}.
\tag{1}
$$

For the spectral stress tensor $R_{(\nu_0)}^{\alpha\beta}$ and spectral third angular moment $M_{(\nu_0)}^{\alpha\beta\gamma}$, freeze

$$
\boxed{
\nabla_\beta R_{(\nu_0)}^{\alpha\beta}
-\frac{\partial}{\partial\nu_0}
\left[
\nu_0M_{(\nu_0)}^{\alpha\beta\gamma}
\nabla_\gamma\!\left(\frac{U_\beta}{c_\gamma}\right)
\right]
=S_{(\nu_0)}^\alpha.}
\tag{2}
$$

The source $S_{(\nu_0)}^\alpha$ is four-momentum added to radiation by material interactions. Define ordered material-frame group edges $\nu_{g-1/2}<\nu_{g+1/2}$ and

$$
R_g^{\alpha\beta}
:=\int_{\nu_{g-1/2}}^{\nu_{g+1/2}}
R_{(\nu_0)}^{\alpha\beta}\,d\nu_0,
\qquad
S_g^\alpha
:=\int_{\nu_{g-1/2}}^{\nu_{g+1/2}}
S_{(\nu_0)}^\alpha\,d\nu_0.
\tag{3}
$$

At a frequency edge define the four-momentum flux toward increasing frequency,

$$
\boxed{
\Phi_{\nu}^{\alpha}
:=-\nu_0M_{(\nu_0)}^{\alpha\beta\gamma}
\nabla_\gamma\!\left(\frac{U_\beta}{c_\gamma}\right).}
\tag{4}
$$

Every group then obeys

$$
\boxed{
\nabla_\beta R_g^{\alpha\beta}
+\Phi_{g+1/2}^{\alpha}
-\Phi_{g-1/2}^{\alpha}
=S_g^\alpha.}
\tag{5}
$$

One evaluated interface flux is shared by its two neighboring groups. Summing contiguous groups gives

$$
\boxed{
\nabla_\beta\sum_gR_g^{\alpha\beta}
+\Phi_{N+1/2}^{\alpha}
-\Phi_{1/2}^{\alpha}
=\sum_gS_g^\alpha.}
\tag{6}
$$

Internal frequency transfers therefore telescope component by component. Outer-edge flux is zero only when the represented spectrum and boundary condition justify it; otherwise it is recorded as a frequency-domain boundary ledger.

## 2. Frozen affine-flow reduction

For a nonrelativistic affine flow with negligible material acceleration over one frequency step, let $A_{ij}:=\partial_j u_i$. The material-frame spectral energy moments are

$$
E_{\nu}:=\frac1{c_\gamma}\int I_\nu\,d\Omega,
\qquad
F_\nu:=\int nI_\nu\,d\Omega,
\qquad
P_\nu:=\frac1{c_\gamma}\int n\otimes nI_\nu\,d\Omega.
\tag{7}
$$

The energy projection of (2), through first order in $|u|/c_\gamma$, is

$$
\boxed{
\partial_tE_\nu
+\nabla\cdot(uE_\nu+F_\nu)
+P_\nu:A
-\partial_\nu[\nu(P_\nu:A)]
=S_\nu^E.}
\tag{8}
$$

Consequently,

$$
\boxed{
\partial_tE_g
+\nabla\cdot(uE_g+F_g)
+P_g:A
+\Phi^E_{g+1/2}-\Phi^E_{g-1/2}
=S_g^E,}
\tag{9}
$$

with

$$
\boxed{\Phi^E_\nu=-\nu(P_\nu:A).}
\tag{10}
$$

For isotropic radiation and homogeneous expansion,

$$
A=H\mathbf1,
\qquad
\nabla\cdot u=3H,
\qquad
P_\nu=\frac{E_\nu}{3}\mathbf1,
\tag{11}
$$

so

$$
\Phi^E_\nu=-H\nu E_\nu.
\tag{12}
$$

Expansion $H>0$ therefore transports radiation toward lower frequency; compression $H<0$ transports it toward higher frequency.

For scale factor $a(t)=e^{Ht}$ and initial spectrum $E_{\nu,0}$, freeze the exact homogeneous solution

$$
\boxed{E_\nu(t,\nu)=a^{-3}E_{\nu,0}(a\nu).}
\tag{13}
$$

It implies

$$
E_\gamma(t)=a^{-4}E_\gamma(0),
\qquad
N_\gamma(t)=a^{-3}N_\gamma(0),
\tag{14}
$$

where $N_\gamma=\int E_\nu/(h\nu)\,d\nu$. In a material volume $V=a^3V_0$, group extensive energy is

$$
\boxed{
U_g(t)
=\frac{V_0}{a}
\int_{a\nu_{g-1/2}}^{a\nu_{g+1/2}}
E_{\nu,0}(s)\,ds.}
\tag{15}
$$

Differentiating at $t=0$ gives

$$
\boxed{
\dot U_g
=-HU_g
+HV\,[\nu E_\nu]_{g-1/2}^{g+1/2}.}
\tag{16}
$$

The first term is the pressure-work contribution to material-frame radiation energy; the second is the difference of shared group-edge transfers. These terms describe a changing local radiation frame and must not be appended to material energy as a second interaction source. Matter receives the negative of the collision four-force in (2). Lab-frame total four-momentum remains the conservation variable, while the two outer frequency-edge terms record any spectral support that leaves the represented material-frame domain.

## 3. Frozen spectral-frame conversion

For a ray seen by an inertial observer, define

$$
D:=\frac{1}{\gamma(1-n\cdot\beta)},
\qquad
\beta:=\frac{u}{c_\gamma},
\qquad
\nu=D\nu_0.
\tag{17}
$$

Freeze the Lorentz invariants

$$
\boxed{
\frac{I_\nu}{\nu^3}=\frac{I_{\nu_0}^{(0)}}{\nu_0^3},
\qquad
d\Omega=D^{-2}d\Omega_0.}
\tag{18}
$$

Thus

$$
I_\nu(n)=D^3I_{\nu_0}^{(0)}(n_0),
\qquad
I_g(n)=D^4
\int_{\nu_{g-1/2}/D}^{\nu_{g+1/2}/D}
I_{\nu_0}^{(0)}(n_0)\,d\nu_0.
\tag{19}
$$

Material collision coefficients are evaluated at $\nu_0$; the observer projection applies (17)–(19) to an accepted radiation state. A spatially uniform boost has no velocity-gradient frequency flux in (4), although its observer-frame spectrum changes by (19).

## 4. Frozen discrete operator

The reference finite-volume state stores group-integrated extensive energy $U_g$. For the isotropic affine control, reconstruct a nonnegative edge value $E_{\nu,g+1/2}^{\rm up}$ from the upwind side of the characteristic speed

$$
a_\nu=-H\nu.
\tag{20}
$$

Use

$$
\widehat\Phi^E_{g+1/2}
=-H\nu_{g+1/2}E_{\nu,g+1/2}^{\rm up}
\tag{21}
$$

and the forward-Euler update

$$
\boxed{
U_g^{n+1}
=U_g^n
-\Delta t\,H U_g^n
-\Delta t\,V
(\widehat\Phi^E_{g+1/2}-\widehat\Phi^E_{g-1/2}).}
\tag{22}
$$

Subcycle so

$$
\Delta t
\max_g
\frac{|H|\nu_{g+1/2}}{\Delta\nu_g}
\leq C_{\rm CFL},
\qquad C_{\rm CFL}=0.4.
\tag{23}
$$

The production operator may use a higher-order monotone reconstruction, but it must retain one shared edge flux. The reference kernel uses piecewise-constant upwinding so its expected first-order refinement is unambiguous.

The general covariant update applies (5) to all four components. Discrete ordinates evaluate $M_{(\nu)}^{\alpha\beta\gamma}$ directly from nonnegative directional intensities. A moment method supplies a declared spectral third-moment closure at every reconstructed edge. Reusing only a group-centred pressure tensor for both edges is outside the frozen operator.

## 5. Frozen analytical controls

All symbolic residuals must simplify to zero.

1. Integrating (2) over one group gives (5).
2. Summing (5) over four contiguous groups cancels all three internal edge fluxes for each of four spacetime components.
3. Substitution of (13) into the isotropic form of (8) gives zero.
4. Integrating (13) over frequency gives both scalings in (14).
5. Differentiating (15) at $t=0$ gives (16).
6. Summing (16) over all groups leaves the material-frame bolometric pressure term and the two outer frequency-boundary terms; the internal edges cancel without creating a material collision source.
7. Equation (18) gives $I_\nu=D^3I_{\nu_0}^{(0)}$ and the group integral in (19).
8. Setting $\nabla U=0$ makes every frequency flux in (4) vanish.

## 6. Frozen numerical controls

### 6.1 Shared-edge four-momentum conservation

Use four groups and edge-flux vectors

$$
\Phi_{1/2}=0,
\quad
\Phi_{3/2}=(0.3,-0.2,0.1,0.4),
\quad
\Phi_{5/2}=(-0.5,0.7,-0.1,0.2),
$$

$$
\Phi_{7/2}=(0.9,0.2,0.6,-0.3),
\quad
\Phi_{9/2}=0.
\tag{24}
$$

Form each group contribution as $-(\Phi_{g+1/2}-\Phi_{g-1/2})$. Require the componentwise group sum to be exactly zero within $2\times10^{-14}$. Repeat with nonzero outer vectors and require the sum to equal the signed outer ledger.

### 6.2 Homogeneous expansion and compression

Use the compact nonnegative spectrum

$$
E_{\nu,0}=\nu^2(1-\nu)^2
\quad\text{for }0\leq\nu\leq1,
\qquad
E_{\nu,0}=0\quad\text{otherwise}.
\tag{25}
$$

For $H\in\{+0.2,-0.2\}$ and $t=0.25$, compare the numerical update (22) on uniform grids with $N\in\{32,64,128,256\}$ against the exact group integrals (15). Use the $L^1$ error over extensive group energies. Require:

- nonnegative group energies at every accepted substep;
- expansion lowers the energy-weighted mean frequency and compression raises it;
- the group-summed numerical increment equals the integrated material-frame pressure term plus the signed outer frequency ledger within $2\times10^{-13}$ per substep;
- the last three grid errors decrease strictly;
- the $N=256$ error is at most $0.35$ times the $N=32$ error.

### 6.3 Exact remap scalings

Integrate (25) analytically and apply (15) at $a\in\{0.8,1,1.25\}$ on a frequency domain wide enough to contain the shifted compact support. Require bolometric energy and photon number to match (14) within $2\times10^{-13}$. Require the $a=1$ remap to reproduce every group integral within the same tolerance.

### 6.4 Lorentz conversion

Use $I_{\nu_0}^{(0)}=\nu_0^2(1-\nu_0)^2$ on $0\leq\nu_0\leq1$, ray cosines $n\cdot\hat\beta\in\{-1,-0.3,0,0.8,1\}$ and $\beta\in\{0,0.03,0.2\}$. For observer groups with edges $(0,0.2,0.5,0.8,1.4)$:

- compare direct observer-frequency integration of $D^3I^{(0)}(\nu/D)$ with (19), requiring normalized error at most $2\times10^{-12}$;
- require $I_\nu/\nu^3$ invariance at five interior frequencies;
- apply the inverse Doppler factor and require frequency and intensity round trips within $2\times10^{-13}$;
- require a uniform boost to leave the frequency-evolution operator exactly zero when $\nabla U=0$.

### 6.5 Rejection controls

Require rejection of unordered or nonpositive group edges, nonfinite states, negative group energy, $|\beta|\geq1$, a missing spectral third-moment closure and independently evaluated values for the two sides of one internal frequency edge.

## 7. Decision rule

The verifier result is **PASS** only if every frozen analytical, numerical and rejection control passes. A failed check gives **FAIL**. A run that lacks a required source, snapshot or immutable output path gives **INCONCLUSIVE** and exits before calculation.

A PASS supports the conditional P4c equation, group-edge discretization and stated affine-flow/frame-conversion controls. It does not establish a live solver, production spatial/angular convergence, a Cassi material map, physical opacity data or any undeclared relativistic/gravitational regime.

## References

- `turbulence/moving-multigroup-radiation-closure.md`—conditional P4c derivation and implementation boundary
- `turbulence/cassi-radiative-material-closure.md`—material-frame transfer and covariant collision four-force
- `turbulence/compressible-radiative-plasma-closure.md`—compressible material, species and multi-angle state
- P. Anninos and P. C. Fragile, [Multi-Frequency General Relativistic Radiation-Hydrodynamics with $M_1$ Closure](https://arxiv.org/abs/2007.12195)—covariant spectral moment equation and conservative frequency advection
- D. Mihalas and B. Weibel-Mihalas, *Foundations of Radiation Hydrodynamics*—comoving-frame transfer and moment equations
