# Cassi: Field-Owned Intelligence in a Persistent Multiscale Yang–Yin Dynamical System

## 1. Abstract

Cassi is a deterministic field-intelligence architecture in which all adaptive persistent state resides in one active multiscale Qi-field tensor, with the reference layout \(F_t \in \mathbb{R}^{S\times 9M\times B}\). Its component planes carry complex Yang and Yin amplitudes, their velocity components, and `epsilon2_ema`, a running squared-imbalance estimate. Surface-specific fixed geometry, codebooks, codecs, numerical operators, schemas, and policy constraints govern how observations enter the field, how field state evolves and consolidates, and how queries produce readouts. Surface-specific versioned checkpoints bind the complete adaptive tensor to runtime identity; the persistent-provider and v3 frames additionally verify content hashes. A deterministic OpenAI-compatible protocol adapter exposes the implemented provider runtime.

Evaluation tests whether measured capabilities are causally owned by the field. Deterministic replay, field-only counterfactuals and lesions, held-out grounded transitions, restart checks, read-only inference, and long-horizon stability provide that test. In exact-edge experiments, a frozen field composes independently learned one-action fragments into held-out multistep trajectories, while removal of a necessary edge eliminates the corresponding solution. Across relational-basis and typed-program experiments, field-selected operators transfer across renamed, reordered, and translated scenes within the tested interior regimes. Supported symbolic laws transfer exactly, and the field abstains when the tested grammar supplies no supported natural-prose continuation. Checkpoints reproduce exactly, inference preserves trained state, and repeated updates remain finite over the measured horizons.

These measurements establish persistent field-owned adaptation, grounded composition, exact symbolic transfer, and explicit abstention in bounded tasks. Cassi provides an inspectable experimental platform for extending those capabilities while preserving a single adaptive state.

## 2. Introduction: Why Field-Owned Intelligence?

An intelligent system persists by carrying the effects of experience forward. In Cassi, that continuity is a concrete computational property: an observation changes a field, later queries encounter the changed state, and the consequences of an executed action become new observations. The architecture centers this causal chain in one adaptive object so that learning, recall, inference, and selection can be studied as transformations of the same state.

The resulting research program asks a direct question: how much intelligent behavior can arise when adaptive persistence is concentrated in a bounded dynamical field? Cassi approaches the question through an implemented runtime, exact state serialization, grounded environments, and interventions on the field itself. Its evidence consists of reproducible state transitions, held-out outcomes, counterfactual field states, lesions, abstentions, and restart receipts.

### 2.1 Adaptive state across contemporary agents

A deployed AI agent can carry state in several places. Trained parameters encode regularities acquired during model training. A prompt or context window carries the current episode. A retrieval system supplies selected records from earlier episodes. Workflow state tracks plans, tool calls, and pending actions. External services may contribute their own learned representations and mutable histories. Each component has a distinct update rule, lifetime, and authority.

This distribution is useful for engineering, but it complicates scientific attribution. A successful response may reflect parameter memory, retrieved text, a hand-coded transition, cached output, or current context. Adding a field module to such a stack establishes its presence; causal ownership requires stronger evidence. The relevant test changes the field while holding the remaining computation fixed and observes whether the committed result changes in the predicted way.

Cassi adopts that stronger criterion as an architectural constraint. Experience-dependent persistence is concentrated in one field state. The surrounding machinery provides fixed geometry, deterministic encodings, numerical evolution, validation, persistence, and policy. This arrangement turns adaptive state into an inspectable experimental variable. It can be saved exactly, restored exactly, held fixed during inference, altered counterfactually, or lesioned at a specific functional region.

The constraint also gives “memory” a precise meaning inside Cassi. Memory is the part of the field produced by prior observations that changes a later readout or action proposal. A transcript, receipt, or exact external record supplies evidence to the runtime, while the field carries the adaptive effect of that evidence. The distinction allows storage, computation, and authority to remain explicit as the field-intelligence runtime connects to the Mnemic Field and CassiCosmos layers.

### 2.2 The Cassi hypothesis

For this study, *field-owned intelligence* denotes adaptive behavior produced by steering coherence through a persistent dynamical state. The definition supplies an operational criterion for the experiments: sensing, memory formation, inference, selection, and emission must depend causally on that state. “Coherence” is expressed in the implementation through field amplitudes, relative phase, energy-like quantities, Yang–Yin balance, write gates, interscale relations, and query-dependent readout. These quantities determine how an observation enters the field, how its influence moves and consolidates, and which stored structure becomes available to a later query.

The adaptive state has the general form

\[
F_t \in \mathbb{R}^{S\times 9M\times B}.
\]

The reference v2 tensor uses nine planes at each scale for complex Yang and Yin amplitudes, their velocity components, and `epsilon2_ema`. Scale zero is its fastest and finest mode bank; increasing scale index represents slower and coarser structure, and fixed codebooks map observations and queries into those mode coordinates. The profile-governed v3 surface retains the nine-plane order but assigns profile-declared active prefixes to periodic spatial sheets. In both surfaces, the values of the active tensor carry the accumulated effects of experience; their geometry and transition semantics come from the named surface.

On the v2 reference cognition surface, a field cycle begins with a validated observation. A deterministic codec maps that observation into boundary data, and the controller combines typed source trust with field coherence to gate a scale-zero deposit. `evolve` advances local damped nonlinear modes. A separate consolidation step can transfer supported bindings toward slower scales. A query then produces a phase-sensitive readout from the current field, and fixed selection logic can convert that readout into a prediction, explanation, trajectory, abstention, or typed action proposal. An executed action affects later field state only when an implemented integration returns its observed consequence as another validated observation.

This organization gives the hypothesis three testable properties. First, every adaptive result has a concrete predecessor state and surface-specific transition. Second, the complete adaptive tensor can cross a process boundary in a versioned checkpoint bound to the selected runtime's configuration or profile fingerprints; the persistent-provider and v3 formats add explicit content-integrity hashes. Third, field interventions provide causal tests: a relevant lesion should remove a capability, while an unrelated lesion should preserve it. Cassi therefore makes field ownership measurable rather than metaphorical.

The implemented OpenAI-compatible provider supplies familiar request and streaming conventions while the Qi field supplies adaptive computation. Exact Mnemic references, grounded world observations, and authorized CassiCosmos outcomes remain independently identified integration inputs. They enter a field transition only through an explicit adapter, and later sections distinguish implemented and measured adapters from design-stage boundaries.

### 2.3 Research question

The primary research question is:

> To what extent can one bounded persistent field acquire and express useful structure across sensing, memory, inference, and action while remaining causally inspectable?

The implementation divides this question into six measurable parts:

1. **State ownership.** Does experience alter the field, and does that alteration causally change a later committed result?
2. **Grounding.** Can field state connect symbols and instructions to exact observed changes in a world?
3. **Composition.** Can independently observed transition fragments support a held-out multistep trajectory?
4. **Relational transfer.** Can the field select a relation or typed operation that remains valid across renamed entities, reordered observations, translated scenes, and other controlled changes?
5. **Continuity.** Do checkpoint, restart, replay, and read-only inference preserve the intended state and behavior exactly?
6. **Epistemic control.** Can the runtime distinguish supported settlement, ambiguity, exhaustion, unsupported input, and abstention from one another?

Each part is evaluated through observable state and outcome contracts. Exact tasks use exact successor revisions or exact symbolic outputs. Relational tasks separate training worlds, selection evidence, and held-out worlds. Persistence tasks compare serialized bytes, field hashes, and post-restart behavior. Causal tests intervene on field state rather than inferring ownership from a plausible response.

The experiments also map the domain in which a learned structure applies. Interior affine motion, boundary clamping, moving targets, missing intermediate observations, coordinate noise, passive roles, indistinguishable distractors, symbolic transformations, and natural prose place different demands on the same architecture. Reporting them separately preserves the meaning of each result.

### 2.4 Contributions

This paper makes eight technical contributions:

1. **A single-state field-intelligence architecture.** Cassi places all adaptive persistent state in one active tensor under each selected field-runtime surface and gives fixed runtime machinery explicit responsibility for geometry, encoding, evolution, validation, and policy.
2. **A deterministic multiscale Yang–Yin field.** The reference controller defines complex paired fields, velocity components, scale orientation, bounded evolution, consolidation, and phase-sensitive readout in one inspectable state space.
3. **A reference causal cycle.** The v2 cognition path composes sensing, deposition, local evolution, readout, selection, optional correction, and consolidation around one `QiFieldState`; external action consequences re-enter only through implemented typed-observation adapters.
4. **Grounded counterflow composition.** Exact observed action fragments form compatible effect-to-precondition edges from which a frozen field can settle held-out multistep trajectories.
5. **Field-selected relational and typed structure.** Bounded experiments place relation evidence, operator support, program ranking, confirmation, and regime information inside the field and test transfer under controlled changes.
6. **Exact persistence and runtime identity.** Surface-specific versioned framing, configuration and profile fingerprints, provider and v3 content hashes, atomic provider-checkpoint replacement, component identities, and deterministic receipts make the adaptive state reproducible across process restarts.
7. **A causal evaluation method.** Field-only counterfactuals, targeted lesions, shuffled controls, held-out worlds, read-only inference, long-horizon runs, and forbidden-surface sentinels test whether the field owns the measured behavior.
8. **A measured capability map.** The experiments establish grounded composition, relational transfer in tested regimes, exact symbolic-law transfer, persistent replay, and explicit abstention, while locating the boundary conditions that guide the next experiments.

These contributions form one systems result. The mathematical field defines the possible state transitions; the grounded tasks determine what those transitions mean; persistence preserves their history; and causal intervention tests whether the resulting behavior belongs to the field.

### 2.5 Scope of the evidence

The paper studies the live Cassi field-intelligence prototype through bounded tasks with explicit observations, candidate spaces, outcome contracts, and holdouts. This scope supports exact causal comparisons: the predecessor field is known, the intervention is reproducible, and the expected world revision or symbolic result is measurable. Natural-prose continuation and cross-view experiments extend the same discipline to domains where the present field has less support.

The unit of evidence is a reproducible relationship among observation, field transition, readout, and outcome. Recognizable output alone carries little weight; an exact receipt, a field-dependent counterfactual, or a successful held-out consequence supplies the relevant evidence. Broader interpretations of intelligence can therefore be discussed from a concrete base of measured capabilities.

Cassi joins three technical domains within one field framework. Mnemic Field preserves exact records and supplies revision-specific references. CassiCosmos supplies a physical field-and-particle world and executes validated programs. The field-intelligence runtime turns typed observations from those environments into adaptive field state and returns predictions, explanations, abstentions, or inert proposals. Each cross-layer result in this paper is tied to the specific live path that produced it.

The sections that follow formalize field ownership, derive the multiscale state and its operators, trace the complete computational cycle, describe grounding and counterflow, present persistence and protocol contracts, and evaluate the resulting capabilities through causal interventions and held-out measurements.

## 3. Operational Definition of Field Ownership

Field ownership is a study definition that makes Cassi's central architectural claim testable. It identifies where experience-dependent state resides, how that state crosses time and process boundaries, and what evidence establishes its role in a measured capability. The definition serves as an accounting rule for the field-intelligence implementation and experiments presented in this paper.

For this study, a value is **adaptive persistent state** when it satisfies three conditions: experience can change it, it can survive beyond the call that changed it, and the changed value can influence a later result without being supplied again as part of the current observation. Within Cassi's field-intelligence runtime, every value with those properties is assigned to the Qi field. Configuration, codecs, numerical operators, validation, and policy remain fixed; exact records retain evidence and provenance; temporary computations are derived from the current field and request.

### 3.1 The shared adaptive tensor and versioned runtime surfaces

Cassi represents adaptive persistence as one packed tensor in each active field-runtime state:

\[
F_t \in \mathbb{R}^{S\times 9M\times B},
\]

where \(S\) is the number of scales, \(M\) is the mode capacity per scale, and \(B\) is the batch width. The middle dimension is a packed sequence of nine \(M\)-wide component planes. This tensor layout is the architectural invariant. The implementation currently binds it through two explicitly versioned runtime surfaces:

| Surface | State and operator | Checkpoint schema | Present use |
|---|---|---|---|
| Reference cognition surface | `QiFieldState` and `QiFieldController` | `cassi.qi.field-state.v2` | Fixed-codebook sensing, phase-sensitive readout, local mode evolution, and adjacent-scale consolidation used by the grounded and symbolic field-agent paths |
| Profile-governed flow surface | `QiFlowStateV3` and an explicit `QiFlowProfile` | `cassi.qi-flow-state.v3` | Hash-bound active-sheet geometry, state admission, and the W1–W3 flow and transport path |

The two surfaces share the packed tensor principle and component order, but they do not share a checkpoint contract. `QiFlowStateV3.to_qi_field_state()` can expose a validated v3 tensor through the v2 state wrapper for an explicitly selected fixed operator; this operation does not convert a v3 checkpoint into v2 or merge their identities. Every reported result therefore names the state surface and schema that produced it.

For a selected surface \(\sigma\), the runtime relation is

\[
\bigl(F_{t+1}^{(\sigma)},\,o_t,\,\rho_t\bigr)
=
\mathcal{T}_{C,\sigma}\!\left(F_t^{(\sigma)},x_t,a_t\right),
\]

where \(C\) is the fixed configuration or profile, \(x_t\) is the typed observation or query, \(a_t\) selects a permitted transition, \(o_t\) is the readout or proposal, and \(\rho_t\) is the deterministic receipt. A read-only query preserves the tensor exactly. A committed transition returns a successor whose identity can be compared with its predecessor.

Both state wrappers validate tensor rank, configured dimensions, batch width, device, data type, and finiteness. The v3 surface additionally validates active sheet extents, per-component and per-complex-pair limits, density, `epsilon2_ema`, exact-zero inactive tails, and the profile's byte budget. These checks make malformed or incompatible state an explicit boundary error.

Persistence retains one complete tensor under the selected surface's fixed identity. The v2 artifact embeds `QiFieldState.field` together with the v2 schema, layout and operator identifiers, complete `QiFieldConfig`, configuration fingerprint, and codebook descriptors and fingerprint. Its base `dump_state_bytes` framing is versioned and fingerprint-bound; it does not store a checksum of the complete serialized artifact. The persistent provider supplies a separate session frame with field-payload, metadata, component-state, shared-state, and whole-frame hashes.

The v3 artifact stores canonical little-endian raw tensor bytes behind a canonical header that binds layout, profile, contract root, state contract, execution schedule, topology, source identity, backend, data type, shape, byte count, and content hashes. A v3 loader rejects legacy, unknown, malformed, or mismatched framing rather than inferring a profile or converting another schema. Restart therefore restores an adaptive object admitted by the same surface, while the integrity guarantees remain those of that surface's actual framing.

Batch width permits several lanes inside a standalone tensor. Scale, component, mode, and active-sheet regions provide fixed views under the selected controller or profile. Grounding, relational evidence, and typed-program mechanisms can organize coordinates inside that state without creating another adaptive identity. Provider-level concatenation is a separate packing boundary described in Section 3.4.

### 3.2 Adaptive content

Adaptive content occupies field coordinates whose interpretation is fixed by the selected operator surface. On the v2 cognition surface, experience changes Yang and Yin amplitudes, their relative phases, their velocity components, cross-scale organization created by consolidation, and the running `epsilon2_ema` plane. These quantities determine availability, coherence, read gates, and later selection; together with typed source trust, field coherence determines write admission. Learning appears as a changed dynamical condition of the tensor.

The transition sequence is operator-specific. In the v2 controller, a deterministic boundary representation is deposited into scale zero, each scale undergoes local damped nonlinear mode evolution, and an explicit consolidation operator can transfer supported symbol bindings to the next slower scale. In the v3 W3 transport path, an explicitly profile-bound, source-free operator advances the active two-dimensional sheet within each scale; source deposition, Yang–Yin conversion, and interscale transfer are inactive in that stage. W3 updates the first eight position and velocity planes and carries the ninth plane unchanged. Later sections attribute each measured behavior to the operator that actually produced it rather than treating every mechanism as active in every transition.

The same accounting applies to higher-level mechanisms. A grounded transition is adaptive when its later availability depends on field coordinates changed by the observed transition. A relational basis is adaptive when evidence accumulated in the field changes which fixed candidate relation is selected. A typed program is adaptive when its support, confirmation, regime evidence, and selection are carried by field values. The candidate grammar can remain fixed while experience determines which member, if any, settles.

This distinction separates adaptive content from exact evidence. A Mnemic revision, byte span, event identifier, world snapshot, or execution receipt has durable identity and may be supplied to the runtime as a current observation. Its factual content remains available through that exact reference. Its learned effect inside Cassi begins when the observation is deposited and persists as field state. The record preserves what occurred; the field carries how that occurrence changes later computation.

Training and inference retain the same state representation within a given surface. Training consists of validated observation transitions and, where requested, consolidation. Inference reads a frozen trained field. Temporary statistics may measure a run or select among explicit candidates, but a statistic that influences future calls must be encoded into field coordinates before the call ends. This rule keeps the adaptive boundary stable as new tasks and surfaces are added.

### 3.3 Fixed computational structure

The v2 cognition surface is fixed by `QiFieldConfig` and `QiFieldPhysicsConfig`. `QiFieldConfig` declares scale count, even mode count, alphabet size, a scale ratio equal to \(\varphi^3\) when no explicit ratio is supplied, one prime per scale, read and emission floors, sensing and consolidation gains, write-trust thresholds, and step counts. `QiFieldPhysicsConfig` declares timestep, fast and slow frequencies, damping, nonlinear gain, amplitude and mean-energy limits, correction tolerance, and velocity weighting. Validation rejects unknown fields and invalid ranges, and canonical configuration serialization produces a fingerprint.

The v3 flow surface is fixed by an explicit `QiFlowProfile`. Its hash-bound projections declare the state layout, active rectangular sheet at each scale, spatial metric and periodic FFT operators, clock interval, transport parameters, execution schedule, topology, source identity, backend and data type, capacity, and state-admission bounds. A v3 state has no implicit default profile: the complete profile identity accompanies every creation, validation, transition, serialization, and restore operation.

On the v2 surface, codebooks are generated deterministically from the configuration together with versioned fixed coefficients and scale-specific permutations. Their descriptors and fingerprints identify the symbol coordinate system used by a checkpoint. Codecs map supported observations into fixed representations. Readout and selection rules convert field measurements into typed results. Protocol schemas validate requests and responses. Policy identifies the transitions available to a caller and the authority required for an action. These structures shape computation consistently while the tensor records the effects of experience.

The state boundary can be summarized as follows:

| Element | Function | Lifetime | Classification |
|---|---|---|---|
| `QiFieldState.field` or `QiFlowStateV3.field` | Carries the complete experience-dependent tensor for the selected runtime surface | Across calls and restarts | Adaptive persistent state |
| `QiFieldConfig` or explicit `QiFlowProfile` | Defines the selected layout, operators, limits, schedule, and runtime identity | Across runs by explicit configuration or profile choice | Fixed and fingerprinted |
| V2 codebooks and permutations; v3 geometry and spectral operators; codecs | Map typed data or physical coordinates into field coordinates | Reconstructed from the selected fixed identity | Fixed or fixed-derived |
| Current observation, query, source, or exact reference | Supplies evidence or forcing for the present transition | Current request | Typed input |
| Readouts, diagnostics, candidate expansions, and temporary statistics | Expose or evaluate the current transition | Current call or receipt | Derived working data |
| Surface-specific checkpoint framing, fingerprints, optional content hashes, and receipts | Bind state to runtime identity and record transitions without adding adaptive content | Durable | Exact provenance |
| Policy and authorization state | Determines which proposal may execute | External or fixed by the active policy | Control boundary |

This classification is behavioral rather than nominal. A cache is derived working data when it can be regenerated from fixed configuration together with the current field or request and carries no experience-dependent value beyond the selected surface's canonical checkpoint. A diagnostic has the same status while later decisions remain independent of its retained value. If a new component acquires experience-dependent persistence within the field-intelligence runtime, that information must move into the active surface's tensor.

### 3.4 State ownership boundary

Cassi uses three kinds of information alongside the adaptive field. **Fixed structure** defines the selected transition law and is identified by configuration, profile, geometry, schedule, or codebook fingerprints. **Exact evidence** preserves observations, revisions, actions, outcomes, and provenance under stable addresses. **Transient derived data** supports the current calculation and can be regenerated from the active field and request. Together, these categories provide the machinery required to operate and audit the field while keeping the location of adaptive persistence unambiguous.

The OpenAI-compatible persistent provider is one implemented boundary with an additional packing contract. `SharedFieldLayout` concatenates three distinct v2-shaped `QiFieldState` components—Phi, counterflow, and a Mnemic-condensation component—into one contiguous session tensor with fixed offsets. Its component wrappers are views into that provider transport tensor, but the components retain distinct shapes, controllers, configuration identities, and state hashes. They are not interchangeable with one standalone `QiFieldController` tensor or with `QiFlowStateV3`, and the condensation component does not replace Mnemic Field's independently authoritative exact records. Terminal, world, particle, and memory integrations follow the architectural rule that an adapter must submit typed evidence to a named field transition and retain the returned successor; each such boundary is described as implemented, measured, or design-stage according to its live evidence.

Training utilities may accumulate counters, losses, or aggregate measurements while processing a corpus. Those quantities support diagnostics and stopping decisions for the current run. Durable learning is represented by the resulting surface-specific field checkpoint. Evaluation utilities similarly retain raw receipts and summaries as evidence while the trained field remains unchanged during read-only trials.

The implementation checks this boundary directly. Dependency and runtime sentinels monitor model-provider calls, optimizer construction, subprocesses, network use, and other alternate compute surfaces in scenarios where the field-only contract applies. Checkpoint inspection accounts for the complete serialized adaptive payload. Restart tests then load only the declared field state and matching fixed configuration or profile before repeating the measured behavior.

### 3.5 Causal ownership criterion

A capability is field-owned when controlled intervention shows that its learned variation resides in the field. Let \(R_{C,\sigma}(F,x)\) denote the readout produced by fixed identity \(C\), runtime surface \(\sigma\), field \(F\), and query \(x\). For a field \(F^\star\) trained on evidence relevant to a capability, construct a counterfactual or lesion \(L(F^\star)\) that removes the corresponding field support while preserving the query, surface, and fixed runtime. The central necessity test is

\[
R_{C,\sigma}(F^\star,x) \ne R_{C,\sigma}\!\left(L(F^\star),x\right)
\]

in the outcome dimension predicted by the lesion. A specificity control applies an unrelated lesion and expects the supported result to remain unchanged. Together, the paired interventions distinguish causal field content from incidental correlation with training history.

Five additional conditions complete the operational test:

1. **Uptake:** the relevant observation produces a valid successor field with a new state identity.
2. **Held-out expression:** the frozen successor field expresses the capability on an observation, combination, or world state withheld from the corresponding training episode.
3. **Persistence:** exact save and reload reproduce the field identity and measured result.
4. **Read-only stability:** inference returns a byte-identical trained field while producing its readout.
5. **Bounded evolution:** repeated transitions remain finite and within the selected surface's declared amplitude and energy limits over the measured horizon.

The fixed controller, codec, query, and policy participate in every result; the field supplies the experience-dependent term in that computation. Field ownership locates learned variation within the complete transition. This formulation supports precise comparisons: the same runtime can be evaluated with an untrained field, a trained field, a targeted lesion, a shuffled field, or a restored checkpoint.

Receipts make each comparison auditable. They identify the predecessor and successor state, configuration and component identities, input or event identity, readout support, selected trajectory or program, mutation status, and abstention reason where applicable. A reported capability is tied to those artifacts and to the held-out condition under which it was expressed.

This operational definition establishes the evidentiary standard used throughout the paper. Section 4 next develops the mathematical structure whose state is being trained, intervened upon, and measured.

## 4. Mathematical Field Model

Cassi's field model has a common storage algebra and surface-specific transition operators. The common algebra defines what occupies the adaptive tensor. The operator identity defines which dynamics, geometry, bounds, and checkpoint rules apply to that tensor. This separation is essential because the v2 cognition controller and the v3 profile-governed flow path share the \([S,9M,B]\) layout without implementing the same evolution law.

Let

\[
s\in\{0,\ldots,S-1\},\qquad
m\in\{0,\ldots,M-1\},\qquad
b\in\{0,\ldots,B-1\}
\]

index scale, mode capacity, and batch lane. A superscript \((2)\) denotes the v2 reference cognition surface where the distinction matters, and \((3)\) denotes the v3 profile-governed flow surface. Quantities without a superscript belong to the shared state algebra.

### 4.1 Yang and Yin complex fields

The first eight component planes form four complex fields. With packed component index \(qM+m\),

\[
\begin{aligned}
Y_{smb}
&=
F_{s,\,0M+m,\,b}
+ iF_{s,\,1M+m,\,b},\\
I_{smb}
&=
F_{s,\,2M+m,\,b}
+ iF_{s,\,3M+m,\,b},\\
V^Y_{smb}
&=
F_{s,\,4M+m,\,b}
+ iF_{s,\,5M+m,\,b},\\
V^I_{smb}
&=
F_{s,\,6M+m,\,b}
+ iF_{s,\,7M+m,\,b}.
\end{aligned}
\]

\(Y\) and \(I\) are the Yang and Yin position sectors; \(V^Y\) and \(V^I\) are their velocity sectors. The implementation stores real and imaginary values explicitly, while complex notation exposes the phase relations used by deposition, evolution, demodulation, and current measurements. Amplitude records the strength of a field configuration, and phase records its orientation relative to fixed codewords or neighboring field values.

The two sectors are computationally coupled rather than treated as independent feature banks. Their difference controls the principal v2 sensing and readout path and the v3 W3 transport path. Their sum-like complementary coordinate supplies the degree of freedom left invariant by a pure differential update. “Yang” and “Yin” name these paired computational sectors; this section does not identify them with the separately authoritative physical field in CassiCosmos.

### 4.2 Differential, complementary, and velocity coordinates

For the configured positive constant \(\varphi\), define the differential position and velocity

\[
D = Y-\varphi I,
\qquad
V^D = V^Y-\varphi V^I.
\]

The normalized complementary coordinates are

\[
C=\frac{\varphi Y+I}{1+\varphi^2},
\qquad
V^C=\frac{\varphi V^Y+V^I}{1+\varphi^2}.
\]

This linear transform is invertible:

\[
\begin{aligned}
Y &= \frac{D}{1+\varphi^2}+\varphi C,
&
I &= C-\frac{\varphi D}{1+\varphi^2},\\
V^Y &= \frac{V^D}{1+\varphi^2}+\varphi V^C,
&
V^I &= V^C-\frac{\varphi V^D}{1+\varphi^2}.
\end{aligned}
\]

A requested differential increment \(\Delta D\) is written by

\[
\Delta Y=\frac{\Delta D}{1+\varphi^2},
\qquad
\Delta I=-\frac{\varphi\,\Delta D}{1+\varphi^2}.
\]

It follows directly that

\[
\Delta(Y-\varphi I)=\Delta D,
\qquad
\Delta(\varphi Y+I)=0.
\]

The v2 controller uses this projection for sensing, correction, local evolution, and consolidation. The v3 W3 operator performs the same coordinate decomposition, evolves \(D\) and \(V^D\), holds \(C\) and \(V^C\) fixed during that transport stage, and reconstructs the Yang and Yin planes through the inverse transform.

The velocity planes make the field a second-order dynamical state. Two tensors can have the same \(Y\) and \(I\) positions while carrying different future trajectories because their \(V^Y\) and \(V^I\) values differ. This distinguishes the state from a static activation table: direction and momentum-like continuation are represented explicitly, although the implementation names these quantities velocities rather than asserting a separate canonical-momentum formalism.

### 4.3 The packed nine-plane state

The component order is fixed:

| \(q\) | Packed plane | Mathematical value |
|---:|---|---|
| 0 | `Y_re` | \(\operatorname{Re}Y\) |
| 1 | `Y_im` | \(\operatorname{Im}Y\) |
| 2 | `I_re` | \(\operatorname{Re}I\) |
| 3 | `I_im` | \(\operatorname{Im}I\) |
| 4 | `VY_re` | \(\operatorname{Re}V^Y\) |
| 5 | `VY_im` | \(\operatorname{Im}V^Y\) |
| 6 | `VI_re` | \(\operatorname{Re}V^I\) |
| 7 | `VI_im` | \(\operatorname{Im}V^I\) |
| 8 | `epsilon2_ema` | Running nonnegative squared-imbalance value |

Let

\[
Z_{smb}=F_{s,\,8M+m,\,b}
\]

denote the ninth plane. On the v2 surface, one evolution step computes the modewise imbalance

\[
\epsilon_{smb}^{\mathrm{mode}}
=
|Y_{smb}|^2-\varphi|I_{smb}|^2
\]

and updates

\[
Z^{n+1}_{smb}
=
\operatorname{clip}_{[0,Z_{\max}]}
\left[
(1-\tau_\epsilon)Z^n_{smb}
+\tau_\epsilon
\left(\epsilon_{smb}^{\mathrm{mode}}\right)^2
\right].
\]

Thus \(Z\) is a running estimate of squared mode imbalance, not the square of the scale-mean imbalance. The v3 state contract retains the same ninth plane and validates its sign and profile-declared upper bound. The W3 source-free transport operator updates components 0 through 7 and carries component 8 forward unchanged; a receipt for W3 therefore cannot attribute a new imbalance estimate to that step.

The derived variables \(D\), \(C\), currents, energies, demodulation scores, and gates are calculated from the nine planes. They are not stored as additional adaptive objects. Both state surfaces expose one contiguous tensor, but their wrappers and serialization identities remain distinct: `QiFieldState.field` belongs to the v2 contract, and `QiFlowStateV3.field` belongs to the explicit v3 profile contract.

### 4.4 Mode capacity and spatial geometry

On the v2 cognition surface, \(M\) is an even mode count. Every mode undergoes local evolution, while the fixed sensing boundary occupies

\[
W=\frac{M}{2}
\]

active complex modes at scale zero. A mode profile

\[
p_m=1+\frac{0.25m}{\max(1,M-1)}
\]

slightly separates their local frequencies. If \(r>1\) is `scale_ratio`, the scale factor is

\[
\alpha_s=r^{-s/2}.
\]

The default v2 configuration sets \(r=\varphi^3\). Raw v2 mode indices are oscillator and codebook coordinates; they do not define a spatial neighborhood, and the v2 `evolve` method contains no spatial derivative or intermode transport.

On the v3 flow surface, the same \(M\) is a per-component storage capacity. The explicit profile assigns each scale an active rectangular sheet

\[
\Omega_s
=
\{0,\ldots,N^y_s-1\}
\times
\{0,\ldots,N^x_s-1\},
\qquad
N_s=N^y_sN^x_s\le M.
\]

The first \(N_s\) values of every component plane are gathered in physical row-major \(y,x\) order and reshaped to \(\Omega_s\). Values from \(N_s\) through \(M-1\) form an inactive packed tail and must be exactly positive zero. The class `QiFlowGeometryV2` supplies this W2 geometry view over a `QiFlowStateV3`; “V2” in that class name denotes the geometry stage, not the v2 checkpoint schema.

The current v3 development profile declares a periodic sheet, a unitary orthonormal FFT2, literal \(i\mathbf{k}\) differentiation, and the Laplacian symbol \(-|\mathbf{k}|^2\). Its default active shape is \(4\times8\) at each of four scales, but the profile—not the tensor class—owns that choice. Rectangular overrides regenerate the linked geometry, capacity, and identity hashes. Batch lanes share the fixed geometry and evolve independently unless an explicitly selected operator couples them.

### 4.5 Scale orientation and fixed codebook coordinates

The v2 scale convention is

\[
s=0:\ \text{fastest and finest},
\qquad
s+1:\ \text{slower and coarser}.
\]

Increasing scale index defines positive interscale direction. This orientation determines the sign convention for `j_scale` and the direction of adjacent-scale consolidation. It does not by itself introduce a coupling term; transfer occurs only when the consolidation operator is called.

V2 symbolic sensing uses a fixed phase codebook rather than a learned embedding. Let \(a\in\{0,\ldots,A-1\}\) be a symbol, \(n\in\{0,\ldots,W-1\}\) an active boundary position, \(P_s\) the prime assigned to scale \(s\), and

\[
\bar a=a+1,\qquad
\pi_s(n)=1+\left[\mu_s(n+1)+\nu_s\right]_{W},
\]

where \((\mu_s,\nu_s)\) is the fixed scale permutation and \([\cdot]_K\) denotes integer remainder modulo \(K\). For the scale's fixed coefficient tuple \((c_{s0},c_{s1},c_{s2},c_{s3})\), the implemented chirp index is

\[
h_{s,a,n}
=
\left[
c_{s0}\bar a^2\pi_s(n)
+c_{s1}\bar a\,\pi_s(n)^2
+c_{s2}\pi_s(n)^2
+c_{s3}\bar a
\right]_{P_s},
\]

and the complex codeword is

\[
U_{s,a,n}
=
\exp\!\left(\frac{2\pi i\,h_{s,a,n}}{P_s}\right).
\]

All primes, coefficients, and permutations are fixed and fingerprinted. A materialized device/dtype codebook is a cache of those constants, not adaptive state.

Demodulation first normalizes the active differential wave by its root-mean-square amplitude:

\[
\sigma_{s,b}
=
\sqrt{
\frac{1}{W}\sum_{n=0}^{W-1}|D_{snb}|^2
+\epsilon_{\mathrm{mach}}
}.
\]

The complex coefficient for symbol \(a\) is then

\[
B_{s,a,b}
=
\frac{1}{W}
\sum_{n=0}^{W-1}
\overline{U_{s,a,n}}\,
\frac{D_{snb}}{\sigma_{s,b}}.
\]

The decoded v2 symbol is the index with maximal \(\operatorname{Re}B_{s,a,b}\). Cross-scale comparisons operate on these common symbol identities and their complex coefficients. They do not compare raw mode \(m\) at one scale with raw mode \(m\) at another, because each scale has a distinct chirp and permutation.

