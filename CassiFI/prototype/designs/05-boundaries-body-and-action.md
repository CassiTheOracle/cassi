# Fixed boundaries, embodiment, attention, and action

> CassiFI implementation plan, Part 5. [Previous](./04-execution-contract.md) · [Index](../README.md) · [Next](./06-memory-and-learning.md)

## Fixed boundary and embodiment contracts

### Rational multirate causal clock

Logical time is exact profile data, not host-clock inference. The run epoch is
`t_0=0`. Every duration and timestamp is a reduced rational multiple of the
profile's positive base unit `tau_0`:

\[
t=\frac nd\tau_0,
\qquad n\geq0,\quad d>0,\quad\gcd(n,d)=1.
\]

The field interval is `h_f=(p_f/q_f)tau_0` with integers
`p_f>=1,q_f>=1`; the world interval is `h_w=m h_f` for the positive integer
`m=field_steps_per_world_tick`; and each source descriptor `r` fixes
`h_r=(p_r/q_r)tau_0` with integers `p_r>=1,q_r>=1` plus its phase relative to
the run epoch. Every fraction is reduced, and every nonpositive or zero
duration rejects before the LCM or tick counts are derived. Let

\[
L=\operatorname{lcm}\!\left(q_f,\{q_r\}_{r\in\mathcal R}\right),
\qquad
\delta t=\frac{\tau_0}{L}.
\]

The profile rejects `L>max_clock_lcm`. Otherwise it derives, without floating
rounding,

\[
\texttt{ticks_per_field_step}=p_f\frac L{q_f},
\quad
\texttt{ticks_per_world_tick}
=m\,\texttt{ticks_per_field_step},
\quad
\texttt{ticks_per_source_interval}[r]=p_r\frac L{q_r}.
\]

`cassi.qi-flow-clock-time.v1` stores `{n,d}` in lowest terms.
`cassi.qi-flow-clock.v1` stores `tau_0`, the epoch, all reduced rates/phases,
`L`, the derived integer tick counts, and the exact interval partition. The
schedule hash and every replay receipt include those bytes. A world logical
tick is the integer world-interval index; a packet additionally carries
`logical_time={n,d}` and half-open `capture_start/end={n,d}`. No field,
source, or world timestamp is inferred from a binary float.

Capture and exposure intervals are half-open `[start,end)`. Admission order is
exact interval end, interval start, registered descriptor priority, source
epoch/stream, source sequence, then packet digest. For each
`(source_epoch,source_stream_id,descriptor_sha256)` scope, sequence begins at
the profile-declared first value and must be contiguous. Each expected source
interval contributes exactly one canonical data frame or one registered
`no_sample` frame carrying the reason and interval identity. A missing interval
does not become zeros and cannot advance its frontier; the cycle waits within
its bounded deadline and then fails visibly.

The watermark stores, per source scope, the greatest contiguous
`(capture_end,source_sequence,frame_sha256)` frontier and hashes the sorted
complete map. Commit A advances only frontiers whose exact frames are indexed
in that envelope. Restart resumes from those frontiers; duplicate replay must
be byte-identical, and a sequence gap, conflicting duplicate, future interval,
or frame beyond the requested cycle frontier fails closed. Changing a source
epoch or stream registry changes `source_identity_sha256` and requires a new
session; it cannot silently rebind an existing trajectory.

Host monotonic, adapter, and wall timestamps are telemetry only and never enter
evolution, freshness, or cross-process tie-breaking. Downsampling is legal
only through the descriptor's immutable `QiAntialiasProfile`: coefficients,
phase, support, boundary convention, passband/stopband tolerance, response
hash, and adjoint are operator identity. Every resampled packet carries an
independently recomputable `cassi.qi-flow-antialias-receipt.v1`; undeclared
sample dropping, averaging, interpolation, or nearest-tick rounding fails
closed.

### Common packet identity

Every ingress and egress event is a strict immutable object. Unknown fields,
nonfinite values, oversize payloads, wrong descriptor/profile identities,
future capture windows, duplicate sequence numbers, and mismatched hashes are
rejected before the field advances.

The common event header is:

```text
schema
run_id
episode_id
world_id
session_id
profile_sha256
clock_sha256
descriptor_sha256
event_id
request_id
logical_tick
logical_time = {n,d}
capture_start = {n,d}
capture_end = {n,d}
source_epoch
source_stream_id
source_sequence
source_timestamp_ns_telemetry
arrival_sequence_telemetry
watermark_sha256
ingress_journal_sha256
antialias_receipt_sha256 | null
causal_parent_event_id
causal_parent_action_id
body_frame_id
payload_shape
payload_dtype
payload_sha256
valid
```

`cassi.qi-flow-no-sample.v1` uses the same scope, exact interval, sequence,
descriptor, clock, and journal fields, fixes `payload_shape=[0]`,
`payload_dtype="none"`, and the empty-payload digest, and adds one registered
reason code. It advances the source frontier but injects no field work. A
malformed or merely absent data frame cannot be recast as this object.

Admission uses the rational capture interval and immutable source identity
above. For an external source, telemetry timestamps and arrival order have no
causal authority. A late/future packet never becomes on-time through arrival
order.

Ingress is consume-after-commit, never dequeue-before-commit. Before any field
mutation, the runtime either appends the exact canonical frame bytes to a
durable content-addressed `QiIngressJournal` or proves an equivalent replayable
source range under `QiSourceReplayContract`. The candidate transaction records
the journal head, inclusive admitted-frame digest set, committed cursor, and
watermark. Commit A atomically publishes those identities with the successor
field, proposal/reaction, response record, and optional tick outbox. Only after
Commit A reopens and verifies may the source receive an acknowledgement or
reclaim the range. A crash before Commit A replays the same frames; a crash
after Commit A resumes strictly after the committed cursor and cannot evolve
them twice. Overflow, corruption, or a replay source that cannot honor the
declared retention horizon blocks admission visibly.

Packets are discarded from the live queue after that acknowledgement.
Checkpoints contain packet hashes/scalars and bounded journal cursors, never raw
camera/audio/proprio arrays, predictions, residual tensors, gaze history, or
action queues. Journal payloads are protocol evidence outside `QiFieldState`,
bounded by byte/time retention and access-control policy, and never read as
adaptive memory.

`QiBoundaryPacket` contains a read-only detached payload at ingress. Each
descriptor owns two directionally named, immutable maps over declared metrics:

\[
A_r:H_r\rightarrow H_{\mathrm{field}}
\quad\text{(sensor injection)},\qquad
B_r:H_{\mathrm{field}}\rightarrow H_r
\quad\text{(boundary observation/prediction)}.
\]

The production descriptor requires
`A_r=g_r B_r^\dagger`, where the nonnegative source gain `g_r` is immutable,
and proves

\[
\langle B_rX,y\rangle_{W_r}
=
\langle X,B_r^\dagger y\rangle_{G_{\mathrm{field}}}.
\]

Its forward ingress transform applies `A_r` to produce one transient drive:

```text
boundary_id
direction
field_coordinate = D | C | both
scale
active_site_mask
start_tick
end_tick
complex_wave
admitted_source_work_budget
causal identities
```

The runtime, not the caller, derives `admitted_source_work_budget` from the
descriptor/profile and the validated payload norm. If a packet carries a
requested budget class, it must exactly equal the descriptor class or the
packet is rejected before allocation. Prediction uses `B_r`; residual return
uses the same proven `B_r^\dagger` through the canonical velocity-force path.
The hashes distinguish `A_r`, `B_r`, both metrics, and `g_r`; no prose use of
“forward” or “adjoint” may reverse their domains.

### Passive field-owned sensory permeability

