# Matter Completion Boundary Report

## Status: Tested conditional boundary—September 2026

## Abstract

This report records the first and sole execution of the frozen MCC1–MCC9
receipt. All nine conditional gates pass. The receipt closes the mathematical
boundary connecting a minimal exterior dilation, reciprocal interface,
routed transport, single-mode power normalization, maintained open-system
coherence, total stress, constant-$G$ backreaction, the Cartan embedding in the
particle branch, and the reduced fixed-charge stability criteria.

The MCC1–MCC9 receipt carries no PA32 solve and therefore makes no stationary
background claim by itself. The independent canonical-preimage continuation
campaign supplies a Q2-qualified finite-grid primary background with verdict
`PASS—Q2-QUALIFIED PRIMARY BACKGROUND`. The selected field fails localization
and carrier retention, while every domain plus high-resolution arm fails Q2.
The physical exterior, microscopic interface coefficients, golden port-power
identification, multimode carrier normalization, reservoir, local reservoir
stress, state-dependent gravity, coherence-fibre particle identity, domain and
resolution convergence, and full constrained spectrum remain open.

## 1. Frozen execution

The preregistration is
`computations/matter_completion_boundary_prereg.md`. The checker was executed
once from the CassiTheory repository root:

```text
python computations/matter_completion_boundary_check.py
```

No coefficient, tolerance, witness, scope flag, or decision rule changed after
execution.

## 2. Verdicts

The receipt verdict is

$$
\boxed{\text{MCC1--MCC9: PASS}.}
$$

This verdict applies to the conditional completion boundary defined in the
preregistration. The retained physical verdict is

$$
\boxed{\mathrm{INCONCLUSIVE\text{-}NUMERICAL\ QUALITY}.}
$$

The second verdict comes from the frozen particle stationary campaign. MCC9
uses only the analytic CC29 length branch and the CC47 frozen-mode
line-density sector.

## 3. Gate summary

| Gate | Tested statement | Result | Physical scope retained |
|---|---|---:|---|
| MCC1 | The golden amplitude-damping map is CPTP, has Kraus rank two, and admits a two-dimensional return-mode dilation whose environment basis is nonunique | **PASS** | Physical exterior carrier and topology open |
| MCC2 | The bilinear reciprocal interface is Hermitian and independently frame-covariant; exact evolution conserves enlarged number and energy; a discrete map has nonunique logarithm branches | **PASS** | $V$, $L_a$, and $R_a$ unselected |
| MCC3 | Closed transport is unitary; a single routed forward leg gives $\varphi^{-N/2}$ cross-coherence amplitude and $\varphi^{-N}$ power; two routed legs give the separate symmetric exponent | **PASS** | Non-re-entry and golden port-power identification unselected |
| MCC4 | Canonical single-mode power scales as amplitude squared; an equal-$\|K\|_F$ counterexample has unequal mode-energy weighting | **PASS** | Universal $\|K\|_F$-to-power map open |
| MCC5 | Repeated fresh return modes give the discrete/continuous decay match and a stable driven stationary cross block | **PASS** | Bath, drive, spectrum, temperature, and correlation time unselected |
| MCC6 | Enlarged unitary evolution conserves total energy and number; interior and complementary exchange vectors close the Ward ledger | **PASS** | Local reservoir stress components require a closed metric-dependent action |
| MCC7 | The constant-$G$ linearized Einstein witness is transverse; a variable scalar coupling creates an extra divergence | **PASS** | State-dependent gravity open |
| MCC8 | The Cartan connection requires the minus-sign transformation; rank-one and full-rank Gram fibres are positive; $Q_C$ remains an independent singlet charge | **PASS** | Physical coherence-fibre particle identity open |
| MCC9 | The frozen CC29 branch has one bounded positive-curvature root and positive nonconstant CC47 line modes | **PASS** | MCC9 contains no PA32 solve; separate recovery supplies a Q2-qualified finite-grid primary background, while localization, domain/resolution convergence, and the constrained spectrum remain absent |

## 4. Literal first-execution output

