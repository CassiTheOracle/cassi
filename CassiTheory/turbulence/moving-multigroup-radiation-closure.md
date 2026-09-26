# Moving Multigroup Radiation Closure

## Status: Derived conditional / Verification pending—September 2026

## Abstract

A moving material changes the frequency assigned to the same photon from cell to cell. Fixed material-frame frequency groups therefore exchange radiation through their shared frequency boundaries even in transparent flow. This paper derives that exchange from the covariant spectral moment equation, gives its conservative group form, identifies the third angular moment required at each edge, and reduces it to a directly implementable Doppler flux for nonrelativistic affine flow. The internal edge fluxes telescope exactly, while the summed stress tensor obeys the bolometric covariant conservation law. Lorentz invariants provide the separate conversion from material-frame groups to an observer spectrum. The result completes the conditional equation and discrete interface required for P4c. Physical material identification, coefficient data, production spatial/angular convergence and live CassiCosmos integration remain separate requirements.

## 1. Scope and frame convention

P4c evolves a spectrum through material whose velocity varies in space or time. A gray solver cannot represent photons crossing a frequency boundary, and independent gray exchange in fixed bins omits that transfer.

The canonical frequency coordinate in this closure is the local material-frame frequency

$$
\boxed{\nu_0:=-\frac{p_\mu U^\mu}{h},}
\tag{1}
$$

where $p^\mu$ is photon four-momentum and $U^\mu U_\mu=-c_\gamma^2$. Group edges

$$
0\leq\nu_{1/2}<\nu_{3/2}<\cdots<\nu_{N+1/2}
\tag{2}
$$

are fixed values of $\nu_0$. The group identity is therefore physical: it refers to the frequency measured by the material at the event where coefficients and collisions are evaluated.

The derivation uses flat spacetime for the CassiCosmos handoff. Covariant notation keeps acceleration and angular aberration in the same equation and states how a curved-spacetime extension would enter. The executable controls cover special relativity and the nonrelativistic affine-flow limit. They make no claim for a general-relativistic production solver.

## 2. Spectral moments on moving frequency surfaces

The frequency-space term follows because the material-frame energy coordinate itself changes along a photon characteristic.

Introduce a unit spatial direction $n^\mu$ in the material tetrad,

$$
U_\mu n^\mu=0,
\qquad
n_\mu n^\mu=1,
\tag{3}
$$

and the dimensionless null direction

$$
\ell^\mu:=\frac{U^\mu}{c_\gamma}+n^\mu,
\qquad
\ell_\mu\ell^\mu=0.
\tag{4}
$$

For specific intensity $I_{\nu_0}(n)$, define the spectral stress and third angular moment in the local material tetrad by

$$
\boxed{
R_{(\nu_0)}^{\alpha\beta}
:=\frac1{c_\gamma}\int_{4\pi}
I_{\nu_0}\ell^\alpha\ell^\beta\,d\Omega_0,}
\tag{5}
$$

$$
\boxed{
M_{(\nu_0)}^{\alpha\beta\gamma}
:=\frac1{c_\gamma}\int_{4\pi}
I_{\nu_0}\ell^\alpha\ell^\beta\ell^\gamma\,d\Omega_0.}
\tag{6}
$$

Their time, mixed and spatial projections give spectral energy, flux, pressure and third spatial moment. In particular,

$$
E_{\nu_0}=R^{00}_{(\nu_0)},
\qquad
\frac{F^i_{\nu_0}}{c_\gamma}=R^{0i}_{(\nu_0)},
\qquad
P^{ij}_{\nu_0}=R^{ij}_{(\nu_0)},
\tag{7}
$$

in an orthonormal material tetrad.

Differentiating (1) along a collisionless photon path gives

$$
\frac{d\nu_0}{d\lambda}
=-\frac1h p^\gamma p^\beta\nabla_\gamma U_\beta.
\tag{8}
$$

The symmetric photon product removes the antisymmetric vorticity contribution. Expansion, shear and material acceleration can change $\nu_0$; the angular part of the same change aberrates $n^\mu$.

