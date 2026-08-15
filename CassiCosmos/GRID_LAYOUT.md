# GRID_LAYOUT — Theory-Accurate Box Aspect for the Cassi Space Sim

**Status:** Design + implementation plan (no code changed this turn; this file is new and uncommitted)
**Repo:** `CassiCosmos` — this repo, extracted from the physics repo's `godot/space-sim` subtree with full git history. The CassiTheory repo is read-only input.
**Date:** 2026-08-11

---

## 0. The problem, restated

RealSim mode (gravity_mode=4) produces realistic voids and filaments, but as the
structure spreads to fill the simulation box it takes on the LARGER grid shape:
filaments align to the box axes and form straight lines. The per-particle force
has a measured grid-line anisotropy that is intrinsic to the discrete
torus-Green (periodic-image) field:

| radius | \|a\| max/min |
|---|---|
| 2h | 1.366 |
| 4h | 1.129 |
| 8h | 1.044 |
| 16h | 1.017 |

Self-similar in r/h (identical at N=64 and N=128 at the same cell radius),
strongest along the grid axes. It is NOT the sampler (Catmull-Rom tricubic
reverted), NOT the k_max truncation, NOT box padding (2L solve = flat no-op),
and the k-space D19 symbol only helps delta sources, not smooth blob fields.
The 19-point real-space stencil is not the problem either (0.8% dispersion
anisotropy at the operating point vs 16% for the 7-point).

**The new interpretation this design develops:** what the user sees is the
**box-mode resonance** — the periodic image lattice of a CUBIC box reinforces
the axes at box scale, locking filaments into straight lines as the structure
grows to fill the box. The theory-accurate fix is to make the BOX itself
incommensurate: per-axis extents ∝ (1, φ, φ²). A RECTANGULAR (not sheared) box
keeps Cartesian separability, so the hand-rolled Stockham FFT and the exact
torus Green's function survive — only the cell aspect becomes anisotropic
(h_x ≠ h_y ≠ h_z with N³ cells unchanged).

---

## 1. Theory grounding (quotes from CassiTheory)

### 1.1 The three lattice periods

`foundations/bubble-lattice-fabric.md` derives the condensation field
(§1.1) and tabulates the three orthogonal periodicities (§3.1):

> $$B(x, y, z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z), \qquad \alpha = \frac{2\pi}{\Lambda_Y},\;\; \beta = \frac{2\pi}{\Lambda_I} = \varphi\alpha,\;\; \gamma = \frac{2\pi}{P_\parallel}$$
>
> - $x$: Yang axis (extended, normal direction)
> - $y$: Yin axis (contracted, binormal direction)
> - $z$: String axis (cascade direction, tangent)
> - $\Lambda_Y$: Yang wake wavelength in the $x$-$y$ plane
> - $\Lambda_I = \Lambda_Y/\varphi$: Yin wake wavelength
> - $P_\parallel$: along-string bubble period

| Axis | Direction | Period | Spacing |
|---|---|---|---|
| x (Yang, normal) | Extended | Λ_Y = ℓ_n | widest |
| y (Yin, binormal) | Contracted | Λ_I = ℓ_n/φ | intermediate |
| z (String, tangent) | Cascade | P∥·ℓ_n | along-string |

- **Λ_Y = ℓ_n** — the Yang wake wavelength (the widest transverse period),
  where ℓ_n = ℓ_Pl·φ^n (`foundations/dimensionful-cascade.md` §2: the cascade
  formula $\ell_n = \ell_{\text{Pl}} \times \varphi^{n}$).
- **Λ_I = ℓ_n/φ** — the Yin wake wavelength, the incommensurate partner.
  At the cosmological rung the measured "BAO ~120 Mpc" label is the Yin period:
  *"Step 284 (117.9 Mpc) is the Yin wake wavelength of the rung-285 lattice
  ($\Lambda_I^{(285)} = \ell_{285}/\varphi$)"* (`dimensionful-cascade.md` §6).
- **P∥ — the along-string bubble period, i.e. the period along the STRING /
  flow / cascade axis (z).** It is the number of cascade rungs between
  adjacent bubble maxima along the string: *"Coherence flowing along the
  string axis is coherence flowing between cascade scales"* and
  *"P∥ = 2 cycle winds the Yang and Yin strand-currents into a double helix
  about the string axis"* (`bubble-lattice-fabric.md` §1.1). P∥(n) = 1 rung at
  the cosmological scale, 2 rungs at the human scale (§2.3 table).

The bubble edge is *"an oblate triaxial spheroid — extended in Yang,
contracted in Yin, bounded along the string"* (§1.3), with the φ-elliptical
transverse cross-section *"a_X/a_Y = β/α = φ"* (§4.1). **The structure itself
is triaxial; a triaxial box is its commensurate container.**

