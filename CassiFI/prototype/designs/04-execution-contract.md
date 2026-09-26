# Complete field execution contract

> CassiFI implementation plan, Part 4. [Previous](./03-architecture-profiles-and-schemas.md) · [Index](../README.md) · [Next](./05-boundaries-body-and-action.md)

## Complete field execution contract

### Coordinate reconstruction and write discipline

The two complex field coordinates are derived from the existing Yang/Yin planes:

\[
D=E_Y-\phi E_I,
\qquad
C=\frac{\phi E_Y+E_I}{1+\phi^2}.
\]

The inverse is exact:

\[
E_Y=\frac{D}{1+\phi^2}+\phi C,
\qquad
E_I=-\frac{\phi D}{1+\phi^2}+C.
\]

The transform is not orthonormal under the unweighted `D,C` coordinates.
Define its exact induced metric weights:

\[
w_D=\frac{1}{1+\phi^2},
\qquad
w_C=1+\phi^2.
\]

At scale `s`, the active field-coordinate metric is

\[
G_s=\operatorname{diag}(w_DW_s,w_CW_s),
\qquad
W_s=\operatorname{diag}(dx_sdy_s)>0.
\]

Every total density, inner product, norm, force power, flux, boundary adjoint,
and work receipt uses these weights:

\[
|E_Y|^2+|E_I|^2=w_D|D|^2+w_C|C|^2,
\]

\[
|V_Y|^2+|V_I|^2=w_D|V_D|^2+w_C|V_C|^2.
\]

`e_D + e_C` is never treated as physical Yang/Yin energy unless `e_D` and
`e_C` already include `w_D` and `w_C`, respectively, together with the
declared coupling/link terms. This convention is frozen in the profile and
shared by the controller, boundaries, receipts, checkpoints, and independent
verifier.

The identical equations hold for `V_D` and `V_C`. The core exposes one internal
write primitive for position and one for velocity:

\[
\Delta E_Y=\frac{\Delta D}{1+\phi^2}+\phi\Delta C,
\qquad
\Delta E_I=-\frac{\phi\Delta D}{1+\phi^2}+\Delta C.
\]

Every Yang/Yin position or velocity mutation, including source drive,
correction, scale coupling, remap, and conversion reconstruction, passes
through these two coordinate-write/accounting primitives. The scalar
`epsilon2_ema` plane mutates only through separate
`remap_epsilon2_ema()` and `update_epsilon2_ema()` primitives, which enforce
nonnegativity/inactive-tail invariants and emit old/new value, weighted-mass,
minimum, and operator receipts. No boundary module receives a writable tensor
view.

The existing `_apply_differential_delta()` becomes an internal special case with
`Delta C=0`; no public caller may write only `D` without a step ledger. The
linear `_mode_profile`, unused `velocity_weight`, top-symbol binding path,
consensus-one-on-no-pair fallback, and direct public snapshot-correction path
are removed from the live flow implementation. Historical code that requires
those semantics is isolated as described above rather than left as a hidden
compatibility route.

### Fixed spatial operators

For every production profile, the active sheet is the complete
\([N_{y,s},N_{x,s}]\) rectangle and
`spatial_operator_family="periodic-fft2.v1"`. The profile's \(F_s\) and
\(F_s^{-1}\) are the unitary DFT pair defined in Part 1, with x-fastest,
y-major storage, signed frequency indices, and physical extents
\(L_{x,s}=N_{x,s}dx_s\) and \(L_{y,s}=N_{y,s}dy_s\). Thus the execution
domain is the torus
\(\mathbb T_s=(\mathbb R/L_{x,s}\mathbb Z)\times
(\mathbb R/L_{y,s}\mathbb Z)\), and all active \(Z_s,V_{Z,s}\) are periodic
in both axes. There is no profile-selected hole, implicit wall, or
finite-aperture boundary in this release operator.

For DFT index \((q,p)\), with \(p\) the x index and \(q\) the y index, the
profile's physical wave numbers are
\[
k_{x,s}(p):=\frac{2\pi}{L_{x,s}}\operatorname{fftindex}_{N_{x,s}}(p),
\qquad
k_{y,s}(q):=\frac{2\pi}{L_{y,s}}\operatorname{fftindex}_{N_{y,s}}(q),
\qquad
|k_s|^2:=k_{x,s}(p)^2+k_{y,s}(q)^2,
\]
where `fftindex` and the even-grid signed Nyquist convention are the Part 1
profile definition. The release spectral symbols are exactly
\[
\begin{aligned}
\widehat{\partial_{x,s}Z}_{q,p}&=i\,k_{x,s}(p)\widehat Z_{q,p},&
\widehat{\partial_{y,s}Z}_{q,p}&=i\,k_{y,s}(q)\widehat Z_{q,p},\\
\widehat{\nabla_s f}_{q,p}
&=(i\,k_{x,s}(p)\widehat f_{q,p},
i\,k_{y,s}(q)\widehat f_{q,p}),&
\widehat{\nabla_s\!\cdot J}_{q,p}
&=i(k_{x,s}(p)\widehat J_{x;q,p}
+k_{y,s}(q)\widehat J_{y;q,p}),\\
\widehat{\nabla_s^2 Z}_{q,p}&=-|k_s|^2\widehat Z_{q,p},
\qquad
\nabla_s^2=\nabla_s\!\cdot\nabla_s.
\end{aligned}
\]
The signed Nyquist value applies literally to the complex \(Z=D+iC\) and
complex current components; no unregistered per-component Hermitian,
finite-difference, or zero-Nyquist substitute is permitted. With the
declared positive sheet metric,
\(\langle\nabla_s f,J\rangle_{W_s}
=-\langle f,\nabla_s\!\cdot J\rangle_{W_s}\).
No nonspatial or inactive mode participates in a spatial-current receipt. A
receipt reports those modes separately as inactive/nonspatial; it never maps
them opportunistically to pixels. Every gradient, current, flux, Hodge,
force/work, remap, and linear propagator uses these wrapped periodic symbols,
their metric adjoint, and their declared normalization.

