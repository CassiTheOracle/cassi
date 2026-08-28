# CassiCraft — Two-Fluid Engine Port Specification (Java)

The exact, implementable port contract for the four engine-domain classes
(`TwoFluidSolver`, `SpectralPoisson`, `GradientPass`, `RiverForce`) + the job /
publish machinery (`EngineJob`, `SnapshotPublisher`), from the real
`CassiCosmos` engine to a JVM thread for the CassiCraft Fabric mod.

This document is **read-only analysis**. It reproduces the source of truth
verbatim from the real files and cites every equation and constant to its
file + line / function. Where the shader, the GDScript engine config, and the
design corpus disagree, the conflict is **flagged explicitly, never resolved
silently** — the port writer must decide, in consultation with the corpus's
determinism gate (§7), before coding.

Source files (all read-only here):

| File | Role |
|---|---|
| `CassiCosmos/compute/cassi_two_fluid.glsl` | pass_a / pass_b leapfrog + 19-point stencil |
| `CassiCosmos/compute/cassi_poisson.glsl` | fused Stockham FFT, k-space solve |
| `CassiCosmos/compute/cassi_nbody_gravity.glsl` | gradient pass + river law |
| `CassiCosmos/scripts/cassi_physics_engine.gd` | config block, step chain, job/publish |
| `CassiCosmos/scripts/cassi_sim.gd` | publish cadence (mirror_publish_cadence) |
| `CassiCraft/BUILD-PLAN.md` | port ordering (§3) + publish wire format (§4) |
| `CassiCraft/designs/chunk-field-quantization.md` | pinned box / dt / grid numbers (§1–2) |

---

## 0. Scope of the port (what this spec fills)

The four Java stubs already exist with pinned signatures:
`src/domain/java/dev/cassicraft/domain/engine/{TwoFluidSolver,SpectralPoisson,GradientPass,RiverForce}.java`
(+ `EngineJob.java`, `EngineBackend.java` and `snapshot/{FieldSnapshot,SnapshotPublisher}.java`
are named in BUILD-PLAN §2.2). This spec gives the exact numeric body each
stub's "port pass" comment promises:

1. `TwoFluidSolver` — reproduce pass_a / pass_b bit-for-bit for the field
   evolution (q, ε² exact).
2. `SpectralPoisson` — the fused Stockham FFT + `Φ̂ = −ρ̂/k²` solve.
3. `GradientPass` — the cell-centered `∇(g·Φ)`.
4. `RiverForce` — the river law at a streaming sample point.
5. `EngineJob` / `SnapshotPublisher` — the job-loop + publish machinery the
   corpus describes but the **current** engine no longer contains (the
   `M0b-P` one-RD migration removed it — §6).

**Not ported in Phase 1** (BUILD-PLAN §3.2): the 2.5M-particle nbody arm,
`mass_deposit` / `particle_merge`, the BH chain, tree gravity mode-5, the
meshless sites' JFA/LLoyd machinery (a radial-hotness fallback is the Phase-1
scheduler), rendering, and the dual-lattice grid. The **dual grid is pinned
OFF** for the port (see §3.1), because the engine header itself states the
default-off gradient/dual path is "numerically bit-identical" to the legacy
chain (`cassi_physics_engine.gd:1078-1079`).

---

## 1. TwoFluidSolver — the exact port

### 1.1 The equations (verbatim)

The shader header (`cassi_two_fluid.glsl:8-11`):

```
// Equations:
//   ∂²EY/∂t² = c²·∇²EY − ω₀²·(EY − φ·EI)
//   ∂²EI/∂t² = c²·∇²EI + ω₀²·(EY − φ·EI)
```

