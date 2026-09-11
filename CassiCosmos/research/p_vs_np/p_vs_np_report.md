# Cassi P versus NP Crossover Report

## Verdict: REJECT—September 10, 2026

The registered bounded-coherence SAT mechanism and the implemented uniform
clause-field solver are rejected as routes to `P = NP`. These are
mechanism-level results, not a proof that `P != NP` and not a claim that every
Cassi-inspired algorithm must fail.

The investigation and beyond-resolution continuation produced sixteen useful
results:

1. the fixed-source Cassi two-fluid field has an exact gapless/gapped
   normal-mode split and is fast-forwardable at fixed numerical precision;
2. its production kick-drift discretization preserves an exact weighted
   quadratic invariant in exact arithmetic;
3. CassiFI can own a complete SAT search in a uniform polynomial-size field
   state with constant action vocabulary and checkable SAT and UNSAT outputs;
4. the baseline search is a resolution-bounded chronological DPLL system, so
   Haken's unrestricted-resolution lower bound for the standard pigeonhole
   formulas proves that this exact baseline transition law has
   superpolynomial worst-case transition count;
5. a successor field derives and checks cutting-plane, GF(2), mixed
   cardinality-parity, extension, and resolution proofs, removing that
   particular pigeonhole lower bound without establishing a general
   polynomial-time SAT algorithm; and
6. a syntax-recognized connected exact-one/parity class has a sound global
   contradiction criterion and an explicit canonical infinite subfamily on
   which the deterministic hybrid field produces exactly linear-size
   refutations; and
7. a separate constant-width field decides every member of that canonical
   subfamily in linear time and space, including the parity-consistent side,
   with checked SAT assignments or complete dynamic-program UNSAT
   certificates; and
8. the complete connected matched exact-one/parity class reduces exactly to
   general-graph perfect matching, yielding a total polynomial-time decision
   theorem for every connected quotient topology; and
9. the first controlled occurrence-alias extension has a total
   `O(2^k c^3)` fixed-parameter decision algorithm, where `k` is the number of
   degree-three variables and `c` is the number of clauses, while its
   unrestricted parameter range already contains an NP-complete cubic planar
   monotone one-in-three SAT subfamily; and
10. direct exact-cover branching compresses the measured alias corpus, but its
    golden-ratio recurrence is only local and does not establish a global
    running-time bound; Gröbner elimination rules out every parity orientation
    of a standard uniform-basis matchgate reduction.
11. the all-cubic occurrence seam is exactly the two-point kernel-intersection
    problem `ker(M) intersect {-1,2}^n`; rational elimination reduces every
    supplied-basis pivot-support-at-most-two instance to 2-SAT, even at linear
    nullity; and
12. exact optimization over 537 column bases shows that both original
    canonical support-three controls have width-two bases, while separate SAT
    and UNSAT controls remain support three under every basis. Thus canonical
    RREF support is not invariant, but basis choice does not universally remove
    ternary interaction.
13. a growing-nullity Schaefer census separates basis width from basis-language
    tractability: disconnected direct sums preserve invariant width three while
    nullity grows linearly, and a connected degree-preserving bridge at `n=24`
    remains width three under all 7,344 bases; this is a finite structural
    obstruction, not a recognition or hardness theorem for connected families.
14. an exhaustive one-switch census over the mixed SAT+UNSAT direct sum screens
    all 1,620 connected 27-variable switches, finds no width-two dual frame in
    any of them, and exhibits a width-three witness in each, so every switch has
    `omega = 3` exactly, with complete coverage certificates at bound two over
    all `C(27,5) = 80,730` free subsets and exact rational widths on the
    witnesses; the 32,232-base disconnected sum is `omega = 3` under its full
    basis census.
15. external frame structure is necessary but not sufficient for width two:
    both invariant-width-three controls admit full-rank two-sparse ambient
    bases while no ground-set basis of either dual is two-sparse, and the
    nullity-three criterion is internal, an element triple whose three joins
    cover every class; direct sums combine width by maximum and yield a family
    that is frame with width three at every measured size up to 48, so a
    polynomial frame test cannot decide the width.
16. a complete class search decides the ground-set frame question without
    free-subset enumeration: it reproduces every recorded width verdict on the
    controls, the direct sums, and sampled members of the 1,620-switch family,
    and it certifies connected chains of the two width-three controls at
    nullity five, seven, and nine, where the 60-variable chain's census would
    need `C(60,9) = 14,783,142,660` free subsets and the search exhausts its
    subtree at 21,671 nodes.
17. the complete within-control one-switch neighborhoods are nullity-conditioned:
    the SAT control has `(k=2, omega=2):261`, `(k=3, omega=2):40`,
    `(k=3, omega=3):60`, `(k=4, omega=2):3`, and `(k=4, omega=3):4`;
    the UNSAT control has `(k=2, omega=2):519`, `(k=3, omega=2):29`,
    `(k=3, omega=3):94`, and `(k=4, omega=3):4`. The class search and exact
    free-basis census agree on all 1,014 neighbors; a seeded distance-two
    sample reaches the listed `k=1` and `k=2` width-one rows as well as
    nontrivial width-two and width-three rows. This is a finite local
    measurement, not a distributional claim about general cubic incidence
    families.


The first two results make the CassiCosmos boundary unusually clear. Its
isolated field is an auditable linear signal processor. Combinatorial search
can only enter through a nonlinear source update, particle rearrangement,
threshold, or external controller, and the work and resources of that
mechanism must be counted. CassiFI adds genuine field-owned discrete
computation, so it requires a separate complexity audit rather than being
classified as an external controller.

The frozen CassiCosmos probe failed through ordinary nonsolution attractors,
and a matched accumulating-clause-memory arm failed its bounded-resource
equivalence gate. The first CassiFI continuation removed the representation
objection, but its proof certificates exposed a known proof-complexity lower
bound. The hybrid continuation then left resolution: it constructs polynomial
cutting-plane refutations for the same pigeonhole formulas and exact GF(2)
refutations for bounded-width Tseitin formulas. It also has a restricted
mixed-class theorem with explicit proof, coefficient, state, and controller
bounds.
A bounded-width field closes both outcomes on the canonical topology, and a
signed-subdivision reduction to general-graph perfect matching closes every
connected topology in the matched exact-one/parity class. The alias
continuation reaches the next boundary: branching on each degree-three
variable leaves a perfect-matching residual, but `k` is unbounded and the
recognized degree-two/degree-three class is already NP-complete. Direct
clause-cover branching compresses the measured branch family without improving
the published asymptotic bound. A uniform holographic basis cannot make both
the cubic equality and exact-one signatures satisfy the necessary matchgate
parity condition.

The all-cubic continuation gives that seam an exact algebraic form:
satisfiability is equivalent to finding a vector in
`ker(M) intersect {-1,2}^n`. Exact elimination closes a polynomial 2-SAT
decision whenever a width-two coordinate basis is supplied, even when nullity
grows linearly. The exact basis census corrects the initial canonical-RREF
reading: both original support-three controls admit alternative width-two
bases, while distinct SAT and UNSAT matrices have irreducible width three
across every column basis. The remaining boundary is therefore a
polynomial-time ground-set frame-basis finder for the dual matroid, a global
algorithm for invariant-width-three two-point kernel intersections, a stronger
nonuniform or non-matchgate representation, or a different algorithm—not
quotient topology, polynomial state representation, rank alone, or one
canonical elimination order. Frame structure cannot replace the width decision:
it is one-sided, satisfied by both width-three controls and by the repeated
all-bases family whose width never drops below three.

The next controlled census separates basis width from small-arity Schaefer
closure. Two all-bases controls have width three under every column basis, but
only some bases share a listed tractable relation class: 90 of 136 SAT bases
and 77 of 237 UNSAT bases. Their direct sums give exact product/intersection
scaling to nullity 48. A degree-preserving switch joining two SAT copies gives
one connected `n=24` instance with no width-two basis. These are exact
finite-family measurements; they do not turn semantic zero-valid basis
existence into a basis-finding algorithm and do not classify the unbounded
connected case.

## 1. What would constitute a solution

For a language `L`, `L in P` means that a deterministic Turing machine decides
membership in time polynomial in the input length. `L in NP` means that every
YES instance has a polynomial-size witness verifiable in polynomial time.
The Clay question is whether these classes are equal.

Because 3-SAT is NP-complete, a uniform deterministic polynomial-time 3-SAT
algorithm would prove `P = NP`. Proving a superpolynomial lower bound for an
explicit NP language on unrestricted deterministic computation would prove
`P != NP`.

A physical or field solver counts as a polynomial-time algorithm only if its
complete description and use are polynomially bounded: cells, particles,
steps or physical evolution time, numerical precision, coefficient range,
energy, controller work, initialization, and readout. Exponentially large
weights or energy, exponentially fine precision, or exponentially many
parallel degrees of freedom do not evade the definition.

## 2. Exact result for the linear Cassi sector

For fixed sources, write the field as `(EY, EI)` and let `L` be the periodic
19-point Laplacian. The production equations have the form

```text
EY_tt = L EY - omega2 (EY - phi EI) + source_EY
EI_tt = L EI + omega2 (EY - phi EI) + source_EI.
```

The change of variables

```text
R       = EY + EI
 epsilon = EY - phi EI
```

gives

```text
R_tt       = L R + source_EY + source_EI
 epsilon_tt = (L - phi^2 omega2) epsilon
            + source_EY - phi source_EI.
```

Thus `R` is a gapless transport channel and `epsilon` is a gapped
constraint-error channel. On the periodic grid, the spatial DFT diagonalizes
`L`. Every Fourier coefficient is an independent constant-size affine
second-order recurrence.

### Fixed-precision fast-forward corollary

For `M` cells and a requested step count `T`, a fixed-source state can be
computed at fixed precision by:

1. FFT of the initial state and source;
2. binary powering of one constant-size affine recurrence per mode;
3. inverse FFT.

This takes `O(M log M + M log T)` fixed-precision arithmetic operations rather
than replaying `T` field steps. With closed-form stable mode evaluation, the
per-mode recurrence factor can be reduced further. This is a numerical
fixed-precision statement, not an exact rational-bit-complexity claim.

Consequently, fixed-source two-fluid propagation cannot be the hidden
combinatorial search engine. If an encoding into polynomially many field cells
solved every SAT instance using only this sector, translating its spectral
simulation back into an ordinary algorithm would already give a conventional
`P = NP` proof.

### Exact kick-drift invariant

Let `u = (EY, EI)`, `H = diag(I, phi I)`, and `K = -H A`, where `A` is the
source-free acceleration operator. The coupling block satisfies

```text
-H C = omega2 [[1, -phi], [-phi, phi^2]],
```

so `K` is positive semidefinite. For

```text
v_next = v - dt H^-1 K u
u_next = u + dt v_next,
```

the exact discrete invariant is

```text
E_dt = 0.5 v^T H v + 0.5 u^T K u - 0.5 dt u^T K v.
```

It is positive definite on positive-frequency modes when
`dt^2 lambda_max(H^-1 K) < 4`, and semidefinite on the gapless zero mode.

The receipt measured:

| Structural check | Maximum residual |
|---|---:|
| Direct field versus `R/epsilon` evolution | `2.1094e-15` |
| Weighted invariant relative drift | `5.7451e-16` |
| Superposition | `4.1078e-15` |
| Iteration versus affine matrix power | `1.0880e-14` |

The preregistered limit was `1e-9`; S1 passed.

## 3. Where nonlinearity actually enters CassiCosmos

The live implementation has several nonlinear boundaries, but none is free:

- `compute/cassi_two_fluid.glsl` is linear for fixed mass density and learned
  command. Its `q = EY^2 + EI^2` is a readout.
- `compute/cassi_nbody_gravity.glsl` uses bounded coherence in particle
  acceleration. Moving particles change the next mass deposit, closing a real
  nonlinear loop.
- merge and condensation are thresholded, lossy topology changes;
- the CassiCosmos `cassi_field_intelligence.gd` hook applies bounded learned
  actuation and plasticity, while its reward choice, episode control, targets,
  and readout are host computation;
- mind-engine deposits and projections are requested by an external TCP
  client. The requester's search work must be charged to the algorithm.

These statements describe the CassiCosmos hook, not the independent CassiFI
architecture.

This yields a useful architecture—linear transport, a gapped conflict channel,
and explicit nonlinear intervention sites—but no automatic SAT mechanism.

## 4. Registered SAT crossover

The frozen protocol is `research/p_vs_np/p_vs_np_prereg.md`. A variable used
`s_i in [-1,1]`; a clause used

```text
K_m(s) = product_i (1 - c_mi s_i) / 2.
```

The Cassi-shaped bounded coherence was

```text
q_m = 1 / (1 + phi^2 K_m^2),
```

with damped second-order descent on

```text
V_q = sum_m (1 - q_m) + 0.25/4 sum_i (s_i^2 - 1)^2.
```

Four matched arms used identical formulas and initial states:

1. bounded second-order coherence;
2. static first-order clause-gradient descent;
3. accumulating clause memory capped at `64`;
4. the same registered accumulation law capped at `1e12`.

The registered CTDS comparison uses the explicit equation in the
preregistration. Its spin component differs by a factor of two from the
normalization in Ercsey-Ravasz and Toroczkai, so its measurements apply to this
registered crossover variant rather than reproducing that paper's exact
integrator.

