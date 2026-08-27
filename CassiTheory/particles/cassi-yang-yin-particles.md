# Yang-Yin Field Interference and Particle Formation: Conditional Complex-Field/NLS Extension

## Status: Hypothesized—August 2026

## Abstract

The committed Cassi solver uses two nonnegative real density fields, $E_Y$ and $E_I$. Its state is the density pair and the derived quantities

$$
\rho = E_Y + E_I, \qquad \varepsilon = E_Y - \varphi E_I,
$$

with a gated, equal-and-opposite conversion term that relaxes $\varepsilon$ while conserving the conversion contribution to $\rho$. This canonical state contains no complex phase, prescribed propagation direction, chirality, compact phase coordinate, NLS equation, or particle variable.

This paper records a separate, conditional extension. The extension introduces complex amplitudes $\Psi_Y$ and $\Psi_I$ on a selected one-dimensional coordinate $s$, chooses opposite spatial wave-number signs in a particular ansatz, and gives both components the same temporal factor $e^{-i\omega t}$. The resulting intensity has a stationary cosine modulation by direct algebra. A further focusing nonlinear Schrödinger equation (NLS) can be selected as an effective model for localization. The amplitude ratio $r=A_I/A_Y=\varphi^{-1}$, the sech profile, the threshold rule, and the reported soliton receipts are properties of that selected extension and its numerical experiments.

The extension supplies a conditional wave-mechanical particle proxy. It does not promote the proxy to a canonical Cassi particle, a Dirac field, a Higgs mechanism, a quantum-scattering theory, or a direction-bearing Yang/Yin ontology. The conventional LDA/PBE/Dirac-Kohn-Sham measurements in `particles/dft-benchmarks.md` concern their own numerical implementation and atomic reference comparisons; they are separate from the canonical solver and from this complex-field/NLS extension.

---

## 1. Canonical real-density baseline

### 1.1 State variables

The canonical state is the pair of real densities

$$
E_Y(\mathbf{x},t) \ge 0, \qquad E_I(\mathbf{x},t) \ge 0.
$$

The labels $Y$ and $I$ identify the two framework channels. They do not, by themselves, assign a spatial direction, a temporal frequency sign, a chirality, or a complex phase. Define

$$
\rho = E_Y + E_I, \qquad
\varepsilon = E_Y - \varphi E_I,
$$

and the canonical scalar gate

$$
q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}.
$$

The fixed ratio of the conversion term is $E_Y=\varphi E_I$. At that line, the Yang share of the total density is $E_Y/\rho=\varphi^{-1}$. These are density statements; they do not determine a complex-amplitude ratio.

### 1.2 Canonical two-fluid equations

In the density variables used by the solver, the governing form is

$$
\partial_t E_Y = -(\mathbf{u}\!\cdot\!\nabla)E_Y + \nu\nabla^2 E_Y
 - \lambda(1-q)(E_Y-\varphi E_I) + S_Y[E_I,\Phi],
$$

$$
\partial_t E_I = -(\mathbf{u}\!\cdot\!\nabla)E_I + \nu\nabla^2 E_I
 + \lambda(1-q)(E_Y-\varphi E_I) + S_I[E_Y,\Phi].
$$

Here $\mathbf{u}$ is the velocity field, $\nu$ is the solver's diffusion or viscosity coefficient, and $\lambda$ is the asserted solver normalization/timescale convention, with $\lambda=0.1$ where numerically used. The proposed relation $\lambda=1/(2w)$ with $w=5$ is not derived here. $S_Y,S_I$ denote the model's potential-coupled source terms. Let

$$
\kappa = \lambda(1-q).
$$

The conversion-only contribution is

$$
\left.\partial_t
\begin{pmatrix}E_Y\\E_I\end{pmatrix}\right|_{\mathrm{conv}}
=\kappa
\begin{pmatrix}-1&\varphi\\1&-\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.
$$

The matrix has rank one and eigenvalues $0$ and $-\kappa(1+\varphi)$. Consequently,

$$
\left.\partial_t\rho\right|_{\mathrm{conv}}=0,
\qquad
\left.\partial_t\varepsilon\right|_{\mathrm{conv}}
=-\kappa(1+\varphi)\varepsilon.
$$

