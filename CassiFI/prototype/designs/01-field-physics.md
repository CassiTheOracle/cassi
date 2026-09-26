# Field state, geometry, and intrinsic physics

> CassiFI implementation plan, Part 1. [Previous](./00-foundations.md) · [Index](../README.md) · [Next](./02-retention-capacity-and-cognition.md)

## Canonical derived coordinates

Define both weighted coordinates explicitly:

\[
D=E_Y-\phi E_I,
\qquad
V_D=V_Y-\phi V_I,
\]

\[
C=\frac{\phi E_Y+E_I}{1+\phi^2},
\qquad
V_C=\frac{\phi V_Y+V_I}{1+\phi^2}.
\]

Both are transient views of the existing state. They add no tensor.

The inverse map and its metric identity are normative:

\[
w_D=\frac{1}{1+\phi^2},
\qquad
w_C=1+\phi^2,
\]

\[
E_Y=w_DD+\phi C,
\qquad
E_I=C-\phi w_DD,
\]

\[
V_Y=w_DV_D+\phi V_C,
\qquad
V_I=V_C-\phi w_DV_D,
\]

and, site by site,

\[
|E_Y|^2+|E_I|^2=w_D|D|^2+w_C|C|^2,
\qquad
|V_Y|^2+|V_I|^2=w_D|V_D|^2+w_C|V_C|^2.
\]

The norm identity is an algebraic equality, not a fitted metric:

\[
\frac{|E_Y-\phi E_I|^2}{1+\phi^2}
+\frac{|\phi E_Y+E_I|^2}{1+\phi^2}
=|E_Y|^2+|E_I|^2,
\]

because the cross terms cancel; the velocity identity follows by replacing
`E` with `V`.
Let

\[
\mathcal E_Y=|E_Y|^2,
\qquad
\mathcal E_I=|E_I|^2,
\qquad
\epsilon=\mathcal E_Y-\phi\mathcal E_I.
\]

The implementation and independent verifier evaluate both inverse identities
and both weighted-norm identities from canonical fixture bytes. Failure is a
geometry/profile failure, not a tolerance that a later dynamics gate may
waive. These identities are the reason every `D,C` Hamiltonian, current,
boundary adjoint, and cross-scale operator uses the declared metric weights.

The target interpretation is:

- `C` is the bulk coherence carrier;
- `D` is the differential steering field;
- Yang/Yin conversion regulates local composition;
- spatial transport carries phase and energy;
- neighboring scales exchange full distributed spectra;
- fixed world boundaries admit and emit work;
- slower circulation is memory.

In compact form:

\[
\boxed{
C\ \text{carries};\quad
D\ \text{steers};\quad
Y\leftrightarrow I\ \text{regulates};\quad
\text{scale circulation remembers}.
}
\]

## Declared spatial geometry

Spatial flow is valid only under a fingerprinted coordinate map. The flow
profile declares:

- packed storage width `M` and each scale's active rectangular size
  `N_s=N_{x,s}N_{y,s}<=M`;
- the invariant layout in which the first `N_s` slots are the complete
  row-major rectangle and the remaining `M-N_s` slots are zero inactive tail;
- the exact x-fastest, y-major active order
  `m <-> (y,x)`, `m=yN_{x,s}+x`, and derived unitary
  `m <-> (k_{y,s},k_{x,s})` DFT order;
- grid spacing, boundary conditions, body-frame orientation, and origin;
- scale-specific spatial spacing, wave numbers, and speed;
- fixed active-subspace restriction/prolongation operators and positive
  cell-volume metrics;
- transform normalization and sign conventions.
### Release spatial operator: periodic FFT2

The release spatial law is the periodic operator family
`spatial_operator_family="periodic-fft2.v1"` on every active sheet. For scale
`s`, the active rectangle is uniform with
\(N_s=N_{x,s}N_{y,s}\), spacings \(dx_s,dy_s>0\), and physical extents
\(L_{x,s}=N_{x,s}dx_s\) and \(L_{y,s}=N_{y,s}dy_s\). Its physical domain is
\(\mathbb T_s=(\mathbb R/L_{x,s}\mathbb Z)\times
(\mathbb R/L_{y,s}\mathbb Z)\); every active field and velocity therefore
satisfies
\(Z_s(x+L_{x,s},y)=Z_s(x,y)\) and
\(Z_s(x,y+L_{y,s})=Z_s(x,y)\), with the same identities for \(V_Z\).
There is no implicit wall, zero-padding boundary, or finite-aperture
interpretation in this release family.

