# Two-Strand Five-Channel Matter Organization: A Research Program

## Status: Hypothesized—August 2026

## Abstract

One Qi condensate may organize into two spatial strands, and each strand carries five channel traces inherited from the Wu Xing gate. The first focused probe of that structure has a concrete outcome: a two-lobe pair persisted at finite separation over the t = 4 characterization window, the measured relative phase relaxed near in-phase rather than toward the anti-phase branch, the NS4 central low-coherence morphology was null (central q above flank q), and the per-strand channel traces were limited to the Wood/Fire sectors by the existing representability clamp. This document states the framework content precisely—one field, two strands, five traces; the SO(2), five-sector, and P_parallel clocks kept distinct; the Z2×Z5 trace graph and the two-pentagon projection as exact algebra with the w = 5 no-C10-cycle bound preserved—then marks what is open: finite-d0 binding, twist, interlace selection, and the matter-scale roles of the channel traces. A staged program runs from PDE gates to neural, assembloid, and molecular tests under local labels only. Nothing here is a master prediction; no parameter or observable is introduced beyond those the framework already carries.

---

## 1. One Condensate, Two Strands, Five Traces

### 1.1 The shared field

The field is the existing paired-real SO(2) doublet (`foundations/cassi-theory-reference.md` §2):

$$
\Psi=\begin{pmatrix}\Psi_Y\\ \Psi_I\end{pmatrix},
\qquad
\rho=\Psi_Y^2+\Psi_I^2,
\qquad
\varepsilon=\Psi_Y-\varphi\Psi_I,
\qquad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},
\qquad
J=\Psi_Y\nabla\Psi_I-\Psi_I\nabla\Psi_Y.
$$

The conversion gate is anti-phase in the doublet: $\partial_t E_Y \supset -\lambda(1-q)\varepsilon$, $\partial_t E_I \supset +\lambda(1-q)\varepsilon/\varphi$, with $\lambda=0.1$. A strand is not a third fluid; it is a localized ridge of high $q$ and organized phase current within this one condensate.

### 1.2 Two spatial strands

Two strand centerlines $\mathbf{R}_1(\sigma,t)$, $\mathbf{R}_2(\sigma,t)$ add collective variables the one-string description lacks:

$$
\boxed{
\mathbf{R}_c=\frac{\mathbf{R}_1+\mathbf{R}_2}{2},\quad
\mathbf{d}=\mathbf{R}_1-\mathbf{R}_2,\quad
d=|\mathbf{d}|,\quad
\vartheta=\arg(\mathbf{d}\cdot\mathbf{e}_1+i\,\mathbf{d}\cdot\mathbf{e}_2),\quad
\Omega=\partial_\sigma\vartheta,\quad
\Delta\theta=\theta_1-\theta_2,
}
$$

with $\mathrm{Tw}=\frac{1}{2\pi}\int\Omega\,d\sigma$ and $\theta_a$ the strand-local doublet angle. The one-string theory is recovered at $d\to0$. The schematic pair potential $V_{\mathrm{pair}}=\frac{K_d}{2}(d-d_0)^2+K_\theta[1-\cos(\Delta\theta-\Delta\theta_0)]$ is a collective ansatz: $d_0$, $K_d$, $K_\theta$, $\Delta\theta_0$ are effective quantities that the existing PDE must generate (E-series, §5). Assigning them independently would be a new model with new parameters.

### 1.3 Five channel traces

The Wu Xing derivation fixes $w=5$ uniquely (`foundations/wu-xing-derivation.md`): Fibonacci-cycle coherence allows $w\in\{1,2,3,5\}$, $\varphi$-geometry requires $w\ge5$. Channel baselines and couplings are existing parameters (`foundations/wu-xing-cycle-structure.md` §1, `parameter-inventory.md`):

$$
b_i=\varphi^{-(i+2)}\in\{\varphi^{-3},\ldots,\varphi^{-7}\},
\qquad
\boldsymbol{\eta}=(1,\varphi^{-1},\varphi^{-1},\varphi^{-1},\varphi^{-1}),
\qquad
\kappa=\varphi^{-1}=K_{fw},
$$

