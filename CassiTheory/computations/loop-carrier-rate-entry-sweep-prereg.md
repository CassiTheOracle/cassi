# Loop-carrier rate-entry sweep pre-registration

This body asks one question about the two-coordinate result and answers it in the only form that
is not a tautology.

The two-coordinate body declared the point `r = 0`, predicted `dim ker(mode 0) = 2` before its run,
and measured two retained coordinates with independent injectors. Its retention reading, however,
is a verdict taken *at* the crossing -- and a vanished gap entry *is* a zero decay rate, so a
coordinate that stands still over a declared window cannot be separated from a coordinate whose
window happened to be short. The non-tautological form of the same question is a **sweep through
the crossing**: declared points on both sides of `r = 0`, the state off equilibrium at every point,
and at every point the **fitted decay rate of the declared coordinate against the gap entry**,
read with one declared estimator over one declared window and published beside the **window's own
clock** -- the same estimator applied to a companion arm whose rate is the conversion entry of
(LB39), independent of `r`. What makes that a measurement is a rate that goes to zero linearly in
the entry across the range, at both signs, with the fit's own quality readings beside it.

The dialled coefficient is the exchange `r` of (LB42), whose entry in (LB39) is `2r`. The protocol
below declares the points, the seeds, the reader, the estimator, the thresholds, the arms, the
gates and the branches **before** the single invocation. The reading domain is the two-coordinate
body's own declared one and is proved again here, against that body's executor bytes.

Sections 1 to 7 are the frozen body: section 0 and section 8 may be written around them, and the
frozen pair is only ever extended in place with a marker that names what it read before.

## 0. Bound sources and the frozen pair

Every row below is a file whose bytes this executor reads, hashes and refuses on. None is a running
process, a clock or a machine threshold. The two rows marked *at freeze* are printed by
`--freeze` and pasted here; the frozen body is everything from `## 1.` to just before `## 8.`.