### Corpus

The receipt contains 313 exactly enumerated formulas:

- all 255 nonempty subsets of the eight possible full-width clauses on three
  variables;
- 12 planted 2-SAT formulas;
- 32 planted 3-SAT formulas at `n = 6, 8, 10, 12`;
- 8 balanced 3-XOR systems converted to CNF;
- 4 planted formulas selected from 128 candidates per size for maximal
  one-flip local-minimum count;
- a 3-pigeons/2-holes contradiction and an inconsistent XOR system.

There were four starts per formula and four arms: 5,008 runs. Exact enumeration
classified 310 formulas SAT and three UNSAT. The independent verifier
recertified every final assignment directly from the stored CNF and state.
None of the 48 UNSAT control runs emitted a false positive.

## 5. Measured result

Across the 1,240 satisfiable runs per arm:

| Arm | Certified | Missed | Rate | Maximum clause weight |
|---|---:|---:|---:|---:|
| bounded coherence | 1,211 | 29 | 97.66% | `1` |
| static gradient | 1,210 | 30 | 97.58% | `1` |
| capped clause memory | 1,226 | 14 | 98.87% | `64` |
| expanded clause memory | 1,221 | 19 | 98.47% | `5102.64` |

The bounded coherence arm solved every satisfiable three-variable formula, but
missed:

- 7 of 48 planted 2-SAT runs;
- 11 of 128 planted 3-SAT runs;
- 7 of 32 XOR runs;
- 4 of 16 selected adversarial runs.

Its successful readout margin reached as low as `1.5971e-6`, below the frozen
`1e-3` robustness threshold. S2 therefore contradicted the hypothesis through
both missed satisfiable cases and insufficient decision margin.

### A concrete nonsolution attractor

For `planted3_n8_03`, starts 2 and 3 converged to the same state within
`3.0114e-10`. Its Boolean assignment

```text
[-1, +1, +1, +1, -1, +1, -1, -1]
```

violates clause

```text
(not x_2) OR x_4 OR x_6
```

using zero-based variable indices. The converged point is interior to the
hypercube. An independent float64 finite-difference audit found:

| Quantity | Value |
|---|---:|
| `V_q` | `0.683620956352132` |
| maximum absolute gradient | `3.08199e-10` |
| minimum Hessian eigenvalue | `+0.3432087` |
| maximum Hessian eigenvalue | `+4.0645463` |
| smallest energy change over 2,000 radius-`1e-4` directions | `+2.12509e-9` |

This is numerical evidence for a strict nonsolution local minimum of the
registered bounded potential, with a visible basin reached from at least two
starts. Damped second-order motion does not remove it. This is the decisive
mechanistic obstruction.

### Clause-memory resource gate

The capped and expanded arms disagreed on seven satisfiable XOR runs. In one
case (`xor3_n10_00`, start 0), the capped arm failed while the expanded arm
succeeded after its weight reached `320.24`, already beyond the registered cap
of `64`. In six other cases the cap regularized the finite-step trajectory and
the capped arm succeeded while the expanded arm did not.

The expanded arm reached:

- maximum clause weight `5102.64` (`log2 = 12.317`);
- maximum gradient `109.51`, versus `5.095` under the cap;
- 475,098 total derivative evaluations;
- 14 numerical clamp events.

These small sizes do not establish asymptotic exponential growth. They do show
that the accumulating-memory mechanism is not equivalent under a fixed bound,
and that increasing the available amplitude is not monotonically beneficial
under finite-precision integration. S3 contradicted the registered bounded
resource hypothesis.

No polynomial or exponential scaling fit is reported from `n <= 12`; the
protocol explicitly forbids that extrapolation.

## 6. CassiFI field-owned SAT crossover

CassiFI materially changes the computational model. Its architecture separates

```text
F_t = sole adaptive field state
E_t = exact evidence and immutable computational history
A_t = nonlearned authority and operational control
K   = fixed codecs, primitives, solvers, validators, and interpreters.
```

Learned numerical relations, discrete structures, temporal policies,
predictions, plans, and provisional workspaces belong to `F_t`. Removing the
responsible field coordinates removes the learned ability even if the fixed
machinery remains. Host ownership of persistence, authorization, and world
effects does not make the learned computation host-owned.

The implemented mechanisms have different complexity:

- On one fixed chart branch, variational completion has an SPD quadratic
  objective. It assembles a precision matrix and solves a finite linear system.
  This is polynomial-time digital computation, not a nonconvex SAT landscape.
- A `FieldProgram` is typed straight-line arithmetic with a bounded execution
  budget. It has no implicit unbounded search.
- A `TemporalField` stores empirical transitions, predictive states, safe
  reachability ranks, and action policies in numeric field planes. This is real
  field-owned finite-state computation.
- Independent discrete chart modes are expanded as an explicit Cartesian
  product. For mode-group sizes `m_j`, the branch count is
  `product_j m_j`, subject to a hard configured budget.

### Executed temporal-field search

`CassiFI/run_p_vs_np_field_probe.py` learned a complete lexicographic
assignment-enumeration policy in a `TemporalField`. On each step, the field
selected the next complete assignment. Fixed world machinery performed only
the polynomial certificate operation: evaluate that assignment against the
given CNF and return `sat` or `miss`.

The probe exercised 22 formulas from `n = 2` through `n = 6`: unique-solution
unit CNFs, planted CNFs, a variable-permuted planted CNF, and the
3-pigeons/2-holes contradiction. All 21 satisfiable cases returned assignments
that an independent receipt pass verified clause by clause. The UNSAT control
visited all 64 assignments and then became `unresolved`; the field did not emit
a false certificate or claim UNSAT.

The field-causality control passed at every size:

- exact serialize/reload preserved the field bytes and state digest;
- removing the learned transition and policy planes while retaining the same
  codecs and fixed machinery changed the skill from `formed` to `pending` and
  action selection to `unresolved`.

The measured resource profile was:

| Variables | Assignment actions | Learned states | Maximum safe rank | Field bytes |
|---:|---:|---:|---:|---:|
| 2 | 4 | 5 | 4 | 73,728 |
| 3 | 8 | 9 | 8 | 147,456 |
| 4 | 16 | 17 | 16 | 294,912 |
| 5 | 32 | 33 | 32 | 589,824 |
| 6 | 64 | 65 | 64 | 1,179,648 |

Every additional variable doubled the action vocabulary, maximum policy rank,
and field storage. At seven variables, this encoding requires 128 actions and
is rejected by the temporal field's 64-action limit.

A separate audit of CassiFI's structural alternatives found exactly 2, 4, 8,
16, 32, and 64 branches for one through six independent binary mode groups.
Seven groups were rejected with `BRANCH_BUDGET`, reporting `required = 128`
and `limit = 64`.

### Interpretation

This corrects the earlier scope error: **CassiFI really does compute in the
field.** The experiment is not a host search disguised as field dynamics. The
field owns the candidate order, learned predictive states, and decreasing-rank
policy; the host supplies the same kind of polynomial witness verifier used in
the definition of NP.

It also exposes the resource rather than eliminating it. This particular exact
solver places exhaustive search in field-resident action identities, states,
and policy rank. The direct structural encoding places it in explicit branch
count. Both therefore reproduce `2^n` work or representation.

That is a result about these two natural CassiFI encodings, not a lower bound on
all possible CassiFI algorithms. A surviving route would need a uniform
field-owned transition law or learned program that:

1. uses polynomially many field coordinates and bits for an `n`-variable CNF;
2. performs polynomially many bounded-precision operations;
3. returns a satisfying certificate on YES instances;
4. returns a checkable decision on NO instances;
5. avoids explicitly expanding independent Boolean modes or assignment
   identities.

The CassiFI finding is therefore `SUPPORTS` for bounded field computation and
`REJECT` for the tested `P = NP` route.

### Uniform clause-field continuation and resolution boundary

The next CassiFI implementation removes both exponential representation costs
identified above. `CassiFI/cassi_clause_field.py` stores a variable-length CNF
and its complete search state in one immutable float64 field tensor with shape
`[1, 9*M, 1]`. Every stored value is an exact integer bounded by `2^53 - 1`.
The nine planes contain:

1. clause lengths;
2. original and learned literals;
3. provisional assignments;
4. decision levels;
5. implication reasons;
6. the assignment trail;
7. decision literals;
8. first/second-branch phases;
9. status and cumulative resource counters, including proof work.

The capacity profile is fixed before a run. For `n` variables, `m` original
clauses, and at most `8n` learned clauses in the measured corpus,

```text
M = max(21, n, m + max(16, 8n), n[m + max(16, 8n)])
field bytes = 72M.
```

This is polynomial storage. It does not place complete assignments in action
identities or allocate a Cartesian product of Boolean modes.

Repeated calls to one fixed `step(state)` transition implement a uniform
chronological DPLL procedure:

- scan the field-resident clauses;
- apply one unit propagation when available;
- otherwise choose one unassigned variable by field-derived unresolved-clause
  occurrence count;
- on conflict, derive a clause from the conflicting clause and implication
  reasons, weaken it when necessary to the negation of the current decision
  prefix, store that decision nogood, chronologically backtrack, and flip the
  deepest untried decision;
- return `sat` with a complete assignment or `unsat` after the search tree is
  closed.

The learned decision clause is sound: resolution eliminates propagated
variables from the conflicting clause, leaving a clause falsified by the
current decisions. Weakening that core to the full decision nogood preserves
entailment. Learned clauses, decisions, phases, reasons, the trail, and proof
work counters are field coordinates. The host repeatedly invokes the same
transition and never proposes an assignment, chooses a branch, schedules a
search subtree, or retains an adaptive side table.

#### Proof-carrying output

Each conflict transition now emits the exact conflicting clause, the reason
clause for every eliminated propagated literal, every pivot and resolvent, the
derived conflict core, and any weakening to the stored decision nogood. When
both children of a decision prefix close, the runner resolves their nogoods on
that decision literal. An UNSAT run ends with the empty clause.

The resulting object is a chronological DPLL resolution DAG with linear
conflict derivations, weakening to decision nogoods, reuse of earlier learned
nogoods as lemmas, and a depth-first branch-closure tree. It is not a
truth-table transcript and it does not ask the verifier to trust the solver's
conflict labels. The proof object is nonadaptive output and is never fed back
into search.

`CassiFI/verify_p_vs_np_clause_field_probe.py` imports neither the field nor
the runner. It reconstructs the clause database, independently checks every
resolution pivot and resolvent, verifies each weakening, requires learned
clauses to match the field receipt, checks the branch-prefix and child
relations, and requires the root line to be the empty clause and to depend on
every conflict leaf. Focused tamper tests alter a conflict resolvent and a
branch-closure resolvent; both are rejected.

#### Exact corpus result

`CassiFI/run_p_vs_np_clause_field_probe.py` exercised 282 formulas:

- all 255 nonempty subsets of the eight full-width clauses on three variables;
- standard pigeonhole contradictions with 6, 12, and 20 variables;
- satisfiable and contradictory Tseitin parity formulas on three prism sizes;
- 18 planted random 3-SAT formulas from 6 through 16 variables near clause
  density 4.25.

The field returned 275 `sat` decisions and 7 `unsat` decisions, with no
resource exhaustion. Every SAT certificate passed direct clause evaluation,
and all seven UNSAT results produced complete resolution refutations. An
independent verifier exhaustively enumerated all assignments for 281 cases;
the remaining 20-variable case was independently reconstructed as the
standard 5-pigeons/4-holes contradiction. All 281 truth-table decisions
matched. On every satisfiable enumerated case, every learned clause preserved
every model of the original formula; that model-preservation check is
necessarily vacuous on UNSAT cases.

Each final field checkpoint was serialized, reloaded, and matched by exact
state digest. The receipt includes every original and learned clause, SAT
assignment or UNSAT proof, action counts, field byte count, resource counters,
problem digest, state digest, transition-trace digest, and proof digest.

The structured UNSAT profiles were:

| Family | Variables | Transitions | Conflicts | Proof inferences | Field bytes |
|---|---:|---:|---:|---:|---:|
| Pigeonhole 3 into 2 | 6 | 12 | 2 | 10 | 24,624 |
| Pigeonhole 4 into 3 | 12 | 53 | 6 | 51 | 101,952 |
| Pigeonhole 5 into 4 | 20 | 256 | 24 | 289 | 295,200 |
| Odd Tseitin prism 3 | 9 | 111 | 16 | 95 | 62,208 |
| Odd Tseitin prism 4 | 12 | 287 | 48 | 223 | 110,592 |
| Odd Tseitin prism 5 | 15 | 703 | 96 | 511 | 172,800 |

Across the full corpus, the verifier checked 226 conflict derivations, 1,018
linear conflict-resolution steps, 125 weakenings, and 189 branch-closure
resolutions: 1,332 proof inferences in total. The largest serialized proof
payload was 55,731 bytes.

The corresponding satisfiable Tseitin instances required 10, 13, and 16
transitions and no proof inferences. For the contradictory instances,
descriptive regressions over only three sizes give `0.4438` added bits of
transition count and `0.4046` added bits of proof-inference count per variable.
The three standard pigeonhole points give `0.3137` and `0.3448`, respectively.
These finite measurements illustrate the mechanism; they are not the
asymptotic argument.