### 1.2 The de-resonance argument

`principles/de-resonance-principle.md` §1:

> In a system of coupled oscillators, a **rational frequency ratio** leads to
> **resonance** — energy concentrates at a single scale, and the multi-scale
> structure collapses. An **irrational frequency ratio** prevents this…
> The golden ratio φ is the **most irrational** of all irrationals: its
> continued fraction is [1; 1, 1, 1, …] forever… **Consequence:** φ is the
> *maximally de-resonant* value.

Against ANY periodic box, the wake-geometry theorem (quoted in rewrite brief
37 §2.1) is exact:

> "A common crest requires x = a·ℓ_n = b·ℓ_n/φ with integers a, b, i.e.
> a = b/φ. Since φ is irrational, the only integer solution is a = b = 0.
> The de-resonance principle is built into the wave structure itself: the
> wakes can never resonate with each other, at any point, at any rung."

A cubic box's mode lattice n ∈ Z³ has the full cubic symmetry group; any
structure whose power spreads to the box scale locks onto the degenerate
axis/face-diagonal directions. A box whose three periods are mutually
incommensurate removes the degeneracy by construction. **This is the box-level
application of the same principle** (this is a design rationale, not a new
derived claim — flagged as such).

### 1.3 The flow direction (which axis is P∥)

The string axis **z** is the flow/cascade axis:
- Brief 67 (`spiral-gravity/67-gravity-from-flow-laws.md` §A.0):
  *"The 1D harness's 'axial' direction is the string; ∇·J = ∂_zJ_z there"* —
  the phase-current flow object lives along z.
- The owner's river synthesis: *"the flow across scales is a spatial river of
  changing force"* — the inter-scale flow is along the string (z).
- The cascade ladder is the 1D slice along the string: *"The cascade steps
  n = 0…292 are the along-string bubble maxima"* (`bubble-lattice-fabric.md`
  §5).

**Conclusion for the box orientation:** z = string = P∥ axis = the direction
along which structure extends farthest (the flow direction). The box must be
longest along z. The transverse pair (x, y) mirrors the φ-elliptical
anisotropy: Yang extended (larger period) vs Yin contracted (Λ_I = Λ_Y/φ).

---

## 2. Design decision

### 2.1 The export and the theory preset

```gdscript
## Per-axis box aspect (extent_i = aspect_i · 1.5 · cluster_radius; N³ cells).
## Vector3(1,1,1) = the legacy cube (the existing verify battery runs this).
## Theory preset: Vector3(PHI, 1.0, PHI*PHI) — see GRID_LAYOUT.md §2.2.
@export var box_aspect: Vector3 = Vector3(1, 1, 1)
```

Default cube → the existing battery is untouched (bit-behavior preserved up to
fp32 reassociation, all tolerances met).

### 2.2 The permutation: (x, y, z) = (φ, 1, φ²)

| Sim axis | Theory label | Aspect | Rationale |
|---|---|---|---|
| x | Yang (normal, extended) | φ | L_x : L_y = φ : 1 mirrors Λ_Y : Λ_I = φ : 1 (the φ-elliptical cross-section §4.1); the extended direction needs the larger transverse extent so the checkerboard is equally resolved |
| y | Yin (binormal, contracted) | 1 | the contracted partner; reference extent |
| z | String (tangent, cascade) | φ² | the P∥ axis and the flow direction — longest extent; φ² is the next φ-power, chosen de-resonantly: at P∥=1 the literal periods would be (1, φ⁻¹, 1) with an x–z degeneracy, so (1, φ, φ²) deliberately breaks it |

Every pairwise ratio is irrational (φ, φ², φ), so the box-mode lattice
n ∈ Z³ with shell Σ(n_i/L_i)² = const is an ellipsoid with **no axis
permutation symmetry** — only the trivial n_i → −n_i sign flips survive
(real field). No direction is degenerate with any other; filaments have no
axis set to lock to. The box-mode frequency ratios are 1 : φ : φ² — the
maximally de-resonant triple — so the box cannot resonate with the
structure's own φ-cascade scales, nor can the three box directions beat with
each other.

The theory labels are assigned to the SIM's x/y/z axes (the box axes); there
is no physical reason to align the string axis with the camera orbit axis.

### 2.3 Derived quantities

With extent_base = 1.5·cluster_radius (the current single extent):

```
extent_i = box_scale · box_aspect[i] · extent_base   (half-extent per axis)
L_i      = 2 · extent_i                     (torus period per axis)
h_i      = 2 · extent_i / N = box_scale · aspect_i · h₀,   h₀ = 2·extent_base/N
```