| row | value | what it binds |
| --- | --- | --- |
| `frozen_body_sha256` | `97f8bf764dbfb7f2da845a465c1102c0b84143f7e353354aa97c1d30dfc92f2e` | sections 1-7 of this file, at freeze |
| `executor_sha256` | `b4b6aea7bf6a6192030de4aad7d478a13c86a9f0a166d49c3b68cf070a7eb05d` | this body's own executor, at the re-anchoring that followed its invocation; the bytes this body ran against were `c1a8d490…` |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | the frozen operator module (LB1)-(LB7) |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | the successor probe that executes them |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | the projection split |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` | the gate-load chain |
| `prior_executor_sha256` | `3852eadbd434e021d1dc351820db06e6295c34c11270144b0826f6097b09f6b1` | the composition coexistence body |
| `audit_executor_sha256` | `0503f109c8b431768fbe16d37dfe8a82dec18cce2f97dc417d2fb08d1474f07a` | the kernel-dimension audit (§71) |
| `write_executor_sha256` | `740d0fc036721be5f1ee0fd5527fe54e771243113e13b7133be053f6439cf6c6` | the attractor-write body (the clock oracle) |
| `first_invocation_receipt_sha256` | `cdfb45468af1ebdcf1bfc21828f78a502d396c9dd484251114814db340dcd6ec` | the archived first invocation of this body (`runs/loop_carrier_rate_entry_sweep/first-invocation-verification.json`) |
| `two_coordinate_executor_sha256` | `7f78244067def849dd5d9f287f45a34937e57bd1912b7744b42cf0ed6812be00` | the two-coordinate body's own reader, kernel check and domain probes; the bytes this body ran against were `671e4a5e…`, re-anchored after this sweep ran, when section 6 of that body gained one sentence at the user's instruction (§8 records it) |
| `two_coordinate_receipt_sha256` | `46ae3ee2b93051277c6e1c86dce4c713fb3b397d74cb06c2559ff8e7b98f344e` | its receipt, the zero-rate and erase oracles |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | the relaxation receipt |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | the split receipt |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` | the gate-load receipt |
| `prior_receipt_sha256` | `5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200` | the coexistence receipt |
| `coexistence_receipt_sha256` | `9724143b98cf394eb9948741d3a117c4cc1e4b14fe54ff2ad9e81dfddb8bf60f` | the coexistence body's receipt |

The two rows at the top were re-anchored at the second freeze. *Amended in place:* at the first
freeze this table read `frozen_body_sha256 = f81a4776f736d91d6724d08c10fbdb14ca81f775934dc38ab03c0f76775224d5`
and `executor_sha256 = e70007614ab45d83b9eb835297354bd8465b6a9abc89986dc19b4b329fd22b7d`, and the
single invocation of that pair integrated all twenty-nine arms and wrote
`runs/loop_carrier_rate_entry_sweep/first-invocation-verification.json` -- the receipt preserved
byte for byte under the row above -- with status `FAIL` and gate 8 as its only failure, on readings
that satisfy that gate's bound as this text now states it. Section 8 records what the failure was,
why it is a defect in this section's own gate sentence rather than a finding about the sweep, the
amendment that follows from it, and both invocations with their digests.

## 1. Definitions

### 1.1 The declared points and their entries

The dialled coefficient is the exchange `r` of (LB42). Its entry in (LB39) is `2r`, and at every
declared point the frozen closed spectrum of the mode-0 generator must carry the declared four
values on the nose: `{0, -2r, -k(1+phi), -k(1+phi)-2r}` with `k = ENTRY_KAPPA / (1 + phi)` the
frozen module's own per-carrier conversion coefficient. The entries are read at run time from the
frozen `closed_spectrum`; the table below is the declaration they are checked against, and the
runner's mode-0 generator is checked against the same four values by the same multiset residual the
§71 audit used.

| row | value | meaning |
| --- | --- | --- |
| `entry_exchange` | `0.0` | the crossing, the two-coordinate body's declared point |
| `exchange_spent` | `0.6` | the spent chain's declared point, carried for the kernel comparison |
| `canfail_exchange` | `0.5` | the can-fail control's exchange |
| `canfail_entry` | `1.0` | its entry: fifty times the largest swept entry |
| `witness_exchange` | `0.25` | the extrapolation witness's exchange |
| `witness_entry` | `0.5` | its entry: twenty-five times the largest swept entry |
| `kappa_mode_zero` | `0.0043041004594355226` | `ENTRY_KAPPA / (1 + phi)`, the per-carrier coefficient |
| `conversion_entry_declared` | `0.011268281293796237` | `k(1+phi)`, the conversion entry of (LB39) |
| `conversion_clock_oracle` | `0.01119569724312185` | the chain's own recorded clock, from the write body |

The seven swept points, their exchanges and their entries:

| point | exchange `r` | entry `2r` |
| --- | --- | --- |
| 1 | `-0.0100` | `-0.02` |
| 2 | `-0.0050` | `-0.01` |
| 3 | `-0.0025` | `-0.005` |
| 4 | `0.0` | `0` |
| 5 | `0.0025` | `0.005` |
| 6 | `0.0050` | `0.01` |
| 7 | `0.0100` | `0.02` |

### 1.2 The declared seed

At every declared point the sweep's seed is the frozen `on_ray` family in its chi-uniform,
exterior-flat restriction, with the same orientation imbalance on both carriers:

    f_{a,s}(x, chi) = (E_a / 2) (1 + s beta),   a in {Y, I},   s in {+1, -1},
    E_Y : E_I = phi : 1   (the frozen `on_ray` profile),
    imbalance beta = 0.01, no exterior and no loop modulation.

The load arms carry the chain's own declared transfer, applied to the same seed per orientation:
`f_Y <- f_Y + (c/2) rho`, `f_I <- f_I - (c/2) rho` with `rho` the seed's own local total, so the
total is preserved and the bracket `B = -f_Y + phi f_I` becomes `-(c/2)(1 + phi) rho`.

**Why the sweep can be exact.** The seed has `epsilon = e_Y - phi e_I = 0` **pointwise**, so the
conversion term of (LB6) vanishes identically; the state is uniform in the exterior and in the
loop, so both transports vanish and the gate rate is a single scalar; the evolution is therefore
exactly the frozen generator's uniform four-vector `(Y_up, Y_down, I_up, I_down)`. That generator
is a Kronecker sum -- `conversion` on the carrier axis, `direction` on the orientation axis -- so
its spectrum is `{0, -2r, -k(1+phi), -k(1+phi)-2r}` and the swing the imbalance creates lies
exactly on `u_0 (x) v_1` (the equilibrium-ratio direction, orientation-antisymmetric), whose
eigenvalue is `-2r` alone. **The state's antisymmetric amplitude therefore decays exactly at the
entry, at every declared point, on both sides of the crossing.** The load arm's transfer lies on
`u_1 (x) v_0` (the conversion's non-kernel direction, orientation-symmetric), whose eigenvalue is
`-k(1+phi)` alone: its signal decays exactly at the conversion entry and the exchange annihilates
it exactly, which is what makes it the window's own clock rather than a per-point reading.

The seed's antisymmetric content is decomposed on the declared direction `w0 = (phi, 1)` and on the
complementary `w1 = (1, -phi)`; the fraction on `w1` and the pointwise epsilon are both gated.

### 1.3 The declared coordinate

The measured coordinate is the frozen bounded composition

    q(e_Y, e_I) = rho^2 / (rho^2 + phi^-2 + epsilon^2),  rho = e_Y + e_I,  epsilon = e_Y - phi e_I,

read pointwise on the two carrier fields and averaged over the exterior axis, so that the reading
is indexed by the loop sample and partitioned by the field's own orientation group:

    profile = mean_x q(f_{Y,0}, f_{I,0}) and mean_x q(f_{Y,1}, f_{I,1})   (2, 24)
    even    = (profile[0] + profile[1]) / 2      odd = (profile[0] - profile[1]) / 2

The **entry arm's declared series is the odd group's mean over the loop**: it is zero on the ray
(`epsilon = 0` at both orientations gives `q = rho^2/(rho^2 + phi^-2)`, the same at both
orientations) and it is the imbalance's own nonlinear image. It is not linear in the amplitude --
`q` carries `rho^2` and `epsilon^2` -- so the fitted rate is `2r` times a correction of order
`beta^2`, and gating the fit's own residual is part of the measurement. The **clock arm's declared
series is the ray distance** `max|epsilon| / max(1, max|rho|)` of the arm's own projection, which
is exactly proportional to the decaying conversion mode.

### 1.4 The declared estimator

One estimator, applied to every series this body reads, at every point:

    pairs = samples with |v| >= READABLE_FLOOR_Q
    require len(pairs) >= FIT_MIN_SAMPLES
    fit  ln|v| = a - rate * t   by least squares over pairs
    require one sign throughout the pairs
    residual = max |exp(a - rate t) - |v|| / |v|   over pairs

The estimator is signed (a rising series reads negative), issues no rate when fewer than
`FIT_MIN_SAMPLES` samples clear the floor, and reports its own residual and sign constancy beside
the rate. The same estimator, the same stride and the same window length are used on the entry
coordinate at every point and on the clock at every point.

### 1.5 The design probe's declared readings

`--design-probe` runs every arm once, prints the readings below in this order, and writes nothing.
The values are pasted here before the freeze and the invocation must reproduce every one of them
within `PROBE_TOL` relative (gate 7), so the invocation cannot silently run a different
integration from the one the thresholds were chosen against.

| index | reading | declared value |
| --- | --- | --- |
| 1 | `entry@-0.0100:rate` | `-0.020087210596378125` |
| 2 | `entry@-0.0050:rate` | `-0.010005319983069205` |
| 3 | `entry@-0.0025:rate` | `-0.005001058250020064` |
| 4 | `entry@+0.0000:rate` | `2.4880630605367724e-17` |
| 5 | `entry@+0.0025:rate` | `0.005000236194936966` |
| 6 | `entry@+0.0050:rate` | `0.010000265174148837` |
| 7 | `entry@+0.0100:rate` | `0.02000022063745508` |
| 8 | `entry@-0.0100:odd_initial` | `0.004390337204869366` |
| 9 | `entry@-0.0025:odd_initial` | `0.004390337204869366` |
| 10 | `entry@+0.0025:odd_initial` | `0.004390337204869366` |
| 11 | `entry@+0.0100:odd_initial` | `0.004390337204869366` |
| 12 | `clock@-0.0100:rate` | `0.011282357172592223` |
| 13 | `clock@+0.0000:rate` | `0.011282357172592223` |
| 14 | `clock@+0.0100:rate` | `0.011282357172592223` |
| 15 | `canfail@+0.5000:rate` | `1.0000059865642859` |
| 16 | `witness@+0.2500:rate` | `0.5000075974138588` |
| 17 | `inject@+0.0000:even_part` | `0.0` |
| 18 | `inject@+0.0000:odd_part` | `-0.0014358387617779411` |
| 19 | `inject@-0.0100:even_part` | `0.0` |
| 20 | `inject@-0.0100:odd_part` | `-0.012646830210309101` |
| 21 | `inject@+0.0000:erase_fraction` | `0.7715799746327933` |
| 22 | `inject@-0.0100:erase_fraction` | `0.3690299651437342` |

The probe also prints the two readings the thresholds below are chosen against and which are *not*
gated by reproduction because they are declared afterwards: the largest fit residual over the entry
arms, and the entry coordinate's own first-sample magnitude.

## 2. Thresholds and the declared branches

### 2.1 The rate branch

The branch is selected from the seven per-point comparisons `|rate - entry| <= tolerance` with
`tolerance = max(|entry| * ENTRY_TOL_RELATIVE, ENTRY_ZERO_CEILING)`, and from the fit's own quality
and the clock's readings. The four labels and their rules, declared before the run:

| label | rule |
| --- | --- |
| `LINEAR_BOTH_SIDES` | every positive-entry point, every negative-entry point and the crossing point pass, and every fit is readable and within the residual ceiling |
| `FLAT` | every fitted rate is within `FLAT_CEILING` of zero, so the coordinate's decay is not the entry away from the crossing |
| `ONE_SIDE_ONLY` | exactly one of the two sides passes together with the crossing point, and the other does not |
| `INCONCLUSIVE` | any fit fails its own quality conditions, or any clock reading is outside its band, or neither side passes |

`sweep_slope` (the least-squares slope of the fitted rates on the declared entries) is reported
beside the branch as the reading's own shape and is a reported feature, not a gate.

### 2.2 The injector's law

At each of the two declared injector points the runner drives the orientation channel from the same
loaded seed twice, with the drive at its own sign and with the drive reversed, and reports

    plus  = odd_end(plus arm)  - odd_end(the point's clock arm)
    minus = odd_end(minus arm) - odd_end(the point's clock arm)
    even_part = (plus + minus) / 2      odd_part = (plus - minus) / 2

`even_part` is the response that does not flip when the drive flips and `odd_part` the response
that does. A third arm at each point repeats the drive in its first phase, applies the **reversed**
drive in its second phase and nothing in its third, and the fraction a reversed channel removes is
`erase_fraction = 1 - |erase| / |plus|`, reported beside the `0.66%` the two-coordinate body's
erasure branch read.

| label | rule |
| --- | --- |
| `EVEN_IN_SIGN` | the response is readable and `|odd_part| <= INJECTOR_EVEN_CEILING * |even_part|`, so the coordinate stores the drive's magnitude and not its sign |
| `SIGN_DEPENDENT` | the response is readable and the odd part is not small against the even part, so the write is signed |
| `RESERVED_NO_RESPONSE` | the response is below `READABLE_FLOOR_Q`: the channel wrote nothing measurable at this seed |

Section 8 states the law in one sentence, from these readings.

### 2.3 The declared thresholds

| row | value | meaning |
| --- | --- | --- |
| `readable_floor_q` | `1.0e-12` | a sample's magnitude must clear this to enter a fit |
| `entry_tol_relative` | `1.0e-2` | the entry band, relative to the point's own entry: the reader is quadratic in the amplitude, so the fitted rate carries an `O(beta^2)` correction, and the design probe measured the largest departure at `4.4e-3`; the band is that with headroom |
| `entry_zero_ceiling` | `1.0e-6` | the absolute ceiling at the crossing, where the entry is zero |
| `flat_ceiling` | `1.0e-4` | every fitted rate must clear this for the `FLAT` branch |
| `fit_residual_ceiling` | `2.0e-2` | the fitted exponential's largest relative departure from its series: the design probe measured `8.5e-3` at the widest point, which is the declared `O(beta^2)` nonlinearity and not noise, so the ceiling is that with headroom |
| `fit_min_samples` | `4` | samples above the readable floor needed to issue a rate |
| `canfail_band_relative` | `1.0e-3` | the can-fail and witness arms' band against their entries |
| `canfail_floor` | `1.0` | the can-fail arm's fitted rate must also exceed this |
| `ray_readable_floor` | `1.0e-6` | the clock's ray distance at the first sample |
| `seed_content_ceiling` | `1.0e-12` | the seed's antisymmetric content allowed on the complementary direction |
| `seed_epsilon_ceiling` | `1.0e-14` | the seed's pointwise `epsilon` allowed above zero: the frozen profile's ratio is exact in real arithmetic and its two densities are floats, so `phi E_I` differs from `E_Y` by round-off and no more |
| `injector_even_ceiling` | `5.0e-2` | `|odd_part| / |even_part|` below which the write is called even in its sign |
| `probe_tol` | `1.0e-12` | gate 7's tolerance on the declared probe readings, taken against the larger of the reading and one, so the crossing's round-off-level rate is pinned absolutely rather than by its own magnitude |
| `domain_chi_floor` | `1.0e-3` | the loop-only probe's row spread through the declared reader |
| `domain_exterior_ceiling` | `1.0e-15` | the exterior-only probe's row spread through the declared reader |
| `beta` | `0.01` | the declared orientation imbalance |
| `load_transfer` | `0.02` | the declared load of the load arms, ten times below the chain's largest |
| `load_transfer_tol` | `1.0e-13` | the transfer's relative error, in the total it preserves and in the `epsilon` it creates: the latter is a difference of `O(1)` densities, so its own round-off is amplified by that cancellation |
| `drive_delta` | `0.2` | the orientation drive's own declared magnitude |
| `window_units` | `150.0` | the common window, in units of time |
| `window_steps` | `7500` | the common window, in steps of dt = 0.02 |
| `sample_stride` | `250` | the common sampling stride, in steps |
| `short_units` | `5.0` | the can-fail and witness arms' window |
| `short_steps` | `250` | the short window, in steps |
| `phase_steps` | `2500` | the injector arms' phase length, in steps |
| `declared_executions` | `29` | the arms below |
| `per_execution_cap` | `10000` | steps per execution |
| `total_step_cap` | `250000` | steps in total |
| `bound_seconds` | `600.0` | the invocation's declared cost bound |

`CLOCK_TOLERANCE` (= 2.0, the chain's own factor band) and `FIT_MIN_SAMPLES` are the chain's; the
clock's own gate here is the tighter one: each point's fitted ray-distance rate must be within
`entry_tol_relative` of the conversion entry **measured at that point's own clock seed**, because
the clock's rate is not fitted against a typed constant but read from the frozen gate and the
frozen projection.

## 3. The declared arms

Twenty-nine arms in one process. Per declared point, three arms of the same window:

| arm | seed | dynamics | declared reading |
| --- | --- | --- | --- |
| `entry@r` | imbalance `beta`, no load | the frozen (LB6) line at `r` | the odd group's fitted rate against `2r` |
| `clock@r` | no imbalance, load `c` | the same line at `r` | the ray distance's fitted rate against the conversion entry at its own seed |
| `ray@r` | the profile exactly | the same line at `r` | the frozen fixed point: the state must not move at all |

Two arms on the short window test the law outside the swept band: `canfail@+0.5000` (entry `1.0`,
fifty times the largest swept entry) and `witness@+0.2500` (entry `0.5`, twenty-five times it).
Both must read their own entries within `CANFAIL_BAND_RELATIVE`.

At `r = 0` and `r = -0.01`, three driven arms each, from the loaded seed, with the phases
`(+, +, +)`, `(-, -, -)` and `(+, -, none)` held for `phase_steps` each: `inject_plus`,
`inject_minus` and `erase`. Their baseline is the point's own clock arm, whose seed is the same
loaded seed with no drive.

Schedules: `dt = 0.02` on every arm, chosen by the frozen step rule `dt <= 1/(STEP_SAFETY *
lambda_max)` with `STEP_SAFETY = 40` over the candidates `(0.05, 0.02, 0.01)`. `lambda_max` is
taken over the seed's own mode (0) **and** the chain's declared mode (1), so the rule is not
weakened by this body's choice of a chi-uniform seed; the can-fail arm is the binding one at
`r = 0.5`. `declared_executions = 29`, `per_execution_cap = 10000`, `total_step_cap = 250000`.

## 4. The gates and the reported features

Fourteen gates, all conjunctive, and the status is a `PASS` only if every one holds. None of them
selects a branch; every declared branch is a recorded finding.

1. **binding** -- every section-0 row matches what this executor hashes.
2. **reading domain** -- this body's reader resolves the loop-only probe (`>= DOMAIN_CHI_FLOOR`),
   averages the exterior-only probe out (`<= DOMAIN_EXTERIOR_CEILING`), is not the spent reader,
   agrees with it on the chi-uniform mean, and is bit-equal to the two-coordinate body's reader on
   all three declared-shaped probes.
3. **structure** -- every recorded state is nonnegative and every composition lies in `[0, 1)`.
4. **schedule and budget** -- 29 executions, `<= 10000` steps each, `<= 250000` in total, and the
   step rule satisfied on every arm's own exchange.
5. **the entries** -- each point's frozen closed spectrum equals `{0, -2r, -k(1+phi), -k(1+phi)-2r}`
   to `SPECTRUM_MULTISET_TOL`, the runner's stored generator reproduces the closed form to
   `REPLICATION_TOL`, and the four-value multiset residual is printed for every point.
6. **the kernel at every declared point** -- `dim ker(mode 0) = 2` at `r = 0` and `1` at every other
   declared point, the surviving direction direction-symmetric, the antisymmetric direction present
   only at the crossing, and its direction's epsilon residual within `KERNEL_SPAN_TOL`. This is the
   §71-style prediction, declared here **before** the run.
7. **design probe reproduction** -- every reading declared in section 1.5, within `PROBE_TOL`.
8. **the seed's declaration** -- the content on the complementary direction is `<=
   SEED_CONTENT_CEILING` on every recorded seed; the pointwise epsilon is within
   `SEED_EPSILON_CEILING` of zero on every **entry and ray** seed; and a seed that carries the load
   transfer is held instead to the transfer's own declared value within `LOAD_TRANSFER_TOL`. The
   epsilon ceiling is round-off and not a modelling residual: the frozen `on_ray` profile is exact
   in real arithmetic, while its two densities are floats, so `phi E_I` differs from `E_Y` by one
   unit in the last place and the conversion term is correspondingly small rather than zero. *Amended
   in place at the second freeze:* this gate as first frozen applied the epsilon condition to every
   recorded seed without excluding the load arms, whose whole declared purpose in section 1.2 is to
   carry the transfer's `epsilon` and to serve as the window's own clock; the first invocation read
   that sentence literally and failed on readings that satisfy the bound stated here. Section 8.1
   carries the pre-amendment wording, both states of the frozen pair and the repair.
9. **silence on every ray arm** -- the state's digest before and after the window is the same on
   every ray arm, and the same at every point; and, as the control that shows the digest can tell a
   fixed point from a moving state rather than being equal by construction, the first two entry
   arms' own first and last digests must differ. *Amended in place at the second freeze:* the gate
   as first frozen carried no such control.
10. **readable on every declared arm** -- the entry coordinate's first sample `>= READABLE_FLOOR_Q`
    and the clock's ray distance's first sample `>= RAY_READABLE_FLOOR`.
11. **can-fail at fifty times the largest swept entry** -- the short-window arm at `r = 0.5` reads
    its own entry within `CANFAIL_BAND_RELATIVE` and above `CANFAIL_FLOOR`.
12. **the window's own clock at every point** -- every point's ray-distance rate within
    `ENTRY_TOL_RELATIVE` of the conversion entry at its own seed, and the clock arms bit-identical
    across the whole sweep.
13. **the fit's own quality** -- on every entry arm, at least `FIT_MIN_SAMPLES` samples above the
    floor, one sign throughout, and a residual within `FIT_RESIDUAL_CEILING`.
14. **single invocation** -- the receipt was absent at the start and one process wrote it, and the
   invocation that preceded this one is archived at the path section 0 binds and matches that row.
   *Amended in place at the second freeze:* the gate as first frozen read "the receipt was absent at
   the start and one process wrote it", with no reading that says which invocation it was.

Reported features, deliberately not gated: `F1_can_fail_fired`, `F2_ray_silent`, `F3_readable`,
`F4_clock_uniform`, `F5_seed_pure`, `F6_fit_quality`, `F7_rate_linear_in_entry` (the slope),
`F8_injector_law`, `F9_witness_at_twenty_five_times`, `F10_erase_fraction_largest`, and the two
branch labels themselves.

## 5. Replication against the bodies this continues

The three two-coordinate oracles this body reads, declared as rows so a receipt cannot drift
silently under them:

| row | value | meaning |
| --- | --- | --- |
| `two_coordinate_retained_share` | `0.9999998175949137` | the crossing coordinate's retained share in the two-coordinate receipt |
| `two_coordinate_channel_window` | `450.0` | the window that share stood over, in units of time |
| `two_coordinate_erase_residual` | `0.0066` | the fraction of the written charge its erasure branch removed |

| reading | source | how it is compared |
| --- | --- | --- |
| the crossing's zero rate | the two-coordinate receipt's retained share `0.9999998175949137` over a 450-unit window | the bound `-ln(share)/450` is printed beside the crossing point's fitted rate; the fitted rate may not exceed it |
| the erased fraction | the two-coordinate erasure branch's `RESIDUAL = 0.66%` | this body's `erase_fraction` at both injector points is printed beside it |
| the clock | the write body's own recorded `NU_REFERENCE` | the measured clock reference and its ratio to the oracle are printed, with the chain's factor band of `CLOCK_TOLERANCE = 2.0` |
| the entries | the frozen closed spectrum | the four values and the multiset residual at every point |
| the kernel's labels | the §71 audit's own two labels at the free point | the direction labels are re-read through the two-coordinate body's check |
| the reader | the two-coordinate body's reader | bit-equality on all three declared-shaped probes |

## 6. Cost, invocation and the budget

One invocation, one process:

    timeout 600 python computations/verify_loop_carrier_rate_entry_sweep.py

`bound_seconds = 600.0` is a **cost** bound. It moves no statistic, threshold, tolerance, arm or
decision rule; the arm table, the schedules, the estimator, the gates and the branches are fixed
above and are identical whatever the wall-clock reading turns out to be. The chain's own measured
cost is `1.195e-3` seconds per step, on this machine and library, which puts the declared
`203000` steps at about `245` seconds; the assumption the chain's earlier bodies recorded is
`8.36e-4` seconds per step, which puts them at about `170` seconds. The budget fields are recorded
in the receipt.

*Amended in place at the second freeze.* As first frozen this section read: "If the invocation is
interrupted before it writes a receipt, the honest procedure is: leave the record as it stands,
state in section 8 that the invocation wrote nothing, and re-run once. A second invocation is
permitted only that way; the executor refuses a third, and refuses outright if the receipt already
exists."

That rule was written for an invocation that dies before writing anything, and the invocation of
the first freeze did not: it integrated every arm and wrote a receipt, with status `FAIL` and a
single failing gate whose sentence was defective (section 8.1). The amended rule, and the one this
body is now run under, is: the first invocation's receipt stands in the record byte for byte at
`runs/loop_carrier_rate_entry_sweep/first-invocation-verification.json`, bound as a section-0 row;
the amendment of section 4 raises the frozen pair to its second state; exactly one further
invocation is permitted, against **that** state and no other; the executor refuses to run while the
declared receipt path is occupied, refuses to run without the archived first invocation in place
and matching its bound row, and so refuses a third by construction. Nothing here moves a statistic,
a threshold, a tolerance, an arm or a decision rule: what changed is one gate's sentence, which had
been written so that it contradicted section 1.2, plus the two readings that make the record
self-describing.

## 7. What would falsify this

- A rate that does not track its entry at one of the two signs, with every gate passing, is a
  `ONE_SIDE_ONLY` finding: the coordinate's decay is the entry on one side of the crossing only.
- Every rate inside `FLAT_CEILING` is a `FLAT` finding: the coordinate's decay is not the entry
  away from the declared point, and the two-coordinate body's reading does not extend.
- A residual above `FIT_RESIDUAL_CEILING`, a rate issued from fewer than `FIT_MIN_SAMPLES` samples,
  or a series that changes sign inside the window makes the fit unreadable and the branch
  `INCONCLUSIVE`; the readings are still printed.
- A can-fail arm that does not read `1.0` means the estimator cannot see a rate fifty times the
  swept band, and every other reading in this body is worthless: the run `FAIL`s.
- A clock whose rate is not the conversion entry at its own seed means the window is not the window
  the entries are quoted in: the run `FAIL`s.
- A ray arm that moves at all falsifies the exactness argument of section 1.2: the run `FAIL`s.
## 8. Post-execution record

### 8.1 The frozen pair, the amendment, and the checks that can fire

The body was frozen once, invoked once, amended once and invoked once more. The pairs, with their
digests, so the record can be read without reconstruction:

| state | protocol body | executor | invocation against it |
| --- | --- | --- | --- |
| first freeze | `f81a4776f736d91d6724d08c10fbdb14ca81f775934dc38ab03c0f76775224d5` | `e70007614ab45d83b9eb835297354bd8465b6a9abc89986dc19b4b329fd22b7d` | invocation 1: `FAIL`, receipt `cdfb4546...`, archived |
| amendment, first print | `97f8bf764dbfb7f2da845a465c1102c0b84143f7e353354aa97c1d30dfc92f2e` | `9272d7f2c2de167ddd378e678a8b98f297007a9fd8a39196fe879b04fc59a2ac` | none: the static pass refused it on its own `executor_sha256` row |
| second freeze (as invoked) | `97f8bf764dbfb7f2da845a465c1102c0b84143f7e353354aa97c1d30dfc92f2e` | `c1a8d490bc85792507a2fef654a70a9efd4fe2545c0a8b53ca4861513aa03777` | invocation 2: `PASS`, receipt `318a2ac64f60b5c52cafd21014d008c40483ed7abc9287df4d4f0d9f19d2cd18` |

The whole-file digest of this protocol as it stood at invocation 1, recomputed from the committed
blob rather than quoted, is `e297111884198ebe83705cb054081949c5e10ca6e4fab775b4a320aca3c0f700`, and
its frozen-body read is the first-freeze state in the table above. The file's digest *after* this
section is written is not quoted here, because a file cannot carry a stable digest of itself: what
this section can carry, and does, is the frozen body's, which is read from `## 1.` up to `## 8.` and
is therefore independent of section 0 and this section. The final whole-file bytes are the commit's
blob and the two receipts' `protocol_body_sha256` rows.