The periodic family is not a generic FFT instruction. A future nonperiodic
operator must use a new `spatial_operator_family` and new
profile/operator/state identities, with independently declared domain,
boundary traces, transform/basis normalization, derivative/Laplacian,
positive metric and adjoints, force/energy/current/flux and boundary-work
identities, remap, and resolution/refinement proof. Its flux and boundary
closure cannot cite the periodic torus identities, and this execution path
cannot select it.

The constant linear spectral symbol for coordinate `Z` at scale `s` is
\[
L_{Z,s}(k):=\omega_{Z,s}^2+c_{Z,s}^2|k|^2.
\]
The implementation uses the analytic per-mode matrix exponential for the
constant damped oscillator with
\(\Omega_{Z,s}^2(k)=L_{Z,s}(k)\). The profile pins the underdamped,
critically damped, and overdamped branches, the small-argument series used
near branch boundaries, dtype promotion, and exact normalization/reduction
order. Damping is included in this matrix exponential exactly once. The
propagator is split symmetrically from local nonlinear, composition,
coupling, conversion, and boundary terms. A uniform finite-difference
stencil cannot appear under this FFT coordinate declaration.

The spatially varying composition coupling is the metric-gradient pair
`F_D^composition,F_C^composition` derived from
`u_s^composition` above. The implementation evaluates `epsilon`, `f`, `f'`,
both Wirtinger derivatives, and both forces on the same frozen physical-grid
split-stage state. It never treats the coefficient as diagonal in Fourier
space and never applies a one-way `C` force without its reciprocal `D` force
and potential ledger.

For reference and validation, the complete velocity-form law is

\[
\dot Z_s=V_Z,
\]

\[
\dot V_Z=
c_{Z,s}^2\nabla^2Z_s
-\omega_{Z,s}^2Z_s
-\gamma_{Z,s}V_Z
+F_{Z,s}^{\mathrm{local}}
+F_{Z,s}^{\mathrm{composition}}
+F_{Z,s}^{\mathrm{link}}
+F_{Z,s}^{\mathrm{retention}}
+F_{Z,s}^{\mathrm{boundary}}
+F_{Z,s}^{\mathrm{residual}}.
\]

The local nonlinear force is the declared `-kappa_Z|Z|^2Z` term. Yang/Yin
conversion is an explicit finite position map in the centered split stage, not
an acceleration term in this ODE. Each named force and finite map has a
separate work row; none is a learned activation or static feature transform.

Nonlinear and composition terms use one versioned projected-pseudospectral
operator. For integer oversampling factors
\(\sigma_{x,s},\sigma_{y,s}\geq1\), define
\[
N_{x,s}^{+}:=\sigma_{x,s}N_{x,s},\qquad
N_{y,s}^{+}:=\sigma_{y,s}N_{y,s},\qquad
N_s^{+}:=N_{x,s}^{+}N_{y,s}^{+},
\]
\[
dx_s^{+}:=\frac{L_{x,s}}{N_{x,s}^{+}},
\qquad
dy_s^{+}:=\frac{L_{y,s}}{N_{y,s}^{+}}.
\]
Let \(F_s^{+}\) be the unitary periodic DFT on this oversampled rectangle,
and let \(J_s\) be the fixed Fourier-coefficient injection from the base
DFT array into the oversampled array, preserving the declared signed
frequencies and zeroing every other coefficient. The physical interpolation
and its normalization are
\[
\alpha_s:=\sqrt{\frac{N_s^{+}}{N_s}},
\qquad
I_s:=(F_s^{+})^{-1}\alpha_sJ_sF_s.
\]
For
\[
W_s:=dx_sdy_s\,I_{N_s},\qquad
W_s^{+}:=dx_s^{+}dy_s^{+}\,I_{N_s^{+}},
\qquad
\langle u,v\rangle_W:=u^HWv,
\]
the exact metric adjoint restriction is
\[
R_s:=W_s^{-1}I_s^HW_s^{+},\qquad
I_s^HW_s^{+}I_s=W_s,\qquad
R_sI_s=I_{N_s},
\]
and \(\Pi_s^{+}:=I_sR_s\) obeys
\[
(\Pi_s^{+})^2=\Pi_s^{+},
\qquad
(\Pi_s^{+})^HW_s^{+}=W_s^{+}\Pi_s^{+}.
\]
Here \(I_n\) is the \(n\)-dimensional identity and \(H\) is conjugate
transpose. If \(U_s^{+}\) is the oversampled potential, its base-grid
restriction and gradient are required to satisfy
\[
U_s(z):=U_s^{+}(I_sz),\qquad
\nabla_{W_s}U_s(z)
:=R_s\nabla_{W_s^{+}}U_s^{+}(I_sz),
\]
where \(\nabla_W\) is defined by
\(dU[\delta z]=\operatorname{Re}\langle\nabla_WU,\delta z\rangle_W\).
Products, any declared spectral filter, and the potential quadrature are
therefore evaluated on the oversampled physical grid with \(W_s^{+}\), then
returned through \(R_s\) and no other slice or decimator. The padding map,
Nyquist handling, filter and its adjoint, both metrics, and the factors
\(\alpha_s\) are operator identity. Resolution doubling holds
\(L_{x,s},L_{y,s}\) and physical time fixed while changing these declared
operators; collocation aliasing or a metric mismatch cannot be hidden in a
work residual.