Multiplying the invariant Boltzmann equation by photon four-momentum and integrating over directions at fixed $\nu_0$ gives

$$
\boxed{
\nabla_\beta R_{(\nu_0)}^{\alpha\beta}
-\frac{\partial}{\partial\nu_0}
\left[
\nu_0M_{(\nu_0)}^{\alpha\beta\gamma}
\nabla_\gamma\!\left(\frac{U_\beta}{c_\gamma}\right)
\right]
=S_{(\nu_0)}^\alpha.}
\tag{9}
$$

Here $S_{(\nu_0)}^\alpha$ is four-momentum added to radiation by emission, absorption and scattering. Equation (9) is the spectral conservation law. The derivative term includes the changes of frequency and angle induced by the moving material tetrad; it is therefore safer than attaching selected Doppler source terms to separate energy and momentum equations.

A spatially uniform, time-independent boost has $\nabla_\gamma U_\beta=0$ and no frequency-space evolution. It changes the components and observed spectrum through a Lorentz transformation, treated in §7.

## 3. Conservative group equation

Integrating (9) converts the continuous frequency derivative into two boundary fluxes. Define

$$
R_g^{\alpha\beta}
:=\int_{\nu_{g-1/2}}^{\nu_{g+1/2}}
R_{(\nu_0)}^{\alpha\beta}\,d\nu_0,
\qquad
S_g^\alpha
:=\int_{\nu_{g-1/2}}^{\nu_{g+1/2}}
S_{(\nu_0)}^\alpha\,d\nu_0,
\tag{10}
$$

and orient the frequency-space four-momentum flux toward increasing $\nu_0$:

$$
\boxed{
\Phi_\nu^\alpha
:=-\nu_0M_{(\nu_0)}^{\alpha\beta\gamma}
\nabla_\gamma\!\left(\frac{U_\beta}{c_\gamma}\right).}
\tag{11}
$$

The group equation is

$$
\boxed{
\nabla_\beta R_g^{\alpha\beta}
+\Phi_{g+1/2}^\alpha
-\Phi_{g-1/2}^\alpha
=S_g^\alpha.}
\tag{12}
$$

The value at $g+1/2$ is evaluated once and applied with opposite signs to groups $g$ and $g+1$. Summing all groups gives

$$
\boxed{
\nabla_\beta\sum_{g=1}^{N}R_g^{\alpha\beta}
+\Phi_{N+1/2}^\alpha
-\Phi_{1/2}^\alpha
=\sum_{g=1}^{N}S_g^\alpha.}
\tag{13}
$$

Every internal edge cancels component by component. If the represented spectrum satisfies

$$
\lim_{\nu_0\to0}\nu_0M_{(\nu_0)}^{\alpha\beta\gamma}=0,
\qquad
\lim_{\nu_0\to\infty}\nu_0M_{(\nu_0)}^{\alpha\beta\gamma}=0,
\tag{14}
$$

then the outer terms vanish and (13) becomes the bolometric radiation equation. Matter receives the exact negative collision source,

$$
\boxed{
\nabla_\beta T_{\rm matter}^{\alpha\beta}
=-\sum_gS_g^\alpha,}
\tag{15}
$$

so

$$
\boxed{
\nabla_\beta
\left(T_{\rm matter}^{\alpha\beta}+\sum_gR_g^{\alpha\beta}\right)=0}
\tag{16}
$$

when (14) holds and external boundaries supply no four-momentum.

The Doppler edge flux in (12) is a redistribution of the spectral representation. It is not an additional collision four-force. Adding its material-frame pressure term independently to matter would double-count exchange. A finite frequency interval that violates (14) must carry the outer-edge term as a spectral-domain ledger or include explicit tail groups.

## 4. Nonrelativistic affine-flow reduction

The leading-order form shows the sign and the implementable edge quantity. Let

$$
A_{ij}:=\partial_j u_i,
\qquad
\beta:=\frac{|u|}{c_\gamma}\ll1,
\tag{17}
$$

and neglect material acceleration during one local frequency update. Projecting the time component of (9) into the instantaneous material frame gives