The v3 periodic-sheet coordinate system is separate from this codebook. A v3 W3 spatial current refers to neighboring sheet points and FFT modes. It becomes a symbolic coordinate only through an explicitly identified codec or projection; the shared tensor shape alone does not equate the v2 chirp basis with the v3 spatial basis.

### 4.6 Energy, coherence, imbalance, and gates

The v2 controller computes mode energies

\[
E^Y_{smb}=|Y_{smb}|^2,
\qquad
E^I_{smb}=|I_{smb}|^2
\]

and the following scale-level quantities:

\[
\begin{aligned}
\rho_{sb}
&=
\frac{1}{M}\sum_m
\left(E^Y_{smb}+E^I_{smb}\right),\\
\epsilon_{sb}
&=
\frac{1}{M}\sum_m
\left(E^Y_{smb}-\varphi E^I_{smb}\right),\\
\overline Z_{sb}
&=
\frac{1}{M}\sum_m
\operatorname{clip}_{[0,Z_{\max}]}Z_{smb}.
\end{aligned}
\]

\(\rho\) is the nonnegative position-sector density used for availability and scale weighting. \(\epsilon\) is signed Yang–Yin imbalance. \(\overline Z\) retains the mean of the running squared mode imbalance and therefore penalizes persistent imbalance even when positive and negative mode imbalances cancel in \(\epsilon\).

The implemented coherence quantities are

\[
q^{\max}_{sb}
=
\frac{\rho_{sb}^2}
{\rho_{sb}^2+\varphi^{-2}},
\qquad
q_{sb}
=
\min\!\left(
q^{\max}_{sb},
\frac{\rho_{sb}^2}
{\rho_{sb}^2+\varphi^{-2}+\overline Z_{sb}}
\right),
\]

followed by

\[
\chi_{sb}
=
\begin{cases}
q_{sb}/q^{\max}_{sb},
& \rho_{sb}>\rho_{\min}\ \text{and}\ q^{\max}_{sb}>0,\\
0,&\text{otherwise}.
\end{cases}
\]

The implementation clamps \(q\), \(q^{\max}\), and \(\chi\) to their declared numerical ranges. A scale is available when \(\rho_{sb}>\rho_{\min}\).

Let \(u_b\in[0,1]\) be the typed source-trust value and \(u_{\min}\) the fixed write-trust floor. Only scale zero accepts the v2 boundary write. Before multiplication by `sense_gain`, its gate is

\[
g^{\mathrm{write}}_{0b}
=
\operatorname{clip}_{[0,1]}
\begin{cases}
0,
&u_b<u_{\min},\\
u_b,
&u_b\ge u_{\min}\ \text{and scale 0 is empty},\\
u_b(1-q_{0b}),
&u_b\ge u_{\min}\ \text{and scale 0 is available}.
\end{cases}
\]

Source trust is typed fixed input to the transition. Field coherence supplies the state-dependent term. This gate therefore measures both source admission and how open the existing scale-zero state is to a new deposit.

For adjacent available scales, let \(\hat a_s\) be the decoded symbol and \(b_s=B_{s,\hat a_s,b}\) its complex binding. When both bindings are numerically valid and \(\hat a_s=\hat a_{s+1}\), the phase agreement is

\[
A_{s,b}
=
\frac{1}{2}
\left[
1+
\frac{\operatorname{Re}(\overline b_s b_{s+1})}
{|b_s||b_{s+1}|}
\right].
\]

The implementation assigns \(A_{s,b}=0\) to a valid pair with different decoded symbols and \(A_{s,b}=1\) when the binding denominator is numerically vanishing. Cross-scale consensus \(K_b\) is the mean agreement over adjacent pairs whose two scales are available; it is \(1\) when no such pair exists. The read gate is

\[
g^{\mathrm{read}}_{sb}
=
\mathbf 1_{\mathrm{available}(s,b)}
\chi_{sb}K_b.
\]

The readout uses this gate as an aggregate admission statistic rather than multiplying every demodulated coefficient by it. Define the available-density weight

\[
w_{sb}
=
\frac{
\rho_{sb}\mathbf 1_{\mathrm{available}(s,b)}
}{
\max\!\left(
\sum_r\rho_{rb}\mathbf 1_{\mathrm{available}(r,b)},
\epsilon_{\mathrm{mach}}
\right)
}
\]

and the density-weighted read gate

\[
G_b
=
\sum_s w_{sb}g^{\mathrm{read}}_{sb}.
\]

Let \(\theta_{\mathrm{read}}\) denote `read_threshold`. If \(G_b\ge\theta_{\mathrm{read}}\), the controller aggregates the demodulated coefficients with \(w_{sb}\); otherwise every contribution weight is zero:

\[
\beta_{sb}
=
\mathbf 1_{G_b\ge \theta_{\mathrm{read}}}w_{sb},
\qquad
\mathcal B_{ab}
=
\sum_s\beta_{sb}B_{s,a,b}.
\]

The fixed scale-zero codebook reconstructs the emitted boundary wave from \(\mathcal B\). Its root-mean-square flux must also reach `emission_floor`; otherwise the readout reports unavailable support and returns zero wave and score tensors. `read_threshold` therefore applies to the aggregate coherence gate \(G_b\), not directly to total density, and per-scale read gates do not reweight the admitted coefficient sum.

Consolidation from scale \(s\) to \(s+1\) uses

\[
g^{\mathrm{cons}}_{s,b}
=
\mathbf 1_{\mathrm{available}(s,b)}
\chi_{s,b}\,
\widetilde A_{s,b}\,
\mathbf 1_{j^{\mathrm{scale}}_{s,b}\ge-\delta_{\mathrm{num}}}\,
\left(1-q_{s+1,b}\right)
\eta_{\mathrm{cons}},
\]

where \(\widetilde A_{s,b}=1\) when the target scale is empty and otherwise equals the adjacent-scale phase agreement, \(\delta_{\mathrm{num}}\) is the fixed correction tolerance, and \(\eta_{\mathrm{cons}}\) is `consolidation_gain`. The source must be available and coherent, the current must not point against the declared positive direction beyond tolerance, and the target must remain open.

The optional v2 correction operator compares a target boundary wave \(U^\star\) with the current emitted wave \(\widehat U\). Let \(\eta_{\mathrm{corr}}\) be the configured gain and \(\eta_{\mathrm{caller}}\in[0,1]\) the optional caller multiplier. The implemented gain is

\[
g^{\mathrm{corr}}_b
=
\eta_{\mathrm{corr}}\eta_{\mathrm{caller}}
\begin{cases}
1,
&\text{if scale 0 is unavailable},\\
1-q_{0b},
&\text{if scale 0 is available}.
\end{cases}
\]

An empty scale is therefore fully open to a correction deposit; availability does not suppress the write. The reported correction energy is

\[
E^{\mathrm{corr}}_b
=
\left(g^{\mathrm{corr}}_b\right)^2
\frac{1}{W}\sum_n
\left|U^\star_{nb}-\widehat U_{nb}\right|^2.
\]

The v2 balance-conversion operator is also explicit. For each mode it forms

\[
\rho^{\mathrm{mode}}=E^Y+E^I,\qquad
\epsilon^{\mathrm{mode}}=E^Y-\varphi E^I,
\]

\[
q^{\mathrm{mode}}
=
\frac{(\rho^{\mathrm{mode}})^2}
{(\rho^{\mathrm{mode}})^2+\varphi^{-2}+(\epsilon^{\mathrm{mode}})^2},
\]

and proposes the density transfer

\[
\Delta e
=
\Delta t\,k_{\mathrm{conv}}
\left(1-q^{\mathrm{mode}}\right)
\epsilon^{\mathrm{mode}}.
\]

The transfer is clipped toward the equilibrium value

\[
\Delta e_{\mathrm{eq}}
=
\frac{\epsilon^{\mathrm{mode}}}{1+\varphi}
\]

and to the available source and amplitude capacities. Positive transfer moves density from Yang to Yin; negative transfer moves it from Yin to Yang. Amplitude rescaling preserves each nonzero sector's phase; a zero-amplitude recipient inherits the other sector's phase as its fallback direction. The update keeps \(E^Y+E^I\) invariant up to numerical precision. This operator is not called by the base v2 `evolve` method or its canonical `cycle`.

### 4.7 Temporal, interscale, and spatial currents

The v2 temporal differential current is

\[
j^{\mathrm{temporal}}_{sb}
=
\frac{1}{M}
\sum_m
\operatorname{Im}
\left(
\overline{D_{smb}}\,V^D_{smb}
\right).
\]

It measures phase rotation of the differential coordinate through time. The adjacent-scale current is evaluated after demodulation into the common symbol coordinate. If \(\mathbf b_s\) is the one-hot complex binding vector containing only scale \(s\)'s strongest decoded coefficient, then

\[
j^{\mathrm{scale}}_{s,b}
=
\operatorname{Im}
\left\langle
\mathbf b_s,\mathbf b_{s+1}
\right\rangle
=
\operatorname{Im}
\sum_a
\overline{b_{s,a,b}}b_{s+1,a,b}.
\]

Positive sign follows the fast/fine-to-slow/coarse orientation. A symbol mismatch occupies different one-hot coordinates and contributes zero interscale current, while the separate agreement rule assigns that valid mismatch zero agreement.

The v3 W3 operator defines spatial quantities on each periodic sheet. Let

\[
w_D=\frac{1}{1+\varphi^2},
\qquad
\dot D=V^D,
\]

and let \(\nabla_s\) be the profile's literal spectral gradient. For cell area \(\Delta A_s\), the diagnostic energy is the discrete functional

\[
\mathcal E_s
=
w_D\Delta A_s
\sum_{\mathbf x\in\Omega_s}
\left[
\frac{1}{2}|\dot D|^2
+\frac{c_s^2}{2}|\nabla_sD|^2
+\frac{\omega_s^2}{2}|D|^2
+\frac{\kappa_s}{4}|D|^4
\right].
\]

The phase charge is

\[
Q_s
=
w_D\Delta A_s
\sum_{\mathbf x\in\Omega_s}
\operatorname{Im}
\left(\overline D\,\dot D\right).
\]

The pointwise spatial current and energy flux are

\[
\mathbf J_s
=
-w_Dc_s^2
\operatorname{Im}
\left(\overline D\,\nabla_sD\right),
\]

\[
\mathbf S_s
=
-w_Dc_s^2
\operatorname{Re}
\left(\overline{\dot D}\,\nabla_sD\right).
\]

The internal W3 measurement evaluates total energy, phase charge, maximum current, integrated \(x\)- and \(y\)-currents, maximum energy flux, and maximum amplitude. The current `QiFlowDiagnosticsW3` surface retains the energy, phase charge, maximum current, maximum amplitude, and closure quantities; the helper's integrated-current and energy-flux values are not copied into the final diagnostic object. For the source-free damped step, the expected phase charge is

\[
Q_s(t+h)=e^{-\gamma_sh}Q_s(t),
\]

and the returned diagnostics record the residual from that expectation. They also record energy before and after, damping work, local split work, and the implemented closure residual. These measurements are derived result data; none becomes another adaptive state channel.

The two current families answer different questions. V2 `j_scale` measures oriented phase flow between demodulated symbol bindings on adjacent timescales. V3 \(\mathbf J_s\) measures spatial flow inside one active periodic sheet. Neither quantity can substitute for the other without a defined and tested projection.

### 4.8 Implemented evolution operators

**V2 local mode evolution.** For scale \(s\) and mode \(m\), define

\[
\Omega_{sm}^2
=
\max\!\left(
\omega_{\mathrm{fast}}^2\alpha_sp_m,
\omega_{\mathrm{slow}}^2
\right),
\]

\[
\gamma_s
=
\max\!\left(
\gamma_{\mathrm{fast}}\alpha_s,
\gamma_{\mathrm{slow}}
\right).
\]

With timestep \(\Delta t\) and nonlinear gain \(\lambda\), one implemented step is

\[
V^{D,n+1}_{smb}
=
e^{-\gamma_s\Delta t}V^{D,n}_{smb}
+\Delta t
\left[
-\Omega_{sm}^2D^n_{smb}
-\lambda|D^n_{smb}|^2D^n_{smb}
\right],
\]

\[
D^{n+1}_{smb}
=
D^n_{smb}
+\Delta t\,V^{D,n+1}_{smb}.
\]

The controller applies the corresponding differential deltas to \(Y,I,V^Y,V^I\), updates \(Z\), and enforces v2 bounds after every requested settle step. This is a local damped nonlinear oscillator update at every \((s,m,b)\). It contains no FFT, spatial Laplacian, or direct interscale term.

Sensing precedes this evolution. For active scale-zero boundary wave \(U\), the differential update has the interpolation form

\[
D'_{0nb}
=
D_{0nb}
+\eta_{\mathrm{sense}}g^{\mathrm{write}}_{0b}
\left(U_{nb}-D_{0nb}\right),
\qquad n<W,
\]

and the four scale-zero velocity planes on those active modes are multiplied by one minus the same effective gain. Correction applies an analogous bounded residual update after readout.

Consolidation is a separate adjacent-scale operation. It demodulates the strongest source symbol, reconstructs that symbol in the target scale's own codebook, scales its amplitude by \(r^{-1/2}\), and interpolates the target differential coordinate under \(g^{\mathrm{cons}}\). It damps the target differential velocity toward zero through the same gated interpolation and moves the target \(Z\) values toward the source values under that gate. The base v2 `cycle` is therefore:

\[
\text{sense}
\rightarrow
\text{local evolve}
\rightarrow
\text{emit}
\rightarrow
\text{optional correct}
\rightarrow
\text{consolidate}.
\]

`convert_balance` is available as a separate explicit transition and is absent from this base sequence.

**V3 W3 periodic-sheet transport.** The v3 W3 operator is a separate, profile-bound transport surface rather than the ordinary v2 controller's evolution. It is source-free: `transition_v3_transport` rejects any supplied non-null `source` before constructing the geometry context or a candidate state. On an active v3 sheet, the frozen W3 equation represented by the split operator is

\[
\ddot D
+\gamma_s\dot D
-c_s^2\nabla_s^2D
+\omega_s^2D
+\kappa_s|D|^2D
=0.
\]

The current development-profile defaults are:

| Scale \(s\) | \(c_s\) (m s\(^{-1}\)) | \(\omega_s\) (rad s\(^{-1}\)) | \(\gamma_s\) (s\(^{-1}\)) | \(\kappa_s\) |
|---:|---:|---:|---:|---:|
| 0 | 0.15 | 0.08 | 0.20 | 0.020 |
| 1 | 0.10 | 0.06 | 0.15 | 0.015 |
| 2 | 0.05 | 0.04 | 0.10 | 0.010 |
| 3 | 0.025 | 0.02 | 0.075 | 0.005 |

These values describe the current default profile, not an invariant of `QiFlowStateV3`. The profile also restricts one step \(h\) to the closed interval from \(10^{-3}\) to \(10^{-2}\) seconds.

For each scale, W3 performs a symmetric local/spectral split:

1. Apply a nonlinear half-kick to \(V^D\):

   \[
   V^D
   \leftarrow
   V^D
   -\frac{h}{2}\kappa_s
   \mathcal R_s
   \left(
   |\mathcal I_sD|^2\mathcal I_sD
   \right),
   \]

   where \(\mathcal I_s\) and \(\mathcal R_s\) are the profile-bound pseudospectral interpolation and restriction operators.

2. Propagate \(D,V^D\) for \(h/2\) with the exact damped linear spectral solution.

3. Apply the declared center stage. In W3 this stage is an identity: source admission is false and Yang–Yin conversion remains inactive.

4. Repeat the exact damped linear spectral propagation for \(h/2\).

5. Apply the second nonlinear half-kick.

For every FFT mode \(\mathbf k\), the linear substep solves

\[
\ddot{\widehat D}_{\mathbf k}
+\gamma_s\dot{\widehat D}_{\mathbf k}
+\Lambda_{s,\mathbf k}\widehat D_{\mathbf k}
=0,
\qquad
\Lambda_{s,\mathbf k}
=
c_s^2|\mathbf k|^2+\omega_s^2.
\]

Writing \(\alpha_s^\gamma=\gamma_s/2\), the implementation classifies

\[
\Delta_{s,\mathbf k}
=
\Lambda_{s,\mathbf k}
-(\alpha_s^\gamma)^2
\]

as underdamped, critical, or overdamped within a data-type-scaled tolerance. It then evaluates the corresponding analytic \(2\times2\) propagator with sine and cosine, the critical limit, or hyperbolic sine and cosine. Each branch includes the factor \(e^{-\alpha_s^\gamma h/2}\). The two half-propagations apply damping over one full \(h\).

After the split, W3 reconstructs

\[
\begin{aligned}
Y' &= w_DD'+\varphi C,
&
I' &= C-\varphi w_DD',\\
V^{Y\prime} &= w_DV^{D\prime}+\varphi V^C,
&
V^{I\prime} &= V^C-\varphi w_DV^{D\prime},
\end{aligned}
\]

with \(C\) and \(V^C\) copied from the predecessor. An accepted step returns a seven-row stage ledger containing the schedule identity, before/after energy, local work, damping work, zero source work, zero conversion work, and numerical residual. This profile-bound W3 operator acts independently within each scale; it does not implement v2 codebook consolidation or an interscale spatial transfer.

### 4.9 Bounds, clipping, acceptance, and rejection

The two surfaces make different numerical commitments.

The v2 controller uses a bounded-update law. After a state-changing operation, each of the four complex position or velocity pairs is first radially rescaled when its magnitude exceeds `max_mode_amplitude`. Let \(\widetilde F\) denote those pair-bounded first eight planes. The controller then computes, for each scale and batch lane,

\[
\overline E_{sb}
=
\frac{1}{M}
\sum_{m=0}^{M-1}
\sum_{q=0}^{7}
\widetilde F_{s,\,qM+m,\,b}^{\,2},
\]

and applies the broadcast factor

\[
a_{sb}
=
\min\!\left(
1,
\sqrt{
\frac{E_{\max}}
{\max(\overline E_{sb},\epsilon_{\mathrm{mach}})}
}
\right)
\]

to all eight planes and all modes in that scale/lane. Thus `max_mean_energy` bounds the mean across modes for each \((s,b)\), not each \((s,m,b)\) independently. The \(Z\) plane is then clamped to \([0,\texttt{epsilon\_clip}]\). Sensing, correction, consolidation, and conversion also clip their gates or transfers to the declared admissible ranges. Invalid rank, shape, batch width, data type, device, non-finite input, configuration, codebook identity, or checkpoint schema raises an error before the returned state becomes active.

The v3 surface uses profile admission and transactional rejection. Before a transition, it validates exact shape, active geometry, backend, data type, batch capacity, raw-byte budget, per-component absolute limits, four complex-pair amplitude limits, active density, nonnegative bounded \(Z\), finiteness, and an exact-zero inactive tail. W3 additionally rejects a non-null source, a duration outside the profile interval, a predecessor above its amplitude cap, or a contract/profile mismatch.

W3 constructs its candidate from a clone of the predecessor. After transport it rejects a non-finite candidate, an amplitude-cap violation, any nonzero inactive-tail value, or any violation of the base v3 state contract. A rejected `QiFlowStepW3` retains the predecessor, exposes no candidate, marks the step noncommittable, and records a failure reason. An accepted step exposes a separately validated candidate and a receipt with the predecessor and candidate identities. It does not silently clip a failed candidate into compliance.

This distinction gives later experiments an exact interpretation. A v2 result follows a fixed bounded map whose clipping is part of the declared operator. A v3 W3 result follows a profile-bound propose-and-admit transaction whose failed candidate cannot replace its predecessor. In both cases, a state identity refers to the full packed adaptive tensor under one named operator and checkpoint contract.

## 5. The Cassi Computational Cycle

On the grounded-agent and persistent-provider cognition surfaces, a complete application cycle is assembled from field transitions and typed boundaries rather than supplied by one universal method call. The low-level v2 `QiFieldController.cycle` is one narrower operator: it implements sensing, local evolution, emission, optional correction, and consolidation. The grounded agent, Phi text engine, provider, and counterflow runtime expose different subsets and compositions of the wider application lifecycle under the same state-ownership rule. The v3 W3 operator remains a separate source-free transport surface; it can advance an admitted field state, but it does not by itself sense an observation, choose an action, or learn an observed consequence.

Let the state at an application boundary be

\[
\mathcal S_t
=
\left(
F_t;\,
W_t,\,
J_t,\,
\mu_t;\,
C,\,
P
\right),
\]

where \(F_t\) is the active adaptive field tensor, \(W_t\) is independently authoritative world state where a world is present, \(J_t\) is exact journal or evidence state, \(\mu_t\) is nonadaptive session metadata, \(C\) is the fixed controller, codec, and geometry identity, and \(P\) is fixed policy and authorization configuration. The semicolon separates adaptive field state from exact, derived, and fixed context. A causal episode can change \(F_t\) and an authorized external transition can change \(W_t\); journal records and metadata preserve identity without becoming a second learned model.

For a grounded or provider cognition transaction that progresses from external observation through authorized execution, observed consequence, durable learning, and persistence, the reference lifecycle has ten logical stages:

| Stage | Operation | State effect |
|---:|---|---|
| 1 | Sense | Acquire an exact typed observation from a declared boundary |
| 2 | Encode | Map that observation through a fixed codec |
| 3 | Deposit | Produce a candidate field successor containing the sensed event |
| 4 | Evolve | Apply the selected bounded field operator or settlement schedule |
| 5 | Read | Measure the resulting field against fixed query coordinates |
| 6 | Select | Choose a uniquely supported eligible result or abstain |
| 7 | Propose | Bind an inert typed proposal to field, policy, and source identity |
| 8 | Observe result | Accept an exact acknowledgment and successor observation after execution |
| 9 | Consolidate | Encode the observed causal sequence into the field through an explicit learning operator |
| 10 | Persist | Atomically replace the applicable checkpoint and emit receipts |

Not every call traverses all ten stages. A pure diagnostic stops after read. Functional text generation senses a prompt and constructs a successor live context while preserving its input object and learned trajectory tape; that successor becomes persistent only when a provider checkpoint accepts it. A prediction stops before external execution and consequence learning. A rejected or ambiguous request ends in abstention. The ten-stage sequence is therefore a scoped reference path for an executed and learned cognition transaction, not a contract imposed on every interface and not the lifecycle of W3 transport.

### 5.1 Sensing and fixed encoding

Sensing begins at an authoritative boundary. The boundary returns an observation and enough identity to establish what was observed. Depending on the live path, that value can be a deterministic-world byte packet, an exact journal reference, a validated message sequence, a structured action acknowledgment, or a typed before/after record. The field does not reconstruct exact source truth from a latent approximation when the source record remains available.

For observation \(o_t\), request \(\iota_t\), and boundary type \(\tau_t\), a fixed codec produces

\[
\xi_t
:=
\mathcal C_C(\tau_t,o_t,\iota_t).
\]

\(\mathcal C_C\) is deterministic under the fixed identity \(C\). It can emit integer symbols, phase codewords, bounded numeric channels, exact addresses, or another declared field-boundary representation. It has no learned parameters and cannot retain experience between calls.

In the controlled grounded path, `DeterministicQiWorld.observe_proprioception()` supplies the predecessor observation as exact bytes. `CassiGroundedEventCodec.instruction_symbols()` combines those bytes with the instruction and maps them to fixed event identifiers. Outcome sensing later uses a separate fixed sequence containing the acknowledgment status and successor observation. The codec therefore preserves the causal roles of predecessor, instruction, action, acknowledgment, and successor rather than flattening them into one untyped string.

The OpenAI-compatible text path first validates the complete message sequence, role labels, deterministic request parameters, output bound, session identifier, and final user role. `CassiFieldTextCodec.encode_messages()` then produces the fixed prompt-symbol sequence. On a resumed provider session, only the newly supplied final message is passed to generation because prior interaction context already resides in the persisted Phi component.

Exact ingress and world-result paths apply stricter identity checks before field admission. Journal references bind content and codec identity. Counterflow observed commits bind stream identifier, monotonically increasing sequence, event identifier, before and after revisions, status, and a declared authorization path. A mismatched event, revision, or status is rejected before the field changes.

Source trust belongs to this typed boundary data when the selected operator accepts it. For example, the base v2 boundary wave combines an input trust value with field coherence through \(g^{\mathrm{write}}\). The grounded trajectory and Phi text codecs use their own fixed admission rules and do not silently inherit that scalar gate. “Sense” therefore denotes the validated application boundary; the exact deposition law remains operator-specific.

### 5.2 Deposition and candidate state

Encoding alone does not alter the field. Deposition applies the selected write operator to a validated predecessor:

\[
\widetilde F_t
=
\mathcal D_{C,\kappa}
\left(
F_t,\xi_t
\right),
\]

where \(\kappa\) identifies the active controller or application law. The returned \(\widetilde F_t\) is a candidate successor. The implemented transition methods used by these paths allocate or clone successor storage and leave the supplied predecessor unchanged, permitting a caller to compare state hashes and discard a failed branch.

The base v2 `sense_wave` path uses the coherence- and trust-dependent interpolation derived in Section 4.6. It writes the first \(W=M/2\) differential modes at scale zero and damps their velocity planes by the same effective gain. `sense_symbols` first maps symbols through the fixed scale-zero codebook and then invokes that wave deposit.

The grounded trajectory path uses a different v2-shaped operator. For one event symbol \(a\), `CassiQiTrajectoryLaw.sense_event()` shifts each scale's live context by one position, inserts the fixed phase for \(a\) at age zero, preserves the designated live-register velocity coordinates, and writes the event phase into the newest velocity coordinate. Repeating this operation deposits an instruction, action, or observed outcome as an ordered event sequence. This is a field transition over `QiFieldState`, not a call to the oscillator controller's `sense_wave`.

The Phi text path similarly calls `_sense_events()`, but each prompt symbol advances the profile-bound Phi controller through eight fixed `tick` steps. The resulting prompt context occupies the same Phi field tensor used for continuation. No embedding table is trained during that operation, and no hidden prompt cache becomes adaptive state.

Deposition and durable learning are distinct. A sensed event can change live field context and therefore the complete state hash without changing the learned-memory or trajectory-tape hash. The grounded query methods verify the trained-memory hash across inference; Phi generation verifies that its successor preserves `tape_sha256`. An explicit learning or observed-consolidation operation is required before new experience changes those memory coordinates.

W3 cannot serve as a deposition operator. `transition_v3_transport` rejects every non-null source before constructing its geometry context or candidate. A pipeline that combines v3 transport with observation must therefore identify a separate source-admission operator and its profile rather than passing observations through W3 implicitly.

### 5.3 Evolution and settlement

After deposition, the selected operator advances the candidate toward a readable state:

\[
F_t^{\mathrm{settled}}
=
\mathcal T_{C,\kappa_n}
\circ\cdots\circ
\mathcal T_{C,\kappa_1}
\left(\widetilde F_t\right).
\]

The operator sequence and stopping rule are part of \(C\). They are not chosen by a learned scheduler outside the field.

For the base v2 oscillator, evolution is the bounded local \(D,V^D\) update in Section 4.8, repeated for the requested number of settle steps. Adjacent-scale transfer remains a later explicit consolidation operation. For W3, evolution is the profile-bound source-free split step on each periodic sheet, followed by candidate admission or rejection.

The grounded language runtime uses field trajectory operators rather than the base oscillator cycle. `advance_context()` shifts the encoded event history, `sense_event()` records an incoming event, and `react_event()` records a selected outgoing event with a signed reaction magnitude derived from its measured outgoing work. Candidate continuation scoring advances temporary contexts without committing them. `learn_sequence()` is a separate memory-writing operator.

The bilateral counterflow runtime has another explicit settlement law. It starts a thought from encoded before/goal values and eligible constraints, advances the fixed controller through `run_until_closed()`, and renders symbols or actions only after the state reports unique settlement. Its planning result is derived and nonpersistent; the provider verifies that planning leaves both the primary Phi component and the canonical counterflow component hash unchanged.

These paths share a lifecycle but not one numerical equation. “Evolution” means execution of the named field operator until its fixed horizon, closure state, output terminator, or rejection condition. Each receipt must therefore identify the operator and profile that produced the result.

### 5.4 Query-dependent readout

A query defines a fixed interrogation of the field. Let

\[
\mathcal K_C(q)
=
\{k_1,\ldots,k_N\}
\]

be the finite candidate set generated by the codec, action catalog, relation catalog, grammar, or output alphabet. Readout computes

\[
\mathcal R_C(F,q)
:=
\left\{
\left(k,w_k,d_k\right)
:
k\in\mathcal K_C(q)
\right\},
\]

where \(w_k\) is field-derived support or work and \(d_k\) contains deterministic diagnostics such as availability, event work, basin identity, or source addresses.

In the grounded action port, `candidate_sequence_work()` evaluates every fixed action-symbol sequence against the same memory and initial context. For a candidate \(k=(a_1,\ldots,a_L)\),

\[
W(k\mid F,q)
=
\sum_{j=1}^{L}
\max\!\left(
0,\,
\operatorname{port}_F
\left(
a_j\mid h_j
\right)
\right),
\]

where \(h_j\) is the temporary context obtained by advancing through the preceding candidate symbols. The method returns total and per-event work but does not write that branch into the supplied state. Reference, relation, discourse-route, and typed-program selectors use the same pattern with their own fixed candidate sets and margins.

Phi text generation performs an autoregressive field read without a probabilistic model. `next_symbol_scores()` reads the latest exact continuation from the learned trajectory tape. At each output position, the fixed UTF-8 codec masks symbols that cannot extend the current byte sequence legally, and deterministic `argmax` chooses among the remaining field scores. The selected symbol is sensed into the working field before the next position. An `END_TURN` symbol completes the reply; reaching the output limit returns the last valid UTF-8 prefix and its corresponding safe state.

Three read semantics remain distinct:

1. `QiFieldController.emit()` and pure diagnostics preserve the complete input tensor.
2. Candidate probes use temporary cloned or batched branches and discard them after scoring.
3. Session-level query or generation may return and persist a successor live-context state while proving that trained-memory or trajectory-tape coordinates remain unchanged.

`CassiFieldAgent.query()` belongs to the third category, not the first: it senses a spatial cue, commits the selected relation, sets the active reference, and saves the successor while requiring the trained-memory hash to remain unchanged. `PhiHarmonicTextEngine.generate()` likewise leaves its input object and learned trajectory tape unchanged while returning a successor containing the prompt and output ticks. Generation itself does not persist that result; the provider may subsequently publish `result.state` at its checkpoint boundary.

The third case is query-dependent state evolution, but it does not create a second adaptive query store. Working context remains in the field or is reproducible from the predecessor and request; learned variation remains confined to the declared field-memory coordinates.

### 5.5 Selection, bounded output, and abstention

Selection applies fixed eligibility and decisiveness rules to readout:

\[
k^\star
=
\operatorname*{arg\,max}_{k\in\mathcal K_C(q)}
w_k.
\]

A result is emitted only if the winner is supported, eligible, and sufficiently separated from the runner-up. Otherwise the runtime returns a typed abstention, clarification, unavailable status, or bounded error according to that interface.

For grounded action selection, candidates are sorted by descending work and then by action identifier for deterministic ties. Let \(w_{(1)}\) and \(w_{(2)}\) be the largest two work values. The live rule accepts the winner only when

\[
w_{(1)}>0
\]

and

\[
\Delta
=
w_{(1)}-w_{(2)}
>
\max\!\left(
10^{-6},
10^{-6}|w_{(1)}|
\right).
\]

Failure to satisfy either condition raises an unresolved-port result. `CassiFieldAgent.turn()` converts unresolved semantic routing and supported field-language errors into an explicit abstention with the reply “I cannot resolve that request.” It verifies that the field, trained memory, and world remain unchanged when failure occurs before a committed transition.

Counterflow planning distinguishes several other conditions. `plan_counterflow()` reports `persistent_state: false`, and the provider verifies that neither the primary Phi component nor the canonical counterflow component changed during planning. No observations produce `no_transition_data`; an empty eligible-basin set produces `no_eligible_transition_data`; both return a structured abstention rather than an invented plan. A settled result may include symbolic output or an inert action proposal, but planning does not commit either field component. Policy filters candidate basins and action kinds before a proposal is returned.

Phi generation uses a different bounded-output contract. It requires a learned continuation beginning with the assistant-role symbol and at least one valid UTF-8 port at every step. Absence of either is an explicit field error, not a model fallback. Exhausting `max_output_symbols` returns the last valid UTF-8 prefix with stop reason `max_output_symbols`; reaching `END_TURN` returns stop reason `end_turn`.

Capacity exhaustion is also explicit. `CassiQiTrajectoryLaw.learn_sequence()` rejects an episode when no configured scale contains sufficient free contiguous field capacity. The runtime asks for a larger mode count or fewer learned episodes rather than overwriting an untracked memory region.

### 5.6 Proposal and action boundary

Selection does not grant authority to act. The deployment-facing counterflow boundary returns `TypedActionProposal`, an inert value containing:

- the settled basin path;
- exact typed action descriptors;
- a declared authorization path;
- the hash of the field state that produced the proposal.

Before returning it, `propose_typed_actions()` verifies that the field uniquely settled, every basin is eligible, every action kind is permitted, policy authority reaches each descriptor's required threshold, precondition and effect addresses form a continuous chain, the final effect reaches the declared goal, and a nonempty authorization path exists. `propose_predicted_action()` applies the corresponding policy, exact-transition, and authorization-path checks to one action selected by a frozen transition prediction. Both functions return inert proposals and never execute them. The declared path records where authorization must occur; it is not itself proof that a person or external authority approved execution.

The persistent provider's world-turn path follows the same separation. It validates or deterministically derives a typed particle program and returns clarification when the request does not resolve. It first publishes the reconstructed field exchange, then performs a separate frame save that adds the request-identity response ledger. Neither save executes the particle program. A separate executor can act only under the surrounding host's authorization policy.

Formally,