### Profile preflight and fail-closed admissibility

`QiFieldController.advance()` admits a candidate only after the immutable
profile and its prerequisite receipts have been checked. The preflight is
causal state validation, not a diagnostic advisory:

- `QI-SCALE-001` requires exactly one frozen `scale_geometry_mode` and a
  matching `QiScaleGeometryComparisonReceipt` for
  `temporal-full-rank` or `spatiotemporal-pyramid`. The selected ranks,
  nullspaces, active/padded byte budgets, and operator hashes must match the
  candidate; a runtime workload cannot select another mode or conceal rank
  loss.
- `QI-RET-001` requires the W4R topological-retention Hamiltonian/topology core to be
  installed after W4 and before W5. Its `U_topo`, torus-sector guards, and
  conservative force are available to this controller, while W10R
  behavioral retention/consolidation remains a later trajectory-level claim.
- `QI-CONV-001` requires a current `QiConversionViabilityReceipt` proving that
  the frozen-`Q` map has a forward-viable domain. The profile stores physical
  `epsilon_memory_time`; the controller derives the per-step EMA coefficient
  from the actual `h` and never accepts a caller-supplied coefficient.
- `QI-BOUND-001` requires a valid `QiBoundaryPermeabilityProfile` for every
  admitted sensory source. Its field-derived passive admission/reflection
  split and work interval are checked before any source kick.
- `QI-PORT-001` requires a `QiScatteringReceipt` for each participating
  scale-link and external port, with incident, reflected, transmitted, and
  absorbed work intervals closed before commit.
- `QI-NUM-001` requires a profile-matching `QiNumericalCertificate` and its
  cheap online guard parameters. A missing, stale, or independently
  unreproducible certificate rejects the candidate; finite output alone is
  never admissibility evidence.

The preflight checks profile/state/operator/receipt hashes, units, active
tails, topology endpoint domain, work budgets, and exact rational clock
frontiers. It performs no state mutation. Any failed predicate returns the
predecessor identity with a failure receipt and no candidate that downstream
stages can commit. No fading-retention, alternate conversion, rank-normalizing,
permeability-off, scattering-omitting, clipping, or numerical fallback is
reachable from this path.
The requested `h` is validated as one exact rational member of the frozen
\(\mathcal H_{\mathrm{runtime}}=[h_{\min},h_{\max}]\cap\mathbb Q\), where
\(0<h_{\min}\leq h_{\max}\) are profile identities, with
\(t_{n+1}=t_n+h\). Wall-clock duration, floating-point rounding, a
below-minimum subdivision, and a scale-local rescaling cannot alter that
frontier. All per-scale frequencies, damping times, conversion memory time,
source exposures, and declared horizons are interpreted in this same physical
time. A certificate subdivision uses positive exact rational durations whose
sum is the accepted parent interval, but is evidence only and never an
additional `advance()` or conversion call; a zero-clock map is not one of
those subdivisions.


### One causal time step

`QiFieldController.advance()` is the only live field evolution entry point. It
accepts an immutable drive bundle constructed by `cassi_qi_flow.py` and returns
a `QiFlowStep` containing a candidate state, a complete ledger, diagnostics,
outgoing boundary prediction, and no external side effect.

For the validated exact rational physical interval
\(h\in\mathcal H_{\mathrm{runtime}}\), with \(t_{n+1}=t_n+h\), the frozen
split order is:

1. run the no-mutation profile preflight above; validate the current state and
   complete immutable drive bundle, then derive `D`, `C`, `V_D`, `V_C`,
   pre-state energy, and hashes;
2. apply exactly one previously committed `QiAppliedEfference` affine
   body-frame relabel to every active position/velocity sheet and the positive
   scalar EMA remap;
3. evaluate `QiBoundaryPermeabilityProfile` for every timed source, split its
   incident work into admitted/reflected/absorbed terms, and create the
   scale/external-port `QiScatteringReceipt` before any source mutation;
4. apply half of each admitted timed ingress and residual-return force as
   separately ledgered bounded velocity kicks;
5. evaluate and apply half of the conservative cross-scale, local nonlinear,
   reciprocal composition, and W4R topological-retention retention-core forces in frozen
   descriptor order;
6. apply the first exact half interval of the constant-coefficient spectral
   propagation/damping operator;
7. after rechecking the `QiConversionViabilityReceipt`, apply the centered
   exact Yang/Yin position-density conversion map once over the full interval
   `h` with frozen `Q`; do not update `epsilon2_ema` yet;
8. apply the second exact spectral propagation/damping half interval, then
   reevaluate the post-conversion local/link/composition/retention forces and
   apply their second halves, followed by the external-force second halves, in
   the exact reverse registered order;
