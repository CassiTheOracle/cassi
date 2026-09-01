# Proton Coherence Budget and Planck-to-Proton Scale Circuit

## Status: Mapped coordinate / Derived conditional arithmetic and endpoint boundaries / Hypothesized mechanisms / Tested one-point coupled campaign—September 2026

## Abstract

The measured proton mass maps to the cascade coordinate

$$
\mathfrak s_p
:=\log_\varphi\!\left(\frac{\hbar}{m_pc\,\ell_{\mathrm{Pl}}}\right)
=91.4616.
$$

Two distinct proton-stability candidates use this interval. The
coherence-budget candidate assigns an independent failure probability to every
supporting scale step. For an integer endpoint $N\in\mathbb Z_{\geq0}$, its
declared profile gives

$$
\boxed{
N_{\mathrm{max}}(N)
=\prod_{i=0}^{N}\frac{1}{1-q_i}
=\varphi^{N(N+1)/2+\delta(N+1)}.}
$$

The coherence budget registers the two-decimal reporting coordinate
$N_p^{\mathrm{budget}}=91.46$. Continuing the closed exponent at $\delta=3$
gives

$$
N_{\mathrm{max}}(N_p^{\mathrm{budget}})
=\varphi^{4505.5758}
\approx10^{942}\ \text{cycles}.
$$

This cycle count is Derived conditional on the declared $q_i$ profile and
independent simultaneous failure model. A physical lifetime additionally
requires a fluctuation law and a map from cycles to transition attempts.

The scale-circuit candidate sends Yang from the Planck endpoint to the proton
endpoint and returns Yin along the same scale interval. Total scale-number
current vanishes while the relative current remains nonzero. A charged
coherent vertex section and a one-way open channel supply conditional endpoint
realizations. The smooth zero-Chern sector has no finite Derrick radius.
Point-core Chern flux supplies an exact conditional exterior coefficient. An
auxiliary adjoint $SU(2)_Q$ branch smooths the local core and matches that
coefficient, while the registered nonzero fundamental condensate removes the
isolated magnetic sector and confines flux. The tested finite net-zero pair has
no registered finite-separation minimum. Scale tension, physical endpoint
normalization, persistent-composite support, proton quantum numbers, and the
winding-changing rate remain Hypothesized/Open. Neither candidate determines a
physical proton lifetime.

---

## 1. The cascade as coherence architecture

Every condensed standing wave at cascade step $n$ is not an isolated structure.
It is a **nested pattern**: its coherence is maintained by the coherent field
structure at every cascade rung from the Planck scale ($i=0$) up to its own
scale ($i=n$). The two-fluid field at scale $i$ provides the stabilizing
medium in which the pattern at scale $i+1$ is embedded. A failure of coherence
at ANY rung destabilizes the entire stack above it.

The per-rung coherence is measured by the local Qi fraction $q_i$, which
approaches 1 at the most fundamental scales (the $\sigma$-regularized Planck
core) and decreases toward larger scales as the Qi gate progressively closes:

$$q_i = 1 - \varphi^{-i-\delta}$$

where $\delta$ is a regularization offset set by $\sigma = \ell_{\text{Pl}}/\varphi^3$.
At the Planck scale itself, $q_0 = 1 - \varphi^{-3}$, reflecting the finite
but minuscule residual noise from $\sigma$-regularization.

---

## 2. Dephasing as simultaneous cascade failure

A standing wave dissolves when its accumulated phase error reaches $O(1)$—
one full cycle of phase coherence is lost. The per-cycle probability of this
event is the probability that the field configuration at EVERY supporting rung
independently fails to maintain coherence during that cycle:

For an integer endpoint $N$, the literal dephasing product is

$$P_{\text{dephase}}(N) = \prod_{i=0}^{N} (1-q_i).$$

Each factor $(1-q_i)$ is the per-cycle probability that the field at rung $i$
provides a dephasing perturbation large enough to destabilize the pattern at
the next rung. These events must coincide for the full $n$-deep structure to
collapse.