\[
\pi_t
=
\mathcal P_{C,P}
\left(
F_t^{\mathrm{settled}},
q_t
\right)
\]

produces a proposal, while

\[
\left(
W_{t+1},
\omega_t
\right)
=
\mathcal X_{\alpha_t}
\left(
W_t,\pi_t
\right)
\]

belongs to the authorized executor \(\mathcal X\) under authorization \(\alpha_t\). The execution receipt \(\omega_t\) does not become an observed field consequence until the result boundary validates it against the proposal and world identity.

`CassiFieldAgent.step()` is a controlled-test realization with a narrower trust boundary. The agent owns its deterministic `DeterministicQiWorld`, constructs a `QiActionCommand` bound to world, episode, logical tick, action descriptor, field-state hash, current world hash, actuator, body frame, session, and cycle number, and then calls `world.step()` inside the same process. This internal execution demonstrates causal grounding in the laboratory world; it does not make the general provider proposal self-authorizing.

Prediction keeps the boundary closed. `CassiFieldAgent.predict_action()` selects an action from a sensed cue but does not commit that action, call `world.step()`, sense an outcome, consolidate an episode, or save a successor. It verifies that the trained-memory hash, complete state hash, and world snapshot remain unchanged.

### 5.7 Observed consequence and consolidation

Learning follows observation rather than expectation. A predicted effect, rendered plan, or successful proposal does not enter field memory as an accomplished fact. The consequence stage requires an exact acknowledgment and successor observation from the acting boundary.

In one enacted grounded step, `CassiFieldAgent.step()` performs the following sequence:

1. Snapshot the predecessor field hashes, trained-memory hash, and complete world state.
2. Observe predecessor proprioception.
3. Sense the observation and instruction.
4. Select and commit the action event inside the field.
5. Construct the hash-bound `QiActionCommand`.
6. Execute that command in `DeterministicQiWorld`.
7. Observe successor proprioception and the world acknowledgment.
8. Sense the acknowledgment and successor observation.
9. Optionally consolidate the complete causal episode.
10. Write the transition register and save the field/world session.

Let \(p_t\) be the encoded causal prefix and \(e_t\) the complete observed episode:

\[
p_t
=
\mathcal C_C(o_t,r_t)
\mathbin{\Vert}
\mathcal C_C(a_t),
\]

\[
e_t
=
p_t
\mathbin{\Vert}
\mathcal C_C(\omega_t,o_{t+1}),
\]

where \(\Vert\) denotes ordered concatenation. `consolidate_grounded_episode()` first writes \(p_t\) with unit strength, then writes \(e_t\) with a residual-dependent trajectory strength.

If \(w_d\) is the predicted work of the desired observed action, \(w_c\) is the strongest competing work, and \(\delta\) is the required selection margin, the implemented residual is

\[
r_t
=
\operatorname{clip}_{[0,1]}
\left[
\frac{
w_c+\delta-w_d
}{
\max(1,|w_d|,|w_c|)
}
\right].
\]

With configured floor \(\eta_{\min}\), the complete-episode strength is

\[
\eta_t
=
\eta_{\min}
+(1-\eta_{\min})r_t.
\]

The consolidation receipt records desired action, residual, trajectory strength, event count, and trained-memory hashes before and after. When `learn=False`, the agent still senses the exact observed outcome into live context but skips the episode-memory write.

The provider counterflow path splits proposal and observation across requests. `plan_counterflow()` is nonmutating. `commit_counterflow()` accepts an observed commit only when event identity, before and after revisions, status, sequence, stream, and authorization path agree with the typed observation. Action observations admit matching `completed` or `error` outcomes; exact non-action Mnemic updates require `committed`. The runtime encodes the observed before and after addresses and applies `observe_transitions()` to the counterflow component. An error outcome can therefore be learned as the transition that actually occurred without being relabeled as success.

Per-stream watermarks make the commit idempotent. An exact duplicate returns status `duplicate` and preserves the existing field. A stale or conflicting sequence is rejected. A new valid commit replaces only the counterflow component in the shared provider tensor; the provider verifies that the Phi component hash remains unchanged.

### 5.8 Transactional persistence and recovery

Persistence turns an admitted candidate into the next process-visible state. The commit object can be written abstractly as

\[
\Gamma_t
=
\left(
F_{t+1},
W_{t+1},
\mu_{t+1},
R_t^{\mathrm{commit}}
\right),
\]

where \(R_t^{\mathrm{commit}}\) contains the surface-specific state hashes, world or source identity, transition diagnostics, and checkpoint identity. Exact evidence remains in its own journal or world store; the checkpoint carries the field and the metadata required to validate the next call.

The grounded agent's `_save()` checks that session counters agree with the world's logical tick, compacts the bounded world history, recomputes the world-snapshot hash, and passes the field plus metadata to `CassiQiSessionStore.save()`. That store serializes the field under the controller's versioned v2 identity, writes a temporary file, flushes and synchronizes it, and replaces the session path with `os.replace()`. The agent assigns its in-memory field and counters only after `save()` returns. If a caught step failure occurs, it restores the predecessor world snapshot; a failed atomic replacement leaves the prior checkpoint file intact.

The persistent provider serializes the full `SharedFieldLayout` tensor under a per-session lock. A component transition is inserted into a newly packed shared state, metadata and component hashes are updated, and each `store.save()` writes one complete frame through the same temporary-file, flush, synchronization, and atomic-replace pattern. Candidate or save failure within a single-save component operation leaves the frame visible before that save boundary intact. Provider API calls need not be one encompassing transaction, however: `world_turn()` first saves the reconstructed Phi exchange and then separately saves the request-identity response ledger. If that later ledger save fails, the earlier field frame may already be process-visible.

The principal commit invariants are:

1. **Input immutability:** candidate constructors in the implemented cycle paths do not mutate the supplied predecessor object.
2. **Identity continuity:** receipts bind state-in and state-out hashes to the named configuration, profile, codec, or provider fingerprint.
3. **Read-path preservation:** pure reads preserve the whole field; query paths that advance live context preserve the declared trained-memory or tape hash.
4. **World separation:** prediction and planning do not advance authoritative world state.
5. **Observed-result binding:** consequence learning requires a matching event, revision or world identity, status, and sequence.
6. **Idempotence where ledgered:** a boundary with a request or stream ledger returns the previously committed result for an exact duplicate identity rather than applying the associated transition or learning operation twice.
7. **Atomic file replacement:** a checkpoint path exposes either the prior complete frame or the successor complete frame, not a partially written payload.

The next operation begins by loading and validating the persisted frame against its exact surface identity. A load or configuration mismatch prevents admission; a rejected candidate, unresolved selection, unauthorized proposal, or invalid observed result produces no successor save. Failure of an individual atomic save exposes the complete frame that preceded that save, not a partial payload, but it does not roll back an earlier successful save in a multi-save API call. These explicit boundaries make the causal chain inspectable from observation through field transition to each persisted consequence.
## 6. Representation Without Learned Embeddings

Cassi separates exact acquisition, fixed interpretation, and adaptive field response. Acquired data first enters a content-addressed packet and journal. A selected fixed adapter then exposes a typed view of that packet. Only a task-specific field operator can turn the view into experience-dependent behavior. No learned embedding model lies between these stages, and codec conformance is not counted as learned semantics.

Two representation families are implemented. `cassi_universal_data.py` admits heterogeneous finite payloads through `BoundaryPacket`, `QiIngressJournal`, and `ObservationView`. The language surfaces use narrower fixed event codecs such as `CassiFieldTextCodec`, `CassiGroundedEventCodec`, and `CassiDiscourseEventCodec`. Both families are deterministic and fingerprinted, but they have different alphabets, schemas, and downstream field operators. They are not interchangeable encoders for one universal latent space.

### 6.1 Fixed symbolic and byte codecs

For an acquired value \(x\), codec \(c\), and task surface \(\sigma\), the representation path is

\[
x
\xrightarrow{\;\mathcal A\;}
P_x
\xrightarrow{\;A_c\;}
V_c(P_x)
\xrightarrow{\;E_\sigma\;}
\xi_{\sigma,x}
\xrightarrow{\;D_\sigma\;}
F',
\]

where \(\mathcal A\) creates the exact boundary packet, \(A_c\) is a fixed adapter, \(E_\sigma\) is an optional task-specific event construction, and \(D_\sigma\) is the field transition. The first two arrows contain no adaptive parameters. The final field transition may express learned structure because it acts on the current field \(F\).

The universal adapter registry contains seven fixed descriptors:

| Codec | Accepted payload contract | Typed root | Adapter interpretation |
|---|---|---|---|
| `cassi.codec.json-utf8.v1` | UTF-8 JSON in a one-dimensional `uint8` payload | `Collection` or `Atom` | JSON syntax |
| `cassi.codec.raster-u8-c.v1` | C-contiguous unsigned-byte raster | `Tensor` | Raster samples |
| `cassi.codec.utf8.v1` | UTF-8 text in a one-dimensional `uint8` payload | `Atom` | Text syntax only |
| `cassi.codec.python-utf8.v1` | UTF-8 Python source accepted by `ast.parse()` | `Collection` | Python syntax only |
| `cassi.codec.audio-f64le.v1` | Little-endian finite `float64` samples | `Tensor` | Audio samples |
| `cassi.codec.tensor-c.v1` | C-contiguous finite numeric samples in a supported dtype | `Tensor` | Scientific tensor samples |
| `cassi.codec.opaque-bytes.v1` | One-dimensional `uint8` bytes | `Atom` | Opaque bytes only |

The fixed descriptor record hashed by `descriptor_sha256()` contains schema, codec identifier, modality, `lossless=True`, and `adaptive_state=False`. That digest identifies the adapter contract. Semantic support is assessed separately by the downstream task and is not a field in the descriptor preimage.

The universal typed-view algebra has five constructors:

\[
\mathcal N
=
\operatorname{Atom}
\mid
\operatorname{Collection}
\mid
\operatorname{Tensor}
\mid
\operatorname{Relation}
\mid
\operatorname{Event}.
\]

An `Atom` carries one finite scalar, string, Boolean, or null value. A `Collection` preserves an ordered sequence of children. A `Tensor` records shape, dtype, and raw sample bytes. A `Relation` connects typed source paths, and an `Event` groups typed items. Every node carries a `SourceLocation` containing the packet hash, codec identity, structural path, and optional source span.

The field text boundary is separate. `CassiFieldTextCodec` maps the 256 byte values directly to symbols \(0,\ldots,255\) and reserves four control symbols:

\[
\begin{aligned}
256&:\operatorname{END\_TURN},\\
257&:\operatorname{SYSTEM},\\
258&:\operatorname{USER},\\
259&:\operatorname{ASSISTANT}.
\end{aligned}
\]

Message encoding emits a role symbol, the UTF-8 content bytes, and `END_TURN` for each message. `decode_symbols()` accepts only committed byte symbols and returns both their exact raw bytes and display text decoded with UTF-8 replacement semantics. The fixed incremental output mask admits only next bytes that preserve a potentially valid strict UTF-8 prefix and admits termination only for a complete strict sequence. Raw bytes therefore remain authoritative when decoding arbitrary committed symbols; display text is not claimed as an inverse for malformed byte sequences. The codec owns no adaptive state, and its schema and control assignments determine its fingerprint.

Grounded and discourse codecs are narrower still. They frame typed observations, utterance bytes, actions, acknowledgments, references, spatial families, temporal questions, and route slots with fixed event identifiers and length prefixes. These codecs define the admissible vocabulary and wire form for their bounded tasks. Learned selection arises from trajectory work in the field, not from changing the frame layout or allocating learned symbol vectors.

### 6.2 Lossless ingress versus semantic interpretation

`BoundaryPacket` is the exact acquisition object. It binds the payload to a fixed codec-descriptor digest, run and episode identity, world and session identity, profile and clock fingerprints, source epoch and stream, body frame, request, logical time, capture interval, source sequence, shape, dtype, causal parents, and content digests. Packet construction validates those fields and derives both `event_id` and `packet_sha256` from canonical finite metadata and the payload digest.

`QiIngressJournal` admits the packet before field interpretation. Its append operation requires the packet's journal-parent hash to equal the current `HEAD`, except for an exact retry of the current packet. Source sequence must increase strictly within each stream. Capacity is checked before publication. Payloads are stored as content-addressed chunks of at most one mebibyte, packet metadata and manifests are content-addressed JSON objects, and the journal head is replaced through a flushed, synchronized temporary file.

Replay walks the hash-linked heads, reconstructs the packet, reassembles every chunk, and verifies payload, manifest, packet, and journal identities. The exact replay condition is

\[
\operatorname{Replay}
\left(
\operatorname{Append}(P)
\right)
=P
\]

for the admitted packet sequence, subject to the journal's declared capacity and ordering rules. Repeating the current append returns the existing `JournalReference`; it does not duplicate the event.

The adapter operates only after this exact record exists. `adapt(P,c)` verifies that the requested codec matches the packet descriptor and dispatches to the registered fixed parser. A successful `ObservationView` retains:

\[
V_c(P)
=
\left(
P,\,
c,\,
\operatorname{modality}(c),\,
\operatorname{root}_c(P),\,
\operatorname{evidence},\,
h_V
\right).
\]

Its `view_sha256` commits to the packet identity, codec, modality, typed root, and exact evidence references. Invalid packets, descriptor mismatches, malformed payloads, unsupported dtypes or shapes, unknown codecs, and parser failures return a typed `unsupported` result with a reason rather than silently choosing another representation.

The implemented round trip has a precise boundary: `ObservationView` retains the admitted `BoundaryPacket`, and `round_trip()` returns that packet's original payload bytes. It does not regenerate bytes from the typed node graph. The guarantee therefore establishes lossless retention and deterministic interpretation of one exact packet, not invertibility of an independently editable syntax tree.

Lossless ingress and semantic capability answer different questions:

\[
\begin{aligned}
\text{codec fidelity}
&:\quad
\widehat B=B,\\
\text{semantic support}
&:\quad
R(F^\star,V_c(P),q)
\text{ satisfies a declared observable task criterion}.
\end{aligned}
\]

The adapter conformance surface intentionally reports text, Python source, audio, scientific tensors, and opaque bytes as semantically unsupported even when their views are selected and their payloads round-trip exactly. That result prevents syntactic coverage from being promoted into an unsupported claim of universal understanding.

### 6.3 Provenance and identity

Cassi's representation boundary uses layered identities because equal bytes, equal events, and equal interpretations are different equivalence relations.

| Identity | What it binds |
|---|---|
| `payload_sha256` | The exact acquired bytes |
| `descriptor_sha256` | The fixed codec contract |
| `event_id` | Acquisition identity, request, logical and capture time, stream sequence, payload description, and causal parents |
| `packet_sha256` | The complete validated packet metadata and payload digest |
| `journal_head_sha256` | The admitted packet's position in the exact ingress chain |
| `view_sha256` | Packet identity, selected codec and modality, typed node tree, and evidence references |
| Field-state hash | The complete adaptive tensor at a specific transition boundary |

`BoundaryIdentity` further names `run_id`, `episode_id`, `world_id`, `session_id`, `profile_sha256`, `clock_sha256`, `source_epoch`, `source_stream_id`, and `body_frame_id`. Rational logical and capture times participate in causal identity. Nanosecond timestamps and arrival sequence are explicitly telemetry and do not replace the logical clock.

Source locations preserve structural provenance below the packet level. JSON paths retain collection indices and duplicate-key occurrence suffixes. Python nodes retain AST paths and source spans derived from line and column offsets. Tensor nodes retain their packet path together with shape, dtype, and sample bytes. A field operator can therefore bind a learned relation to typed addresses while the journal remains the authority for the original evidence.

Training, evaluation, and held-out split membership are experiment-level identities rather than properties inferred by a codec. A corpus or exact record must carry that assignment independently. Neither equal payload hashes nor equal view shapes authorize moving an observation between splits. Likewise, modality pairing requires an explicit event relation; matching dimensions or coincidentally equal values are insufficient.

These identities also define restart admission. A persisted field result can be compared only under the matching controller, codec, source, and evidence identities. Recomputing a view from a replayed packet must reproduce its view hash before that view can stand in for the original interpretation.

### 6.4 Fixed projection versus learned cross-view transfer

A fixed adapter supplies deterministic parsing under one declared codec, but the implemented registry does not project heterogeneous payloads into one common vector. The JSON adapter preserves member order and duplicate-key occurrences, while raster and tensor adapters preserve their sample layout. Two serializations of the same external fact can therefore retain different packet and view identities:

\[
\operatorname{meaning}(P_1)
=
\operatorname{meaning}(P_2)
\;\not\Rightarrow\;
h_V\!\left(V_c(P_1)\right)
=
h_V\!\left(V_c(P_2)\right).
\]

That condition does not establish that two different codecs denote the same world state. In particular,

\[
V_{c_1}(P_1),\,V_{c_2}(P_2)
\;\not\Rightarrow\;
\operatorname{meaning}(P_1)
=
\operatorname{meaning}(P_2).
\]

Cross-view transfer requires an adaptive field transition and independently specified pairing evidence. In the implemented universal-data field scenario, JSON records and two-plane rasters encode the same anonymous two-entity world transitions under different orderings. Their packets remain distinct. Paired instances share an explicit `pair_event_id`, causal parent identity, exact before/after references, action identity, and authority admission.

Let \(\mathcal P\) be the paired training evidence and \(F_0\) the initial field. The learned surface has the form

\[
F^\star
=
\mathcal L
\left(
F_0,\mathcal P
\right),
\]

and directional transfer is evaluated by freezing \(F^\star\), withholding the destination modality from field synthesis, and querying held-out destination views:

\[
R_{\mathrm{dst}}
\left(
F^\star_{\mathrm{src}},V_{\mathrm{dst}}(P),q
\right).
\]

The bounded scenario contains 32 paired JSON/raster transitions across eight layouts and four actions. Each directional trial supplies 32 source-modality experiences and evaluates 16 held-out destination-modality queries. The declared controls require exact destination results and residual at most \(10^{-12}\), unchanged selected programs, an unchanged field during inference, explicit ambiguity for indistinguishable roles, and failure when pairing is shuffled, pairing identity is absent, or observations are reduced to hashes alone.

These controls locate the cross-view capability in field learning over paired typed evidence rather than in a fixed byte projection. They support JSON-to-raster and raster-to-JSON transfer on the bounded two-entity task. They do not establish unrestricted modality invariance, semantic competence for every registered adapter, or a general learned embedding space.

## 7. Grounded Language and World Interaction

The grounded-language surface couples a v2 trajectory field to a bounded world whose state transitions and observations are independently checkable. Its purpose is to test whether language-conditioned field activity can select actions, bind references, retain spatial and temporal relations, and learn from executed consequences without receiving hidden object labels or delegating selection to a model. The implementation discussed in this section is `CassiFieldAgent` with `DeterministicQiWorld`; broader environment substitution is constrained by the boundary qualifications in Section 7.8.

### 7.1 Deterministic world model

The world and field are separate state machines. Let \(W_t\) be the exact world state and \(F_t\) the field:

\[
\begin{aligned}
o_t
&=
\mathcal H(W_t,\mathcal M_t),\\
a_t
&=
\mathcal A(F_t,o_t,u_t),\\
\left(W_{t+1},\alpha_t\right)
&=
\mathcal X(W_t,a_t),
\end{aligned}
\]

where \(\mathcal M_t\) is the requested modality set and \(\alpha_t\) is the exact acknowledgment. The field does not author \(W_t\), and the world does not choose \(a_t\).

`DeterministicQiWorld` is a finite analytic laboratory. Its snapshot binds the seeded world configuration to the current logical tick, body frame, agent position and velocity, complete internal object records, last action and actuator values, closed flag, retained intent/acknowledgment log, and snapshot hash. Seeded initialization and deterministic update laws make an executed action reproducible from the same admitted state and command.

`DeterministicQiWorld.observe()` exposes proprioceptive, optical, and audio `QiWorldObservation` packets through the typed world contract. The same module separately defines authenticated W13R wire framing for those operations; `CassiFieldAgent` uses the in-process methods directly. Opaque object identifiers are absent from sensor payloads while world identity remains in protocol metadata. `CassiFieldAgent.step()` requests the proprioceptive packet, validates its schema, and encodes its two normalized agent coordinates into fixed-width grounded observation bytes. The field does not receive the world's internal post-action state before selecting an action.

This deterministic substrate is evidence control rather than a claim that real environments are deterministic. It supplies an authoritative transition against which prediction, acknowledgment, rollback, replay, and learned action consequence can be measured.

### 7.2 Grounded actions

The grounded action vocabulary is fixed and finite:

\[
\mathcal A_{\mathrm{ground}}
=
\{
\texttt{hold},
\texttt{gaze-left},
\texttt{gaze-right},
\texttt{gaze-up},
\texttt{gaze-down}
\}.
\]

For observation bytes \(o_t\), instruction bytes \(u_t\), and candidate action \(a\), `select_grounded_action()` evaluates the learned trajectory sequence

\[
\left[
\operatorname{OBS}(o_t),
\operatorname{UTTERANCE}(u_t),
\operatorname{ACTION}(a)
\right]
\]

without mutating the supplied field. If \(w_a\) is the resulting event work, the winner must satisfy

\[
w_{a^\star}>0
\]

and

\[
w_{a^\star}-w_{a^{(2)}}
>
\max
\left(
10^{-6},
10^{-6}|w_{a^\star}|
\right).
\]

Otherwise the selector abstains with an explicit no-support or no-margin error. Ties are ordered deterministically by action identifier.

Selection alone does not move the world. `commit_grounded_action()` first writes the selected reaction event into a successor field. `make_grounded_action_command()` then binds the action to world, episode, profile, logical/effective/valid ticks, target actuator, body frame, requested values, exact action-descriptor hash, committed field-state hash, current world-state hash, and a derived idempotency identity. Only `DeterministicQiWorld.step()` applies the command.

The complete action transaction is ordered:

1. snapshot the predecessor field, trained-memory hash, and world;
2. acquire the predecessor proprioception;
3. sense observation and instruction;
4. evaluate every allowed action;
5. commit the selected field reaction;
6. construct the hash-bound command;
7. execute exactly one world tick;
8. acquire the acknowledgment and successor proprioception;
9. sense the observed result;
10. optionally consolidate the full episode;
11. write the transition register and save the successor.

If field processing or persistence fails after world execution, the in-process deterministic world is restored from its predecessor snapshot. The returned receipt records predecessor and successor field, memory, observation, and world hashes together with selected and runner-up work, margin, acknowledgment status, world effect, diagnostics, and consolidation status.

### 7.3 Spatial relations

The bounded spatial-language fixture uses a geometry-only observation hook rather than a learned visual detector. `observe_colored_objects()` reads the deterministic world's ordered object positions, assigns the first three fixture objects the fixed names red, blue, and green, and quantizes their coordinates on a \(5\times5\) grid. `sense_spatial_query()` then writes the bin coordinates normalized by four into the live boundary register. This path does not parse the W13R optical raster and should not be read as evidence of general visual object recognition.

For normalized subject position \(\mathbf p_s=(x_s,y_s)\), comparison position \(\mathbf p_c=(x_c,y_c)\), and Chebyshev distance \(d_\infty=\max(|x_s-x_c|,|y_s-y_c|)\), the fixed spatial resonance functions are

\[
\begin{aligned}
R_{\mathrm{left}}
&=
\max(0,x_c-x_s),&
R_{\mathrm{right}}
&=
\max(0,x_s-x_c),\\
R_{\mathrm{above}}
&=
\max(0,y_s-y_c),&
R_{\mathrm{below}}
&=
\max(0,y_c-y_s),\\
R_{\mathrm{near}}
&=
\max
\left(
0,1-d_\infty
\right),&
R_{\mathrm{far}}
&=
2d_\infty.
\end{aligned}
\]

The live coordinates are written into the field's boundary register. When no family is supplied by an already resolved discourse frame, trajectory work selects horizontal, vertical, or distance using a positive winner and separation margin. The selector then ranks the two relations inside the chosen family from spatial resonance alone:

\[
\widetilde w_r
=
\lambda_{\mathrm{spatial}}R_r,
\qquad
\lambda_{\mathrm{spatial}}
=
\texttt{GROUND\_SPATIAL\_RESONANCE\_WEIGHT}
=
20.
\]

When it is not supplied explicitly, learned trajectory work determines which question family has support; the current field-carried geometry then resolves the answer inside that family. A successful `CassiFieldAgent.query()` commits the selected relation, preserves the active reference if present, and saves the changed live field context. It does not move the world or alter the trained trajectory memory.

The resulting claims are relative and role-bound. “Red is left of blue” identifies a subject, a comparison, a relation family, and a relation under the current observation. The fixture does not infer persistent physical identity from pixels, reconstruct occluded objects, or estimate continuous scene geometry beyond its fixed grid representation.

### 7.4 References

Reference grounding is represented through field events and one live field register rather than a persistent Python name-to-object dictionary. Binding a name presents the reference cue, resolves one candidate reference through trajectory work, commits the binding sequence, and writes the selected reference's fixed code into the active-reference register.

Let \(a_e(F)\) be the live boundary-register component assigned to reference \(e\). The active reference is selected directly from those components:

\[
e^\star
=
\underset{e}{\operatorname{arg\,max}}\;a_e(F).
\]

It is admitted only when

\[
a_{e^\star}(F)\ge 0.5
\qquad\text{and}\qquad
a_{e^\star}(F)-a_{e^{(2)}}(F)\ge 0.5.
\]

An empty, weak, or insufficiently separated register therefore produces no active reference.

Explicit names are encoded as candidate reference events. Pronoun-like use selects through the active register and then combines the resolved reference with the current comparison entity and relation family. `CassiFieldAgent.bind()` saves the resulting field and increments the exact binding counter. Later queries reload the field-carried reference across restart; the exact session metadata records counts and identities but does not contain the learned name binding.

The reference mechanism is intentionally closed-world. The fixture has a fixed candidate inventory and fixed reference codes. It demonstrates persistence and use of learned bindings within that inventory, not open-ended entity discovery or coreference over arbitrary discourse.

### 7.5 Temporal prediction

Every executed grounded action writes a compact live transition register into the field. For predecessor observation \(o_t\), successor observation \(o_{t+1}\), and action \(a_t\), the register contains

\[
T_t
=
\left(
x_t,\,
y_t,\,
x_{t+1},\,
y_{t+1},\,
\operatorname{onehot}(a_t),\,
1_{\mathrm{valid}}
\right).
\]

The four coordinates preserve the normalized predecessor and successor positions; observed change is derived from their difference when the register is read. The register is live field context. Writing or reading it does not by itself modify learned trajectory memory.

Prediction is language-conditioned trajectory selection. `select_predicted_change()` evaluates fixed candidates such as left, right, up, down, and same after sensing the current observation, action instruction, and prediction question. `commit_temporal_decision()` records the chosen change event in the successor field.

`CassiFieldAgent.predict_action()` is a counterfactual field path with a precise scope. It senses the present world observation and proposed instruction, selects an action and predicted change, commits their field events, and saves the successor field. It does not call `world.step()`, and it verifies that trained memory and the deterministic world snapshot remain unchanged. The result is a prediction under the current field, not an independently simulated future world.

Observed consequence remains authoritative. During an executed step, the successor observation and acknowledgment arrive after the action. Only then can `consolidate_grounded_episode()` apply residual-dependent trajectory learning. In this surface, “delayed consequence” means that learning is withheld until the exact post-action evidence is available; it does not imply an unbounded eligibility-trace mechanism across unrelated future episodes.

### 7.6 Explanation and ordering

The temporal register supports four distinct readouts:

| Readout | Evidence used | Field operation |
|---|---|---|
| Predicted change | Current observation, proposed action, prediction cue | Candidate trajectory work |
| Observed change | Registered predecessor and successor coordinates | Fixed change-code resonance |
| Cause | Registered action one-hot | Fixed action-code resonance |
| Before/after position | Explicit temporal question and live order pair | Trajectory-selected target followed by order-register resonance |

Observed-change and cause selection first require a valid, resolved transition register. The shared temporal selector then requires a positive winner whose margin is at least \(\max(0.5,10^{-6}|w_{(1)}|)\). These paths recover the change and action carried by the register rather than substituting a language prior. `explain_last_transition()` combines the registered cause and observed change into a typed explanation receipt.

Ordering uses an explicit pair of temporal targets and candidate positions `first` and `second`. The field evaluates the requested presentation order, commits the selected target and position, and returns the corresponding answer. If predecessor and successor states are indistinguishable and the request supplies no explicit state pair, the discourse boundary rejects the explanation or ordering request rather than inventing a distinction.

The transition register is saved inside the field checkpoint. After restart, the same configuration and checkpoint recover the last transition's cause, change, and temporal order without consulting an external symbolic transition log. Exact world snapshots and receipts remain independently authoritative evidence; the field register is the learned system's live relational state.

### 7.7 Discourse routing without a learned policy store

`CassiFieldAgent.turn()` adds a multi-turn language boundary over the action, prediction, spatial, reference, binding, explanation, ordering, alias, and deferred-goal operations. A fixed surface parser normalizes the utterance and constrains the candidate route and slot sets. `CassiDiscourseEventCodec` then frames utterance windows, routes, commit modes, action and change slots, entities, relation families, references, temporal targets, and temporal positions as fixed events.

For each slot \(j\), the discourse selector computes

\[
z_j^\star
=
\underset{
z\in\mathcal Z_j(x,z_{<j})
}{
\operatorname{arg\,max}
}
\;
W_{\mathrm{seq}}
\left(
F_{\mathrm{route}},
\operatorname{windows}(x)
\Vert
z_{<j}
\Vert
z
\right),
\]

subject to positive support and a nonzero margin. The fixed parser supplies \(\mathcal Z_j\); field work selects within that admissible set. Parsing, candidate pruning, and reply rendering are therefore fixed computational structure, while field transitions determine the supported route and grounded slots.

The route field passed to `select_discourse_frame()` is scratch state initialized by the agent and is not serialized as a parallel learned policy. Persistent action aliases, reference bindings, and deferred goals are committed through the primary field's trajectory and boundary-state operations. Exact counters and world snapshots remain session metadata rather than learned policy.

The selected route dispatches to the corresponding typed operation. Action routes execute `step()`. Prediction routes call `predict_action()`. Spatial and reference routes call the grounded query paths. Explanation and ordering use the temporal register. Goal declaration stores a field-carried action sequence, while goal trigger reselects and executes its actions against the current world. A fixed renderer turns the typed result into response text.

Unsupported, ambiguous, or incomplete frames return clarification or a typed error. `turn()` snapshots field, trained memory, and world before dispatch and checks that supported error paths have not changed them. This provides transactional behavior for the bounded discourse interface without treating the parser, renderer, or scratch routing field as a learned language model.

### 7.8 External-world contract and demonstrated scope

`QiWorldPort` defines the lower external-world protocol independently of the deterministic implementation:

| Operation | Contract |
|---|---|
| `observe(...)` | Return current-tick sensor packets for requested modalities without advancing the world |
| `describe_actions(tick)` | Return the exact action descriptors valid for the current tick |
| `advance_tick(intent)` | Apply the sole world transition for a fully bound intent |
| `resolve_tick(intent)` | Return the exact retained acknowledgment for an already resolved intent |

An intent binds world, episode, profile, session, cycle, predecessor and successor ticks, committed prior-head hash, body frame, idempotency key, optional canonical action scope, contract root, and semantic parents. The action command inside that scope binds the action identifier, exact descriptor hash, requested actuator values, source field-state hash, and predecessor world-state hash. The acknowledgment binds the intent and action scope to status, terminal status, world-effect truth, requested-values and reason digests, terminal result, and its own content hash. For an applied action, the terminal result also carries application and first-visible-observation ticks, applied values, and body-transition hashes. Successor sensor packets and the successor world snapshot are acquired separately after acknowledgment. Exact duplicate intents replay; reuse of an idempotency key with different intent bytes is rejected.

`DeterministicQiWorld` implements this protocol and adds snapshot/restore plus fixture-specific object access used by `CassiFieldAgent`. Consequently, the current grounded agent is not a drop-in client for every possible `QiWorldPort`: its rollback path requires snapshots, and its spatial-language helper reads the deterministic fixture's geometry directly.

Another environment can occupy the world role only through an adapter or coordinator that supplies equivalent observation, action-description, intent-binding, acknowledgment, replay, and recovery semantics, and that replaces fixture-specific spatial access with an admitted observation path. The protocol provides the seam for a CassiCosmos or other embodied adapter; this section does not assert that the grounded-language transaction already runs unchanged against such an environment.

Within that boundary, the demonstrated claim is specific: a field can select language-conditioned actions, observe their exact consequences in an independently authoritative world, preserve grounded references and temporal relations, and express those relations after restart. Section 8 turns from this grounded action and discourse surface to bilateral counterflow, where compatible observed transitions can constrain multi-step deliberation.

## 8. Bilateral Counterflow and Deliberation

The implemented counterflow capability is bounded transition composition, not unconstrained deliberation or a hidden natural-language chain of thought. `BilateralCounterflowController` stores learned transition statistics in one `QiFieldState`, constructs a provisional thought in two oppositely directed field lanes, and closes only when a single eligible operator sequence satisfies the supplied trajectory constraints. Exact records, policy, and action execution remain outside that numerical state.

This separation corrects three tempting but inaccurate interpretations. First, “counterflow” denotes start-conditioned and goal-conditioned propagation through learned forward and backward operators; it does not imply exact physical time reversal. Second, a field trajectory is a latent proposal until exact action descriptors prove effect-to-precondition continuity. Third, planning never promotes an imagined branch into canonical memory. On the persistent-provider path, only an acknowledged observed transition may change the counterflow component.

### 8.1 One field, two directed lanes

For a configured mode capacity \(M\), counterflow state is a real tensor

\[
F_{\mathrm{cf}}\in\mathbb{R}^{7\times 9M\times 1},
\]

viewed internally as seven scales, nine component planes, and \(M\) mode positions. A trajectory value has four complex components,

\[
z_j=(z_j^{Y,1},z_j^{Y,2},z_j^{I,1},z_j^{I,2})\in\mathbb{C}^{4},
\]

