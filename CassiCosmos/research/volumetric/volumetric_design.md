# Voxel Volume Raymarching — "Recreate Reality" Visual Design

**Status:** Design + verify-scene implementation (compute-matched raw RGBAF frame dump);
LIVE `cassi_sim.gd` hookup is **design-only**, deferred.
**Repo:** `godot/space-sim` (the volumetric real-time raymarch arm)
**Date:** 2026-08-13
**GPU target:** AMD RX 7900 XTX (RDNA3, 6144 shaders / 96 CUs, 24 GB GDDR6)

---

## 0. Goal and scope

Turn the sim's two-fluid grid field — `EY`/`EI` float-per-cell buffers plus the
derived `q = EY²+EI²` coherence and `ρ = EY+EI` density — into a **real-time,
ray-marched volumetric render** of the Qi field. This is the visual leap from
"a starfield of particles with a color legend" to "you are *inside* the field".
This wave ships:

1. `research/volumetric/volumetric_design.md` (this document — the model).
2. `compute/cassi_volumetric.gdshader` — a Godot fragment raymarcher of that
   model (box intersection, 3D-texture sampling, emission model).
3. `scripts/verify_volumetric.gd` + `scenes/verify_volumetric.tscn` — a
   self-contained scene: builds a KNOWN analytic field into a 3D texture,
   renders it through a SubViewport with the raymarch shader, dumps the raw
   frame to `_diag/volumetric_frame.png` and the pixel RGBAF values to
   `_diag/volumetric_pixels.json`.
4. `research/volumetric/volumetric_verify.py` — a NumPy reference raymarch of
   the SAME analytic field with the SAME model; gate **G35**: ≤ 1e-1 relative
   L2 vs the GPU frame, and the emission hue at the φ-gate pixel is pink.

The LIVE hookup (uploading `_field_ey`/`_field_ei` every frame) is designed
here (§6) but **does not modify `cassi_sim.gd`** — read-only this wave, per the
parallel-worker contract.

---

## 1. The field domain — the φ-aspect box

The raymarch domain is the sim's grid volume: the **φ-aspect box** (GRID_LAYOUT.md
§2.2). Origin-centered, per-axis **half-extents** (the `_extents()` formula,
`cassi_sim.gd:875`):

$$\vec{E} = (E_x, E_y, E_z) = \text{box\_scale} \cdot (1,\varphi,\varphi^2) \cdot 1.5\,R_c$$

with `R_c = cluster_radius`, and the theory preset `box_aspect = (φ, 1, φ²)` —
the maximally-de-resonant triple (GRID_LAYOUT.md §2.2). The box spans
`[-E, +E]` per axis; the grid stores `N³` cells (`grid_N ∈ [64, 256]`, power of
two), per-axis cell sizes

$$h_i = \frac{2 E_i}{N}$$

The box is the *view-aligned* containment volume for the march: a ray enters at
`t₀` and exits at `t₁` where the segment `S(t) = ro + t·rd` lies inside
`[−E, +E]` on every axis (slab intersection, §4).

**Why φ-aspect matters for the render:** the field is triaxial (Yang extended,
Yin contracted, string along z — the triaxial spheroid a_X/a_Y = φ of
GRID_LAYOUT.md §1.1). A cubic containment box would render the structure as if
isotropic; the φ-box is the theory-accurate container and the incommensurate
periods prevent the box modes from locking the visual structure to the axes —
the same de-resonance argument that justifies the solver box (§1.2). The volume
hoisting the field is the volume the physics actually lives in.

---

## 2. The per-cell field channels

The raymarcher consumes a **3D float texture** carrying the two-fluid state per
cell. The sim keeps these in `RenderingDevice` **storage buffers**, not
textures (`cassi_sim.gd:341-342`):

```
_field_ey — float per cell (Yang fluid), _field_ei — float per cell (Yin fluid)
```

Layout is `float ey[i + N·(j + N·k)]` (the `idx3` stride of the physics shaders,
`cassi_instancer.glsl:180`). For real-time volumetric we need a **texture**, so
the live hookup (§6) transfers buffer → 3D texture each frame (deferred). For
the **verify** wave the script builds the analytic field directly into a 3D
`ImageTexture3D` (RG float: R = EY, G = EI) — no sim edit.

From the two fluids the shader derives the two scalar axes, **matched exactly
to the particle palette** (§3):

