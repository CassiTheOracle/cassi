# Compressible Radiative Plasma and Stellar-Light Closure

## Status: Derived conditional / Tested reference controls and integrity qualification—September 2026

## Abstract

A physical luminous gas must conserve mass, momentum and energy while its density, pressure, species populations and radiation evolve. This paper closes that conditional system. It extends `turbulence/cassi-radiative-material-closure.md` with four pieces: compressible hydrodynamics and shock jump conditions; time-dependent ionization and excitation populations with line and continuum transfer; gravitational, accretion and nuclear energy ledgers for persistent stellar luminosity; and multi-angle discrete-ordinates transport that preserves distinct crossing beams.

The equations use established radiation hydrodynamics, atomic kinetics and stellar structure. Atomic level energies, transition probabilities, collision strengths, photoionization cross-sections, opacities, nuclear masses and reaction rates are constitutive data. The canonical Cassi variables do not determine those data or identify a chemical species. The result is therefore a complete conditional evolution law once a physical unit map, material inventory and data tables are supplied.

## 1. State and conventions

The evolved material state is a constrained conservative state. With specific internal energy $e$, specific total material energy $E=e+|u|^2/2$, species mass fractions $Y_s$ and level populations $n_{s\ell}$, the solved variables satisfy

$$
\boxed{
\mathcal U_{\rm mat}
:=\left(\rho,\rho u,\rho E,\{\rho Y_s\},\{n_{s\ell}\}\right),
\qquad
\rho Y_s=m_u\sum_{\ell\in\mathcal L_s}A_{s\ell}n_{s\ell}.}
\tag{1a}
$$

The radiation block is $\{E_g,F_g\}$ for a moment solve or $\{I_{gm}\}$ for the multi-angle solve. The species densities and level populations in (1a) are two representations of the same baryonic content, so only constrained states are admissible. Primitive variables such as $u$, $T$, $p$ and the level fractions are recovered through the equation of state and the population constraints. In particular,

- $\rho$ is conserved baryonic mass density;
- $u$ is material velocity;
- $Y_s$ is the mass fraction of transported material species $s$, with $\sum_sY_s=1$;
- $n_{s\ell}$ is the number density of internal, excitation or ionization level $\ell\in\mathcal L_s$ of species $s$; every positive-density transported species has at least one represented level, while a zero-density species may have none;
- $n_e$ is the free-electron number density;
- $T>0$ is material temperature;
- $E_g,F_g,P_g$ are the energy, flux and pressure tensor of radiation group $g$;
- $I_{gm}$ is the group-integrated intensity in discrete direction $n_m$ when multi-angle transport is enabled;
- $\Phi$ is the gravitational potential, with acceleration $g=-\nabla\Phi$.

The baryonic density uses a fixed mass unit rather than the reaction-dependent nuclear rest mass:

$$
\boxed{\rho=m_u\sum_i A_i n_i,}
\tag{1}
$$

where $A_i$ is the baryon number of state $i$. Equation (1) is the sum of the per-species constraints in (1a). Nuclear binding-energy release then belongs in the energy ledger without violating baryon continuity. The Newtonian inertia is $\rho$ at this order. A relativistic implementation must include the released energy in the stress-energy tensor rather than silently changing (1).

The speed of light is $c_\gamma$. The symbol $c$ remains the Yang/Yin composition fraction in the parent fluid paper.

## 2. Compressible material and shocks

Density changes become physical when the conservative mass, momentum and energy fluxes are evolved together. Pressure work then heats compression, cools expansion and supplies the correct shock jump conditions.

### 2.1 Mass and species continuity

Baryonic mass obeys

$$
\boxed{
\partial_t\rho+\nabla\cdot(\rho u)=0.}
\tag{2}
$$

Each represented level $i=(s,\ell)$ obeys

$$
\boxed{
\partial_t n_i+\nabla\cdot(n_i u+J_i)=\omega_i,}
\tag{3}
$$

Here $J_i$ is a diffusive number flux and $\omega_i$ is the net local production rate. The conservative species variables obey

$$
\boxed{
\begin{aligned}
\partial_t(\rho Y_s)
+\nabla\cdot(\rho Y_su+J_s^{m})
&=\dot\omega_s^{m},\\
J_s^{m}
&=m_u\sum_{\ell\in\mathcal L_s}A_{s\ell}J_{s\ell},\\
\dot\omega_s^{m}
&=m_u\sum_{\ell\in\mathcal L_s}A_{s\ell}\omega_{s\ell},
\end{aligned}}
\qquad
\sum_sY_s=1,
\quad
\sum_sJ_s^{m}=0,
\quad
\sum_s\dot\omega_s^{m}=0.
\tag{3a}
$$

Thus $J_s^{m}$ and $\dot\omega_s^{m}$ are the baryon-weighted sums of the level number fluxes and source rates. The variables $\rho Y_s$ and $n_{s\ell}$ are not independent conserved contents: an implementation may evolve one representation and reconstruct the other, or evolve both while enforcing (1a) and (3a) after every conservative update. Electronic transitions and ionization preserve the nuclei of each element. Nuclear reactions preserve total baryon number and electric charge:

$$
\sum_i A_i\omega_i=0,
\qquad
\sum_i Z_i\omega_i-\omega_e=0.
\tag{4}
$$

For a quasineutral plasma,

$$
\boxed{n_e=\sum_i Z_i n_i,}
\tag{5}
$$

with signed ionic charge $Z_i\geq0$ for the ordinary electron-ion mixture. Pair production, charged grains and nonneutral regions require their populations in (4) and a live electromagnetic field.

The minimum inviscid closure sets $J_i=J_s^m=0$. A model that enables species diffusion must construct each $J_s^m$ from the level fluxes through (3a), enforce the barycentric constraint $\sum_sJ_s^m=0$, and include the associated enthalpy flux in the energy equation.

### 2.2 Momentum and total material energy

Momentum conservation fixes where pressure, viscous stress, gravity and radiation force enter. With viscous stress $\tau$ and material radiation-force density $G_{\rm rad}$,

$$
\boxed{
\partial_t(\rho u)
+\nabla\cdot\left(\rho u\otimes u+p\mathbf1-\tau\right)
=\rho g+G_{\rm rad}.}
\tag{6}
$$

For a Newtonian fluid,

$$
\tau=2\eta\left[S-\frac13(\nabla\cdot u)\mathbf1\right]
+\zeta(\nabla\cdot u)\mathbf1,
\qquad
S=\frac12(\nabla u+\nabla u^{\mathsf T}),
\tag{7}
$$

with shear viscosity $\eta\geq0$ and bulk viscosity $\zeta\geq0$.

Let $e$ denote specific material internal energy, including thermal, excitation and ionization energy but excluding the common baryonic rest-energy reference. Then

