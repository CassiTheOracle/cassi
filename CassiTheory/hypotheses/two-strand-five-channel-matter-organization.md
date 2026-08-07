# Two-Strand Five-Channel Matter Organization: A Research Program

## Status: Hypothesized—August 2026

## Abstract

One Qi condensate may organize into two spatial strands, and each strand carries five channel traces inherited from the Wu Xing gate. The first focused probe of that structure has a concrete outcome: a two-lobe pair persisted at finite separation over the t = 4 characterization window, the measured relative phase relaxed near in-phase rather than toward the anti-phase branch, the NS4 central low-coherence morphology was null (central q above flank q), and the per-strand channel traces were limited to the Wood/Fire sectors by the existing representability clamp. A second probe with a filament initialization measured the twist sector: the initialized half-twist persisted over the same window (Tw 0.500 → 0.499), a parallel pair generated no twist, and no rung-periodicity relation emerged. The lock-timescale suite (t = 40 = 2/$\lambda$, six fresh-solver arms) resolved the remaining PDE-level items: the pair escapes (no finite-separation attractor), the $d\to0$ limit does not recover the one-string centerline, the antisymmetric perturbation mode is not centerline-fixed, the central-low-q morphology stays null, and the near-in-phase endpoint realizes the coincident-pentagon 5-fold joint projection the algebra predicts—TS1–TS4 null, TS5 passed on its observed branch. The framework-native attractive branch—the Yin-excess pair, $\Pi=E_Y-E_I<0$ via the buoyancy sign of the existing gravity term—is then measured (§3.5): with the same two-lobe state initialized with $E_Y\leftrightarrow E_I$ exchanged (representable under the positivity floor), the pair persists at finite separation through t = 40 (d 9.90 → 7.51 cells, no merge, no escape) while the Yang-excess counterfactual escapes; the Yin excess is transient (erased by conversion at t ≈ 21), the state is a slow contraction that ends in coalescence at t ≈ 47 (t = 80 continuation), and E1 equilibrium coefficients remain unprojected at every measured timescale. This document states the framework content precisely—one field, two strands, five traces; the SO(2), five-sector, and P_parallel clocks kept distinct; the Z2×Z5 trace graph and the two-pentagon projection as exact algebra with the w = 5 no-C10-cycle bound preserved—then marks what is open: finite-$d_0$ binding (excluded under the existing PDE at lock timescale), twist generation, interlace selection, and the matter-scale roles of the channel traces. A staged program runs from PDE gates to neural, assembloid, and molecular tests under local labels only. Nothing here is a master prediction; no parameter or observable is introduced beyond those the framework already carries.

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

The gate-weighted projection is two-sector as well (TS7, `two-fluid/ts7_channel_manifold.py`): the `five` gate's openness profile is a function of the single scalar $\epsilon_{\text{norm}}=\epsilon^2/(\epsilon^2+M+\varphi^{-2})$, so the trace vector moves on a one-dimensional curve whose dominant channel is Wood for $\epsilon_{\text{norm}}<0.475$ and Fire above; Earth would need $\epsilon_{\text{norm}}>0.809$, unreachable with positive fields ($\epsilon_{\text{norm}}\le\varphi^2/(\varphi^2+1)=0.724$), and Metal and Water never lead at any imbalance ($\eta_c\,\mathrm{ch\_open}_c$ for both lies strictly below Earth's for every $\epsilon_{\text{norm}}$). The gate is direction-blind—the event direction enters only through $\epsilon^2$—so the Wood/Fire selectivity of `two-fluid/run_trauma_phase_channels.py` lives entirely in the phase-angle partition, and in the two-strand probe run the gate-weighted cross-strand relation is "same" (Wood/Wood) while the phase-angle one is "sheng" (Wood/Fire). A five-sector manifold needs two missing degrees of freedom: a signed field component (the clamp) for the far arc and Earth dominance, and an angle-dependent gate coupling for Metal/Water—both are new model content, not parameter re-fits.

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

### 3.1 The two-lobe pair probe

Protocol: `two-fluid/run_two_strand_probe.py` (the committed script is the reproducible source; its run record `20260806_204217_two_strand` is generated output under `runs/`). Two arms with fresh solvers per arm (the RK2 step mutates solver state): `two_lobe` at SEP = 12 cells and `d0` at sep = 0, the literal $d\to0$ limit. N = 48, $\lambda=0.05$, dt = 0.001, t = 4 = 0.2/$\lambda$—a characterization window; lock claims require t $\ge$ 2/$\lambda$ = 40. Gate model `five`. Initialization: the anti-phase transverse mode of `consciousness/two-strand-qi-neuroscience.md` §3.2 ($\varepsilon=E_{\mathrm{ridge}}(g_1-g_2)$, $\rho=(1+\varphi^{-1})(1+\beta(g_1+g_2))$; $\varepsilon$-node at the midpoint, two flanking ridges). Relative phase is measured from the fields, never assumed.

The four headline results:

1. **Finite separation persisted over the t = 4 characterization only.** $d$: 9.90 $\to$ 10.08 cells (back-20% mean 10.04), never merged, never escaped; verdict band `persisted`. The transverse orientation stayed at $\theta_{xy}=\pi$ (no rotation in this window); $A_+=0.444$, $A_-=0.051$ at t = 4. The lock-timescale outcome (t $\ge$ 2/$\lambda$ = 40) is measured in §3.3: the pair escapes.
2. **The relative phase relaxed near in-phase.** $\Delta\theta$: $+0.265\to+0.244\to+0.227$ rad at t = 0, 2, 4—a slow decay toward in-phase, away from the $\pi$ branch. The anti-phase branch of the schematic pair model is not realized in this state.
3. **NS4 central-low-q morphology null.** Central q 0.7072 $\to$ 0.7074 versus flank q 0.6984 $\to$ 0.7009: central q sits above flanks at both endpoints. The $\varepsilon$-node exists by construction, but q is an outcome, and the outcome matches the in-phase central-antinode branch (`foundations/why-three-dimensions.md` §4.2), not an anti-phase paired-sheet morphology.
4. **Channel traces Wood/Fire-limited by the representability clamp.** Dominant channels [Wood, Fire] with a stable sheng relation and zero transitions over 4000 steps; the phase-partitioned conversion vectors have support only in Wood (strand A, $-0.00560\to-0.00470$) and Fire (strand B, $+0.00541\to+0.00449$); Earth/Metal/Water are identically zero in the phase partition. The gate-weighted vectors concentrate in the same two sectors (strand A at t = 0: Wood $-0.00418$, Earth $-0.00111$, Fire $-0.00028$), and their magnitudes decay slowly over the window. Five-sector traces beyond two sectors are not observable in the field angle.

The NS2 reference arm recovered its constructed reference exactly: the d0 arm has $\varepsilon\equiv0$ identically (anti-phase cancellation), a single static density ridge, $q=0.7082$ unchanged over t = 4, $\varepsilon_{\mathrm{mid}}=8.6\times10^{-15}$ at t = 4, $\rho_{\mathrm{mid}}=2.542$. The pair's midpoint at t = 4 ($q=0.7074$, $\varepsilon=-0.020$, $\rho=2.078$) differs in the way two flanking ridges differ from one ridge.

The lock-timescale suite (§3.3) measures the items this window left open: the pair escapes (no finite-separation attractor), the relative phase relaxes to $\Delta\theta=0.042$ rad, the realized interlace is the even multiple (coincident-pentagon 5-fold joint projection, TS5), and the gate-weighted trace remains Wood/Fire-limited (TS7, §1.3). The twist sector is measured in §3.2.

### 3.2 The TS6 twist probe (t = 4)