box_scale is a UNIFORM rescale: it multiplies every extent by the same
factor, so all ratios — the aspect incommensurability, the anisotropic
stencil weights (§2.5), the k-sum Green's force ratios on the three axes,
and the resolved rung window log_φ(N/2) — are invariant. Its only physical
effect is to separate the cluster from its periodic images (§2.8). The
default 1.0 is the legacy geometry bit-for-bit (×1.0 is exact in fp32);
scale ≈ 3 is the tested isolation regime. Calibration note: G_N is
recomputed from the ACTUAL h (G_N = 4π/(π_ref·g_ref·h³·m_mean)), so the
grid force stays ≈ M_count/r² at every box_scale (the product
G_N·V_cell = G_N·h_x·h_y·h_z is box_scale-invariant).

Concrete numbers for the (φ, 1, φ²) preset:

| cluster_radius | extent (x,y,z) | h at N=64 (x,y,z) |
|---|---|---|
| 25 (verify scenes) | (60.68, 37.50, 98.18) | (1.896, 1.172, 3.069) |
| 50 (gravity_modes scene) | (121.35, 75.00, 196.35) | (3.793, 2.344, 6.138) |
| 20 (main.tscn) | (48.54, 30.00, 78.54) | — |

Nice invariant: the resolved rung window is axis-independent. Per axis,
k_min,i = 2π/L_i, k_max,i = π/h_i, and
log_φ(k_max,i/k_min,i) = log_φ(N/2) = 7.20 rungs at N=64 (the brief-37
convention) on every axis — the "N³ cells unchanged" property. The φ-aspect
box does not change the resolved dynamic range, only its geometric shape.

### 2.4 Transport: extents live in the BH header

Single source of truth for the three extents — **bh[2].yzw** (the buffer
already exists, is bound by the nbody/BH shaders, and is re-uploaded by the
host every frame):

```
bh[2] = (cluster_radius, extent_x, extent_y, extent_z)
```

- bh[2].x stays the Plummer softening scale (unchanged).
- bh[2].y keeps the name "extent" (at aspect 1 it IS the old extent) — the
  nbody samplers, grad pass, bh_integrate and condensation read bh[2].yzw
  directly; no nbody PC growth needed.
- The Poisson shader does NOT bind the bh buffer → its PC grows from 5 to 7
  floats (extent_x/y/z appended; dedicated PC, safe to grow).
- The mass-deposit shader binds only (pos, rho) → its PC grows from 4 to 5
  floats.
- The two-fluid shader binds only field buffers → it gets a **dedicated
  14-float PC** (the shared 11 + extent_x/y/z), following the established
  "dedicated-PC precedent" (the nbody shader already has its own 60-B PC;
  Godot hard-errors on push-constant size mismatch, so the shared 11-float
  `_pc_bytes` used by field_render/instancer/lensing stays untouched).
- `box_aspect` and `box_scale` are init-time exports like `cluster_radius`:
  changing them requires `reinit()` (the extents are encoded in
  `_bh_init_bytes` at `_setup_buffers`). Both flow through `_extents()`
  (cassi_sim.gd) — the SINGLE geometry formula — into the bh header, the
  Poisson/mass-deposit/two-fluid push constants, the IC truncation, the
  calibration and the occupancy sampler; there is no second extent formula
  anywhere in the host or the shaders (shaders read bh[2].yzw or their PC
  extents, which the host encodes from `_extents()`).

### 2.5 The 19-point stencil with anisotropic h (the derivation)

The two-fluid PDE's Laplacian must approximate the SAME physical ∇² the
Poisson solve inverts (k² = Σ(2πn_i/L_i)²), or the wave physics and the
gravity sector disagree in physical units. On an anisotropic lattice the
index-space second differences approximate h_i²·∂²/∂x_i², so the weights must
be h-dependent.

**Anisotropic 19-point** (L = Σ_i a_i·A_i + Σ_{i<j} b_ij·F_ij, where A_i =
ψ(i+1)+ψ(i−1)−2ψ is the axis pair and F_ij = Σ(4 face-diagonal neighbors
in plane (i,j)) − 4ψ):

```
b_ij = (1/3) · h₀² / (h_i² + h_j²)
a_i  = h₀²/h_i² − 2·(b_ij + b_ik)
```

