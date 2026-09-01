# Memory, recall, grounding, and learning

> CassiFI implementation plan, Part 6. [Previous](./05-boundaries-body-and-action.md) · [Index](../README.md) · [Next](./07-world-loop-and-transactions.md)

## Memory, recall, and cross-modal grounding

Cue-addressable episodic/associative memory remains entirely in slower
`D,C,V_D,V_C` circulation under the same field tensor. `epsilon2_ema` is a
local constitutive statistic, not a cue-addressable memory store and not a
recall gate. Continuous reciprocal cross-scale links replace top-one
consolidation; **QI-SCALE-001** requires the selected `scale_geometry_mode` to
be explicit profile data. `temporal-full-rank` and
`spatiotemporal-pyramid` are the only production values. Production chooses
one only after the registered W6T/G6T comparison and records any rank loss; a
pyramid may not reduce rank implicitly.

A transient `QiRecallRequest` supplies a cue boundary and expected modality or
world port. The runtime:

1. applies the cue as ordinary source work through its validated boundary;
2. evolves through the same fixed operators and selected scale geometry;
3. measures slow-to-fast predicted outflow before the successor observation;
4. records the predicted boundary and slow-link work hashes;
5. compares the successor observation before correction; and
6. applies the residual through the same metric-adjoint boundary.

Recall is accepted only if the slow field predicts a held-out successor and
reduces pre-correction work versus shuffled-cue, frozen-slow, scale-link-off,
and no-recall controls. `reset(preserve_memory=True)`, a replay buffer,
transcript re-ingestion, template library, learned lookup, or copied hidden
state is not a flow-memory implementation.

### Two memory tiers in one field

The retention order is a hard dependency. **QI-RET-001** requires W4R to
install the topological-retention Hamiltonian, topology algebra, barrier, and stability core
after W4 and before W5. W10R later owns behavioral retention and
consolidation. W10R cannot add an unreceipted memory mechanism to compensate
for a missing W4R law, and a W4R topology receipt alone is not behavioral
retention.

**Within-sector analog acquisition** is the first memory tier. Repeated
ordinary boundary and residual-return work changes amplitudes, phases,
circulation, and reciprocal-link balance continuously while the complete
valid topological-retention sector vector \(\mathcal T_{\mathrm{topo}}\) remains unchanged. Its capacity is
the reachable, response-distinguishable subset of the current metastable
basin. It is demonstrated by a partial cue that improves a held-out
successor, emission, or action after washout without a phase slip. A trace
that merely remains detectable, or a same-sector state with no returned
prediction, is not analog acquisition.

**Topological consolidation** is the second, distinct tier. A work-funded
positive-duration phase-slip path crosses a certified topological-retention barrier and
changes the complete derived sector vector \(\mathcal T_{\mathrm{topo}}\), including its
registered winding and circulation coordinates. It is not a copy of the
analog signal and does not promote a sector integer to a hidden key. The
phase-slip receipt retains the path, barrier lower bound, complete admitted/
reflected/absorbed work partition, old/new sector vectors, branch/amplitude
guards, residence, and the subsequent causal return. A controller-only
retention reset is a separately authorized transition and is never called
acquisition.

Both tiers use only the existing `QiFieldState.field` planes. Derived topology,
basin coordinates, response matrices, and capacity values are diagnostics
computed from a candidate; they are not persistent slots. There is no analog
array, sector table, address key, learned matrix, sidecar EMA, optimizer,
embedding, replay store, or external memory. **QI-RET-002** fails if the two
tiers cannot be measured separately without adding state.

### Capacity, saturation, overwrite, and recovery

For each registered experience family, the driver computes a finite
within-sector intervention-response matrix \(\mathsf R_{\mathrm{analog}}\)
from field-to-boundary trajectories, with fixed work and delay normalization.
Its rank/conditioning and the number of distinguishable response intervals
inside one valid basin define reachable analog capacity; the topology driver
enumerates only the sector vectors reachable by certified paths and records
their basin residence. These are measurements, not selectors:

\[
\operatorname{Cap}_{\mathrm{analog}}
:=\operatorname{rank}_{\delta_{\mathrm{resp}}}
\mathsf R_{\mathrm{analog}},
\qquad
\operatorname{Cap}_{\mathrm{topo}}
:=\#\{\mathcal T_{\mathrm{topo}}:
\text{a certified path reaches }\mathcal T_{\mathrm{topo}}\}.
\]
The topology-algebra fixture applies the declared identity, inverse, and
composition operations to reachable sector paths and records closure,
associativity, inverse return, winding/circulation residue, and path
orientation. A failed algebraic law is a topological-retention/W4R failure, not an
alternative memory encoding.


The resolution \(\delta_{\mathrm{resp}}\), intervention directions, horizon,
and work metric are frozen in the experience plan. A candidate is **saturated**
when additional paired work stays within the same declared basin but produces
no response interval separated by \(\delta_{\mathrm{resp}}\), while all
state, barrier, and work guards remain valid. Saturation is reported with the
last distinguishable analog state and its admitted work; it is not normalized
away and does not authorize a new slot.

An **overwrite** is observable, not silent replacement. It occurs when a
subsequent admitted residual either drives the analog state across its
measured basin boundary or funds a certified phase slip to a different
\(\mathcal T_{\mathrm{topo}}\). The receipt names the old response/sector, new
response/sector, complete path work, barrier interval, and the first
post-overwrite cue. If the next experience cannot be admitted without
violating a bound, the field abstains/rejects and leaves the predecessor
unchanged; it never clips an analog value or discards an old state as a
hidden eviction.

**Recovery** is measured after neutral/source-free washout and a partial cue.
Within-sector recovery requires the old analog response to return with a
work-normalized successor improvement. Topological recovery requires a new
certified reciprocal path to the original sector/basin, or the separately
authorized retention-reset receipt; merely observing the old integer or
reloading a checkpoint is not recovery. The driver reports retention,
residence, recovery fraction, recovery work, and whether A remains measurable
after B in an `A -> B -> A` exercise. **QI-RET-003** therefore measures the
topology algebra, reachable basin capacity, saturation, overwrite, and
recovery rather than treating a changed endpoint or a long-lived amplitude as
memory.

### Field-native selective forgetting and reacquisition

**QI-RET-003** also requires an addressable forgetting lifecycle, not merely a
retention or overwrite curve. The canonical evidence object is
`cassi.qi-flow-forgetting.v1`. A frozen fixture registers a target response
functional (or an allowed complete topological-retention sector transition), a set of
collateral response functionals, their metric/scale/body descriptors, a finite
incident/source-work budget, and the pre/post-washout/reacquisition
frontiers. `forgetting_id` and `target_descriptor_sha256` identify that
fixture and its receipt only; neither is an address, key, label, or slot in
`QiFieldState`.

The production forgetting arm is field-native. Starting from an exact
pre-forgetting predecessor \(X_A\), it applies only ordinary declared
boundary packets, residual-return packets, and the existing field law to
produce \(X_{A\setminus j}\); it does not allocate a selective erase
operator, lookup table, target register, or auxiliary queue. With
\(\rho_j\) the target response and \(\rho_k\) each collateral response, the
receipt must prove directed intervals for

\[
\rho_j(X_A)-\rho_j(X_{A\setminus j})
\geq \Delta_{\mathrm{forget},j}>0,
\qquad
\left|\rho_k(X_{A\setminus j})-\rho_k(X_A)\right|
+U_{\rho_k}
\leq \Delta_{\mathrm{collateral},k}
\quad(k\ne j).
\]

The target loss and every collateral bound are evaluated on the complete
field trajectory and held-out successor, not on a state hash or endpoint
label. `W_forget` is the complete incident/admitted/reflected/absorbed/
residual work partition for the finite path; its positive interval must fit
the frozen work budget and every ordinary Hamiltonian, amplitude, branch,
stability, and source-ledger guard. If the target is a topological component,
the path must additionally carry the complete old/new \(\mathcal T_{\mathrm{topo}}\), a
certified phase-slip barrier and residence interval, and the registered
topology-algebra identity. A below-barrier path that changes the claimed
sector, an unresolved collateral interval, or a target loss without a
causal successor change is `FORGETTING_SELECTIVITY_FAIL`; it is rejected and
does not erase or clip the predecessor.

The lifecycle is explicit and restartable:

1. `prepared` names the exact predecessor, target/collateral descriptor
   hashes, and frozen packet schedule;
2. `forgotten` commits the field-only target-loss path and its complete work/
   barrier/sector receipt;
