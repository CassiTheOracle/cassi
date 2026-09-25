# Cassi Surface: A Persistent Computer-Use Body

## Status and relationship to the entity

**Software interfaces implemented; dedicated Linux workstation operational—2026-09-22.** The shared Surface broker, field-owned sensory publications and procedures, authenticated entity routes and viewer, field-native backend, native Windows helper, Linux RFB and portal clients, supervision, and scoped artifact/audio facilities are present. The restricted Ubuntu 24.04 WSL2 `cassi-surface` account runs Xfce on Xvnc with a private RFB socket behind mutually authenticated loopback TLS. Windows drive automount, process interoperability, automatic host paths, and shared clipboard are disabled. The entity service can start the configured session, require a complete 1280×800 baseline, register its visual and dedicated PulseAudio routes, and stop only that session. Host-protected transport credentials remain outside the field and guest actuator context.
The actual Linux desktop has published visual and private-sink audio into the continuing field. A scoped keyboard grant inserted text in its terminal, a bounded field-held audio page played to its exact null sink with server-accepted acknowledgment, and an exact binary artifact crossed from Windows into the restricted Linux home with matching guest SHA-256. A restarted desktop received a new source incarnation and rejected the old RFB binding. The field-native application path has also been exercised through the authenticated entity and browser, including durable effect replay, revocation, human takeover, and retained observation. Native Windows capture and UI Automation reached a live Notepad window; the focus fence rejected an action after another window took focus, and successful foreground insertion remains unverified. A masked owner-held visual page reached the local image request and refused a protected password region. The Wayland portal awaits an actual consenting compositor; 35B multimodal inference and PCSX2 interruption remain explicitly deferred. No mission or model run is started by this document.

The resident program path has also run a registered field-owned procedure against the field-native application: it read a bounded live sensory page, emitted one scoped input through the effect broker, inspected the queued-only acknowledgment, observed the next published frame, and completed from its persisted field checkpoint without repeating the input. The queue acknowledgment does not assert that the application achieved the procedure's goal; that conclusion requires the new observation.

The normal entity service now accepts a separate host-held human token for an exact active mission, source instance, and operation set. One approval supports repeat bounded broker leases across viewer reconnection, broker-only release, and a geometry rebind of the same source; a source restart or mission change requires new approval. Emergency revocation fences in-flight grants and closes the mission window, while human takeover still requires a fresh exact token confirmation. The browser and HTTP paths were exercised against an isolated synthetic canvas; the provisioned token has not authorized the real Linux desktop. Windows and restricted-guest audio helpers compare both active source-file SHA-256 values before guest media capture or playback; matching deployed bytes worked and deliberately drifted bytes were rejected.

Cassi Surface gives the existing Cassi entity a continuing connection to computer environments. New applications and tasks change Cassi's knowledge and acquired procedures, without requiring application-specific source code, tools, adapters, or installed generated plugins.