- **Derivation (corrected 2026-08-11, verified against the analytic
  symbol):** for the mode e^{ik·x}, F_ij/ψ = 4(cosθ_i·cosθ_j − 1) with
  θ_i = k_phys,i·h_i, so F_ij ≈ 2h_i²∂²_iψ + 2h_j²∂²_jψ — the face term
  carries a **factor 2** on each ∂² (an earlier draft used
  2(cosθ_i+cosθ_j−2) and got this wrong by 2×; at unit aspect both reduce
  to (1/3, 1/6), so the cube battery cannot see the difference, but the
  wrong formula leaves a ±20% leading-symbol anisotropy at the φ-aspect).
  The ∂²_i coefficient of L is therefore h_i²(a_i + 2b_ij + 2b_ik);
  constraining it to h₀² (the cube's normalization — the current operator
  reads h²∇², coefficient 1) gives the a_i above. With
  b_ij = (1/3)h₀²/(h_i²+h_j²) the uniform limit is b = (1/3)/(2) = 1/6
  and a = 1 − 2(1/6+1/6) = 1/3.
- **Reduces EXACTLY to (1/3, 1/6) at unit aspect** → the cube battery's PDE
  behavior is preserved (weights computed from PC floats carry ~1e-7 fp
  rounding vs the current literal constants; every in-build tolerance is
  far looser).
- **Leading symbol −h₀²·k²_phys — EXACTLY isotropic in physical k** (the
  wave speed is isotropic in world units on all three axes at long
  wavelengths; the PDE sees the true ∇², matching the Poisson sector). The
  O(k⁴) terms are direction-dependent (∝ h_i⁴k_i⁴ — unavoidable on an
  anisotropic lattice): at fixed physical |k| with θ ≲ 1 the dispersion
  anisotropy is a few %, growing to ~10–20% at θ ~ 1.5–2 (wavelengths
  ~3–6 cells). This is the expected ellipsoidal dispersion of the φ-box;
  verify_phi_box check (e) pins it to the analytic symbol.