**QI-BOUND-001**, implemented and gated by **W7P/G7P**, is the
`QiBoundaryPermeabilityProfile` contract
(`cassi.qi-flow-boundary-permeability-profile.v1`). Every characteristic
sensory port (optical, audio, proprioceptive, and text ingress, and every
explicitly registered scale port) declares one immutable passive permeability
profile. The profile names the port and scale, characteristic basis and
metric, fixed state observable, permeability operator, gate coefficients,
incident-work units, quadrature/refinement identity, and lower/upper bounds for
the gate and for each power fraction. It is a property of the field boundary,
not a caller gain or a policy decision. A packet can request only a profile
class already selected by the run; it cannot select a gate value.

Let \(\mathcal O_r\) be the fixed metric-compatible observable from the active
field subspace into the characteristic port and let \(q_r\) be its normalized
profile vector. For the current committed field, or for the current candidate
at an accepted quadrature sample, define the dimensionless state signal

\[
u_r(X)=
\frac{\operatorname{Re}\langle q_r,\mathcal O_rX\rangle_{W_r}}
{s_{r,\mathrm{ref}}+\|\mathcal O_rX\|_{W_r}},
\qquad
s_{r,\mathrm{ref}}>0.
\]

The descriptor proves \(\|q_r\|_{W_r}=1\), so
\(-1\leq u_r(X)\leq1\) without a clipping or saturation operator. The
transient field-owned gate is

\[
\begin{aligned}
\kappa_r(X)
&=\kappa_{r,\min}
 +(\kappa_{r,\max}-\kappa_{r,\min})
 \frac{1+\tanh(b_r+\ell_ru_r(X))}{2},\\
0&\leq\kappa_{r,\min}\leq\kappa_{r,\max}\leq1 .
\end{aligned}
\]

The bias \(b_r\), slope \(\ell_r\), \(s_{r,\mathrm{ref}}\), and the gate
observable are fixed profile values with units and provenance. They are not
learned coefficients. The gate is recomputed from the scratch successor at
each declared positive-duration subinterval and is discarded after the
boundary event; no gate history, accumulator, or gate-selected key is
written to `QiFieldState`. A state outside the profile's certified observable
domain rejects before the gate is evaluated. A gate interval that cannot be
enclosed inside its declared \([\kappa_{r,\min},\kappa_{r,\max}]\) also
rejects; the runtime never clips it into range.

The profile maps this gate to three power fractions, with no independent
runtime tuning:

\[
\begin{aligned}
\eta_{r,\mathrm{trans}}(\kappa)
&=\eta_{r,\mathrm{trans},\min}
 +(\eta_{r,\mathrm{trans},\max}
   -\eta_{r,\mathrm{trans},\min})\kappa,\\
\eta_{r,\mathrm{abs}}(\kappa)
&=\eta_{r,\mathrm{abs},\min}
 +(\eta_{r,\mathrm{abs},\max}
   -\eta_{r,\mathrm{abs},\min})\kappa,\\
\eta_{r,\mathrm{ref}}(\kappa)
&=1-\eta_{r,\mathrm{trans}}(\kappa)
   -\eta_{r,\mathrm{abs}}(\kappa).
\end{aligned}
\]

Profile loading requires

\[
0\leq\eta_{r,j,\min}\leq\eta_{r,j,\max}\leq1
\quad(j\in\{\mathrm{trans},\mathrm{abs}\}),
\qquad
\eta_{r,\mathrm{trans},\max}
 +\eta_{r,\mathrm{abs},\max}\leq1,
\]

and derives and verifies finite nonnegative lower/upper bounds for
\(\eta_{r,\mathrm{ref}}\). For each registered scale \(s\), the admitted
permeability is \(\Pi_{r,s}:=\eta_{r,\mathrm{trans}}(\kappa_r)\), with
\(0\leq\Pi_{r,s}\leq1\); the scale identity is part of the profile and an
admitted interval cannot be copied from another scale. The profile also fixes
positive and maximum admitted source-work budgets and a nonnegative numerical
enclosure \(U_{\mathrm{scatter},r}\). A profile with a negative fraction, a
fraction above one, a zero/negative metric, an unbounded observable, an
unbounded source-work interval, or an undeclared phase/orientation is invalid
before any field allocation.

An undeclared candidate-dependent operator, negative admitted/reflected/
absorbed work, unbounded remainder, descriptor/scale mismatch, or missing
recomputation is `PERMEABILITY_NONPASSIVE` and rejects the packet before field
mutation. State dependence through the explicitly declared current-field
observable is the production behavior, not an exemption from the profile.

For an incident characteristic amplitude \(a_r^{\mathrm{inc}}\), normalized
under the declared port metric, the fixed scattering map uses

\[
\begin{aligned}
P_r^{\mathrm{inc}}(t)
 &=\frac{w_r}{2}|a_r^{\mathrm{inc}}(t)|^2,\\
P_r^{\mathrm{ref}}(t)
 &=\eta_{r,\mathrm{ref}}(\kappa_r(X(t)))P_r^{\mathrm{inc}}(t),\\
P_r^{\mathrm{trans}}(t)
 &=\eta_{r,\mathrm{trans}}(\kappa_r(X(t)))P_r^{\mathrm{inc}}(t),\\
P_r^{\mathrm{abs}}(t)
 &=\eta_{r,\mathrm{abs}}(\kappa_r(X(t)))P_r^{\mathrm{inc}}(t).
\end{aligned}
\]

The reflected and transmitted amplitudes use the profile's fixed phases,
\[
a_r^{\mathrm{ref}}
 =e^{i\varphi_{r,\mathrm{ref}}}
  \sqrt{\eta_{r,\mathrm{ref}}}\,a_r^{\mathrm{inc}},
\qquad
a_r^{\mathrm{trans}}
 =e^{i\varphi_{r,\mathrm{trans}}}
  \sqrt{\eta_{r,\mathrm{trans}}}\,a_r^{\mathrm{inc}},
\]
and the absorbed fraction is a declared passive sink, never an unreported
field source. The ingress field drive is synthesized only from
\(a_r^{\mathrm{trans}}\), then passed through the already validated \(A_r\)
and its ordinary source-work row. Reflected work never enters that drive.
Any field-side incident characteristic wave is accounted for by the same
map in the reverse orientation; it is not silently folded into the sensor
packet.
The executable admission order is fixed:

1. validate the packet, source watermark, characteristic basis, and incident
   amplitude against the descriptor and clock;
2. derive the transient gate and all power-fraction intervals from the current
   candidate, rejecting an out-of-domain or unresolved state;
3. synthesize only the transmitted amplitude and integrate incident,
   reflected, transmitted, and absorbed work over the declared subintervals;
4. apply the transmitted drive through \(A_r\), run the ordinary complete
   field/port Hamiltonian preflight, and compare the source-work and scattering
   closures; and
5. commit the packet, successor, `QiScatteringReceipt`, and ledger atomically,
   or leave both field and source cursor unchanged.

No step can observe a future packet or external consequence, and no
post-commit correction can retroactively change the gate or its work rows.


Directed interval quadrature records

\[
\begin{aligned}
W_r^{\mathrm{inc}}
&=\int P_r^{\mathrm{inc}}(t)\,dt, &
W_r^{\mathrm{ref}}
&=\int P_r^{\mathrm{ref}}(t)\,dt,\\
W_r^{\mathrm{adm}}
&:=W_r^{\mathrm{trans}}
 =\int P_r^{\mathrm{trans}}(t)\,dt, &
W_r^{\mathrm{abs}}
&=\int P_r^{\mathrm{abs}}(t)\,dt .
\end{aligned}
\]

The intervals include every gate enclosure, zero-clock split, quadrature
roundoff, and refinement bound. They must satisfy

\[
W_r^{\mathrm{inc}}
 -W_r^{\mathrm{ref}}
 -W_r^{\mathrm{adm}}
 -W_r^{\mathrm{abs}}
\in[-U_{\mathrm{scatter},r},U_{\mathrm{scatter},r}],
\]

