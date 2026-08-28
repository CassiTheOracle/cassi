# Trajectory-owned language and serving

> CassiFI implementation plan, Part 8. [Previous](./07-world-loop-and-transactions.md) · [Index](README.md) · [Next](./09-backends-receipts-and-verification.md)

## Trajectory-owned text and serving cutover

### Current text/runtime gap

The current `CassiQiTextEngine` remains a snapshot reader:

1. `_advance_symbol()` performs `sense_symbols -> evolve -> consolidate`;
2. output calls `controller.emit()` once;
3. the instantaneous argmax symbol is fed back through the inbound path;
4. receipts identify snapshot scores/wave/RMS and state hashes;
5. provider streaming emits the complete final content in one chunk rather than
   streaming field events.

This is field-only, but it is not yet flow-owned emission. The existing
`all_outputs_field_owned` count equality is also insufficient: it can be true
without a directional counterfactual and is vacuously true for no output.

### Timed text ingress

`CassiFieldTextCodec` retains its v1 byte/control contract exactly. For each
encoded source symbol, `CassiQiTextEngine` constructs a transient inbound
`QiBoundaryPacket` with:

- exact symbol and source role;
- request ID, event position, and logical start/end tick;
- text descriptor/profile identity;
- fixed source-wave hash and work budget;
- predecessor state/step identity.

The flow engine advances for the descriptor's fixed dwell interval. Prompt
packets are consumed in codec order, and all packet bodies are discarded after
their steps. A loaded session senses only events supplied by the new request;
it never replays persisted transcript metadata through the boundary.

The provider contract is explicit: the `messages` array in a request is sensed
exactly once as that request's new boundary sequence. Re-sending earlier
messages intentionally senses them again. There is no transcript-driven suffix
deduplication or hidden replay cursor. Exactly-once network retry is instead
provided by a request idempotency key whose already committed response hash can
be returned without evolving the field again.

### Integrated outbound text event

`QiTextBoundaryDescriptor` contains 260 fixed analysis probes
`p_a in C^{N_0}` normalized by
`\langle p_a,p_a\rangle_{W_0}=1`, fixed reaction-synthesis vectors `q_a`
satisfying `\langle p_a,q_a\rangle_{W_0}=1`, an orientation
`o_a in {-1,+1}`, and a positive port frequency `omega_{p,a}`. The descriptor
hashes the probe Gram matrix `G_ab=\langle p_a,p_b\rangle`, the reaction
cross-talk matrix `M_ba=\langle p_b,q_a\rangle`, rank, frame bounds, mutual
coherence, conditioning limits, and the exact active fastest-sheet size `N_0`.
The 260 probes may form an explicitly overcomplete frame, but they cannot claim
independent or orthogonal symbol coordinates. Frame bounds, rank, collision
rates, and null envelopes are calibrated on the actual selected `N_0`;
results from the 16-by-16 analytic profile never transfer to a larger release
geometry without a new fixture and descriptor hash. At each accepted sample
boundary,

\[
z_a=\langle p_a,D_0\rangle_{W_0},
\qquad
u_a=\langle p_a,V_{D,0}\rangle_{W_0},
\]

\[
a_a^{\mathrm{out}}
=\frac{u_a-i\,o_a\omega_{p,a}z_a}{\sqrt2},
\qquad
a_a^{\mathrm{in}}
=\frac{u_a+i\,o_a\omega_{p,a}z_a}{\sqrt2},
\]

\[
w_a^{\mathrm{out}}
=
\frac{w_D\omega_{p,a}}{2}
\left(
|a_a^{\mathrm{out}}|^2-|a_a^{\mathrm{in}}|^2
\right).
\]

\[
E_{\mathrm{port},a}
=\frac{w_D}{2}
\left(|a_a^{\mathrm{out}}|^2+|a_a^{\mathrm{in}}|^2\right).
\]

The descriptor partitions each candidate's output window at every zero-clock
finite map and every other point where output power or its derivative can be
discontinuous. Continuous segment \(g\) has even
`N_emit,a,g>=2`, uniform rational step \(h_g\), \(N_{\mathrm{emit},a,g}+1\)
accepted substage samples, and duration
\(T_g=N_{\mathrm{emit},a,g}h_g\). Both left and right limits of a zero-clock
boundary are retained at the same rational time; that boundary contributes
zero area and no trapezoid spans it. The temporal-resolution condition is

\[
\max_{a,g}h_g\omega_{\mathrm{out},a,g}
\leq\theta_{\max},
\]

and a profile-frozen refinement sweep must bound score, ordering, reaction, and
work changes at \(h_g/2\). No coarse-window result is inherited by a release
descriptor.

On each continuous segment, interval propagation through the admitted rollout
and backend arithmetic must prove \(w_a^{\mathrm{out}}\in C^2\) and reproduce
finite profile-frozen bounds

\[
M^{\mathrm{out}}_{1,a,g}
\geq
\sup_{t\in g}\left|\frac{dw_a^{\mathrm{out}}}{dt}\right|,
\qquad
M^{\mathrm{out}}_{2,a,g}
\geq
\sup_{t\in g}\left|\frac{d^2w_a^{\mathrm{out}}}{dt^2}\right|.
\]

Fine/coarse roundoff bounds are also retained. A segment whose regularity,
curvature, slope, or roundoff bound cannot be independently reproduced is
invalid.

