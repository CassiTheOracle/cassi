# Conservative rotation-stress build — pre-registration

Date: 2026-09-02
Reference artifact: `_diag/rotation_reference.json`
GPU artifact: `_diag/rotation_stress_gpu.json`
Production gate: `scenes/verify_rotation_stress.tscn`
Independent gate: `research/rotation/rotation_verify.py`

## Question

Can CassiCosmos add a default-off vector Qi momentum/stress sector that:

1. transports three-dimensional momentum through space and across a small explicit scale ladder;
2. exchanges momentum with particles without creating net linear or angular momentum;
3. uses the cascade factor as a scale-interface transfer coefficient rather than claiming that scalar amplitude loss is momentum attenuation;
4. retains dissipated relative kinetic energy as an explicit heat ledger;
5. converts existing merge spin into a finite, normalized object orientation; and
6. leaves the established engine path byte-identical while disabled?

This build does not test a galaxy rotation curve and does not claim that attenuation creates torque. Existing gravity remains the torque-acquisition mechanism. The new sector transports and stores angular momentum after a directed matter or field state exists.

## Frozen constitutive branch

The implementation adopts the **flux branch** from `rotation_design.md`. It does not adopt the current-amplitude or readout branches.

### Vector field state

Each coarse periodic cell and scale rung $a=0,\ldots,S-1$ carries:

- displacement $\mathbf u_a$ with units $L$;
- momentum $\mathbf p_a$ with units $ML/T$;
- unresolved intrinsic angular momentum $\mathbf s_a$ with units $ML^2/T$;
- heat $H_a$ with units $ML^2/T^2$.

Each cell has fixed field inertia $M_Q$ with units $M$. The field velocity is

$$
\mathbf v_{Q,a}=\frac{\mathbf p_a}{M_Q}.
$$

This is new state. It is not an alias for `FieldVel`, $\partial_tE_Y$, $\partial_tE_I$, CassiFI `learned_medium_flow`, or the scalar site momenta.

### Spatial stress

The spatial field is the isotropic linear-elastic reference system

$$
\dot{\mathbf u}_a=\frac{\mathbf p_a}{M_Q},
$$

$$
\dot{\mathbf p}_a
=M_Q\left[
 c_T^2\nabla^2\mathbf u_a
 +(c_L^2-c_T^2)\nabla(\nabla\cdot\mathbf u_a)
 +\mathbf a_a^{\mathrm{scale}}
\right].
$$

$c_T$ and $c_L$ have units $L/T$. The finite-difference spatial operator is periodic, centered, and evaluated from the old displacement. Momentum is kicked before displacement is drifted, giving a symplectic-Euler field step.

### Interscale transfer

Adjacent rungs use a symmetric spring current:

$$
\mathbf a_a^{\mathrm{scale}}
=\omega_s^2\left[
 D_{a-1}(\mathbf u_{a-1}-\mathbf u_a)
 +D_a(\mathbf u_{a+1}-\mathbf u_a)
\right],
$$

with absent boundary terms omitted and

$$
D_a=d^{a+1},\qquad d=\varphi^{-1}.
$$

$\omega_s$ has units $T^{-1}$. Each interface applies equal and opposite momentum kicks. Therefore $D_a$ is a dimensionless **interface conductance/stiffness weight**. It changes the transfer rate; it does not delete momentum and is not interpreted as a measured amplitude attenuation law.

For a frozen displacement contrast with all other factors fixed, the first-step interface impulse must scale linearly with $D_a$. No $D^2$ claim is registered.

### Matter–field exchange

Only rung $a=0$ couples to matter. Particles are aggregated into the coarse cell containing their window-relative position:

$$
M_C=\sum_{n\in C}m_n,
\qquad
\mathbf P_C=\sum_{n\in C}m_n\mathbf v_n.
$$

For $M_C>0$, define

$$
\mathbf v_C=\frac{\mathbf P_C}{M_C},
\qquad
\mu_C=\frac{M_CM_Q}{M_C+M_Q},
\qquad
\eta=1-e^{-\gamma\Delta t}.
$$

The cell impulse from matter to Qi is

