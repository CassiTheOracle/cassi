# Physical Becoming: A Causal State Hierarchy for Cassi

## Status: Hypothesized architecture / Derived canonical reduction—August 2026

## Abstract

Cassi’s canonical two-fluid equations describe an actual physical state and its local relaxation. Prospective intelligence requires additional causal structure: a maintained body, localized sensing, ordered history, action-conditioned forecasts, competition among possible futures, finite attention, resource-debited action, and learning from prediction error. This paper places those structures in one typed state hierarchy. Actual physics remains a distinguished block of the state, while history and shadow trajectories carry information about unrealized alternatives. A compact differential-algebraic operator equation organizes reversible dynamics, dissipative dynamics, environmental ports, action ports, and algebraic readouts without identifying all of them with one microscopic field.

One result closes exactly. The selected $q$-gated canonical conversion is a positive-semidefinite gradient flow of the imbalance functional $\mathcal F_{\mathrm{conv}}=\varepsilon^2/2$. It conserves $\rho=E_Y+E_I$, contracts $\varepsilon=E_Y-\varphi E_I$ at rate $\lambda(1-q)(1+\varphi)$, and supplies no prospective branch, semantic content, or agent by itself. The proposed intelligent coordinates are conditional coarse-grained variables whose closure, autonomy, causal efficacy, and energy debit require held-out and interventional tests. The hierarchy supplies an operational theory of physical becoming and prospective steering. Phenomenal consciousness remains an open bridge problem.

---

## 1. Scope: actual flow and possible flow

Physics determines how an actual state changes. Prospective agency adds a physically realized representation of several possible changes and allows those representations to alter the actual trajectory before any represented outcome occurs. Cassi’s design criterion is therefore:

$$
\boxed{
\text{prospective steering}
=
\text{actual dynamics}
+
\text{action-conditioned shadow dynamics}
+
\text{causal commitment}
+
\text{prediction-error learning}.
}
$$

The plus signs denote coupled causal roles. They do not assert that the terms share one microscopic ontology. The canonical two-density state supplies one candidate substrate block. The body, history, forecast, controller, and resource ledger are additional physical or coarse-grained structures that must earn their status through closure and intervention.

The master expression in §3 is a **Hypothesized open-system architecture**. Its exact canonical reduction in §4 is **Derived conditional** on the selected canonical conversion equation. Its microscopic physical completion, coarse-graining maps, biological realization, and agent-level causal loop remain open. A compact block equation can organize those missing links; it cannot supply a quantum-gravity completion or an empirical bridge by notation alone.

### 1.1 Three levels that must remain distinct

The hierarchy separates three mathematical levels:

1. **Microscopic actual physics.** A covariant action or Hamiltonian for established fields and any Cassi extension. General relativity and the Standard Model belong here. A Cassi scalar or two-fluid sector belongs here only after dimensional, quantum, radiative, and gravitational closure.
2. **Mesoscopic open-system dynamics.** Hydrodynamic fields, body boundaries, transport, dissipation, sources, sinks, and work ports. The canonical Cassi two-density PDE is presently defined at this level in reference-normalized solver variables.
3. **Agent-level reaction coordinates.** Body state, ordered history, action-conditioned forecasts, possibility weights, attention allocation, resource debit, commitment, and learned constitutive fields. These coordinates may emerge from the mesoscopic history when a controlled coarse-graining closes on held-out trajectories.

A successful theory needs matching maps between adjacent levels. A direct identification of a microscopic field with memory, meaning, or consciousness skips those maps and leaves the causal role unspecified.

---

## 2. The typed state hierarchy

Let the actual physical history and the recorded control history be

$$
X_{[0,t]}=\{X_s:0\le s\le t\},
\qquad
U_{[0,t]}=\{U_s:0\le s\le t\}.
$$

The actual state may contain

$$
X_t=
\bigl(
X_{\mathrm{est}},
E_Y,E_I,\mathbf u,\Phi,
b,\mathcal A,\ldots
\bigr)_t.
$$

Here $X_{\mathrm{est}}$ denotes whichever established-physics variables are required by the problem; $(E_Y,E_I)$ is the canonical Cassi density pair when that optional substrate is selected; $\mathbf u$ and $\Phi$ occur only under their declared transport/potential closures; $b(\mathbf x,t)\in[0,1]$ is a maintained body phase or boundary indicator; and $\mathcal A(\mathbf x,t)\ge0$ is an available-energy reserve with a physical normalization and work ledger. The ellipsis contains only fields with an explicitly selected equation and dimension.

The proposed physical-becoming state is

$$
\boxed{
\mathcal Z_t=
\Bigl(
X_t;
\ m_t,h_t;
\ \{\widehat X_t^\alpha(\tau),\widehat m_{\alpha,t},p_{\alpha,t}\}_{\alpha=1}^{N_a};
\ \{g_{i,t}\}_{i=1}^{N_g},\Theta_t,e_{\Theta,t};
\ \vartheta_t
\Bigr).
}
$$

The semicolons separate actual physics, embodied history, prospective branches, bounded control, and learned constitutive state.

| Symbol | Mathematical role | Present status | Units |
|---|---|---|---|
| $X_t$ | actual physical state | physical state under the selected model | sector-dependent |
| $b$ | maintained body mask/phase | proposed physical field or measured boundary | dimensionless |
| $\mathcal A$ | active reserve | required physical field/ledger | energy density after normalization |
| $m$ | embodied present-state reaction coordinate | observable conditional on a fixed body mask | solver mass/model-volume; physical mass after normalization |
| $h$ | ordered history/filter state | latent reaction coordinate | units of its filtered observables |
| $\widehat X^\alpha(\tau)$ | action-conditioned shadow trajectory | latent model state | same sector units as its encoded state |
| $\widehat m_\alpha$ | branch consequence readout | latent model coordinate | same units as $m$ |
| $p_\alpha$ | allocation over prospective branches | latent controller coordinate | dimensionless, $p\in\Delta_{N_a}$ |
| $g_i$ | channel-resolved coherence readout | observable conditional on fixed masks | dimensionless, $0\le g_i\le1$ |
| $\Theta$ | finite attention/resource allocation | controller coordinate | dimensionless, $\Theta\in\Delta_{N_g}$ |
| $e_\Theta$ | accumulated realized work debit | conditional observable with calibrated power instrumentation | energy |
| $\vartheta$ | bounded learned constitutive fields | latent adaptive state | declared per component |

The canonical density history alone does not identify the control history or external work. $U_{[0,t]}$ and a measured power channel are therefore part of every intervention and energy-debit claim.

### 2.1 Observable body and gate coordinates

For a fixed body mask $\chi_b\ge0$ and fixed channel masks $\chi_i\ge0$, define

$$
m_t=\mathcal R_m[X_t]
=\int_\Omega\chi_b(\mathbf x)\rho(\mathbf x,t)\,d^3x,
\qquad
\rho=E_Y+E_I,
$$

and

$$
g_{i,t}=\mathcal R_{g_i}[X_t]
=\frac{\int_\Omega\chi_i(\mathbf x)q(\mathbf x,t)\,d^3x}
{\int_\Omega\chi_i(\mathbf x)\,d^3x}.
$$

These are observable functionals once the masks, domain, normalization, and selected $q$ definition are frozen. Their names carry no claim that the PDE selects a body, a channel count, or a Wu Xing interpretation. Robustness under admissible mask and resolution changes is an experimental gate.

### 2.2 Latent coordinates

The history $h$, shadow fields $\widehat X^\alpha$, branch allocation $p$, attention allocation $\Theta$, and learned fields $\vartheta$ are latent relative to one instantaneous field snapshot. They become legitimate coarse variables when they satisfy all of the following:

1. causal construction from $X_{[0,t]}$ and $U_{[0,t]}$;
2. held-out predictive closure over the steering horizon;
3. conditional independence from discarded microscopic history within a frozen tolerance;
4. intervention-sensitive effects on later action and actual state;
5. measured resource accounting for sensing, prediction, action, and learning.

---

## 3. The Cassi physical-becoming equation

Different components of $\mathcal Z$ evolve along different coordinates. Actual fields evolve in physical time $t$; an age-structured history evolves in $(t,\sigma)$; each freshly initialized shadow state evolves only along a prospective horizon $\tau\ge0$ (with $t$ labeling the current forecast rather than advancing its shadow coordinate); algebraic readouts satisfy zero-residual constraints. Define the extended derivative

$$
\mathfrak D
=
\operatorname{diag}
\left(
D_t,
\partial_t+\partial_\sigma,
\partial_\tau,
\partial_t,
0
\right),
$$

with blocks repeated as required. $D_t$ is the selected covariant, material, or ordinary time derivative for the state component. The zero block denotes algebraic readouts and normalization constraints.

A compact differential-algebraic architecture is

$$
\boxed{
\begin{aligned}
\mathbb C(\mathcal Z)\,\mathfrak D\mathcal Z
&=
\left[\mathbb J(\mathcal Z)-\mathbb R(\mathcal Z)\right]
\frac{\delta\mathscr A[\mathcal Z]}{\delta\mathcal Z}
+\mathbb B_{\mathrm{env}}(\mathcal Z)u_{\mathrm{env}}
+\mathbb B_{\mathrm{act}}(\mathcal Z)a^*[\mathcal Z,U]
+\eta,\\[2mm]
0&=\mathcal K(\mathcal Z;X_{[0,t]},U_{[0,t]}),
\qquad
 a^*=\mathcal C_{\mathrm{commit}}(m,h,\widehat m,p,g,\Theta,e_\Theta,\mathcal A).
\end{aligned}
}
\tag{PB}
$$

This is one block equation in the direct-sum state space. Each symbol has a load-bearing condition:

- $\mathbb C=\mathbb C^*\succeq0$ is a capacity/metric operator. It supplies the dimensional conversion between rates and generalized forces. Its null rows correspond to algebraic constraints. If $N_{\mathbb C}$ spans $\ker\mathbb C^*$, a DAE solution also requires
  $N_{\mathbb C}^*\bigl([\mathbb J-\mathbb R]\delta\mathscr A/\delta\mathcal Z+\mathbb B_{\mathrm{env}}u_{\mathrm{env}}+\mathbb B_{\mathrm{act}}a^*+\eta\bigr)=0$; $\mathcal K=0$ must enforce these compatibility and tangent constraints.
