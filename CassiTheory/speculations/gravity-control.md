# Gravity Control: Conditional Engineering Requirements

## Status: Speculative—September 2026

## Abstract

Cassi currently supplies a canonical two-fluid state, a bounded coherence
diagnostic, an optional gravitational coupling-magnitude expression, and
separate candidate gravity actions. These ingredients define questions for a
gravity-control program; they do not yet define a device. A physical proposal
requires a map from controllable matter to the Yang/Yin state, a covariant
source and response law, conservation and stability proofs, and a measured
laboratory contrast.

The strongest available weak-field boundary is the Quantum Galileo
Interferometer. Its ideal phase follows from the conditional centre-of-mass
Schrödinger sector after the Earth potential is supplied. The same derivation
shows that local acceleration calibration absorbs a uniform source or response
rescaling. A Cassi-specific test must therefore compare independently
calibrated preparations or sources under a frozen atomic state map. This
document limits gravity-control speculation to that measurable boundary.

## 1. Available Cassi structure

### 1.1 Canonical state and attractor line

The local two-fluid variables are

$$
\rho=E_Y+E_I,\qquad
\pi=E_Y-E_I,\qquad
\varepsilon=E_Y-\varphi E_I.
$$

With physical reference density $\rho_\star$, the canonical coherence
diagnostic is

$$
q=
\frac{\rho^2}
{\rho^2+\varphi^{-2}\rho_\star^2+\varepsilon^2}.
$$

The composition attractor is the full line $\varepsilon=0$, on which

$$
\frac{\pi}{\rho}=\varphi^{-3}.
$$

The diagnostic $q$ still varies with density along that line. The dilute
endpoint has $q\to0$. In the registered dimensionless reference convention
$\rho_\star=1$ and $\rho=\varphi$,

$$
q_{\mathrm{eq}}=\frac{\varphi^2}{3}\approx0.872678.
$$

No current projection assigns ordinary laboratory matter or the ambient Solar
System a value of $\rho/\rho_\star$, $E_Y$, $E_I$, or $q$.

### 1.2 Coupling-magnitude diagnostic

The optional Qi-gravity expression is

$$
\mathcal G_C(E_Y,E_I)
:=
\frac{\pi}{\rho}
\left[1+(\varphi^6-1)q\right].
$$

Along the composition attractor it approaches $\varphi^{-3}$ at the dilute
endpoint, equals

$$
\mathcal G_C=\frac{5\sqrt5}{3}\approx3.72678
$$

at the registered reference-density point, and approaches $\varphi^3$ in the
high-density same-composition limit. The often-quoted factor $\varphi^6$ is
the fixed-composition ratio between the high- and low-$q$ endpoints. It is not
a canonical free-$q$ device range.

The expression is a dimensionless magnitude diagnostic. It supplies neither
an attractive force sign nor a metric, source profile, screening law, atomic
response, or measured normalization to $G_N$. The canonical optional
$+\pi\nabla\Phi$ force branch is outward for $\Phi=-GM/r$ and positive $\pi$.
An attractive Newtonian or metric interpretation therefore belongs to a
separate Hypothesized closure.

## 2. Three distinct gravity hypotheses

### 2.1 Universal metric or scalar-tensor source branch

The covariant candidate has the form

$$
S=
\int d^4x\sqrt{-g}
\left[
\frac12F(\chi)R
-\frac12K_{AB}(\chi)
\nabla_\mu\chi^A\nabla^\mu\chi^B
-U(\chi)
\right]
+S_m[g,\psi_m].
$$

Universal Jordan-frame matter coupling gives all matter one metric. A varying
$F$ can alter the sourced geometry and add scalar exchange, subject to
screening and post-Newtonian bounds. It does not by itself assign
body-dependent gravitational-to-inertial response. Engineering this branch
would mean controlling a declared $\chi$ source while retaining the metric,
constraint, and matter equations.

### 2.2 Direct response-charge branch

A separate phenomenological completion may define

$$
r_B:=\frac{m_{g,B}}{m_{i,B}},
\qquad
\widehat{\mathcal G}_B(X_B\mid X_\star)
:=\frac{\mathcal G_C(X_B)}{\mathcal G_C(X_\star)},
\qquad
r_B\stackrel{\mathrm{hyp}}{=}\widehat{\mathcal G}_B.
$$

Here $X_B$ is a microscopic Cassi state assigned to body or preparation $B$,
and $X_\star$ is a laboratory reference. This normalization keeps measured
$G_N$ separate from the internal diagnostic. The mapping remains
Hypothesized: no current carrier or atomic calculation supplies $X_B$.

### 2.3 Common-lapse branch

The candidate physical-time relation is

$$
\frac{d\tau_{\mathrm{phys}}(x)}{d\tau_\star}
=
\frac{1-q(x)}{1-q_\star}.
$$

A constant common lapse produces no phase anomaly when an interferometer
duration is expressed in that same physical clock. A measurable test requires
worldlines sampling different lapse values, a full variational constraint
linking lapse and $q$, and independent clock sectors. Applying $(1-q)$ to one
equation while leaving the other sectors unchanged defines a gate model rather
than a common spacetime lapse.

These three branches are alternatives until a complete action relates them.
A scalar-tensor source change, a direct body charge, and a clock lapse cannot
be substituted for one another.

## 3. Quantum free-fall boundary

For a supplied uniform potential $V_g=m_ggz$, the ideal closed ballistic phase
is

$$
\Delta\phi
=-\frac{m_g^2g^2T^3}{3\hbar m_i}.
$$

Universal response, $m_g=m_i=m$, gives the observed standard form

