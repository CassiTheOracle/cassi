# Rotation and Interscale Stress: Design Outline

## Status: Design outline—September 2026

## Purpose

This outline organizes a conservative path from large-scale structure formation to rotating matter-like objects. It addresses two linked questions:

1. How can a locally nonrotating cloud acquire coherent rotation without creating angular momentum from nothing?
2. Can a stress-derived spatial force be the dynamical expression of attenuation or transport across Cassi scales?

The short answers are:

- **Local rotation can arise through torque exchange.** The most immediate mechanism is ordinary tidal torque from structure outside the chosen cloud. A future Qi stress can also transport angular momentum, but it must carry an equal and opposite reaction in the field, another scale, or the boundary.
- **Attenuation can modulate or represent a stress-derived force only after the attenuated quantity is identified.** Attenuation alone is a scalar survival factor, not a force or a source of handedness. A force requires a spatially directed current, stress gradient, mixed space–scale curvature, or boundary flux.

This is not an adopted field law and not an experiment preregistration. Any probe derived from it requires a frozen statistic, controls, decision rule, and stopping rule before execution.

## 1. Present physical boundary

### 1.1 Angular momentum cannot appear in a closed symmetric system

For an isolated system with rotationally invariant dynamics,

$$
\frac{d\mathbf L_{\mathrm{total}}}{dt}=0.
$$

A perfectly symmetric, exactly nonrotating cloud cannot acquire nonzero **total** angular momentum from an internal scalar force. A local cloud may nevertheless gain angular momentum if its environment, a field sector, another scale, or a boundary receives the opposite amount.

This distinction is central:

- **global creation of angular momentum:** prohibited by the intended conservative model;
- **local acquisition of angular momentum:** expected when the subsystem is not closed;
- **spontaneous choice of rotation axis:** possible only through a perturbation or instability, with compensating angular momentum elsewhere;
- **numerical asymmetry:** useful as a seed only if the measured torque and full ledger explain the result.

### 1.2 Current merging stores rotation but does not create it

`CassiCosmos/compute/cassi_particle_merge.glsl` conserves pair linear momentum and transfers pair orbital angular momentum into the survivor’s `spin` accumulator:

$$
\Delta\mathbf S
=\mu\,\mathbf r_{12}\times\mathbf v_{12}+\mathbf S_{\mathrm{infall}}.
$$

This is the pair’s **internal angular momentum about its center of mass**, not its entire angular momentum about an arbitrary origin. Using unwrapped coordinates and a consistent pair-separation convention,

$$
\mathbf L_{\mathrm{origin}}
=
\mathbf R_{\mathrm{COM}}\times\mathbf P_{\mathrm{COM}}
+
\mu\,\mathbf r_{12}\times\mathbf v_{12}
+
\mathbf S_1+\mathbf S_2.
$$

After a merge, the center-of-mass orbital term remains in the survivor’s resolved position and momentum, while the relative-orbit term and infaller spin enter the internal accumulator. A conservation check must compare the sum of resolved center-of-mass orbit and internal spin before and after the merge; comparing `spin` alone with origin-frame angular momentum would be incorrect. In a periodic domain, that comparison requires one consistent unwrapped local frame because raw wrapped coordinates can jump across the boundary.

That accumulator currently participates in merge eligibility and virial stopping. It does not feed particle force, particle velocity, resolved orientation, cloud rotation, or a rotating rendered object. Merging therefore performs a coarse-graining operation:

$$
\mathbf L_{\mathrm{resolved\ orbit}}
\longrightarrow
\mathbf S_{\mathrm{hidden\ merge}},
$$

but it cannot turn a zero-angular-momentum cloud into a rotating one.

### 1.3 Current Qi state is not yet a conserved three-vector momentum field

The live engine has several velocity-like quantities, but they do not yet define one conserved Qi momentum current:

- In the default grid path, `FieldVel.xyz` is written as approximately $(\partial_t E_Y,\partial_t E_I,0)$, not as a material three-velocity.
- In CassiFI mode, `FieldVel.xyz` can hold a bounded embodied medium-flow command, but there is no accompanying conserved spatial momentum or stress law.
- In the boxless site path, `flow_at` repeats the scalar $(\pi_Y+\pi_I)/\rho$ along all three spatial axes. It is a steering proxy, not a directionally resolved vector current.
- The coherence observable $q$ is a scalar and cannot by itself carry angular momentum.
- The local Yang/Yin conversion operator relaxes an internal density ratio; it is not a spatial rotation generator.

A genuine Qi-mediated rotation mechanism therefore needs an explicit vector momentum density, stress tensor, or equivalent geometric current before it is coupled to particles.

## 2. Working hierarchy of rotation

The least speculative hierarchy is:

```text
large scales        external matter/Qi structure supplies tidal torque
        ↓
intermediate scales a vector Qi current or stress transports circulation
        ↓
small scales        collapse and merging store resolved orbital L as object spin
        ↓
resolved objects    spin controls orientation, internal rotation, or subgrid dynamics
```

The stages have different jobs:

1. **Acquire:** tidal fields generate local angular momentum by exchange with the environment.
2. **Transport:** a field momentum/stress sector moves that angular momentum through space and possibly through scale.
3. **Concentrate:** collapse turns distributed orbital motion into compact rotation.
4. **Store:** merging moves unresolved orbital angular momentum into an internal spin state.
5. **Resolve:** object dynamics or rendering make stored spin physically observable without feeding it back twice.

The first stage can be tested using existing gravity before inventing a new Qi law. The later stages should be added only where the ledger shows a missing transport channel.

## 3. Required angular-momentum ledger

Every future rotation probe should close an explicit ledger rather than inspecting particle swirl alone:

$$
\mathbf L_{\mathrm{total}}
=
\mathbf L_{\mathrm{particle\ orbit}}
+
\mathbf L_{\mathrm{Qi\ orbit}}
+
\mathbf S_{\mathrm{Qi\ intrinsic}}
+
\mathbf S_{\mathrm{merge/object}}
+
\mathbf L_{\mathrm{boundary/reservoir}}.
$$

A practical local-domain form is

$$
\mathbf L_{\Omega}
=
\sum_{a\in\Omega}
(\mathbf r_a-\mathbf r_\Omega)\times m_a(\mathbf v_a-\mathbf v_\Omega)
+
\int_{\Omega}(\mathbf r-\mathbf r_\Omega)\times\mathbf p_Q\,dV
+
\int_{\Omega}\mathbf s_Q\,dV
+
\sum_{a\in\Omega}\mathbf S_a.
$$

Here $\mathbf p_Q$ and $\mathbf s_Q$ are proposed Qi orbital-momentum and intrinsic-spin densities; they do not yet exist as authoritative Godot state. The boundary/reservoir term is mandatory whenever the observed domain excludes the environment or some scales.

Required diagnostics are:

- particle orbital $\mathbf L$ about both the global and local centers of mass;
- merge/object spin $\sum\mathbf S_a$;
- field orbital and intrinsic contributions once defined;
- angular-momentum flux through spatial and scale boundaries;
- torque decomposed by source;
- vorticity $\boldsymbol\omega=\nabla\times\mathbf u$;
- circulation $\Gamma=\oint\mathbf u\cdot d\boldsymbol\ell$;
- tangential velocity $v_\phi(R)$ and rotation-axis stability;
- closure error in both linear and angular momentum.

## 4. Candidate rotation mechanisms

### 4.1 Baseline mechanism: external tidal torque

For a cloud occupying $\Omega$, separate acceleration from sources inside and outside the cloud. The external torque is

$$
\boldsymbol\tau_{\mathrm{ext},\Omega}
=
\sum_{a\in\Omega}
(\mathbf r_a-\mathbf r_\Omega)
\times
m_a\,\mathbf a_a^{\mathrm{outside}}.
$$