The conversion contribution relaxes the density contrast and conserves total density. It is not a norm-preserving rotation and supplies no fixed phase advance. A density-plane diagnostic such as

$$
\theta_d=\operatorname{atan2}(E_I,E_Y)
$$

is a state coordinate of the real density pair. It is distinct from a complex amplitude phase and does not create an independent compact $U(1)$ or $SO(2)$ degree of freedom.

### 1.3 What the canonical equations supply

The canonical equations supply density evolution, advection, diffusion, potential sources, the gated conversion, the fixed ratio, and the scalar coherence diagnostic $q$. They do not supply the following extension ingredients:

- a complex lift of either density, including the two phase functions $\arg\Psi_Y$ and $\arg\Psi_I$;
- a one-dimensional coordinate with a chosen positive orientation and length $L_s$;
- a wave operator with a speed $v$, damping $\gamma$, or spatial-bias coefficient $\chi$;
- a counterpropagating plane-wave ansatz;
- an NLS dispersion coefficient $\hbar_{\mathrm{eff}}^2/(2m_{\mathrm{eff}})$, an attractive coefficient $g$, or an external potential $V(s)$;
- a soliton, a condensation threshold for that soliton, or a particle ontology.

Any such ingredient belongs to the conditional extension described below and carries its own assumptions.

---

## 2. Extension inventory and boundary

The extension makes the following additions in sequence. The sequence is a modeling choice rather than a derivation from the canonical density equations.

| Added object | Role in the extension | Status and boundary |
|---|---|---|
| $s\in[0,L_s]$ | Chosen one-dimensional coordinate | Application coordinate; the canonical solver does not select it or an intrinsic orientation. |
| $\Psi_Y(s,t),\Psi_I(s,t)\in\mathbb{C}$ | Complex amplitudes carrying phase information absent from $E_Y,E_I$ | New fields; an observation map such as $E_Y^{\mathrm{ext}}=|\Psi_Y|^2$, $E_I^{\mathrm{ext}}=|\Psi_I|^2$ is an additional convention. |
| $A_Y,A_I,k,\omega$ | Amplitudes and wave numbers in the selected plane-wave ansatz | Chosen initial or trial data; $+k$ and $-k$ are spatial phase signs in that ansatz. |
| $\gamma,v,\chi$ | Damping, propagation scale, and opposite spatial-bias signs in the extended wave equations | New dimensional or fitted parameters; they do not assign intrinsic direction to the canonical channels. |
| $\alpha,\beta$ | Nonlinear cross-couplings in the extended source terms | New couplings; their signs and magnitudes are model inputs. |
| $\hbar_{\mathrm{eff}},m_{\mathrm{eff}},g,V(s)$ | Coefficients and potential in an optional focusing NLS closure | New effective-model parameters; no relativistic or Higgs interpretation follows from their symbols. |
| $\mu,s_0,v_g,k_0,\omega_0$ | Parameters of a selected localized NLS solution | Solution data subject to the chosen NLS and boundary conditions. |
| $\theta_{\mathrm{cond}}$ | Threshold used by an experiment to label a high-intensity localized state | Imported or selected criterion for the experiment; not a canonical particle equation. |
| $\eta$ (when used) | Optional loss coefficient for a damped NLS experiment | Additional loss assumption; the conservative NLS has no such term. |

The phases are underdetermined by the densities. If the optional observation map $E_Y^{\mathrm{ext}}=|\Psi_Y|^2$, $E_I^{\mathrm{ext}}=|\Psi_I|^2$ is imposed at the canonical fixed ratio, then

$$
\frac{|\Psi_Y|^2}{|\Psi_I|^2}=\varphi
\quad\Longrightarrow\quad
\frac{|A_I|}{|A_Y|}=\varphi^{-1/2}
$$

for constant positive amplitudes. The frequently used extension value $A_I/A_Y=\varphi^{-1}$ is therefore a separate amplitude ansatz. It is not the amplitude form of the canonical density fixed point.

---

## 3. Conditional complex wave system

### 3.1 Extended equations

One possible extension places the two complex fields on the chosen coordinate $s$ and gives them damped second-order wave equations:

$$
\partial_t^2\Psi_Y+\gamma\,\partial_t\Psi_Y
= v^2\partial_s^2\Psi_Y+\chi\,\partial_s\Psi_Y+S_Y^{\mathrm{ext}}(s,t),
$$