$$
\boxed{
\partial_tE_\nu
+\nabla\cdot(uE_\nu+F_\nu)
+P_\nu:A
-\partial_\nu[\nu(P_\nu:A)]
=S_\nu^E+O(\beta^2).}
\tag{18}
$$

The group form is

$$
\boxed{
\partial_tE_g
+\nabla\cdot(uE_g+F_g)
+P_g:A
+\Phi^E_{g+1/2}-\Phi^E_{g-1/2}
=S_g^E+O(\beta^2),}
\tag{19}
$$

where

$$
\boxed{
\Phi^E_\nu=-\nu(P_\nu:A).}
\tag{20}
$$

The pressure term and frequency derivative belong to the same material-frame projection. Their bolometric combination agrees with the frequency-integrated covariant equation after the radiation tensor is transformed to the simulation frame.

For one ordinate whose direction changes negligibly during the substep, the frequency characteristic is

$$
\boxed{
\frac{d\ln\nu_0}{dt}
=-n_in_jA_{ij}+O(\beta^2).}
\tag{21}
$$

The fuller first-order characteristic contains material acceleration $a=D_tu$,

$$
\frac{d\ln\nu_0}{dt}
=-\frac{n\cdot a}{c_\gamma}
-n_in_jA_{ij}+O(\beta^2),
\tag{22}
$$

with a corresponding angular-aberration characteristic. Equation (9) retains both terms without splitting them by hand.

### 4.1 Isotropic expansion and compression

For

$$
A=H\mathbf1,
\qquad
\nabla\cdot u=3H,
\qquad
P_\nu=\frac{E_\nu}{3}\mathbf1,
\tag{23}
$$

one obtains

$$
P_\nu:A=HE_\nu,
\qquad
\boxed{\Phi^E_\nu=-H\nu E_\nu.}
\tag{24}
$$

Expansion has $H>0$ and a negative frequency velocity, so photons cross group edges toward the red. Compression has $H<0$ and moves them toward the blue.

With $a(t)=e^{Ht}$, the collisionless homogeneous solution is

$$
\boxed{E_\nu(t,\nu)=a^{-3}E_{\nu,0}(a\nu).}
\tag{25}
$$

Direct integration gives

$$
\boxed{
E_\gamma(t)=a^{-4}E_\gamma(0),
\qquad
N_\gamma(t)=a^{-3}N_\gamma(0).}
\tag{26}
$$

The first relation is the redshift plus volume-dilution law; the second is photon-number dilution. For a material volume $V(t)=a^3V_0$, the exact extensive energy in group $g$ is

$$
\boxed{
U_g(t)
:=V(t)E_g(t)
=\frac{V_0}{a}
\int_{a\nu_{g-1/2}}^{a\nu_{g+1/2}}
E_{\nu,0}(s)\,ds.}
\tag{27}
$$

At $t=0$,

$$
\boxed{
\dot U_g
=-HU_g
+HV[\nu E_\nu]_{g-1/2}^{g+1/2}.}
\tag{28}
$$

Equation (28) separates the material-frame bolometric pressure contribution from radiation crossing the two group edges. Summing groups cancels every internal edge. The change in material-frame energy is frame dependent; lab-frame four-momentum and the collision pairing in (15)–(16) remain the conservation statement.

## 5. Angular closure at a frequency edge

P4c requires one rank more than a gray two-moment equation because (11) contains $M^{\alpha\beta\gamma}_{(\nu)}$.

### 5.1 Discrete ordinates

For positive ordinates $(n_m,w_m)$, define

$$
\ell_m^\mu:=\frac{U^\mu}{c_\gamma}+n_m^\mu.
\tag{29}
$$

Then

$$
\boxed{
R_{(\nu)}^{\alpha\beta}
=\frac1{c_\gamma}\sum_mw_mI_{\nu m}
\ell_m^\alpha\ell_m^\beta,}
\tag{30}
$$

$$
\boxed{
M_{(\nu)}^{\alpha\beta\gamma}
=\frac1{c_\gamma}\sum_mw_mI_{\nu m}
\ell_m^\alpha\ell_m^\beta\ell_m^\gamma.}
\tag{31}
$$

