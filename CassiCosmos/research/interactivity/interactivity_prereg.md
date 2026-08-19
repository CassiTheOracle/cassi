# Interactive Field Workbench—frozen verification protocol

## Status: Pre-registered—August 2026

This protocol is frozen before the first Interactive Field Workbench verification run. It covers the first vertical slice: explicit paused-state field and particle operations, deterministic command logging, selected-region measurements, and scenario replay. No simulator run was performed before this document was written.

## 1. Scope

The workbench separates five categories:

1. **Initial-state settings** regenerate state through `reinit()` and are not live operations.
2. **Physics operations** mutate field or particle buffers only through an explicit Apply action while the simulator is paused.
3. **Transport operations** pause, resume, or advance an explicit number of fixed steps.
4. **View operations** select a lens or region and must not mutate simulation state.
5. **Measurements** read a selected region and must not mutate simulation state.

The first physics operations are:

- `deposit`: add a compact spherical Yang/Yin charge distribution;
- `align`: rotate each selected $(E_Y,E_I)$ pair toward $E_Y=\phi E_I$ while preserving $E_Y^2+E_I^2$ per cell;
- `impulse`: add a constant velocity vector to live particles inside a sphere without changing positions or masses.

The first implementation may use bounded CPU read-modify-write operations because they occur only while paused. The decoupled worker owns a separate RenderingDevice; live operations must reject that mode rather than cross the ownership boundary.

## 2. Frozen fixture

The focused verification scene uses:

- fixed grid, particle count, box extents, timestep, and nonzero initial-condition seed;
- `playing = false` before every operation;
- inline/global-RD mode for buffer ownership;
- fresh `reinit()` or an exact captured baseline before each independent arm;
- a fixed ordered command list;
- no adaptive step count, parameter tuning, or result-dependent rerun.

A missing RenderingDevice, incomplete initialization, wrong buffer length, non-finite baseline, or unavailable inline buffer owner makes the run **INVALID**. INVALID is not FAIL and does not enter the decision tree.

## 3. Quantities

For field cell $i$:

$$q_i = E_{Y,i}^2 + E_{I,i}^2,$$

$$\epsilon_i = E_{Y,i} - \phi E_{I,i},$$

$$\rho_i = E_{Y,i} + E_{I,i}.$$

The selected spherical region uses the simulator's world-to-grid convention and periodic shortest displacement. Particle membership uses live world positions and excludes particles with mass $m\le 0$.

Alignment uses target unit direction

$$\hat{a}=\frac{(\phi,1)}{\sqrt{\phi^2+1}}$$

and preserves $q_i$ exactly up to floating-point roundoff by assigning

$$(E'_{Y,i},E'_{I,i})=\sqrt{q_i}\,\hat{a}$$

at full strength. If a partial alignment strength is supported, it must normalize the interpolation back to radius $\sqrt{q_i}$.

## 4. Gates

### G0—fixture validity

PASS when the expected field and particle buffers exist at exact lengths, every sampled value is finite, the simulator is paused, inline ownership is active, and the fixed seed/configuration are recorded. Otherwise INVALID.

### G1—ordered-command determinism

From the same fresh baseline, apply the fixed command list twice. PASS requires:

- identical sequential command IDs and ordering;
- identical applied-step values;
- identical canonical command-log bytes;
- zero differing bytes in final EY, EI, Q, position, and velocity buffers.

Any non-finite value is FAIL. The run is not repeated with looser tolerances.

### G2—operation accounting

**Deposit.** Requested Yang/Yin charge equals the measured global buffer delta for each channel within relative error $10^{-3}$, with absolute floor $10^{-6}$. Q is recomputed from the resulting EY/EI values.

**Alignment.** For every selected cell, relative drift in $E_Y^2+E_I^2$ is at most $10^{-6}$; aggregate selected-region drift is at most $10^{-6}$. The absolute selected-region $|\epsilon|$ sum must not increase at positive alignment strength.

**Impulse.** The position and mass buffers remain byte-identical. The measured live-particle momentum change equals $\sum_i m_i\Delta v$ within relative error $10^{-4}$ and absolute floor $10^{-5}$. EY, EI, and Q remain byte-identical.

A parameter rejected before mutation is an explicit rejected command, not a passing operation.

### G3—scenario replay identity

Save a versioned scenario containing the exact captured baseline and ordered applied operations, then replay it into a fresh compatible simulator. PASS requires:

- schema version, dimensions, extents, and buffer lengths validated before mutation;
- checksum validation before mutation;
- identical ordered command-log bytes;
- identical final field and particle buffer bytes;
- the same step count and simulation time.

Wrong schema, dimension mismatch, truncated data, or checksum mismatch must be rejected without mutation.

### G4—pause/step state machine

PASS requires:

- Pause leaves state and counters unchanged;
- Apply while running is rejected without mutation;
- one explicit Step advances `_step_count` by exactly one and `_time` by exactly `dt`;
- an operation is applied once, never at two step boundaries;
- Resume changes transport state but does not itself apply an operation twice.

The verdict arm uses a fixed eight-step maximum and no wall-clock pacing assertion.

### G5—UI and view-only behavior

PASS requires the Workbench surface to expose transport, tool, center, radius, strength/vector parameters, Apply, scenario save/replay, lens selection, measurement, and operation status. Controls must have nonzero geometry, tooltips, and the existing camera/WASD focus behavior. Tool selection, lens selection, cursor/region movement, and measurement must leave field/particle bytes, step/time, and the physics operation log unchanged.

### G6—default no-op identity

With no workbench command applied, the new command layer performs no per-frame buffer access or mutation. A fixed short baseline must match a same-config workbench-disabled run byte-for-byte. Existing CassiCosmos regression arms must remain green.

### G7—lens and selected-region correctness

On an analytically planted field, selected-region readout must reproduce direct reference sums for cell count, EY, EI, Q, $\rho$, and $\epsilon$ within absolute error $10^{-6}$ per reported scalar. Particle counts and momentum are exact for the planted live-particle set. Lens selection itself remains view-only.

## 5. Decision tree

- **ADOPT VERTICAL SLICE**: G0 is valid and G1–G7 all PASS.
- **REJECT**: any valid gate FAILS. Report the failing gate and preserve the result; do not tune the same run.
- **INVALID**: G0 fails or the environment cannot provide the required RenderingDevice/buffer ownership. Repair only the invalid infrastructure, then begin one fresh run under this unchanged protocol.

The program makes no claim that a visual pattern demonstrates a human psychological or biological mechanism. Human-experience mappings remain explicitly interpretive presentation material.

## 6. Stopping rule

Run each focused verification arm once after implementation. Fix implementation defects revealed by a FAIL, record the defect, and run the complete frozen arm once more from a fresh fixture. Stop when the full arm yields ADOPT VERTICAL SLICE or when a valid gate yields a mechanism-level REJECT that cannot be repaired without changing this protocol. After focused adoption, run the existing CassiCosmos regression battery once. No result-dependent parameter sweep is permitted.