- **Weights at the (φ,1,φ²) aspect:** a = (0.127, 0.731, −0.009),
  b = (b_xy=0.092, b_xz=0.035, b_yz=0.042) — a_z is slightly NEGATIVE (the
  long axis's face terms over-contribute to ∂²_z; unavoidable for the
  exact leading symbol with this family), but the symbol stays
  negative-definite: max|S| ≈ 4.05 at (π,π,0) — LOWER than the cube's
  19-point 8.00 at (π,π,π) / 5.33 at (π,π,0), so the leapfrog CFL bound is
  relaxed, not tightened; dt = 0.001 stays far below it (confirmed by the
  φ-battery's 200-step occupancy run).

**Implementation note (bit-fidelity):** prefer computing the weights in the
shader from the three PC extents; at aspect = 1 the weights land on (1/3,
1/6) to fp32 rounding. The two strictest in-build checks (A3==A0 < 1e-9) are
within-build comparisons sharing the new code path, so they are unaffected.
Do NOT special-case aspect=1 in the shader unless a measured bit-level
regression demands it.

### 2.6 Mass deposit (TSC): kernel stays cell-based — justified

The TSC kernel is a separable quadratic B-spline in FRACTIONAL-CELL
coordinates: weights are functions of (f_x, f_y, f_z) only and form an exact
partition of unity at any fractional position. The kernel's PHYSICAL support
is 1.5h_i per axis automatically once the coordinate map becomes per-axis
(gc_i = wp_i·(N/2)/extent_i + N/2). **No weight change needed** — the
anisotropic physical support is a consequence of the map, the deposit stays
an exact partition of unity, and the 27-cell footprint in index space is
unchanged (same cost). The "isotropic cells → per-axis physical support" is
exactly this: the kernel is defined on the cell lattice, the physics is in
the map.

### 2.7 What else per-axis (the list)

| Quantity | Cube | φ-box |
|---|---|---|
| Poisson k-space | k² = (kx²+ky²+kz²)(2π/L)² | Σ (2π·k_i/L_i)² |
| Samplers (ey/ei/q/vel/grad) | gc = wp·(N/2)/extent + N/2 | gc_i = wp_i·(N/2)/extent_i + N/2 |
| Gradient pass h | h = extent/(N/2) | h_i = extent_i/(N/2); ∂_iS = Δ_iS/(2h_i) |
| Heuristic q-grad dx | dx = extent/(N/2) | dx_i = extent_i/(N/2) |
| Two-fluid Laplacian | (1/3, 1/6) weights | §2.5 weights |
| TSC deposit map | scale = (N/2)/extent | scale_i = (N/2)/extent_i |
| BH integrate world map | gc = pos·N/extent + N/2 | per-axis |
| BH cell volume | (extent/N)³ | extent_x·extent_y·extent_z/N³ |
| Condensation world map / volume | same | same |
| G_N calibration | h³ | h_x·h_y·h_z (= φ³·h₀³ at the preset) |
| IC safe radius | r_max = fr·extent − \|c\|_∞ | r_max = fr·min_i(extent_i) − \|c\|_∞ (conservative; keeps every IC inside the box and the retained-fraction analytics unchanged) |
| Out-of-box / occupancy | \|x_i\| > extent | \|x_i\| > extent_i; lim_i = 0.85·extent_i |
| Poisson residual report | (Σ6−6Φ)/h² | Σ_i (Σ2_i − 2Φ)/h_i² |

### 2.8 box_scale: cluster/image separation (the isolation lever)

The φ-aspect removes the box-mode DEGENERACY but keeps the cluster
FILL FRACTION fixed: extent_i = 1.5·aspect_i·R means the cluster always
spans 2/3 of the short axis (y), and the nearest periodic images sit at
2·extent_y = 3R — a quarter of the self-force at the cluster edge. The
image field is axis-ANISOTROPIC (short-axis images dominate), so at the
(φ,1,φ²) preset the y-axis restoring force is 10–15% weaker than circular
while x/z are 5–19% stronger (measured shader-exact: force/circular ratios
at r = a are x 1.05, y 0.85, z 1.12 at N=128/R=12). A single IC rotational
factor cannot balance all axes — the cluster is shredded along the short
axis within a few orbits, which is the observed φ-aspect cluster ejection
and (with RealSim dissipation) the corner pooling.

`box_scale` scales ALL three extents uniformly, so the aspect
incommensurability (§2.2) and every ratio in §2.7 are preserved while the
cluster pulls away from its images. The image/self force ratio at the
cluster edge drops like

```
F_img/F_self ~ 1/(3·box_scale − 1)²      (edge of the short axis)
```

| box_scale | extent_min | image/self at edge | y-axis deficit |
|---|---|---|---|
| 1 (legacy) | 1.5R | 25% | 10–15% (ejection regime) |
| 2 | 3R | 4% | ~4% |
| 3 (tested) | 4.5R | 1.6% | < 2% (isolated regime) |

verify_phi_box check (f) pins the measured multi-axis anisotropy of the
sphere's force below 2% at scale 3 and above 2% at scale 1 (the bracket).
The two-fluid stencil weights (§2.5) and the calibration (§2.3) are
uniform-rescale invariant, so scale 3 costs nothing in the physics —
only the resolved rung window per axis is unchanged (log_φ(N/2)) while the
cluster occupies a smaller fraction of each axis.

---

## 3. Solver survey — every site that assumes a single cubic extent

Per-site change + risk. Line numbers as of 2026-08-11.

### 3.1 `compute/cassi_poisson.glsl`
- **Header comment (7–9):** k_1d convention → per-axis L_i.
- **PC (41):** `float extent` → 3 floats (extent_x/y/z).
- **kspace_main (169–170):** `k2 = (kx²+ky²+kz²)·(2π/L)²` with
  `L = 2·pc.extent` → `k2 = (2π·kx/Lx)² + (2π·ky/Ly)² + (2π·kz/Lz)²`.
  Risk: fp32 reassociation changes Φ at ~1-ULP — verify_fft tolerances are
  loose (≥1e-4); within-build comparisons unaffected.
- Modes 0/1/3 (load/FFT/clear): extent-free — the Stockham FFT is pure
  index-space; **the FFT costs nothing extra for the φ-box.**

### 3.2 `compute/cassi_nbody_gravity.glsl`
- **Header (160):** document bh[2].yzw = extents.
- **DEFINE_TRI_SAMPLER macro (211–215):** `extent = bh[2].y` scalar map →
  per-component map from bh[2].yzw (affects tri_ey/tri_ei).
- **tri_grad (270–275):** same per-component map.
- **grad_main (330–335):** `h = bh[2].y/(N·0.5)` → h_i per axis; each gradient
  component divided by its own 2h_i.
- **sample_q_field (398–402, 438):** map + `dx = extent/hn` → dx_i per axis.
- **tri_fvel (511–516):** map (RealSim viscosity input).
- **Note block (262–269):** update the tricubic-verdict note — the lever is
  now the box aspect, not the sampler.
  Risk: 4 sampler bodies + gradient pass; all share one per-axis helper
  pattern (macro or a `gc_from_wp` function).

### 3.3 `compute/cassi_two_fluid.glsl`
- **PC (23–28):** +3 floats (extent_x/y/z) — becomes the dedicated 14-float PC;
  +1 float (pass_sel, pass A/B) → 15; +1 float (omega2 = ω₀², default 20.0) → 16 floats = 64 B.
- **lap_ey_at / lap_ei_at (45–81):** constant (1/3, 1/6) weights → §2.5
  per-axis weights (computed from the PC extents).
  Risks: (i) CFL — max|symbol| ≈ 4.07 vs cube 5.333, verify dt=0.001 stays
  far below the leapfrog bound; (ii) verify_ring's [100]/[110] premise
  (§4.5); (iii) at aspect=1 the weights must land on (1/3, 1/6) to fp
  rounding (§2.5 note).
- **source_ey/source_ei (84–107):** keep index-space Gaussians (debug seed
  path — the physical sources come from the deposited ρ; documented choice).

### 3.4 `compute/cassi_mass_deposit.glsl`
- **PC (44–49):** `extent` + `_pad` → 3 extents (PC 4 → 5 floats).
- **Main (62–64):** `scale = hn/extent` → scale_i = hn/extent_i;
  `gc = p·scale + hn` per component.
- TSC weights (82–91): unchanged (§2.6).
  Risk: none beyond the map; partition of unity preserved.

### 3.5 `compute/cassi_bh_integrate.glsl` *(found in the survey — not on the brief's list)*
- **(49–51):** `extent = bh[2].y`, `gc = (pos/extent)·N + N/2` → per-axis map
  from bh[2].yzw.
- **(58):** `cell_vol = (extent/N)³` → extent_x·extent_y·extent_z/N³
  (BH mass growth from field density).
  Risk: changes BH mass-growth normalization at aspect ≠ 1 (correct — the
  physical cell volume); BH tests run with the cube battery at aspect 1.

### 3.6 `compute/cassi_condensation.glsl` *(found in the survey — not on the brief's list)*
- **(55–62):** `extent = bh[2].y`, `world_pos = ((cell+0.5)/N·2−1)·extent`
  → per-axis world position (BH nucleation sites).
- **(64):** `cell_vol = (extent/N)³` → per-axis product.
  Risk: same as 3.5.

### 3.7 `scripts/cassi_sim.gd`
- **New export** `box_aspect: Vector3 = Vector3(1,1,1)` (§2.1) + a
  `_extents()` helper returning Vector3(extent_x, extent_y, extent_z).
- **_setup_buffers (459):** bh header `bh[2] = (cluster_radius, extent_x,
  extent_y, extent_z)` — encode from `box_aspect`.
- **_init_particles (780, 815, 931):** `extent_box` scalar → per-axis;
  `r_max_c = fr·min(extent_i) − c_abs`; out-of-box check per component.
- **_apply_gravity_calibration (1067–1073):** `h³` → `h_x·h_y·h_z`
  (the cell-volume factor the deposited density carries).
- **_step_dispatches (1205–1208):** md PC → 5 floats (3 extents);
  (1229–1233, 1391–1393): poisson PC → 7 floats; **(1261):** two-fluid
  dispatch binds the new 14-float `_two_fluid_pc_bytes` (new pre-allocated
  buffer, encoded alongside the shared `_pc_bytes`).
- **_report_poisson_residual (1363–1377):** per-axis 7-point
  ((Σ2_x − 2Φ)/h_x² + (Σ2_y − 2Φ)/h_y² + (Σ2_z − 2Φ)/h_z²).
- **_sample_occupancy (1599–1628):** per-axis extent_i and lim_i.
- **_setup_multimesh (1478):** custom_aabb ±5000 — the φ-box max extent at
  the biggest scene is φ²·1.5·50 ≈ 196 ≪ 5000; no change needed (note in
  code comment).
  Risks: PC size changes must keep Godot's strict size-match (the
  dedicated-PC precedent); `box_aspect` is init-time (reinit to apply).