The third moment is therefore explicit for the multi-angle state already defined in `turbulence/compressible-radiative-plasma-closure.md` §6. Frequency reconstruction is applied to each nonnegative $I_{gm}$, and the same reconstructed edge state generates every component of $\Phi^\alpha$.

The direction also aberrates as the material tetrad changes. A transport implementation may update the complete angular phase-space flux, or remap directions between adjacent tetrads before evaluating (30)–(31). Holding $n_m$ fixed while retaining the frequency part alone is qualified only in controls where the angular characteristic vanishes by symmetry or is higher order.

### 5.2 Moment methods

A two-moment state supplies $E_\nu$, $F_\nu$ and a closed $P_\nu$. Its frequency-momentum flux additionally needs the third spatial moment

$$
Q_\nu^{ijk}
:=\frac1{c_\gamma}
\int n_in_jn_kI_\nu\,d\Omega.
\tag{32}
$$

A moment implementation must declare a realizable angular distribution whose first three moments generate $F_\nu$, $P_\nu$ and $Q_\nu$ at each reconstructed frequency edge. For M1, that distribution is the same maximum-entropy or radiation-rest-frame distribution used to close $P_\nu$; evaluating (31) by a positive angular quadrature supplies $Q_\nu$ consistently. A separately chosen third-moment formula would define a different closure and needs its own realizability and diffusion/free-streaming qualification.

Group-centred $P_g$ cannot determine the two edge spectra. P4c therefore requires both:

1. an intragroup frequency reconstruction that produces one edge spectral state; and
2. an angular closure that produces the third moment of that same state.

## 6. Conservative frequency discretization

The numerical state uses group-integrated conserved quantities. For a spatial control volume $V_i$, denote its group four-momentum by $Q_{ig}^\alpha$. The frequency-only finite-volume update is

$$
\boxed{
Q_{ig}^{\alpha,n+1}
=Q_{ig}^{\alpha,n}
-\Delta t\,V_i
\left(
\widehat\Phi_{i,g+1/2}^{\alpha}
-\widehat\Phi_{i,g-1/2}^{\alpha}
\right).}
\tag{33}
$$

A single stored or identically evaluated $\widehat\Phi_{i,g+1/2}^\alpha$ is used by both neighbors. Independent left and right evaluations can differ at roundoff or after limiting and do not satisfy the discrete telescoping identity.

For the isotropic affine control, the characteristic speed is

$$
a_\nu=-H\nu.
\tag{34}
$$

Piecewise-constant upwinding gives

$$
\widehat\Phi^E_{g+1/2}
=-H\nu_{g+1/2}E_{\nu,g+1/2}^{\rm up},
\tag{35}
$$

where expansion samples the higher-frequency cell and compression samples the lower-frequency cell. For extensive material-frame group energy, (19) gives

$$
\boxed{
U_g^{n+1}
=U_g^n
-\Delta t\,HU_g^n
-\Delta t\,V
(\widehat\Phi^E_{g+1/2}-\widehat\Phi^E_{g-1/2}).}
\tag{36}
$$

The first-order reference operator subcycles under

$$
\boxed{
\Delta t
\max_g
\frac{|H|\nu_{g+1/2}}{\Delta\nu_g}
\leq C_{\rm CFL}.}
\tag{37}
$$

A production solver can use monotone piecewise-linear or higher-order reconstruction. It must preserve nonnegative intensity or a realizable moment state, use the same edge flux for adjacent groups, and converge under both time-step and spectral refinement.

### 6.1 Outer frequency boundaries

A finite spectral grid needs an explicit low- and high-frequency policy:

- a tail group whose reconstruction enforces (14);
- an analytic tail integral with its four-momentum retained in the state;
- or an open spectral boundary whose outgoing $\Phi^\alpha$ is accumulated in a ledger.

Zeroing an edge flux while resolved radiation reaches that edge traps energy in the terminal group. Discarding it without a ledger breaks (13). Inflow through an outer frequency edge requires a declared external spectrum.

### 6.2 Operator order

One accepted coupled step has four distinct transactions:

1. spatial radiation transport in the chosen simulation frame;
2. conservative frequency-and-angle phase-space transport from (9)–(12);
3. material-frame emission, absorption, scattering and population exchange;
4. the exact negative collision four-force applied to material.

The frequency transaction changes group membership. The collision transaction changes total radiation four-momentum and is the only local transaction paired to matter. Strang splitting or a coupled implicit method may be used, but the measured order and stiff-limit behavior belong to the qualification.

## 7. Spectral conversion to an inertial observer

Transport groups are labelled by $\nu_0$, while a camera measures an observer frequency $\nu$. Let the material have velocity $\beta=u/c_\gamma$ relative to the observer and let $n$ be the photon direction in that observer frame. Then

$$
\boxed{
\nu=D\nu_0,
\qquad
D:=\frac{1}{\gamma(1-n\cdot\beta)}.}
\tag{38}
$$

Liouville invariance gives

$$
\boxed{
\frac{I_\nu}{\nu^3}
=\frac{I_{\nu_0}^{(0)}}{\nu_0^3},
\qquad
d\Omega=D^{-2}d\Omega_0.}
\tag{39}
$$

Therefore

$$
\boxed{I_\nu(n)=D^3I_{\nu_0}^{(0)}(n_0),}
\tag{40}
$$

and the observer energy in a fixed group is

$$
\boxed{
I_g(n)
=D^4
\int_{\nu_{g-1/2}/D}^{\nu_{g+1/2}/D}
I_{\nu_0}^{(0)}(n_0)\,d\nu_0.}
\tag{41}
$$

Equation (41) is a spectral remap. Relabelling a material-frame group with the same observer index misses radiation shifted across the observer's boundaries. The angular direction $n_0$ is obtained by aberration and the camera response is applied only after the shifted spectral integral is formed.

The material coefficients use their covariant invariants:

$$
\frac{j_\nu}{\nu^2}
\quad\text{and}\quad
\nu\alpha_\nu
\tag{42}
$$

are invariant, while $I_\nu/\nu^3$ obeys (39). This keeps emission, absorption and observation in one frame convention.

## 8. Coupling and runtime invariants

The complete moving multigroup state retains:

- ordered material-frame group edges and tail policy;
- group stress-energy or a realizable angular/moment representation;
- intragroup reconstruction identity;
- angular third-moment closure identity;
- material four-velocity and the gradient/tetrad data used for each accepted frequency update;
- collision four-force and its paired material increment;
- internal and outer frequency-edge flux ledgers;
- simulation-frame and observer-frame conversion metadata.

At every accepted step require:

$$
\sum_g
(\widehat\Phi_{g+1/2}^\alpha-
\widehat\Phi_{g-1/2}^\alpha)
=
\widehat\Phi_{N+1/2}^\alpha-
\widehat\Phi_{1/2}^\alpha
\tag{43}
$$

for all four components, and

$$
\boxed{
\Delta P_{\rm matter}^\alpha
+\sum_g\Delta P_{g,{\rm collision}}^\alpha=0.}
\tag{44}
$$

Equation (43) diagnoses frequency-space conservation. Equation (44) diagnoses physical matter–radiation exchange. They test different transactions and must be reported separately.

For a discrete-ordinates state, positivity means $I_{gm}\geq0$. For a two-moment state, require

$$
E_g\geq0,
\qquad
|F_g|\leq c_\gamma E_g,
\qquad
P_g\succeq0,
\qquad
\operatorname{tr}P_g=E_g.
\tag{45}
$$

Clipping a failed state can alter the edge ledger. Step rejection, subcycling or a conservative realizability-preserving limiter is required.

## 9. CassiCosmos P4c interface

The conditional P4c implementation boundary is now explicit. A transport descriptor must provide:

- material-frame frequency edges and physical units;
- the simulation frame and observer frame;
- spatial and temporal discretizations;
- material velocity and covariant-gradient reconstruction;
- an $S_N$ representation or a named moment/third-moment closure;
- intragroup edge reconstruction and limiter;
- spectral outer-boundary/tail behavior;
- source splitting and accepted-step semantics;
- checkpoint identities for all of the above.