The signed work-like trajectory functional and its positive/negative
partitions are sums of segment-local composite trapezoids:

\[
\begin{aligned}
A_a
&=\sum_g T_{h_g}[w_a^{\mathrm{out}}],\\
P_a
&=\sum_g T_{h_g}[\max(w_a^{\mathrm{out}},0)],\\
N_a
&=\sum_g T_{h_g}[\max(-w_a^{\mathrm{out}},0)].
\end{aligned}
\]

The even-sample coarse signed trapezoid is a consistency check:

\[
\begin{aligned}
D_a
&=\left|
A_a-\sum_g T_{2h_g}
\left[w_a^{\mathrm{out}}\text{ on even segment samples}\right]
\right|,\\
U_{A,a}^{(h)}
&=\sum_g\frac{T_gh_g^2}{12}M^{\mathrm{out}}_{2,a,g}
+U_{\mathrm{round},A,a}^{(h)},\\
U_{A,a}^{(2h)}
&=\sum_g\frac{T_g(2h_g)^2}{12}M^{\mathrm{out}}_{2,a,g}
+U_{\mathrm{round},A,a}^{(2h)}.
\end{aligned}
\]

Because \(\max(\pm w,0)\) is Lipschitz even at a zero crossing, the verified
slope bound gives the conservative trapezoid bounds

\[
\begin{aligned}
U_{P,a}
&=\sum_g\frac{T_gh_g}{3}M^{\mathrm{out}}_{1,a,g}
+U_{\mathrm{round},P,a},\\
U_{N,a}
&=\sum_g\frac{T_gh_g}{3}M^{\mathrm{out}}_{1,a,g}
+U_{\mathrm{round},N,a}.
\end{aligned}
\]

The factor \(1/3\) follows by integrating the maximum deviation between a
Lipschitz function and its endpoint linear interpolant on each subinterval.
Define

\[
A_a^-=A_a-U_{A,a}^{(h)},\qquad
B_a^+=P_a+N_a+U_{P,a}+U_{N,a},\qquad
R_a^-=\frac{A_a^-}{B_a^+}.
\]

`R_a^-` is undefined when `B_a^+<=0`. Raw trajectory eligibility requires
`D_a<=U_{A,a}^{(h)}+U_{A,a}^{(2h)}`, the declared port-energy interval,
`A_a^->=A_min>0`, defined `R_a^->=R_min>0`, and
`U_{A,a}^{(h)}<=U_abs+U_rel|A_a|`. Thus neither a refinement difference nor a
nonsmooth directional integral is relabeled as a certified error bound.

Historical positive integral cannot rescue a terminal-dark trajectory. At the
final pre-reaction sample, the same candidate must have finite
`a_a^{out},a_a^{in},w_a^{out}` and satisfy

\[
|a_{a,N}^{\mathrm{out}}|^2\geq E_{\mathrm{term,min}}>0,
\qquad
w_{a,N}^{\mathrm{out}}\geq w_{\mathrm{term,min}}>0.
\]

For every raw-eligible candidate, the controller constructs its exact
characteristic reaction on an isolated clone and performs the common
full-Hamiltonian/topology/stability preflight. Only candidates whose reaction
would commit are **reaction-feasible**. Sort that set by descending canonical
`A_a` and ascending symbol ID.

The null is not an arbitrary zero state or a profile constant. Its registered
counterfactual starts from the identical predecessor before the source range
The deterministic null source is replayed through the same isolated rollout,
segmentation, reaction preflight, and certified quadrature, producing
`A_null` and the alias `U_null:=U_{A,null}^{(h)}`; if that arm is invalid, the
field abstains. Let `a*` be the
highest-central-score reaction-feasible candidate. Every raw-eligible
different-symbol candidate remains a robustness competitor even when its
reaction preflight failed:

\[
A_{\mathrm{ref}}^+
=\max\!\left(
A_{\mathrm{null}}+U_{\mathrm{null}},
\max_{\substack{a\neq a^\star\\a\ \mathrm{raw\ eligible}}}
(A_a+U_{A,a}^{(h)})
\right),
\]

\[
S_{\mathrm{text}}
=\max\!\left(
|A_{a^\star}|+U_{A,a^\star}^{(h)},
|A_{\mathrm{null}}|+U_{\mathrm{null}},
\max_{\substack{a\neq a^\star\\a\ \mathrm{raw\ eligible}}}
(|A_a|+U_{A,a}^{(h)})
\right).
\]

The empty candidate maximum in `A_ref^+` is \(-\infty\), while the empty
candidate maximum in `S_text` is zero. For the receipt, the raw runner is the
different-symbol raw-eligible candidate with largest
`(A_a+U_{A,a}^{(h)}, A_a)`; the fixed lowest symbol ID resolves an exact tuple tie.
This runner definition cannot omit a wider upper interval merely because its
central score is lower.

The field commits only if

\[
A_{a^\star}-U_{A,a^\star}^{(h)}-A_{\mathrm{ref}}^+
\geq
\max(\Delta_{\mathrm{abs}},
\Delta_{\mathrm{rel}}S_{\mathrm{text}}).
\]

No feasible candidate, interval overlap, reaction failure, or failed
quadrature/topology guard yields `abstain` and emits nothing. Otherwise the
selected isolated post-reaction state is atomically committed, the source
event and emitted symbol are appended to the canonical event/result chain, and
the full winner/raw-runner/null/reaction/interval receipt is retained. The
selected symbol is never reconstructed from a later state.

