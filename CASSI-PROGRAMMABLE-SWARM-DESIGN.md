# Cassi: A Programmable Field Swarm

## Status: Specified architecture with implemented execution paths—2026-09-23

Cassi acquires executable instruments of thought. A Python interpreter is one
such instrument: its implementation, running programs, objects, and suspended
computations belong to the regional field computer. The resident pretrained
brain is another executable program, imported with its identified model graph
and weights. A native Vulkan service executes compatible work across members,
model continuations, and working branches. Acquired methods, Python execution,
and neural inference share one regional programming and ownership architecture.

This document specifies the complete Python, resident-model, and GPU
realization, including acquired representations, runnable explanations, inverse
design, causal studies of computation, constructed specialist instruments,
experience-driven simplification, and the shared research workspace. The
regional computer, persistent owner, research organism, Hive, and field–brain
entity provide its basis. The repository also contains the Python compiler and
resumable executor (`CassiFI/programs/python/`), resident model execution
(`CassiFI/programs/model/`), optimizer (`CassiFI/programs/optimizer/`), and native
runtime transport (`CassiFI/cassi_field_runtime_native.py`), integrated through
`CassiFI/cassi_programmable_swarm.py`. These paths have narrower coverage than
the complete destination: guest resource growth, full language and library
compatibility, autonomous construction of new capability proposals, and native
publication without logical owner replay remain implementation work. The
Python source-analysis module remains a separate instrument. The embodied
design's [generality review](CASSI-EMBODIED-SELF-DESIGN.md#implementation-coverage-established-by-the-generality-review)
records the concrete boundaries found in these execution paths. No mission
launch or permission expansion follows from this design.

## 1. Destination and design authority

The destination is an intelligence that develops the computational instruments
through which it understands: representations, explanations, experiments,
reasoning procedures, and methods for constructing further methods. It can
inspect a calculation, resume it, change an assumption in a private branch,
combine partial discoveries, and retain useful structure as executable
knowledge. Python provides a rich scientific language; the underlying machine
remains language-independent.

A complete research action follows this path:

> Admit an observation → identify the unresolved distinction → construct a
> representation or instrument → execute, inspect, or branch its continuation
> → check the result → retain and teach the useful method → use it in the next
> investigation.

Three boundaries define the design:

- **Language capability:** general Python 3.12 computation, within the resources
  of a finite deployment. A quantum limits uninterrupted work, not the number
  of times a terminating computation may resume.
- **Application compatibility:** libraries, native extensions, and environmental
  services have explicit implementations and capability requirements.
- **Acceleration:** many independent computations and parallel operations supply
  GPU work. A sequential dependency chain remains sequential.