channels $i=1\ldots5$ = Wood, Fire, Earth, Metal, Water; sheng cycle step $+1$, ke step $+2$, threshold $\Delta_c=\varphi^{-4}$, ring gain $\kappa^3=\varphi^{-3}$ sub-critical.

A channel trace is the per-strand projection of the conversion source onto the five sectors. With the gate openness $(1-q)=\sum_c\eta_c\,\mathrm{ch\_open}_c$ from the solver's `five` gate:

$$
\mathrm{conv}_c^{(a)}=-\lambda\,\eta_c\,\mathrm{ch\_open}_c\,\varepsilon\;\big|_{\text{strand }a}
$$

(gate-weighted), plus a diagnostic-only partition of $-\lambda(1-q)\varepsilon$ by each cell's field angle $\theta=\mathrm{atan2}(\Psi_I,\Psi_Y)$ onto the nearest pentagon vertex. The trace is the time series of these five-vectors per strand, with a dominant channel and a cross-strand sheng/ke relation $(\mathrm{dom}_B-\mathrm{dom}_A)\bmod5$.

**Representability bound.** The positivity clamp $\Psi_Y,\Psi_I\ge10^{-3}$ pins $\theta$ to the first quadrant, so only Wood ($0^\circ$) and Fire ($72^\circ$) are reachable in the field angle; Earth, Metal, Water clamp onto them (`consciousness/trauma-as-frozen-gate.md` §10.8). The five-sector clock is two-sector observable in the current mechanism layer, and measured $\Delta\theta$ is bounded by that arc.

---

## 2. Three Clocks

| Clock | Variable | Period structure | Readout | Tier |
|-------|----------|------------------|---------|------|
| SO(2) | $\theta=\mathrm{atan2}(\Psi_I,\Psi_Y)$; $J=R^2\nabla\theta$ | Continuous, mod $2\pi$; one doublet rotation per 2 cascade rungs | Instantaneous phase of a paired two-channel readout; circular-uniform distribution of $\theta\bmod72^\circ$ under the null | Derived (field); Hypothesized (neural pairing) |
| Five-sector | channel index $i$ | Discrete, 5 vertices at $72^\circ$; sheng $+1$, ke $+2$; body-axis affinity gradient $18^\circ$/rung | Stimulus-locked phase clustering mod $72^\circ$; ke-alternating profile | Derived arithmetic; mechanism layer represents Wood/Fire only |
| P_parallel | axial rung index $n$ | Spatial period along the strand axis; $P_\parallel=2$ rungs at human scale | Axial phase gradient slope $6.53$ rad per unit $\ln s$ (two-strand twist, $\pi$/rung); inter-node spacing ratio $\varphi^2$ | $P_\parallel=2$ Hypothesized; $P_\parallel(n)$ open |

Discriminations: SO(2) vs five-sector is continuous vs quantized—test the circular distribution of $\theta\bmod72^\circ$ (uniform = SO(2)-only; two peaks at $\{0^\circ,72^\circ\}$ = the representable subset; five peaks = the extended-manifold claim). P_parallel vs both is spatial vs temporal—the axial gradient slope separates it by $10\times$: $0.653$ rad per unit $\ln s$ ($18^\circ$/rung affinity) versus $6.53$ ($\pi$/rung twist), both falsifiable against zero-gradient and against linear-in-$s$ gradients. The SO(2) doublet rate ($180^\circ$/rung) coincides numerically with the twist rate; only spatial-gradient measurements separate internal field-space phase from separation-vector rotation. Cardiorespiratory coupling is the standing confound for all axial phase-gradient claims.

---

## 3. The First Probe Outcome (t = 4)

