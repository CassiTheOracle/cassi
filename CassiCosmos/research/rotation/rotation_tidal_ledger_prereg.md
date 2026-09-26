# Live cloud–environment angular-momentum ledger — preregistration

Status: PRE-REGISTERED before implementation and the first run — 2026-09-02

## Question

Can the live Cassi gravity path transfer angular momentum from a resolved cloud–environment orbit into a cloud's internal orbital rotation with the expected nulls, mirror parity, and timestep/resolution convergence; and does the existing merge pass then partition pair-internal orbital angular momentum into survivor spin without losing the total ledger?

This campaign measures the existing production forces and merge shader. It does not add a tidal force, prescribe spin by hand, or use the vector-Qi rotation pass to manufacture the acquisition signal.

## Frozen decomposition

Particles `0..3` are the cloud and `4..5` are the environment. For group `g`, with mass `M_g`, center `R_g`, mean velocity `V_g`, mean acceleration `A_g`, define

- internal angular momentum `S_g = sum_i m_i (r_i-R_g) x (v_i-V_g)`;
- intrinsic torque `tau_g = sum_i m_i (r_i-R_g) x (a_i-A_g)`.

About the whole-system center `(R,V,A)`, define the group-orbit term

`L_orb = sum_g M_g (R_g-R) x (V_g-V)`

and its torque

`tau_orb = sum_g M_g (R_g-R) x (A_g-A)`.

The ledger identity is

`L_total = S_cloud + S_environment + L_orb`.

Every interval uses the actual GPU position, velocity, and cached acceleration buffers. The predicted angular impulse is trapezoidal: `0.5 dt (tau_n + tau_n+1)`. The first production step after a planted state is warm-up only; statistics begin from its completed state so both interval endpoints have live cached accelerations.

## Frozen live gravity setup

- local RenderingDevice, windowed;
- production `CassiPhysicsEngine.run_steps(1)` path;
- six particles, `grid_N=64` except the registered spatial check at 128;
- cube half-extent 20, river self-gravity mode 3, black holes off, meshless/gridless/merge/rotation stress off;
- `G_N=1`, source strength 0, one cluster, fixed seed 86091;
- the canonical two-fluid state is reset before each case to spatially uniform `EY=phi`, `EI=1`, `Q=EY^2+EI^2`, zero FieldVel, then held with the existing `freeze_field=true` diagnostic toggle so the campaign measures gravity rather than concurrent field evolution;
- cloud masses 1 each; environment masses 30 each at `(±8,0,0)`; all initial velocities zero.

The cloud always has two particles at `±a u` and two at `±b v`, where `u=(cos theta,sin theta,0)`, `v=(-sin theta,cos theta,0)`, unless the spherical control is selected. Frozen geometries:

- `sphere`: `(±1.5,0,0)`, `(0,±1.5,0)`;
- `aligned`: `a=2.0`, `b=0.75`, `theta=0 deg`;
- `plus`: `a=2.0`, `b=0.75`, `theta=+45 deg`;
- `minus`: `a=2.0`, `b=0.75`, `theta=-45 deg`.

The primary physical duration after warm-up is `T=0.08`. Runs are:

| Case | Grid | dt | measured intervals |
|---|---:|---:|---:|
| sphere | 64 | 0.005 | 16 |
| aligned | 64 | 0.005 | 16 |
| plus | 64 | 0.010 | 8 |
| plus | 64 | 0.005 | 16 |
| plus | 64 | 0.0025 | 32 |
| minus | 64 | 0.005 | 16 |
| plus | 128 | 0.005 | 16 |

No case-dependent tuning, field reseeding, recentering, or rotation of outputs is allowed.

## Frozen merge partition setup

A separate four-particle local-RD engine uses the production merge path at `grid_N=64`, cube half-extent 37.5, `dt=1e-6`, merge enabled, high coherent uniform field (`EY=phi`, `EI=1`), and gravity/source/rotation stress otherwise inert over that interval.

The merging pair is the established merge-spin fixture:

- masses `(10,10)`, positions `(5,0,0)` and `(5.4,0,0)`;
- velocities `(0,3,0)` and `(0,-5,0)`;
- expected internal pair angular momentum `(0,0,-16)`.

Two tagged environment particles, masses `(5,5)`, sit at `(-15,0,0)` and `(15,0,0)` with zero velocity and remain outside merge range. Exactly one pair must merge. Total momentum and total `orbital + merge_spin` angular momentum are evaluated across every live particle before and after. The environment's own position/velocity/mass bytes must be unchanged to relative `1e-5` over the near-zero-duration merge step.

## Raw and independent receipts

The Godot arm writes `_diag/rotation_tidal_ledger_gpu.json` containing every per-step particle position, velocity, acceleration, the fixed group tags, all configuration values, and pre/post merge state. It may compute convenience summaries, but those are not authoritative.

`research/rotation/rotation_tidal_ledger_verify.py` independently recomputes every center, internal/orbital angular momentum, torque, trapezoidal impulse, gate, and merge ledger from raw arrays. It writes `_diag/rotation_tidal_ledger_verify.json`. Source/raw SHA-256 digests bind the receipt.

## Registered gates

### G86 — live ledger closure

For the primary `plus`, `grid=64`, `dt=0.005` run:

- acquired `|Delta S_cloud| >= 1e-6`;
- cloud impulse closure error `|Delta S_cloud - integral tau_cloud dt| / max(|Delta S_cloud|,|impulse|) <= 0.10`;
- the equivalent environment and mutual-orbit closures are each at most 0.10; and
- total-ledger drift `|Delta L_total| / |Delta S_cloud| <= 0.10`.

### G87 — spherical and aligned nulls

The larger of the spherical and aligned `|Delta S_cloud|` values is at most 0.25 times the primary plus-case signal.

### G88 — mirror parity

The `plus` and `minus` cloud `Delta S_z` values have opposite signs. Their magnitude mismatch divided by their mean magnitude is at most 0.25, and the norm of each run's transverse `(x,y)` acquisition is at most 0.20 of its `|z|` acquisition.

### G89 — timestep convergence

For the three grid-64 plus runs:

- medium/fine `Delta S_cloud` relative difference is at most 0.10;
- coarse/medium difference is not smaller than medium/fine difference minus `1e-4`; and
- the fine cloud impulse-closure error is no larger than the medium error plus `0.01`.

### G90 — spatial convergence

The grid-64 and grid-128 medium-step plus runs have the same `Delta S_z` sign and relative vector difference at most 0.50. This intentionally loose bound detects a branch or normalization failure while acknowledging the known cubic spectral-grid bias; it is not a continuum certification.

### G91 — merge partition

- exactly one pair merges and three of four particles remain live;
- relative total momentum error at most `1e-3`;
- relative total angular-momentum error (including merge spin) at most `1e-3`;
- survivor spin relative error against `(0,0,-16)` at most `1e-3`; and
- tagged environment relative state change at most `1e-5`.

## Decision tree and stopping rule

G86–G91 all PASS: `SUPPORTS_LIVE_TIDAL_ACQUISITION_AND_MERGE_PARTITION`.

Any harness, shader, source-integrity, finite-state, or raw-replay failure: `INCONCLUSIVE—IMPLEMENTATION`.

Valid execution with any physics gate failed: `DOES_NOT_SUPPORT_REGISTERED_TIDAL_LEDGER`. The negative is retained; do not tune geometry, thresholds, duration, or field values and rerun under this preregistration.

Run each listed case once, then run the independent verifier once. The Godot arm may be rerun only to correct a pre-statistic harness defect documented before the rerun.