3. `washed_out` evolves for the declared neutral/source-free horizon with no
   cue, reset, checkpoint substitution, or teacher input; and
4. `reacquired` requires a fresh ordinary target cue to restore the target
   response/sector within its declared interval and to improve the held-out
   successor, while collateral remains within its preservation bounds.

The reacquisition arm uses the same field-only path and exact restart
contract. Equal-work one-shot, shuffled/wrong-cue, field-frozen,
phase-scrambled, below-barrier, and collateral-target controls must fail to
produce the registered selective lifecycle. Reopening the post-forgetting
checkpoint, replaying a receipt, observing an old sector integer, or invoking
the controller-only \(\mathcal Z_{\mathrm{topo}}\) reset is not reacquisition. The
production arm has an explicit `no_reset=true` guard; a separately hashed
retention-reset arm may calibrate the contrast but can never count as
forgetting, acquisition, recovery, or evidence for this lifecycle.

`cassi.qi-flow-forgetting.v1` records `forgetting_id`, the complete
predecessor/forget/washout/reacquisition state and receipt heads, target and
collateral descriptor hashes, all packet and checkpoint identities, directed
target-loss/collateral-preservation intervals, incident/admitted/residual
work and barrier intervals, topology vectors when applicable, restart
comparison, no-reset status, and every control outcome. It is bounded
content-addressed evidence. No target functional, collateral score,
forgetting phase, or reacquisition credit persists in the field or checkpoint
state.

### Conversion viability and physical-time constitutive memory

Before experience acquisition, **QI-CONV-001** requires W5V/G5V to prove the
complete frozen \(\mathcal D_{\mathrm{conv}}\) support: every preregistered
cell has zero unresolved status and maps into both
\(\mathcal D_{\mathrm{conv}}\) and
\(\mathcal A_{\mathrm{accepted}}\). The guarded
\(\mathcal D_{\mathrm{prog}}\) cells must clear their positive signed transfer
margin; \(\mathcal D_{\mathrm{neutral}}\) cells must clear the separate bounded
transfer margin, with balanced/exact-zero controls remaining exact no-ops.
Repeated rejection, fixture-only coverage, or post-observation support
shrinkage is not a conversion result. If the frozen-\(Q\) map fails this
complete-domain proof, W5V revises the constitutive law and profile rather than
normalizing, clipping, or labeling rejection as learning.

The physical constitutive time is stored as the positive profile quantity
\(\epsilon_{\mathrm{memory\_time}}>0\), not as a bare per-step knob. For a
field interval \(h>0\), the derived EMA coefficient is

\[
\alpha_h
:=1-\exp\!\left(-\frac{h}
{\epsilon_{\mathrm{memory\_time}}}\right),
\qquad
m_{\epsilon^2,t+h}
:=(1-\alpha_h)m_{\epsilon^2,t}
 +\alpha_h\epsilon_{t+h}^{\,2}.
\]

The plan freezes the physical time, units, and source of \(h\); it never
chooses \(\alpha_h\) per curriculum stage or per example. The constitutive
field remains one of the existing nine planes and receives exactly one
accepted update after the complete conversion/force path. A conversion
statistic or matched EMA cannot satisfy analog or topological recall by
itself.

### Recall, acquisition, and grounding evidence

The field must do more than retain a slowly decaying perturbation. The
implementation distinguishes four observable capabilities:

1. **trace** — a prior drive remains detectable after the drive ends;
2. **recall** — a partial cue causally restores a relevant trajectory;
3. **acquisition** — repeated related experience improves a future prediction,
   emission, or action after a washout interval; and
4. **generalization** — that improvement transfers to a held-out ordering,
   rendering, timing, position, or composition.

An engineering experience exercise uses only ordinary boundary packets,
prediction windows, residual return, field evolution, and canonical
checkpoints. It has no optimizer, gradient update, learned coefficient,
hidden teacher state, internal replay buffer, second persistent object, or
teacher-fed target. External training text or episodes are simply experienced
boundary streams; expected outcomes are scored only after the committed
observation.

Cross-modal grounding uses one body frame and logical clock. A visual event,
audio event, proprioceptive consequence, text event, and motor action retain
their distinct descriptor identities while coupling through the shared field.
A pairing is supported only when the correct causal delay and body transform
predict another modality or world consequence better, per admitted work, than:

- each modality alone;
- matched-energy shuffled pairing;
- positive and negative tick offsets;
- phase reversal;
- mirrored/offset body frame;
- permuted action/efference identity;
- silent, invalid, and no-evolution controls; and
- the fading-retention and reciprocal-link-off comparators.

Instantaneous shared resemblance, static cross-modal cosine, an external
label, or an output byte fed back as an input is never a grounding gate.

## `QiFieldExperiencePlan` and field-only curriculum

**QI-LEARN-001** makes `QiFieldExperiencePlan` the frozen contract for every
field-only curriculum run. The mandatory path is **field-only adaptation under
a frozen externally scheduled experience protocol**: an external scheduler
fixes the complete source/world order, timing, work budgets, stage sequence,
whole-episode splits, washout, stopping, and checkpoint rule before the first
exposure. The field may change only through the ordinary declared boundary and
residual-return trajectories; it cannot choose the next experience, request
extra practice, rewrite the schedule, or observe held-out outcomes. The
object is a frozen, content-addressed experiment record, not a learned
object. Its canonical schema is
`cassi.qi-flow-field-experience-plan.v1`. A plan is valid only when all fields
below are present, canonical, and hashed before the first exposure:

```text
QiFieldExperiencePlan
  plan_id
  plan_sha256
  profile_sha256
  source_identity_sha256
  state_contract_sha256
  scale_geometry_mode = temporal-full-rank | spatiotemporal-pyramid
  codec_sha256
  boundary_descriptor_sha256[]
  body_frame_sha256
  clock_schedule_identity
  raw_utf8_control_streams[]
    {stream_id, descriptor_sha256, source_epoch, source_stream_id,
     intervals, byte_count, bytes_sha256}
  grounded_world_episode_streams[]
    {world_id, episode_id, initial_state_sha256, tick_log_sha256}
  event_and_chunk_partition_fixture_sha256
  timing_and_delay_windows
  work_budgets
    {per_port, per_packet, per_event, per_episode, total}
  residual_budget
  work_classes = {incident, admitted, reflected, absorbed, residual}
  curriculum_stage_specs[]
  whole_episode_split_sha256
    {train_episode_ids, control_episode_ids, heldout_episode_ids}
  washout_schedule
  control_profile_sha256[]
  stopping_rule
  checkpoint_selection_rule
    {initial, pre_washout[], post_washout[], stage_boundary[], final}
  raw_artifact_retention_policy_sha256
  teacher_model_exclusion = true
  plan_self_sha256
```

`stopping_rule` is a declarative plan predicate fixed before exposure, not an
adaptive signal or field-resident controller. Every array is canonically
sorted by its declared stream/episode key and every interval is encoded as a
rational numerator/denominator before `plan_self_sha256` is computed. The
plan's source identity covers byte/control ordering and world tick logs, not a
model or teacher checkpoint.


`raw_utf8_control_streams` contains exact byte strings, role/control events,
source order, chunk partitions, and episode boundaries. It may include
well-formed and intentionally ill-formed RFC 3629 byte sequences. Controls
such as `end_turn`, role boundaries, abstention, and empty events remain
observable committed field events with empty content; they are not omitted
from the stream. The sole decoder is the fixed maximal-subpart codec already
owned by the text boundary.

`grounded_world_episode_streams` contains exact episode and world/adapter
descriptor identities, body-frame pose, logical-tick schedule, modality
packet digests, action-geometry digest, and causal delay. The world may expose
the next observation only at its declared post-commit frontier. Unobserved
world payload and hypothetical candidate consequences are not plan inputs to
the live field. Ground-truth observations used to score a completed episode
remain outside the boundary and are never injected as labels, target waves, or
teacher corrections.

The plan freezes source order, all rational intervals, dwell/capture windows,
latency and delay bins, candidate/action work classes, residual-return
budgets, per-event and per-episode maxima, state-domain bounds, and the
selected scale geometry. Any packet whose actual incident, admitted,
reflected, absorbed, or residual work cannot fit its declared interval is
rejected; the runner cannot rescale it to make an episode fit. Every exposure
references the `QiScatteringReceipt` rows for the external and scale ports.
A split that bisects an episode, changes after seeing a result, omits washout,
exceeds a work budget, uses an unregistered stream/control, or selects a
checkpoint post hoc fails `EXPERIENCE_PLAN_INVALID` before field mutation.

