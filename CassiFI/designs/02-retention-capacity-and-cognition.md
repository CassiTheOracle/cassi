# Retention, capacity, cognition, and release criteria

> CassiFI implementation plan, Part 2. [Previous](./01-field-physics.md) · [Index](../README.md) · [Next](./03-architecture-profiles-and-schemas.md)

## Fading and topological field retention

The profile distinguishes two field-memory laws. They have different
`state_contract_sha256` identities and cannot share a checkpoint:

- **Fading retention — `fading-v1`.** The ordinary slow-scale carrier,
  damping, and reciprocal links provide a finite-horizon fading trace.
  `U_topo=0`. Fading retention is a required matched comparator and calibration
  law only.
- **Topological retention — `topological-v1`.** The release endpoint adds one
  fixed, bounded, U(1)-invariant slow-scale potential to the existing field
  Hamiltonian. Topological retention is the production candidate and becomes
  an adopted behavioral memory law only after the W10R evidence below passes.
  A failed or unavailable topological-retention profile blocks release; the
  runtime never falls back to fading retention.

`QI-RET-001` separates the physical core from the behavioral claim. W4R
installs the topological-retention Hamiltonian and torus-topology core immediately after W4
and before W5. This section's `U_topo`, amplitude/branch guards, sector algebra,
barrier path proof, and conservative force are the early core; they are
required for the W5 conversion and execution ledgers but do not by
themselves establish retention, recall, or learning. W10R is the later
behavioral-retention/consolidation package. It consumes the core's receipts
and measures whether field trajectories actually acquire, retain, overwrite,
recover, and causally return.

Both packages operate on the existing slow-scale coordinates. W4R and W10R
may not allocate a topology key, basin table, cue store, replay buffer,
optimizer, or any other persistent adaptive object.


Topological retention adds no state slot. Let `s_star=S-1`, let

\[
\widetilde D=\sqrt{w_D}D_{s_\star},
\qquad
\widetilde C=\sqrt{w_C}C_{s_\star},
\]

and choose immutable real `a_topo,b_topo` with
`a_topo^2+b_topo^2=1`:

\[
\psi_{\mathrm{topo}}=a_{\mathrm{topo}}\widetilde D+b_{\mathrm{topo}}\widetilde C,
\qquad
\chi_{\mathrm{topo}}=-b_{\mathrm{topo}}\widetilde D+a_{\mathrm{topo}}\widetilde C.
\]

The same weighted orthogonal rotation defines the velocities:

\[
\widetilde V_D=\sqrt{w_D}V_{D,s_\star},
\qquad
\widetilde V_C=\sqrt{w_C}V_{C,s_\star},
\]

\[
V_{\psi}=a_{\mathrm{topo}}\widetilde V_D+b_{\mathrm{topo}}\widetilde V_C,
\qquad
V_{\chi}=-b_{\mathrm{topo}}\widetilde V_D+a_{\mathrm{topo}}\widetilde V_C.
\]

The production profile fixes the carrier-ring specialization `a_topo=0,b_topo=1`.
The orthogonal coordinate `chi_topo` remains ordinary field dynamics. This
metric-orthogonal change of coordinates preserves

\[
|\psi_{\mathrm{topo}}|^2+|\chi_{\mathrm{topo}}|^2
=w_D|D_{s_\star}|^2+w_C|C_{s_\star}|^2.
\]

On the declared periodic two-dimensional active sheet, define

\[
\widehat\psi_i=
\frac{\psi_{\mathrm{topo},i}}
{\sqrt{|\psi_{\mathrm{topo},i}|^2+r_{\mathrm{core}}^2}},
\qquad r_{\mathrm{core}}>0,
\]

and let `e=(i,j)` range over the profile's oriented periodic edge registry with
fixed positive weights `omega_e`. With
`V_star=1^T W_star 1`, the topological-retention potential is

\[
\begin{aligned}
U_{\mathrm{topo}}=E_{\mathrm{topo}}\Bigg[
&\lambda_{\mathrm{ph}}
\frac{\sum_e\omega_e
\left(1-\operatorname{Re}(\widehat\psi_i^*\widehat\psi_j)\right)}
{\sum_e\omega_e}\\
&+\lambda_{\mathrm{core}}
\frac{\sum_i(W_\star)_{ii}
\left(
\frac{|\psi_{\mathrm{topo},i}|^2-\rho_{\mathrm{ring}}^2}
{|\psi_{\mathrm{topo},i}|^2+\rho_{\mathrm{ring}}^2}
\right)^2}
{V_\star}
\Bigg],
\end{aligned}
\]

A topological-retention profile is invalid unless `N_x,N_y>=2`, `W_star` has strictly
positive diagonal and `V_star>0`, the oriented edge registry and the registered
torus-cycle/plaquette sets are nonempty, every `omega_e>0`,
`sum_e omega_e>0`, and `0<rho_topo<=rho_ring`. These predicates are checked before
forming any quotient, maximum, phase, or force.

where `E_topo>0`, `lambda_ph,lambda_core>0`, and `rho_ring>0` are immutable profile
values with declared units and provenance. The law is smooth, bounded,
U(1)-invariant, and satisfies

\[
0\leq U_{\mathrm{topo}}\leq
E_{\mathrm{topo}}(2\lambda_{\mathrm{ph}}+\lambda_{\mathrm{core}}).
\]

Before any `Arg` is evaluated, each endpoint field value is represented by an
independently reproduced complex interval disk with radius
`u_psi,i>=0`. Every topology fixture and runtime endpoint requires

\[
0<\delta_{\mathrm{topo}}<\pi,\qquad
\underline{\rho}_i
:=|\psi_{\mathrm{topo},i}|-u_{\psi,i}
\geq\rho_{\mathrm{topo}}>0.
\]

Only after those disks exclude zero may an edge phase be enclosed. For each
oriented edge \(i\to j\), let

\[
\delta_{ij}
:=\operatorname{Arg}\!\left(\psi_{\mathrm{topo},i}^{*}\psi_{\mathrm{topo},j}\right)
\in(-\pi,\pi]
\]

and let `u_delta,ij` be the independently reproduced half-width of a verified
interval enclosure for that principal phase. Endpoint acceptance requires

\[
|\delta_{ij}|+u_{\delta,ij}
\leq\pi-\delta_{\mathrm{topo}}
\]

for every used edge. On the periodic slow sheet,

\[
\tilde n_{\mathrm{topo},x}(y)
:=\frac{1}{2\pi}\sum_x \delta^x_{x,y},\qquad
\tilde n_{\mathrm{topo},y}(x)
:=\frac{1}{2\pi}\sum_y \delta^y_{x,y},
\]

\[
\tilde p_{\mathrm{topo}}(x,y)
=\frac{1}{2\pi}
\left(
\delta^x_{x,y}
+\delta^y_{x+1,y}
-\delta^x_{x,y+1}
-\delta^y_{x,y}
\right).
\]

Their interval radii are the corresponding sums of edge half-widths divided
by \(2\pi\). Each raw value is accepted only when it has a unique integer
\(n=\operatorname{round}(\tilde n)\) or
\(p=\operatorname{round}(\tilde p)\) satisfying

\[
|\tilde n-n|+u_{\tilde n}
\leq\Delta_{\mathrm{topo,int}}<\frac12,\qquad
|\tilde p-p|+u_{\tilde p}
\leq\Delta_{\mathrm{topo,int}}<\frac12.
\]

The topological-retention sector is the full vector

\[
\mathcal T_{\mathrm{topo}}
:=\left(
\{n_{\mathrm{topo},x}(y)\}_{y=0}^{L_y-1},
\{n_{\mathrm{topo},y}(x)\}_{x=0}^{L_x-1},
\{p_{\mathrm{topo}}(x,y)\}_{x,y}
\right),
\]