For \(p\in\{0,\ldots,N_{x,s}-1\}\) and
\(q\in\{0,\ldots,N_{y,s}-1\}\), the profile fixes
\[
\operatorname{fftindex}_N(j):=
\begin{cases}
j,&0\leq j\leq\lfloor (N-1)/2\rfloor,\\
j-N,&\lfloor (N-1)/2\rfloor<j<N,
\end{cases}
\]
including the signed Nyquist convention when \(N\) is even, and
\[
k_{x,s}(p):=\frac{2\pi}{L_{x,s}}\operatorname{fftindex}_{N_{x,s}}(p),
\qquad
k_{y,s}(q):=\frac{2\pi}{L_{y,s}}\operatorname{fftindex}_{N_{y,s}}(q).
\]
The unitary DFT pair is
\[
\widehat Z_{s;q,p}
:=\frac{1}{\sqrt{N_s}}
\sum_{y=0}^{N_{y,s}-1}\sum_{x=0}^{N_{x,s}-1}
Z_{s;y,x}
\exp\!\left[-2\pi i\left(\frac{px}{N_{x,s}}+\frac{qy}{N_{y,s}}\right)\right],
\]
\[
Z_{s;y,x}
:=\frac{1}{\sqrt{N_s}}
\sum_{q=0}^{N_{y,s}-1}\sum_{p=0}^{N_{x,s}-1}
\widehat Z_{s;q,p}
\exp\!\left[+2\pi i\left(\frac{px}{N_{x,s}}+\frac{qy}{N_{y,s}}\right)\right].
\]
Here \(i^2=-1\), \((x,y)\) is the physical site coordinate in the declared
x-fastest/y-major order, and \((q,p)\) is the corresponding DFT-array
index. Writing \(F_s\) and \(F_s^{-1}\) for these two maps, the canonical
first-derivative, gradient, divergence, and Laplacian symbols are
\[
\begin{aligned}
\widehat{\partial_{x,s}Z_s}_{q,p}
&:=i\,k_{x,s}(p)\widehat Z_{s;q,p},&
\widehat{\partial_{y,s}Z_s}_{q,p}
&:=i\,k_{y,s}(q)\widehat Z_{s;q,p},\\
\widehat{\nabla_s f}_{q,p}
&:=\left(i\,k_{x,s}(p)\widehat f_{q,p},
i\,k_{y,s}(q)\widehat f_{q,p}\right),&
\widehat{\nabla_s\!\cdot J}_{q,p}
&:=i\left(k_{x,s}(p)\widehat J_{x;q,p}
+k_{y,s}(q)\widehat J_{y;q,p}\right),\\
\widehat{\nabla_s^2 Z_s}_{q,p}
&:=-\left(k_{x,s}(p)^2+k_{y,s}(q)^2\right)\widehat Z_{s;q,p}.
\end{aligned}
\]
Thus
\[
\nabla_s^2=\nabla_s\!\cdot\nabla_s
=F_s^{-1}\operatorname{diag}(-|k_s|^2)F_s,
\]
where \(|k_s|^2=k_{x,s}^2+k_{y,s}^2\). The declared signed Nyquist
\(\operatorname{fftindex}\) value is used literally in every symbol; the
combined coordinate \(Z=D+iC\) and vector currents are complex sheet
quantities, so no undeclared per-component Hermitian or zero-Nyquist override
is permitted. Under the positive uniform sheet metric \(W_s\),
\[
\langle\nabla_s f,J\rangle_{W_s}
=-\langle f,\nabla_s\!\cdot J\rangle_{W_s}.
\]
Every gradient, phase/current, divergence/flux, Hodge, force/work, remap,
linear-propagation, and closure row uses these exact symbols and this
metric-adjoint identity. A periodic integrated divergence is consequently an
exact zero in the continuum identity and is only a numerical residual after
the declared quadrature.

The periodic law is not a generic instruction to use an FFT for another
boundary problem. A future nonperiodic operator family must receive a new
`spatial_operator_family` identifier and a new profile/operator/state
identity. Before it can be admitted, that family must declare its domain and
boundary traces, basis or transform and normalization, discrete derivative
and Laplacian, positive cell metric, metric adjoints for every restriction,
prolongation, and remap, force/energy/current/flux identities, endpoint
boundary work, and resolution/refinement error proof. Its independent
boundary and flux closure must be replayed at the selected resolution and
under refinement; periodic torus closure, wrapped FFT symbols, or periodic
zero-divergence identities cannot be reused as evidence. The present release
profile has no nonperiodic branch.

### Oversampled pseudospectral metric and restriction

When a nonlinear or composition product uses oversampling, the profile fixes
integer factors \(\sigma_{x,s},\sigma_{y,s}\geq1\) and
\[
N_{x,s}^{+}:=\sigma_{x,s}N_{x,s},\qquad
N_{y,s}^{+}:=\sigma_{y,s}N_{y,s},\qquad
N_s^{+}:=N_{x,s}^{+}N_{y,s}^{+},
\]
while preserving the physical extents:
\[
dx_s^{+}:=\frac{L_{x,s}}{N_{x,s}^{+}}
=\frac{dx_s}{\sigma_{x,s}},
\qquad
dy_s^{+}:=\frac{L_{y,s}}{N_{y,s}^{+}}
=\frac{dy_s}{\sigma_{y,s}}.
\]
Let \(F_s^{+}\) be the unitary periodic DFT on the oversampled rectangle and
let \(J_s:\mathbb C^{N_s}\to\mathbb C^{N_s^{+}}\) be the fixed Fourier
coefficient injection that preserves every base signed frequency in the
profile's Nyquist convention and fills all other coefficients with zero.
The physical-grid interpolation is
\[
\alpha_s:=\sqrt{\frac{N_s^{+}}{N_s}},
\qquad
I_s:=(F_s^{+})^{-1}\alpha_sJ_sF_s.
\]
The factor \(\alpha_s\) is required by unitary DFT normalization; omitting it
would change constant fields and the metric.

