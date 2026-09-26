# Checkerboard Edge Phase Coupling (Wave 4)

## Status: Hypothesized—August 2026

## Abstract

Wave 4 escalates the Wave 3 imposed-operator/readout check to one explicit directed checkerboard edge. An externally supplied, carrier-signed amplitude-space $SO(2)$ kick is distributed along the finite proxy's target-to-diagonal corridor with a frozen endpoint phase ramp. The experiment tests whether the supplied matched-carrier projection at the diagonal receiver differs from equal-norm carrier-quadrature, axial-void, and undirected-flat route controls. It is an additive driven-edge construction; it does not claim endogenous phase selection, spontaneous transport, a persistent macro-spiral, biology, or an anatomical lattice.

## 1. Prior constraint and hypothesis

`field-experience/counterflow-carrier-demodulation-wave-3-report.md` records an imposed-carrier operator/readout contrast for a target-local kick while checkerboard routing remains unresolved. The missing tested feature is a directed edge operator. Wave 4 tests the following finite supplied construction:

> Under the supplied target-gated carrier schedule and route profile, does a bounded rhythmic phase-current pulse produce a stronger matched-reference response across the permitted diagonal checkerboard edge than across an axial void barrier or through an undirected tube?

The Wave 3 matched-carrier coherence metric, block size, bootstrap seed, and $0.10$ threshold remain unchanged. The hypothesis is a protocol feature test, not a claim that the canonical PDE selects a route endogenously.

## 2. Frozen finite geometry

The source geometry is the staggered-checkerboard principle in `foundations/bubble-lattice-fabric.md` §1.2: diagonal bubble connections pass through saddles, while axial paths meet void barriers. The finite five-Gaussian state used in Waves 1–3 is an **index-lattice proxy**. Its equal 12-cell $x$/$y$ offsets do not instantiate the physical $\varphi$-anisotropic metric; `(18,18,24)` is called a proxy saddle rather than an exact $C=0$ physical saddle.

The target and permitted diagonal receiver are

$$
T=(12,12,24),\qquad D=(24,24,24),
$$

with

$$
\hat e_D=\frac{(1,1,0)}{\sqrt2},\qquad \ell_D=12\sqrt2.
$$

The axial route-null ends at the proxy void coordinate

$$
V=(12,24,24),\qquad \hat e_A=(0,1,0),\qquad \ell_A=12.
$$

For each route $R\in\{D,A\}$, form a periodic smooth tube from $Q_R+1$ equally spaced centers

$$
c_q=T+\frac{q}{Q_R}(R-T),
$$

where $Q_D=34$, $Q_A=24$, and adjacent samples are at most 0.5 cells apart. With periodic signed displacement $\delta_N$, tube width $\sigma_t=3$ cells, and

$$
g_q(\mathbf x)=\exp\!\left[-\frac{|\delta_N(\mathbf x,c_q)|^2}{2\sigma_t^2}\right],
\qquad
m_R(\mathbf x)=1-\prod_{q=0}^{Q_R}(1-g_q),
$$

we have $m_R\in[0,1]$. Let

$$
h_R=\operatorname{clip}\!\left(\frac{\delta_N(\mathbf x,T)\cdot\hat e_R}{\ell_R},0,1\right).
$$

The finite proxy labels assign $\theta_T=+\pi/4$ and $\theta_D=0$, hence $\Delta\theta_D=-\pi/4$. The directed phase-ramp profile is

$$
p_R(h_R)=\frac{\sin\left[\Delta\theta_D(h_R-\tfrac12)\right]}
{\sin(\Delta\theta_D/2)},
\qquad
w_R=m_Rp_R.
$$

It has $p_R(0)=-1$ and $p_R(1)=+1$. The axial route uses this same frozen label-derived ramp as an equal-construction null. The set-aside alternative is a direct $C(x,y)$ path with $\varphi$-rescaled coordinates; that would impose a physical metric absent from the finite proxy.

The undirected diagonal-tube control uses $w_{D,\rm flat}=m_D$.

## 3. Frozen amplitude-space edge kick

At every matched cadence event, the target amplitude phasor and threshold are unchanged from Wave 3:

$$
Z_T=\langle A+iB\rangle_T,
\qquad M_n\geq\cos(\pi/6),
\qquad A=\sqrt{E_Y},\ B=\sqrt{E_I}.
$$

For route profile $w$, externally supplied carrier sign $s_n$, and $\alpha=s_n\beta w$, apply the additive kick once before the unmodified canonical `rk2_step`:

$$
A'=\cos\alpha\,A-\sin\alpha\,B,
\qquad
B'=\sin\alpha\,A+\cos\alpha\,B,
\qquad
E_Y'=A'^2,\ E_I'=B'^2.
$$

Each event and route independently solves $\beta\in[0,0.05]$ using 48 bisection iterations to satisfy

$$
\|\Delta(A,B)\|_2^2
=4\sum_{\mathbf x}\rho\sin^2\!\left(\frac{\beta w}{2}\right)
=0.45^2,
\qquad \rho=E_Y+E_I.
$$

This matches amplitude-space kick energy despite unequal tube supports. The kick preserves $\rho$ pointwise. The fixed $F=10^{-3}$, $\delta=10^{-5}$ safety wedge is unchanged:

$$
\theta_F=\arcsin\sqrt{\frac{F+\delta}{\rho}},
\qquad
\theta_F\leq\operatorname{atan2}(B,A)+\alpha\leq\frac\pi2-\theta_F.
$$

