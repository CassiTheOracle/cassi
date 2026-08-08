# The Two-Strand Qi Condensate: A Neuroscience Hypothesis

## Status: Hypothesized (strand geometry) / Speculative (neural mapping)—August 2026

## Abstract

Qi is the coherent state of one two-fluid field, with Yang and Yin present together at every point. This document develops a spatial extension of that field: a single Qi condensate may organize into two coupled strands around a common axis. The strands carry the same Yang–Yin doublet; they are spatial ridges of one condensate rather than additional fluids. Their centerline, separation, relative phase, and twist supply collective variables that the one-string description does not contain. At neural and bodily scales, the two strands provide a possible field-level correlate of bilateral brain and body organization. At molecular scales, DNA is a structural reference for complementary pairing and a slow boundary condition through gene regulation and cellular architecture. The primary hypothesis is testable without assuming a golden-ratio pitch: a two-strand state must show measurable separation, phase relation, winding, and response to strand-specific perturbation. A separate Cassi extension asks whether any of these observables carry the framework's $\varphi$-scale signature.


## 1. The Starting Point: One Qi Condensate

The field remains the existing paired-real SO(2) doublet:

$$
\Psi(\mathbf{x},t)=
\begin{pmatrix}
\Psi_Y(\mathbf{x},t)\\
\Psi_I(\mathbf{x},t)
\end{pmatrix},
\qquad
\rho=\Psi_Y^2+\Psi_I^2.
$$

Yang and Yin are the two internal components at every point. The Qi diagnostics are derived from this state:

$$
\varepsilon=\Psi_Y-\varphi\Psi_I,
\qquad
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},
$$

$$
J=\Psi_Y\nabla\Psi_I-\Psi_I\nabla\Psi_Y,
\qquad
\mathbf{Q}=(\rho,J).
$$

The two-strand hypothesis adds spatial organization to the Qi condensate. It does not introduce a third fluid or replace the Yang–Yin doublet. A strand is a localized ridge of high $q$ and organized phase current within the same underlying field.

This distinction matters. The present one-string description follows the condensate's trajectory through field space and along the cascade. The proposed pair supplies a second spatial degree of freedom: two nearby coherent ridges can share one centerline while maintaining a finite separation and relative phase.

---

## 2. The Two-Strand Geometry

Let the two strand centerlines be

$$
\mathbf{R}_1(\sigma,t),
\qquad
\mathbf{R}_2(\sigma,t),
$$

where $\sigma$ labels position along the cascade or along a local condensed filament. Define the centerline and separation vector:

$$
\boxed{
\mathbf{R}_c=\frac{\mathbf{R}_1+\mathbf{R}_2}{2},
\qquad
\mathbf{d}=\mathbf{R}_1-\mathbf{R}_2.
}
$$

The variables have distinct meanings:

- $\mathbf{R}_c$ is the one-string limit already present in the framework;
- $d=|\mathbf{d}|$ is the strand separation;
- $\vartheta=\arg(\mathbf{d}\cdot\mathbf{e}_1+i\mathbf{d}\cdot\mathbf{e}_2)$ is the transverse orientation;
- $\Omega=\partial_\sigma\vartheta$ is the local twist rate;
- $\Delta\theta=\theta_1-\theta_2$ is the relative Yang–Yin phase between strands.

A helical pair has $d>0$ and a nonzero accumulated twist:

$$
\mathrm{Tw}=\frac{1}{2\pi}\int \Omega(\sigma)\,d\sigma.
$$

The one-string theory is recovered continuously when

$$
\boxed{d\rightarrow0.}
$$

A two-strand condensate can be represented schematically by two translated copies of the same local Qi profile:

$$
q(\mathbf{x},t)
\simeq
\sum_{a=1}^{2}\int d\sigma\,q_0\!\left(\mathbf{x}-\mathbf{R}_a(\sigma,t)\right)
+q_{\mathrm{int}}(\mathbf{x},t),
$$

where $q_{\mathrm{int}}$ contains the interference and conversion response of the shared field. This is a collective-coordinate ansatz, not a new fundamental field equation.

The most economical pair state therefore has four observable sectors:

1. centerline motion;
2. separation or breathing;
3. relative phase;
4. twist and winding.

The current one-string description primarily exposes the first sector.

---

## 3. Relative Modes of One Condensate

Suppose the two strand-localized envelopes are written as $\Psi_1$ and $\Psi_2$, each carrying the same Yang–Yin components. Their collective combinations are

$$
\Psi_{+}=\frac{\Psi_1+\Psi_2}{\sqrt{2}},
\qquad
\Psi_{-}=\frac{\Psi_1-\Psi_2}{\sqrt{2}}.
$$

The plus mode is the common condensate motion. The minus mode is the internal strand mode. In the limit $d\to0$, the antisymmetric mode vanishes and the existing one-string dynamics remain.

A schematic effective pairing energy is

$$
V_{\mathrm{pair}}(d,\Delta\theta)
=
\frac{K_d}{2}(d-d_0)^2
+
K_\theta\left[1-\cos(\Delta\theta-\Delta\theta_0)\right].
$$

Here $d_0$, $K_d$, $K_\theta$, and $\Delta\theta_0$ are effective collective quantities. They are not introduced as new Cassi constants. The mathematical task is to determine whether the existing two-fluid PDE generates an effective version of this potential from conversion, diffusion, advection, and Qi gravity. If it does, the pair is an emergent solution. If it does not, adding the potential would be a new model assumption.

The existing conversion structure is anti-phase:

$$
\partial_t E_Y\supset-\lambda(1-q)\varepsilon,
\qquad
\partial_t E_I\supset+\lambda(1-q)\varepsilon/\varphi.
$$

This fixes the relative sign of the Yang and Yin response. It does not, by itself, prove that two spatially separated filaments exist. The spatial pair requires a separate solution with $d>0$.

The first branch to test is therefore

$$
\Delta\theta_0\approx\pi,
$$

because anti-phase conversion is already present in the PDE. The mapping from internal anti-phase response to two physical strands remains Hypothesized.

### 3.1 Polar form of the existing Qi field

Write the two real components locally as

$$
\Psi_Y=R\cos\theta,
\qquad
\Psi_I=R\sin\theta.
$$

