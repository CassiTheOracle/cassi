# Cutoff Dependence of the Vortex-Stretching Band Split

## Status: Pre-registered—September 2026

## Abstract

The two-cutoff band split of
`computations/navier-stokes-strain-band-split-prereg.md` returned no
classification, and the reason it returned none is the measurement: three of
its five helical-tube families change their per-cutoff verdict between
$k_c=2$ and $k_c=4$, so whether the positive vortex-stretching production sits
in the low band $|k|\le k_c$ or in the high band $|k|>k_c$ depends on where
the cutoff is drawn. A two-cutoff schedule cannot distinguish a crossover at a
located cutoff from a gradual trend that the next cutoff would have continued.
This schedule evaluates the frozen statistic on a declared ladder of six
cutoffs $\{1,2,3,4,6,8\}$ along the same $N=32$ primary trajectories, freezes
the crossing brackets and the rules that separate a located crossover from a
gradual trend and from non-monotone behaviour, and stops after six executions.
The output is a finite-family cutoff scan at one viscosity and one horizon: it
supplies no cutoff-uniform estimate, no data-controlled bound on the
accumulated strain norm, and no regularity statement.

## 1. Statistic and the cutoff ladder

The bands, the projections, the accumulated integrals, the fractions and the
denominator are those of
`computations/navier-stokes-strain-band-split-prereg.md` §1, reused unchanged.
On the $2\pi$-periodic torus with viscosity $\nu=1/10$ and horizon $T=1/2$, for
a declared cutoff $k_c$ the strain splits by wavenumber magnitude,

$$
S_{\mathrm{low}}=\mathbb P_{\le k_c}S,\qquad
S_{\mathrm{high}}=\mathbb P_{>k_c}S,
$$

$$
P_{\mathrm{low}}(t)=\int\omega\cdot S_{\mathrm{low}}\omega\,dx,\qquad
P_{\mathrm{high}}(t)=\int\omega\cdot S_{\mathrm{high}}\omega\,dx,
$$

so that $P=P_{\mathrm{low}}+P_{\mathrm{high}}$ exactly at every state. The
recorded quantities are the positive accumulated integrals

$$
I_{\mathrm{low},+}(k_c;T)=\int_0^T\max(P_{\mathrm{low}},0)\,dt,\qquad
I_{\mathrm{high},+}(k_c;T)=\int_0^T\max(P_{\mathrm{high}},0)\,dt,
$$

the statistic

$$
r_{\mathrm{high}}(k_c)=\frac{I_{\mathrm{high},+}(k_c;T)}
{\max(I_P(T),10^{-12})},
$$

its complement $r_{\mathrm{low}}(k_c)$ over the same denominator, and
$I_P(T)=\int_0^T\max(P,0)\,dt$. Only the cutoff $k_c$ varies across the
ladder. No band boundary, integrand, normalization, denominator or trapezoid
accumulation is redefined here, and the per-cutoff levels used in §4 are the
frozen §5 levels $0.5$ and $0.1$.

**Ladder.** The declared cutoffs are

$$
k_c\in\{1,\ 2,\ 3,\ 4,\ 6,\ 8\}.
$$

Both frozen cutoffs $2$ and $4$ are ladder points, so the frozen table is a
subset of the ladder table. The N=32 Galerkin truncation retains $|k|\le32$ on
its $M=193$ product grid, so every ladder cutoff lies strictly inside the
retained band and no band is emptied by the truncation mask. The ladder is a
cutoff scan of one truncation pair, not a truncation study: the grid cutoff
stays at $N=32$ and the grid at $M=6N+1=193$.

**One trajectory, several cutoffs.** The band split is a spectral reading of a
single flow. The evolution equation carries no $k_c$, each projection acts on
the retained state after an accepted step, and the frozen accumulation adds
every band to its own running integral, so an added cutoff changes neither the
trajectory nor the state sequence nor $P$ nor $I_P(T)$ nor the accumulated
value of any other band. Reading six cutoffs from one trajectory is therefore
the same statistic six times over, not a cheaper substitute for it: each
reported $r_{\mathrm{high}}(k_c)$ is the trapezoid accumulation of
$\max(P_{\mathrm{high}}(k_c),0)$ over the same 1025 accepted states of the same
run that the frozen schedule already evolved. Re-running the trajectory once
per cutoff would reproduce the same numbers at six times the cost.