not a scalar sum. Vector equality is elementwise after the complete
amplitude/branch/integer guard. Raw values, interval radii, rounded integers,
minimum amplitude lower bound, minimum branch-margin lower bound, and the full
sector vector are retained in the topology receipt.

### Torus topology algebra in the early core

The cycle and plaquette integers are constrained by the periodic edge
algebra; they are not independently selectable labels. Indices are taken
modulo `L_x,L_y`, and the accepted integer vector must satisfy

\[
n_{\mathrm{topo},x}(y)-n_{\mathrm{topo},x}(y+1)
:=\sum_x p_{\mathrm{topo}}(x,y),
\qquad
n_{\mathrm{topo},y}(x+1)-n_{\mathrm{topo},y}(x)
:=\sum_y p_{\mathrm{topo}}(x,y),
\]

\[
\sum_{x,y}p_{\mathrm{topo}}(x,y)=0.
\]

The verifier encloses both sides from the edge-phase intervals before
rounding and requires exact integer equality with a margin strictly larger
than the propagated interval radius. A cycle/plaquette mismatch, a
non-cancelling total plaquette charge, or a branch guard that cannot decide
the equality rejects the endpoint even when each scalar round operation would
appear valid. These algebra, amplitude, and branch predicates are part of the
W4R topological-retention core and are checked at every accepted endpoint and every
positive-duration path subdivision. They do not create a persistent topology
record; `\mathcal T_{\mathrm{topo}}` is recomputed from the existing field bytes.
### Resolution-aware topological-retention topology codebook

For the slow sheet \(s_\star=S-1\), set
\[
L_x:=N_{x,s_\star},\qquad L_y:=N_{y,s_\star},
\qquad N_\star:=L_xL_y.
\]
Here \(L_x,L_y\) are site counts used by the torus index algebra (the
physical extents remain \(L_{x,s_\star},L_{y,s_\star}\) from Part 1), and
\(N_\star\) is the number of slow-sheet active sites. Define the
resolution-specific realizable sector universe
\[
\mathscr C_{\mathrm{topo,real}}^{(L_x,L_y)}
:=
\left\{
\tau\in
\mathbb Z^{L_y}\times\mathbb Z^{L_x}\times\mathbb Z^{L_xL_y}
\ \middle|\
\begin{array}{l}
\exists\ \psi\in\mathbb C^{N_\star}\text{ on the selected slow sheet}:\\
\mathcal T_{\mathrm{topo}}(\psi)=\tau,\ \psi\text{ passes the amplitude, principal-branch,}\\
\text{torus-algebra, and selected-resolution operator guards}
\right\}.
\]
The first two integer factors in this product are the two cycle-vector
families and the third is the plaquette-vector family; \(\mathbb Z\) denotes
the integers. The witness \(\psi\) is an offline field at exactly the
selected \((L_x,L_y)\) resolution, with the independently reproduced
endpoint disks and edge-phase intervals required above. Thus an integer
vector is not a realizable codeword merely because it satisfies a count or
looks distinct.

The immutable registered topology codebook is a finite, duplicate-free
subset
\[
\varnothing\ne
\mathscr C_{\mathrm{topo}}^{(L_x,L_y)}
\subseteq
\mathscr C_{\mathrm{topo,real}}^{(L_x,L_y)}.
\]
Every codeword has a distinct full vector \(\tau=\mathcal T_{\mathrm{topo}}(\psi)\), a
profile-certificate witness hash, and an exact-resolution guard receipt.
The branch guard also imposes the necessary resolution-dependent bounds
\[
|n_{\mathrm{topo},x}(y)|
\leq\left\lfloor\frac{L_x(\pi-\delta_{\mathrm{topo}})}{2\pi}\right\rfloor,
\qquad
|n_{\mathrm{topo},y}(x)|
\leq\left\lfloor\frac{L_y(\pi-\delta_{\mathrm{topo}})}{2\pi}\right\rfloor,
\qquad
|p_{\mathrm{topo}}(x,y)|
\leq\left\lfloor\frac{4(\pi-\delta_{\mathrm{topo}})}{2\pi}\right\rfloor,
\]
where \(\lfloor\cdot\rfloor\) is the floor function. These are necessary
filters, not substitutes for the field witness and full torus-algebra proof.
The codebook identity binds \((L_x,L_y)\), the selected \(dx,dy\), positive
cell metric \(W_\star\), periodic FFT/operator identity, amplitude/branch
guards, and the ordered edge registry. A spatial resolution, oversampling
factor, metric, or operator change therefore requires a new codebook and a
new `cassi.qi-flow-capacity-ladder.v1` identity; codeword counts cannot be
copied from one resolution to another.

