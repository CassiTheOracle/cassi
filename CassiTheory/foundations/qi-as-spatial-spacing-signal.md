# Qi as the Spatial-Spacing Signal

## Status: Hypothesized—August 2026

## Abstract

This document gives a Hypothesized channel interpretation of the measured
$\varphi$-spacing records. The canonical two-fluid state is the real density
pair $(E_Y,E_I)$; its conversion contribution conserves
$\rho=E_Y+E_I$ and relaxes $\varepsilon=E_Y-\varphi E_I$. The derived
density-plane angle $\theta_d=\operatorname{atan2}(E_I,E_Y)$ and
$\mathbf J_d=(E_Y^2+E_I^2)\nabla\theta_d$ are local diagnostics with units
distinct from the amplitude current $\mathbf J_\Psi$. Neither diagnostic
supplies inter-rung transport without a separate constitutive map.

An optional reference-normalized positive-root amplitude lift can introduce
$\Psi_0=\sqrt{E_Y}$, $\Psi_1=\sqrt{E_I}$, and an amplitude-plane coordinate.
An explicit periodic identification could promote that coordinate to a compact
phase, and an additional spacing or ring map could then be tested. Those
structures and the associated channel-transmission reading are Hypothesized
extensions requiring implementation and measurement. The canonical density
conversion supplies none of them. The measured disk-gap, period-ratio, and
simulation records below are retained with that boundary.

---

## 1. Canonical density diagnostics and optional coherence lift

The canonical two-fluid state is the real density pair $(E_Y,E_I)$, with
$E_Y$ the Yang density and $E_I$ the Yin density. Define

$$
\rho=E_Y+E_I,\qquad
\varepsilon=E_Y-\varphi E_I,\qquad
\theta_d=\operatorname{atan2}(E_I,E_Y).
$$

The associated local density-plane diagnostic is

$$
\mathbf J_d=E_Y\nabla E_I-E_I\nabla E_Y
            =(E_Y^2+E_I^2)\nabla\theta_d.
$$

$\mathbf J_d$ records a density-plane-angle gradient at a named spatial
direction. It has units distinct from the amplitude current
$\mathbf J_\Psi$ and has no inter-rung transport interpretation without a
separate constitutive map, projection, boundary condition, and test.

For an optional reference-normalized positive-root amplitude lift, one may set

$$
\Psi_0=\sqrt{E_Y},\qquad \Psi_1=\sqrt{E_I},\qquad
R^2=\Psi_0^2+\Psi_1^2,\qquad
\theta_\Psi=\operatorname{atan2}(\Psi_1,\Psi_0).
$$

The lift then defines the amplitude-plane current

$$
\boxed{\mathbf J_\Psi
=\Psi_0\nabla\Psi_1-\Psi_1\nabla\Psi_0
=R^2\nabla\theta_\Psi
=\rho_\Psi\nabla\theta_\Psi},
\qquad \rho_\Psi=R^2,
$$

and the corresponding local identity is

$$
\mathbf J_d
=E_Y\nabla E_I-E_I\nabla E_Y
=(E_Y^2+E_I^2)\nabla\theta_d
=2\sqrt{E_YE_I}\,\mathbf J_\Psi.
$$

The positive-root lift and the conversion between $\mathbf J_d$ and
$\mathbf J_\Psi$ are optional reference-normalized Hypothesized extensions.
An explicit periodic identification is required before $\theta_\Psi$ can be
used as a compact phase. The canonical conversion ODE is a rank-one
density-plane relaxation and supplies no compact $U(1)$ or $SO(2)$ generator,
fixed phase advance, or inter-rung current law.

A field pattern can propagate through the medium while advective/particle
motion remains a separate channel:

- **Wave propagation of a density pattern.** The PDE's advection, diffusion,
  conversion, and source terms can carry patterns in $E_Y$ and $E_I$.
  Describing such a pattern as a compact phase ripple requires the optional
  amplitude-plane coordinate, its periodic identification, and the lift above.
  The condensation field
  $C(x,y)=\cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$
  (`foundations/bubble-edge-geometry.md` §1.1) is a specified standing
  interference pattern of the two wakes; its propagation speed is a measured
  property of the tested run.