Protocol: `two-fluid/run_two_strand_twist_probe.py` (the committed script is the reproducible source; its run record `20260806_214650_twist` is generated output under `runs/`). Two arms with fresh solvers per arm: `twist` (helical pair, axial rate $\Omega_0=2\pi/N=0.1309$ rad/cell—one full turn per periodic box, half-turn across the $\pm2\sigma_z$ core, Tw(0) = 0.5) and `ztwist` (parallel ridges, $\Omega_0=0$). N = 48, $\lambda=0.05$, dt = 0.001, t = 4, gate `five`; the helical embedding of `consciousness/two-strand-qi-neuroscience.md` §3.3 with the axial rate left free—no $P_\parallel=2$, no $\varphi$ scaling imposed. The strands are $\varepsilon$-ridges of the one condensate ($\varepsilon=E_{\mathrm{ridge}}(g_1-g_2)$, $\rho=(1+\varphi^{-1})(1+\beta(g_1+g_2))$, tube $\sigma=3.5$ cells, axial envelope $\sigma_z=6$ cells, separation d = 12 cells, the house SEP). The twist observables are longitudinal, not a ball-lobe proxy: per-axial-slice tracking of the $|\varepsilon|$ ridges in the transverse plane gives $d(s)$, $\vartheta(s)$ (unwrapped), $\Omega=\partial_s\vartheta$, and $\mathrm{Tw}=\frac{1}{2\pi}\int\Omega\,ds$ over the fixed window $|s-24|\le12$ cells. The t = 0 check reproduces the construction to the grid scale (max$|\vartheta-\vartheta_{\mathrm{init}}|=0.0017$ rad; max$|d-12|=0.075$ cells; Tw = 0.5000; the ztwist arm measures $\vartheta\equiv0$).

The headline results:

1. **The initialized twist persisted over the t = 4 window.** $\mathrm{Tw}: +0.500\to+0.499$ (ratio 0.9976, band `persisted`); detection window constant at 25 slices, zero merged slices; $\langle\Omega\rangle: 0.1309\to0.1306$ rad/cell. The separation vector's axial orientation is a reproducible longitudinal observable of the current PDE. Lock-timescale persistence (t $\ge$ 2/$\lambda$ = 40) is unmeasured.
2. **No spontaneous twist generation.** The zero-twist arm measures $\mathrm{Tw}\equiv0.0000$ throughout: a parallel pair stays parallel. The PDE (isotropic diffusion, gated conversion, Poisson gravity) has no chiral or axial term, so twist is representable as initialized structure but has no source—the E5 twist sector is an initial-condition label on this window.
3. **No rung-periodicity relation emerged.** The axial field-phase spectrum is unchanged t = 0 → 4: dominant wavenumber 0.0400 cycles/cell in both arms at both times (the window fundamental set by the Gaussian envelope; the top three lines carry 98% of the power), and the axial field-phase gradient is bounded and small (max $|\partial_s\theta_{\mathrm{field}}|$ 0.0144 → 0.0121 rad/cell). Nothing locks $\Omega$ to a periodicity—expected without a coupling term.
4. **d and phase drift mirror the two-lobe probe.** d: 12.07 → 12.11 cells (never merged, never escaped); $\Delta\theta$: $+0.175\to+0.149$ rad (the same slow decay toward in-phase as §3.1, E7); $A_+=0.271$, $A_-=0.025$ at t = 4; the axial centroid offset stays $\le10^{-9}$ cells (no longitudinal displacement develops). Wrap and clamp telemetry: seam-plane density contrast ratio 2.1e-2 → 2.2e-2 (the Gaussian-tail floor; the helix itself closes exactly at the periodic seam), zero near-floor cells in both arms, ey_min = 1.0000, mass drift −1.4e-13.

Verdict: TS6's first leg passes—a reproducible longitudinal twist observable exists and persists on the characterization window; its second leg is null at this stage—no twist generation, no rung-periodicity relation, because the current PDE contains no source term for either. The generation leg needs the smallest scratch-layer term: a parity-odd coupling of the phase-current vorticity to the conversion rate, conv $\to -\lambda(1-\chi_{\mathrm{circ}}(\nabla\times J)_z/J_{\mathrm{scale}})(1-q)\varepsilon$ with $J=R^2\nabla\theta$ already derived from the field; $\chi_{\mathrm{circ}}=0$ must reproduce the canonical trajectory bit-for-bit, and the term vanishes at the $\varphi$-attractor ($J=0$ at $\varepsilon=0$). Implemented as a flagged scratch layer (`two-fluid/scratch_twist_chi_axial.py`, canonical solver untouched) and validated by `two-fluid/run_twist_chi_axial_ramp.py` (run records `runs/20260807_013639_chi_axial_ramp/` and `runs/20260807_014503_chi_axial_ramp/`, regenerated by the script). The layer computes the axial component $g=(\nabla\times J)_x$ in the solver label frame (x = grid axis 2 = the helix axis) $=-(\nabla\times J)_z$ in box-frame labeling, so the protocol parameter $\chi_{\mathrm{ax}}$ multiplies $-(\nabla\times J)_z$ (the sketch's $\chi_{\mathrm{circ}}=-\chi_{\mathrm{ax}}$); the convention is recorded, not fitted. $\chi_{\mathrm{ax}}=0$ reproduces the canonical trajectory bit-for-bit on both arms (exact equality of the field hats after every one of 4000 steps, solver scalar state at report cadence), and an analytic component check pins the sign to $2.2\times10^{-14}$ on a field with known axial curl. The mirror identity $d\mathrm{Tw}(\chi,-\Omega_0)=-d\mathrm{Tw}(\chi,+\Omega_0)$ holds to $4\times10^{-7}$ relative (the axial term is even under the box midplane reflection), and the response is even in $\chi$ ($d\mathrm{Tw}(-\chi)=d\mathrm{Tw}(+\chi)$ to $3\times10^{-11}$): the term couples to the twist amplitude, not to handedness. The t = 4 magnitude ramp is null (max $\|\Delta\mathrm{Tw}\|=5.0\times10^{-6}$ over $\chi\in\{\pm0.25,\dots,\pm2\}$, monotone in $|\chi|$, no clamp engagement, 0.25% f<0 cells at $\chi=\pm2$ only, ey_min $\ge$ 0.9999, mass drift ~1e-13). The t = 40 lock leg is null: Tw tracks the seed (0.448 at $2\pi/N$, 0.914 at $4\pi/N$, both ~9% decay), the $\chi=1$ response is $-1.0\times10^{-4}$ (W0) / $+2.8\times10^{-3}$ (2W0), the dominant axial wavenumber is unchanged (dom_k1 = 0.0435, fraction 0.90–0.97), and J_scale = 0.1718 at both seeds (the axial curl is transverse-gradient dominated). Generation-leg verdict across both windows: null—the axial component does not source twist; E5 remains open.

### 3.3 The TS1–TS5 lock-timescale suite (t = 40)

Protocol: `two-fluid/run_two_strand_suite.py` (the committed script is the reproducible source; its run record `20260806_214032_two_strand_suite` is generated output under `runs/`, regenerated by the script). Six arms, fresh solver per arm, N = 48, $\lambda=0.05$, dt = 0.001, t = 40 = 2/$\lambda$ (the lock timescale: 1/$\lambda$ is the conversion time, and the churning-gate discipline requires t $\ge$ 2/$\lambda$ before any settled-state claim), gate `five`: `sep12` (the §3.1 baseline pair), `sep6`, `sep3`, `sep0` (the one-string reference), `sym` (both ridges at 1.2$\times E_{\mathrm{ridge}}$), `asym` (ridges at 1.2$\times$ / 0.8$\times E_{\mathrm{ridge}}$). The `sep12` arm reproduces the t = 4 baseline exactly (all eight §3.1 quantities within tolerance) before extending it. Zero near-floor cells in all arms (ey_min $\ge$ 1.00, ei_min $\ge$ 0.52; the $10^{-3}$ clamp never fires).

The five verdicts:

1. **TS1 null—the pair escapes at the lock timescale.** $d$: 9.90 $\to$ 15.73 cells (back-20% mean 15.00 > 1.2$d_0$ = 11.88), still drifting apart at t = 40 (0.20 cells/unit t over the last 10%); the ridge amplitudes fade with the separation ($A_+$: 0.517 $\to$ 0.090), and the late-window d readings (t $\ge$ 37) sit near the tracking floor of the fading field. No finite-separation attractor exists under the existing PDE; the t = 4 `persisted` band is a characterization-window reading, not a bound state. The §8.1 consequence applies: the two-strand extension is not realized as Cassi physics.
2. **TS2 null—the $d\to0$ limit does not recover the one-string centerline.** At t = 40 the centerline observables of the separation series {0, 3, 6, 12} behave differently: $q_{\mathrm{mid}}$, $A_+$, and $q_{\mathrm{flank}}$ residuals vs the `sep0` reference are monotone in separation ($r_3<r_6<r_{12}$), but the $\rho_{\mathrm{mid}}$ residual diverges ($r_3=0.79 > r_6=0.75 > r_{12}=0.68$ cells; $\rho_{\mathrm{mid}}^{\mathrm{sep0}}=2.509$ vs $\rho_{\mathrm{mid}}^{\mathrm{sep3}}=1.718$ at t = 40). The small-separation arms do not relax onto the one-string ridge: they resolve into a pair at $d\approx3.1$–3.7 cells with a midpoint density dip. The pair is a separate relaxation channel, not an extension of the one-string theory.
3. **TS3 null—relative response exists, but the mode is not centerline-fixed and the imbalance bound fails.** The `sym` arm mirrors the control (escape then fade, as TS1); the `asym` arm shows a genuine relative-mode response—$d$ deviates from the control by up to 9.3 cells, $\Delta\theta$ by up to 0.042 rad—and the amplitude imbalance $m=(A_1-A_2)/(A_1+A_2)$ decays 0.261 $\to$ 0 by t $\approx$ 33, order-consistent with the §6 linearized rate ($\gamma(0)=0.0764$ at $\lambda=0.1$ $\to$ 0.0382 here, $\tau\approx26$). The formal §6 bound fails at the endpoint: $m(40)/m(0)=0.798\ge0.7$, because the imbalance inverts ($m=-0.209$) once the ridges fade below the tracking floor. The centerline drifts 3.35 cells in the `asym` arm—but the unperturbed control drifts 3.30 cells itself: no stationary centerline exists in this regime at all, and the recorded antisymmetric channel signature $(-0.96,-0.08,-0.26,-0.01,0.00)$ has cosine similarity 0.29 to the §6 linearized $c_i^-$, so the predicted Fire-positive signature is not realized.
4. **TS4 null—no central low-q node at the lock timescale.** $q_{\mathrm{mid}}=0.708094>q_{\mathrm{flank}}=0.707795$ at t = 40 (gap $+3.0\times10^{-4}$, below the 0.003 node threshold) and the field-measured $q(x)$ profile has no local minimum at the midpoint. The morphology is the in-phase central-antinode branch (`foundations/why-three-dimensions.md` §4.2) at both windows; the anti-phase paired-sheet morphology is not the solver's behavior.
5. **TS5 passed on its observed branch—the near-in-phase endpoint realizes the coincident-pentagon 5-fold joint projection.** $\Delta\theta$ decays 0.265 $\to$ 0.042 rad (2.4° at t = 40); with the interlace read as $\alpha:=\Delta\theta$ (the §4.3 operationalization), the joint vertex set $\{2\pi i/5+a\alpha\}$ classifies as **5-fold coincident (even interlace)** at the endpoint—the algebra's prediction for the near-in-phase state. The trajectory passes through a non-quantized 10-fold configuration for t < 30 before relaxing into coincidence; no odd interlace (decagon) is realized in this window, so the decagonal branch remains unrealized.

The suite leaves the §3.2 twist sector unchanged: initialized twist persists on its window with no generation term, and TS7's two-sector representability bound (§1.3) is unaffected. Stage-0 status: TS1–TS4 null, TS5 passed on its observed branch, TS6 first leg passed / generation null, TS7 realized.

### 3.4 The wake-binding scratch layer (E1/E3 candidate; measured 2026-08-07)

Protocol: `two-fluid/run_two_strand_binding_suite.py` (committed; run record `20260807_binding_suite` is generated output under `runs/`, regenerated by the script) and the unit-corrected re-test `two-fluid/run_two_strand_binding_unit_corrected.py` (committed; run records under `runs/`, regenerated by the script; t = 4 and t = 40 arm sets, fresh solver per arm, N = 48, $\lambda=0.05$, dt = 0.001, gate `five`). The smallest transport-capable scratch layer on the canonical solver (which is untouched): a damped-diffused wake field driven by the anti-phase source, $\partial_t W = -W/\tau_W + S_W/\tau_W + (\ell^2/\tau_W)\nabla^2 W$ with $S_W=(1-q)\varepsilon^2$, $\tau_W=1/\lambda=20$, coupling the strand densities mass-like through $\partial_t E_a \supset -\chi_w\,\mathrm{div}(E_a\,\nabla W)$; $\chi_w$ is the single protocol parameter (no framework constant registered). Acceptance: T1 $\chi_w=0$ bit-exact vs canonical, T2 monotone binding across the bracket, T3 sep0 one-string preservation, T4 no clamp pathologies.

Length convention: the solver's wave numbers are in rad/L units ($k=2\pi\,\mathrm{fftfreq}(N,d=\mathrm{d}x)$, fundamental $2\pi/L = 1.0$ rad/L at L = 2$\pi$), so the operator length is $\ell = \mathrm{ELL}_L = \mathrm{SIG}\cdot(L/N) = 0.6545$ L-units—the committed 5-cell ridge width expressed in the operator's units. A raw-cells value of $\ell$ (5 cells × rad/L) is dimensionally inconsistent and over-diffusive by $(5/0.6545)^2 = 58.4\times$: the factor $1+\ell^2k^2$ then retains ~4% of the box fundamental and ~0.25% of the pair-scale modes—the measured "transfer $W_{\mathrm{peak}}\sim1.6\times10^{-2}\,S_{\mathrm{peak}}$". fftn/ifftn are self-inverse; the suppression is the unit error in $\ell$, not an fftn normalization. The $\varepsilon^2$ source carries no length and is unchanged; the mass-like flux is unchanged. The corrected static wake on the frozen init has transfer $W^*/S = 0.217$ (vs 0.0164 under the raw-cells operator) and ridge flux speed $|\nabla W^*| = 1.97\times10^{-3}$ cells/t per unit $\chi_w$ (spectral gradient, finite-difference verified). Coupling calibration: $\chi^\* = 101.33$ sets the wake flux speed at the density ridges equal to the measured escape drift (~0.2 cells/t, the TS1 late-window rate); the bracket is the minimal $\{\chi^\*/3, \chi^\*, 3\chi^\*\} = \{33.78, 101.33, 304.0\}$.

Verdict: **null survives the unit correction—across the escape-calibrated bracket** $\{33.78, 101.33, 304.0\}$; no coupling binds the pair:

1. **The wake peaks at the $\varepsilon$-extrema, 1.65 cells outward of the density centers** ($\varepsilon$-extrema at 17.44/30.56 cells vs the $\rho$ ridges at 19.05/28.95; the W humps track the source humps under the corrected 5-cell smoothing): the flux sharpens each hump toward its own center and drags the pair apart—the wrong direction for binding. The measured ridge gradient of the static wake points outward ($\partial_x W^\* = \pm1.97\times10^{-3}$ cells/t per unit $\chi_w$).
2. **The $\varepsilon$-compression feedback is super-critical at the escape-calibrated coupling:** $\partial_t\varepsilon\supset-\chi_w\,\mathrm{div}(\varepsilon\nabla W)$ scales as $\varepsilon^3$ (Keller–Segel-type self-focusing). Every bracket arm collapses to NaN—t = 0.8 at $\chi_w=33.78$ (the sub-critical $\chi^\*/3$ arm), t = 0.5 at $\chi^\*=101.33$, t = 0.3 at $\chi_w=304$—so there is no inert window at or below the escape scale. TS1 at $\chi^\* = 101.33$ reads **escaped** (collapse before any binding; pre-collapse $d\approx12.8$).
3. **There is no coupling window in which the pair binds:** the corrected wake is 13$\times$ stronger than the raw-cells operator's (transfer 0.217 vs 0.0164), so sub-escape couplings are active rather than inert, yet the repulsive geometry and the super-critical $\varepsilon^3$ feedback leave the window empty from the escape-calibrated coupling down. E1 remains open; the wake mechanism as specified does not supply $d_0$.