$$
\partial_t^2\Psi_I+\gamma\,\partial_t\Psi_I
= v^2\partial_s^2\Psi_I-\chi\,\partial_s\Psi_I+S_I^{\mathrm{ext}}(s,t).
$$

The opposite signs of the $\chi$ terms are a chosen spatial-bias convention. They make a counterpropagating ansatz natural for a particular calculation; they do not identify $E_Y$ with one direction or $E_I$ with another. The canonical density equations contain no $\partial_s^2\Psi$ operator from which these equations could be read off.

A selected asymmetric source pair is

$$
S_Y^{\mathrm{ext}}=+\alpha |\Psi_I|^2\Psi_Y,
\qquad
S_I^{\mathrm{ext}}=-\beta |\Psi_Y|^2\Psi_I.
$$

This pair is an extension input. It can amplify one component and suppress the other in a chosen regime, while the canonical conversion is an equal-and-opposite density relaxation with a fixed density ratio. The two source pairs should not be identified without an explicit derivation and parameter map.

### 3.2 What is and is not a closed model

The extended wave equations and the NLS closure in §5 are distinct model choices. A calculation must state whether it integrates the damped wave system, the NLS, or a coupled system with an explicitly supplied coupling. The equations in this paper do not silently identify the two systems. In particular, a complex-field initial condition does not become a solution of the canonical real-density PDE merely because its intensity is called a density.

---

## 4. Linear interference from a selected ansatz

### 4.1 Shared temporal dependence and opposite spatial signs

For the standing-wave calculation, choose $k>0$ and constant complex amplitudes $A_Y,A_I$:

$$
\Psi_Y(s,t)=A_Y e^{i(ks-\omega t)},
\qquad
\Psi_I(s,t)=A_I e^{i(-ks-\omega t)}.
$$

Both components have the same temporal factor $e^{-i\omega t}$. Their spatial phase gradients have opposite signs. An ansatz with $e^{+i\omega t}$ for one component would be a different model choice and is not part of this standing-wave construction. The shared temporal factor is the convention required for the stationary intensity below.

Define the extension intensity

$$
I_\Psi(s,t)=|\Psi_Y+\Psi_I|^2.
$$

Direct expansion gives

$$
I_\Psi(s,t)=|A_Y|^2+|A_I|^2
+2\,\operatorname{Re}\!\left[A_YA_I^*e^{2iks}\right].
$$

The common temporal factor cancels from the intensity. For real nonnegative amplitudes,

$$
I_\Psi(s)=A_Y^2+A_I^2+2A_YA_I\cos(2ks).
$$

This stationary cosine modulation is the algebraic standing-wave consequence of the selected ansatz. It is an intensity property of the extension. The symbol $I_\Psi$ is used here to keep it separate from the canonical total density $\rho=E_Y+E_I$.

### 4.2 Maxima, minima, and spacing

For real positive $A_Y,A_I$, the maxima and minima occur at

$$
\begin{aligned}
I_{\Psi,\max}&=(A_Y+A_I)^2 &&\text{when }\cos(2ks)=+1,\\
I_{\Psi,\min}&=(A_Y-A_I)^2 &&\text{when }\cos(2ks)=-1.
\end{aligned}
$$

The maxima lie at $s=n\pi/k$ and the minima at $s=(n+\tfrac12)\pi/k$, up to a constant phase offset when $A_YA_I^*$ is complex. The spacing between adjacent maxima is

$$
\Delta s=\frac{\pi}{k}=\frac{\lambda_s}{2},
\qquad \lambda_s=\frac{2\pi}{k}.
$$

The minima are exact zeros only for equal magnitudes $|A_Y|=|A_I|$. For unequal amplitudes, including the $\varphi^{-1}$ ansatz below, they are nonzero troughs. Periodic quantization $k_n=2\pi n/L_s$ follows only after periodic boundary conditions are imposed on the chosen coordinate.

### 4.3 Amplitude-ratio table

Let

$$
 r=\frac{A_I}{A_Y}
$$

for positive real amplitudes. The intensity becomes

$$
I_\Psi(s)=A_Y^2\left(1+r^2+2r\cos(2ks)\right).
$$