### Curriculum stages

The field-only curriculum is a fixed sequence of boundary experiences. A stage
may have a diagnostic evaluator, but it cannot introduce another state or
change a law/profile in place.

1. **Raw UTF-8 and control streams.** Inject one exact raw byte/control event
   per ordinary timed `QiBoundaryPacket`, in codec order. Compare the
   predicted next event with the committed successor before residual return.
   Exercise valid multibyte scalars, every invalid maximal-subpart case,
   partition-invariant chunks, role boundaries, `end_turn`, abstention, and
   empty/max-output controls. A failed cycle contributes no byte and does not
   mutate decoder state. No tokenizer, vocabulary lookup, embedding, or
   output feedback is allowed.
2. **Delayed association.** Present two or more distinct modality streams with
   profile-frozen positive, zero, and negative tick offsets. The field must
   acquire the correct delay through ordinary residual-return work and improve
   a held-out successor after neutral washout. Shuffled, mispaired,
   phase-reversed, equal-energy, and wrong-delay arms retain identical work
   budgets. No instantaneous resemblance is accepted.
3. **Sequence composition.** Compose byte/control events and delayed modality
   events into fixed sequences using the same codec and field clock. Hold out
   whole episodes containing unseen orderings, lengths, compositions, and
   chunk partitions; do not split a prefix across training and validation.
   Measure next-event and partial-cue return at multiple delays. Composition
   is a trajectory property of the one field, not a learned n-gram table or
   semantic key.
4. **Grounded episodes.** Run complete deterministic world episodes with
   optical/audio/proprioceptive packets, body transforms, action geometry,
   terminal acknowledgements, and successor observations. Apply the action and
   output no-peek rules: the field sees only the current committed payload and
   fixed geometry before commit, and only a later world observation after
   commit. Evaluate prediction, grounded text, action, and applied-effect
   paths against modality-alone, lagged, mirrored, transfer-permuted,
   source-suppressed, fading-retention, and reciprocal-link-off controls.

   Failure-handling is a separate declared fixture, not host metadata: use
   matched applied, rejected, expired, and `action_scope=null` hold outcomes
   from the same predecessor, proposal scope, geometry, clock, and work classes.
   The terminal outcome is admitted as the ordinary field packet defined in
   Part 5; only the applied arm has self-predicted efference/body remap. A
   field failure-handling claim must improve its status-conditioned
   held-out next-valid-action or prediction by the positive
   work-normalized interval in Part 5 over status-blind and hold controls.
   Unresolved timeout rows advance no world and cannot enter this fixture.
5. **Interference, saturation, overwrite, and recovery.** Expose family A,
   family B, then A again with equal-work episodes and a neutral washout. Use
   below-barrier and above-barrier drives, partial cues, multiple delays, and
   exact checkpoint/restart. Record analog basin capacity, saturation onset,
   overwrite path, topological-retention sector transition, residence, analog-after-topological recovery,
   and work-normalized behavior. A failed bound rejects the candidate and
   leaves its predecessor; it never silently replaces A with an auxiliary
   memory.

### Optional field-selected practice requests (post-cutover research only)

The mandatory curriculum above is not field-selected. A separate
**field-selected practice-request path** may be studied only as a
post-cutover experiment, never as a prerequisite for W10E/G10E, behavioral
retention, or release readiness. Before that experiment begins, a distinct
content-addressed plan freezes a finite registry of practice descriptors,
candidate work/delay/horizon intervals, request rate and expiry, whole-episode
splits, external scheduler identity, nulls, controls, and stopping rule. The
mandatory `QiFieldExperiencePlan` and its externally scheduled sequence
remain the release path.

The transient request is fully specified as:

```text
QiPracticeRequest (receipt-only; never field state)
  request_sha256
  predecessor_state_sha256
  experiment_plan_sha256
  candidate_descriptor_set_sha256
  selected_descriptor_sha256
  requested_work_class
  delay_window
  horizon
  issued_tick
  expiry_tick
  external_scheduler_sha256
  no_peek_inputs_sha256
  field_only_intervention_sha256
  decision_interval
```