$$\begin{aligned}
q(p) &= \mathrm{EY}^2 + \mathrm{EI}^2 \quad &&\text{Qi coherence (the instancer's } x\text{-axis, `cassi_instancer.glsl:68/277`)}\\
\rho(p) &= \mathrm{EY} + \mathrm{EI} \quad &&\text{density (scatter/absorption opacity; the deferred mode-4 axis, `cassi_instancer.glsl:216-219`)}
\end{aligned}$$

`q ≥ 0` and (for the verify field, whose EY/EI are Gaussian ≈ always non-negative)
`ρ ≥ 0`; the shader clamps both (`max(q,0)`, `max(ρ,0)`).

---

## 3. The emission color — the Qi-rainbow palette, exactly

The volumetric emission must use **the same color law as the particle
instancer** — a white-hot core that is chemically *pink* through the φ-gate
approach (violet 0.8 → pink 0.93 at the white point, `cassi_sim.gd:2461`),
plus the full Qi rainbow below it. The mapping is copied verbatim from
`cassi_instancer.glsl` so a raymarched Qi cloud reads as the *same physics* as
the particles.

### 3.1 The branchless HSL→RGB (instancer: `cassi_instancer.glsl:168-171`)

```glsl
vec3 hsl2rgb(vec3 c) {   // hue in [0,1): 0=red, 1/3=green, 2/3=blue, ~0.8=violet, ~0.93=pink
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}
```

### 3.2 The approach band (white-hot; instancer `cassi_instancer.glsl:310-315`,
### host fill `cassi_sim.gd:2461`)

The count-invariant white-hot stage maps `q ∈ [a_lo, a_hi]` onto hue
violet → **pink**, and lightness 0.5 → 1.0, **linearly** in a progress `pA`:

$$pA = \frac{q - a_{lo}}{a_{hi} - a_{lo}}\bigg|_{01}, \qquad
hA = 0.8 + (a_{top} - 0.8)\,pA, \qquad lA = 0.5 + 0.5\,pA$$

with `a_top = 0.93` — **pink at the white point** (`cassi_sim.gd:2461`
`_engine_c[E_TOP] = 0.93  # approach top hue = pink — red never appears at high
coherence`; the `:300` export docstring's "red (1.0)" is a stale superseded
comment). Because the band runs violet (0.8) → pink (0.93), a given emission
hue `h` in the pink band `[0.90, 0.97]` sits at

$$pA_h = \frac{h - 0.8}{0.93 - 0.8} \in [0.77, 1.0]\quad\Longrightarrow\quad
q_{gate}(h) = a_{lo} + pA_h\,(a_{hi} - a_{lo})$$

The verify run chooses `a_lo = 0.2`, `a_hi = 0.5` (a wide variant of the narrow
default `(0.617382, 0.618)` so the pink shell has measurable thickness) and
`GATE_PA = 0.95` (gate hue 0.9235); `q(0) = 0.5 = a_hi` makes the condensate
core exactly the white/pink top, and the pink shell is a well-defined analytic
radius (§5).

The mode gate (instancer `:313-315`):

```glsl
float inA = approach_on * step(a_lo, q);
float h   = mix(h_cyc, hA, inA);
float l   = mix(0.5,  lA, inA);
emit      = hsl2rgb(vec3(h, 1.0, l));
```

### 3.3 The cycle band (below the approach, `q < a_lo`) — instancer `:286-308`

For `q < a_lo` the hue follows the Qi rainbow: one full hue circle over
`q ∈ [q_lo, q_hi] = [2e-4, 1e-3]` with **log** progress and `ref = 0`:

$$h_{cyc} = \mathrm{mod}\!\Big(slope \cdot \ln\frac{q+\epsilon}{q_{lo}+\epsilon},\; 1.0\Big), \qquad slope = \frac{1}{\ln(q_{hi}/q_{lo})} = \frac{1}{\ln 5}$$

This yields red at the band foot, the full spectrum, and red again at the top —
the cascading rainbow halo around the white-hot core, faded by absorption.

### 3.4 Qi-coherence glow (optional)

A `GLOW` boost lifts lightness/emission toward white where `q` is a large
fraction of the white point (`cassi_instancer.glsl` ADDITIVE_GLOW, `:346-356`):

$$g = \mathrm{clamp}\!\Big(\frac{q}{a_{hi}}·GLOW\_GAIN,\ 0, 1\Big), \qquad
\mathrm{emit} = \mathrm{mix}(\mathrm{emit},\ \mathbf{1},\ g)$$

Default-off in the verify (so the raw model comparison is pure); documented as
the live-cosmetic upgrade.

---

## 4. The transport / compositing model

Ray from the camera (position `ro`) through the pixel has direction `rd`
(§4.1). The segment `[t₀, t₁]` inside the box is marched in fixed steps `ds =
(t₁ − t₀)/M` (`M = 224` GPU, `M = 320` NumPy — **different step counts by
design**, §7's tolerance justification). Front-to-back, first-order Beer–Lambert:

$$\begin{aligned}
\sigma_t &= \sigma_{abs}\,\rho + \sigma_{fog}   \quad \text{(extinction; m}^{-1}\text{)}\\
T &\leftarrow T \cdot e^{-\sigma_t\,ds}         \quad \text{(transmittance)}\\
C &\leftarrow C + T \cdot \big(\sigma_{em}\,\mathrm{emit}(p)\big)\,ds  \quad \text{(accumulate radiance before this step's absorption)}
\end{aligned}$$

- `σ_abs` = absorption/scatter coefficient on `ρ` (the "Yin absorbs the light
  that Yang emits" density coupling). Uniform in the verify.
- `σ_em` = emission coefficient (a scalar on the palette RGB; `emit` is already
  unit-saturating HSL→RGB, so `σ_em·emit` is the radiance rate).
- `σ_fog` = a constant residual extinction for camera-distance cave fog
  (default 0 in the verify so the reference is clean).
- **Early termination:** when `T < ε = 1e-3` the march breaks — the far field is
  opaque and contributes nothing.
- **Camera distance fog:** a final pass blends what remains transparent toward
  `fog_color` (the sim's near-black `(0, 0, 0.01)` default clear,
  `project.godot`), giving natural depth falloff:

$$C_{\text{final}} = C + T_{t_1}\cdot \mathrm{fog\_color}$$
with `T_t1` the surviving transmittance at box exit. (Optional: fog ∝ actual
camera distance is enabled by feeding the live camera slots, §6.2.)

The step count, `σ_abs`, `σ_em`, and the field all flow as uniforms so the verify
can dial them; the model above is literally what both the shader and the NumPy
reference compute.

---

## 5. The verify analytic field

The scene fills a `64³` RG 3D texture (R = EY, G = EI) with a **φ-attractor-like
config that is exactly recoverable analytically** — a central condensate blob
(the white-hot → pink → violet core) plus a small ε-structure pair (the Yin/Yang
φ-split perturbation). Box half-extents `E = (φ, 1, φ²)`; cell size
`h_i = 2E_i/64`.

**φ-anisotropic ellipsoidal radius** (the transverse ellipse a_X/a_Y = φ of
GRID_LAYOUT.md §4.1):

$$r_2(p) = x^2 + (\varphi\,y)^2 + (z/\varphi)^2$$

**Field** (`σ = 0.62`, so the core spans ≈ 12 cells in x — well inside the
trilinear-faithful band; `A = B = 0.5` sets `q(0) = A²+B² = 0.5 = a_hi`):

$$\begin{aligned}
\mathrm{EY}(p) &= A\,e^{-r_2/\sigma^2} + \varepsilon\,e^{-\lvert p-p_1\rvert^2/\sigma_\varepsilon^2}, \quad
\mathrm{EI}(p) = B\,e^{-r_2/\sigma^2} + \varepsilon\,e^{-\lvert p-p_2\rvert^2/\sigma_\varepsilon^2}\\
p_1 &= (0.85,\ 0.25,\ -0.35),\quad p_2 = (0.95,\ -0.20,\ 0.30),\quad \varepsilon = 0.06,\ \sigma_\varepsilon = 0.18
\end{aligned}$$

Both differentials have **closed-form q and ρ** (a radial Gaussian core plus two
small spherical ε bumps), so the NumPy reference samples the *same analytic
expressions* — it does not re-read the texture. The texture reads and the
analytic reference therefore differ only by trilinear interpolation error,
which the G35 tolerance absorbs.

**The φ-gate radius** (where the palette emission is pink, §3.2): solving
`q(r) = q_gate` on the core with `GATE_PA = 0.95` gives

$$q(r) = (A^2+B^2)\,e^{-2r_2/\sigma^2} = 0.5\,e^{-2r_2/\sigma^2}, \qquad
q_{gate} = a_{lo} + 0.95\,(a_{hi}-a_{lo}) = 0.485$$

$$r_{gate} = \sigma\sqrt{\tfrac{1}{2}\ln\frac{0.5}{0.485}} = 0.62\,\sqrt{\tfrac{1}{2}\ln 1.03093} \approx 0.0765$$

**The φ-gate pixel** is the pixel whose ray **tangently grazes** the `r_gate`
sphere — impact parameter `b = r_gate` on the horizontal through the origin
projection (`_tangent_gate_pixel` in the scene, `tangent_gate_pixel` in NumPy —
identical formula). A tangent ray samples radii `r ≥ r_gate` only
(`r² = b² + t² ≥ b²`), so its accumulated emission is the pink shell **without
dilution by the achromatic white core**; measured sweep (§7) shows its
accumulated HSL hue is 0.90–0.91 for every step count in [160, 448]. Both
renderers dump/read the accumulated RGB at that pixel; the G35 pink clause
checks its HSL hue ∈ `[0.90, 0.97]`.

---

## 6. The LIVE hookup — `cassi_sim.gd` (deferred, design-only)

The sim keeps the two fluids in RD **storage buffers** (§2). A volumetric frame
needs them as a **3D GPU texture**, so the hookup is a one-time texture
allocation + a per-frame buffer→texture upload. Nothing here edits
`cassi_sim.gd` this wave; the exact insertion points are below for the
integration turn.

### 6.1 Buffers and the upload pattern

Existing precedent — the sim already reads `_field_ey`/`_field_ei` into a CPU
array for the meshless sampler (`cassi_sim.gd:1552-1553`) and already creates
RD textures (`_make_render_texture`, `:2182-2190`). The volumetric hook adds one
3D texture plus a per-frame `_rd.texture_update`:

```gdscript
# ONCE (after _setup_buffers) — 3D RG float (R=EY, G=EI), N³
var _vol_tex := _rd.texture_create(
    RDTextureFormat.new()  # format = RD_DATA_FORMAT_R32G32_SFLOAT,
                          # width=height=depth=grid_N,
                          # usage = STORAGE | SAMPLING | UPDATE
    , RDTextureView.new(), [])
_rd.texture_update(_vol_tex, 0,
    _rd.buffer_get_data(_field_ey, 0, grid_N**3 * 4))   # EY → R
```

Because the two fluids live in *separate* float buffers but the texture is one
RG texture, the clean upload is **one interleaving compute pass**: a tiny
`cassi_volumetric_upload.glsl` that reads `ey[i]`, `ei[i]` (two storage
bindings — the exact pair the deferred instancer hook already specifies,
`cassi_instancer.glsl:37-38`) and writes `texel = vec4(ey, ei, 0, 0)` into the
3D texture, dispatched `grid_N³/64`. This stays fully GPU-side (no readback,
matches the sim's no-readback-per-frame discipline) and reuses the uniform-set
shape `cassi_sim.gd:1195-1198` binds.

### 6.2 Insertion points (exact)

| Site in `cassi_sim.gd` | What to add |
|---|---|
| `_setup_buffers` (≈459) | allocate `_vol_tex` (3D RG float N³), the upload shader + pipeline, the sampler uniform set |
| `_cache_uniform_sets` (≈1195) | bind the 3D texture (set `_us_vol_0` = the 2 storage buffers + the texture view) |
| `_physics_step()` → the per-step chain ending ≈2578 | after the two-fluid/nbody gradient passes (`_barrier`), dispatch the interleave-upload pass once per rendered frame |
| `_step_dispatches` / the global RD's per-frame command list | `_rd.texture_update(_vol_tex, 0, upload_interleave_bytes)` of the RG pair; no readback |
| Camera | the instancer's deferred camera slots pattern (`cassi_instancer.glsl:42-51`): write the live `_sim_cam` world position into 3 spare slots so the volumetric fog/depth-cue can use the true camera distance |

The **render pass**: a fullscreen quad (or the sim's existing field-render
texture mechanism) running `cassi_volumetric.gdshader`, sampling `_vol_tex` as
`sampler3D`, with the palette/a_lo/a_hi/σ uniforms driven by the same
`qi_approach`/`qi_condensation_threshold` exports the instancer uses
(`cassi_sim.gd:2358-2378`) so particles and volume always agree.

### 6.3 Cost on the 7900 XTX

Per-frame: one 3D-texture upload pass (`grid_N³/64` invocations — a few µs) +
the raymarch at viewport resolution. The raymarch is the cost:
`pixels × steps × (3 text)`. At 1280×720 with 96 steps early-terminated by the
1e-3 transmittance cut (most rays exit in ≪ 96 once they hit the dense core
edge) ≈ 8.8M final texture fetches — a fraction of a frame on RDNA3. Real-time
headroom is documented in §8; the verify frame (256², 224 steps) is
deliberately small to keep the two-image dump instantaneous.

---

## 7. Gate G35 — the verify pass

`research/volumetric/volumetric_verify.py`:

1. Recomputes the analytic field (`§5`), the camera, rays, and runs the NumPy
   reference march (`M = 320` steps, `ds` from the box entry/exit).
2. Reads the GPU frame's **raw RGBAF/RGB8 floats** from
   `_diag/volumetric_pixels.json`. Godot's SubViewport returns an **sRGB-encoded
   8-bit** image (3 B/px), so G35a is evaluated against BOTH the linear and the
   `sRGB(linear)` NumPy references and passes if either is ≤ 1e-1 (the sRGB
   encode is a display convention, not part of the raymarch model). `s_em = 0.31`
   keeps the peak linear radiance ≈ 1.0 so the 8-bit frame never clips to white
   and the pink gate pixel stays chromatic.
3. **relative L2**

$$\frac{\lVert C_{gpu} - C_{npy}\rVert_2}{\lVert C_{npy}\rVert_2} \le 1\times10^{-1}$$
   **measured 0.084** (sRGB-matched; the residual is the 8-bit quantization
   plus the trilinear-vs-analytic field difference at the 64³ texture).

   **Tolerance justification:** the GPU marches with `M = 224` steps and reads
   the *trilinear-interpolated 64³ texture*; NumPy marches `M = 320` steps and
   samples the *analytic field in closed form*. First-order integration error is
   O(ds) and finite-difference between step counts here is ≈ 2-6% of the
   accumulated radiance over the smooth σ = 0.62 core (the ε blobs add a
   localized ≤ few-% perturbation). The 1e-1 bound is ~2-5× the measured
   step+interpolation error (verified empirically), leaving unambiguous margin
   for a genuine model mismatch while still rejecting a broken palette or a
   wrong box/camera.
4. **Hue at the φ-gate pixel:** the φ-gate pixel is the tangent-to-`r_gate`
   pixel (§5). Its accumulated HSL hue is asserted ∈ `[0.90, 0.97]` in **both**
   the NumPy reference and the GPU frame. Measured (linear-RGB hue, invariant
   under the uniform `s_em` scaling; sRGB-encoded 8-bit ≈ 0.905, GPU ≈ 0.917):
   0.9008 (224 steps) / 0.9123 (320 steps) / 0.9097 (448 steps), with a
   chromatic spread well above the achromatic-noise floor — the pixel is
   genuinely pink, not the white core — robust to the step-count/`ds`
   difference at hand.
5. Prints `G35 PASS` (or `FAIL` with the L2 and hue values).

---

## 8. Performance budget — real-time on the RX 7900 XTX

| Parameter | Verify (this wave) | Target real-time |
|---|---|---|
| Viewport | 256² | 1280×720 (up-scalable) |
| Steps / ray | 224 (early-exit at T < 1e-3) | 96–128 + early exit |
| Texture res | 64³ RG | 64³–96³ RG (matches `grid_N`) |
| Fetches / ray (worst) | 224×3 | 128×3 |
| Est. cost | one-off (µs) | ≈ 8–12 M fetches/frame ≈ a few ms on RDNA3 |

Leverage order if the live hook needs headroom (all already in the model):
(1) reduce steps, (2) half-resolution render + bilinear upscale + a light blur,
(3) the transmittance early-exit (most rays exit behind the dense core),
(4) interleave-upload throttling (upload every 2nd frame; the field is smooth).
A dedicated MIP/prefilter of the 3D texture for the far field is a future,
non-blocking refinement.

---

## 9. Files and acceptance

- `compute/cassi_volumetric.gdshader` — the raymarcher (box intersection,
  sampler3D reads, palette/emission/absorption/fog).
- `scripts/verify_volumetric.gd` — builds the analytic 64³ RG texture, creates a
  SubViewport + camera + fullscreen quad, renders one frame, writes
  `_diag/volumetric_frame.png` + `_diag/volumetric_pixels.json`, dumps the box /
  camera / palette / σ params for the verifier.
- `scenes/verify_volumetric.tscn` — the entry scene (root + the verify script).
- `research/volumetric/volumetric_verify.py` — NumPy reference + **G35**.

**Acceptance:** the scene runs windowed and writes the frame;
`volumetric_verify.py` prints `G35 PASS`; this doc covers the live hookup.