| Ratio $r$ | Extension intensity | Interpretation within this ansatz |
|---|---|---|
| $r=0$ | $I_\Psi=A_Y^2$ | Uniform single-component trial state. |
| $r=1$ | $I_\Psi=4A_Y^2\cos^2(ks)$ | Maximal contrast with exact zeros. |
| $r=\varphi^{-1}$ | $I_\Psi=A_Y^2(1+\varphi^{-2}+2\varphi^{-1}\cos(2ks))$ | Selected Cassi-motivated trial ratio. |
| $r\gg1$ | $I_\Psi\simeq A_I^2$ | Uniform Yin-labeled single-component limit. |

At the selected value $r=\varphi^{-1}$,

$$
I_{\Psi,\max}=A_Y^2(1+\varphi^{-1})^2=A_Y^2\varphi^2,
$$

$$
I_{\Psi,\min}=A_Y^2(1-\varphi^{-1})^2=A_Y^2\varphi^{-4},
$$

and therefore

$$
\frac{I_{\Psi,\max}}{I_{\Psi,\min}}=\varphi^6\approx17.94.
$$

These identities follow from the ansatz and the algebra of $\varphi$. They do not derive the amplitude ratio from canonical conversion, and they do not establish a universal localization mechanism.

---

## 5. Optional focusing NLS closure

### 5.1 Equation and added assumptions

A second extension step selects a scalar focusing NLS for the total complex field

$$
\Psi(s,t)=\Psi_Y(s,t)+\Psi_I(s,t):
$$

$$
 i\hbar_{\mathrm{eff}}\frac{\partial\Psi}{\partial t}
 =-\frac{\hbar_{\mathrm{eff}}^2}{2m_{\mathrm{eff}}}
   \frac{\partial^2\Psi}{\partial s^2}
   +V(s)\Psi-g|\Psi|^2\Psi,
 \qquad g>0.
$$

The new terms and parameters have specific roles:

- $\hbar_{\mathrm{eff}}$ sets the dispersive scale;
- $m_{\mathrm{eff}}$ sets the coefficient of the second spatial derivative;
- $V(s)$ is an externally supplied potential on the selected coordinate;
- $g>0$ is an attractive cubic self-interaction.

The term $-g|\Psi|^2\Psi$ favors self-focusing in this effective equation. The canonical gate $q$ and the canonical conversion term do not determine $g$, $V$, $m_{\mathrm{eff}}$, or $\hbar_{\mathrm{eff}}$. A dimensionless rescaling may produce the shorthand

$$
 i\partial_t\Psi=-\partial_s^2\Psi-g|\Psi|^2\Psi,
$$

with the rescaling itself counted among the experiment's assumptions.

The homogeneous choice $V=0$ is used for the bright-soliton receipt. The conservative NLS displayed here has no damping coefficient $\gamma$ and no particle-creation source. A loss or decay experiment requires an explicit extension, such as a damped term $-i\eta\Psi$ with $\eta>0$, a lossy boundary condition, or coupling back to a specified dissipative system.

### 5.2 Bright-soliton trial solution

For $V=0$ and a positive binding-energy parameter $\mu>0$, a self-consistent bright-soliton family is

$$
\Psi(s,t)=\sqrt{\frac{2\mu}{g}}\,
\operatorname{sech}\!\left[
 \frac{\sqrt{2m_{\mathrm{eff}}\mu}}{\hbar_{\mathrm{eff}}}
 (s-s_0-v_gt)
\right]
 e^{i(k_0s-\omega_0t)}.
$$

For the displayed phase convention,

$$
v_g=\frac{\hbar_{\mathrm{eff}}k_0}{m_{\mathrm{eff}}},
\qquad
\omega_0=\frac{\hbar_{\mathrm{eff}}k_0^2}{2m_{\mathrm{eff}}}
-\frac{\mu}{\hbar_{\mathrm{eff}}}.
$$

Here $s_0$ is the center, $v_g$ is the translation speed, $k_0$ is the carrier wave number, and $\omega_0$ is the corresponding carrier frequency. The sech envelope is localized, while the carrier supplies an internal oscillatory factor within the selected complex model. The terms “particle” and “wave” describe the two features of this trial solution; they do not establish a particle ontology for the canonical solver.

The characteristic NLS width is