$$
u_m=\rho e,
\qquad
E_m=\rho E=\frac12\rho|u|^2+u_m,
\qquad
q_h=-k_T\nabla T,
\tag{8}
$$

where $q_h$ is the conductive heat flux. If $\mathcal Q_{\rm rad}$ is the total material energy received from radiation in the simulation frame, the conservative material-energy equation is

$$
\boxed{
\begin{aligned}
\partial_tE_m
+\nabla\cdot\left[
(E_m+p)u-\tau u+q_h+\sum_i h_iJ_i
\right]
={}&\rho u\cdot g+\mathcal Q_{\rm rad}\\
&+Q_{\rm nuc}-Q_\nu+Q_{\rm ext}.
\end{aligned}}
\tag{9}
$$

Here $h_i$ is the partial enthalpy carried by one particle in level $i$, so $h_iJ_i$ has energy-flux units under the number-flux convention of (3). It uses the same excitation, ionization and formation-energy zero as $e$. The quantity $Q_{\rm nuc}$ is gross nuclear mass-defect power, $Q_\nu$ is energy carried away by neutrinos, and $Q_{\rm ext}$ is a declared external source. The covariant four-force in `turbulence/cassi-radiative-material-closure.md` §7 supplies $G_{\rm rad}$ and $\mathcal Q_{\rm rad}$ as the exact negatives of the radiation momentum and energy sources.

Subtracting $u$ dotted into (6) from (9) gives the internal-energy law

$$
\boxed{
\begin{aligned}
\partial_tu_m+\nabla\cdot
\left(u_m u+q_h+\sum_i h_iJ_i\right)
={}&-p\nabla\cdot u+\tau:\nabla u\\
&+\mathcal Q_{\rm rad}-u\cdot G_{\rm rad}
+Q_{\rm nuc}-Q_\nu+Q_{\rm ext}.
\end{aligned}}
\tag{10}
$$

The term $-p\nabla\cdot u$ is positive during compression and negative during expansion. It follows from the conservative fluxes; adding a second compression-heating term would count the same work twice. The viscous term is nonnegative for (7).

In the instantaneous material rest frame, the radiation terms reduce to

$$
\mathcal Q_{\rm rad}
=c_\gamma\sum_g\alpha^{\rm a}_g(E_g-E_g^{\rm LTE}),
\qquad
G_{\rm rad}=\sum_g\frac{\alpha^{\rm tr}_g}{c_\gamma}F_g.
\tag{11}
$$

A moving-frame implementation uses the full four-force because the lab-frame energy source contains the work $u\cdot G_{\rm rad}$ and Doppler terms.

### 2.3 Ideal multilevel equation of state

A concrete baseline EOS makes the conserved system invertible. For a dilute, nondegenerate, monatomic mixture with explicit ionic levels,

$$
\boxed{
p=k_BT\left(n_e+\sum_i n_i\right),}
\tag{12}
$$

$$
\boxed{
u_m=\frac32k_BT\left(n_e+\sum_i n_i\right)
+\sum_i n_i\epsilon_i.}
\tag{13}
$$

The level energy $\epsilon_i\geq0$ is measured from the neutral ground state of the same nuclei. It includes excitation and accumulated ionization thresholds. This convention makes ionization energy visible in the conserved variable.

For frozen populations, primitive recovery is explicit:

$$
\boxed{
T=\frac{2\left(u_m-\sum_i n_i\epsilon_i\right)}
{3k_B\left(n_e+\sum_i n_i\right)}.}
\tag{14}
$$

Admissibility requires positive particle count and
$u_m>\sum_i n_i\epsilon_i$. A reaction update that violates this inequality has spent more thermal energy than the cell owns and must be subcycled or solved implicitly.

For fixed monatomic composition,

$$
p=(\gamma-1)u_{\rm th},
\qquad
\gamma=\frac53,
\qquad
c_s^2=\left(\frac{\partial p}{\partial\rho}\right)_s
=\gamma\frac p\rho.
\tag{15}
$$

LTE ionization and excitation change the heat capacity and the adiabatic exponent because energy can enter internal levels. A thermodynamically consistent general closure starts from one specific fundamental relation,

$$
\boxed{
de
=T\,ds-p\,d\!\left(\frac1\rho\right)
+\sum_s\mu_s\,dY_s
+\sum_i\mathcal A_i\,dx_i,}
\tag{15a}
$$

where $s$ is specific entropy, $x_i$ denotes an independent normalized internal-state coordinate, and $\mu_s$ and $\mathcal A_i$ are the associated chemical potentials and nonequilibrium affinities in specific-energy units. The EOS interface must provide

$$
\boxed{
\begin{aligned}
p&=\rho^2\left(\frac{\partial e}{\partial\rho}\right)_{s,Y,x},&
T&=\left(\frac{\partial e}{\partial s}\right)_{\rho,Y,x}>0,\\
c_v&=\left(\frac{\partial e}{\partial T}\right)_{\rho,Y,x}>0,&
c_{s,{\rm fr}}^2&=\left(\frac{\partial p}{\partial\rho}\right)_{s,Y,x}>0,
\end{aligned}}
\tag{16}
$$
together with $e(\rho,T,Y,x)$ and the derivatives needed by the primitive solver. Molecules, degeneracy, Coulomb corrections, radiation pairs and relativistic temperatures replace (12)–(13) with a table or free-energy model. Deriving every returned quantity from one Helmholtz, Gibbs or internal-energy potential enforces the corresponding Maxwell identities and prevents inconsistent pressure, energy and sound speed.

For an operator-split reaction step, the internal coordinates are frozen during the hyperbolic update, so $c_{s,{\rm fr}}$ sets its characteristic speeds. In the instantaneous-equilibrium limit, the affinities determine $x_{\rm eq}(\rho,s,Y)$ through $\mathcal A_i=0$, and the relevant derivative is

$$
\boxed{
c_{s,{\rm eq}}^2
:=\left.\frac{d}{d\rho}
p\!\left(\rho,s,Y,x_{\rm eq}(\rho,s,Y)\right)
\right|_{s,Y}>0.}
\tag{16a}
$$

A production EOS declares the relaxation limit used by its Riemann solver. Finite-rate kinetics use the frozen wave speed in the flux step and resolve relaxation in the source step; an equilibrium table uses (16a) only after eliminating the equilibrated coordinates from the same thermodynamic potential.


### 2.4 Shock jump conditions

A shock is a weak solution selected by conservative fluxes and entropy production. Let a planar discontinuity move at speed $D$ with normal material speed $u_n$ and shock-frame speed $w=u_n-D$. Integrating (2), (6) and (9) across an infinitesimal stationary control volume gives the gas-only Rankine–Hugoniot relations