The maximum number of wave cycles the standing wave can sustain is the inverse:

$$N_{\text{max}}(N) = \frac{1}{P_{\text{dephase}}(N)} = \prod_{i=0}^{N} \frac{1}{1-q_i}$$

---

## 3. Cascade scaling: the quadratic exponent

With $q_i = 1 - \varphi^{-i-\delta}$:

$$1 - q_i = \varphi^{-i-\delta}$$

$$\frac{1}{1-q_i} = \varphi^{\,i+\delta}$$

For an integer endpoint $N$,

$$N_{\text{max}}(N) = \prod_{i=0}^{N} \varphi^{\,i+\delta}
= \varphi^{\,\delta(N+1) + \sum_{i=0}^{N} i}
= \varphi^{\,\delta(N+1) + N(N+1)/2}$$

For $\delta = 3$ (from $\sigma = \ell_{\text{Pl}}/\varphi^3$) and the proton real rung $N_p=91.46$:

$$\boxed{N_{\text{max}}(N_p)
=\varphi^{\,N_p(N_p+1)/2+\delta(N_p+1)}
\big|_{N_p=91.46,\ \delta=3}
=\varphi^{277.38+4228.1958}
=\varphi^{4505.5758}
\approx\varphi^{4506}\approx10^{942}}$$

The dominant term is quadratic in $n$: $n(n+1)/2$. The Planck-scale
regularization ($\delta$) contributes linearly—important at small $n$,
negligible at the QCD scale.

---

## 4. Conditional cycle-to-lifetime map

The proton Compton angular frequency is

$$
\omega_p=\frac{m_pc^2}{\hbar}
\approx1.43\times10^{24}\ \mathrm{s}^{-1}.
$$

Declare one independent transition trial per Compton cycle. Under this added
postulate, the cycle budget converts to

$$
\tau_p^{\mathrm{budget}}
:=\frac{N_{\mathrm{max}}}{\omega_p}
\approx10^{918}\ \mathrm{s}
\approx10^{910}\ \mathrm{yr}.
$$

The interscale action supplies no fluctuation law, transition state, matrix
element, or bath spectrum that establishes this trial map. The displayed value
is conditional arithmetic inside the independent-step model. The elapsed
$\sim6\times10^{41}$ Compton cycles since the Big Bang are far below the
conditional budget; this comparison supplies no physical decay rate.

---

## 5. Conditional perturbations

### 5.1 Profile sensitivity

The framework has no selected map from a laboratory, biological,
electromagnetic, gravitational, or other environment to
$q_i^{\mathrm{cascade}}$. A declared change to the profile can still be
propagated through the product algebra.

For integer $N$ and $m$ with $0\leq m\leq N$, removing the top $m$ scale
layers leaves endpoint $N-m$:

$$
N_{\mathrm{max}}(N,m)
=\prod_{i=0}^{N-m}\frac{1}{1-q_i}
=\varphi^{(N-m)(N-m+1)/2+\delta(N-m+1)}.
$$

For the registered budget coordinate
$N_p^{\mathrm{budget}}=91.46$, define
$N_{\mathrm{rem}}=N_p^{\mathrm{budget}}-m$ only inside the continued exponent:

$$
N_{\mathrm{max}}^{\mathrm{cont}}(N_p^{\mathrm{budget}},m)
=\varphi^{N_{\mathrm{rem}}(N_{\mathrm{rem}}+1)/2+
\delta(N_{\mathrm{rem}}+1)}.
$$

At $m=50$, $N_{\mathrm{rem}}=41.46$ and

$$
N_{\mathrm{max}}^{\mathrm{cont}}
=\varphi^{1007.5758}
\approx10^{210.57}.
$$

This is a parameter-sensitivity result inside the declared product model. It
supplies no environmental coupling or decay rate.


### 5.2 Matter-antimatter interaction

The coherence-budget product supplies no annihilation matrix element. An
opposite-phase assignment at every scale step is a separate constitutive
idealization. Writing