$$
\Delta\phi_{\mathrm{EP}}
=-\frac{mg^2T^3}{3\hbar}.
$$

The ballistic acceleration is $g_b=(m_g/m_i)g$, so the phase may also be
written

$$
\Delta\phi
=-\frac{m_i g_b^2T^3}{3\hbar}.
$$

The same-arm phase and acceleration therefore contain no separate measurement
of source field $g$ and response ratio $m_g/m_i$. This identifiability boundary
rules out extracting a numerical Cassi $q$ from a residual of the standard
apparatus fit.

If the ballistic and held preparations have response ratios $r_b$ and $r_r$
to one source, the ideal differential observable is

$$
\mathcal R_{br}
:=
\sqrt{\frac{-3\hbar\Delta\phi_b}{m_iT^3a_h^2}}
=
\left|\frac{r_b}{r_r}\right|,
$$

where $a_h=r_rg$ is the independently calibrated holding acceleration. A
future direct-charge proposal must predict $\mathcal R_{br}$ before examining
the phase data and must retain finite-pulse, magnetic, interaction,
wave-packet, and three-dimensional corrections in the joint apparatus model.

The published $^{87}\mathrm{Rb}$ result
([doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045);
[arXiv:2502.14535](https://arxiv.org/abs/2502.14535)) establishes this
weak-field quantum correspondence target. It contains no prepared
gravitational-field superposition and no resolved Cassi state contrast.

## 4. Engineering prerequisites

A gravity-control proposal becomes calculable only when it supplies all of the
following:

1. **Matter-state map.** A normalized map from material composition, internal
   state, density, interactions, and environment to
   $X_B=(E_Y,E_I,\rho_\star,\text{carrier data})$.
2. **Gravity action.** One selected metric, scalar-tensor, or direct-charge
   branch with an attractive weak-field limit and a conserved total stress
   tensor.
3. **Source solution.** Boundary data and equations that determine the field
   generated by a laboratory source, including scalar exchange or screening.
4. **Control law.** A demonstrated physical operation that changes the mapped
   state by a measured amount without assuming the desired gravitational
   effect.
5. **Energy and momentum ledger.** Actuator work, field energy, recoil, heat,
   radiation, and relaxation included in one closed accounting.
6. **Stability and causality.** Positive kinetic structure, bounded energy,
   well-posed evolution, and compatibility with equivalence-principle,
   inverse-square, post-Newtonian, and clock constraints.
7. **Frozen observable.** A preregistered differential prediction evaluated
   with the complete apparatus model and ordinary systematic controls.

The current framework provides none of the numerical inputs required for a
device mass, power, size, thrust, artificial-gravity field, inertial response,
or black-hole threshold. Cascade rung labels and fitted galactic profiles do
not supply those missing laboratory quantities.

## 5. Status of proposed outcomes

| Proposed outcome | Current status | Missing result |
|---|---|---|
| Weight or free-fall modulation | Hypothesized | Atomic state map plus a response law predicting $\mathcal R_{br}\neq1$ |
| Inertial damping or inertial-mass change | Unsupported by the present gravity expressions | Dynamical matter action whose kinetic coefficient changes consistently with momentum and energy conservation |
| Artificial gravity from a coherent material | Speculative | Source equation, controllable field state, attractive branch, and measured local geometry |
| Propulsion without reaction mass | Unsupported | Closed stress-energy and momentum flux demonstrating the compensating recoil channel |
| Solar-System ambient-$q$ baseline | Undetermined | Physical $\rho_\star$ and a source/environment solution |
| SPARC profile as a device design | Unsupported | Independent evidence that the fitted galactic profile is a controllable Cassi field rather than a phenomenological fit |
| Black-hole control | Unsupported | Covariant horizon solution and a verified interacting quantum completion |

The table is a boundary on inference. It leaves the hypotheses available for
future calculation while preventing a constitutive diagnostic from being
treated as an implemented actuator.

## 6. Smallest decisive program

The shortest empirical route is:

1. derive one atomic or mesoscopic $X_B$ map without fitting to gravity data;
2. select one gravity branch and calculate its source and test responses;
3. freeze a nonzero differential prediction for two preparations;
4. reverse which preparation is ballistic and which is held;
5. repeat with a second isotope or species while measuring trajectories and
   phases jointly;
6. compare the complete Cassi and universal-metric apparatus models under one
   declared stopping rule.

A null differential response rejects the selected state-to-response map at the
registered sensitivity. A nonzero result becomes evidence for that map only
after magnetic, collisional, wave-packet, source-gradient, and clock
systematics are excluded. Either outcome is more informative than an
unscaled device scenario.

## References

- `foundations/quantum-free-fall-correspondence.md`—ideal action, gauge phase, source/test separation, Qi normalization, and common-lapse boundary.
- `foundations/physical-becoming-hierarchy.md` §7.4—covariant scalar-tensor completion and local weak-field constraints.
- `foundations/matter-completion-boundary.md`—constant-$G_N$ closed-action gravity boundary.
- `foundations/unified-lagrangian.md` §1.7—candidate common-lapse action criterion and CT-2.
- `foundations/xi-derivation.md`—conditional derivation of $\xi=\varphi^6$ and reference-state normalization.
- `predictions/falsifiable-predictions.md`—QGI-1 and CT-2 experimental contracts.
- Y. Margalit *et al.*, “Observation of the quantum phase of free fall and the consistency with the equivalence principle,” *Science Advances* (2026), [doi:10.1126/sciadv.aec8045](https://doi.org/10.1126/sciadv.aec8045); accessible derivation at [arXiv:2502.14535](https://arxiv.org/abs/2502.14535).