- **Advective/gravitational motion of matter.** Particles and dense patches
  move by advection and gravity (the canonical $q=0$ Poisson limit, the orbital
  dynamics of detached bodies). This is a separate channel for mass and
  momentum. Any inter-scale coordinate organization assigned to it requires
  the optional spacing map and a constitutive law.

*Coherence ripples differently than it moves* is therefore a Hypothesized
reading of the measured separation between a propagating field pattern and
particle motion. The $\varphi$-scaled spacing of $C$ is a geometric input or
pattern record; its transmission to a tracer remains a channel hypothesis.

**Tier: Hypothesized conditional.** The canonical density fields,
conversion, $\theta_d$, and $\mathbf J_d$ are defined diagnostics. The
amplitude lift, periodic compact phase, $\mathbf J_\Psi$ spacing map, and
coherence-channel transmission require the additional structure and tests
specified above.

## 2. Coherence clumps: the condensation field is the lattice

The condensation field $C(x,y) = \cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$,
with $\Lambda_Y = \varphi\Lambda_I$, creates **high-$q_{\rm proxy}$ patches** at
the constructive-interference (bubble interior) sites—$C \to +1$,
$q_{\rm proxy} \to 2$—and **voids** at the destructive-interference
(parity-odd) sites—$C \to -1$, $q_{\rm proxy} \to 0$
(`foundations/bubble-edge-geometry.md` §1.1). At the $C=0$ saddle,
$q_{\rm proxy}=1/2$. The geometric coordinate
$q_{\rm proxy} = (1+C)^2/2$ is separate from canonical
$q = \rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ in the reference-normalized
solver state. The bounded solver reading is supplied by a separate
constitutive map
$$
q_{\rm solver}=\mathcal M(q_{\rm proxy}),\qquad
\mathcal M:[0,2]\to[0,1].
$$
Claims that these patches carry high- or low-$q$ canonical coherence, or that
canonical-$q$ dynamics place matter there, are conditional on that separately
supplied and measured map.

The clumping is *itself* the geometric lattice/parity structure: the staggered
checkerboard of bubble and void sites (`foundations/bubble-lattice-fabric.md`
§1–2), a scale-covariant geometric construction repeated at each assigned
cascade rung. Assigning matter condensation to organized regions requires the
proxy-to-$q$ map and a matter constitutive law, while the *spacing of the
clumps* is set by the specified trigonometric pattern of $C$. Calling this
pattern a compact coherence phase requires the optional lift and phase map in
§1.

**Tier: Hypothesized conditional for the geometric lattice and canonical-$q$
consequences.** The displayed condensation field and checkerboard parity are
geometric constructions from `foundations/bubble-lattice-fabric.md` §1–2 and
`foundations/bubble-edge-geometry.md` §1.1. Identifying $q_{\rm proxy}$ with
canonical $q$, inferring canonical-$q$ matter clumping, or assigning a compact
phase to $C$ requires the separately measured constitutive and phase maps. The
**emergent φ-spaced clump ladder in the sim's free dynamics is measured-null**
(single-mode clumping, measured status below).
**Measured status (owner's space-sim, live config).** The coherence field in
the owner's space-sim (Godot, 128³ grid, 2.5M particles, meshless tree gravity
ON, dual-grid ON, black holes ON, multi-rung seed ON ×6, single cluster,
cluster_radius 50, gravity_mode 4, river calibration, φ-aspect box
$(φ,1,φ^2)$, source_strength 0, dt 0.05) *does* clump: it condenses into a
single dominant box-scale mode with monotonic radial power decay—theory-q
radial fractions (shells up to 10) ≈ $1.0, 0.169, 0.0352, 0.00502, 0.00101,
0.000618, \dots$ (color q = $E_Y^2+E_I^2$ slightly shallower: $1.0, 0.359,
0.164, 0.0626, 0.0198$)—with dominant_mode_count = 1, ladder_ratios empty,
and autocorr clump-lags empty. Both measured q diagnostics agree, and the
pre-registered MIN_MODES=3 gate fails, so the reading is **NO-PHI-LADDER**:
the clumping is a single-scale condensation, not a φ-spaced clump ladder.
This is a single-mode falsification of an emergent φ-ladder clump structure in
the sim's own free dynamics. The measured result leaves the specified
condensation-field morphology intact; it does not establish a canonical
compact phase or an emergent inter-rung spacing current. The same run measured
coherence-pattern propagation at $v_c \approx 0.92$ cells/unit-t, ≈ the wave
speed c, while particles move at $v_p \approx 559$—coherence ≈ 610× slower
than particles, ~900σ separation from equal, both q conventions. These values
support the measured distinction between field-pattern propagation and
particle motion; the optional phase/ring interpretation remains Hypothesized.
**Caveat on record (once).** The null collapsed the field radially: only a
radial-only $|k|$-shell power analysis was run; a direction-resolved per-axis
spectrum was **not**. Radial-only collapse can **hide** a genuine optional
ladder if an ellipsoidal clump smears power across shells; it cannot **create**
secondary modes, so the single-mode, no-φ-ladder reading stands as measured.