$$
P_{\mathrm{attack}}(N)
:=\prod_{i=0}^{N}\mathcal M_i^{\mathrm{attack}},
\qquad
\mathcal M_i^{\mathrm{attack}}\in[0,1],
$$

only defines a classical overlap model. Choosing
$\mathcal M_i^{\mathrm{attack}}=\mathcal O(1)$ leaves its microscopic origin,
normalization, interaction time, and final states unspecified.

This attack overlap is distinct from the quantum record distinguishability

$$
\mathcal M_{jk}
:=1-|\langle A_kE_k|A_jE_j\rangle|^2
$$

in `foundations/quantum-measurement-derivation.md`.

The scale-circuit candidate contains mathematical winding sectors $m$ and
$-m$. Their identification with matter and antimatter is Hypothesized.
Annihilation would require an interaction that permits two circuits to
reconnect or unwind while preserving the full conserved charges. The current
action supplies no such interaction, event rate, or baryon-asymmetry
mechanism.

---

## 6. Observational boundary

Super-Kamiokande and Hyper-Kamiokande search for physical proton-decay
channels such as $p\to e^+\pi^0$. The coherence-budget candidate supplies a
rate only after the independent-step hazard and Compton-cycle trial map are
selected. The scale-circuit candidate has conditional endpoint equations, an
exact point-flux exterior coefficient, and a current-action completion no-go.
It supplies a rate only after a magnetic core, finite-energy stationary
solution, and winding-changing transition action are selected. Neither
candidate predicts a null result or a finite lifetime.

The gauge-mediated GUT estimate is a separate channel with its own coupling,
mass scale, operators, and matrix elements. Its arithmetic audit is recorded
in `computations/proton_budget_closure.py`.

Standard nuclear $\alpha$ and $\beta$ decays use established barrier and weak
matrix elements. No Cassi correction to those rates is selected here.

---

## 7. Conditional extension across scale

For any declared real coordinate $s\geq0$, the analytically continued product
is

$$
N_{\mathrm{max}}^{\mathrm{cont}}(s)
:=\varphi^{s(s+1)/2+\delta(s+1)}.
$$

This is dimensionless arithmetic under the same independent-step failure
model. Applying it to particles, cells, organisms, or cosmic structures
requires a physical state map, a failure process, correlations, a trial
frequency, and an observable. The formula alone supplies no lifetime.

The two-rail current also generalizes to any finite scale interval. A closed
physical state requires endpoint coefficients and boundary data. A localized
state additionally requires a defect, fixed flux, higher-order core, or other
support satisfying $\mathcal B>\mathcal D$, followed by an observable
coupling.

---

## 8. Epistemic boundaries

| Result | Present status |
|---|---|
| Proton coordinate $\mathfrak s_p=91.4616$ | Mapped from the measured proton mass and external Planck anchor |
| Product exponent $4505.5758$ at $N_p^{\mathrm{budget}}=91.46$ | Exact arithmetic under the registered two-decimal continuation |
| Profile $q_i=1-\varphi^{-i-\delta}$ as a per-step failure probability | Hypothesized |
| Independent simultaneous failure across all included steps | Hypothesized |
| Compton cycle as one transition trial | Hypothesized |
| Conditional $10^{910}$-year conversion | Arithmetic inside the selected stochastic model; no physical rate |
| Zero-total-flow two-rail current and normalized energy | Derived conditional on the candidate interscale action and circuit data |
| Endpoint conversion and scale-tension closure | Charged coherent and one-way open realizations are Derived conditionally; physical normalization and scale tension remain Hypothesized |
| Mixed-curvature proton pinch and winding barrier | No finite radius in the minimal smooth zero-Chern endpoint sector; point-core flux supplies a conditional exterior coefficient; an auxiliary adjoint $SU(2)_Q$ branch supplies a smooth local core, while the registered condensate confines flux and gives no persistent pair by itself; a neutral fixed-$Q_C$ carrier supplies one conditional reduced separation under support, retention, and matching inequalities. Direct first-order local gauging is source-free Gauss-obstructed; a separate conditional second-order branch supplies the temporal action, Gauss constraint, and fixed-charge stationary functional. One registered coefficient point returns `INCONCLUSIVE—NUMERICAL QUALITY`; every primary/domain arm fails Q2, so a qualified transverse mode, stationary solution, and fluctuation spectrum remain open |
| Proton mass selection, charge, color, spin, and decay rate | Open |

