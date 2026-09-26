# Cassi Framework—Definitions

## Status: Reference—August 2026

## Abstract

This glossary defines the Cassi two-fluid variables, $\varphi$-attractor, Qi coherence, phase currents, conversion, optional spatial drift, and the regulated CassiFI quantum sector. The canonical solver variables are the nonnegative square densities $E_Y$ and $E_I$; $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ is their exact positive-root coordinate lift for amplitude-plane diagnostics. The conditional quantum state $\Psi[Q,t]$ is a distinct complex wavefunctional on the full CassiFI configuration space. The signed imbalance is $\pi=E_Y-E_I$, while $\rho=E_Y+E_I$ remains nonnegative. Yang/Yin direction words are phenomenological or coordinate mnemonics unless a shared advection field or named potential-relative drift supplies the motion.

> Framework proposal grounded in the φ-attractor and the Yin-Yang two-fluid,
> with emergent-spacetime geometry treated as an optional closure.

---

## Table of Contents

1. [Fundamentals](#1-fundamentals)
2. [Two-Fluid Dynamics](#2-two-fluid-dynamics)
3. [Spacetime & Gravity](#3-spacetime--gravity)
4. [Black Holes & Compact Objects](#4-black-holes--compact-objects)
5. [Particle Physics](#5-particle-physics)
6. [Time](#6-time)
7. [Consciousness & Psychology](#7-consciousness--psychology)
8. [Life](#8-life)
9. [Chemistry](#9-chemistry)
10. [Phase Transitions & Thermodynamics](#10-phase-transitions--thermodynamics)
11. [Information](#11-information)
12. [Cosmology—CMB, Inflation, Structure](#12-cosmology--cmb-inflation-large-scale-structure)
13. [Unification—Theory of Everything](#13-unification--the-theory-of-everything)
14. [Observables & Predictions](#14-observables--predictions)
15. [Code & Implementation](#15-code--implementation)
16. [Epistemic Tiers](#16-epistemic-tiers)

---

## 1. Fundamentals

### φ (phi)—the Golden Ratio
- **Value**: (1 + √5)/2 ≈ 1.6180340
- **Role**: Canonical attractor ratio for the two-fluid conversion sector; cross-scale applications use it as an optional mapping unless independently supported.
- **Appears in**: selected dark-energy, galactic-rotation, biological, and PDE mappings, with each application carrying its own epistemic status.
- **Inverse**: φ⁻¹ = φ − 1 ≈ 0.6180; φ⁻² = 2 − φ ≈ 0.3820; φ⁻³ ≈ 0.2361.

### $\Psi^{(+)}$—positive-root amplitude-plane lift
- **Definition**: The canonical solver state is $(E_Y,E_I)\in\mathbb{R}_{\geq0}^2$. Its reference lift is $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})\in\mathbb{R}_{\geq0}^2$.
- **Scope**: The positive-root lift is a coordinate diagnostic on the nonnegative quadrant. Independent signs and compact phase belong to optional extensions.
- **State ratio**: $r=E_Y/E_I$ where $E_I>0$; the ratio is continuous and the densities remain the primary solver variables.

### $\Psi[Q,t]$—regulated CassiFI quantum wavefunctional
- **Configuration**: $Q^A=\{\operatorname{Re}D,\operatorname{Im}D,\operatorname{Re}C,\operatorname{Im}C\}_{s,j}$ is the finite regulated CassiFI complex-field configuration, with positive metric $G_{AB}$.
- **State space (QF1)**: $\Psi[Q,t]\in L^2(\mathcal C,d\mu_G)$ is a normalized complex wavefunctional on the full configuration space. The positive-root lift $\Psi^{(+)}$ remains a real density-coordinate diagnostic.
- **Dynamics (QF2)**: $\hat H_Q=-\hbar^2\Delta_G/2+U_{\mathrm{FI}}(Q)$ and $i\hbar\partial_t\Psi=\hat H_Q\Psi$ in the closed conservative sector.
- **Actual configuration (QF3)**: One field configuration follows the selected conserved current, $\dot Q^A=J^A/|\Psi|^2$. DQ4 exhibits divergence-free current additions with the same equivariant density and different trajectories; the frozen source supplies no uniqueness theorem for this guidance law.
- **Quantum Qi flow**: For $Q=(Q_A,Q_B)$, $\mathfrak F_\Psi=(\rho_\Psi,J_A,J_B)$ with $\rho_\Psi=|\Psi|^2$. A product state obeys $\rho_\Psi=\rho_A\rho_B$, $J_A=\rho_BJ_A^{(A)}$, and $J_B=\rho_AJ_B^{(B)}$. On connected nonnodal product support, the converse holds; Schmidt rank or reduced-state purity supplies the exact global criterion across disconnected support.
- **Local cross-flow diagnostics**: $\Xi^{(R)}_{a\beta}=\nabla_a\nabla_\beta\ln R$ diagnoses amplitude correlation and $\Xi^{(S)}_{a\beta}=\nabla_a\nabla_\beta S$ diagnoses cross-dependent guidance flow. Schmidt rank, reduced purity, and $\mathcal E_{A:B}=-\operatorname{Tr}(\rho_A\ln\rho_A)$ supply the global entanglement criteria.
- **Entangling links**: The quantized reciprocal term $w_Zg_{Z,s}\|Z_{s+1}-P_sZ_s\|_{W_{s+1}}^2/2$ directly couples the nonzero metric-aware singular modes of $P_s$. Its classical signed current $\mathcal K$ measures the exchange quadrature; reduced-state invariants measure entanglement.
- **Quantum equilibrium (QF4)**: $\rho_Q=|\Psi|^2$ is an explicit statistical postulate. It is equivariant and yields $P(k)=\langle\Psi|P_k|\Psi\rangle$ for disjoint retained apparatus sectors. DQ5 shows that the same flow also transports nonequilibrium ratios, so equivariance does not select the preparation density.
- **Record distinguishability**: $\mathcal M_{jk}=1-|\langle A_kE_k|A_jE_j\rangle|^2$. The Creative classical attack coefficient $\mathcal M_i^{\mathrm{attack}}$ is a separate Hypothesized quantity.
- **Canonical bridge audit**: DQ1 finds that the real positive-root section has zero symplectic pullback and the density projection leaves a two-dimensional phase fibre. DQ2 finds no canonical Qi-to-Fisher bridge. DQ3 and DQ6 pass conditionally; DQ1, DQ2, DQ4, DQ5, DQ7, DQ8, and DQ9 fail their promotion criteria.
- **Geometric projection**: $\mu_{\mathrm{dens}}(\mathcal E_Y,\mathcal E_I)=(|\mathcal E_Y|^2,|\mathcal E_I|^2)$ is the candidate lower moment map. At the $\varphi$ attractor, the normalized complex pair lies at Bloch latitude $n_z=\varphi^{-3}$ while its relative-phase longitude remains free. Equal modulus data carry different declared $D/C$ modal contents and link currents.
- **Finite Kähler structure**: $g_W=\operatorname{Re}(u^\dagger Wv)$, $\omega_W=\operatorname{Im}(u^\dagger Wv)$, and $Ju=iu$ are compatible on the declared complex configuration. Complex-linear refinements satisfying $I^\dagger W'I=W$ preserve them.
- **Status**: The regulated mathematical construction is **Derived conditional** on QF1–QF4. The DQ1–DQ9 campaign verdict is **`REJECT` promotion**. The GQ1–GQ7 campaign **`ADOPT`s** the moment-map/Kähler projection architecture as a **Hypothesized research direction** and retains `REJECT` for physical-identification promotion (`foundations/quantum-measurement-derivation.md` §§8.1, 8.3).

### $E_Y$—Yang density
- **Definition**: $E_Y\ge0$ is the canonical Yang density component, equivalently $E_Y=(\Psi_0^{(+)})^2$ in the positive-root lift.
- **Phenomenology**: Yang is the expansive, radiative component in the framework's directional mnemonics. This label does not prescribe a velocity; spatial motion comes from the shared advection field and any activated, named potential-relative drift.

### $E_I$—Yin density
- **Definition**: $E_I\ge0$ is the canonical Yin density component, equivalently $E_I=(\Psi_1^{(+)})^2$ in the positive-root lift.
- **Phenomenology**: Yin is the contractive, absorptive component in the framework's directional mnemonics. This label does not prescribe a velocity; spatial motion comes from the shared advection field and any activated, named potential-relative drift.

### $\rho$ and $\pi$—total and signed densities
- **Total density**: $\rho=E_Y+E_I=(\Psi_0^{(+)})^2+(\Psi_1^{(+)})^2\ge0$.
- **Signed Yang excess**: $\pi=E_Y-E_I$, with $-\rho\le\pi\le\rho$. The sign records the density imbalance; it does not make either density negative.

### Qi—coherence and spatial diagnostics
- **Instantaneous deviation**: $\varepsilon=E_Y-\varphi E_I$.
- **Optional IIR deviation memory**: when the default-off `qi_memory` switch is enabled, $\bar{\varepsilon}^2(t)=(1-\tau)\bar{\varepsilon}^2(t-\Delta t)+\tau\varepsilon^2(t)$. The default $\tau=\varphi^{-1}$ is a solver convention per completed step.
- **Effective deviation**: $\varepsilon_{\mathrm{eff}}^2=\bar{\varepsilon}^2$ with memory enabled and $\varepsilon_{\mathrm{eff}}^2=\varepsilon^2$ otherwise.
- **Coherence**:

$$
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon_{\mathrm{eff}}^2}.
$$

In this expression, $\rho^2$, $\varepsilon_{\mathrm{eff}}^2$, and the additive $\varphi^{-2}$ term use the same dimensionless reference normalization. The rational form and bare $\varphi^{-2}$ floor are a **C / Asserted** canonical constitutive definition, not a consequence derived from $\varphi$ and the PDE. If $E_Y,E_I$ are physical energy densities, introduce an external reference density $\rho_*$ and evaluate the formula with $\tilde\rho=\rho/\rho_*$ and $\tilde\varepsilon_{\mathrm{eff}}=\varepsilon_{\mathrm{eff}}/\rho_*$, equivalently $q=\rho^2/(\rho^2+\varphi^{-2}\rho_*^2+\varepsilon_{\mathrm{eff}}^2)$; no $\rho_*$ scale is derived or counted as a framework parameter. A change of density units must rescale the reference term consistently; otherwise the numerical value of $q$ changes. The bounds and reference-state value below are **Derived conditional** on this definition and normalization.

- **Reference equilibrium**: At $E_Y=1$, $E_I=\varphi^{-1}$, $\varepsilon_{\mathrm{eff}}=0$, and $\rho=\varphi$, $q_{\mathrm{eq}}=\varphi^2/(\varphi^2+\varphi^{-2})\approx0.873$ and $1-q_{\mathrm{eq}}=\varphi^{-2}/3\approx0.127$. This value belongs to the stated reference normalization; on the $\varphi$-line at another density, $q_{\mathrm{eq}}(\rho)=\rho^2/(\rho^2+\varphi^{-2})$ changes.
- **Positive-root amplitude-plane diagnostic**:

$$
J_\Psi^{(+)}
:=\Psi_0^{(+)}\nabla\Psi_1^{(+)}
-\Psi_1^{(+)}\nabla\Psi_0^{(+)}
:=\rho\nabla\theta_\Psi^{(+)}.
$$

This is the foundational local amplitude-plane phase-current diagnostic of the reference lift. Along a named coordinate $z$, the polar-coordinate identity $\Psi_0^{(+)}+i\Psi_1^{(+)}=R e^{i\theta_\Psi^{(+)}}$ gives $J_{\Psi,z}^{(+)}=R^2\partial_z\theta_\Psi^{(+)}$, with units of field$^2$/length and $R^2=\rho$. Transport and periodic-phase interpretations each require a separate constitutive extension.

### Amplitude-plane and density-plane coordinates
- **Positive-root amplitude-plane angle**: $\theta_\Psi^{(+)}=\operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)})=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y})\in[0,\pi/2]$.
- **Density-plane angle**: $\theta_d=\operatorname{atan2}(E_I,E_Y)\in[0,\pi/2]$.
- **Stokes double angle**:

$$
\Theta_S=\operatorname{atan2}(2\sqrt{E_YE_I},E_Y-E_I)
:=2\theta_\Psi^{(+)}\pmod{2\pi}
$$

On the positive-root reference domain, these coordinates parameterize the same two-density state. A compact angle requires an optional signed or complex extension. Where the positive-root scope is already explicit, documents may use $\theta_\Psi$ and $J_\Psi$ as shorthand for $\theta_\Psi^{(+)}$ and $J_\Psi^{(+)}$.

- **Positive-root density-plane/lattice diagnostic**:

$$
J_d=E_Y\nabla E_I-E_I\nabla E_Y
   =(E_Y^2+E_I^2)\nabla\theta_d
   =2\sqrt{E_YE_I}\,J_\Psi^{(+)}.
$$

$J_d$ has units of density$^2$/length, distinct from the field$^2$/length units of $J_\Psi^{(+)}$. A spatial diagnostic requires a named projection. Constitutive transport and inter-rung interpretations require a separate map.

### Attractor—$\varphi$-equilibrium
- **Definition**: The conversion fixed point is $E_Y=\varphi E_I$; in the positive-root lift, $(\Psi_0^{(+)})^2=\varphi(\Psi_1^{(+)})^2$.
- **Reference state**: $E_Y=1$, $E_I=\varphi^{-1}$, $\rho=\varphi$, and $\pi/\rho=\varphi^{-3}$.
- **Scope**: Conversion relaxes the density imbalance toward this line; advection, diffusion, sources, and optional drift can move the state through space.

### Optional $\chi$ drift and shared advection
The potential-relative $\chi$ drift is an optional spatial term. With scalar potential $\Phi$ and mobilities $\chi_Y,\chi_I$:

$$
\mathcal{D}_{\chi}E_Y=-\nabla\!\cdot(\chi_Y E_Y\nabla\Phi),\qquad
\mathcal{D}_{\chi}E_I=+\nabla\!\cdot(\chi_I E_I\nabla\Phi),
$$

equivalently $\mathbf v_Y^{(\chi)}=+\chi_Y\nabla\Phi$ and $\mathbf v_I^{(\chi)}=-\chi_I\nabla\Phi$. Thus Yin is attracted toward lower-potential wells and Yang is repelled relative to $\nabla\Phi$ when this term is active; $\chi=0$ removes the drift. The solver may use $\chi_Y=\chi/\varphi$ and $\chi_I=\chi$ as mobility choices.

Both densities share the same advection field:

$$
\mathcal{A}E_Y=-(\mathbf u\!\cdot\!\nabla)E_Y,\qquad
\mathcal{A}E_I=-(\mathbf u\!\cdot\!\nabla)E_I.
$$

Directional words such as inward and outward have velocity meaning only through a named potential-relative projection; otherwise they remain phenomenological mnemonics.

### Conditional four-channel extension
Four nonnegative directional populations $f_{Y,+},f_{Y,-},f_{I,+},f_{I,-}$ may be introduced only as a kinetic extension after an oriented spatial axis has been chosen; $+$ and $-$ are relative to that axis. Reconstructing them requires separately defined species currents, speeds, and a direction-mixing rule. The canonical model supplies two densities and one shared advection field, so these four populations are conditional, unselected extension variables rather than a canonical four-field adoption. Their operational four-component state does not add a spacetime dimension, and the canonical $J_\Psi$ and $J_d$ cannot be substituted for the missing kinetic constitutive data.

### Conversion geometry
The canonical conversion sector is a rank-one relaxation:

$$
\left.\partial_t
\begin{pmatrix}E_Y\\E_I\end{pmatrix}\right|_{\mathrm{conv}}
=-\lambda(1-q)
\begin{pmatrix}1&-\varphi\\-1&\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.
$$

This rank-one operator conserves $\rho=E_Y+E_I$ and has eigenvalues $0$ and $-\lambda(1-q)(1+\varphi)$; it generally changes $E_Y^2+E_I^2$, so it is a relaxation toward the $\varphi$-line rather than an $SO(2)$ generator. The named C-class/framework convention $\lambda=0.1$ is an asserted inverse-time normalization/timescale, while the implementation class default is $\lambda=0.02$. The relation $\lambda=1/(2w)$ with $w=5$ is a Hypothesized Wu Xing linkage requiring independent cycle-time and dynamical closure.

$$
\boxed{\frac{d\theta_d}{dt}
=\lambda(1-q)\frac{\rho\,\varepsilon}{E_Y^2+E_I^2}}.
$$

The coordinate $\delta n_{\mathrm{map}}\equiv\Delta\theta_d/(2\pi)$ may be introduced as a Hypothesized geometric mapping to a cascade-rung offset. It is not a PDE derivation of a rung or inter-rung transport. Any fixed per-rung phase or pitch belongs to that separate Hypothesized coordinate construction and is not selected by canonical conversion.

### σ (sigma)—Gaussian Softening (Hypothesized regularization)
- **Role**: Optional Gaussian softening scale in selected force-law extensions; it is not a fundamental length of the canonical PDE.
- **Value**: Empirically ~ 0.1–1.0 in code units (nature's value to be determined from observations).
- **Effect**: Within the selected closure, the $r\to0$ Coulomb/Newtonian divergence is replaced by harmonic behavior, $F(r)\propto r$.
- **Consequence**: This closure removes a modeled point-force singularity; no universal no-singularity theorem follows for the framework.
- **Physical origin**: A minimum coherence length is a Hypothesized interpretation; the canonical fields do not by themselves impose resolution below $\sigma$.

---

## 2. Two-Fluid Dynamics

### Two-Fluid PDE
The canonical coupled evolution is written in the square-density variables $E_Y,E_I\ge0$ and the shared velocity field $\mathbf u$.

$$
\partial_t E_Y=-(\mathbf u\!\cdot\!\nabla)E_Y+D\nabla^2E_Y
-\lambda(1-q)(E_Y-\varphi E_I)+S_0[E_I,\Phi],
$$

$$
\partial_t E_I=-(\mathbf u\!\cdot\!\nabla)E_I+D\nabla^2E_I
+\lambda(1-q)(E_Y-\varphi E_I)+S_1[E_Y,\Phi].
$$

- **Conversion**: The equal-and-opposite terms conserve $\rho$ in the conversion sector and have the rank-one spectrum stated in §1.
- **Spatial terms**: Both channels use the same $\mathbf u$ advection and $D$ scalar diffusion. The shared velocity equation carries the separate viscosity coefficient $\nu$. Optional $\chi$ drift adds the potential-relative terms $\mathcal D_\chi E_Y$ and $\mathcal D_\chi E_I$ from §1.
- **Sources**: $S_0$ and $S_1$ couple the channels through the gravitational/information potential $\Phi$.
- **Potential**: $\nabla^2\Phi=4\pi G(E_Y+E_I)$ in the Poisson form.

### Scale Factor a(t)—Comoving Expansion (optional cosmology closure)
- **Definition**: A cosmological scale factor evolved with a chosen Hubble parameter.
- **Evolution**: $a\leftarrow a\,\exp(H\,dt)$, with $H=da/(a\,dt)$ in this model convention.
- **Energy-density scaling**: $E_Y\propto a^{-3}$ and $E_I\propto a^{-3}$ are matter-like ansätze supplemented by selected curvature and back-reaction terms.

### Hubble Modes (Hypothesized cosmology closure)
Three candidate expansion modes are used in optional cosmology solvers:

1. **Conversion mode**: $H=(\lambda/3)(\varphi-r)(1+r)/r$, where $r=E_Y/E_I$.
   - $r=\varphi$ gives $H=0$ in this closure.
   - $r>\varphi$ gives $H>0$ and can be mapped to accelerated expansion or dark energy.
   - $r<\varphi$ gives $H<0$ and can be mapped to contraction.
   - This is a scale-factor mode of the selected conversion closure; spatial channel motion remains the shared advection and any named potential-relative drift in §1.

2. **Stress-energy mode**: $H=H_{\rm empty}+H_{\rm conv}+H_{\rm struct}$, a bookkeeping ansatz for selected energy components.

3. **Friedmann mode**: $H=H_0\sqrt{\rho/\rho_{\rm crit}}$, a comparison to the standard $\Lambda$CDM form as $q\to0$.

### DESI Calibration (Calibrated optional cosmology mapping)
- **Result**: $w_0=-0.87$ (structural gap-derived $r_0=\varphi^{-5}/(2-\varphi^{-5})=0.0472$), $2\sigma$ from DESI DR2's $w_0\approx-0.75\pm0.06$ [INFERENCE].
- **Procedure**: ODE bisection over the $E_Y/E_I$ ratio with the Yang-fraction-weighted coupling (`two-fluid/calibrate_initial_ratio_xi_v2.py`).
- **Scope**: The fit is a calibrated optional model mapping; it does not establish that today's universe has $E_Y/E_I$ slightly above $\varphi$ or derive a residual dark-energy component.

---

## 3. Spacetime & Gravity

### Spacetime (Cassi definition; Hypothesized closure)
- **Status**: An emergent metric is a Hypothesized extension, not a canonical field of the two-fluid PDE.
### Optional Attractive Qi-Gravity Branch (Hypothesized regularized mapping)

The canonical density PDE uses the optional constitutive force convention
$$\mathbf f=+\pi\left[1+(\varphi^6-1)q\right]\nabla\Phi,$$
which is outward for positive fixed-point $\pi$ when
$\Phi=-GM/r$. An attractive Newtonian or GR-like interpretation requires
the separate sign-changing branch below; its negative sign is not supplied
by the canonical PDE.

$$F_{\mathrm{attr}}(r)=-\frac{1+(\varphi^6-1)q}{r^2}
\left[\operatorname{erf}\!\left(\frac{r}{\sigma\sqrt2}\right)
-\sqrt{\frac{2}{\pi}}\frac{r}{\sigma}
+\exp\!\left(-\frac{r^2}{2\sigma^2}\right)\right].$$

- **Within this optional attractive branch, $r\gg\sigma$**:
  $F_{\mathrm{attr}}\to-[1+(\varphi^6-1)q]/r^2$.
- **Within this optional attractive branch, $r\to0$**:
  $F_{\mathrm{attr}}\propto-[1+(\varphi^6-1)q]r/(3\sigma^3)$.
- **$\xi=\varphi^6\approx17.944$**: Derived rung identity via
  $\varphi^6=\varphi^5+\varphi^4$; Calibrated empirical pin
  ($\xi\approx18$ from Milky Way rotation curves, 0.3% residual; ledger
  `parameter-inventory.md` §10). Interpreting the sixth power as 2 field
  components × 3 spatial dimensions is Hypothesized and conditional on
  adopting that embedding; it is not a canonical derivation.

### Effective Gravitational Coupling (Hypothesized coupling mapping)

$$G_{\mathrm{eff}}^{\mathrm{mag}} =
\frac{\pi}{\rho}\left[1+(\varphi^6-1)q\right]G_N.$$

The core, halo, and outer diagnostics below use source-specific mapped
values of $(\pi/\rho,q)$ and do not define a canonical density sweep:

- **Core model diagnostic ($r<5$)**: $\pi/\rho\approx0.274$,
  $q\approx0.147\Rightarrow G_{\mathrm{eff}}^{\mathrm{mag}}\approx1.0\,G_N$
  (GR-like magnitude comparison).
- **Halo model diagnostic ($r\sim7$)**: $\pi/\rho\approx0.633$,
  $q\approx0.669\Rightarrow G_{\mathrm{eff}}^{\mathrm{mag}}\approx7.8\,G_N$.
- **Outer model diagnostic ($r>9$)**: $\pi/\rho\approx0.723$,
  $q\approx0.701\Rightarrow G_{\mathrm{eff}}^{\mathrm{mag}}\approx9.3\,G_N$.
- **Formal unconstrained endpoint ($q=1,\pi/\rho=1$)**:
  $G_{\mathrm{eff}}^{\mathrm{mag}}=\varphi^6G_N\approx17.9\,G_N$.

At the reference attractor $\rho=\varphi$, $\pi/\rho=\varphi^{-3}$,
$q=0.872677996$ and
$G_{\mathrm{eff}}^{\mathrm{mag}}/G_N=3.726779962$ under the stated
normalization. The formal $\varphi^6$ value is an external endpoint
comparison, not a canonical free-$q$ maximum or dynamic range.

### Weak-Field Metric (Hypothesized metric closure)
    ds² = −(1+2Φ)dt² + (1−2Φ)(dr² + r²dΩ²)

- **$\Phi(r)$**: Optional Cassi potential, $\Phi(r)=-\int G_{\rm eff}(r')M/r'^2\,dr'$, rather than $-GM/r$.
- **Limiting check**: The $\xi\to0$, $\sigma\to0$, $G_{\rm eff}\to G_N$ limit is intended to recover the weak-field GR form; exact Schwarzschild recovery is not established by the canonical PDE.

### Three-Body Problem (optional solver diagnostic)
- **Status**: Numerical results under a selected dissipative regularization; they are not canonical theorems of the two-fluid PDE.
- **Reported result**: The chosen solver has an energy attractor at $E\approx-0.02$ for the tested initial conditions.
- **Shape preservation**: Symmetric configurations such as an equilateral triangle retain their shape in that solver.
- **Periodic orbits**: None were found in the tested runs; the system expands self-similarly or approaches the attractor.
- **Harmonic regime ($r\ll\sigma$)**: The selected solver reports three coupled oscillators with numerical error $\sim5.5\times10^{-10}$.
- **Scope**: The model is numerically tractable rather than analytically integrable; these diagnostics do not establish a universal 3BP closure.

### Black Hole Shadow (Hypothesized lensing mapping)
    b_crit = 3√3 · G_eff · M = b_GR · G_eff

- **Core model output ($r<5$)**: $b_{\rm crit}\approx5.2M$ (GR-like and EHT-consistent within the selected closure).
- **Halo model output ($r\approx7$)**: $b_{\rm crit}\approx14$–$50M$ (an enlarged, testable mapping).
- **Formal full-coherence endpoint of this optional mapping ($q\to1$)**: $b_{\rm crit}\approx\varphi^6$ times the GR value, $\approx17.9$ times GR, or $\approx93.2M$; this is not a canonical free-$q$ maximum or dynamic range.

### Precession Formula (Hypothesized softening mapping)
    Δφ = −√(2π)·(σ/a)³·(1+e²/4)/(1−e²)³   [Cassi softening precession]

- **Limiting check**: As $\sigma\to0$, the optional correction vanishes; the standard GR perihelion term $\Delta\phi=6\pi GM/(ac^2)$ is an external comparison, not a consequence of the canonical PDE.

---

## 4. Black Holes & Compact Objects

### Black Hole (Cassi definition; Hypothesized soliton/metric closure)
A proposed Cassi compact object is a two-fluid soliton—a stable, self-consistent equilibrium of the Yang and Yin density channels, equivalently of their amplitude doublet, regularized by the optional Gaussian softening $\sigma$.

- **Core regularity**: The selected softening closure has a harmonic core with $F\propto r$.
- **Redshift and horizon**: Whether the closure contains an infinite-redshift surface is a model question; the canonical PDE does not determine a horizon statement.
- **Smooth core**: A finite density maximum near $r\approx\sigma$ is a model output when that closure is solved.
- **GR comparison**: GR-like behavior inside the modeled photon sphere is an observational target of the closure, not a universal indistinguishability claim.

### Photon Sphere (Hypothesized lensing mapping)
    r_{\rm ps}=3\,G_{\rm eff}(r_{\rm ps})\,M

- **Scope**: This self-consistent radius is a model mapping that depends on the optional $G_{\rm eff}$ closure.
- **Core model output**: $r_{\rm ps}\approx3M$ when $G_{\rm eff}(3M)\approx1$ in the selected profile.

### ISCO—Innermost Stable Circular Orbit (Hypothesized orbital mapping)
    r_{\rm ISCO}=6\,G_{\rm eff}(r_{\rm ISCO})\,M

- **GR comparison**: $r_{\rm ISCO}=6M$ is the external GR reference.
- **Cassi model output**: The optional variable-$G_{\rm eff}$ mapping moves $r_{\rm ISCO}$ outward where $G_{\rm eff}>1$.
- **Observable consequence**: Larger modeled inner cutoffs than the GR reference are a conditional, testable mapping for X-ray iron lines (XRISM).

### Soliton Mergers (Hypothesized compact-object mapping)
- **GW150914 analogy**: A selected fluid closure models two BH-like solitons merging through fluid dynamics; the canonical PDE does not supply a spacetime waveform.
- **Chirp**: A relaxation oscillation is a candidate interpretation of the merged-fluid settling signal.
- **Ringdown**: Qi-gating damping modes are a candidate alternative to metric quasi-normal modes.
- **Conditional prediction**: A q-polarization mode beyond GR's $+$ and $\times$ would test this extension.

---

## 5. Particle Physics

### Particles (Cassi definition; Hypothesized soliton mapping)
Localized, self-stabilizing solitons are a proposed interpretation of standing-wave configurations in the two-fluid $E_Y,E_I$ square-density channels and their amplitude doublet.

- **Field content**: The canonical PDE contains the two density channels; whether all observed particles reduce to their solitons is an open model question.
- **Matter mapping**: A particle as a standing Qi wave in the cosmos-fluid is a Hypothesized interpretation.
- **Particle spectrum**: Harmonic overtones of a $\varphi$-resonant cavity are a Hypothesized mass-and-quantum-number mapping, not a derived spectrum.

### Leptons (tentative)
| Particle | Character | Fluid ratio |
|----------|-----------|------------|
| Electron | $E_Y$-dominant | Yang-weighted mode; propagation depends on the active PDE terms |
| Neutrino | $E_I$-thin | Yin-weighted mode; weakly interacting in this tentative mapping |

### Hadrons (tentative)
- **Proton**: Candidate dense $E_I$-dominant soliton with an $E_Y$-rich surface; stability and the proposed $\varphi$ energy minimum require a closed soliton model.
- **Neutron**: Candidate metastable hybrid near $\varphi$-equilibrium; the decay interpretation is Hypothesized.
- **Quark confinement**: Treating quarks as internal hadron modes is a Hypothesized mapping, not a canonical consequence.
- **Gluons**: High-frequency two-fluid standing waves are a candidate gauge-sector mapping.

### Antimatter (Hypothesized mapping)
- **Candidate definition**: A soliton with a flipped Yang/Yin amplitude configuration relative to a matter soliton.
- **Candidate annihilation channel**: Paired $E_Y,E_I$ configurations may cancel into a traveling wave; the photon interpretation requires the conditional gauge extension.

### Mass (Hypothesized mapping)
- **Candidate origin**: A soliton's stability cost may represent the energy bound into maintaining its standing wave.
- **φ-scaling**: Particle masses are a testable mapping rather than a derived law; the electron/proton mass ratio (1/1836) may relate to $\varphi^{15}\approx1428$ (within 30%).


### Electromagnetism—Conditional particle/gauge extension (Hypothesized)
The cited script `experiments/cassi_physics/cassi_electromagnetism.py` records a second-order wave ansatz and numerical toy model. The canonical live solver in §2 is first-order in the square densities $E_Y,E_I$; an exact reduction to this second-order system is not closed here.

**Conditional second-order ansatz**—A pressure-coupled particle/gauge extension may postulate:
    ∂²E_Y/∂t² = c²·∇²E_Y − ω₀²·(E_Y − φ·E_I)
    ∂²E_I/∂t² = c²·∇²E_I + ω₀²·(E_Y − φ·E_I)

**Conditional resonant mapping**: $E_Y=\varphi E_I$ is the φ-resonant ratio in this extension.
Under that condition, the $\omega_0^2$ terms vanish:
    ∂²E/∂t² = c²·∇²E,  ∂²B/∂t² = c²·∇²B
These scalar wave equations support a Mapped vacuum-wave analogy; they do not by themselves derive Maxwell's vector equations or source terms from the canonical first-order density PDE.

| EM Quantity | Cassi Analog |
|-------------|--------------|
| E (electric field) | Mapped electric-field analogue of the $E_Y$ Yang square density—radiative, electric-like correspondence |
| B (magnetic field) | Mapped magnetic-field analogue of the $E_I$ Yin square density—absorptive, magnetic-like correspondence |
| c (speed of light) | Mapped speed correspondence for this conditional extension; c = c_vacuum is an observational convention |
| Charge density $\rho_{\mathrm{EM}}$ | Hypothesized Qi-curvature source mapping $\rho_{\mathrm{EM}}=-\kappa\nabla^2q$; distinct from canonical $\rho=E_Y+E_I$ |
| Application current $J_{\mathrm{EM}}$ | Hypothesized diagnostic $\kappa\cdot\partial_t(\nabla q)$; distinct from foundational $J_\Psi$ |
| Photon | Mapped traveling $E_Y/E_I$ square-density wave at φ-resonance |

**Conditional propagation-speed mapping (Hypothesized)**:
In this extension, effective-medium refractive indices are assigned to EM and gravitational modes:
    n_EM = φ⁻¹,  n_grav = φ  →  |c_EM − c_grav| → 0 in vacuum
This conditional speed correspondence is compatible with the GW170817 constraint $|c_{\mathrm{grav}}-c_{\mathrm{EM}}|/c_{\mathrm{EM}}<10^{-15}$.
The ratio $c_{\mathrm{EM}}/c_{\mathrm{grav}}=\varphi^2$ remains a Hypothesized mapping for the effective medium; it is not selected by the canonical first-order density PDE.

### Weak Force (SU(2) × U(1)_Y gauge theory; Hypothesized extension)
See `standard-model/su2-gauge-extension.md` for the proposed gauge-sector construction. It is optional and is not selected by the canonical first-order density PDE.

Within that extension, an SU(2) gauge symmetry on the isospinor doublet $(\nu_e,e)$ is coupled to U(1)$_Y$ hypercharge. The extension assigns the W/Z mass and mixing-angle mappings
    m_W / m_Z = √(1 − φ⁻³) ≈ 0.874 (tree); 0.878 with the ρ correction
    sin²θ_W = φ⁻³ ≈ 0.236, +2.1% above the Z-pole value; the running angle
    equals it at μ* ≈ 233 GeV (the angle runs upward, not down)
    (falsifiable at FCC-ee with precision electroweak measurements; see
    `standard-model/sm-radiative-corrections.md`)

**SU(3) color (Hypothesized extension)**: A tripled-field coupling assignment gives
α_GUT = φ⁻³/(4π) and runs to α_s(m_Z) ≈ 0.058–0.061, 2.0× below measured
0.118; the required Δb = 1.70 and a complete gauge closure remain unresolved.

### 5.1 Electroweak Unification (Hypothesized extension)

The referenced gauge-sector extension proposes an SU(2) isospinor doublet coupled to the two-fluid; the canonical density PDE does not by itself derive this gauge theory.

- **Doublet**: $\Psi=(\psi_Y,\psi_I)^{\mathsf T}$ with $|\psi_Y|^2=E_Y$ and $|\psi_I|^2=E_I$.
- **φ-VEV mapping**: $\langle\Psi\rangle\propto(\sqrt{\varphi},1)^{\mathsf T}$ gives $\rho_Y/\rho_I=\varphi$ within the extension.
- **Weak mixing mapping**: $\sin^2\theta_W=\varphi^{-3}$ is an assigned VEV relation, not a canonical PDE identity.
- **Measured comparison**: $\sin^2\theta_W=\varphi^{-3}\approx0.236$ is +2.1% above the measured 0.231 at $m_Z$; the running angle reaches it at $\mu_*\approx233$ GeV (RG running is upward and does not close the gap; see `standard-model/sm-radiative-corrections.md`).
- **W/Z mass mapping**: $m_W/m_Z=\sqrt{1-\varphi^{-3}}\approx0.874$, 0.36% below the Standard Model value after the $\rho$ correction (0.878 vs 0.881); this is a conditional FCC-ee test.
- **SU(3) color mapping**: $\alpha_{\rm GUT}=\varphi^{-3}/(4\pi)$ runs to $\alpha_s(m_Z)\approx0.058$–$0.061$, 2.0× low; $\Delta b=1.70$ remains required.


**Conditional predictions and open mappings**:
- Photon-photon scattering at intensity $I\approx\sigma^2\omega_0^2$ is a Hypothesized nonlinear correction of the optional extension.
- The scalar mapping has no magnetic-charge variable; it does not establish a universal no-monopole theorem.
- Charge units of $\varphi^{-2}e$ remain a Hypothesized quantization mapping requiring gauge completion.
- A weak-force SU(2) × U(1)$_Y$ theory with a $\varphi$-VEV is the proposed extension described above.
- Gravity as a residual Qi pull is a phenomenological interpretation in selected mappings, not a derived field-theory identity.


### Strong-force scale mapping (Hypothesized, unresolved)

One proposed extension compares the same regularized force form at different softening scales:
    σ_gravity ≈ 1 kpc,  σ_nuclear ≈ 0.5 fm  (ratio: 10³⁷)

The Cassi force is reported as 4–13× stronger than Coulomb at $r\approx0.5$–$2$ fm in the selected numerical mapping. This comparison is exploratory and does not establish that the strong interaction is gravity or that one PDE supplies both sectors.

| Nuclear Concept | Cassi Analog |
|----------------|--------------|
| Strong force | Optional σ-regularized gravity mapping at fm scale |
| Nucleus | Candidate soliton in the two-fluid |
| Binding energy | Candidate energy cost of confining $E_Y/E_I$ square densities in a soliton |
| Fission | Candidate soliton splitting at a Qi node |
| Fusion | Candidate soliton merging (two → one, with binding-energy release) |
| Half-life | Candidate Qi-coherence decay time of a soliton |
| Radioactivity | Candidate $E_Y/E_I$ square-density rearrangement toward lower energy |
| Neutron star | Candidate soliton matter at high density |
| Quark-gluon plasma | Candidate Qi fluid above the selected σ-resolution scale |

- The canonical PDE supplies no separate strong-force sector and does not close the gravity-to-nuclear mapping.
- The observed stability of ⁵⁶Fe is an external nuclear datum; interpreting it as a deepest soliton well is Hypothesized.
- Fusion and fission as soliton merging or node splitting are Hypothesized process mappings.

**Coupling status**: For the scale mapping to account for the strong interaction, the
Cassi coupling would need to run by ~40 orders of magnitude from galactic
($G\sim1$, $\xi\approx18$) to nuclear ($\alpha_{\rm strong}\sim1$) scales. A
mechanism for that running, such as σ-dependent renormalization or a complete
SU(3) gauge coupling flow to $\alpha_s(m_Z)\approx0.118$, remains unresolved.

## 6. Time

### Conversion-flow time (Derived conditional)

For the isolated canonical conversion subflow,

$$
\partial_t E_Y|_{\mathrm{conv}}
=-\lambda(1-q)\varepsilon,
\qquad
\partial_t E_I|_{\mathrm{conv}}
=+\lambda(1-q)\varepsilon,
\qquad
\varepsilon=E_Y-\varphi E_I.
$$

The transfer defines the dimensionless exposure $\chi_F$ and conversion age
$\tau_F$:

$$
d\chi_F
:=\frac{dE_I|_{\mathrm{conv}}}{\varepsilon}
=-\frac{d\varepsilon}{(1+\varphi)\varepsilon}
=\lambda(1-q)\,dt,
\qquad
d\tau_F:=\frac{d\chi_F}{\lambda}=(1-q)\,dt.
$$

For resolved nonzero endpoints on one conversion branch,

$$
\Delta\tau_F
=-\frac{1}{(1+\varphi)\lambda}
\ln\left|\frac{\varepsilon_1}{\varepsilon_0}\right|
=\int(1-q)\,dt.
$$

This identity uses the canonical bounded coherence
$q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$, or its explicitly
normalized physical-density form. Other quantities also named $q$ do not
inherit the clock equation. Transport, diffusion, and source increments
require separate accounting.

### Candidate physical time (Hypothesized common lapse)

Let $x_\star$ be a reference worldline with $q_\star<1$. The candidate
physical proper time is

$$
\boxed{
\frac{d\tau_{\mathrm{phys}}(x)}{d\tau_\star}
=N_q(x\mid x_\star)
:=\frac{1-q(x)}{1-q_\star}
}.
$$

With an external open-gate normalization,
$d\tau_{\mathrm{phys}}=(1-q)dt=d\tau_F$. The $q_\star=0$ case is a
normalization limit; an active canonical conversion reference requires
$\varepsilon_\star\neq0$ and hence $q_\star>0$. The candidate time is
accumulated along a worldline:

$$
\Delta\tau_{\mathrm{phys}}[\gamma]
=\int_\gamma N_q\,d\tau_\star.
$$

Spatially varying $q$ therefore desynchronizes worldline clocks and supplies
no global time coordinate by itself.

The canonical conversion equation admits the factorization

$$
\frac{d\varepsilon}{dt}
=-(1+\varphi)\lambda K(q)N(q)\varepsilon,
\qquad K(q)N(q)=1-q.
$$

Candidate physical time selects $K=1$ and $N=1-q$, so
$d\varepsilon/d\tau_{\mathrm{phys}}
=-(1+\varphi)\lambda\varepsilon$. Uniform physical time with gated kinetics,
$K=1-q$ and $N=1$, produces the same conversion trace. Conversion data alone
therefore establish $\tau_F$ but do not establish a universal lapse.

### Clock-universality criterion

For an independent clock phase $\Theta_a$ with intrinsic frequency
$\omega_a$ per unit physical time, define

$$
\mathcal C_a
:=\frac{1}{\omega_a}\frac{d\Theta_a}{d\tau_\star},
\qquad
\mathcal C_F
:=-\frac{1}{(1+\varphi)\lambda\varepsilon}
\frac{d\varepsilon}{d\tau_\star}.
$$

The candidate predicts
$\mathcal C_a=\mathcal C_F=N_q$ for every independent local sector.
CT-2 requires a conversion receipt and at least two independent
non-conversion clocks. A reproducible cross-clock disagreement contradicts
the universal interpretation while preserving the conversion identity.

### Arrow and entropy status

The conversion subflow has the exact Lyapunov relation

$$
\frac{d}{dt}\frac{\varepsilon^2}{2}
=-(1+\varphi)\lambda(1-q)\varepsilon^2\leq0.
$$

Under the candidate clock postulate this becomes

$$
\frac{d}{d\tau_{\mathrm{phys}}}\frac{\varepsilon^2}{2}
=-(1+\varphi)\lambda\varepsilon^2\leq0.
$$

The separate proxy
$S_q=-qk_B\ln\varphi$ and its budget
$I_q=qk_B\ln\varphi$ remain Asserted/Hypothesized mappings. No monotonicity
theorem for $q$ or identity with thermodynamic or Shannon entropy follows
from the conversion arrow.

### Domain and physical scope

For finite canonical fields, $0\leq q<1$. The $q\to1$ limit is a degenerate
clock boundary and cannot be used as the reference. Exact
$\varepsilon=0$ has no readable conversion tick, although $N_q$ remains
continuous; an independent clock is required there. Memory-bearing $q$
makes $\tau_{\mathrm{phys}}$ a history-dependent worldline functional.
Physical seconds require an independently calibrated reference clock and
the physical-density scale $\rho_\star$.

The candidate supplies no complete spacetime metric, light cone, global
synchronization rule, or derivation of GR time dilation. Those require a
closed common-lapse action with the mandatory $q$-backreaction and constraint
terms described in `foundations/unified-lagrangian.md` §1.7. The canonical
framework therefore makes no time-travel or cosmological-origin claim from
this clock alone.

---

## 7. Consciousness & Psychology

### Overview
See `consciousness/consciousness-from-phi.md` for the broader proposed theory.
The entries below are Hypothesized or Speculative application mappings; they are
not canonical neuroscience derivations from the two-fluid PDE.

### Term Mapping
| Cassi Physics | Consciousness Framework | Connection |
|-------------|------------------------|------------|
| $E_Y$ (Yang square density) | Active-attention phenomenology | Proposed symbol correspondence in a neural application |
| $E_I$ (Yin square density) | Receptive-attention phenomenology | Proposed symbol correspondence in a neural application |
| $\mathbf Q=(\rho,\mathbf J_\Psi)$ | Qi energy-and-current pair | Candidate self-aware-field mapping from neural self-prediction |
| q-coherence | Level of self-awareness | Candidate proxy using prediction error $\varepsilon=\psi-\hat\psi$ |
| φ-attractor | Optimal mental state (flow, equanimity) | Hypothesized cognitive mapping |
| Gaussian softening σ | Neural refractory period, minimum resolution | Hypothesized regularization mapping; no neural resolution theorem follows |
| $\varphi$-scaled chakras (Hypothesized application mapping) | 13 frequency bands of conscious experience | Proposed neural wave decomposition; not a canonical phase or rung clock |

### Scale Invariance (Hypothesized application)
Scale invariance is a property of selected nondimensional solver forms. Applying the
same PDE at Planck, galactic, and neural scales is a Hypothesized extrapolation, not
a result established across those regimes. A proposed neural mapping writes

    Q = Qi-fluid proxy at neural scale
    = |ψ|² · (1 − |ε|²/(|ψ|² + φ⁻²))
    where ε = ψ − ψ̂  (self-prediction error)

The persistent-self and cross-chakra standing-wave interpretation is Speculative
and depends on the IIR filter and neural constitutive choices.

### Key Principle (Speculative interpretation)
In this interpretation, consciousness is not identified with the neural field $\psi$;
$\psi$ is treated as a possible medium for Qi-like structure. Standing waves,
vortices, and currents are analogies for the proposed dynamics, not a derivation
of consciousness from the canonical PDE.
---

## 8. Life

### Definition (Speculative/Hypothesized life mapping)
Life is modeled as a possible self-sustaining Qi condensate—an open thermodynamic
system that maintains a coherence level above a candidate death threshold by
exporting entropy. This is a framework mapping, not a biological definition.

    q_death ≈ φ⁻² ≈ 0.382  (Hypothesized threshold candidate; no recovery theorem)
    P_meta = (q_t − q_0)·mass·T·|q̇| / η  (Hypothesized metabolic bookkeeping)

### Key Principles (Hypothesized mappings)
- **Metabolism**: Candidate entropy-export mechanism for maintaining q, analogous to a coherence bubble.
- **Evolution**: Candidate optimization of q-maintenance strategies through selection.
- **Intelligence**: Candidate optimization of q across longer timescales.
- **Consciousness**: Candidate self-aware q-feedback above an unspecified complexity threshold.
- **Death**: A fall below the candidate $\varphi^{-2}$ threshold may be associated with loss of coherence; irreversibility is not established.
- **Reproduction**: Candidate splitting of a Qi condensate into two copies.
  - Child inheritance $q_{\rm child}\approx q_{\rm parent}/2$ is a Hypothesized mapping.
  - Growth may be represented as increasing q toward adult levels.
  - Senescence may be represented as falling q after reproductive peak.

### Scale Invariance (Hypothesized biological extrapolation)
A proposed biological scaling hypothesis applies the same q-maintenance form to a
bacterium and a blue whale. The claim of metabolic scaling across 21+ orders of
magnitude requires independent biological calibration and is not established by
the canonical PDE.

### Connection to Coherence Bubble (Speculative analogy)
A living organism may be compared with a coherence bubble in this analogy. The
distinction between chemical energy maintaining q and direct Qi feedback remains
Speculative; no biological identity is derived.

---

## 9. Chemistry

### Definition (Hypothesized chemistry mapping)
A proposed mapping treats chemistry as $E_Y/E_I$ square-density sharing between
candidate atomic solitons. A chemical bond may be represented as Qi coherence
between atomic two-fluid configurations; this analogy does not replace molecular
quantum mechanics.

### Bond Types as Qi States
| Bond | Qi Character | Cassi Analog |
|------|-------------|--------------|
| Ionic | Strong $E_Y/E_I$ separation | One atom transfers Yang square density in the electron mapping, and the other accepts it |
| Covalent | Shared $E_Y/E_I$ standing wave | Shared square-density configuration between nuclei |
| Metallic | Delocalized Qi across many nuclei | The Yang square-density channel is delocalized across the lattice |
| Hydrogen | Weak partial coherence | Fractional q-transfer between molecules |
| van der Waals | Fluctuation-induced q | Transient $E_Y/E_I$ misalignment creates dipole |

### Reaction Rates (Hypothesized mapping)
A chemical reaction may be represented as a Qi rearrangement:
    Rate ∝ exp(−ΔG*/(k_B·T))
where $\Delta G^*$ is a proposed Qi-coherence barrier. The canonical PDE supplies
no molecular rearrangement rule or forbidden-region criterion.

### Catalysis (Hypothesized mapping)
A catalyst may be represented as lowering a proposed Qi-coherence barrier through
an alternative rearrangement path; the $\varphi$-equilibrium interpretation
requires molecular calibration.

### The Periodic Table (Hypothesized soliton mapping)
Treating elements as allowed two-fluid soliton modes at the $\sigma$ scale and
rows as $\varphi$-resonant shells is a speculative organization analogy, not a
derived periodic-table or valence law.

---

## 10. Phase Transitions & Thermodynamics

### Definition (Hypothesized thermodynamic mapping)
A proposed mapping treats phase transitions as Qi-ordering changes in how the
$E_Y$ and $E_I$ square densities are organized at macroscopic scales. The mapping
does not define thermodynamic phases or derive their thresholds.

| Phase | Candidate q-range | Candidate $E_Y/E_I$ Square-Density Organization |
|-------|-------------------|-----------------------------------------------|
| Solid | q > φ⁻¹ | $E_Y$ and $E_I$ locally locked in a fixed lattice—strong local q |
| Liquid | φ⁻² < q < φ⁻¹ | Partially ordered square densities under shared advection—medium coherence |
| Gas | q < φ⁻² | Weakly coupled $E_Y/E_I$ square-density channels |
| Plasma | q ≈ 0 | Weak channel correlation; conversion and spatial terms need not lock the channels |
| Superfluid | q → 1 | Strong coherence with a common shared-advection response |

### Phase Transitions as Qi Thresholds (Hypothesized mapping)
    Melting: q passes through φ⁻¹ (solid → liquid)
    Boiling: q passes through φ⁻² (liquid → gas)
    Critical point: q = φ⁻³ (gas and liquid indistinguishable in the proposed mapping)

The $\varphi$-scaled threshold sequence is a testable hypothesis for phase
transition-temperature ratios, not a canonical prediction; noble-gas data would
provide an external calibration.

### Work and Heat (Hypothesized Qi mapping)
- **Work**: Candidate coherent Qi transfer with q approximately preserved.
- **Heat**: Candidate incoherent Qi transfer associated with q loss.
- **Temperature**: $T=(\partial S_{\mathrm{thermo}}/\partial E)^{-1}$ remains the
  standard thermodynamic definition; a q-based decoherence rate is only a model mapping.

The Carnot efficiency is a standard external thermodynamic result. Representing it
in q is a proposed mapping, and the canonical PDE-level second-law theorem remains open.

---

## 11. Information

### Definition
**Information proxy (Asserted/Hypothesized)**: Define the local proxy
$I_q=k_B q\ln\varphi$, or $i_q=q\ln\varphi$ nats and
$b_q=q\log_2\varphi$ bits, for an independently counted cell or event.
The proxy is bounded by $0\le q\le1$ and is not Shannon entropy; a total
system information value requires an explicit count and aggregation rule.

For one independently counted cell or event, the full q range contributes at most
$\ln\varphi=0.4812$ nats $=0.6942$ bits. One bit therefore requires an aggregate
q-budget satisfying $\sum_i\Delta q_i=\ln2/\ln\varphi\approx1.4404$ across
independently counted units; no single local $\Delta q$ can equal 1.4404 because
each $q_i\in[0,1]$.

The openness $(1-q)$ belongs to the local conversion flow, not the stored q stock.
A solver may report the local proxy rate
$\widehat{\dot I}_q=\lambda(1-q)\,k_B\ln\varphi$ in solver units, but this is
not a universal information rate without a spatial count, timescale, and constitutive map.

### Landauer's Principle
Erasing one bit has the standard external Landauer bound
$E\ge k_B T\ln(2)$, with equality only in the ideal reversible limit.
In the q accounting, one bit corresponds to the aggregate budget
$\sum_i\Delta q_i=\ln2/\ln\varphi\approx1.4404$ above; it is not a local q decrement.

The q proxy and the Landauer bound are separate bookkeeping statements; no
thermodynamic unification is derived.

### Maxwell's Demon
The demon provides a phenomenological analogy for sorting the $E_Y$ and $E_I$
density channels under standard entropy-export constraints. The coherence-bubble
comparison is Speculative; it is not an identity for the demon or a thermodynamic
mechanism derived from the canonical PDE.

---

## 12. Cosmology—CMB, Inflation, Large-Scale Structure

### The CMB (Hypothesized cosmology mapping)
An optional cosmology extension interprets the Cosmic Microwave Background as a
last-scattering surface for the two-fluid, with a conditional photon mode near
$E_Y=\varphi E_I$. The canonical PDE does not derive matter decoupling,
free-streaming, or a complete recombination history.

Conditional tests in that extension:
- **Primordial B-mode level**: The no-inflaton version predicts no primordial
  tensor B-mode contribution; this is an optional model prediction.
- **Preferred axis**: Residual large-scale Qi coherence may produce an axis,
  testable with Planck.
- **CMB cold spot**: A lower-q coherence void is a candidate interpretation.

### Inflation as φ-Reset (Hypothesized cosmology mapping)
An optional model interprets inflation as a period in which $\pi/\rho$ (the
Yang/Yin density ratio) is driven away from its attractor and a conversion closure
returns it toward equilibrium. This is not a canonical consequence and does not
exclude a separate inflaton without an independent cosmology derivation.

    H_inflation ∝ (φ − r_initial)  (conditional expansion ansatz)
    Slow roll: r → φ⁻³ as equilibrium is restored in the selected model
    Reheating: candidate transfer of Qi to photons and matter

Conditional tests:
- **Primordial B-modes**: The no-tensor version predicts no B-modes.
- **Spectral tilt**: $n_s<1$ is a candidate attractor mapping.
- **Running**: negligible running is a candidate single-attractor mapping, not a
  theorem of the canonical PDE.

### Large-Scale Structure (Hypothesized cosmology mapping)
Treating galaxies and clusters as frozen-in Qi fluctuations and the cosmic web as
q-fluctuations amplified by gravity is an optional interpretation. The canonical
PDE does not establish the initial perturbation spectrum or its transfer function.

    δ_galaxy ∝ δ_q  (conditional galaxy-overdensity mapping)
    r_void ∝ φ^n   (conditional void-size hypothesis)

---

## 13. Unification—The Theory of Everything (optional program)

### Shared canonical core
The canonical two-fluid PDE supplies a shared density-and-advection core. An
optional application realization may replace the canonical openness
$\lambda(1-q)$ with the asserted transmission input
$\omega_0g(q)$; that replacement does not change the canonical state variables
or promote the application closure to a universal law:

$$
\partial_t E_Y+\nabla\!\cdot(E_Y\mathbf u)
=-\omega_0g(q)(E_Y-\varphi E_I)+D\nabla^2E_Y,
$$

$$
\partial_t E_I+\nabla\!\cdot(E_I\mathbf u)
=+\omega_0g(q)(E_Y-\varphi E_I)+D\nabla^2E_I,
$$

$$
\partial_t\mathbf u+(\mathbf u\!\cdot\!\nabla)\mathbf u
=-\nabla P-\nabla\Phi+\nu\nabla^2\mathbf u-\eta\mathbf u.
$$

where:
- **$E_Y,E_I$**: Nonnegative square densities; $\Psi^{(+)}$ is their exact positive-root coordinate lift.
- **ρ, π**: $\rho=E_Y+E_I\ge0$ and signed $\pi=E_Y-E_I$.
- **u**: One shared advection field for both density channels.
- **χ**: Optional potential-relative drift, with the mobilities and flux signs defined in §1; it is absent when χ=0.
- **φ ≈ 1.618**: The canonical two-fluid attractor parameter.
- **$g(q)=q/(\varphi^2+q^2)$**: Asserted single-channel application input; selection audit in `computations/gate_origin_audit.py`.
- **σ**: Optional softening parameter in selected extensions, not a universal scale mechanism.
- **ξ = φ⁶ ≈ 17.944**: Derived rung identity and Calibrated empirical pin; using it as a cross-sector coupling is a Hypothesized mapping.
- **$D$**: Scalar density diffusion coefficient; it is separate from the shared-velocity viscosity $\nu$.
- **ν**: Shared-velocity viscosity coefficient; **η** is an optional velocity-damping coefficient.

### How Each Force Is Mapped (optional sector program)
| Scale | σ | Phenomenon | Scope |
|-------|---|-----------|-------|
| fm | 0.5 fm | Nuclear | Hypothesized scale mapping |
| m–km | Earth σ | Daily life | Optional gravity/field mapping |
| kpc | galaxy σ | Galactic | Calibrated/conditional rotation-curve mapping |
| Mpc | cosmological σ | Cosmic | Hypothesized cosmology mapping |

### Four Optional Sector Programs
1. **Dirac QM**: Candidate bridge from the two-fluid at quantum scale to a Dirac/QFT description; closure is not canonical.
2. **GR/Gravity**: Hypothesized metric and $G_{\rm eff}(r)$ closure at large scale.
3. **Gauge fields**: Hypothesized SU(3) × SU(2) × U(1) extension of the two-fluid isospin structure.
4. **Quantum Gravity**: Hypothesized σ-regularized quantization; UV finiteness is unestablished.

See `experiments/cassi_physics/cassi_quantum_gravity.py` for the cited program
script and its current formal status.

The fourth program remains Hypothesized. The Gaussian kernel
    G(k²) = exp(−k²·σ²/2) / k²
is a proposed high-k suppression ansatz; it does not by itself prove absence of
divergences at all orders, renormalizability, unitarity, or a complete quantum
gravity theory.

The sector mappings may be compared at φ-equilibrium, but no claim that one PDE
reproduces all known physics at all σ-scales is established.

> **Implementation mapping (conditional)**: The following scripts implement selected ansätze:
> 1. **Relativistic QM bridge**: `DiracBridge` explores a Dirac-equation correspondence.
> 2. **GR/Gravity bridge**: `QiGravitySolver3D` explores an emergent-gravity closure with $G_{\rm eff}(r)$ and $\xi=\varphi^6$.
> 3. **Gauge bridge**: `two-fluid/cassi_su2_bridge.py` explores SU(2)×U(1)$_Y$ and a candidate SU(3) coupling flow.
>
> These implementation mappings describe how selected extensions are computed;
> they do not establish the corresponding sector closures.

---

## 14. Observables & Predictions

### Model Comparisons (conditional)
These rows record comparisons made by selected solvers or mappings. Agreement with
an external datum does not confirm the canonical PDE or an optional sector closure.
| Observation | Cassi comparison | Status |
|-------------|------------------|--------|
| Dark energy (DESI DR2) | $w_0=-0.87$ | $2\sigma$ from DESI $\approx-0.75\pm0.06$ [INFERENCE]—tension, not matched |
| Galaxy rotation curves | Qi-enhanced $G_{\rm eff}$ mapping | MW comparison Calibrated/Mapped; dwarf proxy screen places 7/8 nominal ratios and 6/8 lower propagated $\sigma_{\text{los}}/R_e$ bounds above the optional pure-$G$ endpoint; no likelihood verdict |
| Baryonic Tully-Fisher | Slope ≈ 0.96 | Consistent comparison |
| Mercury precession | GR limit ($\sigma\to0$) | Selected limit matches 43″/century |
| BH shadow (EHT) | GR-like core $G_{\rm eff}\approx1$ | Consistent comparison with M87* |
| Lagrange stability | σ-increases stability | Verified in the selected numerical model |
| 3BP attractor | Energy attractor at $E\approx−0.02$ | Verified in the selected numerical model |

### Conditional/Falsifiable Mappings
| Mapping | Mechanism | Test |
|---------|-----------|------|
| BH shadow ~5.2M (core) | Optional core $G_{\rm eff}\approx1$ | EHT (already consistent) |
| Larger BH shadow from halo | Optional halo $G_{\rm eff}\approx10$ | Future EHT at larger angles |
| Accretion disk ISCO ~60M | Optional variable-$G_{\rm eff}$ mapping | XRISM iron-line profiles |
| GW q-polarization | Conditional two-fluid extension | LIGO/Virgo/KAGRA beyond $+$,$\times$ |
| Regularized core | Optional σ softening → harmonic behavior | Future quantum-gravity tests |
| φ-scaled particle masses | Hypothesized $E_Y/E_I$ ratios → harmonic overtones | Future collider data |
| Life as Qi condensate | Hypothesized metabolic scaling | Measurable P(q) in organisms |
| Nuclear scale mapping | Hypothesized σ-regularized force comparison | Precision nuclear data |
| Strong-force scale mapping | Unresolved force-ratio comparison | Lattice QCD verification |
| Conditional EM mapping | Hypothesized second-order particle/gauge extension with $E_Y/E_I$ square-density analogues | Optical/EM experiments after an independently closed gauge reduction |


**Unified Lagrangian (structural assembly; optional sector closure):** The displayed
action is an algebraic assembly of named sectors. Its structural coefficients
and inputs are catalogued in `parameter-inventory.md`; external, calibrated,
mapped, and solver inputs retain their recorded statuses. The assembly does not
prove that every sector is derived from the canonical PDE.
See `foundations/unified-lagrangian.md` for the complete derivation.

$$
\mathcal{L}_{\text{Cassi}} = \mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}
$$

Each subsector has its own document:
- Two-fluid core ($\mathcal{L}_{\text{TF}}$): `foundations/cassi-first-principles.md`
- Dirac matter ($\mathcal{L}_{\text{D}}$): `cassi_dirac_bridge.py`
- Gravity ($\mathcal{L}_{\text{GR}}$): `foundations/xi-derivation.md`, `theory/qi-fluid-formalism.md`
- SM gauge ($\mathcal{L}_{\text{SM}}$): `standard-model/su2-gauge-extension.md`, `standard-model/sm-from-phi.md`
- Mixing ($\mathcal{L}_{\text{mix}}$): `foundations/unified-lagrangian.md`

**Cosmology:** An optional $\varphi$-governed two-fluid extension compares inflation,
baryogenesis, and dark-matter mappings; the canonical PDE does not solve all three
cosmology problems.

### Conditional Cosmology Comparisons
| Phenomenon | Mechanism | Cassi Comparison | Observed | Gap |
|-----------|----------|------------------|----------|-----|
| Inflation | Yang/Yin ratio $r\to\varphi$ | $n_s=0.9691$, $r=0.0075$ ($12/N_e^2$ at $N_e=40$—Mapped window, ledger §10 row 495) | $0.9649\pm0.0042$ | $1.0\sigma$ |
| Baryogenesis | $\varphi^{-3}$ chiral asymmetry → sphalerons | $\eta=\varphi^{-44}\approx6.38\times10^{-10}$ | $6.0\times10^{-10}$ | Within 6.3% |
| Dark Matter | High-Qi condensate, $G_{\rm eff}$ boost | $\Omega_{\rm DM}/\Omega_b=\varphi^3\approx4.236$ | $5.39$ | 21% open tension |

New theory documents:
- `cosmology/cosmology-from-phi.md` | Inflation, baryogenesis, dark matter from $\varphi$
- `foundations/unified-lagrangian.md` | Structural action assembly; external, calibrated, mapped, and solver inputs are tracked separately
- `foundations/xi-derivation.md` | $\xi = \varphi^6$ first-principles derivation
---

## 15. Code & Implementation

### Key Scripts
| File | Purpose |
|------|---------|
| `two-fluid/cassi_two_fluid_3d_gpu.py` | Core two-fluid PDE solver |
| `two-fluid/cassi_gr_bridge.py` | Hypothesized GR extension with an optional $G_{\rm eff}(q)$ closure |
| `two-fluid/universal_cassi_solver.py` | Selected formation solver coupling PDE and N-body components |
| `two-fluid/cassi_nbody.py` | Cassi N-body particle integrator |
| `experiments/cassi_physics/cassi_three_body.py` | Selected three-body problem solver with Qi damping |
| `experiments/cassi_physics/cassi_black_hole_raytracer.py` | Heuristic black-hole shadow mapping |
| `experiments/cassi_physics/cassi_nuclear.py` | Optional nuclear/softening mapping |
| `experiments/cassi_physics/cassi_quantum_gravity.py` | Exploratory quantum-gravity mapping using σ regularization; UV finiteness is not established |
| `experiments/cassi_quantum_measurement.py` | Conditional Born-rule threshold mapping (parent repo) |
| `experiments/cassi_time.py` | Hypothesized arrow-of-time mapping (parent repo) |
| `experiments/cassi_coherence_bubble.py` | Speculative consciousness-bubble mapping (parent repo) |
| `experiments/cassi_life.py` | Speculative self-sustaining Qi-condensate mapping (parent repo) |
| `experiments/cassi_spacetime_variable_geff.py` | Optional spatially varying $G_{\rm eff}(r)$ closure (parent repo) |
| `experiments/cassi_accretion_disk.py` | Conditional accretion-disk emission mapping (parent repo) |
| `foundations/unified-lagrangian.md` | Structural action assembly for named sectors; it does not establish all-sector unification or parameter-independent predictions |
| `standard-model/su2-gauge-extension.md` | Hypothesized SU(2) × U(1)_Y gauge extension with φ-VEV |
| `two-fluid/cassi_su2_bridge.py` | Hypothesized SU(2) gauge bridge with φ-governed weak-force mapping |
| `two-fluid/run_electroweak.py` | Electroweak comparison runner for the W/Z mass mapping |
| `foundations/xi-derivation.md` | ξ = φ⁶ first-principles derivation |
| `CassiCosmos/` | Real-time exploratory universe simulator |
### Managed Skills
| Skill | Purpose |
|-------|---------|
| `godot-compute-nbody` | Compute shader N-body in Godot 4 |

### Key Constants
| Symbol | Value | Meaning |
|--------|-------|---------|
| φ | 1.6180340 | Canonical two-fluid attractor ratio |
| φ⁻¹ | 0.6180340 | Inverse golden ratio |
| φ⁻² | 0.3819660 | Yang-Yang coupling-floor value used in selected gate conventions |
| φ⁻³ | 0.23606798 | Reference $\pi/\rho$ value in selected vacuum/cosmology mappings |
| ξ = φ⁶ | 17.944 | Derived rung identity (φ⁶ = φ⁵ + φ⁴); calibrated empirical pin for a Qi-gravity coupling mapping |
| PHI_6 = φ⁶ | 17.944 | Derived rung identity and calibrated empirical pin used by selected Qi-gravity mappings |
| $\lambda$ | 0.1 | Asserted solver normalization/timescale (inverse-time convention); $\lambda=1/(2w)$ with $w=5$ is a Hypothesized Wu Xing linkage requiring independent cycle-time and dynamical closure |
| `σ` | 0.1–1.0 (code units) | Optional Gaussian softening parameter in selected closures |
| `cosmology/cosmology-from-phi.md` |—| Optional cosmology mappings for inflation, baryogenesis, and dark matter |
| $q_{\mathrm{eq}}$ | 0.873 at the stated reference state | Density-dependent coherence; $1-q_{\mathrm{eq}}=\varphi^{-2}/3\approx0.127$ is the corresponding gate openness |

---

---

## 16. Epistemic Tiers

Every claim in the framework carries an epistemic tier. The ladder, highest to
lowest: **Derived > Calibrated > Mapped > Hypothesized > Speculative >
Creative**. Full definitions with worked examples:
`open-questions-cassi-answers.md` §Epistemic Tiers and
`hypotheses/README.md` §Epistemic Tier Definitions.

- **Derived**—a priori mathematical consequence of $\varphi$ + the two-fluid
  PDE; zero fitted or anchored constants. The governing equation is the
  framework's postulate; a claim that merely restates the axiom is the axiom,
  not a Derived consequence.
- **Calibrated**—the framework supplies the form; the constant's value is
  anchored to a stated observation, and downstream claims that use the pinned
  value inherit Calibrated unless independently derived. Example: $\xi =
  \varphi^6$ (Derived algebraic identity, Calibrated empirical pin $\xi \approx 18$
  from the Milky Way rotation curve).
- **Mapped**—the placement (cascade step, exponent, offset, candidate, normalization)
  was selected or fitted to data: search tables, grid scans, nearest-integer
  logs of measured ratios, back-solved normalizations, candidate tables, free
  parameters closing a gap, scan highlights. The fit MUST be recorded in the
  Fit-Status Ledger (`parameter-inventory.md` §10). A Mapped claim carries no
  evidential weight until the placement is independently derived.
- **Hypothesized**—mechanism proposed with a pinned $\varphi$-power or a
  testable prediction; derivation not closed, value not anchored and not
  fitted.
- **Speculative**—framework-consistent; mechanism sketched, prediction not
  yet pinned, testing pending.
- **Creative**—exploration, not a claim (`speculations/creative-extensions/`);
  exempt from the evidential ladder and the ledger duty.

Bookkeeping words—Reference, Index, Synthesis, Plan, Registry, Catalog, Open
problem—are genres rather than epistemic claims and do not sit on the ladder.
"Tested" is a verification marker that attaches to a tier and does not upgrade
it. Use one of the five evidential tiers defined above for claims; reserve Creative for exploratory applications outside the ladder.

---

*End of definitions. This is a living document—add entries as the framework grows.*