**The failure.** Invocation 1 integrated all twenty-nine arms in 71.0 s and wrote a receipt with
status `FAIL`, gate 8 its only failing gate. Its payload satisfies the gate's bound as this text
now states it: the largest complementary-direction content over every recorded seed is
`6.43409935811099e-15` against a ceiling of `1.0e-12`; the largest pointwise epsilon over the entry
and ray seeds is `1.1102230246251565e-16` against `1.0e-14`; and the largest load-carrying seed's
epsilon gap against the transfer's own declared value is `1.9358780408866356e-15` against
`1.0e-13`. What failed was the *predicate*: as first frozen it applied the pointwise-epsilon
condition to **every recorded seed**, including the load arms whose whole declared purpose in
section 1.2 is to carry the transfer's `epsilon` and to serve as the window's own clock. The
gate's own sentence said "on every sweep seed"; the code read every seed. The code was therefore
stricter than the declaration, and it fired on the body's own clock.

**What the amendment moved, and what it did not.** One gate's sentence and predicate (gate 8), one
added control in gate 9's reading, one added reading in gate 14, the rule in section 6 that governs
a second invocation, the section-0 re-anchoring, and the binding of the archived first receipt.
**No statistic, threshold, tolerance, arm, schedule or decision rule moved**: `ENTRY_TOL_RELATIVE`
and `FIT_RESIDUAL_CEILING` were set from the design probe *before* the first freeze, every other
threshold in section 2.3 is unchanged, and the twenty-nine arms, their seeds, their windows, their
stride, the estimator, the four branch labels and their rules are identical in both states. The
two budgets are the two states' own: `bound_seconds = 600.0` in both, and the first state's
receipt records the same 203000 steps and the same 29 executions.