The [entity design](CASSI-ENTITY-DESIGN.md) owns identity, missions, authority, and external-effect semantics. The [regional field design](CassiFI/FIELD-INTELLIGENCE-DESIGN.md#32-one-universal-regional-field-computer) owns representation and execution; its [world-model design](CassiFI/FIELD-INTELLIGENCE-DESIGN.md#33-field-native-world-modeling-and-lifelong-general-intelligence) supplies perception and action semantics. The [living memory design](CASSI-LIVING-MEMORY-DESIGN.md) owns retention, recall, and continuity. The [programmable swarm design](CASSI-PROGRAMMABLE-SWARM-DESIGN.md) supplies executable acquired knowledge and shared computation. Surface adds a body to those systems, not another mind, planner, memory database, or research scheduler.

The [desktop companion design, **Cassi, beside you**](CASSI-DESKTOP-COMPANION-DESIGN.md)
specifies the everyday **Watch with me** interface: source selection, shared
moments, quiet questions, inspectable learning, and scoped desktop demonstrations.
It applies the Surface mechanisms here to Carina's ordinary desktop work.

## 1. The enduring requirement

Cassi can pursue any authorized task expressible through available computer interfaces using one stable perception, control, and learning system. An unfamiliar application is something to investigate and learn, not a request for another integration.

The fixed implementation supplies general interfaces, execution mechanics, and policy. The field supplies changing interpretations, object identities, goals, expectations, and acquired procedures. Learned procedures are executable knowledge: freezing the host software does not freeze Cassi's behavior.

Writing code may itself be an authorized task. Installing generated code as a new privileged Surface adapter is not a way to satisfy the computer-use requirement. Likewise, a new application must not require a new central scheduler branch, native instruction, hand-written application prompt, or application-specific endpoint.

Universality describes access and composition across available interfaces. It does not guarantee success without learning, inaccessible privileges, unbounded computation, support for nonexistent devices, or freedom from operating-system and security maintenance. A missing capability is reported precisely, with the unfinished responsibility retained.

### Core invariants

1. One continuing canonical field owner holds adaptive understanding and acquired behavior.
2. The active pretrained brain remains intentional; its contributions have explicit provenance.
3. Incoming measurements, inferred interpretations, predictions, and imagined branches remain distinguishable.
4. The live sensory region is directly addressable by field computation, not merely a screenshot filename in a prompt.
5. Capture and input helpers own mechanics, never independent learned policies or authority.
6. The host authenticates permissions at the boundary of an effect; observation cannot grant permission.
7. Input delivery and successful task completion are different facts.
8. Unknown non-idempotent effects are reconciled, never blindly replayed.
9. Human takeover and emergency stop remain responsive without waiting for the brain.
10. Closing a viewer does not end an independently running desktop or reset Cassi's mind.
11. All descendants, retries, and continuations consume their root mission's resources and permissions.
12. Completion requires the requested result and supporting evidence, not a finished action sequence.

## 2. One mind across several environments

```text
Authenticated user and existing entity client
                |
Existing entity, owner, workspace, brain, and acquired programs
                |
Field-owned attention, world bindings, predictions, and intentions
                |
Live sensory input regions / authorized effect requests
                |
One capability and effect boundary
       +--------+---------+----------------+----------------+
       |                  |                |                |
Windows helper     Linux virtual      Linux portal     Field-native
in user session    desktop bridge     desktop bridge   virtual surface
       |                  |                |
Windows apps       WSL2 / Linux VM    Wayland session
                   / native Linux
```

The preferred independent workplace is a dedicated Linux desktop, initially hosted in WSL2 on the Windows workstation. The existing field and brain may remain on Windows. The Linux environment is a place where Cassi works, not a second entity and not a requirement to migrate model execution or its GPU stack.

Native Windows applications use an explicit Windows Surface binding. Native Linux hosts and Linux VMs use the same Linux backends. A supported field-native program can publish the same sensory and input boundary directly. An isolated Windows VM uses the Windows backend inside that VM.

One responsibility can use several environments. Switching environments preserves its goal, learned methods, evidence, and continuation. It does not transfer permissions, credentials, open OS handles, or pending input implicitly.

## 3. Deployment profiles and actual capabilities

| Profile | Purpose | Sensing and input | Principal boundary |
|---|---|---|---|
| Dedicated Linux virtual desktop | Default independent browser, document, terminal, development, and application work | Xfce on Xvnc; one controlled RFB connection; optional AT-SPI; dedicated audio service | Own display and input domain; all applications on that X11 display share a trust domain |
| Windows interactive desktop | Native Windows applications in the user's existing session | Windows Graphics Capture, UI Automation, native input, scoped audio | Shared foreground keyboard/pointer; human input and privilege boundaries take precedence |
| Linux portal desktop | Existing supported Wayland sessions, including native Linux and provisioned virtual sessions | ScreenCast/RemoteDesktop portals, PipeWire, EIS where supported, optional AT-SPI | Compositor-granted sources and devices; consent and restore-token rules remain operative |
| Isolated desktop | Work requiring enforceable filesystem, process, credential, or network separation | The same Windows or Linux backend inside a deliberately configured VM | Isolation depends on VM configuration and permitted integrations, not on the word “virtual” |
| Field-native surface | Programs supported by Cassi's own runtime | Direct typed visual/audio publication and standard input events | Same ownership, authority, clock, and evidence rules |

These are environment profiles of one system. Platform capability differences remain visible. The existence of a desktop does not imply audio capture, relative-pointer capture, touch, controller injection, GPU acceleration, or accessibility support.

Every backend publishes a capability descriptor containing supported operations, limits, coordinate systems, formats, clock sources, acknowledgment strength, cancellation behavior, privilege requirements, and current availability. Capabilities are independently marked supported, unavailable, denied, degraded, or lost, with a reason. A single `can_control` flag is insufficient.

A procedure declares the capabilities it needs. If an authorized equivalent route exists, Cassi may choose it explicitly. An unsupported input method is not silently approximated: relative game input, for example, cannot be claimed equivalent to moving an absolute desktop pointer.

## 4. Process ownership and communication

The existing entity remains the cognitive and program-lifecycle entrypoint. The host capability broker is the only route from a field intention to an external action. It owns authenticated grants, durable effect reservations, input-resource leases, revocation fences, and recovery.

Platform helpers perform capture and bounded input in the appropriate OS session. They have independent watchdogs and bounded queues. Helpers may cache framebuffer tiles, accessibility objects, and transport state as disposable operational material; none becomes an authoritative adaptive store.

A supervisor owns named process lifetimes, readiness, restart policy, and graceful shutdown. It does not select research goals. A Windows service, if used for supervision, does not attempt interactive capture or input from Session 0; those operations belong to a helper in the authorized interactive session.

### Independent lifecycles

| Object | State and transition responsibility |
|---|---|
| Environment | Configured/stopped, starting, ready or degraded, quiescing, stopped; a failed start retains its reason and bounded restart policy |
| Source binding | Discovering, bound, live, stale/lost, detached; a source change invalidates only its dependent observations and controls |
| Control lease | Requested, granted, active, suspended/revoked/expired, released; sensing can remain live without control authority |
| Mission | Existing entity states: ready, running, waiting, paused, blocked, completed, archived |
| Viewer | Disconnected, observing, or holding a broker-granted human-control lease; its connection does not own environment lifetime |

An environment becoming ready does not automatically grant control. A lost source does not erase a mission. Reconnecting a viewer does not resume a paused procedure. Destruction, application termination, and session shutdown remain distinct authorized operations.

### Control plane and sensory data plane

Control messages are bounded, versioned, authenticated records. Large image/audio pages travel on a separate bounded data plane. A flood of pixels cannot block cancellation, grant revocation, or input neutralization.

Use local authenticated IPC appropriate to the deployment: access-controlled named pipes on Windows, peer-authenticated Unix sockets within Linux, and an authenticated connection across Windows/WSL or VM boundaries. Loopback binding limits exposure but is not authentication. Guest messages cannot mint host capabilities.

Bulk buffers may be shared within a compatible process/device boundary. Cross-WSL and cross-VM transport must not be described as zero-copy without an implemented compatible mechanism. Copies, decoding, transfer storage, and bandwidth are charged to the mission's resource account.

Protocol versions negotiate before binding. Unknown required semantics, malformed dimensions, unbounded trees, oversized batches, invalid coordinates, unsupported encodings, or expired references are rejected before use. No protocol field accepts arbitrary host callbacks or native object handles supplied by the model.

### Public operations

Expose one generic Surface capability family through the existing entity: describe authorized environments and sources; bind or release a source; subscribe to live publications; submit a bounded intention through the owner; inspect or reconcile an effect; and request pause, resume, revocation, or human takeover. Existing artifact and program interfaces handle transfer and mission management.

These operations manage a continuing connection. The brain does not have to call Observe, Act, and Wait in a screenshot-driven conversation to keep the environment alive. Event and publication cursors support reconnect without admitting the same experience twice.

## 5. Shared records

These are typed views over existing `Value`, `Binding`, `Event`, `Program`, `Assessment`, and `Obligation` records, plus nonadaptive execution records. They are not six new databases.

### 5.1 Mission

A mission binds its identifier and goal revision; original user objective; authorized environments, applications, sources, workspaces, and data flows; required deliverables; completion evidence; forbidden outcomes; resource and time allowances; and conditions for asking, pausing, or stopping.

The field may develop subgoals and methods. It cannot replace the original objective with an easier completion condition. Amended user guidance has a new revision and invalidates affected pending intentions while preserving actions already taken.

### 5.2 SurfaceBinding

A binding records:

- Environment identity, environment incarnation, source instance identity, source epoch, and backend version.
- Session/display/window identity, ownership relationships, and permitted child surfaces.
- Supported and currently available channels and controls.
- Geometry revision, logical and physical extents, scale, orientation, and coordinate transforms.
- Clock domains, timestamp interpretation, uncertainty, and freshness requirements.
- Authority handles, privacy labels, permitted data recipients, and evidence-retention policy.
- Current control-domain lease and binding state.

Titles, process IDs, window handles, accessibility IDs, and PipeWire node IDs are not sufficient permanent identity. Reuse or restart must not attach old authority to a new instance. A source restart changes its epoch; a resize changes geometry; an object changing value changes the relevant object version. Ordinary animation does not invalidate everything.

### 5.3 ObservationPublication

A publication binds an immutable generation to its source and epoch, sequence identity, typed pages, channel revisions, valid extent, changed regions, cursor treatment, missing/redacted areas, and provenance.

For each channel retain source/sample time when available, receipt time, field-admission identity, clock domain, timestamp uncertainty, and age. Missing source time stays unknown; a receipt timestamp must not be relabeled as the capture time. Asynchronous image, accessibility, audio, and lifecycle samples do not become simultaneous because they share a publication record.

Coverage is explicit: skipped intervals, coalesced updates, truncated trees, dropped events, unknown regions, and stale channels are not equivalent to “no change.”

### 5.4 ControlIntent

An intention binds an operation ID and canonical request digest; mission and goal revision; surface instance and epoch; semantic target; relevant source/field dependency versions; exact control values or bounded stream profile; host authority handle; expected consequence; resource reservation; deadline; maximum duration; and stop conditions.

The original field predecessor remains provenance. Dispatch revalidates the relevant dependency read-set against the current state instead of requiring the entire field root to remain unchanged throughout deliberation.

Canonical identity includes everything that changes the action or its scope. Protected credentials are represented by opaque, version-bound secret references, not plaintext or exposed password hashes. Changing arguments under an existing operation identity is a conflict.

### 5.5 EffectOutcome

The outcome separates attempted delivery, provider acknowledgment, application observation, and task assessment. It contains partial-delivery information when known, uncertainty when not, supporting observation/artifact references, and any reconciliation obligation.

Possible delivery dispositions include not started, rejected, partially delivered, delivered, and unknown. Observation can establish success, failure, continued waiting, or an unresolved result. “Transport accepted” never automatically means “application acted.”

### 5.6 Procedure

An acquired procedure carries typed parameters, purpose, applicability, dependencies, capability requirements, executable control flow, expected effects, stop conditions, known exceptions, recovery choices, and supporting experience. It references grounded objects and conditions rather than storing unexplained coordinate macros.

## 6. The live sensory region

### 6.1 Physical representation

The sensory region is directly addressable in the regional computer's input space. Its physical backing uses packed nonadaptive image/audio/source pages, kept hot in RAM or VRAM where appropriate. The owner publishes immutable generations and their bindings. Field programs consume those regions directly.

This does not require encoding each pixel as a permanent semantic observation or rebuilding the whole dense field for every refresh. The input region is read-only to cognition. Adaptive attention, identities, interpretations, and procedures live in the canonical field's ordinary learned state.

Use reference-pinned generations and bounded buffer pools. A producer cannot overwrite pages still being read by a field kernel, perception instrument, or evidence consumer. Publication occurs after the required CPU/GPU fences. Retained evidence must own stable bytes before capture-buffer lifetimes expire.

### 6.2 Updates and continuity

The input pipeline supports initial full images, incremental changed regions, layout changes, and complete resynchronization. A partial update is meaningful only against its declared valid baseline. Reconnect, dropped required deltas, or incompatible format changes invalidate that baseline until a full reconstruction is available.

A coherent publication means stable, well-described data. It does not promise that an application rendered atomically or that all channels were sampled at the same instant.

Maintain a bounded rolling temporal buffer. Pin selected moments or intervals around decisions and outcomes under the evidence policy. Continuous viewing does not produce an unbounded permanent movie or one durable cognitive commit per frame.

### 6.3 Multiple rates and overload

Capture, resident control, brain deliberation, and memory maintenance run at different rates. Latest-frame coalescing may discard superseded visual data with explicit gap accounting. Discrete events are preserved in order or their loss is recorded. Audio loss retains its interval and duration. Control and revocation traffic cannot be coalesced away.

Each action requires an appropriate freshness bound. If the available observations cannot support it, stop or wait rather than continue from an invented current view. A living connection heartbeat proves transport liveness, not fresh pixels.

### 6.4 Attention and interpretation

Field-owned attention chooses broad overview, focused detail, temporal windows, text spans, and relevant accessibility subtrees. Deterministic crops, pyramids, differences, and coordinate transforms report their parameters and information loss.

The active visual path must actually receive images or identified visual features and temporal context. A token-only brain connection does not satisfy the full visual contract. Pretrained vision, OCR, speech recognition, and speech synthesis may be declared instruments; their supplied interpretation is attributed and admitted by the same owner. They do not acquire a separate continuing memory.

Prioritize changed expectations and progress, not merely changed pixels. Animation, cursor blinking, and repeated retries cannot manufacture evidence of success. Remembered or predicted occluded objects retain uncertainty and age. Internal rollouts and Cassi's own explanatory overlays are never admitted as observations of the external application.

## 7. General controls and procedure execution

| Control family | Required distinction |
|---|---|
| Keyboard | Physical key identity and state, key chords, repeats, and bounded holds |
| Text | Intended Unicode text, layout/IME behavior, composition, and supported insertion route |
| Pointer | Absolute versus relative coordinates, movement, buttons, wheel units, drag state |
| Standard devices | Touch contacts, pen state, controller buttons/axes, only when the backend actually supplies them |
| Accessibility | Supported standardized actions and current object references, with explicit provider provenance |
| Content transfer | Typed clipboard payloads or artifact exchange, separately authorized from input |
| Environment | Discover, bind, select/focus, observe lifecycle, and authorized launch/close operations |
| Media | Authorized audio capture/playback or other provisioned media channels with declared routing |
| Existing capabilities | Typed invocation through the existing broker and its actual policy |

Application semantics such as “export,” “attack,” “insert a chart,” or “reply to this message” belong to acquired procedures. No central dispatcher recognizes them as privileged application-specific commands.

The fixed execution language supports sequence, guarded choice, loops, calls, event/condition/time waits, parallel children, joins, typed errors, deadlines, cancellation, and checkpoints. External retries require a justified idempotency or known-not-started condition. A generic retry operator never overrides effect uncertainty.

A resident routine reads current conditions, emits bounded intentions, and observes consequences while the brain can continue deliberating. It yields on a lost target, surprise, insufficient freshness, exhausted resources, new human guidance, authority change, or required approval. Hypothetical branches cannot dispatch real effects.

Learning uses authorized manuals, demonstrations, prior knowledge, actual attempts, and observed consequences through existing machinery. Preserve failures and applicability conditions. Repair the affected part of a plan when an interface changes. This work does not require a new blank-field comparison, transfer campaign, or learning requalification.

## 8. Windows backend

### 8.1 Native session helper

Run capture, UI Automation, and input in a helper bound to the actual authorized Windows user session. A supervisor may manage that helper, but elevated service ownership is not permission to bypass the interactive session or secure desktop.

Authenticate the helper's Windows user SID, session ID, input desktop, and helper generation at connection and handoff. Do not infer those from a window title or let a service's stronger token silently become the application's input authority.

Use Windows Graphics Capture for authorized windows or displays, with explicit source selection and supported permission flow. Preserve capture-item identity, frame timing where supplied, content size, pixel format, colour space, and cursor policy. Handle resize, device loss, source closure, lock, disconnection, and unavailable/protected capture as lifecycle events. Never treat a stale or unavailable image as proof that the application is simply displaying black.

Keep capture support, target availability, and image content separate. A valid black image is possible; black pixels alone neither prove a fault nor justify a bypass. Preserve HDR data in a supported format or record an explicit conversion. Capture-border suppression requires its actual platform consent and capability; it is not an invisible default.

Do not depend on minimized, disconnected, occluded, or inactive windows continuing to produce fresh frames. The selected capture path must report its actual behavior. Recreate frame resources after a geometry/device change and invalidate dependent coordinates before further control.

### 8.2 Accessibility and input

UI Automation is a sourced structural channel and optional standardized action route. Its objects can become stale; provider calls can hang or fail. Isolate and time-bound those calls without holding the canonical owner lock. Rebind targets using current context, and preserve ambiguity rather than guessing between similar controls.

Use native input with explicit physical-key versus text semantics. SendInput insertion counts describe insertion into the input stream, not application success. Partial batches and existing physical key state matter. Input injection is subject to Windows privilege restrictions; failure is not a reason to elevate automatically.

Foreground keyboard and pointer actions require the correct input desktop, target, focus, transform, and exclusive control lease at the final dispatch fence. A focus request can fail. Never continue by typing into whichever application currently owns focus. A background accessibility operation may avoid foreground input only where the provider actually supports it and the mission permits that route.

### 8.3 Human priority and scope

Track broker-owned synthetic input separately from human physical input as far as the backend can establish. Never claim that a physically held key belongs to automation. Takeover cancels queued conflicting actions and neutralizes Cassi's controls; uncertain release remains an explicit condition requiring recovery.

Windows Task View virtual desktops are not independent keyboard/pointer sessions or isolation boundaries. Truly independent Windows work uses an explicitly provisioned VM or supported separate-session arrangement, with its licensing and lifecycle constraints. Switching a task to another Task View desktop is not a substitute.

Owned dialogs, browsers opening new windows, and child processes do not automatically expand a grant. Bind them only when the mission's rules cover the actual source and operation. UAC and other protected interactions retain their native user-mediated boundary.

## 9. Dedicated Linux workstation

### 9.1 Default deployment

Provision a dedicated distribution and restricted Linux account for Cassi. The default desktop is Xfce on TigerVNC Xvnc, with its own display, session bus, runtime directory, application profiles, and audio service. The same profile can run under WSL2, on a Linux host, or inside a Linux VM.

This is a complete virtual desktop session. WSLg's normal integration of individual Linux windows into the Windows desktop is a separate facility and does not supply this independent workspace.

Launch applications with the dedicated session environment. Do not inherit WSLg display, Wayland socket, session bus, or audio variables accidentally. Applications that require a Wayland environment use the supported portal/compositor profile; Xvnc is not described as a native Wayland server.

The session manifest identifies its display, owner-only Xauthority material, private runtime directory, session bus, and audio endpoint. Do not use unrestricted X server access such as `xhost +`. Keep WSLg available to unrelated distributions: its global enablement is not a per-distro setting to change casually.

The field and brain remain attached to their existing owner and homes. Starting or rebuilding the desktop does not create a new mind or move the model into Linux.

### 9.2 One actuator connection and a separate viewer

The bridge owns the privileged desktop connection. It reconstructs the RFB framebuffer and routes bounded input. User viewing is a read-only projection of that stream by default, not another unrestricted VNC client carrying the actuator password.

A viewer's client-side “view only” switch is not enforcement. Input is denied at the trusted proxy/broker unless that viewer holds the current human-control lease. The browser never receives the backend actuator credential.

A trusted take-control operation fences Cassi's lease before viewer input is admitted. Releasing human control does not automatically restore an old action sequence. The viewer can close while the bridge, desktop, and mission continue.

Configure the VNC service to remain alive without a viewer and to avoid an unsolicited client disconnecting the owning bridge. Bind only to the intended local/private endpoint, authenticate, and keep transport credentials outside model context. A browser viewer must enforce authentication, origin checks, and CSRF-resistant control operations; a local web port is not itself an authority boundary.

Prefer an owner-restricted Unix socket between Xvnc and the Linux helper, with the raw RFB TCP listener disabled when supported. Only authenticated Surface transport crosses the guest boundary. If a TCP RFB path is necessary, require the declared protected transport and authentication without downgrade; a legacy VNC password is not transport encryption or a secure credential store. Disable both clipboard directions and primary-selection synchronization unless separately granted.

RFB updates are transport observations. Reconstruct complete valid regions before publication, preserve negotiated pixel format and resize semantics, and distinguish bridge receipt time from unknown source capture time. Standard input messages do not provide application-level acknowledgment. Reconnect requires framebuffer resynchronization and control-state reconciliation before new actions.

The bridge drives framebuffer-update interest independently of human viewers. RFB can aggregate changes and omit transient intermediate states even on a reliable connection; the publication declares sampled coverage, not a complete history of every render. Use a fresh full or requested-region reconstruction when a dependent action needs it. Request/response timing bounds freshness only where the backend semantics support that interpretation; otherwise the required timing capability is unavailable.

### 9.3 Accessibility and sound

AT-SPI is optional structured information from the same authorized application/session bus. It is not universally available and must not turn into access to unrelated sessions. Missing accessibility leaves the visual route available where adequate.

VNC is not a complete audio transport. Provision a dedicated PipeWire/PulseAudio route or equivalent supported session audio service for the desktop. Capture only authorized streams or the explicitly granted session mix; avoid silently reusing WSLg audio routing or mixing unrelated Windows sound. Microphone access, audio playback, and synthetic media input are distinct capabilities and effects.

### 9.4 WSL lifecycle

A Windows-side supervisor owns launch and recovery of the selected distribution and desktop session. Linux service management owns guest processes, but systemd services alone must not be relied on to keep WSL alive. Configure a supported lifetime policy and retain a supervised WSL session anchor where required by the installed version.

Startup is ready only after the expected environment incarnation, desktop source, valid initial view, helper health, and advertised channels are available. Viewer connectivity is not readiness. Report sensing readiness separately from input eligibility.

Never use a global WSL shutdown as the normal way to stop Cassi's desktop. Stop only the resources owned by this deployment. Windows sleep, reboot, user-session lifecycle, explicit distro termination, and network changes are first-class interruption cases. After resume, neutralize and reacquire before acting.

### 9.5 Resource and isolation boundaries

WSL CPU and RAM configuration can affect all WSL2 distributions. Do not overwrite unrelated settings or assume a global limit is a per-desktop quota. The supervisor and guest resource policy must account for the actual shared scope. GPU work competes with the field, brain, and Windows applications.

Verify the selected virtual desktop's graphics path. WSLg acceleration does not prove acceleration inside Xvnc; modern 3D applications, relative-pointer games, and controller-only applications require their actual supported capabilities and measured behavior. Ordinary software rendering is not reported as hardware acceleration.

Disable unnecessary Windows drive automounts, Windows process interoperability, shared clipboard, and credential sharing in the dedicated profile. Use explicit artifact exchange instead of exposing the entire Windows home or workspace. The agent account has no automatic administrative or package-installation authority.

An X11 display is a shared trust domain: applications on it may observe or affect each other. WSL is not made into a hardened sandbox by hiding its windows or disabling a mount. Work requiring enforceable separation runs in a deliberately restricted VM or equivalent adequate OS boundary, with no broad host shares or automatic credential forwarding.

## 10. Linux portal backend

For supported Wayland sessions, use the standard ScreenCast and RemoteDesktop portals with PipeWire. Negotiate actual interface versions, source kinds, cursor modes, device types, and persistence support. A requested capability is not a granted capability.

When combining capture and input, share the RemoteDesktop session with ScreenCast according to the portal lifecycle. Use EIS when supported and selected; do not mix EIS input with the alternative Notify input methods in that same active session. Where EIS is unavailable, use only supported standard input methods.

Bind streams using the identity information available in the negotiated version. PipeWire node IDs alone can be reused. Geometry, cursor metadata, scale, and source identity remain explicit rather than inferred from the first frame forever.

Portal authorization and restore tokens remain host-held. A restore token may be single-use, invalidated, or insufficient after a source change. Restart may require a fresh user interaction. Neither a remembered permission nor a token copied from an old checkpoint authorizes an unavailable session.

Portal session closure revokes dependent controls and invalidates streams. If the compositor does not supply a requested operation, report that capability boundary or choose another explicitly authorized environment. Do not bypass the portal with hidden privileged injection.

The portal profile connects to an available, consenting compositor session. It is not a promise of unattended startup, operation through a locked session, or an independently running headless desktop. Persistence for a combined capture/control session follows RemoteDesktop rather than a second conflicting ScreenCast persistence policy.

## 11. Cross-platform artifacts, clipboard, and credentials

A Windows path and a Linux path are not interchangeable identities. Transfer uses an identified artifact, content type, byte length, digest, provenance, privacy label, source scope, destination, and authorized recipient. Text transfers declare encoding and newline behavior; binary artifacts remain exact. Never silently normalize scientific data or source bytes while claiming an exact copy.

Copy into a scoped destination, verify the bytes, then publish the completed artifact. Resolve final filesystem objects under the allowed root; path-prefix checks alone do not handle symlinks, reparse points, case differences, or traversal. A crash leaves a named incomplete transfer rather than a fictitious finished file.

Cross-environment clipboard sharing is disabled by default. Explicit paste or clipboard transfer names the payload and destination. Human clipboard contents are not automatically read, retained, or forwarded. Text insertion must not silently switch to clipboard paste when that would expose private global state or change application semantics.

Credentials remain in protected host/OS facilities. Bind secret use to the intended target and current authority, with no plaintext in the field, screenshots retained as evidence, generic logs, or model requests. Redacted areas retain redaction/missingness labels; they are not represented as genuine blank application content. Source-derived knowledge and artifacts retain applicable privacy constraints when reused or shared.

Apply declared secret masks before field/model presentation and retained evidence for protected entry regions. Automated pixel redaction is not a guarantee of recognizing every secret in an arbitrary application: limit capture scope and use separated work environments rather than claim a universal visual data-loss-prevention system.

A cross-platform task selects environments by actual capability and authorization. It does not automatically log in elsewhere, copy a browser profile, install a dependency, or enlarge network access.

## 12. Authority, containment, and trusted interaction

The host issues unforgeable capability handles bound to identity, scope, operation classes, environment, expiry, generation, and use policy. The field can request or refer to a grant but cannot manufacture one. Provider-required safety checks receive explicit interactive approval and fail closed otherwise.

Already-authorized ordinary actions proceed without repetitive permission prompts. Consequential external effects, permission expansion, publication, purchases, private-data disclosure, destructive actions, and high-impact categories retain their applicable exact point-of-risk confirmation. Approval is bound to the actual target and values, not a vague description of a workflow.

A terminal keystroke or browser click can execute code or disclose data. Input transport does not downgrade those effects. UI labels and model confidence are insufficient to prove the effect class. When consequences cannot be resolved within the granted scope, retain the intention and request the missing authorization or information.

Screen text, application audio, manuals, demonstrations, web pages, model output, and tool results are untrusted content for authority purposes. They cannot impersonate the user, register a privileged backend, or authorize a new action. Trusted user messages arrive through the authenticated client/control channel. A screenshot of that client is still only screen content.

A selected window is an observation/input scope, not a filesystem or network sandbox. For unrestricted code authoring and execution, require a real contained execution environment with explicit filesystem, process, network, and credential policy. A Job Object, timeout, working-directory restriction, or WSL label alone is insufficient. Authoring code does not install it into the Surface runtime.

Treat guests and captured applications as untrusted protocol peers. Validate lengths, formats, encodings, tree bounds, decompression output, and references before allocation or execution. A guest connection's credential permits only its declared guest transport, never host administration. Strong separation from malicious applications requires an adequate OS trust boundary; same-user helpers cannot promise protection from an already-compromised host session.

## 13. Effect delivery and continuous control

### 13.1 Dispatch transaction

For each action or bounded control lease:

1. Resolve the proposed target, dependencies, capability requirements, authority, and resource allowance.
2. Reserve its identity and request digest durably before external delivery.
3. Acquire the relevant exclusive resources through the broker's compare-and-set/in-flight reservation.
4. At the final handoff, recheck source epoch, relevant geometry/target state, focus where required, authority generation, deadline, and revocation.
5. Dispatch once through the platform backend; record actual delivery information and uncertainty.
6. Admit source-bound observations and assess the predicted versus actual outcome through the owner.
7. Settle, wait, repair, or retain an explicit reconciliation obligation.

The owner does not hold its global mutation lock across capture, UI providers, model inference, or OS input. The broker's final dispatch fence closes the interval between owner reservation and physical delivery. A revocation before handoff prevents dispatch; after delivery begins, report the actual partial or unknown disposition.

### 13.2 Streams and watchdogs

A control lease has an environment incarnation, resource set, expiry, heartbeat, ordered sequence, permitted control envelope, and maximum duration. It cannot grow its own authority. A bounded durable lease reservation may cover high-rate updates; every update need not force a whole-field save. Crash recovery never resumes that old stream from a guessed sequence.

Reject duplicate, reordered, expired, or wrong-epoch control updates. An independent helper watchdog neutralizes broker-owned held keys, buttons, contacts, and controller axes on expiry or loss of the controlling connection. Physical/human input is not treated as broker-owned. If neutralization cannot be confirmed, expose the uncertainty and inhibit further control until recovery.

### 13.3 The three guarantees

- Cognitive result admission is idempotent under the owner.
- External delivery is an at-most-once attempt at the declared operation boundary unless the target explicitly supplies stronger idempotency.
- An uncertain physical outcome remains uncertain until reconciled.

Never promote these into an exactly-once claim about arbitrary GUI effects. Do not replay an entire partially inserted key sequence, paste, drag, submission, or purchase. A compensating action is a new real action with its own permission and evidence; it is not an automatic rollback.

## 14. Scheduling and resource ownership

Use the existing mission/program and programmable-swarm scheduling machinery. Separate the rate and priority of sensory publication, resident routine control, brain deliberation, source work, and maintenance. Preserve a responsive control/watchdog lane even when CPU, GPU, storage, or provider calls are saturated.

Resource claims include RAM, VRAM, capture buffers, transfers, retained evidence, disk publication space, CPU/GPU service, model context/output, process slots, and input domains. Measure actual occupancy and latency; avoid fixed assumptions about free memory or GPU compatibility. Reserve storage needed to record an effect before permitting it.

Many windows can be watched concurrently. One keyboard/pointer/focus domain has one controlling lease. Independent Windows and Linux input domains may act concurrently when the mission, host policy, field computation, and resources permit. Parallel reasoning does not imply two actors can safely share a pointer.

Apply fairness across programs and preserve their root accounting across child work, retries, waits, and restart. Resource exhaustion produces an inspectable wait with retained continuation, not a reset, hidden downgrade, or busy retry loop. Finite native work slices and bounded provider workers keep cancellation actionable.

## 15. Persistence and recovery

Four lifetimes remain separate:

| State | Treatment |
|---|---|
| Adaptive knowledge and unfinished responsibility | Canonical field and existing durable continuations |
| Exact source/artifact evidence | Immutable, privacy-scoped retention selected by the mission |
| External-effect and authority records | Durable host operational records independent of field rollback |
| Live buffers, OS handles, focus, portal sessions, held controls | Ephemeral state that must be reacquired or neutralized |

On restart, restore the existing field rather than a blank mind. Reopen the operational ledger, identify the environment incarnation, mark old sensory pages historical, reconcile in-flight effects, reacquire current sources, and request fresh control leases. Never restore saved held-input state as if the world had paused with the checkpoint.

A cloned/restored VM or WSL image receives a new environment incarnation. Keep the host effect ledger outside the disposable desktop image so guest rollback cannot erase delivery history. Host/field recovery must preserve or explicitly reconcile newer outside-world effects; restored images do not grant permission to replay them.

Viewer close, viewer disconnect, control release, source detach, mission pause, application close, desktop stop, and environment destruction are distinct operations. Detaching observation does not kill an application. Destructive environment reset or deletion is not a maintenance shortcut and requires its applicable authorization.

Preserve existing learned state, saved game experience, source evidence, application files, and unfinished work during integration. Migrate generic transport consumers when the new route is ready; do not run competing control loops against the same application.

## 16. Human collaboration and inspection

Extend the existing authenticated entity client/workspace with a Surface view. It shows the actual source, observation age, selected target, attention, current objective, proposed or active action, expected consequence, uncertainty, authority state, and resource wait. Explanations come from the current field-owned work and relevant summaries, not a separate narrative generator inventing a retrospective plan.

Modes are explicit: observing, assisting, delegated operation, human control, paused, and disconnected. Observation-only mode emits no application input. A delegated mission carries its existing scope; selecting the mode does not grant unlimited authority.

Provide trusted pause, emergency neutralization, take-control, resume, revoke, and detach operations. The emergency route does not depend on successful model reasoning. Normal Windows typing outside Cassi's independent Linux viewer is not a takeover of the Linux desktop; input deliberately directed into that viewer is.

Authorized demonstrations bind human actions to their actual surface and time. Avoid global keylogging or password recording. Cassi can ask a focused question about an ambiguous object, receive a point/region annotation, and update the plan without recreating the mission.

Keep explanatory overlays separate from captured application pixels. Sanitize application-derived labels in the client. Do not execute source markup or accept application-suggested control-channel instructions.

## 17. Representative complete workflows

### Research across Linux and Windows

A mission asks Cassi to examine an authorized dataset and produce a report using available applications. She reads instructions, inspects the data, chooses suitable tools in her Linux desktop, and creates a chart. If a Windows-only application is required, she requests or uses the existing scoped Windows binding, transfers an identified artifact through the permitted route, and continues the same responsibility. She verifies the saved result, retains its evidence, and reports completion. Publishing or sending it remains a separate authorized effect.

No step requires a new charting-app adapter. A missing account, unsupported file format, ambiguous instruction, or unavailable capability becomes a specific unresolved dependency rather than invented success.

### Continuous game interaction

A permitted game exposes only the channels allowed by the mission. Cassi's sensory region tracks current observations and relevant recent motion. Acquired routines perform bounded movement while the brain handles unfamiliar situations. A stalled expectation changes the plan; animation alone does not count as progress. Loss of frames or control timing neutralizes the affected inputs. Learned experience survives a game process restart, while the new game instance receives fresh bindings.

No hidden game state is supplied under a pixel-only profile. GPU performance and device support belong to the actual environment capability reading, not the game's name.

### Interruption and continuation

You take control during an application interaction. The broker fences Cassi's input and neutralizes her held controls before accepting your viewer actions. She observes the changed situation within the authorized scope, retains her unfinished goal, and resumes only after explicit release and fresh validation. Closing the viewer leaves the independently supervised desktop running. A later host restart recovers the mission and reconciles any unresolved effects before new input.

## 18. Integration ownership and complete build

The following source locations identify existing owners to extend, not a claim that the new behavior already exists.

| Existing owner | Surface responsibility |
|---|---|
| `CassiFI/cassi_field_owner.py` | Admit sourced observations and typed intentions; preserve one canonical publisher, current dependencies, effect outcomes, and continuing obligations |
| `CassiFI/cassi_field_input.py` | Extend fixed source codecs/views with live publication, timing, geometry, missingness, and bounded regional access |
| `CassiFI/cassi_field_regions.py`, `CassiFI/cassi_field_atlas.py`, `CassiFI/cassi_field_residency.py` | Directly addressable sensory pages, reference lifetime, resource accounting, bounded access and publication |
| `CassiFI/cassi_field_cognition.py`, `CassiFI/cassi_field_program.py` | Shared perception, identities, attention, acquired procedures, predictions, plan repair, and outcome-sensitive learning |
| `CassiFI/cassi_programmable_swarm.py` | Resident procedures, independent work, joins, deadlines, continuation and shared scheduling |
| `CassiFI/programs/model/qwen_executor.py` and the existing brain adapter | Actual identified visual/temporal input and bounded brain work; no pretend sight through token-only input |
| `CassiQwen/cassi_autonomous_researcher.py` | Mission wakeups, resource/lifecycle integration and existing work-order handling without an additional desktop planner |
| `CassiQwen/cassi_field_brain_entity.py`, `CassiQwen/cassi_field_brain_server.py` | Authenticated binding, inspection, guidance, control, artifact and event projections through the existing entity |
| `CassiQwen/surface/mission_authority.py`, `CassiQwen/surface/linux_audio.py` | Host-owned mission approval with repeat bounded leases and independently checked guest audio helper bytes |
| `CassiQwen/dsh-cassi-entity/work-order-broker.js` | Preserve host approval, dispatch identity and unknown-effect semantics where Harness execution is used |
| `CassiQwen/games/` | Migrate shared interaction responsibilities without erasing game experience, source attribution, or retained scenarios |

Proposed new source ownership is one `CassiQwen/surface/` package for the shared transport schemas, environment registry, effect-broker integration, platform bindings, and viewer projection; a native Windows helper; and a Linux session helper beside the provisioned desktop. These names describe proposed implementation locations. Helpers do not contain acquired policies, duplicate entity homes, or application-specific skill libraries.

The live input path must remain bounded through the actual consumer: decoding, region lookup, perception inputs, hashing, validation, publication, and retention. Paging a file while materializing the entire field at every sensory update does not satisfy the design. Existing regional and residency work is reused and extended where needed rather than replaced by a second storage system.

The complete build comprises the shared records and ownership rules; actual visual input; Windows, Linux virtual-desktop, and Linux portal backends; session supervision; authority and effect recovery; field-owned continuous procedures; privacy-scoped transfer and audio; resource scheduling; and human observation/takeover. These responsibilities are developed together against the same interfaces. A screenshot-only client, hand-coded game player, unmediated remote-control tool, or capture stream without cognition and recovery is not the delivered system.

Environment provisioning is an explicit operational action after implementation. Installing WSL features, distributions, packages, virtual devices, VM images, or changing host permissions remains outside an ordinary task's ability to authorize itself.

## 19. Direct operational completion

Exercise actual changed paths with the existing learned entity and authorized applications. These are ordinary operational acceptance cases, not a new learning-proof campaign or a frozen scientific protocol. Unsupported deployment capabilities must be reported accurately; a backend that merely returns unsupported for its mandatory supported-environment paths is not complete.

| Case | Required observable result |
|---|---|
| Unfamiliar pixel-only GUI | Useful interaction through the same sensing/control path, with no application adapter |
| Accessible GUI | Sourced structural data and supported actions agree with observed application consequences; stale/ambiguous references do not cause blind input |
| Instruction or demonstration | A parameterized field-owned procedure and its applicability can be used in the actual task without adding host code |
| Cross-application task | Goal, data identity, dependencies, and saved result survive application changes |
| Windows/Linux handoff | Explicit artifact transfer and scope checks; no automatic drive, clipboard, credential, or authority sharing |
| Viewer closes | Dedicated Linux desktop and authorized mission continue; no dependency on the watching browser |
| Human takes control | Queued conflicting input is fenced, owned controls are neutralized, and no stale automatic resume occurs |
| Window moves, resizes, changes DPI, or opens a modal | Target-local revalidation prevents stale coordinates and wrong-focus typing |
| Unrelated animation during deliberation | Relevant actions remain eligible; global frame/root equality does not starve control |
| Capture loss, protected source, minimized source, or locked session | Explicit stale/unavailable state; no false fresh observation or uncontrolled continued gesture |
| RFB reconnect or missing delta | Full valid reconstruction before dependent control; no corrupted baseline accepted |
| Portal revocation or expired restore token | Control stops; session is reacquired with the required actual consent |
| Missing accessibility or audio | Capability is explicit; no fabricated structure, silent unrelated audio capture, or false full-modality claim |
| Partial input delivery or crash after dispatch | Unknown/partial outcome retained and reconciled; the whole action is not automatically replayed |
| Duplicate operation or changed payload under the same ID | Exact replay of settled outcome or pre-dispatch conflict, never a second effect |
| Revocation between reservation and dispatch | Final host fence prevents delivery; post-start uncertainty is reported accurately |
| Brain, UI provider, or renderer stalls | Pause/watchdog remains responsive and bounded controls expire |
| Two tasks share a pointer | Exclusive ownership serializes effects; independent input domains remain separately usable |
| CPU/GPU/RAM/storage pressure | Accounted resource wait, retained continuation, and neutralization when timing can no longer be met |
| WSL/host sleep, termination, or restart | Existing mind preserved; current environment reacquired; effect history reconciled before action |
| Guest image restore or clone | New incarnation and no replay of old authority or streams; host effect history survives |
| Secret or prompt-injection content | No authority expansion, unauthorized disclosure, or credential retention in ordinary memory/logs |
| Task outcome contradicts expected progress | Procedure repairs or asks appropriately; successful input delivery does not declare the mission complete |
| Field-native virtual surface | Same source/action/evidence semantics without implying arbitrary Windows binary emulation |

Record what the exercised application actually did, relevant errors and timing, and any deployment limitation. Keep focused regressions where a plausible defect would violate these behaviors. Do not substitute screenshots of a dashboard, mocked key delivery, or source-text assertions for the real application path.

## 20. Primary platform references

The deployed versions must be inspected for their actual capabilities; these sources explain the architectural boundaries.

- [Windows Graphics Capture](https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture): capture support, selection, frame resources, and source behavior.
- [Windows SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput): input insertion counts, existing keyboard state, and privilege restrictions.
- [Windows interactive services](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services): Session 0 isolation, per-user helpers, and access-controlled IPC.
- [WSL GUI applications](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps): WSLg application integration and its distinction from a full desktop.
- [WSL service lifecycle](https://learn.microsoft.com/en-us/windows/wsl/systemd): systemd support and the fact that its services alone do not keep the instance alive.
- [WSL configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config): mount/interop defaults, global versus distribution settings, resource and lifecycle controls.
- [TigerVNC Xvnc](https://tigervnc.org/doc/Xvnc.html): virtual display, input/clipboard options, connections, lifetime and rendering capabilities.
- [TigerVNC session management](https://tigervnc.org/doc/vncsession.html): desktop user-session and service lifecycle.
- [RFB protocol, RFC 6143](https://www.rfc-editor.org/rfc/rfc6143): demand-driven rectangle updates, sampled intermediate states, reconnection, and input-message semantics.
- [ScreenCast portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html): source selection, PipeWire streams, cursor modes, and persistence.
- [RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html): granted devices, combined capture/control lifecycle, EIS, and restore tokens.

The architectural result is one continuing Cassi with several work environments. New applications extend her experience and acquired methods; they do not require a new computer-use system.
