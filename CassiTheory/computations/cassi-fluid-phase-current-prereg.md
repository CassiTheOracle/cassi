# Cassi Phase-Current Hydrodynamics: Fixed Rotational and Projection Controls

## Status: Preregistered—September 2026

## Abstract

This schedule tests whether the phase-bearing Yang/Yin action supplies rotational fluid kinematics and whether its scale coordinate supplies a route to positive viscosity. A normalized doublet gives a Berry-current velocity and the Mermin–Ho vorticity identity. One everywhere-positive doublet has a zero-helicity global Clebsch chart on a closed domain; component zeros or additional scale bands change that topology. Two fixed scale bands are tested against an exact periodic Beltrami flow. Scalar diffusion of their composition amplitudes gives an exact viscous decay for that fixture, while a commutator control tests the extension to general Clebsch fields. The closed first-order action remains Hamiltonian. An exact resolved/exterior reduction identifies the memory kernel and initial exterior state required before a positive Markovian viscosity can be inferred.

## 1. Fixed state and current map

For scale band $r$, take constant positive band density $\rho_r$, composition $0\leq c_r\leq1$, phases $\theta_{Yr},\theta_{Ir}$ and

$$
\psi_{Yr}=\sqrt{\rho_rc_r}\,e^{i\theta_{Yr}},
\qquad
\psi_{Ir}=\sqrt{\rho_r(1-c_r)}\,e^{i\theta_{Ir}},
\qquad
\kappa_v=\frac{\hbar}{m}.
$$

The ungauged number current and band velocity are

$$
j_r=\rho_r u_r,
\qquad
u_r=\kappa_v\left[c_r\nabla\theta_{Yr}+(1-c_r)\nabla\theta_{Ir}\right]
=\kappa_v\left(\nabla\theta_{Ir}+c_r\nabla\alpha_r\right),
\qquad
\alpha_r=\theta_{Yr}-\theta_{Ir}.
$$

For constant fractions $f_r=\rho_r/\sum_s\rho_s$, the observed current velocity is

$$
u=\sum_r f_ru_r
=\kappa_v\nabla\left(\sum_r f_r\theta_{Ir}\right)
 +\kappa_v\sum_r f_rc_r\nabla\alpha_r.
\tag{PC1}
$$

For one band set $c=(1+\cos\beta)/2$ and

$$
Z=e^{i\Theta}
\begin{pmatrix}
\cos(\beta/2)e^{i\alpha/2}\\
\sin(\beta/2)e^{-i\alpha/2}
\end{pmatrix},
\qquad
n=(\sin\beta\cos\alpha,-\sin\beta\sin\alpha,\cos\beta).
$$

Then the dimensionless current connection, curvature and physical vorticity are

$$
A=-iZ^\dagger dZ=d\Theta+\frac12\cos\beta\,d\alpha,
\qquad
F=dA=-\frac12\sin\beta\,d\beta\wedge d\alpha,
$$

$$
\omega_i=\frac{\kappa_v}{2}\epsilon_{ijk}F_{jk}
=\frac{\kappa_v}{4}\epsilon_{ijk}
 n\cdot(\partial_jn\times\partial_kn).
\tag{PC2}
$$

For the relative gauge connection of the source action, use

$$
A_B=d\Theta+\frac12\cos\beta\,(d\alpha-g_QB),
$$

$$
F_B=-\frac12\sin\beta\,d\beta\wedge(d\alpha-g_QB)
     -\frac{g_Q}{2}\cos\beta\,G,
\qquad G=dB.
\tag{PC3}
$$

The projective Berry curvature and dynamical relative curvature retain separate terms.

## 2. Analytical controls

All statements concern smooth fields on their declared domains.

### 2.1 Current, vorticity and energy identities

1. Derive (PC1) directly from the Noether number currents of the ungauged first-order action, including the mass convention $\kappa_v=\hbar/m$.
2. Derive (PC2) from the normalized spinor and verify $dF=0$ away from component-zero or singular charts.
3. Derive (PC3) from the opposite relative charges of the two components. A nonzero $G$ term must remain when $d\beta=d\alpha=0$ and $\cos\beta\ne0$.
4. Establish the kinetic variance identity
   $$
   \frac12\sum_r\rho_r\left[c_r|v_{Yr}|^2+(1-c_r)|v_{Ir}|^2\right]
   =\frac{\rho}{2}|u|^2
   +\frac12\sum_r\rho_r\left[c_r|v_{Yr}-u|^2+(1-c_r)|v_{Ir}-u|^2\right],
   \tag{PC4}
   $$
   where $v_{ar}=\kappa_v\nabla\theta_{ar}$, $\rho=\sum_r\rho_r$ and $u$ is (PC1). The second term is unresolved species-and-band counterflow energy and is nonnegative.