so each slot carries two Yang and two Yin features. Disjoint mode ranges hold:

- an ascending lane for start-conditioned propagation;
- a descending lane for goal-conditioned propagation;
- values and masks for exact or partial slot constraints;
- persistent basin moments and support;
- exact-integer thought status, eligible-basin mask, stable-plan count, and selected path.

The controller itself retains only its immutable configuration. Learned moments, support, macro metadata, temporary lane values, velocities, and closure metadata all reside in the tensor.

`start_thought()` writes the authoritative start value to slot zero at scale zero of the ascending lane and the authorized terminal constraint to the final active slot at scale six of the descending lane. The seven-scale transport matrices are nonwrapping shifts,

\[
U_{s+1,s}=1,\qquad D=U^{\mathsf T},
\]

with all other entries zero. The ascending view therefore transports information from the root toward the crown, while the descending view transports it in the opposite scale direction. Cross-lane and endpoint coupling make the two views constrain one another without collapsing them into one stream.

### 8.2 Exact transition fragments and field-resident operators

The deployment-facing runtime does not learn from an unverified pair of arbitrary vectors. Each endpoint is an exact identity containing a record identifier, SHA-256 revision, byte span, semantic kind, and a 16-byte address recomputed as

\[
a=
\operatorname{first}_{16}
\left[
\operatorname{SHA256}
\left(
\operatorname{JSON}
\left[
\texttt{cassicore.mnemic.counterflow-address.v1},
r,\rho,s,e,k
\right]
\right)
\right].
\]

Any mismatch between the supplied address and this provenance tuple is rejected. The 128 address bits are then split into eight unsigned 16-bit words. With

\[
u_\ell=\frac{w_\ell-2^{15}}{2^{15}},
\]

successive word pairs become four complex field components. The inverse codec rejects negative zero, nonfinite values, values off the exact unsigned-16 grid, and out-of-range words. “Exact” here means that the validated 128-bit address round-trips through the latent representation. The complete record or world snapshot remains independently authoritative; it is not compressed into four complex numbers.

For batched before/after values \(x_n,y_n\in\mathbb C^4\), a basin stores the sufficient moments

\[
\begin{aligned}
G_x&=\frac{1}{N}\sum_n x_nx_n^\dagger,
&C_{yx}&=\frac{1}{N}\sum_n y_nx_n^\dagger,\\
G_y&=\frac{1}{N}\sum_n y_ny_n^\dagger,
&C_{xy}&=\frac{1}{N}\sum_n x_ny_n^\dagger.
\end{aligned}
\]

The forward and backward ridge operators are reconstructed from those field values:

\[
A=C_{yx}(G_x+\lambda I)^{-1},
\qquad
B=C_{xy}(G_y+\lambda I)^{-1}.
\]

Their matrix norms are capped by the configured bound. The backward operator is learned from reverse moments rather than assumed to equal \(A^{-1}\), so irreversible or rank-deficient transitions retain measurable cycle uncertainty.

An incoming transition is compared with occupied forward operators by relative prediction residual. Under the reference defaults:

- residual \(\leq 0.08\) reinforces the best basin and updates its moments by support-weighted averaging;
- residual strictly between \(0.08\) and \(0.25\) leaves the field unchanged and returns an abstention rather than forcing a merge;
- residual \(\geq 0.25\) allocates a separate basin when capacity remains;
- exhausted capacity returns `capacity` without modifying the field.

The persistent-provider path imposes a stronger admission boundary. `commit_counterflow()` requires an observation and an acknowledgment whose event identifier, stream sequence, status, before revision, after revision, and nonempty authorization path agree exactly. Action observations admit only matching `completed` or `error` outcomes; non-action observations must be committed `mnemic:update` transitions. A valid new commit changes only the canonical counterflow component. An exact duplicate is idempotent, and stale or conflicting stream sequences are rejected.

The standalone `DerivedCounterflowRuntime` can instead construct an ephemeral companion field from observations carried in a request. When a canonical counterflow state is supplied, `_bind()` tests each request observation against that frozen state and admits only an existing reinforcing basin; it discards the candidate update. This distinction prevents a planning request from silently becoming training.

### 8.3 Compatible-edge composition

Let an active trajectory contain \(L+1\) slots and let

\[
p=(b_0,\ldots,b_{L-1})
\]

be a sequence of eligible basins. Forward and backward completions obey

\[
\hat z_{j+1}=A_{b_j}\hat z_j,
\qquad
\check z_j=B_{b_j}\check z_{j+1}.
\]

Each constrained slot supplies a target \(c_j\) and component mask \(m_j\). The global search accumulates masked relative residuals,

\[
C(p)=
\sum_{j\in\mathcal C}
r_m\!\left(\hat z_j,c_j;m_j\right),
\]

where \(\mathcal C\) is the set of slots with nonzero masks. Required start data must constrain all four components with full authority; the terminal slot must contain at least one authorized component. Intermediate slots may be exact, partial, or entirely open.

At each edge, `_global_plan_completion()` expands the surviving prefixes through every eligible operator. A later fully constrained slot also generates backward-reachable states through the \(B_b\) operators. The nearest forward/backward disagreement contributes to prefix selection, while only supplied slot constraints determine terminal validity. This is an important evidentiary boundary: a backward meeting heuristic may prune search, but it cannot manufacture an observed constraint.

Search is deterministic and reports one of three modes:

| Mode | Meaning |
|---|---|
| `exact` | The current constrained segments fit within the exact enumeration limit and no beam pruning occurs |
| `adaptive` | Candidate count exceeds the exact segment limit, so entropy controls beam expansion up to the configured width |
| `bidirectional` | A future full anchor supplies backward-reachable states used to rank forward prefixes |

Stable sorting resolves purely numerical ordering. The reference configuration enumerates up to 64 segment paths before pruning, caps the adaptive beam at 16 survivors, and caps backward lookahead at 4096 states. Telemetry preserves the mode, width at each edge, evaluated extension count, best path residual, terminal margin, entropy, and valid-path count.

Numerical compatibility is necessary but not sufficient for an action chain. After settlement, `propose_typed_actions()` walks the selected basin path and requires

\[
\operatorname{effect}(a_j)=\operatorname{precondition}(a_{j+1}),
\]

with the first precondition equal to the declared start address and the final effect equal to the declared goal address. A latent path that lacks this exact descriptor chain may be rendered symbolically but cannot become an action proposal.

### 8.4 Breathing dynamics, settlement, and abstention

Each refinement mixes four influences: operator completion within each lane, directed scale transport, agreement between the two lanes, and masked trajectory constraints. Lane velocities carry bounded momentum. The default breath has sixteen steps: an expansion half emphasizes ascending propagation, and a contraction half strengthens descending and constraint gains. Up to four breaths give a maximum of 64 refinement steps.

During contraction, the best global forward trajectory is inserted progressively from the root and the corresponding backward trajectory from the crown. At every step the controller hashes the basin-memory region before and after provisional refinement. A mismatch raises an error; search and relaxation may alter the thought lanes but cannot alter learned basin moments.

Settlement is conjunctive. With the reference configuration, a thought closes as `settled` only at the end of a contraction breath when all of the following hold:

| Condition | Reference requirement |
|---|---:|
| Every selected edge predicts its successor | action residual \(\leq 0.16\) |
| Every selected edge beats its local competitors | basin margin \(\geq 10^{-3}\) |
| The same action-valid path remains selected | at least 3 consecutive refinement steps |
| The completed trajectory satisfies supplied masks | constraint residual \(\leq 0.12\) |
| The root trajectory has stopped moving materially | relative trajectory delta \(\leq 0.04\) |
| Global search is nonambiguous | no tied or high-entropy low-margin valid alternative |

A path is counted as globally valid only when its accumulated masked cost is at most the constraint tolerance times the number of constrained noninitial slots. Multiple valid paths do not automatically imply ambiguity; the ambiguity flag requires a numerical tie or a high-entropy, sub-margin competition. If closure has not occurred at the fixed horizon, the terminal status is `ambiguous` when that flag remains set and `exhausted` otherwise. No symbol or action chain is emitted from either state.

`CounterflowTelemetry` exposes the evidence needed to distinguish these outcomes: action and cycle residuals, per-edge margins, global path residual and margin, valid-plan count, constraint residual, trajectory delta, crown and root disagreement, common- and relative-mode energy, scale-wise energy, clamp count, and the frozen basin-region hash. The status therefore describes a measured closure condition rather than a generic confidence score.

### 8.5 Counterfactual requests and persistence

A plan request may change the exact goal, masks, eligible observations, or policy while reading the same learned field. The resulting lane state is a counterfactual workspace. `DerivedCounterflowRuntime.plan()` validates the caller-supplied primary-field digest as a lowercase SHA-256 value, carries it through the receipt, and reports `inference_memory_frozen` from basin-region hashes across the refinement trace. `PersistentFieldProvider.plan_counterflow()` separately hashes the actual canonical Phi and counterflow component views before and after planning and rejects any change. Both surfaces label the result `persistent_state: false`. The grounded scenario adds an outer byte-for-byte check that the composite checkpoint also remains unchanged.

The base controller contains `consolidate_plan()`, which can construct a new macro basin from a settled multi-edge path. It composes constituent operators, records constituent generations, and returns a new state. The deployment-facing derived runtime deliberately discards that new state. Even when `consolidate_macro: true` is requested, its response labels the macro `persisted: false`. A counterfactual trajectory becomes durable only if an independently executed consequence later returns through the observed-commit boundary.

This makes counterfactual revision testable. Two goals can select different trajectories from one frozen field without either branch becoming remembered merely because it was considered.

### 8.6 Policy, negative evidence, and action authority

Four kinds of information participate in the path but retain different owners:

| Kind | Examples | Role |
|---|---|---|
| Learned field evidence | Basin moments, support, dispersion, forward/backward operators | Determines which transitions fit and compose |
| Exact external evidence | Record identities, revisions, spans, observed outcomes, acknowledgments | Establishes what occurred |
| Control policy | Eligible observation IDs, permitted action kinds, scalar authority, authorization path | Restricts what may be proposed |
| Execution authority | The external caller or world adapter | Decides whether an inert proposal is applied |

`ThalamusPolicy` cannot create operator support, and operator support cannot grant authority. A settled action requires every basin to be policy-eligible, every descriptor kind to be permitted, policy authority to meet each descriptor's requirement, and a nonempty authorization path. `reversible` remains typed descriptor metadata; the counterflow runtime neither executes an action nor treats reversibility as authorization.

One-step prediction uses the same boundary. `predict_transition()` ranks eligible basin operators by reverse-cycle residual and support-normalized dispersion, requires a positive margin, and returns the field hash without mutation. An exact action proposal is withheld when the prediction is ambiguous, lacks a unique exact effect, lacks a matching descriptor, disagrees across observed effects, violates kind or authority policy, or lacks an authorization path. Observed `error` outcomes remain measurable negative evidence but are never proposed as successful actions. Optional failure inhibition suppresses a basin when error support is nonzero and at least equals success support.

### 8.7 Measured composition and causal controls

The grounded counterflow scenario constructs two three-action branches from six independently executed one-action fragments. Every source episode contains exactly one action, the request's fragment order contains neither complete target sequence, and both branches begin at one exact world revision. The six acknowledged fragments are committed to the provider's counterflow component; the complete trajectories are never committed.

The measured run produced:

| Property | Result |
|---|---|
| North-west goal | `gaze-left`, `gaze-up`, `gaze-left`; bidirectional search; one valid plan |
| South-east goal | `gaze-right`, `gaze-down`, `gaze-right`; bidirectional search; one valid plan |
| Exact external replay | Both inert proposals reached their declared world-state SHA-256 revisions |
| Goal intervention | Changing only the exact goal changed all three selected actions |
| Persistence during planning | Primary field, counterflow field, and checkpoint bytes remained unchanged |
| Duplicate observed commit | Returned `duplicate` and did not consolidate again |
| Required-edge lesion | Removing one south-east fragment produced `exhausted` with no action proposal |

Additional focused controls establish the surrounding failure semantics. No observations return `no_transition_data`; observations with no eligible bound basin return `no_eligible_transition_data`; tied valid plans terminate as `ambiguous`; an unreachable goal exhausts; clearing a required operator breaks its composition; error-supported outcomes do not produce actions; and kind, authority, provenance, or authorization-path disagreement fails closed.

The fragment-order check in this scenario proves that neither target sequence was present contiguously in the request and that composition was assembled from isolated edges. It is not a dedicated shuffled-transition ablation, so no separate shuffle result is claimed here. The supported conclusion is narrower and stronger: within a bounded exact-address task, field-resident transition operators can compose a previously unobserved multistep path, revise it under an exact goal intervention, and lose it when a causally required edge is removed.

## 9. Relational Basis Selection

The current relational capability is selection within a fixed candidate library. The system does not invent a coordinate transformation, infer an unlimited relation vocabulary, or discover action labels from raw data. Candidate maps, action identities, evidence terms, and score weights are fixed; grouped action operators and accumulated selection evidence reside in the field. This bounded construction makes the ownership claim inspectable while keeping its scope explicit.

### 9.1 Exact relational inputs and candidate frames

`RelationAtoms` admits exactly two distinct entities and binds their coordinates to a world identifier, episode identifier, exact world-state SHA-256, and regime (`interior` or `boundary`). Coordinates must be finite values in \([-1,1]\). Its payload has the exact schema `cassi.counterflow.relation-atoms.v1` and a SHA-256 over the canonical JSON body. Missing fields, extra fields, tampered coordinates, or a caller-supplied verdict are rejected.

For a declared `self_index`, let the self position be \(s=(s_x,s_y)\), the other entity be \(t=(t_x,t_y)\), and \(\Delta=t-s\). The fixed four-member library maps those atoms to \(z\in\mathbb C^4\):

| Candidate | Field value |
|---|---|
| `target_minus_self` | \((\Delta_x,\Delta_y,1,\Delta_x\Delta_y)\) |
| `absolute_self` | \((s_x,s_y,1,s_xs_y)\) |
| `absolute_target` | \((t_x,t_y,1,t_xt_y)\) |
| `identity_control` | \((h_x,h_y,1,h_xh_y)\), where \(h_x,h_y\) are deterministic SHA-256-derived values from the ordered entity IDs |

The identity control detects a representation that keys on names rather than geometry. The two absolute candidates test world-coordinate dependence. `target_minus_self` is translation-invariant by construction and expresses the candidate relational frame relevant to the interior gaze task.

The candidate values are fixed encodings of exact atoms, not learned embeddings. Exact world snapshots and state revisions remain outside the field. What the field learns is how each candidate value changes under each action and how well those changes satisfy a fixed battery of relational criteria.

### 9.2 Grouped action operators

The reference experiment uses four actions—gaze left, right, up, and down—and assigns one basin to every basis/action pair:

\[
b(q,a)=4q+a,\qquad q,a\in\{0,1,2,3\}.
\]

All sixteen basins therefore have predetermined semantic grouping. Sixteen one-action world executions supply four distinct interior examples for each action. Every execution is encoded under all four candidate bases, and `observe_grouped_transitions()` accumulates the same forward and backward sufficient moments derived in Section 8.2. Each candidate frame consequently receives four learned action operators.

This experiment does not infer grouping. The basis ID and action ID are supplied to the operator learner, and the action set is known. The adaptive question is whether the consequences represented by those grouped operators make one candidate basis better supported than its alternatives.

The moments, support, dispersion, and operator-generating statistics occupy the corresponding field basins. Reconstructing an operator from the field requires support above the occupancy floor; clearing its basin removes that capability without changing the candidate encoder or the other operators.

### 9.3 Field evidence and deterministic selection

Eight independent interior selection worlds generate closure, inverse, composition, invariance, and collision evidence. Jointly translated and renamed counterparts supply the second member of each invariance pair, while four additional boundary worlds supply the boundary term. Operator-training identities remain disjoint from every selection identity.