**No partial artifact.** The first invocation left the declared receipt path holding one complete
receipt and nothing else: the run's `runs/loop_carrier_rate_entry_sweep/` directory held exactly
that file, of 451426 bytes, and the second invocation began with that path *free* -- the first
receipt standing byte for byte at the archived path section 0 binds, its digest unchanged
(`cdfb45468af1ebdcf1bfc21828f78a502d396c9dd484251114814db340dcd6ec`) across the move.

**The refusals, as observed.** With the first receipt in place, a further invocation was attempted
and refused before any arm was constructed:

    REFUSING TO RUN: runs/loop_carrier_rate_entry_sweep/verification.json already exists; this
    body is invoked once and a second invocation is permitted only after an invocation that wrote
    no receipt.

That message is the *pre-amendment* guard's own text, quoted from the pre-amendment executor; the
amended guard says "invoked once per freeze and a further invocation is refused outright" and, in
addition, refuses to run at all when the archived first invocation is absent or does not match its
section-0 row. After invocation 2 the declared path is occupied again, so a third is refused by the
same mechanism, and gate 14's reading records which invocation it is.

**The checks can fire, and were made to.** Every reading below is a deliberate perturbation with
the bytes restored afterwards, digests verified:

| check | perturbation | observed |
| --- | --- | --- |
| gate 8, epsilon half | `SEED_EPSILON_CEILING = 0.0` | `passed: false` |
| gate 8, load half | `LOAD_TRANSFER_TOL = 0.0` | `passed: false` |
| gate 7 | one declared probe reading moved by `1e-6` | `passed: false`, mismatch at position 14: declared `1.0000069865642858` against observed `1.0000059865642859` |
| gate 1's binding | one byte flipped in the bound archive | `REFUSING TO RUN: source binding failed`, `first_invocation_receipt_sha256: 240bf498... != cdfb4546...` |
| gate 9 | none needed | the control is in the receipt: `entry@-0.0100` first digest `9155605c8a7a` against its last `d3ea331969df`, so the digest separates a fixed point from a moving state rather than being equal by construction |
| the whole gate path | none needed | invocation 1 *is* the firing witness: the path produced a `FAIL` with a named gate on a real run |