9. reconstruct packed Yang/Yin coordinates and update `epsilon2_ema` exactly
   once from the complete-step imbalance using the derived
   `1-exp(-h/epsilon_memory_time)` coefficient;
10. compute pre-bound diagnostics, currents, fluxes, every work/scattering row,
    and normalized closure from the untouched candidate; enforce online
    `QiNumericalCertificate` guards and all profile identities. On any failure
    return the predecessor hash plus a failure candidate with no committable
    state; otherwise return the candidate state and complete ledger.

`transition_kind=port_reaction` and `retention_reset` are the only
non-time-advancing controller variants. Each validates the predecessor and
declared finite map, computes the complete pre/post Hamiltonian and component
ledger, checks endpoint bounds, emits the applicable `QiScatteringReceipt` or
retention-topology proof, and produces one successor hash. They skip
propagation, conversion, and EMA integration because no logical time elapses;
the physical `epsilon_memory_time` is never converted into a fictitious
zero-clock update. `retention_reset` additionally requires the explicit
authenticated authorization and expected session head defined in Part 2.
No boundary, text, action, or retention module may mutate the tensor outside
these controller transitions.

Timed sensory packets are divided at their declared exposure boundaries. If
multiple modalities share a timestamp, their fixed descriptor priority and
phase alignment are part of `QiFlowProfile`; no incidental Python dictionary
order affects the field.

The ordering is runtime operator identity, not an optimization detail. Changing
it changes the operator fingerprint, makes incompatible checkpoints unloadable,
and reruns the affected engineering validation.

### Stability and bound policy

The profile validator emits a machine-checkable `QiStabilityEnvelope`; prose
about a "small enough" step is not an admissibility proof. Let `G` be the
block-diagonal metric induced by `w_D`, `w_C`, the scale quadratures, and the
declared sheet quadrature. On the profile's closed admitted-state domain
`\mathcal A`, all retained kick-drift terms below are included in the
profile-bound certificate.

### `QiNumericalCertificate` provenance and use

`QI-NUM-001`'s canonical schema and evidence object are owned by Part 9; this
execution section assigns the three roles to numerical evidence. W3N/G3N
produces a profile-bound `QiNumericalCertificate` offline using the declared
high-precision arithmetic and interval/enclosure procedures. It derives the
curvature, spectral-branch, nonlinear projection, topology phase/barrier,
conversion-work, permeability/scattering, intermediate-amplification, and
decision-margin bounds from the exact profile domain. The certificate stores
the source/profile/operator hashes, precision and enclosure method, formula
versions, domain caps, interval endpoints, reduction order, toolchain
identity, and independent derivation receipt. A decimal safety factor or a
runtime-generated bound is not a certificate.

During `advance()`, cheap online guards use only the certificate's frozen
limits and the candidate's exact stage scalars: finiteness, denominator and
amplitude floors, inactive tails, interval radii, work caps, topology/branch
predicates, and decision margins. Online guards may reject a candidate, but
they may not widen an interval, replace an enclosure with a point estimate,
recompute a missing bound heuristically, or mutate the certificate. The
expensive offline derivation therefore cannot be confused with a per-step
diagnostic, and a finite state cannot substitute for a passed bound.

An independent replay, using the verifier's separate arithmetic and the
frozen profile/operator identity, recomputes the certificate inputs and
selected full trajectories from raw receipts. It checks the online decisions,
stage order, work closure, and predecessor/successor hashes without trusting
the controller's self-report. Any profile/precision/toolchain drift, failed
replay, stale hash, or disagreement between offline enclosure and online
guard fails closed before a state or receipt head can be committed. The
certificate is immutable profile evidence, never persistent adaptive state.
Certificate evolution is append-only. A changed or newly completed bound is
an immutable parent-linked
`cassi.qi-flow-certificate-extension.v1` record naming the parent certificate
hash, owning law/package/gate, consumed semantic subhashes, arithmetic and
toolchain identity, and completed section hash. No extension mutates or
silently replaces its parent. The final certificate names the complete
ordered section inventory, including every required spatial, oversampling,
topology, conversion, work, and decision section; an implicit, omitted, or
placeholder section is not final evidence.



\[
U_{\mathrm{nonlinear}}
=
\sum_s\mathbf 1^\mathsf T W_s
\left(
\frac{w_D\kappa_{D,s}}{4}|D_s|^4
+\frac{w_C\kappa_{C,s}}{4}|C_s|^4
\right),
\]

\[
U_{\mathrm{composition}}
=\sum_s\mathbf 1^\mathsf T W_s u_s^{\mathrm{composition}},
\qquad
U_{\mathrm{KD}}
=
U_{\mathrm{nonlinear}}
+U_{\mathrm{composition}}
+E_{\mathrm{links}}
+\mathbf 1_{\{\mathrm{retention.mode}=\mathrm{topological\text{-}v1}\}}U_{\mathrm{topo}} .
\]

Let `x` be the real vector formed in canonical
`(Re D,Im D,Re C,Im C)` packed/scale order, restricted to active sites, and let
`G_R` repeat the induced complex metric on those real components. The
executable curvature certificate is

\[
\Omega_{\mathrm{KD,max}}^2
:=
\sup_{x\in\mathcal A}
\left\|
G_R^{-1/2}\nabla_x^2 U_{\mathrm{KD}}(x)G_R^{-1/2}
\right\|_2 .
\]

