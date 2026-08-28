# Phase-Staggered Scale Gaps in the Cassi Wave Equation

## Status: Hypothesized mechanism; Derived channel decomposition; tested conditional realization—August 2026

## Abstract

Adjacent supplied Cassi wake carriers have an exact beat envelope whose demodulated sign alternates from one envelope antinode to the next. Equal-amplitude carriers place exact nodes between those antinodes; unequal amplitudes leave residual troughs with contrast

$$
C_{\rm gap}=\frac{2A_YA_I}{A_Y^2+A_I^2}.
$$

The layers are additively spaced in ordinary radius. A multiplicative $\varphi$ ladder appears only when log-radius phase is supplied as a separate coordinate law. In the default CassiCosmos second-order wave equation, the density and imbalance normal modes have thresholds $0$ and $\varphi\omega_0$. A harmonic drive at the supplied frequency $\Omega_*=\varphi^{3/2}\omega_0$ gives the two propagating wavenumbers the ratio $\varphi$ and produces a phase-staggered additive layer train. A generic control frequency gives ratio $1.31186$, and the live source law contains no selector for $\Omega_*$. Uniform phase staggering leaves a nearest-neighbor spectrum gapless; physical link modulation opens the tested unit gap and suppresses 12-cell transmission to $4.738\times10^{-6}$.

The resulting answer is conditional. Interference nodes can mark where a scale switch acts. A sharp switch requires a constitutive law that turns those nodes into coupling- or amplitude-magnitude modulation. Phase alternation alone supplies no spectral gap, no multiplicative radial ladder, and no endogenous selection of the $\varphi$ wavenumber ratio.

---

## 1. Question and frozen evidence

The campaign tests four distinct claims:

1. adjacent-rung carriers alternate average phase across neighboring beat layers;
2. destructive gaps sharpen transitions between those layers;
3. ordinary radial propagation generates multiplicative $\varphi$ spacing;
4. the live second-order field law selects the required carrier ratio by itself.

The frozen parent protocol is `field-experience/phase-staggered-scale-gap-pre-registration.md`. Its two time-domain receipts are:

- `runs/20260827T093422Z_phase_staggered_scale_gap/results.json`;
- `runs/20260827T093616Z_phase_staggered_scale_gap/results.json`.

Both receipts preserve the failed sub-gap time-domain quality gate. The registered replacement lengthened the run once. The longer run still contained an undamped freely propagating transient, so no additional time-domain replacement was authorized.

The fresh closure protocol is `field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md`. Its single authorized receipt is:

- `runs/20260827T093929Z_phase_staggered_scale_gap_lockin/results.json`.

The closure solves the same radial channel equations directly at the drive frequency with outgoing or decaying boundary conditions. It does not overwrite either time-domain receipt.

---

## 2. Exact adjacent-wake phase structure

Take supplied adjacent-rung carriers

$$
F(x)=A_Y\cos(k_Yx)+A_I\cos(k_Ix),
\qquad
k_Y=\frac{2\pi}{\ell_n},\quad
k_I=\frac{2\pi}{\ell_{n-1}}=\varphi k_Y.
$$

For equal amplitudes $A_Y=A_I=A$,

$$
F(x)=2A\cos\!\left(\frac{\Delta k}{2}x\right)
       \cos\!\left(\bar{k}x\right),
$$

with

$$
\Delta k=k_I-k_Y=\frac{k_Y}{\varphi}
=\frac{2\pi}{\ell_{n+1}},
\qquad
\bar{k}=\frac{k_Y+k_I}{2}.
$$

The envelope antinodes occur at

$$
x_m=\frac{2\pi m}{\Delta k}=m\ell_{n+1}.
$$

After demodulation by the carrier $\cos(\bar{k}x)$, the envelope sign at successive antinodes is

$$
\operatorname{sgn}\!\left[\cos\!\left(\frac{\Delta kx_m}{2}\right)\right]
=(-1)^m.
$$

Therefore adjacent antinodes are anti-correlated and next-nearest antinodes are correlated. The frozen numerical certificate measured

| Quantity | Measured | Gate |
|---|---:|---:|
| next-rung closure residual | $1.776\times10^{-15}$ | $\le10^{-12}$ |
| equal-amplitude node maximum | $2.305\times10^{-14}$ | $\le10^{-12}$ |
| adjacent demodulated correlation | $-1.000000000000$ | $|\operatorname{corr}_{1}+1|\le10^{-12}$ |
| next-nearest correlation | $+1.000000000000$ | $|\operatorname{corr}_{2}-1|\le10^{-12}$ |

For unequal amplitudes,

$$
I_{\max}=(A_Y+A_I)^2,
\qquad
I_{\min}=(A_Y-A_I)^2,
$$