and \(W_r^{\mathrm{adm}}\) is the only sensory work admitted to the field; it
appears once in the boundary source-work row. Incident, reflected, and
absorbed work remain receipt channels and are not charged again to the field
Hamiltonian.
For every declared packet class the profile also fixes
\[
W_{r,\min}^{\mathrm{adm}}\leq W_r^{\mathrm{adm}}
\leq W_{r,\max}^{\mathrm{adm}},
\qquad
W_{r,\min}^{\mathrm{ref}}\leq W_r^{\mathrm{ref}}
\leq W_{r,\max}^{\mathrm{ref}},
\]
with nonnegative finite endpoints and the source-budget upper bound. These
are interval predicates, not a request to clip a packet or force a minimum
sample. A packet whose admitted/reflected/absorbed intervals cannot meet their
declared class bounds is rejected before allocation. The receipt exposes
\(W_r^{\mathrm{adm}}\), \(W_r^{\mathrm{ref}}\), and
\(W_r^{\mathrm{abs}}\), even when one is zero. The
complete field Hamiltonian and source ledger remain authoritative for the
effect of admitted work; a permeability receipt cannot turn a failed
full-energy preflight into an accepted event.

`QiScatteringReceipt` is the **QI-PORT-001** evidence object, required by
**W6T/G6T** (`cassi.qi-flow-scattering-receipt.v1`). For every external and
registered scale characteristic port it records the exact incoming trajectory
digest, orientation, nonnegative `W_incident`, `W_reflected`, `W_transmitted`
(`W_adm` for sensory ingress), and `W_absorbed` interval rows; gate samples
and bounds; phases; metric/operator/profile hashes; segment grid; state
predecessor/successor; full-Hamiltonian and source-ledger references; and the
closure residual/bound plus independent replay identity. External-to-field and
scale-to-scale directions are separate rows, so a scale link cannot be
mistaken for sensory admission. Signed characteristic-port reaction remains in
the field ledger rather than in a negative work channel.
The receipt is content-addressed evidence, not adaptive state. Its mandatory
balance is
\[
W_r^{\mathrm{inc}}
=W_r^{\mathrm{ref}}+W_r^{\mathrm{trans}}
+W_r^{\mathrm{abs}}+R_{\mathrm{scatter},r},
\qquad
|R_{\mathrm{scatter},r}|\leq U_{\mathrm{scatter},r}.
\]
For the permeability-only summary,
\(R_{\mathrm{permeability},r}:=
W_r^{\mathrm{abs}}+R_{\mathrm{scatter},r}\), so the equivalent profile row is
\(W_r^{\mathrm{inc}}=W_r^{\mathrm{adm}}+
W_r^{\mathrm{ref}}+R_{\mathrm{permeability},r}\). The expanded receipt keeps
transmitted/admitted and absorbed channels separate and never hides either in
the remainder.
An omitted subinterval/channel, negative work magnitude, nonfinite power, an
interval crossing a declared bound, a scale/port mismatch, or a closure
residual outside the profile envelope fails
`SCATTERING_RECEIPT_INVALID` and rejects the entire event before cursor or
field mutation.

The causal controls are part of **G7P** and cannot be replaced by a single
open-port comparison:

1. `state-gate-live` recomputes \(\kappa_r\) on every accepted sample;
   `state-gate-frozen` evaluates it once from the predecessor while holding
   packet bytes, source work, clock, and all operators fixed. Their admitted
   and reflected work differences must equal the registered state-gate
   counterfactual.
2. `gate-off` and `gate-open` are separately hashed diagnostic profiles with
   matched incident work. They establish the zero and maximum controls only;
   neither can replace the production state-derived gate.
3. Matched-energy phase reversal, sign reversal, packet-order permutation,
   and field-state permutation controls must produce the profile-predicted
   phase/work transforms, not an unexplained change in the packet or a
   hidden label.
4. An exact reversal of port orientation swaps incident/reflected direction
   labels and flips signed work under the common passive-egress rule. A
   differently phased or differently gated port is a new descriptor, not an
   informal control.

No control may call the world, inspect a future observation, read an action
consequence, or persist an auxiliary gate. A valid treatment changes only
through the declared current field, fixed geometry, packet, and profile
operators; invalid controls leave the predecessor and source cursor untouched.

### Incident-work-normalized sensory openness, recovery, and anti-self-sealing

The passive profile also has a mandatory incident-work-normalized
openness/recovery fixture. **QI-BOUND-001** emits the content-addressed
evidence object `cassi.qi-flow-sensory-openness.v1`; this is evidence for the
field-capacity audit owned by **QI-CAP-001** (Part 2), not a second adaptive
object or a replacement for `QiScatteringReceipt`. For every mandatory
production port/scale pair \((r,s)\), the fixture uses the exact incident and
admitted work intervals from the scattering receipt:

\[
\mathsf O_{r,s}^{-}
:=\frac{W_{r,s,\mathrm{adm}}^{-}}{W_{r,s,\mathrm{inc}}^{+}},
\qquad
\mathsf O_{r,s}^{+}
:=\frac{W_{r,s,\mathrm{adm}}^{+}}{W_{r,s,\mathrm{inc}}^{-}},
\qquad
0<W_{r,s,\mathrm{inc}}^{-}\leq W_{r,s,\mathrm{inc}}^{+}<\infty .
\]

An unresolved, zero, or nonpositive incident-work denominator invalidates the
fixture; raw amplitude, packet count, or host time cannot normalize openness.
The profile declares finite \(\mathsf O_{\min,r,s}>0\),
\(\mathsf R_{\min,r,s}>0\), a recovery horizon, and recovery-work interval
for the fixture, together with the admissible uncertainty margin. A
registered post-perturbation probe has

\[
\mathsf R_{r,s}^{-}
:=
\frac{\mathsf O_{r,s,\mathrm{post}}^{-}}
{\max(\mathsf O_{r,s,\mathrm{pre}}^{+},\mathsf O_{r,s,\mathrm{ref}})},
\qquad
\mathsf O_{r,s,\mathrm{ref}}>0,
\]

with all ratios interval-certified and all incident work charged through the
same passive scattering map. Recovery passes only when
\(\mathsf O_{r,s,\mathrm{post}}^{-}\geq\mathsf O_{\min,r,s}\) and
\(\mathsf R_{r,s}^{-}\geq\mathsf R_{\min,r,s}\), the declared finite
source-free/neutral interval has elapsed, and a downstream boundary or
registered scale return improves by the declared amount per unit incident
work. A port that was selectively quiet for one state may therefore recover
under a different current-field state; the fixture does not replace the
state-derived \(\kappa_r(X)\) or force a global open-port minimum.

The anti-self-sealing obligation is stronger than a one-time nonzero response.
For each mandatory port, a finite registered sequence of positive incident
probes, neutral/source-free intervals, and ordinary successor observations
must contain a recovery interval satisfying the above lower bounds. Repeated
zero admitted work, absent successor return, or persistent
\(\mathsf O_{r,s}^{+}<\mathsf O_{\min,r,s}\) under finite incident work is
`BOUNDARY_SELF_SEALED`: blindness cannot masquerade as attention, useful
selective gating, or a successful selective gate. The runtime fails the
affected boundary/profile rather than silently lowering the denominator,
retrying forever, opening a caller-chosen port, or treating an unobservable
state as evidence of attention.
Selective field-owned permeability remains valid only as a finite, current-field
dependent routing choice with this recovery/escape obligation.

The receipt records the complete pre/post state and profile hashes, port/scale
identity, incident/admitted/reflected/absorbed work intervals, openness and
recovery intervals, source-free horizon, downstream-return hashes, fixture
thresholds, and matched controls. Required controls include a
state-gate-frozen arm, matched-energy phase/current reversal, field-frozen
arm, gate-off diagnostic, shuffled probe order, and a finite repeated-probe
anti-self-sealing arm. No control may call a future world observation or
persist a gate, probe counter, recovery score, or port address in
`QiFieldState`; every gate remains the transient field-derived quantity
already defined above.

### Optical boundary

`QiOpticalBoundaryDescriptor` declares calibrated range, sensor and retinal
shape, camera intrinsics/extrinsics, exposure, body frame, resample kernel, DFT
normalization, active sheet, saturation policy, and adjoint.