```text
Matter completion boundary — frozen MCC1–MCC9 receipt
phi=1.618033988749895 T=0.618033988749895 R=0.381966011250105 T+R=1.000000000000000
MCC1 PASS: TP_error=0.000e+00 Choi_min=-5.551e-17 Choi_rank=2 dilation_unitarity=5.465e-18 extraction_error=0.000e+00 basis_rotation_error=5.551e-17
MCC2 PASS: Hermitian_error=0.000e+00 covariance_error=1.114e-16 number_error=8.882e-16 energy_error=5.554e-17 branch_map_error=5.467e-16 generator_gap=31.415927
MCC3 PASS: unitarity=5.465e-18 one_sided=0.300283106001 symmetric=0.090169943749 routed_power=0.090169943749 ledger_error=1.110e-16 coherent_power=0.964478868272 control_difference=8.743e-01
MCC4 PASS: single_mode_ratio=0.618033988750 ratio_error=0.000e+00 equal_norm_error=0.000e+00 weighted_A=0.040000 weighted_B=0.120000 universal_map=False
MCC5 PASS: gamma=2.406059125298 population_ratio=0.055728090001 coherence_ratio=0.236067977500+0.000e+00i continuous_error=2.776e-17 stationary_residual=0.000e+00 pole_real=-1.203030 physical_bath=False
MCC6 PASS: number_error=1.110e-15 energy_error=9.541e-18 closed_Ward_error=0.000e+00 local_reservoir_stress=False
MCC7 PASS: harmonic_error=0.000e+00 Bianchi_error=0.000e+00 source_divergence=0.000e+00 variable_G_extra=6.724e-03 state_dependent_gravity=False
MCC8 PASS: minus_covariance_error=1.390e-17 plus_residual=1.207e-01 rank1_det=7.994e-19 mixture_min=5.462e-01 mixture_det=9.033e-01 population_change=3.541e-01 carrier_charge_error=0.000e+00
MCC9 PASS: root=1.269522140245 residual=4.441e-16 bound_margin=4.478e-02 monotonic_margin=1.755000 curvature=1.496039 min_line_mode=0.975736 Q2_background=False full_spectrum=False
RECEIPT VERDICT: PASS
PHYSICAL PARTICLE VERDICT: INCONCLUSIVE—NUMERICAL QUALITY
OPEN PHYSICAL SCOPES: physical_exterior_selected, microscopic_interface_coefficients_derived, golden_port_power_identification_derived, universal_cross_coherence_power_map, physical_reservoir_identified, local_reservoir_stress_derived, state_dependent_gravity_closed, coherence_fibre_particle_identity_derived, q2_qualified_full_background, full_constrained_spectrum_computed
```

## 5. Nine derived boundaries

### 5.1 Exterior-domain identity

The reduced golden channel has two Kraus operators and Choi rank two. Its
minimal Stinespring environment is therefore two-dimensional. The explicit
one-excitation splitter reproduces those Kraus operators with extraction error
zero. Rotating the Kraus pair changes the environment basis while preserving
the reduced channel to $5.551\times10^{-17}$.

The mathematical exterior is the complementary output of the selected
dilation, unique up to an environment unitary in the minimal realization. The
reduced map supplies no carrier species, physical topology, preparation law,
or boundary dynamics.

### 5.2 Interface action and transfer maps

The lowest-order local bilinear interface satisfying the frozen assumptions is

$$
\mathcal H_{\rm int}
=\Psi_{\rm in}^\dagger V\Psi_{\rm out}
+\Psi_{\rm out}^\dagger V^\dagger\Psi_{\rm in}.
$$

The independent-frame covariance residual is
$1.114\times10^{-16}$. Exact enlarged evolution conserves number and energy to
$8.882\times10^{-16}$ and $5.554\times10^{-17}$, respectively. Two generators
separated by $2\pi/\Delta t=31.415927$ produce the same discrete map to
$5.467\times10^{-16}$. Discrete transfer data therefore leave the continuous
generator branch unresolved.

### 5.3 Transport branch

The full golden two-port matrix is unitary to $5.465\times10^{-18}$. At five
interfaces, the one-sided routed cross block gives

$$
\frac{\|K_5\|_F}{\|K_0\|_F}=0.300283106001=\varphi^{-5/2},
$$

while forward power gives

$$
\frac{P_5^{\rm fwd}}{P_0^{\rm fwd}}
=0.090169943749=\varphi^{-5}.
$$

The symmetric two-leg cross block also has ratio $0.090169943749$ because both
indices are independently attenuated. The closed coherent control gives
forward power $0.964478868272$, separating coherent re-entry from routed
multiplication.

The complete dynamics are conservative. The single-forward-carrier reduced
observable selects the one-sided cross-block exponent once non-re-entry is
imposed.

### 5.4 Coherence and power normalization

The canonical single-mode relation $P=\hbar\omega\dot N$ gives
$P_{\rm out}/P_{\rm in}=|t_\varphi|^2=0.618033988750$ exactly at displayed
precision. Two mode blocks with equal Frobenius norm receive weights $0.04$
and $0.12$ from the frozen nondegenerate frequency operator. A Frobenius norm
alone therefore does not determine multimode physical power.

### 5.5 Reservoir support

Six fresh-return channel applications give

$$
\frac{N_6}{N_0}=0.055728090001=T^6,
\qquad
\frac{C_6}{C_0}=0.236067977500=T^3.
$$

The continuous rate

$$
\gamma=-\frac{\ln T}{\Delta t}=2.406059125298
$$

reproduces both factors to $2.776\times10^{-17}$. The frozen maintained solution
has zero residual and homogeneous pole real part $-1.203030$. This establishes
the collision-model support equation under its declared assumptions. A
physical reservoir action and drive remain to be selected.

