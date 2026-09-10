# Radiative Material Closure for CassiCosmos

## Status: Derived conditional LTE transfer, conservation and entropy identities / Tested numerical kernels / Hypothesized Cassi material map—September 2026

## Abstract

A radiative material needs more state than visible color. It needs thermal energy, photon energy and flux, absorption, scattering, an equation of state or heat capacity, and a rule that transfers energy and momentum between matter and radiation. This paper supplies one closed conditional model: established photon transfer with LTE Planck emission and Kirchhoff detailed balance, frequency-group moments with an M1 angular closure, and conservative coupling to the selected Cassi capillary and thermal fluid. The local source conserves total four-momentum, produces entropy, recovers free streaming and optically thick diffusion, and has a positive energy-conservative implicit update.

The photon law and material coefficients are constitutive inputs. The canonical real-density pair $(E_Y,E_I)$ does not determine temperature, physical mass density, opacity, ionization, electric charge or an electromagnetic current. The optional gauge extension identifies a massless gauge direction while leaving the density-to-current map open. The result therefore provides a simulation-ready radiative-material architecture once physical units and material data are supplied; electromagnetic radiation remains outside the canonical-fluid PDE alone.


## 1. What the model must carry

Radiation becomes dynamical when emitted energy leaves one cell, crosses the domain, deposits momentum elsewhere and heats or cools the receiving material. A color ramp can display structure without performing any of those exchanges. A physical closure must retain the following quantities.

| Sector | Required state or input | Role |
|---|---|---|
| Material | velocity $u$, composition $c$, temperature $T>0$ | Motion, Yang/Yin fraction and thermal state |
| Material normalization | physical inertia density $\rho_m$ or direct per-length coefficients | Converts normalized simulation content into material units |
| Thermodynamics | internal energy $e_{\rm th}(T,c,\rho_m)$ and equation of state or heat capacity | Converts radiative heating into temperature and pressure |
| Radiation | energy $E_g\geq0$ and flux $F_g$ for every frequency group $g$ | Propagating photon energy and momentum |
| Material response | true absorption $\alpha_g^{\rm a}$ and transport extinction $\alpha_g^{\rm tr}$ | Thermal exchange and angular relaxation |
| Spectral definition | fixed physical group boundaries $\nu_{g-1/2}$ | Distinguishes infrared, visible, ultraviolet and higher-energy radiation |
| Boundaries | incoming intensity or moment data | Vacuum escape, periodic controls or an external radiation bath |

The selected Cassi fluid in `turbulence/cassi-fluid-feasibility.md` §7 already supplies a conditional constant-density state $(u,c,T)$, composition energy $e_c$, heat capacity $C$, conductivity $k_T$, viscosity $\eta$ and conversion heat. It is the material side used below. A compressible plasma or stellar gas additionally requires mass continuity and an equation of state $p(\rho_m,T,c)$ with ionization energy. Section 12 states that extension explicitly.

The symbol $c_\gamma$ denotes the speed of light throughout this paper. The unadorned $c$ remains the material composition fraction.


## 2. LTE emissive radiation

Thermal emission has a fixed equilibrium spectrum once a physical temperature is known. For $T>0$, its form follows from the equilibrium photon mode count.

In a large cavity, electromagnetic modes including both transverse
polarizations have density

$$
\frac{dN_{\rm mode}}{V\,d\nu}
=\frac{8\pi\nu^2}{c_\gamma^3}.
$$

The Bose occupation of one mode is
$\bar n_\nu=[\exp(h\nu/k_BT)-1]^{-1}$, so its thermal energy is
$h\nu\bar n_\nu$. The zero-point term is independent of $T$ and does not
participate in thermal emission. The spectral energy density is therefore

$$
u_\nu(T)
=\frac{8\pi h\nu^3}{c_\gamma^3}
\frac{1}{\exp[h\nu/(k_BT)]-1}.
$$

An isotropic field satisfies
$u_\nu=c_\gamma^{-1}\int_{4\pi}I_\nu\,d\Omega
=4\pi B_\nu/c_\gamma$. Solving for its equilibrium specific intensity gives

$$
\boxed{
B_\nu(T)=\frac{2h\nu^3}{c_\gamma^2}
\frac{1}{\exp[h\nu/(k_BT)]-1}.}
$$

Let $\alpha_\nu^{\rm a}\geq0$ be true absorption per unit length. Local thermodynamic equilibrium imposes Kirchhoff detailed balance:

$$
\boxed{j_\nu^{\rm a}=\alpha_\nu^{\rm a}B_\nu(T).}
$$

Here $j_\nu^{\rm a}$ is emitted energy per volume, time, solid angle and frequency. Absorption and spontaneous plus stimulated emission cancel mode by mode when $I_\nu=B_\nu(T)$. This equality fixes emissivity once temperature and absorption are supplied. An independent brightness multiplier would break thermal equilibrium and the energy ledger.

Using $x=h\nu/(k_BT)$ and
$\int_0^\infty x^3/(e^x-1)\,dx=\pi^4/15$, the frequency integral is

$$
\int_0^\infty B_\nu(T)\,d\nu
=\frac{\sigma_{\rm SB}}{\pi}T^4,
$$

so a gray volume emits