so

$$
C_{\rm gap}
=\frac{I_{\max}-I_{\min}}{I_{\max}+I_{\min}}
=\frac{2A_YA_I}{A_Y^2+A_I^2}.
$$

The three frozen amplitude-ratio arms $A_I/A_Y\in\{1,0.8,0.5\}$ matched this law with zero measured residual. Exact destructive gaps require equal modal amplitudes. Phase staggering survives amplitude imbalance while the troughs become nonzero.

**Claim verdict: SUPPORTS for supplied adjacent-rung carriers.** The result is a wave identity and a phase-sensitive diagnostic. It does not establish physical condensation at the antinodes.

---

## 3. Additive and multiplicative radial spacing

For two ordinary radial carriers with fixed wavenumbers, constructive surfaces obey

$$
\Delta k\,r_m+\delta=2\pi m,
$$

hence

$$
r_{m+1}-r_m=\frac{2\pi}{\Delta k}.
$$

The spacing is additive. The frozen control measured an additive-spacing residual of $0$ and a log-spacing RMS residual of $0.502630$.

A log-periodic profile

$$
F_{\log}(r,t)=
\cos\!\left[
\pi\left(\frac{\ln(r/r_0)}{\ln\varphi}-c_ut\right)
\right]
$$

has signed antinode surfaces

$$
r_m(t)=r_0\varphi^{m+c_ut}
=r_0\varphi^m e^{c_ut\ln\varphi},
$$

so $r_{m+1}/r_m=\varphi$. This is a separate scale-covariant coordinate law supplied by construction. Ordinary radial beating does not derive it.

### 3.1 Frozen C4 integrity finding

The parent protocol requires the finite-difference log-surface speed residual to be at most $10^{-12}$. The executed script used $10^{-9}$ for its C4 Boolean, and the receipt reports $4.056\times10^{-11}$. The receipt's printed Stage C `PASS` therefore does not satisfy the frozen C4 threshold. The analytic identity

$$
\frac{dr_m}{dt}=c_u\ln\varphi\,r_m
$$

follows exactly by differentiating the supplied surface law, while the registered numerical Stage C result remains formally failed at C4. No replacement run is introduced.

**Claim verdict: CONTRADICTS endogenous multiplicative spacing from ordinary radial beats.** The log-periodic control verifies only the explicitly supplied multiplicative coordinate law.

---

## 4. Normal modes of the default second-order field law

The default CassiCosmos wave branch uses the restoring frequency $\omega_{0,\mathrm{wave}}$, written $\omega_0$ below. Its second-order equations are

$$
\ddot E_Y=c^2\nabla^2E_Y-\omega_0^2(E_Y-\varphi E_I)+S_Y,
$$

$$
\ddot E_I=c^2\nabla^2E_I+\omega_0^2(E_Y-\varphi E_I)+S_I.
$$

This is the `ham_completion = 0` branch of `CassiCosmos/compute/cassi_two_fluid.glsl`. Define

$$
\rho=E_Y+E_I,
\qquad
\epsilon=E_Y-\varphi E_I.
$$

Using $1+\varphi=\varphi^2$ gives the exact channel equations

$$
\boxed{\ddot\rho=c^2\nabla^2\rho+S_\rho},
$$

$$
\boxed{\ddot\epsilon=c^2\nabla^2\epsilon-\varphi^2\omega_0^2\epsilon+S_\epsilon},
$$

where

$$
S_\rho=S_Y+S_I,
\qquad
S_\epsilon=S_Y-\varphi S_I.
$$

The density channel is massless. The imbalance channel has threshold

$$
\boxed{\Omega_g=\varphi\omega_0}.
$$

For harmonic frequency $\Omega>\Omega_g$,

$$
k_\rho=\frac{\Omega}{c},
\qquad
k_\epsilon=\frac{\sqrt{\Omega^2-\varphi^2\omega_0^2}}{c}.
$$

The equation $k_\rho/k_\epsilon=\varphi$ has one positive solution:

$$
\boxed{\Omega_*=\varphi^{3/2}\omega_0}.
$$

Thus the channel law supplies a real propagation threshold. The exact $\varphi$ wavenumber ratio requires the supplied frequency $\Omega_*$. The live source contains a spatial Gaussian scaled by `source_strength` plus a mass-density deposit; neither source function reads `pc.t`, and the current path has no harmonic source or cavity filter that selects $\Omega_*$.

The first-order canonical density PDE in `foundations/cassi-first-principles.md` §8.2 is a different model boundary. It carries nonnegative real densities and shared flow without a compact wave phase. The phase-layer result therefore belongs to the second-order CassiCosmos wave branch and to supplied-wave diagnostics.