$$
\boxed{
[\rho w]=0,
\qquad
[\rho w^2+p]=0,
\qquad
\left[\rho w\left(h+\frac{w^2}{2}\right)\right]=0,}
\tag{17}
$$

where $h=(u_m+p)/\rho$ and $[a]=a_2-a_1$. Tangential velocity is continuous for an inviscid shock with nonzero mass flux. Excitation and ionization energy remain inside $h$.

For an ideal gas with upstream Mach number $M_1=w_1/c_{s,1}>1$,

$$
\boxed{
\frac{\rho_2}{\rho_1}
=\frac{(\gamma+1)M_1^2}{(\gamma-1)M_1^2+2},}
\tag{18}
$$

$$
\boxed{
\frac{p_2}{p_1}
=1+\frac{2\gamma}{\gamma+1}(M_1^2-1),
\qquad
\frac{T_2}{T_1}
=\frac{p_2/p_1}{\rho_2/\rho_1}.}
\tag{19}
$$

The specific entropy change is

$$
\boxed{
\Delta s=c_v\log\left[
\frac{p_2/p_1}{(\rho_2/\rho_1)^\gamma}
\right]>0
\quad(M_1>1).}
\tag{20}
$$

For a general EOS the admissibility condition is the entropy inequality

$$
\boxed{[\rho w s]\geq0}
\tag{20a}
$$

for positive mass flux from state 1 to state 2. A viscous and conductive shock profile realizes the same condition through

$$
\rho T\frac{Ds}{Dt}
=\tau:\nabla u+\frac{k_T}{T}|\nabla T|^2
+T\dot s_{\rm chem}\geq0,
\tag{20b}
$$

where a thermodynamically consistent reaction network has $\dot s_{\rm chem}\geq0$. This regularization supplies entropy production while its stress and heat flux remain inside the conservative momentum and energy equations.

Radiative shocks use total fluxes. In the shock frame, $P_{\gamma,nn}$ joins the normal momentum flux and $F_{\gamma,n}$ joins the energy flux:

$$
[\rho w^2+p+P_{\gamma,nn}]=0,
\tag{21}
$$

$$
\left[\rho w\left(h+\frac{w^2}{2}\right)+F_{\gamma,n}\right]=0,
\tag{22}
$$

when no energy or momentum escapes through another channel. Frequency-dependent precursors and nonequilibrium ionization are resolved by (3) and the transfer equations rather than absorbed into an altered gas jump formula.

A finite-volume Godunov, HLLC or suitably complete radiation-hydrodynamic Riemann solver evolves these weak solutions. Fourier collocation without shock capturing produces oscillations and does not enforce (17). Artificial viscosity may regularize a front only when its dissipated kinetic energy appears in (10).

## 3. Species, ionization and excitation kinetics

Line color comes from quantum-state populations. Temperature and elemental abundance alone do not determine those populations away from LTE.

### 3.1 Population master equation

Let $i=(A,Z,q,\ell)$ label a nucleus, ionization stage $q$ and internal level $\ell$. Its local source has the gain-minus-loss form

$$
\boxed{
\omega_i
=\sum_{j\ne i}(n_jR_{ji}-n_iR_{ij})
+\sum_r\nu_{ir}\mathcal R_r.}
\tag{23}
$$

The rates $R_{ij}\geq0$ include radiative and collisional bound-bound transitions, photoionization, collisional ionization, radiative and dielectronic recombination, charge exchange and molecular processes. Nuclear reaction $r$ has stoichiometric coefficient $\nu_{ir}$ and event rate $\mathcal R_r$.

For electronic transitions within one element, the rate generator has zero column sum. Consequently

$$
\frac d{dt}\sum_{q,\ell}n_{A,Z,q,\ell}=0.
\tag{24}
$$

A matrix exponential preserves nonnegative populations for a finite Markov generator. Practical networks use positivity-preserving implicit solvers because the fastest radiative transition and the slowest recombination or flow time can differ by many orders of magnitude.

### 3.2 LTE populations

LTE supplies a useful equilibrium oracle. Within ionization stage $q$, the Boltzmann population is

$$
\boxed{
\frac{n_{q\ell}}{n_q}
=\frac{g_{q\ell}}{U_q(T)}
\exp\left[-\frac{E_{q\ell}-E_{q0}}{k_BT}\right],}
\tag{25}
$$

with partition function

$$
U_q(T)=\sum_\ell g_{q\ell}
\exp\left[-\frac{E_{q\ell}-E_{q0}}{k_BT}\right].
\tag{26}
$$

Adjacent ion stages obey the Saha relation

$$
\boxed{
\frac{n_{q+1}n_e}{n_q}
=\frac{2U_{q+1}(T)}{U_q(T)}
\left(\frac{2\pi m_ek_BT}{h^2}\right)^{3/2}
\exp\left[-\frac{\chi_q}{k_BT}\right].}
\tag{27}
$$

Charge neutrality (5), elemental abundance and (27) determine the LTE ion fractions. Pressure ionization and truncated partition functions require a consistent nonideal EOS. Using an unbounded hydrogenic partition sum without plasma corrections is not a closed LTE model.

### 3.3 Bound-bound radiative and collisional rates

For a transition $u\leftrightarrow l$ with frequency $\nu_{ul}$ and normalized line profile

$$
\int_0^\infty\phi_{ul}(\nu)\,d\nu=1,
\tag{28}
$$

define the profile-averaged mean intensity

$$
\bar J_{ul}=\int_0^\infty\phi_{ul}(\nu)J_\nu\,d\nu,
\qquad
J_\nu=\frac1{4\pi}\int I_\nu\,d\Omega.
\tag{29}
$$

The radiative rates per particle are

$$
R^{\rm rad}_{lu}=B_{lu}\bar J_{ul},
\qquad
R^{\rm rad}_{ul}=A_{ul}+B_{ul}\bar J_{ul}.
\tag{30}
$$

The Einstein identities are

$$
\boxed{
g_lB_{lu}=g_uB_{ul},
\qquad
A_{ul}=\frac{2h\nu_{ul}^3}{c_\gamma^2}B_{ul}.}
\tag{31}
$$

Electron-impact excitation and de-excitation add
$n_eC_{lu}(T)$ and $n_eC_{ul}(T)$. Maxwellian detailed balance requires

$$
\boxed{
\frac{C_{lu}}{C_{ul}}
=\frac{g_u}{g_l}
\exp\left[-\frac{h\nu_{ul}}{k_BT}\right].}
\tag{32}
$$

When effective collision strength $\Upsilon_{lu}(T)$ is tabulated, the customary cgs coefficients are