Twelve independent variable/clause/literal permutations of one planted
10-variable formula all returned verified certificates. Their work ranged
from 26 to 28 transitions, a ratio of `1.0769`. Declaring six unused variables
left the transition count unchanged while increasing allocated field bytes by
`2.2244`. Thus the decision is representation invariant, the heuristic work
has small order sensitivity on this control, and unused declared capacity
remains visible rather than free.

#### Complexity theorem for this solver

Let `PHP_(h+1)^h` be the standard pigeonhole CNF used by the probe: every one
of `h+1` pigeons occupies at least one of `h` holes, and no hole contains two
pigeons. It has

```text
N = h(h+1)
```

Boolean variables. Haken proved that every unrestricted resolution refutation
of this family has size `2^Omega(h)`, equivalently
`2^Omega(sqrt(N))` as a function of the variable count.

The clause-field execution maps to such a refutation with polynomial overhead.
For `T` field transitions, each conflict derivation eliminates at most `N`
propagated variables, there is at most one conflict per transition, and the
branch closure contributes fewer resolutions than conflict leaves. Hence the
emitted resolution DAG has `O(N*T)` inference lines. If `T` were polynomial in
the CNF input length, this would yield polynomial-size resolution refutations
for the standard pigeonhole family, contradicting Haken's theorem.

Therefore the exact clause-field transition law has superpolynomial
worst-case transition count. Polynomial instantaneous state, fixed precision,
field ownership, and clause learning do not change that conclusion. This is a
proof for the implemented resolution-bounded solver class—not for all
algorithms, CassiFI programs, or deterministic Turing machines—and therefore
does not establish `P != NP`.

## 7. Relation to known routes

### Continuous-time SAT

Ercsey-Ravasz and Toroczkai prove useful dynamical properties for an analog SAT
flow with positive clause variables `a_m`, including the absence of
nonsolution fixed-point attractors in their model. They also state that
polynomial continuous time comes at the expense of exponential energy
fluctuations, and report exponential digital integration-step behavior in the
hard regime. This is precisely the resource boundary a Cassi route must cross,
not rename.

### Ising, annealing, and optical machines

Physical annealers and coherent Ising machines can be effective heuristics,
but benchmark studies on hard Ising families do not supply worst-case
polynomial exact algorithms. Coupling range, embedding size, annealing time,
precision, and repeated success probability all count. A field superposition
of many modes is not parallel evaluation of exponentially many assignments
unless exponentially many distinguishable degrees of freedom or precision are
available at readout.

### Memcomputing

Memcomputing supplies a richer nonlinear memory architecture and can be
classically simulated, but empirical solver performance and continuous-time
claims are not a worst-case polynomial proof. Published critiques emphasize
spectral/precision and total-resource accounting. Its most useful lesson here
is architectural: persistent violated-constraint memory matters. The bounded
Cassi crossover tested that lesson and found that a fixed cap changes outcomes.

### Circuit lower bounds

A direct `P != NP` attack would need lower bounds for unrestricted
polynomial-size computation, not merely for a local lattice, bounded-depth
network, monotone circuit, or fixed PDE. Relativization, natural proofs, and
algebrization explain why broad reusable lower-bound templates repeatedly
stall. Cassi's geometry does not by itself evade those barriers.

The algorithms-to-lower-bounds program remains relevant: even modest general
Circuit-SAT improvements imply major circuit lower bounds. The clause-field
work does not provide such an improvement. It instead gives a complete
restricted lower-bound result: once the field transition is translated to
resolution, classical proof complexity rules out polynomial worst-case search
for that architecture without confusing wave propagation with computation.

## 8. What survives

### Result A—linear-sector theorem

The fixed-source Cassi field is spectrally reducible and fast-forwardable at
fixed precision. This is useful for simulation, preconditioning, and conflict
transport, but excludes it as the missing combinatorial engine.

### Result B—bounded-coherence obstruction

The specific bounded clause-coherence potential has strict nonsolution traps
on small satisfiable instances. Any successor must change the escape mechanism,
not tune the timestep, damping, or corpus.

### Result C—resource-accounting criterion

For any proposed field SAT solver, if the encoding size, coefficients,
precision, evolution steps, controller work, and readout are all polynomially
bounded, then a polynomial-accuracy digital simulation is itself the desired
algorithm. If one of those quantities is not polynomially bounded, it is the
hidden computational resource. A claimed physical speedup must prove the
bounds rather than infer them from small runs.

### Result D—resolution lower bound for uniform field-owned search

The clause field decides both SAT and UNSAT with a constant operation
vocabulary, polynomial exact state, persistent learned conflict clauses, and
no host-owned candidate schedule. Its complete traces produce independently
checkable resolution refutations. Haken's standard pigeonhole lower bound and
the `O(N*T)` trace translation prove that its worst-case transition count is
superpolynomial. Any successor must leave this resolution-bounded DPLL
mechanism, not merely accelerate its field representation.

### Result E—hybrid proof field beyond resolution

The successor in `CassiFI/cassi_hybrid_inference.py` keeps all adaptive proof
state in a second immutable nine-plane field tensor. Its typed lines are source
clauses, derived clauses, pseudo-Boolean inequalities, GF(2) equations, and
fresh-variable definitions. Premise pointers, inference rules, status, line
counts, and resource counters occupy the same tensor. All coordinates are exact
integers in float64's exact range; overflow and capacity limits return
`exhausted`, never UNSAT.

The fixed transition law implements clause-to-inequality conversion,
nonnegative integer scaling, addition, exact-coefficient division with
floor-rounded right-hand side, CNF-grounded bounded-width parity import, GF(2)
addition, exact-cardinality-to-parity bridges, acyclic disjunction extensions,
and resolution. An independent standard-library checker reconstructs every
serialized inference from its premises.

For the standard `(h+1)`-pigeons/`h`-holes formula, let

```text
m = (h+1) + h * C(h+1, 2).
```

The implemented construction emits `m` clause conversions, `m-1` additions,
`h(h-2)` nonnegative scalings, and `h(h-1)` divisions: exactly
`2m-1+2h^2-3h` derived lines. This is polynomial in the CNF size and therefore
removes Haken's resolution lower bound as an obstruction to this successor.
At `h=12`, the measured proof had 949 input clauses and 2,149 derived lines,
with maximum integer magnitude 23.

For the odd-charge degree-three prism Tseitin family with `r` rungs, the
construction emits `8r` input clauses, `8r` clause conversions, `2r` recovered
parity equations, and `2r-1` GF(2) additions, for `20r-1` total proof lines.
The largest measured case, `r=16`, had 48 variables and 319 lines.

One adversarial crossed case requires both systems: cutting planes derive an
exact-one equality, the bridge extracts its odd parity, and GF(2) cancellation
with a CNF-grounded even-parity equation yields `0 = 1 (mod 2)`. A separate
case introduces a fresh disjunction and uses its defining clauses in a checked
resolution refutation. Satisfiable, incomplete-premise, and forced-exhaustion
controls make no false UNSAT claim.

This result strengthens the mechanism but does not settle `P` versus `NP`.
The controller constructs proofs for recognizable bounded structural patterns.
No theorem shows polynomial-size proofs or polynomial-time discovery for every
unsatisfiable CNF, and a polynomially bounded refutation system alone would
establish `NP = coNP`, not by itself provide the required SAT algorithm.

### Result F—connected matched exact-one/parity theorem

Let `b >= 4` be even. A formula belongs to the connected matched exact-one
class when its CNF syntax can be partitioned into:

1. `b` disjoint three-variable blocks, each represented by the positive
   three-literal clause and all three negative pair clauses, hence asserting
   exactly one true variable; and
2. a perfect matching of all `3b` variable occurrences, with every matching
   edge represented by the complete two-clause CNF of a binary parity equation.

Every matching edge joins different blocks, and the quotient graph on blocks
must be connected. The standard-library verifier recognizes this structure
from clauses and literal signs alone. It receives no family name or generator
metadata.

Write the block equations and matching equations over GF(2) as

```text
XOR_{x in B_i} x = 1
x_u XOR x_v       = ell_e.
```

XORing all equations cancels every variable exactly twice: once in its block
and once in its matching edge. The result is

```text
0 = (b mod 2) XOR XOR_e ell_e.
```

Consequently, every recognized instance for which the right-hand side is one
is UNSAT. This is a proof of soundness for the whole recognized class, not an
empirical inference from the sampled formulas. Connectedness prevents the
construction from padding a local contradiction with unrelated components.

The implemented canonical subfamily connects each block to its two cycle
neighbors and pairs the remaining ports across adjacent even/odd block pairs.
For the exact scaling sequence, one matching label is odd and all others are
even. At every measured size, the deterministic controller derives the
contradiction without branching, extension variables, resolution, family
labels, or proof hints. Its exact line counts are:

```text
variables                         3b
input clauses                     7b
clause-to-PB lines                7b
parity imports                    3b/2
PB additions                      4b - 1
PB divisions                      b
cardinality-to-parity bridges     2b + 1
GF(2) additions                   5b/2
derived proof lines               18b
total proof lines                 25b.
```

The largest stored integer magnitude is `b`. With the fixed profile used by
the runner, `max_lines = 83b + 256` and the dense field occupies exactly

```text
17928b^2 + 55296b bytes.
```

A direct loop audit gives conservative controller bounds of `O(b^3)` time and
`O(b^2)` temporary space when `solve` constructs the proof plan once. Calling
the public one-transition `step` interface throughout reconstructs that plan
`18b` times and is therefore bounded by `O(b^4)`. Both are polynomial in the
encoded CNF length; the slower bound is an implementation cost, not a hidden
oracle.

The deterministic guarantee extends to every parity-label placement on this
canonical topology for which `XOR_e ell_e = 1`. Complete pair encodings import
all `3b/2` matching equations; cutting planes derive all `b` exact block
cardinalities; and Gaussian elimination must expose their inconsistent sum.
The bridge planner now retains one representative for each
coefficient/right-hand-side pair, so duplicate derivations cannot inflate this
schedule. A conservative bound for arbitrary labels is

```text
max proof lines              40b^2 + 32b + 256
maximum integer magnitude    3b
field bytes                  216b(40b^2 + 32b + 256).
```

The corresponding one-plan controller and temporary-space bounds are
`O(b^3)`; repeated single-transition stepping is `O(b^5)`. The looser storage
and step bounds account for worst-case GF(2) row reduction rather than assuming
the one-odd-edge elimination order.

Runs at `b = 4, 6, 8, 12, 16, 24` matched the exact one-odd-edge formulas.
The `b=24` instance has 72 variables, 168 input clauses, 432 derived lines,
600 total proof lines, maximum integer magnitude 24, and 11,653,632 field
bytes. Dense odd-label stress cases at `b = 4, 6, 8, 12` also closed within
the general bound. The behavioral suite exhaustively checks all 64 labelings
at `b=4` and all 512 labelings at `b=6`: every globally inconsistent labeling
produces a checked refutation, while no globally consistent labeling produces
a false root. An adjacent consistent `b=4` instance has a truth-table model
and ends `exhausted`.

This settles soundness for the whole syntax-recognized class and deterministic
polynomial proof discovery for every globally inconsistent labeling on the
canonical infinite topology. The hybrid proof field alone does not decide
globally consistent members, extend the discovery proof to every connected
matching topology, or settle unrestricted CNF. It also does not establish
efficient automatizability of the combined proof system in general.

### Result G—total decision on the canonical mixed topology

The canonical topology has more structure than the global parity proof uses.
Write the variables of block `i` as `x[i,0]`, `x[i,1]`, and `x[i,2]`, and set
`p[i] = x[i,1]`. If `c[i]` is the label on the cycle edge from `x[i,1]` to
`x[i+1,0]`, the cycle constraints and exact-one condition force

```text
x[i,0] = p[i-1] XOR c[i-1]
x[i,2] = 1 - x[i,0] - p[i].
```

The second expression is a bit precisely when block `i` has one true
variable. For each adjacent even/odd pair, the only remaining condition is

```text
x[2j,2] XOR x[2j+1,2] = d[j],
```

where `d[j]` is that pair's chord label. This gives a constant-width dynamic
program. It separately tracks the two hypotheses for the boundary value
`p[b-1]`; within each hypothesis, its only carried state is the previous
`p` bit. One transition enumerates the four choices for
`(p[2j], p[2j+1])`, rejects choices that violate either exact-one block or
the chord, and stores the first predecessor for each reachable carry. After
`b/2` pair transitions, an accepting state is one whose carry equals its
boundary hypothesis.

This condition is necessary and sufficient. Every satisfying assignment
specifies one enumerated path and survives every local check. Conversely,
backtracking any accepting path fixes all `p[i]`, after which the displayed
equations reconstruct all remaining variables and satisfy every block,
cycle edge, and chord. If neither boundary hypothesis closes, no assignment
exists. The field therefore returns either a complete Boolean assignment or
the full unreachable-final-layer certificate; it never returns `exhausted`
for a recognized canonical member.

For even `b >= 4`, the exact resource counts are

```text
variables                         3b
input clauses                     7b
field transitions                 b/2
candidate checks                  8b
float64 field values              12 + 21b/2
field bytes                       96 + 84b.
```