- $\mathbb J^*=-\mathbb J$ is the reversible generator in the chosen metric. A proposed field-theory Poisson block must also satisfy its Jacobi and constraint conditions.
- $\mathbb R=\mathbb R^*\succeq0$ is the dissipative operator. Its positivity is checked on the physical constraint manifold.
- $\mathscr A$ is an availability functional: a Hamiltonian in reversible blocks and a free-energy or Lyapunov functional in dissipative blocks, expressed in one physical unit after normalization.
- $u_{\mathrm{env}}$ contains measured boundary fluxes and sensory perturbations. $\mathbb B_{\mathrm{env}}$ localizes those ports at the body/environment interface.
- $a^*$ is the committed action. $\mathbb B_{\mathrm{act}}a^*$ acts on the actual state and carries a matching debit in the reserve equation.
- $\eta$ is a declared stochastic source. A thermal interpretation requires a fluctuation-dissipation relation; an externally imposed random drive requires a recorded covariance and work contribution.
- $\mathcal K=0$ contains body/gate readout definitions, simplex normalization, positivity constraints, shadow initial conditions, and work-ledger identities.

For a closed, unforced, deterministic block with $\mathbb C=I$ and one availability functional,

$$
\frac{d\mathscr A}{dt}
=-\left\langle
\frac{\delta\mathscr A}{\delta\mathcal Z},
\mathbb R
\frac{\delta\mathscr A}{\delta\mathcal Z}
\right\rangle
\le0,
$$

because the $\mathbb J$ contribution vanishes by antisymmetry. Open active systems maintain organization through measured ports. Their energy ledger must satisfy

$$
\boxed{
\frac{dE_{\mathrm{reserve}}}{dt}
=P_{\mathrm{uptake}}
-P_{\mathrm{maintenance}}
-P_{\mathrm{sense}}
-P_{\mathrm{shadow}}
-P_{\mathrm{act}}
-P_{\mathrm{learn}}
-P_{\mathrm{waste}},
}
\tag{1}
$$

with every term expressed in the same units and every outgoing term nonnegative under its declared sign convention. Equation (PB) earns a physical interpretation only after this ledger and the sector normalizations are closed.

### 3.1 Exact neutral limits

The architecture has three required reductions:

1. **No-agent limit.** Removing $b,\mathcal A,h,\widehat X,p,\Theta,e_\Theta,\vartheta$ and setting the two ports to zero leaves the selected actual-physics generator for $X$.
2. **Passive-body limit.** Retaining $b$ and transport while setting $a^*=0$ leaves a maintained or decaying open physical system with no prospective control claim.
3. **Shadow-off limit.** Retaining the actual state and controller wiring while disabling the shadow-to-commitment map must reproduce the preregistered reactive baseline exactly. Any default-off field-intelligence extension must satisfy this no-op contract.

These limits keep established physical predictions separate from agent-level hypotheses.

---

## 4. Exact reduction to the canonical two-fluid conversion

The canonical selected conversion law is

$$
\frac{D E_Y}{Dt}=-\gamma_{\mathrm{conv}}\,\varepsilon,
\qquad
\frac{D E_I}{Dt}=+\gamma_{\mathrm{conv}}\,\varepsilon,
\qquad
\varepsilon=E_Y-\varphi E_I,
\tag{2}
$$

where $\gamma_{\mathrm{conv}}=\lambda(1-q)\ge0$ for the selected $q$-gated theory form and $\gamma_{\mathrm{conv}}=\lambda$ for the ungated implementation path. Advection, diffusion, potential coupling, and sources are separate terms.

### 4.1 Density and imbalance coordinates

The invertible change of variables is

$$
\rho=E_Y+E_I,
\qquad
\varepsilon=E_Y-\varphi E_I,
$$

$$
\boxed{
E_Y=\frac{\varphi\rho+\varepsilon}{1+\varphi},
\qquad
E_I=\frac{\rho-\varepsilon}{1+\varphi}.
}
\tag{3}
$$

Nonnegative densities correspond exactly to

$$
\rho\ge0,
\qquad
-\varphi\rho\le\varepsilon\le\rho.
\tag{4}
$$

Equation (2) gives

$$
\boxed{
\frac{D\rho}{Dt}=0,
\qquad
\frac{D\varepsilon}{Dt}=-(1+\varphi)\gamma_{\mathrm{conv}}\,\varepsilon.
}
\tag{5}
$$

The local conversion matrix is

$$
\gamma_{\mathrm{conv}}
\begin{pmatrix}
-1&\varphi\\
1&-\varphi
\end{pmatrix},
$$

with eigenvalues $0$ and $-(1+\varphi)\gamma_{\mathrm{conv}}$. The zero mode is the equilibrium ray $(E_Y,E_I)\propto(\varphi,1)$; the contracting mode is $(1,-1)$. The left null vector $(1,1)$ gives total-density conservation.

### 4.2 Positive-semidefinite gradient-flow form

Define the normalized conversion availability

$$
\mathcal F_{\mathrm{conv}}(E_Y,E_I)
=\frac12\left(E_Y-\varphi E_I\right)^2
=\frac12\varepsilon^2
$$

and

$$
\boxed{
\mathbb R_{\mathrm{TF}}
=\frac{\gamma_{\mathrm{conv}}}{1+\varphi}
\begin{pmatrix}
1&-1\\
-1&1
\end{pmatrix}
\succeq0.
}
\tag{6}
$$

Then

$$
\boxed{
\frac{D}{Dt}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}
=-\mathbb R_{\mathrm{TF}}
\nabla_{(E_Y,E_I)}\mathcal F_{\mathrm{conv}}
=
\begin{pmatrix}-\gamma_{\mathrm{conv}}\varepsilon\\+\gamma_{\mathrm{conv}}\varepsilon\end{pmatrix}.
}
\tag{7}
$$

The Lyapunov derivative is

$$
\boxed{
\frac{D\mathcal F_{\mathrm{conv}}}{Dt}
=-(1+\varphi)\gamma_{\mathrm{conv}}\,\varepsilon^2\le0.
}
\tag{8}
$$

This embeds the canonical local conversion exactly in the dissipative block of equation (PB). It also fixes the interpretation: the conversion is rank-one contraction toward the $\varphi$ ray. It supplies one conserved material coordinate and one decaying composition coordinate.
With shared scalar diffusion $D\ge0$, incompressible advection, and periodic or no-flux boundaries, the spatial equations also give

$$
\partial_t\rho+\mathbf u\cdot\nabla\rho
=D\nabla^2\rho,
\qquad
\frac{d}{dt}\int_\Omega\rho\,d^3x=0,
\tag{GF1}
$$

and

$$
\boxed{
\frac{d}{dt}\left[\frac12\int_\Omega\varepsilon^2\,d^3x\right]
=-D\int_\Omega|\nabla\varepsilon|^2\,d^3x
-(1+\varphi)\int_\Omega \gamma_{\mathrm{conv}}(\rho,\varepsilon)\varepsilon^2\,d^3x
\le0.
}
\tag{GF2}
$$

The global result depends on equal channel diffusivities and the stated boundary and velocity conditions. Unequal diffusion, compressible prescribed flow, reservoirs, or external sources add explicit terms and require a separate energy balance.


### 4.3 Coherence remains a state diagnostic

The selected canonical diagnostic is

$$
q(\rho,\varepsilon)
=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}.
\tag{9}
$$

At $\varepsilon=0$,

$$
q_{\mathrm{eq}}(\rho)
=\frac{\rho^2}{\rho^2+\varphi^{-2}}<1
$$

for every finite $\rho$. At the reference state $(E_Y,E_I)=(1,\varphi^{-1})$, $\rho=\varphi$ and

$$
q_{\mathrm{eq}}=0.872677996\ldots,
\qquad
1-q_{\mathrm{eq}}=\frac{\varphi^{-2}}{3}=0.127322004\ldots.
$$

Thus exact compositional balance and maximal coherence are distinct limits. The scalar $q$ measures a normalized combination of density support and imbalance. Memory, branch identity, action preference, and semantic content require additional coordinates and causal tests.

### 4.4 Minimal Markovian open-system completion

The gradient-flow representation fixes a compatible fluctuation structure once a Gaussian Markovian bath and a fluctuation-dissipation normalization are selected. With $\mathcal F_{\mathrm{conv}}$ measured in units of $k_{\mathrm B}T_{\mathrm{bath}}$, write the following finite-dimensional or finite-volume/per-cell normalization:

$$
d\mathbf E
:=-\mathbb R_{\mathrm{TF}}\nabla_{\mathbf E}\mathcal F_{\mathrm{conv}}\,dt
 +\mathbb B_{\mathrm{TF}}\,dW_t,
\qquad
\mathbb B_{\mathrm{TF}}\mathbb B_{\mathrm{TF}}^{\mathsf T}
:=2\mathbb R_{\mathrm{TF}},
\tag{OS1}
$$

where $\mathbf E=(E_Y,E_I)^{\mathsf T}$. One minimal factor is

$$
\mathbb B_{\mathrm{TF}}
:=\sqrt{\frac{2\gamma_{\mathrm{conv}}}{1+\varphi}}
\begin{pmatrix}-1\\1\end{pmatrix}.
\tag{OS2}
$$

The noise is equal and opposite in the two channels, so $(1,1)\mathbb B_{\mathrm{TF}}=0$ and $\rho$ remains exactly conserved. In imbalance coordinates,

$$
d\varepsilon
:=-(1+\varphi)\gamma_{\mathrm{conv}}\,\varepsilon\,dt
 -\sqrt{2(1+\varphi)\gamma_{\mathrm{conv}}}\,dW_t.
\tag{OS3}
$$

Equations (OS1)–(OS3) use a finite-dimensional or finite-volume/per-cell normalization. In a continuum interpretation, the corresponding unit-temperature covariance is

$$
\left\langle\eta_i(\mathbf x,t)\eta_j(\mathbf x',t')\right\rangle
:=2\mathbb R_{\mathrm{TF},ij}(\mathbf x)\,
\delta^{(3)}(\mathbf x-\mathbf x')\delta(t-t').
$$