$$
C_{lu}
=\frac{8.629\times10^{-6}}{g_lT^{1/2}}
\Upsilon_{lu}(T)e^{-h\nu_{ul}/(k_BT)},
\tag{33}
$$

$$
C_{ul}
=\frac{8.629\times10^{-6}}{g_uT^{1/2}}
\Upsilon_{lu}(T),
\tag{34}
$$

in $\mathrm{cm^3\,s^{-1}}$. The numerical coefficient is an established unit conversion and electron-Maxwellian result, not a Cassi parameter.

### 3.4 Photoionization and thermal partition

A photon above threshold can store part of its energy as ionization potential and leave the remainder as electron heat. For threshold $h\nu_0=\chi_i$ and photoionization cross-section $\sigma_i(\nu)$,

$$
\boxed{
\Gamma_i^{\rm ph}
=4\pi\int_{\nu_0}^\infty
\frac{\sigma_i(\nu)J_\nu}{h\nu}\,d\nu.}
\tag{35}
$$

The radiation-energy loss is

$$
Q_{\gamma,i}^{\rm ph}
=-4\pi n_i\int_{\nu_0}^\infty
\sigma_i(\nu)J_\nu\,d\nu.
\tag{36}
$$

The same absorbed power splits exactly into ionization storage and photoelectron heat:

$$
\boxed{
-Q_{\gamma,i}^{\rm ph}
=n_i\chi_i\Gamma_i^{\rm ph}
+4\pi n_i\int_{\nu_0}^\infty
\frac{\sigma_iJ_\nu}{h\nu}(h\nu-\chi_i)\,d\nu.}
\tag{37}
$$

Radiative, dielectronic and three-body recombination supply the reverse population paths. Their photons, electron heating or cooling and internal-level changes must be applied in the same energy solve. Case-A or case-B recombination is a boundary-dependent reduced model and must be declared with its optical-depth regime.

## 4. Line emission, absorption and opacity

Once the populations are known, the line coefficients follow directly. They become physical only with transition data and a normalized profile.

### 4.1 Bound-bound coefficients and detailed balance

For $u\to l$,

$$
\boxed{
j_\nu^{ul}
=\frac{h\nu_{ul}}{4\pi}n_uA_{ul}\phi_{ul}(\nu),}
\tag{38}
$$

$$
\boxed{
\alpha_\nu^{ul}
=\frac{h\nu_{ul}}{4\pi}
(n_lB_{lu}-n_uB_{ul})\phi_{ul}(\nu).}
\tag{39}
$$

Using the LTE ratio

$$
\frac{n_u}{n_l}=\frac{g_u}{g_l}
e^{-h\nu_{ul}/(k_BT)}
\tag{40}
$$

and (31), the source function becomes

$$
\frac{j_\nu^{ul}}{\alpha_\nu^{ul}}
=\frac{A_{ul}/B_{ul}}{e^{h\nu_{ul}/(k_BT)}-1}
=\boxed{B_\nu(T).}
\tag{41}
$$

Thus the multilevel line system recovers Kirchhoff equilibrium. Population inversion gives $\alpha_\nu^{ul}<0$; such a maser requires saturation and an explicit pump-energy reservoir.

The net radiative transition count is

$$
\dot N_{ul}^{\rm rad}
=n_u(A_{ul}+B_{ul}\bar J_{ul})-n_lB_{lu}\bar J_{ul}.
\tag{42}
$$

Its energy exchange is exact:

$$
\boxed{
\dot u_{\rm level}^{ul}=-h\nu_{ul}\dot N_{ul}^{\rm rad},
\qquad
\dot E_\gamma^{ul}=+h\nu_{ul}\dot N_{ul}^{\rm rad}.}
\tag{43}
$$

A local solver updates populations, material energy and radiation together so (43) cancels to stored precision. Collisional excitation changes level and electron thermal energy with no direct photon term.

### 4.2 Line profiles

Thermal and unresolved Gaussian velocities give Doppler width

$$
\Delta\nu_D
=\frac{\nu_{ul}}{c_\gamma}
\sqrt{\frac{2k_BT}{m_i}+v_{\rm turb}^2},
\tag{44}
$$

$$
\mathcal N_D
:=\frac12\left[1+\operatorname{erf}
\left(\frac{\nu_{ul}}{\Delta\nu_D}\right)\right],
\qquad
\phi_D(\nu)
:=\frac{1}{\mathcal N_D\Delta\nu_D\sqrt\pi}
\exp\left[-\frac{(\nu-\nu_{ul})^2}{\Delta\nu_D^2}\right],
\quad \nu\geq0.
\tag{45}
$$

The factor $\mathcal N_D$ makes (28) exact on the physical frequency half-axis; $\mathcal N_D$ is indistinguishable from unity for the usual narrow-line regime $\Delta\nu_D\ll\nu_{ul}$. Both Doppler and Voigt profiles are normalized and nonnegative on the transported frequency domain. Their sampled value may be exactly zero in a limiting tail or outside the support of a compact numerical profile; the line coefficient then vanishes at that frequency. Negative or nonfinite profile values are inadmissible.

Natural and collisional damping produce a Voigt profile with damping parameter

$$
a=\frac{\Gamma_{\rm damp}}{4\pi\Delta\nu_D}.
\tag{46}
$$

The bulk velocity shifts the comoving frequency by
$\nu'=\nu(1-n\cdot u/c_\gamma)+O(|u|^2/c_\gamma^2)$. A moving multigroup solver must move photons across fixed frequency boundaries consistently with this shift.

### 4.3 Continuum opacity and group construction

The total extinction is assembled without counting one interaction twice:

$$
\alpha_\nu^{\rm a}
=\alpha_\nu^{\rm bb}
+\alpha_\nu^{\rm bf}
+\alpha_\nu^{\rm ff}
+\alpha_\nu^{\rm dust,a},
\tag{47}
$$

$$
\alpha_\nu^{\rm s}
=\alpha_\nu^{\rm es}
+\alpha_\nu^{\rm dust,s}
+\alpha_\nu^{\rm line,s}.
\tag{48}
$$

Bound-free coefficients are evaluated constitutive inputs rather than an algebraic Cassi closure. Write

$$
\boxed{
\left(\eta_\nu^{\rm bf},\alpha_\nu^{\rm bf}\right)
:=\mathcal C_\nu^{\rm bf}
\!\left(T,n_e,\{n_i\};\mathcal D_{\rm bf}\right),}
\tag{49}
$$

where $\mathcal D_{\rm bf}$ contains versioned photoionization cross-sections, recombination coefficients, threshold energies, statistical weights, continuum normalization and uncertainty metadata. Its direct photoabsorption contribution is $\sum_i n_i\sigma_i(\nu)$. The inverse spontaneous and stimulated recombination terms come from the same data and detailed-balance convention; in LTE they must satisfy $\eta_\nu^{\rm bf}/\alpha_\nu^{\rm bf}=B_\nu(T)$ wherever $\alpha_\nu^{\rm bf}>0$.

