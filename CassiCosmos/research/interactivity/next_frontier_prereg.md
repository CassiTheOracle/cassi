# Interactive Field Workbench: Next-Frontier Pre-registration

## Status: Frozen—2026-08-18

This protocol freezes the completion gates for direct manipulation, bounded GPU operations, controlled branching, procedural initial states, and the Energy-versus-coherence demonstration before any new verification run.

## Scope

The first complete frontier targets the periodic grid, inline physics path. It does not reinterpret the decoupled engine mirror or the boxless moving-Voronoi state as writable grid storage. Unsupported ownership/topology combinations must reject the command with a named reason.

The workbench remains opt-in and paused-first. Cursor movement, lens changes, camera movement, and branch selection are view operations and never enter the physics command ledger.

## Canonical coordinates and observables

Grid flattening is x-fastest:

$$
\operatorname{id}=i+N(j+Nk).
$$

The world-space center of cell $(i,j,k)$ is

$$
\mathbf{x}_{ijk}=\mathbf{x}_0+\left(\left(\frac{2(i+1/2)}{N}-1\right)e_x,\left(\frac{2(j+1/2)}{N}-1\right)e_y,\left(\frac{2(k+1/2)}{N}-1\right)e_z\right),
$$

where $\mathbf{x}_0$ is the live window center and $\mathbf e$ contains the anisotropic half-extents.

The comparison panel reports three different quantities with explicit names:

- field intensity: $E^2=E_Y^2+E_I^2$;
- bounded coherence: $q_{\mathrm{coh}}=\rho^2/(\rho^2+\varphi^{-2}+\epsilon^2)$;
- disequilibrium: $\epsilon=E_Y-\varphi E_I$, with $\rho=E_Y+E_I$.

`field_q` is the unbounded field intensity buffer and must never be labelled bounded coherence.

## Frozen command semantics

All commands carry `kind`, world-space `center`, positive finite `radius`, and command-specific finite values.

- `deposit`: add a total Yang amount and the same total Yin amount over selected cells. Uniform and radial weighted selections are normalized so the requested total is independent of selected-cell count.
- `align`: preserve each selected cell's $\sqrt{E_Y^2+E_I^2}$ while rotating its channel direction toward normalized $(\varphi,1)$. Strength is in $[0,1]$. Zero strength is exact identity. A zero or antipodal interpolation vector uses the target direction rather than producing NaN.
- `impulse`: add the supplied velocity vector to each live particle in the periodic spherical selection.

The bounded GPU route is required for `align` and `impulse`. Normalized deposit is admitted only if its deterministic normalization gate passes; otherwise the command remains an explicit CPU paused operation and the report records the rejected GPU promotion rather than substituting a non-normalized kernel.

## Branch model

A checkpoint records field buffers, particle position/velocity, grid size, extents, window center, step count, simulation time, and the compatibility signature. Exact restore is limited to inline periodic-grid mode with decoupling, meshless state, merging, black holes, tracking envelope, and home-window tracking disabled. Any incompatible mode rejects capture or restore.

A branch run restores the shared checkpoint, applies an ordered command list, advances an exact integer step count, and captures a summary. The no-operation sibling follows the same restore and step schedule. Difference summaries use frozen scales derived once from the shared checkpoint; they are numerical and do not depend on the currently incomplete field-slice renderer.

## Procedural initial-condition model

The composer emits a deterministic ordered recipe in normalized box coordinates. The first supported primitives are shell, Gaussian knot, filament, vortex, and a finite $\varphi$-cascade. A recipe is applied after deterministic base initialization and before the scenario baseline is captured. Same seed, box geometry, and recipe must produce the same digest.

## Guided Energy-versus-coherence scenario

Two regions begin with matched mean $E^2$ within $10^{-5}$ relative tolerance. One region is channel-aligned to $(\varphi,1)$ and the other is channel-orthogonal while preserving magnitude. The demonstration passes only when:

1. matched-intensity setup gate passes;
2. aligned-region mean $q_{\mathrm{coh}}$ exceeds the orthogonal region by at least 0.05;
3. absolute mean disequilibrium is smaller in the aligned region;
4. repeated measurement without a command is byte-stable;
5. the no-operation sibling retains the frozen baseline digest at zero steps.

This demonstrates that equal field intensity does not imply equal coherence. It does not claim a complete Hamiltonian energy measurement.

## Gates

- **NF0—Adapter and ownership:** public API exists; paused inline grid accepts; playing, decoupled, and boxless ownership reject without buffer writes.
- **NF1—Coordinate identity:** index decoding, shifted window center, anisotropic extents, and periodic distance match independent expected values.
- **NF2—Direct cursor:** numeric and viewport paths share one world-space cursor; viewport manipulation is explicitly armed; leaving the tab or collapsing the rail disarms it; text editing does not trigger global shortcuts.
- **NF3—GPU identity:** zero-strength align and zero-vector impulse are byte-identical; dispatch order is command order.
- **NF4—GPU parity:** nonzero align and impulse match the frozen CPU reference within $2\times10^{-6}$ absolute error, including the antipodal align guard.
- **NF5—Checkpoint:** capture/restore digest is exact; step/time restore; incompatible configurations reject.
- **NF6—Branch:** no-op sibling is exact; two distinct command branches report distinct summaries using the same frozen scales.
- **NF7—Composer:** each primitive is deterministic, finite, bounded to the requested geometry, and same-recipe digests match.
- **NF8—Signature scenario:** all five guided-scenario conditions above pass.
- **NF9—Lifecycle/default:** new resources free cleanly; the ordinary disabled path does not dispatch workbench kernels or mutate state.

## Decision tree and stopping rule

A gate is `PASS` only from the focused verifier's measured output. A failed ownership or determinism gate blocks promotion of the affected operation. A GPU normalized-deposit implementation that fails determinism or costs more than one full field readback on the 64³ fixture is `REJECT` for this frontier, preserving the correct CPU operation. The run stops after one focused result plus one applicable existing regression arm; failures are repaired once and rerun under this unchanged protocol. Verdicts are `ADOPT`, `REJECT`, or `INCONCLUSIVE` per feature, with exact limitations retained in the completion report.