## 3. Optional reference-normalized ring coordinate

An optional geometric model may assign a radial coordinate to the interior of
a bubble:

$$\boxed{\alpha(r) = \pi\,u, \qquad u = \log_\varphi\!\left(\frac{r}{\ell_n}\right)}$$

with matter rings at $r_k = \ell_n\,\varphi^{-k}$ and voids at
$\ell_n\,\varphi^{-(k+\frac12)}$ (`foundations/bubble-edge-geometry.md`
§3.1, the ring law). Here $\alpha$ is an assigned coordinate of the optional
reference-normalized map; it is separate from the canonical
$\theta_d=\operatorname{atan2}(E_I,E_Y)$. The ring positions and the
$\varphi$-scaled coordinate are therefore retained as a geometric ansatz, not
as a phase advance generated by the density conversion.

Under this optional map the ladder can be called a coordinate-phase ladder:
its parity and ring assignments are additional structure, rather than a
consequence of a canonical $SO(2)$ generator or a matter-density placement
law. The naive matter wake-sum
$\cos(2\pi r/\ell_n)+\cos(2\pi\varphi r/\ell_n)$ has zeros at
$\{0.191,0.573,0.809,0.955\}\,\ell_n$, none a $\varphi$-ladder position
(`foundations/bubble-edge-geometry.md` §3.5). That result is a null for the
alternative matter-density construction and does not validate the optional
coordinate map.

**Tier: Hypothesized conditional.** The boxed ring law and its radial-reading
inference are retained as optional geometric data from
`foundations/bubble-edge-geometry.md` §3.1; the wake-sum null is retained from
§3.5. Neither result establishes a compact canonical phase or inter-rung
transport.

## 4. Optional channel-transmission hypothesis

The measured separation between a propagating field pattern and advective
particle motion motivates a channel question. The condensation field $C$ is a
specified geometric pattern, while the optional amplitude lift and spacing map
in §1 provide a possible way to test whether a tracer receives an imprint of
that pattern. This interpretation is conditional on the lift, map, and
constitutive coupling.

> **Conditional channel hypothesis.** A tracer coupled to the density or
> condensate field may carry a measured $\varphi$-spacing imprint when the
> optional spacing map is implemented and its coupling is tested. Detached
> orbital dynamics provide a separate gravitational/advective channel whose
> statistics need not carry that imprint.

The two channel classes define testable comparisons:

1. **Coherence-coupled tracers.** Disk-gas substructure, condensate patches,
   and other fields driven by the specified $C$ pattern can be tested for the
   registered spacing record.
2. **Detached-body tracers.** Period ratios and other orbital statistics can
   be tested as a separate gravitational channel, with no automatic
   identification with $\theta_d$, $\mathbf J_d$, or $\mathbf J_\Psi$.

**Tier: Hypothesized conditional.** The channel-transmission rule is a model
interpretation. The canonical density fields, $\theta_d$, and $\mathbf J_d$
remain local diagnostics; the optional amplitude lift, periodic compact
$\theta_\Psi$, spacing map, and constitutive coupling require implementation
and measurement.

## 5. Mixed measured verdicts

