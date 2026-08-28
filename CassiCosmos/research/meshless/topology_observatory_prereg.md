# Topology observatory — preregistration

Status: PRE-REGISTERED (frozen before the first observatory run)

## Question

Do the fields that are actually available in the CassiCosmos meshless path show a
repeatable, detector-level phase-circulation signal in a supplied snapshot? The
observatory measures only the winding of the two-component field that is present.
It does not infer a mechanism, a particle string, or a new field from a positive
number.

## Available state and scope boundary

The live state available to this observatory is the site field pair `EY` and `EI`.
The runtime may also expose transient `PiY, PiI` values in `_field_vel` or in a
site `pi` buffer, and it may expose a `particle_vorticity` diagnostic. Those
parent circulation quantities are retained as diagnostic-only telemetry. They do
not enter the phase detector, do not change its thresholds, and do not establish
a persistent compact phase/current field.

There is no persistent compact phase-current state carrier in this campaign. In
particular, `PiY, PiI` are not silently promoted to such a carrier. A detector
hit therefore means only that the sampled `EY/EI` pair has lattice winding at the
sampled time. This campaign cannot establish a persistent compact phase/current,
physical strings, string persistence, or a physical circulation law without a
new state carrier and a separately preregistered persistence test.

## Frozen lattice and phase convention

The verifier uses a deterministic open Cartesian site lattice with shape
`(N_x, N_y, N_z) = (grid_N, grid_N, grid_N)`, indexed `(x, y, z)`. A flat JSON
field is reshaped in C order, so the last (`z`) index varies fastest. Spatial
boundary faces are retained; the domain is not spatially rolled. "Periodic
wrapped edge differences" means that every phase increment is reduced modulo
`2*pi` (the phase circle), not that a boundary site is connected to the opposite
boundary. This open-boundary choice makes boundary crossings measurable.

The native Godot field buffers use the shader's `idx3 = x + N*(y + N*z)`
layout, with `x` fastest. The live probe runs the detector in that native
layout, then reorders the top-level `ey` and `ei` receipt arrays to the
frozen C-order `(x,y,z)` contract above before JSON serialization. The
detector summaries retain the native coordinate labels; this serialization
step changes only the flat transport order.

At every site the compact coordinate used by the detector is exactly

```
theta(x,y,z) = atan2(EI(x,y,z), EY(x,y,z))
```

with `atan2` in `(-pi, pi]` as represented by numpy. Synthetic fields use
`EY = A*cos(theta)` and `EI = A*sin(theta)` with `A = 1.0`, so their amplitude is
nonzero everywhere. A live snapshot is phase-valid only when every amplitude
`sqrt(EY**2 + EI**2)` is finite and strictly greater than the frozen floor
`AMP_FLOOR = 1e-12`. A phase-invalid live snapshot is `INCONCLUSIVE`; the
verifier never assigns a phase at an amplitude zero and calls it topology.

For an oriented edge, the wrapped increment is

```
wrap(d) = ((d + pi) mod (2*pi)) - pi
```

with the exact tie `-pi` represented as `+pi`, giving `wrap(d) in (-pi, pi]`.
The three edge arrays are forward `+x`, `+y`, and `+z` differences. The three
plaquette arrays are integer values obtained by rounding the oriented
circulation divided by `2*pi`:

```
W_xy[x,y,z] = round(( dx[x,y,z] + dy[x+1,y,z]
                    - dx[x,y+1,z] - dy[x,y,z] ) / (2*pi))

W_yz[x,y,z] = round(( dy[x,y,z] + dz[x,y+1,z]
                    - dy[x,y,z+1] - dz[x,y,z] ) / (2*pi))

W_zx[x,y,z] = round(( dz[x,y,z] + dx[x,y,z+1]
                    - dz[x+1,y,z] - dx[x,y,z] ) / (2*pi))
```

