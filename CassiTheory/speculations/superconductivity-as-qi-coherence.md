# Superconductivity as a Qi-Coherence Hypothesis

## Status: Creative—August 2026

## Abstract

This document defines a Creative material model in which a Cassi-inspired coherence variable modulates an effective electronic dissipation or pairing coefficient. The construction is phenomenological: canonical $E_Y,E_I,q$, and $\lambda$ are not electron, phonon, resistance, or gap variables, and the two-fluid PDE contains no electronic Hamiltonian. A viable mechanism would need a microscopic matter-to-field bridge, gauge-covariant current dynamics, a derived attractive interaction, and quantitative comparison with established superconductivity data.

**Epistemic status:** Creative. The transport mapping, material coherence variable, effective interaction, gap equation, transition-temperature relation, and proposed discriminators are unregistered hypotheses. No part of this document is a Cassi prediction.

---

## 1. A Proposed Transport Mapping

### 1.1 Separate the canonical state from material variables

For a candidate metal model, introduce $U_{\text{drift}}$ for organized carrier energy density, $U_{\text{th}}$ for thermal carrier-plus-lattice energy density, and $q_m\in[0,1]$ for a material coherence statistic. These quantities are not identified with canonical $E_Y,E_I,q$ without a constitutive map.

A Cassi-inspired damping ansatz could borrow the rank-one conversion form:

$$
\frac{dU_{\text{drift}}}{dt}
=\mathbf J\!\cdot\!\mathbf E
-\lambda_m(1-q_m)(U_{\text{drift}}-\varphi U_{\text{th}}),
$$

with the opposite transfer added to $U_{\text{th}}$. Here $\lambda_m$ is a material rate. The equation is an application model; it is not obtained by substituting electronic variables into the canonical PDE.

### 1.2 What this ansatz does and does not establish

The borrowed term supplies one tunable damping channel. It does not derive Ohm's law, the Drude relaxation time, a Kubo conductivity, charge conservation, flux quantization, the Meissner effect, or a superconducting condensate. In particular, suppressing one dissipative term as $q_m\to1$ does not prove zero total resistance because impurity, phonon, electron-electron, boundary, and radiative channels remain unless the microscopic model closes them.

The asserted gate input

$$g(q_m)=\frac{q_m}{\varphi^2+q_m^2}$$

may be tested as an additional transmission factor, but it is not part of the canonical conversion coefficient. A model using $\lambda_m g(q_m)(1-q_m)$ must declare that extra multiplication and fit or derive $\lambda_m$ and the material definition of $q_m$.

---

## 2. A Candidate Pairing Coupling

### 2.1 The missing microscopic bridge

Canonical $q$ is an algebraic diagnostic of two nonnegative densities. It is not an electron wavefunction, an electronic order parameter, or an energy functional. The expression

$$\frac{\lambda}{2}(\Psi_0^2-\varphi\Psi_1^2)^2$$

therefore cannot be used as an electronic excitation energy without defining the fields, their units, their coupling to Bloch states, and an action whose variation produces both field and electron equations.

Opposite electron momenta cancel electric current in a zero-center-of-mass pair, but their positive energy densities do not cancel. A current-carrying condensate also has nonzero pair momentum. “Qi neutrality” consequently supplies no pairing theorem.

### 2.2 A testable effective interaction

One possible microscopic starting point is a declared effective pairing channel