A planted defect of the class that cost this body its first invocation was also proved caught before
the freeze: removing the per-point `clock_rate` key that gates 12 and 14 and the probe path read
makes the static pass report `the gate, feature and receipt path fails on shaped inputs:
KeyError: 'clock_rate'`, and renaming the pre-flight's `step_rule` key makes the static checker
itself stop with `KeyError: 'step_rule'` rather than a tidy message.

**Ruling (director).** An **instrument repair** is permitted once, and only against a contradiction
*inside* the frozen text: here gate 8's pointwise-epsilon predicate could not be honored together
with §1.2's declaration that the load seeds carry the transfer's epsilon and serve as the clock, so
the executor contradicted the body it implements. Permitted only with all four conditions met — the
failed receipt preserved byte-for-byte and bound as a §0 row, no statistic, threshold, tolerance,
arm, schedule or decision rule moved, the repaired predicate proven to fire in both directions, and
in-place amendment markers naming the pre-amendment text. A **measurement outcome is never
repairable**: a reading that comes out against a declared branch, or a gate whose criterion is
merely inconvenient once a number is visible, stands as the verdict, and the correction is a new
protocol. The test that separates the two: does the amendment change *what counts as evidence*? If
it does, it is a new body.

This body stands against that ruling as an instrument repair and does not reach into it again: the
four conditions are the archived and bound receipt above, the sentence in 8.1 that no statistic,
threshold, tolerance, arm, schedule or decision rule moved, the firing table in 8.1 where gate 8
fails with either ceiling zeroed, and the in-place markers section 0, section 4 and section 6 carry
naming what they read before. The refusal of a third invocation is kept exactly as it is, the
sweep's readings stand as its verdict, and any correction that changed what counts as evidence
would be a new protocol rather than an amendment to this one.