Here \(\star'\) denotes the target resolution with site counts
\(L_x',L_y'\), and \(I_{\star\to\star'}\) is the declared Part 1
periodic-band resolution map, including its metric adjoint and Nyquist
convention. Since the full indexed sector vectors have different dimensions
when \((L_x,L_y)\ne(L_x',L_y')\), they are never compared by untyped literal
equality.

The target profile may instead register a finite,
content-addressed codebook transport
\[
\Pi_{\star\to\star'}:
\mathscr C_{\mathrm{topo,eligible}}^{(L_x,L_y)}
\longrightarrow
\mathscr C_{\mathrm{topo}}^{(L_x',L_y')},
\]
with its source/target dimensions, index convention, complete mapped-codeword
table, target torus-algebra checks, and independent witness hashes. It is not a
new field table or adaptive state: it is immutable profile/evidence metadata.
For every eligible witness \(\psi\), the guard must prove the typed relation
\[
\mathcal T_{\mathrm{topo}}^{(L_x',L_y')}
\!\left(I_{\star\to\star'}\psi\right)

=
\Pi_{\star\to\star'}
\!\left(\mathcal T_{\mathrm{topo}}^{(L_x,L_y)}(\psi)\right)
\in
\mathscr C_{\mathrm{topo}}^{(L_x',L_y')}.
\]
The reverse map, when a bidirectional preservation claim is made, requires its
own registered transport and witnesses; no inverse is implied by
prolongation/restriction. Otherwise the target-resolution codebook is
regenerated and the sector is not assumed to survive. This contract describes
only the topology vector and selected field resolution; it does not redeclare
a sensory, body, action, or text packet schema and it never allocates a
topology table or key in `QiFieldState.field`.

For every zero-clock transition \(z\) other than the separately authorized
retention reset, let \(X_z\) be its candidate successor and \(X\) its
predecessor. The immutable operator/body descriptor declares an exact
invertible action \(\Pi_z\) on the complete ordered sector vector.
Source, conversion, reaction, and genuinely index-preserving coordinate maps
use \(\Pi_z=I\). A periodic integer translation is an exact torus automorphism
but is generally **not** index-preserving: for the declared pullback
\[
X_z(x,y)=X(x-\Delta_x,y-\Delta_y)
\]
with indices modulo \(L_x,L_y\), its required sector action is
\[
\begin{aligned}
\left[\Pi_{\Delta_x,\Delta_y}\mathcal T_{\mathrm{topo}}\right]_{n_x}(y)
&=n_{\mathrm{topo},x}(y-\Delta_y),\\
\left[\Pi_{\Delta_x,\Delta_y}\mathcal T_{\mathrm{topo}}\right]_{n_y}(x)
&=n_{\mathrm{topo},y}(x-\Delta_x),\\
\left[\Pi_{\Delta_x,\Delta_y}\mathcal T_{\mathrm{topo}}\right]_{p}(x,y)
&=p_{\mathrm{topo}}(x-\Delta_x,y-\Delta_y).
\end{aligned}
\]
The descriptor records this pullback convention and its exact inverse
\(\Pi_{-\Delta_x,-\Delta_y}\). Any other nonidentity \(\Pi_z\) is admissible
only for a declared exact torus automorphism or signed cycle/plaquette
permutation derived from the coordinate relabel itself, with an exact inverse
and codebook closure.
Topology preservation is then the transported obligation
\[
\Delta t(z)=0
\quad\Longrightarrow\quad
\mathcal T_{\mathrm{topo}}(X_z)=\Pi_z\mathcal T_{\mathrm{topo}}(X),
\qquad
\Pi_z\mathscr C_{\mathrm{topo}}^{(L_x,L_y)}
=\mathscr C_{\mathrm{topo}}^{(L_x,L_y)}.
\]
An interpolated remap whose amplitude/branch enclosure cannot prove this
identity is rejected. The reset is never a codebook witness, acquisition
trajectory, or capacity member; its separate authorization and
`cassi.qi-flow-retention-reset.v1` receipt remain the only exception.



The accepted split trajectory is part of the sector proof. Every continuous
substage is subdivided under profile-frozen derivative/interval bounds; every
zero-clock map is a distinct path point and is never interpolated as positive
time. Except for an explicit retention reset, each zero-clock map must preserve
the complete valid endpoint sector under its declared \(\Pi_z\) or the
candidate is rejected. An
ordinary same-sector step must enclose the amplitude floor and branch margin
over every positive-duration subdivision. If an enclosure touches zero or the
principal branch cut, the ordinary step is rejected rather than inferred to
preserve topology. A candidate with different valid endpoint sectors is
classified only as a timed `phase_slip` when deterministic interval refinement
isolates its guard crossing inside a positive-duration continuous substage; its
complete path evidence is retained.

For every accepted path \(\Gamma=\{X(\tau):0\leq\tau\leq1\}\), the receipt
contains a certified interval \([B_{\Gamma,\mathrm{topo}}^-,B_{\Gamma,\mathrm{topo}}^+]\) enclosing

\[
B_{\Gamma,\mathrm{topo}}
=\max_{\tau\in[0,1]}
\left[H(X(\tau))-H(X(0))\right],
\]

The accumulated path-work term has energy units and is exactly

\[
W_{\mathrm{admitted}}(0,\tau)
:=W_{\mathrm{sensory}}(0,\tau)
+W_{\mathrm{residual}}(0,\tau)
+W_{\mathrm{remap}}(0,\tau)
+W_{\mathrm{port\ reaction}}(0,\tau),
\]

using the same signed source rows as the per-step ledger. At every path
subdivision the receipt closes

\[
H(X(\tau))-H(X(0))
=W_{\mathrm{admitted}}(0,\tau)
+W_{\mathrm{conversion}}(0,\tau)
-Q_{\mathrm{damp}}(0,\tau)
+R_H(\tau).
\]

`Q_conversion=-W_conversion` remains the resolved-dissipation classification
and is never subtracted again: `W_conversion` is the sole conversion term in
both this path identity and the global ledger.

The selected profile freezes
`Delta_H_topo_min > barrier_uncertainty_guard > 0`; registered calibration
fixtures must independently reproduce that threshold with numerical
uncertainty strictly below `barrier_uncertainty_guard`. A sector-changing
endpoint is valid only when the timed phase-slip path has
`B_Gamma^- >= Delta_H_topo_min + barrier_uncertainty_guard` and every
path-ledger residual is within tolerance. A registered below-barrier control
with `B_Gamma^+ <= Delta_H_topo_min - barrier_uncertainty_guard` must preserve
the complete sector vector. Thus
“above barrier” is a full-Hamiltonian, work-funded path claim rather than a
label inferred from changed endpoint integers.

Explicit retention reset is a separate controller transition:

\[
\mathcal Z_{\mathrm{topo}}:
\quad
\psi_{\mathrm{topo}}\mapsto\rho_{\mathrm{ring}} e^{i\theta_0},
\qquad
V_{\psi,\mathrm{topo}}\mapsto0,
\]

with \(\chi_{\mathrm{topo}},V_{\chi,\mathrm{topo}}\) preserved. It is accepted only from an authenticated,
explicit operator request naming the expected session head and reset reason;
ordinary stepping, failure recovery, profile mismatch, and startup can never
invoke it. The reset target must pass the same amplitude/branch/integer guard.
The preflight computes

\[
W_{\mathrm{reset}}
=H(X_{\mathrm{after}})
-H(X_{\mathrm{before}}),
\qquad
\Delta Q_{Z,\mathrm{reset}}
=Q_Z(X_{\mathrm{after}})
-Q_Z(X_{\mathrm{before}}).
\]

`cassi.qi-flow-retention-reset.v1` records authorization identity, predecessor,
old/new full sector vectors, old/new state hashes, signed controller work
`W_reset`, the phase-charge impulse `Delta_Q_Z,reset`, the full-Hamiltonian
terms, and topology proofs. It is a zero-clock transition edge between
positive-duration steps: the cumulative session ledger includes its signed
controller work and charge impulse, while no per-step rate divides it by a
fictional \(h\). Apply is atomic and only after finite/budget/profile checks;
any failure leaves the predecessor state and receipt head unchanged.

topological-retention validation measures source-free residence, below-barrier perturbation,
phase-slip acquisition, winding and circulation diversity, cue-specific
slow-to-fast return, held-out successor effect, interference/recovery,
work-normalized retention, explicit reset, and exact checkpoint restart.
Matched fading-retention, equal-work one-shot, shuffled-order, phase-scrambled,
matched-energy/opposite-current, link-off, and wrong-cue controls are required.
Neither slow amplitude, `epsilon2_ema`, checkpoint persistence by itself, nor a
single frozen sector satisfies the topological-retention claim.

### W10R behavioral tiers and topological-retention capacity

`QI-RET-002` requires two memory tiers with one field representation. **Tier
1, within-sector analog acquisition**, changes the amplitudes, phases,
velocities, and slow circulation continuously while the complete
`\mathcal T_topo` remains fixed. Its evidence is a cue-specific trajectory and
held-out successor effect along one exact-controller-reachable trajectory; it
is not a topology integer and not a copied analog trace. **Tier 2, topological
consolidation** is a work-funded transition between distinct valid
`\mathcal T_topo` vectors through the guarded phase-slip path and its
full-Hamiltonian barrier. It is
not inferred from a slow amplitude, a checkpoint hash, or an endpoint label.
Both tiers use only `QiFieldState.field`; no tier allocates a key, table,
buffer, or additional persistent state.

`QI-CAP-001` is the single owner definition for topological-retention capacity in Part 2.
W6A, W6B, and W10R implement its measurements, and G6A, G6B, and G6C
consume the resulting evidence. Capacity is generated by the frozen
controller, not by a static basin label or an arbitrary continuous path.

Let \(\mathfrak G_{\mathrm{ctrl}}\) be the frozen controller grammar: the
profile-selected `advance()` split order, exact rational clock, source and
boundary descriptor order, body/efference rules, admissible packet grammar,
and all profile/operator identities. Each immutable grammar-valid drive bundle
\(d_j\) contains its canonical, hashed ordered zero-clock schedule
\[
\zeta_j=(z_{j,1},\ldots,z_{j,m_j}),
\]
where every \(z_{j,r}\) names its registered map descriptor, exact arguments,
declared \(\Pi_{j,r}\), and position in the staged `advance()` order. The
controller rejects a drive bundle if the emitted zero-clock receipts differ
from \(\zeta_j\) in identity, arguments, order, or declared transport.

For a committed predecessor \(X_0\) at physical clock \(t_0\), an exact
rational physical horizon \(\ell\in\mathbb Q_{>0}\), and a nonnegative work
budget \(\mathcal W\geq0\), define the accepted script set
\[
\begin{aligned}
\Sigma_{\mathfrak G}^{\Phi}(X_0;t_0,\ell,\mathcal W)
:=\Bigl\{\sigma={}&((d_j,h_j,\zeta_j))_{j=0}^{J-1}\ \Bigm|\ 
J\in\mathbb N_{>0},\ h_j\in\mathcal H_{\mathrm{runtime}},\\
&\sum_{j=0}^{J-1}h_j=\ell,\quad
t_j=t_0+\sum_{m<j}h_m,\quad
X_{j+1}=\operatorname{advance}_{\mathfrak G_{\mathrm{ctrl}}}
(X_j;d_j,h_j),\\
&X_j\text{ and every }X_{j+1}\text{ are committed field states, every
advance receipt passes,}\\
&\text{each \(d_j,\zeta_j\) is immutable, grammar-valid, receipt-matched, and
does not invoke }\texttt{retention\_reset}\Bigr\}.
\end{aligned}
\]
Here \(J\) is the positive integer number of advances, \(h_j\) is a positive
physical duration, \(t_j\) is the exact rational clock frontier, \(d_j\) is a
drive bundle with its zero-clock schedule \(\zeta_j\), and
\(\operatorname{advance}_{\mathfrak G_{\mathrm{ctrl}}}\) is the canonical
`QiFieldController.advance()` call. The terminal state is
\[
\Phi_{\ell}^{\mathfrak G}(X_0;\sigma):=X_J,\qquad
t_J=t_0+\ell.
\]

Flatten the receipt-matched schedules in canonical lexicographic order
\[
(z_1,\ldots,z_m)
:=(z_{0,1},\ldots,z_{0,m_0},z_{1,1},\ldots,z_{J-1,m_{J-1}}),
\]
omitting empty schedules. Define
\[
\Pi_\sigma:=\Pi_{z_m}\cdots\Pi_{z_1},
\qquad
\widetilde{\mathcal T}_{\mathrm{topo}}(X_J;\sigma)
:=\Pi_\sigma^{-1}\mathcal T_{\mathrm{topo}}(X_J),
\]
with \(\Pi_\sigma=I\) when no such map occurs. This transported endpoint is
derived entirely from immutable transition receipts and allocates no field
or checkpoint state. It prevents a body-coordinate relabel from being counted
as acquisition; only a sector change remaining after inverse transport is a
physical topological-retention change relative to \(X_0\).
The superscript \(\Phi\) therefore denotes only trajectories generated by
the exact controller calls above; a hand-written ODE path, interpolation,
reset edge, failed candidate, or arbitrary endpoint is not in this set.

For each advance \(j\), let \(\mathcal I_j\) be its registered physical
source events. Every event selects exactly one nonnegative **interval** budget
channel. Let
\([w_{j,a}^{\mathrm{inc},-},w_{j,a}^{\mathrm{inc},+}]\) be the certified
incident-work interval for a characteristic-port event, and let
\([W_{j,a}^{\mathrm{source},-},W_{j,a}^{\mathrm{source},+}]\) be the signed
source-work interval for a registered nonport source. Define
\[
\mathbf w_{j,a}^{+}:=
\begin{cases}
[w_{j,a}^{\mathrm{inc},-},w_{j,a}^{\mathrm{inc},+}],&
\text{for a port event, with \(0\leq w_{j,a}^{\mathrm{inc},-}\)},\\
[\max(W_{j,a}^{\mathrm{source},-},0),
\max(W_{j,a}^{\mathrm{source},+},0)],&
\text{for a nonport source event}.
\end{cases}
\]
The second row is the monotone interval enclosure of
\(\max(W_{j,a}^{\mathrm{source}},0)\). An external port event never
contributes both its incident row and its derived transmitted/source row.
Using interval Minkowski addition, define
\[
\mathbf{\mathcal W}_{\mathrm{source}}^{+}(\sigma)
:=
\sum_{j=0}^{J-1}\sum_{a\in\mathcal I_j}\mathbf w_{j,a}^{+}
=
[\underline{\mathcal W}_{\mathrm{source}}^{+}(\sigma),
\overline{\mathcal W}_{\mathrm{source}}^{+}(\sigma)]
\subseteq[0,\infty).
\]
Membership in \(\Sigma_{\mathfrak G}^{\Phi}\) additionally requires
\[
\overline{\mathcal W}_{\mathrm{source}}^{+}(\sigma)\leq\mathcal W,
\qquad
\widetilde{\mathcal T}_{\mathrm{topo}}(X_J;\sigma)\ne\mathcal T_{\mathrm{topo}}(X_0)
\Longrightarrow
\underline{\mathcal W}_{\mathrm{source}}^{+}(\sigma)>0.
\]
Thus signed net work, a negative admitted-work row, conversion dissipation,
reflection, or a reset can never refund the nonnegative source budget. An
interval crossing zero cannot establish a new sector's positive-work
obligation; a source-free continuation is an admitted control only when its
full accumulated interval is exactly \([0,0]\).

The controller-generated reachable topological-retention sector set is
\[
\mathcal R_{\mathrm{topo}}^\Phi(X_0;t_0,\ell,\mathcal W)
:=
\left\{
\widetilde{\mathcal T}_{\mathrm{topo}}\!\left(
\Phi_{\ell}^{\mathfrak G}(X_0;\sigma);\sigma
\right)
\ \middle|\
\sigma\in\Sigma_{\mathfrak G}^{\Phi}(X_0;t_0,\ell,\mathcal W),\
\widetilde{\mathcal T}_{\mathrm{topo}}\!\left(
\Phi_{\ell}^{\mathfrak G}(X_0;\sigma);\sigma
\right)\in\mathscr C_{\mathrm{topo}}^{(L_x,L_y)}
\right\}.
\]
Reset transitions are excluded from \(\Sigma_{\mathfrak G}^{\Phi}\) and
therefore from \(\mathcal R_{\mathrm{topo}}^\Phi\); `retention_reset` is a separately
authorized destructive reset/calibration operation, never acquisition,
selective forgetting, or capacity. All
positive-duration barrier subdivisions are internal evidence for one
accepted `advance()` script and cannot add trajectories or sectors to this
set.

### QI-CAP-001 capacity ladder

The immutable resolution-specific codebook is the geometric universe:
\[
\mathscr C_{\mathrm{geom}}:=\mathscr C_{\mathrm{topo}}^{(L_x,L_y)},\qquad
\mathscr C_{\mathrm{reach}}(X_0;t_0,\ell,\mathcal W)
:=\mathcal R_{\mathrm{topo}}^\Phi(X_0;t_0,\ell,\mathcal W).
\]
For any registered paired probe \(r\) and exact rational physical delay
\(\tau>0\), let \(Y_r^\tau(c)\) be its declared scalar or vector
consequence for codeword \(c\); for a vector, \(|\cdot|\) below is the
profile-frozen uncertainty-weighted norm, and for a scalar it is ordinary
absolute value. Let
\(\widehat\Delta_r^\tau(c)\) be the measured treatment-minus-matched-null
difference, \(\mathcal U_r^\tau(c)\geq0\) its independently propagated
interval half-width, and \(\Delta_{r,\mathrm{null}}^\tau>0\) its frozen
null threshold. Let \(\widehat\Delta_{r,\mathrm{null}}^\tau\) and
\(\mathcal U_{r,\mathrm{null}}^\tau\) be the corresponding null-arm
estimate and interval. A consequence clears the uncertainty/null guard
only when
\[
\operatorname{clear}_r^\tau(c)
\Longleftrightarrow
\left[
\left|\widehat\Delta_r^\tau(c)\right|-\mathcal U_r^\tau(c)
>\Delta_{r,\mathrm{null}}^\tau
\right]
\land
\left[
\left|\widehat\Delta_{r,\mathrm{null}}^\tau\right|
+\mathcal U_{r,\mathrm{null}}^\tau
\leq\Delta_{r,\mathrm{null}}^\tau
\right],
\]
and the observed direction/identity is the preregistered one. An unresolved
interval, a null interval crossing the threshold, or an effect at or below
the threshold is not a causal consequence.

Let \(\mathcal P_{\mathrm{obs}}\) be the finite registered field/probe
discrimination set and \(\mathcal P_{\mathrm{use}}\) the registered
boundary, text, action, or world-consequence set (both use the fixed
descriptors and no-peek runtime). Let \(\mathcal P_{\mathrm{ret}}\) be the
registered source-free residence tests with exact rational residence
horizons, and let \(\mathcal P_{\mathrm{reuse}}\) be the held-out cue and
successor tests. The complete ladder is
\[
\begin{aligned}
\mathscr C_{\mathrm{obs}}
&:=\{c\in\mathscr C_{\mathrm{reach}}:
\exists(r,\tau)\in\mathcal P_{\mathrm{obs}}\ 
\operatorname{clear}_r^\tau(c)\},\\
\mathscr C_{\mathrm{use}}
&:=\{c\in\mathscr C_{\mathrm{obs}}:
\exists(r,\tau)\in\mathcal P_{\mathrm{use}}\ 
\operatorname{clear}_r^\tau(c)\},\\
\mathscr C_{\mathrm{ret}}
&:=\{c\in\mathscr C_{\mathrm{use}}:
\text{every registered residence test in }\mathcal P_{\mathrm{ret}}
\text{ preserves }c\text{ and its analog response within its
interval guard}\},\\
\mathscr C_{\mathrm{reuse}}
&:=\{c\in\mathscr C_{\mathrm{ret}}:
\exists(r,\tau)\in\mathcal P_{\mathrm{reuse}}\ 
\operatorname{clear}_r^\tau(c)\text{ after a held-out cue and
registered delay}\}.
\end{aligned}
\]
Here “preserves” means that the complete sector vector and the registered
within-sector response both remain in their preregistered intervals; it is
not a checkpoint-hash or slow-amplitude test. The capacities are the
cardinalities
\[
\begin{gathered}
C_{\mathrm{geom}}:=|\mathscr C_{\mathrm{geom}}|,\qquad
C_{\mathrm{reach}}:=|\mathscr C_{\mathrm{reach}}|,\qquad
C_{\mathrm{obs}}:=|\mathscr C_{\mathrm{obs}}|,\\
C_{\mathrm{use}}:=|\mathscr C_{\mathrm{use}}|,\qquad
C_{\mathrm{ret}}:=|\mathscr C_{\mathrm{ret}}|,\qquad
C_{\mathrm{reuse}}:=|\mathscr C_{\mathrm{reuse}}|,
\end{gathered}
\]
with the required inclusions
\[
\mathscr C_{\mathrm{reuse}}\subseteq\mathscr C_{\mathrm{ret}}
\subseteq\mathscr C_{\mathrm{use}}\subseteq\mathscr C_{\mathrm{obs}}
\subseteq\mathscr C_{\mathrm{reach}}\subseteq\mathscr C_{\mathrm{geom}}.
\]
The receipt also reports interval-certified effective rank and conditioning
of the finite within-sector analog-response matrix at each rung. That rank
is a measured property of the registered perturbations; it is neither
automatically \(260\) nor automatically the alphabet size, and it is not
added to the discrete codeword cardinality.

The canonical `cassi.qi-flow-capacity-ladder.v1` receipt contains the
resolution-bound codebook and witness hashes, exact controller grammar and
clock identity, \(\mathcal R_{\mathrm{topo}}^\Phi\) script/predecessor hashes, every ordered
zero-clock \(\Pi_z\), composed \(\Pi_\sigma\), raw and inverse-transported
endpoint sectors, the nonnegative single-charge source budget, all six sets
and capacities, analog rank intervals, probe collisions/nullspaces, and the
uncertainty/null margins. Each delayed
held-out consequence additionally emits
`cassi.qi-flow-delayed-influence.v1`; explicit forgetting emits
`cassi.qi-flow-forgetting.v1` and is never counted in any rung. For exact
rational \(\ell_k>0\) and nonnegative \(\mathcal W_k\), saturation is a
statement about the interval-bounded curve
\(C_{\mathrm{reach}}(X_0;t_0,\ell_k,\mathcal W_k)\): it passes only when
the registered additional-work scripts produce no new codeword under their
upper/lower intervals. Crossing an amplitude, work, codebook, or
controller-reachable cap rejects with `topology_saturation`; it is never
clipped, wrapped to an old sector, or silently counted as acquisition.

Overwrite is a paired acquisition experiment. Starting from a state with
sector/analog target `A`, an equal-work new experience `B` is applied with
fixed whole-episode bytes and a held-out cue. The receipt proves the
old/new sector vectors, path barrier and work, the within-sector response
change, and the held-out successor advantage for `B`; it also reports the
remaining response to `A` and the shuffled, one-shot, phase-scrambled, and
equal-energy controls. A claimed overwrite without a changed field
trajectory and a changed held-out consequence is rejected; no old cue index
or overwrite log may be retained in field or checkpoint state (receipts may
retain the experiment's hashed evidence).

Recovery is measured after the registered phase/current perturbation, bounded
noise, temporary boundary loss, rejected candidate, and exact checkpoint
restart controls. The receipt records the first horizon at which the full
sector vector, torus-algebra margins, and within-sector analog response
return to their pre-perturbation intervals, or records certified failure.
Recovery may not invoke \(\mathcal Z_{\mathrm{topo}}\) or selective forgetting. The
separately authorized zero-clock reset above is calibration only and never
recovery. W10R owns these behavioral
measurements and consolidation claims; W4R owns only the physical topological-retention
core and its topology/work proofs.


## Dynamical capacity, reachability, and observability

State size is not treated as usable intelligence capacity. For every declared
boundary-to-output or boundary-to-action path, the implementation measures the
finite-horizon map from admitted boundary work into field modes and back to a
committed consequence.

The capacity audit records:

- boundary-to-fast, fast-to-slow, slow-to-fast, and fast-to-output impulse
  responses over declared horizons;
- effective reachability and observability rank and singular-value spectra;
- dark modes, scale-link nullspaces, and probe/codebook collisions after every
  restriction/prolongation path;
- finite-time perturbation growth by scale, distinguishing rapid collapse,
  useful persistence, and unstable sensitivity;
- retention-versus-discrimination curves and the longest useful causal delay;
- candidate/action/text decision margins relative to propagated numerical
  uncertainty.

A modality or memory path is not complete merely because its source changes the
state. It must excite a mode that survives the required horizon and causally
returns to the registered output, residual, or action. These audits guide
capacity and coefficient design and become regression checks for released
profiles.

### Boundary-to-boundary causal transfer

Capacity is measured through the nonlinear controller, not inferred from a
static boundary matrix. For a fixed committed predecessor state \(X\), source
descriptor \(q\), target descriptor \(r\), registered source fixture
\(\delta\), and exact rational physical horizon
\(\ell\in\mathbb Q_{>0}\), define the finite intervention response
\[
\mathcal T_{\!r\leftarrow q}^{X,\ell}(\delta)
:=
B_r\!\left[
\Phi_{\ell}^{\mathfrak G}(X;\sigma_{q,\delta})
-\Phi_{\ell}^{\mathfrak G}(X;\sigma_{q,0})
\right],
\qquad
A_q:=g_qB_q^\dagger.
\]
Here \(B_q\) and \(B_r\) are the fixed source and target boundary operators,
\(B_q^\dagger\) is the declared metric adjoint, \(g_q\) is the immutable
source gain, and \(\sigma_{q,\delta}\) and \(\sigma_{q,0}\) are the paired
grammar-valid drive scripts with the same exact clock, body frame, ordinary
packets, and positive incident/source-work budget except for the registered
source fixture \(\delta\). The map
\(\Phi_\ell^{\mathfrak G}\) is the exact `advance()` trajectory defined above,
so neither arm can inspect a future observation or world consequence. `T` is
a derived measurement, not a learned cross-modal matrix and not persistent
state. A local tangent is reported only when a separately registered
symmetric perturbation fixture demonstrates its linearization range.
Its target effect is admitted only through the uncertainty/null predicate
\(\operatorname{clear}_r^\tau\) defined in the QI-CAP-001 ladder; a point
estimate or an unresolved interval is never called causal.

For the ordered boundary registry, the capacity audit forms the complete
source-to-target transfer table over declared horizons and reports:

- per-coordinate `D,C,V_D,V_C,epsilon2_ema` reachability and observability;
- admitted source work, target response, delay, rank, singular spectrum,
  nullspace, and numerical interval;
- the spatial, scale-link, and passive-egress path that carries each
  nonzero response;
- C-only, D-only, and matched C/D optical fixtures so a static luminance source
  cannot become invisible to a D-only reader;
- state-matched controls with equal Hamiltonian, scale spectrum, EMA, and
  topological-retention topology but opposite registered phase current.

Raw state bytes, inactive tails, inaccessible velocities, and an unobserved
topological sector never count as usable capacity.

Multimodal binding is an equal-work causal closure test. For every source `q`,
treatment and control fixture bytes are fixed so

\[
\frac{
\left|W^{\mathrm{treat}}_{\mathrm{in},q}
-W^{\mathrm{control}}_{\mathrm{in},q}\right|
}{
\max\!\left(
W_{\mathrm{in,ref},q},
\left|W^{\mathrm{treat}}_{\mathrm{in},q}\right|,
\left|W^{\mathrm{control}}_{\mathrm{in},q}\right|
\right)
}
\leq\varepsilon_{\mathrm{work},q},
\qquad W_{\mathrm{in,ref},q}>0.
\]

The treatment must reduce the registered delayed prediction residual and
produce the declared target/action effect relative to modality-alone,
shuffled, lagged, phase-current-reversed, body-frame-mirrored,
transfer-permuted, and equal-work null controls. The runtime never rescales
live packets to manufacture equal work. The receipt hashes both trajectories,
all boundary/operator identities, per-source work, target response, residual
improvement, decision effect, delay, and uncertainty.
Every claimed delayed return or held-out successor therefore uses an exact
positive rational delay and the same \(\operatorname{clear}_r^\tau\) guard:
\[
\left|\widehat\Delta_r^\tau(c)\right|-\mathcal U_r^\tau(c)
>\Delta_{r,\mathrm{null}}^\tau
\quad\text{and}\quad
\left|\widehat\Delta_{r,\mathrm{null}}^\tau\right|
+\mathcal U_{r,\mathrm{null}}^\tau
\leq\Delta_{r,\mathrm{null}}^\tau.
\]
The delayed-influence receipt retains the paired scripts, exact clock
frontiers, positive incident/source-work intervals, target identity, and
all uncertainty and null controls; residual reduction without this margin
is not a capacity consequence.

## Boundary work

All modalities enter and leave through fixed, fingerprinted, label-free
boundary descriptors. A descriptor declares dimensions, units, coordinate
map, normalization, timing, saturation, phase convention, and inverse or
adjoint operation where one exists.

Permitted transient transforms are fixed coordinate changes and protocol
serialization. They do not create learned embeddings or engineered adaptive
features.

### Field-derived passive sensory permeability

`QI-BOUND-001` is the `QiBoundaryPermeabilityProfile` contract owned by
Part 5. This section does not redeclare fixed modality packet shapes,
alphabets, units, timing, transforms, characteristic bases, or source
watermarks. It fixes the cognition/retention obligation: the admitted
permeability at registered source `r` and scale `s`,

\[
\Pi_{r,s}(X):=\eta_{r,\mathrm{trans}}\!\left(\kappa_r(X)\right),
\qquad 0\leq\Pi_{r,s}(X)\leq1,
\]

is recomputed from the current declared field observable and fixed boundary
geometry. Its coefficients and metric are immutable profile data, not a
learned gate or a persistent history. The profile's passive fractions must
close, with admitted work equal to transmitted inward work,

\[
W_{\mathrm{incident}}^{r,s}
=W_{\mathrm{reflected}}^{r,s}
+W_{\mathrm{admitted}}^{r,s}
+W_{\mathrm{absorbed}}^{r,s}
+r_{\mathrm{permeability}}^{r,s},
\]

using the interval bounds and sign/orientation convention of
`QiScatteringReceipt`. `W_admitted` is linked exactly once to the signed
`W_sensory` row and the metric-adjoint reaction; reflected or absorbed work
cannot be hidden in a residual or copied from another scale. W7P/G7P rejects
an out-of-range or unresolved field-derived profile before mutation. The
complete profile, packet, and receipt schema remains in Part 5 so this
retention section adds no competing modality contract or persistent adaptive
state.


### Optical contract summary

A fixed optical boundary maps raw photometric or event increments into the
active spatial sheet. It preserves contrast and absolute source work under the
declared normalization. It does not encode glyph, word, object, or page labels.
A fixation supplies a timed boundary force rather than replacing the field with
a stored image.

### Text contract summary

The fixed 260-symbol byte/control alphabet remains a symbolic protocol port.
Direct terminal text is not presented as visual perception. Each source symbol
launches a timed boundary packet. Emission is based on integrated outgoing
field flow through fixed symbol probes, with deterministic tie-breaking and
abstention. A static resonance snapshot is not sufficient for flow ownership.

### Audio contract summary

Raw waveform windows enter through a fixed invertible coordinate transform and
time base. Any Fourier representation is used as a declared coordinate basis,
not as a learned feature encoder. Delay, phase, and reconstruction error are
part of the boundary identity and receipt.

### Proprioceptive and actuator boundaries

Pose, gaze, joint, camera, and actuator values use fixed units and ranges.
Proprioception enters as a timed source packet. Motor emission is a bounded
deterministic transducer from outgoing field current and declared gates. A
proposal, command, terminal applied acknowledgement, and applied efference have
distinct identities and exact rational ticks, linked by predecessor hashes; no
proposal identity or timestamp may stand in for an applied world effect.

## Prediction and residual return

The field is advanced under intrinsic dynamics and the declared action remap to
produce a transient predicted boundary. The next observation produces

\[
e_{t+1}=W^{\mathrm{observed}}_{t+1}-W^{\mathrm{predicted}}_{t+1}.
\]

The metric adjoint boundary/body map returns this residual to field
coordinates. For scale `s`, define
`H_{field,s}=C^{N_s}\oplus C^{N_s}` over the ordered `(D,C)` coordinates and

\[
G_s:=\operatorname{diag}(w_DW_s,w_CW_s).
\]

The full field space is the ordered direct sum across scales with
`G_field=blockdiag(G_0,\ldots,G_{S-1})`. For modality `r`, let
`B_r:H_field->H_r`; a descriptor that addresses only one coordinate/scale uses
the corresponding restricted block. Its fixed adjoint is defined by

\[
\langle B_rx,y\rangle_{W_r}
:=
\langle x,B_r^\dagger y\rangle_{G_{\mathrm{field}}}.
\]

The sole production residual operator is a bounded velocity force

\[
F^{\mathrm{residual}}_r
:=\eta_rB_r^\dagger e_{r,t+1},
\qquad \eta_r\geq0,
\]

applied as two registered `(h/2)F_residual` kicks in the external-force stages.
`eta_r`, its units, accepted source-work envelope, destination coordinate/scale,
and accumulation order are immutable descriptor/profile fields. The caller
cannot select them. A positional source version exists only as a named control.
The actual kinetic/total-energy delta is `W_residual,r`; no inverse is claimed
unless a descriptor separately proves invertibility.

The completed system does not teleport `D` to the target boundary, cache a
predicted frame, or persist a separate error state. Boundary packets and
predictions live only for the current cycle.

For every valid observed packet, the primary pre-correction metric is
per-modality:

\[
E_{\mathrm{pred},r}
:=
\frac{
\|W^{\mathrm{observed}}_r-W^{\mathrm{predicted}}_r\|_{W_r}^2
}{
\max(
\|W^{\mathrm{observed}}_r\|_{W_r}^2,
E^{\mathrm{obs}}_{\mathrm{ref},r}
)
},
\qquad
E^{\mathrm{obs}}_{\mathrm{ref},r}>0.
\]

Thus a false-positive prediction against a valid zero observation receives a
finite, nonzero penalty. Missing, malformed, saturated-without-accounting, or
otherwise invalid packets fail validation separately and never masquerade as a
zero vector. The reference energy, units, and null calibration are immutable
descriptor/profile data.

When a gate needs one multimodal scalar it uses
`E_pred=sum_r nu_r E_pred,r` with fixed nonnegative profile weights
`sum_r nu_r=1`; it never invents an unregistered aggregate metric.

## Perception, attention, memory, action, and meaning

- **Perception** is a reproducible field trajectory caused by sensory boundary
  work, not a stored picture.
- **Recognition** is low residual work and correct causal continuation under
  changed rendering or position, not state cosine.
- **Attention** is field-owned routing of boundary permeability and sensing
  action toward improved future closure.
- **Memory** is how slow Qi tends to flow next; it is not a copied content
  object.
- **Recall** is slow circulation launching a predicted fast boundary flow.
- **Prediction** is endogenous flow reaching a boundary before the successor
  observation.

- **Learning** is durable reorganization of the sole field through repeated
  residual-return circulation; there are no trained weights.
- **Action** is outward field flow committed through a fixed world boundary.
- **Self** is the distributed body-frame invariant that cancels reafference.
- **Meaning** is demonstrated when a flow initiated at one boundary closes at
  the correct causal delay through another boundary or a world consequence.

## Field-owned gaze and action

The field chooses one bounded action by the exact `mathcal C(a)` functional in
the normative attention contract below:

\[
a_t=\operatorname*{arg\,min}_{a\in\mathcal A_t}\mathcal C(a).
\]

This compact argmin is a forward reference to the sole expanded
`\mathcal C(a)` definition under **Field-owned attention, gaze, and action**;
it is not a second or partially specified action score.

Candidate evaluation sees current field, current boundary/residual packets,
current body pose, and fixed action geometry/cost only. It never sees
unobserved foveal pixels or future world consequences. There is no external
visited set, learned policy, recurrent gaze controller, stochastic sampler, or
sidecar inhibition state. Slow current contributes through the exact
flow-alignment term; a matched current reversal must change the committed
action on the registered directional fixtures.

### No-peek finite-horizon observability term

`QI-ACT-001` is the field-side constraint on the canonical action contract
owned by Part 5. The sole score there includes the additive
`-\mu_{\mathrm{obs}}I_{\mathrm{obs}}(a)` term, evaluated over the common
finite horizon `H` against the matched hold candidate. This section does not
redeclare the fixed modality/action packet shapes, direction list, Gramian
normalization, or safety functional.

The field candidate branch may use only the current committed field, current
admitted packets, calibrated body/gaze geometry, and hashed profile/operator
constants. Its bounded scratch rollout uses null future packets and the
candidate's declared remap; it cannot read future pixels, future world state,
labels, or the consequence of committing `a`. The resulting
`I_obs(a)` is a transient derivative/Gramian view, never a salience map,
visited set, policy state, or persistent tensor. Its rank, conditioning,
cross-talk, horizon, and propagated interval are included in the action
receipt and are checked by G9O. An unresolved or non-positive improvement is
not manufactured into a win: the canonical hold/abstention path is used.


## Flow diagnostics and conservation ledger

The implementation distinguishes amplitude movement, phase movement, spatial
current, energy transport, conversion, scale exchange, and boundary work.

Temporal amplitude rate:

\[
v_{\mathrm{amp}}
:=
\frac{\operatorname{Re}(D^*V_D)}{|D|+\delta_{\mathrm{amp}}},
\qquad \delta_{\mathrm{amp}}>0.
\]

Phase rate:

\[
\dot\theta
:=
\frac{\operatorname{Im}(D^*V_D)}
{|D|^2+\delta_{\mathrm{phase}}},
\qquad \delta_{\mathrm{phase}}>0.
\]

With the induced metric weights, phase charge and spatial current are

\[
q_D=w_D\operatorname{Im}(D^*V_D),
\qquad
\mathbf J_D=-w_Dc_D^2\operatorname{Im}(D^*\nabla D).
\]

### Derived spatial-current Hodge decomposition

Hodge analysis applies only to the derived two-dimensional vector current
`J_{Z,s}` on a profile-declared periodic uniform active sheet. It is never
applied to a scalar optical page and never stored as observer state. The
canonical spectral derivative symbols obey

\[
\mathbf d_s(k)=
\left(d_{x,s}(k),d_{y,s}(k)\right)
=i\widetilde{\mathbf k}_s,
\qquad
\widetilde{\mathbf k}_s\in\mathbb R^2,
\]

Array lookup remains `(k_y,k_x)` in the x-fastest/y-major DFT registry, while
physical vector components remain ordered `(x,y)`; therefore
`\widetilde{\mathbf k}_s=(k_{x,s},k_{y,s})`. A non-anti-Hermitian or differently
ordered derivative symbol is a profile failure.
Define the exact derivative-null registry

\[
\mathcal N_s:=
\{k:\mathbf d_s(k)^\dagger\mathbf d_s(k)=0\}.
\]

It always contains DC and contains a Nyquist/checkerboard mode only when the
frozen derivative convention makes that mode null. For every `k`,

\[
\widehat{\mathbf J}^{\,H}_{Z,s}(k)
:=
\begin{cases}
\widehat{\mathbf J}_{Z,s}(k),&k\in\mathcal N_s,\\
0,&k\notin\mathcal N_s,
\end{cases}
\]

and, for every $k\notin\mathcal N_s$,

\[
\widehat{\mathbf J}^{\,L}_{Z,s}(k)
:=
\mathbf d_s(k)
\frac{
\mathbf d_s(k)^\dagger
\widehat{\mathbf J}_{Z,s}(k)
}{
\mathbf d_s(k)^\dagger\mathbf d_s(k)
},
\qquad
\widehat{\mathbf J}^{\,T}_{Z,s}(k)
:=
\widehat{\mathbf J}_{Z,s}(k)
-\widehat{\mathbf J}^{\,L}_{Z,s}(k),
\]

with $\mathbf J^L=\mathbf J^T=0$ on $\mathcal N_s$. The DC member is the ordinary harmonic
component. Any additional discrete derivative-null member is reported
separately as grid-harmonic/null and cannot count as physical transport,
circulation, capacity, or topological-retention winding evidence. `L` is the
longitudinal/divergent component and `T` is the transverse/solenoidal
circulation component. The inverse DFT is transient. The receipt reports
`L/T/H` norms, reconstruction residual, `L/T` inner product, divergence,
curl, boundary-normal flux, and topological-retention cycle circulation. It must verify

\[
\mathbf J=\mathbf J^L+\mathbf J^T+\mathbf J^H,
\qquad
\langle\mathbf J^L,\mathbf J^T\rangle_W=0
\]

within the independently derived numerical interval. Traveling, standing,
vortex/circulation, harmonic-wrap, phase-current-reversed, and finite-aperture
guard fixtures prevent lingering amplitude or periodic wrap from being called
memory circulation.

Wave-energy density and transport are

\[
e_D
:=
w_D\left[
\frac12|V_D|^2
+\frac{c_D^2}{2}|\nabla D|^2
+\frac{\omega_D^2}{2}|D|^2
+\frac{\kappa_D}{4}|D|^4
\right],
\]

\[
\mathbf P_D
:=
-w_Dc_D^2\operatorname{Re}(V_D^*\nabla D).
\]

The corresponding carrier quantities use `C`, `V_C`, and `w_C`; total energy
also includes the declared composition and scale-link potentials and, in
topological retention, `U_topo`. Every step reports:

- active-sheet and total state energy;
- amplitude rate and phase rate;
- spatial phase current and wave-energy flux;
- centroid position and velocity;
- boundary-normal flux and normalized continuity residual;
- Yang/Yin density transferred;
- cross-scale link energy/current and per-scale work;
- sensory, residual, remap, port-reaction, conversion, and damping work;
- composition, link, and retention conservative work/potential closure;
- topological-retention sector, core margin, barrier margin, residence, and reset/phase-slip
  identity;
- candidate pre-check and committed-state energy;
- attempted component clipping/global rescaling and rejected-bound counts;
- body-remap round-trip error;
- pre-correction successor residual;
- proposal-versus-hold advantage and, only after a terminal applied
  acknowledgement, applied-efference prediction advantage as distinct rows;
- state, operator, boundary, packet, proposal, reaction, action, acknowledgement,
  applied-efference, and receipt identities.

Globally, reciprocal scale phase sources cancel and conservative composition,
link, and topological-retention retention force work telescopes with the potentials included
in the Hamiltonian. Every accepted run has zero clipping/rescaling; a rejected
stress candidate records the attempted operation and its work without
producing a committable state.

## Analytic calibration and flow counterfactuals

Every flow measure has a known-flow calibration and a null:

1. frozen field: zero temporal and spatial motion;
2. amplitude-only ramp: nonzero amplitude rate, zero phase current;
3. rigid phase rotation: nonzero phase rate, zero spatial transport;
4. standing `+k/-k` wave: local dynamics, zero net transport;
5. traveling packet: known phase-current and energy-flux directions;
6. phase-current-reversed and energy-flux-reversed packets with matched energy;
7. zero-velocity and DC fields: zero spatial current;
8. unitary `+Delta x/-Delta x` remap: norm and state round trip;
9. true, absent, lagged, permuted, and reversed efference copies;
10. enabled, disabled, and phase-shifted scale coupling;
11. balanced, positive-imbalance, and negative-imbalance conversion;
12. fixed-boundary collision, phase-scramble, noise, and invalid-source arms;
13. zero-clipping long-horizon evolution and deliberately over-budget failure;
14. exact checkpoint continuation and wrong-identity rejection.
15. Hodge traveling, standing, vortex, and harmonic-wrap fixtures with exact
    reconstruction and longitudinal/transverse orthogonality;
16. fading-retention fading and topological-retention below-barrier, phase-slip, winding, cue-return,
    explicit-reset, and matched-energy/opposite-current fixtures.

The counterfactual suite separates phase circulation from wave-energy
transport. No transform is called a generic flow reversal.

The packed-real phase-current reversal is

\[
\mathcal R_J:
(E_Y,E_I,V_Y,V_I,m_{\epsilon^2})
\mapsto
(E_Y^*,E_I^*,V_Y^*,V_I^*,m_{\epsilon^2}).
\]

It negates every imaginary position/velocity plane and leaves every real plane
and `epsilon2_ema` unchanged. Under real conjugation-equivariant geometry it
preserves amplitude, Yang/Yin density, composition/link potential, total
energy, and wave-energy flux while reversing
`q_D,q_C,J_D,J_C`. A `phase-current-reversed field` always means this
whole-state transform.

The matched packet/energy-flux reversal is

\[
\mathcal R_P:
(E_Y,E_I,V_Y,V_I,m_{\epsilon^2})
\mapsto
(E_Y^*,E_I^*,-V_Y^*,-V_I^*,m_{\epsilon^2}).
\]

For the instantaneous source-free fixture it preserves total energy and phase
charge while reversing spatial phase current and wave-energy flux. Because
damping and external sources break time-reversal symmetry, `mathcal R_P` is a
calibration/counterfactual transform, not a claim that a production trajectory
can be rewound. Velocity negation and covariant spatial reflection remain
separate registered controls.

A reversed boundary-wave control keeps raw payload, timing, and admitted work
class fixed but applies the separately versioned control injection
`A_r^{rev}x=(A_rx)^*`; it is never a production descriptor. Every reversal
receipt names the transformed flow channel and includes pre/post energy,
`q/J/P`, state, descriptor, payload, and geometry identities. Action relabeling
or an informal `reverse packet` cannot substitute for a declared transform.

The separate `composition-reversal-v1` fixture is also exact. Choose constant
`\rho>0` and
`0<\epsilon_0<\min(\rho,\phi\rho)=\rho\min(1,\phi)`, zero spatial gradients,
and real positive
Yang/Yin phases. For signs `s in {-1,+1}`,

\[
|E_Y^{(s)}|^2=\frac{\phi\rho+s\epsilon_0}{1+\phi},
\qquad
|E_I^{(s)}|^2=\frac{\rho-s\epsilon_0}{1+\phi}.
\]

This gives identical total position density and opposite imbalance. Reconstruct
real `D,C`, include every base/composition/link position term, and compute each
zero-velocity energy `E_pos^(s)`. Let the profile contain a real,
`G_field`-unit velocity basis `b` with zero phase current for both states and a
positive ballast `E_ballast`. Set

\[
E_*=\max_s E_{\mathrm{pos}}^{(s)}+E_{\mathrm{ballast}},
\qquad
V^{(s)}=\sqrt{2(E_*-E_{\mathrm{pos}}^{(s)})}\,b.
\]

Both arms therefore have exact total energy `E_*`, zero initial spatial/phase
current, identical scale/work class, and opposite `epsilon`. The primary
steering statistic is the potential-on minus potential-off paired difference
within each arm, so the declared velocity ballast cannot be mistaken for
composition steering. The manifest hashes `rho,epsilon_0,b,E_ballast` and both
raw states.

## Full-system release criteria

The flow-first endpoint is release-ready only when all of the following coexist
in the canonical runtime and pass their current engineering checks:

1. explicit `scale_geometry_mode` selection after the registered
   `temporal-full-rank`/`spatiotemporal-pyramid` comparison, exact numerical
   semantics, and measured transport;
2. active steering and coherence-carrier dynamics in the sole Qi state;
3. explicit Yang/Yin conversion with W5V/G5V forward viability, physical-time
   EMA semantics, and full work closure;
4. reciprocal continuous cross-scale circulation over its declared retained
   subspaces, with scale-link and external-port scattering closure;
5. measured reachability, observability, the full QI-CAP-001 geometric/
   reachable/usable/retained/reusable topological-retention capacity ladder, and
   uncertainty-thresholded dynamical capacity;
6. fixed optical, text, audio, proprioceptive, and actuator boundaries;
7. body-centered predictive remapping and residual return;
8. field-owned attention and action with the no-peek finite-horizon
   observability-improvement term and guarded decisions;
9. W4R topological-retention physical-core proofs followed by W10R within-sector analog and
   topological behavioral retention, cue-causal recall, acquisition,
   overwrite/recovery, and held-out transfer;
10. deterministic passive trajectory-based text emission and abstention;
11. exact persistence, profile compatibility, and restart continuation;
12. terminal and loopback-provider integration with no Qwen fallback;
13. acknowledged embodiment in both the deterministic reference world and the
    real default-off CassiCosmos adapter;
14. CPU/ROCm finite, bounded execution under the same operator identity and
    declared decision margins;
15. independently recomputable ownership, displacement, flow, work,
    topology, `QiBoundaryPermeabilityProfile`, `QiScatteringReceipt`,
    conversion-viability, transaction, and checkpoint receipts.

A visual probe, isolated PDE operator, passing unit test, or coherent text
sample is not completion by itself.