$$
\sigma=\frac{\hbar_{\mathrm{eff}}}{\sqrt{2m_{\mathrm{eff}}\mu}}
=\sqrt{\frac{\hbar_{\mathrm{eff}}^2}{2m_{\mathrm{eff}}\mu}}.
$$

It is an NLS width. A Compton-wavelength interpretation would require an additional relativistic theory and is not assigned here.

With the displayed normalization on an infinite line, the integrated NLS intensity is

$$
M_\Psi
=\int_{-\infty}^{+\infty}|\Psi(s,t)|^2\,ds
=\frac{4\hbar_{\mathrm{eff}}}{g}
  \sqrt{\frac{\mu}{2m_{\mathrm{eff}}}}.
$$

This expression follows by integrating $\operatorname{sech}^2$ with the amplitude and width shown above. It depends on $\mu$, $m_{\mathrm{eff}}$, $g$, and $\hbar_{\mathrm{eff}}$ under the stated normalization. A different normalization or finite domain changes the reported quantity.

### 5.3 Stability boundary

For the homogeneous one-dimensional focusing NLS, the norm and Hamiltonian are conserved for sufficiently regular solutions. For example, with $V=0$,

$$
H[\Psi]=\int\left[
 \frac{\hbar_{\mathrm{eff}}^2}{2m_{\mathrm{eff}}}|\partial_s\Psi|^2
 -\frac{g}{2}|\Psi|^4
\right]ds
$$

is conserved together with $M_\Psi$. Orbital stability of a selected soliton family can be studied within this NLS model under its stated boundary and perturbation conditions. The canonical conversion supplies neither this Hamiltonian nor a topological or Berry-phase protection rule. Stability receipts therefore remain conditional on the NLS choice and numerical setup.

### 5.4 Conditional localization criterion

An experiment may define a localized-state proxy by comparing the NLS peak intensity with an externally selected threshold:

$$
I_{\Psi,\mathrm{peak}}=\frac{2\mu}{g}>\theta_{\mathrm{cond}}.
$$

Under this rule, the run labels the trial as a localized-state proxy. The inequality does not by itself derive a focusing threshold or a canonical particle criterion. The value and provenance of $\theta_{\mathrm{cond}}$ must be stated for each experiment. The canonical density threshold and the NLS localization threshold are separate objects until a mapping is supplied.

---

## 6. The $\varphi$ ratio as an extension ansatz

### 6.1 The optional mass functional

The current optional extension records the following ratio-dependent functional:

$$
M_{\mathrm{ansatz}}(r)=M_0\frac{(1+r)^2}{\sqrt r}.
$$

This is an additional ratio-dependent functional. Differentiation gives

$$
\frac{dM_{\mathrm{ansatz}}}{dr}=0
\quad\Longleftrightarrow\quad
3r-1=0,
$$

so its positive stationary point is $r=1/3$. Numerically,

$$
M_{\mathrm{ansatz}}(\varphi^{-1})\approx3.33M_0,
\qquad
M_{\mathrm{ansatz}}(1/3)\approx3.08M_0.
$$

The functional consequently does not select $r=\varphi^{-1}$ as its minimum. The $\varphi^{-1}$ value remains a proposed structural ansatz whose behavior is tested in the numerical scan of §10.3. Neither this functional nor its stationary point belongs to the canonical real-density equations.

### 6.2 Peak amplification under the selected ratio

The standing-wave algebra gives

$$
I_{\Psi,\max}=A_Y^2\varphi^2
$$

when $r=\varphi^{-1}$. A cited extension experiment reports a $\varphi^2$ peak relative to its driving normalization. That receipt concerns the selected amplitude convention and experiment. The canonical conversion fixes a density ratio and does not by itself select the extension amplitude ratio or the peak-intensity normalization.

### 6.3 Conditional coordinate comparison with chakra positions

If periodic boundary conditions are imposed on the chosen coordinate, then

$$
k_n=\frac{2\pi n}{L_s},\qquad n\in\mathbb{Z}_{>0},
\qquad
\Delta s_n=\frac{\pi}{k_n}=\frac{L_s}{2n}.
$$

The following comparison retains the listed application coordinates while giving them only conditional status:

| Label | Supplied coordinate $s_c/L_s$ | $n_c=L_s/(2s_c)$ |
|---|---:|---:|
| Root | 0.07 | 7.14 |
| Sacral | 0.14 | 3.57 |
| Solar | 0.29 | 1.72 |
| Heart | 0.43 | 1.16 |
| Throat | 0.57 | 0.88 |
| Eye | 0.71 | 0.70 |
| Crown | 0.86 | 0.58 |

The rounded values are generally noninteger. They provide a coordinate comparison for a selected application convention. They do not establish a canonical mode spectrum, an intrinsic chakra direction, irrational spacing, or mode-locking prohibition. A quantitative match would require a stated coordinate map, boundary condition, and error model.

---

## 7. Boundaries on quantum and particle analogies

The opposite spatial signs in §4 resemble the two signs used in a one-dimensional plane-wave decomposition. A resemblance can be recorded without identifying the extension fields with relativistic spinors. For comparison, a $1+1$-dimensional Dirac equation and its massless mode notation are

$$
 i\gamma^\mu\partial_\mu\psi=m\psi,
$$

$$
 \psi_R\sim e^{i(kx-\omega t)},
 \qquad
 \psi_L\sim e^{i(-kx-\omega t)}.
$$

A Dirac interpretation additionally requires a spinor representation, gamma matrices, a Lorentzian spacetime structure, transformation rules, and a specified mass coupling. The extension supplies none of those structures. Its $\Psi_Y$ and $\Psi_I$ are complex scalar amplitudes on a selected coordinate, and the signs $+k$ and $-k$ are ansatz data.

The following table records the boundary of each analogy:

| Extension quantity | Possible comparison | Required qualification |
|---|---|---|
| $s$ | One-dimensional configuration coordinate | No spacetime or physical compact dimension is supplied. |
| $e^{\pm iks}$ | Counterpropagating mode factors | The signs are selected spatial phase gradients; they do not establish chirality. |
| $(\Psi_Y,\Psi_I)$ | Two-component wave-amplitude notation | A Dirac spinor requires additional relativistic structure. |
| $\Psi=\Psi_Y+\Psi_I$ | Scalar superposition | A scalar superposition is not a fermion field. |
| $M_\Psi=\int|\Psi|^2ds$ | NLS norm or particle-number-like quantity | A rest mass and a Noether charge require a specified action and symmetry. |
| $g|\Psi|^2\Psi$ | Attractive self-interaction | The coefficient is an NLS parameter, not a Higgs vacuum or Yukawa coupling. |
| Sech localization | Localized effective excitation | A localized NLS state is a model proxy for a particle-like state. |
| Two-soliton collision | NLS collision with a phase shift | The receipt is an effective wave calculation; a quantum $S$-matrix is a separate construction. |
| $\theta_{\mathrm{cond}}$ crossing | Selected localization label | It is a threshold rule, not a mass gap or a canonical particle-creation law. |
| Carrier phase | Complex-model phase factor | A Berry phase requires a parameter-space connection and is not supplied here. |

### 7.1 Dirac and Higgs claims

The equations above permit a conditional analogy to the way opposite-sign plane-wave factors appear in a $1+1$-dimensional Dirac decomposition. They do not derive a Dirac mass term. The NLS norm, the cross-couplings $\alpha,\beta$, and the attractive coefficient $g$ do not constitute a Higgs field, a vacuum expectation value, or a Yukawa interaction. A particle-mass mechanism in either sense would require a new action, symmetry content, and parameter map.

### 7.2 Direction and compact-phase claims

The canonical labels $Y$ and $I$ have no built-in outward/inward or right/left propagation assignment. The extension's $+k$ and $-k$ signs define the spatial pattern only after $s$ and its orientation are selected. The shared factor $e^{-i\omega t}$ gives a common temporal convention. The canonical rank-one conversion has no fixed phase advance, compact phase clock, or chirality operator. Any such structure must be introduced and tested as an additional model sector.

The GQ6 audit in `foundations/quantum-measurement-derivation.md` §8.3 sharpens
this boundary geometrically. A normalized complex Yang/Yin pair supplies
$\mathbb{CP}^1$ qubit geometry, while physical spin requires a derived
$SU(2)$ action covering spatial $SO(3)$. Fermionic exchange requires a line
bundle over unordered multiparticle configuration space, and a local gauge
sector requires a connection with gauge-covariant observables. These
structures are absent from the extension.