Thus one reaction-feasible candidate may pass, but only by clearing the
same-predecessor source-suppressed null and every raw runner-up after propagated
uncertainty. Exact equal scores remain diagnostic-ID ordered but fail the
strict positive margin. All read bounds, terminal thresholds, null-arm
construction, reaction bounds, sampling bound, and floating comparison
encoding are versioned profile data with declared domains.
Standing, frozen, reversed-orientation, phase-only, and under-resolved
trajectories cannot pass through a static final resonance.

If no candidate is eligible, commit the window successor and a
`field_abstained` decision without manufacturing a byte. If candidate `a`
wins, its already preflighted fixed characteristic-port reaction evaluates

\[
\eta_{\mathrm{emit},a}
:=\frac{2A_a}
{w_D|a_a^{\mathrm{out}}(t_1^-)|^2},
\qquad
\sigma_{\mathrm{emit},a}
:=1-\sqrt{1-\eta_{\mathrm{emit},a}}.
\]

The numerator uses
`[A_a-U_{A,a}^{(h)},A_a+U_{A,a}^{(h)}]`; the terminal characteristic comes from
the common contract's complex interval disk, and interval division is permitted
only when the denominator lower endpoint clears its frozen positive guard. The
candidate is reaction-feasible only when the entire resulting ratio interval
lies in `[\eta_emit,min,1]`; the deterministic midpoint value used for the
reaction must lie inside it. This makes the isolated quadratic characteristic
debit equal the canonical measured outgoing work within its retained enclosure
without a runtime-tuned coefficient. The final-state reaction is

\[
(a_a^{out})'=(1-\sigma_{\mathrm{emit},a})a_a^{out},
\qquad
(a_a^{in})'=a_a^{in}.
\]

\[
u_a'=\frac{(a_a^{out})'+(a_a^{in})'}{\sqrt2},
\qquad
z_a'=\frac{(a_a^{in})'-(a_a^{out})'}
{\sqrt2\,i\,o_a\omega_{p,a}}.
\]

Let `delta_z_a=z_a'-z_a` and `delta_u_a=u_a'-u_a`. The candidate reaction is

\[
D_0'=D_0+q_a\,\delta z_a,
\qquad
V_{D,0}'=V_{D,0}+q_a\,\delta u_a.
\]

This guarantees the requested winner-coordinate change but does not pretend
that other nonorthogonal probe readings remain unchanged. The receipt records
their exact cross-talk through `M_ba`.

The text layer never writes field planes. It submits the already preflighted
winner reaction through the same controller as a canonical
`transition_kind=port_reaction`. The reaction advances no logical time and
does not independently integrate `epsilon2_ema`, but it repeats the ordinary
full-energy, bound, topology, stability, predecessor/state-hash, and atomic
commit checks against the unchanged predecessor. Any mismatch or failed
reaction emits no symbol.

The authoritative exported work is the full-Hamiltonian debit

\[
W_{\mathrm{emit},a}
:=
H(X_{\mathrm{before}})
-
H(X_{\mathrm{after}}),
\]

including kinetic, gradient, base, nonlinear, composition, scale-link, and
topological-retention `U_topo` changes. The isolated quadratic characteristic expression

\[
W_{\mathrm{port,quad},a}
:=\frac{w_D}{2}
\left[1-(1-\sigma_{\mathrm{emit},a})^2\right]
|a_a^{out}|^2
\]

is retained only as a port diagnostic. It is not substituted for the full
field-energy change. The reaction commits only when
`0<W_emit_min<=W_emit,a<=W_emit_max`, every component is finite, the total
energy debit is positive, and the passivity/ledger residual is within the
versioned numerical envelope. G11 independently recomputes the probe frame,
reaction synthesis, full pre/post Hamiltonian, cross-talk, state hash, and
trajectory samples. The emitted event is never reintroduced through inbound
`A_text`, so source work is not counted twice.

After each committed event the fixed codec applies byte/control semantics and
the field begins a fresh window. Generation stops only at `end_turn`, a role
boundary, output limit, abstention, or visible failure.

The clean schema cutover is:

```text
cassi.qi-flow-text-event.v2
cassi.qi-flow-text-result.v2
cassi.qi-flow-chat-turn.v2
```

Each event records logical interval, direction, symbol/control, state-in/out,
packet/probe/trajectory/ledger/decision/step hashes, integrated signed outflow,
gates, and commit identity. The result chains every prompt and output event,
contains the exact byte hash and decoded text, and validates contiguous state
and receipt predecessors. Raw trajectory arrays are transient and never stored
in session metadata.

### Dynamic text-port frame and exact reaction pruning

The static 260-probe frame is not by itself a text capability claim.
**QI-TEXT-001** requires a `QiDynamicPortFrame` measured on the actual
selected fastest-sheet size `N_0` and the complete temporal response window.
Its canonical evidence identity is
`cassi.qi-flow-dynamic-port-frame.v1`. The frame is a diagnostic artifact,
not a second field or a learned readout.
The retained object contains `frame_id`, step/predecessor/head hashes, port
and descriptor identity, horizon and intervention-set hashes, response-vector
payload digests, interval-certified `rank_lower`/`rank_upper`, singular-value
and conditioning intervals, cross-talk matrix/bound, sampling/refinement
identity, and the exact no-peek candidate inputs. Dynamic rank is never
inferred from the static probe Gram matrix.


