# Embodied World-Field Intelligence Pre-registration

## Status: Frozen—2026-08-31

This protocol freezes the first measured test of learned actuation inside the authoritative CassiCosmos Yang/Yin world field before the focused scene is run.

## Scope and ownership

The first implementation is opt-in and limited to the inline periodic-grid path on the global RenderingDevice. `physics_decoupled`, `gridless_physics`, and `meshless_mode` must be off. Unsupported ownership combinations reject startup instead of mirroring learned state or moving it to a second field.

The new persistent state has two GPU buffers:

- `FieldPlasticity.pe[]`, one `vec2` per world-field cell, with slow plasticity $P$ and eligibility $e$;
- one fixed 128-byte `FieldLearningState` header containing reward telemetry, target, probe, organ, bounded control, context, episode status, and faults.

The six actuator lobes are fixed at $\pm x$, $\pm y$, and $\pm z$ around the central field organ. Goal direction is encoded as a spatial offset inside each actuator lobe. The resulting scalar $P$ volume is therefore a target-conditioned six-action policy, not a parallel learned model.

## Frozen update and ordering

For reward $r_t$, eligibility $e$, and plasticity $P$:

$$
e_{t+1}=\gamma e_t+a_t,
$$

$$
P_{t+1}=\operatorname{clip}((1-\lambda)P_t+\eta r_t e_{t+1},-P_{\max},P_{\max}),
$$

$$
r_t=\operatorname{clip}(d_{t-1}-d_t,-1,1)-\lambda_u\lVert u_{t-1}\rVert^2.
$$

Each physics step records, in one owner compute list: existing field and particle dynamics; reward measurement; a storage-buffer barrier; the $P/e$ update; a storage-buffer barrier; next-control selection; and a final barrier before the next PDE step. The phase/plasticity view is recorded after the last learning pass in that same list. No main-RD `submit()` or `sync()` call is admitted.

The learned command enters the ordinary two-fluid pass as a bounded Yang/Yin lobe pulse and as bounded medium flow in the existing `FieldVel` world-field component. Particles receive no direct learned impulse; the existing RealSim viscosity coupling is the actuator surface. The disabled branch must execute the previous field formulas unchanged.

## Deterministic fixture

The focused arm uses:

- one live probe particle, index 0, reset to the organ center with zero velocity at each episode;
- grid $64^3$, fixed periodic box, fixed seed, no black holes, merge, moving home window, tracking envelope, meshless state, or decoupled producer;
- five targets at radius 6 from the organ: $+x$, $-x$, $+y$, $-y$, and $+z$;
- success radius 0.75;
- 216 training steps per target, then 120 frozen-policy replay steps per target;
- deterministic lower-action-ID tie handling at score differences $\le 10^{-6}$.

One shared $P$ volume persists across all five training targets. Eligibility resets at each episode boundary; $P$ does not. Replay freezes $P$ and disables exploration.

## Controls

Two controls run the identical target/reset/step schedule:

1. $\eta=0$, which leaves $P$ at zero;
2. deterministic reward shuffling, which removes the temporal action-outcome association while retaining reward magnitudes and all field dynamics.

The causal intervention captures a trained snapshot, clears only $P/e$ and the compact learning control state, runs the replay schedule, restores the exact snapshot, and repeats the replay schedule.

## Gates

- **FI0—Ownership and ABI:** inline-grid configuration starts; unsupported ownership rejects; plasticity and header sizes are exact; all shader descriptors are bound when FI is both on and off.
- **FI1—Default-off identity:** with FI disabled, the existing two-fluid output buffers remain byte-identical to the frozen paired fixture.
- **FI2—Finite bounded state:** every measured $P$, $e$, reward, command, field, position, and velocity value is finite; $|P|\le P_{\max}$ and each command component is in $[-8,8]$.
- **FI3—Learning causality:** frozen trained replay succeeds on at least 4 of 5 targets; cleared replay succeeds on at most 1 of 5; trained median terminal distance is no more than half the cleared median.
- **FI4—Controls:** the $\eta=0$ control succeeds on at most 1 of 5 targets and deterministically shuffled reward succeeds on at most 2 of 5.
- **FI5—Exact persistence:** capture records sizes, profile fingerprint, and SHA-256; immediate restore reproduces both GPU buffers byte-for-byte; an incompatible profile or checksum rejects without writes.
- **FI6—Restore recovery:** restored replay succeeds on at least 4 of 5 and its terminal-distance vector matches the first trained replay within 0.20 per target.
- **FI7—Render purity:** a paused phase/plasticity render dispatch leaves both learning buffers byte-identical.
- **FI8—Same-list visibility:** the rendered receipt from the owner list identifies the same logical tick read from the learning header after that frame.
- **FI9—Lifecycle:** resources and cached uniform sets are released and rebuilt across reinitialization without errors or orphaned Godot processes.

## Decision tree and stopping rule

A gate is `PASS` only from the focused verifier's measured output. FI0, FI1, FI2, FI5, FI7, FI8, and FI9 are hard correctness gates: any failure blocks adoption. FI3, FI4, and FI6 are behavioral gates: one repair and one rerun are allowed under this unchanged protocol. If the second behavioral run misses any threshold, the result is `REJECT`; thresholds, target radius, and step counts are not changed after observing results. The focused arm runs once after implementation, followed by the full CassiCosmos battery only if all hard gates and behavioral gates pass. The final verdict is `ADOPT`, `REJECT`, or `INCONCLUSIVE`.