`\mathcal A` is the exact closed amplitude/composition/topology endpoint domain
listed in the profile, including every coordinate cap
\(|Z_{s;m}|\le R_{Z,s}\). A `timed_phase_slip` additionally carries a separate
refinement-converged transient-domain/barrier certificate; its interior core
crossing is not silently folded into the endpoint Hessian bound.

The certificate is assembled from explicit, independently recomputable terms:
the quartic bound
\[
\max_{Z,s}3\kappa_{Z,s}R_{Z,s}^2,
\]
the full reciprocal composition-potential Hessian on the declared
`rho/epsilon_ref` domain, the spectral radius of every metric-weighted
scale-link block, and the topological-retention `U_topo` Hessian bound from `r_core`,
`lambda_ph`, `lambda_core`, `W`, and `V_star`. The same receipt records

\[
\Omega_{\mathrm{lin,max}}^2
:=
\max_{Z,s,k}\left(\omega_{Z,s}^2+c_{Z,s}^2|k|^2\right),
\]

even though the constant linear spectral stage is integrated analytically and
therefore does not consume a kick-drift stability allowance. Boundary,
residual, remap, and port-reaction stages contribute their exact induced norms,
admitted-work ceilings, and intermediate-state amplification bounds rather
than being misrepresented as conservative Hessians.

For the retained damped kick-drift composition, the profile-derived quantities
\[
\gamma_{\max}:=\max_{Z,s}\gamma_{Z,s},
\qquad
a_{\min}(h):=\exp(-\gamma_{\max}h)
\]
give the recorded scalar reference condition
\[
h^2\Omega_{\mathrm{KD,max}}^2
\le
(1-\sigma_{\mathrm{stab}})\,2(1+a_{\min}(h)),
\qquad 0<\sigma_{\mathrm{stab}}<1.
\]

This is one necessary component of the executable envelope, not a
complete-system theorem. `QiStabilityEnvelope` also lists every bound term,
the admitted domain and caps used to derive it, exact spectral branch/error
bounds, nonlinear projection error, source-work accumulation, remap gain,
candidate-branch maxima, each intermediate split-stage maximum, the evaluated
left and right sides above, and the resulting margin. The independent verifier
recomputes the certificate from the frozen profile; an unexplained empirical
safety multiplier is forbidden.

The production profile is admissible only when the analytic certificate
passes, a refinement fixture agrees with its bounds, and the declared
long-horizon regression stays finite without hidden saturation. Changing a
force, potential, active-mode mask, stage order, dtype, or capacity invalidates
the envelope and forces regeneration before execution.

The canonical path removes silent component clipping and global mean-energy
rescaling as stabilization devices. On any cap crossing it retains the prior
committed state, emits `cassi.qi-flow-failure.v1`, and records candidate
pre-bound energy, overflowing sites, requested source work, stability-envelope
identity, and rejected receipt identities. A separately named stress profile
may drive a candidate past the bound and verify rejection, but no
clipped/saturated field can support a release-flow capability.

### Spatial phase, energy, and continuity

For `Z` equal to `D` or `C`, use its metric weight `w_Z`:

\[
q_Z=w_Z\operatorname{Im}(Z^*V_Z),
\qquad
\mathbf J_Z=-w_Zc_Z^2\operatorname{Im}(Z^*\nabla Z),
\]

\[
e_Z=
w_Z\left[
\frac12|V_Z|^2
+\frac{c_Z^2}{2}|\nabla Z|^2
+\frac{\omega_Z^2}{2}|Z|^2
+\frac{\kappa_Z}{4}|Z|^4
\right],
\]

\[
\mathbf P_Z=-w_Zc_Z^2\operatorname{Re}(V_Z^*\nabla Z).
\]

The reciprocal composition potential at a frozen stage is

\[
u_s^{\mathrm{composition}}
:=
\frac{w_C\omega_{C,s}^2\beta_s}{2}
\tanh\!\left(\frac{\epsilon_s}{\epsilon_{\mathrm{ref},s}}\right)|C_s|^2.
\]

Lowercase per-coordinate rows are signed, per-time diagnostic subledger terms;
they are never added a second time as global external work. For every
non-transport stage `j` of positive duration, define the exact stage-difference
phase source

\[
r_Z^{(j)}
:=
\frac{q_Z(Z_j^+,V_{Z,j}^+)-q_Z(Z_j^-,V_{Z,j}^-)}{h}.
\]

For a positive-duration `advance()` with parent interval \(h>0\), the
denominator is that complete physical interval. Two half-kicks owned by the
same cause are accumulated into its one row. A zero-clock finite map has no
per-time \(r_Z^{(j)}\) row and is represented by its endpoint phase-charge
impulse in the transition receipt; it is never divided by \(h=0\) or by a
fictional duration. Remap, conversion, and port reaction use exact
finite-map endpoints; boundary, residual, composition, link, and retention
rows use their actual before/after stage values. A fixed attribution rule
makes composition-force work telescope with `Delta U_composition`, link-force
work telescope with `Delta E_links`, and retention-force work telescope with
`Delta U_topo`. A potential change caused by conversion belongs only to
`W_conversion`.

Damping is not represented as a kick. For the two analytic spectral
half-stages `j` of duration `delta_j`, define the signed local step-average rows

\[
\bar r_Z^{\mathrm{damp}}(x)
:=
-\frac1h\sum_j\int_0^{\delta_j}
\gamma_{Z,s}q_Z(x,t)\,dt,
\]