The frame profile freezes the source and receiver probe ordering, actual
`N_0`, predecessor state, null source, candidate source amplitudes, temporal
sample grid, positive trajectory metric \(W_{\mathrm{traj}}\), rank
resolution \(\delta_{\mathrm{rank}}\), conditioning guard, cross-talk guard,
and interval/refinement identity. For each source probe/symbol \(a\), the
runtime rolls out the same zero-new-observation candidate from the same
predecessor as the registered null. At temporal sample \(t_\ell\), the
response of receiver probe \(b\) is

\[
r_{b,a,\ell}
:=
\left\langle p_b,
D_{0}^{(a)}(t_\ell)-D_{0}^{(\mathrm{null})}(t_\ell)
\right\rangle_{W_0}.
\]

Each source column is work-normalized before rank/conditioning:
\[
\widetilde r_{b,a,\ell}
:=
\frac{r_{b,a,\ell}}
{\sqrt{W_{a}^{\mathrm{adm}}+W_{\mathrm{traj,ref}}}},
\qquad
W_{\mathrm{traj,ref}}>0,
\]
where \(W_a^{\mathrm{adm}}\) is the declared admitted source work for that
probe. The profile records its interval and the frame stacks
\(\widetilde r\) (the raw response remains only as a digest). A zero,
negative, or unresolved work denominator rejects the frame; rank and
cross-talk are never inflated by a larger source packet.

The frame may additionally retain the paired characteristic
\(a_b^{\mathrm{out}}\) and \(a_b^{\mathrm{in}}\) differences, but it may not
replace the field trajectory with a static score. Stack the normalized
responses \(\widetilde r\) into \(\mathsf R\) with rows \((b,\ell)\), and define