[CASSI-ENTITY-DESIGN.md](CASSI-ENTITY-DESIGN.md) governs identity, mission,
continuing learning, the active brain, authority, and the organism's lifetime.
[Regional Section 32](CassiFI/FIELD-INTELLIGENCE-DESIGN.md#32-one-universal-regional-field-computer)
governs the one field image, instruction semantics, automaton, and publisher.
[Platform Section 36](CassiFI/FIELD-INTELLIGENCE-DESIGN.md#36-extensible-platform-and-sustained-apprenticeship)
governs owner-backed extensions. This companion specifies their language,
resident-model, instrument-development, and physical-execution realization.
It creates no competing owner or planner.

## 2. Implemented basis and required extension

| Surface inspected | Implemented basis | Extension specified here |
|---|---|---|
| `CassiFI/cassi_field_regions.py` | Typed regional image, references, instruction/event execution, scopes, bounded native catalog, validation, state digest | Device lowering, typed Python records, exact residency conversion, bounded native implementation |
| `CassiFI/cassi_field_program.py` | Fixed structured and regional source compilers; immutable lowering data | Interpreter-program packaging, source maps, language frontend programs, guarded compilation |
| `CassiFI/cassi_learning_computer.py` | One authoritative regional machine and resumable owner-facing work | Fenced native execution of the same machine and continuation |
| `CassiFI/cassi_python_universal.py` | AST bindings, calls, effects, runtime-boundary analysis, persisted analysis | Reuse analysis as evidence; add an actual interpreter as a field program |
| `CassiFI/cassi_field_owner.py`, `CassiFI/cassi_hive_session.py` | Owner lifecycle, persistent sessions, evidence and authority boundaries | Residency attachment, candidate publication, scoped inspection and migration |
| `CassiFI/cassi_research_organism.py`, `CassiFI/cassi_hive_collective.py` | Continuing research and collective-learning machinery | Execution-aware collaboration, interpreter development, reusable compiled methods |
| `CassiQwen/cassi_field_brain_entity.py`, `CassiQwen/cassi_autonomous_researcher.py` | Existing field–brain root and research director | Resource-coordinated member work and computational inspection |
| `CassiCosmos/scripts/cassi_mind_engine.gd`, llama.cpp Vulkan | Separate numerical/model GPU runtimes; native Qwen embedding/attention/FFN/head service | Keep Godot an explicit world boundary; lower model operations and state into a resident field program with an explicit Vulkan ownership seam |

The Torch resonant solver and Godot PDE engine are numerical components. Their
GPU execution does not make the regional program computer GPU-resident. The
existing regional `NATIVE` boundary calls fixed Python implementations; those
implementations require genuine bounded native/device equivalents, not a shader
wrapper around a host callback.

## 3. One organism, many members, scoped working branches

```text
Existing field–brain entity / research director
  ├─ Continuing root: one existing owner and regional image
  ├─ Enduring members: separate owners, homes, lineages, regional images
  │    ├─ Acquired Python, symbolic, and numerical programs
  │    ├─ Resident Qwen program and owner-specific model continuations
  │    └─ Working branches: scopes and overlays inside each member's image
  ├─ Initial external-brain adapter: explicitly attributed inference requests
  └─ Native field-runtime service
       ├─ Resident pages, immutable code, and shared read-only model tensors
       ├─ CPU regional backend
       └─ Vulkan regional/tensor backend: compatible operation groups
```

The root remains `FieldBrainEntity.memory` / `CassiFieldWorkMemory`; its existing
director is the background coordinator. Existing `open_field_session` and
`attach_field_session` paths attach members. A resident slot is a placement of
an owner, not a newly created mind. Reattaching never seeds a replacement field.

An enduring member acquires its own experience. A branch is a hypothetical
scope with private changes and a continuation in that same member's machine.
It has neither an independent publisher nor a separately learned personality.
Shared immutable backing can reduce physical memory without merging knowledge.

The scaling ambition is hundreds of enduring members and thousands of cheap
working branches, with only useful ready work active. These are design targets,
not measured capacity. Admission depends on actual state, scratch, brain,
transfer, and checkpoint costs; a member need not be GPU-resident to exist.

## 4. State, identity, and executable records

All authoritative adaptive state and unfinished execution remain in the owning
`ComputerState.field`. Existing `Value`, `Binding`, `Event`, `Program`,
`Assessment`, and `Obligation` families carry the new views. Typed payloads use
the regional directory, generation-checked references, and versioned schemas.
There is no Python heap database, host learned scheduler, or separate task mind.

| Record/view | Required content |
|---|---|
| `PythonSemantics` | Python version, grammar, implementation choices, stdlib manifest, arithmetic and hash policy, compatible primitive contracts |
| `InterpreterProgram` | Executable regional program, immutable source/IR digests, semantics reference, dependencies, entry, source-span map, assessment and adoption state |
| `PythonProgram` | Exact guest source identity, module/package context, compilation mode, future flags, dependency and capability requirements |
| `PyObject` | Stable object identity/generation, type, layout, mutable version, payload references, owning scope, collection metadata |
| `PyFrame` | Interpreter/code references, program counter, locals/globals/builtins, value and block stacks, closure cells, exception/unwind state, caller and source span |
| `PyTask` | Main/generator/coroutine/import/finalizer role, frame, suspension state, await target, pending send/throw, schedule binding |
| `PyOperation` | Long-operation phase, cursor, immutable input versions, private partial output, callback/effect progress, charged work |
| `ModelProgram` | Model graph/control program, GGUF/tensor/tokenizer identities, architecture and quantization profile, operation versions, entry and assessment |
| `TensorView` | Owner/scoped reference, shape, dtype, strides, quantization layout, immutable backing or mutable version, rights and dependencies |
| `ModelContinuation` | Token/position and block/operation cursor, live activation references, attention/recurrent memory roots, sampler/RNG state, pending deltas and checkpoint |
| `ComputationView` | Versioned projection of frames, objects, assumptions, dependencies, effects, costs, result or unfinished reason |
| `RepresentationProgram` | Concept/role schema, grammar where needed, executable operators and observation mappings, preserved/lost distinctions, applicability and version |
| `WorldProgram` | Executable explanation, state/transition/readout references, assumptions, uncertainty, numerical regime, forecast history and observed-outcome links |
| `DesignProblem` | Desired readout, horizon, admissible variables/interventions, constraints, objective definitions, world/method versions and search continuation |
| `ReasoningStudy` | Original episode and checkpoint, contrasted computation, matched input/runtime conditions, readouts, retained differences, scope and actual cost |
| `InstrumentProgram` | Typed callable ports, representation/tensor meanings, effects, guards, state/continuation interface, dependencies and composition assessment |
| `ConstructorProgram` | Typed specification inputs and program-valued outputs, construction dependencies, unresolved holes, product lineage and admission disposition |
| `WorkspaceBinding` | Principal, question/object references, representation/view versions, field revision, annotation status, selected branches and admitted guidance identity |

Exact source/artifact bytes live in existing evidence stores, linked by digest
and source span. Semantically active code, heap, continuations, selection, and
learned applicability live in the field. An artifact cache cannot become the
only surviving copy of an acquired program's executable meaning.

Every execution binds at least:

```text
owner_id, member_id, lineage_id, program_id, operation_id
predecessor_state_digest, source_refs, executable_program_ref
regional_profile_digest, instruction_catalog_digest, language_or_model_semantics_digest
dependency_manifest, effective_capability_view, ordered_input_refs
reservation_id, lease_fence, logical_transition_limit, work_and_memory_limits
```

Names are not identity: two same-named modules with different source/package
contexts remain different inputs. Dynamically generated code has a child source
identity. Changing admitted code creates a new version; running frames retain
the old version until a declared migration or normal return.

These are typed views over the existing six semantic families. Construction
frontiers, executable meanings, world states, study continuations and adaptive
method selection live in the field. Exact source captures and immutable trace
artifacts may use the existing evidence store; a client cache or trace index
never becomes their adaptive owner.

Programs and representations are inspectable, transformable values. A program
reference binds code/version, closed-over values, typed ports and effects;
returning one cannot export a private reference or enlarge its recipient's
rights. Construction produces a candidate through ordinary field computation.
Fixed admission checks structure, dependencies, permissions and bounds before
execution; successful admission alone does not establish behavioral usefulness.

## 5. Acquiring the interpreter and becoming self-hosting

The fixed regional interpreter executes the field instruction set. The Python
interpreter is an **ordinary acquired program on that machine**. Its parser,
semantic dispatch, object operations, call rules, import logic, exceptions, and
resumption rules are executable field programs. Multiple invocations share an
immutable implementation while keeping their own state.

The fixed substrate supplies canonical codecs, reference checks, word
operations, bounded arithmetic/Unicode/hash/memory panels, and the existing
control/event instructions. It does not hide the language behind a whole
`python.interpreter-step`, host `exec`, or arbitrary `solve` callback. A helper
contract declares inputs, effects, maximum indivisible work, and continuation.
Unbounded traversal and Python callbacks return through field program frames.

Acquisition and improvement use the existing development machinery:

1. Study the language specification, reference behavior, and an implementation
   source; retain exact origins and the particular behavior being implemented.
2. Construct interpreter routines as regional programs. Qwen can actively reason
   about the construction; its proposal is not the executed answer.
3. Validate structure, references, effects, primitives, and resource bounds.
   Invalid code remains non-executable. Valid candidate code may run in a
   restricted development scope for software checks, before general adoption.
4. Exercise real language behavior against the specification and, where
   applicable, CPython 3.12. Keep implementation-specific differences explicit.
   Passing examples is compatibility evidence, not universal equivalence proof.
5. Adopt an identified implementation through existing owner-held program and
   assessment machinery. Preserve the incumbent and pinned live continuations.
6. Use actual failures, workloads, and costs to acquire repairs and faster
   methods. Interpreter updates never silently redefine the semantics profile.

The initial loader/compiler is a deterministic bounded bootstrap codec, as in
regional §32.7. It can load regional source without needing an existing Python
interpreter. Large parsing/compilation resumes through an explicit continuation
or refuses the admitted bound; no uncharged host optimizer performs the task.

The complete destination includes a parser and compiler acquired as programs:
Cassi develops these instruments using its own runtime. The bootstrap remains
sufficient to load, inspect, and recover them. Changing the trusted ISA,
validator, native catalog, or authority mechanism is a runtime upgrade, not
something an interpreter program can grant itself.

## 6. Python language and library semantics

The language target is Python 3.12, with a versioned implementation ABI and
module manifest. Every feature is labelled language-required,
CPython-compatible, or implementation-specific. Full language support is the
end target; intermediate coverage is reported by feature, never renamed
“arbitrary Python.” Native-extension binary compatibility is a separate axis.

| Area | Required semantics |
|---|---|
| Source and binding | Full grammar, evaluation order, lexical and dynamic namespaces, comprehensions, closures, assignment expressions, pattern matching, annotations and future flags |
| Values | `None`, booleans, arbitrary integers, binary64 floats, complex values, Unicode strings, bytes/bytearray, memory views, containers, ranges and callable/runtime objects |
| Identity and mutation | References preserve aliases and cycles; assignment does not copy an object; `is`, in-place operations, object lifetime and buffer exports remain meaningful |
| Calls and classes | Positional/keyword rules, defaults, unpacking, mutable closure cells, descriptors, dynamic attribute hooks, C3 MRO, metaclasses, class creation and operator fallback |
| Containers | Dict insertion order, equality/hash contracts, versioned mutations, iterator invalidation rules, stable sorting and normal user callbacks |
| Exceptions | Matching and groups, chaining, tracebacks, pending return/break/continue, `finally`, context-manager entry/exit and exception suppression |
| Suspension | Generators and `send`/`throw`/`close`, coroutines, async generators, asynchronous context/iteration, explicit await dependencies |
| Dynamic execution | `compile`, `eval`, `exec`, code objects, explicit namespaces, imports and runtime introspection through the same field interpreter |
| Modules | Package resolution, cyclic/partial initialization, per-execution module state, import failure and reload semantics; no accidental host module substitution |

Integer arithmetic uses signed arbitrary-length limbs; machine word overflow
never implements Python integer arithmetic. Division/remainder with negative
operands, shifts, conversion and large powers follow the pinned language.
Floats are binary64 bit patterns, stored as two u32 payload words when needed.
The profile specifies NaNs, signed zero, subnormals, rounding, contraction and
library transcendental behavior; device fast-math cannot alter a Python branch.

Strings index Unicode code points, including representable surrogate values,
not encoded bytes or grapheme clusters. Identifier normalization follows the
language; string contents are not silently normalized. `id()` is a stable
logical identity over an object's lifetime, not a host or device address.

An immutable module manifest classifies each import as field-executed Python,
field runtime/library code using bounded primitives, explicit host adapter,
native extension with a declared ABI, or unavailable. OS-dependent modules use
capability handles. NumPy/PyTorch and other extension packages need compatible
implementations or explicit adapters; their installed CPU binaries do not
become shader code. Missing support produces a specific import/ABI error.

## 7. Resumable execution, memory, and completion

The Python heap is a graph in regional storage. Frames, closure cells, generator
state, import transactions, awaited results, and pending unwind operations are
explicit records. GPU recursion uses those frames; it requires no shader call
stack recursion. A checkpoint serializes graph identities once, preserving all
aliases and cycles; it does not pickle arbitrary host objects.

Long arithmetic, sorting, hashing, comparison, parsing, regex/library work,
collection and compilation have bounded phases. Partial progress is private
except at the language's defined callback/effect boundaries. A yielding sort
resumes the same comparator invocation; a resumed import does not repeat its
already completed side effects. Runtime safe points can lie inside a Python
operation without exposing an invalid partial Python value.

Use an incremental tracing/cycle collector with field-owned progress, roots,
write barriers, weak references, finalizer queue, and resurrection state.
Roots include frames, closures, exceptions, module/task tables, overlays,
prepared effects and all live handles. Collection work is charged. Logical
unreachability and physical device-page reclamation are distinct.

Finalization timing is a declared implementation choice; CPython's immediate
reference-count timing is not assumed. Finalizers execute through normal
frames and capabilities at defined safe points, with explicit ordering and
resurrection rules. Serialization can preserve a suspended finalizer frame;
it does not invoke finalizers or user code while traversing the checkpoint.

A runtime resource pause is distinct from a Python exception. A finite quantum
yields; a missing reservation blocks; a genuine language-visible allocation or
recursion failure raises the declared Python exception. `except` cannot swallow
host cancellation and continue indefinitely. Cancellation stops new ordinary
work; policy may permit bounded cleanup, still subject to current permissions.

An invocation completes when its declared structured task group and required
cleanup have settled, its result or uncaught exception is published, and no
unresolved effect is reported as success. An unconsumed generator object is a
value, not automatically unfinished work. A registered child task or required
finalizer is work. Awaiting input, resource pause, cancellation, fault, and
unknown external outcome are distinct projected dispositions.

## 8. Computation as a research object and hypothetical branches

`ComputationView` exposes a read-only, versioned snapshot with bounded paging:
source spans, interpreter and guest frames, values, aliases, assumptions,
dependencies, exceptions, pending operations, costs and effect dispositions.
Inspection cannot mutate the field, mint permissions, or count as learning.
A brain context receives a selected, source-linked projection rather than an
unbounded heap dump. The existing context budget still applies.

A repair is a proposed operation against an identified continuation: substitute
an input, replace a method, or migrate compatible frames. It is applied at a
safe point after checking references and dependencies. Arbitrary debugger-style
rewriting of a live object graph is not a correctness-preserving repair.

`BEGIN`, `COMMIT`, and `ROLLBACK` retain regional §32.11 semantics. A branch
shares unchanged state and owns scoped overlays; nested branches remain in the
same image. Device copy-on-write pages are physical backing for these scopes,
not additional independently running field machines.

Branch inputs state what changed and whether it is observed, assumed, or
counterfactual. Results retain that classification. Publication checks the
base/read versions, authority, source support, reference-escape map, queued
events and nested scopes. A successful calculation does not turn an assumption
into an observation. The initial implementation invalidates prepared promotion
if its base changes; it does not guess a merge for mutable Python aliases.

Large promotion is staged and finishes with a bounded root switch. Rollback
tombstones the branch immediately and reclaims it incrementally. Its spent work
and retained evidence remain. Hypothetical external requests are inert intents;
choosing a branch may formulate a fresh authorized action, never replay one.

## 9. Native service and exact CPU/device representation

Build one C++20 field-runtime service per selected physical GPU, with a native
CPU regional backend and a Vulkan backend behind the same typed instruction
contracts. It has its own `VkDevice`, separate from Godot. Section 15 specifies
importing model computation into this service; the initial external llama.cpp
adapter retains its separately owned device and execution boundary.
It owns physical resources and private candidates; only the existing field
owner publishes adaptive state. CPU placement executes the same field
interpreter, not a hidden host CPython replacement.

The initial Windows transport is a restricted local named pipe authenticated
by the owning user/session, instance identity and per-launch nonce. Framing is
length-bounded and versioned. Large payloads use immutable, digest-identified
staging mappings with restricted handles; no service receives a shared writable
canonical owner buffer. Protocol/schema/size errors fail before allocation.

The current regional profile uses nine planes of float64 storage containing
finite, integral u32 word values. Ordinary GPU residency stores those words as
little-endian u32. Its physical ABI declares layout/version, source profile and
state digest, counts/offsets, instruction catalog, service generation, page
manifest, and separate transport digest. Numeric payloads retain their own
codec: u64/binary64 use paired words, arbitrary integers use limbs.

**Residency does not change canonical identity.** The existing `state_sha256`
binds profile/shape metadata and the complete float64 image bytes. Import and
export must round-trip those bytes exactly. Transport/page hashes cannot
replace that digest. The original checkpoint remains the recovery authority.

The current validator admits negative-zero word storage, but u32 packing would
reconstruct positive zero. Such an image returns `unsupported-image-encoding`
from the packed backend, unchanged; explicit same-machine CPU placement remains
possible. It is not silently normalized. A future canonical-format migration
would have its own profile, mapping and retained predecessor.

An image with 393,216 modes occupies 27 MiB in the existing nine-plane word
storage and 13.5 MiB packed; 128 packed images total 1.6875 GiB. This is raw
storage arithmetic, excluding all runtime/heap growth/scratch/brain costs,
not a capacity measurement.

Python typed records and device-friendly tables require explicit payload
schemas. The current JSON-framed records are not reinterpreted as binary structs.
Derived decoded indexes must be reconstructible; canonical binary payload
extensions require profile/schema migration. The resident path must not decode
and reserialize the entire field through host JSON for every interpreter step.

## 10. Resident memory and physical isolation

Suballocate large device arenas into logical pages; begin with 64 KiB logical
pages and satisfy queried Vulkan alignment/storage limits. Do not require
hardware sparse residency. Stable object references resolve through checked
owner, page/object generation, bounds and rights; physical addresses never
become Python identities or ambient authority.

Immutable code and compatible immutable data can share backing after import
policy checks. Heaps, learned values, event queues, scopes and continuations
remain owner-specific. Copy-on-write reserves the replacement before publishing
a mapping. New and reused allocations are explicitly zeroed before exposure.

At most one candidate epoch per owner may write. Its pages are private; the
published predecessor stays immutable. Allocation preflights data, events,
rollback metadata, checkpoint and error-report capacity together. Failed
admission cannot leave a half-visible object or lose the failure notification.

A retired page is reused only after all referencing candidates, checkpoints,
leases and GPU timeline uses retire. Generations never wrap into validity.
An expired lease fences publication; it does not prove submitted GPU work has
stopped or release its memory reservation. Device scratch is disposable only
when it carries no authoritative continuation information.

Sharing a GPU is not strong fault isolation. Descriptor/bytecode validation and
bounds checks protect ordinary execution; a service/driver fault can still
invalidate every member resident on that device. A physical reset may also
affect Qwen, Godot or the display. Recovery must retain their separate owners.

## 11. Automaton-selected work and Vulkan operation groups

The existing field-resident excitable automaton remains the semantic scheduler.
It advances its own excitation/recovery/trace state, chooses eligible work and
accounts for transitions. The runtime supplies capacity and fair shares across
owners; it never invents local intellectual priorities or readiness.

Per-owner event order, fairness and blocked-reason precedence remain those of
regional §32.8–9. Dependencies include program/frame/object versions, source
support, authority, topology, fuel and effects. Queue/cursor state remains in
the field; operation bins are disposable indexes over an identified selection.

The device loop is bounded:

```text
Read automaton-selected ready sites and version dependencies
  → classify by compatible operation / arithmetic / layout profile
  → stable compaction of independent sites
  → bounded direct or indirect compute dispatch
  → explicit storage/indirect-read synchronization
  → record ordered transitions and make further local work eligible
  → checkpoint boundary, wait, yield, cancellation or epoch cap
```

Compatible work may use one lane per simple continuation or a cooperative
workgroup for an explicit numerical panel. The interpreter decides semantics;
SIMD lanes do not. Dependent Python operations retain evaluation order. Branch
computations within one owner may evaluate private candidates in parallel only
when their read versions and ordered publication preserve the selected causal
sequence. Completion races never choose which result becomes field knowledge.

Use stable prefix-scan compaction, bounded queues and checked indirect dispatch
counts. Atomic append order cannot become event order. Workgroup synchronization
is local; cross-workgroup phases use dispatch boundaries and proper barriers.
There is no indefinitely running shader or global spin barrier.

Initial service policy allows one in-flight epoch per owner, at most 64 logical
transitions per owner epoch and 32 dispatches per submitted command sequence;
all existing per-kernel work, event, allocation and effect bounds also apply.
These are adjustable admission defaults, not a wall-clock guarantee. Device
loss, excessive latency or resource pressure reduces dispatch/epoch limits;
changing limits preserves the declared logical semantics.

The service queries limits and features instead of assuming float64, subgroup
width, timelines, synchronization extensions or memory-budget support. Integer
word storage needs no floating-point approximation. A binary64 primitive uses
an explicitly supported exact implementation or returns a placement requirement.
Backend-required requests refuse missing support; `auto` may select an allowed
semantically compatible CPU path and reports the actual placement.

## 12. Publication, effects, and recovery

One GPU epoch can compute several logical transitions privately. For the same
admitted inputs, arithmetic profile and transition count, it must reproduce the
ordered state/events, stop/fault boundary and logical charges of stepping.
Batching may remove physical copies and seals, not logical work. A later fault
retains the earlier successful transitions and the reference fault disposition.

The owner/service boundary is:

1. The owner durably identifies ordered inputs, request, predecessor, effective
   grants and resource reservation; it issues a fenced execution lease.
2. The service validates the binding, reserves peak resources, and computes a
   bounded private candidate on the selected backend.
3. Before returning the candidate, it exports touched pages and continuation
   state, ordered transition/effect intents, stop reason and physical telemetry.
4. The owner validates the changed closure, current dependencies/grants/fence,
   complete reconstructed state digest and the expected predecessor.
5. The existing durable publication mechanism atomically binds operation and
   request identity, predecessor, result and successor; recovery resolves that
   binding before acknowledging it. A stale candidate never overwrites a root.
6. The service receives publication disposition and retires only resources no
   longer referenced by a live candidate or submitted GPU operation.

A service result is `candidate`, not `committed`. Lost acknowledgments are
resolved by operation identity: a matching published request returns its prior
result; a different payload under the same ID is rejected. No re-execution or
second learning update follows merely from retrying delivery.

External effects use the entity's existing sequence: durable intent → authorized
dispatch/acknowledgment → durable raw outcome → owner admission → delivery.
No device dispatch sends network requests, publishes, purchases, or starts a
host process. Authority is checked at the point of action, including applicable
interactive approvals. Revocation fences unpublished intents and candidates.

External handles checkpoint as logical proxies with adapter identity and an
explicit reopenable/reconcilable/non-replayable disposition. They are not
serialized sockets, process pointers or locks. Unknown non-idempotent outcomes
block reconciliation; checkpoint replay never guesses an outcome or retries the
action. Time, entropy and environmental observations enter as identified inputs.

Cross-member delivery uses an outbox in the sender's committed result and an
idempotent receiver admission. Sender and receiver have separate commits; no
cross-owner atomic field merge is claimed. Already authorized immutable payloads
may be staged on-device, but they become receiver knowledge only after that
admission. Same-owner internal events can proceed within a resident epoch.

On service crash/device loss, unpublished work is discarded or retained as
non-authoritative diagnostic evidence. Rehydrate each last durable owner state,
replace service generations and leases, and replay only identified admitted
inputs. Effects remain governed by the independent journal. Partial GPU output
is never called a successful checkpoint.

## 13. Interpreting, specializing, and choosing execution placement

The same executable knowledge has three execution forms:

| Form | Use and condition |
|---|---|
| General field interpreter | Full dynamic behavior and the authoritative resumable program state |
| Guarded compiled regional/SPIR-V code | Repeated compatible interpreter routines or guest-code regions whose guards and lowering preserve meaning |
| CPU regional execution | Irregular work, absent device primitives, recovery, or a measured better placement; same field semantics and capability boundary |

Compilation is a derived implementation of identified program code, not another
learned mind. Artifact identity binds interpreter/guest sources, semantics,
regional catalog and schemas, primitive versions, guards, compiler version,
arithmetic profile, target features and driver/runtime compatibility. Immutable
artifacts may share physical backing across eligible owners.

Specialization guards cover actual type/layout/object/global/code versions,
input domains, dependencies and effective capabilities. Their outcomes include
true, false, unknown, stale and error; only checked true permits optimized
execution. Revocation or dependency correction invalidates dependent artifacts.

Every optimized safe point has a deoptimization map that reconstructs the
interpreter's heap references, frames, stack, operation cursor, exception state,
logical charges and completed effect/callback tokens. Guard failure before an
operation takes the general path; failure after committed progress resumes
from the next logical point. It never restarts an already completed effect.

Transparent replacement requires a proved local transformation or complete
check of a declared finite domain, preserving the regional successor and
observable boundaries. Finite differential runs do not prove equivalence for
arbitrary Python. A useful approximate algorithm or heuristic is an explicitly
assessed alternative method with its own applicability, not an exact JIT.

The field learns applicability, expected cost and the value of compiling from
actual work. The compiler supplies fixed lowering; the resource service enforces
limits. Compilation, failed candidates, checking and deoptimization are charged.
A cache miss changes physical work, not the chosen program's logical meaning.

## 14. Learned cooperation, representations, and regulation

Existing organism/Hive operations carry a question, offered method or partial
result with origin member, source/program version, assumptions, representation,
units, preconditions, expected outputs, cost, uncertainty and correction links.
These are views of the established semantic families, not a new knowledge graph.

Recipients choose among delegation, adoption and study through field programs.
A received contribution is not automatically installed as a skill. Interface
bindings and representation translations are executable, checked methods; their
usefulness is assessed from actual downstream results. Novel work can assemble
partial methods instead of choosing only from prewritten complete solutions.

For example, a bound-structure investigation can branch from one state into
perturbation analysis, a symbolic conservation argument and several numerical
resolutions. Members exchange constraints and methods; a synthesis checks their
assumptions and units and decides the next informative experiment. Disagreement
remains attributable rather than being removed by a vote.

The field can acquire policies for team formation, branch width, effort depth,
method choice and stopping. Existing affect/regulation supplies grounded context
for these choices. It changes allocation and inquiry, not truth, evidence
multiplicity or permission. Repeated forwarding of one observation is one source.

Corrected sources/methods invalidate dependent uses and guarded code, notify
known recipients through the existing Hive path, and leave unaffected knowledge
available. Each recipient admits corrections under its own policy and lineage.
There is no tensor averaging, automatic whole-mind synchronization or covert
adoption. Other languages and symbolic/numerical representations use the same
program, frame, event and capability substrate as Python.

### 14.1 Invented representations and internal languages

A recurring ambiguity, expensive calculation or useful analogy can become a
representation-development obligation within the current investigation. The
field proposes entities, roles, relations and operations that preserve the
distinctions needed by that question. A representation may be a relational
schema, geometric construction, equation system or domain language; inventing
syntax is optional. Its parser/interpreter or compiler, where needed, is an
admitted program on the same regional machine.

Retain executable mappings from identified observations and existing meanings,
including units, coordinates, time, uncertainty, validity and information loss.
A compact description of a structure must still expose which measurements it
can reconstruct or predict and which distinctions it cannot express. An
unavailable distinction remains unresolved rather than being assigned a value.
Mappings need not be invertible; an inverse has its own conditions and support.

Construct a candidate in a scoped branch, use it on the actual unresolved work,
compare its consequences with the original observations or a valid derivation,
and retain the resulting applicability and counterexamples. A field-structure
description might organize sampled values into circulation, symmetry and
boundary motion without claiming those variables are sufficient universally.
Qwen contributions, fixed codecs and acquired constructions retain their
separate origins.

Evolving a representation creates a version and dependency-aware migration.
Live procedures retain their original meanings until an explicit compatible
mapping exists. Changing a grammar or concept cannot silently redefine old
evidence. New operations compose admitted instructions; a representation cannot
mint a trusted primitive, physical sensor, permission or hidden host interpreter.

### 14.2 Runnable explanations and inverse design

A runnable explanation binds a `WorldProgram` to state variables, transition
and readout procedures, initial/boundary conditions, numerical assumptions,
parameter uncertainty, support and known failure regimes. Its state and
unfinished simulation belong to the invoking owner's branch. An external
simulator is an explicitly identified adapter with its own recovery contract;
it is never reported as resident execution merely because both use a GPU.

Competing explanations can share immutable observations while retaining
different assumptions and private state. Forecasts record the model/version,
inputs, horizon and observable they predict. Model disagreement can suggest a
discriminating observation; agreement does not create another observation.
Resolution, convergence, stochastic assumptions and approximation errors remain
attached to the result. Reusing a capture supplies another calculation from the
same evidence, not another independent sample.

Inverse design begins with an admitted desired readout and explicit horizon,
constraints, admissible variables/interventions and separately named objectives.
The field selects or constructs a search/control method and advances its
candidate frontier as ordinary resumable work. It may use sensitivity analysis,
automatic differentiation, symbolic reasoning or discrete search where their
assumptions apply. These are executable methods with charged work; a host
optimizer cannot silently choose the answer or change the desired outcome.

Each candidate retains its predicted outcome, constraint disposition, source
model and uncertainty. Distinguish a feasible candidate, a proved infeasibility
within the represented problem, and search exhaustion or missing information.
An optimizer cannot improve its apparent result by relaxing constraints,
changing the readout or choosing only favorable cases without a new identified
question. Model refinement and candidate search have distinct versions and
assessments, so improving a model's fit is not credited as improving the world.

An applicable candidate can formulate a fresh authorized experiment or control
request. Only its actual outcome enters as observation and informs the next
model/design revision. A hypothetical branch never dispatches an intervention;
new grants and consequential effects retain the entity's point-of-action
approval. Model predictions, selected plans and acknowledged world outcomes
remain separately inspectable.

### 14.3 Causal investigation of computation

Cassi may investigate an obstacle in its own ongoing work: whether an
observation changed a conclusion, an extra branch helped, a representation hid
a contradiction, or an acquired method could replace a costly reasoning step.
This is mission-directed inquiry using actual episodes, not a prerequisite
campaign to establish that the field learns.

A `ReasoningStudy` names the original episode, a restorable predecessor,
changed input/method/representation or work allocation, the measured outcome,
and the conditions held fixed. Fork through the existing scope mechanism.
Retain input and program versions, numerical/backend profile, model memory,
sampler/RNG state and identified environment events at the chosen boundary.
External effects are replayed as recorded observations or disabled intents;
the study cannot repeat the original action.

To ask about removing an earlier source, reconstruct before its admission or
account for every affected descendant. Deleting its current text while
retaining a model memory or derived conclusion influenced by it does not
remove its contribution. When complete reconstruction is unavailable, retain
the narrower question actually examined. A dependency trace locates possible
influence; it is not by itself a causal attribution.

Readouts can include changed conclusions, validity of an executed result,
error, unresolved distinctions, steps or measured resource use. A computational
contrast establishes a consequence within those execution conditions. It does
not prove a hypothetical world outcome or uniquely assign credit among
interacting methods. Nonmatching replay conditions, missing feedback, exhausted
work and an uninformative contrast remain distinct results.

Useful findings revise field-held applicability, effort allocation, inquiry
and regulation methods through ordinary outcome admission. All failed studies,
restoration work and discarded branches are charged. Replaying the source
episode does not count it as a new real-world experience, and a model's verbal
account of its reasoning is an attributed interpretation rather than a trace.

### 14.4 Specialist instruments and higher-order construction

Geometric reasoning, symbolic manipulation, tracking, estimation and control
are callable `InstrumentProgram`s with representation-aware ports. Tensor ports
declare shape, dtype, layout and meaning; all ports bind units/frame/time,
guards, effects, errors, dependencies and continuation/state requirements.
Stateful instruments use owner-held state with explicit branch behavior.
Imported neural programs and acquired procedures use this same composition
boundary while retaining their identities and numerical profiles.

A composition binds ports through checked translations, names unresolved
requirements, and executes with complete call/return and suspension state.
Private partial results are not published as complete answers. Feedback loops
retain their state and stopping conditions; component success does not prove
whole-loop stability or usefulness. Native tensor substitution requires an
applicable model-specific correspondence and separate assessment, not merely
matching tensor dimensions.

Construction is itself an ordinary learnable procedure. A `ConstructorProgram`
takes a typed problem, representation or method specification and returns
candidate program references, dependencies and unresolved holes. Constructors
can build other constructors through the same mechanism; products retain both
construction and source lineage. Fixed checking/lowering cannot supply the
answer-bearing construction while attributing it to the field.

Every product passes normal admission. Missing required components prevent
execution; imported closures cannot capture inaccessible owner state. Nested
construction shares the mission's work/memory allowance, yields through normal
continuations, and cannot alter the evaluator, evidence rules or permissions.
Changing a selected instrument produces a version; it does not patch an
incumbent beneath a suspended caller.

Hive contributions may include instruments, representations, constructors and
their adaptations. Recipients bind local meanings and prerequisites, then
delegate, adopt or study under existing policy. A portable constructor conveys
a way to build solutions; it does not disclose its author's private working
memory or grant authority to install host code. Assess actual compositions and
return attributed use/correction outcomes through the existing exchange path.

### 14.5 Experience-driven computational simplification

Consolidation can identify repeated reasoning, extract a guarded procedure, and
retain which circumstances require deeper work. The candidate includes the
source episodes, preserved distinctions, assumptions, exceptional cases,
dependencies and unresolved applicability. Experiences need not repeat exactly:
the field can construct a parameterized method from common structure while
preserving consequential differences.

Keep two routes explicit. Section 13 compilation changes the implementation of
an identified computation under its equivalence requirements. An acquired
shortcut, heuristic, approximation or different decomposition changes the
method and receives its own assessment. Matching several answers cannot turn
the second route into an exact replacement. A false, stale or unknown
applicability guard prevents use; the field chooses another eligible method or
retains the unmet requirement.

Exercise the method on its real intended work and informative boundary cases,
then use subsequent outcomes to improve its applicability. Count construction,
checking, compilation, exceptional paths, missed opportunities and recovery as
well as successful execution. Faster local execution is useful only relative
to the retained result requirements and downstream work. Unknown benefit stays
unknown; shortening a trace or increasing lesson counts is not the objective.

The field can acquire consolidation, teaching and effort-allocation procedures
through the same process. Their improvement stays attached to the mission and
actual consequences rather than becoming an unbounded self-improvement loop.
Existing affect supplies situated significance; it cannot make an appealing
shortcut correct or erase an inconvenient counterexample.

Retain source evidence and recoverable method versions under existing lifetime
rules. Correction invalidates dependent guards, compositions and compiled
artifacts while preserving unrelated knowledge. Quiet periods, cache eviction,
rejected candidates and failed upgrades do not erase acquired competence or
unfinished investigations.

### 14.6 Shared live research workspace

The user and Cassi work on the same identified investigation through authorized
views of its objects, explanations, predictions, observations and methods.
Text, equations, plots, spatial selections and timelines resolve to versioned
semantic/source references rather than becoming separate client-owned meanings.
A renderer states its representation, coordinates, units, time and omitted
detail. Changing a display is distinct from changing the underlying question.

The workspace supports three connected actions:

- **Inspect:** open a source or computation, compare branches, see unresolved
  distinctions, and follow a finding to the evidence or derivation supporting it.
- **Propose:** bind a user annotation, example, constraint or suggested
  relationship to the selected object and current revision. "These feel related"
  enters as an attributed proposed relationship; a desired outcome is a goal,
  not evidence that it occurred.
- **Investigate:** request a scoped variation, hold named features fixed, choose
  readouts, preview consequences and continue the resulting branch within the
  mission. Candidate methods and representations return to the same learning
  and construction lifecycle.

An admitted proposal has a principal, request identity, source/object versions,
intended role, dependencies and disposition. Ambiguous reference bindings
remain visible for resolution; clear authorized local work proceeds without
asking the user to approve each intermediate computation. A stale proposal
cannot silently target a newer object: preserve its original meaning and offer
a checked rebind or distinct branch. Neither viewing nor reconnecting creates
a learning event; admitted guidance and subsequent consequences do.

Show assumptions beside predicted outcomes, observed results beside their
origins, and running/provisional/committed/failed states distinctly. A comparison
displays what changed and which conditions were shared. Direct observation
opens the recorded artifact; rerunning an experiment is a separate action.
Scientific interpretation and user suggestions do not mint grants.

The client holds navigation and reconstructible projections, not an adaptive
planner or independent investigation database. Stable event cursors, request
identities and revision checks preserve work through reconnect and concurrent
edits. Pause/cancel, sharing changes and consequential actions use the existing
control and approval boundaries. Private evidence remains scoped in every
projection, export, brain context and Hive contribution.

These six capabilities form one development loop: an investigation constructs
a representation or instrument; its execution reveals consequences and costs;
useful structure becomes a reusable method or constructor; the next question
uses that capability while retaining the earlier evidence and exceptions.
The loop develops ways of computing without changing the identity, mission,
trusted execution rules or publication authority of the continuing organism.

## 15. Host capabilities and active-brain coexistence

Python code, imported sources and model output cannot grant capabilities.
Guest access resolves through unforgeable logical handles constrained by the
intersection of mission, owner, program, scope and current runtime grants.
Introspection returns field-language objects, never service memory or host
pointers. `eval`/`exec` retain exact source lineage and those same restrictions.

Generated Python may execute in the validated field interpreter with bounded
memory, instructions and capability mediation. This does not enable generated
host Python, arbitrary FFI, `ctypes`, native code loading or subprocesses. A
native extension/host-code lane needs real filesystem/network/process
containment and explicit adapter admission; a separate process and timeout
alone are not that containment. Current uncontained host execution stays disabled.

### 15.1 Resident brain destination and current boundary

Qwen 3.8 27B remains the active shared pretrained brain for conversation,
reasoning and synthesis. The destination is an imported `ModelProgram` executed
by the regional computer, with its unfinished computation in the invoking
owner's field. Python and model graphs are frontends to the same machine.
Model admission and tensor execution do not depend on completing the Python
language or its library ecosystem.

The implemented HTTP path and initial integration use an external model lane.
Requests yield the field continuation, retain task identity and evidence, and
resume on an admitted result. Embedding llama.cpp as a library in the native
service can reduce transport, but retains external/native execution attribution
until the regional program owns model control, operands, and continuations.
One opaque `llama_decode` or `run_model` instruction is not this destination.

A general guest runtime could also host compiled C/C++ with an implemented ABI.
The preferred model route imports its tensor/control graph and reuses numerical
kernels; it need not emulate the server application or an operating system.
Physical driver calls, source loading and authorized I/O remain fixed host
mechanisms. Tokenization, model control and sampling can execute as identified
field programs rather than permanently remaining host algorithms.

Imported pretrained weights retain their origin and model identity. Running
them inside the computer does not establish that Cassi acquired their knowledge
through its own learning. Reports distinguish imported model execution,
field-acquired construction, fixed lowering, and external execution. The active
brain remains useful independently of how many methods Cassi can execute alone.

### 15.2 Model programs, tensors, and complete continuations

Admit an identified executable package: model metadata and architecture,
quantized tensor manifest, vocabulary/tokenizer rules, graph/control program,
primitive dependencies, and arithmetic/quantization profile. Exact immutable
weight bytes may use digest-bound evidence backing shared across authorized
owners. Their typed bindings and executable use belong to the regional image;
deleting an incidental cache cannot erase the only implementation or model
identity needed to resume. Keep quantized data packed, without expanding every
weight into a float64 reference-cell representation.

The model program uses the common control instructions and bounded tensor
operations: indexed embedding reads, quantized matrix panels, normalization,
position transforms, attention panels, convolution, recurrent updates,
activation functions, residual operations and output sampling. Long operations
have explicit progress and private partial results. The trusted catalog
declares types, read/write effects, numerical semantics and indivisible work;
admitted model code supplies their composition and control. A new primitive is
a runtime/catalog upgrade, not authority granted by a learned program.

The Qwen hybrid execution state includes attention keys/values and their
position/sequence metadata, convolution and gated recurrent state, token and
block cursors, live residual/intermediate values, pending memory writes,
sampler configuration/history and RNG state. A final hidden vector does not
replace that history. Every live value needed at a safe point has an owned
regional reference or a declared exact reconstruction; descriptors, command
buffers and graph pointers are disposable physical caches.

Execution lowers to stages with explicit inputs, outputs and state effects:

```text
Input/tokenization → embedding
  → normalization / attention-or-recurrence / residual
  → normalization / feed-forward / residual → next block
  → output normalization / head / sampling
  → accepted token and memory commit → next token or return
```

Block/operator groups may be fused under Section 13 when their safe-point maps,
state effects and numerical profile are preserved. Mid-block suspension needs
the live tensors and operation cursor, not merely a layer number. Cancellation,
faults and retries cannot expose half-published recurrence or repeat accepted
sampling/effects. The current llama.cpp whole-decode graph and observation
callbacks do not provide this resident continuation contract.

### 15.3 Vulkan and llama.cpp reuse

Reuse GGUF loading semantics, the Qwen graph description, tensor layouts and
optimized ggml Vulkan kernels. The existing Qwen one-token service exposes
embedding, attention, feed-forward and head operations through `llama_context`;
it is a useful decomposition seam, not already a field-owned model runtime.
Import/lower graph stages into regional programs and field-selected operation
groups. Kernel implementations remain fixed execution machinery.

The current ggml Vulkan public interface initializes a backend by device
number; its device, queues, allocations and pipeline resources are privately
owned. Resident integration therefore requires a deliberate backend refactor
or field backend: explicit device/queue identity, allocation and tensor-view
ownership, command recording/submission, barriers, timeline dependencies,
lifetimes, error propagation and resource accounting. Sharing a process or GPU
does not supply this contract. Ordinary `VkDevice`s cannot exchange buffers or
semaphores implicitly; any retained cross-device adapter declares copies or
supported external-memory synchronization.

Semantic selection remains with the field automaton. The physical backend may
batch compatible independent work and execute approved fusions, but cannot
silently replace a selected program, choose a thought's conclusion, or keep an
unrecorded model continuation. Host execution or unsupported placement is
reported explicitly; it does not masquerade as resident model execution.

### 15.4 Thought branches and speculative decoding

Weights and immutable graph code share physical backing. Model invocations
have separate logical continuation roots. Exact matching prefixes may share
read-only attention pages when tokens, positions, masks, model/profile and
scope agree. Divergence requires private suffixes and recurrent/convolution
snapshots; sharing a weight bank does not merge members' working memories.
Persistent thought count and simultaneously active model decodes are distinct
resource quantities.

At a speculative fork, preserve all model memory, cursor and sampler/RNG roots.
An acquired field method or an explicitly attributed imported draft program
proposes tokens in a private scope. The target verifies from the correct
predecessor; publish only the accepted token prefix and its matching complete
state. Rejected tokens, RNG advances and recurrent writes cannot leak into the
next target step. Native partial sequence removal is insufficient where its
recurrent snapshot bound or additional coupling state does not cover the fork.

Exact speculative mode preserves the selected target computation/distribution.
Target-sample-and-compare can do this without draft probabilities when target
conditionals and state are unchanged; probability-ratio rejection sampling is
a separate acceptance optimization. Coupled field interventions define a
changed target and are labelled accordingly. Verification must read each row
against its correct prefix state, not a final state already changed by rejected
draft tokens. Whole-checkpoint restoration after a mismatch alone does not
repair a wrongly conditioned verification pass.

Draft acceptance measures agreement with the target, not program correctness.
Retain execution/scientific outcomes separately from draft acceptance and cost.
Speedup requires useful accepted work to exceed drafting, verification,
checkpoint, rollback and scheduling costs. No draft source is assumed faster.

### 15.5 Executable cooperation and acquisition

A field-owned construction method can emit a typed program, execute it
independently, or supply tokenized proposals to a resident model. The compiler
renders the selected structure; a host catalog of complete answers is not
field-authored construction. Qwen may contribute new candidate methods while
their acquisition, applicability and subsequent independent execution remain
separately attributed. Existing procedure/binding machinery supplies this path.

Within one investigation, a continuation can call a learned calculation,
request neural reasoning, inspect the result, branch a hypothesis, and resume
its program. The field chooses useful ready work and learns from actual costs
and consequences; hard capacity and interactive fairness remain host policy.
Recursive model requests yield rather than wait on their own occupied lane.

Model activations become versioned computation views, not automatically
understood concepts. Learned correspondences and bounded interventions carry
their dependencies and measured meaning through the existing entity coupling
path. Exact imported-model execution, changed model programs and acquired
replacement methods have distinct identities and assessments. Model/weight
changes never mutate the incumbent artifact beneath live continuations.

The initial external HTTP adapter retains semantic reconstruction when it
cannot restore native state. Resident execution must expose its actual
continuation, branching and backend capabilities through the existing entity
and owner surfaces; a backend label does not grant them.

## 16. Machine-wide resources and responsive operation

The [whole-machine performance design](CASSI-PERFORMANCE-DESIGN.md) connects
these execution and publication mechanisms to CPU cache locality, persistent
model state, grouped fields and neural experts, a shared resource executor,
and a field-owned communication service. It supplies the consolidated placement,
reuse, and improvement strategy; the native ownership and continuation rules
in this document remain applicable to every execution group.

Extend the entity's execution reservation journal rather than adding a second
resource ledger. Every reservation binds mission, owner/member, work order,
resource class, cap, lease/fence, measured consumption and settlement. Field
cost predictions guide proposals; the host accounts actual resources and applies
fairness, hard limits and interactive priority within the user's mission.

Account peak resident/COW pages, interpreter heap growth, program caches,
descriptors/commands, numerical and compiler scratch, device/host staging,
checkpoint copies and recovery headroom. Shared immutable backing is counted
once physically with an explicit allocation rule, not billed as free work.
Copies retain both source and destination charges until retirement.

Include Qwen weights, KV/cache, context and scratch, CPU/offloaded weights,
Godot allocations, pinned RAM and transfer bandwidth in machine admission.
Use reported Vulkan budgets where available and a conservative configured cap
otherwise; other processes can change availability after admission. Reserve
cleanup/export capacity before starting work. Out-of-memory returns bounded
backpressure or permitted CPU placement, never state reset or hidden brain-only
execution.

Logical transition/fuel/event charges remain deterministic. Physical time,
transfers, compilation, queue waits and memory pressure are separate observations.
When cost experience influences learning, admit it once as an identified event;
replay uses that event instead of remeasuring the clock. Backend comparisons use
the same admitted telemetry stream when claiming identical adaptive successors.

Pause/cancel/control is serviced at bounded submission and logical safe points;
no host deadline promises immediate GPU preemption. Windows TDR can reset the
adapter if work cannot complete or be preempted in time. Keep submissions
bounded and measure responsiveness under contention; do not disable the watchdog
or infer safety merely from an instruction count.

## 17. Existing public surface and lifecycle

Extend the existing owner-backed program admission/invocation, advance,
inspection and control operations and entity `/v1/programs` surface. No separate
Python-owner API or swarm-specific research endpoint is introduced. The proposed
program request carries a language/profile, exact source reference, input
references, limits, capability requirements and backend policy.
Resident model admission names the model program/tensor manifest and numerical
profile through this same surface. Inspection projects its stage, memory-root
identity and branch disposition alongside Python frames; it does not introduce
a second model owner or a parallel conversation-state database.

Execution returns a program/operation identity and the existing continuation
handle, with proposed Python projections for result, exception, frame/source
location, wait reason, logical cost, actual placement and checkpoint. Inspection
and branch requests name the expected owner/version; stale views cannot mutate
newer work. Backend selection never changes the public owner or program identity.

Distinguish language coverage, module/ABI coverage, available backends, granted
authority and temporary resource availability. Unsupported syntax, absent native
ABI, denied access and lack of VRAM are different failures.

```text
admitted → compiling → ready → running
running → yielded | waiting | resource-paused | completed | faulted | cancelled
waiting → running on the matching admitted event
resource-paused → running on a new reservation, or remains paused
unknown external outcome → reconciliation before further dependent execution
```

These are projections onto existing owner dispositions, not another durable
state machine. A bounded advance can finish while its Python task is unfinished.
Cancellation, late completion and duplicate delivery resolve against the same
operation/fence and effect history.

### 17.1 Research workspace projections and commands

The following are required extensions to the existing authenticated entity
API, not claims about fields currently returned or commands currently accepted:

| Existing surface | Shared-workspace extension |
|---|---|
| Program inspection | Authorized paged object, representation, method and computation views, each bound to an owner revision and immutable source references |
| Program guidance | Structured annotations, examples, representation suggestions and branch/inverse-design requests, with request identity, target references, expected versions, intended role and explicit argument values |
| Program control | Pause/resume/cancel the identified investigation and its structured work; do not reinterpret a view selection as a control action |
| Program events | Revision-bound proposal admission, clarification/conflict, operation progress, result and correction events; reconnect reuses the committed sequence |
| Artifact retrieval and approval | Scoped original evidence plus the existing explicit point-of-action approval for consequential effects |

Keep the current route meanings in
[entity Section 10](CASSI-ENTITY-DESIGN.md#10-communication-api-and-client-experience).
A client request becomes one owner-admitted proposal/obligation. The field
selects the computational realization; the fixed broker validates capability
and resources. No browser-side solver supplies an undisclosed answer, and no
projection authorizes a direct GPU or field write.

The proposed research client in `CassiQwen/research_workspace/` renders these
same surfaces without another backend or learned store. It must support the
complete inspect → propose → branch/compute → compare → retain/revise flow,
including stale selection, inaccessible source, absent capability, cancellation
and reconnect. Read-only views remain available when computation is paused.
Client deployment preserves loopback authentication, restricted origins and
cross-origin mutation protection; credentials never enter event or share URLs.

## 18. Source ownership and complete implementation sequence

Existing files below retain their responsibilities. New paths are **proposed**,
not claimed to exist. The native runtime has a standalone CMake build; the
workspace does not gain a shared build system.

| Source owner | Complete responsibility |
|---|---|
| `CassiFI/cassi_field_regions.py`, `CassiFI/cassi_regional_catalog.py` | Canonical records/instruction contracts, exact packing bridge, changed-closure checks, shared logical ordering and primitive definitions |
| `CassiFI/cassi_field_program.py`, `CassiFI/cassi_python_universal.py` | Regional admission/compiler and source maps; typed program-valued construction and inspectable representation lowering; reusable static analysis without making its analyzer a hidden evaluator |
| Proposed `CassiFI/programs/python/` | Interpreter, parser, object/import/exception/GC/library routines as reviewable regional source, acquired into existing field `Program`s |
| Proposed `CassiFI/native/field-runtime/` | C++ protocol/codec, CPU ISA backend, Vulkan device/arena/synchronization, bounded scalar/tensor primitives, model continuation execution, derived compilation and diagnostic replay |
| Proposed `CassiFI/cassi_field_runtime.py` | Thin transport/residency adapter, no adaptive choices or parallel persistence root |
| `CassiFI/cassi_learning_computer.py`, `CassiFI/cassi_field_owner.py` | Same-machine backend dispatch, fenced candidate validation/publication, scoped reasoning-study replay, continuation recovery and migration |
| `CassiFI/cassi_field_cognition.py`, `CassiFI/cassi_research_residency.py`, `CassiFI/cassi_research_organism.py` | Representation/world/instrument/constructor views and acquisition, field-owned inverse-design frontiers, reasoning studies, guarded simplification, applicability and outcome/cost admission |
| `CassiFI/cassi_hive_session.py`, `CassiFI/cassi_hive_collective.py`, `CassiFI/cassi_hive_runtime.py` | Persistent member attachments, attributed partial instruments and constructors, recipient binding, committed delivery, correction and existing adoption policy |
| `CassiQwen/cassi_autonomous_researcher.py`, `CassiQwen/cassi_field_brain_entity.py`, `CassiQwen/cassi_field_brain_server.py` | Existing director/root, resource and brain coordination, revision-bound workspace guidance/projections, authorized program/control and resumable event surfaces |
| `CassiQwen/native/llama.cpp/src/models/qwen35.cpp` | Identified Qwen graph/service source for field program lowering, explicit block inputs/outputs and attention/recurrent state effects |
| `CassiQwen/native/llama.cpp/ggml/include/ggml-vulkan.h`, `CassiQwen/native/llama.cpp/ggml/src/ggml-vulkan/ggml-vulkan.cpp` | Supported device/buffer/submission ownership seam and reusable tensor kernels; no implicit cross-device sharing |
| `CassiFI/cassi_research_worlds.py`, `CassiFI/cassi_cosmos_adapter.py` | Actual observation/intervention boundary, captured-source identities, model/prediction/outcome separation and effect-safe research continuation |
| Proposed `CassiQwen/research_workspace/` | Authenticated research client for linked text/geometry/equation/timeline views, structured guidance and comparison; reconstructible projections only |

Build dependencies define one complete destination:

| Work | Dependency | Observable completion |
|---|---|---|
| Exact regional CPU/runtime bridge | Current schema and catalog | Native CPU candidates match logical state/events/errors; canonical checkpoints and prior learning survive attachment and restart |
| Acquired Python interpreter | Regional program admission and bounded primitives | Full language/object/control behavior, libraries manifest, dynamic code and explicit environmental adapters execute through field programs |
| Persistent computation objects | Interpreter and owner publication | Inspect, suspend/reopen, preserve aliases/cycles/unwind state, settle cancellation and uncertain effects without duplicate actions |
| Resident Vulkan execution | Exact bridge and portable primitive contracts | Ordinary regional execution and required Python routines stay resident across bounded groups, with semantic parity and explicit CPU placement for declared adapters |
| Resident pretrained model | Regional program/tensor contracts and bounded native backend; full Python is not a dependency | Complete Qwen inference executes as a field program with matching model/profile behavior, canonical hybrid-memory/sampler state, safe-point resume and explicit backend placement |
| Branching and compiled methods | Continuations, exact safe points and reference maps | Scoped alternatives, checked promotion, guarded specialization and deoptimization preserve behavior and full logical accounting |
| Field construction and speculative use | Acquired procedures/bindings, model continuations and branch publication | A retained construction method executes directly or proposes drafts; verification commits only the accepted prefix and matching state, with correctness and agreement assessed separately |
| Cooperative organism integration | Existing director, Hive and reservation journal | Independent enduring members exchange useful partial methods while Qwen remains responsive and the root retains mission continuity |
| Invented representations and runnable explanations | Program-valued records, scoped execution and observation mappings | A research obstacle produces an executable representation/world with applicable mappings, retained losses, predictions and correction-aware use |
| Inverse design and causal reasoning studies | Complete checkpoints, identified outcomes and resource/effect boundaries | A desired constrained outcome drives resumable candidate search; an episode-specific computational contrast changes method assessment without manufacturing world evidence |
| Specialist instruments and constructors | Typed ports, admission, continuations and Hive bindings | Members compose a complete instrument, use a constructor to build an adapted method, and retain product lineage and observed behavior |
| Experience-driven simplification | Outcome history, applicability and identified program versions | Repeated work yields a usable guarded method with explicit exceptional behavior, complete cost and separate exact/approximate status |
| Shared live research workspace | Revision-bound entity views, guidance, control and events | A user suggestion becomes a scoped investigation, compared results and retained guidance; pause/reconnect, stale targets and private evidence retain their meanings |
| Self-hosted development and scientific use | Complete interpreter, cooperation and actual tool outcomes | Cassi develops its own interpreter/compiler methods, retains useful revisions and completes a substantial continuing research investigation |

Interpreter routines, model graph lowering, native operation implementation,
and organism integration may be developed concurrently against the same
identities and schemas. Dependency order is not permission to stop at a syntax
analyzer, arithmetic-only Python subset, opaque embedded model call,
numerical-only GPU solver or disconnected swarm demonstration.

Migration uses the entity's existing immutable generation/cohort mechanism.
Quiesce affected writers, preserve owner/runtime/profile/checkpoint pairs and
journals, prepare explicit record/continuation mappings, validate successors,
and activate a compatible set. Unsupported continuations retain their original
runtime and exact state; they are not reset. Failed migration keeps the
recoverable incumbent and any newer evidence requiring reconciliation.

## 19. Operational completion and performance questions

Implementation checks serve actual language/runtime behavior, not a new
qualification campaign for Cassi's established learning. No blank-field,
teacher-withdrawal or general-learning comparison is required by this design.

The complete system must exercise:

- Language cases where aliases, mutable closures, dynamic classes/descriptors,
  negative division, Unicode indexing, exceptions/finally, generators and async
  suspension affect the answer; compare only the appropriate Python guarantees.
- Cycles, weak references, resurrection and suspended finalizers across
  collection/restart; buffer aliasing and resource exhaustion without corruption.
- A real failing computation inspected, repaired as a new version, and resumed;
  `eval`/`exec`, cyclic imports and a precisely reported unsupported native ABI.
- General versus optimized execution, including a guard invalidated after
  mutation and deoptimization after a callback, without repeating its effect.
- Scoped alternatives with conflicting assumptions, parent revision, nested
  rollback, escaping references and a retained non-selected branch cost.
- Several independent existing owners, restart from committed state, stale
  generation/fence, duplicate result, queue pressure, cancellation and GPU loss.
- An authorized effect with lost acknowledgment and owner reconciliation,
  plus denial/revocation; neither a speculative branch nor a replay dispatches it.
- Actual collective use of complementary contributions, source correction,
  continuing Qwen conversation and acquired method reuse in a real investigation.
- Resident model results against the pinned imported model and arithmetic
  profile, including attention and recurrent history, batching and tokenization.
- Suspension/restart at declared model safe points, separate owner contexts,
  exact-prefix sharing and divergence, sampler/RNG recovery, and memory pressure.
- Accepted and rejected drafts with deep rollback, partial acceptance, model
  coupling state and correctly conditioned verification; no speculative effect
  or mutable suffix survives rejection.
- Acquired construction used directly and as a draft, with attribution of field,
  imported-model and compiler contributions and independent behavioral results.
- An invented representation applied to actual source observations, including
  an unexpressible distinction, lossy mapping and corrected dependency.
- A runnable explanation's forecast joined to its real outcome; inverse design
  distinguishes a feasible candidate, proved bounded infeasibility, exhausted
  search and an unobserved prediction without weakening the requested constraints.
- A reasoning study that restores the relevant predecessor, isolates the
  declared change and identifies when contaminated state or missing feedback
  prevents the broader causal conclusion; replay dispatches no external effect.
- A composed instrument and a constructor-produced adaptation used on their
  intended work, including incompatible meaning/units, unresolved components,
  inaccessible captured state and correction of an adopted dependency.
- A guarded simplification with a meaningful exceptional case and complete
  costs; exact compilation and assessed alternative methods remain distinct.
- An actual research-client interaction linking a user example to objects,
  a scoped branch, comparison and retained method; reconnect, stale guidance,
  denied source access and cancellation preserve the original investigation.

A speed claim compares useful completed work with matching inputs, language and
numerical semantics, outcomes and resource limits. Include native CPU and
ordinary CPython CPU where applicable; compare numerical paths with properly
batched/compiled Torch, not only eager per-operation calls. GPU and CPU may have
different physical telemetry without different logical answers.
Resident model speed claims also compare the pinned llama.cpp implementation
with the same model, context, generation policy and declared numerical
semantics; count model-state traffic and all branch/sampler work.

Measure end-to-end throughput, time to useful research result, p95 conversation
and cancellation latency, resident/peak memory, transfer volume, compilation
amortization, wasted speculative work and recovery time. Report cold/warm code,
resident/spilled state, branch width, program mix and brain contention. Stable
resident operation and useful cooperation matter more than a shader-only ratio.

Workload-specific thresholds, profitable specialization, safe epoch sizes and
actual member/branch capacity are empirical questions. The architecture fixes
who decides, what state means and how recovery works before those measurements;
it does not manufacture a speedup or capacity result.

## 20. Primary references

These specify language and hardware behavior; they are not evidence that the
proposed Cassi runtime has already implemented it.

- [Python 3.12 execution model](https://docs.python.org/3.12/reference/executionmodel.html)
  and [data model](https://docs.python.org/3.12/reference/datamodel.html): scopes,
  objects, identity and implementation-dependent collection behavior.
- [Python extension and embedding boundary](https://docs.python.org/3.12/extending/index.html):
  native libraries are separate implementations, not source-language semantics.
- [Vulkan indirect dispatch](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdDispatchIndirect.html):
  dispatch dimensions in a device buffer and their explicit validity requirements.
- [Vulkan memory allocation](https://docs.vulkan.org/guide/latest/memory_allocation.html):
  suballocation, discrete-device transfer and allocation limits.
- [Vulkan physical-device features](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceFeatures.html):
  queried optional features, including shader float64 support.
- [Windows timeout detection and recovery](https://learn.microsoft.com/en-us/windows-hardware/drivers/display/timeout-detection-and-recovery):
  bounded GPU execution, reset behavior and the need for durable host state.
- [PyTorch operation fusion](https://docs.pytorch.org/tutorials/recipes/recipes/tuning_guide.html#fuse-operations):
  an appropriate optimized comparison, rather than assuming Vulkan wins by API.