### 3.8 `scripts/main_recorder.gd`
- **inherit_list (61–69):** add `"box_aspect"` — the value flows through from
  main.tscn automatically (per the task brief; confirmed the list is the only
  copy point). Optional `--aspect=x,y,z` CLI override for recording runs.

### 3.9 Verify scripts (cube battery stays at aspect 1; per-site for the φ-battery)
- **verify_gravity_modes.gd:** `extent`/`h` (103, 128–129); IC checks
  (431–444, 806–836 — lim = fr·extent → fr·min(extent_i)); occupancy
  (365–396 — per-axis lim/box); Gaussian blob writer (315–332 —
  x = (i−N/2)·h_x etc.); `_field_rho_at` mirror (902–922 per-axis map).
- **verify_river_isotropy.gd:** `extent`/`h` (106–107, 359–360); `_tri`
  (239–241), `_old_grad` (299–303), `_build_new_grad` (310–328) per-axis h;
  PHYS_RINGS (86) are physical radii — probe placement unchanged, cell
  radii differ per axis. The recorded cube anchors (1.3662/1.1293/1.0441/
  1.0173) stay as the aspect=1 regression values.
- **verify_ring.gd:** [100]/[110] plane waves at matched INDEX-|k|
  (m=20 vs m=14) — the dispersion test's premise (§4.5); unchanged at
  aspect 1.