**Families.** The six frozen cases are reused: the exact Beltrami control and
the five helical-tube families (wide, narrow, tight-pitch, two-scale,
opposite-handed). Geometry, seeds and the Leray projection come from the
retained construction of
`computations/verify_navier_stokes_helical_dynamic_depletion.py`, and every
family is rescaled after projection to $K(0)=\tfrac12\|u\|_2^2=1$, exactly as
the frozen §2 declares.

## 2. Run matrix, compute budget, and the stopping rule

The schedule declares six executions: one $N=32$ primary run per case, at
$M=6N+1=193$, 1024 equal RK4 steps in float64 over $[0,T]$, evaluated at every
accepted state (1025 states per run) with checkpoints at
$t/T\in\{0,1/4,1/2,3/4,1\}$. These are the six $N=32$ primary runs that carry
the frozen §5 classification; the $N=16$ primaries and the 1024-to-2048-step
refinements are not repeated. The ladder adds no dynamics, so the integration
evidence of the frozen receipt carries over rather than being re-measured:
that receipt records a maximum timestep-refinement change of $4.10\times10^{-7}$
against its frozen $10^{-4}$ tolerance for the same trajectory, grid factor and
step count, and the added cutoffs are readings of that verified trajectory.

The executions are run from the repository root:

```text
timeout 14400 python computations/verify_navier_stokes_strain_band_split_cutoff_ladder.py
```

**Projected wall time.** The frozen log
`runs/navier_stokes_strain_band_split/probe_completed.log` times the six $N=32$
primary runs at 531–564 s each with two cutoffs, a mean of 542 s. Counting the
work of one accepted state in inverse transforms: the four RK4 right-hand-side
evaluations use nine each (36), the full-band strain diagnostics use nine, and
each band adds six for the band-limited strain. Two bands therefore cost 57
transforms in about 0.53 s, and four added bands take the count to 81. If cost
tracks transforms alone, the six-cutoff run costs about 0.75 s per state,
830 s per run and 5000 s for the six executions. Each band also repeats its
pointwise quadratic form, matrix-vector coupling, two norms, two spectral
reductions and Parseval sum, which is comparable to the transform share, and
the pessimistic reading of that share puts the six-cutoff run at 1.65 s per
state, about 1690 s per run and 10100 s for the six executions. The declared
projection is the midpoint of the two models, about 1330 s per run and 7990 s
(2.2 h) for the schedule, with the declared range 5000–10100 s.

**Bound.** The invocation is bounded at 14400 s (4 h) by the outer `timeout`,
which leaves at least 1.4× headroom over the pessimistic projection.

**Stopping rule.** One invocation. If it expires inside the bound without
writing a receipt, the execution record states the bounded attempt with the
last printed progress line and no classification; a single re-run of the
identical command and the identical ladder under a larger bound is then
permitted, and the aggregate wall time across all invocations of this probe is
capped at 21600 s. Beyond that the probe stops with no classification. The
ladder is not changed after any invocation, a timeout is not converted into a
smaller ladder or a cheaper statistic, and the six executions are not extended.

**Ladder sizing.** The declared ladder is fixed before execution, and no
trajectory ran before this file was complete. It is a six-cutoff ladder rather
than a seven-cutoff one because no marginal band cost can be measured without
running, and the denser candidate that also carries $k_c=5$ reaches about
11600 s in the pessimistic model, which leaves only 1.24× headroom inside the
declared bound. The declared ladder carries both frozen cutoffs, one interior
point that splits the disputed interval at $k_c=3$, and two tail points at
$k_c=6$ and $k_c=8$ that decide whether a family reaches low-band dominance
inside the ladder or is right-censored by it.

## 3. Integrity gates

The six executions carry the frozen numerical gates on the gates' own frozen
tolerances:

- every recorded scalar is finite;
- projected kinetic normalization error at most $10^{-10}$;
- Fourier divergence residual at most $10^{-10}$;
- the band identity $P-P_{\mathrm{low}}-P_{\mathrm{high}}=0$ to relative error
  at most $10^{-10}$ with denominator $\max(1,|P|)$, at every accepted state
  and every ladder cutoff;