**Wave-speed conflict (flag #1).** The header writes `c²·∇²EY` with an explicit
`c²`, but `pass_a` (`cassi_two_fluid.glsl:202-203`) has **no `c²` factor**:

```glsl
float acc_ey = lap_ey - omega2 * ey_ei_diff;
float acc_ei = lap_ei + omega2 * ey_ei_diff;
```

The `c²` is **not a separate constant** anywhere in the engine config
(grep of `cassi_physics_engine.gd` for a wave-speed constant returns nothing;
only the concept `c_s` appears in the `merge_subsonic` comment). The operator
is normalized so that the 19-point stencil's leading symbol is `−h₀²·k²_phys`
(the shader comment at `cassi_two_fluid.glsl:74-80`: "the current operator
reads h²∇²", "The leading symbol is −h₀²·k²_phys"). In effect `c² · ∇²` is
`∇²` with the physical cell `h₀²` absorbed — i.e. **the leapfrog implements
`∂²ψ/∂t² = lap(ψ) ∓ ω₀²·ε` with `lap` carrying the `h₀²` normalization, and the
wave speed is implicit in the `dt`/`h₀` pairing, not a named constant.** The
BUILD-PLAN §8 step-8 row item "`FieldVel`, c_s = h₀/dt" names `c_s = h₀/dt` as
a *derived display* quantity, not a solver input. The port must implement the
shader form (no `c²` multiply); the corpus's `c²·∇²` notation should be read
as documentation of the continuum limit.

### 1.2 The leapfrog discretization (verbatim)

`pass_a` (`cassi_two_fluid.glsl:178-216`) — **reads** `ey/ei/vel/rho` (canonical,
old values), **writes ONLY** `scr` (the double-buffer). Per cell at `(i,j,k)`:

```glsl
float ey_old = ey[id];
float ei_old = ei[id];
vec4 vel_old = vel[id];
float lap_ey = lap_ey_at(i, j, k);
float lap_ei = lap_ei_at(i, j, k);
float omega2 = pc.omega2;                // ω₀² = 20.0
float phi = pc.phi;
float ey_ei_diff = ey_old - phi * ei_old;
float acc_ey = lap_ey - omega2 * ey_ei_diff;
float acc_ei = lap_ei + omega2 * ey_ei_diff;
float vx_new = vel_old.x + acc_ey * dt;  // half-step velocity
float vy_new = vel_old.y + acc_ei * dt;
float ey_new = ey_old + vx_new * dt + source_ey(i, j, k) * dt * dt;
float ei_new = ei_old + vy_new * dt + source_ei(i, j, k) * dt * dt;
scr[id] = vec4(ey_new, ei_new, vx_new, vy_new);
```

So the leapfrog is **velocity-Verlet-like**: `v ← v + acc·dt` then
`ψ ← ψ + v·dt` (a half-step-then-full-step on the half-integer velocity grid).
`vel.xyz` carries the time derivatives `(∂EY/∂t, ∂EI/∂t, 0)`; `vel.z` is
structurally `0` (a two-scalar-field wave). `source_ey`/`source_ei` are the
Gaussian perturbation sources (`cassi_two_fluid.glsl:149-172`) —

```glsl
// source_ey: dx=(i−half)/half, r2 = dx²+dy²+dz², s=source_strength
return s * exp(-r2 * 4.0) + mr * 0.001;        // mr = rho[id]
// source_ei: offset center (×0.7, ×0.8, ×0.6), s=source_strength·0.707
return s * exp(-r2 * 4.0) + mr * 0.001;        // mr = rho[id]·0.707
```

**The seed / IC conflict (flag #2).** The `CassiCraft` `TwoFluidSolver.java`
STUB seeds `java.util.Random` flat noise; the **real** engine IC
(`cassi_physics_engine.gd:1387-1422`, `_init_field`) seats
`field_attractor_init=false` as flat noise `rng.randf_range(-0.01,0.01)` in
EY/EI, `q = ey²+ei²`, and **`vel` all zero** (`vel[id*4..*4+3]=0`).
`source_strength = 0.0` by default (`:88`) — but `source_ey/source_ei` still
add their `rho·0.001` term, so the source is **not** pure-zero. GDScript
`RandomNumberGenerator.randf_range` is **not bit-compatible** with
`java.util.Random`; a fixed-seed replay across engine↔Java diverges at every
cell (top parity risk §7). The parity harness must either reproduce the
GDScript RNG, or replay a Java-generated IC and gate on relative drift
(iso-surface evolution) rather than bit-state. The Java `seed()` must at
minimum also zero `vel` (the current stub does).

**Buffer layouts (engine, `cassi_physics_engine.gd:1009-1018,1072`):**
`_field_ey/_field_ei/_field_q` = `nc·4` bytes (float per cell);
`_field_vel` and `_field_scratch` = `nc·16` (vec4 per cell);
`_fft_buf` = `nc·8` (vec2 per cell). `nc = grid_N³ = 262,144` at 64³.

### 1.3 pass_b (verbatim)

`pass_b` (`cassi_two_fluid.glsl:222-246`) — **reads ONLY `scr`**, writes the
canonical `ey/ei/q/vel`. The `q` and `ε²` the domain needs are recomputed here
(bit-identical to the single-pass formulas):

```glsl
vec4 s = scr[id];
float ey_new = s.x;
float ei_new = s.y;
float phi = pc.phi;
float q_val = ey_new * ey_new + ei_new * ei_new;          // q = EY² + EI²
float eps  = ey_new - phi * ei_new;
float eps2 = eps * eps;                                    // ε² = (EY − φ·EI)²
ey[id] = ey_new;
ei[id] = ei_new;
q[id]  = q_val;
vel[id] = vec4(s.z, s.w, 0.0, eps2);                       // (∂EY/∂t, ∂EI/∂t, 0, ε²)
```

So **`vel[].w` carries ε²**, and `q` rides its own `q` buffer — NOT `vel`. The
build-plan §4 table's "ρ … `vel[].w` carries **ε²**" phrasing (chunk doc §2)
is consistent: ε² lives in `vel[].w` per the engine.

### 1.4 The 19-point anisotropic Laplacian (verbatim weights)

`lap_ey_at` / `lap_ei_at` (`cassi_two_fluid.glsl:86-146`). The periodic wraps
(index helpers at `cassi_two_fluid.glsl:88-90`) —

```glsl
int ip = (i + 1) % N; int im = (i - 1 + N) % N;   // and jp/jm, kp/km
```

The weights (identical block in both `lap_ey_at` and `lap_ei_at`, computed
per-cell from the push-constant extents; `cassi_two_fluid.glsl:91-102`) —

```glsl
float hn = float(N) * 0.5;                              // N·0.5
float hx = pc.extent_x / hn;                            // = 2·extent_x/N
float hy = pc.extent_y / hn;
float hz = pc.extent_z / hn;
float h0 = min(min(pc.extent_x, pc.extent_y), pc.extent_z) / hn;   // 2·min(extent)/N
float hx2 = hx*hx; float hy2 = hy*hy; float hz2 = hz*hz; float h02 = h0*h0;
float bxy = (1.0/3.0) * h02 / (hx2 + hy2);
float bxz = (1.0/3.0) * h02 / (hx2 + hz2);
float byz = (1.0/3.0) * h02 / (hy2 + hz2);
float ax  = h02 / hx2 - 2.0 * (bxy + bxz);
float ay  = h02 / hy2 - 2.0 * (bxy + byz);
float az  = h02 / hz2 - 2.0 * (bxz + byz);
```

Then the stencil sum over the 19 taps (`cassi_two_fluid.glsl:103-114`):

```glsl
float e = ey[idx3(i,j,k)];
// per-axis second differences:
float axis_x = ey[ip,j,k] + ey[im,j,k] - 2.0*e;
float axis_y = ey[i,jp,k] + ey[i,jm,k] - 2.0*e;
float axis_z = ey[i,j,kp] + ey[i,j,km] - 2.0*e;
// face-diagonal sums (each is the sum of 4 corners − 4·center):
float fd_xy = (ey[ip,jp,k] + ey[im,jp,k] + ey[ip,jm,k] + ey[im,jm,k] - 4.0*e);
float fd_xz = (ey[ip,j,kp] + ey[im,j,kp] + ey[ip,j,km] + ey[im,j,km] - 4.0*e);
float fd_yz = (ey[i,jp,kp] + ey[i,jm,kp] + ey[i,jp,km] + ey[i,jm,km] - 4.0*e);
return ax*axis_x + ay*axis_y + az*axis_z
     + bxy*fd_xy + bxz*fd_xz + byz*fd_yz;
```

**At unit aspect** (the CassiCraft cube) `hx=hy=hz=h0`, so `bxy=bxz=byz=1/6`
and `ax=ay=az=1/3` exactly — the shader comment at `cassi_two_fluid.glsl:81-82`
calls this "fp32-exact: (1/3)·h02/(2·h02) = (1/3)/2 = 1/6". The port MUST
compute the weights with the **same per-cell fp32 arithmetic** (or precompute
them once per box, since they are constant per box — the shader recomputes
them per cell but they are loop-invariant; a Java `static` precompute is
bit-identical as long as it uses the same expression order). The 19 taps
match the `STENCIL_X` array already in the stub (`center, ±x, ±y, ±z, then the
twelve ±xy/±xz/±yz corners`).

**Boundary conditions (flag #3).** The stencil and gradient pass use
**periodic torus wraps** (`(i+1)%N`, `(i-1+N)%N`); the corner taps reach two
wraps (e.g. `im,jm,k` wraps both x and y). The Java loop must reproduce the
wrap arithmetic **exactly as written** — a branchy clamped index differs and
is rejected (a modulo index is equivalent and fine). Over-flow across the
grid faces is impossible: the simulation is a torus and never reveals a
non-periodic seam.

**Physics note for the port's tolerance:** at the cube the operator's symbol
is `−h₀²·k²_phys` isotropic to `O(h⁶)`, so the stencil is fp32-exact at unit
aspect (no anisotropic weight drift). The CassiCraft box adds no dispersion
beyond the cube's.

### 1.5 The exact Java loop structure (deterministic fp32)

```
passA():                                      # one full grid loop, read-old/write-scratch
  float[] ey, ei, vel, rho; float[] scr;      # canonical + scratch (all float[])
  precompute hx,hy,hz,h0,bxy,bxz,byz,ax,ay,az once (per box)
  for k in 0..N-1: for j: for i:              # ANY traversal order — each cell is independent
    idx = i + N*(j + N*k)
    lap_ey = ax*(ey[ip]+ey[im]-2*ey[idx]) + ... + byz*fd_yz    # exact expression order
    lap_ei = (same with ei)
    diff  = ey[idx] - phi*ei[idx]
    accEy = lap_ey - omega2*diff;  accEi = lap_ei + omega2*diff
    vx = vel[4*idx+0] + accEy*dt;  vy = vel[4*idx+1] + accEi*dt
    srcEy = s*exp(-r2*4) + rho[idx]*0.001     # r2 from (i,j,k) cell coords
    srcEi = s*0.707*exp(-r2*4) + (rho[idx]*0.707)*0.001
    eyN  = ey[idx] + vx*dt + srcEy*dt*dt
    eiN  = ei[idx] + vy*dt + srcEi*dt*dt
    scr[4*idx+0]=eyN; scr[4*idx+1]=eiN; scr[4*idx+2]=vx; scr[4*idx+3]=vy

passB():                                      # copy scratch → canonical + q/ε²
    for each cell:
      ey[idx]=scr[4*idx+0]; ei[idx]=scr[4*idx+1]
      vx=scr[4*idx+2]; vy=scr[4*idx+3]
      q[idx] = eyN*eyN + eiN*eiN
      eps = eyN - phi*eiN; vel[4*idx+3] = eps*eps
      vel[4*idx+0]=vx; vel[4*idx+1]=vy; vel[4*idx+2]=0.0
```

**fp32 parity risk.** `pass_a` per-cell arithmetic is single-rounding fp32 and
partially associative — **the same expression with `+`/`-`/`*` in the same
order is bit-identical on CPU and GPU** for a scalar cell (no FMA contraction
in the shader; Java `float` math does not fuse multiply-add by default).
Two genuine risks: (a) if the Java JIT contracts an `fma` the shader did not
(it does not by default for `float` — JLS §15.17.2 forbids extended precision,
so `float` ops are IEEE-754 strict), the result flips ~1 ulp; (b) the source
`exp(-r2*4.0)` — GLSL `exp` and Java `Math.exp`/`(float)Math.exp` are NOT
guaranteed bit-identical (different libm). With `source_strength=0` only the
`rho·0.001` term survives (`source_ey` returns `mr·0.001` when `s=0`), so
`exp` is not on the default path — keep `source_strength=0` for the parity
run. If a nonzero source is ever used, reimplement `exp` with a `.f`-matching
table or accept a drift flagged as a parity risk.

---

## 2. SpectralPoisson — the FFT port

### 2.1 The solve (verbatim)

From `cassi_poisson.glsl:9-17` and the k-space passes:

```
∇²Φ = ρ_mass,  Φ̂ = −ρ̂/k²,  k = 0 nulled.
k_i = 2π·fftfreq(N)/L_i,  L_i = 2·extent_i    (per-axis torus period)
fftfreq labels: n ≤ N/2 → +n, n > N/2 → n − N   (Nyquist at +N/2 only)
```

`k²` per cell, `k2_of_cell` (`cassi_poisson.glsl:147-158`):

```glsl
int kx = (i <= N/2) ? i : i - N;              // and ky, kz from (j,k)
float kxw = TWO_PI * float(kx) / (2.0 * pc.extent_x);   // TWO_PI = 6.28318530717958647693
float kyw = TWO_PI * float(ky) / (2.0 * pc.extent_y);
float kzw = TWO_PI * float(kz) / (2.0 * pc.extent_z);
return kxw*kxw + kyw*kyw + kzw*kzw;
```

The k-space multiply (`kspace_main`, `cassi_poisson.glsl:263-268`; and the
fused mode-5 at `192-205`): `if (k2 > 0.0) { v = -v / k2; } else { v = 0; }`
— **division, one rounding** (`−f/k2`), NOT a reciprocal-multiply; the shader
comment at `144-147` is explicit that a reciprocal-multiply would differ by
~1 ulp. **The Java port must divide, never `1/k2 * f`.** `k=0` is nulled
(the mean of Φ is unphysical).

### 2.2 The fused Stockham structure (the 6 dispatches)

From `_dispatch_poisson` (`cassi_physics_engine.gd:2464-2513`) and the shader
modes, the per-solve sequence is:

```
mode 4  load ρ + forward-x            (fused; reads rho[], imag=0)
mode 1  forward FFT y
mode 1  forward FFT z
mode 5  inverse-z FUSED with the k-space multiply (axis=2, direction=1)
mode 1  inverse FFT y
mode 1  inverse FFT x
```

That is exactly the build-plan's `clear → load+x → fft(y) → fft(z) →
[kspace+inv-z] → ifft(y) → ifft(x)` (BUILD-PLAN §3.1; the corpus's
`chunk-field-quantization.md §4.1` lists it identically). `clear` (mode 3,
`cassi_poisson.glsl:277-296`) zeroes `rho` + telemetry at the top of each
step. With no particle deposit in field-only mode, **ρ is whatever the
mass-deposit produced (empty = 0) — the field-only Poisson solves over an
all-zero ρ unless the PDE's own `rho=EY+EI` is deposited.** The flux/reference
chain in the current engine deposits particle mass only, so a purely field-only
Poisson has `ρ=0` → `Φ=0` unless the port re-tasks the source. **Flag #4:** the
engine's Poisson source is the particle deposit; the corpus's field-only port
needs a defined ρ source (the build-plan table names `rho = EY+EI` as the
published channel — decide whether the Poisson solves over `EY+EI` or the
zero particle deposit). The Poisson kernel itself is source-agnostic.

### 2.3 The Stockham FFT (verbatim, per stage)

From `fft_main` (`cassi_poisson.glsl:164-254`):

- Dispatch is `(N, N²/R, 1)` with `R = 256/N` rows per workgroup (`R = 4` at
  `N=64`), 256 threads. Each thread `t`: `r = t/N`, `e = t%N`, row within
  block `= block·R + r`. This multi-row layout is asserted **bit-identical to
  the old one-row-per-workgroup schedule** (same bitrev, twiddles, butterfly
  order — `cassi_poisson.glsl:32-35`).
- The per-axis row's grid offsets (`row_base_stride`, `cassi_poisson.glsl:136-142`):
  - axis 0 (x): `base = N·r0 + N²·r1`, `stride = 1`
  - axis 1 (y): `base = r0 + N²·r1`, `stride = N`
  - axis 2 (z): `base = r0 + N·r1`, `stride = N²`
- **DIT requires the row loaded into shared in bit-reversed order** (log2(N)
  bits per axis, `bitrev` at `cassi_poisson.glsl:125-132`; the same reversed
  load on the inverse side closes the transform pair).
- Twiddle table `tw_tab[255]` (`cassi_poisson.glsl:215-223`):

```glsl
float ang = TWO_PI * float(jj) / float(1 << s);   // s stage 1..8, jj ∈ [0, 2^(s−1))
tw_tab[t] = vec2(cos(ang), -sin(ang));            // forward: exp(−iθ)
```

The per-stage butterfly (`cassi_poisson.glsl:228-250`), with an inverse
conjugating the twiddle (`if direction>0.5: tw.y = −tw.y`):

```glsl
for s in 1..bits:
  n_sub = 1<<s; halfn = 1<<(s-1)
  jj = e & (n_sub-1);  blk = e >> s
  if jj < halfn:
    even = sdata[rbank][r*N + blk*n_sub + jj]
    odd  = sdata[rbank][r*N + blk*n_sub + jj + halfn]
    tw   = tw_tab[(1<<(s-1))-1 + jj]             # forward: exp(−iθ); inverse conjugates
    o    = vec2(odd.x*tw.x − odd.y*tw.y, odd.x*tw.y + odd.y*tw.x)   # complex multiply
    sdata[wbank][slot] = even + o
    sdata[wbank][slot+halfn] = even − o
  barrier(); swap(rbank, wbank)                   # double-buffered banks
```

**Normalization:** forward passes are unnormalized; **each inverse pass scales
by `1/N`** (`cassi_poisson.glsl:252-253`). There are three inverse passes
(z, y, x) → total `1/N³`. `N=64` is radix-2 (R=4, bits=6).

**The k-space multiply rides the inverse-z load** (mode 5): the element is
taken from the *bit-reversed* offset, and **k² belongs to that physical cell**
(`cassi_poisson.glsl:194-204`): `cell = base + bitrev(e,bits)·stride`, `v = f[cell]`,
then `if k2>0: v = −v/k2 else 0`. So the k-space multiply is applied to the
forward spectrum at its physical positions during the first inverse load, then
the inverse butterflies run. This is the single most delicate ordering to
reproduce.

**The real part of `_fft_buf` (vec2/cell) holds Φ afterward**
(`cassi_poisson.glsl:43-44`; `readback_snapshot` extracts `fft[i*2]` as `pot`,
`cassi_physics_engine.gd:676-682`). The `pot` channel = the `.x` (real) part
of `_fft_buf`.

### 2.4 The Java plan — hand-rolled vs library (recommendation)

**Decision: hand-roll the radix-2 Stockham for determinism. Do not use
JVector/JOML's FFT.** Reasoning:

- The corpus's determinism gate (BUILD-PLAN §8, `async-field-domain.md` §7 Q6)
  demands q/pot/ρ/∇(g·Φ) match the engine's published reference **within the
  corpus's tolerance** — which is currently *unwritten* ([assumption], §7).
  A library FFT (JTransforms, JVector, FFTW bindings) uses a different
  radix/decomposition/twiddle ordering and **cannot be bit-identical** to the
  KISS-style Stockham autosort schedule in the shader. A hand-rolled Stockham
  with the exact bitrev + double-buffer + `1/N` per inverse pass is the only
  path to bit-level reproducibility.
- A hand-rolled Stockham for radix-2 `N=64`, `R=4` rows per workgroup is ~60
  lines and runs in well under the budget. The Java port performs the same
  stages over a flat `float[]` complex buffer (interleaved re/im), one axis at
  a time, iterating the row enumeration with the exact `base/stride` map.
- **Buffered vs shared-memory difference (parity risk):** the shader uses
  workgroup `shared` double-buffer `sdata[2][256]`; a Java port can use a
  single double-length scratch array (or two `N`-element rows) — the butterfly
  arithmetic is identical; only the memory layout differs, which does not
  change fp32 results because each butterfly reads/writes discrete elements
  with no reduction across different orders. **This is safe.** The one thing
  the port must NOT reorder is the **butterfly stage sequence** (s=1..bits,
  jj/blk decomposition) — that IS the aliasing contract.
- The port must replicate the **inverse-conjugation + `1/N` scale per inverse
  pass** and the **`−v/k2` (division) k-space multiply fused into the first
  inverse-z load**.

**Concrete step-by-step mapping (Java):**

1. Precompute (per box, once): the three `h_i`-derived `k²` denominator
   constants per cell (`kxw²+kyw²+kzw²`, from `extent_x/y/z`) — or compute
   per load; keeping the `kx,ky,kz` from `(i,j,k)` unrolled match the shader's
   `k2_of_cell(cell,N)` bit-for-bit.
2. `solve(rho, phi)`: `clear` ρ (internal dust) → `load+x` fused (write the
   row of `rho` at bit-reversed offsets into the working buffer, then run the
   forward-x butterflies) → `fft(y)` → `fft(z)` → `inv-z` with the fused
   `−v/k2` (load the *physical*-cell value at `base+bitrev(e)·stride`, null
   `k=0`) → `fft` inverse y → inverse x. After the last axis, `phi[i] =
   buffer[2i]` (the real part).
3. Each axis pass: build the 255-entry twiddle table once per run (they are
   N-dependent but not step-dependent — precompute once), and for axis `a`
   iterate rows `0..N²/R` with the `base/stride` map, applying the bit-reversed
   load and the staged butterflies with the `1/N` scale on inverse passes.

---

## 3. GradientPass — the trim

### 3.1 The gradient build (verbatim)

From `cassi_nbody_gravity.glsl`, `grad_pass` (`:431-472`), `chord_s_at`
(`:354-362`), and the cell selector `s_cell` (`:404-406`). One thread per cell,
2D dispatch, periodic wraps (`:442-444`). `gradient_order = 2` means the
**3-point** branch — `bh[3].z > 3.5` is the 5-point (order 4); the default
is `gradient_order = 2` (`cassi_physics_engine.gd:107`).

Cell value `S = g·Φ` at the cell center, whole product never hand-split
(`chord_s_at`):

```glsl
float rho_f = eyv + eiv;                       // cell EY+EI
float eps   = eyv - pc.phi * eiv;
float q     = (rho_f*rho_f) / (rho_f*rho_f + PHI_INV2 + eps*eps);  // PHI_INV2 = φ⁻²
return (1.0 + (pc.xi - 1.0) * q) * ph[id].x;   // g · Φ (the real part of the Poisson buffer)
```

With `PHI_INV2 = 0.3819660112501051` (`cassi_nbody_gravity.glsl:240`) and
`pc.xi = φ⁶` (the `xi` config, `17.94427191`).

The gradient (3-point, order 2; `cassi_nbody_gravity.glsl:446-465`):

```glsl
float spx = s_cell(ip,j, k), smx = s_cell(im,j, k);     // +/‑ x neighbors
float spy = s_cell(i, jp,k), smy = s_cell(i, jm,k);
float spz = s_cell(i, j, kp), smz = s_cell(i, j, km);
vec3 h = bh[2].yzw / (float(N) * 0.5);     // per-axis cell sizes (extent_i / hn)
g = vec3((spx - smx) / (2.0 * h.x),
         (spy - smy) / (2.0 * h.y),
         (spz - smz) / (2.0 * h.z));
grad[gid] = vec4(g, 0.0);                   // .xyz = ∇(g·Φ), .w = 0
```

**The `_grad_buf` layout** — `vec4/cell`, `.xyz = gradient`, `.w = 0`
(`cassi_nbody_gravity.glsl:174-177,469-471`; allocated `nc·16` bytes at
`cassi_physics_engine.gd:1072`). The **vec3 publish trim** = the `.xyz`
(`chunk-field-quantization.md §2`: 3 MiB, lossless). The 5-point (order 4)
formula is at `cassi_nbody_gravity.glsl:452-461` — not the Phase-1 default,
included for completeness:

```glsl
g = vec3((-s2px + 8.0*spx - 8.0*smx + s2mx) / (12.0*h.x),  ... );
```

**Dual-grid note (flag #5):** the engine default `dual_grid = true`
(`cassi_physics_engine.gd:108`), and phase-1 refers to the dual partner chain
binding 8. BUT `async-field-domain` / the build-plan pin the **field-only**
port; the engine header at `cassi_physics_engine.gd:1078-1079` states the
default-off cascade path is "numerically bit-identical". The port should pin
**dual_grid = false** (single `_grad_buf`, `gradS2` = 0) for the legacy
bit-identical chain, and record that the BCC dual chain (`chord_s_at_dual`,
`sample_fields`' `gradS2`) is a later, non-default extension. **The river arm
(`river_field_acc_smp`) averages `0.5·(gradS+gradS2)` when dual, else `gradS` —
with dual off it is exactly `gradS`.**

**Cell-center vs cell-value detail:** the engine evaluates `S` at **cell
centers from CELL values** (no interpolation; `chord_s_at` reads `ey[id]` /
`ei[id]` directly at the cell). The dual variant trilinearly samples the base
lattice back at the shifted center — do not port that unless dual is enabled.

The Java loop (per cell, flat arrays):

```
gradPass(double phi[], float ey[], float ei[], float[] gx,gy,gz):
  for cell (i,j,k) with ip/im/jp/jm/kp/km wraps:
    Sp = law(phi, ey, ei, at +x) ; Sm = law(phi, ey, ei, at −x)     # 6 law evals
    ... y, z
    gx = 0.5f*(Sp.x−Sm.x)/hx;  ...  (hx = extent_x / (N·0.5))
```

---

## 4. RiverForce — the river law

### 4.1 The law (verbatim)

From `chord_g_from` (`cassi_nbody_gravity.glsl:499-518`) and
`river_field_acc_smp` (`:526-532`):

```glsl
float chord_g_from(float eyv, float eiv, out float q_out, out float pi_over_rho, inout TeleStats st) {
    float rho_f = eyv + eiv;
    float eps = eyv - pc.phi * eiv;
    float q = (rho_f * rho_f) / (rho_f * rho_f + PHI_INV2 + eps * eps);
    if (rho_f < 1e-6) {                      // ρ guard
        pi_over_rho = 0.0;
    } else {
        pi_over_rho = (eyv - eiv) / rho_f;   // the Yang fraction π/ρ
        if (pi_over_rho > 0.72)       pi_over_rho = 0.72;   // upper clamp (PI_CLAMP_MAX)
        else if (pi_over_rho < 0.0)   pi_over_rho = 0.0;    // lower clamp
    }
    return 1.0 + (pc.xi - 1.0) * q;          // g — the chord coupling
}

vec3 river_field_acc_smp(FieldSmp fs, inout TeleStats st) {
    chord_g_from(fs.ey, fs.ei, q, pi_over_rho, st);
    float G_N = bh[1].w;
    vec3 gv = (bh[3].y > 0.5) ? 0.5*(fs.gradS + fs.gradS2) : fs.gradS;
    return -G_N * pi_over_rho * gv;          // a = −G_N·(π/ρ)·∇(g·Φ)
}
```

So at a sample point the acceleration is `a = −G_N·(π/ρ)·∇(g·Φ)` with:
- `ρ = EY+EI`, `ε = EY−φ·EI`, `q = ρ²/(ρ²+φ⁻²+ε²)`;
- `g = 1 + (ξ−1)·q` with `ξ = φ⁶`;
- `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)` with the `ρ < 1e-6` guard → 0
  (guard counted in telemetry, not silent — the port may drop telemetry or
  keep a counter, it does not change a);
- `∇(g·Φ)` from the gradient pass's trilinear sample at the point.

**Note the clamp is** `[0, 0.72]` — the law is **sign-definite** (the Yang
fraction is clamped positive). The engine hardcodes `0.72` via
`PI_CLAMP_MAX` (`cassi_physics_engine.gd:47`) and `1e-6` as a literal in
`chord_g_from`.

**G_N (engine config / flag #6).** `G_N` lives in `bh[1].w` and is written
by `_apply_gravity_calibration` (`cassi_physics_engine.gd:1685-1703`). When
`river_calibrate_gn = false` (the default, `:97`), `G_N = 1.0`
(`_bh_init_bytes.encode_float(28, 1.0); _gn_eff = 1.0`, `:1689-1692`). When
calibration is on, `gn = 4π / (river_pi_ref · g_ref · h·hy·hz · m_mean)`
(`:1699`) — the IC-consistent scale. **The port defaults `G_N = 1.0`** for the
Phase-1 steer (BUILD-PLAN §8 step-4 table uses the sign-flip direction);
`river_calibrate_gn` is a later option. This is a **conflict to note**: the
build-plan §3.1 names the river law without G_N's default; the engine default
is `1.0` only when calibration is off.

The domain's `RiverForce.accelerate(ek, gx, gy, gz)` stub currently takes
`ek` = ρ but the shader needs `(eyv, eiv)` separately (to form `ρ = EY+EI`
and `π/ρ = (EY−EI)/(EY+EI)`). **The Java signature must be extended to the
EY/EI pair** (or the sampler passes both) — the current `ek`-only stub cannot
compute the chord factor. The build-plan §4.1 field table's per-entity sample
already names "8 corners + mix, plus EY/EI for π/ρ" (`chunk-field-quantization.md
§2.2`), confirming both fields are needed.

---

## 5. The config block — every constant the port needs

From `cassi_physics_engine.gd` (var block `:79-114`, constants `:43-47`) and
the shaders. Each is cited; the pinned CassiCraft value from
`chunk-field-quantization.md §1.2` is called out where it differs from the
engine default.

| Constant | Engine default | CassiCraft pin | Source |
|---|---|---|---|
| `grid_N` | `64` | `64` | `cassi_physics_engine.gd:79` |
| `dt` | `0.001` | **`0.05`** (one field step/tick) | `:81`; chunk doc §1.1 |
| `xi` (ξ = φ⁶) | `17.94427191` | `17.94427191` | `:82`; `PHI_6` `:46` |
| `softening` | `0.1` (ε² = softening²) | (nbody-only, unused field-only) | `:83` |
| `cluster_radius` | `50.0` | **`64.0`** (cube) / `60.0` (default aspect) | `:84`; chunk doc §1.2 |
| `qi_condensation_threshold` | `0.5` | `0.5` (τ_c) | `:89` |
| `box_aspect` | `(1.618, 1.0, 2.618)` | **`(1,1,1)`** (Phase-1 chunk-aligned 192³) | `:105`; chunk doc §1.2 |
| `box_scale` | `1.0` | `1.0` | `:106` |
| `gradient_order` | `2` | `2` | `:107` |
| `dual_grid` | `true` | **false** (port pins off — bit-identical legacy) | `:108`; flag #5 |
| `omega2` (ω₀²) | `20.0` | `20.0` | `_two_fluid_pc_bytes…encode_float(60, 20.0)` `:2180` |
| `PHI` (φ) | `1.618033988749895` | same | `:43` |
| `PHI_INV2` (φ⁻²) | `0.3819660112501051` | same | `:45`; `cassi_nbody_gravity.glsl:240` |
| `PHI_INV3` (φ⁻³) | `0.2360679774997898` | same | `cassi_nbody_gravity.glsl:241` |
| `PHI_6` (φ⁶) | `17.94427191` | same | `:46` |
| `PI_CLAMP_MAX` | `0.72` | `0.72` | `:47` |
| `ρ` guard | `1e-6` | `1e-6` | `chord_g_from` (nbody `:507`) |
| `field_attractor_init` | `false` | false (flat noise IC) | `:100` |
| `source_strength` | `0.0` | `0.0` | `:88` |
| `N_particles` | `2500000` | **0** (field-only, no nbody) | `:80` |
| `q ≈ 0.947` | (derived, not a constant) | — | see below |
| `c_s = h₀/dt` | (derived, display only) | — | BUILD-PLAN §8 step 8 |

**`q ≈ 0.947` is NOT a literal.** It is derived in the shader header
(`cassi_nbody_gravity.glsl:68-71`): at the theory attractor `EY = φ·EI`,
`ρ = 1+φ`, so `q = (1+φ)²/((1+φ)²+φ⁻²) = 0.947 ≈ 1`. `(1.618033988749895+1)²/
((1.618033988749895+1)² + 0.3819660112501051) = 0.9472135954999581…` The port
does not need a `0.947` constant — it must NOT hardcode it, only the q formula.

**`c_s = h₀/dt`** appears only in BUILD-PLAN §8 step 8 as the weather-envelope
reading (`FieldVel, c_s = h₀/dt`), not in the engine (`cassi_physics_engine.gd`
has no `c_s` constant). `h₀ = 2·min(extent)/N`; at the CassiCraft cube
`h₀ = 2·96/64 = 3.0`, so `c_s = 3.0/0.05 = 60` — a derived display quantity;
**not a solver input** (the wave speed is implicit in the stencil normalization,
§1.1). Flag if the corpus expects `c_s` as a named constant.

**The box geometry (CassiCraft pin, verbatim from the engine's `_extents`):**
`_extents() = box_aspect · (cluster_radius·1.5) · max(box_scale, 1e-3)`
(`cassi_physics_engine.gd:908-909`). `_extent_min() = min of the three`
(`:912-914`). Chunk doc §1.2 pins the Phase-1 box: **`box_aspect=(1,1,1)`,
`cluster_radius=64.0` → half-extent 96 per axis → full 192³ m, `grid_N=64` →
cell = 3 m/axis, `h₀ = 2·96/64 = 3.0 m`, 12×12×12 chunks, 1,728 chunks**.
(The alternative default-aspect engineering baseline: `(1.618,1.0,2.618)×60×1.5`
→ half-extents `(145.62, 90, 235.62)`, full `291.24×180×471.24` m, `h₀=2.8125`.)
The port's `h_i = 2·extent_i/N` and `h₀ = 2·min(extent)/N` come from these.

---

## 6. The job / publish machinery

### 6.1 What the CURRENT engine actually does (verified)

The engine has **migrated to the `M0b-P` one-RD decoupled mode**: the worker's
job loop and every worker-side job mechanism is **gone**. The literal note at
`cassi_physics_engine.gd:365-370`:

> "(M0b-P-FX cleanup: the worker-side job machinery — _job_sem/_done_sem/
> _setup_sem/_job_mutex/_res_mutex/_job/_job_pending/_res_result/_res_gen/
> _consumed_gen/_wait_next/_snapshot_cadence/_job_counter — died with the
> job loop in M0b-P; all were reset-only. … snapshot_cadence is accepted and
> ignored (the readback cadence is the sim's mirror_publish_cadence).)"

The current run path is:

- `record_pending_steps(cl, target)` (`:554-572`): records `min(target−_executed,
  JOB_STEP_CAP)` steps into the **render thread's open list**, advancing
  `_executed` and `_time`. `JOB_STEP_CAP := 64` (`:66`) — a coalesced backlog
  drains in bounded <0.25 s slices. `TREE_JOB_STEP_CAP := 8` (`:65`) is the
  tree-cadence cap (not used field-only).
- `run_steps(n, wait, tree_in_list)` (`:580-594`) is the **local-RD standalone
  path** only; the decoupled global-RD path records into the frame list, which
  the renderer submits — the engine **never submits/syncs** on the global RD.
- `readback_snapshot(packed)` (`:665-686`) is **PROBE-ONLY** (`:660-663`: it
  "survives solely for the _diag/m0b_parity.gd parity probe"); **no production
  caller reads snapshots** — the decoupled render reads the engine's live
  buffers directly. Its layout *is* the parity reference the port replays:
  `pos`/`vel` (nbody), `field_q`, and `pot = fft[i*2]` (the real part).
- The window ships via `update_bh_header` (`:614-628`): `_window_center` is
  encoded into `bh[0].yzw` (`_bh_init_bytes.encode_float(4/8/12, …)`), row 0 of
  the BH buffer, at the top of each frame — the samplers map world→grid
  window-relative (`sample_fields`: `gc = ((wp − bh[0].yzw)·inv_ext)·hn + hn`,
  `cassi_nbody_gravity.glsl:278`).
- The **snapshot publish cadence** is the sim's `mirror_publish_cadence: int = 8`
  (`cassi_sim.gd:329`), and the publish payload is *telemetry-only meta*
  (`cassi_sim.gd:1932-1937`): `{"executed", "step_count", "t"}` every frame,
  with the *readback* `_engine_read_publish(true)` every `mirror_publish_cadence`
  frames. The full snapshot (field_q + pot + pos/vel) is only in
  `readback_snapshot`.

### 6.2 What the corpus / build-plan REQUIRE the JVM to re-create

BUILD-PLAN §3.3 and §9.1 name the divergence explicitly: the corpus's
`async-field-domain.md` (§2, §5) cites the engine's **older** job-loop API —
`submit_steps(target, block=)`, `poll()`, `_consume_latest()`, `_res_gen` /
`_consumed_gen`, the mutex handoff — as "the source of truth," but the **current**
engine no longer has it ("died in M0b-P"). **The JVM port must re-create the
job-loop / publish / latest-wins machinery from the corpus docs**, not from
the current engine. So the Java `EngineJob` / `SnapshotPublisher` are:

- **`EngineJob`** — the immutable record `{executed, step_count, t,
  window_center, generation}` (BUILD-PLAN §4.1). The JVM worker's `CassiFieldThread`
  polls a bounded job queue and drains `min(target − executed, JOB_STEP_CAP)`
  steps per job (the bounded-slice rule, `:66`), advancing `_executed` /
  `_time` — the engine's `record_pending_steps` accounting, re-created.
- **`SnapshotPublisher`** — the latest-wins volatile-reference handoff with a
  monotonic generation (BUILD-PLAN §4.2): `SnapshotPublisher.freshest()` is a
  volatile load; the worker builds a *fresh* immutable snapshot per publish and
  never mutates a published buffer; the sampler drops stale generations
  (`_consumed_gen` semantics re-created from the corpus). **The publish cadence
  the JVM should honor is the corpus's `snapshot_cadence = 2`** (BUILD-PLAN §4.2
  table) for the full snapshot, with light `{executed, step_count, t}` meta
  every job. This is a **conflict with the current engine** (`snapshot_cadence`
  is dead there; the sim's live value is `mirror_publish_cadence = 8`) — flag
  it: the port follows the **corpus** (`snapshot_cadence = 2`) for the field
  publish, not the engine's current 8.
- **`window_center` shipping** — the port's `EngineJob` must carry
  `window_center` so the box's world origin moves (the engine encodes it into
  `bh[0].yzw`, `:621-623`; the build-plan §5.3 pulse uses it to advect the grid
  with the player).
- **Snapshot payload** — the ≈ 6 MiB canonical field publish (BUILD-PLAN §4.1;
  chunk doc §2): `q` (1 MiB), `pot` (the `_fft_buf` real part, 1 MiB), `grad`
  (`_grad_buf` `.xyz` vec3 trim, 3 MiB), `ρ = EY+EI` (1 MiB); ε² rides in the
  ρ read (single float per cell, per the corpus's canonical form).

---

## 7. Parity risks, ranked

The corpus's determinism gate (BUILD-PLAN §9.1, `async-field-domain.md` §7 Q6)
states the **CPU ↔ GPU parity standard is unwritten** — a Phase-1 measurement,
flagged **[assumption] until pinned**. Every risk below is against that unset
tolerance; the recommended parity test is the same for all: **replay N steps
from a fixed seed and compare q / pot / ρ / ∇(g·Φ) against an engine-published
reference** (`readback_snapshot` field_q + pot + the `_grad_buf` trim). Until
the tolerance is written, the port should target **bit-identical (0 ulp)
wherever achievable** and lock any measured drift behind the pinned number.

Ranked:

1. **fp32 FFT determinism (hand-rolled Stockham).** The FFT butterfly stage
   order and twiddle/bitrev schedule are the highest-fidelity risk. If the
   Java port reorders stages or uses a library FFT, q/pot drift by many ulp.
   The hand-rolled Stockham with the exact `base/stride` + bit-reversed load +
   `−v/k2` division + `1/N` inverse scaling removes this risk entirely (it
   becomes bit-identical). **Gate:** hash `pot` after a solve vs the engine's
   `fft` real part; tolerance [assumption], target 0 ulp. **This is the top
   risk and the reason for §2.4's hand-rolled decision.**

2. **`exp()` / `sin`/`cos` libm mismatch.** GLSL `exp`, `cos`, `sin` vs Java
   `Math.*` (or `(float)Math.*`) are not guaranteed bit-identical across
   implementations. Impact: the Poisson twiddle table (`cos/sin`) and the
   source terms (`exp`). With `source_strength=0`, `exp` drops off pass_a's
   default path (only `rho·0.001` remains). The twiddle table is the real
   exposure: a `sin`/`cos` that differs by 1 ulp from the GPU's changes the
   FFT result. Mitigation: hard-code the 255-entry twiddle constants (computed
   once, frozen, machine-independent) rather than evaluating `sin/cos` at
   runtime — they are `N`-dependent but step-independent, so a constant table
   is valid and fully deterministic across CPU/GPU. **Gate:** pot hash vs
   engine, target 0 ulp modulo the table choice (the engine's GPU `sin/cos`
   table is itself the reference; if 1-ulp differs, flag and offset the
   tolerance).

3. **Seed / IC RNG mismatch (Java vs GDScript).** The engine IC uses GDScript
   `RandomNumberGenerator.randf_range`; the Java stub uses `java.util.Random`.
   These are different bit streams — a fixed seed does NOT produce identical
   initial EY/EI. If the parity harness replays an *engine* reference from a
   fixed seed, the Java solver cannot reach the same state (every cell's IC
   differs). Either (a) reproduce the GDScript RNG in Java for the reference
   replay, or (b) run the parity gate on a Java-generated IC and compare
   *relative* evolution (feature/iso-surface drift) rather than bit state.
   This is a **must-resolve before the parity harness is built.** Flag #2.

4. **Stencil boundary handling (periodic torus).** An off-by-one in the wrap
   (`(i−1+N)%N` vs a clamp) changes the stencil at every seam and seeds a
   growing error. The explicit-wrap arithmetic is trivially portable; the risk
   is a port that "simplifies" the modulus to a cheaper branch. **Gate:** after
   1 step the stencil-laplacian of a known field (e.g. a plane wave) must match
   the analytic symbol; after N steps, the mid-volume cells (far from any seam)
   stay bit-identical to the engine, and seam cells converge to the analytic
   periodic result.

5. **Wave-speed / c² treatment.** The header's `c²·∇²` must not become a
   literal `c*c` multiply in the port (there is no such constant in pass_a).
   A port that inserts `c²·lap` (e.g. from `c_s = h₀/dt`) over-scales the
   diffusion and diverges from the engine immediately. **Gate:** the first
   step's `log` change rate must match the engine's field_q delta; any
   `c²`-introduced factor shows as an immediate, large q drift. Flag #1.

6. **The missing job loop in the current engine.** The port re-creates the
   corpus's job-loop / publish from docs, not from the live engine (the engine
   has "decoupled" it away). This is an architecture drift, not a numeric one
   — the risk is implementing a publish cadence/step-budget that does not
   match what the corpus promises. **Gate:** the JVM `EngineJob` drains
   `JOB_STEP_CAP = 64` bounded slices, publishes field snapshots at
   `snapshot_cadence = 2` (per corpus), and carries `window_center`; the
   sampler sees only fresh generations. Flag the `snapshot_cadence=2` (corpus)
   vs `mirror_publish_cadence=8` (current engine) conflict — do not silently
   adopt one.

7. **Poisson source (ρ) ambiguity in field-only mode.** The engine's Poisson
   source is the particle mass deposit; field-only (no nbody) has `ρ=0` →
   `Φ=0` → `∇(g·Φ)=0` unless the port defines a source (e.g. `ρ = EY+EI`).
   This is a physics decision, not a numeric one — but it changes whether the
   river arm has any signal. **Gate:** the parity replay must state which ρ
   source it solves; a "river" test with an all-zero Poisson that returns zero
   gradient is a valid deterministic result, but must be documented so a
   non-zero expectation doesn't read as a bug. Flag #4.

**Recommended single parity probe (BUILD-PLAN §9.1 restated):** replay the
same N-step, fixed-seed run through the JVM domain and the engine
(`readback_snapshot`) and assert `q / pot / ρ / ∇(g·Φ)` match within the
corpus's tolerance (currently **[assumption]**; target bit-identical where the
RNG/table issues above are resolved, else lock the measured gap). Every
milestone's determinism gate (BUILD-PLAN §5 rows) is a hash of exactly these
four channels + the quantized world.

---

## 8. Cross-file citation index (the load-bearing lines)

- Two-fluid equations + pass_a/pass_b + stencil: `cassi_two_fluid.glsl:8-11, 178-254`
- Stencil weights + anisotropy analysis: `cassi_two_fluid.glsl:53-115`
- Poisson solve + Stockham + normalization + modes: `cassi_poisson.glsl:9-44, 125-268`
- 6-dispatch chain: `cassi_physics_engine.gd:2464-2513`
- Gradient pass + chart values + vec4/w=0 trim: `cassi_nbody_gravity.glsl:344-472`
- River law + π/ρ clamp + ρ guard + G_N: `cassi_nbody_gravity.glsl:499-532, 240-241, 507-518`
- Config block: `cassi_physics_engine.gd:43-47, 79-114`
- Gravity calibration / G_N default: `cassi_physics_engine.gd:1685-1703`
- `_extents` / `_extent_min`: `cassi_physics_engine.gd:908-914`
- Init field IC: `cassi_physics_engine.gd:1387-1422`
- run_steps / job cap / readback / window: `cassi_physics_engine.gd:554-686, 614-628`
- M0b-P job-loop death + publish cadence: `cassi_physics_engine.gd:365-370`; `cassi_sim.gd:329, 1932-1937`
- Corpus pins: `BUILD-PLAN.md §3.1-3.3, §4.1-4.2, §8 row 8, §9.1`; `chunk-field-quantization.md §1.2, §2, §4.1`