- **verify_fft.gd:** kbase (163) and `_torus_green_center` (161–173) →
  per-axis kbase_i for the analytic reference; roundtrip tests extent-free.
- **verify_river_law.gd:** `extent`/`h` (35–36, 50–51); `_tri` mirrors
  (139–141, 257–258); radial profile probes (368–387) map with h_x.
- **scenes:** no tscn change needed — box_aspect defaults to (1,1,1); the
  φ-battery sets it via the new verify script.

---

## 4. Expected effect + honest limits

**What it removes:** the CUBIC image-lattice degeneracy. In the cube the
k-space mode shell is a sphere in n-space with the 48-element cubic symmetry
group; structure spreading to the box scale locks onto the degenerate axis
directions. In the φ-box the shell Σ(n_i/L_i)² = const is an ellipsoid with
no axis-permutation symmetry — **no direction is degenerate with any other,
so filaments cannot lock to a single axis set.** Box modes sit at
incommensurate frequencies (1 : φ : φ²), so they cannot resonate with the
structure's own φ-cascade scales — de-resonance at the box level, the same
principle that forbids wake crests from ever coinciding (de-resonance-principle §1;
wake-geometry's no-common-crests theorem, brief 37 §2.1).

**What it costs (stated plainly):** the per-direction anisotropy becomes
ELLIPSOIDAL. The torus-Green's iso-force contours are no longer cubic-
symmetric: at a fixed physical radius |a| differs along x vs y vs z by the
aspect-dependent image-lattice factors (the verification plan pins these to
the analytic k-sum, not to guesses). This does NOT remove the small-scale
r/h bias — the near-field lattice anisotropy (1.366@2h … 1.017@16h at fixed
r/h) is a per-direction effect that persists in magnitude class; what changes
is WHICH directions are degenerate (none at box scale) and how the |a|(θ)
pattern is distributed. The sim's resolved rung window is unchanged
(log_φ(N/4) per axis). ICs stay spherical (physical); the box is elongated
so the cluster's relative fill fraction along the long axes is smaller.

**Honest framing:** the φ-aspect box is the structural fix for the
box-scale straight-line lock, motivated by the theory's triaxial lattice
(§1.1) and de-resonance (§1.2). It is a DESIGN application of those results,
not a new derivation; the verification plan (below) pins the predictions
shader-exactly against the analytic k-sum.

---

## 5. Verification plan

Cube battery (aspect 1) must stay green untouched: verify_fft, verify_ring,
verify_river_law, verify_river_isotropy, verify_gravity_modes (all five
scenes, including the N=128 pass). All tolerances below are DERIVED from the
analytic prediction — none loosened from the cube tests.

**(a) ∇²Φ = ρ with the anisotropic stencil.**
The sim's one-time residual report becomes per-axis (§3.7). New check: the
7-point per-axis residual in the φ-box ≤ cube residual × max_i(h_i/h₀)² —
the 7-point truncation is O(h²) per axis, so the aspect-scaled bound is the
analytic expectation, not a loosening. Additionally, a manufactured-solution
check on the 19-point: apply the anisotropic stencil to the solved Φ of a
Gaussian blob and assert |L19[Φ] − ρ|/|ρ| ≤ the cube's measured value ×
max_i(h_i/h₀)² at the same blob σ.

**(b) Ellipsoid ring test at fixed r/h per axis-pair.**
Rings of 64 zero-mass probes in the xy, xz, yz planes at the same physical
radius (r = 8h₀, 4h₀) around a central delta. The |a|(θ) pattern is now the
ellipsoidal image-sum pattern; the CPU reference is the per-axis k-sum Green
(the `_torus_green_center` machinery generalized to per-axis L_i). Assert:
shader |a| vs the per-axis estimator < 1% (the cube's existing (i)
tolerance, per-axis h mirrors); per-axis OLD-vs-NEW estimator identity < 1%
(the algebraic identity survives per-axis); the |a|(θ=0)/|a|(θ=π/2) ratio on
each ring matches the k-sum prediction within the same 1% band.

**(c) Box-mode de-resonance proxy (the cubic-degeneracy test).**
Probes at (r,0,0), (0,r,0), (0,0,r) with r = 8h₀. Cube: the three |a| values
are equal by the 48-element symmetry — assert max pairwise relative deviation
< 1e-3 (a symmetry regression that also pins the cube battery). φ-box: the
three values differ; assert each matches the analytic image-lattice sum
F(r ê_i) = Σ_m (r ê_i − 2m·L)/|r ê_i − 2m·L|³ (computed in the verify script)
within the same 1% relative band the cube achieves against its own reference —
the inequality is PREDICTED, not merely "not equal".

**(d) 200-step occupancy / no-NaN with the φ-aspect.**
Extend `_test_occupancy_modes` with a φ-aspect pass (river, calibrated):
identical assertions to the cube battery (no NaN, zero out-of-box with the
per-axis bounds — guaranteed by the fr·min(extent_i) truncation, corner/face
reported per axis). Nothing loosened.

**(e) verify_ring dispersion extension (anisotropic stencil).**
The [100]/[110] plane-wave test measures the stencil symbol ratio at matched
INDEX-|k|. In the φ-box the physical wavenumbers differ per axis, so the
comparison must be at matched PHYSICAL |k|: choose mode indices m_ax, m_diag
per plane with (2πm_ax/N)²/h_i² = (2πm_diag/N)²(1/h_i² + 1/h_j²), then require
symbol[110]/symbol[100] ∈ [1−TOL, 1+TOL] with TOL re-derived from the
anisotropic symbol's O(k⁴) residual at those k (same 1.5%-class band as
today, computed — not inherited blindly). The cube battery's m=20/m=14 pair
stays as-is.