There are 16 candidate checks per block pair: two boundary hypotheses, two
prior carries, and four choices for the pair's outgoing bits. The tensor
stores eight header counters, `3b/2` labels, four reachability bits for each
of `b/2+1` layers, two predecessor bits for each of four states in every
noninitial layer, and `3b` assignment bits. These sum to `12 + 21b/2`
float64 values. Bulk dynamic-program state construction is `O(b)`, while
recognition, CNF canonicalization, and certificate digest serialization make
the complete public solve `O(b log b)`. Persistent state and the abstract
certificate entry count are `O(b)`. Replaying the immutable public `step`
interface is `O(b^2)`, because every transition validates, copies, and hashes
the full `O(b)` tensor.

The implementation recognizes the class from the complete CNF and then keeps
the canonical labels, all reachability layers, deterministic predecessors,
assignment, status, and resource counters in one immutable field tensor.
There is no learned side table, family-name branch, model fallback, or
host-supplied proof plan.

The receipt contains 600 decisions. Exhaustive label coverage gives:

| Blocks | Labelings | SAT | UNSAT | Parity-consistent UNSAT |
|---:|---:|---:|---:|---:|
| 4 | 64 | 31 | 33 | 1 |
| 6 | 512 | 235 | 277 | 21 |

Independent enumeration of all `3^b` exact-one block choices gives the same
SAT/UNSAT partition in the behavioral suite. The 22 parity-consistent UNSAT
cases show that the decision field is strictly stronger than the global
parity criterion. Twenty-four additional cases cover zero, one-odd-edge, and
dense-odd-edge label patterns at
`b = 8, 12, 24, 48, 96, 192, 384, 768`. The `b=768` instances decide
2,304-variable, 5,376-clause formulas using exactly 384 transitions, 6,144
candidate checks, and 64,608 field bytes.

The standard-library verifier imports neither the field nor the runner. From
the serialized labels and clauses, it independently reconstructs every
canonical formula, all dynamic-program layers and deterministic predecessors,
the accepting path or its absence, each SAT assignment, the complete tensor
layout, state and certificate digests, and all aggregates. It additionally
truth-tables all 64 `b=4` cases. State digests provide checkpoint integrity;
the independent recurrence and assignment reconstruction provide the
semantic proof check.

This bounded-width construction is a total deterministic polynomial-time
algorithm for an infinite CNF class with the exact `1..3b` block/port numbering
and full canonical clause set. Variable permutations must be normalized before
using its recognizer. Its recurrence is specific to the canonical topology;
the general matching reduction below removes that topology restriction for
the complete connected matched exact-one/parity class.

### Result H—total decision on every connected matched topology

For even `b >= 4`, the connected matched exact-one/parity class has a
stronger characterization: it is an exact perfect-matching problem. Let each
variable occurrence be one of three distinct variables in exactly one
exact-one block, and let every
variable belong to exactly one binary parity edge. The block variables are
pairwise disjoint, every parity edge joins two different blocks, and the
quotient graph is connected. These are all checked from the complete CNF;
there are no hidden occurrence aliases or omitted equality constraints.

Construct an auxiliary edge-identity multigraph `H` as follows:

1. create one vertex `v_i` for each exact-one block;
2. replace a parity-zero edge by one direct edge between its two block
   vertices; and
3. replace a parity-one edge `e` by a fresh subdivision vertex `s_e` and the
   two edges from `s_e` to the endpoint block vertices.

A satisfying assignment gives a perfect matching. For a parity-zero edge,
select the direct edge precisely when both endpoint variables are true. For a
parity-one edge, match its subdivision vertex to the block containing the
unique true endpoint. Every block has exactly one true variable, so every
block vertex is matched once; every subdivision vertex is also matched once.

Conversely, a perfect matching sets both endpoints of a selected direct edge
to one and both endpoints of an unselected direct edge to zero. At each
subdivision vertex, it sets the endpoint on the selected side to one and the
other endpoint to zero. Matching every block vertex once enforces exactly one
true variable in each block. The direct and subdivided cases respectively
enforce parity zero and parity one. These maps are inverse when edge identity
is retained, proving a bijection between satisfying assignments and perfect
matchings of `H`.

Parallel parity-zero edges between the same block pair represent different
source variables and therefore remain distinct in the theorem graph. The
decision implementation may collapse them in its adjacency relation because
parallel edges do not change perfect-matching existence; it retains every
source edge and canonically lifts a selected block pair to the first applicable
source edge when reconstructing an assignment. The strict recognizer rejects
same-block parity edges, repeated variables, incomplete parity encodings,
disconnected quotients, and any formula outside the promised occurrence
model.

If `m_1` of the `3b/2` parity edges have label one, then

```text
auxiliary vertices N = b + m_1        <= 5b/2
auxiliary edges    E = 3b/2 + m_1     <= 3b.
```

The field uses deterministic Edmonds blossom search with ascending roots,
sorted adjacency, FIFO exploration, deterministic blossom contraction, and
no randomized or model-supplied choices. A standard one-pass root schedule
gives the conservative `O(N^3) = O(b^3)` matching bound and `O(b)` live
scratch space on this sparse graph. The implementation stores the source
incidence, auxiliary edges, current matching, terminal barrier, assignment,
and exact work counters in one immutable tensor:

```text
float64 field values = 12 + 17b + 5m_1
field bytes          = 96 + 136b + 40m_1.
```

CNF canonicalization adds `O(b log b)` work. Public one-root stepping performs
the same `N` blossom searches as bulk solve; full-field validation, copying,
and hashing add `O(b^2)` work and do not change the `O(b^3)` conservative
bound.

The mathematical algorithm uses ordinary `O(log b)`-bit vertex identifiers and
counters. The concrete float64 profile additionally rejects any size whose
conservative `N^3` counter range could exceed exact integer representation, so
numeric rounding cannot silently become a matching decision.

For SAT, the certificate contains a perfect matching and complete satisfying
assignment. For UNSAT, the implementation emits a Tutte barrier
`S subseteq V(H)` satisfying

```text
odd_components(H - S) > |S|.
```

Every perfect matching would have to match each odd component through a
distinct vertex of `S`, so this strict inequality is a direct proof that no
perfect matching exists. The independent checker reconstructs `H` from the
source clauses and verifies the inequality by connected-component traversal
in `O(N+E)`. The current even-`N` barrier extractor identifies the
Gallai-Edmonds sets by at most `N` additional deterministic matching runs, so
its conservative construction bound is `O(b^4)`. Connected odd-`N` instances
use the immediate empty-set barrier. Certificate verification remains linear
regardless of extraction cost. Thus the implemented total SAT path is
`O(b^3)`, while the implemented even-`N` UNSAT path including proof-grade
witness extraction is `O(b^4)`.

The receipt contains 672 decisions:

| Quotient topology | Labelings | SAT | UNSAT | Parity-consistent UNSAT |
|---|---:|---:|---:|---:|
| simple `K_4` | 64 | 31 | 33 | 1 |
| connected four-block multigraph | 64 | 31 | 33 | 1 |
| triangular prism | 512 | 241 | 271 | 15 |

Those 640 cases exhaust every edge labeling and agree with independent
enumeration of all `3^b` exact-one choices. Additional `K_3,3`, Petersen, and
prism cases exercise distinct cubic topologies and scaling through `b=192`.
The full receipt has 324 SAT and 348 UNSAT outcomes, including 23
parity-consistent UNSAT cases. It replays 45 decisions through the immutable
public `step` path. At `b=192`, the largest case has 576 variables, 480
auxiliary vertices, and 37,728 field bytes.

The standard-library verifier imports neither field nor runner. For all 672
cases it independently recognizes the source class, reconstructs the
provenance-preserving auxiliary graph, checks each perfect matching or Tutte
barrier, evaluates every SAT assignment against every source clause, decodes
the full persisted tensor, checks state/problem/certificate digests, and
rebuilds all aggregates. Four malformed-source or damaged-state controls fail
closed.

This is a total deterministic polynomial-time theorem for the entire
syntax-recognized connected matched exact-one/parity class, including
unbounded-width quotient families. It is not a polynomial-time algorithm for
unrestricted SAT and does not establish `P = NP`; it identifies the class as a
disguised general-graph perfect-matching problem already in `P`.

### Result I—parameterized total decision at the occurrence-alias boundary

The next field breaks the occurrence matching in the smallest regular way.
Its source language is positive exact-one CNF with three distinct variables
per clause and every variable occurring exactly two or three times. Let `c`
be the number of clauses and let `k` be the number of degree-three variables.
The incidence identity is

```text
3c = 2(n-k) + 3k,       so       n = (3c-k)/2.
```

For each of the `2^k` assignments to the degree-three variables:

1. a clause already containing two selected degree-three variables closes the
   branch as contradictory;
2. every degree-two variable incident to an already satisfied clause is
   forced false;
3. each remaining degree-two variable joins its two unsatisfied incident
   clauses by an edge; and
4. the branch is satisfiable exactly when this residual multigraph has a
   perfect matching.

The correspondence is exact. A satisfying assignment selects one residual
edge at each unsatisfied clause, and every selected degree-two variable covers
both of its occurrences, so the selected edges form a perfect matching.
Conversely, a perfect matching sets its source variables true and every other
degree-two variable false, satisfying each residual clause exactly once while
leaving every previously satisfied clause unchanged.

The resulting deterministic algorithm is fixed-parameter tractable in `k`:

```text
decision search                         O(2^k c^3)
complete UNSAT proof construction       O(2^k c^4) conservative
immutable persistent field state        13 + 6c float64 values
SAT certificate                         O(c)
complete UNSAT certificate              O(2^k c)
certificate checking                    O(2^k c) plus serialization
```

The abstract algorithm uses ordinary `O(log c)`-bit integer identifiers and
counters. The concrete float64 field rejects any profile whose identifiers or
conservative `2^k c^3` work-counter range could exceed exact integer
representation.

The field stores the canonical clauses, occurrence degrees, cubic-variable
indices, branch cursor, exact work counters, status, and final assignment in
one immutable tensor. One public `step` evaluates one complete cubic
assignment. SAT certificates contain the selected branch, a perfect matching,
and the reconstructed source assignment. UNSAT certificates contain one
ordered witness for all `2^k` branches: a clause conflict, an odd residual
order, or an independently checkable Tutte barrier.

This extension reaches an NP-complete boundary rather than another tractable
subclass. Cubic Planar Monotone 1-in-3 SAT, proved NP-complete by Moore and
Robson, is the special case in which every variable has degree three; it lies
inside the recognizer with `k=n`. Membership in NP is immediate from a Boolean
assignment. Therefore the unrestricted recognized degree-two/degree-three
class is NP-complete, and the exponential parameter cannot be replaced by a
general polynomial bound without proving `P = NP`.

The receipt contains 65 decisions: 56 small cases checked by independent full
truth tables and nine larger scaling or stress cases. The outcomes are 43 SAT
and 22 UNSAT. Public immutable steps are replayed in 29 cases. The largest
case has 48 clauses, 65 variables, 14 cubic variables, and 16,384 available
branches; its complete search checks all 16,384 branches while persistent
state remains 2,408 bytes. Every checkpoint restores exactly.

The standard-library verifier imports neither field nor runner. It
independently recognizes the occurrence promise, reconstructs every residual
graph, checks every branch conflict, perfect matching, odd-order obstruction,
or Tutte barrier, evaluates all SAT assignments, truth-tables every enumerated
case, decodes every tensor coordinate, verifies all digests and counters, and
rebuilds the receipt aggregates. All 65 certificates and four fail-closed
controls pass.

The result isolates the new obstruction precisely. Quotient topology still
reduces to perfect matching after a branch is fixed. The hard resource is the
globally consistent reuse of degree-three variables across three clauses,
which creates an exponential family of coupled matching residuals.

### Result J—elementary compression works empirically; no global bound follows

The alias formula is equivalently an exact-cover instance on the clause
vertices. Every degree-two variable is a two-edge and every degree-three
variable is a three-edge. A direct recurrence chooses an uncovered clause and
branches over the at most three still-available incident variables. If a
chosen variable has degree `d`, its `d` clauses leave the residual instance.

One permitted local configuration has one available degree-three variable and
two degree-two variables. Its recurrence is

```text
T(c) <= T(c-3) + 2 T(c-2),
```

with characteristic equation `rho^3 = 2 rho + 1` and positive root
`rho = 1.618033988749895`. The all-cubic local configuration instead gives
`T(c) <= 3 T(c-3)`, with base `3^(1/3) = 1.442249...`.

Neither local relation is a global bound for the implemented clause-selection
rule. A permitted degree-two-only clause has three choices that each remove
two clauses, giving the local relation `T(c) <= 3 T(c-2)`. The four-clause
fixture
`(123), (145), (246), (356)` realizes exactly that root configuration.
Consequently the earlier golden-ratio global interpretation is withdrawn.

This does remove large amounts of redundant work in the measured corpus.
Across the same 65 alias cases, the cubic-bit solver checks 25,425 assignments,
whereas deterministic memoized exact-cover search visits 957 residual states.
The largest comparison is 16,384 assignments versus 395 residual states.
Exact-cover search visits fewer states on 31 cases, the same number on two,
and more on 32; the increases occur primarily where the binary schedule finds
a SAT branch immediately.