---

## 5. Driven radial realization

The parent radial probe uses spherical symmetry with $u(r,t)=rE(r,t)$, which turns each three-dimensional channel outside the origin into a one-dimensional wave or Klein-Gordon equation. It drives four frozen arms:

| Arm | Frequency | Channels driven | Purpose |
|---|---:|---|---|
| D0 | $0.9\varphi\omega_0$ | $\rho,\epsilon$ | sub-gap attenuation |
| D1 | $\varphi^{3/2}\omega_0$ | $\rho,\epsilon$ | tuned ratio and layers |
| D2 | $2.5\omega_0$ | $\rho,\epsilon$ | generic-frequency control |
| D3 | $\varphi^{3/2}\omega_0$ | $\rho$ only | two-mode requirement |

The valid propagating-arm measurements from the frozen parent receipt are:

| Quantity | Measured | Frozen criterion |
|---|---:|---:|
| tuned $k_\rho/k_\epsilon$ | $1.618271586$ | within 2% of $\varphi$ |
| generic $k_\rho/k_\epsilon$ | $1.311925567$ | at least 0.1 from $\varphi$ |
| layer-spacing residual | $1.112\times10^{-16}$ | $\le2\%$ |
| adjacent phase parity | $-0.999932783$ | $\le-0.95$ |
| measured layer contrast | $0.964525098$ | $>0.8$ |
| contrast-law residual | $3.930\times10^{-4}$ | $\le0.05$ |
| D3 imbalance amplitude | $0$ | $<10^{-12}$ |

The first D0 receipt gave attenuation $1.158827$ and the registered longer replacement gave $1.391807$, both above the required $10^{-2}$. Their fitted travelling wavenumbers and high $R^2$ values identify undamped free transients inside the finite lock-in windows. The parent Stage D verdict remains `INCONCLUSIVE` under its frozen quality rule.

D3 deliberately has no imbalance signal, so its epsilon phase-fit fields are undefined and serialize as `NaN`; `expected_k_epsilon` is intentionally `null` for the evanescent D0 arm and the absent D3 channel. The operative D3 metric is the exactly zero imbalance amplitude. These undefined reference and fit fields violate a literal all-metrics-finite reading and do not change the already `INCONCLUSIVE` parent Stage D status.

### 5.1 Frequency-domain closure

The independent lock-in protocol removes the transient ambiguity by solving the driven Helmholtz systems directly at frequency $\Omega$. Its quality gates all pass:

| Quantity | Measured | Gate |
|---|---:|---:|
| maximum linear residual | $8.072\times10^{-12}$ | $<10^{-10}$ |
| minimum fit $R^2$ | $0.999999739834$ | $\ge0.99$ |
| minimum median amplitude | $4.998\times10^{-3}$ | $>10^{-12}$ |

The sub-gap arm gives

$$
\kappa_{\rm fit}=0.705275510,
\qquad
\kappa_{\rm expected}=0.705284664,
$$

with attenuation $|U(30)|/|U(12)|=3.067\times10^{-6}$. The propagating arms give

$$
\left(\frac{k_\rho}{k_\epsilon}\right)_{\Omega_*}=1.618096626,
$$

$$
\left(\frac{k_\rho}{k_\epsilon}\right)_{2.5\omega_0}=1.311855471.
$$

All four propagating lock-in rates agree with the valid parent time-domain fits to maximum relative residual $1.319\times10^{-4}$.

**Combined claim verdict: EMERGES CONDITIONAL.** The second-order equation supports a phase-staggered additive radial layer train when both channels are harmonically driven above threshold. The tuned $\varphi$ ratio is source-selected, and the parent time-domain receipt retains its own `INCONCLUSIVE` label.

**Automatic-selection verdict: CONTRADICTS.** The generic arm does not approach $\varphi$, and no current source law selects $\Omega_*$.

---

## 6. Does phase staggering open a gap?

A uniform nearest-neighbor chain with alternating site phase is related to the unstaggered chain by the diagonal gauge transformation

$$
G=\operatorname{diag}(1,-1,1,-1,\ldots).
$$

The transformation changes coupling signs and preserves eigenvalues. The 128-site control measured

| Quantity | Measured |
|---|---:|
| gauge residual | $0$ |
| spectral-symmetry residual | $0$ |
| central gap | $8.228\times10^{-17}$ |

Therefore uniform phase staggering is gapless.

The declared physical modulation control alternates coupling magnitudes,

$$
K_1=1.25,
\qquad
K_2=0.75.
$$

Its central gap is

$$
\Delta=2|K_1-K_2|=1,
$$

and its 12-cell transmission intensity is