Free-free absorption, electron scattering and dust likewise require evaluated temperature, density, composition and wavelength dependence. The Planck mean governs LTE emission and absorption; the Rosseland mean governs optically thick diffusion. Strong lines require explicit frequency groups or profile-aware transport because a gray mean erases their color and self-absorption.

### 4.4 Required atomic-data record

A production data record contains the quantities that the rate and transfer equations actually consume.

| Record | Required fields | Used by |
|---|---|---|
| Element and ion | nuclear charge, isotope or atomic mass, abundance, ion stage | (1), (4), (5), EOS |
| Level | stable identifier, energy $E_i$, statistical weight $g_i$, parity and angular labels | (13), (25), line identification |
| Bound-bound transition | lower/upper level identifiers, wavelength or energy, $A_{ul}$ or oscillator strength, uncertainty | (30), (31), (38), (39) |
| Electron collision | effective collision strength or resolved cross-section over temperature | (32)–(34) |
| Bound-free transition | threshold, photoionization cross-section, recombination data | (27), (35)–(37), (49) |
| Broadening | radiative, Stark, pressure and adopted microturbulent widths | (44)–(46) |
| Continuum response | free-free Gaunt factors, electron-scattering model, molecular or dust coefficients | (47), (48) |
| Nuclear reaction | reactant and product identifiers, nuclear masses, rate fit and validity range, screening rule, branching fractions and neutrino energy | (51)–(54) |
| Provenance | database version, source reference, units, interpolation rule and uncertainty flag | reproducibility |

Hydrogen line transport must include the relevant H I bound levels, H II continuum, recombination cascades and collisional transitions. H$\alpha$ requires the $n=3$ and $n=2$ manifolds plus the paths that populate them. Oxygen-rich nebular transport must carry the relevant oxygen ion stages and metastable levels. The [O III] 495.9 nm and 500.7 nm lines arise from the $^1D_2$ level and are collisionally excited; their density response depends on radiative decay competing with collisional de-excitation. For an upper level $u$,

$$
\boxed{n_{e,{\rm crit}}
=\frac{\sum_lA_{ul}}{\sum_{j\ne u}C_{uj}(T)}.}
\tag{50}
$$

A color preset cannot reproduce this density dependence. The transition and collision records are imported from evaluated atomic databases.

## 5. Persistent stellar luminosity

A luminous object remains bright by spending stored or supplied energy. The luminosity is a flux in the energy ledger rather than an independent visual attribute.

### 5.1 Nuclear reaction network and mass defect

For nuclear reaction $r$, write reactant multiplicities $a_{ir}\geq0$ and product multiplicities $b_{ir}\geq0$,

$$
\nu_{ir}=b_{ir}-a_{ir},
\qquad
\mathcal R_r
=\lambda_r(T,\rho,\{n_j\})
\prod_i\frac{n_i^{a_{ir}}}{a_{ir}!}.
\tag{51}
$$

Identical-particle factors and the units of $\lambda_r$ follow from the reaction order. The network must satisfy

$$
\sum_iA_i\nu_{ir}=0,
\qquad
\sum_iZ_i\nu_{ir}=0.
\tag{52}
$$

With measured or independently calculated nuclear masses $m_i$, the gross mass-defect power is

$$
\boxed{
Q_{\rm nuc}
=-c_\gamma^2\sum_i m_i\omega_i^{\rm nuc}.}
\tag{53}
$$

It is positive when products have lower rest mass. Neutrino energy $Q_\nu$ is removed separately in (9). If nuclear rest energy is retained explicitly inside the conserved energy variable, (53) is omitted; using both conventions would count the release twice.

The gross volume power supplied by nuclear mass defect is

$$
\boxed{L_{\rm nuc}=\int_VQ_{\rm nuc}\,dV.}
\tag{54}
$$

Neutrino loss is tracked separately as
$L_\nu=\int_VQ_\nu\,dV$. Reaction rates, screening, weak-interaction
branching and neutrino spectra are external nuclear data. A temperature
threshold alone does not define nuclear power.

### 5.2 Gravitational contraction

Self-gravity supplies a finite reservoir. For an isolated configuration,

$$
\Omega=\frac12\int\rho\Phi\,dV<0.
\tag{55}
$$

Hydrostatic equilibrium and a negligible surface-pressure term give the scalar virial relation

$$
3\int p\,dV+\Omega=0.
\tag{56}
$$

For a monatomic ideal gas, $U=(3/2)\int p\,dV$, so

$$
\boxed{2U+\Omega=0,
\qquad
E_*=U+\Omega=\frac{\Omega}{2}=-U.}
\tag{57}
$$

Write $\Omega=-\alpha_GGM^2/R$, where $\alpha_G$ is fixed by the density profile. Quasistatic contraction from $R_i$ to $R_f<R_i$ can radiate

$$
\boxed{
E_{\rm KH}
=E_*(R_i)-E_*(R_f)
=\frac{\alpha_GGM^2}{2}
\left(\frac1{R_f}-\frac1{R_i}\right)>0.}
\tag{58}
$$

The corresponding Kelvin–Helmholtz time at luminosity $L$ is

$$
\boxed{t_{\rm KH}=\frac{|E_*|}{L}
=\frac{\alpha_GGM^2}{2RL}.}
\tag{59}
$$

Contraction therefore gives a finite luminous lifetime. The density profile and surface boundary determine $\alpha_G$; taking it as unity is an order-of-magnitude convention.

### 5.3 Accretion power

Material arriving from large radius releases gravitational binding energy. For central mass $M$, surface or inner radius $R$ and accretion rate $\dot M$,

$$
\boxed{L_{\rm acc}=\eta_{\rm acc}\frac{GM\dot M}{R},
\qquad 0\leq\eta_{\rm acc}\leq1.}
\tag{60}
$$

The efficiency records how the released energy is divided among outgoing photons, retained heat, mechanical outflows, advection through an inner boundary and neutrinos. The sum of these channels equals $GM\dot M/R$ in the Newtonian model. Compact relativistic objects require the appropriate binding energy at the inner orbit or surface.

### 5.4 Stellar structure and luminosity transport

A spherically averaged star couples the EOS, gravity, energy generation and radiation diffusion through

$$
\boxed{
\frac{dm}{dr}=4\pi r^2\rho,
\qquad
\frac{dp}{dr}=-\frac{Gm\rho}{r^2},}
\tag{61}
$$