### 2.2 One-band topology controls

For an everywhere-positive doublet on a closed three-manifold, $c$, $d\theta_I$ and $d\alpha$ are global while

$$
A=d\theta_I+c\,d\alpha,
\qquad
F=dc\wedge d\alpha,
\qquad
A\wedge F=-d\left(c\,d\theta_I\wedge d\alpha\right).
\tag{PC5}
$$

The integrated helicity is therefore zero. This statement allows compact phase windings and concerns one global positive chart.

Use the exact $2\pi$-periodic shear fixture, with integer $N>0$ and $0<U<\kappa_vN$,

$$
\theta_Y=Nx,
\qquad
\theta_I=-Nx,
\qquad
c=\frac12+\frac{U}{2\kappa_vN}\sin y.
\tag{PC6}
$$

It must give

$$
u=(U\sin y,0,0),
\qquad
\omega=(0,0,-U\cos y),
\qquad
\nabla\cdot u=0,
\qquad
\langle u\cdot\omega\rangle=0.
$$

Its mean microscopic phase kinetic energy is $\rho\kappa_v^2N^2/2$, its mean resolved kinetic energy is $\rho U^2/4$, and the difference is the positive counterflow term in (PC4).

For a full normalized doublet on the unit $S^3$ use

$$
Z=(\cos\eta\,e^{i\xi_1},\sin\eta\,e^{i\xi_2}),
\quad
0\leq\eta\leq\frac\pi2,
\quad
0\leq\xi_1,\xi_2<2\pi,
\tag{PC7}
$$

with orientation $d\eta\wedge d\xi_1\wedge d\xi_2$. Its connection must satisfy

$$
A=\cos^2\eta\,d\xi_1+\sin^2\eta\,d\xi_2,
\qquad
*dA=-2A,
\qquad
\int_{S^3}A\wedge dA=-4\pi^2.
\tag{PC8}
$$

The physical velocity $u=\kappa_vA^\sharp$ has $\operatorname{curl}u=-2u$ and helicity $-4\pi^2\kappa_v^2$. Each component vanishes on one Hopf circle, so (PC5) does not apply.

### 2.3 Two-band rotational completion

For bounded periodic real potentials $\phi,a_1,a_2,b_1,b_2$, positive fixed fractions $f_1+f_2=1$, reference compositions $c_{0r}\in(0,1)$ and constants $L_r$ large enough that

$$
c_r=c_{0r}+\frac{a_r}{\kappa_vf_rL_r}\in(0,1),
\qquad
\alpha_r=L_rb_r,
$$

choose the common lower phase

$$
\theta_{I1}=\theta_{I2}
=\frac{\phi}{\kappa_v}-\sum_{r=1}^2f_rc_{0r}L_rb_r.
\tag{PC9}
$$

Equation (PC1) then gives the two-pair generalized Clebsch field

$$
u=\nabla\phi+a_1\nabla b_1+a_2\nabla b_2.
\tag{PC10}
$$

This is a constructive bounded periodic class. Global boundary-value and component-zero topology remain separate from this construction.

Use the fixed $2\pi$-periodic Beltrami fixture $\kappa_v=1$, $f_1=f_2=1/2$,

$$
\theta_{I1}=\theta_{I2}=-2x-2y,
\qquad
\alpha_1=8x,
\qquad
\alpha_2=8y,
$$

$$
c_1=\frac12+\frac{A}{4}\sin z,
\qquad
c_2=\frac12+\frac{A}{4}\cos z,
\qquad
0\leq A\leq1.
\tag{PC11}
$$

It must give

$$
u=A(\sin z,\cos z,0),
\qquad
\nabla\times u=u,
\qquad
\nabla\cdot u=0,
\qquad
\langle u\cdot\omega\rangle=A^2.
\tag{PC12}
$$

At $A=1$, each band has zero mean self-helicity while the observed cross-band field has mean helicity one. The mean microscopic phase kinetic energy is $12\rho$ in the convention where $\rho=1$; the resolved mean kinetic energy is $A^2/2$ and the counterflow remainder is $12-A^2/2$.

### 2.4 Restricted viscosity correspondence and general obstruction

Let $A(t)=e^{-Dt}$ in (PC11), with fixed phases and $D>0$. Each composition obeys $\partial_tc_r=D\Delta c_r$, and the observed velocity obeys