Internal central pair forces cancel in the total torque of the isolated set. External structure need not be globally rotating: a misalignment between the cloud inertia tensor and the external tidal tensor is sufficient to torque the cloud. The environment acquires the compensating angular momentum.

This is the first mechanism to measure because it needs no new state variable and directly matches cosmological structure formation. A symmetric spherical cloud in a symmetric environment is the null. A triaxial cloud in a deliberately misaligned external tidal field is the positive geometry.

### 4.2 Proposed Qi mechanism: vector momentum and stress

A conservative Qi transport sector would introduce a spatial momentum density

$$
\mathbf p_Q=\rho_Q\mathbf u
$$

and a momentum balance such as

$$
\partial_t p_{Q,i}+\partial_j T^Q_{ij}
=f_i^{\mathrm{matter}\rightarrow Q}+f_i^{\mathrm{scale}}.
$$

The particle equation must receive the opposite exchange force:

$$
\mathbf f^{Q\rightarrow\mathrm{matter}}
=-\mathbf f^{\mathrm{matter}\rightarrow Q}.
$$

A reference-only candidate discussed in the theory work has a force proportional to a scalar coefficient $\Pi$ times $\nabla\Phi$. Its curl contains

$$
\nabla\times(\Pi\nabla\Phi)
=
\nabla\Pi\times\nabla\Phi.
$$

Misaligned gradients can therefore source vorticity even though $\nabla\Phi$ alone is curl-free. This is a useful mechanism to investigate, but it is **Hypothesized** and must not be identified with the current site variables $\pi_Y$ and $\pi_I$ without a derivation from one declared action.

### 4.3 Mechanisms that are not sufficient

The following may gate or weight a real torque, but they cannot generate rotation on their own:

- scalar coherence $q$;
- local rank-one Yang/Yin conversion;
- isotropic damping or uniform attenuation;
- central gravity inside a closed particle set;
- merge accumulation of angular momentum that was not already present;
- copying one scalar flow value into the $x$, $y$, and $z$ components;
- visual particle swirl without a closed momentum ledger.

## 5. Relation between interscale attenuation and stress-derived force

### 5.1 The precise connection

Yes, a stress-derived force can be related to attenuation across scales, but the relation is conditional. The clean formulation introduces a scale coordinate

$$
\mathfrak s=\log_\varphi(\ell/\ell_*),
$$

and treats spatial momentum as a quantity that can flow both through physical space and through scale:

$$
\partial_t p_i
+\partial_j T_{ij}
+\partial_{\mathfrak s} T_{i\mathfrak s}
=f_i^{\mathrm{ext}}.
$$

$T_{ij}$ is spatial stress. $T_{i\mathfrak s}$ is the flux of the $i$th component of spatial momentum along the scale direction. Integrating over an observed scale window $[\mathfrak s_1,\mathfrak s_2]$ gives

$$
\partial_t\int_{\mathfrak s_1}^{\mathfrak s_2}p_i\,d\mathfrak s
+\partial_j\int_{\mathfrak s_1}^{\mathfrak s_2}T_{ij}\,d\mathfrak s
=
\int_{\mathfrak s_1}^{\mathfrak s_2}f_i^{\mathrm{ext}}\,d\mathfrak s
-\left[T_{i\mathfrak s}\right]_{\mathfrak s_1}^{\mathfrak s_2}.
$$

The apparent scale-derived force on the resolved sector is therefore

$$
f_i^{\mathrm{scale}}
=-\left[T_{i\mathfrak s}\right]_{\mathfrak s_1}^{\mathfrak s_2}.
$$

In this interpretation, attenuation is not destruction. It is momentum leaving the resolved scale window and entering another scale or reservoir. The enlarged closed system still conserves momentum.

A complementary geometric candidate already present in the CassiTheory manifold work has the full static force contribution

$$
f_i
=
\hbar\mathcal I_jG_{ij}
+
\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}.
$$