$$
\boxed{
\frac{dL}{dr}
=4\pi r^2\rho
\left(\epsilon_{\rm nuc}-\epsilon_\nu
-T\frac{Ds}{Dt}\right).}
\tag{62}
$$

The entropy term represents local storage or release during contraction and expansion. In an optically thick radiative region, the diffusion law

$$
F_\gamma=-\frac{c_\gamma}{3\kappa_R\rho}
\nabla(a_RT^4)
\tag{63}
$$

gives

$$
\boxed{
\frac{dT}{dr}
=-\frac{3\kappa_R\rho L}
{16\pi a_Rc_\gamma r^2T^3}.}
\tag{64}
$$

Convectively unstable regions require a convective flux closure; forcing (64) there can create an unphysical gradient.

The global energy statement for a fixed control volume is

$$
\boxed{
L_\gamma+L_\nu+\dot E_{\rm mech,out}
=P_{\rm ext}+L_{\rm nuc}+\dot E_{\rm matter,in}
-\frac d{dt}(K+U+\Omega).}
\tag{65}
$$

Here $\dot E_{\rm matter,in}$ is the net enthalpy, kinetic and gravitational
energy advected through the material boundary under one declared energy-zero
convention. Thermal cooling uses $-dU/dt$, contraction uses
$-d(U+\Omega)/dt$, and nuclear burning uses (53). Resolved accretion appears
through the material boundary flux and the changing binding energy. An
unresolved source may instead debit the separate accretion reservoir (60);
the corresponding boundary and binding-energy contribution is then omitted
from (65). Applying both representations to the same infalling mass would
count its released energy twice.
Heat retained inside the control volume appears through the stored-energy derivative in (65): retention makes $d(K+U+\Omega)/dt$ less negative, or positive when the stored reservoir grows. It is not part of $\dot E_{\rm mech,out}$. Any reduced unresolved model must therefore choose one destination for each released energy increment—radiation, neutrinos, mechanical escape, boundary advection or retained storage—and reconstruct the gross budget before applying (65).

### 5.5 Unresolved luminous particles

An unresolved star or sink carries enough state to enforce (65):

$$
(M,R,\{N_i\},E_{\rm th},E_{\rm grav},E_{\rm nuc,res},\dot M,L_g).
\tag{66}
$$

During one step,

$$
\boxed{
\sum_gL_g\Delta t
\leq
\Delta E_{\rm th}^{\rm available}
+\Delta E_{\rm grav}^{\rm released}
+\Delta E_{\rm nuc}^{\rm released}
+\Delta E_{\rm acc}^{\rm released}
+E_{\rm external}.}
\tag{67}
$$

The emitted group energy is deposited once into the radiation state and debited from these reservoirs. A blackbody surface may use
$L=4\pi R^2\sigma_{\rm SB}T_{\rm eff}^4$; a line-emitting atmosphere uses the rate and transfer system in §§3–4. When the available energy reaches zero and no supply remains, the source cools instead of continuing at fixed brightness.

## 6. Multi-angle transfer for crossing beams

Crossing-beam structure requires angular information beyond energy and flux. The obstruction for M1 is algebraic and the discrete-ordinates completion retains the missing information explicitly.

### 6.1 Why two moments cannot identify crossing beams

Consider two equal counterpropagating pencil beams along $\pm e_x$. Their moments are

$$
E=E_0,
\qquad
F=0,
\qquad
P=E_0e_x\otimes e_x.
\tag{68}
$$

An isotropic field with the same energy has

$$
E=E_0,
\qquad
F=0,
\qquad
P=\frac{E_0}{3}\mathbf1.
\tag{69}
$$

The pair $(E,F)$ is identical in (68) and (69), while $P$ differs. Any algebraic closure $P=P(E,F)$ must assign the same pressure to both states. M1 selects (69) at $F=0$, so it merges the counterpropagating beams. More elaborate formulas using only the same two moments cannot remove this non-identifiability.

### 6.2 Discrete-ordinates state

Choose directions $n_m\in S^2$ and positive solid-angle weights $w_m$ satisfying

$$
\boxed{
\sum_mw_m=4\pi,
\qquad
\sum_mw_mn_m=0,
\qquad
\sum_mw_mn_m\otimes n_m
=\frac{4\pi}{3}\mathbf1.}
\tag{70}
$$

The group moments are reconstructed from nonnegative intensities:

$$
\boxed{
E_g=\frac1{c_\gamma}\sum_mw_mI_{gm},
\quad
F_g=\sum_mw_mn_mI_{gm},
\quad
P_g=\frac1{c_\gamma}\sum_mw_mn_m\otimes n_mI_{gm}.}
\tag{71}
$$

Positive $I_{gm}$ guarantees $E_g\geq0$, $P_g\succeq0$, $\operatorname{tr}P_g=E_g$ and $|F_g|\leq c_\gamma E_g$.

Use the monochromatic transfer convention

$$
\frac1{c_\gamma}\partial_t I_\nu+n\cdot\nabla I_\nu
=\eta_\nu-\alpha_\nu I_\nu,
$$

with $[I_\nu]={\rm energy}\,{\rm time}^{-1}{\rm area}^{-1}{\rm sr}^{-1}{\rm Hz}^{-1}$, $[\eta_\nu]=[I_\nu]\,{\rm length}^{-1}$ and $[\alpha_\nu]={\rm length}^{-1}$. Group-integrated $I_{gm}$ and $B_g$ have the corresponding units after frequency integration. For coefficients held within group $g$, the multi-angle transfer equation is

$$
\boxed{
\begin{aligned}
\frac1{c_\gamma}\partial_tI_{gm}
+n_m\cdot\nabla I_{gm}
={}&\alpha_g^{\rm a}(B_g-I_{gm})\\
&+\alpha_g^{\rm s}
\left(\sum_{m'}w_{m'}p_{g,mm'}I_{gm'}-I_{gm}\right),
\end{aligned}}
\tag{72}
$$

where $B_g=\int_gB_\nu\,d\nu$ under the chosen intragroup convention. With $E_g^{\rm eq}:=4\pi B_g/c_\gamma$, the weighted angular sum fixes the energy-source normalization:

$$
\boxed{
\partial_tE_g+\nabla\cdot F_g
=c_\gamma\alpha_g^{\rm a}
\left(E_g^{\rm eq}-E_g\right).}
\tag{72a}
$$

Equivalently, the monochromatic isotropic source is $4\pi\eta_\nu-c_\gamma\alpha_\nu E_\nu$. The material source is its exact negative, $\mathcal Q_{{\rm rad},g}=c_\gamma\alpha_g^{\rm a}(E_g-E_g^{\rm eq})$, which matches (11). The discrete phase matrix is a nonnegative, quadrature-weighted column-stochastic kernel:

$$
\boxed{
p_{g,mm'}\geq0,
\qquad
\sum_mw_mp_{g,mm'}=1\quad\text{for every incoming ordinate }m'.}
\tag{73}
$$

The first index labels the outgoing ordinate and the second labels the incoming ordinate. This orientation makes each column a probability density over outgoing solid angle. Summing (72) over $w_m$ therefore makes the elastic scattering source vanish exactly. Multiplying by $w_mn_m/c_\gamma$ gives the radiation momentum source, whose negative is applied to matter. Absorption and emission are paired with the material energy and population updates from §§3–4.

### 6.3 Crossing and boundary behavior

In vacuum, each ordinate satisfies

$$
\partial_tI_{gm}+c_\gamma n_m\cdot\nabla I_{gm}=0.
\tag{74}
$$

Distinct beams therefore pass through the same cell and continue on their own characteristics. They superpose in $E_g$ while remaining separate in the array index $m$. Absorption attenuates each along its own optical path, and scattering transfers intensity between directions through the normalized matrix in (72).

At a boundary with outward normal $N$, data are prescribed only for incoming ordinates,

$$
n_m\cdot N<0.
\tag{75}
$$

Outgoing ordinates leave freely unless reflection or an external bath is explicitly selected. A finite-volume upwind transport step has the light-crossing CFL condition

$$
\Delta t\leq C_{\rm CFL}
\min_{\rm cells,m}
\frac{1}{c_\gamma\sum_d|n_{m,d}|/\Delta x_d}.
\tag{76}
$$

Implicit transport or a declared reduced light speed can relax the wall-clock restriction. A reduced speed changes transients and requires convergence against the physical-speed result in the relevant flow, diffusion and ionization timescale ratios.

### 6.4 Angular accuracy and hybrid option

The six axis directions $\{\pm e_x,\pm e_y,\pm e_z\}$ with weights $4\pi/6$ satisfy (70) and exactly carry axis-aligned crossing beams. They are a verification quadrature, not a general visual-quality choice. Finite $S_N$ sets produce ray effects when a source direction lies between ordinates, while low-order spatial reconstruction produces false scattering of oblique beams. Angular refinement, rotated quadratures or adaptive rays address those errors.

A hybrid solver may retain $S_N$ or M1 for diffuse radiation and trace direct rays from a small number of hard sources. The direct and diffuse sectors then need one partition:

$$
E_g=E_{g,{\rm direct}}+E_{g,{\rm diffuse}},
\qquad
L_g=L_{g,{\rm direct}}+L_{g,{\rm diffuse}},
\tag{77}
$$

with scattering moving energy from direct to diffuse exactly once. This partition is useful when a full high-order angular grid is too expensive.

## 7. One conservative coupled update

The four sectors form one evolution problem when every exchange is paired. A practical operator split is:

1. Recover $(\rho,u,T,\{n_i\})$ from the conserved material variables and EOS.
2. Advance conservative hydrodynamic fluxes for $\rho$, $\rho u$ and $E_m$ with a shock-capturing finite-volume method.
3. Advance species advection with the same mass flux so elemental abundances remain bounded and consistent with (2).
4. Advance gravity using a momentum-and-energy-paired source or a conservative self-gravity formulation.
5. Transport every $I_{gm}$ with (72), positive angular and spatial fluxes, and incoming-boundary data.
6. Solve absorption, emission, scattering, ionization, excitation and chemistry locally or implicitly. Apply each radiation, level and thermal increment once and with opposite signs.
7. Advance nuclear reactions, debit nuclear rest-mass difference, remove neutrino energy and update composition.
8. Recover primitives again and reject or refine any step that leaves $\rho$, $T$, populations or intensities outside their admissible set.

For a closed domain without gravity escape, external work or neutrino loss, the diagnostic invariant is

$$
\boxed{
\mathcal E_{\rm tot}
=\int_V\left(E_m+\sum_gE_g\right)dV
+\frac12\int_V\rho\Phi\,dV
+E_{\rm nuclear\ rest}
=\text{constant}.}
\tag{78}
$$
Here $E_m$ and each $E_g$ are volume energy densities, $\rho\Phi/2$ is the self-gravitational energy density, and $E_{\rm nuclear\ rest}$ is the domain-integrated nuclear rest-energy reservoir. Every term in $\mathcal E_{\rm tot}$ is therefore extensive after the displayed volume integrations.

If nuclear rest energy is converted through (53), $E_{\rm nuclear\ rest}$ decreases by the same gross amount deposited into matter and radiation. For an open domain, boundary fluxes and neutrino escape explain the complete change in (78).

The required runtime diagnostics are

- total baryon number and elemental nuclei by species family;
- total electric charge and charge-neutrality residual;
- minimum $\rho$, $T$, $n_i$ and $I_{gm}$;
- material, radiation, gravitational and nuclear-reservoir energies;
- pressure-work, viscous, conductive, radiative, chemical, nuclear and neutrino increments;
- emitted, absorbed, scattered, escaped and boundary-injected radiation by group;
- Rankine–Hugoniot residuals across detected shocks;
- angular quadrature moment residuals and direct/diffuse partition residual;
- maximum optical depth, reduced flux and source-solver iteration count.

These diagnostics distinguish physical luminosity from display exposure and identify any missing energy destination.

## 8. CassiCosmos interface

The conditional closure can be attached to CassiCosmos only after material state and units are declared. The minimum persistent fields are

$$
(\rho,\rho u,E_m,\{n_i\},\{I_{gm}\}),
\tag{79}
$$

or $(E_g,F_g)$ in cells that remain on the M1 diffuse path. The existing Observatory renderer can read the outgoing group intensities and convert them through a declared sensor response. Exposure, tone mapping and bloom remain downstream presentation operations and never feed the energy equations.

A default-off implementation preserves the existing solver exactly when disabled. Enabling physical mode requires:

- length, time, baryonic-mass, temperature and energy units;
- a density and velocity interface to the live gravitational state;
- an EOS and primitive-recovery table;
- a material/species inventory with atomic and nuclear data versions;
- frequency groups fine enough for the selected continua and lines;
- an angular quadrature or direct/diffuse partition;
- boundary conditions for matter, gravity and every incoming radiation direction;
- a source-step tolerance and conservation thresholds.

The canonical pair $(E_Y,E_I)$ and $q$ can influence a declared constitutive model after a physical map is derived or calibrated. They do not identify hydrogen, oxygen, electron density, kelvin temperature, opacity, transition strength or nuclear fuel on their own.

## 9. Epistemic boundary

### 9.1 Derived conditional results

The following statements follow from the displayed assumptions:

- conservative mass, momentum and material-energy equations give pressure work and the Rankine–Hugoniot conditions;
- the ideal multilevel EOS gives the explicit primitive recovery and frozen-composition sound speed;
- population generators preserve each elemental nucleus count, and LTE Saha–Boltzmann populations with Einstein identities recover the Planck line source;
- bound-bound and bound-free energy partitions conserve material-plus-radiation energy;
- nuclear mass defects, gravitational contraction and accretion enter one stellar luminosity ledger;
- the virial relation gives the finite Kelvin–Helmholtz reservoir;
- discrete ordinates preserve multiple beams, while $(E,F)$ alone cannot distinguish counterpropagating beams from an isotropic field;
- normalized scattering quadrature conserves radiation energy.

### 9.2 Tested reference controls

The fixed schedule in
`computations/compressible-radiative-plasma-prereg.md` passes **70 of 70
checks**. It verifies symbolic pressure-work reduction, exact normal-shock
fluxes, primitive recovery, finite population-generator conservation and
positivity, LTE line balance, bound-free energy partition, virial and
source-reservoir ledgers, angular realizability, isotropic scattering and two
axis-aligned beams that cross in one cell and continue independently. The
`cassi-compressible-radiative-plasma-verification-v2` receipt binds the executed
kernel and scientific schedule to their manifest-recorded snapshot files:
`runs/compressible_radiative_plasma_frozen_execution_final/verification.json`.

The separate fixed integrity qualification in
`computations/compressible-radiative-plasma-integrity-prereg.md` passes **36 of
36 checks**. It verifies the species-level mass constraint, defensive public
state construction, kinetic internal-energy recovery, the thermodynamic
identities, exact physical-frequency Doppler normalization, invalid-state
rejection, line and photoionization energy cancellation, normalized transfer
sources, stellar control-volume reconstruction, nuclear conservation and the
`INCONCLUSIVE` classification of missing scientific prerequisites. The
`cassi-compressible-radiative-plasma-integrity-v2` receipt binds the executed
kernel, base verifier and integrity schedule to their manifest-recorded
snapshot files:
`runs/compressible_radiative_plasma_integrity_frozen_execution_final/verification.json`.

The combined qualification verdict is **SUPPORTS** for the conditional closure at reference-kernel
level. Production finite-volume convergence, atomic and nuclear data
qualification, general angular convergence, a physical Cassi material map and
CassiCosmos integration remain open.

### 9.3 Constitutive inputs

The closure imports or selects:

- $G,c_\gamma,h,k_B,m_e,m_u,a_R,\sigma_{\rm SB}$;
- EOS corrections, viscosities, conductivities and species diffusion coefficients;
- elemental abundances and initial ionization and excitation populations;
- evaluated levels, wavelengths, $A$ values, oscillator strengths, collision strengths, photoionization cross-sections and broadening data;
- continuum, molecular and dust opacity data;
- nuclear masses, reaction rates, screening corrections and neutrino losses;
- angular quadrature, frequency bins, spatial resolution and any reduced-light-speed factor.

These inputs receive provenance, units and validity ranges. None is inferred by choosing the value that gives the most colorful image.

### 9.4 Open Cassi identification

The physical mapping from the Cassi field and particle state to baryonic mass, chemical species, electron density, thermodynamic temperature, electromagnetic charge and nuclear composition remains open. Deriving that map requires a selected microscopic matter sector and physical normalization. The conditional system here supplies the conservation and transport architecture that such a map must enter.

## 10. References

- `turbulence/cassi-radiative-material-closure.md`—LTE transfer, M1 moments, covariant four-force and conservative thermal source
- `turbulence/cassi-fluid-feasibility.md` §7—selected constant-density capillary and thermal material
- `standard-model/su2-gauge-extension.md` §§2–3—conditional massless gauge direction and unresolved electromagnetic current map
- `foundations/matter-completion-boundary.md`—current microscopic matter-identification boundary
- `computations/compressible-radiative-plasma-prereg.md`—fixed symbolic, EOS, shock, population, source-ledger and angular controls
- `computations/compressible_radiative_plasma.py`—reference EOS, shock, population, line, stellar-source and discrete-ordinates kernels
- `computations/verify_compressible_radiative_plasma.py`—70-check source-snapshotted verifier
- `computations/compressible-radiative-plasma-integrity-prereg.md`—fixed 36-check state, line-profile, exchange, ledger and prerequisite qualification
- `computations/verify_compressible_radiative_plasma_integrity.py`—source-bound integrity qualification verifier
- D. Mihalas and B. Weibel-Mihalas, *Foundations of Radiation Hydrodynamics*—compressible radiation hydrodynamics and moving-frame transfer
- R. J. LeVeque, *Finite Volume Methods for Hyperbolic Problems*—conservative weak solutions and shock-capturing finite-volume methods
- G. B. Rybicki and A. P. Lightman, *Radiative Processes in Astrophysics*—Einstein coefficients, line transfer and continuum processes
- D. G. Hummer and D. Mihalas, [The equation of state for stellar envelopes. I](https://doi.org/10.1086/167361)—occupation probabilities and nonideal stellar-plasma EOS
- [NIST Atomic Spectra Database, SRD 78, version 5.12](https://doi.org/10.18434/T4W30F)—evaluated atomic levels, wavelengths and transition probabilities
- [CHIANTI atomic database](https://www.chiantidatabase.org/)—level-resolved radiative and collisional data for astrophysical plasmas
- W. Cunto, C. Mendoza, F. Ochsenbein and C. J. Zeippen, *TOPbase at the CDS*, Astronomy & Astrophysics **275**, L5–L8 (1993)—Opacity Project levels, oscillator strengths and photoionization cross-sections
- M. J. Seaton, Y. Yan, D. Mihalas and A. K. Pradhan, [Opacity Project systematic atomic calculations](https://doi.org/10.1093/mnras/266.4.805)—atomic opacity calculations underlying TOPbase
- [JINA REACLIB](https://reaclib.jinaweb.org/)—versioned thermonuclear reaction-rate fits and provenance
- C. Iliadis, *Nuclear Physics of Stars*—reaction networks, mass defects and stellar energy generation
- R. Kippenhahn, A. Weigert and A. Weiss, *Stellar Structure and Evolution*—virial, contraction, nuclear and transport ledgers
- B. G. Carlson, [Discrete-ordinates quadrature over the unit sphere](https://www.osti.gov/biblio/4083770)—symmetric angular quadrature
- K. D. Lathrop, [Ray effects in discrete ordinates equations](https://doi.org/10.13182/NSE68-4)—finite-angle ray effects
- Y.-F. Jiang, J. M. Stone and S. W. Davis, [Time-dependent discrete-angle radiation magnetohydrodynamics](https://doi.org/10.1088/0067-0049/213/1/7)—conservative multi-angle radiation-hydrodynamic implementation