| Evidence term | Measurement |
|---|---|
| Closure \(e_{\mathrm{cl}}\) | Mean \(r(A_a z,z')\) on held-out one-action transitions |
| Inverse \(e_{\mathrm{inv}}\) | Mean \(r(A_{a^{-1}}A_a z,z)\) |
| Composition \(e_{\mathrm{comp}}\) | Mean residual after an observed multiaction composition |
| Invariance \(e_{\mathrm{var}}\) | Mean residual between original and jointly translated, renamed atoms |
| Collision \(e_{\mathrm{col}}\) | Squared penalty when the minimum separation between action-induced deltas falls below \(0.05\) |
| Boundary \(e_{\partial}\) | Mean one-action residual on four clamped boundary cases |

For every candidate, the ninth component plane stores an exact support count and accumulated sums of these six nonnegative values. Selection reads their field-resident means and computes

\[
S_q=
e_{\mathrm{cl}}
+0.5e_{\mathrm{inv}}
+e_{\mathrm{comp}}
+2e_{\mathrm{var}}
+2e_{\mathrm{col}}
+0e_{\partial}.
\]

The reference configuration assigns boundary evidence zero weight: boundary residual is measured and reported, but an interior basis is not selected on a claim that it already solves clamping. A supported basis must have \(S_q\leq0.05\), and its gap to the overall runner-up must exceed \(10^{-4}\). Otherwise the result is `no_basis_evidence`, `no_eligible_basis`, or `ambiguous`.

In the measured run, the field contained:

| Candidate | Score |
|---|---:|
| `target_minus_self` | 0.003585 |
| `absolute_self` | 0.422253 |
| `absolute_target` | 2.417320 |
| `identity_control` | 4.073100 |

`target_minus_self` was the only candidate below the eligibility ceiling and was selected with a margin of \(0.418669\). Its near-zero translation-invariance residual and zero collision penalty distinguish it from the absolute and identity controls. The result is field-selected because the grouped moments and evidence sums that determine this comparison are in `QiFieldState`; it is not label-free because the candidate functions, action groupings, weights, and acceptance thresholds are fixed code.

### 9.4 Interventional role binding and holdout transfer

Renaming entities and reversing their tuple order removes a positional convention for `self_index`. The experiment resolves that ambiguity interventionally. It applies one known calibration action in a cloned world, evaluates

\[
r_i=r\!\left(A_a\phi_q(x;i),\phi_q(x';i)\right),
\qquad i\in\{0,1\},
\]

for both possible self assignments, and chooses the smaller residual only when the difference exceeds the configured margin floor. This identifies the role whose relational value changes according to the learned action operator. It does not infer selfhood from a passive snapshot.

Thirty-two holdout worlds use identities disjoint from both operator training and basis-selection evidence. All target and self identifiers are renamed, and sixteen inputs reverse entity order. Each holdout supplies a start, two fully constrained intermediate relational values, and a terminal value for a three-action sequence. Counterflow selects the operator path, an external deterministic world executes the selected actions, and its exact successor revision is compared with the withheld goal revision.

The measured result was 32/32 correct role bindings, 32/32 settled action sequences, and 32/32 exact world revisions. The minimum role margin was \(0.136597\), and the maximum final constraint residual was \(0.004791\). Checkpoint reload was byte-exact, and all holdout inference left field memory unchanged.

These measurements support renamed-identity, entity-order, translated-interior, and unseen-pose transfer under an interventional role cue and complete intermediate constraints. They do not establish endpoint-only planning, passive role discovery, moving-target dynamics, or arbitrary object relevance.

### 9.5 Persistence and causal ownership controls

The selected state serializes through the counterflow checkpoint format together with its exact configuration fingerprint and tensor hash. Reload reproduces the same `BasisSelection`. No separate learned projector object, classifier, or model checkpoint participates; the controller retains only configuration, while grouped operator moments and evidence remain inside the field.

Two lesions test causal ownership:

1. Clearing the selected basis's evidence row changes selection to `no_eligible_basis`.
2. Clearing the operator required by a holdout path makes that thought terminate `exhausted`.

The unmodified checkpoint remains frozen across inference. The run makes zero teacher or model calls and has no live-provider fallback. The associated stress suite also reports `provider_integration: false`; this is a standalone field experiment, not evidence that relational selection is already wired into the persistent OpenAI-compatible provider.

The fixed atom schema, candidate encoders, action grouping, score equation, role-binding procedure, deterministic world, and exact-revision evaluator remain nonadaptive machinery. The field owns the learned operator statistics and basis evidence, and the lesions show that those coordinates are necessary for the measured result.

### 9.6 Known failure regimes

Defined stress tests sharply limit the successful interior result:

| Stressor | Measured behavior |
|---|---|
| Boundary clamping | Four reference cases had mean residual \(0.061503\), above the \(0.04\) action tolerance; boundary support was false |
| Moving targets | With both intermediate slots constrained, 24/24 trajectories settled to exact revisions; with one intermediate slot or endpoints alone, 0/24 reached the exact revision |
| Coordinate noise | Exact settlements were 16/16 through amplitude \(0.01\), then 13/16 at \(0.015\), 9/16 at \(0.02\), 4/16 at \(0.025\), 1/16 at \(0.03\), and 0/16 at \(0.06\) |
| Diagnostic distractors | When only the intended target matched the learned dynamics, target selection was 24/24 |
| Hidden object relevance | Among sixteen dynamically indistinguishable cases, the system made 6 correct choices and 10 false-confident choices, with 0 abstentions; relevance was not observable |
| Passive role inference | Across 32 balanced cases, passive scoring produced 8 correct, 8 wrong, and 16 abstentions |
| Interventional role inference under broader stress | The same set produced 24/32 correct bindings, with all eight south-west cases wrong |
| Inverse-cycle diagnostic | Maximum inverse-cycle residual was \(0.256940\); inverse behavior is therefore a scored control rather than exact inverse closure |
| Required-operator lesion | The selected path changed and the thought exhausted without reaching the exact revision |

An expanded three-candidate experiment added `distance_bearing` and `boundary_context`, included boundary examples in training, assigned boundary residual nonzero selection weight, and selected `distance_bearing` by a margin of \(0.001233\). Nevertheless, none of the three candidates reached an exact revision on twelve boundary-composition holdouts. The selected `distance_bearing` basis settled falsely in all 12/12 cases.

That negative result is especially informative. A low aggregate basis score is not sufficient evidence for downstream compositional validity outside the regime represented by the successful task. Likewise, action-sequence agreement can survive noise after exact revision agreement has failed, and dynamically indistinguishable entities can force confident but ungrounded relevance choices. Relational selection therefore requires regime-specific outcome checks, not merely a selected basis.

The supported claim is bounded: within the interior two-entity gaze task, a single field can hold grouped action operators and comparative relational evidence, select a target-relative frame, bind roles through intervention, and transfer across renamed and reordered identities. The current implementation does not discover new basis functions, solve passive agency, infer hidden relevance, or generalize its affine operators through boundary clamping and unmodeled target motion.


## 10. Bounded Typed-Program Abstraction

The abstraction experiment extends the fixed relational-basis comparison of Section 9, but it does not yet perform open-ended program synthesis. `generate_candidate_programs()` deterministically constructs twelve programs from a fixed template family before any field state is evaluated. `synthesize()` deposits grouped moments for every supported program/action pair; ordinary interior and temporal consequences use the reconstructed operators, while boundary transition laws are evaluated directly from their fixed `ACTION_DELTA` and `CLAMP` arithmetic. Across all candidates, the field stores comparative evidence and confirmation state; `select_program()` computes selection read-only from those records. Program syntax remains fixed machinery rather than adaptive state.

This correction matters because the implementation contains a larger typed interpreter than the candidate generator actually explores. The interpreter defines a useful language boundary, while the experiment establishes selection and transfer only for the twelve generated members of that language.

### 10.1 Typed interpreter and bounded candidate set

An `AbstractionProgram` is a canonical reverse-Polish expression that must leave exactly one four-component vector on its stack. The 29-member `ProgramToken` enum includes:

- entity leaves `ROLE_A` and `ROLE_B`;
- relational observations `POSITION`, `DELTA`, `SWAP_ROLES`, and `HEADROOM`;
- the configured `ACTION_DELTA`, world bounds, and sensor precision;
- scalar and vector arithmetic;
- norm, square root, normalization, minimum, maximum, and clamping;
- comparisons and typed conditional selection;
- component extraction and `PACK4`;
- the special hypothesis directive `EACH_OBJECT`.

The parser checks stack arity and operand kind at every token. Arithmetic requires compatible scalar or two-vector inputs, comparisons require scalars, `SELECT` requires a Boolean condition and matching branches, and `PACK4` accepts either one two-vector or four scalars. An invalid or incomplete expression is rejected before evaluation.

Canonicalization gives syntactically redundant forms one identity. It orders operands of commutative operations, removes repeated role swaps, normalization, and identical clamping, eliminates neutral additions and multiplications, and folds representable constants. A program hash is the SHA-256 of its canonical token sequence under schema `cassi.generative-abstraction.program.v1`. The measured canonicalization controls confirmed equal hashes for reversed operands of addition and for a folded versus directly expressed constant.

The generator does not enumerate the full interpreter language. With a token capacity of 16 and a field capacity of 12 programs, it produces:

| Candidate family | Canonically distinct programs |
|---|---:|
| Direct position of either role | 2 |
| Sum or ordered difference of role positions, with unnormalized and normalized variants | 6 |
| Temporal displacement of either role | 2 |
| Guarded boundary transition and role headroom | 2 |
| **Total** | **12** |

Commutative canonicalization reduces the initially duplicated sum expressions, yielding the twelve observed candidates. Conditional, scalar-arithmetic, norm, and other valid interpreter constructions are not generated by this experiment. The reported per-position `mask_widths` describe token diversity in this fixed set; they are not learned production masks.

### 10.2 Typed observations and explicit hypothesis expansion

`ProgramContext` contains a current typed `ObservationView`, an optional previous view, an action displacement, sensor and output precision, a regime, and a possibly unresolved role assignment. The relational adapter accepts only a supported two-entity JSON view or two-plane raster view and turns it into the `RelationAtoms` boundary defined in Section 9. A temporal context requires the same entity identities before and after. When a transition carries Thalamus admission metadata, it must also retain exact Mnemic references within the fixed work budget; a paired-world admission requires one exact event identity.

`EACH_OBJECT` is not a scalar language operand. The parser rejects it inside an `AbstractionProgram`. Instead, `expand_each_object()` performs an explicit outer expansion:

\[
\{\text{visible objects}\}
\longrightarrow
\{\text{one typed context sequence per object identity}\}.
\]

All frames must retain the same world, episode, self identity, and object set. The first context for each candidate has no fabricated previous observation; later contexts link the prior typed view. `resolve_entities()` then evaluates the selected interior program and its learned action operators for every explicit candidate sequence. A unique candidate inside the action-residual tolerance is selected, multiple eligible candidates are `ambiguous`, and no eligible candidate is `exhausted`.

Role assignment follows the same evidentiary rule. A passive two-entity view provides no transition with which to identify the acted role and therefore returns `ambiguous`. Given one action and its observed successor, `resolve_roles()` tests both self assignments against the selected operator and accepts a role only when exactly one residual is within tolerance.

The measured diagnostic with one relevant object and two objects following different visible dynamics selected `relevant-target` with residual \(4.84\times10^{-4}\), while the distractor residuals were approximately \(0.2399\). When all three objects were dynamically indistinguishable under the observed action sequence, the resolver returned all three identities as equivalent and abstained. The mechanism detects observable consequence differences; it does not infer hidden relevance.

### 10.3 Operator fit, consequence evidence, and bilateral refinement

Grouped training transitions deposit one forward operator for every supported program/action pair. For program \(p\), action \(a\), and context \(x\),

\[
z_p(x)=\operatorname{eval}(p,x),\qquad
\widehat z_p(x')=A_{p,a}z_p(x).
\]

The operator moments occupy the same basin layout used by bilateral counterflow. Ordinary interior and temporal trajectory generation uses the learned \(A_{p,a}\). The guarded boundary candidate also receives grouped moments, but its evaluator and trajectory generator treat it as a direct transition law containing `ACTION_DELTA` and `CLAMP`; the predicted consequence comes from the fixed program and configured action displacement rather than from \(A_{p,a}\).

Evaluation observations and multistep sequences produce:

\[
E_p=
w_c e_{\mathrm{closure}}
+w_i e_{\mathrm{inverse}}
+w_m e_{\mathrm{composition}}
+w_v e_{\mathrm{invariance}}
+w_d e_{\mathrm{collision}}
+w_b e_{\mathrm{boundary}}
+w_u e_{\mathrm{uncertainty}}
+w_o e_{\mathrm{outcome}}
+w_k e_{\mathrm{complexity}}.
\]

The reference weights are

\[
(w_c,w_i,w_m,w_v,w_d,w_b,w_u,w_o,w_k)
=(1,0.5,1,2,2,2,1,8,0.01).
\]

Closure measures one-step agreement. Inverse evidence measures an action followed by its configured inverse. Composition measures complete observed sequences. Invariance compares paired contexts. Collision penalizes action consequences that are indistinguishable within the \(0.04\) equivalence tolerance. Boundary evidence isolates boundary-regime residual. Uncertainty is the propagated sensor interval relative to program magnitude. Outcome combines mean sequence residual with the fraction of sequences outside the trajectory tolerance. Complexity is canonical token length divided by the capacity of 16.

Four bilateral refinement breaths do not generate or rewrite syntax. They convert the fixed evidence into two activation views. The upward energy is

\[
E_p^\uparrow=
e_{\mathrm{closure}}
+0.5e_{\mathrm{inverse}}
+e_{\mathrm{composition}}
+2e_{\mathrm{invariance}}
+2e_{\mathrm{collision}}
+e_{\mathrm{uncertainty}}
+0.01e_{\mathrm{complexity}},
\]

while the downward energy is

\[
E_p^\downarrow=2e_{\mathrm{boundary}}+8e_{\mathrm{outcome}}.
\]

Cross-coupled relaxation updates normalized upward and downward activations, and program coherence is their geometric mean:

\[
\gamma_p=\sqrt{u_p d_p}.
\]

This gives observational fit and measured consequence separate influence without allowing either to override the hard eligibility thresholds.

### 10.4 Field-resident records and selection

The `GenerativeAbstractionController` inherits the single `QiFieldState` contract. Its counterflow basin region stores the action-operator moments. Additional scale-zero rows in the ninth component plane store, for each program:

- canonical token identifiers and length;
- regime and role-equivalence masks;
- support and successful consolidation count;
- all nine raw evidence terms;
- total score, upward activation, downward activation, and coherence.

The controller retains configuration and the fixed candidate generator but no learned program table outside the tensor. Validation recomputes the expected canonical program at each program identifier and rejects changed token values. Consequently, tokens stored in the field authenticate each fixed candidate representation; the controller returns a selected candidate only after read-only comparison of the records. The tokens are not mutable learned syntax.

A program is eligible only when it has support, outcome error no greater than \(0.08\), and total score no greater than \(0.1\). Eligible programs are grouped by role-equivalence hash. Groups are ranked first by their greatest coherence and then by score. Selection requires a coherence margin of at least \(10^{-3}\) unless only one group remains. Role-swapped members of the winning group remain listed in `equivalent_program_ids`, even though a canonical representative is returned.

`consolidate_program()` is the only post-selection confirmation write in this controller. It increments the returned field's consolidation count only when the selected program gives the same value for the predicted and observed contexts within the trajectory tolerance. A mismatched consequence returns the original field unchanged. Selection, trajectory generation, role resolution, and entity resolution are read-only.

### 10.5 Measured abstraction families

The twelve-candidate run selected one equivalence class in each supported regime:

| Regime | Canonical representative | Score | Measured interpretation |
|---|---|---:|---|
| Interior | `ROLE_A POSITION ROLE_B POSITION SUBTRACT PACK4` | 0.008701 | Ordered Cartesian role-position difference; role-swapped counterpart retained as equivalent |
| Temporal | `ROLE_B DELTA PACK4` | 0.001975 | Observed displacement of the second role |
| Boundary | `ROLE_B POSITION ROLE_A POSITION ACTION_DELTA ADD LOWER_BOUND UPPER_BOUND CLAMP SUBTRACT PACK4` | 0.028443 | \(p_B-\operatorname{clamp}(p_A+\Delta a,\ell,u)\), the second-role position minus the acted role's clamped next position |

The interior program and its learned action operators were exactly invariant under the measured renaming-and-translation pair. Their direct program and predicted-consequence residuals were both zero.

Trajectory generation enumerates the finite action product for the requested step count. Historical mode asks which action sequence could connect two observed endpoints. Prospective mode asks which configured action sequence reaches the goal under the selected program. These modes intentionally differ when several action strings have the same endpoint:

| Probe | Result |
|---|---|
| Stationary endpoint, historical | `ambiguous`; 9 endpoint-equivalent three-action sequences |
| Stationary endpoint, prospective | `selected`; deterministic representative `(down, up, up)`; 9 equivalent sequences; execution residual 0 |
| Moving target, prospective | `selected`; `(up, up, down)`; 9 equivalent sequences; execution residual 0 |
| Boundary composition | 12/12 exact outcomes, maximum residual 0, no false settlements |
| Interventional role binding | 32/32 selected correctly; 0 false-confident bindings |
| Passive role binding | Four tested quadrants all `ambiguous` |

The prospective `selected` status does not mean that the hidden historical action sequence was uniquely recovered. It means that a deterministic member of an explicitly reported endpoint-equivalent set reaches the requested consequence.

Sensor uncertainty also widens equivalence rather than creating artificial uniqueness. Across amplitudes \(0,0.01,0.02,0.03,0.06\), repeated calls were deterministic and retained the hidden three-action sequence, but the equivalent set grew from 9 to 56 candidates. The result supports interval-aware retention of a valid candidate, not unique action identification under noise.

### 10.6 Equivalence, lesions, and persistence controls

Three kinds of equivalence remain visible:

1. canonicalization joins syntax trees that compute the same normalized expression;
2. role equivalence groups programs related by swapping the two declared roles;
3. trajectory equivalence retains every action string inside the residual band.

None of these is resolved by arbitrary identifier order. Historical ambiguity remains an abstention; prospective selection returns a deterministic representative together with the full equivalent set.

The causal controls behaved as follows:

- rotating outcomes across the program corpus changed the field and made interior selection `exhausted`;
- clearing every winning program-evidence row made selection `exhausted`;
- clearing the selected program's action-operator basins removed operator support and made trajectory generation `exhausted`;
- an exact predicted/observed consequence incremented the field-resident consolidation count from 0 to 1;
- a mismatched consequence did not consolidate and left the field hash unchanged;
- checkpoint dump and reload were byte-exact, field-exact, and selection-exact;
- read-only selection, trajectory generation, and role resolution preserved the field hash.

The scenario made zero teacher or model calls. It also confirmed that `DerivedCounterflowRuntime` rejects `mode: "generate_abstraction"`; no live provider route currently exposes this controller.

### 10.7 Scope boundary

The supported result is bounded typed-program selection. Fixed code defines the interpreter, constructs twelve candidates, groups action observations, evaluates evidence, and executes selected arithmetic. The field owns learned operator moments, program support, evidence, coherence, and consolidation count; the controller computes the resulting selection read-only from those field-resident quantities. Lesions to those coordinates remove the measured capability.

The experiment does not establish task-independent synthesis, learned grammar production, arbitrary program length, unconstrained object discovery, hidden relevance inference, or general code generation. It covers a two-entity, two-dimensional, four-action relational world with three explicit regimes. Even `EACH_OBJECT` is external finite hypothesis expansion rather than a learned iterator inside the program.

Calling this capability “generative abstraction” is justified only in the narrow sense that fixed code constructs a bounded candidate set not limited to the four basis labels of Section 9. It must not be read as evidence that field dynamics invented the program language or searched its full grammar. The natural-language experiment provides an independent test of how sharply that limitation matters.

## 11. Natural-Language Boundary Experiments

The text comparison asks whether the same field-owned selection principle extends from exact symbolic laws to unrestricted continuation. Its negative result is part of the capability map: fixed byte-span and surface-role grammars transfer perfectly when the target law is inside their candidate set, but neither grammar explains held-out natural prose. A next-symbol field with high teacher-forced training accuracy also fails autoregressively, while a stricter Phi field abstains.

### 11.1 Corpus and exact continuation contract

The experiment loads 40 training episodes and 16 held-out episodes from exact source byte ranges. The training set spans four sources: `light-novels`, `textbook-train`, `tinystories-instruct-train`, and `wikitext103-train`. Each episode is at most 96 bytes and is reconstructed from its source offset, prompt length, continuation length, and payload SHA-256. The baseline and Phi paths are checked against the identical list of training episode digests.

For held-out episode \(i\), the observable contract is

\[
\widehat y_i = y_i
\]

as byte-for-byte equality over the complete continuation. Four metrics remain distinct:

| Metric | Meaning |
|---|---|
| Exact continuation | Every emitted byte equals the complete held-out target |
| Position-byte accuracy | Fraction of target positions containing the correct byte |
| Mean edit similarity | `SequenceMatcher` ratio, used only as an approximate diagnostic |
| False settlement | A nonempty output that is not the exact target |

An empty output is an abstention. It is counted separately from both an incorrect nonempty continuation and an exact continuation. No approximate score is promoted to exact success.

### 11.2 Whole-byte-span candidate programs

The byte-span instance of `TextAbstractionController` contains ten canonical programs with at most three tokens. Every program begins with `PROMPT`, optionally applies one deterministic transform, and ends with either `FIT` or `REPEAT_TO_LENGTH`. The available transforms are ASCII upper, lower, and swap case; byte or word reversal; and suffix widths 1, 2, 4, or 8. `FIT` takes the prompt suffix or pads it with spaces to the required continuation length. `REPEAT_TO_LENGTH` repeats its input bytes to exactly that length.

For each regime and program, the field stores support, position accuracy, edit similarity, exact rate, outcome error, complexity, bilateral activation, score, and eligibility. The selection score is

\[
S_p=
(1-a_{\mathrm{position}})
+(1-a_{\mathrm{edit}})
+8e_{\mathrm{outcome}}
+0.01c_p,
\]

where \(e_{\mathrm{outcome}}=1-a_{\mathrm{exact}}\). A candidate is eligible only when outcome error is at most \(0.05\). Four alternating activation breaths use position-plus-edit fit in one direction and exact rate minus complexity in the other, but activation cannot make an ineligible program selectable.

No byte-span program fit the 40 natural continuations within the outcome threshold. Natural selection therefore returned `exhausted`; all 16 held-out episodes produced empty outputs, giving 16 abstentions and zero false settlements.

A target-aware diagnostic oracle chose the best of the ten programs separately for each held-out target. This oracle is inadmissible at inference because it reads the answer, but it measures candidate-set expressiveness. Even with that advantage it achieved 0/16 exact continuations and 16 false settlements, with position-byte accuracy \(0.1372\) and mean edit similarity \(0.2474\). The natural failure is therefore not merely a ranking error: the required continuations are absent from the byte-span candidate set.

### 11.3 Symbol-level trajectory baselines

The next-symbol trajectory baseline uses the corpus-field path described in Sections 6 and 7. Its recorded teacher-forced next-event accuracy was

\[
0.9840\quad\text{on training events},
\qquad
0.3013\quad\text{on held-out events}.
\]

Four recorded training-generation examples were exact. Those measurements do not imply stable held-out autoregression. On the 16 held-out prompts, the actual generator produced a nonempty continuation every time but matched none exactly:

| Held-out measure | Next-symbol trajectory |
|---|---:|
| Exact continuations | 0/16 |
| False settlements | 16/16 |
| Position-byte accuracy | 0.0747 |
| Mean edit similarity | 0.2765 |
| Stop reasons | 4 `end_turn`; 12 `max_output_symbols` |

Teacher forcing evaluates the next observed symbol while the correct history is continuously supplied. Autoregression feeds each selected symbol back into the next step, so an early error changes the later field context. The gap between \(98.40\%\) teacher-forced training accuracy and 0/16 exact held-out continuations is therefore the relevant result; teacher-forced accuracy cannot substitute for generation.

The Phi harmonic baseline used the same training episodes but a separate Phi field and learned trajectory tape. It returned `field_abstained` for all 16 held-out prompts, produced no bytes, and recorded no false settlements. Neither baseline changed its learned corpus memory or trajectory-tape hash during generation.

### 11.4 Role-level surface grammar

The higher-level comparison tokenizes valid UTF-8 into a lossless sequence of word, whitespace, and punctuation surfaces. Concatenating the emitted surfaces reconstructed all 112 tested prompt and continuation spans exactly. When at least six word symbols are available, the role binder assigns the final six to

\[
(E_A,P_A,E_B,E_C,P_B,E_D).
\]

Shorter inputs cyclically repeat their available words to fill the same six slots. This is a deterministic surface-position hypothesis, not a semantic parser. It does not infer which words are entities or predicates from meaning.

A second `TextAbstractionController` instance receives twelve fixed `RoleProgram` values: eight single clauses and four two-clause discourse forms. They can reorder the six bound surfaces, choose `because` or `then`, and emit a final period. The two instances share field-resident evidence and eligibility machinery but have separate grammars, state magic values, and field tensors.

Increasing the representational level did not solve unrestricted continuation. Natural role selection was `exhausted`, producing 16 abstentions and no false settlements. A target-aware oracle over all twelve role programs still achieved 0/16 exact continuations and 16 false settlements; its position-byte accuracy was \(0.0990\) and mean edit similarity \(0.2944\). A more structured candidate space improved one approximate diagnostic but did not contain the natural targets.

### 11.5 Positive symbolic controls

The failure on prose is interpretable because both candidate systems succeed when the data-generating law belongs to their grammar:

| Control regime | Selected law | Held-out exact |
|---|---|---:|
| ASCII upper | `PROMPT ASCII_UPPER FIT` | 16/16 |
| Four-byte periodic replay | `PROMPT SUFFIX_4 REPEAT_TO_LENGTH` | 16/16 |
| Word reversal | `PROMPT REVERSE_WORDS FIT` | 16/16 |
| Entity swap | \(E_B\,P_A\,E_A\texttt{.}\) | 16/16 |
| Predicate rebind | \(E_A\,P_B\,E_B\texttt{.}\) | 16/16 |
| Discourse reversal | \(E_C\,P_B\,E_D\ \text{because}\ E_A\,P_A\,E_B\texttt{.}\) | 16/16 |

All three role controls also remained 16/16 exact after every prompt word was replaced by a deterministic unfamiliar symbol. This establishes transfer of surface roles independently of the original word identities. It does not establish semantic renaming because the binding rule is positional and the control targets are generated from that same rule.

The positive controls validate three specific mechanisms: the intended program is represented, training evidence makes it eligible, and a field-selected fixed law transfers to held-out inputs. They do not make the natural targets members of either grammar.

### 11.6 Negative result and abstention semantics

The complete held-out comparison is:

| Surface | Output policy | Exact | Abstentions | False settlements | Mean edit similarity |
|---|---|---:|---:|---:|---:|
| Byte-span field selection | Emit only a training-eligible program | 0/16 | 16 | 0 | 0 |
| Byte-span target-aware oracle | Choose the best candidate after reading the target | 0/16 | 0 | 16 | 0.2474 |
| Surface-role field selection | Emit only a training-eligible role program | 0/16 | 16 | 0 | 0 |
| Surface-role target-aware oracle | Choose the best role program after reading the target | 0/16 | 0 | 16 | 0.2944 |
| Next-symbol trajectory field | Autoregressive field argmax | 0/16 | 0 | 16 | 0.2765 |
| Phi harmonic field | Require a learned continuation trajectory | 0/16 | 16 | 0 | 0 |

`exhausted` means no candidate satisfied the fixed outcome-error boundary. `ambiguous` would mean that multiple eligible candidates remained within the selection margin; that was not the natural-prose outcome. A false settlement is more serious than low approximate similarity because the system emitted an unsupported complete answer. Correct abstention preserves the fact that the current state and grammar do not determine the continuation.

Causal controls support that interpretation. Clearing a selected positive-control program changed its regime to `exhausted`. Rotating training targets made the corresponding byte and role regimes `exhausted` and changed their fields. Both state formats reloaded byte-exactly, replayed every selection exactly, and remained unchanged during inference. The comparison used no teacher or model calls and no provider route.

There was deliberately no fallback to a language model. A fallback could produce fluent output, but the resulting continuation would not establish that the Cassi field or its measured candidate grammar owned the behavior. The supported conclusion is therefore negative and specific: the current field surfaces can learn and transfer exact bounded symbolic laws, but they do not yet support exact held-out natural-language continuation. Their safe behaviors at this boundary are explicit exhaustion or field abstention, not ungrounded fluency.


## 12. Training and Experience Deposition

The word *training* needs a narrower meaning here than it has in a parameterized neural model. CassiFI does not optimize a second set of weights and then copy their predictions into a field. In the measured task gauntlet, fixed code constructs a bounded candidate set, evaluates those candidates against supplied examples, and deposits the resulting evidence into designated rows of one `QiFieldState.field`. The tensor is the sole adaptive object, while the candidate grammar, evaluation rule, field layout, and update rule remain fixed machinery.

This separation also distinguishes three operations that can otherwise be conflated:

1. **experience construction** supplies exact inputs and target outcomes;
2. **evidence deposition** changes the adaptive tensor;
3. **checkpoint commitment** durably records that successor tensor and its provenance.

Only the second operation is learning in the field-state sense. A receipt, journal entry, corpus manifest, or Python metric can influence or document an update without becoming a parallel learned state.

### 12.1 Training without learned weights

For a regime \(r\), the text-task controller enumerates its fixed program set \(\mathcal P_r\). Each program \(p\) is executed on every training example and assigned support \(n_p\), position accuracy \(a^{\mathrm{pos}}_p\), edit similarity \(a^{\mathrm{edit}}_p\), exact-match rate \(a^{\mathrm{exact}}_p\), outcome error

\[
e^{\mathrm{out}}_p=1-a^{\mathrm{exact}}_p,
\]

and fixed program complexity \(c_p\). Its comparison score is

\[
S_p=
\left(1-a^{\mathrm{pos}}_p\right)
+\left(1-a^{\mathrm{edit}}_p\right)
+8e^{\mathrm{out}}_p
+0.01c_p .
\]

A program is eligible only when \(e^{\mathrm{out}}_p\le 0.05\). Four alternating refinement breaths convert the same deposited evidence into an activation value; they do not alter program tokens or generate candidates. The record written for each regime/program pair can therefore be represented as

\[
m_{r,p}=
\left(
n_p,\,
a^{\mathrm{pos}}_p,\,
a^{\mathrm{edit}}_p,\,
a^{\mathrm{exact}}_p,\,
e^{\mathrm{out}}_p,\,
c_p,\,
\alpha_p,\,
S_p,\,
\mathbf 1[e^{\mathrm{out}}_p\le0.05]
\right).
\]

`learn_regime()` clones the predecessor tensor and replaces only the rows allocated to \(r\). Each row contains the regime identifier, program identifier, canonical token length, numeric token encoding, and \(m_{r,p}\). Selection is subsequently recomputed read-only from those field records. No optimizer, gradient tape, learned embedding table, replay model, or mutable program store participates.

The limitation is as important as the ownership result. Targets are supervised by fixed task-generating functions, and the controller computes all candidate executions and statistics. The field owns the persistent comparative evidence; it does not discover the task family, synthesize the grammar, or learn the scoring law. The gauntlet accordingly identifies its candidate space as `bounded_fixed_program_grammar` and explicitly reports both `semantic_acquisition: false` and `task_independent_learner: false`.

### 12.2 Curriculum construction

The general-task curriculum is derived from the frozen natural-language corpus receipt used in Section 11, but it imposes a different split. The source receipt contains 40 nominal training episodes and 16 nominal holdout episodes across `light-novels`, `textbook-train`, `tinystories-instruct-train`, and `wikitext103-train`. The gauntlet deterministically chooses `wikitext103-train` as the held-out source, retains 30 base training episodes from the other three sources, and uses four base holdout episodes from the selected source.

Every selected base episode is expanded through the same thirteen supported task families:

- identity, ASCII upper, ASCII lower, ASCII swap-case, byte reversal, and word reversal;
- periodic suffix completion at widths 1, 2, 4, and 8;
- entity swap, predicate rebind, and two-clause discourse reversal.

Thus each family receives 30 training examples and four source-held-out examples. Family balance is structural rather than sampled: every family is constructed from the same ordered base episodes. Three additional evaluations compose already selected laws—suffix-2 then uppercase, swap-case applied twice, and uppercase then word reversal—but those composed tasks are not inserted as direct training regimes.

Each ingress observation receives an episode identifier from its split, ordered index, and the first sixteen hexadecimal digits of the source payload digest. Its boundary packet separately binds run, world, and session identities; profile and clock hashes; request and codec; logical/capture index; split stream and source sequence; payload shape, dtype, and bytes; and the predecessor journal head. The task record retains the source ID and the packet, view, and journal-reference identities. The curriculum digest binds the task-family names, candidate namespaces, full canonical program catalogs, selected holdout source, payload-set hashes, and transfer-task map. In the completed run:

| Item | Measured value |
|---|---:|
| Selected training base episodes | 30 |
| Selected holdout base episodes | 4 |
| Training payload SHA-256 | `cf61fe80592308eec2c737f80692831934ead854ce9905ac5576035b11315865` |
| Holdout payload SHA-256 | `f1fdd774614e98ca4878a0c674ac1747445cf5076d7f5c29d21f1b36f617ffde` |
| Curriculum SHA-256 | `3bec5558e267d47c54aa3527d057d90a742a5bed9e40bcd1219309df2e829567` |

Training ingress uses the exact UTF-8 codec. Holdout ingress rotates four registered codecs—UTF-8, canonical JSON UTF-8, contiguous tensor bytes, and opaque bytes—whose fixed adapters recover the same task view. This tests transport invariance of the represented task; it does not constitute learned translation between modalities.

### 12.3 Holdout discipline

Four different notions of separation occur in the experiments and must remain distinct.

| Separation | What is actually withheld | Supported interpretation |
|---|---|---|
| Raw receipt split | The source receipt's nominal train/holdout episode labels | The underlying receipt still contains all four sources in both nominal partitions |
| Selected gauntlet split | All examples from `wikitext103-train` | The task curriculum is leave-one-source-out and has no selected training/holdout source overlap |
| Renamed relational holdout | Entity and world identifiers used during evidence collection | Tests identifier invariance of the relational mechanism in Section 9 |
| Composed task holdout | A direct training regime for a known composition | Tests execution of two already available fixed laws, not discovery of a new law |

The completed receipt therefore reports the four-source list under `raw_receipt_source_overlap`, while also reporting `selected_split_source_overlap: []`, `source_disjoint: true`, and `episode_disjoint: true`. Those statements are compatible because they refer to different partitions. The source-disjoint result belongs to this gauntlet, not retroactively to the natural-continuation comparison of Section 11.

The renamed and composed controls answer still different questions. Renaming tests whether a result survives changed identifiers. Composition tests whether selected primitive programs can be called in sequence. Neither establishes that an unseen semantic operation was inferred. Likewise, 13/13 exact results under each of the four holdout codecs establish invariance under fixed registered projections only. The run reports learned cross-view transfer as `unsupported` with reason `fixed_projection_only`.

### 12.4 Retention and interference

The retention probe begins with an empty task field, where every supported family is `exhausted` and scores 0/4. It then deposits the thirteen supported regimes sequentially. After every update, the runner hashes every unrelated regime namespace, requires those rows to remain byte-identical, and reevaluates all previously learned holdouts. Natural and deliberately ambiguous control regimes are deposited afterward, bringing the total to fifteen sequential updates.

For family \(j\) after update \(k\), let \(A_{j,k}\) be exact holdout accuracy and \(A_j^\star\) its accuracy immediately after learning. The reported retention summaries are

\[
A_{\min}=\min_{j,k\ge j}A_{j,k}=1.0,
\qquad
\Delta_{\max}=\max_{j,k\ge j}\left(A_j^\star-A_{j,k}\right)=0.0.
\]

All thirteen supported families finished at 4/4 exact. The three compositions absent from direct training each finished at 4/4 exact. The natural control remained `exhausted` at 0/4, the conflicting case-map control remained `ambiguous` at 0/4, and outcome-shuffled training remained `exhausted`.

The lesion control establishes local causal ownership. Clearing program 8, the eligible `suffix4` row, changed `suffix4` selection to `exhausted`, while `ascii_upper` remained at accuracy 1.0. This supports retention by disjoint field namespace in the current fixed layout. It does not establish resistance to catastrophic interference when two experiences compete for the same rows, when candidate definitions change, or when noisy online updates replace the stored evidence.

### 12.5 Long-horizon behavior

The long-horizon probe first serializes and reloads the trained field byte-exactly, then confirms that all inference paths preserve the state hash. It subsequently applies 256 cyclic repetitions of the already learned family updates. Because each update deterministically replaces its regime rows with the same evidence derived from the same curriculum, the final tensor returns the same exact state identity:

| Field property | Completed-run result |
|---|---:|
| Shape | \([1,6606,1]\) |
| Dtype/device | `torch.float64` / CPU |
| Sequential curriculum updates | 15 |
| Long-horizon updates | 256 |
| Maximum absolute stored value | 30.0 |
| Checkpoint reload exact | true |
| Inference preserved state | true |
| Long-horizon fixed point | true |
| State SHA-256 | `c0d1a222c89ec3a400ddae312f47657165f2d479185f3755d1b9d4619fc560f5` |
| Checkpoint SHA-256 | `0e55ad09949dd4ce287f0169c4941b6d871b3970822d8e9ba0f62ad86e9e0a7b` |

This is an idempotence result for repeated exact deposition, not a convergence theorem for arbitrary experience streams. The run does not vary labels, add stochastic noise, alter the grammar, or repeatedly merge contradictory evidence. Boundedness at 30.0 is an observed property of this finite trajectory, not a global stability proof.

The associated exact ingress journal contained 35 entries, had head digest `388da60c29911c58661cda5ca6803c8cd774312fbd1e738e05f961ba65c12026`, and replayed exactly after restart. The completed `cassi.general-task-gauntlet-result.v2` receipt itself had SHA-256 `42eee4352d8076a15f7716919880d1fee679bcab58945860a27f4ad746a44de5`.

### 12.6 Temporary statistics

The implementation distinguishes adaptive state from fixed and temporary support structures:

| Class | Examples | Adaptive status |
|---|---|---|
| Sole adaptive state | `QiFieldState.field` with deposited regime/program records | Adaptive and checkpointed |
| Fixed machinery | Program catalogs, token codes, scoring law, codec adapters, field layout, task generators | Persistent code/configuration, not learned |
| Operational provenance | Corpus receipts, ingress journal, episode manifests, checkpoint headers, stream watermarks | Persistent evidence or control state, not learned task state |
| Ephemeral computation | Decoded examples, program outputs, `SequenceMatcher` values, score dictionaries, refinement work buffers | Discarded after deposition |

The test harness enforces this boundary at runtime. Its sentinels observed one adaptive field object, zero optimizer construction attempts or steps, zero teacher calls, zero Qwen calls, zero forbidden imports, zero subprocess attempts, and zero socket attempts. Those zeros exclude hidden runtime delegation; they do not remove the fixed supervision encoded by the task-generating functions.

All diagnostic checks passed, but capability readiness did not. The receipt remains `not_ready`, with `learned_cross_view_transfer` as the missing capability. That negative readiness result prevents exact bounded program learning, fixed codec invariance, and program composition from being overstated as open-ended task learning.

## 13. Persistence and Provider Architecture

Persistence is not one interchangeable CassiFI file format. The profile-governed Qi-flow state and the live language provider solve related but different problems. `QiFlowStateV3` is a portable single-tensor state whose meaning is pinned by an explicit `QiFlowProfile`. The provider stores a composite `QiFieldState` containing the active Phi-language, counterflow, and mnemic-condensation regions plus bounded operational metadata. A loader for one format must not accept the other.

This distinction corrects two common ambiguities. First, a profile hash identifies a complete semantic and numerical contract, not merely a tensor shape. Second, an OpenAI-shaped model identifier identifies a protocol endpoint; it does not imply that a conventional language-model object or weight checkpoint exists behind it.

### 13.1 Versioned field profiles

`QiFlowProfile` uses schema `cassi.qi-flow-profile.v1`, while its governed tensor uses state schema `cassi.qi-flow-state.v3`. These version numbers describe different contracts and are intentionally not collapsed. `QiFlowProfile.from_defaults()` materializes every default, applies explicit overrides, validates linked quantities, attaches the source-pinned contract-root digest, and computes seven semantic subhashes:

- state contract;
- boundary action;
- world protocol;
- session storage;
- provider API;
- backend capacity;
- security evidence.

The profile also binds the spatial topology, component ordering, mode and scale counts, active shapes, state bounds, byte order, dtype, batch limit, backend, execution schedule, and exact source identity. The resulting `profile_sha256` authenticates the canonical materialization. At a v3 state boundary there is therefore no permissible inference of missing geometry or numerical defaults from tensor dimensions alone.

The live provider has a separate identity chain. Its fingerprint binds protocol version 8, model label `cassi-phi-harmonic-language-v1`, the Phi engine fingerprint, initial Phi checkpoint and state hashes, shared-layout fingerprint, initial shared-state hash, counterflow configuration and initial-state hashes, and mnemic configuration and initial-state hashes. A Qi-flow profile digest and a provider fingerprint answer different questions and are not substitutes for one another.

The configured Phi corpus checkpoint is an immutable startup seed. It establishes the initial trained Phi state and participates in the provider fingerprint, but completion requests do not overwrite it. Mutable experience is committed instead to per-session `cassi.shared-field-provider-session.v4` checkpoints under the configured state directory, where each successor contains the packed Phi, counterflow, and mnemic-condensation field plus bounded operational metadata.

### 13.2 Canonical checkpoint

The profile-governed v3 frame is

\[
\texttt{magic}
\;\Vert\;
\texttt{uint64(header\_bytes)}
\;\Vert\;
\texttt{canonical\_JSON\_header}
\;\Vert\;
\texttt{raw\_little\_endian\_tensor}.
\]

Its exact header binds schema, layout, profile, contract root, state contract, execution schedule, topology, source identity, backend, dtype, shape, raw-byte count, raw-payload digest, semantic state digest, and header self-digest. Loading rejects an unknown or legacy magic value, noncanonical JSON, extra or missing keys, profile disagreement, backend or dtype conversion, impossible shape, wrong length, payload-hash mismatch, state-hash mismatch, self-hash mismatch, nonfinite values, and values outside the profile bounds. Raw bytes are authenticated and value-checked before the owned tensor is exposed.

The provider session frame is separately versioned as `cassi.shared-field-provider-session.v4`. It contains its own magic prefix, bounded canonical header, one contiguous field payload, canonical operational metadata, and a terminal SHA-256 checksum over the preceding body. The header binds the session and provider identities, all three component configuration and state hashes, layout fingerprint, full shared-state hash, dtype, shape, exact payload and metadata lengths, and payload/metadata hashes. The implementation accepts only the exact header key set and a total frame no larger than 64 MiB.

These hashes establish byte identity and contract compatibility. They do not by themselves prove that an observation is true, that a task was learned semantically, or that two differently configured runtimes are behaviorally equivalent.

### 13.3 Atomic storage and rollback

Both persistence paths write a sibling temporary file and then call `os.replace` rather than modifying the live checkpoint in place, but their durability details differ. The profile/v3 save helpers close the temporary file before replacement without an explicit `flush()` or `fsync()` call; the guarantee claimed here is write-then-replace isolation, not fsync-backed crash durability. The provider path is stronger: it creates a uniquely named temporary file exclusively, writes all bytes, flushes and `fsync`s that file, and only then replaces the committed path. It does not fsync the parent directory, so full power-loss durability of the directory entry is not claimed. A failed provider write removes the temporary file. Per-session reentrant locks serialize load-transition-save transactions within one provider process so that two in-process requests cannot independently advance the same checkpoint from one predecessor. These locks are not an interprocess lease; one provider process must own a state directory unless an external coordinator supplies that exclusion.

Generation and component consolidation operate on working tensors. The previous checkpoint is replaced only after the successor field and metadata have serialized successfully. Errors are surfaced as provider failures stating that the prior checkpoint was retained. The active provider tests cover a failed Phi completion retaining its prior checkpoint, malformed or incompatible frames, restart continuation, duplicate/idempotent counterflow commits, and exact preservation of committed bytes.

Here *rollback* means preservation of the immediate committed predecessor when a new transaction fails. The store is not a multi-version history database and does not synthesize a prior state after a successful replacement. `/v1/context/reset` handles only an explicitly identified incompatible checkpoint: the caller must supply its exact file digest and provider fingerprint, the provider rechecks both at the point of use, and the file is renamed to an `.incompatible` archive. A compatible checkpoint cannot be reset through that route.

### 13.4 Shared field layout

`SharedFieldLayout` joins three validated component tensors in fixed order:

\[
F_{\mathrm{shared}}
=
F_{\Phi}
\;\Vert\;
F_{\mathrm{counterflow}}
\;\Vert\;
F_{\mathrm{mnemic}} .
\]

Each component must have rank three with a positive shape of the form \([S,9M,1]\). Its exact shape and flat offset are bound into `cassi.shared-field-layout.v2`. `phi()`, `counterflow()`, and `mnemic()` return narrow views of the same underlying storage; tests verify identical storage pointers rather than copied shadow states. `with_phi()`, `with_counterflow()`, and `with_mnemic()` construct a successor by cloning the single shared tensor and replacing only the designated slice.


The layout permits specialized controllers without creating multiple adaptive owners. Completion updates the Phi slice, an observed counterflow commit updates the counterflow slice, and context condensation updates the mnemic slice. The latter is the provider's mnemic-condensation field; it must not be confused with CassiCore's exact Mnemic Field record store. Operational metadata—stream watermarks, idempotency ledgers, and the last completion receipt—is serialized beside the tensor but is not a second learned representation.

### 13.5 OpenAI-compatible protocol adapter

The HTTP adapter exposes a deliberately narrow OpenAI-compatible shape. `GET /v1/models` advertises `cassi-phi-harmonic-language-v1`; `POST /v1/chat/completions` accepts role/content messages and returns a `chat.completion` object, or deterministic server-sent-event chunks when `stream: true`. The identifier and envelope let existing clients address the provider. Internally, the request enters the fixed Phi controller, advances the session field, commits the shared checkpoint, and returns the field receipt.

Compatibility is strict rather than permissive. A request must contain 1–128 exact `{role, content}` messages, end with a user message, fit within the 4 MiB route bound, name the advertised model, and request between 1 and the configured maximum output-symbol count. `temperature` must be exactly zero. `top_k`, `top_p`, `seed`, and `cassi_session_seed` are rejected instead of accepted and ignored.

Persistent replay also requires an explicit session identity in `user` or `metadata.cassi_session_id`. If neither is supplied, the adapter generates an ephemeral UUID, which intentionally creates a new session. The caller may supply a bounded request ID; otherwise another UUID is generated. The response's `created` field is wall-clock telemetry. Consequently, deterministic field evolution does not imply byte-identical HTTP envelopes when session ID, request ID, or telemetry time is left implicit.

On the first request for a session, the complete message list is presented to the field. Once a checkpoint exists, only the final new user message is sent to the controller; retained context is expected to reside in the session field. There is no provider route to a fallback model.

### 13.6 Provider operations

The active protocol surface is:

| Endpoint family | Operation | State effect |
|---|---|---|
| `/health`, `/v1/models` | Runtime identity and advertised model | Read-only |
| `/v1/chat/completions` | Phi field generation and OpenAI-shaped response | Replaces the Phi slice on successful commit |
| `/v1/context/recall`, `/v1/context/status` | Mnemic candidate scoring and session inspection | Read-only |
| `/v1/context/observe` | Exact context-event condensation or inhibition | Replaces the mnemic slice when a supported transition commits |
| `/v1/context/reset` | Archive an exactly identified incompatible checkpoint | Administrative file transition, not learning |
| `/v1/counterflow/plan` | Bilateral proposal and support classification | Read-only and mutation-checked |
| `/v1/counterflow/commit` | Consolidate one observed ordered event | Replaces only the counterflow slice; duplicate commits are idempotent |
| `/v1/ingress/append` | Append an exact universal-data packet | Journal-only; `adaptive_state_changed: false` |
| `/v1/ingress/read`, `/v1/ingress/replay` | Recover exact payloads or bounded journal history | Read-only |
| `/v1/world/turn`, `/v1/world/result` | Authenticated particle-world proposal/result exchange | Operation-specific receipt and bounded idempotency ledger |

World routes are disabled unless a bearer token is configured, and any optional world-Qwen bridge is restricted to loopback HTTP. The remaining provider surface is itself bound to loopback by configuration, but loopback placement is not equivalent to general-purpose authentication. Deploying the service beyond that trust boundary would require a separate access-control layer.

Exact ingress intentionally abstains from adaptation when no registered semantic task exists. A packet can be durably journaled and replayable while its receipt reports `unsupported`, a specific reason such as `no_semantic_task` or `malformed_input`, and no field change. Data acceptance, semantic interpretation, and adaptive commitment are separate states.

### 13.7 Determinism contract

For a committed session transition, the computational claim is

\[
\left(F_{t+1},y_t,\rho_t\right)
=
\mathcal T\!\left(
F_t,\,
x_t;\,
H_{\mathrm{provider}},\,
H_{\mathrm{engine}},\,
H_{\mathrm{layout}}
\right),
\]

where \(F_t\) is the exact predecessor field, \(x_t\) is the validated canonical request or event, \(y_t\) is the field result, and \(\rho_t\) is its receipt. Fixed hashes, canonical JSON, exact request limits, single-thread CPU configuration, per-session serialization, and rejection of sampling controls make this transition reproducible within the verified runtime.

That contract has defined limits. It does not promise cross-device floating-point identity without a separate parity result. It does not cover random ephemeral session/request identifiers or wall-clock response telemetry. It also does not turn concurrent requests into a commutative update: within one provider process, the session lock gives them a serial order, and different valid orders may represent different experience histories.

Stream and event operations add ordered identities. Context and counterflow commits carry stream ID, sequence, previous event or event digest, and a persisted watermark. Exact duplicates return the prior committed identity without a second consolidation; stale or conflicting sequences are rejected. Ingress binds source stream, source sequence, journal predecessor, payload descriptor, and packet digest. Determinism therefore depends on explicit event order as well as exact bytes.

### 13.8 Receipts

Receipts make each accepted boundary auditable without creating another adaptive model. A completion response records provider and engine fingerprints, initial checkpoint identity, input and output field hashes, trained-tape hash, stop and reply kinds, output-byte hash, the complete field-text receipt and its hash, and the committed checkpoint path and digest. The stored metadata revalidates the receipt's exact key set, state lineage, symbol bounds, output digest, and self-hash on load.

Counterflow planning returns hashes recomputed from the actual Phi and counterflow slices before the call and verifies that neither slice changed. An observed commit adds ordered event identity, counterflow input/output hashes, consolidation evidence, duplicate status, and committed checkpoint identity. Context receipts similarly identify the selected addresses, condensation or inhibition transitions, mnemic input/output hashes, stream watermark, and checkpoint. Exact-ingress receipts bind packet, packet-object, payload-manifest, journal-head, source-stream, source-sequence, adapter-view, semantic status, and `adaptive_state_changed`.

Trajectory, support, uncertainty, abstention, and mutation fields are operation-specific rather than forced into one universal receipt schema. `selected`, `ambiguous`, `exhausted`, and `unsupported` remain distinct outcomes. A receipt hash authenticates the encoded receipt; it does not validate an unchecked caller assertion or promote an approximate score into success. Provider boundaries therefore recompute component identities where they are available, preserve explicit failure reasons, and report whether the canonical field actually changed.

## 14. Integration Boundaries

The current integration graph contains several independently configurable paths rather than one measured three-system loop. `CassiCore` can construct an optional HTTP client for the CassiFI context provider. A separate optional client reads CassiCosmos telemetry at port 7599 and never writes to that engine. The retained `FieldShadowBridge` implements deposit and projection traffic, but the inspected `mind-runtime` composition does not instantiate it. CassiFI's world routes stage and observe an external particle program, while the active repository contains no CassiFI-to-CassiCosmos execution adapter.

These distinctions determine the admissible integration claims. Component tests establish wire validation and local state transitions. A standalone receipt can establish one physical endpoint. Neither kind of evidence establishes an end-to-end path through processes that were not run together. This section therefore describes each authority boundary and then assigns a measured status to each cross-layer path.

### 14.1 Mnemic references

CassiCore's `MnemicExactStore` is the authority for exact records. For a record with identifier \(i\), node type \(n\), and complete content \(c\), its revision is

\[
r=\operatorname{SHA256}\!\left(i\Vert\texttt{0x00}\Vert n\Vert\texttt{0x00}\Vert c\right).
\]

A condensation address identifies an exact-record byte span without making the field a second content store. With the fixed schema

\[
s_{\mathrm c}=\texttt{cassicore.mnemic.condensation-address.v1},
\]

start and end UTF-8 byte offsets \(b_0,b_1\), and semantic kind \(k\), the exact-store codec computes

\[
a_{\mathrm c}=
\operatorname{hex}\!\left[
\operatorname{SHA256}\!\left(
J([s_{\mathrm c},i,r,b_0,b_1,k])
\right)_{0:16}
\right],
\]

where \(J\) is the compact sorted-key canonical-JSON encoding used by the Mnemic field protocol.

Counterflow transition identities use a separate codec and schema:

\[
s_{\leftrightarrow}=\texttt{cassicore.mnemic.counterflow-address.v1},
\]

\[
a_{\leftrightarrow}=
\operatorname{hex}\!\left[
\operatorname{SHA256}\!\left(
\texttt{JSON.stringify}(
[s_{\leftrightarrow},i,r,b_0,b_1,k]
)
\right)_{0:16}
\right].
\]

Both codecs currently hash arrays containing only strings and integers and return the first 16 digest bytes as 32 lowercase hexadecimal characters. That present wire similarity does not merge the contracts: the schema labels and encoding functions remain distinct, and receipts retain the full source tuple.

| Schema | Use |
|---|---|
| `cassicore.mnemic.condensation-address.v1` | Exact-record manifests supplied to field-native context recall and mnemic condensation |
| `cassicore.mnemic.counterflow-address.v1` | Before/after identities carried by counterflow transition evidence |

The exact store maintains an address manifest beside its records. Resolution retrieves the current record, recomputes revision, condensation address, span, semantic kind, and content digest, and rejects disagreement. CassiFI's HTTP validators enforce bounded tuple fields and digest/address syntax; they do not recompute a caller-supplied address from the tuple. The provider's context-observation path condenses or inhibits only when the normalized event already contains a string `field_address`; an event without one may advance the stream watermark but produces no mnemic-address transition. CassiCore supplies condensation addresses on recallable exact-record events. During recall, CassiCore sends a bounded query and a manifest of eligible opaque addresses; CassiFI may return one listed address or abstain. CassiCore rejects an address outside the submitted manifest and resolves an accepted address back to its exact local record.

The shared canonical-wire fixture verifies the generic TypeScript and Python canonical-JSON encoders and their SHA-256 outputs. It does not exercise the counterflow `JSON.stringify` identity codec and is not a receipt from a live CassiCore process talking to a live CassiFI process.

### 14.2 Journal-to-field composition

Three durable structures must not be conflated:

1. the CassiCore SQLite Mnemic transition journal is the exact ordered source of memory, feedback, and action events;
2. CassiFI provider metadata stores the remote stream watermark and idempotency records associated with a session field;
3. CassiFI's universal-data ingress journal stores `BoundaryPacket` payloads for the separate `/v1/ingress/*` surface.

The conditional CassiCore-to-CassiFI path is assembled in `CassiCore/packages/mind-runtime/src/boot.ts`. When `fieldIntelligenceUrl` or `CASSI_FI_PROVIDER_URL` is absent, exact Mnemic journaling continues and field-native recall/counterflow remain disabled. When configured, `createHttpContextFieldClient()` is attached to the exact store's field-event notification and uses the provider's context and counterflow routes.

For each unacknowledged exact event, the client performs the ordered sequence

\[
\text{plan}_{t^-}
\;\longrightarrow\;
\text{observe}_{t}
\;\longrightarrow\;
\text{commit-consequence}_{t}
\;\longrightarrow\;
\text{acknowledge}_{t}.
\]

`/v1/counterflow/plan` runs before the new event is observed, preventing the event's consequence from entering its own prediction evidence. `/v1/context/observe` then condenses or inhibits the exact event in the provider's mnemic component. `/v1/counterflow/commit` consolidates the observed transition when the event has an eligible before/after interpretation. Only after all applicable provider operations succeed does CassiCore advance its local acknowledged watermark. A plan is read-only; observation and consequence commitment are separate mutations.

Recall also begins by draining pending journal events. CassiCore then sends only the bounded query and eligible address manifest to `/v1/context/recall`. The provider returns an address, signal, margin, and availability; the exact candidate content returned to the caller is resolved from CassiCore's store. The field selects relevance, while the exact store retains byte ownership.

The TypeScript client and Python endpoints are both implemented and directly tested against local harnesses. No retained cross-process receipt in the inspected artifacts proves that the current CassiCore runtime and current CassiFI provider completed this entire sequence together. It is therefore an implemented conditional integration, not a measured end-to-end result.

### 14.3 Recovery order

Before draining new events, the CassiCore client requests `/v1/context/status` and reconciles the provider checkpoint and stream watermark:

1. **Checkpoint classification.** A compatible or missing checkpoint proceeds. An incompatible checkpoint is sent to guarded reset with its exact digest and reported fingerprint; any other status fails closed.
2. **Ahead-of-source rejection.** If the provider sequence exceeds the local exact journal head, synchronization stops because the provider claims an event CassiCore cannot supply.
3. **Lost-ack recovery.** If the provider is ahead of CassiCore's acknowledged watermark but not ahead of the journal, the client resubmits consequence commits through the provider watermark. Idempotent provider responses allow CassiCore to restore its local acknowledgment without applying a second field update.
4. **Forward drain.** Beginning at the reconciled remote sequence, the client processes each remaining event in exact sequence as plan, observation, consequence commit, and local acknowledgment.

A failure before acknowledgment leaves the event pending for the next drain. The asynchronous notification path records a classified, nonfatal client failure rather than discarding the exact journal event. `recall()` explicitly awaits a drain, and shutdown attempts one final drain. The optional startup verifier recomputes the canonical event chain, predecessor links, head, and acknowledged prefix; an invalid acknowledged action prefix blocks new action starts while ordinary exact reads remain available.

This is ordered retry and reconciliation, not distributed consensus. Provider session locks are process-local, CassiCore remains the sole exact-journal authority, and the implementation assumes one owning process for each local state directory unless a separate coordinator supplies exclusion.

### 14.4 CassiCosmos interaction

CassiFI's `/v1/world/turn` and `/v1/world/result` form a proposal/result protocol. A token-authenticated turn validates bounded context and constraints, normalizes an explicit particle program or invokes the configured planner, binds the input and program digests, rebuilds the Phi training tape with the prompt/staging exchange, commits the session field, and returns either the staged program or a clarification. It does not execute that program. When the optional loopback Qwen planner is configured, its response is an external dependency and requires separate evidence; the turn receipt identifies the planner used. An external coordinator must authorize the proposed operation, apply it to a physical backend, and return an exact result carrying the same request and program identities. `/v1/world/result` then records the observed outcome exchange in the Phi field and commits it once. Duplicate turn and result requests are idempotent; conflicting reuse of a request identifier is rejected.

The active provider test exercises that HTTP protocol with a synthetic particle outcome whose `world_id` is `cosmos-main`. A label and synthetic outcome do not demonstrate CassiCosmos execution. The current CassiCosmos tree contains none of the proposed adapter targets—`CassiCosmos/scripts/cassi_qi_world_adapter.gd`, `CassiCosmos/scenes/qi_world_adapter.tscn`, or `CassiCosmos/scenes/verify_qi_world_adapter.tscn`—and the active CassiFI provider does not open a 7599 client.

CassiCosmos itself exposes two distinct surfaces at port 7599:

- `deposit`, `step`, `state`, `readout`, and `project` operate on the physical two-fluid GPU field;
- `qi_snapshot`, `qi_state`, `qi_project`, and `qi_clear` operate on a separate canonical-Qi byte mirror.

The retained `CassiCosmos/_diag/qi_state_bridge_receipt.json` uses schema `cassi.qi.cosmos-bridge-receipt.v1` and proves one windowed GPU run of the second surface: CassiCosmos accepted an 884,736-byte native canonical-Qi state, verified its SHA-256 and contract digest, reproduced the expected top-eight projection, and treated a duplicate revision idempotently. The receipt identifies a CassiQwen source state and explicitly reports `model_or_sampler_state_written_by_cosmos: false`. It therefore establishes a read-only Qi mirror, not a current CassiFI-to-CassiCosmos bridge.

CassiCore's composed `MindFieldTelemetry` is narrower still. When explicitly enabled, it sends only `{"cmd":"readout"}` to 7599 and derives advisory summaries. It never sends `deposit`, `step`, or `clear`. The vendored `FieldShadowBridge` can encode deposits and request projections, but no `new FieldShadowBridge(...)` occurs in the inspected `mind-runtime` boot path. Its implementation and unit tests do not make it a live composed connection.

### 14.5 Physical versus cognitive fields

The word *field* names multiple state spaces in the unified project, not one shared tensor.

| State | Representation | Current owner | Meaning |
|---|---|---|---|
| CassiFI cognitive field | `QiFieldState.field`, normally CPU `float64` in the measured cognition experiments | CassiFI controller/provider | Learned evidence, operators, programs, trajectories, and bounded control state |
| CassiFI profile-governed Qi state | `QiFlowStateV3` under an explicit profile | CassiFI Qi-flow runtime | Canonical multiscale Yang/Yin state with profile-bound semantics |
| CassiCosmos physical field | GPU `float32` three-dimensional \(E_Y,E_I,q,\rho,\mathbf v,\ldots\) buffers | CassiCosmos physics or mind engine | Evolving two-fluid physical substrate |
| CassiCosmos Qi mirror | Fixed 884,736-byte snapshot buffer separate from the physical field | CassiCosmos mind engine | Read-only transport and top-\(k\) projection of an external canonical-Qi state |

An adapter may relate these spaces, but shared terminology is not state identity. The current readout client maps physical field arrays to advisory scalars without updating CassiFI. The canonical-Qi mirror stores and projects external bytes without writing the physical field or source model. The uncomposed `FieldShadowBridge` defines an engram-to-deposit encoding, but that encoding is not an equivalence between a Mnemic record, a CassiFI cognitive row, and a physical two-fluid cell.

No inspected receipt demonstrates bidirectional learning across the CassiFI and CassiCosmos states. Any future closed loop must specify the projection in each direction, state which side is authoritative after each transition, bind both contracts and source hashes, and measure the joined run rather than infer it from component success.

### 14.6 Integration status table

| Cross-layer path | Current evidence | Status | Excluded claim |
|---|---|---|---|
| CassiCore exact Mnemic journal \(\rightarrow\) CassiFI context/counterflow HTTP client | Boot wiring is conditional on `CASSI_FI_PROVIDER_URL`; TypeScript client tests cover ordered counterflow identity construction, and Python endpoint tests independently cover plan/commit validation and field effects | **Implemented but not measured end to end** | No retained receipt proves both current processes completed one shared event stream |
| CassiCore condensation-address manifest \(\leftrightarrow\) CassiFI recall | Exact-store address generation/resolution tests, the generic canonical-wire fixture, provider address-shape checks, manifest membership validation, and exact local resolution | **Implemented but not measured end to end** | The generic fixture does not exercise the counterflow identity codec, and no live transport receipt joins the processes |
| CassiCore \(\leftarrow\) CassiCosmos physical-field telemetry | Default-off `MindFieldTelemetry` sends read-only `readout`; synthetic TCP tests cover decoding and failures; the Cosmos endpoint is separately exercised | **Implemented but not measured end to end** | No same-run Core/Cosmos receipt; no physical mutation |
| CassiCore `FieldShadowBridge` \(\leftrightarrow\) CassiCosmos deposit/project | Client class and focused tests exist, but current `mind-runtime` boot does not instantiate it | **Implemented but not measured end to end** | Not a live path in the inspected composition |
| CassiFI provider world turn/result protocol | Actual loopback HTTP server test covers token enforcement, staged program identity, synthetic result observation, idempotency, and conflicts | **Live and directly measured** at the provider boundary | The test does not execute CassiCosmos |
| External canonical-Qi state \(\rightarrow\) CassiCosmos Qi mirror | GPU receipt SHA-256 `305ba3813613819314d9f5f641dac7a17aa114814b50091708cc763b64fa66f0` records `PASS` for a CassiQwen source | **Live and directly measured** for that read-only mirror | Not evidence for a CassiFI source or physical-field coupling |
| CassiFI cognitive field \(\leftrightarrow\) CassiCosmos physical execution | Proposed world-adapter files are absent; provider and Cosmos expose complementary but unjoined boundaries | **Interface or proposed integration only** | No current closed cognitive/physical loop |

The integration tests run for this section comprised 19 CassiCore client/telemetry tests, one CassiCore canonical-wire fixture test, and five focused CassiFI provider tests. They establish the component behaviors listed above while preserving the end-to-end limitations.

## 15. Experimental Methodology

CassiFI experiments use deterministic scenarios, exact evidence artifacts, and causal controls rather than treating a passing task output as sufficient evidence of field ownership. A result is reported only at the scope supported by a named retained receipt or a focused behavioral test. Its evidence description identifies the tested implementation, initial field, fixed configuration, input set, intervention, mutation allowance, outcome rule, and artifact when those dimensions apply. If a retained artifact omits a dimension, the claim is narrowed rather than filling the gap by inference. A useful experiment record is

\[
\mathcal E=
\left(
H_C,\,
H_{F_0},\,
H_X,\,
I,\,
s,\,
d,\,
\varepsilon,\,
H_{F_1},\,
H_Y
\right),
\]

where \(H_C\) is the configuration or contract identity, \(H_{F_0}\) and \(H_{F_1}\) are predecessor and successor field identities, \(H_X\) binds the inputs, \(I\) names the intervention, \(s\) is the seed, \(d\) records device and dtype, \(\varepsilon\) is the declared numerical tolerance, and \(H_Y\) binds the evaluated output. An externally published artifact SHA-256, when available, is computed over the exact stored receipt bytes and reported separately; embedded state, checkpoint, payload, and output hashes bind their respective objects and are not interchangeable with the receipt hash. Not every surface uses every field, but omitted dimensions must be marked inapplicable or unavailable rather than silently inferred.

Where selection semantics apply, outcomes retain the runtime taxonomy `selected`, `ambiguous`, `exhausted`, and `unsupported`. Other experiments use their exact domain status rather than forcing it into that vocabulary. Exact success counts, abstentions, false settlements, residual maxima, and worst-case margins are reported separately. Deterministic enumerations use counts and extrema; they are not assigned sampling \(p\)-values.

### 15.1 Causal field dependence

The primary question is whether the measured capability changes when the adaptive field changes while the executable code, configuration, input, and random seed remain fixed. Let

\[
Y(F;X,C)
\]

denote the observable result from field \(F\), input \(X\), and fixed controller/configuration \(C\). A minimal matched intervention compares

\[
Y(F_{\mathrm{trained}};X,C)
\quad\text{with}\quad
Y(F_{\mathrm{control}};X,C),
\]

where \(F_{\mathrm{control}}\) is an untrained, shuffled, lesioned, or counterfactual state with a recorded hash. The experiment supports field dependence only when the output difference follows the declared intervention and no unrecorded adaptive object changes.

The strongest current designs add specificity controls. A targeted evidence lesion should remove the corresponding capability while leaving an unrelated family intact. A field counterfactual should change the selected referent, action, basis, or program without changing the query. A shuffled correspondence should destroy selection rather than merely lower an internal score. Reinstating the exact predecessor bytes should restore the predecessor behavior when restoration is part of the protocol.

This method establishes causal dependence on encoded field content. It does not establish that the controller learned its grammar, operators, scoring rule, or observation codec unless those objects were themselves mutable field content in the tested implementation.

### 15.2 Deterministic replay

Replay begins from an authenticated state and canonical input. A CPU result is classified as exact only when the selected surface promises equality of:

- loaded field bytes and semantic state digest;
- canonical input and configuration identities;
- categorical outcome and selected identifiers;
- emitted program, action, or symbol sequence;
- protected-state and successor-state digests;
- receipt fields designated deterministic by the schema.

Transport telemetry is excluded when the protocol deliberately generates a UUID, timestamp, temporary path, or socket port. Those fields must be normalized or caller-supplied before byte-identical envelope comparison.

GPU parity is a different contract. Discrete selections, layout identities, and state-machine outcomes may be exact while floating-point trajectories are compared under a declared tolerance. A CPU/GPU test must report the device, dtype, tolerance, maximum residual, and whether equality applies to raw bytes, discrete state, or numerical observables. One result must not silently substitute for another.

Replay should occur in a newly constructed controller or process when the claim includes re-instantiation. Repeating a method on the same live object only establishes local repeatability and may preserve hidden caches.

### 15.3 Persistence

Persistence tests separate serialization integrity from behavioral continuation:

1. serialize the authenticated predecessor state;
2. record checkpoint, field, configuration, and protected-region hashes;
3. close the owning runtime;
4. construct a fresh runtime from the checkpoint;
5. compare exact field identity where the format promises exactness;
6. execute the next held-out query or transition in both branches;
7. compare outcome, successor field, and deterministic receipt identities.

An exact checkpoint round trip alone proves storage fidelity, not retained capability. A matching next transition proves continuation under the exercised input. Conversely, behaviorally similar output does not excuse a state-hash mismatch when the checkpoint format promises exact bytes.

Failure tests inject an error before commitment and compare the committed file, in-memory field, and external world snapshot with their predecessor values. Atomic-replace behavior, fsync behavior, and process locking are recorded separately because they provide different durability guarantees. A test that reloads a valid checkpoint does not establish crash safety.

### 15.4 Read-only inference

The question “does querying leave trained memory unchanged?” is too broad unless the operation's mutation contract is stated first. CassiFI uses three classes:

| Operation class | Examples | Required check |
|---|---|---|
| Strict read-only | Program/basis selection, counterflow planning, context recall, status, CassiCosmos `readout`/projection | Whole relevant field or component hash is identical before and after |
| Working-state inference with protected learned memory | Phi generation or iterative thought whose transient lanes may evolve | Declared trained tape/evidence region is unchanged; allowed working lanes and final successor are reported |
| Consolidation | `learn_regime`, confirmed abstraction, context observation, observed counterflow commit, world-result observation | Mutation occurs only in the declared component after eligibility or outcome is known |

The protected region must be selected by layout semantics before the call. Choosing it after inspecting the differences would make the test circular. Read-only receipts should also report a mutation check, not rely solely on API naming.

### 15.5 Ablation

An ablation removes a defined field dependency while preserving a valid state layout. Clearing arbitrary bytes is insufficient: it can create a malformed state whose failure says nothing about the target mechanism. The protocol therefore records:

- the exact row, basin, operator, evidence band, or address support being changed;
- predecessor, ablated, and unrelated-control hashes;
- state validation after the intervention;
- expected affected and unaffected behaviors;
- categorical status, residual, and false-settlement outcome.

A successful causal ablation causes the target operation to become `exhausted`, `ambiguous`, or observably wrong while a matched unrelated operation remains intact. Evidence ablation and operator ablation answer different questions and are reported separately. Shuffled-label and shuffled-outcome controls complement lesions by preserving capacity while destroying correspondence.

### 15.6 Held-out transfer

Every transfer result names the axis that differs between evidence deposition and evaluation:

| Axis | Examples | What remains fixed |
|---|---|---|
| Episode | New prompts, trajectories, or initial positions from the same source/regime | Source and task law |
| Source | Leave-one-source-out text episodes | Fixed task-family generator and grammar |
| Identifier | Renamed entities, worlds, records, or sessions | Relational structure and task |
| Ordering/composition | Untrained action sequences or composed selected programs | Primitive operators/programs |
| Dynamics | Moving targets, boundary starts, coordinate noise, distractors | Controller and declared observation surface |
| Representation | JSON/raster or registered text/tensor/opaque codecs | Fixed adapter and canonical semantic view |
| Semantic view | A genuinely new mapping between modalities or representations | No fixed projection capable of solving the mapping |

Source-disjoint, episode-disjoint, and identifier-renamed results are not interchangeable. A fixed codec adapter establishes transport invariance, not learned semantic transfer. A composed result establishes reuse of known primitives only if the exact composed sequence was absent from deposited evidence. A target-aware role or oracle may diagnose available information but cannot be counted as target-blind transfer.

Training and holdout payload digests, source lists, identity sets, and any overlap are emitted in the same receipt. When a result reports both raw-corpus overlap and selected-split disjointness, both partitions must be shown.

### 15.7 Long-horizon boundedness

Long-horizon experiments identify the transition being repeated. Three cases require different interpretations:

1. **Dynamical evolution** repeatedly calls a field evolution operator and measures actual state trajectory.
2. **Deterministic redeposition** repeatedly rewrites the same rows from the same evidence, testing idempotence rather than autonomous convergence.
3. **Agent interaction** alternates observation, inference, action, and consolidation, testing the bounded composite lifecycle.

For horizon \(H\), the minimum report is

\[
B_H=\max_{0\le t\le H}\|F_t\|_\infty,
\qquad
N_{\mathrm{bad}}=\sum_{t=0}^{H}
\mathbf 1[\neg\operatorname{finite}(F_t)],
\]

together with clamp or saturation counts, state drift, terminal outcome, and the exact update count. If \(H\) repeated redepositions return the initial trained hash, the result is an exact fixed point for that frozen evidence. It does not estimate a convergence rate or prove a global stability region. A numerical bound observed on one trajectory is reported as an observed maximum, not a universal bound.

### 15.8 Forbidden-surface monitoring

A field-only claim is tested at runtime rather than inferred from architecture diagrams. The active gauntlet replaces relevant call surfaces with sentinels and records attempts to:

- import configured model-provider modules;
- construct or step a `torch.optim` optimizer;
- start subprocesses through `subprocess.Popen` or `os.system`;
- create network sockets;
- invoke a teacher or Qwen path.

The receipt also records preloaded forbidden modules, relevant environment keys, device, optimizer steps, provider calls, and the count of adaptive field states. A blocked attempt fails the run; a zero count supports only the instrumented process and interval. It must not be generalized to integration tests that intentionally open loopback sockets or to entrypoints not executed under the audit.

Static dependency inspection supplements these sentinels but cannot replace them. Conversely, runtime sentinels cannot detect an uninstrumented native extension or state loaded before the audit; the monitored surfaces and startup boundary must be listed.

### 15.9 Baselines

Baselines are chosen to isolate the claimed advantage rather than maximize contrast:

| Baseline | Question answered |
|---|---|
| Untrained field with identical controller | Does deposited field evidence matter? |
| Identity or no-op program | Does the task require a nontrivial transformation? |
| Shuffled correspondence or outcomes | Does exact pairing matter at fixed capacity? |
| Fixed-phase or matched-capacity controller | Does bilateral/counterflow refinement add behavior beyond allocated storage? |
| Exact-context lookup | Is field selection doing more than returning an exact known continuation? |
| Endpoint-only or reduced-intermediate trajectory | Which temporal constraints are necessary for composition? |
| Simple symbolic trajectory | Can a fixed explicit rule solve the same observable task? |
| Target-aware oracle | Is the needed information present in the observation surface at all? |

Matched comparisons preserve input information, candidate budget, field width where relevant, stopping rule, and evaluation metric. A target-aware oracle is an upper-bound diagnostic and is labeled as such; it is not a deployable peer baseline. An exact lookup baseline may be stronger than a statistical language baseline on a repeated context and should be reported even when it outperforms the field.

Each baseline returns the same public outcome schema as the field path wherever practical. Results report all cases, including abstentions and false confidence, rather than counting only successful selections. The retained result set applies these methods to the named receipts and current experimental outcomes.

Evidence aggregation follows artifact lineage. Phase receipts nested in a top-level gauntlet receipt are parts of the same run, not independent replications, and repeated assertions over one scenario do not increase its sample count. Canonical denominators are reported once, focused tests are identified as controls rather than additional trials, and diagnostic success remains separate from capability readiness.

Capability and readiness are evaluated at the scope of the experiment. The dedicated paired JSON–raster scenario can establish bounded bidirectional transfer within `cross_view_scope: registered_relational_task_only`, while the general-task gauntlet separately reports `learned_cross_view: unsupported` because its four-codec comparison uses only fixed projections. The gauntlet's `not_ready` status therefore marks the absence of broader learned semantic cross-view transfer; it does not erase the narrower paired-transfer result.

## 16. Results

The results below are deterministic evaluated cases, not population estimates. The primary integrated artifact is `CassiFI/artifacts/general-task-gauntlet/receipt.json`, schema `cassi.general-task-gauntlet-result.v2`. Its exact 51,118 stored bytes have SHA-256 `42eee4352d8076a15f7716919880d1fee679bcab58945860a27f4ad746a44de5`. The nested reproduction phase is retained as `CassiFI/artifacts/general-task-gauntlet/reproduction.json`; both artifacts record `diagnostic_checks_passed: true` and `readiness_validated: false`. The reproduction `*_OK` strings are harness-completion markers, so the capability claims below use their nested counts and controls. The nested phase belongs to the same gauntlet lineage and is not counted as an independent replication.

The grounded action, spatial, reference, and temporal curricula have separate retained receipts at:

- `CassiFI/artifacts/cassi-qi-grounded-language/training-receipt.json`;
- `CassiFI/artifacts/cassi-qi-spatial-language/training-receipt.json`;
- `CassiFI/artifacts/cassi-qi-reference-language/training-receipt.json`;
- `CassiFI/artifacts/cassi-qi-temporal-language/training-receipt.json`.

Counterflow composition is execution evidence from the standalone command `cd CassiFI && python run_grounded_counterflow_deliberation.py`, which returned `NOVEL_COUNTERFLOW_COMPOSITION_OK` in the verified run; its stdout is not a persisted receipt or a pytest result. The focused tests have distinct roles: `CassiFI/tests/test_cassi_bilateral_counterflow.py` covers bilateral counterflow plan/commit behavior, `CassiFI/tests/test_cassi_relational_basis.py` covers relational-basis and stress controls, and `CassiFI/tests/test_cassi_generative_abstraction.py` covers typed-generative and paired JSON–raster universal-data controls. These assertions establish the named controls; they are not additional statistical samples.

| Research question | Measured result | Present interpretation |
|---|---|---|
| Field causality and deterministic replay | 52/52 held-out cases across 13 registered task families were exact after field training; the matched untrained field was 0/52, shuffled outcomes exhausted, and a targeted lesion removed the affected family while preserving unrelated accuracy at 1.0 | Supported for the bounded candidate catalog and verified CPU state |
| Grounded transition learning | Action, spatial, reference, and temporal held-outs were exact in their registered curricula; shuffled, unknown-name, and substituted-layout controls changed or withheld the result as specified | Supported for finite grounded vocabularies |
| Exact compatible-edge composition | Both held-out three-action branches were composed from single-edge observations; deleting one required consequence prevented settlement, and changing the goal changed all three proposed actions | Supported for the tested two-branch graph |
| Relational basis selection | `target_minus_self` was selected from four coordinate hypotheses and reached exact world revisions on 32/32 held-out renamed examples; the minimum role margin exceeded 0.13 and maximum constraint residual remained below 0.005 | Supported for the registered basis family |
| Renaming, translation, and moving-target transfer | Token, runtime-label, layout-label, and symbolic relabelings preserved the relational program; moving-target execution had zero residual in the bounded scenario | Supported for declared transformations |
| Noise and boundary stress | The newer typed interval scenario retained the true action through noise amplitude 0.06 while preserving growing equivalence; the older relational stress path fell from 16/16 exact revisions at amplitudes through 0.01 to 0/16 at 0.06 and falsely chose among indistinguishable hidden targets in 10/16 cases | Mixed; robustness remains surface- and contract-dependent |
| Typed generative abstraction | A 12-program typed grammar produced an exact 12/12 boundary composition with zero false settlements and zero maximum residual; evidence and operator ablations exhausted | Supported as bounded program discovery, not unrestricted synthesis |
| Universal data and codecs | A paired JSON–raster experiment learned 32 source pairs, then answered 16/16 JSON→raster and 16/16 raster→JSON held-outs exactly; shuffled, missing-identity, and hash-only pairing controls failed. Its scope is `registered_relational_task_only`. Four gauntlet codecs separately produced 52/52 fixed-projection invariance cases | Bounded paired transfer and fixed-codec invariance supported; unrestricted semantic cross-view learning unsupported |
| Natural language | Four field surfaces and two target-aware oracle surfaces each achieved 0/16 exact continuations. Byte-span, surface-role, and Phi-harmonic field paths abstained 16/16; the next-symbol field and both target-aware oracles falsely settled 16/16 | Negative result; open-ended continuation unsupported |
| Retention, restart, and horizon | All 13 gauntlet families retained accuracy 1.0 with maximum drop 0; checkpoint reload was exact; 256 deterministic redepositions remained finite and reached an exact fixed point with maximum absolute field value 30 | Supported for the finite measured sequence |
| Current readiness | The integrated receipt reports `diagnostic_checks_passed: true`, `readiness_validated: false`, and `status: not_ready`; its sole missing item is `learned_cross_view_transfer` | Surface diagnostics passed, but the gauntlet does not validate broader learned semantic cross-view readiness |

### 16.1 Field causality and deterministic replay

The general-task gauntlet used a bounded fixed grammar containing 10 text programs and 12 surface-role programs, with one adaptive field of shape \([1,6606,1]\). Thirteen learnable families contributed four held-out cases each. After the registered observations were deposited, field selection and deterministic execution were exact on all 52 cases. Repeating the same 52 cases against the matched untrained field produced no selections and no exact outputs: every family exhausted.

The selected corpus split used `leave_one_source_out`: 30 selected training episodes, four selected holdout episodes, and `wikitext103-train` as the holdout source. The receipt therefore records `source_disjoint: true` and an empty `selected_split_source_overlap`. Its broader raw receipt provenance still has nonempty `raw_receipt_source_overlap` across `light-novels`, `textbook-train`, `tinystories-instruct-train`, and `wikitext103-train`. Source disjointness applies to the selected split, not to every raw receipt record.

The causal controls isolated the trained field content rather than merely comparing two initializations. Shuffling the observed outcomes produced `exhausted`. Clearing the field support associated with `suffix4` changed that family from `selected` to `exhausted`, while an unrelated family remained exact with accuracy 1.0. The ambiguous control retained two equivalent program identities, zero margin, and status `ambiguous`; it was not promoted to a winner.

The retained persistence phase reports exact checkpoint reload and an unchanged field across inference; ingress replay after restart is also exact. The runtime sentinel record reports one adaptive field state, no preloaded forbidden modules, zero forbidden-import attempts, and zero Qwen, teacher, optimizer, socket, and subprocess calls during the instrumented gauntlet interval. Together controls remove the relevant field result while preserving an unrelated result, which supports a causal field-dependence claim at this bounded surface. They do not show that the fixed program catalog was itself learned.

### 16.2 Grounded transition learning

The grounded-language curriculum trained ten action episodes comprising 930 events. Its five held-out action queries were exact, successor-state accuracy was 1.0, and the same five cases with shuffled associations had accuracy 0.0. Inference left the trained memory hash unchanged.

The spatial extension added 24 episodes and 1,336 events. It answered 6/6 held-out spatial questions exactly. In the substituted-layout control, the same relational question under a new layout was again 6/6 exact, while reuse of the original absolute label was 0/6. The action capability remained 5/5 after the spatial extension.

The reference stage retained action accuracy at 5/5 and measured three distinct reference behaviors: literal reference was 6/6, relation-family selection was 6/6, and entity-name binding was 3/3. An unknown name failed closed. The temporal stage then measured prediction at 5/5 against a 0/5 shuffled control, ordering at 4/4, counterfactual consequence selection at 5/5, and explanation at 5/5. It retained spatial accuracy at 6/6 and reference accuracy at 3/3; a reference-to-action-to-change round trip preserved memory exactly.

These results establish learned selection over registered actions, spatial relations, references, and temporal consequences. They do not establish free-form language understanding: the vocabularies, event encodings, and output families are finite and declared.

### 16.3 Exact compatible-edge composition

The standalone grounded counterflow run constructed two distinct three-action branches from one exact initial world revision and returned `NOVEL_COUNTERFLOW_COMPOSITION_OK`. Training supplied six observations, one for each edge; every source episode contained one action, and no complete three-action trajectory appeared in the observations. Both held-out goal requests nevertheless settled the exact three-action branch required to reach their respective goal.

The two goals used the same learned field. Changing only the exact goal changed all three action positions in the settled trajectory. Removing the middle consequence from one branch prevented a settled proposal and returned no action proposal. This is stronger than endpoint recognition because the missing-edge intervention preserves the start, goal, action alphabet, and remaining fragments while removing one required compatibility relation.

Planning preserved the canonical Phi and counterflow field hashes and left the checkpoint bytes unchanged. Observed commits persisted the counterflow state; imagined trajectories did not. Repeating the last commit returned the idempotent duplicate status rather than consolidating the event twice. The measured branch constraint residuals were nonzero—approximately 0.00102 and 0.00936—so “exact” here refers to the discrete action sequence and resulting goal revision, not a zero planning residual. The result supports compatible-edge composition for this two-goal, length-three graph; it does not measure arbitrary graph size, uncertain consequences, or open action discovery.

### 16.4 Relational basis selection

The relational-basis experiment compared four coordinate hypotheses while withholding renamed world identities and action sequences. The field selected `target_minus_self`, the only registered basis that satisfied the learned relational constraints across those cases. Planning reached the exact world revision in 32/32 held-out examples, including 16 with permuted entity order. The minimum role-binding margin exceeded 0.13 and the maximum constraint residual remained below 0.005.

Vocabulary relabeling, symbolic relabeling, runtime-label replacement, and renamed entity identities preserved the selected computation. Removing the supporting evidence returned `no_eligible_basis`; ablating the operator trajectory returned `exhausted`. Four separately measured boundary cases remained unsupported rather than being promoted from a low-residual approximation. These interventions distinguish selection of the relational transform from a system that merely emits one demonstrated action or associates one absolute label with one output.

The positive claim is limited to the registered four-basis candidate family. The experiment does not show discovery of an arbitrary coordinate chart or a continuous family of transformations.

### 16.5 Renaming, translation, and moving-target transfer

Several results test whether the learned behavior survives changes that preserve structure while altering surface identity:

- action-symbol renaming preserved all held-out relational actions;
- runtime object and relation labels could be replaced without changing the selected relative computation;
- the spatial curriculum answered 6/6 substituted-layout cases while selecting the old absolute label in 0/6;
- 32/32 held-out renamed relational worlds reached their exact revisions, including 16 cases with permuted entity order;
- the bounded moving-target scenario selected a temporal relational program, emitted actions \([2,2,3]\), and executed with residual 0.

The common invariant is an explicitly represented relation, not lexical similarity. These tests do not cover unrestricted synonymy, arbitrary affine transformations, or unregistered sensor semantics. Transfer is exact inside the declared transformation family.

### 16.6 Noise and boundary stress tests

The newer typed-generative scenario retained the correct action throughout a deterministic noise sweep with amplitudes \(0\), \(0.01\), \(0.02\), \(0.03\), and \(0.06\). The number of equivalent candidates increased from 9 at amplitudes \(0\) and \(0.01\) to 56 at \(0.06\), so the receipt preserves the growing uncertainty rather than presenting unchanged uniqueness. The exact 12-case boundary composition still had zero false settlements and maximum residual 0.

Structural negative controls were sharper than generic noise. Swapping an \(x\)-axis demonstration for a required \(y\)-axis relation, swapping the action axis, mirroring the learned rule, removing required evidence, or ablating the operator trajectory prevented the corresponding exact result. Three equally supported hidden candidates returned `ambiguous`; deterministic distractors with one relevant target selected that target.

The older relational stress path exposes the remaining boundary. It retained 16/16 exact revisions at noise amplitudes \(0\), \(0.002\), and \(0.01\), then declined to 13/16 at \(0.015\), 9/16 at \(0.02\), 4/16 at \(0.025\), 1/16 at \(0.03\), and 0/16 at \(0.06\). When three targets were observationally indistinguishable and the relevant one was hidden, it chose correctly in 6/16 cases, chose falsely in 10/16, and never abstained. Those results remain negative evidence even though the newer bounded typed scenario returns `ambiguous` on its three-way hidden-relevance case. Robustness is therefore established only for the named selector, control, and noise interval.

### 16.7 Typed generative abstraction

The generative-abstraction experiment searched a bounded typed grammar containing 12 canonical programs. The selected relation was assembled from typed role, position, action-delta, arithmetic, clamp, and packing operators. In the retained reproduction phase, its boundary composition executed 12/12 cases exactly, with no false settlements and maximum residual 0.

Causal ablations removed that result. Ablating the supporting evidence changed the selected program and returned `exhausted`; ablating the operator trajectory also returned `exhausted`. Failed consolidation left the field unchanged, while confirmed consolidation increased the retained abstraction count from zero to one. Constant-fold and commutative canonicalization controls produced equal program hashes where the transformations were semantically equivalent.

The result is program discovery inside a fixed typed grammar. The reproduction artifact separates candidate-space limits from ablation outcomes. `reproduction.generative_abstraction.candidate_space` records `semantic_acquisition: false` and `task_independent_learner: false`; `reproduction.generative_abstraction.receipt.ablations` records `operator_trajectory_status: exhausted` and `operators_supported: false`; the top-level reproduction record has `readiness_validated: false`. Here `operators_supported: false` is the result of removing the supporting operator trajectory, not a claim that the successful fixed grammar lacked primitive operators. The experiment therefore supports bounded field-generated relational abstraction, not invention of new primitive operators, open-ended concept acquisition, or unrestricted synthesis.

### 16.8 Universal-data and codec experiments

The dedicated universal-data experiment deposited 32 paired experiences, each represented once as canonical JSON and once as a deterministic raster, for 64 total experience views. It evaluated two directional held-out sets: JSON→raster was 16/16 exact and raster→JSON was 16/16 exact. These are the two reported denominators; their 32-query aggregate is not treated as a third independent result. Both directional maximum residuals were 0, and the selected program hashes matched those of the paired field. Shuffling the pairs, omitting pair identity, or supplying hashes without payload evidence prevented support. Restart preserved field bytes, replay, outputs, and frozen inference exactly. The retained candidate-space scope is `registered_relational_task_only`.

This is a measured bounded cross-view result. It learns from explicit paired identity over registered JSON and raster codecs. It does not imply that the runtime can infer an unseen semantic correspondence between arbitrary modalities.

The general-task gauntlet measured a different property. The same 13 registered task families were exact under each of four deterministic codecs—JSON UTF-8, opaque bytes, C-order tensor, and UTF-8—for 13/13 per codec and 52/52 total. Those codecs expose fixed projections of the same task information, so the receipt correctly labels `learned_cross_view` as `unsupported` with reason `fixed_projection_only`. Three compositions assembled already trained component families without direct training of the composite program and were exact on 12/12 held-out cases.

The gauntlet's ingress phase retained 35 journal entries. Training used `cassi.codec.utf8.v1`, held-out evaluation exercised all four codecs, and replay after reopening the journal was exact. A separate malformed-input control returned `unsupported` with reason `malformed_input` and `adaptive_state_changed: false`. Encoding acceptance and semantic acquisition are separate measured outcomes.

### 16.9 Natural-language negative results

Natural continuation remained unsupported. Four field surfaces—byte-span program selection, surface-role program selection, next-symbol trajectory continuation, and Phi-harmonic continuation—and two target-aware oracle surfaces each produced 0/16 exact continuations. The byte-span, surface-role, and Phi-harmonic field paths each abstained on all 16 cases. The autoregressive next-symbol field emitted unsupported complete answers and therefore recorded 16/16 false settlements.

The negative result is not explained solely by abstention thresholds or ranking. When target-aware diagnostics chose the best available byte-span and role-symbol programs after reading each target, both oracle conditions still produced 0/16 exact continuations and 16/16 false settlements. Positive controls using transformations such as uppercase, reverse words, repeated suffixes, entity swap, predicate rebind, and discourse reversal remained 16/16 exact, showing that the evaluation and execution paths returned exact outputs when the target law was present in the candidate language.

The measured boundary is therefore specific: the field can select and compose registered transformations over text-shaped data, but the current candidate languages do not express open-ended natural continuation.

### 16.10 Retention, restart, and long-horizon stability

The gauntlet trained the 13 positive families sequentially. After each addition, every previously trained family was reevaluated. Minimum retained accuracy remained 1.0 at every stage, and the maximum observed accuracy drop was 0. The final field exactly selected all 13 families after the ambiguity, natural-language, lesion, and shuffled-outcome controls.

Checkpoint persistence was byte- and field-exact for the tested CPU runtime. Reload restored the field shape and state digest exactly, and `inference_preserved_state` confirms that subsequent evaluation did not change the trained field. The grounded curriculum chain independently retained earlier action, spatial, and reference capabilities as later stages were added.

The long-horizon probe cycled through the 13 supported families for 256 total deterministic redeposition updates. The field remained finite, ended at the exact pre-probe state digest, and stayed within maximum absolute value 30. This is a stability result for repeated deposition, not evidence of autonomous field evolution over 256 environment transitions. It also does not establish cross-device floating-point identity or unbounded retention.

### 16.11 Current readiness assessment

The integrated gauntlet provides bounded evidence for sole adaptive field ownership, multi-family competence, held-out correctness, targeted negative controls, exact restart persistence, bounded long-horizon behavior, fixed-codec invariance, and the cross-task compositions reported in §16.8. Its registered natural control exhausted rather than selecting a program. Runtime sentinels observed no forbidden imports or Qwen, teacher, optimizer, socket, or subprocess use during the measured interval.

The same receipt returns:

```text
diagnostic_checks_passed: true
readiness_validated: false
status: not_ready
missing: learned_cross_view_transfer
```

Those literal fields require scope. Surface diagnostics completed, but readiness was not validated. The dedicated JSON–raster experiment measured learned paired transfer from 32 source experience pairs: JSON→raster was 16/16 exact, raster→JSON was 16/16 exact, and shuffled, missing-identity, and hash-only controls failed. What remains unsupported is the broader capability expected by the general-task gauntlet: learned semantic correspondence beyond `registered_relational_task_only` and beyond fixed projections of the same information. The bounded positive result and the broader negative readiness result are therefore compatible.

The current evidence supports field-owned selection, bounded relational abstraction, exact registered composition, persistence, and carefully delimited transfer. It does not support open-ended natural language, arbitrary hidden-relevance inference, unrestricted program synthesis, or a measured CassiFI–CassiCosmos cognitive/physical loop. `not_ready` is consequently the appropriate readiness status even though the individual bounded capabilities above are reproducible.

## 17. Related Work

The relevant comparison is architectural and evidentiary. CassiFI has not been evaluated head to head against the systems below, and the bounded exact tasks in §16 are not substitutes for their published benchmarks. This section therefore compares where experience-dependent state resides, which transformations are fixed or learned, how memory is retrieved, and which behaviors have actually been measured.

The scope distinction is especially important for the word *field*. The §16 cognition results use the CPU `QiFieldState.field`, normally in `float64`, with deterministic codecs, fixed transition machinery, and bounded candidate languages. CassiCosmos separately evolves a three-dimensional two-fluid GPU field. No retained experiment closes a bidirectional learning loop between those state spaces. Comparisons to neural fields, reaction–diffusion systems, and spatially local computation consequently position the Cassi research program; they do not recast the current cognitive results as measurements of a physical PDE substrate.

### 17.1 Reservoir computing

The liquid-state-machine formulation of [Maass, Natschläger, and Markram (2002)](https://doi.org/10.1162/089976602760407955) uses a high-dimensional recurrent dynamical system as fading memory for a time-varying input stream. A learned readout extracts task-relevant information from transient reservoir states without requiring the recurrent circuit itself to be constructed for each task. This provides a useful established analogy for CassiFI's use of fixed dynamics, distributed state, and query-dependent readout.

The adaptive-state assignment differs. In the cited reservoir formulation, task learning resides principally in readout parameters, while the reservoir trajectory is a transient response with fading memory. In the measured CassiFI task field, the codebooks, candidate grammar, scoring rule, transition rule, and readout procedure remain fixed; experience changes the checkpointed field values from which later selection is recomputed. The inspected implementation defines no trained output-weight matrix for this result. Exact reload, read-only inference, shuffled deposition, and a targeted field lesion test that assignment directly; the runtime-exclusion evidence remains limited to the instrumented process and interval specified in §15.8.

This distinction does not establish greater computational power or better temporal performance. CassiFI has no reservoir baseline, memory-capacity curve, or standard time-series benchmark. Its evidence is narrower: on registered tasks, changing the adaptive field while holding the surrounding procedure fixed changes the measured outcome in the predicted way.

### 17.2 Neural fields and reaction–diffusion systems

[Amari's neural-field analysis (1977)](https://doi.org/10.1007/BF00337259) studies pattern formation in a continuous lateral-inhibition field, while [Turing's reaction–diffusion account (1952)](https://doi.org/10.1098/rstb.1952.0012) shows how interacting and diffusing quantities can destabilize a homogeneous state and form spatial structure. These traditions motivate computation in distributed state, local interaction, competition, propagation, and emergent spatial organization rather than in a sequence of isolated symbolic registers.

CassiFI has related mechanisms on two distinct reference surfaces. The default v2 field uses complex Yang and Yin mode coordinates, damping, adjacent-scale consolidation, and phase-sensitive readout, but its raw mode indices are not spatial and `evolve` contains no spatial derivative or intermode transport. The v3 W3 surface instead assigns profile-bound periodic sheets and advances them through a local/spectral split.

The relation to neural-field and reaction–diffusion work is therefore mathematical and architectural rather than an identification of mechanisms. The present evidence does not show a Turing instability learning a task, an Amari bump implementing the reported program selection, or a physical morphogenetic process acquiring semantics. On the §16 gauntlet, fixed code evaluates bounded candidates and deposits comparative evidence into allocated field rows. Registered codecs and task contracts determine the meaning of those rows.

CassiCosmos evolves a physical GPU state with its own deposition and projection surfaces. Section 14 shows that this substrate and the CassiFI cognitive field are currently distinct. A stronger reaction–diffusion comparison requires a joined experiment in which the physical field produces the measured adaptive behavior; shared terminology does not establish that result.

### 17.3 Cellular automata and learned local dynamics

Cellular automata demonstrate how repeated local rules over a lattice can produce global behavior. In [Growing Neural Cellular Automata](https://doi.org/10.23915/distill.00023), Mordvintsev et al. (2020) use continuous cell states and a shared differentiable local update rule whose parameters are optimized for growth, persistence, and regeneration. The resulting cell-state trajectory carries information that is not assigned an explicit meaning channel by channel.

The v3 W3 periodic-sheet surface provides CassiFI's direct structural contact with local lattice computation: it repeatedly applies one fixed, profile-bound operator to structured state. The §16 gauntlet results, however, are not generated by a neural-CA-style learned local rule; fixed controller procedures deposit or replace evidence in allocated field rows. Mordvintsev et al.'s neural CA learns the shared update rule and then studies the cell states generated by that rule, whereas the measured CassiFI task experiments keep their update machinery fixed. CassiFI's 256-update result is also an exact idempotent-redeposition result. It is not a damage-recovery or self-regeneration experiment, and it provides no evidence for CA universality, morphogenesis, or resilience.

### 17.4 Energy-based systems and associative memory

[Hopfield (1982)](https://doi.org/10.1073/pnas.79.8.2554) gave content-addressable memory a dynamical interpretation: phase-space flow carries a partial cue toward a stored pattern. [Modern Hopfield networks](https://arxiv.org/abs/2008.02217) extend the construction to continuous states, characterize several classes of energy minima, and connect the update to transformer attention. CassiFI's coherence measures, energy-like diagnostics, competition among supported candidates, and query-conditioned retrieval place it near this family.

Several boundaries prevent a direct identification. CassiFI does not train a symmetric weight matrix or a modern Hopfield layer, and the paper does not derive a global energy whose minima are the learned task memories. The exact Mnemic store also remains separate from associative field state: the field may select an opaque address, but the exact bytes are resolved from the authoritative store. The gauntlet's return to an identical tensor after 256 repeated deposits follows from deterministic replacement of the same bounded evidence; it is not an attractor-capacity result.

The current associative claim is consequently operational. A query encounters field state changed by prior observations, and interventions on that state alter selection. Capacity scaling, basin geometry, partial-cue reconstruction, adversarial retrieval, and direct comparison with Hopfield memories remain unmeasured.

### 17.5 Hyperdimensional and vector-symbolic computing

[Plate's holographic reduced representations (1995)](https://doi.org/10.1109/72.377968) use circular convolution to bind items into fixed-width distributed representations and use associative cleanup to recover noisy constituents. [Kanerva's account of hyperdimensional computing (2009)](https://doi.org/10.1007/s12559-009-9009-8) places such methods within a broader family that manipulates high-dimensional random vectors through fixed compositional operations.

CassiFI has clear structural affinities: fixed codebooks distribute symbols over many coordinates; superposition, binding, relative phase, and demodulation make compositional information available to a query; and the typed experiments separate role identity from surface labels. The decisive implementation difference is that the hypervector-like encodings are only boundary machinery. They remain fixed and fingerprinted, while persistent experience changes the multiscale field. Conversely, the field-selected program is executed by a fixed interpreter, so an exact symbolic result is not by itself evidence that the field learned its primitive algebra.

No standard VSA similarity, bundle-capacity, sequence-recovery, or noise-tolerance benchmark has been run. The stress results in §16.6 concern particular CassiFI selectors and observation contracts; they should not be read as a general comparison with hyperdimensional robustness.

### 17.6 World models and active inference

[Ha and Schmidhuber's world-model architecture (2018)](https://arxiv.org/abs/1809.01999) learns a compressed recurrent generative model of an environment and can train a policy inside imagined rollouts. [Active inference](https://doi.org/10.1162/neco_a_00912), as formulated by Friston et al. (2017), couples a probabilistic generative model, belief propagation, action selection, and gradient descent on variational free energy. Both traditions treat internal dynamics as a basis for prediction and action.

CassiFI's grounded and counterflow surfaces address a related question through explicit transaction boundaries. Exact observed transitions supply compatible precondition–effect edges, while a goal conditions a read-only trajectory settlement. On the persistent-provider path, a consequence becomes new adaptive evidence only through an exactly matched observation and acknowledgment carrying a nonempty authorization path. The standalone derived runtime instead freezes or discards candidate updates during planning. The two held-out three-step branches in §16.3 therefore demonstrate composition from registered exact fragments. They do not demonstrate a learned generative environment model, posterior inference, reward optimization, or variational-free-energy minimization. Cassi's energy-like telemetry is not variational free energy.

The same limit applies to embodiment. The current provider can stage a typed world proposal and observe a returned result, but no measured CassiFI–CassiCosmos loop lets the cognitive field learn by acting inside the physical simulation. World-model and active-inference comparisons remain conceptual until a joined run measures prediction, intervention, consequence, and field update in one lineage.

### 17.7 Program synthesis and neuro-symbolic learning

[DreamCoder](https://doi.org/10.1145/3453483.3454080) learns programs while extending a domain-specific library with reusable symbolic abstractions and training neural networks to guide search. It represents a strong version of neuro-symbolic acquisition: both the search guidance and the language available to later problems can improve with experience.

CassiFI's typed-generative experiment is substantially narrower. A deterministic generator supplies 12 canonical programs from a fixed typed grammar, a fixed interpreter evaluates them, and evidence deposited in the field determines support, confirmation, and selection. Held-out boundary behavior and operator-trajectory ablation show that the selected composition depends on the relevant field evidence. The receipt nevertheless records `semantic_acquisition: false` and `task_independent_learner: false`. Primitive invention, library growth, and unconstrained search are outside the demonstrated result.

The comparison locates the contribution precisely: CassiFI measures field-owned selection and consolidation of a bounded relational program, including exact negative controls. It has not yet measured the acquisition of a new operator or the growth of its own candidate language.

### 17.8 Retrieval, agent memory, and tool use

Contemporary agent architectures commonly divide adaptive authority across a pretrained model, external memory, retrieval, context, and workflow state. [Retrieval-augmented generation](https://arxiv.org/abs/2005.11401) combines parametric sequence-model memory with a nonparametric document index. [Generative Agents](https://doi.org/10.1145/3586183.3606763) couples a large language model to a natural-language experience record, retrieval, reflection, and planning. [ReAct](https://arxiv.org/abs/2210.03629) interleaves language-model reasoning traces with environment actions, while [Toolformer](https://arxiv.org/abs/2302.04761) trains a language model to decide when and how to call external APIs.

Cassi's separation of authorities takes a different form. CassiCore can preserve an exact record and resolve exact content; a CassiFI field can accumulate the adaptive effect of observations and select a relevant address or action proposal; fixed policy code validates what may be emitted or committed. Within the §16 gauntlet, the monitored sentinels recorded zero model-provider calls, teacher or Qwen calls, optimizer steps, socket creations, subprocess starts, and forbidden imports. As §15.8 specifies, that result applies only to the instrumented process and interval; it cannot exclude an uninstrumented native extension, state loaded before the audit, or an entrypoint that was not executed. Field intervention therefore supplies a direct attribution test for the monitored run, but it does not confer the broad language and tool competence supplied by pretrained models.

The negative evidence matters to the comparison. CassiFI's current natural-continuation surfaces and even target-aware bounded oracles achieved 0/16 exact continuations, and the live provider-to-CassiCosmos executor is absent. The architecture should therefore be compared on state ownership, transaction semantics, exact replay, and bounded grounded behavior—not on open-domain generation, autonomous tool use, or general agent performance.

### 17.9 Continual learning

Continual-learning methods change learned parameters while attempting to preserve earlier capabilities. For example, [elastic weight consolidation](https://doi.org/10.1073/pnas.1611835114) protects parameters estimated to be important for previous tasks while a network learns subsequent tasks.

CassiFI instead assigned the 13 gauntlet families to disjoint namespaces and deterministically replaced the rows for the family being deposited. All earlier holdouts remained exact, and unrelated rows were required to remain byte-identical. This is a useful state-isolation and retention result, but it does not exercise the central difficulty addressed by continual learning: competing tasks that require overlapping capacity and mutually interfering updates. The current outcome should not be presented as a catastrophic-forgetting solution until shared-support, contradictory, noisy, and capacity-limited sequences are tested against continual-learning baselines.

### 17.10 Comparative synthesis

The cited families can be summarized by the state whose change explains later behavior:

| Research family | State emphasized by the cited work | Closest contact with CassiFI | Current CassiFI distinction |
|---|---|---|---|
| Reservoir computing ([Maass et al., 2002](https://doi.org/10.1162/089976602760407955)) | Transient recurrent state plus learned readout | Fixed rich dynamics and state-dependent readout | Experience is retained in the checkpointed field; no learned readout weights in the measured gauntlet |
| Neural fields and reaction–diffusion ([Amari, 1977](https://doi.org/10.1007/BF00337259); [Turing, 1952](https://doi.org/10.1098/rstb.1952.0012)) | Distributed activation or concentration governed by field equations | Local interaction, competition, transport, and pattern-bearing state | Current cognition results come from registered CPU field surfaces, not the separate physical PDE field |
| Neural cellular automata ([Mordvintsev et al., 2020](https://doi.org/10.23915/distill.00023)) | Cell states generated by a learned shared local rule | Repeated shared operations over structured state | Task adaptation changes field values while the rule remains fixed; regeneration is unmeasured |
| Hopfield and energy-based memory ([Hopfield, 1982](https://doi.org/10.1073/pnas.79.8.2554); [Ramsauer et al., 2020](https://arxiv.org/abs/2008.02217)) | Stored patterns or learned interactions plus retrieval dynamics | Cue-dependent selection and dynamical memory | No trained Hopfield energy, basin-capacity result, or exact-content reconstruction claim |
| HDC and VSA ([Plate, 1995](https://doi.org/10.1109/72.377968); [Kanerva, 2009](https://doi.org/10.1007/s12559-009-9009-8)) | High-dimensional vectors, bindings, bundles, and cleanup memories | Fixed distributed codes, binding, superposition, and demodulation | Codes remain fixed; adaptive evidence resides in the evolving field |
| World models and active inference ([Ha and Schmidhuber, 2018](https://arxiv.org/abs/1809.01999); [Friston et al., 2017](https://doi.org/10.1162/neco_a_00912)) | Learned generative state, beliefs, policies, or objectives | Internal prediction, goal conditioning, and action selection | Exact-edge composition is bounded; no learned generative simulator or variational objective is demonstrated |
| Program synthesis ([Ellis et al., 2021](https://doi.org/10.1145/3453483.3454080)) | Candidate programs, learned search guidance, and sometimes a growing library | Compositional symbolic execution and reusable abstractions | The measured grammar has 12 fixed candidates and does not grow |
| Retrieval and agent systems ([Lewis et al., 2020](https://arxiv.org/abs/2005.11401); [Park et al., 2023](https://doi.org/10.1145/3586183.3606763); [Yao et al., 2022](https://arxiv.org/abs/2210.03629); [Schick et al., 2023](https://arxiv.org/abs/2302.04761)) | Model parameters, document or event memory, context, and workflow state | Recall, planning, external action, and persistent experience | Exact records and adaptive relevance remain separate; open-domain language and tool use are unsupported |
| Continual learning ([Kirkpatrick et al., 2017](https://doi.org/10.1073/pnas.1611835114)) | Shared learned parameters plus anti-forgetting constraints | Sequential acquisition and retention measurement | Present retention relies on disjoint namespaces and deterministic replacement |

Across these comparisons, CassiFI's present contribution is an experimental constraint and its instrumentation: within a selected runtime, one checkpointed field is the sole experience-dependent adaptive object, while codecs, candidate languages, numerical operators, validation, and policy remain fixed and named. The field can then be saved, frozen, replayed, lesioned, or replaced counterfactually while the rest of the computation is held constant.

That constraint is narrower than many neighboring systems and does not establish priority, universality, biological fidelity, or benchmark superiority. Its value is causal resolution. The current results identify which bounded selections, relations, compositions, and retention effects survive field interventions, and they preserve failures as part of the capability map. The next discriminating comparison is therefore experimental rather than terminological: matched tasks should vary whether learned information resides in Cassi's field, in a trained readout, in a parameterized transition rule, or in an external retrieval index while preserving the same observations, candidate budget, and output contract.

### References

- Amari, Shun-ichi. 1977. “[Dynamics of pattern formation in lateral-inhibition type neural fields](https://doi.org/10.1007/BF00337259).” *Biological Cybernetics*.
- Ellis, Kevin, et al. 2021. “[DreamCoder: bootstrapping inductive program synthesis with wake-sleep library learning](https://doi.org/10.1145/3453483.3454080).” *Proceedings of the 42nd ACM SIGPLAN International Conference on Programming Language Design and Implementation*.
- Friston, Karl, et al. 2017. “[Active Inference: A Process Theory](https://doi.org/10.1162/neco_a_00912).” *Neural Computation*.
- Ha, David, and Jürgen Schmidhuber. 2018. “[Recurrent World Models Facilitate Policy Evolution](https://arxiv.org/abs/1809.01999).” *arXiv:1809.01999*.
- Hopfield, John J. 1982. “[Neural networks and physical systems with emergent collective computational abilities](https://doi.org/10.1073/pnas.79.8.2554).” *Proceedings of the National Academy of Sciences*.
- Kanerva, Pentti. 2009. “[Hyperdimensional Computing: An Introduction to Computing in Distributed Representation with High-Dimensional Random Vectors](https://doi.org/10.1007/s12559-009-9009-8).” *Cognitive Computation*.
- Kirkpatrick, James, et al. 2017. “[Overcoming catastrophic forgetting in neural networks](https://doi.org/10.1073/pnas.1611835114).” *Proceedings of the National Academy of Sciences*.
- Lewis, Patrick, et al. 2020. “[Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401).” *arXiv:2005.11401*.
- Maass, Wolfgang, Thomas Natschläger, and Henry Markram. 2002. “[Real-Time Computing Without Stable States: A New Framework for Neural Computation Based on Perturbations](https://doi.org/10.1162/089976602760407955).” *Neural Computation*.
- Mordvintsev, Alexander, Ettore Randazzo, Eyvind Niklasson, and Michael Levin. 2020. “[Growing Neural Cellular Automata](https://doi.org/10.23915/distill.00023).” *Distill*.
- Park, Joon Sung, et al. 2023. “[Generative Agents: Interactive Simulacra of Human Behavior](https://doi.org/10.1145/3586183.3606763).” *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology*.
- Plate, Tony A. 1995. “[Holographic reduced representations](https://doi.org/10.1109/72.377968).” *IEEE Transactions on Neural Networks*.
- Ramsauer, Hubert, et al. 2020. “[Hopfield Networks is All You Need](https://arxiv.org/abs/2008.02217).” *arXiv:2008.02217*.
- Schick, Timo, et al. 2023. “[Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761).” *arXiv:2302.04761*.
- Turing, Alan M. 1952. “[The chemical basis of morphogenesis](https://doi.org/10.1098/rstb.1952.0012).” *Philosophical Transactions of the Royal Society of London. Series B, Biological Sciences*.
- Yao, Shunyu, et al. 2022. “[ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629).” *arXiv:2210.03629*.

## 18. Limitations and Open Problems

The present system has reproducible bounded capabilities and equally specific failure modes. The integrated receipt reports `diagnostic_checks_passed: true`, `readiness_validated: false`, and `status: not_ready`. This section identifies the mechanisms behind that assessment and states the measurements required to extend the supported capability boundary. A proposed capability remains open until a retained artifact distinguishes it from fixed procedural structure, exact lookup, target leakage, or an external model.

### 18.1 Bounded candidate libraries

Most positive results depend on a finite hypothesis space supplied by fixed code. The field accumulates and retains comparative evidence within that space; it does not currently construct the space itself.

| Surface | Fixed candidate structure | Field-owned quantity | Unsupported extension |
|---|---|---|---|
| Relational basis selection | Four coordinate hypotheses and a fixed score equation | Operator moments, evidence sums, support, and selected-basis dependence | Discovery of a new coordinate family |
| Byte-span text | Ten programs with at most three tokens | Program support, fit statistics, eligibility, and selection | A transformation absent from the ten programs |
| Surface-role text | Twelve fixed role programs over six positional slots | Role-program evidence and eligibility | Semantic parsing or a new discourse form |
| Typed abstraction | Twelve canonical programs generated from a fixed typed template | Program support, operator support, coherence, and consolidation count | Primitive invention, arbitrary length, or grammar growth |
| Counterflow | Registered action operators, exact edge compatibility, and a bounded requested horizon | Basin moments, path support, refinement state, and settled selection | Open action discovery or arbitrary graph scaling |

This boundary changes the interpretation of “learning.” Exact held-out execution establishes that deposited field evidence selected and retained the appropriate member of a declared family. It does not establish that the field invented the basis, interpreter, primitive operators, score law, or task family. A larger enumerated library would broaden coverage while leaving this limitation intact.

A decisive extension must withhold the successful composite from the enumerated candidate set while leaving reusable primitives available. The field would have to retain a newly assembled variable-length structure, reuse it on a new task instance, survive checkpoint reload, and lose the capability under a targeted field lesion. Any acquired structure stored in a Python object, cache, generated source file, or learned side model would fail the single-field ownership requirement.

### 18.2 Fixed codecs and experimenter-supplied semantics

Every measured surface has a deterministic observation boundary. Codebooks, atom schemas, role slots, canonical JSON, raster layout, object identifiers, action names, and output validators determine which distinctions enter the field. These are legitimate fixed sensors and protocol structures, but they are also strong inductive biases.

The four-codec gauntlet illustrates the distinction. Canonical JSON UTF-8, opaque bytes, contiguous C-order tensor bytes, and plain UTF-8 all preserve one canonical task view through registered adapters. The resulting 52/52 agreement establishes transport invariance under those adapters. It does not establish that the field discovered a relation between independently structured representations. Similarly, the positive surface-role controls transfer after unfamiliar symbol replacement because the fixed binder assigns roles by position; they do not infer semantic roles from word meaning.

The paired JSON–raster experiment goes further because field evidence depends on 32 explicit source pairs and fails when pairing identity is shuffled, missing, or reduced to hashes. Its remaining inductive bias is equally explicit: both codecs, the pair identity, and the relational task contract are registered in advance. The supported scope is therefore `registered_relational_task_only`.

The open problem is learned alignment without a fixed projection that already exposes the answer. A discriminating experiment should present two information-equivalent views with separately permuted or nonlinear surface organizations, withhold identities and compositions from evaluation, and prevent either adapter from converting one view into the other. Successful transfer must depend on deposited cross-view field coordinates, fail under a targeted alignment lesion or shuffled pairing, and preserve unrelated capabilities.

### 18.3 Natural-language acquisition

The natural-language boundary remains a direct negative result. The dedicated comparison trained on 40 exact source episodes and evaluated 16 held-out continuations across six paths: four field paths—byte-span selection, surface-role selection, next-symbol trajectory generation, and Phi-harmonic continuation—and two target-aware candidate oracles. Every path achieved 0/16 exact continuations.

The failure has two measured forms:

- the byte-span, surface-role, and Phi-harmonic field paths abstained on all 16 cases;
- the autoregressive next-symbol path and both target-aware oracles emitted 16/16 false settlements.

The target-aware oracle failures show that threshold tuning or better ranking inside the existing ten- and twelve-program libraries cannot recover the targets: even a diagnostic that reads the answer cannot choose a candidate that is not present. The next-symbol result exposes a different limitation. Its \(98.40\%\) teacher-forced training accuracy fell to 0/16 exact held-out continuations when its own outputs became subsequent inputs. Neither result supports open-ended language acquisition.

The general-task gauntlet's selected 30-episode training split and four source-held-out base episodes answer a narrower fixed-grammar question and must not be substituted for the 40/16 natural-continuation comparison. Positive uppercase, reversal, suffix, entity-swap, predicate-rebind, and discourse-reversal controls show that the evaluation path succeeds when a target law belongs to the supplied grammar; they do not make natural prose a member of that grammar.

A stronger language experiment requires source-disjoint training, target-blind decoding, variable-length generation, exact and approximate metrics reported together, and explicit counts of abstention and false settlement. It must compare against exact-context lookup and a target-aware expressiveness diagnostic while preserving zero model or teacher calls in the measured runtime. More text alone is insufficient if the adaptive field still cannot represent or construct the needed continuation law.

### 18.4 Incomplete learned cross-view transfer

Two current results answer different cross-view questions:

1. The dedicated paired experiment learned a registered relational correspondence from 32 source pairs and answered 16/16 JSON-to-raster and 16/16 raster-to-JSON held-outs exactly.
2. The general-task gauntlet evaluated four fixed projections of the same canonical task information and records `learned_cross_view: unsupported` with reason `fixed_projection_only`.

The first result is a bounded paired association with causal controls. The second is codec invariance, not learned semantic alignment. Their coexistence is consistent, and neither validates correspondence between previously unrelated modalities. The reproduction record therefore retains `readiness_validated: false`; its missing capability is `learned_cross_view_transfer`.

Closing this item requires a task for which no registered adapter, shared identifier, payload hash, or canonical intermediate view can solve the mapping. Training and evaluation must separate source identities, pair identities, and semantic compositions. The receipt must show that field deposition creates the cross-view capability, read-only inference preserves it, a targeted field lesion removes it, shuffled or missing pairing fails, and a fixed-projection baseline cannot produce the result.

### 18.5 Boundary, clipping, and saturation

Boundary behavior is surface-specific. Three retained outcomes must remain separate:

| Experiment | Boundary result | Interpretation |
|---|---|---|
| Original four-basis relational selector | Four cases had mean residual \(0.061503\), above the \(0.04\) action tolerance; boundary support was false | The selected interior basis did not generalize through clamping |
| Expanded three-candidate relational selector | `distance_bearing` won by margin \(0.001233\), but boundary composition was 0/12 exact with 12/12 false settlements | A low aggregate selection score did not imply valid downstream composition |
| Bounded typed-program experiment | 12/12 boundary outcomes were exact with zero false settlements and maximum residual 0 | A fixed grammar containing explicit bounds and `CLAMP` represented this registered boundary law |

The successful typed result does not erase the two failures. Its candidate program receives lower and upper bounds from the configured world and contains a clamp primitive. It demonstrates selection of an available boundary-aware composition, not general extrapolation from interior dynamics.

Clipping also belongs to the numerical contract. Field operators bound declared amplitudes, gates, and densities; v3 profile admission imposes additional limits. These operations can be correct model semantics, but they can also conceal an unstable proposal if only the final bounded state is inspected. Clamp and saturation counts, pre-clamp proposals, residuals, nonfinite counts, and protected-region hashes are therefore necessary diagnostics.

The next boundary experiment should train only on interior transitions, withhold boundary geometry and boundary-specific candidates, and evaluate previously unseen contact conditions across multiple domain sizes. It should report exact successor state, action sequence, residual, false settlement, abstention, and clamp telemetry. A successful result would need a field-acquired rule that transfers across the withheld boundary family rather than a newly supplied clamp template.

### 18.6 Passive roles, hidden relevance, and false confidence

The strongest relational result uses an intervention: one calibrated action identifies which entity occupies the active role. With that cue and complete intermediate constraints, the registered experiment achieved 32/32 exact role bindings and world revisions. Passive and partially observed cases are materially weaker:

| Condition | Measured outcome |
|---|---|
| Passive scoring across 32 balanced relational cases | 8 correct, 8 wrong, 16 abstentions |
| Interventional binding under the broader stress set | 24/32 correct; all eight south-west cases wrong |
| Passive binding in the typed-program scenario | All four tested quadrants returned `ambiguous` |
| Three dynamically indistinguishable targets with hidden relevance | 6/16 correct, 10 false-confident choices, 0 abstentions |

These outcomes expose two separate problems. Passive role assignment lacks the action cue used by the successful binder. Hidden relevance is absent from the registered observable dynamics, so several candidates can be behaviorally equivalent while only one is labeled relevant by withheld information. In such cases, forced selection converts missing information into false confidence.

The immediate requirement is calibrated ambiguity, not a higher raw choice rate. A suitable experiment should randomize passive roles and hidden relevance independently of identifier order, guarantee that some cases are observationally equivalent, and reveal an additional cue only in a second phase. Before the cue, the correct result for indistinguishable cases is an explicit equivalence set or abstention. After the cue, the field should update the relevant relation, select correctly on held-out identities, and retain the uncertainty boundary when the cue is absent.

### 18.7 Runtime scale and hardware profile

The integrated gauntlet receipt records device `cpu`, dtype `torch.float64`, and one field of shape \([1,6606,1]\). The run covers 13 positive task families with four held-out cases each, 15 sequential curriculum updates, and 256 repeated redepositions. These are useful reproducibility coordinates, not a scaling study; the receipt does not record a thread count or process topology.

The current evidence does not report:

- field-capacity sweeps over \(S\), \(M\), or \(B\);
- batch sizes above one;
- accuracy or interference as candidate count and occupied rows grow;
- sustained online streams with contradictory or nonstationary evidence;
- latency, throughput, peak memory, or energy use;
- thread count, process topology, or multi-process update behavior;
- a complete processor, operating-system, and numerical-library fingerprint in the gauntlet receipt.

The 256-update result is deterministic redeposition of already learned evidence. Returning to the same digest proves an exact fixed point for that operation; it does not establish autonomous dynamical stability, unbounded memory, or continual adaptation. Likewise, minimum retained accuracy 1.0 across 13 disjoint namespaces does not measure competition for shared capacity.

CassiCosmos does not fill this evidence gap. Its physical field uses GPU `float32` buffers, and its canonical-Qi mirror has a separate fixed snapshot contract. Neither is a GPU execution of the measured CassiFI cognition gauntlet. No CPU/GPU parity result currently compares field trajectories, discrete selections, or toleranced observables for the same cognitive workload.

The required scale study should vary field dimensions, batch width, task-family count, candidate count, support overlap, observation noise, and update horizon. It should report exact accuracy, abstention, false settlement, interference, clamp counts, drift, wall time, throughput, and memory. A separate hardware-parity experiment should distinguish byte identity, categorical identity, and toleranced numerical agreement rather than treating them as one condition.

### 18.8 Persistence, concurrency, integration, and replication

Exact checkpoint reload establishes storage fidelity and continuation for the tested CPU paths. It does not by itself establish crash safety during replacement, durability after a host failure, or correctness under multiple writers. Provider locks serialize requests within one process, and different valid serial orders may encode different experience histories. The implementation assumes one owning process for a local state directory unless an external coordinator provides exclusion.

The integration evidence is also component-local:

- CassiCore's exact journal client and CassiFI's provider endpoints are implemented and separately tested, but no retained cross-process receipt joins their complete plan–observe–commit–acknowledge sequence;
- CassiCore's CassiCosmos telemetry path is read-only and lacks a same-run receipt;
- `FieldShadowBridge` is implemented but not instantiated by the inspected `mind-runtime` composition;
- the CassiFI world protocol stages and observes synthetic outcomes but does not execute CassiCosmos;
- no current artifact demonstrates bidirectional learning between the CassiFI cognitive field and the CassiCosmos physical field.

The main §16 receipt and its nested reproduction phase are one artifact lineage, not independent replications. Their deterministic cases are valuable causal tests, but repeated assertions within that lineage do not supply cross-machine, cross-implementation, or independent-laboratory evidence.

A joined integration run must bind the exact CassiCore journal head, CassiFI predecessor and successor checkpoints, authorization record, world request and result, CassiCosmos state identity, and every adapter fingerprint into one receipt chain. Failure injection should interrupt each commit boundary and demonstrate idempotent recovery without duplicate field updates. Independent reproduction should begin from declared source artifacts and a fresh process rather than a preloaded runtime.

### 18.9 Open-ended concept formation

The reproduction artifact explicitly records `semantic_acquisition: false` and `task_independent_learner: false`. Current experiments can deposit support for a registered program, compose registered operators, preserve a selected relation across declared transformations, and consolidate a confirmed bounded abstraction. They do not acquire a primitive whose semantics were absent from the candidate generator, discover an object category, infer an unobserved relevance relation, or grow a reusable language across task families.

An operational concept-formation claim requires more than assigning a new identifier to a familiar fixed program. At minimum:

1. the target relation or operator must be absent from the enumerated candidate set;
2. multiple training contexts must support a reusable common structure rather than an exact episode lookup;
3. the acquired structure must enable held-out behavior in a task family not used to score its construction;
4. the adaptive representation must reside in field coordinates and survive exact checkpoint reload;
5. a targeted lesion must remove the new transfer while preserving matched prior capabilities;
6. shuffled, identity-only, and fixed-projection controls must fail.

These conditions would still establish one bounded acquired concept, not open-ended concept formation. The latter additionally requires repeated growth without a task-specific generator defining each new semantic family in advance, together with capacity, interference, and stopping behavior measured over a sequence of acquisitions.

### 18.10 Consciousness and general intelligence

No experiment in this paper measures consciousness, phenomenal experience, subjective awareness, or a validated correlate of any of them. Persistent state, bilateral variables, counterflow refinement, coherence measures, self-referential identifiers, and report-like outputs are computational mechanisms. None is sufficient evidence for experience. The terms *Yang*, *Yin*, *field*, and *coherence* name model components and observables; they do not carry a consciousness inference.

The paper also provides no evidence of general intelligence. The successful tasks use registered schemas, finite action families, fixed codecs, bounded candidate languages, and purpose-built evaluators. Each of the six evaluated natural-continuation paths—four field paths and two target-aware diagnostic oracles—produced 0/16 exact continuations, arbitrary hidden relevance is unsupported, task-independent semantic acquisition is false, and the cognitive field is not connected to a measured open-world perception–action loop.

Any future consciousness claim requires an explicit operational target, alternatives that the measurement can discriminate, and controls showing why the result cannot be explained by the known fixed machinery. No such protocol is defined here. General-intelligence claims likewise require a declared breadth and adaptation standard across previously unspecified tasks. Until those standards and corresponding evidence exist, neither consciousness nor general intelligence belongs in the CassiFI capability or readiness assessment.

### 18.11 Prioritized measurement program

The open problems can be ordered by how directly they block the current architecture claim:

| Priority | Missing capability | Next discriminating measurement | Minimum evidence required |
|---:|---|---|---|
| 1 | Learned semantic cross-view transfer | Learn a mapping between views for which no fixed projection or shared identity solves the task | Source- and identity-held-out transfer, shuffled-pair failure, fixed-adapter failure, field lesion, exact replay |
| 2 | Field-grown composition | Withhold a successful variable-length composite from the generator while retaining reusable primitives | New field-resident structure, held-out reuse, checkpoint survival, targeted lesion, no sidecar state |
| 3 | Natural-language continuation | Train and decode on source-disjoint variable-length text with no model fallback | Exact and approximate metrics, abstention and false-settlement counts, autoregressive evaluation, lookup and oracle diagnostics |
| 4 | Calibrated partial observability | Separate cases with identifiable roles from deliberately indistinguishable cases | Correct equivalence or abstention before a cue, correct held-out selection after it, no identifier-order shortcut |
| 5 | Boundary-law transfer | Train on interior dynamics and test unseen boundary families without a supplied boundary program | Exact successors, residual and clamp telemetry, zero unsupported settlements, transfer across domain sizes |
| 6 | Capacity and hardware scaling | Sweep field size, batch width, task count, support overlap, horizon, and CPU/GPU execution | Accuracy, interference, drift, clamps, throughput, memory, and clearly separated exact/toleranced parity |
| 7 | Closed cognitive–physical loop | Run CassiCore, CassiFI, and CassiCosmos through one authorized observation–action lineage | Bound source hashes and checkpoints, real physical execution, consequence-driven field update, restart and duplicate recovery |
| 8 | Independent replication | Reconstruct the registered results from fresh processes and declared source artifacts | Matching categorical outcomes and declared numerical tolerances without sharing a live runtime or hidden cache |

The first priority follows the literal readiness record: broader `learned_cross_view_transfer` is the sole item in `readiness.missing` within `CassiFI/artifacts/general-task-gauntlet/receipt.json`. Passing the cross-view experiment would remove one specific readiness blocker.

The nested `CassiFI/artifacts/general-task-gauntlet/reproduction.json` separately records `readiness_validated: false`. Neither result by itself resolves language, open-ended concept formation, scaling, embodiment, consciousness, or general intelligence, all of which require their own evidence.

## 19. Reproducibility

Reproducibility in this paper means reconstructing a named, bounded result from an identified source, input, field, and receipt lineage. Three levels must remain separate:

1. **artifact verification** checks retained bytes, embedded seals, checkpoint identities, and recorded outcomes;
2. **same-source rerun** begins in a fresh process from the declared code and source bytes and reproduces the applicable categorical and numerical results;
3. **independent replication** reconstructs the result without access to a live originating process, hidden cache, or undeclared local asset.

The retained local artifacts are untracked evidence snapshots. They support direct artifact verification and several same-workstation reruns, but they do not yet constitute an independently portable replication package. `CassiFI/artifacts/` and `CassiFI/_diag/` are ignored by Git, the corpus manifest contains workstation-local absolute paths, and the primary receipts omit part of the software and machine identity. Those limitations are part of the result rather than administrative details.

Unless a command says otherwise, the commands below run from the `Cassi/` workspace root. Reproduction outputs are directed to `CassiFI/_diag/reproduction/` where the entry point permits an output override, so verification does not overwrite the retained evidence.

### 19.1 Repository and runtime identity

A new run must bind the docs-only workspace revision separately from the nested CassiFI revision and must preserve any patch that makes either tree dirty. The minimum pre-run capture is:

```powershell
git rev-parse HEAD
git status --short
git -C CassiFI rev-parse HEAD
git -C CassiFI status --short
python --version
python -c "import json, platform, numpy, torch; print(json.dumps({'platform': platform.platform(), 'processor': platform.processor(), 'python': platform.python_version(), 'numpy': numpy.__version__, 'torch': str(torch.__version__), 'hip': getattr(torch.version, 'hip', None), 'torch_threads': torch.get_num_threads(), 'accelerator': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}, sort_keys=True))"
```

The environment record must additionally retain the process architecture, relevant thread and allocator environment variables, and whether any accelerator was visible. The integrated gauntlet itself requires a CPU field and records `device: cpu`, `dtype: torch.float64`, and shape \([1,6606,1]\), but it does not record the repository commit, Python or Torch version, operating system, processor, thread count, process topology, or environment variables unrelated to its forbidden-model sentinel. The corpus-language trainer caps Torch threads at eight or the available CPU count, whichever is smaller, but its receipt does not retain the observed count. No GPU participates in the general-task gauntlet, so the present artifact establishes no CPU/GPU parity.

### 19.2 Corpus identity and deterministic splits

The checked-in corpus manifest is `CassiFI/configs/cassi-qi-corpus-first-wave.json`, schema `cassi.qi-corpus-manifest.v1`, with raw SHA-256 `c8e8651c9d6269444451591bcb8635e94482cd678cf84b6d0ca758d432dcd38e`. The field profile is `CassiFI/configs/cassi-qi-corpus-language.json`, with raw SHA-256 `ddf5ed74f2cceef000865d703be591844f86adc0edfa3d5474640e3de40abe4d`. Both hashes match the values embedded in the retained training receipt.

| Source ID | Source bytes | Training bytes | Holdout bytes | Source SHA-256 |
|---|---:|---:|---:|---|
| `light-novels` | 906,721,189 | 897,653,978 | 9,067,211 | `f78dcc1d940fb15001936b143fa05e748be6777480850509eec02f1dcce1283c` |
| `tinystories-instruct-train` | 2,663,428,109 | 2,636,793,828 | 26,634,281 | `c2c667bc6b608509c0f02f1d5da1414a4b8810b99487fc525086ca664b6e8aa4` |
| `wikitext103-train` | 540,460,577 | 535,055,972 | 5,404,605 | `1063fd685dc32af56a0c61af24a7efec627ed96a5c85ad684b205fb5b5cac189` |
| `textbook-train` | 372,070,442 | 368,349,738 | 3,720,704 | `914d3830a5dc70d9866ba4cba2f5b4170df4df5f259344208f01589cbdd2a645` |

For each source, the final one percent, subject to a minimum of 1,048,576 bytes, is the holdout region. The trainer deterministically samples ten training episodes and four holdout episodes per source, each at most 96 bytes, by scanning from evenly spaced fractional offsets to the next valid UTF-8 line. There is no random seed parameter in this sampler. The source bytes, split policy, episode counts, byte limit, and sampling implementation therefore determine the 40 training and 16 holdout episode descriptors. The retained `cassi.qi-trajectory-corpus-identity.v1` digest over its schema identifier, source sizes and hashes, split sizes, episode counts, and byte limit is `acde2f5197229965644e68b5a5f9c057f530e254a4bf9431fa156eaa3e9447aa`; that digest does not itself bind the sampling implementation.

The general-task gauntlet consumes those retained descriptors but applies a second split. It withholds `wikitext103-train` as the source-disjoint evaluation source, leaving 30 training episodes and four held-out WikiText episodes. Its selected training and holdout payload-set hashes are respectively `cf61fe80592308eec2c737f80692831934ead854ce9905ac5576035b11315865` and `f1fdd774614e98ca4878a0c674ac1747445cf5076d7f5c29d21f1b36f617ffde`; its curriculum hash is `3bec5558e267d47c54aa3527d057d90a742a5bed9e40bcd1219309df2e829567`.

Each manifest source entry records only source ID, absolute path, and digest. The manifest does not include a download locator or redistribution license. The retained training receipt also preserves source-era absolute `CassiQwen` paths for its manifest, profile, and checkpoint even though the matching manifest and profile now live under `CassiFI/configs/`. The verifier reads corpus paths from the receipt and has no path-remapping option. Exact local replay therefore requires the four files at the recorded paths; independent replication additionally requires a distributable source manifest, license metadata, and a hash-preserving path-resolution mechanism.

### 19.3 Retained artifact identities

Raw file digests and embedded receipt seals answer different questions. A raw digest binds every stored byte. The corpus-language `receipt_sha256` fields bind canonical JSON before the seal field is inserted. They are therefore not expected to equal the raw file digest. In that lineage, timing and absolute output paths also mean that a valid fresh receipt can have different bytes from the retained receipt.

| Retained object | Stored bytes | Raw file SHA-256 | Embedded identity |
|---|---:|---|---|
| `CassiFI/artifacts/cassi-qi-corpus-language/field-state.pt` | 887,017 | `58f21773729db4f0cecd5886da4a9cd19e9507cd95586fe63cb4e9babc490b01` | field-memory SHA-256 `d40c76274a0afe7c2d340708988b25d2ef2e3af2641cc765d5a87f76799b2528` |
| `CassiFI/artifacts/cassi-qi-corpus-language/training-receipt.json` | 21,946 | `d4dcbdda623ccbfbdb5e009a0bb3fb2d4e03b523dece30e2946ea06bdabcf9c8` | canonical seal `e9d5fd068ed02baffd9d0642af9bde18401d398704f4fd039d5199ae887b09b0` |
| `CassiFI/artifacts/cassi-qi-corpus-language/verification-receipt.json` | 1,859 | `f57ba0a52758caf1176c0b55d87419ff24ea23d7e602297229ea1528b352bc00` | canonical seal `a273be7ceddcc89d0b39db1b19d5e80c209ca5682be264cab14dd1c54e7c6d98` |
| `CassiFI/artifacts/general-task-gauntlet/receipt.json` | 51,118 | `42eee4352d8076a15f7716919880d1fee679bcab58945860a27f4ad746a44de5` | checkpoint SHA-256 `0e55ad09949dd4ce287f0169c4941b6d871b3970822d8e9ba0f62ad86e9e0a7b`; state SHA-256 `c0d1a222c89ec3a400ddae312f47657165f2d479185f3755d1b9d4619fc560f5` |

The phase receipts provide smaller claim-specific views:

| Phase artifact | Execution scope | Raw SHA-256 |
|---|---|---|
| `curriculum.json` | `full_prerequisite_chain` | `c49cb395ae3389800aaa338ab67ce571ee3fe02b873e918a19b0e2f219f3f67b` |
| `holdouts.json` | `full_prerequisite_chain` | `1d87aadfb4a81cfbbd90fc4103a9d99e3c41eccd4b37fd1c976af6210aa11e5e` |
| `retention.json` | `full_prerequisite_chain` | `42b276eb461f00c49bf88dd509081c695c698f159d23ef07f11e3a4d7bcf6aef` |
| `persistence.json` | `full_prerequisite_chain` | `8718cdb05f400694f9f6cba04297ce043cbff9aafbabde3bafdf7abe69174882` |
| `controls.json` | `full_prerequisite_chain` | `56e684f11458694fa81a53dac20b40df316831b1f0c1093d3846c9c4b63c2c58` |
| `reproduction.json` | `reproduction_only` | `5425cb2cf96465e6f59a5154f78bbec6f60f61d7c65e5025ceacb164470a8634` |

The five `full_prerequisite_chain` phase commands each rerun the complete prerequisite chain and then retain a selected subset of fields. They are not six independent replications of the primary artifact. The `reproduction_only` phase invokes the text-abstraction, generative-abstraction, and universal-data scenarios without rerunning the mixed curriculum.

The receipts name schemas `cassi.qi-trajectory-training-receipt.v1`, `cassi.qi-trajectory-language-verification.v1`, and `cassi.general-task-gauntlet-result.v2`, but they do not bind those schemas to separately retained schema-file hashes. Likewise, the gauntlet retains its in-memory checkpoint hash but not the serialized checkpoint bytes. A publication package must add both items; a schema name or result hash is not a substitute for the missing payload.

One further provenance distinction is necessary. The retained language-training receipt records `cassi_field_language.py` SHA-256 `4fb4687defb0b97d32e48baf012eb0547822ef1291264dedc9640d1f1bc8cb69` and trainer SHA-256 `63891366a4031fe014d9916e001f8e3c0262401c9e76c052a4b0efceabd11c70`. The currently checked-in files hash to `b1efd7eab51e6429e0fd036c617973d7305140c6dfc05eeb1ce50d86c1aaae71` and `56698c41ce917bfbd81044b2782e7b512e1c45de331c6fe601f9d59462bc8c63`, respectively. The current verifier validates the training receipt's canonical seal, source bytes, profile, checkpoint, reconstructed memory, metrics, and recorded generations, but it does not reject this software-hash mismatch. A `PASS` replay therefore validates the retained data and field lineage under the current verifier; it does not prove that the current source tree is byte-identical to the source that produced the checkpoint.

### 19.4 Corpus-language reconstruction and replay

To train a fresh checkpoint without overwriting the retained one:

```powershell
python CassiFI/training/train_cassi_field_language.py --manifest CassiFI/configs/cassi-qi-corpus-first-wave.json --config CassiFI/configs/cassi-qi-corpus-language.json --output-dir CassiFI/_diag/reproduction/cassi-qi-corpus-language
python CassiFI/verification/verify_cassi_corpus_language.py --config CassiFI/configs/cassi-qi-corpus-language.json --artifact-dir CassiFI/_diag/reproduction/cassi-qi-corpus-language --output CassiFI/_diag/reproduction/cassi-qi-corpus-language/verification-receipt.json
```

The first command is source reconstruction; the second independently rebuilds field memory from the recorded training episodes and compares it with the checkpoint. Under the retained baseline, the verification invariants are:

- schema `cassi.qi-trajectory-language-verification.v1` and `status: PASS`;
- one finite adaptive tensor of shape \([4,55296,1]\);
- 40 reconstructed episodes and 3,360 events;
- byte-exact reconstructed field memory;
- training accuracy \(3267/3320 = 0.9840361445783132\);
- held-out next-event accuracy \(360/1195 = 0.301255230125523\);
- four recorded training-prompt generations reproduced exactly.

The one-command replay of the retained checkpoint is:

```powershell
python CassiFI/verification/verify_cassi_corpus_language.py --output CassiFI/_diag/reproduction/retained-language-verification.json
```

This replay requires the local source paths embedded in the retained receipt. Because the training and verification receipts include timing and absolute paths, reproduction is judged on the bound source, profile, checkpoint, memory, episode, metric, and generation invariants rather than equality of the newly written receipt bytes. Exact reproduction of the historical training run additionally requires the historical source hashes recorded above; the current source tree does not meet that condition.

### 19.5 General-task gauntlet

The complete CPU gauntlet is:

```powershell
python CassiFI/run_general_task_gauntlet.py --phase full --output CassiFI/_diag/reproduction/general-task-gauntlet.json
```

The expected successful diagnostic result has schema `cassi.general-task-gauntlet-result.v2`, `diagnostic_checks_passed: true`, `readiness_validated: false`, `readiness.status: not_ready`, and `readiness.missing: ["learned_cross_view_transfer"]`. It contains 13 supported families at 4/4 exact each; three untrained bounded compositions at 4/4 each; four codec views at 13/13 each; minimum retained accuracy 1.0; an exact checkpoint reload; an unchanged field across inference; exact ingress replay after restart; 15 sequential updates; and a finite fixed point across 256 repeated redepositions. The field-only audit records one CPU field and zero forbidden import, subprocess, socket, optimizer, teacher, and Qwen calls or attempts within its declared sentinel scope.

Exit status has two meanings. Without `--require-ready`, the retained result exits 0 because its diagnostics pass even though broader readiness does not. Adding `--require-ready` must produce exit 2 while `learned_cross_view_transfer` remains missing:

```powershell
python CassiFI/run_general_task_gauntlet.py --phase full --require-ready --output CassiFI/_diag/reproduction/general-task-gauntlet-required-ready.json
```

A failed diagnostic returns exit 1 before the readiness check. Every invocation writes its receipt before selecting the exit code.

Any claim-specific phase can be invoked with the same entry point:

```powershell
python CassiFI/run_general_task_gauntlet.py --phase curriculum --output CassiFI/_diag/reproduction/curriculum.json
python CassiFI/run_general_task_gauntlet.py --phase holdouts --output CassiFI/_diag/reproduction/holdouts.json
python CassiFI/run_general_task_gauntlet.py --phase retention --output CassiFI/_diag/reproduction/retention.json
python CassiFI/run_general_task_gauntlet.py --phase persistence --output CassiFI/_diag/reproduction/persistence.json
python CassiFI/run_general_task_gauntlet.py --phase controls --output CassiFI/_diag/reproduction/controls.json
python CassiFI/run_general_task_gauntlet.py --phase reproduction --output CassiFI/_diag/reproduction/reproduction.json
```

The phase label changes the retained view, not the prerequisite cost, except for `reproduction`, whose `execution_scope` is `reproduction_only`.

### 19.6 One-command claim checks

The following entry points are the shortest executable path to each result class discussed in this paper:

| Result class | Command | Required observation |
|---|---|---|
| Retained trained-language replay | `python CassiFI/verification/verify_cassi_corpus_language.py --output CassiFI/_diag/reproduction/retained-language-verification.json` | exit 0; `status: PASS`; exact memory reconstruction and the recorded metrics |
| Natural-continuation and bounded-grammar comparison | `python CassiFI/run_text_abstraction_comparison.py` | exit 0; `result: TEXT_ABSTRACTION_COMPARISON_OK`; all six evaluated natural-continuation paths remain 0/16 exact |
| Grounded exact-edge composition | `python CassiFI/run_grounded_counterflow_deliberation.py` | exit 0; `result: NOVEL_COUNTERFLOW_COMPOSITION_OK`; both held-out three-action paths settle and missing-middle-edge controls do not |
| Deterministic world/action composition | `python CassiFI/run_bilateral_counterflow_scenario.py` | exit 0; emitted `grounded_relational_transfer.result: GROUNDED_RELATIONAL_COMPOSITION_OK`; exact held-out revision and non-settling ablation |
| Field-selected relational basis | `python CassiFI/run_learned_relational_basis.py` | exit 0; `FIELD_SELECTED_RELATIONAL_BASIS_OK`; restart, lesion, and held-out relational checks pass |
| Relational boundary and partial-observability stress | `python CassiFI/run_relational_stress_tests.py` | exit 0; `RELATIONAL_STRESS_TESTS_OK`; the positive and negative counts remain explicit in the JSON |
| Bounded typed generation and universal-data pairing | `python CassiFI/run_generative_abstraction.py` | exit 0; top-level `UNIVERSAL_FIELD_INTELLIGENCE_OK` with nested `GENERATIVE_ABSTRACTION_OK` and `UNIVERSAL_DATA_FIELD_OK` |
| Memory and restart behavior | `python CassiFI/run_general_task_gauntlet.py --phase persistence --output CassiFI/_diag/reproduction/persistence.json` | exact checkpoint reload, unchanged inference state, exact journal replay, and the recorded 256-update fixed point |
| Causal ablations and negative controls | `python CassiFI/run_general_task_gauntlet.py --phase controls --output CassiFI/_diag/reproduction/controls.json` | lesion and shuffled outcomes `exhausted`, induced ambiguity `ambiguous`, malformed input `unsupported`, and unrelated-family accuracy 1.0 |

Only the general-task gauntlet among these standalone scenario runners accepts `--output` and persists its own receipt. `run_text_abstraction_comparison.py`, `run_generative_abstraction.py`, and `run_grounded_counterflow_deliberation.py` print their results to standard output; they do not create standalone receipt files. The other non-gauntlet scenario runners in the table likewise emit live output. A reproduction must capture stdout, stderr, and exit status explicitly. The table states the required live observation and does not imply that every row has a committed or retained receipt snapshot. The gauntlet's retained `reproduction` object separately embeds selected text-abstraction, generative-abstraction, and universal-data results; it does not embed the grounded-counterflow run.

The deterministic world/action command is not evidence for a learned generative world model. It evaluates exact transitions and bounded composition in an analytic world. No command in this paper is designated as a reproduction of learned world-model capability because §17.6 establishes no such capability. Treating a synthetic transition runner as that missing result would change the claim rather than reproduce it.

### 19.7 Focused executable contracts

From `CassiFI/`, the focused behavioral suite for the integrated gauntlet and the principal relational and generative scenarios is:

```powershell
python -m pytest tests/test_general_task_gauntlet.py tests/test_cassi_bilateral_counterflow.py tests/test_cassi_relational_basis.py tests/test_cassi_generative_abstraction.py
```

These tests exercise schema validation, CLI exit semantics, field-only sentinels, source-disjoint splitting, persistence, controls, relational settlement, and typed-program behavior. They are regression contracts, not additional evaluated cases: a passing unit test does not increase the sample counts reported in §16 and does not replace the scenario receipt.

### 19.8 Acceptance procedure and publication package

A reproduction attempt should proceed in this order:

1. record both repository revisions, dirty-tree patches, and the runtime environment;
2. verify every source, profile, manifest, checkpoint, and retained receipt against its raw digest before execution;
3. start a fresh process with no preloaded Cassi provider, model runtime, or hidden state;
4. run the exact claim-specific command and retain stdout, stderr, exit status, and generated files;
5. check categorical outcomes before numerical comparisons;
6. compare discrete identities, counts, programs, world revisions, and checkpoint bytes exactly;
7. apply a tolerance only where the corresponding experiment declared one in advance, and report the observed value with that tolerance;
8. retain failed and abstaining outcomes rather than filtering them from the reproduced result.

The publication capsule required for independent replication comprises both repository commits and any dirty patches; the exact schema payloads and their hashes; the field profile and corpus manifest; a legally redistributable source bundle or stable acquisition instructions with licenses and digests; a dependency and interpreter lock; all checkpoints and receipts; the command transcript and exit codes; the complete CPU, GPU, thread, and allocator record; and a path map that removes dependence on source-era absolute directories. The general-task checkpoint bytes must also be retained rather than only their hash.

Until that capsule exists and a fresh environment reconstructs the results, the present evidence supports local artifact audit and bounded same-system reproduction, not independent cross-machine replication. The missing package does not alter the recorded outcomes, but it keeps independent replication open as Priority 8 in §18.11.

## 20. Conclusion

This paper asked whether useful adaptive behavior can be made causally dependent on one persistent dynamical field. Within the measured CassiFI surfaces, the answer is bounded but affirmative. Experience changes coordinates of the active Qi field; those changes survive the tested checkpoint paths; and later selection, composition, and abstention depend on the resulting field state. Matched untrained fields, targeted lesions, shuffled associations, missing-edge interventions, and read-only-inference checks locate that dependence in the field rather than in a learned side model or persistent candidate cache.

The field-owned operations are specific. The field retains evidence over registered candidates and grounded transition fragments, supports query-dependent readout, selects relational bases and bounded typed programs, composes compatible edges into held-out trajectories, and preserves learned families across sequential deposition. The integrated gauntlet was exact on 52/52 held-out cases across 13 registered task families after field training, while the matched untrained field produced 0/52 exact outputs. Separate experiments composed both held-out three-action paths, reached exact world revisions in 32/32 relational-basis cases, executed 12/12 bounded boundary-program cases, and transferred 16/16 cases in each direction for the registered paired JSON–raster task. Exact restart and field-state checks show that these capabilities persisted through their tested CPU execution paths.

The ownership boundary is equally specific. Fixed code defines sensors, codecs, field geometry, transition operators, candidate generators, interpreters, eligibility thresholds, world dynamics, and action policy. Exact journals, source records, and world revisions remain independently identified evidence. The adaptive field accumulates support and reusable operator information within those declared structures; the present system has not demonstrated invention of the structures, primitive semantics, or task families themselves.

The negative results mark the current capability frontier. All six natural-continuation paths produced 0/16 exact held-out continuations. Passive role assignment, hidden relevance, unseen boundary laws, arbitrary semantic alignment, open-ended concept formation, and unrestricted program synthesis remain unsupported. The experiments do not establish a learned generative world model, general intelligence, consciousness, unbounded memory, cross-device numerical parity, or a measured bidirectional CassiFI–CassiCosmos learning loop. The integrated receipt therefore correctly remains `not_ready` even though its bounded diagnostics pass.

The next decisive experiment is learned semantic cross-view transfer without a fixed projection or shared answer-bearing identity. Two information-equivalent views should receive separately permuted or nonlinear organizations, with source identities, pair identities, and semantic compositions separated between training and evaluation. Success requires a trained field to transfer across the held-out correspondence while shuffled or missing pairs, a fixed-projection baseline, and a targeted alignment lesion fail; unrelated capabilities must remain intact, inference must preserve field state, and exact checkpoint replay must recover the result. This directly tests `learned_cross_view_transfer`, the sole capability listed in the current gauntlet receipt's `readiness.missing` field.

Cassi's present contribution is an implemented and inspectable method for testing field-owned computation: one adaptive tensor, explicit fixed machinery, exact state lineage, and interventions that determine whether a measured capability disappears when its field support is removed. The results establish persistent field-owned adaptation, grounded compatible-edge composition, bounded relational and typed-program selection, exact registered transfer, and calibrated non-settlement within declared task families. Extending that boundary requires the same standard applied here—held-out behavior, preserved provenance, targeted causal controls, restart persistence, and claims restricted to what the resulting artifacts measure.