$$
H_{\text{int}}^{(q)}
=-\sum_{\mathbf k,\mathbf k'}
V_q(\mathbf k,\mathbf k';q_m)\,
c^\dagger_{\mathbf k\uparrow}c^\dagger_{-\mathbf k\downarrow}
c_{-\mathbf k'\downarrow}c_{\mathbf k'\uparrow},
$$

where a positive kernel $V_q$ is an attractive interaction. Cassi relevance would require deriving this kernel from a field coupling rather than choosing it to reproduce a gap. The resulting symmetry, cutoff, isotope dependence, and $T_c$ must then follow from the electronic gap equation. Until that bridge exists, $V_q$ and “Qi-mediated pairing” are Creative inputs.

---

## 3. The Gap Equation

### 3.1 Phenomenological Qi–Ginzburg–Landau ansatz

Let $\psi(\mathbf r)$ be a superconducting order parameter and use the standard gauge-covariant Ginzburg–Landau free-energy density

$$f=f_n+a(T,q_m)|\psi|^2+\frac b2|\psi|^4+
\frac{\hbar^2}{2m^*}\left|\left(-i\nabla-\frac{e^*}{\hbar}\mathbf A\right)\psi\right|^2.$$

A proposed coherence coupling is

$$a(T,q_m)=a_0\,[q_c-q_m(T)].$$

This definition parameterizes a transition; it does not derive one. The coefficients $a_0,b,m^*,q_c$ and the observable used to estimate $q_m$ must be specified for each material.

### 3.2 A temperature ansatz

A Debye-like model may be used to test whether a material coherence statistic tracks thermal modes:

$$
q_m(T)=q_m(0)-\gamma
\int_0^{\omega_D}
\frac{D(\omega)\,\hbar\omega/E_{\text{coh}}}
{\exp(\hbar\omega/k_BT)-1}\,d\omega ,
$$

where $D(\omega)$ is normalized consistently and $\gamma$ carries whatever units that normalization requires. In a three-dimensional Debye approximation, selected definitions can give a leading low-temperature change proportional to $T^4$:

$$q_m(T)\approx q_m(0)-\alpha_TT^4.$$

If this ansatz holds and the transition is defined by $q_m(T_c)=q_c$, then

$$
T_c=\left[\frac{q_m(0)-q_c}{\alpha_T}\right]^{1/4}.
$$

This is an algebraic consequence of the chosen $T^4$ parameterization. It is not a parameter-free $T_c$ prediction, because $q_m(0)$, $q_c$, and $\alpha_T$ are external or fitted material quantities.

### 3.3 Gap scale

The phenomenological minimum gives $|\psi_0|^2=-a/b$ when $a<0$, but Ginzburg–Landau theory near $T_c$ does not by itself identify the quasiparticle gap at $T=0$. Write

$$\Delta(0)=C_\Delta k_BT_c$$

with $C_\Delta$ to be derived from the microscopic $V_q$ kernel or measured. The weak-coupling BCS value $C_\Delta\approx1.76$ cannot be inherited merely because both models use a complex order parameter.

---

## 4. Comparison with Established Pairing Models

| Quantity | Established microscopic treatment | Proposed Qi-coherence model |
|---|---|---|
| Pairing kernel | Electron-phonon or other material-specific interaction | Underived $V_q(\mathbf k,\mathbf k';q_m)$ |
| Gap equation | Computed from the interaction and electronic structure | Requires the same microscopic calculation |
| $T_c$ | Depends on spectrum, coupling, Coulomb pseudopotential, and symmetry | Parameterized by $q_m(0),q_c,\alpha_T$ in the simple ansatz |
| Isotope response | Can include mass, disorder, anharmonicity, and multiband effects | Additional dependence on a measured $q_m$ is proposed |
| Meissner and flux response | Gauge-coupled condensate with measured stiffness | Must be derived; damping suppression is insufficient |
| Unconventional materials | Material-specific symmetry and interactions | No present Qi kernel selects a symmetry |

### 4.1 Isotope-disorder discriminator

A possible discriminator is whether isotope disorder changes $T_c$ or superfluid observables after conventional mass, strain, chemistry, defect, and electronic-structure effects are controlled. Under the phenomenological ansatz,

$$
\frac{T_c^{(A)}}{T_c^{(B)}}=
\left[
\frac{q_m^{(A)}(0)-q_c}{q_m^{(B)}(0)-q_c}
\right]^{1/4}.
$$

The comparison requires isotopically engineered samples with measured composition, lattice constants, disorder, residual-resistivity ratio, phonon spectrum, and uncertainty. Conventional superconductivity does not generically predict zero isotope-purification effect, so the null must come from a material-specific microscopic baseline. This proposal is unregistered and has no predicted effect size.

---

## 5. Candidate Material Variables

These are variables to control in a future preregistered study, not design requirements derived from Cassi.

### 5.1 Isotope and defect structure

- isotope composition and mass distribution
- vacancy and interstitial density
- residual-resistivity ratio and mean free path
- strain gradients and grain-boundary density

### 5.2 Phonon and electronic structure

- phonon density of states and anharmonicity
- electronic density of states and Fermi-surface geometry
- pairing symmetry and superfluid stiffness
- independently measured transition width, $T_c$, gap, and critical fields

### 5.3 Candidate coherence observable

The central unresolved task is to define $q_m$ from measured material quantities without using $T_c$ or the gap as an input. A useful definition must be dimensionless, reproducible across samples, and fixed before outcome analysis. Fivefold geometry or Wu Xing labels do not supply such an observable.

---

## 6. Conditional Phase Diagram

If the Ginzburg–Landau coefficient is defined by $a=a_0(q_c-q_m)$, the model labels the region $q_m>q_c$ as ordered and $q_m<q_c$ as normal. This partition follows by definition from the ansatz. It is not evidence that canonical $q$ controls a material transition.

The critical current also needs a gradient and electromagnetic calculation. A provisional near-boundary scaling,

$$J_c(T)=J_0\,[q_m(T)-q_c]^\beta,$$

introduces material amplitude $J_0$ and exponent $\beta$. Selecting $\beta=1/2$ is a mean-field hypothesis rather than a Cassi result.

---

## 7. Unregistered Experimental Discriminators

### D1: isotope disorder at controlled mean mass

Compare matched samples while controlling the conventional variables listed in §4.1. Measure both $q_m$ and superconducting observables; a post hoc coherence score does not test the model.

### D2: vacancy and grain-boundary series

Measure whether one preregistered $q_m$ definition predicts changes in $T_c$, gap, stiffness, and critical field beyond material-specific microscopic baselines. No universal linear or quarter-power suppression is asserted.

### D3: geometry-matched comparison

Compare periodic, approximant, and quasicrystalline samples with matched chemistry and characterized electronic and phonon spectra. Fivefold order alone does not predict stronger superconductivity or a larger isotope effect.

### D4: microscopic-kernel test

Derive or constrain $V_q(\mathbf k,\mathbf k';q_m)$ and test its symmetry and spectral dependence against tunneling, ARPES, isotope, and thermodynamic data. Failure to provide a kernel leaves the proposal phenomenological.

---

## 8. Epistemic Boundaries

### Reused Cassi ingredients

- the canonical nonnegative density pair $E_Y,E_I$ and selected rank-one conversion (`foundations/cassi-first-principles.md`)
- the algebraic coherence diagnostic $q$ for that density pair
- the asserted optional single-channel input $g(q)=q/(\varphi^2+q^2)$ (`computations/gate_origin_audit.py`)
- $\varphi$ as the selected scale-separation constant

### Creative model inputs

- the material variables $U_{\text{drift}},U_{\text{th}},q_m$
- their constitutive map, if any, to canonical $E_Y,E_I,q$
- the damping ansatz and any extra $g(q_m)$ multiplier
- the attractive kernel $V_q$, pairing symmetry, and cutoff
- the $q_m(T)$ model, threshold $q_c$, and all material coefficients
- the discriminator program in §7

### Scope

Known superconductors remain described by their measured electronic, phonon, magnetic, and structural physics. The current proposal establishes no superconducting mechanism, numerical $T_c$, gap ratio, material recipe, or registered prediction.

---

## References

- `foundations/cassi-first-principles.md`—canonical two-density state, selected conversion, and algebraic $q$ diagnostic
- `foundations/cassi-theory-reference.md`—compact canonical formula reference and tier boundaries
- `computations/gate_origin_audit.py`—audit of the asserted optional gate input
- `foundations/bubble-edge-geometry.md`—conditional use of the gate input in an edge model
- `principles/de-resonance-principle.md`—number-theoretic motivation and physical-tier boundary
