# Two-Strand Five-Channel Matter Organization: A Research Program

## Status: Hypothesized—August 2026

## Abstract

One Qi condensate may organize into two spatial strands, and each strand carries five channel traces inherited from the Wu Xing gate. The first focused probe of that structure has a concrete outcome: a two-lobe pair persisted at finite separation over the t = 4 characterization window, the measured relative phase relaxed near in-phase rather than toward the anti-phase branch, the NS4 central low-coherence morphology was null (central q above flank q), and the per-strand channel traces were limited to the Wood/Fire sectors by the existing representability clamp. A second probe with a filament initialization measured the twist sector: the initialized half-twist persisted over the same window (Tw 0.500 → 0.499), a parallel pair generated no twist, and no rung-periodicity relation emerged. The lock-timescale suite (t = 40 = 2/$\lambda$, six fresh-solver arms) resolved the remaining PDE-level items: the pair escapes (no finite-separation attractor), the $d\to0$ limit does not recover the one-string centerline, the antisymmetric perturbation mode is not centerline-fixed, the central-low-q morphology stays null, and the near-in-phase endpoint realizes the coincident-pentagon 5-fold joint projection the algebra predicts—TS1–TS4 null, TS5 passed on its observed branch. This document states the framework content precisely—one field, two strands, five traces; the SO(2), five-sector, and P_parallel clocks kept distinct; the Z2×Z5 trace graph and the two-pentagon projection as exact algebra with the w = 5 no-C10-cycle bound preserved—then marks what is open: finite-$d_0$ binding (excluded under the existing PDE at lock timescale), twist generation, interlace selection, and the matter-scale roles of the channel traces. A staged program runs from PDE gates to neural, assembloid, and molecular tests under local labels only. Nothing here is a master prediction; no parameter or observable is introduced beyond those the framework already carries.

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

Verdict: TS6's first leg passes—a reproducible longitudinal twist observable exists and persists on the characterization window; its second leg is null at this stage—no twist generation, no rung-periodicity relation, because the current PDE contains no source term for either. The generation leg needs the smallest scratch-layer term: a parity-odd coupling of the phase-current vorticity to the conversion rate, conv $\to -\lambda(1-\chi_{\mathrm{circ}}(\nabla\times J)_z/J_{\mathrm{scale}})(1-q)\varepsilon$ with $J=R^2\nabla\theta$ already derived from the field; $\chi_{\mathrm{circ}}=0$ must reproduce the canonical trajectory bit-for-bit, and the term vanishes at the $\varphi$-attractor ($J=0$ at $\varepsilon=0$). Implemented as a flagged scratch layer (`two-fluid/scratch_twist_chi.py`, canonical solver untouched) and validated by `two-fluid/run_twist_chi_ramp.py` (run records under `runs/20260806_235330_chi_ramp/` and `runs/20260806_235509_chi_ramp/`): $\chi_{\mathrm{circ}}=0$ reproduces the canonical trajectory bit-for-bit on both arms (exact equality of the field hats after every one of 4000 steps, solver scalar state at report cadence); the mirror identity $(\chi,\Omega_0)\to(-\chi,-\Omega_0)$ holds to machine precision (Tw +0.4989 vs −0.4989 at t = 4), and the χ-flip response is sign-exact at every $\chi$ with the fitted $\Delta\mathrm{Tw}(\chi)=(-1.16\times10^{-4})\chi+(1.6\times10^{-5})\chi^2$ (t = 4; the quadratic residual is 14% of the linear term at $\chi=1$, so the strict linear-response mirror criterion holds only at small $\chi$). The magnitude ramp ($\chi\in\{0,\pm0.25,\pm0.5,\pm1,\pm2\}$) is monotone in $|\chi|$ with no clamp engagement (near-floor fraction zero, ey_min ≥ 0.9999), a domain exit exactly where derived (cells with $\chi g/J_{\mathrm{scale}}>1$ from t = 0 at $\chi=\pm2$, 0.28% of cells), and max $|\Delta\mathrm{Tw}|=3.3\times10^{-4}$ over the window—30× below the 0.01 generation threshold: the generation leg is null on the characterization window. The term vanishes at the $\varphi$-attractor by construction (pointwise $\varepsilon=0\Rightarrow J=0$), and its response is quadratic in the imbalance there (attractor Jacobian unchanged, slope $-\lambda(1+\varphi)(1-q)$). Component note: the canonical solver's wavenumber arrays are cyclically labeled (self.kz holds the axis-0 wavenumber), so the layer—which uses the solver's gradient helpers verbatim—couples to the curl component along grid axis 0, $-( \nabla\times J)_x$ in box-frame labeling, not the axial $(\nabla\times J)_z$ of the sketch; the term is parity-odd and attractor-vanishing for any curl component, so the verdicts above are valid measurements of the implemented component, and the axial variant is part of the pending follow-up. The t = 40 periodicity-lock leg ($\Omega_0\in\{2\pi/N,\,4\pi/N\}$, $\chi\in\{0,1\}$, `run_twist_chi_ramp.py --tests 4`) is a pending follow-up; its $\chi=0$ baseline arm at t = 40 reproduces the TS1 escape (d 12.07 → 14.28 cells, window 25 → 23 slices) with Tw decaying 0.500 → 0.448.