The two registered disk/exoplanet results are measurements of different
tracers. Their numerical verdicts remain:

| Prediction | Channel | Reading |
|---|---|---|
| **53** (DSHARP disk gaps) | gas/condensation | **SUPPORTS** at 3.86$\sigma$ (`hypotheses/exoplanet-phi-spacing.md` §7) |
| **54** (Kepler/TESS period ratios) | orbital/matter | **INDETERMINATE** (+1.03$\sigma$ headline $\varphi^{3/2}$ window, controls at baseline; the standard 3:2 mean-motion resonance is elevated at +2.39$\sigma$; `hypotheses/exoplanet-phi-spacing.md` §8) |

Under the conditional channel hypothesis, Prediction 53 supplies a measured
spacing result in a gas/condensation tracer, while Prediction 54 remains an
indeterminate orbital-tracer result. The records constrain how a future
constitutive coupling could be tested; they do not determine the compact
phase, the amplitude current, or an inter-rung transport law. The numerical
verdicts remain the records in `hypotheses/exoplanet-phi-spacing.md` §7–§8.

**Tier: Hypothesized conditional.** The table is measured observational
evidence. Its channel interpretation and any transmission from $C$ to a
tracer require the optional structure and a dedicated test.

## 6. Simulation measurements and scope

The first-order four-arm probe and the space-sim second-order waveform report
no persistent radial ladder at the tested lock timescale
(`foundations/bubble-edge-geometry.md` §3.6; the sim's
`diag_bubble_rings.gd`). These nulls describe the measured matter-density
profile: the tested field evolution did not organize that density tracer into
the assigned radial rings.

The same simulation record reports a single dominant coherence-field scale,
with no $\varphi$-ladder in the free clump dynamics (§2). The condensation
field's checkerboard morphology remains the specified geometric construction,
and the single-mode result records the measured dynamical outcome. The
optional radial coordinate, amplitude lift, and spacing map remain separate
model objects whose transmission to a density tracer requires implementation
and measurement.

**Tier: Hypothesized conditional.** The no-ring and single-mode results remain
measured nulls for the tested simulation. Their interpretation as a channel
boundary is conditional on the optional spacing map.

---

## 7. Scope of the interpretation

- Prediction 53 remains **SUPPORTS** at 3.86$\sigma$ in the DSHARP disk-gap
  record.
- Prediction 54 remains **INDETERMINATE**, including the +1.03$\sigma$
  headline and the reported +2.12$\sigma$ K2/TESS cross-check.
- The channel reading is a Hypothesized interpretation of tracer dependence.
  It leaves the observational verdicts and simulation nulls at their recorded
  values.
- A compact phase, an amplitude-plane current, a $\varphi$-ring coordinate,
  and inter-rung transmission are optional structures. Each requires an
  explicit map, units, constitutive coupling, and a measurement that can
  distinguish it from the local density diagnostics.

---

## References

- `foundations/qi-flow-double-helix.md`—canonical density-plane diagnostics;
  optional compact-phase and helical structure
- `foundations/cassi-first-principles.md`—the real doublet, the two-fluid PDE,
  conversion, and canonical coherence definitions
- `foundations/bubble-lattice-fabric.md` §1–2—the condensation field,
  clumping, checkerboard lattice, scale covariance
- `foundations/bubble-edge-geometry.md` §1.1—$C(x,y)$ and
 $q_{\rm proxy} = (1+C)^2/2$, with
 $q_{\rm solver}=\mathcal M(q_{\rm proxy})$ and
 $\mathcal M:[0,2]\to[0,1]$; §3.1—the optional ring law; §3.5—the wake-sum
 null; §3.6—the no-ring nulls
- `foundations/dimensionful-cascade.md`—the cascade ladder $\ell_n$
- `hypotheses/exoplanet-phi-spacing.md` §7—DSHARP disk-gap test (Prediction
  53, SUPPORTS 3.86$\sigma$); §8—Kepler period-ratio test (Prediction 54,
  INDETERMINATE)
- `predictions/falsifiable-predictions.md`—Prediction 53, Prediction 54
- `open-questions-cassi-answers.md`—C9 (cosmic web from the wake/coherence
  field)