No clipping, canonical-solver modification, or post-RK2 intervention is permitted. The route profile, endpoint ramp, carrier signs, and event trigger remain supplied by the probe; the canonical PDE does not evolve them.

## 4. Frozen arms

| arm | flow | route profile | carrier |
|---|---|---|---|
| `baseline` | positive paired flow | none | none |
| `diagonal_matched` | positive paired flow | directed $w_D$ | matched $(+,+,-,-)$ |
| `diagonal_quadrature` | positive paired flow | directed $w_D$ | quadrature $(+,-,-,+)$ |
| `axial_matched` | positive paired flow | directed $w_A$ toward proxy void | matched |
| `diagonal_flat` | positive paired flow | undirected $m_D$ | matched |
| `diagonal_reversed_flow` | reversed paired flow | directed $w_D$ | matched |
| `diagonal_zero_flow` | zero flow | directed $w_D$ | matched |

`diagonal_matched` defines the accepted event schedule. Every driven control replays the same event times with a fresh solver. Each route solves its own $\beta$ to the fixed $0.45$ norm. Thus `diagonal_quadrature` changes the supplied carrier signs, `axial_matched` changes the supplied route profile, `diagonal_flat` removes the supplied ramp while retaining the tube, and the reversal/zero arms change the supplied flow proxy.

## 5. Receiver measurement

The receiver is the diagonal bubble mask, not the target or the target-plus-receiver average. Define

$$
\mathbf J_\Psi=A\nabla B-B\nabla A,
\qquad
j_D=\langle\mathbf J_\Psi\cdot\hat e_D\rangle_D,
\qquad
r_{D,n}=\frac{j_D(t_n+0.01)-j_D(t_n^-)}{J_{D,{\rm rms},0}}.
$$

For every contiguous 20-event block, the Wave 3 matched-carrier coherence is retained byte-identically:

$$
C_{D,b}=
\frac{\left|\sum_{n\in b}s_n^{\rm match}r_{D,n}\right|}
{\sqrt{\sum_{n\in b}(s_n^{\rm match})^2}\sqrt{\sum_{n\in b}r_{D,n}^2}},
$$

with $C_{D,b}=0$ for a zero response denominator. The primary receiver metric always projects onto the **externally supplied** matched carrier, including the quadrature arm.

Secondary receipts include target and receiver phasors, $\Delta\theta_{D-T}$, tube and half-tube current profiles, $\mathbf J_d=2AB\mathbf J_\Psi$, $q$ at target/saddle/receiver/void masks, $\sum\rho w^2$, actual norm, $\beta$, field minima, wedge margin, and pointwise/global invariants.

## 6. Quality gates

The run is **INVALID** if any condition fails:

1. Wave 3 metric-reference checks $C(0)=0$, $C(-s_{\rm match})=1$, and $C(s_{\rm quadrature})=0$;
2. no-op wrapper identity is nonzero after 100 canonical RK2 steps;
3. any field is non-finite, reaches the $10^{-3}$ floor, or violates the fixed wedge;
4. $\max|\rho'-\rho|>10^{-12}$, relative global mass error $>10^{-12}$, or kick-norm error $>10^{-12}$;
5. any route lacks capacity below $\beta=0.05$;
6. `diagonal_matched` accepts fewer than 30 events or controls fail exact schedule replay;
7. a tube violates $|w|\leq1$, lacks support at its stated route endpoints, or the positive flow seed lacks opposite signed right/left $u_z$ and $J_{\Psi,z}$ biases.

## 7. Frozen feature verdicts

A route contrast passes only when its paired 10,000-resample block-bootstrap lower bound exceeds zero and its point estimate is at least $0.10$.

| feature | contrast | feature verdict |
|---|---|---|
| F1 carrier-correlated receiver response under the supplied corridor kick | diagonal matched minus diagonal quadrature | EMERGES / DOES NOT EMERGE |
| F2 diagonal route specificity under supplied profiles | diagonal matched minus axial matched | EMERGES / DOES NOT EMERGE |
| F3 directed-ramp specificity under supplied profiles | diagonal matched minus diagonal flat | EMERGES / DOES NOT EMERGE |

These uppercase feature labels are frozen protocol branches. F1 compares two
externally supplied carrier sign schedules on the same supplied directed
corridor; F2 compares supplied diagonal and axial profiles under the matched
schedule; and F3 compares a supplied directed ramp with a supplied flat tube.
They do not establish endogenous canonical phase selection, spontaneous routing,
or transport. The edge-coupling hypothesis is **SUPPORTS** only if F1, F2, and
F3 all EMERGE. It is **HOLD** if F1 plus exactly one route feature EMERGES. It
**CONTRADICTS** if none of F1–F3 EMERGES. Other valid combinations are
**INCONCLUSIVE**. Counterflow reversal and zero-flow contrasts are recorded as
secondary constraints.

## 8. Scope

The phase ramp is a deliberately supplied edge mechanism applied around an
unmodified canonical PDE/RK2 step. A positive result would show a
route-specific matched-reference response for this bounded construction. It
would not show endogenous canonical phase selection, spontaneous routing,
finite-speed transport, that a brain creates the pulse, that a stable large
spiral forms, or that the proxy maps to biology.

## References

- `field-experience/counterflow-carrier-demodulation-wave-3-report.md`—local synchronization result and missing edge mechanism.
- `field-experience/counterflow_carrier_demodulation_probe.py`—byte-identical carrier metric.
- `foundations/bubble-lattice-fabric.md` §1.2—diagonal saddle connections and axial void barriers.
- `foundations/bubble-edge-geometry.md` §2.2—gentler diagonal edge and steeper axial void edge.