The canonical transform is label-free:

1. validate raw photometric/event values, calibration identity, exposure, and
   physical range;
2. apply one fixed calibrated luminance/channel map;
3. apply the fixed crop/resample from sensor coordinates into the declared
   retinal physical sheet;
4. map absolute calibrated luminance to the declared carrier source and
   temporal/event contrast to the declared differential source with a fixed
   complex phase orientation;
5. scatter that physical sheet directly into the profile's row-major active
   sites and zero every unused port site;
6. integrate the resulting `C/D` drive as timed source work over the exposure
   window.

The optical boundary does not store Fourier coefficients in physical state
slots. FFTs remain transient controller operators for derivatives, remaps, and
diagnostics. Its sensor injection is `A_optical`; prediction is
`B_optical`; `A_optical=g_optical B_optical^\dagger` is verified under the
declared sensor/field metrics.

There is no frame-wise RMS/mean whitening, hidden contrast normalization,
page/glyph/word label, candidate-specific crop before gaze commit, or template
signature. Saturation and lost photometric work are explicit ledger fields.

The existing `_diag/cassi-qi-native/page_field_probe.py` and
`active_gaze_probe.py` remain legacy negative evidence. The former recognizes
with static cosine; the latter precomputes every unseen candidate foveal wave
and carries an external `remaining` set. Neither is migrated into the live
boundary or cited as active-perception evidence.

### Audio boundary

`QiAudioBoundaryDescriptor` declares:

- channel count and channel order;
- sample rate, fixed window length, hop, timestamp convention, and amplitude
  calibration;
- one invertible fixed time/frequency coordinate transform;
- latency, group-delay, phase, saturation, and reconstruction tolerances;
- field sheet and source split.

For a mono profile whose audio-port width is the integer `W>=2`, one valid
fixed real transform is `rfft` over `N=2*(W-1)>=2` samples with
`norm="ortho"`, retaining exactly `W` complex bins. Any profile with `W<2`
rejects before allocating or constructing the transform. A fixed bijection
then scatters those bins into the
descriptor's declared tonotopic physical-port mask; those coordinates are not
misreported as external visual positions. The inverse gathers the same mask
and applies the matching `irfft`; the receipt includes transform and
round-trip error. A noninvertible window, overlapping undeclared port, or
silent channel average is forbidden. Stereo or a different sample rate is a
new descriptor/profile, never an implicit conversion.

Only windows whose exact rational `capture_end` is at or before the requested
cycle frontier, and strictly after the committed source watermark, are visible.
Future or already consumed audio samples cannot participate in the current
action. Cross-modal delay is part of the profile and is tested with
positive/negative lag controls.

### Proprioceptive boundary

`QiProprioceptiveBoundaryDescriptor` contains one ordered set of channel names,
units, calibrated ranges, body-frame meanings, and a fixed injective linear
complex basis. Every encoded channel must have
`x_j^max>x_j^min`; a physically fixed channel is omitted rather than assigned
a zero-width pseudo-range. The descriptor covers the declared head pose, gaze,
camera pose, joint positions/velocities, actuator positions, contact, and
inertial channels. Each scalar is first rejected unless it lies in its
calibrated closed range, then mapped without clipping:

\[
z_j=2\left(\frac{x_j-x_j^{\min}}
{x_j^{\max}-x_j^{\min}}\right)-1.
\]

The profile fingerprints the basis, Gram matrix, adjoint/pseudoinverse, rank,
and reconstruction tolerance. A free-form feature dictionary, semantic pose
label, or learned body encoder is prohibited.

### Common passive-egress contract

Text, audio, and motor ports implement one `QiPassiveEgressContract`. A port
declares its outgoing current operator, reference/null calibration, integration
window, units, fixed boundary transducer, and metric-adjoint reaction map. The
descriptor partitions `[t_0,t_1)` at every zero-clock map and fixes each
continuous substage's rational sample grid. For every quadrature subinterval it
must independently reproduce interval enclosures for `o_r(t)` and
`P_r^out(t)` over the complete subinterval, not only at its endpoints. Directed
interval integration plus outward-rounded summation yields

\[
\mathcal A_r\in[\mathcal A_r^-,\mathcal A_r^+],
\qquad
W^{\mathrm{out}}_r
\in[W^{\mathrm{out},-}_r,W^{\mathrm{out},+}_r].
\]

Each receipt retains the exact grid, subinterval enclosures, quadrature values,
roundoff bounds, refinement identity, and final intervals. Every terminal
characteristic amplitude is also a complex interval disk propagated from the
same isolated successor. A port is ineligible if a subinterval enclosure is
missing/nonfinite, an interval crosses the required outwardness or terminal
guard, or refinement does not satisfy the frozen bound.

Before an event can commit, the controller applies its finite port reaction to
a scratch successor and evaluates the complete Hamiltonian, including
`U_composition`, `E_links`, and `U_topo`. It accepts only when the reaction is
finite, all state/topology/stability bounds hold, and the outward-rounded
reaction interval satisfies

\[
\left|
\left(H_{\mathrm{after}}-H_{\mathrm{before}}\right)
+W^{\mathrm{out}}_r
\right|
\leq\Delta^{\mathrm{reaction}}_r,
\qquad
H_{\mathrm{after}}\leq
H_{\mathrm{before}}+\Delta^{\mathrm{reaction}}_r .
\]

The accepted reaction, event bytes, successor hash, interval-bounded outgoing
work, null response, and uncertainty commit atomically. A failed preflight
emits no event and leaves the predecessor untouched; it cannot shrink the
event, clip the field, or silently skip reaction. Reversing the registered port
orientation performs the exact transform `o_r -> -o_r`: it swaps
ingress/egress labels and flips signed work. A differently phased probe is a
different descriptor, not an informal sign control.

### Text boundary

`QiTextBoundaryDescriptor` references the existing
`CassiFieldTextCodec`; it does not duplicate or expand the alphabet:

```text
0..255  exact byte events
256     user role
257     system role
258     assistant role
259     end turn
```

Direct terminal/provider input is a symbolic protocol port, not visual reading.
Each symbol becomes a timed inbound packet. Every emitted symbol is a timed
outbound boundary event selected from integrated outgoing flow; role/end
controls are committed events but add no output byte.

### Motor boundary

`QiActuatorBoundaryDescriptor` declares ordered channels, physical units,
range, zero, quantization, slew, latency, horizon, capability, and a fixed
characteristic port. It contains no learned motor head, sampler, optimizer, or
hidden controller. For channel `j`, it fixes an analysis vector `p_j`, positive
characteristic frequency `omega_{m,j}`, orientation `o_j in {-1,+1}`, read
phase `theta_j`, positive absorption/domain guards, and monotone physical-unit
map `T_j`. The channel probes are individually `W_0`-normalized and linearly
independent on their admitted sheet. With

\[
G_{ij}:=\langle p_i,p_j\rangle_{W_0},
\qquad
q_j:=\sum_k p_k(G^{-1})_{kj},
\qquad
\langle p_i,q_j\rangle_{W_0}=\delta_{ij},
\]

the profile rejects a non-positive-definite or over-condition-limit `G` rather
than using a pseudoinverse or approximate reaction. At every accepted sample,

\[
z_j=\langle p_j,D_0\rangle_{W_0},
\qquad
v_j=\langle p_j,V_{D,0}\rangle_{W_0},
\]

\[
a_j^{\mathrm{out}}
=\frac{v_j-i\,o_j\omega_{m,j}z_j}{\sqrt2},
\qquad
a_j^{\mathrm{in}}
=\frac{v_j+i\,o_j\omega_{m,j}z_j}{\sqrt2},
\]

\[
o_j(t)=\operatorname{Re}
\!\left(e^{-i\theta_j}a_j^{\mathrm{out}}(t)\right),
\qquad
P_j^{\mathrm{out}}(t)
=\frac{w_D\omega_{m,j}}2
\left(|a_j^{\mathrm{out}}|^2-|a_j^{\mathrm{in}}|^2\right).
\]