- for each band and cutoff, the physical-space band energy agrees with its
  spectral sum by Parseval to relative error at most $10^{-9}$;
- the maximum positive kinetic-energy increment is at most
  $10^{-9}\max(1,K(0))$;
- the kinetic-energy balance residual is at most
  $10^{-9}\max(1,|K'(0)|,2\nu E(0))$ at every accepted state;
- the Beltrami control's band productions stay at most $10^{-10}$ in absolute
  value at every ladder cutoff, which the exact heat-flow solution requires;
- the declared execution count is six;
- every run records a band reading for every ladder cutoff, so a run that
  silently drops a cutoff from the ladder fails rather than shortens the table.

Two further gates bind this probe to the frozen record:

- **Source binding.** The frozen verifier
  `computations/verify_navier_stokes_strain_band_split.py` is loaded as a module
  from disk and is accepted only when its SHA-256 is
  `b31e1782e275f3073ba0c05d4912d1eedc0b6f543e735feebb17e773688dcb66`, the digest
  of the executed file. The probe reads the frozen band machinery rather than
  reimplementing it, and the gate fails closed if that file changes.
- **Frozen-value reproduction.** For each of the five tube families and each
  frozen cutoff $k_c\in\{2,4\}$, the ladder's $r_{\mathrm{high}}(k_c)$ and
  $r_{\mathrm{low}}(k_c)$ agree with
  `runs/navier_stokes_strain_band_split/verification.json` to a relative
  difference of at most $10^{-9}$, using denominator
  $\max(1,|a|,|b|)$; and the Beltrami control's band integrals agree with the
  frozen receipt to $10^{-30}$ in absolute value. The ladder reproduces the
  frozen numbers because it reads the same trajectory through the same
  arithmetic, and a failure here voids the run rather than comparing two
  different measurements.

The schedule reports `status=PASS` only when every gate passes. A verdict is
assigned only on `PASS`; on `FAIL` the receipt records the failed gate, the
measured value and the bound, and no classification.

## 4. Decision tree

The frozen thresholds classify each per-cutoff reading: $r_{\mathrm{high}}>0.5$
is high-band dominance, $r_{\mathrm{high}}\le0.1$ (with
$r_{\mathrm{low}}\ge0.5$) is low-band dominance, and the interval in between is
intermediate. The ladder turns those per-cutoff verdicts into a curve, and the
curve is read through three declared objects.

**Crossing bracket.** For a level $\ell\in\{0.5,0.1\}$, the bracket is the
adjacent ladder pair $(k_i,k_{i+1})$, $k_i<k_{i+1}$, with
$r_{\mathrm{high}}(k_i)>\ell\ge r_{\mathrm{high}}(k_{i+1})$. The bracket is
recorded as $[k_i,k_{i+1}]$. When $r_{\mathrm{high}}$ is at most $\ell$ at the
ladder's first point $k_c=1$, the family is recorded as below the level
throughout; when $r_{\mathrm{high}}(k_c)>\ell$ at the ladder's last point
$k_c=8$, it is recorded as above the level at the top, right-censored by the
ladder.

**Non-monotone flag.** A family is non-monotone when $r_{\mathrm{high}}$
decreases by more than $0.05$ between one adjacent ladder pair and later
increases by more than $0.05$ between another, so the cutoff dependence is not
a single passage.

**Family classes.** Each family takes exactly one class, tested in this order:

1. `non-monotone`—the flag above, with the brackets that make it fire;
2. `located crossover at both levels`—a bracket exists at $0.5$ and a bracket
   exists at $0.1$; the class carries the qualifier `single step` when the two
   brackets are the same ladder pair and `gradual` when they differ, and in the
   gradual case it records both brackets and the intermediate-band cutoffs
   between them;
3. `located crossover at the low level`—a bracket exists at $0.1$ and the
   family never exceeds $0.5$ anywhere on the ladder, so the passage into
   low-band dominance is located while the family starts below high-band
   dominance;
4. `low-band dominated throughout`—$r_{\mathrm{high}}\le0.1$ at every ladder
   cutoff;
5. `high-band dominated throughout`—$r_{\mathrm{high}}>0.5$ at every ladder
   cutoff;
6. `intermediate throughout`—$0.1<r_{\mathrm{high}}\le0.5$ at every ladder
   cutoff;
7. `right-censored above the low level`—otherwise: no bracket exists at the
   low level while the family is not low-band dominated at every ladder
   cutoff, so either the passage into low-band dominance completes above
   $k_c=8$ or the curve never descends past $0.1$ at all.

A located crossover is a family in class 2 or 3. A gradual trend is a family
in class 2 with the qualifier `gradual`, or a family in class 7: the passage
exists but one of its ends lies outside the ladder or beyond the next bracket.
No crossover is a family in class 4, 5 or 6, which never leaves one band, and
class 5 and class 6 are exactly the readings in which no low-level bracket can
exist: a family that stays above $0.5$, or between $0.1$ and $0.5$, at every
ladder cutoff has no passage to locate.

**Per-family outcome.** Each family reports its class, the value of
$r_{\mathrm{high}}$ at every ladder cutoff, and its crossing brackets. The
three families whose frozen per-cutoff verdicts disagreed (narrow, tight pitch,
opposite handed) are the cutoff-sensitive set; the two whose frozen verdicts
agreed at both cutoffs (wide, two-scale) are the cutoff-stable set. Membership
is read from the frozen receipt, not chosen here.

**Aggregate verdict.** With every gate passed:

- `CONTRADICTS`—at least one family is class 1 `non-monotone`: the cutoff
  dependence is then not a single passage, and the frozen two-cutoff
  disagreement is one segment of a curve that reverses. A failed integrity or
  reproduction gate is not a verdict; it is `status=FAIL` with no
  classification, as §3 declares.
- `EMERGES`—every family is class 2, 3 or 4: each family either crosses the low
  level at a recorded bracket (classes 2, 3) or is low-band dominated at every
  ladder cutoff (class 4), and no family sits in class 5, 6 or 7. The reading
  is then that $r_{\mathrm{high}}(k_c)$ is a monotonically decreasing function
  of the cutoff, that each family's passage into low-band dominance is located
  at a recorded ladder bracket, and that the frozen disagreement at
  $k_c\in\{2,4\}$ is one such passage seen at two neighbouring cutoffs.
- `DOES NOT EMERGE`—all three cutoff-sensitive families are class 5, 6 or 7, so
  none of them has a located crossover: the frozen disagreement at $k_c=4$ is
  the beginning of a gradual trend, a plateau above the low level, or a
  right-censored passage whose completion lies above $k_c=8$.
- `INCONCLUSIVE`—otherwise: at least one family sits in class 5, 6 or 7 while
  the families do not compose into one reading, for instance when at least one
  cutoff-sensitive family crosses at a recorded bracket and at least one is
  right-censored or plateaus.
- `SUPPORTS`—unreachable by construction. It would require low-band dominance
  in every family at every ladder cutoff, and the ladder contains $k_c=2$,
  where the reproduction gate pins the frozen readings $0.493540$ (narrow),
  $0.874568$ (tight pitch) and $0.760908$ (opposite handed) above $0.1$.

Classes 5 and 6 are also unreachable for the two cutoff-stable families once
the reproduction gate passes, because their frozen readings at $k_c=2$ and
$k_c=4$ are at most $0.1$; a class 5 or 6 outcome there would make the
reproduction gate fail first.

A `DOES NOT EMERGE` or `CONTRADICTS` outcome is a recorded result at the same
standing as `EMERGES`: the frozen two-cutoff disagreement is then a trend or a
bracket artifact rather than the located crossover the two-cutoff schedule
could not resolve, and the probe is not re-run at full cost to look for
another answer.

## 5. Interpretation boundary

A ladder of cutoffs locates where the spectral split of the stretching
production changes character for five declared families at one viscosity, one
horizon and one truncation pair. It does not make the split a Biot–Savart
near-field/far-field decomposition: the low band still contains large-scale
strain the trajectory generated, the declared kernel split of
`turbulence/navier-stokes-stress-geometry.md` §8.1 is a physical-space chart
split with its own radius, and no crossing bracket here identifies a spatial
support for either band. A located crossover records that the two frozen
cutoffs straddle a passage in that family, and therefore that the frozen
classification was a statement about the cutoffs rather than about the family.
No outcome supplies a cutoff-uniform estimate, a data-controlled bound on
$\mathcal D_S(T)$, a bound on the strain acting on a vortex core from a
distance, or a continuation statement, and the ladder does not change the
unresolved status of the active-dose and direction-coherence obligations of
`turbulence/navier-stokes-coherence-dose-criterion.md`.

## 6. Post-execution record

The schedule ran as written, unmodified, from the repository root:

```text
timeout 14400 python computations/verify_navier_stokes_strain_band_split_cutoff_ladder.py
```

The shell resolved `timeout` to the workspace wrapper, which executes its
command in place, so the declared bound was enforced by the waiting shell: it
would have killed the process tree at start + 14400 s. The invocation never
needed the bound. It exited 0 after 5447.87 s (1.51 h), completing all six
declared executions, and wrote
`runs/navier_stokes_strain_band_split_cutoff_ladder/verification.json` with
`status=PASS` and all 13 gates passed. The measured time sits near the low end
of the declared 5000–10100 s range, close to the transform-count model's
5000 s rather than the midpoint projection of 7990 s; the six runs took
900–1000 s each.

The gates record kinetic normalization $3.33\times10^{-16}$, Fourier
divergence $2.63\times10^{-17}$, band identity $0$, band Parseval
$4.16\times10^{-17}$, a maximum positive kinetic-energy increment of $0$, an
energy-balance ratio of $1.05\times10^{-15}$, a Beltrami band control of
$6.50\times10^{-34}$ against $10^{-10}$, six declared executions, six readings
per accepted state in every run, and the declared source digest
`b31e1782e275f3073ba0c05d4912d1eedc0b6f543e735feebb17e773688dcb66` for the
frozen verifier. Every frozen comparison is exact: each $r_{\mathrm{high}}$ and
$r_{\mathrm{low}}$ at $k_c\in\{2,4\}$ and each Beltrami band integral agrees
with `runs/navier_stokes_strain_band_split/verification.json` with a difference
of $0$, against tolerances $10^{-9}$ and $10^{-30}$. The ladder is the frozen
statistic read at four further cutoffs from the same trajectories.

| Tube family | $r_{\mathrm{high}}(k_c)$ at $k_c=1,2,3,4,6,8$ |
|---|---|
| Wide | 0.607004, 0.080289, 0, 0, $1.41\times10^{-20}$, 0 |
| Narrow | 0.836992, 0.493540, 0.147895, 0.049856, 0, $2.67\times10^{-18}$ |
| Tight pitch | 0.973303, 0.874568, 0.679457, 0.403669, 0.020242, 0.021207 |
| Two scale | 0.625918, 0.093607, 0, 0, 0, $1.13\times10^{-19}$ |
| Opposite handed | 0.879386, 0.760908, 0.465760, 0.008912, 0.062442, 0.001522 |

| Tube family | $r_{\mathrm{low}}(k_c)$ at $k_c=1,2,3,4,6,8$ | Class and brackets |
|---|---|---|
| Wide | 0.392996, 0.919711, 1.144395, 1.102017, 1.011395, 1.000648 | located crossover at both levels, single step, brackets $[1,2]$ and $[1,2]$ |
| Narrow | 0.163008, 0.506460, 0.856587, 0.986010, 1.101164, 1.054189 | located crossover at both levels, gradual, high-level bracket $[1,2]$, low-level bracket $[3,4]$, intermediate at $k_c=3$ |
| Tight pitch | 0.026697, 0.125432, 0.320543, 0.596331, 1.100187, 1.003334 | located crossover at both levels, gradual, high-level bracket $[3,4]$, low-level bracket $[4,6]$, intermediate at $k_c=4$ |
| Two scale | 0.374082, 0.906393, 1.142274, 1.103970, 1.016723, 1.002196 | located crossover at both levels, single step, brackets $[1,2]$ and $[1,2]$ |
| Opposite handed | 0.120614, 0.239092, 0.534240, 1.491487, 0.944954, 1.056591 | non-monotone, high-level bracket $[2,3]$, low-level bracket $[3,4]$, intermediate at $k_c=3$ |

Every family is high-band dominated at $k_c=1$ and low-band dominated from
$k_c=6$ onward, so all five pass from the high band to the low band inside the
ladder. Four of them do so as a single passage: the wide and two-scale families
cross both levels inside the bracket $[1,2]$, the narrow family crosses the
high level inside $[1,2]$ and the low level inside $[3,4]$, and the tight-pitch
family crosses the high level inside $[3,4]$ and the low level inside $[4,6]$.
The two families whose frozen verdicts agreed at $k_c\in\{2,4\}$ cross at
$[1,2]$, which is why they read the same at both frozen cutoffs.

The opposite-handed family reverses. Its $r_{\mathrm{high}}$ falls from
$0.879386$ at $k_c=1$ to $0.008912$ at $k_c=4$ across three drops above the
declared $0.05$ tolerance and then rises to $0.062442$ at $k_c=6$, a rise of
$0.053529$ that clears the tolerance by $0.003529$, before falling to
$0.001522$ at $k_c=8$. Through the §4 rules the family's class is
`non-monotone`, and the aggregate verdict is

```text
CONTRADICTS
```

which the receipt records at
`runs/navier_stokes_strain_band_split_cutoff_ladder/verification.json` as
`status=PASS, verdict=CONTRADICTS`. The verdict reads the ladder as evidence
against monotone cutoff dependence: the frozen disagreement at
$k_c\in\{2,4\}$ is a continuing passage for four families, but for the
opposite-handed family it is one segment of a curve that turns back up before
it turns down again.

The run leaves open the shape of that reversal between $k_c=4$ and $k_c=6$,
because the declared ladder carries no $k_c=5$ point, and it leaves the
monotone readings at the ladder's tail as statements about exact zeros: the
high-band integrals of the wide, narrow and two-scale families are at or below
$10^{-19}$ of $I_P(T)$ from $k_c=6$ onward. Low-band fractions above one, up to
$1.491487$, follow from the frozen §1 normalization. The record remains finite:
five declared families, one viscosity, one horizon, one truncation pair, no
cutoff-uniform estimate, no data-controlled bound on $\mathcal D_S(T)$, and no
continuation statement.

The receipt's `source_hashes` fixes the five inputs of the run: the frozen
verifier at `b31e1782e275f3073ba0c05d4912d1eedc0b6f543e735feebb17e773688dcb66`,
the executed probe script at
`059090600a69a82a60d0ac62c91b356a5b79ffeef1b0d9985cec46c98f55c4c6`, the frozen
preregistration at
`76d10c3bf04650951bda163b90131c78bb8b9aee2e8af534ffa59e3eebe3c9d9`, the frozen
two-cutoff receipt at
`e38a8078cee0e3d4f62fcf2797aa3fb922087812eea83331f9dd75059a248728`, and this
file at `376444fe13b0f790e8dfbf6f4d21619289229e31e4b5a77b856ef1ef941a7d1f`, the
digest the schedule was frozen on. Sections 1–5 state the statistic, the ladder,
the gates and the decision tree exactly as the receipt applies them, and this
section carries the readings the receipt reports.

## References

- `computations/navier-stokes-strain-band-split-prereg.md`—frozen two-cutoff band split, its decision rules and its post-execution record
- `computations/verify_navier_stokes_strain_band_split.py`—frozen two-cutoff verifier whose band projections, packed strain path, accumulation and gates this probe reuses
- `computations/verify_navier_stokes_galerkin_long_trajectory.py`—retained Fourier–Galerkin rotational integrator and ROCm implementation
- `computations/verify_navier_stokes_helical_dynamic_depletion.py`—retained helical-tube construction, spectral helpers and initial-data normalization
- `runs/navier_stokes_strain_band_split/verification.json`—frozen receipt that supplies the reproduction gate and the cutoff-sensitive and cutoff-stable family sets
- `turbulence/navier-stokes-stress-geometry.md`—physical-space chart split of the Biot–Savart kernel and the conditional direction-coherence estimate
- `turbulence/navier-stokes-coherence-dose-criterion.md`—active-dose continuation criterion and its operator-norm reduction
- `turbulence/navier-stokes-helical-dynamic-depletion.md`—the finite helical families whose positive production this split reads
- `field-experience/probe-outcome-ledger.md`—ledger record of the two-cutoff split and, on execution, of this ladder