The exact-cover search has no new competitive worst-case theorem. Wahlström's
published monotone one-in-three upper bound, recorded as `O*(1.0984^n)`,
remains the applicable global benchmark for this class. No asymptotic
comparison with the measured cover-state counts is justified without a
correct global recurrence.

The independent Result I matching-branch theorem still has the proved
parameterized bound `O(2^k c^3)`. Comparing only that theorem's exponential
term with `1.0984^n`, and using `n = (3c-k)/2`, favors matching-branch when

```text
k/c < 3 log2(1.0984) / (2 + log2(1.0984))
    = 0.19022661804781446.
```

The direct exact-cover search is therefore retained only as an empirical
analysis control rather than added as a second field runtime.

The second compression attempt tests the standard planar-matchgate route.
Write the arity-three variable signature as
`EQ3 = [1, 0, 0, 1]` and the clause signature as
`EXACT1_3 = [0, 1, 0, 0]`, indexed by Hamming weight. Every matchgate signature
satisfies the parity condition: either all even-weight or all odd-weight
coordinates vanish.

For a uniform invertible basis

```text
A = [[a, b],
     [c, d]],
```

the transformed equality coordinates are

```text
[a^3+b^3, a^2 c+b^2 d, a c^2+b d^2, c^3+d^3].
```

The analysis applies the corresponding inverse dual basis to `EXACT1_3`,
tests all four even/odd parity assignments for the two signatures, and repeats
the calculation under both row/column transpose conventions. In each of the
eight cases it adds

```text
z(ad-bc)-1 = 0
```

to enforce invertibility and computes the Gröbner basis over the rationals.
Every ideal reduces to `[1]`. Thus no solution exists even over the algebraic
closure: one uniform invertible `2x2` basis cannot make both local signatures
pass the necessary matchgate parity condition.

This is a scoped algebraic obstruction. It rules out the standard
uniform-basis planar-matchgate/Pfaffian compression of this incidence
formulation. It does not rule out nonuniform edge bases, larger gadgets,
higher-dimensional encodings, non-matchgate determinant identities, or
unrelated algorithms.

The analysis receipt binds the 65-case alias receipt by SHA-256. An independent
script rebuilds all 65 exact-cover searches, verifies their assignments and
verdicts, independently truth-tables all 127 degree-two/degree-three formulas
with four or five variables, recomputes both recurrence constants and all
eight Gröbner ideals, and rebuilds every aggregate. It finds 94 SAT and 33
UNSAT formulas in the exhaustive small set; every result agrees.

### Result K—cubic incidence kernels isolate the next algebraic boundary

In the degree-three-only part of the alias class, let `M` be the
clause-by-variable incidence matrix. If there are `n` clauses, counting the
three incidences on both sides shows that there are also `n` variables.
Every row and every column of the square `0/1` matrix `M` has sum three. Exact
one-in-three satisfiability is

```text
M x = 1,       x in {0,1}^n.
```

The affine change of coordinates

```text
z = 3x - 1
```

gives an exact equivalence:

```text
M x = 1, x in {0,1}^n
    iff
M z = 0, z in {-1,2}^n.
```

For the forward direction,
`M z = 3 M x - M 1 = 3 1 - 3 1 = 0`. For the reverse direction,
`x = (z+1)/3` is Boolean and recovers `M x = 1`. Thus the remaining
combinatorics is not Gaussian consistency over the rationals. It is the
two-point alphabet intersection

```text
ker(M) intersect {-1,2}^n.
```

Two immediate UNSAT corollaries are polynomial. If `M` has full column rank,
its kernel contains only zero, which is outside the alphabet. Summing all
rows of `M x = 1` gives

```text
3 sum_i x_i = n,
```

so `n` must be divisible by three.

The implemented algorithm then computes a deterministic exact rational RREF.
Choose the nonpivot coordinates `z_F` freely from `{-1,2}` and write each
pivot coordinate as

```text
z_p = sum_j a[p,j] z_F[j].
```

Each requirement `z_p in {-1,2}` is a Boolean relation on the free
coordinates with nonzero coefficient `a[p,j]`. If every pivot relation touches
at most two free coordinates, its forbidden tuples compile directly to 2-CNF.
An implication-graph SCC computation therefore decides the whole system in
polynomial time, with an explicit SAT assignment or contradictory-component
certificate. Exact rational elimination also has polynomial bit complexity
for these integer matrices. This proves a tractable subclass parameterized by
pivot support rather than nullity.

The support criterion depends on the chosen column basis. A canonical
deterministic RREF gives one sufficient certificate, but another complement of
free columns can change every pivot support. Result L computes the exact
minimum over all column bases for targeted controls. When no supplied
width-two basis is available, the current total decision falls back to
enumerating all `2^nullity` alphabet assignments.

The 34-case receipt contains 15 SAT and 19 UNSAT decisions. Seven UNSAT cases
are full rank, nine fail the divisibility condition, 15 ordinary cases reduce
to 2-SAT, one further case has an empty pivot relation, and only two
support-three cases use exact enumeration. The three singular,
divisibility-compatible UNSAT witnesses separate increasingly strong failures:

1. a one-dimensional kernel whose basis forces a zero coordinate;
2. a one-dimensional full-support kernel that still has no allowed global
   scaling; and
3. a three-dimensional kernel whose ternary relation system has no satisfying
   alphabet vector.

Connectivity does not control the parameter. Twelve connected switched-block
families satisfy a proved rank-one-update lower bound on nullity. The largest
SAT family has 96 variables and nullity 33; the largest UNSAT family has 100
variables and nullity 32. The support-two reduction decides both without
materializing `2^33` or `2^32` assignments.

For every measured canonical pivot relation of arity at most three, the runner
also computes the standard Schaefer closure tests. The canonical support-three
SAT residual is jointly 0-valid. The canonical support-three UNSAT residual
has no one class shared by all its pivot relations among 0-valid, 1-valid,
Horn, dual-Horn, bijunctive, and affine. An independent implementation
recomputes each truth table and closure. These statements classify those
particular coordinate systems only. Result L finds a binary-support basis for
both formulas, so the canonical Schaefer profile is not a basis-invariant
obstruction.

The independent verifier recomputes all 34 rational kernels, decisions,
certificates, and relation profiles. It also exhaustively checks 574
fixed-gauge cubic formulas through six variables: 521 are SAT and 53 are
UNSAT, requiring 35,928 pointwise Boolean assignment checks. Every result
agrees. This is a stronger compression than raw cubic-variable enumeration,
but it does not settle `P` versus `NP`: the source class contains Cubic Planar
Monotone 1-in-3 SAT, so a polynomial algorithm for every such two-point kernel
intersection would itself prove `P = NP`.

### Result L—basis optimization removes a coordinate artifact but leaves invariant width three

Let `N` be the column matroid of the cubic incidence matrix `M`. Choose any
column basis `B` of `N`, and let `F` be its complement. Matroid duality says
that `F` is a basis of `N*`. Eliminating relative to `B` gives

```text
z_B = A_B,F z_F.
```

For each `b in B`, the nonzero coefficients in its row are exactly the
elements of

```text
D_N(b,B) \ {b} = C_N*(b,F) \ {b},
```

where `D_N(b,B)` is the fundamental cocircuit in `N` and `C_N*(b,F)` is the
fundamental circuit in the dual. Define the exact coordinate width

```text
omega(M) =
    min over column bases B
    max over b in B |D_N(b,B) \ {b}|.
```

Equivalently, `omega(M) <= 2` exactly when the complementary ground-set basis
`F` frames the dual matroid: every other ground-set element is spanned by at
most two elements of `F`. This is stronger than saying that some
row-equivalent matrix has at most two nonzeros per column, because such an
external frame need not consist of original variable columns.

The 2-SAT theorem is therefore basis-independent in its correct form:
**given** a column basis witnessing width at most two, exact elimination,
relation construction, implication SCCs, and witness reconstruction take
polynomial time. The basis is checked by exact rational elimination, so it is
a polynomial-size certificate for membership in this tractable class.

[`cubic_kernel_decision.py`](../../../CassiFI/cubic_kernel_decision.py) now
accepts such a basis explicitly, and `cubic_kernel_basis_width` computes the
exact optimum on small matrices by checking every rank-sized column subset.
The evidence census is:

|Control|Status|Subsets checked|Column bases|Maximum-support histogram|Exact minimum|
|---|---:|---:|---:|---:|---:|
|original canonical support-three SAT, `n=9`|SAT|84|36|`2:24, 3:12`|2|
|original canonical support-three UNSAT, `n=15`|UNSAT|455|128|`2:60, 3:68`|2|
|greedy exchange trap, `n=9`|SAT|84|51|`2:8, 3:43`|2|
|all-bases-ternary, `n=12`|SAT|220|136|`3:136`|3|
|all-bases-ternary, `n=15`|UNSAT|455|237|`3:237`|3|

Thus both formulas previously used as canonical support-three controls move
to the 2-SAT branch under an alternative basis and inspect zero alphabet
assignments. Canonical RREF support was an artifact of coordinate choice.
However, basis choice is not a universal cure: the other SAT and UNSAT
matrices have support three for every one of their 136 and 237 column bases.

The analyzer checked 1,298 column subsets and found 588 bases. The independent
verifier imports neither analyzer nor decision implementation; it reconstructs
every rational system, coefficient support, basis histogram, optimum,
certificate digest, optimized 2-SAT decision, original SAT or UNSAT witness,
dual small-circuit profile, and complete one-column basis-exchange graph.

This produces a larger **certificate-bearing** polynomial class, but the exact
optimizer itself costs

```text
binomial(n, rank) poly(n).
```

It therefore does not yet produce a larger unassisted polynomial-time SAT
subclass. The next algorithmic problem is to find a width-two ground-set frame
of the dual in polynomial time when one exists, or to decide the
invariant-width-three cases without enumerating bases or alphabet vectors.
### Result M—polynomial islands and a basis-exchange obstruction

The frame-basis question is not uniformly mysterious. Three exact subclasses
are polynomial.

First, if the nullity `k = n - rank(M)` is fixed, the complementary dual basis
`F` has `k` elements. Enumerating all `binomial(n,k) = O(n^k)` candidates,
checking independence, and checking every fundamental circuit gives a
polynomial algorithm for each fixed `k`. This covers all five finite
basis-width controls in the current receipt, whose dual rank is three, but not
a family in which nullity grows with `n`.