$$
\boxed{
\dot e_{\rm emit}
=4\pi\alpha^{\rm a}\int_0^\infty B_\nu\,d\nu
=4\alpha^{\rm a}\sigma_{\rm SB}T^4
=c_\gamma\alpha^{\rm a}a_{\rm R}T^4,}
$$

with

$$
a_{\rm R}=\frac{4\sigma_{\rm SB}}{c_\gamma}
=\frac{8\pi^5k_B^4}{15h^3c_\gamma^3}.
$$

The emitted power is a debit from material energy. Absorbed intensity is a credit. A persistent emitter therefore needs an energy source such as stored thermal energy, compression, accretion or a declared reaction network.

### 2.1 Spectral groups

For fixed physical frequency edges, define

$$
E_g^{\rm LTE}(T)
=\frac{4\pi}{c_\gamma}
\int_{\nu_{g-1/2}}^{\nu_{g+1/2}}B_\nu(T)\,d\nu.
$$

Writing $x=h\nu/(k_BT)$ gives

$$
\boxed{
E_g^{\rm LTE}(T)=a_{\rm R}T^4w_g(T),
\qquad
w_g(T)=\frac{15}{\pi^4}
\int_{x_{g-1/2}(T)}^{x_{g+1/2}(T)}
\frac{x^3}{e^x-1}\,dx.}
$$

Groups spanning $[0,\infty)$ satisfy $\sum_gw_g(T)=1$. Fixed frequency edges make the weights temperature-dependent. Freezing the weights while $T$ changes represents a different, approximate spectrum and must be measured as such.

A gray model evolves the sum $E=\sum_gE_g$. It closes bolometric heating and cooling but carries no physical color. A multigroup model is required when opacity varies strongly with frequency, when the radiation and material temperatures differ appreciably, or when the image must respond to a transported spectrum.


## 3. Absorption, scattering and optical depth

Opacity is a material property. If a physical mass density $\rho_{\rm phys}$ and mass opacity $\kappa_\nu$ are known, the per-length coefficient is

$$
\alpha_\nu=\rho_{\rm phys}\kappa_\nu.
$$

CassiCosmos can instead accept $\alpha_\nu$ directly. This is the safer interface while its particle and field densities remain normalized simulation content. A proposed $E_Y,E_I$-to-$\rho_{\rm phys}$ conversion must establish units and conserved mass before it enters this equation.