Only terms whose site indices exist are used. Consequently the array shapes are
`W_xy: (N-1,N-1,N)`, `W_yz: (N,N-1,N-1)`, and `W_zx: (N-1,N,N-1)`. The sign is
that of the displayed orientation: `xy` has normal `+z`, `yz` has normal `+x`,
and `zx` has normal `+y`. A plaquette is nonzero exactly when its integer
winding is nonzero; the frozen nonzero threshold is `|W| >= 1`.

## Dual component reconstruction

Each nonzero primal plaquette is recorded as one dual defect link (called a
*dual-face record* in the report). A face at index `k` separates the adjacent
cells `k-1` and `k`; the integer dual nodes are therefore:

- `xy(x,y,z)` -> `(x,y,z-1)` to `(x,y,z)`;
- `yz(x,y,z)` -> `(x-1,y,z)` to `(x,y,z)`;
- `zx(x,y,z)` -> `(x,y-1,z)` to `(x,y,z)`.

Two records are face-adjacent when their dual links share an endpoint. A primal
face at index `k` separates the adjacent cells `k-1` and `k`, so its dual link
uses the corresponding negative-normal offset. The verifier unions these
records and reports connected components in deterministic orientation/coordinate
order. For every component it reports plaquette length, positive/negative
counts, net winding, a uniform sign (`positive`, `negative`, or `mixed`), a
`closed` flag, and boundary crossings. `closed` is true only when every dual
node has degree two and no endpoint is on the open boundary. A crossing is
counted for a dual-link endpoint at `-1` or `N-1` along that link's normal axis.
This is a detector geometry summary, not a claim that the component is a
physical string.
 
## Amendment 1 - dual-face indexing and curved-loop signs (2026-08-27)

The first implementation self-test exposed a dual-face indexing error: mapping
a face at plane `k` to endpoints `k` and `k+1` breaks the shared-cell identity
between the three plaquette orientations. The implementation now maps each
face from the adjacent cell `k-1` to cell `k`. This is a bookkeeping correction
to the frozen lattice convention; it changes no sampled phase field, `N`, `R`,
amplitude, tolerance, or live verdict rule. No live snapshot was supplied
when this correction was made.

The original ring wording required one raw winding sign. A curved loop uses
plaquettes with different fixed normal orientations, so a single directed
loop can contain both positive and negative scalar plaquette windings. The
ring gate therefore retains the frozen one-component, closed, boundary-free,
circumference criterion and requires both local signs, rather than requiring
an impossible uniform raw sign.

## Synthetic controls (frozen)

All controls use `N = 33`, `A = 1.0`, and deterministic constants. Their `theta`
fields are converted to `EY/EI` before entering the detector, exactly as a live
field would be.

1. **uniform**: `theta = 0.35` at every site.
2. **plane_wave**: `theta = 0.20 + 2*pi*3*x/N`; phase wraps are exercised, but
   the oriented plaquette circulation is zero.
3. **straight_line**: with `x0 = y0 = N//2 - 1`,
   `theta = atan2(y-(y0+0.5), x-(x0+0.5))`, independent of `z`. The expected
   detector result is exactly one sign-consistent `W_xy` plaquette at `(x0,y0,z)`
   for each of the `N` z layers, one connected open component of length `N`,
   and two outer-boundary crossings. No `yz` or `zx` plaquette is expected.
4. **vortex_ring**: with `c = (N-1)/2`, `R = 8.5`,
   `rho = sqrt((x-c)^2 + (y-c)^2)`, and
   `theta = atan2(z-c, rho-R)`. The expected result is one boundary-free,
   closed component. Because each plaquette uses a fixed orientation for its
   own normal axis, a curved loop may contain both positive and negative raw
   winding signs. Its length is compared with the geometric circumference
   `2*pi*R` using the declared discretization tolerance below; component count
   must still be exactly one, so extra components are a failure.
5. **global_rotation**: `theta = 0.35 + 1.23456789` at every site. This is a
   global phase rotation of the uniform control and must have exactly zero
   winding.

