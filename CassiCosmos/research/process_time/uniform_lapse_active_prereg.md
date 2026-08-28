# Active pre-registration: uniform scalar process-time reparameterization

**Status:** frozen before the scene and verifier are used. This is an implementation proof for the existing CassiCosmos two-fluid GPU path. It is **not CT-2 evidence, not evidence for a local coherence-derived lapse, and not evidence for universal physical time**.

## Question and strict scope

Can one uniform first-order time reparameterization be represented by the existing two-fluid push-constant contract, with the final GPU state depending only on process age rather than on the arm's coordinate-time label?

The only lapse in scope is one scalar shared by the entire grid:

\[
 t_p = N\,t_c,\qquad dt_p=N\,dt_c,
\]

where `t_c` is coordinate bookkeeping time, `t_p` is shader process time, and `N` is constant for a complete sub-run. The implementation is the existing shader surface: set `pc.dt = dt_p` and `pc.t = t_p` for every pass. No production shader, engine, or push-constant slot is changed, and no new production branch is justified because a uniform lapse is already exactly representable as `dt_process=N*dt_coordinate`.

For notation only, a bounded coherence diagnostic would be written `q_b=rho^2/(rho^2+phi^-2+epsilon^2)` and `N_q=(1-q_b)/(1-q_ref)`. This probe does not read the production unbounded `q` buffer to derive either quantity, does not feed `q` or `N_q` back into the shader, and does not compare `q` between arms. A spatially varying `N_q(x)` is explicitly outside scope: it is not one scalar and would require an action-derived operator, not this existing `pc.dt` contract.

The epistemic boundary is strict: a byte-identical result at equal process age proves only that this existing implementation realizes a uniform scalar reparameterization. It does not establish that coherence generates a physical lapse, that a local lapse exists, that clocks are gravitational/particle/BH clocks, or that any result generalizes beyond this shader, grid, initial condition, and finite run.

## Frozen production surface and equations

The verifier loads exactly `res://compute/cassi_two_fluid.glsl` and dispatches its existing local RenderingDevice pipeline. The shader's 17-float push constant is not resized or repurposed:

| slot | value in every arm | meaning |
|---:|---:|---|
| 0 | `GRID_N` | grid side length |
| 1 | `dt_process` | existing `pc.dt`, the only timestep seen by the shader |
| 2 | `t_process` | existing `pc.t`, advanced on the process-time trajectory |
| 3 | `PHI = 1.618033988749895` | existing `phi` |
| 4 | `0` | `xi` |
| 5 | `0` | `eps2` |
| 6 | `0` | particles absent (`particle_N`) |
| 7 | `0` | mode |
| 8 | `0` | sources OFF (`source_strength`) |
| 9 | `0` | no clusters |
| 10 | `0` | gravity mode |
| 11–13 | `EXTENT` | isotropic periodic box half-extents |
| 14 | `0` then `1` | pass A, then pass B |
| 15 | `OMEGA2 = 20` | existing \(\omega_0^2\) |
| 16 | `1` | Hamiltonian completion ON |

With \(D=EY-\phi EI\), the completed two-fluid equations exercised here are

\[
 \partial_{t_p}^2 EY = L EY-\omega_0^2D,\qquad
 \partial_{t_p}^2 EI = L EI+\phi\omega_0^2D,
\]

where `L` is the existing shader's periodic 19-point Laplacian, including its exact per-axis coefficients for the frozen isotropic box. The verifier never substitutes a CPU evolution for this operator. Each step is exactly one shader pass A (canonical fields to scratch) followed by pass B (scratch to canonical fields), with a local-RD submit and sync after each dispatch.

The discrete Hamiltonian used only for the bounded-shadow diagnostic is frozen as

\[
 H=\sum_x\left[
 \tfrac12(v_x^2+v_y^2+v_z^2)
 -\tfrac12 EY\,(L EY)
 -\tfrac12 EI\,(L EI)
 +\tfrac12\omega_0^2(EY-\phi EI)^2
 \right].
\]

The `w` component of the shader's velocity `vec4` is not included as kinetic velocity; it is the shader's stored \(\epsilon^2\) diagnostic. The Hamiltonian is evaluated on CPU from raw readback using the same periodic stencil and the same `EXTENT` coefficients before step 1 and after the final step. The ratio is a numerical bounded-shadow check, not a claim of an exact conserved continuum quantity.

## Frozen arms and deterministic initial condition

There are exactly three fresh deterministic sub-runs, all on the same local RD pipeline and all reset to the same initial buffers before stepping:

| arm | coordinate `dt_c` | scalar `N` | process `dt_p=N*dt_c` | fixed steps | coordinate duration | process duration |
|---|---:|---:|---:|---:|---:|---:|
| `baseline-A` | `0.005` | `1.0` | `0.005` | `32` | `0.160` | `0.160` |
| `baseline-B` (OFF duplicate) | `0.005` | `1.0` | `0.005` | `32` | `0.160` | `0.160` |
| `uniform-lapse` | `0.010` | `0.5` | `0.005` | `32` | `0.320` | `0.160` |