True absorption changes photon energy into material internal energy. Elastic scattering redirects photons. For a scattering phase function $p_\nu(n,n')$ normalized by

$$
\int_{4\pi}p_\nu(n,n')\,d\Omega=1,
$$

the transport coefficient is

$$
\boxed{
\alpha_\nu^{\rm tr}
=\alpha_\nu^{\rm a}
+\alpha_\nu^{\rm s}(1-\langle\cos\theta\rangle_\nu).}
$$

Forward scattering has less momentum-relaxing power than isotropic scattering. Setting the anisotropy factor to zero gives $\alpha^{\rm tr}=\alpha^{\rm a}+\alpha^{\rm s}$.

Optical depth along a ray is dimensionless:

$$
\tau_\nu(s_0,s_1)=\int_{s_0}^{s_1}\alpha_\nu(s)\,ds.
$$

For constant temperature and pure absorption/emission across one segment,

$$
\boxed{
I_{\nu,\rm out}
=I_{\nu,\rm in}e^{-\Delta\tau_\nu}
+B_\nu(T)(1-e^{-\Delta\tau_\nu}).}
$$

This exact cell solution has the required limits: transparent cells transmit the incoming intensity, opaque cells approach the local source function, and consecutive cells with the same source function compose by adding optical depth. Numerically, $1-e^{-\Delta\tau}$ should be evaluated as $-\operatorname{expm1}(-\Delta\tau)$ to retain precision in thin cells.

For scattering, the local source function becomes

$$
S_\nu
=\frac{\alpha_\nu^{\rm a}B_\nu
+\alpha_\nu^{\rm s}\int p_\nu(n,n')I_\nu(n')\,d\Omega'}
{\alpha_\nu^{\rm a}+\alpha_\nu^{\rm s}}.
$$

The same formal segment solution applies when coefficients and $S_\nu$ are held constant during the segment.


## 4. The transfer equation

In the instantaneous material rest frame, the spectral angular field obeys

$$
\boxed{
\frac{1}{c_\gamma}\partial_tI_\nu+n\cdot\nabla I_\nu
=\alpha_\nu^{\rm a}[B_\nu(T)-I_\nu]
+\alpha_\nu^{\rm s}
\left[\int_{4\pi}p_\nu(n,n')I_\nu(n')\,d\Omega'-I_\nu(n)\right].}
$$

This equation is the radiative state law. Its left side transports intensity at $c_\gamma$. Its first collision term creates or destroys photons through thermal matter. Its second collision term redistributes direction while conserving rest-frame radiative energy for elastic scattering.

Direct angular transport is expensive on a three-dimensional GPU grid. The moment reduction below retains energy and flux in each frequency group and closes the missing pressure tensor algebraically.


## 5. Frequency-group moments

Define the energy, flux and pressure of group $g$ by

$$
E_g=\frac1{c_\gamma}\int_g\!\int_{4\pi}I_\nu\,d\Omega d\nu,
$$

$$
F_g=\int_g\!\int_{4\pi}nI_\nu\,d\Omega d\nu,
\qquad
P_g=\frac1{c_\gamma}\int_g\!\int_{4\pi}n\otimes nI_\nu\,d\Omega d\nu.
$$

Groupwise coefficients are evaluated in the material frame.

The equations below adopt coefficients that are constant within each group during one transport and source update. This piecewise-gray choice is an explicit closure for the unresolved frequency dependence inside a group.

Writing the mean intensity as
$J_\nu=(4\pi)^{-1}\int_{4\pi}I_\nu\,d\Omega$, spectrally varying opacity gives
the exact integrated energy source

$$
c_\gamma\left[
\alpha_{{\rm P},g}E_g^{\rm LTE}
-\alpha_{{\rm E},g}E_g\right],
$$

where

$$
\alpha_{{\rm P},g}
=\frac{\int_g\alpha_\nu^{\rm a}B_\nu\,d\nu}
{\int_gB_\nu\,d\nu},
\qquad
\alpha_{{\rm E},g}
=\frac{\int_g\alpha_\nu^{\rm a}J_\nu\,d\nu}
{\int_gJ_\nu\,d\nu}.
$$

The energy-weighted coefficient depends on the unresolved intragroup radiation spectrum. More groups or an assumed intragroup shape are required when one constant coefficient is inadequate.

$$
\boxed{
\partial_tE_g+\nabla\cdot F_g
=c_\gamma\alpha_g^{\rm a}(E_g^{\rm LTE}-E_g),}
$$

$$
\boxed{
\partial_tF_g+c_\gamma^2\nabla\cdot P_g
=-c_\gamma\alpha_g^{\rm tr}F_g.}
$$

The radiation momentum density is $F_g/c_\gamma^2$. The flux-damping term therefore transfers force density $\alpha_g^{\rm tr}F_g/c_\gamma$ to matter.

A realizable angular distribution satisfies

$$
\boxed{E_g\geq0,
\qquad |F_g|\leq c_\gamma E_g,
\qquad P_g\succeq0,
\qquad \operatorname{tr}P_g=E_g.}
$$

These are evolution invariants and runtime diagnostics. Clamping an invalid flux can conceal a transport defect and changes momentum. A conservative implementation should use a realizability-preserving flux and reject or substep any local update that leaves the admissible set.


## 6. M1 angular closure

M1 reconstructs the pressure tensor from energy and flux. Set

$$
f_g=\frac{|F_g|}{c_\gamma E_g},
\qquad \hat F_g=\frac{F_g}{|F_g|},
$$

and

$$
\chi(f)=\frac{3+4f^2}{5+2\sqrt{4-3f^2}}.
$$

Then

$$
\boxed{
P_g=E_gD_g,
\qquad
D_g=\frac{1-\chi}{2}\mathbf1
+\frac{3\chi-1}{2}\hat F_g\otimes\hat F_g.}
$$

At zero flux, use $D_g=\mathbf1/3$. The two limiting regimes follow directly:

- $f=0$ gives $\chi=1/3$ and $P=E\mathbf1/3$, the isotropic pressure;
- $f=1$ gives $\chi=1$ and $P=E\hat F\otimes\hat F$, a free-streaming beam.

The transverse eigenvalues are $E(1-\chi)/2$ and the longitudinal eigenvalue is $E\chi$. They are nonnegative on $0\leq f\leq1$ and sum to $E$.

M1 merges counterpropagating or crossing beams into one local preferred direction. This is acceptable for a first radiative-material engine whose invariants and thermal exchange matter more than sharp shadows. A camera ray marcher can still use the transported emissivity and opacity for a view-dependent image. Scenes dominated by multiple hard sources require a higher angular method, ray packets or a hybrid source treatment.


## 7. Covariant matter–radiation exchange

The interaction must conserve energy and momentum in any chosen simulation frame. Use metric signature $(-,+,+,+)$ and a material four-velocity

$$
U^\mu U_\mu=-c_\gamma^2.
$$

For bolometric radiation, let $R^{\mu\nu}$ be the radiation stress tensor. The same form applies groupwise when each group's frequency support is defined in material-frame phase space and the transport includes all frequency-boundary terms. Denote such a group tensor by $R_g^{\mu\nu}$ and define its material-frame energy and flux by

$$
\mathcal E_g
=\frac{R_g^{\mu\nu}U_\mu U_\nu}{c_\gamma^2},
$$

$$
h^\mu{}_{\nu}
=\delta^\mu{}_{\nu}+\frac{U^\mu U_\nu}{c_\gamma^2},
\qquad
\mathcal F_g^\mu
=-h^\mu{}_{\alpha}R_g^{\alpha\beta}U_\beta.
$$

The projection gives $U_\mu\mathcal F_g^\mu=0$. The selected four-force density added to radiation is

$$
\boxed{
S_g^\nu
=\alpha_g^{\rm a}(E_g^{\rm LTE}-\mathcal E_g)
\frac{U^\nu}{c_\gamma}
-\alpha_g^{\rm tr}\frac{\mathcal F_g^\nu}{c_\gamma}.}
$$

Matter receives the exact negative:

$$
\boxed{
\nabla_\mu R_g^{\mu\nu}=S_g^\nu,
\qquad
\nabla_\mu T_{\rm matter}^{\mu\nu}
=-\sum_gS_g^\nu.}
$$

Therefore

$$
\boxed{
\nabla_\mu\left(T_{\rm matter}^{\mu\nu}
+\sum_gR_g^{\mu\nu}\right)=0.}
$$

In the material rest frame, $U^\mu=(c_\gamma,0)$, $\mathcal E_g=E_g$ and $\mathcal F_g^\mu=(0,F_g)$. The time projection becomes $c_\gamma\alpha_g^{\rm a}(E_g^{\rm LTE}-E_g)$ and the spatial projection becomes $-\alpha_g^{\rm tr}F_g/c_\gamma$, exactly matching the moment sources. An isotropic LTE tensor can be written

$$
R_{g,\rm LTE}^{\mu\nu}
=\frac{4E_g^{\rm LTE}}{3c_\gamma^2}U^\mu U^\nu
+\frac{E_g^{\rm LTE}}3g^{\mu\nu}.
$$

It has $\mathcal E_g=E_g^{\rm LTE}$ and $\mathcal F_g^\mu=0$, so the interaction vanishes in every inertial frame.

A GPU implementation can reconstruct $R^{\mu\nu}$ from lab-frame $(E,F,P)$, project into the cell's material frame, apply the local source and subtract the same four-momentum increment from matter. This avoids an incomplete hand-written selection of velocity-work terms. Mixed-frame transport still needs regime tests when $\beta\tau$ is appreciable, where $\beta=|u|/c_\gamma$.
Fixed frequency bins in a lab frame exchange energy through Doppler shifts when the material velocity varies. A moving multigroup solver must include that frequency-space transport; independently applying the gray four-force to fixed bins is incomplete. The bolometric sum has no internal frequency boundary and is the appropriate first covariant implementation.


## 8. Coupling to the selected Cassi thermal fluid

The existing conditional material closure uses

$$
e_m=\frac{\rho_m|u|^2}{2}+e_c+CT,
$$

$$
e_c=\frac a2(c-c_*)^2+\frac{g(c)}2|\nabla c|^2,
\qquad
A=g(c)\nabla c\otimes\nabla c,
$$

with composition rate $R=-M\mathcal A$ and chemical potential $\mu$. In one instantaneous material rest frame, the radiative source projections extend its equations to

$$
\nabla\cdot u=0,
$$

$$
\boxed{
\rho_mD_tu
=-\nabla p+\nabla\cdot(2\eta S)-\nabla\cdot A
+\sum_g\frac{\alpha_g^{\rm tr}}{c_\gamma}F_g,}
$$

$$
D_tc=R,
$$

$$
\boxed{
CD_tT
=k_T\Delta T+2\eta S:S-\mu R
+c_\gamma\sum_g\alpha_g^{\rm a}(E_g-E_g^{\rm LTE}).}
$$

Radiation hotter than matter has $E_g>E_g^{\rm LTE}$ and heats the material. Hotter matter has $E_g<E_g^{\rm LTE}$ and cools by emission. Elastic scattering appears in momentum exchange and contributes no material-frame thermal source at this order.

For moving material, the four-force in §7 governs the complete local exchange. The implementation updates material conserved energy and momentum by the negative radiation increment. Appending only the rest-frame heating and force terms to lab-frame equations omits velocity work and can violate total energy.

The composition and capillary identities remain unchanged. Radiation adds a transport channel to their energy ledger; it supplies no new rule for the canonical conversion mobility $M$.


## 9. Entropy production and equilibrium

Detailed balance makes thermal relaxation directional. Introduce the photon occupation number

$$
n_\nu=\frac{c_\gamma^2I_\nu}{2h\nu^3},
\qquad
n_{\nu,B}=\frac1{e^{h\nu/(k_BT)}-1}.
$$

The photon entropy density is

$$
s_\gamma
=\frac{2k_B}{c_\gamma^3}
\int_0^\infty\!\int_{4\pi}\nu^2
\left[(1+n_\nu)\log(1+n_\nu)-n_\nu\log n_\nu\right]
\,d\Omega d\nu.
$$

At fixed material state during the local collision calculation,

$$
\dot n_\nu
=c_\gamma\alpha_\nu^{\rm a}(n_{\nu,B}-n_\nu).
$$

Let

$$
g(n)=\log\frac{1+n}{n},
\qquad g'(n)=-\frac1{n(1+n)}<0.
$$

Adding the material entropy change from the equal-and-opposite heat transfer gives

$$
\boxed{
\dot s_{\rm material}+\dot s_\gamma
=\frac{2k_B}{c_\gamma^2}
\int\!\int\nu^2\alpha_\nu^{\rm a}
(n_{\nu,B}-n_\nu)
[g(n_\nu)-g(n_{\nu,B})]\,d\Omega d\nu
\geq0.}
$$

The product is nonnegative because $g$ is decreasing. Equality requires modewise LTE wherever $\alpha_\nu^{\rm a}>0$. Reciprocal elastic scattering increases the concave photon entropy as it isotropizes the angular distribution while preserving rest-frame energy.

### 9.1 Gray homogeneous reduction

For a gray isotropic radiation field, write

$$
E=a_{\rm R}T_r^4,
\qquad
s_r=\frac43a_{\rm R}T_r^3.
$$

The local thermal source is

$$
\dot E=c_\gamma\alpha^{\rm a}(a_{\rm R}T^4-E),
\qquad
C\dot T=c_\gamma\alpha^{\rm a}(E-a_{\rm R}T^4).
$$

It conserves $CT+E$. The entropy derivative is

$$
\boxed{
\frac{d}{dt}\left[C\log(T/T_*)+\frac43a_{\rm R}T_r^3\right]
=c_\gamma\alpha^{\rm a}a_{\rm R}(T^4-T_r^4)
\left(\frac1{T_r}-\frac1T\right)\geq0.}
$$

Indeed,

$$
(T^4-T_r^4)\left(\frac1{T_r}-\frac1T\right)
=(T-T_r)^2\frac{(T+T_r)(T^2+T_r^2)}{TT_r}.
$$

The unique equilibrium at fixed total energy $U$ solves

$$
\boxed{CT_{\rm eq}+a_{\rm R}T_{\rm eq}^4=U.}
$$

The left side is strictly increasing for $T\geq0$. This gives a direct equilibrium oracle for source-step verification.


## 10. Conservative stiff source update

Emission and absorption can be much faster than material motion. An explicit step then demands $\Delta t\ll(c_\gamma\alpha^{\rm a})^{-1}$. A local implicit solve removes that stability restriction while retaining positivity and exact total-energy pairing.

For one gray cell, set $\lambda=c_\gamma\alpha^{\rm a}\Delta t$. Backward Euler gives

$$
E^{n+1}
=\frac{E^n+\lambda a_{\rm R}(T^{n+1})^4}{1+\lambda},
$$

with the conservative constraint

$$
\boxed{CT^{n+1}+E^{n+1}=CT^n+E^n.}
$$

The scalar residual has derivative

$$
C+\frac{4\lambda a_{\rm R}(T^{n+1})^3}{1+\lambda}>0.
$$

Bisection on

$$
0\leq T^{n+1}\leq\frac{CT^n+E^n}{C}
$$

therefore finds one positive root. The corresponding $E^{n+1}$ is nonnegative. For multiple groups with coefficients held during the source step,

$$
E_g^{n+1}
=\frac{E_g^n+\lambda_gE_g^{\rm LTE}(T^{n+1})}{1+\lambda_g},
\qquad
\lambda_g=c_\gamma\alpha_g^{\rm a}\Delta t,
$$

and the same scalar conservation equation closes $T^{n+1}$. Every $E_g^{\rm LTE}(T)$ is increasing, so the residual remains monotone.

Elastic flux relaxation in a material-rest-frame source substep is exact for fixed coefficients:

$$
\boxed{
F_g^{n+1}=e^{-c_\gamma\alpha_g^{\rm tr}\Delta t}F_g^n,
\qquad
\Delta p_{\rm matter}
=\frac{F_g^n-F_g^{n+1}}{c_\gamma^2}.}
$$

The backward-Euler energy solve is first-order accurate. The fixed verification shows that stability alone is insufficient as an accuracy rule. Source subcycling or step doubling is required when the hydro step is too large. Each accepted substep preserves positivity and total energy.


## 11. Optically thick diffusion and opacity means

In an isotropic thick region, $P=E\mathbf1/3$ and the flux relaxes rapidly. Neglecting $\partial_tF$ in the flux equation gives

$$
\boxed{F=-\frac{c_\gamma}{3\alpha^{\rm tr}}\nabla E.}
$$

When opacity depends strongly on frequency, emission and diffusion use different means. For a mass opacity,

$$
\boxed{
\kappa_{\rm P}(T)
=\frac{\int_0^\infty\kappa_\nu^{\rm a}B_\nu(T)\,d\nu}
{\int_0^\infty B_\nu(T)\,d\nu}}
$$

weights true absorption by emitted power. The Rosseland mean

$$
\boxed{
\frac1{\kappa_{\rm R}}
=\frac{\int_0^\infty(\kappa_\nu^{\rm tr})^{-1}
(\partial B_\nu/\partial T)\,d\nu}
{\int_0^\infty(\partial B_\nu/\partial T)\,d\nu}}
$$

weights transparent channels most strongly and governs thick diffusion. A gray implementation should use $\kappa_{\rm P}$ for thermal energy exchange and $\kappa_{\rm R}$ for diffusive transport. Multigroup coefficients retain more of the spectrum and reduce reliance on a single mean.


## 12. Material data still required

The equations close mathematically once their constitutive functions are supplied. Physical radiative matter requires those functions to correspond to an actual material.

### 12.1 Constant-density material

The selected Cassi thermal fluid can use

$$
e_{\rm th}=CT,
\qquad C>0,
$$

with direct per-length tables

$$
\alpha_g^{\rm a}=\alpha_g^{\rm a}(T,c),
\qquad
\alpha_g^{\rm tr}=\alpha_g^{\rm tr}(T,c).
$$

This is enough for a controlled radiative capillary fluid and for a physically budgeted visualization prototype. Its pressure remains the incompressibility multiplier, so thermal expansion, shocks and stellar hydrostatic structure lie outside this branch.

### 12.2 Compressible gas or plasma

The complete conditional branch in
`turbulence/compressible-radiative-plasma-closure.md` evolves

$$
\partial_t\rho_m+\nabla\cdot(\rho_m u)=0,
$$

plus an equation of state and internal energy,

$$
p=p(\rho_m,T,\{n_i\}),
\qquad
e_{\rm int}=e_{\rm int}(\rho_m,T,\{n_i\}).
$$

The species populations $n_i$ determine ionization energy, electron density and opacity. Their rates have the form

$$
D_tn_i
=\sum_j(n_jR_{ji}-n_iR_{ij})
+\text{transport and reaction sources}.
$$

Tabulated EOS and opacity data are appropriate inputs for a production astrophysical model. Cassi supplies no atomic cross-sections from $\varphi$ or $q$.

That branch supplies conservative momentum and total-energy equations,
pressure work, shock jump conditions, finite population generators, a
stellar-source ledger and multi-angle transfer. Its 70-check reference
schedule and separate 25-check integrity qualification cover the conditional
equations, admissibility boundaries, exchange cancellation and prerequisite
classification. Its EOS and material coefficients still come from physical
constitutive data.

### 12.3 Non-LTE lines

Nebular lines, recombination spectra, masers and fluorescence require level populations beyond one temperature. For a bound transition $u\to l$ with normalized profile $\phi_{ul}(\nu)$,

$$
\boxed{
j_\nu^{ul}
=\frac{h\nu_{ul}}{4\pi}n_uA_{ul}\phi_{ul}(\nu),}
$$

$$
\boxed{
\alpha_\nu^{ul}
=\frac{h\nu_{ul}}{4\pi}
(n_lB_{lu}-n_uB_{ul})\phi_{ul}(\nu).}
$$

LTE populations recover the Planck source through the Einstein relations. Non-LTE populations require their own rate equations and energy debits. Population inversion can make the net line coefficient negative; that is an active-medium model with a separate stored-energy ledger and lies outside the nonnegative-opacity closure verified here.

`turbulence/compressible-radiative-plasma-closure.md` §§3–4 closes these
rates and their bound-bound and bound-free energy exchanges conditionally on
evaluated atomic data.


## 13. Unresolved particles and radiating surfaces

A point particle cannot acquire physical luminosity from mass alone. An unresolved spherical surface with radius $R_*$ and effective temperature $T_{\rm eff}$ has

$$
\boxed{
L_\nu=4\pi^2R_*^2B_\nu(T_{\rm eff}),
\qquad
L=4\pi R_*^2\sigma_{\rm SB}T_{\rm eff}^4.}
$$

An optically thin volume $V$ has

$$
L_\nu=4\pi j_\nu V.
$$

These describe different source geometries. A sink or star particle therefore needs at least $(R_*,T_{\rm eff})$ or a bolometric luminosity plus normalized spectrum, and its luminosity must be charged to a declared internal, accretion or reaction energy source. A gravitational particle's stored mass component supplies none of those quantities by itself.

When one emitter contributes to both a resolved volume and a point pass, use one partition $f_{\rm point}\in[0,1]$:

$$
L_{g,\rm point}=f_{\rm point}L_g,
\qquad
L_{g,\rm volume}=(1-f_{\rm point})L_g.
$$

The sum is the source luminosity and enters the radiation-energy grid once. Camera rendering may draw the point-spread function and volume separately, but it may not create a second copy of the energy.


## 14. Nondimensional form for CassiCosmos

Choose a length $L_0$, time $t_0$, temperature $T_0$ and radiation-energy scale

$$
E_0=a_{\rm R}T_0^4.
$$

Let

$$
\mathcal C=\frac{c_\gamma t_0}{L_0},
\qquad
\tau_{a,g}=\alpha_{a,g}L_0,
\qquad
\tau_{t,g}=\alpha_{t,g}L_0,
\qquad
\mathcal R=\frac{a_{\rm R}T_0^3}{C}.
$$

With $E_g=E_0E_g'$, $F_g=c_\gamma E_0F_g'$, $P_g=E_0P_g'$ and $T=T_0\Theta$, the rest-frame gray equations contain

$$
\partial_{t'}E'+\mathcal C\nabla'\cdot F'
=\mathcal C\tau_a(\Theta^4-E'),
$$

$$
\partial_{t'}F'+\mathcal C\nabla'\cdot P'
=-\mathcal C\tau_tF',
$$

$$
D_{t'}\Theta
=\text{material terms}
+\mathcal C\mathcal R\tau_a(E'-\Theta^4).
$$

The simulator therefore needs a physical unit map before $c_\gamma$, opacity and heat capacity can share one clock. Selecting a reduced transport speed changes the transient model. Such a speed can preserve a steady transfer solution while delaying propagation and diffusion. It should be an explicit numerical approximation with a convergence comparison, especially when $\beta\tau$ approaches unity.


## 15. CassiCosmos implementation contract

The current Observatory path already computes density, optical depth, segment attenuation, a bounded first-scattering cache and a camera ray integral. Its `emission`, `optical_thickness`, `scattering` and warm spectra are appearance controls. The point shader labels its mass-temperature color as a heuristic and disclaims blackbody interpretation. These components provide useful rendering infrastructure; the physical model requires persistent thermodynamic and radiation state upstream of them.

A clean implementation has the following sequence.

1. **Ship disabled.** `radiation_enabled=false` leaves the existing simulation and verification battery bit-identical.
2. **Allocate persistent state.** Store one positive temperature or internal-energy field, and per group one scalar $E_g$ plus one vector $F_g$. Derive $P_g$ from M1 at each use; no persistent pressure field is needed.
3. **Supply calibration.** Define $L_0,t_0,T_0$, material energy scale, physical density or direct $\alpha_g$, and fixed frequency boundaries. Refuse physical mode when the unit set is incomplete.
4. **Deposit sources once.** Resolved thermal emission and unresolved particle luminosity enter the same group-energy budget. Apply any point/volume partition exactly once.
5. **Advance transport conservatively.** Use a finite-volume M1 update with a realizability-preserving numerical flux. A Rusanov or HLL first implementation is adequate; Fourier collocation is poorly matched to positive hyperbolic transport and vacuum fronts.
6. **Apply local interactions.** Project moments to the material frame, solve the implicit energy exchange with source refinement, relax flux, and add the exact negative four-momentum increment to matter.
7. **Enforce boundaries.** Periodic boundaries serve numerical controls. Isolated scenes use zero incoming intensity or a declared external bath while allowing outgoing radiation to escape.
8. **Render from the state.** Ray integration reads group emissivity, opacity and transported incident radiation. Exposure, bloom and tone mapping remain read-only presentation operations.

A compact GPU layout for each group is one `R32F` energy image and one `RGBA32F` flux image. Temperature can use `R32F`; material energy may need higher precision in verification builds when radiation is a small correction to a large reservoir. Opacity can be evaluated from compact tables or cached per cell. Group-major dispatches improve contiguous access when the number of groups is small; cell-major packing reduces repeated material loads. A measured bandwidth comparison should select one layout; carrying both paths adds avoidable complexity.

### 15.1 Required runtime diagnostics

Every radiation step should report or accumulate:

- minimum $T$ and $E_g$;
- maximum reduced flux $|F_g|/(c_\gamma E_g)$;
- total material plus radiation energy;
- total material plus radiation momentum;
- emitted, absorbed and escaped energy by group;
- maximum and integrated optical depth;
- source-solver iterations and substeps;
- entropy change for closed relaxation controls;
- point/volume luminosity partition residual.

A camera image is evidence of appearance. The quantities above are evidence of radiative-material dynamics.

### 15.2 Spectral display

Transport groups should remain physical frequency intervals. To produce display color, integrate outgoing spectral radiance against a declared sensor response. For CIE tristimulus functions,

$$
X=\int L_\lambda\bar x(\lambda)\,d\lambda,
\quad
Y=\int L_\lambda\bar y(\lambda)\,d\lambda,
\quad
Z=\int L_\lambda\bar z(\lambda)\,d\lambda.
$$

A matrix converts $(X,Y,Z)$ to the chosen linear display space before exposure and tone mapping. Three ad hoc RGB coefficients can be retained as an appearance preset, while physical mode should identify its frequency bins and response curves. Infrared and ultraviolet energy still participates in heating even when the visible camera does not display it.


## 16. Verification result

The executable kernel is `computations/cassi_radiative_material.py`. The frozen comprehensive schedule is `computations/cassi-radiative-material-prereg.md`, and its verifier is `computations/verify_cassi_radiative_material.py`.

The comprehensive run records **33 of 34 passing checks**. The passing set includes:

- the Planck integral with relative error $1.37\times10^{-16}$;
- nine physical emissive-power comparisons with maximum relative error $3.96\times10^{-16}$;
- 7,007 M1 tensors with maximum trace error $8.88\times10^{-16}$ and minimum eigenvalue $-1.86\times10^{-16}$ from roundoff;
- 63 slab cases with maximum direct error $2.22\times10^{-16}$ and semigroup error $4.44\times10^{-16}$;
- exact stored total energy across 15 thermal-relaxation trajectories and entropy-step minimum $-8.88\times10^{-16}$;
- 30 scattering cases with momentum residual $1.11\times10^{-16}$;
- 21 diffusion cases with residual $1.78\times10^{-15}$;
- 1,681 photon-entropy pairs with nonnegative production;
- 16 moving-frame projections with normalized flux orthogonality error $8.26\times10^{-16}$ and boosted-LTE source $2.34\times10^{-16}$.

The failed check is a numerical accuracy target for backward Euler. The coolest initial state reaches normalized endpoint error $2.52712195192\times10^{-4}$ at $\Delta t=0.01$, above the fixed $5\times10^{-5}$ limit, while its measured refinement remains first order. The comprehensive receipt is therefore `FAIL`; it does not support using $0.01$ as the benchmark source step.

A separate fixed qualification in `computations/cassi-radiative-material-qualification-prereg.md` retains the same equation, coefficients, initial state, final time, reference solver and accuracy target. It changes only the predeclared substeps and reruns none of the passing comprehensive controls. `computations/verify_cassi_radiative_material_qualification.py` passes **9 of 9 checks**. Its errors are

$$
1.00334827107\times10^{-4},
\quad5.00417502348\times10^{-5},
\quad2.49893979281\times10^{-5}
$$

at $\Delta t=0.004,0.002,0.001$, with refinement ratios $2.0050$ and $2.0025$. The finest step meets the original target, total-energy drift is zero to stored precision, and every entropy step is positive. This supports source subcycling for the benchmark and leaves the comprehensive negative timestep verdict intact.

From the CassiTheory root, a non-evidence smoke run is

```text
python computations/cassi_radiative_material.py --time 2 --dt 0.001 \
  --temperature 0.2 --radiation-energy 0.5
```

The immutable local evidence paths are registered in `BROKEN_REFS.md`.


## 17. Epistemic boundary

### Derived conditional

- Planck integration, Kirchhoff equilibrium and the emissive-power formula under LTE photon physics;
- exact transfer moments under supplied group coefficients;
- M1 pressure eigenvalues, isotropic and free-streaming limits;
- covariant equal-and-opposite matter–radiation source and total four-momentum conservation;
- the spectral and gray entropy-production identities;
- uniqueness and positivity of the conservative implicit thermal source solve;
- the thick-diffusion limit and exact homogeneous-slab solution.

### Tested

- the numerical kernels and all listed analytical identities in the 33 passing comprehensive controls;
- the failed $\Delta t=0.01$ benchmark accuracy target;
- first-order source convergence and the passing $\Delta t=0.001$ qualification.

### Constitutive or external

- $c_\gamma,h,k_B,\sigma_{\rm SB}$ and established photon statistics;
- heat capacity, equation of state, absorption, scattering, line data and group boundaries;
- physical length, time, mass, temperature and energy units;
- any reduced-speed approximation.

### Open for Cassi

- a physical mass-density and temperature map from $(E_Y,E_I)$ or particle state;
- electromagnetic charge and current carried by a selected microscopic Cassi matter sector;
- a species and abundance identification with versioned atomic, opacity and nuclear data;
- an initial fuel, contraction or accretion history for each persistent emitter;
- a production compressible, moving-multigroup and multi-angle implementation with shock, $\beta\tau$ and angular-convergence qualification;
- a green default-off CassiCosmos GPU battery with energy, momentum, realizability and image receipts.

The constant-density M1 branch and its compressible multi-angle extension are
complete conditional systems. Physical interpretation begins when the unit
map, material identity, response tables and source history are supplied.


## References

- `turbulence/cassi-fluid-feasibility.md` §7—selected capillary and thermal material equations, energy flux and entropy production
- `computations/cassi-radiative-material-prereg.md`—fixed comprehensive LTE, M1, source and diffusion controls
- `computations/cassi_radiative_material.py`—reference Planck, M1, covariant source, slab and implicit-exchange kernels
- `computations/verify_cassi_radiative_material.py`—comprehensive 33/34 receipt generator
- `computations/cassi-radiative-material-qualification-prereg.md`—fixed source-subcycling qualification
- `computations/verify_cassi_radiative_material_qualification.py`—passing 9-check source qualification
- `turbulence/compressible-radiative-plasma-closure.md`—compressible hydrodynamics, species kinetics, stellar energy accounting and multi-angle transfer
- `computations/compressible-radiative-plasma-prereg.md`—fixed conservation, population, luminosity and crossing-beam controls
- `computations/compressible_radiative_plasma.py`—reference compressible radiative-plasma kernels
- `computations/verify_compressible_radiative_plasma.py`—70-check source-snapshotted verifier
- `computations/compressible-radiative-plasma-integrity-prereg.md`—fixed conservative-state, exchange, source-ledger and prerequisite qualification
- `computations/verify_compressible_radiative_plasma_integrity.py`—passing 25-check integrity qualification
- `standard-model/su2-gauge-extension.md` §§2–3—conditional gauge extension and photon null direction; electromagnetic current map remains open
- `foundations/dimensionful-constants-status.md`—external status of $c_\gamma$ and $\hbar$
- `computations/matter-formation-continuum-report.md` §§35–36, 66—scalar cloud radiation and scalar loop corrections, distinct from transported electromagnetic photons
- `CassiCosmos/compute/cassi_observatory_light.glsl`—current six-direction appearance illumination cache in the sibling simulation repo
- `CassiCosmos/compute/cassi_observatory_volume.glsl`—current camera attenuation and volume-emission pass in the sibling simulation repo
- `CassiCosmos/shaders/particle_billboard_observatory.gdshader`—current point-emission appearance path in the sibling simulation repo
- C. D. Levermore, [Relating Eddington factors to flux limiters](https://doi.org/10.1016/0022-4073(84)90112-2)—M1 Eddington factor and limiting structure
- B. Dubroca and J.-L. Feugeas, [Étude théorique et numérique d'une hiérarchie de modèles aux moments pour le transfert radiatif](https://doi.org/10.1016/S0764-4442(00)87499-6)—minimum-entropy moment closure
- D. Mihalas and B. Weibel-Mihalas, *Foundations of Radiation Hydrodynamics*—transfer, moments and material coupling
- M. R. Krumholz, R. I. Klein, C. F. McKee and J. Bolstad, [Equations and Algorithms for Mixed-Frame Flux-Limited Diffusion Radiation Hydrodynamics](https://doi.org/10.1086/520791)—mixed-frame energy accounting and dynamic-diffusion ordering
- S. Rosseland, [Note on the Absorption of Radiation within a Star](https://academic.oup.com/mnras/article/84/7/525/975098)—diffusion-weighted opacity
- A. Einstein, *Zur Quantentheorie der Strahlung*, Physikalische Zeitschrift 18, 121–128 (1917)—absorption, spontaneous emission and stimulated emission coefficients