The descriptor's fixed rational, finite-map-partitioned window and
subinterval-enclosed quadrature produce intervals for
`\bar o_j=(t_1-t_0)^{-1}\int o_j(t)dt` and
`W_j^{out}=\int P_j^{out}(t)dt`. The candidate physical value
`c_j=T_j(\bar o_j)` is accepted only if the full transformed interval lies in
one quantization cell and clears range, slew, and terminal-positive-flow
guards; clipping or midpoint-only classification is forbidden.

Every candidate, including the eventual winner, must preflight its exact
simultaneous characteristic reaction from the same terminal sample. For every
channel whose requested value differs from the registered no-action value,
interval arithmetic evaluates

\[
\eta_{m,j}
:=\frac{2W_j^{\mathrm{out}}}
{w_D|a_j^{\mathrm{out}}(t_1^-)|^2},
\qquad
\sigma_{m,j}:=1-\sqrt{1-\eta_{m,j}}.
\]

The denominator interval must have lower endpoint above its terminal guard,
the work interval must be strictly outward, and the complete ratio interval
must lie in `[\eta_m,min,1]`. The deterministic midpoint value used by the
reaction must itself lie inside that certified interval. A no-action channel
has exact zero work and no reaction; it does not evaluate the quotient. This
fixed calculation, rather than a tuned runtime absorption coefficient, makes
the isolated terminal characteristic debit equal the canonical measured
`W_j^{out}` within its retained enclosure. Then

\[
(a_j^{\mathrm{out}})'=(1-\sigma_{m,j})a_j^{\mathrm{out}},
\qquad
(a_j^{\mathrm{in}})'=a_j^{\mathrm{in}}.
\]

\[
z_j'=\frac{(a_j^{\mathrm{in}})'-(a_j^{\mathrm{out}})'}
{\sqrt2\,i\,o_j\omega_{m,j}},
\qquad
v_j'=\frac{(a_j^{\mathrm{out}})'+(a_j^{\mathrm{in}})'}{\sqrt2},
\]

\[
D_0'=D_0+\sum_jq_j(z_j'-z_j),
\qquad
V_{D,0}'=V_{D,0}+\sum_jq_j(v_j'-v_j).
\]

The common passive-egress check recomputes the complete Hamiltonian,
topological-retention endpoint/topology, all state bounds, the characteristic/work residual,
and the exact successor hash. A candidate with an infeasible reaction has
`C_safety=+infinity` before score competition; it cannot win and fail only
after selection. The winning reaction is committed as
`cassi.qi-flow-motor-port-reaction.v1`, advances no logical time, and always
records `world_effect=false`. It proves only that the field paid for a
proposal. No reaction receipt, proposal, command send, `accepted`, or
`started` response establishes an external effect.

Candidate evaluation emits a transient `QiActionPrediction` with current
state/profile/operator hashes, horizon, predicted boundary deltas, score terms,
and uncertainty. It has no `proposal_id` and no side effect. A winning
`QiActionProposal` then names that prediction, the field successor/port
reaction, exact proposed values, and Commit-A predecessor/head. It is a
durable field decision, not yet a world command. A `QiActionCommand` is the
exact proposal-derived command nested by `QiWorldTickIntent`:

```text
cassi.qi-flow-action.v1
world_id
episode_id
action_id
idempotency_key
parent_step_id
proposal_id
logical_tick
effective_tick
command_timestamp_ns_telemetry
valid_until_tick
target_actuator
body_frame_id
requested_values
profile_sha256
descriptor_sha256
state_before_sha256
current_sha256
command_sha256
```

```text
cassi.qi-flow-tick-intent.v1
world_id
episode_id
profile_sha256
session_id
cycle_number
from_tick
to_tick
committed_prior_head_sha256
body_frame_id
idempotency_key
action_scope = null | {action_sha256, canonical_action_bytes}
canonical_intent_sha256
```

`action_scope=null` is the complete hold/abstention form; it is not a missing
field. A non-null scope embeds the exact canonical
`cassi.qi-flow-action.v1` bytes and their matching digest. The tick-intent
self-hash therefore binds the action without creating a second world call.

In the canonical world profile, a command derived at committed tick `t` fixes
`logical_tick=t`, `effective_tick=t+1`, and `valid_until_tick=t+1`.
`command_timestamp_ns_telemetry` has no validity authority. The adapter may
apply the command only at the beginning of that exact world transition; after
the world has passed `t+1`, it returns its retained terminal truth or an
authenticated `expired`, never a late application. A provider timeout cannot
locally manufacture `expired`: it must keep the outbox unresolved and call
`resolve_tick()` against the original scope.

`accepted` and `started` acknowledgements are nonterminal. `applied`,
`rejected`, and `expired` are terminal. `timeout` is a local unresolved status,
not a world acknowledgement. A `duplicate` response is valid only as an
envelope around the world adapter's retained original terminal acknowledgement
with the identical world/episode/idempotency/command scope; it repeats the
original truth and values rather than inventing another outcome.

Only a terminal `applied` acknowledgement creates
`cassi.qi-flow-applied-efference.v1`. That object records
`world_effect=true`, exact applied values, application tick, first visible
observation tick, resulting body transition, original acknowledgement bytes,
proposal/reaction identity, and the Commit-A/predecessor head. It is committed
in Commit B before any remap or residual can consume it. `rejected` and
`expired` record `world_effect=false`; a timeout records `world_effect=unknown`
and blocks further world advancement. A rejection is visible and never
converted to a no-op success.

### Terminal outcomes as ordinary field events

The terminal status is itself an ordinary, fixed `QiBoundaryPacket` event
when it is authenticated and committed. Its detached payload is the
canonical tuple

```text
action_terminal_outcome
  action_id
  idempotency_scope_sha256
  terminal_status = applied | rejected | expired | hold
  world_effect = true | false
  applied_values_sha256 | null
  status_reason_sha256
```

The packet enters the field only after the corresponding terminal
acknowledgement is committed in Commit B (or, for `hold`, after Commit B
commits the pre-registered `action_scope=null` tick-intent). `rejected` and
`expired` therefore are not host metadata or an absent/no-op sample: they are
work-accounted field events with `world_effect=false` and exactly zero
self-predicted work. `hold` is the pre-registered `action_scope=null`
no-command control with the same ordinary packet/event path. Only `applied`
may carry `applied_values_sha256` or create the separately defined
`QiEfferenceCopy`. A local `timeout` is not a packet, terminal event, or
world transition; it remains `world_effect=unknown` and advances nothing
until authenticated resolution yields one of the terminal outcomes.

Any claim that field adaptation handles action failure must use a frozen,
whole-episode applied/rejected/expired/hold fixture with the same predecessor,
proposal scope, geometry, clock, and work classes. The status-aware field
packet and its ordinary residual path must improve the held-out status
discrimination or next-valid-action/prediction by a declared positive
work-normalized interval over a status-blind and no-command hold control:

\[
\frac{\Delta_{\mathrm{status}}^{-}}
{W_{\mathrm{adm}}+W_{\mathrm{residual}}}
\geq
\max(\Delta_{\mathrm{abs}},\Delta_{\mathrm{rel}})>0,
\qquad
0<W_{\mathrm{adm}}+W_{\mathrm{residual}}<\infty .
\]

The applied arm may additionally use its terminal-only efference and body
remap; rejected, expired, and hold arms never do. Status identity is carried
only by the ordinary packet, bounded receipt, and causal parent hashes. No
status sidecar, failure counter, rejection policy, or eligibility/credit
state may be added to `QiFieldState` or a checkpoint. A missing or unresolved
status row fails the failure-handling claim rather than being relabeled
hold, no-op success, or negative learning.

## Body frame and predictive remapping