The continuum expression requires a declared cell/volume convention: a finite-volume discretization represents $\delta^{(3)}(\mathbf x-\mathbf x')$ by $\delta_{nn'}/\Delta V$, and the availability, mobility, and noise amplitudes must be converted consistently to the corresponding cell variables. Without that convention, $\mathbb B_{\mathrm{TF}}\mathbb B_{\mathrm{TF}}^{\mathsf T}=2\mathbb R_{\mathrm{TF}}$ is only a normalized per-cell shorthand.

Equations (OS1)–(OS3) are **Derived conditional** on the Markovian Gaussian bath, the quadratic conversion availability, the stated finite-volume or per-cell normalization, and the fluctuation-dissipation normalization. The closed scalar action does not select the dissipative tensor, the $(1-q)$ rate factor, the bath temperature, or the noise. A physical derivation must obtain them by tracing out identified degrees of freedom and must establish a separation between the bath correlation time and the conversion time.
When $\gamma_{\mathrm{conv}}=\lambda(1-q)$ depends on the state, the stochastic equation additionally needs a calculus convention. In an Itô equilibrium model with bath temperature restored, detailed balance generally adds the thermal drift $T_{\mathrm{bath}}\nabla_{\mathbf E}\!\cdot\mathbb R_{\mathrm{TF}}$; a Stratonovich model packages the same choice differently. Equations (OS1)–(OS3) give the frozen-background covariance and the zero-noise deterministic limit. They do not by themselves define a unique finite-temperature process.

The stochastic process also needs a boundary rule on the positivity wedge (4). The deterministic drift points inward at both density boundaries. Gaussian noise does not preserve that wedge by itself, so the minimal density interpretation uses reflecting, zero-normal-flux boundaries. Absorbing, clipping, or multiplicative-noise alternatives define different models and must be frozen before a probe.

### 4.5 Causal response functional

The deterministic residuals are

$$
\begin{aligned}
\mathcal R_Y&:=\partial_tE_Y+\mathbf u\cdot\nabla E_Y-D\nabla^2E_Y+\gamma_{\mathrm{conv}}\varepsilon,\\
\mathcal R_I&:=\partial_tE_I+\mathbf u\cdot\nabla E_I-D\nabla^2E_I-\gamma_{\mathrm{conv}}\varepsilon .
\end{aligned}
\tag{OS4}
$$

For an Itô Gaussian Markov conversion bath with covariance (OS1), the Martin–Siggia–Rose–Janssen–de Dominicis functional is

$$
\boxed{
S_{\mathrm{MSRJD}}
=\int dt\,d^3x\left[
\widehat{\mathbf E}^{\mathsf T}\boldsymbol{\mathcal R}
-\widehat{\mathbf E}^{\mathsf T}
\mathbb R_{\mathrm{TF}}\widehat{\mathbf E}
\right],
}
\tag{OS5}
$$

up to the conventional factor of $i$ in the response fields. Varying with respect to $\widehat{\mathbf E}$ and then taking the zero-noise saddle returns (OS4). Additional diffusion, boundary, or reservoir noise requires its own positive covariance kernel; the deterministic coefficient $D$ does not fix that kernel without a thermodynamic free energy and bath model.

Linearize around a uniform equilibrium state $\varepsilon=0$, $\rho=\rho_0$, with $\mathbf u=0$ and

$$
\Gamma_0:=(1+\varphi)\lambda\left[1-q_{\mathrm{eq}}(\rho_0)\right].
$$

The retarded density and composition responses are

$$
\boxed{
G_{\rho\rho}^{R}(\omega,\mathbf k)
=\frac{1}{-i\omega+Dk^2},
\qquad
G_{\varepsilon\varepsilon}^{R}(\omega,\mathbf k)
=\frac{1}{-i\omega+Dk^2+\Gamma_0}.
}
\tag{OS6}
$$
At the canonical reference state $(E_Y,E_I)=(1,\varphi^{-1})$, so $\rho=\varphi$ and $\varepsilon=0$,
$$
q_{\mathrm{eq}}=\frac{\varphi^2}{3},\qquad
1-q_{\mathrm{eq}}=\frac{\varphi^{-2}}{3}.
$$
Because $1+\varphi=\varphi^2$, the gated rate therefore has the exact **Derived conditional** value
$$
\boxed{\Gamma_0=(1+\varphi)\lambda(1-q_{\mathrm{eq}})=\frac{\lambda}{3}}.
$$
The ungated implementation instead gives $\Gamma_0=\varphi^2\lambda$. At zero wavenumber, a small fixed-$\rho$ imbalance obeys $\varepsilon(t)=\varepsilon_0\exp(-\lambda t/3)$; with diffusion the pole is $-i\omega+Dk^2+\lambda/3$. Since
$$
q=\frac{\varphi^2}{3+\varepsilon^2}
=\frac{\varphi^2}{3}-\frac{\varphi^2}{9}\varepsilon^2+O(\varepsilon^4),
$$
the $q$ deficit relaxes at $2\lambda/3$, twice the imbalance rate. Under a frozen unit-temperature fluctuation-dissipation normalization, the corresponding scalar Langevin equation is
$$
\mathrm d\varepsilon=-\frac{\lambda}{3}\varepsilon\,\mathrm dt
-\sqrt{\frac{2\lambda}{3}}\,\mathrm dW_t,
$$
with normalized autocorrelation corner $\lambda/3$.
The drift curve and its pole are deterministic consequences of the selected conversion law and require no bath. The frozen-unit-temperature FDT equation and autocorrelation claim are conditional on a Gaussian Markov conversion bath and are stated here at $k=0$. With OS3 conversion noise only, the finite-$k$ spectrum has noise power $2\Gamma_0$ and denominator $\omega^2+(Dk^2+\Gamma_0)^2$, giving equal-time variance $\Gamma_0/(Dk^2+\Gamma_0)$; a full equilibrium variance of $1$ would require an additional diffusion-noise kernel $2Dk^2$, which remains unclosed. The coefficient $D$ alone does not fix that kernel.

The nonlinear fixed-$\rho=\varphi$ rate is
$$
\Gamma(\varepsilon)
=\frac{\varphi^2\lambda(\varphi^{-2}+\varepsilon^2)}
{3+\varepsilon^2},
\qquad
\frac{\mathrm d\Gamma}{\mathrm d(\varepsilon^2)}
=\frac{\varphi^4\lambda}{(3+\varepsilon^2)^2}>0.
$$
At fixed $\rho=\varphi$ the positivity wedge restricts $\varepsilon$ to $-\varphi^2\le\varepsilon\le\varphi$. The formal $\varepsilon^2\to\infty$ limit is therefore outside the physical state space. Within this wedge $\Gamma(\varepsilon)$ is monotone in $\varepsilon^2$ and equals $\lambda/3$ at zero imbalance; finite impulses decay faster initially and cross over to the $\exp(-\lambda t/3)$ tail, but a single exponential is not a global nonlinear law.
For the normalized $q$-gated drift-rate curve,
$$
R_Q(\varepsilon):=\frac{\Gamma(\varepsilon)}{\Gamma(0)}
=\frac{3(1+\varphi^2\varepsilon^2)}{3+\varepsilon^2},
\qquad -\varphi^2\le\varepsilon\le\varphi .
$$
At fixed $\rho=\varphi$, approaching the $E_Y\to0$ boundary from the interior ($\varepsilon\to-\varphi^2$) gives $R_Q\to5.767427$, while approaching the $E_I\to0$ boundary ($\varepsilon\to\varphi$) gives $R_Q\to4.194048$. Under the frozen FDT bath only, the same expression is also the normalized conversion-diffusivity curve. These are analytic approach-to-boundary values; boundary-layer and reflecting-boundary transients are excluded from curve fits, which use interior points only.

A closed-time-path representation has the corresponding retarded and advanced kernels and a Keldysh noise kernel. That kernel is fixed by a fluctuation-dissipation relation only after an equilibrium bath and $T_{\mathrm{bath}}$ are supplied. The construction is a causal response theory for coarse densities, not a unitary quantum field theory.

Equation (OS6) distinguishes the selected open-system dynamics from the closed scalar ansatz. The coarse composition mode has a first-order relaxation pole, while a conservative scalar fluctuation has a second-order oscillatory denominator of the form $-\omega^2+k^2+m^2$. Recovering (OS6) from the local two-singlet action therefore requires traced-out degrees of freedom, a bath spectral density, or auxiliary dissipative fields; the local two-singlet action alone cannot do it.

The quantum-geometric campaign in
`foundations/quantum-measurement-derivation.md` §8.3 adopts this same
micro-to-meso direction as a Hypothesized physical architecture. The finite
carrier reservoir and `foundations/loop-to-bubble-projection-theorem.md`
derive conditional carrier-to-density projections. The shared-loop theorem
also isolates the common-gate and common-transport conditions for exact
closure and gives the internal relaxation gap. Neither construction derives
the carrier state from the regulated complex quantum configuration or from
the P1 effective field theory. This missing physical identification is the
remaining GQ3 and P1→P2 boundary.

The completion ansatz in
`foundations/geometric-manifold-completion.md` embeds the projected density
pair in a positive Hermitian fibre and supplies one minimal
positivity-preserving two-jump conversion lift. Its diagonal equations
reproduce the canonical population operator exactly, while its transverse
coherence decays at $\gamma_c=\gamma_\varepsilon/2$. With the state-dependent
$q$, the lift is a nonlinear pointwise Lindblad-form vector field whose
trajectories reparametrize a fixed linear GKSL flow. The conditional rate
belongs to the selected lift. The physical carrier map and microscopic
conversion reservoir remain open. The integrated balance and exact
finite-density support boundary are derived in
`foundations/yin-yang-qi-dynamical-geometry.md`.

---

## 5. Constitutive blocks for becoming

Equation (PB) becomes executable only when every block below is specified. These forms are minimal admissibility conditions. Their kernels, rates, masks, costs, and physical normalizations are unclosed quantities until an implementation freezes them before a run.

### 5.1 Maintained embodiment