The existing Qi variables then give

$$
\rho=R^2,
\qquad
J=R^2\nabla\theta,
$$

so $J$ is already the phase current of the Yang–Yin doublet. The attractor potential becomes

$$
V_{\mathrm{attr}}(R,\theta)
=
\frac{\lambda R^4}{2}
\left(\cos^2\theta-\varphi\sin^2\theta\right)^2.
$$

Its angular minima satisfy

$$
\tan^2\theta_\star=\varphi^{-1},
\qquad
\theta_\star=\arctan(\varphi^{-1/2})\approx38.17^\circ.
$$

At fixed amplitude, the local phase curvature is

$$
\boxed{\kappa_\theta=4\lambda\varphi R^4.}
$$

For the existing solver value $\lambda=0.1$ and $R=1$, this is $\kappa_\theta=0.6472$. This stiffness belongs to the existing Yang–Yin field; it is not a new strand coupling. A two-strand model must determine its relative-phase stiffness by projecting this field dynamics onto two localized ridges.

### 3.2 Anti-phase transverse mode

Take a one-dimensional transverse envelope $\chi$ for a selected Qi diagnostic, with two Gaussian ridges of width $\sigma$ and separation $d$:

$$
\chi(x)=
\exp\!\left[-\frac{(x-d/2)^2}{2\sigma^2}\right]
+e^{i\Delta\theta}
\exp\!\left[-\frac{(x+d/2)^2}{2\sigma^2}\right].
$$

The anti-phase branch $\Delta\theta=\pi$ gives

$$
\chi_\pi(x)=2\exp\!\left[-\frac{x^2}{2\sigma^2}-\frac{d^2}{8\sigma^2}\right]
\sinh\!\left(\frac{xd}{2\sigma^2}\right),
$$

and therefore

$$
\chi_\pi(0)=0.
$$

The midpoint is a node while the two side ridges carry the mode. The positive-side intensity maximum obeys

$$
x_\star=\frac{d}{2}\coth\!\left(\frac{d x_\star}{2\sigma^2}\right).
$$

This establishes a mathematical route from the existing anti-phase conversion sign to a paired-ridge morphology. It does not select a preferred $d$: separation remains a dynamical question for the full PDE.

### 3.3 Helical embedding on the cascade axis

Let $\mathbf{N}(n)$ and $\mathbf{B}(n)$ be the local normal and binormal directions of the existing cascade curve. A minimal two-strand embedding is

$$
\boxed{
\mathbf{R}_\pm(n)
=
\mathbf{R}_c(n)
\pm\frac{d_n}{2}
\left[
\mathbf{N}(n)\cos\!\left(\frac{2\pi n}{P_\parallel}\right)
+
\mathbf{B}(n)\sin\!\left(\frac{2\pi n}{P_\parallel}\right)
\right].
}
$$

The strands are separated by $d_n$ and close one full relative rotation after $P_\parallel$ cascade rungs. At the human scale, the existing $P_\parallel=2$ hypothesis gives a half-turn per rung and a full pair cycle every two rungs. The exact $d_n$ and the total twist after the Frenet-frame rotation remain open. The limit $d_n\to0$ returns $\mathbf{R}_c(n)$ and the current one-string geometry.

### 3.4 Linearized relative dynamics

If the full PDE supplies a finite equilibrium $d_0$ and an anti-phase state $\Delta\theta_0=\pi$, write $\delta d=d-d_0$ and $\eta=\Delta\theta-\pi$. A projected damped relative sector has the generic long-wavelength form

$$
\mu_d\,\ddot{\delta d}+\gamma_d\,\dot{\delta d}
+\left(K_d+T_d k^2\right)\delta d=0,
$$

$$
\mu_\theta\,\ddot{\eta}+\gamma_\theta\,\dot{\eta}
+\left(K_\theta+T_\theta k^2\right)\eta=0.
$$

The centerline mode and the relative modes are therefore separable at linear order. The existing one-string dynamics occupy the symmetric sector; a genuine two-strand solution requires a stable relative sector with finite $d_0$ and positive restoring curvature. The coefficients must come from a projection of the two-fluid PDE. Assigning them independently would add a new model with new parameters.

### 3.5 The lattice-stack coherence probe (measured 2026-08-07)