Protocol: `two-fluid/run_two_strand_probe.py` (the committed script is the reproducible source; its run record `20260806_204217_two_strand` is generated output under `runs/`). Two arms with fresh solvers per arm (the RK2 step mutates solver state): `two_lobe` at SEP = 12 cells and `d0` at sep = 0, the literal $d\to0$ limit. N = 48, $\lambda=0.05$, dt = 0.001, t = 4 = 0.2/$\lambda$—a characterization window; lock claims require t $\ge$ 2/$\lambda$ = 40. Gate model `five`. Initialization: the anti-phase transverse mode of `consciousness/two-strand-qi-neuroscience.md` §3.2 ($\varepsilon=E_{\mathrm{ridge}}(g_1-g_2)$, $\rho=(1+\varphi^{-1})(1+\beta(g_1+g_2))$; $\varepsilon$-node at the midpoint, two flanking ridges). Relative phase is measured from the fields, never assumed.

The four headline results:

1. **Finite separation persisted over the t = 4 characterization only.** $d$: 9.90 $\to$ 10.08 cells (back-20% mean 10.04), never merged, never escaped; verdict band `persisted`. The transverse orientation stayed at $\theta_{xy}=\pi$ (no rotation in this window); $A_+=0.444$, $A_-=0.051$ at t = 4. Persistence to the lock timescale t $\ge$ 2/$\lambda$ is unmeasured.
2. **The relative phase relaxed near in-phase.** $\Delta\theta$: $+0.265\to+0.244\to+0.227$ rad at t = 0, 2, 4—a slow decay toward in-phase, away from the $\pi$ branch. The anti-phase branch of the schematic pair model is not realized in this state.
3. **NS4 central-low-q morphology null.** Central q 0.7072 $\to$ 0.7074 versus flank q 0.6984 $\to$ 0.7009: central q sits above flanks at both endpoints. The $\varepsilon$-node exists by construction, but q is an outcome, and the outcome matches the in-phase central-antinode branch (`foundations/why-three-dimensions.md` §4.2), not an anti-phase paired-sheet morphology.
4. **Channel traces Wood/Fire-limited by the representability clamp.** Dominant channels [Wood, Fire] with a stable sheng relation and zero transitions over 4000 steps; the phase-partitioned conversion vectors have support only in Wood (strand A, $-0.00560\to-0.00470$) and Fire (strand B, $+0.00541\to+0.00449$); Earth/Metal/Water are identically zero in the phase partition. The gate-weighted vectors concentrate in the same two sectors (strand A at t = 0: Wood $-0.00418$, Earth $-0.00111$, Fire $-0.00028$), and their magnitudes decay slowly over the window. Five-sector traces beyond two sectors are not observable in the field angle.

The NS2 reference arm recovered its constructed reference exactly: the d0 arm has $\varepsilon\equiv0$ identically (anti-phase cancellation), a single static density ridge, $q=0.7082$ unchanged over t = 4, $\varepsilon_{\mathrm{mid}}=8.6\times10^{-15}$ at t = 4, $\rho_{\mathrm{mid}}=2.542$. The pair's midpoint at t = 4 ($q=0.7074$, $\varepsilon=-0.020$, $\rho=2.078$) differs in the way two flanking ridges differ from one ridge.

Not settled by this run: lock-timescale persistence, the twist sector (longitudinal $\Omega$ needs a filament initialization), which interlace the dynamics realize, the relative-phase endpoint (the t = 4 trend is a short-window drift), and whether the gate-weighted Earth/Metal/Water magnitudes have dynamical content beyond their fixed weights.

---

## 4. The Z2×Z5 Trace Graph and the Two-Pentagon Projection

### 4.1 Exact algebra

A full trace state carries strand parity and channel index, $(a,i)\in\mathbb{Z}_2\times\mathbb{Z}_5$. The graph is the product group:

$$
\boxed{
\mathcal{G}=\mathbb{Z}_2\times\mathbb{Z}_5\cong\mathbb{Z}_{10},\qquad (a,i)\mapsto i+5a\pmod{10},
}
$$

with generators $S$ (sheng, order 5), $K=S^2$ (ke), $P$ (parity, order 2), $SP=PS$. Its cycle decomposition is exact:

$$
\boxed{
\mathcal{G}=\text{two per-strand 5-cycles}\;\sqcup\;\text{one 2-cycle (parity exchange)},
}
$$