A body field $b(\mathbf x,t)\in[0,1]$ distinguishes an inside, an outside, and a localized interface. A general dissipative maintenance law has the form

$$
\mathbb C_b D_t b
=-\mathbb R_b\frac{\delta\mathcal F_b}{\delta b}
+S_{\mathrm{repair}}(\mathcal A,X,b)
-S_{\mathrm{damage}}(X,b),
\tag{10}
$$

with $\mathbb R_b\succeq0$ and explicit reserve debit for $S_{\mathrm{repair}}$. A body claim requires persistence, recovery after bounded perturbation, exchange through the interface, and failure when reserve falls below a frozen viability condition. A static mask may serve as an experimental fixture; it establishes no self-maintenance result.

The body coordinate $m$ changes through boundary and mask-interface flux under the full transport law. For fixed $\chi_b$, write the selected density balance as $\partial_t\rho+\nabla\cdot\mathbf J_\rho=S_\rho$. Then

$$
\dot m
:=-\int_{\partial\Omega}\chi_b\,\mathbf J_\rho\cdot d\mathbf A
+\int_\Omega\nabla\chi_b\cdot\mathbf J_\rho\,d^3x
+\int_\Omega\chi_b S_\rho\,d^3x,
\tag{11}
$$

where the second term is the explicit interface contribution for a sharp or smooth mask and the last term vanishes when the selected density law has no source. A maintained body therefore has an observable flux condition rather than a purely visual boundary.

### 5.2 Boundary-localized sensing

Sensory state is produced by a finite-gain interface map

$$
y_t=\mathcal S_{\partial b}[X_t,U_t],
\tag{12}
$$

whose support lies on or near $\nabla b$. The map records modality, gain, bandwidth, noise covariance, propagation delay, and source work. Global access to the complete simulation state belongs to the experimenter and is excluded from the agent’s sensory input.

### 5.3 Ordered history

Let $o_t$ be a declared observation/error vector. A causal history field satisfies

$$
(\partial_t+\partial_\sigma)h(\sigma,t)
=-\Gamma_h h(\sigma,t),
\qquad
h(0,t)=\mathcal W(o_t),
\tag{13}
$$

where $\sigma\ge0$ is memory age and $\Gamma_h$ is stable. A finite filter-bank approximation is

$$
h_t^a=\int_0^\infty k_a(s)o_{t-s}\,ds,
\qquad
k_a(s)=0\quad(s<0),
\qquad
\int_0^\infty|k_a(s)|\,ds<\infty.
\tag{14}
$$

For $k_a(s)=\gamma_a e^{-\gamma_as}$,

$$
\dot h^a=\gamma_a(o_t-h^a).
\tag{15}
$$

The optional Cassi IIR path is one scalar special case when $o=\varepsilon^2$. An ordered memory claim requires a lesion that changes later prediction or steering while current observations are matched.

### 5.4 Action-conditioned shadows

For a frozen finite action set $\{a_\alpha\}_{\alpha=1}^{N_a}$, each internal shadow evolves without reading future actual data:

$$
\partial_\tau\widehat X_t^\alpha(\tau)
=\widehat{\mathcal G}_{\vartheta_t}
\left[\widehat X_t^\alpha(\tau),a_\alpha\right],
\qquad
\widehat X_t^\alpha(0)
=\operatorname{Enc}(m_t,h_t,g_t),
\tag{16}
$$

for $0\le\tau\le T_f$. A branch readout is

$$
\widehat m_{\alpha,t}
=\mathcal R_m\left[\widehat X_t^\alpha(T_f)\right].
\tag{17}
$$

The realized consequence enters the system only after action and observation. For a scalar branch readout, define the signed residual and a nonnegative loss by

$$
r^{\mathrm{pred}}_{\alpha,t+T_f}
:=m^{\mathrm{obs}}_{t+T_f}-\widehat m_{\alpha,t},
\qquad
\delta_{\alpha,t+T_f}
:=\ell\!\left(r^{\mathrm{pred}}_{\alpha,t+T_f}\right)\ge0,
\tag{18}
$$

with the dimension-matched loss $\ell$ frozen before evaluation. For a distributional forecast, replace $\ell(r^{\mathrm{pred}})$ by a declared nonnegative predictive divergence $D_{\mathrm{pred}}(\widehat{\mathsf P}_{\alpha,t},\mathsf P^{\mathrm{obs}}_{t+T_f})$ and freeze its units and logarithm convention.

A shadow field is physically internal when it occupies state and consumes resources inside the modeled boundary. A software copy controlled entirely outside the boundary is an experimenter-side forward model unless the implementation explicitly includes its causal ports and energy cost in the agent.

### 5.5 Possibility allocation

Let $V_\alpha$ be a branch score assembled from predicted viability, work, damage, information gain, option preservation, and uncertainty. Each contribution has its own observable or model source and dimension before normalization. A normalized branch allocation may be defined variationally:

$$
p_t
=\mathop{\arg\min}_{p\in\Delta_{N_a}}
\left[
-\sum_\alpha p_\alpha V_\alpha
+T_p\sum_\alpha p_\alpha\ln p_\alpha
\right],
\tag{19}
$$

For $T_p>0$, with the convention $0\ln0=0$, the unique minimizer is

$$
p_{\alpha,t}
=\frac{\exp(V_{\alpha,t}/T_p)}
{\sum_\gamma\exp(V_{\gamma,t}/T_p)},
\qquad
p_\alpha\ge0,
\qquad
\sum_\alpha p_\alpha=1.
\tag{20}
$$

$T_p$ is a controller convention with score units and is required to be positive for (19)–(20). It is not a $\varphi$-derived physical constant. Let $\tau_p>0$ be a controller timescale. A dynamical alternative may use a column-form Markov generator plus a dimensionally matched replicator term,

$$
\dot p_\alpha
:=(\mathsf L_Ap)_\alpha
+\tau_p^{-1}\frac{p_\alpha}{T_p}
\left(V_\alpha-\sum_\gamma p_\gamma V_\gamma\right).
\tag{21}
$$

Here $\mathsf L_A$ has units of $1/\mathrm{time}$, $\mathbf 1^{\mathsf T}\mathsf L_A=0$, and its off-diagonal transition rates are nonnegative. The term $\tau_p^{-1}p_\alpha(V_\alpha-\langle V\rangle_p)/T_p$ also has units of $1/\mathrm{time}$ and preserves the simplex. The choice between algebraic and dynamical allocation is fixed before an experiment.

### 5.6 Finite attention

For $N_g$ sensed channels, attention is a finite allocation

$$
\Theta\in\Delta_{N_g},
\qquad
\Theta_i\ge0,
\qquad
\sum_i\Theta_i=1.
\tag{22}
$$

One admissible variational definition, for $T_\Theta>0$, is

$$
\Theta_t
=\mathop{\arg\min}_{\theta\in\Delta_{N_g}}
\left[
\sum_i\theta_i C_i(m,h,g,\widehat m)
+T_\Theta\sum_i\theta_i\ln\theta_i
\right].
\tag{23}
$$

The controller must expose the tradeoff: increasing sensing, memory resolution, branch count, or forecast horizon in one place consumes reserve and reduces capacity elsewhere. A static gain vector establishes channel weighting; an attention claim requires causal reallocation of a frozen finite budget.

### 5.7 Commitment and action

The commitment map

$$
a^*=\mathcal C_{\mathrm{commit}}(p,V,h,\Theta,\mathcal A)
\tag{24}
$$

must satisfy four conditions:

1. a finite admissible action set or bounded action manifold;
2. hysteresis or a dwell condition that prevents arbitrarily fast switching;
3. an action port that changes the actual state;
4. a matched reserve debit measured in physical units.

The decisive prospective-causality chain is

$$
\boxed{
\widehat m_\alpha
\longrightarrow(p,\Theta)
\longrightarrow a^*
\longrightarrow X_{t+\Delta}.
}
\tag{25}
$$

Every arrow is tested by intervention with the present actual state, observation history, and external controls matched.

### 5.8 Resource debit

The predicted cumulative debit is formed from declared nonnegative power rates $c_i\ge0$ and $c_\alpha\ge0$:

$$
\widehat e_{\Theta,t}
:=\int_0^t
\left[
\sum_i\Theta_i(s)c_i(X_s,U_s)
+\sum_\alpha p_\alpha(s)c_\alpha\!\left(\widehat X_s^\alpha(\tau_{\alpha,s}),U_s^\alpha\right)
\right]ds.
\tag{26}
$$

Here $\tau_{\alpha,s}\in[0,T_f]$ is the frozen branch-local forecast coordinate used by the debit model, and all $c_i,c_\alpha$ have energy-per-time units. If a signed score is used instead, it is not a debit and must not be substituted into equation (28).
The realized debit is measured from a calibrated power channel,

$$
\boxed{
e_{\Theta,t}
=\int_0^tP_{\mathrm{ext}}(X_s,U_s,\Theta_s,a_s^*)\,ds,
\qquad
P_{\mathrm{ext}}\ge0.
}
\tag{27}
$$

A physical debit satisfies

$$
e_{\Theta,t}
\le
E_{\mathrm{reserve}}(0)-E_{\mathrm{reserve}}(t)
+E_{\mathrm{imported}}(t)-E_{\mathrm{exported}}(t)
\tag{28}
$$

under one sign convention and unit system. Canonical conversion conserves $\rho$ and contains no joule normalization or external power channel. The energy claim remains open until those quantities are instrumented.

### 5.9 Bounded learning

Let $\vartheta$ collect constitutive fields used by sensing, forecasting, scoring, commitment, and actuation. Learning is a projected, resource-debited update

$$
D_t\vartheta
=\Pi_{\mathcal C_\vartheta}
\mathcal U_\vartheta
\left(\vartheta,\delta,h,g,\Theta,e_\Theta\right),
\tag{29}
$$

where $\mathcal C_\vartheta$ enforces positivity, finite transport coefficients, bounded gains, stable memory kernels, and every other sector constraint. Prediction error arrives after the represented consequence. A learning claim requires that altering past prediction-error history, while matching the current observable state, changes a later action through $\vartheta$.

---

## 6. Controlled emergence from the field

The agent-level coordinates become physical observables through a coarse-graining test rather than a naming convention.