The source coefficients and LTE populations remain material-frame quantities supplied by `turbulence/cassi-radiative-material-closure.md` and `turbulence/compressible-radiative-plasma-closure.md`. P4c supplies their moving spectral transport. It does not supply the Cassi-to-baryonic material map, EOS, physical species, atomic tables or initial temperature.

The production qualification must include:

1. zero-gradient and uniform-boost nulls;
2. redshift in expansion and blueshift in compression;
3. a feature crossing several group boundaries;
4. shared-edge four-momentum telescoping;
5. outer-tail accounting;
6. boosted LTE with collision-source balance;
7. spatial, temporal, spectral and angular refinement;
8. the declared range of $\beta$, optical depth $\tau$ and $\beta\tau$;
9. comparison of material-frame transport with observer-frame spectra;
10. the full material/radiation collision ledger.

P4c is a derived conditional capability at the equation and reference-operator level. A live implementation becomes supported only over the velocity, opacity, angular and spectral ranges exercised by those production controls.

## 10. Tested reference controls

The fixed schedule is registered in `computations/moving-multigroup-radiation-prereg.md`. Its verifier checks the group integral, four-component telescoping, the exact homogeneous expansion/compression solution, photon-number and energy scalings, nonnegative upwind refinement, Lorentz spectral invariants, observer-group remapping and malformed-state rejection.

The verification status remains pending until a source-snapshotted immutable receipt is produced. The receipt supports only the displayed conditional equations and reference kernels.

## 11. Epistemic boundary

### 11.1 Derived conditional results

The following statements follow from the stated frame and closure assumptions:

- material-frame frequency changes along photon characteristics according to the material four-velocity gradient;
- the spectral stress equation contains a conservative frequency derivative of a third angular moment;
- group integration produces one four-momentum flux at each frequency edge;
- internal edge fluxes telescope exactly when adjacent groups share the same evaluated flux;
- the group sum recovers the bolometric covariant equation when outer spectral flux vanishes;
- isotropic expansion redshifts the spectrum with $E_\gamma\propto a^{-4}$ and $N_\gamma\propto a^{-3}$;
- observer spectra follow from the Lorentz invariance of $I_\nu/\nu^3$;
- discrete ordinates provide the required third moment directly, while a moment solver needs a declared third-moment closure.

### 11.2 Constitutive and numerical inputs

The closure imports or selects:

- $c_\gamma$ and the spacetime metric;
- material velocity and its resolved gradient;
- group edges, tail policy and intragroup reconstruction;
- angular quadrature or moment closure;
- spatial/time integrator, limiter and tolerances;
- material emissivity, opacity, scattering and population data.

These are declared model or numerical inputs. The derivation introduces no new primary Cassi framework parameter.

### 11.3 Open physical identification

The mapping from the Cassi field and particles to baryonic material, chemical species, thermodynamic temperature and electromagnetic matter remains open. P4c transports a supplied physical radiation state through a supplied moving material state. It does not identify either state from $E_Y$, $E_I$ or $q$.

## References

- `turbulence/cassi-radiative-material-closure.md`—material-frame transfer, M1 moments and covariant collision four-force
- `turbulence/compressible-radiative-plasma-closure.md`—compressible material, species, lines and discrete-ordinates state
- `computations/moving-multigroup-radiation-prereg.md`—frozen P4c analytical and numerical controls
- `computations/moving_multigroup_radiation.py`—reference frequency-edge and frame-conversion kernels
- `computations/verify_moving_multigroup_radiation.py`—source-snapshotted verifier
- P. Anninos and P. C. Fragile, [Multi-Frequency General Relativistic Radiation-Hydrodynamics with $M_1$ Closure](https://arxiv.org/abs/2007.12195)—covariant spectral moment equation and conservative frequency advection
- D. Mihalas and B. Weibel-Mihalas, *Foundations of Radiation Hydrodynamics*—comoving-frame transfer and moment equations
- S. W. Davis, J. M. Stone and Y.-F. Jiang, [A Radiation Transfer Solver for Athena Using Short Characteristics](https://doi.org/10.1088/0067-0049/199/1/9)—angular transport in moving radiation-hydrodynamic calculations