Design-iteration candidates (each a distinct mechanism change; none registers a framework constant):

- (i) **$\rho$-weighted source** $S_W=(1-q)\,\rho\,\varepsilon^2/\langle\rho\rangle$—**rejected by gate-exact analysis.** The weight does not re-center the wake: on the committed two-lobe init the source humps sit at 17.53/30.47 cells along the ridge axis, only 0.09 cells inward of the plain $\varepsilon^2$ humps (17.44/30.56) and ~1.5 cells outward of the true density maxima (19.05/28.95—the cross-ridge tail pulls each $\rho$ peak toward the pair center, which is also why the measured $d_0=9.90<12$). The $\rho$ gradient is too weak ($\rho$ falls <1%/cell at $\ell=\mathrm{SIG}=5$) against the $\varepsilon^2$ plateau and the outward $(1-q)$ gate gradient. The $\varepsilon^3$ feedback is untouched: the core balance $\chi_w(1-q)\rho\varepsilon^2/(\ell^2\langle\rho\rangle)=\lambda(1-q)$ with the unit-corrected length puts the collapse boundary at $\chi_w^{\mathrm{crit}}\approx0.05$ (the raw-cells estimate sits 58.4$\times$ higher—the same unit error), so any binding-scale coupling is hundreds of times above it—the window stays empty.
- (ii) **sub-critical feedback bound**—cap the $\varepsilon$-compression—**rejected.** The cap is a fitted threshold (a protocol parameter with no framework anchor) that can manufacture any verdict by tuning; the framework's only derived saturation, the gate factor $(1-q)$, floors at $\varphi^{-6}+\varphi^{-8}\approx0.077$, so the $\varepsilon^3$ feedback survives below any cap. No field content supplies the attraction a cap would stabilize: the wake is slaved to the pair (the source sits on the ridges, the midpoint $\varepsilon$-node keeps a $W$-valley between them, and the mass-like flux pushes away from that valley), so a capped wake can only sharpen the ridges at their own centers.
- (iii) **Yin-excess pair initialization**—the framework's attractive branch from the $G_{\mathrm{eff}}$ sign derivation (buoyancy is self-repulsive for the Yang-excess pair)—implemented and measured as §3.5: the pair persists at finite separation through t = 40 (d 9.90 → 7.51), the first non-escape at the lock timescale, as a transient-driven contraction.

The open routes are each a new model degree, none a re-weighting of the existing fields: a steady-Yin-excess representation change with a derived negative attractor (e.g. sign-opposite conversion on the $\varepsilon<0$ half-space); and a wake sourced between the ridges ($S_W\propto|\nabla\varepsilon|^2$, the one source geometry in which the mass-like flux pulls the pair inward). The Yin-excess branch's longer-window fate is measured rather than open: the t = 80 continuation (§3.5) ends in coalescence at t $\approx$ 47, so the branch supplies no finite-$d$ equilibrium.

T1 passed (all field/history diffs exactly 0 at t = 4 and t = 40); T3 passed at t = 4 (field diffs exactly 0; the $\varepsilon$-digit reads $4.3\times10^{-13}$, float accumulation, below the $10^{-12}$ threshold) but is null on the strict $\varepsilon$ criterion at t = 40: the sep0 arm's divergence from $\chi_w=0$ appears only after t = 4 and stays at the mean-mode float level (max$|\mathrm{d}EY| = 2.6\times10^{-9}$, max$|\mathrm{d}u| = 2.8\times10^{-11}$, $\varepsilon$-digit $1.61\times10^{-12}$, marginally over $10^{-12}$)—the wake is inert at sep0, but the t = 40 run is not bit-exact; T4's only pathology is the collapse itself.

### 3.5 The Yin-excess pair branch (E1 candidate iii; measured 2026-08-07)