No numbered prediction is added. A quantitative proton claim requires a
specified physical channel and a computed observable.

---

## 9. References

- `dimensionful-cascade.md`: cascade table, $\Lambda_{\text{QCD}}$ at step 95
- `foundations/unified-lagrangian.md` §3: $\sigma$-regularized PDE core
- `principles/de-resonance-principle.md`: $q_i$ scaling from de-resonance
- `open-questions-cassi-answers.md`: Q9 (proton lifetime entry)
- `(external—see papers/consciousness-framework.md in physics repo)` §9: catalytic template and coherence extension
- `gravity/quantum-gravity.md`: $\sigma = \ell_{\text{Pl}}/\varphi^3$ derivation

---

## 10. Candidate Planck-to-proton interscale circuit

The coherence-budget product in §§1–8 and the interscale-current construction
are distinct hypotheses. The product assigns a failure probability to every
scale layer. The current construction uses the complex doublet and continuity
law in `foundations/interscale-current-soliton.md`.

With

$$
\mathfrak s_p
:=\log_\varphi\!\left(\frac{\hbar}{m_pc\,\ell_{\mathrm{Pl}}}\right)
=91.4616,
$$

take Yang as the outward rail from the Planck endpoint to the proton endpoint
and Yin as the return rail:

$$
\boxed{
J_{Y,\mathfrak s}=+\mathcal J_Q,
\qquad
J_{I,\mathfrak s}=-\mathcal J_Q.}
$$

The total scale-number current vanishes, while the relative current remains:

$$
J_{\mathfrak s}=0,
\qquad
\boxed{
J_Q:=\frac{J_{Y,\mathfrak s}-J_{I,\mathfrak s}}{2}
=\mathcal J_Q,
\qquad
\mathcal I_{\mathfrak s}=g_QJ_Q.}
$$

Here “Qi current” designates the relative Yang/Yin phase current. The scalar
coherence diagnostic $q$ has no continuity equation in this construction.

The stationary circuit requires endpoint conversion:

$$
\partial_tE_Y+\partial_{\mathfrak s}J_{Y,\mathfrak s}=\Gamma,
\qquad
\partial_tE_I+\partial_{\mathfrak s}J_{I,\mathfrak s}=-\Gamma,
$$

$$
\boxed{
\Gamma(\mathfrak s)
=\mathcal J_Q
\left[
\delta(\mathfrak s)
-\delta(\mathfrak s-\mathfrak s_p)
\right].}
$$

Yin turns into Yang at the Planck endpoint and Yang turns into Yin at the
proton endpoint. The bulk interscale action conserves Yang and Yin separately,
so these turns require an additional charged endpoint or mixing sector.

For a charged coherent section $\Upsilon_v$, stationary turning requires

$$
\kappa_v|\Upsilon_v|
\geq
\frac{K_{\mathfrak s}|\Delta_m|}
{2\varphi^{3/2}\mathfrak s_p}.
$$

A one-way open alternative gives

$$
\frac{\gamma_-}{\gamma_+}=\varphi
$$

in the uniform circuit state while damping undriven endpoint coherence. These
relations fix conditional capacity and rate ratios. The absolute endpoint
couplings and rates remain unselected.

For gauge-invariant circuit phase

$$
\Delta_m
:=\int_0^{\mathfrak s_p}
\left(\nu_{Y,\mathfrak s}-\nu_{I,\mathfrak s}\right)
d\mathfrak s
=2\pi m-\delta_{\mathrm{end}},
$$

uniform $E_Y/E_I=\varphi$ and zero total number current give