\[
\bar w_Z^{\mathrm{damp}}(x)
:=
-\frac1h\sum_j\int_0^{\delta_j}
w_Z\gamma_{Z,s}|V_Z(x,t)|^2\,dt
\leq0.
\]

The exact modal propagator and its fixed inverse transform own both
quadratures. The total positive dissipation and signed global damping work are

\[
Q_{\mathrm{damping}}
:=-h\sum_{Z,s}
\left\langle\mathbf1,\bar w_{Z,s}^{\mathrm{damp}}\right\rangle_{W_s}
\geq0,
\qquad
W_{\mathrm{damping}}=-Q_{\mathrm{damping}}\leq0.
\]

With `\overline{\nabla\cdot J_Z}` denoting the same stage-integrated spectral
transport divided by `h`, the executable phase-charge continuity identity is

\[
\frac{q_Z^{n+1}-q_Z^n}{h}
+\overline{\nabla\cdot\mathbf J_Z}
:=
r_Z^{\mathrm{boundary}}
+r_Z^{\mathrm{remap}}
+r_Z^{\mathrm{composition}}
+r_Z^{\mathrm{link}}
+r_Z^{\mathrm{conversion}}
+r_Z^{\mathrm{residual}}
+r_Z^{\mathrm{retention}}
+r_Z^{\mathrm{port}}
+\bar r_Z^{\mathrm{damp}}
+r_Z^{\mathrm{numeric}}.
\]

For a frozen-position velocity kick `j` of positive declared duration
\(\delta_j>0\), the endpoint rule reduces exactly to
`r_Z^(j)=(delta_j/h) w_Z Im(Z_j^* F_Z^(j))`. A zero-clock transition has
\(\delta_j=0\) and uses the separate endpoint-impulse receipt above, not this
rate formula. A named force row is the sum of its actual positive-duration
stage rows; in particular, the two separated composition, link, and
retention half-kicks are evaluated at their own states and accumulated, never
replaced by one full-rate value. Radial local nonlinear and harmonic forces
have zero phase source. Global U(1) invariance requires the integrated `D+C`
composition and topological-retention retention phase-source sums to cancel, while each
reciprocal link cancels between its two incident scales. The verifier checks
those cancellations from the endpoint stage rows; a nonzero residual cannot
be renamed transport.

Energy attribution uses the same endpoints. For a finite stage,
`W_j=E_total(X_j^+)-E_total(X_j^-)`, positive into the field, and the local
signed rate row is its declared component-density difference divided by `h`.
The per-coordinate executable identity is

\[
\frac{e_Z^{n+1}-e_Z^n}{h}
+\overline{\nabla\cdot\mathbf P_Z}
=
w_Z^{\mathrm{boundary}}
+w_Z^{\mathrm{remap}}
+w_Z^{\mathrm{link}}
+w_Z^{\mathrm{conversion}}
+w_Z^{\mathrm{composition}}
+w_Z^{\mathrm{residual}}
+w_Z^{\mathrm{retention}}
+w_Z^{\mathrm{port}}
+\bar w_Z^{\mathrm{damp}}
+w_Z^{\mathrm{numeric}}.
\]

These coordinate rows expose internal exchange; the global ledger adds
`U_composition`, `E_links`, and, for topological retention, `U_topo` to its left side and
removes their conservative exchange rows from its right side. The spectral
verifier subtracts the exact damping quadratures before assigning the
remaining linear-stage difference to transport. Telescoping every stage must
reproduce the accepted endpoint differences. The precise residual uses the
same split stages, FFT convention, cell-volume weights, rational interval, and
independently propagated uncertainty. It reports absolute and normalized
closure with a fixed zero-reference absolute tolerance and never calls a
current conserved merely because state stayed finite.


### Yang/Yin conversion and carrier steering

Conversion is the one canonical normalized frozen-`Q` position-sector map
defined under **Yang/Yin conversion** above. The implementation uses
`\rho_ref`, `\bar\rho`, `\bar\epsilon`, and `\bar m_{\epsilon^2}` exactly as
specified there; this section introduces no raw-density or implicit-unit
alternate. `m_epsilon2` is the mathematical name of the stored
`epsilon2_ema` plane and is the EMA of `epsilon^2`, never the square of another
EMA. `Q` is frozen during the exact centered subflow. Position phases follow
the declared zero/nonzero rule; `V_Y,V_I` remain unchanged. The profile stores
the physical positive duration `epsilon_memory_time`, and the controller
derives

\[
\tau_\epsilon(h)
:=1-\exp\!\left(-\frac{h}{\texttt{epsilon\_memory\_time}}\right)
\]

from each actual interval `h`; it updates the EMA once only after the complete
accepted step. The coefficient is not caller input, checkpoint state, or a
second adaptive object.

### QI-CONV-001 forward-viability gate