---

## 8. Conditional creation and decay workflow

The following workflow describes how a numerical study may use the extension's terminology:

1. Choose the coordinate $s$, boundary conditions, complex initial data, and the relation, if any, between $|\Psi_\alpha|^2$ and the canonical densities.
2. Choose either the extended damped wave equations, the conservative NLS, or an explicitly coupled system.
3. If the standing-wave ansatz is used, choose $A_Y,A_I,k,\omega$ with the shared temporal factor shown in §4.
4. Evaluate $I_\Psi=|\Psi_Y+\Psi_I|^2$ and apply the stated threshold rule if a localized-state proxy is desired.
5. For a focusing NLS run, record the norm, peak intensity, width, perturbation response, and boundary effects. A localized state above threshold is labeled a particle proxy for that run.
6. For a decay experiment, include an explicit loss term, lossy boundary, or coupling to a dissipative wave system. Under the conservative NLS alone, the norm is conserved and spontaneous annihilation is not a model consequence.

This vocabulary describes state transitions in the selected extension. The canonical solver continues to evolve $E_Y,E_I,\rho,\varepsilon$, and $q$ without a particle state variable.

---

## 9. Complete conditional picture

```
CANONICAL REAL-DENSITY STATE
  E_Y, E_I >= 0
  rho = E_Y + E_I
  epsilon = E_Y - varphi E_I
  q = rho^2 / (rho^2 + varphi^(-2) + epsilon^2)
  gated rank-one conversion: epsilon relaxes, rho is conserved by conversion
                 |
                 | optional observation map, coordinate, phases, and ansatz
                 v
CONDITIONAL COMPLEX-FIELD EXTENSION
  Psi_Y(s,t), Psi_I(s,t) in C
  chosen s, L_s, gamma, v, chi, alpha, beta
  selected factors exp[i(ks - omega t)] and exp[i(-ks - omega t)]
                 |
                 v
ALGEBRAIC STANDING-WAVE INTENSITY
  I_Psi = |Psi_Y + Psi_I|^2
  I_Psi = A_Y^2 + A_I^2 + 2 A_Y A_I cos(2ks)  [real amplitudes]
                 |
                 | optional effective closure with hbar_eff, m_eff, V, g
                 v
FOCUSING NLS TRIAL
  sech envelope, conditional threshold, and conditional stability receipt
                 |
                 v
LOCALIZED-STATE / PARTICLE PROXY
  label applies only to the selected extension experiment
```

The arrows mark added assumptions. The diagram does not identify the canonical density conversion with the complex wave equations or the NLS.

---

## 10. Conditional numerical receipts

The following receipts belong to the specified complex-field/NLS experiments. They are evidence about those numerical setups, with their chosen parameters and initial conditions.

### 10.1 Soliton formation from an interference trial

The reported Experiment 8v2 run initializes two counterpropagating sech pulses with amplitude ratio

$$
 r=\varphi^{-1}\approx0.618.
$$

Its reported final state is a localized wave packet with:

- integrated intensity $M_\Psi=2.82$ under that run's normalization;
- peak intensity $I_{\Psi,\mathrm{peak}}=0.94$;
- stable measured width over the reported observation window despite dispersive spreading.

These values are conditional receipts. They do not establish that the canonical density PDE generates the same state, and they do not determine a universal amplitude ratio.

### 10.2 Two-soliton collision

The same experiment family reports two NLS solitons approaching, overlapping, and emerging as two distinct localized profiles with a phase shift. This is a collision receipt for the selected effective NLS. It supplies an effective wave-mechanical scattering-like pattern. A quantum scattering interpretation requires separate quantum fields, asymptotic states, and an $S$-matrix construction.

### 10.3 Ratio scan

A reported scan covers

$$
 r\in[0.3,1.5].
$$

The recorded behavior is:

- near $r=\varphi^{-1}$, the run gives a well-defined structure and near-maximal measured mass under its chosen metric;
- for $r\ll\varphi^{-1}$, the Yin-labeled component is weak and the reported localized state is less robust;
- for $r\gg\varphi^{-1}$, the Yin-labeled component dominates and the standing-wave contrast weakens.

The scan supports the selected ratio as an empirical feature of that extension setup. It does not confirm an analytical prediction from canonical conversion. In particular, the optional functional in §6.1 has its stationary point at $r=1/3$, so the scan and the functional are separate pieces of evidence.