The ring's length tolerance is `RING_LENGTH_REL_TOL = 0.65` (the accepted
interval is `[0.35, 1.65] * 2*pi*R`). This tolerance covers lattice placement
and staircase length only. It does not permit spurious components, an open ring,
or boundary crossings. The three null controls must have exactly zero integer
winding in all three plaquette arrays, not merely a small floating circulation.

## Live snapshot input

The optional positional argument is a JSON snapshot path. The top-level JSON
object must contain integer `grid_N > 1` and flat numeric arrays `ey` and `ei`,
each of exactly `grid_N**3` entries. Optional flat numeric arrays `pi` and
`particle_vorticity` are accepted and summarized without phase conversion. They
are parent circulation metrics only; a two-channel `pi` array is allowed as
`2*grid_N**3` values, but it is never treated as a compact phase field. Nonfinite
values, wrong lengths, missing required fields, invalid JSON, or a non-object
snapshot are malformed input and cause a nonzero exit.

With no snapshot argument the report is synthetic-only and the overall verdict is
`INCONCLUSIVE`; absence is not a null result. A valid live snapshot with no
nonzero plaquette has `DOES NOT EMERGE`. A valid live snapshot with at least one
nonzero integer plaquette and detector-consistent components has `SUPPORTS`, but
only for the preregistered detector-level topology criterion: "the sampled
`EY/EI` phase has lattice winding." `CONTRADICTS` is reserved for a future
preregistered positive claim with a falsifiable opposing observation; it is not
assigned to a no-defect snapshot. Any phase-invalid or otherwise unusable live
state is `INCONCLUSIVE`. No verdict in this tree can establish a persistent
compact phase/current or physical strings.

Parent metrics (`pi` and `particle_vorticity`) are reported as presence,
channel/entry count, finite status, mean absolute value, maximum absolute value,
and a frozen activity count above `1e-12`. These numbers are diagnostic-only and
cannot change the detector verdict.

## Decision tree and gates

The executable prints one named `GATE` line per synthetic control, a live-input
gate, and the report-writing gate. A gate is `PASS` only when its frozen
condition is met. The final line `ALL CHECKS PASSED` is printed only after every
synthetic self-test passes and (when supplied) the live snapshot is valid and a
report is written.

1. `GATE SYNTH_UNIFORM`, `SYNTH_PLANE_WAVE`, and `SYNTH_GLOBAL_ROTATION` pass
   only with exactly zero nonzero plaquettes and zero components.
2. `GATE SYNTH_STRAIGHT_LINE` passes only with exactly one component, exactly
   `N` nonzero `W_xy` plaquettes (one per z layer), no other orientation hits,
   one sign, length `N`, and the expected two boundary crossings.
3. `GATE SYNTH_VORTEX_RING` passes only with exactly one component,
   `closed = true`, zero boundary crossings, both positive and negative local
   winding signs, and length in the frozen tolerance interval. Any additional
   component is a failure (not tolerance).
4. A live gate passes when the JSON is valid and its `EY/EI` amplitudes clear
   `AMP_FLOOR`. It is `SKIP` for a synthetic-only run. The live verdict then
   follows the tree above without assuming a compact phase field.
5. `GATE REPORT_WRITTEN` passes only after deterministic JSON is written to
   `_diag/topology_observatory_report.json` by default.

The stopping rule is one deterministic pass over each frozen synthetic control
and, if present, one snapshot. Stop after the report is written; do not tune
`N`, the ring radius, tolerances, phase offsets, or verdict thresholds after
seeing a result. A failed self-test or malformed live input stops with a
nonzero exit and no `ALL CHECKS PASSED` claim.

## Outputs and limitations

`verify_topology_observatory.py` writes a sorted, deterministic JSON report to
`_diag/topology_observatory_report.json` unless an explicit output option is
provided. It records the frozen conventions, thresholds, synthetic metrics,
component summaries, live metrics/verdict, parent diagnostic-only metrics, and
limitations. The report is an observation of the supplied arrays at one sampled
state. It is not a persistent phase/current measurement, a particle-vorticity
identity, a proof of physical strings, or evidence that transient `Pi` values
are a compact state carrier.