This outline intentionally isolates the mixed space–scale term

$$
f_i^{\mathrm{mix}}
=\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}.
$$

Here $\mathcal I_j$ is the spatial gauge-current component, $\mathcal I_{\mathfrak s}$ is the gauge-weighted scale-current source, $G_{ij}$ is spatial gauge curvature, and $G_{i\mathfrak s}$ is mixed space–scale curvature. The theory separately defines a density-flow current $J_{\mathfrak s}$; neither that density current nor the proposed momentum flux $T_{i\mathfrak s}$ is interchangeable with $\mathcal I_{\mathfrak s}$ without the declared gauge normalization and equations of motion. The mixed term vanishes if either $\mathcal I_{\mathfrak s}$ or the mixed curvature vanishes. It is one contribution to the force, conditional on the declared extended action, and is not yet a live CassiCosmos law.

### 5.2 Where the attenuation factor enters

The existing cascade relation is

$$
D_{m\rightarrow n}=\prod_{r=m}^{n-1}d_r,
$$

with the uniform family $d_r=\varphi^{-1}$ giving

$$
D_{m\rightarrow n}=\varphi^{-(n-m)}.
$$

That formula does not specify what physical quantity is attenuated. Four distinct cases must not be conflated:

| Attenuated quantity | Conditional scaling of stress or force | Interpretation |
|---|---:|---|
| gauge-weighted scale current $\mathcal I_{\mathfrak s}$ | $f^{\mathrm{mix}}\propto D$ if $G_{i\mathfrak s}$ is fixed | less current reaches the observed scale |
| field amplitude $A$ | quadratic stress commonly scales as $D^2$ | the force is bilinear or quadratic in the field |
| energy, momentum flux, or stress itself | force may scale as $D$ | $D$ was defined on an already quadratic observable |
| detector/readout signal only | no dynamical force follows | attenuation changes observability, not mechanics |

For the current-attenuation branch,

$$
\mathcal I_{\mathfrak s}(n)
=D_{m\rightarrow n}\mathcal I_{\mathfrak s}(m)
$$

would imply, only while holding the geometry fixed,

$$
f_i^{\mathrm{mix}}(n)
=
\hbar D_{m\rightarrow n}
\mathcal I_{\mathfrak s}(m)G_{i\mathfrak s}(n).
$$

A continuous reduced description would be

$$
\partial_{\mathfrak s}\mathcal I_{\mathfrak s}
=-\alpha(\mathfrak s)\mathcal I_{\mathfrak s},
\qquad
D_{m\rightarrow n}
=
\exp\left[-\int_{\mathfrak s_m}^{\mathfrak s_n}\alpha(\mathfrak s)\,d\mathfrak s\right].
$$

The apparent loss term requires a destination in the full theory. Without that destination it is an open-system damping model, not a conservative derivation.

### 5.3 Attenuation can shape torque but cannot supply handedness

The scale-boundary contribution to the angular-momentum balance is

$$
\boldsymbol\tau_{\Omega}^{\mathrm{scale}}
=
-\left[
\int_{\Omega}
(\mathbf r-\mathbf r_\Omega)
\times\mathbf T_{\cdot\mathfrak s}\,dV
\right]_{\mathfrak s_1}^{\mathfrak s_2}.
$$

This provides the direct relation between interscale momentum transport and torque. However:

- a uniform scalar $D$ cannot select an axis or a sign of rotation;
- isotropic attenuation can reduce or modulate an already directed stress response, but it cannot create vorticity from exact symmetry; apparent amplification requires a change in geometry or coupling rather than a true attenuation factor alone;
- local torque requires anisotropic stress, mixed curvature, misaligned gradients, an antisymmetric stress component, or a boundary flux with angular structure;
- if $T_{ij}$ is symmetric and there is no intrinsic spin current, internal stress cannot change the global angular momentum of a closed domain;
- if an antisymmetric stress is admitted, its exchange with intrinsic field spin must appear explicitly in the ledger.