`cassi_qi_body.py` owns stateless rigid-body registration and field remaps. The
immutable descriptor declares world handedness, the head/neck-midline
engineering origin, body axes, sensor/actuator extrinsics, and all numerical
operators. It contains no persistent pose estimator.

For a world point under one validated pose,

\[
p_B=R_{BW}(p_W-t_{WB}).
\]

Let old body frame `B` and new body frame `B'` define

\[
x_{B'}=Ax_B+b,
\qquad
A=R_{B'W}R_{WB},
\qquad
b=R_{B'W}(t_{WB}-t_{WB'}).
\]

The field is an instantaneous state relabel:

\[
Z_{B'}(x')=Z_B\!\left(A^{-1}(x'-b)\right).
\]

With each scale's profile FFT convention
`\widehat Z_s(k_s)=sum_x Z_s(x)e^{-ik_s dot x}`, a translation-only body
change has `Delta x=b=-R_BW delta t_W` and therefore

\[
\widehat Z'_s(k_s)=e^{-ik_s\cdot\Delta x}\widehat Z_s(k_s),
\qquad
\widehat V'_{Z,s}(k_s)=e^{-ik_s\cdot\Delta x}\widehat V_{Z,s}(k_s),
\qquad Z\in\{D,C\}.
\]

The physical displacement is shared, but every scale uses its own hashed
`k_s` derived from its spacing. The velocity planes are relabeled by the same
instantaneous pullback; no convective
`dot(Delta x) dot grad Z` term is implied. Physical motion and its timing enter
through the acknowledged efference/body packet and successor residual.
Rotation uses the fixed affine order above and one periodic-grid operator per
scale with a declared adjoint and measured interpolation work; an arbitrary
backend resampler cannot enter the release profile.

The intrinsic field topology and the physical sensor aperture are separate
contracts. A periodic spectral sheet may be used with a declared guard band
only when the maximum remap horizon cannot wrap active sensory content across
an edge. A finite-aperture profile instead remaps the overlapping support and
accounts for entering and leaving support as explicit boundary work; it does
not claim unitarity. Exact self-motion cancellation is scoped to the geometry
class encoded by the descriptor, such as a planar/orthographic fixture or a
spherical pure-rotation map. General 3-D camera translation has depth-dependent
parallax and remains exafferent residual unless depth is represented and used
by a fixed field operator.

The ninth `epsilon2_ema` plane is a persistent real nonnegative site field, not
a velocity coordinate. Its active-subspace scalar remap matrix `R_ema,s` must
satisfy

\[
R_{\mathrm{ema},s}\geq0,
\qquad
R_{\mathrm{ema},s}\mathbf 1=\mathbf 1,
\qquad
\mathbf 1^T W_sR_{\mathrm{ema},s}=\mathbf 1^TW_s.
\]

Thus it preserves nonnegativity, constants, and cell-volume-weighted mass. The
complete affine remap is applied once per acknowledged pose transition, never
as two interpolation half-steps. Its receipt records mass change, minimum,
diffusion residual, and forward/reverse error. Integer shifts and declared
grid permutations are exact; fractional translations/rotations are admitted
only after the scalar remap passes positivity and ledger gates.

Every body remap is a zero-clock map and consumes the Part 2 transported
topology contract when topological retention is active. Its descriptor declares the exact
\(\Pi_z\) induced on the ordered cycle/plaquette sector vector. A periodic
integer translation uses the registered
\(\Pi_{\Delta_x,\Delta_y}\) index permutation from Part 2, not \(I\), unless
the entire indexed sector vector is itself translation-invariant. Only
genuinely index-preserving maps use \(I\). A nonidentity signed permutation is
permitted only for a registered exact torus automorphism with an exact inverse.
Before commit, the receipt must prove
\[
\mathcal T_{\mathrm{topo}}(X_z)=\Pi_z\mathcal T_{\mathrm{topo}}(X),\qquad
\Pi_z\mathscr C_{\mathrm{topo}}=\mathscr C_{\mathrm{topo}},
\]
together with the amplitude/branch enclosure. A fractional/interpolated map
that cannot prove this identity is rejected. A remap-induced coordinate
permutation is never a phase slip, acquisition, forgetting, or new capacity;
the controller-generated reachable set inverse-transports it as specified in
Part 2.

`QiEfferenceCopy` is generated only after a terminal `applied`
acknowledgement has committed in Commit B. It has the same action ID, command
hash, application tick, body-remap identity, expected-effect window, and
transform. It is transient and predicts only the self-generated part of
future sensation. A proposal, motor-port reaction, `accepted`, or `started`
status never permits an efference copy. For terminal `rejected` or `expired`,
`world_effect=false` and the self term is exactly zero; a local `timeout`
has `world_effect=unknown`, supplies no efference copy or successor
correction, and leaves world advancement blocked until authenticated
resolution.

At a successor observation admitted after a terminal status, define the
transient status gate

\[
\chi_{\mathrm{self}}=
\begin{cases}
1,&\text{terminal } applied,\\
0,&\text{terminal } rejected\text{ or }expired.
\end{cases}
\]

Then

\[
e_{t+1}
:=
W_{t+1}^{\mathrm{observed}}
-
\left(
W_{t+1}^{\mathrm{predicted,world}}
+\chi_{\mathrm{self}}
W_{t+1}^{\mathrm{predicted,self}}
\right).
\]

The pre-correction residual and all contributing hashes are recorded before
the descriptor adjoint forms the immutable packet
\[
F_{\mathrm{residual}}^{t+1}:=\eta B^\dagger e_{t+1}.
\]
This packet is queued only for the two registered external-force half-kicks of
the *next* call `advance(t+1 -> t+2)`: its receipt names `predecessor_tick=t`,
`observation_tick=t+1`, `effective_tick=t+1`, and
`queued_residual_sha256`. It is never consumed by the call that admitted the
successor observation. A timeout, absent terminal outcome, or failed
observation creates no packet and leaves world advancement blocked until
authenticated resolution. Position/source injection exists only in explicitly
named control fixtures. There is no cached image, persistent prediction tensor,
residual memory, or correction-before-measurement path.

The adjoint form alone does not prove that a velocity kick corrects a
second-order field. Each boundary therefore measures residual effectiveness at
the declared successor horizon: pre-kick error, next-prediction error, admitted
work, and improvement per unit work. It compares `+e`, `-e`, zero,
metric-orthogonal, phase-scrambled, and energy-matched residual drives from the
same predecessor. A residual path that only excites the field without improving
the next prediction is repaired rather than labeled learning.

## Field-owned attention, gaze, and action

The world exposes a finite set of action geometries, bounds, and fixed costs.
It must not expose the sensory consequences of candidates. The runtime may
fork transient candidate field trajectories from the current state, but those
scratch tensors are bounded, cannot outlive the decision, and only the chosen
successor can be committed.

Let `Phi_a^pred` be the profile-versioned, zero-new-observation candidate
evolution under action/body map `a` over one shared decision horizon `H`, and
let `hold` be its matched null action. Action-specific latency, onset, duration,
and slew are represented inside `[0,H]`; candidates are never compared after
different amounts of field time. For every affected modality,

\[
\delta W_{r,a}
=
B_{r,a}\Phi_a^{\mathrm{pred}}(\mathcal X_t)
-B_{r,\mathrm{hold}}\Phi_{\mathrm{hold}}^{\mathrm{pred}}(\mathcal X_t),
\qquad
\widehat e_{r,a}=e_{r,t}-\delta W_{r,a}.
\]

The predicted-correction cost is

\[
\widehat E_{r}(a)
:=
\frac{
\|\widehat e_{r,a}\|_{W_r}^2
}{
\max(
\|e_{r,t}\|_{W_r}^2,
E^{\mathrm{action}}_{\mathrm{ref},r}
)
},
\qquad
E^{\mathrm{action}}_{\mathrm{ref},r}>0.
\]

The finite reference preserves a penalty when the current residual is exactly
zero, so the flow and movement terms may still select a proactive valid action
without making every non-hold candidate impossible. Invalid/missing residual
packets fail before candidate scoring.

### No-peek finite-horizon observability

**QI-ACT-001**, implemented and gated by **W9O/G9O**, adds an
observability-improvement term to gaze and action selection. The term is
computed before any candidate observation exists, from the fixed candidate
geometry, the current committed field, and the same zero-new-observation
horizon \(H\) already used for residual prediction. It is not a value supplied
by the world and is not a learned salience map.

The action profile declares a finite set of unit directions
\(q_{a,k}\) in the registered body/port geometry, the sample times
\(t_\ell\in[0,H]\), positive quadrature weights, the fixed candidate and hold
operators, and a positive-definite reference metric \(G_{\mathrm{obs,ref}}\).
The direction list has one common profile-fixed cardinality \(K\); candidate
and hold vectors are deterministic geometry/body pullbacks of that same list,
so both Gramians have identical dimensions.
For the current committed field \(X_t\), let

\[
y_{r,a,k,\ell}
:=
B_{r,a}\,
D\Phi_{a,\ell}^{\mathrm{pred}}(X_t)[q_{a,k}],
\qquad
y_{r,\mathrm{hold},k,\ell}
:=
B_{r,\mathrm{hold}}\,
D\Phi_{\mathrm{hold},\ell}^{\mathrm{pred}}(X_t)[q_{\mathrm{hold},k}].
\]

Here \(D\Phi^{\mathrm{pred}}\) is the fixed profile derivative of the admitted
field/body operator around the current committed state. It may be evaluated
on bounded scratch trajectories, but it never calls the world or reads a
candidate sensor payload. For each temporal sample, collect the direction
responses as
\[
Y_{r,a,\ell}
:=
\left[
y_{r,a,1,\ell}\ \cdots\ y_{r,a,K,\ell}
\right],
\qquad
Y_{r,\mathrm{hold},\ell}
:=
\left[
y_{r,\mathrm{hold},1,\ell}\ \cdots\
y_{r,\mathrm{hold},K,\ell}
\right].
\]
The finite-horizon observability Gramians are the direction-by-direction
matrices
\[
\begin{aligned}
G_a^{\mathrm{obs}}
&=\sum_{r,\ell}
  \omega_{r,\ell}\,
  Y_{r,a,\ell}^{H}W_rY_{r,a,\ell},\\
G_{\mathrm{hold}}^{\mathrm{obs}}
&=\sum_{r,\ell}
  \omega_{r,\ell}\,
  Y_{r,\mathrm{hold},\ell}^{H}W_rY_{r,\mathrm{hold},\ell}.
\end{aligned}
\]

The profile fixes the direction ordering and the reference scale
\(I_{\mathrm{obs,ref}}>0\). The bounded improvement is

\[
I_{\mathrm{obs}}(a)
:=
\frac{
\operatorname{tr}\!\left[
G_{\mathrm{obs,ref}}^{-1}
\left(G_a^{\mathrm{obs}}-G_{\mathrm{hold}}^{\mathrm{obs}}\right)
\right]
}{
I_{\mathrm{obs,ref}}
+\operatorname{tr}\!\left[
G_{\mathrm{obs,ref}}^{-1}
\left(G_a^{\mathrm{obs}}+G_{\mathrm{hold}}^{\mathrm{obs}}\right)
\right]
},
\qquad -1<I_{\mathrm{obs}}(a)<1 .
\]

The denominator is positive by construction; a singular or nonfinite
reference, derivative enclosure, or Gramian rejects the candidate before
score competition. The profile records the derivative/operator hash,
geometry hash, current-state hash, temporal grid, Gramian intervals,
conditioning, and \(I_{\mathrm{obs}}\) uncertainty. A hold candidate has
zero improvement by definition. There is no state slot for a Gramian,
direction, salience value, or observation history.


The **G9O** controls hold the current packet, predecessor, profile, and
candidate order fixed while: (i) permuting all unseen world consequences,
(ii) changing only registered geometry and checking the analytically predicted
\(I_{\mathrm{obs}}\) delta, (iii) freezing the current field, (iv) setting
\(\mu_{\mathrm{obs}}=0\), and (v) applying matched-energy phase/current
scrambles. Only the declared geometry/current-field operator may change the
term. A missing derivative or unresolved interval abstains rather than
looking at a future observation.

For normalized action displacement `Delta q_a`, the action profile includes
only movable components with strictly positive declared ranges `r_j>0`;
fixed/zero-width components are absent from both candidate and sum:

\[
c_{\mathrm{move}}(a)=
\sum_j\left(\frac{\Delta q_{a,j}}{r_j}\right)^2.
\]

Let `m_a(x)>=0` be the fixed normalized action-region mask,
`d_a(x)` its unit motion direction, `s_*` the declared slow steering scale,
and `J_ref>0`. The bounded current alignment is

\[
A_{\mathrm{flow}}(a)
=
\frac{
\langle m_a d_a,\mathbf J_{D,s_*}\rangle_{W_{s_*}}
}{
J_{\mathrm{ref}}+
\langle m_a,|\mathbf J_{D,s_*}|\rangle_{W_{s_*}}
}.
\]

`A_flow` is zero for hold and lies in `[-1,1]`. `I_obs` is zero for hold
and lies in `(-1,1)`. Safety is purely geometric:
`C_safety(a)=0` only if the descriptor-provided swept path, capability,
latency, and hard bounds validate; otherwise it is `+infinity` and cannot win.
The one canonical score is

\[
\mathcal C(a)
:=
\sum_r\nu_r\widehat E_r(a)
+\mu_{\mathrm{move}}c_{\mathrm{move}}(a)
-\mu_{\mathrm{flow}}A_{\mathrm{flow}}(a)
-\mu_{\mathrm{obs}}I_{\mathrm{obs}}(a)
+\mathcal C_{\mathrm{safety}}(a),
\]

where `nu_r>=0`, `sum_r nu_r=1`, `mu_move>=0`, `mu_flow>=0`,
`mu_obs>=0`, the shared horizon, all masks/directions/ranges, observability
directions/reference, and candidate accumulation order are versioned profile
data. A production claim that depends on a term requires its coefficient to be
positive, including `mu_obs>0` when observability is claimed; exact-zero
variants are named diagnostic profiles. The independent verifier recomputes
each term from raw candidate/field/boundary artifacts.

Let \(w\) be the unique lowest-central-cost feasible candidate,
\(C_w^+=C_w+U_w\), and

\[
C_r^-=\min_{a\neq w}(C_a-U_a),
\qquad
S_C
=\max\!\left(
|C_w|+U_w,\,
\max_{a\neq w}(|C_a|+U_a)
\right).
\]

The empty competitor minimum is \(+\infty\), and the empty inner maximum is
zero, so `S_C` remains finite even for a singleton candidate set. The winner
commits only if

\[
C_r^- - C_w^+
\geq
\max(\Delta_{\mathrm{abs}},\Delta_{\mathrm{rel}}S_C).
\]

An exact central-cost tie, overlapping uncertainty interval, or failed margin
abstains; action IDs order diagnostics only. Abstention commits only the
canonical hold action and never reuses a previous winner.

No-peek is a structural operator and API rule. `B_{r,a}`,
`D\Phi_a^{pred}`, and the finite-horizon observability Gramian may depend only
on frozen boundary geometry, calibrated body transform, current committed
field, current admitted packets, and hashed profile/operator constants. The
candidate branch receives no unobserved world payload and cannot call the
world, read a candidate observation, inspect collision/render consequences,
or vary by hidden adapter, teacher, model, or policy state.
`describe_actions()` returns geometry/cost/capability only; `observe()` returns
the current committed sensor view only; there is no `observe(candidate)` method
and no API by which a candidate consequence can be supplied.

The no-peek fixture permutes all unseen candidate consequences while holding
current input, state, geometry, packet order, and operator hash fixed and
requires byte-identical predictions, finite-horizon observability intervals,
proposals, and chosen action. It then changes only registered geometry and
requires the analytically predicted \(I_{\mathrm{obs}}\), alignment, and
operator deltas. Only a post-commit observation may change the next residual,
observability term, and action.

A `QiFlowDecision` proves causal ownership with a matched-energy directional
counterfactual. The live and transformed states receive identical current
boundary data and candidate geometry. Receipts separate the direct
`A_flow` contribution from prediction-mediated steering: they include
`mu_flow=0`, prediction-frozen, direct-flow-only, `mathcal R_J`, and
`mathcal R_P` arms. A reversal-induced winner change caused solely by the
explicit alignment term proves field-conditioned selection, not predictive
competence. The production path must also show the registered successor or
world consequence changes through the intended flow channel. Static field
availability, state hash inequality, or output count cannot substitute.

### Offline paired-world discriminability and delayed multi-frontier influence

**QI-ACT-001** has a second, offline evidence obligation in addition to the
live no-peek term. The canonical evidence object is
`cassi.qi-flow-action-discriminability.v1`. It is built from two
authenticated deterministic worlds that share the complete prefix through the
same Commit-A predecessor, current packets, body/action geometry, proposal,
and terminal command scope, and differ only at a registered post-commit
world-consequence fixture. The paired worlds are never supplied to candidate
evaluation. Their complete raw successor packets and world adapter receipts
are inspected only after the offline run has committed and observed them.

An observability-driven production claim has an additional linkage gate:
whenever a release profile sets \(\mu_{\mathrm{obs}}>0\), or a capability
claim relies on \(I_{\mathrm{obs}}(a)\), the corresponding selected action
must clear the paired-world separation and matched-hold null margin on every
declared frontier. Without that offline causal consequence,
\(I_{\mathrm{obs}}\) is diagnostic geometry evidence only; setting a positive
coefficient cannot turn local field self-sensitivity into an observability or
action-effect claim. This linkage is checked after the terminal applied
receipt and never exposes paired-world data to the live score.

For candidate \(a\), let \(Y_{a,f}^{(0)}\) and \(Y_{a,f}^{(1)}\) be the
complete committed boundary/successor observations at registered frontier
\(f\) in the two worlds, and let \(U_{a,f}\) be the independently propagated
interval enclosure under the declared observation metric. The
work-normalized paired-world separation is

\[
d_{a,f}^{\mathrm{pw}}
:=
\frac{\left\|Y_{a,f}^{(1)}-Y_{a,f}^{(0)}\right\|_{W_f}}
{\sqrt{W_{a}^{\mathrm{applied}}+W_{f,\mathrm{ref}}}},
\qquad
W_{a}^{\mathrm{applied}}+W_{f,\mathrm{ref}}>0,
\]

where the denominator is a frozen positive profile reference made from the
terminal applied action/efference work and the declared frontier residual
reference. The receipt carries a directed interval
\([d_{a,f}^{-},d_{a,f}^{+}]\), not a central score. A candidate/world pair
demonstrates discriminability only if every claimed frontier has a finite
lower interval that clears both the profile null threshold
\(D_{\mathrm{null},f}^{+}\) and the propagated uncertainty margin:

\[
d_{a,f}^{-}-D_{\mathrm{null},f}^{+}
\geq
\max\!\left(\Delta_{\mathrm{abs}},
\Delta_{\mathrm{rel}}\,
\max(d_{a,f}^{+},D_{\mathrm{null},f}^{+})\right)>0 .
\]

The null is a matched hold/no-action pair with the same incident and
admitted-work classes, predecessor, observation horizon, and world fixture.
An unresolved interval, zero-work normalization, identical-world null, or
separation that does not clear the positive margin is `indeterminate`, not
evidence of an action consequence. Pair labels are swappable and the
world-order permutation must transform the signed/directional rows exactly.
Field-frozen, matched-energy phase/current-scramble, action-permutation,
hold, rejected/expired, and terminal-acknowledgement controls are retained;
proposal, motor-port reaction, `accepted`, and `started` are never counted as
an external effect. Only terminal `applied` can set `world_effect=true` and
anchor a claimed applied action/efference; a timeout remains unresolved and
cannot be turned into a paired-world effect.

The finite delayed influence receipt is
`cassi.qi-flow-delayed-influence.v1`. It records one action identity and a
finite, profile-frozen set of causal frontiers

\[
\mathcal F_a
:=\{f_j=(r_j,\tau_j,\mathrm{world}_j,\mathrm{episode}_j):
1\leq j\leq J,\quad
0<\tau_1<\cdots<\tau_J\leq H_{\mathrm{delay}},\quad
J<\infty\}.
\]

Each frontier has an exact logical tick, post-commit observation/residual
packet hash, causal parent chain, world/episode identity, and a
work-normalized interval. The action-versus-hold residual influence at that
frontier is recorded as

\[
\Delta_{a,f_j}
:=
e_{f_j}^{\mathrm{hold}}-e_{f_j}^{a},
\qquad
\mathsf I^{\mathrm{mag}}_{a,f_j}
:=
\frac{\langle \Delta_{a,f_j},\Delta_{a,f_j}\rangle_{W_{f_j}}}
{\max(E_{f_j,\mathrm{ref}},
W_{a}^{\mathrm{applied}}+W_{f_j,\mathrm{residual}})},
\]

\[
\mathsf I^{\mathrm{red}}_{a,f_j}
:=
\frac{\left\|e_{f_j}^{\mathrm{hold}}\right\|_{W_{f_j}}^2
-\left\|e_{f_j}^{a}\right\|_{W_{f_j}}^2}
{\max(E_{f_j,\mathrm{ref}},
W_{a}^{\mathrm{applied}}+W_{f_j,\mathrm{residual}})} .
\]

with positive finite profile references and directed uncertainty intervals.
\(\mathsf I^{\mathrm{mag}}\) measures only trajectory divergence and cannot
support a beneficial-action or learning claim; every such claim uses the
signed residual-reduction interval \(\mathsf I^{\mathrm{red}}\) below and its
matched-null test:
\[
\underline{\mathsf I^{\mathrm{red}}}_{a,f_j}
-\overline{\mathsf I^{\mathrm{red}}}_{\mathrm{null},f_j}
\geq
\max\!\left(\Delta_{\mathrm{abs}},
\Delta_{\mathrm{rel}}\,
\max(\overline{\mathsf I^{\mathrm{red}}}_{a,f_j},
\overline{\mathsf I^{\mathrm{red}}}_{\mathrm{null},f_j})\right)>0 .
\]
The receipt retains the per-frontier lower/upper influence, the matched hold
and no-action null, frontier order, maximum delay, applied-efference identity,
and a positive null/uncertainty margin for each frontier used in a causal
claim. It does not sum an unbounded tail or assign credit to an unobserved
frontier. A missing, out-of-order, unresolved, or nonterminal frontier seals
the corresponding claim as `indeterminate` and never creates a late action
eligibility.

Delayed corrections are ordinary observed `QiBoundaryPacket` residuals at
their authenticated successor frontiers. They may enter the existing
metric-adjoint residual path after observation, exactly once and with the
usual source/work ledger, but they are never an eligibility trace, delayed
credit variable, queue, accumulator, or persistent policy state. The finite
influence receipt is offline evidence only: it cannot alter the live
no-peek \(\mathcal C(a)\), candidate set, proposal, emitted command, or
future gate. Candidate selection therefore remains based solely on the
current committed field, current admitted packets, fixed geometry, and the
common zero-new-observation horizon already specified above.

The discriminability and influence receipts include the complete
profile/body/action hashes, shared-prefix and predecessor heads, candidate
and hold identities, terminal acknowledgement/efference bytes, applied
frontier schedule, observation/residual digests, incident/admitted/residual
work intervals, null thresholds, uncertainty and margin calculations, and
all control identities. Their arrays are bounded content-addressed evidence
and never enter `QiFieldState`. A receipt that reports only a changed state
hash, proposal, output count, or static field availability does not establish
paired-world discriminability or delayed causal influence.