**The downstream re-anchoring, recorded because the standing section-0 rows moved after this body
ran.** After invocation 2 the two-coordinate body's section 6 gained one sentence at the user's
instruction — its cost bound is enforced by the `timeout` wrapper on its invocation line and its
projection rows are estimates rather than bounds, and that body's own §8.1 carries the fourth state
of its frozen pair. Its executor's body-digest constant was re-anchored to follow, so the standing
row here for `two_coordinate_executor_sha256` now reads
`7f78244067def849dd5d9f287f45a34937e57bd1912b7744b42cf0ed6812be00`, while this body's receipt and
its archived first invocation both record `671e4a5e…` — the bytes both invocations actually ran
against. This body's own executor was re-anchored the same way so that its row could follow, from
`c1a8d490…` to `b4b6aea7…`. Nothing inside this body's frozen range moved, no declared value of this
body moved, and neither of its readings is affected: the difference is two binding rows quoting
another file's digest, and one sentence in the body that follows.

### 8.2 The invocation

Invoked once against the second freeze, as declared:

    timeout 600 python computations/verify_loop_carrier_rate_entry_sweep.py

exit `0`; `69.8` s of the executor's own runtime, `70.0` s wall, against `bound_seconds = 600.0`.
29 executions, 7500 steps each, 203000 steps in total, against caps of 10000 per execution and
250000 in total; `seconds_per_step_measured = 0.001195`, projection `245.0` s measured and `170.0` s
on the chain's recorded assumption. Receipt
`runs/loop_carrier_rate_entry_sweep/verification.json`, digest
`318a2ac64f60b5c52cafd21014d008c40483ed7abc9287df4d4f0d9f19d2cd18`, schema
`cassi.loop-carrier-rate-entry-sweep.v1`, status `PASS`, every one of the fourteen gates `PASS`.