The external response is one of the frozen terminal classes
`honored | refused | expired | invalid`; `honored` carries the exact
pre-registered stream/episode identity and no other payload. The request
hash, response, and scheduler decision are evidence links only and are
discarded from the live field path after their receipt commits.

At one declared logical tick, the field may evaluate those registered
descriptors from the current committed field, current admitted packets, and
fixed geometry using a bounded scratch trajectory and a no-peek
uncertainty/margin rule. It may emit one transient practice request naming
only a pre-registered descriptor, required work class, delay window, and
expiry tick. The request has no target payload, expected answer, world
consequence, or hidden score. The external scheduler alone decides whether
to honor it and, if so, supplies the already frozen byte/world stream through
ordinary boundary packets. A refusal, delay, or different externally supplied
stream is an explicit outcome; it cannot be converted into a field-selected
reward.

The request, candidate scratch state, descriptor ordering, and decision
margin are discarded after the request/receipt boundary. No request queue,
visited set, practice counter, credit assignment, learned curriculum,
replay, optimizer, teacher state, or persistent policy may be added to
`QiFieldState` or a checkpoint. A request may not inspect validation/test
outcomes, change profile laws or budgets, reopen an old episode, or cause the
field to sense a stream outside the separately frozen experiment plan.
Exact restart replays the same predecessor and request bytes; it does not
replay a request merely because a similar field state appears.

The experiment must compare no-request, externally shuffled schedule,
field-frozen/zero-field, phase/current-scrambled, wrong-descriptor,
equal-work, and scheduler-refusal controls. It may claim field-conditioned
practice selection only when a request changes the externally executed
descriptor under a positive uncertainty-cleared margin and the resulting
held-out trajectory improves after washout; a request without that causal
success is diagnostic evidence only. This optional path cannot alter the
mandatory stage order, supply a hidden experience source, or be cited as a
release dependency. Larger field-selected-practice, body-adaptation,
lesion, composition, rest, and scaling campaigns use the same post-cutover
research status.

### Splits, washout, stopping, and checkpoint selection

The plan creates disjoint train, validation, and test sets by **whole
episode**, before any exposure. A byte range, control event, world episode,
action geometry, or delayed pairing used in one split cannot be reused as a
prefix, suffix, permutation, or replay in another split. The split digest,
episode IDs, rendering/timing/position holdouts, and all control assignments
are frozen in `whole_episode_split_sha256`. Validation and test episodes are
not admitted to the live field before their evaluation phase.

Each stage has a fixed source-free or neutral washout schedule in rational
field ticks. Washout injects no source packet, residual, cue, teacher signal,
or transcript; its only evolution is the declared field law. Delays are
measured from the last admitted source frontier, not host time. A checkpoint
restart occurs at the frozen pre-washout and post-exposure boundaries and must
reproduce the same field/step/receipt chain.

All learning curves are work-normalized. The primary quantities include

\[
\Delta_{\mathrm{pred}}/
 W_{\mathrm{adm}},\qquad
\Delta_{\mathrm{pred}}/
 (W_{\mathrm{adm}}+W_{\mathrm{residual}}),\qquad
\Delta_{\mathrm{emit}}/W_{\mathrm{adm}},\qquad
\Delta_{\mathrm{action}}/
 (W_{\mathrm{adm}}+W_{\mathrm{residual}}),
\]

along with the admitted/reflected/absorbed work partition, analog response
rank/conditioning,
retention half-life, sector residence, saturation work, overwrite work,
recovery work, and held-out whole-episode transfer. A zero-work denominator,
ambiguous interval, or absent successor is an explicit invalid/abstain result,
not a zero improvement.

`stopping_rule` freezes a maximum number of exposure passes, a minimum
accepted washout/recall schedule, and a training-only plateau predicate over
complete episode boundaries. A run stops only at a declared boundary after
the predicate is met or the maximum pass count is reached. The predicate
cannot inspect validation/test scores, select a profile, alter work budgets,
or continue after an unresolved rejection. Failure to meet the rule by the
maximum is `FAIL`, not an invitation to tune a hidden coefficient.