### 6.1 Mori projection and reaction-coordinate selection

Use the controlled-history space itself for the projection. Let

$$
\mathscr H_t:=\bigl(X_{[0,t]},U_{[0,t]}\bigr),
\qquad
\xi_t=\Xi_t[\mathscr H_t],
$$

where $\Xi_t$ is a causal reaction-coordinate map. At the architecture level, the selected coordinate vector contains

$$
\xi_t=
\bigl(m_t,h_t,\widehat m_t,p_t,g_t,\Theta_t,e_{\Theta,t},\vartheta_t\bigr).
$$

For any causal observable $A_t=A[\mathscr H_t]$, define the conditional projection under the ensemble measure $\mu$ on recorded controlled histories:

$$
(\mathcal P_t A)_t
:=\mathbb E_\mu[A_t\mid\xi_t,U_t],
\qquad
\mathcal Q_t=I-\mathcal P_t.
\tag{30}
$$

The conditioning on $U_t$ here is the current-control conditioning; future-control conditioning is specified separately in equation (34). A candidate map $\Xi$ in the held-out selection below produces $\xi_t^\Xi:=\Xi_t[\mathscr H_t]$. The selected map is $\Xi^*$, after which $\xi_t$ denotes $\xi_t^{\Xi^*}$.

Select a finite reaction-coordinate map and drift model by a held-out closure problem,

$$
(\Xi^*,F^*)
:=\mathop{\arg\min}_{\Xi\in\mathcal A_d,F}
\mathbb E_\mu\!\left[
\int_0^T
\left\|\dot\xi_{t+s}^{\Xi}
-F\!\left(\xi_{t+s}^{\Xi},U_{t+s}\right)\right\|_W^2ds
\right]
+\mathcal P_{\mathrm{complexity}}(\Xi,F).
\tag{31}
$$

The candidate coordinates must be causal and absolutely continuous on the evaluation intervals, or carry a declared weak/path derivative. This requirement also applies to algebraic controller coordinates such as $p$ and $\Theta$; tie points or jumps require a separately frozen event or finite-difference treatment. The metric $W$ is a fixed positive-definite block metric/whitening operator that converts the differently dimensioned coordinate blocks to a common dimensionless norm. Dimension, masks, regularity, model class, train/validation split, and penalty are fixed before the held-out run.

The unrestricted conditional-mean Mori drift and its residual are

$$
F_\mu(\xi_t,U_t)
:=\mathbb E_\mu[\dot\xi_t\mid\xi_t,U_t],
\qquad
r_{\mathrm{MZ},t}
:=\dot\xi_t-F_\mu(\xi_t,U_t)
:=(\mathcal Q_t\dot\xi)_t .
$$

The finite fitted model selected by (31) is distinct:

$$
\dot\xi_t=F^*(\xi_t,U_t)+r_t^*,
\qquad
r_t^*:=\dot\xi_t-F^*(\xi_t,U_t).
\tag{32}
$$

A relative closure statistic is

$$
R_{\mathrm{cl}}
:=\frac{\mathbb E_\mu\|r_t^*\|_W^2}
{\mathbb E_\mu\|\dot\xi_t\|_W^2},
\qquad
\mathbb E_\mu\|\dot\xi_t\|_W^2>0.
\tag{33}
$$

If the denominator vanishes, the relative statistic is undefined; report instead the absolute residual $R_{\mathrm{abs}}:=\mathbb E_\mu\|r_t^*\|_W^2$ and classify the coordinate as dynamically degenerate for this test. The threshold is frozen before evaluation. $R_{\mathrm{cl}}$ uses the held-out fitted residual $r_t^*$; it equals the Mori residual only when the fitted class recovers the unrestricted conditional mean $F_\mu$. Small training residuals carry no closure verdict; the residual and discarded-mode dependence are measured on held-out controlled histories.

### 6.2 Autonomy condition

A finite coordinate is autonomous over $\Delta$ when

$$
\mathcal L\!\left(\xi_{t+\Delta}\mid X_{[0,t]},U_{[0,t+\Delta]}\right)
\approx
\mathcal L\!\left(\xi_{t+\Delta}\mid\xi_t,U_{[t,t+\Delta]}\right),
\tag{34}
$$

where $\approx$ denotes a preregistered distributional divergence and tolerance. Let $H_t^{\mathrm{disc}}$ denote the recorded history variables excluded by $\xi_t$ under the frozen representation. A measurable sufficient criterion for the conditional-KL version of (34) is

$$
I\!\left(
\xi_{t+\Delta};H_t^{\mathrm{disc}}
\mid\xi_t,U_{[t,t+\Delta]}
\right)
\le\epsilon_{\mathrm{aut}},
\tag{35}
$$

with $\epsilon_{\mathrm{aut}}\ge0$ measured in nats for the displayed natural-log convention, or in bits if the logarithm base is changed and frozen. If a different distributional divergence is used for (34), its relation to (35) must be established separately; the two criteria are not algebraically equivalent without that definition.

Timescale separation can motivate a finite closure; the measured residual and conditional dependence decide it.


### 6.3 Conditional prospective-steering statement

Assume:

1. the selected physical substrate is well posed under recorded controls;
2. $R_{\mathrm{cl}}$ and discarded-mode dependence satisfy their held-out bounds;
3. the history filters are causal and stable;
4. branch forecasts satisfy their held-out error bound over $T_f$;
5. the branch and attention optimizations are unique and stable in their inputs;
6. the power channel and reserve ledger are calibrated;
7. a branch intervention changes the controller input while the current actual state and controls are matched.

On the validated domain, assume $F^*$ is $L$-Lipschitz in $\xi$, uniformly over the recorded controls. Define the reduced trajectory by
$$
\dot{\widetilde\xi}_t=F^*(\widetilde\xi_t,U_t),
\qquad
\widetilde\xi_0=\xi_0-\delta_0,
$$
using the same control history as the full trajectory. Then
$$
\|\xi_t-\widetilde\xi_t\|
\le e^{Lt}\|\delta_0\|
+\int_0^t e^{L(t-s)}\|r_s^*\|\,ds .
$$
For matched initial conditions, $\delta_0=0$. Forecast error affects action and actual state only through separately measured controller sensitivity and intervention margins; it is not folded into this state-closure bound without such a gain. The result is conditional coarse-grained prospective steering, and the mediated causal effect in equation (25) must still be nonzero. A microscopic identity for the agent variables requires the matching program in §7.

---

## 7. Physics nested inside becoming

Physical becoming does not replace physics. It adds open-system and prospective blocks around an actual-physics generator and requires every new block to reduce to that generator in its neutral limit.

### 7.1 The nesting map

Let $P_X$ project equation (PB) onto the actual state. The required identity is

$$
\boxed{
P_X\,\mathfrak B[\mathcal Z]
=\mathcal G_{\mathrm{actual}}[X]
+\mathbb B_{\mathrm{env}}u_{\mathrm{env}}
+\mathbb B_{\mathrm{act}}a^*,
\qquad
P_X\,\mathfrak B[X,0]
=\mathcal G_{\mathrm{actual}}[X].
}
\tag{36}
$$

Here $\mathfrak B$ denotes the full right-hand side of equation (PB). The first relation says that internal possibilities influence reality through declared physical ports. The second says that deleting the agent blocks returns the selected physical law.

### 7.2 Physical sector hierarchy

| Level | State/law | Matching requirement | Current status |
|---|---|---|---|
| P0 | established Standard Model + general relativity in their tested domains | reproduce established observables | established external physics |
| P1 | generic Standard Model plus two-singlet EFT; restricted Cassi matching surface | retain every allowed counterterm; test vacuum, unitarity, and protection of the restricted relations | generic EFT closed; restricted $\varphi$ surface **REJECTED** as RG invariant |
| P2 | canonical two-density PDE and causal response theory | derive as a controlled coarse-grained limit of P1, including bath, noise, and transport coefficients | deterministic and conditional carrier reductions closed; P1 physical matching open |
| P3 | maintained body and reserve | derive or measure boundary, flux, repair, damage, and work balance | proposed |
| P4 | reaction-coordinate state $(m,h,g)$ | held-out closure and autonomy | proposed |
| P5 | shadows, possibility allocation, attention, commitment | forecast accuracy, branch causality, debit | proposed |
| P6 | learned multiscale organization | stable bounded plasticity and generalization | proposed |

The hierarchy is complete as a list of required mathematical interfaces. It is incomplete as a fundamental theory until P1→P2 and P2→P4 are derived and P3→P6 pass causal experiments.

### 7.3 Microscopic action boundary

A candidate covariant microscopic sector has the scalar-tensor form

$$
S_{\mathrm{micro}}^{\mathrm{cand}}
=\int d^4x\sqrt{-g}\left[
\frac{M_{\mathrm{Pl}}^2}{2}F(\Phi^a)R
-\frac12\gamma_{ab}(\Phi)\nabla_\mu\Phi^a\nabla^\mu\Phi^b
-V(\Phi)
+\mathcal L_{\mathrm{SM}}
+\mathcal L_{\mathrm{mix}}
\right].
\tag{37}
$$

With no internal singlet symmetry, the most general power-counting-renormalizable Standard Model extension by two real gauge singlets $\chi_a=(\chi_Y,\chi_I)$ can be written, after making the constant kinetic matrix canonical, as

$$
\begin{aligned}
\mathcal L_{\chi H}
={}&-\frac12\delta^{ab}\nabla_\mu\chi_a\nabla^\mu\chi_b
-V_{\mathrm{gen}}(\chi,H),\\
V_{\mathrm{gen}}
={}&V_H(H)
+t_a\chi_a
+\frac12m^2_{ab}\chi_a\chi_b
+\frac1{3!}\mu_{abc}\chi_a\chi_b\chi_c\\
&+\frac1{4!}\lambda_{abcd}\chi_a\chi_b\chi_c\chi_d
+\left(c_a\chi_a+\frac12\eta_{ab}\chi_a\chi_b\right)H^\dagger H .
\end{aligned}
\tag{EFT1}
$$