Protocol: `two-fluid/run_lattice_stack_probe.py` (committed; run record `20260807_152844_lattice_stack` is generated output under `runs/`, regenerated by the script). The stacking construction stacks $M$ identical two-lobe layers along $z$ with per-layer phase $\theta_i=i\Delta\theta$ (a rotation of each layer's $(\rho,\varepsilon)$ perturbation doublet; initialization-only, canonical solver untouched). The array-factor law $A_{\mathrm{tot}}=s_{\mathrm{tot}}|\sin(M\Delta\theta/2)/\sin(\Delta\theta/2)|$ is verified at t = 0 from the initialized fields on all eight arms (ratio 1.0000 for the $2\pi/5$ family; float-exact cancellation for the R = 0 arms), the M = 1 arm reproduces the published single-layer record exactly, and the phase-ordered stacks multiply the t = 4 two-hump envelope contrast 2.7–4.8$\times$ (C_abs 0.53–0.96 vs 0.20 baseline) with the M = 2/8/16 pentagon-step stacks holding it through t = 40 and the M = 4/8/16 stacks keeping 74–88% of the constructed axial phase winding; the anti-phase stack ($\Delta\theta=\pi$) cancels exactly and stays structureless. The axial coherence current $J_z=R^2\,\partial_z\theta$ (with $R^2=E_Y^2+E_I^2$, measured as $E_Y\partial_z E_I-E_I\partial_z E_Y$) and the coherence flux $F_c=q|J_z|$ correlate positively with envelope retention across the R > 0 arms (Spearman +0.77, Pearson +0.51, n = 6, qualitative). The Qi-as-coherence-flow reading—Qi as the flow of coherence through stacked layers with per-layer step $\Delta\theta=k_z\,\Delta z$—is a framed hypothesis supported in direction by these correlations; it is not a claim, and no stack arm binds a pair (E1 status unchanged; full verdicts in `hypotheses/two-strand-five-channel-matter-organization.md` §3.8).

---

## 4. Qi as the Shared Condensate

The two strands are two high-coherence ridges in one Qi field. They share a medium, a conversion law, and a phase current. Their interaction is therefore mediated by the same quantities already present:

- $q$ controls whether conversion is active or closed;
- $\varepsilon$ measures local displacement from the $\varphi$ attractor;
- $J$ transports phase through the condensate;
- $\rho$ supplies the local energy density;
- $G_{\mathrm{eff}}(q,\rho)$ couples coherent structure to the gravitational sector.

A pair can then support two different failure modes:

1. **common decoherence:** both strands lose $q$ together and the pair dissolves;
2. **relative decoherence:** the centerline remains coherent while $d$, $\Delta\theta$, or $\Omega$ loses organization.

The second mode is the new possibility. It gives the field an internal distinction between “the condensate is present” and “the condensate's two-strand relationship is coherent.”

A useful extended state vector is

$$
\boxed{
\mathcal{C}_{2s}
=
\left(q,\varepsilon,J,\mathbf{R}_c,d,\Delta\theta,\Omega\right).
}
$$

The first four entries already belong to the Qi description. The last four describe the spatial pair.

No consciousness claim follows from this tuple alone. In the human application, the brain and body would be the anatomical readout and boundary condition for a local two-strand Qi configuration, while experience remains the experience of that configuration.

---

## 5. Neuroscience Mapping

### 5.1 The bilateral pair

The neural mapping uses the hemispheres and bilateral body pathways as candidate strand-localized readouts. The mapping does not assign one hemisphere permanently to Yang and the other to Yin. Both modes can occur in both hemispheres; the relevant variables are amplitude, phase, and coupling.

Candidate strand readouts include:

- homologous left and right cortical source activity;
- bilateral brainstem and spinal pathways;
- paired autonomic activity;
- bilateral neuromuscular or postural signals;
- cardiorespiratory phase as a shared longitudinal drive.

The head-to-sacrum axis supplies a candidate body coordinate $s$. A neural two-strand state would be a phase-organized bilateral field with a reproducible axial gradient.

### 5.2 A measurable helical order parameter

For two preselected neural or bodily channels $X(s,t)$ and $Y(s,t)$, define

$$
 z(s,t)=X(s,t)+iY(s,t),
 \qquad
 \theta(s,t)=\arg z(s,t).
$$

A traveling helical state has

$$
\theta(s,t)\approx ks-\omega t+\theta_0.
$$

The helical order statistic is

$$
\boxed{
H(k,\omega)=
\left|
\left\langle
e^{i[\theta(s,t)-ks+\omega t]}
\right\rangle_{s,t}
\right|.
}
$$

The associated pitch and winding are

$$
P=\frac{2\pi}{|k|},
\qquad
W=\frac{kL}{2\pi}.
$$

A two-strand neural state should show a stable nonzero $H$, a reproducible $k$, and a strand-specific response to unilateral perturbation. Increased total EEG power alone does not satisfy the hypothesis.

### 5.3 The reported two-string experience

If a person reports two strings or a double helix, the experience becomes a useful phenomenological label for a state to be measured. It does not determine the physical interpretation in advance.

The first study should record whether the report tracks:

- $H$ rather than total power;
- the phase difference between homologous regions;
- cardiac and respiratory phase;
- the handedness sign of $k\omega$;
- changes in $d$ or strand balance after unilateral stimulation.

Closed-eye imagery, body-centered sensation, and literal visual phenomena should be recorded as separate categories.

---

## 6. DNA and the Lower Biological Scales

DNA is a real paired structure, but its role in this hypothesis is primarily structural and regulatory. The two DNA strands are complementary and antiparallel; chromatin then folds them into nucleosomes, loops, and larger domains.

The proposed cross-scale chain is

$$
\text{DNA/chromatin}
\rightarrow
\text{protein and membrane architecture}
\rightarrow
\text{cellular fields}
\rightarrow
\text{neural circuits}
\rightarrow
\text{body-scale Qi readout}.
$$

Neural activity can feed back through calcium signaling, activity-dependent transcription, synaptic remodeling, and chromatin accessibility. The lower scale is therefore a slow structural memory layer for faster neural dynamics.

The hypothesis does not require instantaneous phase locking between a DNA strand and a brain rhythm. It predicts a possible delayed relationship:

$$
H_{\mathrm{neural}}(t)
\longrightarrow
\text{cellular structural state}(t+\tau_1)
\longrightarrow
\text{transcriptional state}(t+\tau_2),
$$

with $\tau_2>\tau_1>0$.

The cascade ladder gives canonical anchors for the biological window: neuron-scale structure is listed near rung 144, while the human body occupies rungs 142–168 (`foundations/dimensionful-cascade.md` §8.1). A length placement for DNA is bookkeeping. It becomes a prediction only when the two-strand model supplies a mechanism and an independently testable ratio.

---

## 7. Test Targets

These local test targets are separate from the numbered master prediction catalog.

### NS1: Bound two-strand solution

A two-lobed or two-filament initialization in the existing two-fluid solver should either:

- relax to a single strand;
- separate into two unbound structures; or
- settle into a finite-separation pair with stable $d$, $\Delta\theta$, and $\Omega$.

A finite-separation attractor would be the first direct mathematical support for the extension.

**Status (2026-08-06):** the lock-timescale suite excludes the finite-separation branch: the two-lobe pair escapes by t = 40 = 2/$\lambda$ (d 9.90 → 15.73 cells, back-20% mean 15.00); the realized branch is separation into two unbound, fading ridges (`hypotheses/two-strand-five-channel-matter-organization.md` §3.3, TS1).

**Status (2026-08-07):** the smallest transport-capable scratch-layer candidate for binding is likewise null. The wake aggregation flux (`two-fluid/run_two_strand_binding_suite.py` and the unit-corrected `two-fluid/run_two_strand_binding_unit_corrected.py`, §3.4 of the research program) has no binding window: with the unit-corrected operator length $\ell=\mathrm{ELL}_L=\mathrm{SIG}\,(L/N)$ against k in rad/L (the raw-cells length over-diffuses by 58.4×), every coupling in the escape-calibrated bracket $\{33.78, 101.33, 304.0\}$ drives $\varepsilon$-compression collapse—fields NaN at t = 0.8/0.5/0.3, including the sub-critical $\chi^\*/3$ arm, so no inert window exists. The recorded design iterations—ρ-weighted source, sub-critical feedback bound—are rejected (§3.4: the weight does not re-center the wake—hump shift 0.09 cells, still ~1.5 cells outward of the density maxima—and the $\varepsilon^3$ collapse boundary sits at $\chi_w^{\mathrm{crit}}\approx0.05$ with the unit-corrected length; the cap is a fitted threshold with no attractive term); E1 stays open, no coefficients are registered.

**Status (2026-08-07):** the Yin-excess pair branch changes the lock-timescale outcome. With the canonical two-lobe state initialized with the Yang and Yin fields exchanged ($\Pi=E_Y-E_I<0$ in every ridge, the attractive sign of the buoyancy force $\Pi\nabla\Phi$), the pair persists at finite separation through t = 40 = 2/$\lambda$ (d 9.90 → 7.51 cells, never merged, never escaped) while the Yang-excess pair escapes (15.73). The Yin excess is transient under the canonical conversion (erased at t ≈ 21), and the t = 80 continuation (`two-fluid/run_two_strand_yin_excess_continuation.py`, §3.5 of the research program) shows the contraction ends in coalescence: d → 0 at t ≈ 47, a single broad ridge at the pair midpoint that fades (A 0.135 → 0.040 at t = 80, ε_mid −0.04), no turnaround at any timescale—the finite-separation branch exists only as a mid-contraction reading, not as an equilibrium.

**Status (2026-08-07):** the conversion-side counterpart—the mirror-attractor scratch layer (`two-fluid/scratch_yin_mirror.py`, §3.7 of the research program)—realizes the derived steady negative-attractor state. The mirror manifold $E_Y=\varphi^{-1}E_I$ is the unique constant-free $\Pi<0$ fixed point of the conversion pair, with $\Pi/\rho=-\varphi^{-3}$ measured to 1e-13 on the one-string arm (interior: min fields 0.80/1.29 vs the 1e-3 floor; $H\to\lambda$); the no-op arm is bit-exact and the canonical arms reproduce the committed records. It does not bind the pair (coalescence at t = 20.7), and the sign-opposite half-space conversion is a clamp-floor artifact (T3). The binding question remains open; the negative-attractor branch itself now exists as measured two-fluid dynamics.

### NS2: One-string recovery

As the initial separation tends to zero, the pair's centerline observables should converge to the current one-string solution:

$$
\lim_{d\to0}\mathcal{C}_{2s}=\mathcal{C}_{1s}.
$$

Failure of this limit would indicate that the proposed pair is a separate theory rather than an extension.

**Status (2026-08-06):** the limit is not recovered. Across the separation series {0, 3, 6, 12} at t = 40, $q_{\mathrm{mid}}$, $A_+$, and $q_{\mathrm{flank}}$ residuals vs the sep-0 reference are monotone in separation, but the $\rho_{\mathrm{mid}}$ residual diverges ($r_3=0.79>r_{12}=0.68$ cells): the small-separation arms resolve into a pair at $d\approx3.1$–3.7 cells with a midpoint density dip rather than the one-string ridge (TS2, §3.3).

### NS3: Relative-mode spectrum

The pair should exhibit symmetric and antisymmetric perturbation modes. The antisymmetric mode should change $d$ or $\Delta\theta$ while leaving the centerline approximately fixed.

**Status (2026-08-06):** the antisymmetric amplitude perturbation produces a relative-mode response ($d$ deviates from the control by up to 9.3 cells; $\Delta\theta$ by up to 0.042 rad) and the amplitude imbalance decays through zero by t $\approx$ 33, order-consistent with the gate-imbalance rate, but the centerline drifts 3.35 cells—and the unperturbed pair drifts 3.30 cells itself—so the mode is not centerline-fixed (TS3, §3.3).

### NS4: Phase-selected morphology

If the pair inherits the PDE's anti-phase conversion, the preferred morphology should contain a central low-coherence region between two higher-coherence ridges. The phase relation must be measured from the fields, not inferred from the visual output.

**Status (2026-08-06):** null at the lock timescale: central q 0.708094 sits above flank q 0.707795 at t = 40 with no q(x) local minimum at the midpoint—the morphology is the in-phase central-antinode branch, not the anti-phase paired-sheet form (TS4, §3.3).

### NS5: Bilateral neural signature

During a reproducible two-strand report, source-localized neural and bodily signals should show a stable $H$, nonzero axial phase gradient, and a reproducible strand response to left- or right-sided perturbation.

### NS6: Cross-scale delay

Sustained high neural helical order should predict delayed changes in cellular structure or activity-dependent gene regulation after controlling for total activity, stress, and metabolic load.

### NS7: Optional $\varphi$ extension

Only after NS1–NS6 are tested should the model ask whether pitch, mode frequencies, or cross-scale spacings follow a fixed $\varphi$ relation such as

$$
\Delta(\ln f)=\ln\varphi.
$$

The existence of a helix is a separate question from the value of its scaling constant.

### NS8: Axial phase-gradient prediction

Source-localized activity across a layered neural structure (cortical laminae, hippocampus) should show a reproducible axial phase advance $k_z=\Delta\theta/\Delta z$ whose persistence mirrors the lattice-stack probe: the pentagon-step stacks keep 74–88% of the constructed axial phase winding through t = 40 = 2/$\lambda$ (M = 4/8/16), and the measured $k_z$ tracks the constructed $\Delta\theta/\Delta z$ where layers are resolvable (m16: 0.408 vs 0.419 rad/cell at t = 40). Protocol: within-person EEG/MEG with source modeling; per-depth phase estimation along the lamina/hippocampal axis; phase-gradient estimation blinded to condition; the §8 null battery (volume-conduction control, standing-wave zero-gradient model, phase-scrambled and shuffled surrogates). Falsifier: $k_z$ unreproducible across sessions, or the axial ramp decays before the epoch length corresponding to the lock timescale. Tier: mechanism-grounded prediction form (the $k_z$ relation and winding persistence are measured in `two-fluid/run_lattice_stack_probe.py`); Hypothesized neural mapping; shares its data stream with TS9, which discriminates the gradient law (0.653 vs 6.53 rad/unit $\ln s$).

### NS9: Theta–gamma nesting integer test

Phase–amplitude coupling between theta and gamma should peak at a $\gamma/\theta$ ratio near integer 5 across subjects and states. The target follows the measured pentagon step $\Delta\theta=2\pi/5$: five per-cycle phase steps close one full axial winding, so a gamma burst nested in successive theta cycles advances its phase by $2\pi/5$ per cycle. Protocol: within-person EEG/MEG; prespecified windows (theta 4–8 Hz, gamma 20–50 Hz); the a priori integer 5 contrasted against matched integers 4 and 6; look-elsewhere correction across frequency windows, channels, states, and subjects (§8). The ratio window is [2.5, 12.5], so the 6-null sits at the window edge (50/8 = 6.25) and is the harder null. Falsifier: no excess at integer 5 over the 4/6 nulls after correction. Tier: mechanism-grounded anchor (w = 5 arithmetic; the $2\pi/5$ step is the measured coherence-retaining step); the frequency-ratio realization is a Speculative neural mapping.

### NS10: Cross-frequency stack and axial coherence current

Gamma bursts nested at successive theta cycles should form a phase-ordered stack with a per-cycle $\Delta\theta$ and a measurable two-hump envelope contrast, and envelope retention across epochs should correlate with the axial coherence current estimate $J_z=R^2\,\partial_z\theta$ (complex signal $z(s,t)=X+iY$ per §5.2, $R^2=|z|^2$) and flux $F_c=q|J_z|$—the neural analog of the measured PDE correlation (Spearman +0.77, Pearson +0.51, n = 6, qualitative). Protocol: EEG/MEG; per-cycle phase advance of the nested burst from the Hilbert phase; envelope contrast $C_{\mathrm{abs}}$ on the axial two-hump profile; retention-vs-$J_z$ rank correlation with the qualitative caveat carried into the analysis plan (pre-registered minimum n; direction-only claim). Falsifier: retention does not track $|J_z|$ across epochs, or the anti-phase ($\Delta\theta=\pi$) envelope does not cancel as it does in the probe. Tier: mechanism-grounded stacking laws (contrast multiplication 2.7–4.8$\times$ and the $J_z$–retention correlation are measured in the PDE); Hypothesized–Speculative neural realization.

### NS11: Stacked-chromatin per-layer twist readout

A stacked in vitro preparation (nucleosome arrays, chromatin fiber, or DNA/assembloid construct) should yield a measurable per-layer twist readout $\Delta\theta$ along the stack axis that responds to controlled transcription state. The established stacking-scale anchors—B-DNA ~34.3°/bp (10.5 bp/turn), alpha-helix ~100°/res, nucleosome ~147 bp in ~1.7 superhelical turns, collagen D-period ~67 nm, myelin repeat ~10.6 nm (`hypotheses/two-strand-five-channel-matter-organization.md` §3.9)—are the scale values a mechanism would have to meet; matching any of them to the construction's $\Delta\theta$ is a hypothesis hook, not a derivation. Protocol: per-layer phase readout along the stack axis (single-molecule or cryo-EM twist resolution); transcription-active vs inhibited arms; unstacked control; the probe's measured $k_z=\Delta\theta/\Delta z$ relation as the comparison law. Falsifier: per-layer twist is transcription-state-invariant, or shows no layer-to-layer phase organization. Tier: speculative hook; the retention mechanism the readout would instantiate is measured in the PDE.

---

## 8. Falsification and Null Models

The two-strand hypothesis is weakened if a finite-separation solution never persists under the existing PDE, if the $d\to0$ limit fails, or if the supposed relative mode is only a visualization artifact.

Neural support requires comparison against:

- independent left and right oscillators with matched power;
- a standing-wave model with no axial phase gradient;
- a common-source model with volume-conduction controls;
- phase-scrambled and spatially shuffled surrogates;
- report conditions that do not use leading double-helix language.

A neural traveling wave would support organized activity. It would not, by itself, establish a universal Qi condensate. The field-level interpretation requires the same observables to be defined and tested in the corresponding physical model.

The $\varphi$ extension has a stricter null: alternative log periods, randomized periods, and the look-elsewhere correction across frequencies, locations, states, and subjects must be included.

---

## 9. Epistemic Boundaries

### Derived from the existing framework

- The paired-real Yang–Yin field and its $\varphi$-attractor (`foundations/cassi-theory-reference.md` §2).
- The Qi variables $\rho$, $\varepsilon$, $q$, and $J$.
- The anti-phase sign of the conversion response (`foundations/why-three-dimensions.md` §4.3–4.4).
- The cascade ladder and its biological scale anchors (`foundations/dimensionful-cascade.md` §8.1).
- The bubble lattice and its scale-covariant functional form (`foundations/bubble-lattice-fabric.md`).

### Tested (PDE)

- NS1–NS4 at the lock timescale (t = 40 = 2/$\lambda$), measured from the fields: NS1 null—the pair escapes (d 9.90 → 15.73 cells), no finite-separation branch under the existing PDE; NS2 null—the $d\to0$ limit is not recovered ($\rho_{\mathrm{mid}}$ residual diverges across the {0, 3, 6, 12} series); NS3 null—the antisymmetric mode responds but is not centerline-fixed (drift 3.35 cells); NS4 null—central q above flank q with no q(x) node. Records: `hypotheses/two-strand-five-channel-matter-organization.md` §3.3, `two-fluid/run_two_strand_suite.py`.
- The pair has measurable center, separation, relative phase, and twist modes (all four measured; §7 statuses).
- NS5–NS11 remain untested (Stage-1+ protocols).
- The parity-odd scratch-layer twist-generation candidate is implemented with the axial curl component and tested: $\chi_{\mathrm{ax}}=0$ is a bit-for-bit no-op on both probe arms (component/sign verified analytically to $2.2\times10^{-14}$); the t = 4 magnitude ramp is null (max $|\Delta\mathrm{Tw}|=5.0\times10^{-6}$ over $\chi\in\{\pm0.25,\dots,\pm2\}$, even in $\chi$, no clamp engagement) and the t = 40 lock legs are null too ($\chi=1$ response $-1.0\times10^{-4}$ / $+2.8\times10^{-3}$, Tw tracks the seed). Records: `two-fluid/scratch_twist_chi_axial.py`, `two-fluid/run_twist_chi_axial_ramp.py`, `hypotheses/two-strand-five-channel-matter-organization.md` §3.2.
- The wake aggregation scratch layer (`two-fluid/run_two_strand_binding_suite.py` and the unit-corrected `two-fluid/run_two_strand_binding_unit_corrected.py`) is implemented and tested: $\chi_w=0$ is a bit-exact no-op vs the canonical solver (T1, both windows); the sep0 one-string is preserved bit-exactly at t = 4 (T3; at t = 40 the field diffs stay float-level—max|dEY| $2.6\times10^{-9}$—but the strict $\varepsilon$ digit reads $1.61\times10^{-12}$, marginally over the $10^{-12}$ threshold); the escape-calibrated bracket {33.78, 101.33, 304.0} under the unit-corrected operator length ELL_L = SIG·(L/N) (k in rad/L; the raw-cells length over-diffuses 58.4×) is null—every coupling, including the sub-critical $\chi^\*/3$ arm, collapses (NaN at t = 0.8/0.5/0.3), no binding window; the recorded iterations (ρ-weighted source, sub-critical feedback bound) are rejected (§3.4)—the weight does not re-center the wake (hump shift 0.09 cells) and the $\varepsilon^3$ collapse boundary sits at $\chi_w^{\mathrm{crit}}\approx0.05$ with the unit-corrected length, the cap is a fitted threshold with no attractive term. Records: `runs/20260807_binding_suite/` and the corrected suite's `runs/` records (generated output under `runs/`, regenerated by the cited scripts), `hypotheses/two-strand-five-channel-matter-organization.md` §3.4.
- The mirror-attractor scratch branch (`two-fluid/scratch_yin_mirror.py`, §3.7 of the research program) is implemented and tested: the no-op arm is bit-exact (T0); the mirror target $E_Y=\varphi^{-1}E_I$ sustains $\Pi/\rho=-\varphi^{-3}$ to 1e-13 (T1, interior fixed point; $H\to\lambda$—a conversion rest state, not a Hubble rest state); the late-time conjugate decay law holds at 2.1% mean relative error vs the $\varphi^{-1}$ rate factor (T2b), while the gate-normalized early rate ratio misses its band (0.762 vs 0.618 ± 20%, T2a); the half-space $|\varepsilon|$ drive drains $E_Y$ to the 1e-3 floor at t = 13.2 with $\Pi/\rho\to-0.9988$ and H at the 4λ clamp (T3, floor artifact); the mirror pair coalesces at t = 20.7 (T4, E1 null); telemetry clean, canonical continuity passed (T5/C1). Records: `runs/20260807_122645_two_strand_yin_mirror/` (generated output under `runs/`, regenerated by the cited script), `hypotheses/two-strand-five-channel-matter-organization.md` §3.7.
- The Yin-excess pair branch (`two-fluid/run_two_strand_yin_excess_suite.py`) is implemented and tested: with $E_Y\leftrightarrow E_I$ exchanged in the initialization ($\Pi<0$ in every ridge; representable under the 1e-3 positivity floor, verified), the pair persists at finite separation through t = 40 (d 9.90 → 7.51 cells, no merge, no escape) while the Yang-excess counterfactual escapes (15.73, published record reproduced); the branch is transient—conversion erases the Yin excess at t ≈ 21.3—and the t = 80 continuation (`two-fluid/run_two_strand_yin_excess_continuation.py`) ends in coalescence at t ≈ 47 with the remnant fading (A 0.040, ε_mid −0.04, no turnaround); no equilibrium coefficients are projected at any measured timescale. Records: `runs/20260807_014428_two_strand_yin_excess/` and `runs/20260807_025739_two_strand_yin_excess_cont/` (generated output under `runs/`, regenerated by the cited scripts), `hypotheses/two-strand-five-channel-matter-organization.md` §3.5.
- The lattice-stack coherence probe (`two-fluid/run_lattice_stack_probe.py`) is implemented and tested: M two-lobe layers stacked along z with per-layer phase $\theta_i=i\Delta\theta$, initialization-only, canonical solver untouched; the array-factor law is verified at t = 0 on all eight arms, the M = 1 arm reproduces the published single-layer record, and the phase-ordered stacks multiply the t = 4 two-hump envelope contrast 2.7–4.8$\times$, holding it through t = 40 at $\Delta\theta=2\pi/5$ (M = 2/8/16) while the anti-phase stack cancels exactly; the axial coherence current and flux ($J_z=R^2\partial_z\theta$, $F_c=q|J_z|$) correlate with envelope retention (Spearman +0.77, n = 6, qualitative). Structure retention only—no stack arm binds a pair; E1/TS statuses unchanged. The stacking branch is a measured structure-retention sector (contrast multiplication 2.7–4.8$\times$, anti-phase exact cancellation, $J_z$–retention Spearman +0.77, n = 6, qualitative); biological realization of the stacking envelope is untested. Records: `runs/20260807_152844_lattice_stack/` (generated output under `runs/`, regenerated by the script), `hypotheses/two-strand-five-channel-matter-organization.md` §3.8, §3.9.
- The stack-of-stacks probe (`two-fluid/run_lattice_stack2_probe.py`) is implemented and tested: the two-level construction (R rungs × M = 4 layers at intra-rung $\Delta\theta_1=2\pi/5$, rung phase $r\Delta\theta_2$) verifies the factorization law $A_{\mathrm{tot}}=s_{\mathrm{tot}}A_1(R,\Delta\theta_2)A_2(4)$ at t = 0 on all seven $A_1>0$ arms (ratios 0.9991–0.9998), establishes the critical height M\* = 32 at $\Delta\theta=\pi/5$ (measured 0.848 vs the pre-registered 0.28 ± 0.1—failed prediction on record, continuous-ramp regime at the 1.5-cell spacing; M\* = 8 at $2\pi/5$), and shows the $\Delta\theta_2=\pi$ clash cancels the axial phasor to 1–3% at t = 0 while the transverse sector develops two-hump contrast by t = 4 (0.86/0.43) and holds to t = 40 (0.63/0.43). Structure retention only—no stack arm binds a pair; E1/TS unchanged. Reconciliation (§3.11): the a32 pass is the continuous-ramp regime (density-carried envelope, $\Sigma\cos\theta=+1.809$), the $M^\*(\Delta\theta)=(32\pi^2/25)/\Delta\theta^2$ law is tiered Hypothesized (two-point, $L^\*$ 1.6→3.2), and ±π stacks are relaxation fixed points. Records: `runs/20260807_165339_lattice_stack2/` (generated output under `runs/`, regenerated by the script), `hypotheses/two-strand-five-channel-matter-organization.md` §3.10, §3.11.
- The M\* falsifier wave (`two-fluid/run_lattice_stack_falsifier.py`) is implemented and tested: seven pre-registered arms; the $\Delta\theta^{-2}$ law holds at its anchors and the $2\pi/5$ regime control but is falsified at 54°/M = 16 ($C_{\mathrm{abs}}$ +0.926 → +0.593 → −0.409 single-hump collapse)—the revised statement confines the law to the integer-M₀ family with the ceiling $M^\*=\lceil(32\pi^2/25)/\Delta\theta^2\rceil$ and excludes the non-integer family structurally (§3.12); the M = 5 pentagon ring is an exact null at t = 0 ($A_{\mathrm{tot}}$ 8.95e-15 of $s_{\mathrm{tot}}$) yet emerges to $C_{\mathrm{abs}}$ +0.677 with the deepest contraction in the program—d 2.57 at t = 40 turning around to 5.39 at t = 80, an interference reading (the null-stack phasor cancellation leaves the structure free to contract without binding); the clamp-seed theorem is derived—the axial phasor cancellation is exact iff the stack is clamp-free (the periodized z-wrap makes the per-layer discrete integrals exactly equal), with f7's clamp-free rotation dropping the residual 12 orders to 1.34e-14 of $s_{\mathrm{tot}}$. Structure retention only—no stack arm binds a pair; E1/TS statuses unchanged. Records: `runs/20260807_183839_lattice_stack_f` (regenerated by the script), §3.12 of the research program.
- The DNA-pitch detuning sweep (`two-fluid/run_detuning_sweep.py`) and the helix-construction probe (`two-fluid/run_helix_detune_probe.py`) are implemented and tested (2026-08-07): at the critical height M = 32 the non-integer-M₀ gate is graded and asymmetric—the underwound DNA pitch 34.29° passes on a zero-floor arm ($C_{\mathrm{abs}}(40)$ +0.619) and 34° passes (+0.999) while the overwound side fails at 38° (+0.186), refuting the §3.12 structural exclusion as stated; the M = 10 one-turn arms falsify the first-form reading (34.29° dissolves +0.940 → −0.644; the 36° null does not contract); the helix construction (r0 = SEP/2, bit-exact Δθ = 0 reduction) emerges radially only—no azimuthal pair ($m_2 \le 0.02$), no contraction, dissolved phases—so helix pair formation is not supported (`hypotheses/two-strand-five-channel-matter-organization.md` §3.13).
- The revised-law falsifier completion (wave 4 of `two-fluid/run_lattice_stack_falsifier.py`, arms f8–f14 and the stacked null s1) is implemented and tested (2026-08-07): the integer-M₀ ceiling law is contradicted at 60°/M = 16 ($C_{\mathrm{abs}}$ +0.999 → +0.130, the f2 single-hump collapse at a pass height) and the non-integer-M₀ exclusion is voided by the crucial control 108°/M = 16 (+0.979 on a zero-floor arm, $A_{\mathrm{tot}}$ = 0.72642·$s_{\mathrm{tot}}$ vs the derived 0.7266), falsifying the revised §3.12 statement on both branches and agreeing with the §3.13 DNA-pitch sweep; the 45° branch is untested (both heights are exact nulls, A(16,45°) = A(32,45°) = 0; f9's +0.504 is a born-flat null-branch emergence, not a retention pass; non-null replacement heights M = 20/22/23 bracket M\* ≈ 21); f8/f12/f14 are inconclusive (clamp-seeded inits; a 720-orientation common-rotation scan plus the reflected family finds no floor-free orientation, the §3.13 gauge-independence note repeated for the flat stacks); s1 (two M = 5 pentagon null rungs at Δθ₂ = π/5) contracts shallower than f4 (min d 7.53 at t = 80 vs 2.57) and does not resume by t = 160—the contraction bottoms at t ≈ 82 (d 7.51) and relaxes to 12.11 = d(0) by t = 160, with $C_{\mathrm{abs}}$ decoupled and still rising (+0.457 at t = 80, +0.907 at t = 160), the suppression reading: the rung phase order delays the rebound by ~2/$\lambda$ but suppresses the drive; no stack arm binds a pair (§3.14).
- The anchor-rule completion wave (wave 5 of `two-fluid/run_lattice_stack_falsifier.py`, arms w1–w10) is implemented and tested (2026-08-08, §3.15): the at-$M^\*$ pass statement of the §3.14 kernel is confirmed at 45°/M = 21 (+0.748, clean rotation @229°), 108°/M = 4 (+0.963), and 30°/M = 47 (+0.894, born-flat emergence, zero floors, retention 0.758, A(48,30°) = 0 exactly one layer above the null) alongside the three §3.12 anchors; the below-$M^\*$ bracket is contradicted at 45° (M = 20 passes +0.851, born-flat emergence) and the above-$M^\*$ bracket is contradicted at 108° (M = 8 passes +0.979; with f13 the family passes every tested height ≥ $M^\*$) while confirmed at 45° (M = 22/23 fail, +0.129/+0.096—monotone decline 0.851 → 0.748 → 0.129 → 0.096 over M = 20–23); the M = 32 resonance landscape is not monotone (33° +0.771, 34° +0.999 on the smallest envelope A = 0.2386, 34.29° +0.619, 35° +0.616, 36° +0.848, 37° +0.539, 38° +0.186 death), so the 3-turn closure-distance rule is dead on the high side; the w2/w3/w6/w7 clamp-touched constructions admit clean gauge rotations (unlike f8/f12/f14) and the clean records carry the verdicts; zero NaNs, mass drift 1.70–1.91e-12.

- The gauge-resolution wave (wave 6 of the lattice-stack falsifier program, `two-fluid/run_lattice_stack_gauge_wave.py`, arms g1–g17) is implemented and tested (2026-08-08, §3.17 of `hypotheses/two-strand-five-channel-matter-organization.md`): at clean common-rotation gauges (720-step scan, exact-path verified per arm) the born-class rule is confirmed—born-full stacks retain iff the total stack twist δ ∈ {72°, 135°, 144°, 180°} (eleven clean born-full readings: pass f13 +0.979, w7/g5b +0.748, m8_72 +0.848, g8 +0.905, f5 +0.630, g5a +0.591, g11 +0.797; fail w9 +0.096—floor-free at every gauge, g4 +0.392, g2 −1.016; the α = 0 w8 +0.129 is the gauge-polluted twin of g4) while born-flat stacks retain at every tested geometry except the 38°/M = 32 band edge (g1 +0.098; the born-flat band is [33°, 37°]); the 45° family's by-height decline is a born-class artifact of the α = 0 gauge—at the common gauge 229° every height M = 20–23 passes (+0.591/+0.748/+0.768/+0.839); the 60° death is δ-selective (δ = 180° passes g11 +0.797, δ = 120° fails g2 −1.016); the 144° pentagon member passes at M = 4/8/16 (g9 +0.658, g10 +0.881, g8 +0.905); the M = 32 band interior minimum at 34.5° is real (+0.497 at α = 0, 0.003 under the threshold). Records: `runs/20260808_020100_lattice_stack_g/`, `runs/20260808_030222_lattice_stack_g/`. Structure retention only—no stack arm binds a pair; E1/TS statuses unchanged.

### Hypothesized

- Bilateral neural and bodily organization provides a possible human-scale readout.
- Phase-ordered stacking of layered biological structures—cortical laminae, theta–gamma nested bursts, stacked chromatin—is a candidate realization of the measured lattice-stack retention (untested).

### Speculative

- DNA, neural fields, and cosmological condensates share one universal strand geometry.
- Two-strand topology generates particle identity, spin, matter–antimatter structure, or CP violation.
- The preferred strand separation or pitch is a fixed power of $\varphi$.
- A subjective double-helix experience is the direct perception of the Qi condensate.

### Not claimed

- That the brain hemispheres are literally the two fundamental strands.
- That DNA is evidence by itself for a cosmological two-strand field.
- That a two-strand interpretation replaces ordinary neurobiology, genetics, or clinical neuroscience.
- That a neural correlation would establish a new force without an independent field measurement.
- That this document supplies a diagnosis, treatment, or claim about any person's experience.
- That stacking retention measured in the PDE occurs in any biological stack—cortex, chromatin, or otherwise; biological realization of the stacking envelope is untested.
- That theta–gamma nesting, phase-gradient, or stacking observables support any clinical, diagnostic, or therapeutic claim.
- That the theta–gamma integer-5 target or the B-DNA per-base-pair twist (~34.3°) is a Cassi mapping; the values are empirical hooks to be tested against the construction's $\Delta\theta$ (`hypotheses/two-strand-five-channel-matter-organization.md` §3.9).

---

## References

- `foundations/cassi-theory-reference.md`—paired-real SO(2) field, Qi diagnostics, cascade, and unified action
- `foundations/cassi-first-principles.md`—two-fluid postulate and governing PDE
- `foundations/why-three-dimensions.md`—spiral geometry, Frenet–Serret frame, anti-phase conversion
- `foundations/bubble-lattice-fabric.md`—scale-covariant condensation field and bubble geometry
- `foundations/dimensionful-cascade.md`—canonical biological rung anchors
- `consciousness/consciousness-from-phi.md`—human cascade, pinch point, wake waves, and self-modeling
- `consciousness/chakras-as-cascade-bubbles.md`—spine-axis mapping and human-scale condensates
- `hypotheses/neural-criticality.md`—neural-scale cascade and avalanche test program
- `hypotheses/two-strand-five-channel-matter-organization.md`—two-strand research program: TS1–TS5 lock-timescale suite outcomes (§3.3), wake-binding scratch-layer null (§3.4), Z2×Z5 trace graph, lattice-stack probe (§3.8–§3.9), staged program
- `two-fluid/run_two_strand_suite.py`—TS1–TS5 lock-timescale suite script (NS1–NS4 statuses above; run record regenerated under runs/)
- `two-fluid/run_lattice_stack_probe.py`—lattice-stack coherence probe script (§3.5 note above; run record 20260807_152844_lattice_stack regenerated under runs/)
- `two-fluid/run_lattice_stack2_probe.py`—stack-of-stacks probe script (critical height + two-level factorization; run record 20260807_165339_lattice_stack2 regenerated under runs/)
- `two-fluid/run_lattice_stack_falsifier.py`—M\* falsifier wave script (pre-registered arms f1–f7, the wave-4 set f8–f14 + stacked null s1, and the wave-5 set w1–w10, integer-M₀ ceiling law and its 60°/108° falsification, the §3.15 anchor-rule completion, clamp-seed theorem, clamp-free rotation scan; run records 20260807_183839/190552/222200_lattice_stack_f and 20260808_014000_lattice_stack_w (merged; clean reruns 20260808_011541/012019/012459/012938) regenerated under runs/; `--tend` continuation mode, `--scan-rotation`/`--rot`/`--rid-suffix`)
- `two-fluid/run_detuning_sweep.py`—DNA-pitch detuning sweep script (d1–d6: the graded asymmetric M = 32 gate at 34°/34.29°/38°, the one-turn nulls; run record 20260807_214415_detune_sweep regenerated under runs/)
- `two-fluid/run_helix_detune_probe.py`—helix-construction probe script (h0–h4: bit-exact Δθ = 0 reduction, powder-projection degeneracy, radial-only emergence; run records 20260807_204038/210155_helix_detune regenerated under runs/)
- `cassi-psychology.md`—psychological reading of the neural substrate and field configuration