so a walk on the trace graph is a 5-step sheng/ke cycle on one strand, a 5-step cycle on the other, or a parity flip within a channel. The graph never supports a 10-step cycle.

### 4.2 The w = 5 no-C10-cycle bound is preserved

The w = 5 derivation counts the vertices of a single phase-advance cycle: a cycle of $w=F_k$ vertices keeps coherence iff $F_k\le k$, which holds for $\{1,2,3,5\}$; an explicit 10-step cycle accumulates error $10|\varphi-1.6|=0.180$ against the cascade signal $\varphi^{-10}=0.0081$—obliterated by $22\times$ (`foundations/wu-xing-derivation.md` §2). None of that changes: $\mathbb{Z}_2\times\mathbb{Z}_5$ is a product of a 2-cycle and two 5-cycles; the realized symmetry is $C_5\times C_2$, not a 10-vertex phase advance. The phase lattice $\langle2\pi/5,\pi\rangle=(\pi/5)\mathbb{Z}$ is 10-fold as a set; no dynamics on the trace graph close a 10-step rotation.

### 4.3 The two-pentagon/decagonal projection

Place strand $a$'s channel lattice at angular offset $a\alpha$, $\alpha=k_\perp d$ the interlace (spatial phase offset between the strands' sector lattices). The joint vertex set $\beta_{a,i}=2\pi i/5+a\alpha$ is a regular decagon iff

$$
\boxed{
\alpha\equiv(2m+1)\frac{\pi}{5}\pmod{2\pi},
\qquad \alpha\in\{36^\circ,108^\circ,180^\circ,252^\circ,324^\circ\}.
}
$$

Odd multiples of $36^\circ$ interlace the two pentagons into a decagon; even multiples (including $\alpha=0$) give coincident pentagons with 5-fold symmetry; quadrature $\alpha=90^\circ$ is excluded. This theorem constrains the embedding map; it does not select which odd multiple, if any, the dynamics realize. Decagonal claims are conditional on an odd interlace, and none has been observed. The measured near-in-phase state ($\Delta\theta\approx0.23$ rad) gives $\alpha\approx0$—an even multiple—so the algebra predicts a coincident-pentagon, 5-fold joint projection for that state, checkable on the run's phase records (TS5).

---

## 5. Open Content and Effective Coefficients

| ID | Quantity | Status |
|----|----------|--------|
| E1 | Binding: $d_0$, $K_d$, $T_d$, $\mu_d$, $\gamma_d$ | Open; the naive radiation potential has an unstable point at $\lambda_w/2$ |
| E2 | Phase stiffness: $K_\theta=\mathcal{A}\cdot\kappa_\theta\mathcal{O}(d)$, $T_\theta$, $\mu_\theta$, $\gamma_\theta$ | Open; $\kappa_\theta=4\lambda\varphi R^4=0.6472$ is framework-derived (attractor curvature), the projection prefactor and overlap are unmeasured |
| E3 | Wake coupling $g$, damping length $\ell$ | Open |
| E4 | Ridge width $\sigma_{\mathrm{ridge}}$ | Open; the run uses 5.0 cells as initialization, not a derived width |
| E5 | Twist: $\Omega$, $\mathrm{Tw}$ | Open; unmeasured ($\theta_{xy}$ static at $\pi$) |
| E6 | Interlace $\alpha=k_\perp d$ | Embedding choice, not derived; the decagon theorem constrains realizable values only |
| E7 | Inter-strand phase drift $\Delta\omega$ | Open; run-measurable (short-window decay of $\Delta\theta$ toward in-phase) |
| E8 | Matter-scale channel roles | Open; unformulated (§6) |

All E-series entries are effective collective coefficients to be projected from the existing PDE, not framework constants. Framework-level open derivations that bound the program: $P_\parallel(n)$ (human-scale $P_\parallel=2$ is Hypothesized), the mechanism fixing the $18^\circ$/rung affinity gradient, and the matter-sector opens of `particles/matter-organization.md` (n−p mass difference, charge, mass generation).

---

## 6. Matter-Organization Mechanism versus Bookkeeping