The tensors are real and symmetric in their singlet indices. Their mass dimensions are $[t_a]=3$, $[m^2_{ab}]=2$, $[\mu_{abc}]=[c_a]=1$, and $[\lambda_{abcd}]=[\eta_{ab}]=0$. This basis includes tadpoles, mixed masses, every cubic and quartic singlet operator, linear and quadratic Higgs portals, and the Standard Model Higgs potential $V_H$. A constant positive kinetic-mixing matrix adds no independent local interaction because an invertible linear field redefinition makes it canonical.

Renormalization on a curved background also requires

$$
\begin{aligned}
\Delta\mathcal L_R={}&
\frac12\left[
M_0^2+2\zeta_a\chi_a+\xi_{ab}\chi_a\chi_b
+2\xi_HH^\dagger H
\right]R-\Lambda_c\\
&+a_{R^2}R^2+a_{C^2}C_{\mu\nu\rho\sigma}C^{\mu\nu\rho\sigma}
+a_E\mathcal E_4+a_{\Box R}\Box R ,
\end{aligned}
\tag{EFT2}
$$

up to four-dimensional curvature identities and boundary terms. Here $[\zeta_a]=1$ and the $\xi$ coefficients are dimensionless. The curvature-squared terms are gravitational counterterms; they need not be interpreted as a weakly coupled fundamental gravity theory.

Independent reflections $\mathbb Z_{2,Y}\times\mathbb Z_{2,I}$ provide one possible Cassi restriction. They remove every operator odd in either singlet and reduce the interacting potential to

$$
\begin{aligned}
V_{\mathbb Z_2\times\mathbb Z_2}={}&
\frac12m_Y^2\chi_Y^2+\frac12m_I^2\chi_I^2
+\frac{\lambda_Y}{4}\chi_Y^4
+\frac{\lambda_I}{4}\chi_I^4\\
&+\frac{\lambda_{YI}}{4}\chi_Y^2\chi_I^2
+\frac12\left(\eta_{YH}\chi_Y^2+\eta_{IH}\chi_I^2\right)H^\dagger H ,
\end{aligned}
\tag{EFT3}
$$

with diagonal curvature couplings $\tfrac12(\xi_Y\chi_Y^2+\xi_I\chi_I^2)R$. The reflection symmetry does not fix any coefficient. Setting the portals to zero isolates the singlets from Standard Model matter; a laboratory signature then requires gravitational mixing or another declared transduction port.

Under this two-singlet reading, the quartic ansatz displayed in `foundations/unified-lagrangian.md` §1 is

$$
V_{\mathrm{Cassi},4}
:=\frac{g_4}{4}(\chi_Y^2+\chi_I^2)^2
+\frac{\lambda_A}{2}(\chi_Y^2-\varphi\chi_I^2)^2,
\tag{EFT4}
$$

where $g_4$ and $\lambda_A$ are dimensionless microscopic quartics. Neither is the dimensionful PDE conversion rate. In convention (EFT3), this ansatz occupies the two-parameter surface

$$
\boxed{
\lambda_Y=g_4+2\lambda_A,\quad
\lambda_I=g_4+2\varphi^2\lambda_A,\quad
\lambda_{YI}=2g_4-4\varphi\lambda_A.
}
\tag{EFT5}
$$

For $g_4,\lambda_A\ge0$, equation (EFT4) is nonnegative. It is coercive when $g_4>0$; at $g_4=0$ it has a flat $\chi_Y^2=\varphi\chi_I^2$ ray. A nonzero vacuum requires the mass and portal terms and must satisfy the full Hessian test. The general quartic (EFT3) is bounded below when

$$
\lambda_Y\ge0,\qquad
\lambda_I\ge0,\qquad
\lambda_{YI}\ge-2\sqrt{\lambda_Y\lambda_I},
\tag{EFT6}
$$

with strict inequalities for a strictly positive quartic away from the origin.

For nonzero vacuum values $v_Y,v_I$, stationarity of the reflection-symmetric potential gives

$$
\begin{pmatrix}
\lambda_Y & \lambda_{YI}/2\\
\lambda_{YI}/2 & \lambda_I
\end{pmatrix}
\begin{pmatrix}v_Y^2\\v_I^2\end{pmatrix}
=-\begin{pmatrix}m_Y^2\\m_I^2\end{pmatrix}.
\tag{EFT6a}
$$

The $\varphi$ ray $v_Y^2=\varphi v_I^2$ therefore exists only if

$$
\boxed{
m_Y^2\left(\lambda_I+\frac{\varphi\lambda_{YI}}2\right)
=m_I^2\left(\varphi\lambda_Y+\frac{\lambda_{YI}}2\right),
\qquad
v_I^2=-\frac{m_Y^2}{\varphi\lambda_Y+\lambda_{YI}/2}>0 ,
}
\tag{EFT6b}
$$

followed by the full Hessian test. On the Cassi surface (EFT5), both bracketed quartic combinations equal $g_4\varphi^2$. For $g_4>0$, the ray therefore requires $m_Y^2=m_I^2$; at $g_4=0$, the denominator in (EFT6b) vanishes, and a nonzero point on the isolated quadratic-plus-quartic sector instead requires $m_Y^2=m_I^2=0$.


A minimal symmetry-breaking realization illustrates the extra assumptions:

$$
V_{\mathrm{vac}}
:-\frac{\mu_\chi^2}{2}\rho_\chi
+\frac{g_4}{4}\rho_\chi^2
+\frac{\lambda_A}{2}\varepsilon_\chi^2,
\qquad
\rho_\chi:=\chi_Y^2+\chi_I^2,\quad
\varepsilon_\chi:=\chi_Y^2-\varphi\chi_I^2 .
\tag{EFT6c}
$$

For $\mu_\chi^2,g_4,\lambda_A>0$, its minimum has $\rho_\chi=\mu_\chi^2/g_4$ and $\chi_Y^2/\chi_I^2=\varphi$. This vacuum is not contained in the source quartic alone. In the complete EFT it additionally requires equality of the two effective quadratic coefficients after Higgs and curvature backgrounds are included. The $\varphi\ne1$ attractor term breaks the $SO(2)$ symmetry that could protect that equality, so the equality is another matching condition. Nonzero values of both singlets spontaneously break $\mathbb Z_{2,Y}\times\mathbb Z_{2,I}$ and produce degenerate vacua; a cosmological use must address the associated domain-wall sector.
Within this minimal vacuum, if the singlet kinetic terms are canonical and portal and curvature contributions are negligible, the Hessian has two orthonormal modes
$$
\begin{aligned}
h_R&:=\frac{\sqrt{\varphi}\,\delta\chi_Y+\delta\chi_I}{\varphi},
&
h_A&:=\frac{\delta\chi_Y-\sqrt{\varphi}\,\delta\chi_I}{\varphi},
&
h_R\cdot h_A&=0,\\
m_R^2&=2g_4\rho_\chi=2\mu_\chi^2,
&
m_A^2&=4\varphi\lambda_A\rho_\chi,
&
\frac{m_A^2}{m_R^2}&=\frac{2\varphi\lambda_A}{g_4}.
\end{aligned}
\tag{EFT6d}
$$
The radial mode makes an angle $\theta_R$ with the $\delta\chi_Y$ axis satisfying $\tan\theta_R=\varphi^{-1/2}$, hence $\theta_R\approx38.1727^\circ$. This is **Derived conditional** within the stated minimal vacuum: $g_4$, $\lambda_A$, and $\mu_\chi^2$ remain free, so the result fixes neither absolute scalar masses nor a universal mass ratio outside this restricted action and its negligible-portal/curvature limit.
These displayed eigenvectors use the $(+,+)$ vacuum representative. The other $\mathbb Z_{2,Y}\times\mathbb Z_{2,I}$ sign-related vacua flip the corresponding eigenvector components but preserve the masses and $|\tan\theta_R|=\varphi^{-1/2}$.


Tree-level partial-wave unitarity supplies a domain rather than a prediction. For example, constant $YY\rightarrow YY$ scattering has $|a_0|=3|\lambda_Y|/(8\pi)$, so $|\lambda_Y|\le4\pi/3$ is necessary; the coupled-channel scattering matrix adds joint bounds. The framework fixes no numerical $g_4$ or $\lambda_A$, so it currently predicts neither a scalar mass nor a scattering amplitude. Any selected $\varphi$-power value must pass these bounds before perturbative loop evolution is used.

The optional spatial operator $\kappa_4(\nabla^2\chi)^2$ has dimension six and is not Lorentz invariant. Positive $\kappa_4$ gives $\omega^2=k^2+\kappa_4k^4$ without a higher-time-derivative Ostrogradsky mode, but it belongs to a mesoscopic Lifshitz theory with cutoff of order $\kappa_4^{-1/2}$ and is excluded from the covariant renormalizable basis (EFT1).

The dimensions force an explicit P1→P2 bridge. In natural units $[\chi_a^2]=M^2$, whereas a physical energy density has dimension $M^4$. A possible bookkeeping map is

$$
E_a^{\mathrm{phys}}
:=Z_aM_{\mathrm{match}}^2\langle\chi_a^2\rangle,
\qquad
E_a^{\mathrm{solver}}
:=\frac{E_a^{\mathrm{phys}}}{\rho_*},
\tag{EFT7}
$$

with $Z_a$ dimensionless, $M_{\mathrm{match}}$ a matching scale, and $\rho_*$ the external physical reference density. Equation (EFT7) closes the dimensions only. Deriving its coefficients, averaging kernel, and domain is part of the open coarse-graining problem.

### 7.4 Covariant gravity boundary

A position-dependent Newton coupling requires a scalar-tensor completion rather than the substitution $G\mapsto G_{\mathrm{eff}}(x)$ in Einstein’s equation. A general two-derivative Jordan-frame sector is

$$
S_{g\chi}
=\int d^4x\sqrt{-g}\left[
\frac12F(\chi)R
-\frac12K_{AB}(\chi)\nabla_\mu\chi^A\nabla^\mu\chi^B
-U(\chi)
\right]
+S_m[g_{\mu\nu},\psi_m],
\tag{GR1}
$$

where $[F]=M^2$, $[\chi^A]=M$, $[K_{AB}]=1$, and $[U]=M^4$. The factor $M_{\mathrm{Pl}}^2$ is included in $F$; it was written separately in equation (37). Metric variation gives