---

## 6. Rollout plan

Each commit keeps the repo runnable; verification per commit:

1. **Host plumbing (no behavior change).** `box_aspect` export + `_extents()`;
   bh[2].yzw encoding; md PC 4→5, poisson PC 5→7, new 14-float two-fluid PC
   (bound, values = cube); per-axis IC/occupancy/residual/calibration
   refactors; recorder inherit_list. Verify: the full cube battery (5 scenes)
   green at aspect 1.
2. **Shader per-axis kernels.** Poisson k² per-axis L_i; nbody samplers +
   grad + q-grad per-axis; two-fluid anisotropic weights; deposit per-axis
   map; BH shaders per-axis map + cell volume. Verify: cube battery green
   again (fp reassociation absorbed by tolerances); verify_fft delta/Gaussian
   solves re-checked against the per-axis analytic Green.
3. **φ-aspect activation + φ-battery.** New `verify_phi_box.gd` +
   `verify_phi_box.tscn` implementing (a)–(e); the occupancy extension. Verify:
   cube battery AND the φ-battery green; record the measured ellipsoid ratios
   vs the k-sum predictions (the doc's expected-effect claims).
4. **Preset flip + docs.** main.tscn / main_recorder.tscn RealSim runs move to
   box_aspect = (φ, 1, φ²); GRID_LAYOUT.md referenced from the sim README;
   commit message notes the new file is part of this commit. Verify: a short
   recorded RealSim run at the preset (no NaN; straight-line lock visually
   gone; occupancy sane).

The commit for this design doc alone is optional (it lives in the gitignored
godot/ subtree); fold it into commit 4's message.

---

## 7. Alternative ranking (honest)

| Option | Cost | Effect | Verdict |
|---|---|---|---|
| **φ-aspect box (this plan)** | moderate refactor (~10 shader/host sites + 1 new verify battery) | removes the cubic image-lattice degeneracy by construction; box-level de-resonance; FFT + exact torus-Green survive (rectangular, separable) | **first** — the structural fix |
| D19 k-space symbol | cheap (one kernel line) | partial: measured 1.9×@4h / 2.8×@8h for DELTA sources, but a measured NO-OP for the sim's TSC blob field (1.0896→1.0919@4h — the blob's roll-off damps exactly the modes the symbol changes); leaves the box-mode lattice cubic | cheap, partial |
| Render-only φ-shear | trivial (camera/world transform) | cosmetic: the SOLVER stays cubic — the box-mode resonance lives in index space; straight lines persist, only the visual mapping skews | doesn't fix dynamics |
| PM/PP direct correction | O(N²) or tree, new force term | fixes innermost forces only (r ≲ 2h); the box-scale mode structure is untouched | wrong lever |
| Higher resolution (N→2N) | 4× cost | ~2× r/h gain at fixed physical radius (the anisotropy is r/h-self-similar); box-mode structure unchanged — the straight-line lock persists | 4× for ~2×, box untouched |

---

## 8. Open items for the implementation turn

- Confirm the leapfrog CFL bound at the φ-aspect max|symbol| ≈ 4.07 with a
  short stability run before commit 2 lands (acceptance item, §2.5).
- Decide the φ-battery's exact PHYS_RINGS (use the cube's 2h₀/4h₀/8h₀/16h₀
  physical radii so the r/h anchors are directly comparable per axis).
- Record whether the φ-aspect measurably changes RealSim structure formation
  (filament orientation distribution) in a 200-step comparison run vs the
  cube at the same N — the qualitative claim this design is built on.