### 8.3 The design probe, run before the first freeze

`--design-probe` integrated every arm once, wrote nothing, and its readings are section 1.5. Two
thresholds were set from it with headroom, and both moves are visible in the readings: the fitted
rate departs from its entry by at most `4.36e-3` relative, at the widest point, which is the
reader's declared `O(beta^2)` nonlinearity and not noise -- hence `entry_tol_relative = 1.0e-2` --
and the same point's fit residual is `8.541e-3`, so `fit_residual_ceiling = 2.0e-2`. The crossing's
own fitted rate was `2.488e-17` and its residual `4.1e-15`, the can-fail arm read `1.0000059866`
against its entry of `1.0`, the witness read `0.5000075974` against `0.5`, and the clock read
`0.011282357172592223` at every point tested.

### 8.4 The result

One estimator, one stride, one window, applied to the entry coordinate at seven declared points and
to the window's own clock at every one of them:

| point | exchange | entry | fitted rate | rate / entry | fit residual | clock rate / its reference |
| --- | --- | --- | --- | --- | --- | --- |
| `-0.0100` | `-0.0100` | `-0.02` | `-0.020087210596378125` | `1.004361` | `8.541e-03` | `0.996199` |
| `-0.0050` | `-0.0050` | `-0.01` | `-0.010005319983069205` | `1.000532` | `2.399e-04` | `0.996199` |
| `-0.0025` | `-0.0025` | `-0.005` | `-0.005001058250020064` | `1.000212` | `2.173e-05` | `0.996199` |
| `+0.0000` | `0.0` | `0` | `2.4880630605367724e-17` | -- | `4.149e-15` | `0.996199` |
| `+0.0025` | `+0.0025` | `+0.005` | `0.005000236194936966` | `1.000047` | `4.853e-06` | `0.996199` |
| `+0.0050` | `+0.0050` | `+0.01` | `0.010000265174148837` | `1.000027` | `1.198e-05` | `0.996199` |
| `+0.0100` | `+0.0100` | `+0.02` | `0.02000022063745508` | `1.000011` | `2.220e-05` | `0.996199` |