$$
\boxed{
\begin{aligned}
F G_{\mu\nu}
={}&T_{\mu\nu}^{(m)}
+K_{AB}\left(
\nabla_\mu\chi^A\nabla_\nu\chi^B
-\frac12g_{\mu\nu}\nabla_\alpha\chi^A\nabla^\alpha\chi^B
\right)-g_{\mu\nu}U\\
&+\nabla_\mu\nabla_\nu F-g_{\mu\nu}\Box F .
\end{aligned}
}
\tag{GR2}
$$

The scalar equations are

$$
K_{AB}\Box\chi^B
+\Gamma_{ABC}\nabla_\mu\chi^B\nabla^\mu\chi^C
+\frac12F_{,A}R-U_{,A}=0,
\tag{GR3}
$$

with $\Gamma_{ABC}$ the connection of the field-space metric $K_{AB}$. Equations (GR2) and (GR3), together with the matter equations, satisfy the Bianchi identity. Minimally coupled matter obeys $\nabla^\mu T_{\mu\nu}^{(m)}=0$ on shell; internal equal-and-opposite conversion does not create a net matter source. Omitting the derivative-$F$ and scalar-stress terms destroys this closure.

The tensor and scalar no-ghost conditions are

$$
\boxed{
F>0,\qquad
\mathcal K^{E}_{AB}
:=\frac{M_{\mathrm{Pl}}^2}{F}K_{AB}
+\frac{3M_{\mathrm{Pl}}^2}{2F^2}F_{,A}F_{,B}
\succ0 .
}
\tag{GR4}
$$

The GR limit has a stationary background $\chi_0^A$, $F(\chi_0)=M_{\mathrm{Pl}}^2=(8\pi G_N)^{-1}$, negligible derivative terms, and scalar modes that are heavy, weakly coupled, or screened on the scale of the experiment. The locally measured Newton constant also includes scalar exchange unless that condition holds.

For a spatially flat FLRW background, (GR2) becomes

$$
\begin{aligned}
3FH^2&=\rho_m+\frac12K_{AB}\dot\chi^A\dot\chi^B+U-3H\dot F,\\
-2F\dot H&=\rho_m+p_m+K_{AB}\dot\chi^A\dot\chi^B+\ddot F-H\dot F .
\end{aligned}
\tag{GR5}
$$

Thus a cosmological use must solve the scalar background and perturbations, not insert an epoch-dependent $G_{\mathrm{eff}}$ algebraically. The quantity $\alpha_M:=d\ln F/d\ln a$ measures Planck-mass running; the simple $F(\chi)R$ sector keeps the tensor-wave speed equal to the metric light speed.
For the signed composition fraction
$$
s:=\frac{E_Y-E_I}{\rho},
$$
the current Cassi halo-strength ansatz is


$$
\mathcal G_C(E_Y,E_I)
:=\frac{G_{\mathrm{eff}}}{G}
:=s\left[1+(\varphi^6-1)q(\rho,\varepsilon)\right].
\tag{GR6}
$$

A quasistatic scalar-tensor matching would require $F\simeq M_{\mathrm{Pl}}^2/\mathcal G_C$, up to scalar-exchange corrections, and only on a branch where $\mathcal G_C>0$. At the reference equilibrium state it gives $\mathcal G_C\simeq3.73$; along the fixed-composition ray it ranges from $\varphi^{-3}$ at $q=0$ toward $\varphi^3$ as $q\to1$. These are order-unity background changes. The formula is a composite of coarse densities, supplies no independent covariant scalar equation, and becomes inadmissible where $s\le0$ under the direct matching.

For one effectively massless, universally coupled Einstein-frame scalar, define

$$
\alpha_{\mathrm{ST},0}
:=-\frac{M_{\mathrm{Pl}}}{2}
\left.\frac{d\ln F}{d\phi_E}\right|_0 .
$$

The unscreened post-Newtonian result is

$$
\gamma_{\mathrm{PPN}}-1
:=-\frac{2\alpha_{\mathrm{ST},0}^2}{1+\alpha_{\mathrm{ST},0}^2}.
\tag{GR7}
$$

Cassini measured $\gamma_{\mathrm{PPN}}-1=(2.1\pm2.3)\times10^{-5}$. The order-unity astrophysical change in (GR6) and the local fifth-force amplitude in (GR7) are distinct observables. Connecting them requires an explicit mass, weak-coupling, or environmental-screening profile. No such profile, scalar source law, or weak-field matching is currently derived. The river-flow law is likewise a phenomenological Newtonian closure until it follows from (GR1) with a declared coordinate and matter map. The covariant Cassi gravity branch therefore remains **REJECTED** as a completed theory; (GR1)–(GR7) state the conditions for reconsideration.


### 7.5 Radiative and coarse-graining boundaries

For the isolated quartic sector in convention (EFT3), the one-loop weak-coupling beta functions are

$$
\begin{aligned}
16\pi^2\beta_{\lambda_Y}
&=18\lambda_Y^2+\frac12\lambda_{YI}^2,\\
16\pi^2\beta_{\lambda_I}
&=18\lambda_I^2+\frac12\lambda_{YI}^2,\\
16\pi^2\beta_{\lambda_{YI}}
&=4\lambda_{YI}^2
+6\lambda_{YI}(\lambda_Y+\lambda_I).
\end{aligned}
\tag{RG1}
$$

The only real perturbative fixed point of this isolated system is the Gaussian point: the first two beta functions can vanish together only when all three quartics vanish. More importantly, the Cassi surface (EFT5) obeys the linear constraint

$$
\mathcal C_\varphi
:=-2\varphi^2\lambda_Y+2\varphi\lambda_I+\lambda_{YI}=0.
\tag{RG2}
$$

Substitution into (RG1) gives its normal beta function,

$$
\boxed{
16\pi^2\beta_{\mathcal C_\varphi}
=12\lambda_A\left[
(44+20\sqrt5)\lambda_A+(7+3\sqrt5)g_4
\right].
}
\tag{RG3}
$$

For $g_4,\lambda_A\ge0$ with $\lambda_A>0$, this is strictly positive. The flow therefore leaves the $\varphi$-attractor surface immediately. The $\lambda_A=0$ radial ray is invariant but contains no $\varphi$ attractor. Masses, Higgs portals, curvature couplings, and anomalous dimensions add further running and matching terms; restoration requires an explicit symmetry or an independently demonstrated fixed manifold.

The unrestricted operator basis (EFT1) is an ordinary radiatively closed effective field theory when every allowed counterterm is retained. The restricted $\varphi$ relations are **REJECTED** as a radiatively invariant or parameter-fixing microscopic completion. They remain available as boundary conditions at one declared matching scale, with ordinary RG drift away from that scale.

The P1→P2 map must derive all of the following from the same microscopic model:

1. nonnegative coarse densities $E_Y,E_I$;
2. the rank-one conversion direction and rate;
3. the selected $q$-gate dependence;
4. advection, scalar diffusion, and velocity viscosity with their units;
5. fluctuation/noise covariance and cutoff dependence;
6. the reference density and physical time conversion;
7. the domain in which the positivity wedge is invariant.

A successful derivation predicts those quantities together. Fitting the PDE after selecting them is a mesoscopic model calibration.

---

## 8. Operational meanings of the hierarchy

The following definitions state what the architecture can test.

### 8.1 Physical becoming

A system exhibits **physical becoming** over horizon $\Delta$ when internal action-conditioned states represent multiple reachable futures, those states causally change a present committed action, and the action changes the later actual state. The criterion is the mediated intervention in equation (25).

### 8.2 Prospective intelligence

A system exhibits **prospective intelligence** when it satisfies physical becoming and prediction error changes later forecasting or action selection in a way that improves a preregistered vector of viability, work, information, and option-preservation measures across held-out environments. Improvement in one scalar reward alone can be produced by a reactive controller; branch and learning lesions distinguish the richer loop.

### 8.3 Embodied self

An **embodied self** is the slowly maintained, controllable, and re-identifiable organization defined jointly by the body boundary $b$, body state $m$, reserve $\mathcal A$, ordered history $h$, and body-indexed model state. Persistence is tested under perturbation and interruption. The definition carries no claim that the self is a new substance.

### 8.4 Memory

A coordinate is **memory** when it preserves ordered information about past events and changing that retained history, while matching the present observation, changes a later prediction or action. A moving average that only smooths the present signal remains a filter until it passes this causal test.

### 8.5 Attention

A coordinate is **attention** when it reallocates a finite sensing, modeling, or action-resolution budget and that reallocation changes downstream precision or behavior while total cost remains bounded. Static channel gain is a readout convention.

### 8.6 Meaning

A pattern has **operational meaning** for the system when its internal equivalence class is defined by predicted consequences for the system’s reachable actions, viability, and future observations. Two inputs have the same operational meaning over a declared horizon when replacing one with the other leaves the relevant predicted and realized consequence distributions within tolerance. This supplies a testable functional semantics. Phenomenal quality requires a separate bridge.

### 8.7 Agency

A system has **bounded agency** when its internal branch state changes its action among physically available alternatives, with measured work and finite control capacity, and matched interventions establish that the change originates within the modeled boundary rather than the experimenter’s controller.

### 8.8 Access consciousness and phenomenal consciousness

The architecture supplies a candidate criterion for **access consciousness**: selected content becomes available to branch evaluation, global action competition, memory update, and report through a finite attention bottleneck. A content lesion should affect those functions together.

**Phenomenal consciousness**—why or whether such processing is accompanied by subjective experience—remains open. The canonical $q$ diagnostic, the $r=\varphi^{-1}$ pinch relation, a vortex, or a global broadcast supplies no derivation of experience by itself. Any proposed bridge principle requires its own statement, alternatives, and discriminating evidence.

---

## 9. Decisive gates

### 9.1 Exact mathematical gates