Second, suppose the dual column matroid `N*` is graphic. A basis `F` is then
a spanning forest. For a nonforest edge `b` joining vertices `u` and `v`, its
fundamental circuit consists of `b` and the unique `u`-`v` path in `F`.
Therefore the circuit size after removing `b` is the forest distance between
its endpoints, and `omega(M) <= 2` is exactly the unweighted tree-2-spanner
condition, component by component. [Cai and Corneil](https://doi.org/10.1137/S0895480192237403)
give a linear-time construction for tree 2-spanners in unweighted graphs.

Third, suppose the primal column matroid `N` is graphic. A basis `B` is a
spanning forest, and the fundamental cocircuit of a forest edge is the cut
induced by deleting that edge. Its cardinality is the number of graph-edge
detours using the tree edge, including the tree edge itself. Consequently
`omega(M) <= 2` is exactly spanning-tree congestion at most three.
[Otachi, Bodlaender, and van Leeuwen](https://ics-archive.science.uu.nl/research/techreps/repo/CS-2010/2010-007.pdf),
Theorem 4.6, gives a linear-time algorithm for unweighted `k`-STC for
`1 <= k <= 3`.

The recognition statement is an oracle-model statement. [Seymour](https://doi.org/10.1007/BF02579179)
gives a polynomial graphicness test from an independence oracle. Given an
exact rational matrix, an independence query is answered by testing
`r_N(X) = |X|`; each rank query is polynomial-time exact elimination.
Cographicness is tested by applying the same procedure to the dual rank
oracle

```text
r_N*(X) = |X| + r_N(E \ X) - r_N(E).
```

Thus the three subclasses above are polynomial in the represented-graph or
exact-rational-matrix model stated here; this does not provide a polynomial
algorithm for the unrestricted internal frame-basis problem.

These algorithms are genuine clean enlargements of the tractable region, but
they do not classify the unrestricted cubic incidence family. The rank-three
dual controls also reveal two tempting shortcuts that fail:

1. **Local triangle coverage is insufficient.** Across the five controls the
   verifier checks 316 loops, parallel pairs, and triangles in the dual. Every
   element lies in some circuit of size at most three, including both matrices
   whose width is three under every basis. The needed property is one common
   basis that simultaneously covers all outside elements.
2. **Strictly improving basis exchange can get stuck.** A connected SAT
   control has 51 bases, eight of optimum width two, and 43 of width three.
   Nineteen width-three bases have no one-column exchange of smaller width,
   although the basis-exchange graph is connected and the optimum is at graph
   distance at most three. Only 32 of the 51 bases can reach an optimum through
   strictly width-decreasing exchanges. Equal-width moves rescue all 51 in
   this example, so this refutes naive strict descent, not every
   plateau-aware or globally guided algorithm.

Across all five controls, the exact exchange census contains 588 basis nodes
and 5,885 exchange edges. The verifier independently rebuilds every edge,
distance, local-minimum count, and SHA-256 graph certificate. This narrows the
unresolved target to **unbounded-nullity, non-graphic and non-cographic
represented matroids with a ground-set frame basis**. No polynomial
recognition algorithm or hardness reduction for that restricted cubic
rational-matrix class is established here.

Result Q fixes the direction of that target: external frame structure is a
necessary condition for `omega(M) <= 2` rather than an equivalent one, so the
recognition question is one-sided and a frame test cannot replace the width
decision.




### Result N—the zero-valid internal-basis problem is exactly cubic exact-one SAT

The semantic basis search has a sharper boundary than the width search. Let
`K = ker(M)` have dimension `k`, let `B` be a column basis of `M`, and let
`F` be its `k`-element complement. In the coordinates ordered as `B,F`, exact
elimination writes each pivot coordinate as

```text
z_b = - sum_{f in F} a[b,f] z_f.
```

Write `z_f = 3 y_f - 1` for Boolean free variables `y_f`. Each pivot equation
induces a Boolean relation: it accepts a free tuple exactly when the resulting
`z_b` is `-1` or `2`. Call `F` **zero-valid** when every induced pivot relation
accepts the all-zero tuple. This property is jointly semantic: it says that
setting every free Boolean coordinate to zero reconstructs a complete
alphabet-valued kernel vector.

**Theorem.** A cubic monotone one-in-three formula is satisfiable if and only
if it has a zero-valid complementary dual ground-set basis.

For the forward direction, let `x` be a satisfying assignment and partition
the variable columns into

```text
O = {i : x_i = 1},       Z = {i : x_i = 0}.
```

Every clause contains exactly one column from `O`. Consequently, the nonzero
row supports of the columns indexed by `O` are pairwise disjoint. Each such
column occurs three times, so none is zero, and the columns in `O` are linearly
independent.

Now restrict kernel vectors to their coordinates in `Z`. If `u in K` vanishes
on `Z`, then `u` is supported on `O`; independence of the `O` columns and
`M u = 0` force `u = 0`. Thus the coordinate projection

```text
K -> Q^Z
```

is injective and has rank `k`. The coordinate functionals indexed by `Z`
therefore contain `k` independent members. Choose their indices as
`F subseteq Z`. Projection `K -> Q^F` is then an isomorphism, equivalently
`B = [n] \ F` is a column basis of `M`.

Set every free Boolean coordinate to zero. Since `F subseteq Z`, this fixes
`z_f = -1 = 3x_f - 1` on all free coordinates. Unique reconstruction through
the basis gives the original vector `z = 3x - 1`, so every pivot coordinate is
also in `{-1,2}`. Hence `F` is zero-valid. A suitable `F` can be selected from
`Z` by rational Gaussian elimination in polynomial time once `x` is known.

For the reverse direction, a zero-valid `F` reconstructs a vector
`z in ker(M) intersect {-1,2}^n` from the all-zero free tuple. Then
`x = (z+1)/3` is Boolean. Because every row of `M` contains three ones,

```text
0 = Mz = 3Mx - M1 = 3Mx - 3 1,
```

so `Mx = 1` and `x` satisfies every exact-one clause. This reconstruction is
also polynomial.

**Corollary.** Deciding whether such a zero-valid basis exists is NP-complete,
even when `M` is a planar square `0/1` incidence matrix with exactly three
ones in every row and column. Membership in NP follows because a proposed
column basis is checked by exact elimination and only the all-zero free tuple
must be evaluated. NP-hardness is the identity reduction from Cubic Planar
Monotone 1-in-3 SAT: the Moore–Robson restriction already has exactly these
matrix properties, and the theorem makes its SAT answer identical to the
zero-valid-basis answer.

This is a certificate-preserving equivalence, not a SAT algorithm. It rules
out the hope that zero-valid basis selection is an easier generic preprocessing
step: a polynomial finder or recognizer would itself prove `P=NP`. It does not
settle the different question of recognizing a width-two frame basis, and it
does not rule out other semantic tractable languages.

The implementation now includes a deterministic witness-to-basis transformer.
For each of the three SAT controls in the basis census, it selects independent
zero-coordinate functionals, checks the complementary column basis, and
reconstructs the original `{-1,2}` kernel vector. The SHA-256-bound receipt
stores all three certificates, and the independent verifier rebuilds each
coordinate representation and basis from scratch. In particular, the
`n=12` SAT control still has width three under all 136 column bases, yet it has
a zero-valid basis. Structural arity three and semantic triviality under a
known tuple can coexist.


### Result O—growing nullity separates width from Schaefer language

For a column basis `B` of a cubic incidence matrix, eliminate the pivot
coordinates against the complementary free set `F`. When every pivot support
has size at most three, each pivot gives an explicit constant-arity Boolean
relation on the free bits. The probe records the Schaefer closure classes
shared by all pivot relations in that coordinate system. This is a supplied
basis property. It is not a claim that the basis, or even a basis with a
desired language, can be found in polynomial time.

The census starts with two controls whose every column basis has exact maximum
support three:

|Control|Status|Variables|Rank|Nullity|Column bases|Common-class histogram|
|---|---:|---:|---:|---:|---:|---|
|all-bases SAT|SAT|12|9|3|136|`84: zero-valid; 6: one-valid; 46: none`|
|all-bases UNSAT|UNSAT|15|12|3|237|`6: bijunctive; 2: dual-Horn+bijunctive; 53: Horn+bijunctive; 6: Horn+dual-Horn+bijunctive; 10: Horn+dual-Horn+bijunctive+affine; 160: none`|

Thus neither control has a width-two basis. Only 90 SAT bases and 77 UNSAT
bases share at least one listed Schaefer class; the remaining 46 and 160 bases
share none. The two properties must not be conflated: width two gives the
direct 2-SAT reduction already proved above, whereas a supplied bounded-arity
zero-valid, one-valid, Horn, dual-Horn, bijunctive, or affine language gives
its own polynomial residual solver. Finding such a basis is still a separate
search problem.

The controls admit an exact disconnected scaling law. For `t` direct-sum
blocks, every column basis is the disjoint union of one basis from each
block. Therefore basis counts multiply, maximum-support widths combine by
maximum, and common Schaefer classes combine by intersection. At `t=16`, the
SAT family has `n=192`, rank `144`, nullity `48`, and
`136^16 = 13,696,907,849,916,094,763,278,545,543,233,536` bases. The UNSAT
family has `n=240`, rank `192`, nullity `48`, and
`237^16 = 99,077,157,015,023,530,086,040,615,318,112,651,841`. In both
families every basis still has width three. This proves a growing-nullity exact
product construction, not an unassisted algorithm: the basis census itself is
exponential.

To test whether connectivity alone changes the result, the probe applies one
degree-preserving incidence 2-switch between two copies of the SAT control.
The resulting connected bridge has 24 variables, rank 19, nullity 5, and 7,344
column bases. Its exact maximum-support histogram is:

```text
width 3: 4,374 bases
width 4: 1,944 bases
width 5: 1,026 bases
```

No bridge basis has width at most two. Its canonical residual has support
histogram `1:7, 2:6, 3:6` and the single common Schaefer class `0-valid`.
The bridge therefore shows that connectivity does not force a width-two frame
or erase a supplied small-arity language profile. It is only one finite
connected construction: it does not establish an unbounded connected family,
a polynomial Schaefer-basis recognizer, or NP-hardness of width-two or
Schaefer-basis recognition.

The independent verifier rebuilds both cubic matrices, all component basis
censuses, all ten direct-sum rows, the bridge switch, its 7,344 basis census,
and the canonical relation truth tables without importing the probe or the
cubic-kernel implementation. It reports `status: verified`, with bridge
minimum width three. The bounded conclusion is:

> Growing nullity can preserve invariant width three while leaving many
> individual coordinate systems Schaefer-tractable. Basis existence,
> basis-language recognition, and basis discovery remain distinct problems.
> Result N closes only the zero-valid semantic shortcut; it does not close
> width-two frame recognition or the broader supplied-Schaefer-basis question.

### Result P—mixed connectivity preserves the width-three frame optimum

Result O measured one connected bridge. Result P replaces that single
construction with a census over the entire cross-component switch family of the
mixed SAT+UNSAT sum, and it decides the width-two question by exhaustive
certificate at the level of free subsets.

Take the all-bases SAT control (`n=12`, rank 9) and the all-bases UNSAT control
(`n=15`, rank 12) and form their disjoint union on 27 variables. Every column
basis is the union of one basis from each component, so the mixed matrix has
`136 * 237 = 32,232` bases, nullity 6, rank 21, and basis-width histogram
`3: 32,232`. Every basis of the sum has width exactly three, so its frame
optimum is `omega = 3` exactly, and it has no width-two frame. The classifier
adds that no basis of the sum shares a listed Schaefer class, because the
component histograms intersect in the empty class.

Now cut two incidences, one from each side, and reattach them across the
components. Each of the 36 left incidence edges can be switched against each of
the 45 right edges, giving 1,620 raw switches that are pairwise distinct
formulas, all connected, all with rank 22, nullity 5, and all UNSAT. None of
the 1,620 admits a width-two dual frame, and every one of them admits a
width-three frame witness, so all 1,620 have `omega = 3` exactly.

The certificate is a free-subset screen, not a basis census. A free set `F`
frames the dual in width `k` exactly when every ground-set element lies in the
span of at most `k` elements of `F`. Collecting, for every element, all element
`k`-subsets whose span contains it, and intersecting the corresponding subset
bitsets, leaves exactly the free subsets whose internal `k`-subsets already
cover the ground set. At `k = 2` that intersection is empty for all 1,620
switches, so no free subset of any kind covers, independent or not, and each
negative is complete over all `C(27,5) = 80,730` five-subsets of that formula
without an independence test. At `k = 3` the intersection is nonempty, and its
first element is independent in every switch, so one exact independence check
per formula yields a width-at-most-three frame. The exact width is then computed
rather than assumed, by Gauss-Jordan elimination on the augmented
kernel-coordinate system: the maximum number of non-zero coordinates of any
element expressed in the free set. Every switch measures exactly three, and the
canonical RREF basis is typically not the witness. The canonical basis attains
width three on 864 of the 1,620 switches and width four or five on the remaining
756, so it is a strict upper bound on the frame optimum for 756 formulas that
still have `omega = 3`.

A bound-`k` screen is a feasibility test rather than an optimiser: it returns
an independent free set of width at most `k`, which can be wider than the
optimum, as the support-three UNSAT control shows when screened at bound three.
Exactness comes from pairing the two bounds, the failed lower bound
`omega >= 3` with the measured upper bound `omega <= 3`.

Two independent agreement checks fix the scale of the screen. The exact width
primitive reproduces the canonical pivot-support width whenever it is applied to
the canonical free set, so the two width conventions coincide. The screens
reproduce the known control invariants: both all-bases controls certify
`omega = 3` exactly at both bounds, in agreement with their complete basis
censuses, and the bound-two screen with the exact width measurement finds
width-two witnesses for both canonical support-three controls, in agreement with
their known minimum.

The same filter independently reproduces the mixed census. On the disconnected
27-variable sum the bound-two intersection is empty and the bound-three
intersection has exactly 32,232 survivors, the same number as the width-three
basis count from the exhaustive enumeration, and the screened optimum equals
the census optimum. Neither number was supplied to the filter.

Independent verification reconstructs every component basis census, all 32,232
direct-sum rows, all 1,620 switches, the canonical widths, both coverage
screens, every width witness through its own exact rational elimination, and
seven full-enumeration brute-force controls over every free subset at both
bounds without the coverage prefilter. It reports `status: verified`. The
bounded conclusion:

> Cutting the mixed sum open with a degree-preserving 2-switch makes the
> formula connected, drops nullity from 6 to 5, and blocks the width-two frame
> on every one of the 1,620 switches, each of which instead has a width-three
> frame and frame optimum exactly three. Connectivity is not what blocks the
> width-two frame, and no switch in this family exposes one. Canonical RREF
> width is not the frame optimum. This remains a finite family measurement; it
> does not decide width-two frame recognition, classify unbounded connected
> cubic families, or bear on `P = NP`.


### Result Q—element triangles decide nullity-three width; frame structure is one-sided

Result M's recognition target needs the direction of its implication pinned
down. Call the dual `D = N*` frame when an ambient basis `T` of kernel
coordinates makes every column of `T*B` have at most two nonzero entries. That
is the frame-matroid condition of the matroid-minors literature in the form
`D = M'\B` for a basis `B` of an extension `M'`. Frame matroids have a
polynomial recognition algorithm for represented matroids, so the test is
available in principle; this result shows it cannot settle the width.

Width two implies frame structure. If `omega(M) <= 2`, some ground-set
complementary basis `F` spans every element of `D` with at most two of its own
elements. That `F` is also a basis of the matroid `D`, so extending `D` by the
`F` columns gives `D = M'\F` and `D` is frame. The converse fails inside this
family. Both all-bases ternary controls have `omega = 3` under every basis, and
each admits an exact integer two-sparse ambient basis `T` of full rank with
every column of `T*B` two-sparse. No ground-set basis of either dual is
two-sparse. A frame test is therefore necessary only: non-frame `D` forces
`omega >= 3`, while frame `D` leaves the width undecided.

At nullity three the internal criterion is exact and finite. A triple of
classes `p1, p2, p3` spans the kernel-coordinate space, its three pairwise
joins are the orthogonal spaces of three independent normals, and such a triple
exists exactly when a ground-set basis of `D` spans every element with at most
two of its elements. So `omega(M) <= 2` exactly when some element triple has
its three joins covering every class. The three width-two controls all carry
such an element triangle and the two width-three controls carry none, matching
the basis census on all five. The external decision is equally finite:
partition the classes into three groups of projective span at most a line and
test the eight exact Hall conditions on the orthogonal spaces. The independent
verifier enumerates every partition rather than searching, and cross-checks the
runner's cover search on all five controls, a graphic anchor, and seven
general-position points.

Frame structure is closed under direct sums, and widths combine by maximum:

```text
omega(M1 + M2) = max(omega(M1), omega(M2))
```

The block diagonal of two-sparse witnesses is a two-sparse witness, and the
bases of a sum are exactly the unions of component bases. All five control sums
confirm the law, the block structure is detected from the kernel-coordinate
support graph, and the 18-variable sum is additionally censused by brute force
as an anchor. Repeating the 12-variable width-three control `t` times gives an
unbounded family `M_t` with `n = 12t`, nullity `3t`, a two-sparse frame witness
of rank `3t`, and `omega(M_t) = 3` for every measured `t`, through size 48 and
nullity 12.

> External frame-matroid structure cannot decide internal width. The width-two
> criterion is internal to the ground set, an element triangle covering every
> class, while frame structure is satisfied by width-three matrices and by a
> family that stays at width three at every measured size. Fixed-nullity
> enumeration, tree-2-spanner recognition, and spanning-tree congestion remain
> the polynomial islands of Result M. This is a finite measurement plus the
> proof of the one-sided implication; it does not decide width-two frame
> recognition or bear on `P = NP`.

### Result R—a complete class search decides the ground-set frame question beyond census reach

Result Q's remaining target is the ground-set frame basis: a basis of the dual
that spans every element with at most two of its own elements, equivalently a
complementary free set of width at most two. Enumerating `C(n, k)` free subsets
decides it and stops being feasible once nullity reaches the high single digits.
The search works instead on the classes of the kernel-coordinate representation.
Pick the first class not yet covered by pairwise joins of the chosen classes,
branch over every class pair whose join covers it, and accept when the chosen
classes are independent and cover every class; independent classes are then
added to reach a full ground basis, which cannot lose coverage. Any ground-set
two-sparse basis must cover the branching target with two of its own classes, so
a search that exhausts its subtree without a success proves that no ground-set
basis is two-sparse, and a success is re-verified by exact coordinates in the
free basis. The procedure is complete; its worst case remains exponential.

The chains use the degree-preserving incidence two-switch of Result P, applied
once per consecutive pair of copies. Chaining `t` copies of the 12-variable
all-bases control gives `n = 12t` and nullity `2t + 1`; chaining the 15-variable
control gives `n = 15t` with the same nullity. Every link keeps the clause
variable incidence graph connected, so unlike the direct-sum family the
components interact at growing size and nullity.

```text
t   SAT chain      UNSAT chain      nullity   search nodes   verdict
2   24 elements    30 elements      5         608    1167    no ground-set basis
3   36 elements    45 elements      7         3611   7091    no ground-set basis
4   48 elements    60 elements      9         10850  21671   no ground-set basis
```

At `n = 60` and nullity nine the census would need `C(60, 9) = 14,783,142,660`
free subsets; the search exhausts its subtree at 21,671 nodes and reports no
ground-set two-sparse basis, so every measured chain has `omega = 3`. The same
verdict holds for the star composition, which joins every later copy to the
first, and for alternating SAT and UNSAT blocks. The five controls and five
direct sums reproduce their recorded widths, and 24 sampled members of the
1,620-switch family all report no ground-set basis, with the sampled population
tied to that earlier enumeration by the sorted-digest hash of all 1,620
canonical formulas.

The independent verifier imports neither the runner nor any cubic-kernel
implementation. It rebuilds every formula, canonical order, rational
elimination, kernel-coordinate column, and class partition; re-decides all 43
cases with its own complete search under a different branching order; rechecks
all five width-two certificates; decides the 37 cases of nullity at most six
again by exact ground-element sieve over every `C(n, nullity)` free subset;
enumerates every class subset of the 40 cases whose class universe is at most
350,000, which is 312,859 subsets and includes both nullity-nine chains; and
tests the covering identity on sampled bases, where "spans every element with at
most two free elements" agreed with the exact coordinate width on all 787
independent draws. The 36 width-two draws all lie inside the known width-two
cases, and none of the 7,200 draws on the nullity-seven and nullity-nine chains
reaches width two.


### Result S—within-control switches expose a nullity-conditioned local boundary

Result R's two width-three controls are not locally stable under arbitrary
degree-preserving switches inside a block. The complete legal one-switch
neighborhood of the 12-variable all-bases SAT control has 424 switch
descriptions and 368 distinct canonical formulas. Its joint `(nullity, omega)`
counts are

| control | `k = 2` | `k = 3` | `k = 4` |
|---|---:|---:|---:|
| all-bases SAT | `261: omega=2` | `40: omega=2`, `60: omega=3` | `3: omega=2`, `4: omega=3` |
| all-bases UNSAT | `519: omega=2` | `29: omega=2`, `94: omega=3` | `4: omega=3` |

The UNSAT control has 726 legal descriptions and 646 distinct formulas. The
class search and exact `C(n, nullity)` free-basis census agree on all 1,014
neighbors. The nullity-three element-triangle criterion is available on 100
SAT and 123 UNSAT neighbors and agrees in every case. The `k = 2` rows are
automatically width at most two; the genuine nullity-three neighborhoods
contain 40 of 100 SAT formulas and 29 of 123 UNSAT formulas at width two, with
the remaining rows at width three. The seven nullity-four rows are nontrivial:
three SAT rows have width two and all four UNSAT rows have width three.

A seeded sample of 400 two-switch walks per control has 397 and 399 unique
final formulas. Their joint outcomes are `k = 1: omega=1 (145)`, `k = 2:
omega=2 (195)`, `k = 3: omega=2 (38), omega=3 (15)`, and `k = 4: omega=2
(4)` for the SAT control; and `k = 1: omega=1 (221)`, `k = 2: omega=1 (7),
omega=2 (151)`, and `k = 3: omega=2 (5), omega=3 (15)` for the UNSAT control.
The independent search agrees with the census on all 397 and 399 decisions.
The first-step one-switch formulas have `omega = 2` on 341 of 400 SAT walks
and 355 of 400 UNSAT walks.

This maps a finite local neighborhood and a seeded distance-two sample. It does
not estimate a distribution for arbitrary cubic incidence formulas, establish a
generic perturbation law, or provide a polynomial recognition algorithm.


> The ground-set frame question for cubic incidence duals is decidable without
> free-subset enumeration, and connected chains of the two width-three controls
> stay width three through nullity nine, where enumeration is infeasible. This is
> a complete decision procedure with an exponential worst case plus measured
> connected witnesses; it does not give a polynomial recognition algorithm and
> does not bear on `P = NP`.

## 9. Remaining credible research directions

The alias theorem reaches an NP-complete occurrence boundary, and three
compression attempts now have precise outcomes. The next work is:

1. **Classify the unbounded-nullity internal-frame problem.** Fixed nullity is
   polynomial by `O(n^k)` dual-basis enumeration, and graphic or cographic
   column matroids reduce to tree 2-spanners or threshold-three spanning-tree
   congestion. The remaining target is the non-graphic, non-cographic cubic
   incidence family with nullity growing in `n`. Determine whether its
   ground-set frame basis can be found in polynomial time or is NP-hard.
   Strictly improving one-column exchange is not sufficient; any proposed
   local algorithm must handle certified width-three plateaus. Result R reaches
   nullity nine with a complete search at tens of thousands of nodes and
   certifies connected width-three chains there, so the open question is
   polynomial recognition or hardness rather than decidability. Frame structure
   is one-sided here, by Result Q: the repeated all-bases family is frame at
   every measured size while its width stays three, so a frame test cannot
   substitute for the width decision. For matrices
   with `omega(M) >= 3`, seek a shared invariant, decomposition,
   determinant/Pfaffian identity, or bounded dynamic program. Enumerating
   `2^nullity` assignments or `binomial(n,rank)` bases only restates the
   obstruction.
   Zero-valid basis search is not a shortcut: Result N proves it NP-complete
   by a certificate-preserving equivalence with the original cubic formula.
   Keep that semantic problem separate from width-two frame recognition, and
   test whether any broader union of Schaefer-tractable basis languages has a
   recognizable structural characterization rather than merely encoding a
   satisfying assignment. Result P's coverage filters are exact and much
   faster than a basis census per formula: bound two decides the width-two
   question and bound three adds a measured width-three witness, but the
   `C(n,k)` free-subset intersection at each bound is still `O(n^k)` for fixed
   nullity `k`, so the pair certifies finite families rather than changing the
   asymptotics.
2. **Move beyond one uniform matchgate basis.** Test whether locally varying
   edge gauges, bounded-size equality gadgets, higher-dimensional signatures,
   or non-matchgate determinant identities can aggregate the correlated
   residual matchings. The uniform `2x2` holographic route is closed by the
   parity ideal; broader routes require their own explicit transformation and
   polynomial resource proof.
3. **Exploit the parameterized crossover.** The matching-branch algorithm has
   the better exponential term below `k/c = 0.1902266`; the published
   monotone one-in-three algorithm wins above it. Seek reductions or kernels
   that lower `k` without increasing `c`, and compare against the published
   `1.0984^n` baseline rather than raw assignment enumeration.
4. **Proof search versus proof existence.** Characterize the strength of the
   combined proof system and separate short-proof existence from efficient
   automatizability. A polynomially bounded refutation system would imply
   `NP = coNP`; a polynomial-time SAT procedure needs an additional total
   decision and search argument.
5. **Restricted-circuit algorithms.** Characterize circuits representable by
   gapless transport, a gapped error channel, and sparse bounded nonlinear
   gates. Seek a genuinely faster SAT algorithm for that restricted class,
   then use the algorithms-to-lower-bounds connection. This can produce real
   complexity results without claiming unrestricted `P` versus `NP`.
6. **Proof-complexity and locality.** Use finite propagation and the exact
   invariant to study routing or communication lower bounds for local proof
   and constraint-propagation systems. The hybrid checker and its explicit
   cross-system steps provide a concrete boundary object. Such bounds apply
   to the architecture, not to all Turing machines.

Cassi can also remain a useful heuristic SAT substrate, but empirical solution
rate—even excellent rate—is not evidence for a Millennium Prize resolution.
The baseline clause-field family's published resolution lower bound settles
its worst-case status. The hybrid successor has exact and conservative
infinite-subfamily proof bounds. The matching field is total on every
connected topology in its syntax-recognized class. The alias field is total
with explicit `O(2^k c^3)` search and `O(2^k c^4)` proof-construction bounds,
and the NP-complete cubic subfamily explains why this is not yet polynomial.
The direct cover recurrence reduces measured states but has no competitive
global theorem, and the uniform matchgate parity route is algebraically unavailable.
The cubic kernel equivalence removes rational linear consistency as the
mystery and proves a supplied-width-two polynomial theorem. Exact basis
optimization shows that the original canonical support-three controls also
belong to that class, but only after a basis is found. Fixed nullity and
graphic or cographic column structure now give three unassisted polynomial
subclasses. They do not cover the unbounded-nullity general case. Separate SAT
and UNSAT controls have invariant width three; every tested dual element still
lies in a small circuit, so local triangle coverage does not construct a
global frame. A fifth SAT control has a width-two basis but 19 nonglobal
width-three local minima under one-column exchange, ruling out naive strict
descent. The sharp open question is recognition or hardness of internal
dual-frame bases for unbounded-nullity, non-graphic and non-cographic cubic
incidence matroids, or an algorithm that shares work across the remaining
ternary alphabet intersection without recreating exponential exact-cover,
basis, or free-coordinate search.
The growing-nullity census sharpens that boundary: exact direct sums preserve
width three through nullity 48, while a connected 24-variable bridge has no
width-two basis but retains a jointly 0-valid canonical residual. Some
individual bases share zero-valid, one-valid, Horn, dual-Horn, bijunctive, or
affine closures, while many share none. The product law and finite bridge do
not provide a connected-family recognizer, a basis finder, or a hardness result.

## 10. Reproduction

From the `CassiCosmos` root:

```text
python research/p_vs_np/p_vs_np_probe.py
python research/p_vs_np/p_vs_np_verify.py
```

From the `CassiFI` root:

```text
python run_p_vs_np_field_probe.py
python run_p_vs_np_clause_field_probe.py
python verify_p_vs_np_clause_field_probe.py
python -m pytest test_clause_field.py -q
python run_p_vs_np_hybrid_inference.py
python verify_hybrid_inference.py
python -m pytest test_hybrid_inference.py -q
python run_mixed_exact_one_decision.py
python verify_mixed_exact_one_decision.py
python -m pytest test_mixed_exact_one_decision.py -q
python run_general_matched_decision.py
python verify_general_matched_decision.py
python -m pytest test_general_matched_field.py -q
python run_alias_exact_one_decision.py
python verify_alias_exact_one_decision.py
python -m pytest test_alias_exact_one_field.py -q
python run_alias_compression_analysis.py
python verify_alias_compression_analysis.py
python run_cubic_kernel_analysis.py
python verify_cubic_kernel_analysis.py
python growing_nullity_schaefer_probe.py
python verify_growing_nullity_schaefer_probe.py
python run_mixed_schaefer_frame_obstruction.py
python verify_mixed_schaefer_frame_obstruction.py
python run_frame_separation_probe.py
python verify_frame_separation_probe.py
python run_frame_search_probe.py
python verify_frame_search_probe.py
python run_switch_neighborhood_probe.py
python verify_switch_neighborhood_probe.py
python -m pytest test_switch_neighborhood_probe.py -q
python -m pytest test_cubic_kernel_decision.py -q
python -m pytest test_frame_separation_probe.py -q
python -m pytest test_frame_search_probe.py -q
```

The raw receipt is `_diag/p_vs_np_probe.json`. The verifier checks the frozen
preregistration hash, exhaustively recomputes all SAT labels, certifies every
stored final assignment, rebuilds aggregates, enforces resource caps, and
recomputes all verdicts.

The CassiFI raw receipt is `CassiFI/_diag/p_vs_np_cassifi_probe.json` relative
to the unified workspace. It stores every CNF, attempted assignment index,
certificate, field-state digest, byte count, causality control, and branch
budget result. An independent pass re-enumerated all assignments and confirmed
all 22 labels, first-solution indices, and certificates.

The uniform clause-field receipt is
`CassiFI/_diag/p_vs_np_clause_field_probe.json`. The independent verifier does
not import either the field implementation or the runner. It re-evaluates all
SAT certificates, truth-tables 281 cases, reconstructs the 20-variable
standard pigeonhole control, checks every enumerated learned clause against
every original model, verifies every resolution and weakening inference and
the empty-clause root of all seven UNSAT proofs, rebuilds the proof, resource,
and scaling aggregates, and confirms the polynomial storage formula.

The hybrid receipt is `CassiFI/_diag/p_vs_np_hybrid_inference.json`. It stores
31 formulas, 10,521 checked proof lines, all state and proof digests, exact
resource ledgers, deterministic replay and checkpoint results, representation
controls, four scaling tables, and the restricted-class theorem receipt. Its
independent standard-library verifier imports neither the field implementation
nor the runner. It reconstructs every clause, pseudo-Boolean, GF(2), bridge,
extension, and resolution line from serialized premises. It also recognizes
the mixed class from raw CNF syntax, re-derives all exact and conservative
`b`-dependent proof and storage bounds, and truth-tables the consistent
control. Twenty-five cases end in a verified contradiction; six satisfiable,
incomplete-premise, or resource-bound controls end `exhausted`.

The total-decision receipt is
`CassiFI/_diag/mixed_exact_one_decision.json`. It stores 600 canonical CNFs,
complete dynamic-program certificates, immutable-field descriptors, state and
certificate digests, exact work counts, and persistence and replay results.
The independent standard-library verifier imports neither implementation nor
runner. It reconstructs all formulas, reachability layers, predecessors,
outcomes, assignments, serialized tensor coordinates, and aggregates. The
receipt contains 274 SAT and 326 UNSAT cases, including 22 parity-consistent
UNSAT labelings; every check passes.

The general-matching receipt is
`CassiFI/_diag/general_matched_decision.json`. It stores 672 recognized CNFs,
perfect matchings or Tutte barriers, complete assignments for SAT cases,
immutable-field descriptors, exact work counters, and replay results. The
independent verifier reconstructs every source occurrence model and auxiliary
graph, checks all SAT and UNSAT certificates without rerunning proof search,
decodes every tensor coordinate, verifies all digests, and rebuilds the
aggregates. It accepts 324 SAT and 348 UNSAT cases; all 672 certificates and
all four fail-closed controls pass.

The alias-boundary receipt is
`CassiFI/_diag/alias_exact_one_decision.json`. It stores 65 recognized
degree-two/degree-three monotone exact-one CNFs, every required branch
certificate, immutable-field descriptors, exact work counters, truth-table
labels, checkpoint results, and public-step replays. The independent verifier
reconstructs every branch residual and checks all conflicts, perfect matchings,
Tutte barriers, SAT assignments, tensor coordinates, digests, controls, and
aggregates. It accepts 43 SAT and 22 UNSAT decisions; all 65 certificates and
all four fail-closed controls pass.

The alias-compression receipt is
`CassiFI/_diag/alias_compression_analysis.json`. It is SHA-256-bound to the
65-case alias receipt and stores every deterministic exact-cover comparison,
the recurrence and crossover constants, and all eight uniform-basis matchgate
parity ideals. The independent verifier reconstructs all 65 searches,
truth-tables 127 additional small formulas, recomputes the recurrence
constants, and independently reduces every Gröbner basis to `[1]`.

The cubic-kernel receipt is
`CassiFI/_diag/cubic_kernel_analysis.json`. It is SHA-256-bound to the
65-case alias receipt and stores all 34 canonical cubic formulas, exact rational
kernel profiles, total decisions, 2-SAT or enumeration certificates,
connected-family rank bounds, arity-at-most-three Schaefer closure profiles,
five exact basis-width controls, and three zero-valid basis certificates. The
basis supplement checks 1,298 column subsets, 588 actual bases, and 5,885
one-column exchange edges; three canonical-width-three cases have width-two
bases, two controls remain width three under every basis, and one width-two
case contains 19 nonglobal width-three local minima. The independent verifier
imports neither implementation nor runner, recomputes every matrix, basis
optimum, dual small-circuit profile, exchange graph, zero-valid basis, and
certificate, and truth-tables 574 fixed-gauge formulas through six variables.
All 34 receipt decisions and all 574 exhaustive labels agree.

The growing-nullity receipt is
`CassiFI/_diag/growing_nullity_schaefer_probe.json`. It stores the two
all-bases controls, exact rank/nullity profiles, every component basis and
Schaefer-class histogram, five direct-sum sizes for each status, the connected
degree-preserving bridge, its 7,344-basis width census, and its canonical
relation truth tables. The independent verifier imports neither the probe nor
the cubic-kernel implementation. It reconstructs both matrices, all ten
product/intersection rows, the bridge connectivity and exact basis census, and
the canonical 0-valid language profile. The current run reports two component
statuses, ten scaling rows, 7,344 bridge bases, and minimum bridge width three.

The mixed-frame receipt is
`CassiFI/_diag/mixed_schaefer_frame_obstruction.json`. It stores both component
censuses, the 27-variable mixed direct sum with all 32,232 bases, the 1,620
cross-component switches with rank 22 and nullity 5, the free-subset
pair-coverage and triple-coverage screens with an exact width witness for every
formula, and the scope record. The independent verifier imports neither the
runner, the growing-nullity probe, nor the cubic-kernel implementation. It
rebuilds both matrices and every basis row, re-runs both coverage screens on all
1,620 switches and on the mixed sum, remeasures every witness with its own
rational elimination, and full-enumerates every free subset of seven sampled
switches at both bounds with no coverage prefilter. The current run reports
32,232 verified mixed bases, 1,620 verified switches, no width-two frame and an
exact width-three witness in each, and seven-of-seven brute-force agreement at
bound two and at bound three.

The frame-separation receipt is
`CassiFI/_diag/frame_separation_probe.json`. It stores the five basis-width
controls with their exact element-triangle and frame verdicts, the five
component direct sums with block structure and witnesses, and the repeated
all-bases family through size 48. The independent verifier imports neither the
runner nor the cubic-kernel implementation. It rebuilds every formula,
canonical order, rational elimination, kernel-coordinate column, class
configuration, and basis census; decides nullity-three frame structure by
enumerating every class partition under exact Hall conditions instead of
searching; and rechecks every witness matrix by direct support evaluation. It
also validates its decision procedure on a graphic anchor that is frame and on
seven general-position points that are not. The current run reports five
verified controls, nine verified sum and family witnesses, census and criterion
agreement on all five controls, the width law on every sum, and a family that
is frame with width three at sizes 12, 24, 36, and 48.

The frame-search receipt is `CassiFI/_diag/frame_search_probe.json`. It stores
the five controls, five direct sums, 24 sampled switches, and nine chains with
size, rank, nullity, class count, connectivity, search nodes, verdicts, the
certificate of every width-two frame, and the scope record. The independent
verifier imports neither the runner nor any cubic-kernel implementation. It
rebuilds every formula, canonical order, rational elimination,
kernel-coordinate column, and class partition; re-decides all 43 cases with its
own complete search under a different branching order; rechecks all five
certificates against exact coordinates in the claimed free basis; ties the
1,620-switch population to the mixed-frame receipt by recomputing its
sorted-digest hash; enumerates the complete class-subset universe of the 40
tractable cases; decides the 37 cases of nullity at most six again by exact
ground-element sieve over every `C(n, nullity)` free subset; and verifies the
covering identity on 787 sampled independent bases. The current run reports 43
verified verdicts, ten verified certificates, 312,859 enumerated class subsets
across 40 cases with three skipped as too large, 2,694,750 sieved free subsets,
1,282,415 dependent coverings rejected by the independence filter, and no
width-two draw outside the known width-two cases.

The switch-neighborhood receipt is `CassiFI/_diag/switch_neighborhood_probe.json`.
It stores every distinct one-switch neighbor with its canonical digest, switch,
nullity, exact census width, class-search verdict, and witness metadata, plus
every unique final formula in the seeded distance-two samples. The independent
verifier imports neither the runner nor a cubic-kernel implementation. It
rebuilds both controls, every legal switch and canonical deduplication, fresh
rational kernel coordinates, every free-basis census, the class-search
decisions, both seeded walk sequences, and every stored frame witness. The run
reports 1,014 complete neighbors, 796 unique sampled finals, census/search
agreement on every decision, and two synthetic search anchors; the distance-two
walks are samples rather than an exhaustive radius-two neighborhood.

## Primary references

- [Clay Mathematics Institute: P versus NP](https://www.claymath.org/millennium/p-vs-np/)
- [Stephen Cook: official problem description](https://www.claymath.org/wp-content/uploads/2022/06/pvsnp.pdf)
- [Ercsey-Ravasz and Toroczkai: analog SAT and transient chaos](https://arxiv.org/abs/1208.0526)
- [Aaronson: NP-complete problems and physical reality](https://arxiv.org/abs/quant-ph/0502072)
- [Hamerly et al.: experimental Ising-machine comparison](https://arxiv.org/abs/1805.05217)
- [Markov: review of polynomial-resource memcomputing claims](https://arxiv.org/abs/1412.0650)
- [Sheldon et al.: stress-testing digital memcomputing](https://arxiv.org/abs/1807.00107)
- [Razborov and Rudich: Natural Proofs](https://eccc.weizmann.ac.il/report/1994/010/)
- [Aaronson and Wigderson: Algebrization](https://arxiv.org/abs/0805.1385)
- [Williams: Improving Exhaustive Search Implies Superpolynomial Lower Bounds](https://people.csail.mit.edu/rrw/improved-algs-lbs2.pdf)
- [Haken: The Intractability of Resolution](https://doi.org/10.1016/0304-3975(85)90144-6)
- [Buss, Hoffmann, and Johannsen: Resolution Trees with Lemmas](https://arxiv.org/abs/0811.1075)
- [Cook and Reckhow: The Relative Efficiency of Propositional Proof Systems](https://www.cs.toronto.edu/~sacook/homepage/cook_reckhow.pdf)
- [Beame and Pitassi: Propositional Proof Complexity—Past, Present, and Future](https://homes.cs.washington.edu/~beame/papers/proofsurvey.pdf)
- [Schaefer: The Complexity of Satisfiability Problems](https://doi.org/10.1145/800133.804350)
- [Moore and Robson: Hard Tiling Problems with Simple Tiles](https://arxiv.org/abs/math/0003039)
- [Wahlström: Algorithms, Measures and Upper Bounds for Satisfiability and Related Problems](https://liu.diva-portal.org/smash/get/diva2%3A23420/FULLTEXT01.pdf)
- [Jonsson et al.: Strong Partial Clones and the Time Complexity of SAT Problems](https://victorlagerkvist.github.io/assets/pdf/jcss2017.pdf)
- [Cai and Gorenstein: Matchgates Revisited](https://arxiv.org/abs/1303.6729)
- [Chen and Whittle: On Recognising Frame and Lifted-Graphic Matroids](https://arxiv.org/abs/1601.01791)
- [Geelen: Recognizing Frame Matroids—matrix-algorithm abstract](https://uwaterloo.ca/combinatorics-and-optimization/events/tutte-colloquium-jim-geelen)
- [Seymour: Recognizing Graphic Matroids](https://doi.org/10.1007/BF02579179)
- [Cai and Corneil: Tree Spanners](https://doi.org/10.1137/S0895480192237403)
- [Otachi, Bodlaender, and van Leeuwen: Complexity Results for the Spanning Tree Congestion Problem](https://ics-archive.science.uu.nl/research/techreps/repo/CS-2010/2010-007.pdf)