The field law in Part 1 is not production-admissible merely because its
closed-form densities remain nonnegative. W5V/G5V owns the
`QiConversionViabilityReceipt` and must preregister a complete
forward-viability proof for the centered frozen-`Q` map before this execution
contract can admit it. Let \(\mathbf z\) denote the complete conversion input
(active Yang/Yin positions, stored \(m_{\epsilon^2}\), all declared amplitude
and denominator quantities, and
\(h\in[h_{\min},h_{\max}]\)); let
\(\mathcal D_{\mathrm{conv}}\) be the closed profile support of these inputs.
Runtime executes only the exact-rational members of this closed interval. The
profile freezes \(\epsilon_{\mathrm{prog,min}}>0\), the registered balanced and
exact-zero control sets \(\mathcal D_{\mathrm{bal}},\mathcal D_{\mathrm{zero}}\), and
\[
\begin{aligned}
\mathcal D_{\mathrm{prog}}
&:=\{\mathbf z\in\mathcal D_{\mathrm{conv}}:
|\epsilon(\mathbf z)|\geq\epsilon_{\mathrm{prog,min}}\},\\
\mathcal D_{\mathrm{neutral}}
&:=\mathcal D_{\mathrm{conv}}\setminus\mathcal D_{\mathrm{prog}},
\end{aligned}
\]
with
\(\mathcal D_{\mathrm{bal}}\cup\mathcal D_{\mathrm{zero}}
\subseteq\mathcal D_{\mathrm{neutral}}\).

Before fixtures or outcomes are observed, the profile fixes a finite
complete-domain cover \(\{\mathcal D_\nu\}_{\nu=1}^{K}\) with
\[
\mathcal D_{\mathrm{conv}}=\bigcup_{\nu=1}^{K}\mathcal D_\nu,
\qquad
\operatorname{int}(\mathcal D_\nu)\cap
\operatorname{int}(\mathcal D_\mu)=\varnothing\quad(\nu\ne\mu),
\]
where \(K\) is finite and cell endpoints/boundaries are exact profile
values. Interval or analytic inclusion must prove, for every point in every
cell,
\[
\mathcal M_h(\mathcal D_\nu)
\subseteq\mathcal D_{\mathrm{conv}},
\qquad
\mathcal M_h(\mathcal D_\nu)
\subseteq\mathcal A_{\mathrm{accepted}}.
\]
Here \(\mathcal A_{\mathrm{accepted}}\) is the closed profile endpoint
domain. Every cell has exactly one status in
\(\{\mathrm{PASS},\mathrm{FAIL},\mathrm{UNRESOLVED}\}\); production requires
\[
\#\{\nu:\mathrm{status}(\nu)=\mathrm{UNRESOLVED}\}=0
\quad\text{and}\quad
\mathrm{status}(\nu)=\mathrm{PASS}\ \text{for every }\nu.
\]
An unresolved interval is a failed gate, not an omitted cell or a post-hoc
reason to narrow the support.

For every \(\mathbf z\in\mathcal D_{\mathrm{prog}}\), the proof also encloses
the transfer \(T\) with radius \(\mathcal U_T\geq0\) and establishes
\[
\operatorname{sign}(T)=\operatorname{sign}(\epsilon),
\qquad
|T|-\mathcal U_T\geq\Delta_{T,\min}>0.
\]
For every \(\mathbf z\in\mathcal D_{\mathrm{neutral}}\), it proves the
separate bounded-transfer predicate
\[
|T|+\mathcal U_T\leq\Delta_{T,\mathrm{neutral}}.
\]
Both margins are frozen before execution. Balanced and exact-zero fixtures
remain exact named no-ops; other nonzero neutral points may execute their
certified small transfer but never count as positive progress.
Fixtures cover interior, boundary, heterogeneous, multiscale, near-zero,
near-capacity, both phase branches, source-free, and admitted-work states.
They are retained only as hashed witnesses linked to covered cells; they do
not define, enlarge, or shrink the support and cannot replace its
complete-domain proof.

The receipt binds the frozen support and cover hashes, map/profile identity,
exact rational-time convention, interval/analytic method, every cell status,
zero unresolved count, witness/state hashes, transfer margins, work
classifications, invariant margins, and every rejected candidate.
Post-observation support shrinkage or cell deletion is a new failed profile
identity. G5V accepts only an all-cell proof with forward progress without
clipping, normalization, retries, or silent `T` shrinkage; otherwise the
design revises the law rather than normalizing repeated rejection. The
required redesign direction is constrained full-Hamiltonian gradient flow
under the same metric, positivity, work, and boundary admissibility rules,
not an unregistered runtime fallback.

The conversion subledger reports density transfer and the single

\[
W_{\mathrm{conversion}}
=
\Delta\!\left(
E_{\mathrm{wave}}
+U_{\mathrm{composition}}
+E_{\mathrm{links}}
+\mathbf1_{\{\mathrm{retention.mode}=\mathrm{topological\text{-}v1}\}}U_{\mathrm{topo}}
\right)
\]

across the finite map, including gradient-energy change for spatially
heterogeneous transfer. Composition, link, and retention deltas from this
stage are not entered again. The implementation tests analytic transfer,
positivity, phase rules, matched `+epsilon/-epsilon` fixtures, unchanged
velocities, one EMA update, exactly one conversion stage per complete step,
and the dissipative/numerical-zero/reject interval classification. It never
calls conversion a spatial current or claims whole-wave energy conservation
without the measured metric ledger.

The reciprocal `D,C` composition potential is active only through the frozen
law above and must pass independent stability, transport, and
counterfactual-steering gates. Reversing the registered Yang/Yin-composition
fixture under matched total energy must redirect the predicted carrier current
while the two coordinate-work rows and `Delta U_composition` close together.
If it does not, the system reports a null steering result rather than treating
`C` as a decorative diagnostic.