| Gate | Criterion | Current verdict |
|---|---|---|
| **PB-M1 coordinate inversion** | equation (3) inverts $(E_Y,E_I)\leftrightarrow(\rho,\varepsilon)$ and reproduces the positivity wedge | **PASS** |
| **PB-M2 conversion modes** | eigenvalues are $0$ and $-(1+\varphi)\gamma_{\mathrm{conv}}$ with conserved left mode $(1,1)$ | **PASS** |
| **PB-M3 gradient embedding** | equation (7) reproduces the selected conversion with $\mathbb R_{\mathrm{TF}}\succeq0$ | **PASS** |
| **PB-M4 contraction** | $D_t\mathcal F_{\mathrm{conv}}\le0$ for $\gamma_{\mathrm{conv}}\ge0$ | **PASS** |
| **PB-M5 simplex preservation** | selected branch/attention law preserves positivity and unit sum | open until the controller law is selected |
| **PB-M6 response poles** | the linearized open-system reduction gives (OS6) and differs from a conservative scalar propagator | **PASS** as a conditional coarse response; microscopic bath matching remains open |

### 9.2 Coarse-graining and causal gates

| Gate | PASS criterion | FAIL/NULL condition |
|---|---|---|
| **PB-C1 closure** | held-out $R_{\mathrm{cl}}$ and discarded-mode dependence lie below frozen bounds | **FAIL** if either bound is exceeded |
| **PB-C2 embodiment** | boundary persists, exchanges through localized ports, repairs with debit, and fails under reserve depletion | **NULL** if a static mask explains the result |
| **PB-C3 memory** | history lesion changes held-out forecast or later steering with present observation matched | **NULL** if behavior is unchanged |
| **PB-C4 branch causality** | $do(\widehat m_\alpha)$ changes $p/\Theta$, committed action, and future $X$ in sequence | **FAIL** if any mediated link is absent |
| **PB-C5 attention** | reallocation changes downstream resolution/behavior under a fixed total budget | **NULL** for static weighting or unlimited gain |
| **PB-C6 debit** | predicted and realized work calibrate and satisfy equations (1), (27), and (28) | unclosed without an instrumented power channel; **FAIL** on ledger violation |
| **PB-C7 learning** | prediction-error history changes later $\vartheta$, prediction, and action under matched current state | **NULL** if the update has no later causal effect |
| **PB-C8 generalization** | the full loop improves the preregistered outcome vector in held-out environments and beats reactive/no-shadow controls | **FAIL** if gains vanish outside the training distribution |

The prospective-steering closure may be **ADOPT**ed only after PB-C1, PB-C4, and PB-C6 pass, with PB-C2, PB-C3, PB-C5, PB-C7, and PB-C8 passing for the corresponding embodiment, memory, attention, learning, and intelligence claims. PB-C1 or PB-C4 failure yields **REJECT** for the proposed agent-level closure.

### 9.3 Physical completion gates

| Gate | Requirement | Current verdict |
|---|---|---|
| **PB-P1 quantum EFT** | dimensions, counterterms, unitarity domain, stable vacuum, and protecting symmetry/fixed manifold | **FAIL** as a closed microscopic unification; effective ansatz remains available |
| **PB-P2 covariant gravity** | scalar equations, Bianchi-compatible metric equation, $F>0$, weak-field limit, and screening | equations defined; current composite map **FAILS** completion because its covariant source and screening profile are absent |
| **PB-P3 micro-to-PDE** | controlled derivation of the two-density PDE, $q$ gate, transport, noise, and physical units | finite carrier and shared-loop realizations **PASS** conditionally; physical P1 state map, coefficients, and units remain open |
| **PB-P4 distinctive observation** | a preregistered result that differs from GR+SM plus an ordinary auxiliary field and survives full controls | open |

---

## 10. Relation to the present field-experience record

The field-experience waves establish real properties of driven and freely evolved two-density fields: exact read-only parity, compact-support perturbations, conserved density under the stated kicks, measurable receiver responses, and several null or contradictory route/timing hypotheses. Wave 6 finds a detectable receiver field-space response after an externally supplied pulse, while the registered delayed-diagonal timing and label-specific timing hypotheses are contradicted.

Those probes exercise actual-state response under experimenter-supplied sources and readouts. They do not yet contain a maintained body, internal shadow branches, endogenous commitment, a work-debited action port, or prediction-error learning. Their contribution to this hierarchy is the substrate and measurement discipline. PB-C1 through PB-C8 require a new preregistered closed-loop experiment.

The first decisive demonstration should use a minimal **Hungry Detour** environment:

1. a maintained field body with a measured reserve;
2. two locally similar routes, one ending in a hidden dead end or damaging region;
3. boundary-localized sensing that cannot directly reveal the full route;
4. at least two internal action-conditioned shadows;
5. branch scores that debit forecast and action work;
6. commitment that acts through the body’s physical effector port;
7. prediction error that changes a later choice;
8. no-shadow, shuffled-shadow, zero-reserve, and reactive baselines.

Success requires the full mediated chain, a closed energy ledger, and generalization to a held-out route geometry. A reactive potential that reaches the goal does not pass the shadow-causality gate.

---

## 11. Current verdict

The theory closes one exact mathematical bridge and one architectural hierarchy:

- **Derived conditional:** the canonical selected rank-one conversion is a positive-semidefinite gradient flow in $(E_Y,E_I)$, conserving $\rho$ and contracting $\varepsilon$.
- **Derived conditional:** a finite shared-loop carrier law projects exactly
  to the canonical PDE, with an explicit internal spectrum and
  coherence-sensitive affine-bubble projection.
- **Derived within the completion ansatz:** the positive coherence fibre
  contains the canonical density diameter and projective boundary, while the
  minimal positivity-preserving two-jump conversion lift reproduces canonical
  populations and gives $\gamma_c=\gamma_\varepsilon/2$. At finite density
  with $\lambda>0$, its undriven nonzero transverse coherence decays.
- **Defined:** actual state, body readouts, gate readouts, history, shadow trajectories, branch allocation, attention, commitment, resource debit, learning, and their causal order occupy typed slots in one differential-algebraic state.
- **Hypothesized:** these slots form an autonomous field-native prospective controller after coarse-graining.
- **Open:** a symmetry-protected microscopic completion, covariant screened gravity, the physical P1-to-carrier state map, physical unit matching, maintained embodiment, agent-level causal gates, and a distinctive physical prediction validated against controls.
- **Outside the derived scope:** phenomenal consciousness and a universal metaphysical identity between experience and any single Cassi diagnostic.

The compact physical-becoming equation is therefore a research contract. It says exactly what must be built, conserved, measured, lesioned, and falsified for possible flow to become part of present flow.

## References

- `README.md` §The field-AGI program—causal definition of prospective intelligence and the minimal loop.
- `foundations/cassi-first-principles.md` §§1–2—canonical $E_Y,E_I,\rho,\varepsilon,q$ state and selected conversion.
- `foundations/cassi-theory-reference.md` §2—compact canonical equations and diagnostic boundaries.
- `foundations/qi-flow-double-helix.md` §§1–2—exact density/amplitude diagnostic lifts and conditional channel construction.
- `foundations/loop-to-bubble-projection-theorem.md`—conditional
  shared-support carrier reduction, coherence map, and internal spectral gap.
- `foundations/geometric-manifold-completion.md`—stratified positive coherence
  fibre, two-rail scale graph, exact canonical reduction, and conditional
  positivity-preserving conversion lift.
- `foundations/yin-yang-qi-dynamical-geometry.md`—integrated open-system
  matrix balance and finite-density coherence-support boundary.
- `computations/dynamical_geometry_closure_report.md`—DG1–DG7 analytic and
  deterministic closure receipt.
- `foundations/unified-lagrangian.md`—optional microscopic action assembly and its dimensional/covariant blockers.
- `foundations/dimensionful-constants-status.md`—physical-unit and external-constant boundaries.
- `computations/verify_physical_becoming_reduction.py`—symbolic checks of the exact conversion, mobility, covariance null mode, response eigenmodes, reference-state $\Gamma_0=\lambda/3$, physical fixed-$\rho$ wedge, and conditional FDT normalization.
- `computations/verify_physical_becoming_eft.py`—symbolic checks of the two-singlet matching surface, conditional canonical-vacuum Hessian modes and masses, vacuum brackets, and one-loop RG obstruction.
- `computations/verify_physical_becoming_gravity.py`—reference-state coupling, fixed-ray limits, coordinate-independence, and unscreened PPN-bound checks.
- B. Bertotti, L. Iess, and P. Tortora, “A test of general relativity using radio links with the Cassini spacecraft,” *Nature* **425**, 374–376 (2003), doi:10.1038/nature01997—Solar-System $\gamma_{\mathrm{PPN}}$ measurement.
- C. Burrage and J. Sakstein, “Tests of chameleon gravity,” *Living Reviews in Relativity* **21**, 1 (2018), doi:10.1007/s41114-018-0011-x—environmental-screening review.
- H. Mori, “Transport, Collective Motion, and Brownian Motion,” *Progress of Theoretical Physics* **33**, 423 (1965), doi:10.1143/PTP.33.423—projection-operator reduction and memory kernels.
- P. C. Martin, E. D. Siggia, and H. A. Rose, “Statistical Dynamics of Classical Systems,” *Physical Review A* **8**, 423 (1973), doi:10.1103/PhysRevA.8.423—response-field functional for stochastic dynamics.
- H. C. Öttinger, *Beyond Equilibrium Thermodynamics* (Wiley, 2005)—GENERIC-style reversible/dissipative structure.
- M. E. Machacek and M. T. Vaughn, “Two-Loop Renormalization Group Equations in a General Quantum Field Theory: (III) Scalar Quartic Couplings,” *Nuclear Physics B* **249**, 70 (1985), doi:10.1016/0550-3213(85)90040-9—one-loop scalar quartic beta functions.
- N. D. Birrell and P. C. W. Davies, *Quantum Fields in Curved Space* (Cambridge University Press, 1982)—curved-background counterterms.
- `field-experience/source-only-fieldspace-timing-wave-6-report.md`—current source-only field-space response and contradicted timing hypothesis.
- `field-experience/probe-outcome-ledger.md`—registered field-experience outcomes.
- `consciousness/consciousness-from-phi.md`—Hypothesized consciousness mapping and null pinch-correlation result.
- `open-questions-cassi-answers.md` §M1–M2—consciousness and mind-brain questions.