$$
\mathbf J_C=\eta\mu_C(\mathbf v_C-\mathbf v_{Q,0}).
$$

The field receives $+\mathbf J_C$. Particle $n$ receives

$$
\Delta\mathbf p_n=-\frac{m_n}{M_C}\mathbf J_C.
$$

Thus the cell exchange conserves linear momentum algebraically. The lost relative kinetic energy is not discarded:

$$
\Delta H_C
=\frac12\eta(2-\eta)\mu_C
\left|\mathbf v_C-\mathbf v_{Q,0}\right|^2
\ge 0.
$$

This is a momentum-conserving viscous exchange with an explicit heat ledger, not a Hamiltonian particle coupling.

### Angular-momentum closure

For a particle impulse $\mathbf j_n=(m_n/M_C)\mathbf J_C$ deposited at field-cell center $\mathbf r_C$, the unresolved cell spin receives

$$
\Delta\mathbf s_C
=(\mathbf r_n-\mathbf r_C)\times\mathbf j_n.
$$

Then the particle orbital change, field orbital change, and spin correction sum to zero:

$$
\mathbf r_n\times(-\mathbf j_n)
+\mathbf r_C\times\mathbf j_n
+\Delta\mathbf s_C
=0.
$$

The same ledger correction records the Cartesian discretization residual of a spatial stress kick $\Delta\mathbf p_C$ as $-\mathbf r_C\times\Delta\mathbf p_C$. Positions used by the gate are unwrapped in one local frame; periodic minimum-image separation is used only for the particle-to-cell offset.

### Merge spin orientation

When the canonical merge-spin buffer exists, each live survivor uses the solid-sphere reference model

$$
R(m)=\operatorname{clamp}(k_Rm^{1/3},R_{\min},R_{\max}),
\qquad
I=\frac25mR^2,
\qquad
\boldsymbol\omega=\frac{\mathbf S}{I}.
$$

A unit quaternion is advanced by $\dot q=\tfrac12(\boldsymbol\omega,0)q$ and renormalized. Orientation is observable through the engine rotation-state readback. It does not feed force or velocity in this build because no quadrupole or nonspherical object action has been derived.

## Frozen implementation boundary

- One new compute shader owns the vector-field, scale-transfer, exchange, heat, spin-ledger, and orientation passes.
- The production owner is `scripts/cassi_physics_engine.gd`; no parallel learned state and no reuse of `FieldVel`.
- The feature is available on the default decoupled/standalone physics-engine path. The legacy inline duplicate remains unchanged.
- Buffers and pipeline are created only when `rotation_stress_enabled=true`.
- The toggle defaults to false. No existing push-constant or binding layout changes.
- Coarse-grid resolution is independent of the canonical two-fluid grid and is limited to keep memory bounded.
- Production defaults when enabled are: 16³ cells, 4 rungs, $M_Q=1$, $c_T=0.5$, $c_L=0.8$, $\omega_s=0.5$, $d=\varphi^{-1}$, and $\gamma=0.25$ in simulation units.
- The implementation rejects $S<2$, nonpositive inertia, nonpositive extents, $d\notin(0,1]$, $c_L<c_T$, or a field CFL number $c_L\Delta t/h_{\min}>0.35$.

## Frozen reference inputs

`rotation_reference.py` uses float64 NumPy with:

- coarse grid $N_R=4$ and extents $(2,2,2)$;
- three scale rungs;
- $\Delta t=0.01$, $M_Q=2$, $c_T=0.4$, $c_L=0.7$, $\omega_s=0.5$;
- $d=\varphi^{-1}$ and $\gamma=1.5$;
- deterministic arrays written directly in the script; no random seed or fitted value;
- one-step controls for algebraic identities and 64 steps for finite stability.

The tidal control uses a fixed triaxial particle cloud and a fixed symmetric external tidal tensor. The mirrored arm reflects the $x$ coordinate and corresponding tensor components.

## Frozen GPU inputs

`verify_rotation_stress.gd` runs windowed on a local RenderingDevice with:

- canonical engine grid $N=8$;
- eight deterministic particles;
- rotation grid $N_R=4$ and three rungs;
- the same $\Delta t$, field parameters, attenuation, and exchange rate as the reference;
- gravity and two-fluid evolution bypassed for the isolated rotation-step gates;
- direct workbench writes of particle and rotation state;
- one-step algebraic controls followed by a 64-step finite-stability arm;
- a separate pair of feature-off engine runs using the same seed and two complete engine steps.

The GPU arm writes every registered metric to `_diag/rotation_stress_gpu.json` before exiting.

## Registered gates

### G75 — tidal torque and mirror control

Reference PASS requires:

- relative error between $\Delta\mathbf L$ and the integrated measured external torque no greater than $10^{-10}$;
- the mirrored arm reverses the registered angular-momentum component with relative magnitude error no greater than $10^{-10}$;
- the symmetric/aligned null has absolute angular-momentum change no greater than $10^{-12}$.

### G76 — reference matter–field conservation

Reference PASS requires after one exchange:

- relative total linear-momentum error no greater than $10^{-12}$;
- relative total angular-momentum error, including cell spin, no greater than $10^{-12}$;
- heat increment finite and nonnegative;
- omitting the spin correction produces an angular error at least $10^4$ times larger than the registered full-ledger error.

### G77 — reference interscale transfer

Reference PASS requires:

- summed scale momentum change no greater than $10^{-12}$ in absolute norm;
- first-interface impulse ratio between $d=\varphi^{-1}$ and $d=1$ agrees with $\varphi^{-1}$ within $10^{-12}$ relative error;
- the zero-displacement and equal-rung controls produce no interscale impulse above $10^{-12}$;
- all state and heat values remain finite for 64 steps.

### G78 — production default-off identity

GPU PASS requires the complete position, particle-velocity, acceleration, $E_Y$, $E_I$, and $q$ bytes after two engine steps to be identical between a baseline config with no rotation key and the same config with `rotation_stress_enabled=false`. The disabled rotation-state readback must report `enabled=false` and no rotation buffer may be required for engine readiness.

### G79 — GPU linear-momentum exchange

GPU PASS requires one isolated rotation exchange to have relative matter-plus-field linear-momentum error no greater than $2\times10^{-5}$ and finite nonnegative heat.

### G80 — GPU angular-momentum ledger

GPU PASS requires relative total angular-momentum error no greater than $5\times10^{-4}$ when field orbital momentum and intrinsic cell spin are included. The error without intrinsic cell spin must be at least ten times larger.

### G81 — GPU attenuation and null controls

GPU PASS requires:

- the first-interface impulse ratio for $d=\varphi^{-1}$ versus $d=1$ to agree with $\varphi^{-1}$ within $2\times10^{-4}$ relative error;
- zero-displacement and equal-rung controls to have maximum absolute interscale impulse no greater than $10^{-6}$;
- no nonfinite telemetry or state values.

### G82 — object orientation and finite stability

GPU PASS requires:

- a planted nonzero merge spin changes the survivor quaternion by more than $10^{-6}$ in Euclidean norm;
- quaternion norm error no greater than $10^{-5}$;
- a zero-spin survivor remains identity within $10^{-6}$;
- all particle, vector-field, heat, spin, and orientation values remain finite through 64 isolated rotation steps;
- total linear-momentum drift no greater than $5\times10^{-4}$ and full-ledger angular-momentum drift no greater than $5\times10^{-3}$ over those steps.

## Decision tree and stopping rule

- G75–G77 must pass before the GPU production toggle is accepted.
- G78–G82 must all pass for `rotation_stress_enabled` to remain wired into the production engine.
- Any failed registered condition is `FAIL`; no coefficient, tolerance, initial state, or sample count may be changed after the first run.
- A shader compile failure, device loss, timeout, nonfinite value, missing artifact, or independent-verifier disagreement is `INCONCLUSIVE—IMPLEMENTATION` and stops adoption until the implementation defect is corrected without changing the frozen physics inputs or thresholds.
- The full windowed GPU battery is the final regression contract. A battery failure blocks completion even when G75–G82 pass.
- Scientific interpretation is limited to conservation and implementation behavior. These gates do not establish a cosmological origin of rotation, a physical value of $d$, or a measured stress–attenuation law.