$$
\partial_tu=D\Delta u,
\qquad
(u\cdot\nabla)u=0.
\tag{PC13}
$$

Thus the lifted field is an exact unforced incompressible Navier–Stokes solution with kinematic viscosity $\nu=D$ for this fixture. Equation (PC4) shows that its resolved kinetic-energy loss enters the counterflow remainder; a heat interpretation requires an additional irreversible closure.

For a general fixed-potential Clebsch field $u=\nabla\phi+\sum_ra_r\nabla b_r$ with $\partial_ta_r=D\Delta a_r$, the mismatch from vector viscosity is

$$
D\Delta u-\partial_tu
=D\nabla\Delta\phi
+D\sum_r\left[2(\nabla a_r\cdot\nabla)\nabla b_r+a_r\nabla\Delta b_r\right].
\tag{PC14}
$$

A pressure can absorb the gradient part only. Use $a=\sin x$, $b=\sin y$ as the fixed periodic witness: the bracket has nonzero curl, so its Leray projection remains nonzero. The identity $D\Delta u=\partial_tu$ therefore fails for generic phase potentials.

### 2.5 Reversible-action and projection controls

For a finite closed Hermitian linearization split into resolved and exterior variables,

$$
i\dot x=H_Lx+Vy,
\qquad
i\dot y=V^\dagger x+H_Ey,
$$

exact elimination gives

$$
\dot x(t)=-iH_Lx(t)-iVe^{-iH_Et}y(0)
-\int_0^tK(t-s)x(s)\,ds,
\qquad
K(t)=Ve^{-iH_Et}V^\dagger.
\tag{PC15}
$$

Two exterior initial states with the same $x(0)$ generally give different $\dot x(0)$. A finite commensurate exterior has recurrent $K(t)$. Hence the resolved instantaneous state has no autonomous positive-viscosity semigroup supplied by the closed action alone.

A selected rapidly decaying positive memory kernel

$$
K_\tau(t)=\frac{\nu k^2}{\tau}e^{-t/\tau}
$$

has the auxiliary form

$$
\dot A=-R,
\qquad
\tau\dot R=\nu k^2A-R,
\qquad
A(0)=1,
\qquad
R(0)=\nu k^2.
\tag{PC16}
$$

It approaches $\dot A=-\nu k^2A$ as $\tau\to0$. This is a mathematical Markov-limit control. A Cassi viscosity value requires a declared resolved map, exterior state or ensemble, correlation decay and a low-$k$ limit with $\operatorname{Re}\int_0^\infty K_k(t)dt=\nu k^2+o(k^2)$.

## 3. Fixed computational controls

The executable verifier is `computations/verify_cassi_fluid_phase_current.py`. It uses SymPy exact algebra and NumPy float64/complex128. No coefficient fitting, floor, smoothing or random input is permitted.

### 3.1 Exact algebra

The verifier must simplify every identity in §§2.1–2.5 to zero where symbolic representation is finite. It must explicitly check:

- normalization, component populations, Berry connection, curvature and the Mermin–Ho coefficient;
- the gauged curvature term and its nonzero constant-composition witness;
- the kinetic variance decomposition;
- exactness of the positive-chart helicity density;
- the shear velocity, curl, divergence and energy split;
- the Hopf connection, Hodge relation and helicity integral;
- the bounded two-pair construction;
- the Beltrami velocity, vorticity, helicity and band energies;
- the scalar-diffusion/viscosity identity and the nonzero curl of the (PC14) witness;
- the exact block-Hamiltonian elimination and initial-exterior-state dependence.

### 3.2 Periodic spatial reconstruction

On the $2\pi$ cube use odd grids $N=9,15,21$ and Fourier differentiation.

1. Reconstruct (PC6) with $(\kappa_v,N,U)=(1,3,0.7)$. Require maximum velocity, curl and divergence errors below $10^{-12}$, mean helicity magnitude below $10^{-13}$, and each composition sample in $(0,1)$.
2. Reconstruct (PC11) at $A=1$ directly from all four component currents. Require maximum velocity, Beltrami-curl and divergence errors below $10^{-12}$; mean helicity must agree with one within $10^{-12}$. Reconstruct each band self-helicity and the energy split independently from the component arrays.
3. Reconstruct (PC9)–(PC10) for
   $$
   \phi=0.1\sin(x+y+z),\quad
   a_1=0.2\sin z,\quad b_1=\sin x+0.3\cos y,
   $$
   $$
   a_2=0.15\cos x,\quad b_2=\cos y+0.2\sin z,
   $$
   with $f_1=f_2=1/2$, $c_{01}=c_{02}=1/2$, $L_1=L_2=4$ and $\kappa_v=1$. Require maximum current-reconstruction error below $10^{-12}$ and $0<c_r<1$.