### 3.3 The TS1–TS5 lock-timescale suite (t = 40)

Protocol: `two-fluid/run_two_strand_suite.py` (the committed script is the reproducible source; its run record `20260806_214032_two_strand_suite` is generated output under `runs/`, regenerated by the script). Six arms, fresh solver per arm, N = 48, $\lambda=0.05$, dt = 0.001, t = 40 = 2/$\lambda$ (the lock timescale: 1/$\lambda$ is the conversion time, and the churning-gate discipline requires t $\ge$ 2/$\lambda$ before any settled-state claim), gate `five`: `sep12` (the §3.1 baseline pair), `sep6`, `sep3`, `sep0` (the one-string reference), `sym` (both ridges at 1.2$\times E_{\mathrm{ridge}}$), `asym` (ridges at 1.2$\times$ / 0.8$\times E_{\mathrm{ridge}}$). The `sep12` arm reproduces the t = 4 baseline exactly (all eight §3.1 quantities within tolerance) before extending it. Zero near-floor cells in all arms (ey_min $\ge$ 1.00, ei_min $\ge$ 0.52; the $10^{-3}$ clamp never fires).

The five verdicts:

1. **TS1 null—the pair escapes at the lock timescale.** $d$: 9.90 $\to$ 15.73 cells (back-20% mean 15.00 > 1.2$d_0$ = 11.88), still drifting apart at t = 40 (0.20 cells/unit t over the last 10%); the ridge amplitudes fade with the separation ($A_+$: 0.517 $\to$ 0.090), and the late-window d readings (t $\ge$ 37) sit near the tracking floor of the fading field. No finite-separation attractor exists under the existing PDE; the t = 4 `persisted` band is a characterization-window reading, not a bound state. The §8.1 consequence applies: the two-strand extension is not realized as Cassi physics.
2. **TS2 null—the $d\to0$ limit does not recover the one-string centerline.** At t = 40 the centerline observables of the separation series {0, 3, 6, 12} behave differently: $q_{\mathrm{mid}}$, $A_+$, and $q_{\mathrm{flank}}$ residuals vs the `sep0` reference are monotone in separation ($r_3<r_6<r_{12}$), but the $\rho_{\mathrm{mid}}$ residual diverges ($r_3=0.79 > r_6=0.75 > r_{12}=0.68$ cells; $\rho_{\mathrm{mid}}^{\mathrm{sep0}}=2.509$ vs $\rho_{\mathrm{mid}}^{\mathrm{sep3}}=1.718$ at t = 40). The small-separation arms do not relax onto the one-string ridge: they resolve into a pair at $d\approx3.1$–3.7 cells with a midpoint density dip. The pair is a separate relaxation channel, not an extension of the one-string theory.
3. **TS3 null—relative response exists, but the mode is not centerline-fixed and the imbalance bound fails.** The `sym` arm mirrors the control (escape then fade, as TS1); the `asym` arm shows a genuine relative-mode response—$d$ deviates from the control by up to 9.3 cells, $\Delta\theta$ by up to 0.042 rad—and the amplitude imbalance $m=(A_1-A_2)/(A_1+A_2)$ decays 0.261 $\to$ 0 by t $\approx$ 33, order-consistent with the §6 linearized rate ($\gamma(0)=0.0764$ at $\lambda=0.1$ $\to$ 0.0382 here, $\tau\approx26$). The formal §6 bound fails at the endpoint: $m(40)/m(0)=0.798\ge0.7$, because the imbalance inverts ($m=-0.209$) once the ridges fade below the tracking floor. The centerline drifts 3.35 cells in the `asym` arm—but the unperturbed control drifts 3.30 cells itself: no stationary centerline exists in this regime at all, and the recorded antisymmetric channel signature $(-0.96,-0.08,-0.26,-0.01,0.00)$ has cosine similarity 0.29 to the §6 linearized $c_i^-$, so the predicted Fire-positive signature is not realized.
4. **TS4 null—no central low-q node at the lock timescale.** $q_{\mathrm{mid}}=0.708094>q_{\mathrm{flank}}=0.707795$ at t = 40 (gap $+3.0\times10^{-4}$, below the 0.003 node threshold) and the field-measured $q(x)$ profile has no local minimum at the midpoint. The morphology is the in-phase central-antinode branch (`foundations/why-three-dimensions.md` §4.2) at both windows; the anti-phase paired-sheet morphology is not the solver's behavior.
5. **TS5 passed on its observed branch—the near-in-phase endpoint realizes the coincident-pentagon 5-fold joint projection.** $\Delta\theta$ decays 0.265 $\to$ 0.042 rad (2.4° at t = 40); with the interlace read as $\alpha:=\Delta\theta$ (the §4.3 operationalization), the joint vertex set $\{2\pi i/5+a\alpha\}$ classifies as **5-fold coincident (even interlace)** at the endpoint—the algebra's prediction for the near-in-phase state. The trajectory passes through a non-quantized 10-fold configuration for t < 30 before relaxing into coincidence; no odd interlace (decagon) is realized in this window, so the decagonal branch remains unrealized.

