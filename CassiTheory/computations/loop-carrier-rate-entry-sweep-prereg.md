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
| `frozen_body_sha256` | `f81a4776f736d91d6724d08c10fbdb14ca81f775934dc38ab03c0f76775224d5` | sections 1-7 of this file, at freeze |
| `executor_sha256` | `e70007614ab45d83b9eb835297354bd8465b6a9abc89986dc19b4b329fd22b7d` | this body's own executor, at freeze |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | the frozen operator module (LB1)-(LB7) |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | the successor probe that executes them |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | the projection split |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` | the gate-load chain |
| `prior_executor_sha256` | `3852eadbd434e021d1dc351820db06e6295c34c11270144b0826f6097b09f6b1` | the composition coexistence body |
| `audit_executor_sha256` | `0503f109c8b431768fbe16d37dfe8a82dec18cce2f97dc417d2fb08d1474f07a` | the kernel-dimension audit (§71) |
| `write_executor_sha256` | `740d0fc036721be5f1ee0fd5527fe54e771243113e13b7133be053f6439cf6c6` | the attractor-write body (the clock oracle) |
| `two_coordinate_executor_sha256` | `671e4a5edbe406f6c1f932d855987d5cc746315b10c13f387291bf15cbf778f0` | the two-coordinate body's own reader, kernel check and domain probes |
| `two_coordinate_receipt_sha256` | `46ae3ee2b93051277c6e1c86dce4c713fb3b397d74cb06c2559ff8e7b98f344e` | its receipt, the zero-rate and erase oracles |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | the relaxation receipt |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | the split receipt |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` | the gate-load receipt |
| `prior_receipt_sha256` | `5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200` | the coexistence receipt |
| `coexistence_receipt_sha256` | `9724143b98cf394eb9948741d3a117c4cc1e4b14fe54ff2ad9e81dfddb8bf60f` | the coexistence body's receipt |

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
   SEED_CONTENT_CEILING` and the pointwise epsilon is within `SEED_EPSILON_CEILING` of zero on
   every sweep seed. That ceiling is round-off and not a modelling residual: the frozen `on_ray`
   profile is exact in real arithmetic, while its two densities are floats, so `phi E_I` differs
   from `E_Y` by one unit in the last place and the conversion term is correspondingly small
   rather than zero.
9. **silence on every ray arm** -- the state's digest before and after the window is the same on
   every ray arm, and the same at every point.
10. **readable on every declared arm** -- the entry coordinate's first sample `>= READABLE_FLOOR_Q`
    and the clock's ray distance's first sample `>= RAY_READABLE_FLOOR`.
11. **can-fail at fifty times the largest swept entry** -- the short-window arm at `r = 0.5` reads
    its own entry within `CANFAIL_BAND_RELATIVE` and above `CANFAIL_FLOOR`.
12. **the window's own clock at every point** -- every point's ray-distance rate within
    `ENTRY_TOL_RELATIVE` of the conversion entry at its own seed, and the clock arms bit-identical
    across the whole sweep.
13. **the fit's own quality** -- on every entry arm, at least `FIT_MIN_SAMPLES` samples above the
    floor, one sign throughout, and a residual within `FIT_RESIDUAL_CEILING`.
14. **single invocation** -- the receipt was absent at the start and one process wrote it.

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

If the invocation is interrupted before it writes a receipt, the honest procedure is: leave the
record as it stands, state in section 8 that the invocation wrote nothing, and re-run once. A
second invocation is permitted only that way; the executor refuses a third, and refuses outright if
the receipt already exists.

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

Not yet executed. This section is written after the single invocation, and the frozen body above is
not edited to receive it.