A bookkeeping rule records an observation in framework coordinates without adding constraints; a mechanism constrains or produces observations from the existing dynamics. The quality bar for matter organization is that the pair and the traces do work—select, bind, or relate—rather than relabel.

**Mechanism-level content that exists now:**

1. The trace graph and decagon theorem (§4): exact constraints on any embedding—no 10-step walk, odd-interlace quantization, quadrature excluded.
2. The attractor curvature $\kappa_\theta=4\lambda\varphi R^4=0.6472$: the relative-phase stiffness scale of the shared field.
3. Gate-derived imbalance damping (algebra on the solver's own gate response, non-overlap pair ansatz): the linearized antisymmetric amplitude mode is unconditionally damped—$B(\hat\delta)\ge\eta_3b_3-\eta_1b_1/8-\eta_2b_2\cdot0.220=0.0064>0$ ($\min B=0.0719$, $B(0)=0.2918$), $\gamma_{\mathrm{imb}}=\lambda(1+\varphi)B$, $\gamma(0)=0.0764$ at $\lambda=0.1$, equalization $\tau\approx13$ solver units; antisymmetric channel signature $c_i^-=(-0.236,+0.584,0,+0.056,+0.002)\,\hat\delta^-$; the sum gate is blind to the antisymmetric sector at linear order. The gate damps pair imbalance without new parameters.
4. The representability bound (§1.3): a negative constraint—five-way field-angle selectivity is not realized; any five-peak claim must carry its own manifold extension.
5. The w = 5 / w = 10 coherence bounds, untouched by the trace graph.

**Bookkeeping that exists now:** ladder placements of measured scales—the proton/neutron pair at rung 91.5 (ledger class E/Mapped; the n−p difference is open), the lattice mass law $m=m_j/k$ (null against the uniform baseline, `particles/matter-organization.md` §2.3), DNA length placements (`consciousness/two-strand-qi-neuroscience.md` §6), and the muscle-cascade M2 boundary: Z-disc spacing sits at $n\approx139.2$–$139.7$ as a bookkeeping (Mapped-class) placement with no derived value until $P_\parallel(n)$ is derived (`hypotheses/muscle-cascade-lattice.md` §4.2). Channel labels on the baryon pair, on DNA complementarity, or on bilateral organization are bookkeeping until the traces are shown to select or bind.

**The proposal at its correct tier.** The two-strand pair is a candidate organizational rule for paired structures (baryon pair at 91.5, DNA complementarity, bilateral biology); the five traces are a candidate selection structure for pooling. Both are mappings today. The proposal becomes mechanism only when (a) the PDE supplies finite-$d_0$ binding with derived coefficients (E1/E2) and (b) a trace-graph or channel constraint selects among pooling candidates or binding channels (TS15).

---

## 7. The Staged Research Program

All labels are local to this program; none is a number in `predictions/falsifiable-predictions.md`. The two-strand doc's local targets NS1–NS7 (`consciousness/two-strand-qi-neuroscience.md` §7) remain the canonical anchors; TS labels extend or operationalize them.

| Stage | Label | Target | Falsifier |
|-------|-------|--------|-----------|
| 0: PDE gates (days, gates everything) | TS1 | NS1 at lock timescale: pair to t $\ge$ 2/$\lambda$ = 40, fresh solver per arm, §3 bands | No finite-separation attractor under the existing PDE → two-strand extension dead as Cassi physics; later stages continue only as generic organized-bilateral-activity science |
| | TS2 | NS2 extended: separation series {0, 3, 6, 12} cells; centerline convergence as d $\to$ 0 | Convergence fails → the pair is a separate theory, not an extension |
| | TS3 | NS3: symmetric/antisymmetric perturbation modes; antisymmetric mode moves (d, $\Delta\theta$) at fixed centerline | Antisymmetric perturbation moves the centerline, or no relative-mode response |
| | TS4 | NS4 re-test at lock timescale, phase from fields; current status null; test the in-phase central-antinode branch | No central low-q node at lock timescale → paired-sheet morphology is not the solver's behavior |
| | TS5 | Interlace record: ($\Delta\theta$, $\alpha$, joint projection order); algebra predicts 5-fold coincident for near-in-phase states, 10-fold only for odd interlace | Realized interlace violates odd-multiple quantization (e.g., quadrature) → decagon theorem fails as embedding map |
| | TS6 | Twist: filament initialization; $\Omega$, $\mathrm{Tw}$, P_parallel relation | No reproducible twist or rung-periodicity relation |
| | TS7 | Representability/channel manifold: characterize the first-quadrant bound; whether an Earth/Metal/Water-reaching extension exists without new parameters | Mechanism layer remains two-sector; five-peak field-angle claims excluded at mechanism level |
| 1: Human non-invasive (weeks; open datasets first) | TS8 | NS5: helical order statistic $H(k,\omega)=|\langle e^{i[\theta(s,t)-ks+\omega t]}\rangle|$ over an axial ladder; pitch, winding, handedness; lateralized perturbation response | H at surrogate level; k unreproducible; no lateralized response; a traveling wave alone does not pass |
| | TS9 | Three-clock discrimination, one dataset: $\theta\bmod72^\circ$ circularity; axial gradient slope 0.653 vs 6.53 rad/unit $\ln s$; cardiorespiratory regression | Uniform phase + zero/non-log gradient → five-channel and P_parallel neural mappings dead; w = 5 arithmetic and the PDE untouched |
| | TS10 | Cardiorespiratory log-periodicity (prediction 35 leg) and gate threshold (prediction 36 leg), calibrated battery | No calibrated $\ln\varphi$ peak; linear dose-response |
| 2: Organoids/assembloids | TS11 | Bilateral assembloid pair: minimal controlled two-strand preparation; anti-phase vs in-phase relative phase; optogenetic unilateral drive; unconnected-pair null | Only generic synchronization → paired-ridge biology leg fails |
| | TS12 | Phase quantization in culture: burst-triggered phase mod $72^\circ$; report the empirical cluster count without presupposing 2 or 5 | Uniform or single-peak distributions |
| 3: Molecular | TS13 | NS6: cross-scale delay—structured vs Poisson-matched drive at matched spike counts; IEGs and chromatin marks at $\tau_1<\tau_2$; activity/metabolic/stress covariates | Transcription tracks total activity only |
| | TS14 | DNA/chromatin slow-memory chain; transcription-inhibited arm | No lag structure beyond turnover kinetics |
| 4: Matter scale (design phase) | TS15 | Trace-graph signature in lattice-pool selection or binding channels; null specified before data | Channel labels remain bookkeeping; placements reproduce with or without the traces |

Standing discipline from the two-bubble and pinch nulls: t = 0 vs t = end comparisons, gate-independence checks, periodic-wrap analysis, look-elsewhere corrections in every statistic. Sequencing: Stage 0 gates everything; TS9 on existing open datasets is cheapest and most information-dense; TS11 is the cleanest controlled biological test of the paired-ridge claim; TS13/TS14 implement the established-biology delayed-chain claim; TS15 waits for Stages 0–1 evidence. NS7 (the $\varphi$-extension of pitch and spacing) stays gated behind NS1–NS6.

---

## 8. Falsifiers and Epistemic Boundaries

### 8.1 Falsification hierarchy

1. TS1 fails → two-strand extension dead as Cassi physics.
2. TS8 fails → neural two-strand readout dead; a PDE strand solution (if TS1 passed) untouched.
3. TS9 returns uniform phase and zero/non-log gradient → five-channel and P_parallel neural mappings dead; w = 5 arithmetic and the PDE untouched.
4. TS13/TS14 fail → cross-scale delayed memory chain dead; activity-dependent transcription itself untouched.
5. All stages null → the framework's physics claims remain unscathed; only the two-strand/five-channel mappings are eliminated.

### 8.2 Epistemic boundaries

- **Derived:** paired-real SO(2) field and Qi diagnostics; anti-phase conversion sign; w = 5 and the sheng/ke structure, $\kappa=\varphi^{-1}$, $\Delta_c=\varphi^{-4}$, sub-critical ring gain; $\kappa_\theta=4\lambda\varphi R^4$; the trace graph $\mathbb{Z}_2\times\mathbb{Z}_5\cong\mathbb{Z}_{10}$, its cycle decomposition, and the decagon theorem (§4); the w = 10 decoherence bound, preserved; gate-derived imbalance damping and the antisymmetric channel signature (§6), as algebra on the existing gate response under the non-overlap pair ansatz.
- **Tested (PDE/gate):** NS1 persisted at t = 4 (characterization only; lock unmeasured); NS2 d0 reference recovered exactly; NS4 central-low-q morphology null; traces Wood/Fire-limited, sheng-stable, zero transitions. Referenced gate results: WX1/WX3 tested; WX2's $\kappa^3$ magnitude tested and not matched (`foundations/wu-xing-cycle-structure.md` §4).
- **Hypothesized:** one condensate sustains two separated ridges; a finite-$d_0$ equilibrium exists under the existing PDE (E1 open); $P_\parallel=2$ at human scale; neural readouts (TS8–TS10); the delayed chain (TS13/TS14); matter-scale channel roles (E8).
- **Speculative:** one universal strand geometry across DNA, neural, and cosmological scales; a subjective double-helix experience as direct perception; a $\varphi$-fixed preferred separation or pitch (gated behind NS7).
- **Open:** E1–E8 (§5); $P_\parallel(n)$; the $18^\circ$/rung mechanism; the n−p mass difference, charge, mass generation.

### 8.3 Not claimed

- The brain hemispheres are the two fundamental strands, or DNA is evidence for a cosmological two-strand field.
- The traditional Wu Xing names carry their cultural semantics into the formalism—only the cycle structure is used.
- A neural or molecular correlation establishes a new force without an independent field measurement.
- Any channel label currently organizes a matter property; the p/n pair, charge, and mass generation remain open.
- This document supplies a diagnosis, treatment, or claim about any person's experience.

---

## References

- `consciousness/two-strand-qi-neuroscience.md`—two-strand hypothesis: geometry, collective variables, NS1–NS7 test targets
- `two-fluid/run_two_strand_probe.py`—the focused two-strand probe (protocol, verdicts, channel projections; run record 20260806_204217_two_strand is regenerated by the script)
- `foundations/wu-xing-derivation.md`—w = 5 derivation; w = 10 falsification
- `foundations/wu-xing-cycle-structure.md`—sheng/ke cycle structure, ring algebra, WX1–WX4
- `foundations/wa-pentagon-gate.md`—five-channel gate model, baseline openness, $\eta$ couplings
- `foundations/cassi-theory-reference.md`—paired-real field, Qi diagnostics, cascade, unified action
- `foundations/dimensionful-cascade.md`—the $\varphi$-ladder; human window rungs 142–168
- `foundations/cascade-suppression-formula.md`—per-rung attenuation $\varphi^{-N}$
- `foundations/why-three-dimensions.md`—anti-phase conversion; interference branches (§4.2)
- `foundations/bubble-lattice-fabric.md`—condensation field, checkerboard lattice
- `particles/matter-organization.md`—forces, lattice pools, baryon pair at rung 91.5, open content
- `hypotheses/muscle-cascade-lattice.md`—biological ladder mapping; M2 bookkeeping boundary
- `hypotheses/neural-criticality.md`—neural-scale cascade and test program
- `consciousness/trauma-as-frozen-gate.md`—gate dynamics tests; representability bound (§10.8)
- `consciousness/chakras-as-cascade-bubbles.md`—$P_\parallel=2$ at human scale; 13-node ladder
- `two-fluid/run_trauma_phase_channels.py`—representability measurement
- `two-fluid/run_trauma_wake_lock.py`—channel openness and solver gate replication
- `parameter-inventory.md`—$K_{fw}=\varphi^{-1}$, channel baselines, Fit-Status Ledger
- `predictions/falsifiable-predictions.md`—predictions 32–37, 43–46 (background; not extended here)