The coordinate duration is host-side bookkeeping only. The process duration is the shader trajectory. For every arm and one-based process step \(s\in\{1,\ldots,32\}\), the verifier sends `pc.dt=0.005` and `pc.t=s*0.005` (the same process-time value to pass A and pass B). Therefore all three arms have the same `pc.dt` and `pc.t` bytes at the same process step; the lapse arm's coordinate clock is exactly twice as long while its process age is equal.

The frozen grid is `GRID_N=16`, `EXTENT=12.0`, with periodic indexing and `CELLS=16^3`. The deterministic initial seed label is `0x51A7`; no random generator is called. At cell `(i,j,k)`, with \(\theta_u=2\pi u/16\), the initial canonical fields are

\[
 EY_0=0.20\left[\cos\theta_i+0.5\cos\theta_j+0.25\cos\theta_k\right],
\]
\[
 EI_0=0.10\left[\sin\theta_i-0.5\sin\theta_j+0.25\sin\theta_k\right].
\]

The initial velocity buffer is all zero; its `w` lane is also zero. The `q` buffer, `rho` source-density buffer, and scratch buffer are zeroed before every arm. The fields are periodic by construction and the source path is disabled by both `source_strength=0` and the zeroed `rho` buffer. There are no particles (`particle_N=0`).

## Measurements and frozen gates

The verifier must finish all 32 steps for all three arms; there is no data-dependent early stop. It records one compact JSON receipt at exactly `res://_diag/process_time/uniform_lapse_receipt.json`. The receipt must preserve, per arm, the coordinate duration, process duration, `dt_coordinate`, `N`, `dt_process`, final process `t`, and explicit provenance strings stating that `pc.dt=dt_process=N*dt_coordinate` and `pc.t=step*dt_process`. It records raw final bytes for EY, EI, and the complete velocity `vec4` buffer as SHA-256 digests plus byte counts. The receipt explicitly says that `q` was not used as a lapse source and was not compared.
The frozen receipt schema is `uniform_lapse_receipt/v1`. Every implementation receipt must identify `candidate_role="uniform_scalar_process_time_reparameterization"` and `default_off_state="production shader unchanged; no new branch; baseline-A/B are the duplicate OFF control"`. It must identify the law as `d2EY_dt2=L(EY)-omega2*(EY-phi*EI); d2EI_dt2=L(EI)+phi*omega2*(EY-phi*EI)` and the operator as `L=existing periodic 19-point two-fluid Laplacian from res://compute/cassi_two_fluid.glsl`, with `pc.dt` as the process-time implementation surface.

The following gates are frozen and all are required:

1. **RD/pipeline/buffer gate:** a local RenderingDevice, the existing shader, compute pipeline, all six storage bindings, and 17-float push constants are valid. A windowed launch is required; `--headless` is not a valid run mode for this GPU probe.
2. **Step gate:** each arm reports exactly `32` completed steps and exactly one pass-A then pass-B pair per step.
3. **Finite-state gate:** every final EY, EI, q, and velocity float returned by the GPU is finite (`not NaN` and `not ±Inf`) in each arm. `q` is checked only for finiteness; it is never a lapse input or equality statistic.
4. **OFF duplicate bit-identity gate:** the raw final EY, EI, and velocity bytes of `baseline-A` and `baseline-B` are exactly equal. This is the default/off reproducibility control.
5. **Equal-process-age identity gate:** the raw final EY, EI, and velocity bytes of `baseline-A` and `uniform-lapse` are exactly equal. This is the implementation identity at equal process age.
6. **Clock bookkeeping gate:** `uniform-lapse.coordinate_duration / baseline-A.coordinate_duration` equals `2.0` within `1e-12`; the two process durations and every sent `pc.dt`/final `pc.t` agree within `1e-12`. The receipt must show the coordinate and process quantities separately.
7. **Hamiltonian bounded-shadow gate:** for every arm, `H_initial` and `H_final` are finite and `abs(H_final-H_initial)/max(abs(H_initial),1e-12) < 0.01`. The strict `<1%` bound is frozen conservatively from the measured completed-form bounded shadow; it is not tuned after this run.
8. **Receipt gate:** the parent directory is created if needed, the JSON is written and re-opened, and its compact receipt contains all three arms, all gate booleans, raw-byte digests/counts, finite-state results, Hamiltonian values/drifts, coordinate/process durations, and the epistemic boundary. Exit status is `0` only if every gate above and the receipt write/re-read pass; otherwise exit status is `1`.

No result may be rescued by changing the grid, seed, step count, constants, threshold, shader, or receipt schema after the run. A failed gate is reported with the frozen `FAIL` vocabulary.

## Expected interpretation and verdict vocabulary

- `PASS_IMPLEMENTATION_ONLY`: all frozen gates pass. This means only that the existing `pc.dt`/`pc.t` surface realizes the specified uniform scalar reparameterization and preserves the equal-process-age canonical state for this deterministic probe.
- `FAIL_IMPLEMENTATION`: any frozen gate fails, including byte identity, finiteness, clock ratio, Hamiltonian bound, or receipt write.
- `INVALID_SETUP`: the local RD/shader/pipeline/buffer/receipt prerequisites are unavailable or the run was not windowed; this is not a physical negative result.

The receipt and console result must repeat: **implementation proof only; not CT-2 evidence; not local coherence-derived lapse evidence; not universal physical-time evidence.** No interpretation may promote coordinate-duration separation into a physical clock claim.