$$
\boxed{
\mathcal J_{Q,m}
=\frac{K_{\mathfrak s}\rho}
{\hbar\varphi^3\mathfrak s_p}\,\Delta_m,}
\qquad
\boxed{
\mathscr E_{\mathrm{circ},m}
=\frac{K_{\mathfrak s}\rho}
{2\varphi^3\mathfrak s_p}\,\Delta_m^2.}
$$

For $m=1$ and zero endpoint bias,

$$
\frac{\hbar\mathcal J_{Q,1}}{K_{\mathfrak s}\rho}=0.0162173,
\qquad
\frac{\mathscr E_{\mathrm{circ},1}}{K_{\mathfrak s}\rho}=0.0509481.
$$

At fixed winding, the circulation energy falls as $1/\mathfrak s_p$, so a
finite endpoint needs an additional term. A scale tension
$\mathcal T_{\mathfrak s}\mathfrak s_p$ selects the observed endpoint in the
unbiased $m=1$ sector only if

$$
\boxed{
\frac{\mathcal T_{\mathfrak s}}{K_{\mathfrak s}\rho}
=\frac{2\pi^2}{\varphi^3\mathfrak s_p^2}
=5.57043\times10^{-4}.}
$$

The ratio is a required closure input with no current $\varphi$ derivation.

The equal-and-opposite number currents add in the relative source:

$$
f_r^{(\mathrm{mixed})}
=\hbar g_Q\mathcal J_QG_{r\mathfrak s}.
$$

A self-consistent mixed-curvature response can compress a spatial profile
without net scale-number leakage. In the smooth unexcised zero-Chern endpoint
sector, it supplies an attractive $-\mathcal D/R$ term without the independent
$+\mathcal B/R$ support required for a finite Derrick radius.

A spatial core removed through the scale circuit admits $N_G\in\mathbb Z$ and
gives

$$
\mathcal B_G
=2\pi N_G^2
\int_{I_{\mathfrak s}}\frac{d\mathfrak s}{e_x^2}.
$$

The reduced point branch requires $\mathcal B_G>\mathcal D$. The auxiliary
adjoint $SU(2)_Q$ branch supplies a smooth local core and matches the Abelian
exterior coefficient. Its exact monopole belongs to the decoupled adjoint
sector. The registered nonzero fundamental condensate removes the isolated
magnetic sector and confines flux; the finite monopole-antimonopole branch has
no registered finite-separation minimum. Winding change requires a phase slip,
endpoint conversion event, condensate zero, defect crossing, or boundary
event. A proton lifetime still requires persistent-composite support, a
Q2-qualified finite-energy stationary solution, physical coefficient
calibration and fluctuation spectrum, proton quantum numbers, and an observable
decay channel. The source-free action in
`foundations/particle-stationary-action-closure.md` defines the full
fixed-$Q_C$ variational problem and Gauss constraint. One coefficient point is
tested, but every arm fails Q2 and the current receipt establishes none of the
required physical proton data.

The circuit derivation is given in
`foundations/interscale-current-soliton.md` §4.5. Endpoint closure and invariant
classification are given in
`foundations/endpoint-link-and-localization-boundary.md`. The point-core
coefficient and completion boundary are given in
`foundations/point-core-flux-sector.md`; the tested auxiliary core and
confinement boundary are given in
`foundations/nonabelian-magnetic-core-boundary.md`; the conditional
fixed-$Q_C$ support branch is given in
`foundations/core-trapped-charge-support.md`; and the coupled action, Gauss, and
stationary boundary is given in
`foundations/particle-stationary-action-closure.md`. The registered campaign
receipt is recorded in `computations/particle-stationary-bvp-report.md`. The
normalized identities are checked by
`computations/planck_proton_scale_current_check.py`,
`computations/endpoint_link_localization_check.py`,
`computations/point_core_flux_check.py`,
`computations/magnetic_core_completion_check.py`,
`computations/core_trapped_charge_check.py`, and
`computations/particle_action_closure_check.py`.