### 5.6 Total stress

The finite-dimensional enlarged witness conserves energy to
$9.541\times10^{-18}$ and number to $1.110\times10^{-15}$. Its interior and
complementary exchange vectors cancel exactly. The field statement is the
conditional closed-action Ward identity

$$
\nabla^\mu T^{\rm closed}_{\mu\nu}=0,
$$

with equal-and-opposite exchange in reduced sectors. Explicit local reservoir
stress components await $S_{\rm out}$, $S_{\rm int}$, and $S_{\rm env}$ with
their metric dependence.

### 5.7 Geometry backreaction

The frozen harmonic-gauge perturbation, its linearized Einstein tensor, and the
constant-$G$ source are transverse to machine zero. A spatially varying scalar
coupling produces the extra divergence $6.724\times10^{-3}$ in the fixed
counterexample. The minimal covariant branch is therefore

$$
G_{\mu\nu}+\Lambda g_{\mu\nu}
=8\pi G T^{\rm closed}_{\mu\nu}
$$

with constant $G$ and total closed stress. A $q$-dependent coupling requires
additional covariant dynamics.

### 5.8 Particle-branch map

The minus-sign Cartan transformation gives covariance residual
$1.390\times10^{-17}$. The plus-sign alternative gives residual $0.1207$.
Together with PA7–PA8, this fixes

$$
B_A\mapsto B_A-\frac1{g_Q}\partial_A\alpha
$$

for DG15's convention.

The particle doublet produces a positive rank-one fibre with determinant
$7.994\times10^{-19}$. A two-state Gram mixture has minimum eigenvalue
$0.5462$ and determinant $0.9033$, giving a full-rank positive fibre. A generic
$SU(2)_Q$ rotation changes the Cartan population split by $0.3541$, while the
singlet carrier charge is unchanged. The relative Cartan charge and global
$Q_C$ therefore remain separate.

### 5.9 Reduced stationary and spectrum boundary

For the frozen CC29 coefficients, the unique monotone-branch root is

$$
L_*=1.269522140245,
$$

with CC36 residual $4.441\times10^{-16}$, positive distance from both CC38
bounds, and reduced curvature $1.496039$. The smallest nonconstant frozen
line-density eigenvalue is $0.975736$.

These numbers verify the length and frozen line-density sectors.
Canonical-preimage continuation of the registered particle endpoints supplies
five structural primary arms that pass Q1–Q4. The frozen rule selects
`P:separated_core`. That field fails localization and carrier retention, and
every domain plus high-resolution arm fails Q2. MCC9 therefore supplies no
domain-stable basin ordering or spectrum qualification. The unresolved
particle sectors remain: non-axisymmetric deformations and knots; arbitrary
multicore and fragmented-charge configurations; higher scale and transverse
modes; topology-changing paths; infinite-domain existence; the full
fixed-charge, gauge-quotiented Hessian and mixed dynamical spectrum; real-time
decay, tunnelling, and continuum thresholds; and quantum spin and statistics.

## 6. Present boundary

The nine sectors now have one shared conditional chain:

$$
\begin{aligned}
&\text{minimal dilation}
\longrightarrow \text{reciprocal bilinear interface}
\longrightarrow \text{closed splitter plus routed readout}\\
&\longrightarrow \text{single-mode stress normalization}
\longrightarrow \text{maintained reduced coherence}
\longrightarrow \text{closed total stress}\\
&\longrightarrow \text{constant-}G\text{ backreaction}
\longrightarrow \text{Cartan particle embedding}
\longrightarrow \text{fixed-charge stationary qualification}.
\end{aligned}
$$

Each arrow states its assumptions and remaining physical input. The selected
Q2-qualified primary artifact permits construction of the finite-grid
projected Hessian. Carrier localization, domain and resolution convergence,
the full gauge quotient, and selected temporal groups remain independent
qualification requirements.

## References

- `computations/matter_completion_boundary_prereg.md`—frozen MCC1–MCC9
  statements, constants, gates, and decision tree.
- `computations/matter_completion_boundary_check.py`—deterministic first-run
  receipt.
- `foundations/yin-yang-qi-dynamical-geometry.md`—positive coherence fibre,
  cross-domain source, transport, and stress boundary.
- `foundations/interscale-stress-attenuation-boundary.md`—golden splitter,
  routed ledger, and mixed-stress requirements.
- `foundations/physical-becoming-hierarchy.md`—conditional open-system
  conversion and response dynamics.
- `foundations/particle-stationary-action-closure.md`—fixed-charge particle
  action and variational class.
- `foundations/core-trapped-charge-support.md`—reduced support and stability
  theorem.
- `computations/particle-stationary-bvp-report.md`—registered source campaign
  receipt.
- `computations/particle-stationary-q2-recovery-report.md`—Q2-qualified primary
  background and retained localization, domain, resolution, and spectrum
  boundaries.