$$
T=\left(\frac{K_2}{K_1}\right)^{24}
=4.738\times10^{-6}.
$$

The live shader's pass B computes the field-norm diagnostic

$$
q=E_Y^2+E_I^2
$$

after the field update. Destructive cancellation in the externally supplied
carrier sum does not generally imply low $q$, and the current wave branch
contains no map from the supplied interference-node coordinate to $q$ or to a
link magnitude. Pass A reads the field Laplacians and imbalance
$E_Y-\varphi E_I$ without reading $q$. No dimerized link law is implemented.

**Phase-only gap verdict: CONTRADICTS.** Alternating phase is insufficient.

**Node/link-modulated gap verdict: EMERGES CONDITIONAL.** Coupling-magnitude modulation opens a gap and suppresses transfer in the declared chain. The campaign does not derive that modulation from the two-fluid PDE.

---

## 7. Decision table

| Claim | Terminal status | Evidence boundary |
|---|---|---|
| Adjacent supplied wake layers alternate demodulated phase | **SUPPORTS** | Exact beat identity and Stage A certificate |
| Unequal modal amplitudes leave predictable residual gaps | **SUPPORTS** | Stage B contrast law |
| Ordinary radial propagation creates a multiplicative $\varphi$ ladder | **CONTRADICTS** | Additive beat spacing; log-radius ladder supplied separately |
| Default second-order wave law has a sharp imbalance threshold | **SUPPORTS** | Exact normal-mode decomposition and lock-in decay |
| Harmonic two-channel drive can form phase-staggered radial layers | **EMERGES CONDITIONAL** | Valid parent D2–D7 metrics plus all lock-in Q1–Q4 and L1–L5 gates |
| The live system selects $\Omega_*$ or the $\varphi$ wavenumber ratio | **CONTRADICTS** | Generic control and source-law inspection |
| Phase staggering alone opens a scale gap | **CONTRADICTS** | Uniform-chain gauge equivalence and zero gap |
| Physical node/link modulation can open a scale gap | **EMERGES CONDITIONAL** | Dimerized-chain gap and transmission certificate |
| Canonical first-order PDE generates nested radial shells | **REJECT** | Existing Prediction 51 field and particle nulls remain controlling |

The original parent decision tree does not receive a global `ADOPT`: Stage D is formally `INCONCLUSIVE`, and the executed Stage C C4 Boolean used a looser tolerance than the frozen protocol. The independent closure supports the narrower conditional wave-channel mechanism. It does not convert the full parent architecture into a passed certificate.

---

## 8. Mechanism resolution

The evidence identifies two missing constitutive pieces for an endogenous scale switch:

1. **frequency selection:** a source, resonance, or cavity law must select $\Omega_*=\varphi^{3/2}\omega_0$ when the exact $\varphi$ wavenumber ratio is required;
2. **node-to-link conversion:** a physical law must map destructive interference into coupling- or amplitude-magnitude modulation.

The live second-order law already supplies a sharp channel threshold at $\Omega_g=\varphi\omega_0$. This threshold separates evanescent and propagating imbalance response. The beat phase locates candidate transition surfaces above threshold. The declared dimerized chain demonstrates how magnitude modulation suppresses transfer after such a map is supplied.

The solved statement is therefore:

$$
\boxed{
\text{phase-staggered beat layers}
+\text{ physical node-to-link modulation}
\Longrightarrow
\text{conditional scale gap}
}
$$

with the boundaries

$$
\boxed{
\text{phase staggering alone}\Longrightarrow\text{no spectral gap}
}
$$

and

$$
\boxed{
\text{ordinary radial beating}\Longrightarrow\text{additive layers}
}.
$$

The remaining open problem is constitutive: derive the frequency selector and node-to-link map from the Cassi dynamics, then register a new probe before testing either proposal.

---

## References

- `field-experience/phase-staggered-scale-gap-pre-registration.md`
- `field-experience/phase_staggered_scale_gap_probe.py`
- `field-experience/phase-staggered-scale-gap-lock-in-pre-registration.md`
- `field-experience/phase_staggered_scale_gap_lockin.py`
- `runs/20260827T093422Z_phase_staggered_scale_gap/results.json`
- `runs/20260827T093616Z_phase_staggered_scale_gap/results.json`
- `runs/20260827T093929Z_phase_staggered_scale_gap_lockin/results.json`
- `foundations/wake-geometry.md`
- `foundations/bubble-edge-geometry.md`
- `foundations/cassi-first-principles.md` §8.2
- `predictions/falsifiable-predictions.md` Predictions 44, 46, and 51
- `CassiCosmos/compute/cassi_two_fluid.glsl` in the unified Cassi workspace