The suite leaves the §3.2 twist sector unchanged: initialized twist persists on its window with no generation term, and TS7's two-sector representability bound (§1.3) is unaffected. Stage-0 status: TS1–TS4 null, TS5 passed on its observed branch, TS6 first leg passed / generation null, TS7 realized.

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
| E1 | Binding: $d_0$, $K_d$, $T_d$, $\mu_d$, $\gamma_d$ | Open; TS1 null: the pair escapes at the lock timescale (d 9.90 → 15.73 cells at t = 40, §3.3), so no finite-$d_0$ binding coefficients are projectable from the existing PDE |
| E2 | Phase stiffness: $K_\theta=\mathcal{A}\cdot\kappa_\theta\mathcal{O}(d)$, $T_\theta$, $\mu_\theta$, $\gamma_\theta$ | Open; $\kappa_\theta=4\lambda\varphi R^4=0.6472$ is framework-derived (attractor curvature), the projection prefactor and overlap are unmeasured; the relative phase decays 0.265 → 0.042 rad over t = 40 (TS5 record, §3.3) |
| E3 | Wake coupling $g$, damping length $\ell$ | Open |
| E4 | Ridge width $\sigma_{\mathrm{ridge}}$ | Open; the run uses 5.0 cells as initialization, not a derived width |
| E5 | Twist: $\Omega$, $\mathrm{Tw}$ | Tested at t = 4: initialized half-twist persisted (Tw 0.500 → 0.499, band `persisted`); zero-twist arm null; the parity-odd scratch-layer generation candidate ($\chi_{\mathrm{circ}}$, `two-fluid/scratch_twist_chi.py`) is implemented and its t = 4 ramp is null (max $\|\Delta\mathrm{Tw}\|=3.3\times10^{-4}$ over $\chi\in\{\pm0.25,\dots,\pm2\}$, no clamp engagement, §3.2); P_parallel relation unmeasured; t = 40 lock leg pending follow-up |
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

**The proposal at its correct tier.** The two-strand pair is a candidate organizational rule for paired structures (baryon pair at 91.5, DNA complementarity, bilateral biology); the five traces are a candidate selection structure for pooling. Both are mappings today. The proposal becomes mechanism only when (a) the PDE supplies finite-$d_0$ binding with derived coefficients (E1/E2) and (b) a trace-graph or channel constraint selects among pooling candidates or binding channels (TS15).

---

## 7. The Staged Research Program

All labels are local to this program; none is a number in `predictions/falsifiable-predictions.md`. The two-strand doc's local targets NS1–NS7 (`consciousness/two-strand-qi-neuroscience.md` §7) remain the canonical anchors; TS labels extend or operationalize them.

| Stage | Label | Target | Falsifier |
|-------|-------|--------|-----------|
| 0: PDE gates (days, gates everything) | TS1 | NS1 at lock timescale: pair to t $\ge$ 2/$\lambda$ = 40, fresh solver per arm, §3 bands | No finite-separation attractor under the existing PDE → two-strand extension dead as Cassi physics; later stages continue only as generic organized-bilateral-activity science—**realized 2026-08-06**: pair escapes (d 9.90 → 15.73 at t = 40, §3.3) |
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