The strongest defensible hypothesis is therefore:

> **Attenuation is a scale-transfer weight or the reduced signature of unresolved momentum flux. Mixed space–scale stress converts that directed flux into a spatial force. Geometry supplies the direction and torque; attenuation controls how much of the current or stress survives between scales.**

## 6. Hypothesis branches to keep separate

1. **Readout-only null:** $D$ attenuates an observable signal; particle and field dynamics are unchanged.
2. **Current branch:** $D$ attenuates $\mathcal I_{\mathfrak s}$; mixed-curvature force scales linearly with $D$ at fixed $G_{i\mathfrak s}$.
3. **Amplitude branch:** $D$ attenuates a field amplitude; quadratic stress scales as $D^2$.
4. **Flux branch:** $D$ describes resolved-to-unresolved momentum transport; the force is the divergence or scale-boundary value of $T_{i\mathfrak s}$.
5. **Geometry branch:** attenuation co-varies with $G_{i\mathfrak s}$ rather than multiplying a fixed geometry; no simple $D$ or $D^2$ law follows.

These branches need distinct controls. Choosing one only because it fits a rotation curve would not identify the mechanism.

## 7. Implementation sequence

### Stage A — Measure the existing tidal baseline

- Keep merging off while torque is acquired.
- Define a local cloud and a separate external environment.
- Decompose internal and external gravitational acceleration.
- Measure $\boldsymbol\tau_{\mathrm{ext},\Omega}$ and compare $\Delta\mathbf L_\Omega$ with its time integral.
- Confirm the opposite angular-momentum change in the environment.
- Use symmetric, aligned, misaligned, and mirror-reflected geometries.

**Purpose:** determine how much rotation already follows from existing conservative gravity.

### Stage B — Build a standalone vector-Qi reference

- Define one three-vector Qi momentum density and its units.
- Derive its stress and exchange force from one declared action or Hamiltonian.
- Keep it separate from default `FieldVel`, the CassiFI command flow, and scalar site momenta.
- Verify momentum conservation, vorticity production, circulation transport, and spatial boundary flux before particle coupling.
- Prefer a small reference solver over a production GPU path until the conservation law is settled.

**Purpose:** establish whether the proposed field sector has a real rotation-carrying degree of freedom.

### Stage C — Add a minimal scale dimension in the reference model

- Use a small explicit set of scale bins rather than a full four-dimensional production grid.
- Represent the density current $J_{\mathfrak s}$, gauge-weighted source $\mathcal I_{\mathfrak s}$, or momentum flux $T_{i\mathfrak s}$ explicitly, without treating them as interchangeable.
- Make both scale boundaries observable.
- Compare the readout-only, current, amplitude, and flux branches.
- Require the receiving scale or reservoir to account for every apparent attenuation loss.

**Purpose:** decide what the cascade factor attenuates and whether a stress-derived force follows.

### Stage D — Couple Qi stress to matter conservatively

- Deposit the matter-to-field force and apply its exact negative to particles.
- Track matter, Qi, scale-reservoir, and boundary momentum separately.
- Add the feature behind a default-off toggle.
- Preserve the default CassiCosmos battery bit-identically while the feature is off.
- Do not tune the coupling against galaxy rotation before the conservation and null checks pass.

**Purpose:** test whether Qi transports or redistributes angular momentum without manufacturing it.

### Stage E — Resolve compact-object spin

- Keep merge spin as an internal angular-momentum state.
- Give compact objects a resolved orientation and moment-of-inertia model only after the torque ledger is stable.
- Convert between orbital and internal spin once, with no duplicate feedback.
- Decide separately whether spin affects rendering, quadrupole forces, internal cloud rotation, or later matter structure.

**Purpose:** make conserved subgrid rotation observable and dynamically useful.

## 8. Verification outline

Each experimental stage needs its own preregistration. The common control matrix should include:

| Control | Expected role |
|---|---|
| spherical cloud + isotropic environment | zero-torque null |
| aligned inertia and tidal tensors | suppressed-torque null |
| misaligned triaxial cloud + external structure | positive tidal-torque case |
| mirrored initial geometry | equal magnitude, reversed handedness |
| internal forces only | global angular-momentum conservation |
| $\mathcal I_{\mathfrak s}=0$ with $G_{i\mathfrak s}\neq0$ | zero mixed-curvature force |
| $\mathcal I_{\mathfrak s}\neq0$ with $G_{i\mathfrak s}=0$ | zero mixed-curvature force |
| uniform scalar attenuation | no spontaneous torque from symmetry |
| merge off/on after torque acquisition | orbital-to-spin bookkeeping check |
| multiple spatial and scale resolutions | convergence and boundary-flux check |

A rotation mechanism is credible only if:

1. local $\Delta\mathbf L$ tracks the integrated measured torque;
2. the full matter–field–scale ledger closes;
3. mirror reflection reverses handedness without changing the magnitude beyond numerical tolerance;
4. null geometries remain null;
5. the effect survives resolution and timestep refinement;
6. merge changes the partition of angular momentum, not the total;
7. any claimed $D$ or $D^2$ scaling is tested while the other factors in the force law are independently controlled.

## 9. Decisions required before implementation

1. **What does $D$ attenuate?** Amplitude, current, energy, stress, or readout probability are different models.
2. **What is the physical Qi momentum variable?** It must not be inferred by relabeling $(\partial_tE_Y,\partial_tE_I)$ as a spatial vector.
3. **Is the Qi medium compressible?** This determines the longitudinal stress and projection scheme.
4. **Is $T_{ij}$ symmetric?** If not, an intrinsic spin/couple-stress current is required.
5. **What are the scale boundaries?** A scale-flux force is undefined until the observed window and receiving reservoir are explicit.
6. **How is $G_{i\mathfrak s}$ generated?** It must follow from the extended geometry rather than from a fitted force profile.
7. **Which action is authoritative?** The spatial Qi law, interscale current, and matter exchange must descend from one compatible action.
8. **What units connect simulation and physical scale?** $J_{\mathfrak s}$, $\mathcal I_{\mathfrak s}$, $G_{i\mathfrak s}$, $T_{i\mathfrak s}$, and particle acceleration need a closed dimensional map.
9. **How is parity handled?** A handed object needs a seed or instability, while the mirrored case must remain equally allowed.
10. **How does CassiFI flow remain separate?** Learned embodied commands must not silently become a physical momentum source.

## 10. Source anchors

### Live CassiCosmos behavior

- `CassiCosmos/compute/cassi_particle_merge.glsl` — pair momentum transfer, accumulated merge spin, and current flow proxy.
- `CassiCosmos/compute/cassi_two_fluid.glsl` — default field-rate semantics and CassiFI medium-flow branch.
- `CassiCosmos/compute/cassi_nbody_gravity.glsl` — RealSim consumption of mode-dependent `FieldVel` as `v_field`; this does not establish a conserved Qi stress law.
- `CassiCosmos/compute/cassi_voronoi_cells.glsl` — boxless site momentum variables and scalar site steering.
- `CassiCosmos/scripts/cassi_physics_engine.gd` — engine buffers and production coupling surface.

### Theory inputs and status boundaries

- `CassiTheory/foundations/cascade-suppression-formula.md` — product attenuation law; uniform $\varphi^{-1}$ attenuation is a declared cascade input, not a derived spatial force.
- `CassiTheory/foundations/interscale-current-soliton.md` — Hypothesized scale-coordinate current and separation from density-plane diagnostics.
- `CassiTheory/foundations/geometric-manifold-completion.md` — conditional mixed-curvature force $f_i=\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}$.

These sources support the architecture of the question. They do not yet establish that interscale attenuation causes galactic or particle rotation.