`checkpoint_selection_rule` always retains the initial checkpoint, every
accepted stage boundary, pre/post-washout checkpoints, and the final accepted
pass. If one representative is required, it is selected by the frozen
training-only work-normalized criterion, then earliest pass, then canonical
digest; validation/test data cannot choose it. Each checkpoint contains only
the content-addressed field state and bounded step/packet/plan identities.
It contains no raw payload, expected answer, prediction tensor, gaze/action
queue, decoder cache, teacher/model state, or derived topology/basin table.

### Experience controls and endpoint

The required controls are equal-total-work one-shot exposure, shuffled order,
mispaired or delayed residual, energy-matched phase scramble, fading retention,
scale-link-off, separately hashed diagnostic `slow-to-fast-return-off`,
matched-EMA/different-flow, wrong cue, field frozen, zero field,
matched-energy/opposite-current state, and checkpoint/restart. The
return-off surgery zeros only the target-to-source member of one registered
reciprocal link, records its nonreciprocal energy residual, and is forbidden
from production or conservation claims.

W10E/G10E passes only when repeated ordinary experience yields a receipted
within-sector analog improvement and, where claimed, a distinct topological-retention
consolidation path; both beat equal-work controls after washout on a
whole-episode held-out prediction, emission, or action, survive exact restart,
and expose saturation/overwrite/recovery measurements. Trace or recall without
selective acquisition is a failed endpoint. The runtime may not add a learned
lookup, optimizer, embedding, teacher/model state, external memory, or
fading-retention fallback.

Output is one-way. A committed text symbol, control event, or provider
fragment is never reintroduced through inbound `A_text` or any other sensory
port, and no output bytes are available to candidate evaluation. Teacher,
evaluator, language-model, Qwen/llama.cpp, KV, sampler, and policy state stay
outside the live field path; a post-commit evaluator may score immutable
artifacts but cannot mutate or steer the field.

### Post-cutover rest/consolidation and factorized composition experiments

**Source-free rest/consolidation** is an optional post-cutover experiment, not
an additional mandatory curriculum stage or a release blocker. After an
accepted externally scheduled episode, the experiment closes every source,
cue, residual, and teacher channel and evolves the one field under its
declared intrinsic law for a finite rational rest horizon. It compares the
pre-rest and post-rest slow-to-fast return, within-sector response, sector
residence, and held-out successor under work-normalized intervals. The rest
arm may report consolidation only when a causal successor measure improves
without new incident work; unchanged trace, checkpoint persistence, or a
sector label is not consolidation. Source-injected matched-work, field-frozen,
link-off, phase-scrambled, and explicit-reset controls are separate and cannot
be used to turn ordinary washout into a positive result.

**Factorized composition** is likewise a post-cutover experiment. A frozen
plan registers finite factor streams \(A_1,\ldots,A_m\), their ordinary
boundary descriptors and delays, and whole held-out episodes containing
previously unseen factor orderings and combinations. The field experiences
the factors and composed episodes only through the existing packet/field-law
path; it may claim factorized trajectory composition only when each factor's
partial cue and the composed held-out successor close causally after washout.

For every claimed factor/episode pair, let
\(\Delta_{\mathrm{comp}}^{-}\) be the directed lower interval for improvement
over the matched factor-alone and shuffled controls. It must clear the
work-normalized margin

\[
\frac{\Delta_{\mathrm{comp}}^{-}}
{W_{\mathrm{adm}}+W_{\mathrm{residual}}}
\geq
\max(\Delta_{\mathrm{abs}},\Delta_{\mathrm{rel}})>0,
\qquad
0<W_{\mathrm{adm}}+W_{\mathrm{residual}}<\infty .
\]

The claim is limited to the finite declared horizons, factor count, episode
lengths, orderings, and held-out combinations in that post-cutover plan; it
does not imply untested length extrapolation or an unbounded compositional
capacity.
Shuffled-factor, missing-factor, phase/current-scrambled, equal-work
one-shot, and nonfactorized-order controls are required. No factor table,
composition key, learned n-gram, external replay, or second persistent field
may be introduced.

Both experiments retain only bounded receipt/artifact evidence and their exact
field/checkpoint hashes. They do not modify `QiFieldExperiencePlan`, its
mandatory externally scheduled path, stopping rule, or release endpoint, and
cannot satisfy or waive W10E/G10E, W10A, G6B, G15A, or G15B. A failure,
unresolved interval, or absent successor leaves the mandatory result
unchanged and is reported as research failure rather than a reason to add
hidden state or relax the release gates.