For the uniform periodic grids, define
\[
W_s:=dx_sdy_s\,I_{N_s},\qquad
W_s^{+}:=dx_s^{+}dy_s^{+}\,I_{N_s^{+}},
\qquad
\langle u,v\rangle_{W}:=u^HWv,
\]
where \(I_n\) is the \(n\)-dimensional identity and \(H\) denotes conjugate
transpose. The exact weighted restriction (which is distinct from the
cross-scale map \(P_s\)) is
\[
R_s:=W_s^{-1}I_s^HW_s^{+},
\qquad
I_s^HW_s^{+}I_s=W_s,
\qquad
R_sI_s=I_{N_s}.
\]
Thus \(I_sR_s\) is the \(W_s^{+}\)-orthogonal projector onto the embedded
base band:
\[
\Pi_s^{+}:=I_sR_s,\qquad
(\Pi_s^{+})^2=\Pi_s^{+},\qquad
(\Pi_s^{+})^HW_s^{+}=W_s^{+}\Pi_s^{+}.
\]
If \(U_s^{+}(z^{+})\) is an oversampled discrete potential, \(z^{+}=I_sz\),
and \(\nabla_W\) denotes the gradient defined by
\(dU[\delta z]=\operatorname{Re}\langle\nabla_WU,\delta z\rangle_W\),
then the base-grid potential and force gradient are fixed by
\[
U_s(z):=U_s^{+}(I_sz),
\qquad
\nabla_{W_s}U_s(z)
:=R_s\nabla_{W_s^{+}}U_s^{+}(I_sz).
\]
All oversampled products, filters, and potential quadratures use \(W_s^{+}\)
and return through this \(R_s\); no unweighted slice, nearest-neighbor
decimation, or independently normalized restriction is admissible. The
oversampling factors, \(J_s\), Nyquist handling, filter, and both metrics are
operator identity. Changing spatial resolution or oversampling therefore
changes the profile/operator and any resolution-bound codebook; it never
changes the physical extents or introduces a hidden state object.
For source resolution \(\star=s\), abbreviate
\(N_\star:=N_s\), \(F_\star:=F_s\), and \(W_\star:=W_s\). The target
\(N_{\star'},F_{\star'},W_{\star'}\) are defined below.

For a distinct target resolution \(\star'\) on the same physical extents,
the release transfer is **refinement only**:
\[
N_{x,\star'}\geq N_{x,\star},\qquad
N_{y,\star'}\geq N_{y,\star}.
\]
Write \(N_{\star'}=N_{x,\star'}N_{y,\star'}\), let \(F_{\star'}\) be its
unitary periodic DFT, and let \(J_{\star\to\star'}\) be the fixed
one-to-one signed-frequency injection of the **complete** source DFT array,
including the declared Nyquist convention, into the target array. It must
satisfy
\[
J_{\star\to\star'}^{H}J_{\star\to\star'}=I_{N_\star}.
\]
With \(W_{\star'}\) the target cell-volume metric, the only admitted
full-field periodic-band resolution map is
\[
I_{\star\to\star'}
:=(F_{\star'})^{-1}
\sqrt{\frac{N_{\star'}}{N_\star}}\,
J_{\star\to\star'}F_\star,
\qquad
R_{\star\to\star'}
:=W_\star^{-1}I_{\star\to\star'}^HW_{\star'},
\]
and therefore
\[
I_{\star\to\star'}^HW_{\star'}I_{\star\to\star'}=W_\star,
\qquad
R_{\star\to\star'}I_{\star\to\star'}=I_{N_\star}.
\]
Here \(N_\star\) and \(F_\star\) are the source count and DFT, and the
source/target metrics and Nyquist conventions are those already defined
above. Coarsening is not a full-field transfer in this release: a future
profile must first declare a retained source band/subspace, its projection
metric identity and lost-mode evidence, then use a different named operator
family and codebook proof. A target without this one-to-one complete-frequency
injection receives no transfer map and must regenerate its codebook. This map
is a declared resolution-transfer operator, not an unweighted resize; topology
preservation still requires the independent Part 2 codebook guard.



### Scale-geometry alternatives and frozen production choice

`QI-SCALE-001` is the release contract for the scale stack. The immutable
profile field `scale_geometry_mode` names exactly one of two registered
candidates: `temporal-full-rank` or `spatiotemporal-pyramid`. The mode is
selected once after the W6T/G6T comparison and is part of the profile,
operator, and state-contract hashes; it is never inferred from an input,
silently changed to hide rank loss, or selected per episode.

Rank loss is never implicit: every rank-deficient `P_s`, retained subspace,
and dark mode is declared, measured, and bound to the frozen production
profile rather than inferred from a failed response.

The `temporal-full-rank` (temporal-only) candidate keeps one physical active
sheet at every temporal level:

\[
N_s=N_\star,\qquad
\operatorname{rank}(P_s)=N_\star,\qquad
\ker(P_s)=\{0\}.
\]

Its scales differ by their clocks, characteristic frequencies, damping, and
declared temporal response, while the cross-scale map preserves the complete
active spatial subspace. It therefore avoids spatial rank loss and exposes
the largest candidate endpoint rank, at the cost of carrying the same active
spatial bytes at every level and potentially repeating spatial modes across
timescales.

The `spatiotemporal-pyramid` candidate declares a registered decreasing
sequence of sheets and fixed restriction/regrid maps:

\[
N_{s+1}<N_s,\qquad
\operatorname{rank}(P_s)=r_s\leq N_{s+1},\qquad
\dim\ker(P_s)=N_s-r_s.
\]

It trades fine-scale spatial degrees of freedom for slower-scale support and
lower active-sheet storage. Every lost direction is an explicit scale-link
nullspace/dark mode; it is not called full-spectrum, memory, or endpoint
capacity unless a registered boundary probe can reach and observe it through
another declared path. The singular values, effective rank, kernel basis,
aliasing/collision controls, and retained subspace are profile data.

For a packed real scalar width `b` bytes, the comparison reports both the
physical active-byte budget and the checkpoint-byte budget:

\[
B_{\mathrm{active}}
   =9bB\sum_{s=0}^{S-1}N_s,\qquad
B_{\mathrm{packed}}=9bBSM,\qquad
B_{\mathrm{tail}}=B_{\mathrm{packed}}-B_{\mathrm{active}}.
\]

`B_packed` remains fixed by the one-field `[S,9M,B]` checkpoint contract;
`B_active` and `B_tail` are accounting quantities and do not authorize
compression, another tensor, or a persistent sidecar. Thus a full-rank
temporal stack buys rank and byte access, whereas a pyramid may reduce active
bytes and improve coarse support while paying an explicit nullspace and
collision cost. A change to the packed representation is a new state schema,
not an optimization hidden under the same profile.

The registered `QiScaleGeometryComparisonReceipt` contains both candidate
profile hashes, active and packed byte budgets, per-link singular spectra and
nullspaces, boundary-to-output/action rank and conditioning, cross-talk,
dark-mode and collision counts, retention horizon, and the same work/fixture
set for both arms.
W6T/G6T may select only the candidate whose measured rank, nullspace,
persistent-byte, and stability tradeoffs satisfy the declared release
margins. If neither arm is admissible, the profile fails closed. Once selected,
`scale_geometry_mode` is frozen for every run; runtime input, workload, or
observed rank cannot switch modes or normalize away a failed comparison.

The `W6T / G6T` gate pair is the registered comparison and release-selection
boundary; production cannot proceed on an unselected or unreceipted mode.

The four production banks are temporal scales, not feature banks. Each bank is
one declared spatial sheet with its own clock/frequency/spacing/operator
identity; `temporal-full-rank` uses the same active sheet at every level,
whereas `spatiotemporal-pyramid` uses the registered sheet sequence above.
The release `scale_count=4` can change only through a new profile, capacity
receipt, and incompatible state contract.

The current boundary-active width is `W=M/2=256`, which can support a declared
`16 x 16` complex physical sheet after a new layout/operator cutover. This is
the numerical calibration profile, not the complete perceptual capacity.
Capacity changes are explicit profile and checkpoint-schema changes. No
existing quadratic-chirp index is silently relabeled as a retinal location.

The active state slots store physical-grid values so `epsilon2_ema`, local
Yang/Yin conversion, body coordinates, and boundary work retain a sitewise
meaning. A fixed unitary two-dimensional DFT is a transient derivative and
translation view. It is invertible and contains no learned features. Its exact
normalization, frequency order, Nyquist convention, and signs are operator
identity.
### Physical clock and timescale identity

The symbol \(t\) is one physical time coordinate shared by every scale and
boundary. The profile freezes two exact rational bounds
\[
0<h_{\min}\leq h_{\max},
\qquad
\mathcal H_{\mathrm{runtime}}
:=[h_{\min},h_{\max}]\cap\mathbb Q.
\]
Every live controller interval belongs to this set:
\[
t_n\in\mathbb Q,\qquad
h_n\in\mathcal H_{\mathrm{runtime}},\qquad
t_{n+1}:=t_n+h_n.
\]
For complete-domain numerical proofs, \(h\) is enclosed over the closed real
interval \([h_{\min},h_{\max}]\); runtime executes only its exact-rational
members. Zero-duration evolution is forbidden, and a requested duration below
\(h_{\min}\) or above \(h_{\max}\) fails preflight.
The scale clock is the declared physical sampling/advance schedule, not a
second dimensionless time. Thus \(\omega_{Z,s}h_n\),
\(\gamma_{Z,s}h_n\), \(h_n/\texttt{epsilon\_memory\_time}\), and every
cross-scale phase advance are dimensionless only after their declared units
are validated. A slower scale means its profile-declared frequencies,
damping, and response horizon are slower in this same \(t\), not that it uses
a rescaled or hidden step count.

Spatial refinement changes \(N_{x,s},N_{y,s},dx_s,dy_s\), the associated
Fourier and oversampled operators, and their profile identities while holding
\(L_{x,s},L_{y,s}\), \(t\), and all physical time constants fixed. An internal
certificate subdivision of an accepted parent interval \(h\) is a finite
sequence \(h_j\in\mathbb Q_{>0}\) with \(\sum_jh_j=h\). It is an evidence
partition, not a new `advance()` or conversion-duration request: only the
parent belongs to \(\mathcal H_{\mathrm{runtime}}\), and a subdivision cannot
create an additional trajectory or capacity member. A zero-clock finite map is
a separate endpoint transition, does not advance \(t\), and never receives a
fictitious duration or EMA update.


## Intrinsic field transport

For each scale, the target steering-field law is

\[
\dot D_s=V^D_s,
\]

\[
\dot V^D_s=
c_{D,s}^2\nabla^2D_s
-\omega_{D,s}^2D_s
-\gamma_{D,s}V^D_s
-\kappa_{D,s}|D_s|^2D_s
+F^{\mathrm{composition}}_{D,s}
+F^{\mathrm{link}}_{D,s}
+F^{\mathrm{boundary}}_{D,s}
+F^{\mathrm{residual}}_{D,s}
+F^{\mathrm{retention}}_{D,s}.
\]

The coherence carrier follows

\[
\dot C_s=V^C_s,
\]

\[
\dot V^C_s=
c_{C,s}^2\nabla^2C_s
-\omega_{C,s}^2C_s
-\gamma_{C,s}V^C_s
-\kappa_{C,s}|C_s|^2C_s
+F^{\mathrm{composition}}_{C,s}
+F^{\mathrm{link}}_{C,s}
+F^{\mathrm{boundary}}_{C,s}
+F^{\mathrm{residual}}_{C,s}
+F^{\mathrm{retention}}_{C,s}.
\]

The retention force is selected only by the immutable retention profile. On
the slow scale, write the canonical weighted rotation as
\[
\begin{pmatrix}\psi_{\mathrm{topo}}\\\chi_{\mathrm{topo}}\end{pmatrix}
:=
\begin{pmatrix}a_{\mathrm{topo}}&b_{\mathrm{topo}}\\-b_{\mathrm{topo}}&a_{\mathrm{topo}}\end{pmatrix}
\begin{pmatrix}\sqrt{w_D}D_{S-1}\\\sqrt{w_C}C_{S-1}\end{pmatrix},
\qquad a_{\mathrm{topo}}^2+b_{\mathrm{topo}}^2=1,
\]
with its fixed real transpose as the inverse. For a real scalar potential,
the positive-cell-metric Wirtinger convention is exactly
\[
\operatorname{grad}^{W}_{Z^*}U:=W^{-1}\frac{\partial U}{\partial Z^*}.
\]
Thus the verifier first differentiates the declared
`U_topo(psi_topo,chi_topo)` in the rotated coordinates and applies the
explicit pullback
\[
\frac{\partial U_{\mathrm{topo}}}{\partial D_{S-1}^*}
:=\sqrt{w_D}\!\left(
a_{\mathrm{topo}}\frac{\partial U_{\mathrm{topo}}}{\partial\psi_{\mathrm{topo}}^*}
-b_{\mathrm{topo}}\frac{\partial U_{\mathrm{topo}}}{\partial\chi_{\mathrm{topo}}^*}\right),\qquad
\frac{\partial U_{\mathrm{topo}}}{\partial C_{S-1}^*}
:=\sqrt{w_C}\!\left(
b_{\mathrm{topo}}\frac{\partial U_{\mathrm{topo}}}{\partial\psi_{\mathrm{topo}}^*}
+a_{\mathrm{topo}}\frac{\partial U_{\mathrm{topo}}}{\partial\chi_{\mathrm{topo}}^*}\right).
\]
The force is then
\[
F^{\mathrm{retention}}_{Z,s}
:=
\mathbf 1_{\{\mathrm{retention.mode}=\mathrm{topological\text{-}v1}\}}
\mathbf 1_{\{s=S-1\}}
\left(-\frac{2}{w_Z}\operatorname{grad}^{W_{S-1}}_{Z^*}U_{\mathrm{topo}}\right),
\qquad Z\in\{D,C\}.
\]
Fading retention sets this force identically to zero. It acts only on existing
slow-scale coordinates, is conservative, introduces no EMA or coefficient
update, and owns no state other than its ordinary effect on the candidate
`QiFieldState.field`.

`QI-RET-001` fixes the causal dependency: W4R installs this topological-retention
Hamiltonian/topology core immediately after W4 and before W5. The core
supplies only the bounded force, torus-sector guards, and conservative
Hamiltonian/work terms needed by the subsequent conversion and split-step
proof; it does not claim that a trajectory has retained or recalled anything.
W10R is the later behavioral-retention/consolidation package and may claim
acquisition, residence, cue return, overwrite, or recovery only after the
core and the boundary/trajectory evidence exist.


Composition steering is one conservative reciprocal coupling, not a one-way
coefficient injection. Define

\[
a_\phi=\frac{1}{1+\phi^2},
\qquad
f_s(\epsilon)=\tanh\!\left(\frac{\epsilon}{\epsilon_{\mathrm{ref},s}}\right),
\qquad
f'_s(\epsilon)=
\frac{\operatorname{sech}^2(\epsilon/\epsilon_{\mathrm{ref},s})}
{\epsilon_{\mathrm{ref},s}},
\]

\[
u^{\mathrm{composition}}_s
=
\frac{w_C\omega_{C,s}^2\beta_s}{2}
f_s(\epsilon_s)|C_s|^2,
\qquad
0\leq\beta_s<1,\quad \epsilon_{\mathrm{ref},s}>0.
\]

Under the exact `D,C` inverse,

\[
\frac{\partial\epsilon}{\partial D^*}
=a_\phi(E_Y+\phi^2E_I),
\qquad
\frac{\partial\epsilon}{\partial C^*}
=\phi(E_Y-E_I).
\]

Both forces are the metric gradient of that one potential:

\[
F^{\mathrm{composition}}_{D,s}
=
-\frac{2}{w_D}
\frac{\partial u^{\mathrm{composition}}_s}{\partial D_s^*}
=
-\frac{w_C}{w_D}\omega_{C,s}^2\beta_sf'_s
|C_s|^2a_\phi(E_Y+\phi^2E_I),
\]

\[
F^{\mathrm{composition}}_{C,s}
=
-\frac{2}{w_C}
\frac{\partial u^{\mathrm{composition}}_s}{\partial C_s^*}
=
-\omega_{C,s}^2\beta_s
\left[
f_sC_s+f'_s|C_s|^2\phi(E_Y-E_I)
\right].
\]

The base carrier quadratic plus this term is bounded below because
`beta_s<1`. The base `omega_C`, gain, reference imbalance, evaluation stage,
and stability envelope are profile data. The two coordinate-work rows plus the
composition-potential delta close together; `D` work and `C` work are not
incorrectly required to be equal and opposite at every instant.

The numerical operator uses a velocity-first split step. Fixed spectral
transport, local nonlinear evolution, Yang/Yin conversion, cross-scale
coupling, damping, and boundary work are separate sub-operators with separate
ledger terms. No accepted run depends on post-step clipping to remain finite.

## Body-motion transport and embodied reference

Intrinsic field propagation is distinct from coordinate remapping caused by an
eye, head, body, or camera action. For a displacement `Delta x`, the spectral
remap is

\[
\widehat D'(k)=e^{-ik\cdot\Delta x}\widehat D(k),
\qquad
\widehat V_D'(k)=e^{-ik\cdot\Delta x}\widehat V_D(k),
\]

with the same operation applied to `C` and `V_C`. Rotation uses a fixed declared
resampling operator whose forward/inverse error is included in the receipt.
Translation is unitary, DC-preserving, norm-preserving, and exactly reversible
within the declared numerical tolerance.

The head/neck-midline self-center is an engineering body-frame origin inspired
by subjective report. It is not a pineal biological claim, hidden observer,
selector, memory store, or energy sink. Its function is distributed across the
field:

- register every sensory boundary in one moving body frame;
- provide the phase and coordinate reference for outward action;
- apply the action's efference remap before the next observation;
- cancel predicted self-generated return flow;
- leave unexpected world-generated flow as a residual.

Correct, offset, mirrored, lagged, and shuffled body frames are mandatory
controls. The center is accepted only when the declared body frame improves
causal residual closure without suppressing exafferent motion.

## Yang/Yin conversion

At conversion entry, let the profile's positive position-density reference be
`\rho_ref` and define

\[
\rho=\mathcal E_Y+\mathcal E_I,
\qquad
m_{\epsilon^2}:=\texttt{epsilon2_ema},
\]

\[
\bar\rho=\frac{\rho}{\rho_{\mathrm{ref}}},
\qquad
\bar\epsilon=\frac{\epsilon}{\rho_{\mathrm{ref}}},
\qquad
\bar m_{\epsilon^2}
=\frac{m_{\epsilon^2}}{\rho_{\mathrm{ref}}^2},
\]

\[
Q=
\frac{\bar\rho^2}
{\bar\rho^2+\phi^{-2}+\bar m_{\epsilon^2}},
\qquad 0\leq Q<1.
\]

The normalizations are part of the immutable conversion profile. They make
every term in `Q` dimensionless; an implicit unit amplitude is prohibited.

### Conversion viability and physical-time constitutive memory

`QI-CONV-001` makes the frozen-`Q` map a conditional production law rather
than an assumption. W5V/G5V must preregister a complete forward-viability
proof before this map can be selected by a release profile. Let
\(\mathbf z\) denote one complete conversion input (the active Yang/Yin
positions, the stored \(m_{\epsilon^2}\), all declared amplitude and
denominator quantities, and a duration
\(h\in[h_{\min},h_{\max}]\)); let
\(\mathcal D_{\mathrm{conv}}\) be the closed profile support of such inputs.
Runtime conversion invokes only the exact-rational members
\(\mathcal H_{\mathrm{runtime}}\), while the forward proof encloses the full
closed real duration interval. The support includes the positive `\rho_ref`
and denominator conditions, nonnegative sector densities and `epsilon2_ema`,
the phase rule, numerical work-interval guards, and amplitude bounds.
The profile freezes a positive resolved-progress guard
\(\epsilon_{\mathrm{prog,min}}>0\), the registered balanced and exact-zero
control sets \(\mathcal D_{\mathrm{bal}},\mathcal D_{\mathrm{zero}}\), and
\[
\begin{aligned}
\mathcal D_{\mathrm{prog}}
&:=\{\mathbf z\in\mathcal D_{\mathrm{conv}}:
|\epsilon(\mathbf z)|\geq\epsilon_{\mathrm{prog,min}}\},\\
\mathcal D_{\mathrm{neutral}}
&:=\mathcal D_{\mathrm{conv}}\setminus\mathcal D_{\mathrm{prog}}.
\end{aligned}
\]
\(\mathcal D_{\mathrm{bal}}\cup\mathcal D_{\mathrm{zero}}\) is a subset of
\(\mathcal D_{\mathrm{neutral}}\). This guarded partition prevents continuity
near \(\epsilon=0\) from being misreported as a uniform positive-progress
margin.

Before any fixture or outcome is observed, the profile fixes a finite
complete-domain cover \(\{\mathcal D_\nu\}_{\nu=1}^{K}\) with
\[
\mathcal D_{\mathrm{conv}}=\bigcup_{\nu=1}^{K}\mathcal D_\nu,
\qquad
\operatorname{int}(\mathcal D_\nu)\cap
\operatorname{int}(\mathcal D_\mu)=\varnothing\quad(\nu\ne\mu),
\]
where \(K\) is finite and every cell has declared exact rational endpoints
or an analytically described closed boundary. The interval/analytic proof
must establish, for every cell and every point in that cell, the complete
centered map \(\mathcal M_h\) satisfies
\[
\mathcal M_h(\mathcal D_{\nu})
\subseteq\mathcal D_{\mathrm{conv}},
\qquad
\mathcal M_h(\mathcal D_{\nu})
\subseteq\mathcal A_{\mathrm{accepted}}.
\]
Here \(\mathcal A_{\mathrm{accepted}}\) is the profile's closed endpoint
domain, and the inclusions are set inclusions proved by interval enclosures
or analytic inequalities, not by evaluating one representative state.
Every cell receives exactly one proof status,
\(\mathrm{PASS}\), \(\mathrm{FAIL}\), or \(\mathrm{UNRESOLVED}\); production
requires all cells to be `PASS`, in particular
\[
\#\{\nu:\mathrm{status}(\nu)=\mathrm{UNRESOLVED}\}=0.
\]
An unresolved cell is a failed gate, not an omitted cell or a reason to
reduce precision after seeing outcomes.

For every \(\mathbf z\in\mathcal D_{\mathrm{prog}}\), the same proof encloses
the transfer \(T\) and its interval radius \(\mathcal U_T\), and establishes
\[
\operatorname{sign}(T)=\operatorname{sign}(\epsilon),
\qquad
|T|-\mathcal U_T\geq\Delta_{T,\min}>0.
\]
For every \(\mathbf z\in\mathcal D_{\mathrm{neutral}}\), it instead proves
\[
|T|+\mathcal U_T\leq\Delta_{T,\mathrm{neutral}},
\]
under a separately preregistered finite neutral bound. The balanced and
exact-zero controls must remain exact named no-ops. A nonzero neutral point
may execute its certified bounded transfer, but it is not counted as
positive progress; an ordinary point may never be turned into a no-op by
runtime rejection or post-hoc domain reclassification.

Fixtures cover interior, boundary, heterogeneous, multiscale, near-zero, and
near-capacity states, both phase branches, and source-free/admitted-work
controls. They are retained in the receipt as hashed witnesses linked to
the cells they exercise; they do not define, enlarge, or shrink
\(\mathcal D_{\mathrm{conv}}\), and fixture success cannot substitute for
the complete-domain proof. The support, cell cover, endpoint domain, proof
method, and cell-status vector are frozen and hashed before execution.
Post-observation support shrinkage, cell deletion, or a narrower replacement
domain is a new failed profile identity rather than a passing repair.

The `QiConversionViabilityReceipt` records the frozen support and cover
hashes, map identity, interval/analytic method, every cell status (with zero
unresolved cells), witness/state hashes, accepted forward-step count, transfer
margins, work classifications, invariant margins, and every rejected
candidate. G5V accepts the frozen-`Q` law only when every ordinary-domain
cell proves forward progress without clipping, normalization, retries, or
silent shrinkage of `T`. If any cell fails or remains unresolved, the design
revises the law rather than normalizing repeated rejection. The required
redesign direction is constrained full-Hamiltonian gradient flow under the
same metric, work, positivity, and boundary admissibility rules; that
redesign is not an unregistered runtime fallback and requires a new profile
and state-contract identity.

The profile stores the physical positive duration
`epsilon_memory_time`, not a free-standing adaptive coefficient. For every
complete accepted interval `h`, the controller derives the dimensionless
per-step coefficient

\[
\tau_\epsilon(h)
:=1-\exp\!\left(-\frac{h}{\texttt{epsilon\_memory\_time}}\right),
\qquad
0<\tau_\epsilon(h)\leq1.
\]

`h` and `epsilon_memory_time` carry declared time units; their ratio is formed
only after unit and profile validation. A changed interval therefore changes
the derived coefficient deterministically, while the physical time constant
remains profile identity. `tau_epsilon` is not caller input, checkpoint
state, or a second memory object.


`Q` is computed once and frozen for the complete centered conversion substep.
With immutable dimensionless `phi>0`, profile rate `lambda>=0` in inverse
time, and the complete step interval `h`,

\[
\alpha=
\exp\!\left[-(1+\phi)\lambda(1-Q)h\right],
\qquad
T=
\frac{\rho_{\mathrm{ref}}\bar\epsilon}{1+\phi}(1-\alpha)
=\frac{\epsilon}{1+\phi}(1-\alpha),
\]

\[
\mathcal E_Y'=\mathcal E_Y-T,
\qquad
\mathcal E_I'=\mathcal E_I+T.

\]

The center-map imbalance reconstructed from these two densities is named
`\epsilon_{\mathrm{conv}}'`; it is not the EMA sample.

This is the exact frozen-`Q` solution of
`R=lambda(1-Q)epsilon`. It preserves nonnegative sector densities and local
Yang-plus-Yin position density without clipping or projection. Each nonzero
complex sector keeps its phase; a newly nonzero empty sector receives the
other sector's phase, and two empty sectors remain empty. `V_Y` and `V_I` are
unchanged by this position-exchange suboperator. Let

#### Conversion-flow time receipt

The same frozen-`Q` map gives an exact internal age for the conversion
subflow. Its imbalance obeys

\[
\epsilon_{\mathrm{conv}}'
=\mathcal E_Y'-\phi\mathcal E_I'
=\alpha\epsilon.
\]

Define the dimensionless conversion exposure

\[
\boxed{
\Delta\chi_F
:=-\frac{1}{1+\phi}
\ln\left|\frac{\epsilon_{\mathrm{conv}}'}{\epsilon}\right|
=\lambda(1-Q)h
}.
\]

For `lambda>0`, the corresponding time-dimension conversion age is

\[
\boxed{
\Delta\tau_F
:=\frac{\Delta\chi_F}{\lambda}
=-\frac{1}{(1+\phi)\lambda}
\ln\left|\frac{\epsilon_{\mathrm{conv}}'}{\epsilon}\right|
=(1-Q)h
}.
\]

In differential form this is literally the inter-fluid transfer divided by
its imbalance drive:

\[
d\tau_F
=\frac{d\mathcal E_I|_{\mathrm{conv}}}{\lambda\epsilon}
=-\frac{d\mathcal E_Y|_{\mathrm{conv}}}{\lambda\epsilon}
=-\frac{d\epsilon}{(1+\phi)\lambda\epsilon}
=(1-Q)\,dt.
\]

For equal external intervals under one profile, two frozen gates therefore
have the exact relative conversion-clock rate

\[
\frac{\Delta\tau_F(Q_1)}{\Delta\tau_F(Q_0)}
=\frac{1-Q_1}{1-Q_0}.
\]

This quantity is derived from the existing predecessor/successor state and
adds no runtime state, adaptive clock, or checkpoint field. It is the
openness-weighted age of the conversion subflow and equals the external
interval only when `Q=0`. The shared rational physical clock `t` remains the
release schedule. With the memory-bearing gate, endpoint imbalance determines
`\Delta\tau_F`; recovering elapsed `t` also requires the frozen-`Q` history.
Promoting this relative conversion rate to a universal lapse for wave,
particle, geometry, boundary, and memory dynamics is outside the release
contract.

The logarithmic receipt is evaluated only for resolved nonzero predecessor
and successor imbalance on one conversion branch. Exact balance and
unresolved near-zero endpoints contain no readable state-derived tick and do
not evaluate the quotient or logarithm. `lambda=0` fixes
`\Delta\chi_F=0` while leaving the time-dimension `\Delta\tau_F` undefined.

\[
E_{\mathrm{total}}
=E_{\mathrm{wave}}
+U_{\mathrm{composition}}
+E_{\mathrm{links}}
+\mathbf 1_{\{\mathrm{retention.mode}=\mathrm{topological\text{-}v1}\}}U_{\mathrm{topo}}.
\]

Conversion work is defined exactly once as

\[
W_{\mathrm{conversion}}
:=
E_{\mathrm{total}}(\text{after conversion})
-E_{\mathrm{total}}(\text{before conversion}).
\]

It therefore includes every map-induced position, gradient, base/nonlinear
potential, composition-potential, link-potential, and topological-retention
potential delta; kinetic energy is unchanged. None of those deltas is entered
again under another global work row.

The canonical release profile fixes
`conversion_energy_mode="dissipative-v1"`. `W_conversion` is therefore not an
unfunded internal source, an unnamed reservoir, or boundary work. Before any
mutation, the controller recomputes the complete post-conversion Hamiltonian,
the signed work above, and a nonnegative numerical interval radius
`\mathcal U_conversion`. With the profile's nonnegative numerical-zero guard
`\Delta_conversion`, exactly one classification must hold:

\[
\begin{array}{lll}
\text{resolved dissipation}
&\Longleftrightarrow&
W_{\mathrm{conversion}}+\mathcal U_{\mathrm{conversion}}
<-\Delta_{\mathrm{conversion}},\\[1mm]
\text{numerical zero}
&\Longleftrightarrow&
|W_{\mathrm{conversion}}|+\mathcal U_{\mathrm{conversion}}
\leq\Delta_{\mathrm{conversion}}.
\end{array}
\]

A resolved-dissipation candidate is accepted and records
`Q_conversion=-W_conversion>0` once as a constitutive sink unavailable to every
other operator. A numerical-zero candidate is accepted with
`Q_conversion=0`, while retaining the signed `W_conversion` and interval in the
receipt rather than coercing the measured work to zero. Every other interval,
including resolved positive work and an interval too ambiguous to distinguish
zero from dissipation or source behavior, rejects the entire field-step
candidate with `conversion_energy_unresolved`. Rejection never shrinks `T`,
clips a sector, silently skips conversion, or falls back to another law.
Exact-zero conversion remains a named null control. Any future active
conversion law requires a different state-contract hash and an explicit
energy-bearing source; it is not a runtime option of this profile.

After the complete accepted field step, and only then, reconstruct
`\epsilon_{t+h}` from the final post-force candidate positions and update

\[
m_{\epsilon^2,t+h}
=(1-\tau_\epsilon(h))m_{\epsilon^2,t}
+\tau_\epsilon(h)\epsilon_{t+h}^2,
\qquad \tau_\epsilon(h)
=1-\exp\!\left(-\frac{h}{\texttt{epsilon\_memory\_time}}\right).
\]

The completed field cycle invokes this conversion exactly once at its declared
center. It never exposes caller-selected rate/time controls.

`epsilon2_ema` is a declared local constitutive field inside the sole state,
not a Hamiltonian position/velocity coordinate and not a cue-addressable memory
store. Its old/new values and fixed update are receipted, but no fictitious
wave energy is assigned to it. Energy-conservation claims apply to the
position/velocity, composition, link, and topological-retention terms under
the discrete ledger; conversion separately proves local Yang-plus-Yin density
conservation.

## Continuous cross-scale circulation

Top-one reconstruction is replaced by distributed reciprocal coupling over the
coarse scale's retained subspace. Let `P_s` be a fixed restriction/regrid
operator from scale `s` to `s+1`, let
`P_s^\dagger=W_s^{-1}P_s^H W_{s+1}` be its cell-volume-weighted adjoint, and
define

\[
w_D=\frac{1}{1+\phi^2},
\qquad
w_C=1+\phi^2.
\]

For `Z` equal to `D` or `C`, with its corresponding metric weight `w_Z`,

\[
E_{\mathrm{link},Z,s}
:=
\frac{w_Zg_{Z,s}}{2}
\left\|Z_{s+1}-P_sZ_s\right\|_{W_{s+1}}^2.
\]

The paired coordinate forces are

\[
F^{\mathrm{link}}_{Z,s}
:=
g_{Z,s}P_s^\dagger(Z_{s+1}-P_sZ_s),
\]

\[
F^{\mathrm{link}}_{Z,s+1}
:=
-g_{Z,s}(Z_{s+1}-P_sZ_s).
\]

The reciprocal link also carries a signed phase-charge current. With

\[
\Delta_{Z,s}=Z_{s+1}-P_sZ_s,
\]

define positive source-to-target transfer by

\[
\mathcal K_{Z,s\rightarrow s+1}
:=
-w_Zg_{Z,s}
\operatorname{Im}
\left\langle
P_sZ_s,\Delta_{Z,s}
\right\rangle_{W_{s+1}}.
\]

The link contribution to the integrated phase charges is exactly
`\dot Q_{Z,s}|link=-K_{Z,s->s+1}` and
`\dot Q_{Z,s+1}|link=+K_{Z,s->s+1}`. Their sum vanishes when the declared
weighted adjoint is used. For

\[
Q_{Z,s}:=
\left\langle
\mathbf 1,
w_Z\operatorname{Im}(Z_s^*V_{Z,s})
\right\rangle_{W_s},
\]

the discrete space-scale continuity receipt closes

\[
\frac{Q_{Z,s}^{n+1}-Q_{Z,s}^{n}}{h}
+\Phi^{\mathrm{spatial}}_{Z,s}
+\mathcal K_{Z,s\rightarrow s+1}
-\mathcal K_{Z,s-1\rightarrow s}
=
\mathcal R^{\mathrm{boundary}}_{Z,s}
+\mathcal R^{\mathrm{remap}}_{Z,s}
+\mathcal R^{\mathrm{composition}}_{Z,s}
+\mathcal R^{\mathrm{conversion}}_{Z,s}
+\mathcal R^{\mathrm{residual}}_{Z,s}
+\mathcal R^{\mathrm{retention}}_{Z,s}
+\mathcal R^{\mathrm{port}}_{Z,s}
+\mathcal R^{\mathrm{damping}}_{Z,s}
+r^{\mathrm{numeric}}_{Z,s}.
\]

For endpoint scales, absent links are exact zeros:
`\mathcal K_{Z,-1\rightarrow0}=0` and
`\mathcal K_{Z,S-1\rightarrow S}=0`. The scale-0 receipt owns only its outgoing
link row; the scale-`S-1` receipt owns only its incoming row. No out-of-range
operator is constructed.

Every term has one sign convention, unit, stage owner, quadrature, and
uncertainty bound in the profile. Link phase-charge current is distinct from
link energy, source/target link work, and the stored link potential; none may
substitute for another in a receipt. Summing the equation over scales cancels
all internal `K` terms. Link-off, adjoint-perturbed, phase-current-reversed,
and source/target-swapped fixtures verify the sign and cancellation.

The same required construction applies to both differential and carrier
coordinates; a profile may set a declared coupling coefficient to exact zero
only as an explicit diagnostic/control configuration, not as a silent
production fallback. Coupling is continuous and bidirectional over the
subspace represented by `P_s`. When `N_{s+1}<N_s`, `P_s` is rank-deficient and
its kernel does not directly reach the slower scale; the implementation never
calls that path full-spectrum. The profile records the singular spectrum,
effective rank, and nullspace of every `P_s`.

The total ledger includes link energy, source-scale power, and target-scale
power, so a target-scale gain is never called transfer without paired
source/link accounting. Slower scales have versioned lower characteristic
frequencies and damping. Memory is a metastable multiscale circulation: a fast
boundary disturbance decays, slower flow persists, and a measured slow-to-fast
path generates a successor prediction. No argmax binding, learned memory
matrix, replay buffer, or sidecar trace is part of memory.

## Scale-link and port scattering ledger

`QI-PORT-001`'s canonical schema and evidence object are owned by Part 9.
The field contract requires one `QiScatteringReceipt` for every declared
scale-link interface and external field port. This receipt is an accounting
view of the fixed operators; it does not add a boundary modality contract or
store a port history.
External characteristic amplitudes, modality packet
identity, and permeability fractions remain the fixed Part 5 boundary
contract. This section only joins those already-accounted external terms to
the field Hamiltonian and defines the additional reciprocal scale-link rows;
it does not introduce a second modality or port schema. For a
profile-oriented interface `p`, define positive work magnitudes by the
directed port-power quadrature:

\[
W_{\mathrm{incident}}^{p}
-W_{\mathrm{reflected}}^{p}
-W_{\mathrm{transmitted}}^{p}
-W_{\mathrm{absorbed}}^{p}
=r_{\mathrm{scat}}^{p}.
\]

`W_incident` is work arriving at the interface, `W_reflected` returns through
the same interface, `W_transmitted` crosses to the declared neighboring scale
or external system, and `W_absorbed` is work removed by the declared passive
port or interface loss. The receipt stores all four nonnegative magnitudes,
the signed source/target orientation, interval quadratures, and an
independently propagated interval for `r_scat`; it never reports only a net
work value. At an ingress boundary, transmitted work is the admitted field
work; at an egress boundary the orientation is reversed before the same
equation is applied. The existing signed `W_sensory`, `W_residual`,
`W_remap`, and `W_port reaction` rows are linked to these terms exactly once,
with no duplicate global source row.

For an internal `s\leftrightarrow s+1` interface, the source-to-target
transmitted term is paired with the target-to-source term and the two
scale-owned receipts share one interface identity. Their internal exchange
cancels in the summed scale ledger; any reflected or absorbed work remains
on the side whose operator owns it. For an external port, the receipt binds
the incident/reflected/transmitted/absorbed terms to the fixed boundary
descriptor and its metric-adjoint reaction. Missing orientation, an
unclosed interval, or a scale gain without the paired interface receipt
rejects the candidate. W6T/G6T must reproduce these ledgers on link-off,
source/target-swapped, reflection-only, transmission-only, and matched-work
fixtures at both scale and external ports.

`QiScatteringReceipt` records the `scale_geometry_mode`, profile/operator
hashes, port and interface identifiers, active rank/nullspace identity,
stage and exact tick interval, four work terms, residual interval, and
pre/post field-state hashes. It is derived per transaction and is not
checkpointed as adaptive memory. No scattering term may be substituted for
link potential, phase-charge current, damping, or conversion work.