### Conservative cross-scale coupling

Every `Z_s` below denotes the gathered active vector
`\mathcal G_s Z_s^storage`, and every force is scattered back with
`\mathcal G_s^T`; inactive storage tails therefore
remain exactly zero. For `Z` in `{D,C}`,

`scale_geometry_mode` is consumed as an execution invariant, not a hint to
the link builder. Under `temporal-full-rank`, the preflight requires
`N_s=N_\star`, `rank(P_s)=N_\star`, and an empty link kernel at every
adjacency. Under `spatiotemporal-pyramid`, it requires the frozen
`N_{s+1}<N_s` sequence and records
`rank(P_s)` and `dim(ker(P_s))` before the force is formed. The controller
uses only the selected map and its `QiScaleGeometryComparisonReceipt`; it
never relabels a kernel as transmitted capacity or changes the mode to pass a
rank check. The active/padded byte accounting from Part 1 is carried into
the receipt, while the packed one-field state contract remains unchanged.


\[
W_s=\operatorname{diag}(dx_sdy_s)>0,
\qquad
P_s:\mathbb C^{N_s}\rightarrow\mathbb C^{N_{s+1}},
\qquad
P_s^\dagger=W_s^{-1}P_s^H W_{s+1}.
\]

`P_s` includes its frozen low-pass and cell-average normalization. Its
restricted adjoint is verified by
`\langle P_sx,y\rangle_{W_{s+1}}=\langle x,P_s^\dagger y\rangle_{W_s}`.
The link energy is

\[
E_{\mathrm{link},Z,s}
:=
\frac{w_Zg_{Z,s}}{2}
\left\|Z_{s+1}-P_sZ_s\right\|_{W_{s+1}}^2.
\]

The paired active-coordinate forces are

\[
F_{Z,s}^{\mathrm{link}}
:=g_{Z,s}P_s^\dagger(Z_{s+1}-P_sZ_s),
\]

\[
F_{Z,s+1}^{\mathrm{link}}
:=-g_{Z,s}(Z_{s+1}-P_sZ_s).
\]

### Scattering receipt at scale and external ports

The canonical receipt schema and independent replay are owned by Part 9; this
section specifies when the controller must produce and close the evidence.

Every execution path that admits, reflects, transmits, or absorbs work emits
the `QiScatteringReceipt` required by `QI-PORT-001`. For each scale-link or
external port, its interval ledger must contain the directed
`W_incident`, `W_reflected`, `W_transmitted`, and `W_absorbed` terms and the
closure residual

\[
W_{\mathrm{incident}}
-W_{\mathrm{reflected}}
-W_{\mathrm{transmitted}}
-W_{\mathrm{absorbed}}
=r_{\mathrm{scat}}.
\]

The receipt is linked to the same stage endpoints and profile-oriented port
power used by the field ledger. Scale-internal transmitted work is paired
between source and target receipts and cancels only after the declared
orientation and weighted adjoint are verified. External admitted work links
once to `W_sensory` and the metric-adjoint port reaction; reflected work
cannot disappear into a net residual. A missing term, ambiguous interval,
unpaired direction, or duplicate source debit rejects the candidate before
commit. The receipt is transient evidence, never a second state object.


The release full-system profile has positive declared `g_D` and `g_C` for
every adjacent scale pair. Exact-zero links exist only in named control
profiles. The controller records source-scale power, target-scale power, and
link-potential delta together. A gain at a slower scale without the paired
source/link account is a failed receipt, not memory transfer.

The former top-one demodulate/reconstruct consolidation is retired from the
live path. Fixed text/visual/audio probes remain boundary measurement
operators, but they are never used to collapse a distributed field into a
single scale-binding memory.

### Core implementation edits

The core cutover changes the following symbols in one coordinated migration:

| Current surface | Flow replacement | Required migration |
|---|---|---|
| `QiFieldConfig` loaded directly from `cassi-qi-language.json` | `QiFlowProfile.load("cassi-qi-flow.json")` from the new strict profile | update every canonical constructor and reject legacy config |
| `_mode_profile` | frozen `scale_geometry_mode`, declared spectral geometry, masks, and symbols | delete the linear index slope from the live law; do not infer or hide rank loss |
| `sense_symbols()` / `sense_wave()` | validated `QiBoundaryPacket` -> immutable drive bundle | move text and sensor encoding to boundary adapters |
| `evolve()` | internal stage of `advance()` | prohibit standalone live evolution without ledger |
| `correct_wave()` | metric-adjoint residual-return velocity half-kicks | remove direct state-target overwrite and any inverse-map claim |
| `consolidate()` | W4R topological-retention topology/Hamiltonian core plus W10R trajectory evidence | remove top-symbol memory writes; behavioral consolidation is measured later and never a hidden controller step |
| `emit()` / static `QiFieldReadout` | integrated `outflow()` window and `QiFlowDecision` | update text/world output consumers |
| `_bounded_parts()` | validate-before-commit plus explicit failure receipt | eliminate silent global rescale |
| `dump_state()` / `load_state()` v2 | v3 flow envelope identity and atomic chain | reject old state schemas |

Focused core test files are `test_cassi_qi_profile.py`,
`test_cassi_qi_field.py`, `test_cassi_qi_transport.py`, and
`test_cassi_qi_checkpoint.py`. Their detailed gates appear below; they test
laws and observable transitions rather than source text.