**Branch `LINEAR_BOTH_SIDES`.** Both signs pass their bands together with the crossing, every fit is
readable with 31 samples above the floor, one sign throughout, and a residual inside the ceiling.
The rate-to-entry slope of the seven readings is `1.001724712832028` with intercept
`-1.3266688989497523e-05`, so the rate is not merely close to its entry at each point: it is the
entry to `1.7e-3` relative across a range of a factor of four in the entry, and the crossing's own
rate is `2.488e-17` -- a factor `1.6e10` below the smallest swept entry, and `1.6e7` below the
two-coordinate receipt's own bound `-ln(share)/450 = 4.053e-10` on a window three times longer.
Section 71's identification of the decay rate with the gap entry therefore holds at one point, at
both signs, and across the range, not only where the entry vanishes by construction.

The rest of the readings the gates carried: can-fail at `r = +0.5` reads `1.0000059865642859`
against its entry `1.0`, the witness at `r = +0.25` reads `0.5000075974138588` against `0.5`, every
ray arm is fixed point for fixed point and the same at every point, the clock's seven fitted rates
are bit-identical, the reader resolves the loop-only probe (`0.07376815905011214` against the spent
reader's `0.0`), averages the exterior-only probe out (`0.0` against `0.06938268539288772`), is not
the spent reader, agrees with it on the chi-uniform mean, and is bit-equal to the two-coordinate
body's reader on all three declared-shaped probes. The kernel at every declared point, predicted
before the run: `dim ker(mode 0) = 2` with the direction-antisymmetric direction present only at
`r = 0`, and `1` at `r = 0.6`, `0.5`, `0.25` and at all six non-zero swept points, with the
antisymmetric direction absent; every closed-form multiset residual is `<= 2.3e-16`.

### 8.5 The injector's law, in one sentence

**The orientation drive writes a signed charge and not a magnitude**: at both declared injector
points the response's even part is exactly `0.0` to the last bit and its odd part is the whole
response (`-0.0014358387617779411` at `r = 0`, `-0.012646830210309101` at `r = -0.01`), so
reversing the drive reverses what the coordinate stores, and the coordinate is not a monotone
store. The removed fraction of the body's own reversed-channel arm, which writes for one phase,
applies the reversed drive for a second and holds nothing for a third, is `0.7715799746327933` at
`r = 0` and `0.3690299651437342` at `r = -0.01`: the reversed channel removes most of what it wrote
and leaves a residue, on this body's schedule, far larger than the `0.66%` the two-coordinate
body's erasure branch read on its own.

### 8.6 What this does and does not say

It says: on the frozen (LB6) line, restricted to the declared chi-uniform, exterior-flat seed
family, the declared coordinate's decay rate *is* the gap entry, linearly, at both signs through
the crossing, against a clock that does not move with the entry -- so the two-coordinate body's
retention reading extends from its declared point to a range, and section 71's identification is
not an artifact of reading where the entry vanishes.

It does not say: that any physically realized memory exists, that the erased fraction is a storage
efficiency, or that the linearity extends outside this seed family. The seed's exactness is what
makes the rate readable -- its antisymmetric content lies on the equilibrium-ratio direction, whose
eigenvalue is the entry alone -- and a seed with content on the other direction would mix the two
eigenvalues and read a rate between them. The clock, the erased fraction and the injector's law are
this body's own schedules; what they share with the bodies this continues is stated in the
requirement rows of section 5 and nowhere else.