Protocol: `two-fluid/run_two_strand_yin_excess_suite.py` (committed; run record `20260807_014428_two_strand_yin_excess` is generated output under `runs/`, regenerated by the script). The smallest initialization-only change: the canonical two-lobe state with the Yang and Yin fields exchanged, $\Psi_Y\leftrightarrow\Psi_I$—the same $\rho$ ridges, the same $|\varepsilon|$ lobes, $\Pi=E_Y-E_I<0$ in every ridge. The buoyancy force $\mathbf{F}=\Pi\nabla\Phi$ of the existing PDE ($\Phi=-\nabla^{-2}\rho$, `two-fluid/cassi_two_fluid_3d_gpu.py`) is then self-attractive in the ridges: the framework-native attractive branch of the $G_{\mathrm{eff}}$ sign. No binding term, no new parameter, canonical solver untouched, fresh solver per arm; N = 48, $\lambda=0.05$, dt = 0.001, t = 40 = 2/$\lambda$, gate `five`. Three arms: `ctrl` (canonical Yang-excess pair—the counterfactual and machine reproduction), `ysep12` (Yin-excess pair), `ysep0` (Yin-excess one-string reference, $\varepsilon\equiv0$ by construction so $\varepsilon=-(φ-1)\rho<0$ everywhere, single ridge). Per-strand ridge positions are tracked from the density field (under the exchange, $E_Y$ is anti-correlated with density, so the probe's $E_Y$-slab y-tracker would place the strand balls on the background ring); $d$ comes from the $\rho$ x-profile as in the probe.

Representability (Y1): the positivity clamp is a floor ($E_Y,E_I\ge10^{-3}$), not a sign constraint—$\Pi<0$ needs $E_I>E_Y$ with both positive, and the swapped state has $\min(E_Y,E_I)=0.57\gg10^{-3}$ with $\Pi=[-0.753,-0.190]$ at the ridge cores and $\Pi_{\mathrm{tot}}=-4.27\times10^4$. A mere $\varepsilon$-sign flip does not reach the branch (the $(φ-1)\rho$ density pedestal keeps the cores Yang-excess, $\Pi=+0.16$). The branch is transient by construction: the conversion pair drives $\varepsilon\to0$ ($\partial_t\varepsilon=-\lambda(1+\varphi)(1-q)\varepsilon$), and $\varepsilon=0$ with $\rho>0$ gives $\Pi=(φ-1)E_I>0$, so every trajectory ends Yang-excess under the canonical conversion; a steady Yin-excess state would need a representation change that this test does not implement.

Verdict:

1. **The Yin-excess pair persists at finite separation through the lock timescale—the first non-escape outcome at t = 40.** $d$: 9.90 $\to$ 7.51 cells (back-20% mean 7.72, inside the §3 band), never merged, never escaped; the pair contracts monotonically at $\approx0.06$ cells/t through the window. The Yang-excess counterfactual escapes ($d$: 9.90 $\to$ 15.73, the published TS1 record reproduced exactly; the t = 4 baseline is reproduced too). Max $|d_{\mathrm{ysep}}-d_{\mathrm{ctrl}}|=8.23$ cells.
2. **The attractive phase is transient, but the inward momentum outlasts it.** Per-strand $\Pi$: $[-0.753,-0.190]\to[+0.254,+0.333]$; conversion erases the Yin excess by t $\approx$ 21 (first both-strands-positive record at t = 21.3), yet the pair keeps contracting ($d$ 8.60 $\to$ 7.51 over t $\in$ [21, 40])—the $\Pi<0$ phase's attractive impulse supplies inward velocity that persists after the sign flip. The t = 40 state is a slow contraction, not an equilibrium: no turnaround, $d$ still decreasing.
3. **The Yin-excess one-string reference is valid and static.** `ysep0` holds a single ridge at Rc = 24.00 with drift $1.5\times10^{-11}$ cells; $\Pi_{\mathrm{glob}}$: $-0.386\to+0.236$ (conversion restores Yang excess by t $\approx$ 16); $q$: 0.646 $\to$ 0.704; $\varepsilon_{\mathrm{mid}}=-0.30$ at t = 40 (the negative displacement still unwinding). The pair-vs-reference residuals at t = 40: $q_{\mathrm{mid}}$ $8\times10^{-5}$ (converged), $\varepsilon_{\mathrm{mid}}$ 0.051, $\rho_{\mathrm{mid}}$ 0.469—the pair midpoint keeps its two-ridge density dip, as in the Yang-excess TS2 record.
4. **Morphology and phase: the in-phase branch persists in the Yin-excess branch too.** $q_{\mathrm{mid}}$ 0.659 vs $q_{\mathrm{flank}}$ 0.660 at t = 4 and 0.704 vs 0.704 at t = 40: central q at/above flank q, no central low-q node (the anti-phase paired-sheet morphology stays unrealized). The relative phase relaxes $-0.265\to-0.038$ rad—the mirror of the Yang-excess record, the same slow approach to in-phase.
5. **Telemetry clean.** Zero floor touches in every arm (min $E_Y/E_I$ over the runs 0.57–1.03, far above the $10^{-3}$ floor), total mass drift $\le2\times10^{-12}$ (per-component drift ~50%/31% in the Yin arms is conversion transfer, not numerical loss), no NaN; $H_{\mathrm{end}}$ 0.0064 (ctrl) vs 0.0145 (Yin arms: the swapped initial ratio $r=1/\varphi$ drives stronger conversion-mode expansion while it unwinds), $a_{\mathrm{end}}$ 1.29 vs 2.88.

E1 status: the Yin-excess branch changes the lock-timescale outcome from escape to persistence at t = 40—the first finite-separation survival under the existing PDE—but the continuation (below) shows the branch is a transient that ends in coalescence, not an equilibrium. E1 (a finite-$d_0$ bound state with projected $K_d$, $T_d$) remains open; the remaining routes are the open model degrees of §3.4—a steady-Yin-excess representation change with a derived negative attractor, or a wake sourced between the ridges—each a new model term.

**Continuation (t = 80; measured 2026-08-07).** Protocol: `two-fluid/run_two_strand_yin_excess_continuation.py` (committed; run record `20260807_025739_two_strand_yin_excess_cont` is generated output under `runs/`, regenerated by the script). The same ysep12 arm (identical protocol and swapped initialization, fresh solver run from t = 0) extended to t = 80 = 4/$\lambda$; record-by-record continuity against the suite's ysep12 history for t ≤ 40 passes at float tolerance (max dynamics diff 5.1×10⁻⁵ cells; the per-component mass totals differ by ≤2.5×10⁻⁵ relative from cross-process float accumulation in the conversion partition, while the total mass matches to 10⁻¹¹ relative—the conserved invariant—in both runs). Outcome:

- **Coalescence at t ≈ 47, no turnaround.** $d$: 9.90 → 7.51 (t = 40) → 6.69 (t = 46) → 0.00 (t = 48, single tracked ridge). The contraction does not stall: the approach rate holds ≈ 0.06–0.18 cells/t through t ∈ [40, 46] as the ridges fade (A: 0.286/0.183 → 0.220/0.146), and by t = 48 the tracker resolves only a single ridge. The t = 80 axial density profile is one broad flat-top bump centered on the old pair midpoint (x ≈ 25, σ ≈ 7–8 cells, peak 2.13 vs background 1.62)—the coalesced remnant.
- **The remnant fades; the field relaxes to the Yang-excess one-string manifold.** A: 0.135 → 0.040 over t ∈ [48, 80]; $\varepsilon_{\mathrm{mid}}$: −0.25 → −0.04 (conversion nearly complete); q_mid: 0.704 → 0.708 (uniform, central q at flank level—no paired-sheet morphology at any time); $\Pi_{\mathrm{strand}}$: [+0.25, +0.33] → [+0.44, +0.44] (Yang-excess, stable after the t ≈ 21 flip; no second sign flip); ρ_mid: 2.06 → 1.82 (dissolving into the background). The Yin-excess branch therefore ends in the same attractor manifold as the Yang-excess branch—a single ε ≈ 0 ridge—via coalescence instead of escape.
- **Telemetry clean throughout.** Zero floor touches, total mass drift 4×10⁻¹², no NaN; H_end 0.0082 (H decays from 0.0145 as the ratio r = ⟨E_Y⟩/⟨E_I⟩ unwinds toward φ), a_end 4.39.

The t = 160 extension was not run: the assignment condition (still contracting without turnaround at t = 80) is not met—the pair coalesced at t ≈ 47—and the t = 80 state is a single fading ridge whose further evolution adds no branch information. The full branch trajectory is now measured under the existing PDE with no new terms: Yin-excess attraction (π < 0, t < 21) → inertial contraction (t ∈ [21, 47]) → coalescence (t ≈ 47) → diffusion fade.

### 3.6 The breathing scratch protocol (measured 2026-08-07)

Protocol: `two-fluid/run_two_strand_breathing_suite.py` (committed; run record `20260807_050644_two_strand_breathing` is generated output under `runs/`, regenerated by the script). The separation mode ("breathing," the second collective variable of `consciousness/two-strand-qi-neuroscience.md` §2) is driven by the smallest possible scratch operation: the discrete field exchange $\Psi_Y\leftrightarrow\Psi_I$—the init's own transformation, $\Pi\to-\Pi$ exactly, mass and positivity conserved—applied between steps at the in-process natural period $P_0$. The reference arm's pi_mid series has no dominant period in the $\lambda$-scale acceptance window $[1/(4\lambda),3/\lambda]$ (the FFT candidate 0.801 sits below it), so the schedule uses the fallback $P_0=1/\lambda=20$, the single existing conversion timescale; the measured natural flip t ≈ 21.3 ≈ 1/$\lambda$ is the branch's intrinsic alternation scale. The exchange is forced scratch physics—an externally imposed instantaneous operation applied between steps, the $\pi/2$ rotation of the SO(2) doublet (`foundations/why-three-dimensions.md` §2.3)—and its schedule is the protocol's only free dial. Fresh solver per arm, N = 48, $\lambda=0.05$, dt = 0.001, gate `five`; the canonical solver is untouched.

The discrete exchange is the first scratch test because the drive-mechanism audit of the existing terms closes the other routes: native conversion is a one-way valve ($\partial_t\Pi=-2\lambda(1-q)\varepsilon$, and $\varepsilon=0$ carries $\Pi=(\varphi-1)E_I>0$, so $\Pi\ge0$ is the only accessible attractor), and every committed drive is a single-component injection that rectifies into a pump ($\varepsilon_{\mathrm{peak}}=(\varphi I/\pi)T$, monotone, no resonance—`two-fluid/run_pump_resonance.py` §8.2; churning verdicts, `consciousness/neurodivergence-as-gate-configuration.md` §9; held-configuration drains, `consciousness/gender-as-qi-configuration.md` §8). Continuous doublet rotation is blocked at the mechanism layer: the $\Omega$ source half is unstable on the grid (`foundations/spiral-dynamics.md` §1.1, §7). The exchange is the one operation that can restore $\Pi<0$ after conversion erases it.

Verdict:

1. **The native reproduction is exact.** The no-drive reference arm (t = 80) is record-by-record identical to the committed continuation record (max diff 0.0, same-process deterministic): $\Pi$ flip at t = 21.3, coalescence at t = 47.6, d(40) = 7.5086, single merged ridge at t = 80, zero floor touches, total mass drift 4×10⁻¹².
2. **The exchange alternates per-ridge $\Pi$ by construction.** With exchanges at t = 20, 40, 60, 80, each ridge completes Yin→Yang→Yin cycles over the two-strand window (2 on ridge 0, 3 on ridge 1) with per-ridge $\Pi$ extrema at |$\Pi$| ≥ 0.05 (the stated protocol floor); $\Pi$ sign fractions are 0.52/0.42 Yin. The alternation is the exchange's own doing—$\Pi\to-\Pi$ at every swap, then conversion relaxes the excess on 1/$\lambda$. It is a driven artifact: the native dynamics contain no oscillation—the undriven arm's single flip is transient.
3. **The separation mode does not breathe—NULL.** d(t) contracts monotonically 9.90 → 7.5 (t = 40) → 6.45 (t = 60) and the pair coalesces at t = 61.9: zero d cycles (no extremum pair with span ≥ 0.5 cells at the 2P₀ period) and the limit-cycle diagnostic fails (relative Poincaré steps 0.25 → 1.00, not converged). The Yang phases of the forced cycle slow the contraction but never reverse the inward momentum. The exchange delays coalescence by 14.3 time units (61.9 vs 47.6) and pumps the merged remnant (A ≈ 0.78 at t = 62 vs the undriven fade), yet no breathing claim follows: the forced $\Pi$ alternation is a reduced-model alternation, and no native limit cycle exists in the separation sector. This is the distinction the two-cycle requirement enforces—a single sign flip, or even a forced sequence of sign flips, is not breathing.
4. **Telemetry clean.** Zero floor touches, total mass drift 4.8×10⁻¹², no NaN; a_end 15.0 (vs 4.39 undriven) and H_end 0.0192 (vs 0.0082)—the repeated exchanges keep the conversion-mode expansion pulsing as the global ratio r = ⟨E_Y⟩/⟨E_I⟩ is inverted each swap.
5. **The φ·P₀ and e·P₀ cadence arms and the churning-drive arm were not run.** The primary separation-mode null settles the discrete-exchange route: the matched exchange produces zero d cycles while per-ridge $\Pi$ alternates by construction, and the existing drive-family evidence (rectification law, churning and held-configuration verdicts cited above) bounds every continuous-drive alternative. No cadence control can restore an oscillation the separation sector does not exhibit under the exchange.

E1 status: unchanged—the breathing protocol does not realize a sustained two-strand oscillation, and the forced-exchange route is bounded (the separation mode is inert under it). A steady Yin-excess branch would still require the conversion-side representation change of §3.4 (a derived negative attractor $\varepsilon^*$), which remains open.

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

Odd multiples of $36^\circ$ interlace the two pentagons into a decagon; even multiples (including $\alpha=0$) give coincident pentagons with 5-fold symmetry; quadrature $\alpha=90^\circ$ is excluded. This theorem constrains the embedding map; it does not select which odd multiple, if any, the dynamics realize. Decagonal claims are conditional on an odd interlace, and none has been observed. The measured near-in-phase state relaxes to $\Delta\theta=0.042$ rad by t = 40, and the run's phase records realize the coincident-pentagon, 5-fold joint projection the theorem predicts for that even-multiple interlace (TS5, §3.3); no odd interlace has been observed.

---

## 5. Open Content and Effective Coefficients

| ID | Quantity | Status |
|----|----------|--------|
| E1 | Binding: $d_0$, $K_d$, $T_d$, $\mu_d$, $\gamma_d$ | Open; TS1 null: the pair escapes at the lock timescale (d 9.90 → 15.73 cells at t = 40, §3.3), so no finite-$d_0$ binding coefficients are projectable from the existing PDE. The wake aggregation scratch layer is null as well (§3.4): no binding window—every coupling in the escape-calibrated bracket $\{33.78, 101.33, 304.0\}$ (including the sub-critical $\chi^\*/3$ arm) drives Keller–Segel collapse. The Yin-excess init candidate is measured (§3.5): the pair persists at finite separation through t = 40 (d 9.90 → 7.51, slow contraction, no turnaround)—the first non-escape at the lock timescale—but the branch is transient (conversion erases $\Pi<0$ at t ≈ 21) and the t = 80 continuation ends in coalescence (d → 0 at t ≈ 47, remnant fading), so no equilibrium coefficients are projectable at any timescale; the $\rho$-weighted source and sub-critical feedback bound iterations are rejected (§3.4: the weight shifts the wake humps 0.09 cells and the $\varepsilon^3$ collapse boundary sits at $\chi_w^{\mathrm{crit}}\approx0.05$ with the unit-corrected length, far below any binding coupling; the cap is a fitted threshold with no attractive term) |
| E2 | Phase stiffness: $K_\theta=\mathcal{A}\cdot\kappa_\theta\mathcal{O}(d)$, $T_\theta$, $\mu_\theta$, $\gamma_\theta$ | Open; $\kappa_\theta=4\lambda\varphi R^4=0.6472$ is framework-derived (attractor curvature), the projection prefactor and overlap are unmeasured; the relative phase decays 0.265 → 0.042 rad over t = 40 (TS5 record, §3.3) |
| E3 | Wake coupling $g$, damping length $\ell$ | Open; the wake aggregation candidate was instantiated with $g=\chi_w$ (protocol parameter), $\ell=\mathrm{ELL}_L=\mathrm{SIG}\,(L/N)$ (unit-corrected), $\tau_W=1/\lambda$ and tested null (§3.4); the recorded iterations ($\rho$-weighted source, sub-critical bound) are rejected (§3.4); coefficients remain unprojected |
| E4 | Ridge width $\sigma_{\mathrm{ridge}}$ | Open; the run uses 5.0 cells as initialization, not a derived width |
| E5 | Twist: $\Omega$, $\mathrm{Tw}$ | Tested at t = 4: initialized half-twist persisted (Tw 0.500 → 0.499, band `persisted`); zero-twist arm null; the parity-odd scratch-layer generation candidate is implemented with the axial curl component ($\chi_{\mathrm{ax}}$, `two-fluid/scratch_twist_chi_axial.py`; $g=(\nabla\times J)_x$ in the solver label frame $=-(\nabla\times J)_z$ in box labels, so $\chi_{\mathrm{ax}}$ multiplies $-(\nabla\times J)_z$ and the sketch's $\chi_{\mathrm{circ}}=-\chi_{\mathrm{ax}}$) and is null on that component: t = 4 ramp max $\|\Delta\mathrm{Tw}\|=5.0\times10^{-6}$ over $\chi\in\{\pm0.25,\dots,\pm2\}$ (even in $\chi$, monotone in $|\chi|$), mirror identity $d\mathrm{Tw}(\chi,-\Omega_0)=-d\mathrm{Tw}(\chi,+\Omega_0)$ to $4\times10^{-7}$, no clamp engagement, §3.2; t = 40 lock leg: no lock—Tw tracks the seed (0.448 at $2\pi/N$, 0.914 at $4\pi/N$, both ~9% decay) and the $\chi=1$ response is $-1.0\times10^{-4}$ / $+2.8\times10^{-3}$ (null); $P_\parallel$ relation unmeasured |
| E6 | Interlace $\alpha=k_\perp d$ | Embedding choice, not derived; the decagon theorem constrains realizable values only; the realized endpoint ($\alpha:=\Delta\theta=2.4°$ at t = 40) is an even multiple, giving the 5-fold coincident joint projection; no odd interlace realized (§3.3) |
| E7 | Inter-strand phase drift $\Delta\omega$ | Measured: $\Delta\theta$ decays 0.265 → 0.042 rad over t = 40 = 2/$\lambda$; the endpoint is near in-phase, no quadrature (§3.3) |
| E8 | Matter-scale channel roles | Open; unformulated (§6) |

All E-series entries are effective collective coefficients to be projected from the existing PDE, not framework constants. Framework-level open derivations that bound the program: $P_\parallel(n)$ (human-scale $P_\parallel=2$ is Hypothesized), the mechanism fixing the $18^\circ$/rung affinity gradient, and the matter-sector opens of `particles/matter-organization.md` (n−p mass difference, charge, mass generation).

---

## 6. Matter-Organization Mechanism versus Bookkeeping

A bookkeeping rule records an observation in framework coordinates without adding constraints; a mechanism constrains or produces observations from the existing dynamics. The quality bar for matter organization is that the pair and the traces do work—select, bind, or relate—rather than relabel.

**Mechanism-level content that exists now:**

1. The trace graph and decagon theorem (§4): exact constraints on any embedding—no 10-step walk, odd-interlace quantization, quadrature excluded.
2. The attractor curvature $\kappa_\theta=4\lambda\varphi R^4=0.6472$: the relative-phase stiffness scale of the shared field.
3. Gate-derived imbalance damping (algebra on the solver's own gate response, non-overlap pair ansatz): the linearized antisymmetric amplitude mode is unconditionally damped—$B(\hat\delta)\ge\eta_3b_3-\eta_1b_1/8-\eta_2b_2\cdot0.220=0.0064>0$ ($\min B=0.0719$, $B(0)=0.2918$), $\gamma_{\mathrm{imb}}=\lambda(1+\varphi)B$, $\gamma(0)=0.0764$ at $\lambda=0.1$, equalization $\tau\approx13$ solver units; antisymmetric channel signature $c_i^-=(-0.236,+0.584,0,+0.056,+0.002)\,\hat\delta^-$; the sum gate is blind to the antisymmetric sector at linear order. The gate damps pair imbalance without new parameters. TS3 (PDE, §3.3) finds the imbalance decays through zero by t $\approx$ 33 in the antisymmetric arm, order-consistent with $\gamma(0)=0.0382$ at $\lambda=0.05$, but the recorded antisymmetric channel signature has cosine similarity 0.29 to $c_i^-$ and the centerline is not fixed—the linearized signature is not the realized one.
4. The representability bound (§1.3): a negative constraint—five-way field-angle selectivity is not realized; any five-peak claim must carry its own manifold extension.
5. The w = 5 / w = 10 coherence bounds, untouched by the trace graph.

**Bookkeeping that exists now:** ladder placements of measured scales—the proton/neutron pair at rung 91.5 (ledger class E/Mapped; the n−p difference is open), the lattice mass law $m=m_j/k$ (null against the uniform baseline, `particles/matter-organization.md` §2.3), DNA length placements (`consciousness/two-strand-qi-neuroscience.md` §6), and the muscle-cascade M2 boundary: Z-disc spacing sits at $n\approx139.2$–$139.7$ as a bookkeeping (Mapped-class) placement with no derived value until $P_\parallel(n)$ is derived (`hypotheses/muscle-cascade-lattice.md` §4.2). Channel labels on the baryon pair, on DNA complementarity, or on bilateral organization are bookkeeping until the traces are shown to select or bind.

**The proposal at its correct tier.** The two-strand pair is a candidate organizational rule for paired structures (baryon pair at 91.5, DNA complementarity, bilateral biology); the five traces are a candidate selection structure for pooling. Both are mappings today. The proposal becomes mechanism only when (a) the PDE supplies finite-$d_0$ binding with derived coefficients (E1/E2) and (b) a trace-graph or channel constraint selects among pooling candidates or binding channels (TS15). The wake aggregation scratch layer has been tested and is null (§3.4); the Yin-excess pair branch (§3.5) changes the lock-timescale outcome from escape to a slow contraction that ends in coalescence at t ≈ 47, and no equilibrium coefficients are projectable—the binding mechanism remains open.

---

## 7. The Staged Research Program

All labels are local to this program; none is a number in `predictions/falsifiable-predictions.md`. The two-strand doc's local targets NS1–NS7 (`consciousness/two-strand-qi-neuroscience.md` §7) remain the canonical anchors; TS labels extend or operationalize them.

| Stage | Label | Target | Falsifier |
|-------|-------|--------|-----------|
| 0: PDE gates (days, gates everything) | TS1 | NS1 at lock timescale: pair to t $\ge$ 2/$\lambda$ = 40, fresh solver per arm, §3 bands | No finite-separation attractor under the existing PDE → two-strand extension dead as Cassi physics; later stages continue only as generic organized-bilateral-activity science—**realized 2026-08-06** for the Yang-excess branch (pair escapes, d 9.90 → 15.73 at t = 40, §3.3); the Yin-excess branch (§3.5) persists at finite separation through t = 40 (d 9.90 → 7.51, slow contraction) but coalesces by t ≈ 47 (t = 80 continuation), so the no-attractor falsifier stands at every measured timescale |
| | TS2 | NS2 extended: separation series {0, 3, 6, 12} cells; centerline convergence as d $\to$ 0 | Convergence fails → the pair is a separate theory, not an extension—**realized**: $\rho_{\mathrm{mid}}$ residual diverges as d $\to$ 0 ($r_3=0.79>r_{12}=0.68$; §3.3) |
| | TS3 | NS3: symmetric/antisymmetric perturbation modes; antisymmetric mode moves (d, $\Delta\theta$) at fixed centerline | Antisymmetric perturbation moves the centerline, or no relative-mode response—**realized**: response present (d gap ≤ 9.3 cells) but centerline drift 3.35 cells (control 3.30); imbalance ratio 0.798 fails the §6 bound (§3.3) |
| | TS4 | NS4 re-test at lock timescale, phase from fields; current status null; test the in-phase central-antinode branch | No central low-q node at lock timescale → paired-sheet morphology is not the solver's behavior—**realized**: $q_{\mathrm{mid}}$ 0.708094 > $q_{\mathrm{flank}}$ 0.707795 at t = 40, no q(x) node (§3.3) |
| | TS5 | Interlace record: ($\Delta\theta$, $\alpha$, joint projection order); algebra predicts 5-fold coincident for near-in-phase states, 10-fold only for odd interlace | Realized interlace violates odd-multiple quantization (e.g., quadrature) → decagon theorem fails as embedding map—**not realized**: endpoint is the 5-fold coincident projection ($\Delta\theta$ = 0.042 rad); no odd interlace observed (§3.3) |
| | TS6 | Twist: filament initialization; $\Omega$, $\mathrm{Tw}$, P_parallel relation | No reproducible twist or rung-periodicity relation |
| | TS7 | Representability/channel manifold: characterize the first-quadrant bound; whether an Earth/Metal/Water-reaching extension exists without new parameters—**done 2026-08-06**: both projections two-sector (Wood/Fire); Earth needs signed fields, Metal/Water an angle-dependent gate (§1.3) | Mechanism layer remains two-sector; five-peak field-angle claims excluded at mechanism level—**realized** |
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

1. TS1 realized (2026-08-06): no finite-separation attractor under the existing PDE—the two-strand extension is not realized as Cassi physics, and later stages continue only as generic organized-bilateral-activity science.
2. TS8 fails → neural two-strand readout dead; a PDE strand solution (if TS1 passed) untouched.
3. TS9 returns uniform phase and zero/non-log gradient → five-channel and P_parallel neural mappings dead; w = 5 arithmetic and the PDE untouched.
4. TS13/TS14 fail → cross-scale delayed memory chain dead; activity-dependent transcription itself untouched.
5. All stages null → the framework's physics claims remain unscathed; only the two-strand/five-channel mappings are eliminated.

### 8.2 Epistemic boundaries

- **Derived:** paired-real SO(2) field and Qi diagnostics; anti-phase conversion sign; w = 5 and the sheng/ke structure, $\kappa=\varphi^{-1}$, $\Delta_c=\varphi^{-4}$, sub-critical ring gain; $\kappa_\theta=4\lambda\varphi R^4$; the trace graph $\mathbb{Z}_2\times\mathbb{Z}_5\cong\mathbb{Z}_{10}$, its cycle decomposition, and the decagon theorem (§4); the w = 10 decoherence bound, preserved; gate-derived imbalance damping and the antisymmetric channel signature (§6), as algebra on the existing gate response under the non-overlap pair ansatz.
- **Tested (PDE/gate):** NS1: the pair persists through the t = 4 characterization window but escapes by t = 40 = 2/$\lambda$ (d 9.90 → 15.73 cells, back-20% mean 15.00)—no finite-separation attractor under the existing PDE (TS1); NS2: the d0 reference is recovered exactly ($\varepsilon\equiv0$, single static ridge), but the separation series {0, 3, 6, 12} does not converge to the one-string centerline—$\rho_{\mathrm{mid}}$ residual diverges as d $\to$ 0 (TS2); NS3: relative response present (d gap up to 9.3 cells vs control), antisymmetric imbalance decays through zero by t $\approx$ 33, centerline drift 3.35 cells, recorded antisymmetric channel signature cosine 0.29 to the §6 $c_i^-$ (TS3); NS4: central-low-q morphology null at both windows ($q_{\mathrm{mid}}$ 0.708094 > $q_{\mathrm{flank}}$ 0.707795 at t = 40, no q(x) node; TS4); TS5: near-in-phase endpoint $\Delta\theta$ = 0.042 rad realizes the coincident-pentagon 5-fold joint projection, no odd interlace observed; traces Wood/Fire-limited, sheng-stable (one dominant-channel transition per pair arm as the field fades); TS6 twist probe: initialized half-twist persisted (Tw 0.500→0.499), zero-twist arm null—no generation term (§3.2); TS7 gate-weighted bound: dominant channel Wood/Fire only, Metal/Water non-dominant at any imbalance, gate direction-blind (`two-fluid/ts7_channel_manifold.py`). Referenced gate results: WX1/WX3 tested; WX2's $\kappa^3$ magnitude tested and not matched (`foundations/wu-xing-cycle-structure.md` §4).
- **Tested (PDE/gate), wake-binding scratch layer (2026-08-07):** the smallest transport-capable E1/E3 candidate—wake field $S_W=(1-q)\varepsilon^2$, $\tau_W=1/\lambda$, $\ell=\mathrm{ELL}_L=\mathrm{SIG}\,(L/N)$, mass-like flux $-\chi_w\,\mathrm{div}(E_a\nabla W)$—is null across the escape-calibrated bracket $\chi_w\in\{33.78, 101.33, 304.0\}$: $\chi_w=0$ is a bit-exact no-op vs the canonical solver (T1), the sep0 one-string is preserved bit-exactly at t = 4 (field diffs 0; at t = 40 the diffs stay float-level—max|dEY| $2.6\times10^{-9}$, max|du| $2.8\times10^{-11}$—but the strict $\varepsilon$ digit reads $1.61\times10^{-12}$, marginally over the $10^{-12}$ threshold, so T3 is null on that criterion at t = 40), but no coupling binds the pair—every bracket coupling, including the sub-critical $\chi^\*/3 = 33.78$ arm, drives $\varepsilon$-compression collapse (NaN at t = 0.8/0.5/0.3); TS1 at $\chi^\* = 101.33$ reads escaped (§3.4, `two-fluid/run_two_strand_binding_suite.py`, run record `20260807_binding_suite`, and the unit-corrected `two-fluid/run_two_strand_binding_unit_corrected.py`, run records under `runs/`). The operator length is unit-corrected (k in rad/L; the raw-cells length over-diffuses by 58.4×—the low-transfer reading that looked like an inert sub-critical window was that unit error, not an fftn normalization; the corrected transfer is 13× higher and still leaves no window). The recorded iterations are rejected by gate-exact analysis (§3.4): the $\rho$-weighted source shifts the wake humps 0.09 cells (still ~1.5 cells outward of the density maxima) and keeps the super-critical $\varepsilon^3$ feedback ($\chi_w^{\mathrm{crit}}\approx0.05$ with the unit-corrected length); the sub-critical bound is a fitted cap with no framework scale and no attractive term to stabilize. The open routes are new model degrees—a wake sourced between the ridges ($S_W\propto|\nabla\varepsilon|^2$) and a steady-Yin-excess representation change; the Yin-excess branch's t > 40 continuation is measured (§3.5): coalescence at t ≈ 47.
- **Tested (PDE/gate), Yin-excess pair branch (2026-08-07):** the smallest initialization-only change—the canonical two-lobe state with $E_Y\leftrightarrow E_I$ exchanged, $\Pi=E_Y-E_I<0$ in every ridge (representable under the positivity floor: min fields 0.57, $\Pi_{\mathrm{tot}}=-4.27\times10^4$; a mere $\varepsilon$-sign flip is insufficient, §3.5 Y1)—turns the lock-timescale outcome around: the pair persists at finite separation (d 9.90 → 7.51 cells, back-20% mean 7.72, no merge, no escape) while the Yang-excess counterfactual escapes (15.73); the Yin excess is transient (erased by conversion at t ≈ 21.3) and the t = 80 continuation ends in coalescence (d → 0 at t ≈ 47, single fading ridge, ε_mid −0.04, no turnaround), so E1 equilibrium coefficients remain unprojected at every measured timescale (§3.5, `two-fluid/run_two_strand_yin_excess_suite.py` and `two-fluid/run_two_strand_yin_excess_continuation.py`, run records `20260807_014428_two_strand_yin_excess` and `20260807_025739_two_strand_yin_excess_cont`).
- **Tested (PDE/gate), breathing scratch protocol (2026-08-07):** the discrete field exchange $\Psi_Y\leftrightarrow\Psi_I$—forced scratch physics, the SO(2) $\pi/2$ rotation, applied between steps at the in-process period $P_0=1/\lambda$—alternates per-ridge $\Pi$ (2–3 forced Yin→Yang→Yin cycles, §3.6) but leaves the separation mode inert: d contracts monotonically to coalescence at t ≈ 61.9 (vs 47.6 undriven, +14.3 delay), zero d cycles, limit-cycle diagnostic not converged. Breathing is NULL under the existing PDE with the exchange—the forced $\Pi$ alternation is a reduced-model artifact, no native limit cycle exists in the separation sector, and the discrete-exchange route is bounded (§3.6, `two-fluid/run_two_strand_breathing_suite.py`; run record `20260807_050644_two_strand_breathing` is regenerated by the script).
- **Hypothesized:** one condensate sustains two separated ridges over a finite window (no equilibrium at the lock timescale, TS1 null); $P_\parallel=2$ at human scale; neural readouts (TS8–TS10); the delayed chain (TS13/TS14); matter-scale channel roles (E8).
- **Speculative:** one universal strand geometry across DNA, neural, and cosmological scales; a subjective double-helix experience as direct perception; a $\varphi$-fixed preferred separation or pitch (gated behind NS7).
- **Open:** E1–E4, E6, E8 (§5; E5 tested, E7 measured); $P_\parallel(n)$; the $18^\circ$/rung mechanism; the n−p mass difference, charge, mass generation.

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
- `two-fluid/run_two_strand_twist_probe.py`—the TS6 filament twist probe (longitudinal Ω/Tw measurement, zero-twist counterfactual; run record 20260806_214650_twist is regenerated by the script)
- `two-fluid/run_two_strand_suite.py`—the TS1–TS5 lock-timescale suite (six fresh-solver arms at t = 40, §3.3 verdicts; run record 20260806_214032_two_strand_suite is regenerated by the script)
- `two-fluid/run_two_strand_binding_suite.py`—the wake-binding scratch-layer suite (E1/E3 candidate, T1–T4 acceptance, §3.4 verdicts; run record 20260807_binding_suite is regenerated by the script)
- `two-fluid/run_two_strand_binding_unit_corrected.py`—the unit-corrected wake-binding suite (operator length ELL_L = SIG·(L/N) against k in rad/L; escape-calibrated bracket; §3.4 verdicts; run records under `runs/` are regenerated by the script)
- `two-fluid/run_twist_chi_axial_ramp.py`—the axial twist-chi scratch-layer suite (E5 candidate, T0–T4 acceptance, §3.2 verdicts; run records 20260807_013639_chi_axial_ramp / 20260807_014503_chi_axial_ramp are regenerated by the script)
- `two-fluid/run_two_strand_yin_excess_suite.py`—the Yin-excess pair branch suite (E1 candidate iii, §3.5 verdicts; run record 20260807_014428_two_strand_yin_excess is regenerated by the script)
- `two-fluid/run_two_strand_yin_excess_continuation.py`—the Yin-excess pair t = 80 continuation (coalescence at t ≈ 47; run record `20260807_025739_two_strand_yin_excess_cont` is regenerated by the script)
- `two-fluid/run_two_strand_breathing_suite.py`—the breathing scratch protocol (discrete $\Psi_Y\leftrightarrow\Psi_I$ exchange at in-process $P_0=1/\lambda$; §3.6 verdicts; run record `20260807_050644_two_strand_breathing` is regenerated by the script)
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
- `two-fluid/ts7_channel_manifold.py`—TS7 representability audit: gate-weighted vs phase-angle reachable channel set, direction-blindness, missing degrees of freedom
- `two-fluid/run_trauma_wake_lock.py`—channel openness and solver gate replication
- `parameter-inventory.md`—$K_{fw}=\varphi^{-1}$, channel baselines, Fit-Status Ledger
- `predictions/falsifiable-predictions.md`—predictions 32–37, 43–46 (background; not extended here)