\[
\mathsf K
:=\mathsf R^{H}W_{\mathrm{traj}}\mathsf R,
\qquad
\mathsf C_{a,a'}
:=
\frac{|\mathsf K_{a,a'}|}
{\sqrt{\mathsf K_{a,a}\mathsf K_{a',a'}}},
\]

when both denominator intervals clear their positive guard. Directed
interval SVD/enclosure supplies

\[
\operatorname{rank}_{\delta_{\mathrm{rank}}}(\mathsf R)
:=\#\{j:\sigma_{j}^{-}>\delta_{\mathrm{rank}}\},
\qquad
\operatorname{cond}(\mathsf R)
:=\frac{\sigma_{\max}^{+}}{\sigma_{\min}^{-}},
\]

with condition `infinite/invalid` when the lower smallest singular value does
not clear its guard. The receipt records singular-value intervals, rank,
conditioning, every cross-talk interval, null/collision envelope, temporal
grid, source/receiver hashes, actual `N_0`, and the full state/operator
predecessor. A 260-symbol frame may be overcomplete: rank is the measured
rank, not 260, and a cross-talk interval is never relabeled as independent
symbol capacity. The 16-by-16 calibration frame cannot satisfy this contract
for another `N_0`.

Trajectory arrays used to construct the frame are bounded evidence artifacts,
never runtime state. Gate and calibration runs retain the complete raw/null
arrays in a separate content-addressed artifact whose hash is published by the
frame; live non-validation runs may retain only that hash, the bounded samples
required by the receipt, and interval summaries. No response matrix, probe
activation, output history, or candidate consequence enters `QiFieldState`.
The frame's source and receiver interventions are field-internal diagnostics;
they do not feed emitted bytes back through `A_text`.

**QI-TEXT-002** requires exact interval-certified reaction pruning under
W11D/G11D. The exhaustive reference evaluates every raw-eligible candidate
and the registered null from one predecessor, performs terminal/trajectory
gates, full-Hamiltonian reaction preflight, and the calibrated raw-runner
margin. The pruned evaluator starts with the identical complete candidate-set
digest and may omit a candidate only after a directed interval certificate
proves one of the following:

1. the candidate's full reaction is provably infeasible over its entire
   interval; its reaction branch is skipped, but the candidate remains in the
   raw-runner/robustness frontier with that certified infeasibility;
2. the candidate's best possible score upper bound cannot change the
   exhaustive winner, raw runner, null comparison, abstention result, or
   strict uncertainty margin; or
3. an interval refinement proves the same candidate decision for every value
   remaining in the enclosure.
Each candidate carries one interval tuple
\[
\mathcal I_a=
[\underline A_a,\overline A_a]\times
[\underline F_a,\overline F_a]\times
[\underline C_a,\overline C_a],
\]
for integrated response, reaction feasibility, and the final calibrated
decision quantity, respectively. The interval evaluator refines this tuple
using the same directed trajectory, terminal, Hamiltonian, topology, and
raw-runner predicates as exhaustive evaluation. It maintains the complete
candidate frontier, certifies impossible reaction intervals first, and then
uses lower/upper score and margin bounds to certify dominance or fixed
abstention. It evaluates/refines any interval whose endpoint combinations
could change the winner or tie ordering; finite precision exhaustion is
`abstain`, never a central-value guess.


For clarity, let \(\mathfrak D(\mathcal A)\) be the exhaustive decision
(selected symbol, canonical tie ordering, or `abstain`) after all candidate
intervals in \(\mathcal A\), including the null, are refined until the
registered decision predicate is resolved. A candidate \(a\) is prunable only
when the certificate proves

\[
\mathfrak D(\mathcal A)
=\mathfrak D(\mathcal A\setminus\{a\})
\]

for every value permitted by its current intervals, and the receipt retains
the proof bounds. A raw-eligible candidate whose reaction is infeasible
remains a robustness competitor exactly as in the exhaustive path until its
score interval is also proven unable to change the decision. An overlapping
or unresolved interval is refined or causes `abstain`; it is never guessed.

The pruning receipt block records the complete candidate-set hash, exhaustive
reference decision/hash, pruned decision/hash, each evaluated and pruned
candidate, reaction-feasibility interval, score bounds, raw-runner/null
identities, margin bounds, refinement steps, and proof predicate. Its canonical
fields are `exhaustive_candidate_set_sha256`,
`pruned_candidate_set_sha256`, `interval_rule_sha256`, `decision_sha256`,
`decision_equivalent_to_exhaustive=true`, and per-candidate interval outcomes.
It is content-addressed evidence and does not authorize a shortcut in a later
session. There is no heuristic `top_k`, central-score shortlist, fixed
candidate truncation, beam, random omission, or resource-budget omission. If
all candidates cannot be bounded within the declared memory/time envelope, the
runtime evaluates the complete set or abstains/fails; it does not silently
change the candidate set.

The decision-equivalence fixture runs exhaustive and pruned evaluation over
the actual 260 candidates, singleton and empty competitor cases, candidate
order permutations, exact ties, near-overlap intervals, high-score
reaction-infeasible candidates, wider-uncertainty raw runners, terminal-dark
historical trajectories, rank-deficient/cross-talk frames, and exact reverse
orientation. It requires byte-identical selected symbol or abstention,
winner/raw-runner/null identities, successor/reaction state hashes, event
bytes, and field ledger; only traversal order may differ, and that order is
recorded. Missing response bytes, rank/conditioning enclosures, no-peek
inputs, or a non-equivalent pruning decision fails
`DYNAMIC_PORT_FRAME_INVALID`. A mismatch is `FAIL`, not a reason to relax the
interval or adopt top-\(k\) semantics.

Output remains one-way while these diagnostics run. The emitted symbol,
control event, provider fragment, and later response bytes are not candidate
inputs and cannot be observed by the frame or reaction evaluator. Teacher,
language-model, sampler, Qwen/llama.cpp, KV, policy, and evaluator state is
outside the live field process; an offline exhaustive verifier may inspect
immutable receipts but cannot supply a target wave, mutate the field, or
select a symbol.

### QI-TEXT-003 field necessity and robust codebook packing

**QI-TEXT-003** is owned by Part 8, implemented by **W11D**, and consumed by
**G11/G11D**. It adds two offline evidence objects:
`cassi.qi-flow-text-ownership.v1` for field-necessity ownership and
`cassi.qi-flow-text-codebook-packing.v1` for uncertainty-aware trajectory
separation. Neither object is a field plane, readout, decoder cache, or
runtime policy.

Before observing outcomes, W11D freezes a finite nonempty designated set
\(\mathcal E_{\mathrm{sens}}\) of resolved, non-tie, nonprotocol fixtures for
which a named field-state intervention is predicted to cross the decision
boundary. The set covers at least one adaptive emitted byte; it also covers a
field-caused `abstain` when the release makes a field-owned-abstention
capability claim. Each fixture freezes the exact predecessor, source bytes,
packet intervals, candidate set/order, profile/operator hashes, no-peek inputs,
reaction predicate, and intervention before the run. The intervention's sole
changed input is a profile-registered field-state transform: field-frozen,
zero-field, metric-preserving phase/current permutation, or another fixed
field-only control. Its transform, energy/work matching, and state hash are
committed in advance. Candidate consequences, future observations, output
bytes, and abstention labels are never changed by the harness.

Every runtime adaptive output still links to its live field trajectory and
decision receipt, but a fixture outside \(\mathcal E_{\mathrm{sens}}\) does
not inherit an individual counterfactual-necessity claim. A broader
per-byte/per-history necessity claim requires its own preregistered coverage
set and cannot be inferred from one sensitive fixture.

Deterministic protocol controls such as `end_turn`, `role_boundary`,
`max_output_symbols`, malformed/failed cycles, and transport completion are
recorded as protocol-owned rows with an explicit
`ownership_exemption_reason`; they are not claimed as field-selected bytes.
An abstention caused solely by an invalid packet, limit, or unresolved
transaction is likewise protocol/guard-owned. A designated field-caused
abstention remains in the necessity arm below.

For \(e\in\mathcal E_{\mathrm{sens}}\), let \(d_e(X)\) be the complete
decision from the frozen candidate set, including the selected canonical
byte/control or `abstain`, and let \(\mathcal I_{d,e}\) be the directed
enclosure for the live/intervened decision margin. A field-necessity claim
requires
\[
d_e(X_{\mathrm{live}})\ne d_e(X_{\mathrm{intervened}}),
\qquad
\underline M_{d,e}
\geq
\max(\Delta_{\mathrm{abs}},
\Delta_{\mathrm{rel}}\overline S_{d,e})>0,
\]
where the interval lower margin \(\underline M_{d,e}\) and scale
\(\overline S_{d,e}\) include reaction feasibility, null, raw-runner, and
quadrature uncertainty. For a designated adaptive byte, the intervention
must produce a different committed byte/control or a certified abstention.
For a designated field-caused live abstention, it must produce a committed
byte/control with a positive resolved margin; two arms that both abstain do
not establish field ownership. Protocol/guard-owned controls use the explicit
exemption above and are not required to flip. Candidate-order permutation and
every registered semantics-preserving control must leave the decision
unchanged. A score change with the same decision, state-hash inequality, or
output-count change without the preregistered decision flip is not a
field-necessity result.

`cassi.qi-flow-text-ownership.v1` records the event/decision identity,
predecessor and post-intervention field hashes, complete candidate-set and
no-peek-input hashes, live/intervened source and work rows, selected
byte/control or abstention reason, winner/raw-runner/null identities,
reaction and interval margins, the field-only intervention descriptor,
matched-energy/error bounds, and replay/control outcomes. It records both
positive ownership and a failed/non-discriminating intervention; an
unresolved interval is `indeterminate` and cannot be promoted to ownership.
The receipt's state intervention is transient evidence: no intervention
label, decision margin, byte history, or field-necessity score enters
`QiFieldState` or a checkpoint.

The packing arm uses the complete integrated trajectory rather than a
snapshot. For each registered symbol/control candidate \(a\), let
\(\Gamma_a(t_\ell)\) contain the profile's characteristic outflow and
field-to-port trajectory on the complete output window at the fixed sample
times.

The default packing domain is explicitly **single-predecessor**: every
\(\Gamma_a\) starts from the same exact predecessor field/state head, packet
frontier, clock, geometry, and one finite output window. Thus
\(K_{\mathrm{robust}}\) and any \(K_{\mathrm{ind}}\) below are conditional on
that predecessor and window; they do not imply sequence-level capacity,
history-conditioned separation, or compositional generalization. A sequential
text claim would require a separately frozen, bounded
history-conditioned held-out sequence-collision fixture; no such claim is
made by this single-predecessor receipt, and the fixture would remain
evidence-only rather than runtime state or rank.

For every pair \(a\ne b\), the work-normalized trajectory distance is

\[
\widehat d_{ab}
:=
\frac{
\left(\sum_{g,\ell}\omega_{g,\ell}
\left\|\Gamma_a(t_\ell)-\Gamma_b(t_\ell)\right\|_{W_{\mathrm{text}}}^{2}
\right)^{1/2}}
{\sqrt{W_{a}^{\mathrm{adm}}+W_{b}^{\mathrm{adm}}
+W_{\mathrm{traj,ref}}}},
\qquad
W_{\mathrm{traj,ref}}>0.
\]

The receipt carries a certified nonnegative uncertainty radius \(U_{ab}\)
and

\[
d_{ab}^{-}:=\max(0,\widehat d_{ab}-U_{ab}),
\qquad
d_{ab}^{+}:=\widehat d_{ab}+U_{ab}.
\]

The profile freezes positive separation/collision thresholds and uncertainty
scales. A pair is robustly separated only when

\[
d_{ab}^{-}
\geq
\max\!\left(\delta_{\mathrm{sep}},
\Delta_{\mathrm{abs}}+\Delta_{\mathrm{rel}}d_{ab}^{+}\right)>0,
\]

and is a collision when \(d_{ab}^{+}\leq\delta_{\mathrm{coll}}\). An interval
that overlaps the collision/separation boundary is unresolved and fails the
robust-packing claim; it is never resolved by symbol ID or central distance.
The receipt reports

\[
d_{\mathrm{pack}}^{-}:=\min_{a\ne b}d_{ab}^{-},
\qquad
r_{\mathrm{pack}}^{-}:=\frac12d_{\mathrm{pack}}^{-},
\]

along with every pair's separation, collision, or unresolved label. The
minimum is over the complete registered codebook and separately includes
the null/abstention competitor; no pair may be dropped because its central
score is low or its reaction is infeasible.

The codebook cardinality
\(K_{\mathrm{codebook}}:=|\mathcal A_{\mathrm{text}}|\) is a profile
protocol count (260 is the current fixed value where declared). Dynamic
trajectory rank
\(\operatorname{rank}_{\delta_{\mathrm{rank}}}(\mathsf R)\) remains the
interval-certified response rank from **QI-TEXT-001**, measured on the
actual fastest-sheet size \(N_0\) and temporal window. Probe count, \(N_0\),
codebook size, and dynamic rank are recorded as separate quantities:
dynamic rank is neither automatically 260 nor automatically the alphabet
size, and codebook cardinality cannot be inferred from a static Gramian or
used to inflate a collision-prone trajectory frame.

Pairwise robust separation is not a claim of \(K_{\mathrm{codebook}}\)
independent field channels. The receipt reports
\(K_{\mathrm{robust}}\), the number of entries whose complete trajectory
intervals clear the packing margin, separately from
\(K_{\mathrm{codebook}}\) and dynamic rank. An **independent-symbol capacity**
claim is permitted only when a profile declares \(K_{\mathrm{ind}}\), the
lower interval of the QI-TEXT-001 dynamic rank clears \(K_{\mathrm{ind}}\),
the singular/conditioning guard is finite, and a byte/control equivalence
fixture maps those independent trajectories without collision. Otherwise a
low-rank many-point codebook may be reported as a protocol cardinality and
robust packing result only; it cannot be relabeled \(K_{\mathrm{ind}}\) or
used to claim 260 independent symbols.

`cassi.qi-flow-text-codebook-packing.v1` records the complete codebook and
candidate-set hashes, actual \(N_0\), probe/frame and temporal-grid
identities, predecessor/state/operator hashes, trajectory digests, work
intervals, every pairwise distance/uncertainty interval, null and
abstention rows, thresholds, robust-packing radius, \(K_{\mathrm{robust}}\),
\(K_{\mathrm{ind}}\) when declared, collision list, refinement steps, and
candidate-order/phase/current/work-matched controls.
Raw trajectories are bounded content-addressed evidence only. Packing and
ownership are offline calibration receipts: they do not prune candidates,
alter the live no-peek score, feed output bytes back to `A_text`, or add
credit/history/embedding state. A missing trajectory, unresolved pair,
field-necessity decision, or actual-\(N_0\) mismatch blocks the QI-TEXT-003
claim rather than authorizing a fallback.

### UTF-8 and control-event streaming

Byte symbols append exactly one raw byte. Role symbols and `end_turn` are
observable committed field events with empty content. The sole decoder is
`utf8-rfc3629-maximal-subpart.v1`: it accepts only RFC 3629 scalar-value
encodings, rejects overlong forms, surrogate code points, values above
`U+10FFFF`, stray continuation bytes, and invalid lead bytes, and applies the
Unicode maximal-subpart rule to each ill-formed subsequence. One `U+FFFD` is
emitted for each maximal subpart consumed, never one per implementation chunk
and never by silently dropping a byte. The descriptor pins the Unicode rule
version and exhaustive valid/invalid chunk-partition fixture digest.

The incremental decoder retains at most three committed pending bytes, emits
only complete scalar sequences, performs no NFC/NFD or other normalization,
and is chunking-invariant: decoding any partition of the same committed raw
byte string yields the same scalar sequence and UTF-8 output bytes. At
`end_turn`, role boundary, output limit, or abstention, an incomplete valid
prefix is consumed under that same maximal-subpart rule. The response record
stores the exact raw byte string, scalar/output UTF-8 bytes, fragment
boundaries, replacement count, and pending-tail-before-flush bytes.

A failed or uncommitted cycle contributes no byte, does not mutate the decoder,
and cannot flush a speculative tail. SSE exposes only post-Commit-A stored
fragments, so concatenated stream bytes and the nonstream content bytes are
identical for every valid, invalid, and truncated sequence.

The OpenAI finish mapping is:

| Field stop reason | OpenAI `finish_reason` |
|---|---|
| `end_turn` | `stop` |
| `role_boundary` | `stop` |
| `field_abstained` | `stop` |
| `max_output_symbols` | `length` |
| failed/uncommitted cycle | no successful completion |

The Cassi metadata retains the exact field reason.

### Transactional terminal and provider

`CassiQiSessionStore` supplies one cross-process per-session lock shared by
terminal, provider text, and world events. Distinct sessions may run
concurrently; the same session cannot.

Request processing has a lock-free validation phase. Before constructing a
session path, opening a session lock, allocating field/candidate state, or
entering a transaction, a bounded parser validates method and normalized path,
header count/bytes, declared content length, canonical JSON byte/depth limits,
allowed keys/types/model/messages, ASCII session-ID allowlist, request
sequence, idempotency key, create/resume flag, stream flag, and world headers.
It canonicalizes the body once into immutable `QiPreparedRequest` bytes and
hashes. Any failure returns the registered `4xx` without touching session
storage.

The stateful transaction is then:

1. resolve the validated session ID beneath the canonical store root, acquire
   its exact lock, and load/validate the v3 envelope, object index, field/head,
   source identity, and request high-water mark;
2. apply the state-dependent create/resume/idempotent-retry/next-sequence rule
   as a compare-and-swap against that loaded head;
3. bind immutable staged object handles under the validated store root and
   process the complete request into candidate events, state, ingress cursor,
   flow receipts, and `cassi.qi-flow-ownership.v1`; the live transaction never
   constructs `cassi.qi-flow-displacement.v2`;
4. durably stage the indexed event/result/ownership/step/checkpoint objects and
   exact response/event-frame bytes using the canonical commit protocol;
5. Commit A one v3 envelope containing the successor state/head, request high
   water mark, ingress journal/head/cursor/source frontiers/watermark, proposal
   and port-reaction identities, request identity, response hash/body, ordered
   event/result/turn/stream-object bytes/hashes, and bounded retention metadata;
6. update in-memory state/display transcript only after reopen-validating the
   committed envelope, release the lock, then expose the already committed
   nonstream response or exact stored event-granular stream.

This is **validate, prepare, lock/CAS, compute, atomic commit, then wire
streaming**. Streaming is event-granular but not live-compute streaming. A
disconnect after commit does not roll back the field; a generation/save
failure sends neither a successful response nor `[DONE]` and leaves the prior
checkpoint, ingress cursor, and in-memory display unchanged. Immutable staging
handles are closed and quarantined on every failure path; no path or request
field is reinterpreted after validation.

`cassi_conscious_chat.py` follows the same candidate-then-save rule. A failed
save leaves both in-memory state and messages unchanged. Its default one-shot,
interactive, and JSON surfaces remain; an explicit event-stream mode outputs
text fragments once and prints no duplicate final reply.

`cassi_persistent_provider.py` retains:

- `GET /health`;
- `GET /v1/models`;
- `POST /v1/chat/completions`;
- deterministic request validation;
- rejection of temperature, top-k/top-p, seed, sampling, or wrong model;
- loopback-only `127.0.0.1:8086`;
- one field state per session;
- no Qwen, GGUF, tokenizer, LM head, KV, sampler, or fallback.

Health and responses add profile, codec, engine, checkpoint-head, step-chain,
backend, live ownership, and Qwen-zero process-evidence identities built by
`cassi_qi_receipts.py`. The provider never imports `cassi_qwen_displacement.py`
or loads a baseline artifact. Historical Qwen baseline comparison remains
available only to the separately invoked offline displacement driver.

The target API contract is `cassi.qi-flow-openai-api.v1`, with model ID
`cassi-qi-flow-v1`. `POST /v1/chat/completions` requires the strict headers
`X-Cassi-Session-Id`, `X-Cassi-Request-Sequence`, and `Idempotency-Key`, plus
`X-Cassi-Create-Session: true|false`. Session IDs match the profile's ASCII
allowlist and bind the store path, lock, profile, and every emitted receipt.
`create=true` succeeds only when the session is absent and sequence is zero;
an existing session conflicts. `create=false` on an absent session is `404`.
A new session has `request_high_watermark=null` and admits sequence zero. Every
later new request must be exactly high-water-plus-one, and gaps conflict. A
previously committed sequence/key with the identical canonical body hash and
stream flag returns the exact stored response/event bytes without advancing the field.
Key/body/stream mismatch, or retry after full response bytes age out, is `409`
and never re-executes. The profile fixes retained response count, aggregate
bytes, and retry horizon; the monotonic high-water mark prevents an evicted old
request from becoming new work.

The API schema freezes allowed request keys and types, model name, message/role
grammar, error object, response fields, SSE frame bytes, finish mapping,
canonical JSON, and the hash from committed response bytes into the session
envelope. Unknown keys, unsupported OpenAI sampling fields, missing extension
headers, or limit violations return the registered `4xx` error before state
allocation. Terminal invocations require the same session ID, request sequence,
idempotency key, and explicit create/resume mode through CLI/config; there is no
implicit “default” mutable session.

The bundle pins `cassi.qi-flow-chat-request.v1`,
`cassi.qi-flow-chat-response.v1`, `cassi.qi-flow-api-error.v1`, and
`cassi.qi-flow-sse-frame.v1`. A world-attached request additionally requires
`X-Cassi-World-Id`, `X-Cassi-Episode-Id`, and `X-Cassi-Logical-Tick`; all three
must match the session's authenticated currently open tick before the text
packet is admitted. A non-world session omits those headers and uses canonical
`world_id=none`. This provider-text-to-world schedule is shared by G13R and G13C.

For SSE:

1. emit the stored assistant-role preamble;
2. emit each stored ordered `cassi.qi-flow-text-event.v2` frame, with text
   content only when a complete UTF-8 fragment exists;
3. emit a final frame carrying the committed
   `cassi.qi-flow-ownership.v1`, flow result/step/checkpoint identities, and
   exact finish reason;
4. emit `[DONE]`.

Stream and nonstream executions starting from identical fresh states must end
at the same state, event chain, bytes, text, and receipt. Controls remain visible
as empty-content event metadata.

### Text and serving source migration

| File | Required change |
|---|---|
| `cassi_field_language.py` | retain codec; replace static emission receipts and direct `emit()` loop with timed ingress, integrated outflow, text event/result v2, and trajectory reaction |
| `cassi_conscious_chat.py` | chat-turn v2 identity, transient event callback, candidate/save/assign transaction, exact session/request CLI binding, no transcript replay |
| `run_cassi_conscious_chat.py` | explicit profile/backend/session/sequence/idempotency and event-stream modes; no field logic |
| `cassi_persistent_provider.py` | `cassi.qi-flow-openai-api.v1`, one shared v3 flow transaction, cross-process lock, loopback enforcement, event SSE, live ownership health/receipts |
| `cassi_qwen_displacement.py` | offline only: combine historical baseline hash with verified `cassi.qi-flow-ownership.v1`, profile v1, step v1, decision v1, state/session v3, and checkpoint identities into `cassi.qi-flow-displacement.v2` |
| `measure_cassi_field_language_dependence.py` | replace direct static `emit()` arm with live/reversed/frozen integrated-flow engine arms |
| `run_cassi_field_only_displacement.py` | separately invoke the offline displacement builder over exact live receipt schema IDs; never enter provider startup |
| `verify_cassi_qi_flow.py` | require trajectory-owned text or valid abstention and prove canonical text call graph has no snapshot `emit()` |
| `conscious-chat.json` | strict canonical composition config selecting `cassi.qi-flow-profile.v1`, backend, v3 state directory, API/session limits, and no baseline path |
| `README.md` | document the current flow runtime after release-readiness verification |

All v1 text/session receipts and v2 modal state artifacts are rejected. There is
no deprecated alias, automatic conversion, state reset on mismatch, or static
emission fallback.