### 10.4 Conventional DFT boundary

The conventional DFT benchmark in `particles/dft-benchmarks.md` reports shell structure, orbital ordering, and energy hierarchy for first-row atoms ($Z=1$–$10$) using its LDA/PBE/Dirac-Kohn-Sham implementation and atomic reference comparisons. Those measurements validate the conventional numerical implementation and its reference comparisons. The benchmark contains no realization of the canonical gated two-fluid conversion, no counterpropagating $\Psi_Y,\Psi_I$ extension, and no NLS soliton test. Its complex Kohn-Sham orbitals, where used, are separate from the extension fields in this paper. The benchmark therefore supplies no validation of Cassi field equations or of a particle-emergence hypothesis.

---

## 11. Summary of the model boundary

### Canonical equations

$$
\partial_t E_Y = -(\mathbf{u}\!\cdot\!\nabla)E_Y + \nu\nabla^2 E_Y
 -\lambda(1-q)(E_Y-\varphi E_I)+S_Y[E_I,\Phi],
$$

$$
\partial_t E_I = -(\mathbf{u}\!\cdot\!\nabla)E_I + \nu\nabla^2 E_I
 +\lambda(1-q)(E_Y-\varphi E_I)+S_I[E_Y,\Phi],
$$

$$
\rho=E_Y+E_I,
\qquad
\varepsilon=E_Y-\varphi E_I,
\qquad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}.
$$

### Conditional complex wave equations

$$
\partial_t^2\Psi_Y+\gamma\partial_t\Psi_Y
=v^2\partial_s^2\Psi_Y+\chi\partial_s\Psi_Y+\alpha|\Psi_I|^2\Psi_Y,
$$

$$
\partial_t^2\Psi_I+\gamma\partial_t\Psi_I
=v^2\partial_s^2\Psi_I-\chi\partial_s\Psi_I-\beta|\Psi_Y|^2\Psi_I.
$$

These equations add complex amplitudes, a one-dimensional coordinate, second-order wave dynamics, damping, spatial-bias signs, and cross-couplings.

### Standing-wave consequence

$$
\Psi_Y=A_Ye^{i(ks-\omega t)},
\qquad
\Psi_I=A_Ie^{i(-ks-\omega t)},
$$

$$
I_\Psi=|\Psi_Y+\Psi_I|^2,
\qquad
I_\Psi=A_Y^2+A_I^2+2A_YA_I\cos(2ks)
$$

for real amplitudes. The cosine pattern and spacing $\Delta s=\pi/k$ are algebraic consequences of the selected ansatz.

### Conditional NLS and localized profile

$$
 i\hbar_{\mathrm{eff}}\partial_t\Psi
 =-\frac{\hbar_{\mathrm{eff}}^2}{2m_{\mathrm{eff}}}\partial_s^2\Psi
 +V(s)\Psi-g|\Psi|^2\Psi,
$$

$$
\Psi=\sqrt{\frac{2\mu}{g}}\,\operatorname{sech}\!\left[
 \frac{\sqrt{2m_{\mathrm{eff}}\mu}}{\hbar_{\mathrm{eff}}}(s-s_0-v_gt)
\right]e^{i(k_0s-\omega_0t)}.
$$

The selected ratio $r=\varphi^{-1}$, the threshold $I_{\Psi,\mathrm{peak}}>\theta_{\mathrm{cond}}$, the stability scan, and the collision receipt are Hypothesized extension results. The canonical conversion remains a real-density rank-one relaxation.

---

## References

- `particles/dft-benchmarks.md`—conventional LDA/PBE/Dirac-Kohn-Sham numerical implementation and atomic reference comparisons for first-row atoms; separate from the canonical two-fluid solver and this extension.
- `foundations/cassi-theory-reference.md` §2—canonical real-density state, gated conversion, and the distinction between density diagnostics and complex phases.
- `foundations/bubble-edge-geometry.md`—conditional condensation-threshold construction used by some canonical applications; any use of its threshold in the NLS experiment requires an explicit mapping.
- `consciousness/chakras-as-cascade-bubbles.md`—application coordinates that may be compared with the extension's selected coordinate only under an explicit coordinate convention.