4. At times $t=0,0.3,1$ with $D=0.03$, reconstruct (PC13) from the diffused compositions. Require the velocity, time derivative and Laplacian identities below $10^{-12}$. Record the resolved and counterflow energy exchange.
5. Evaluate the (PC14) witness by both analytic and Fourier derivatives. Require agreement below $10^{-12}$ and a Leray-projected mismatch norm above $10^{-3}$.

### 3.3 Hopf and memory reconstruction

1. Integrate $A\wedge dA$ on $S^3$ with tensor-product trapezoidal phase quadrature and Gauss–Legendre latitude quadrature at orders $8,16,32$. Every result must agree with $-4\pi^2$ within $10^{-12}$.
2. Use $H_E=\operatorname{diag}(-2,-1,1,2)$ and $V=(0.2,0.3,0.3,0.2)$. Verify $K(2\pi)=K(0)$ within $10^{-12}$ and exhibit two unit-norm exterior initial states giving resolved initial derivatives separated by more than $0.1$ at the same $x(0)=1$.
3. Solve (PC16) by exact eigendecomposition for $\nu=0.03$, $k=1$, $t\in[0,2]$ and $\tau=0.2,0.1,0.05$. Compare with $e^{-\nu t}$. The maximum error must decrease strictly at each refinement and the finest error must be below $2\times10^{-4}$. Independently integrate $\dot Q=AR$ and require $A^2/2+Q=1/2$ within $10^{-12}$. Positivity of $A$ and $R$ is required on the sampled interval.

Store the full spatial fields for the finest spatial controls and all memory trajectories. Independently reconstruct every reported norm, mean helicity and energy from the retained arrays.

## 4. Decisions and immutable evidence

The verifier status is `PASS` only if every scheduled check passes. The result classifications are fixed as follows:

- successful (PC1)–(PC3), shear and Hopf controls give `SUPPORTS` for local doublet vorticity and full-doublet topological helicity;
- (PC5) gives `CONTRADICTS` for nonzero integrated helicity in one everywhere-positive global doublet chart;
- successful (PC9)–(PC12) give `SUPPORTS` for the declared two-band periodic generalized-Clebsch and Beltrami class;
- successful (PC13) gives `SUPPORTS` for the exact fixed-phase Beltrami diffusion/viscosity correspondence;
- the nonzero (PC14) control gives `CONTRADICTS` for identifying scalar composition diffusion with vector viscosity for general fixed phase potentials;
- successful (PC15) gives `CONTRADICTS` for an autonomous irreversible finite closed resolved dynamics determined by $x(0)$ alone;
- successful (PC16) gives `SUPPORTS` for the selected exponential-memory Markov limit;
- a Cassi-derived positive viscosity coefficient and an arbitrary-flow hydrodynamic closure remain `UNESTABLISHED` regardless of verifier status.

Capture this protocol, the verifier, `foundations/interscale-current-soliton.md`, `foundations/geometric-manifold-completion.md`, `foundations/quantum-measurement-derivation.md`, `turbulence/cassi-fluid-feasibility.md` and the executed Python environment as immutable source or metadata snapshots before calculation. Refuse an existing output directory. Retain all failures and raw arrays. Any change to equations, fixtures or tolerances after execution requires a fresh output path and reconciliation; the original result remains intact.

## References

- `foundations/interscale-current-soliton.md`—first-order doublet action, species currents, relative connection and exact exterior-memory reduction.
- `foundations/geometric-manifold-completion.md`—normalized projective spinor and distinction between Berry and dynamical relative curvature.
- `foundations/quantum-measurement-derivation.md`—phase-fibre causality and missing microscopic projection map.
- `turbulence/cassi-fluid-feasibility.md`—selected rotational velocity, positive viscosity and thermodynamic completion boundary.
- N. D. Mermin and T.-L. Ho, [Circulation and Angular Momentum in the A Phase of Superfluid Helium-3](https://doi.org/10.1103/PhysRevLett.36.594)—vorticity from order-parameter geometry.
- Z. Yoshida, [Clebsch parameterization: Basic properties and remarks on its applications](https://doi.org/10.1063/1.3256125)—local and generalized Clebsch representation with global and boundary qualifications.
- R. Zwanzig, [Memory Effects in Irreversible Thermodynamics](https://doi.org/10.1103/PhysRev.124.983)—exact projected memory and fluctuating-force structure.
