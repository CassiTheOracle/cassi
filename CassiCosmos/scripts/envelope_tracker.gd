class_name EnvelopeTracker
## Tracking-envelope computation for the B-build coarse grid (overhaul
## build plan, M3): the AMR tile's extent re-fits to the structure's
## envelope on the slow cadence instead of the fixed box.
##
## Pure logic — no RenderingDevice, no sim references. Deterministic:
## identical inputs (the same sample array + the same internal state)
## produce bit-identical outputs, so a probe-gated re-tile cadence stays
## reproducible (the plan's determinism canary: max-diff == 0.0).
##
## The rules mirror the movable home-window discipline (3e3f9a6):
##   - a soft move cap on the center (<= 25% of the min extent per
##     re-fit — the grid never jerks);
##   - an ASPECT-PRESERVING extent with grow/shrink hysteresis (the tile
##     re-fits only when the structure's envelope demands it — it does not
##     breathe on noise), so the extent stays expressible as a single
##     uniform scale of the fixed box (the box_scale path);
##   - a PERCENTILE envelope (0.5%..99.5% per axis) — robust to
##     stragglers: one outlier cannot blow the tile;
##   - the coverage demand is computed around the CURRENT center before
##     the move, so the tile covers the structure at every re-fit (the
##     move toward the envelope mid only improves the coverage).
extends RefCounted

const PCT_LO := 0.005
const PCT_HI := 0.995
const PAD := 1.05          # the tile = the structure envelope x 1.05
const GROW_THRESH := 1.10  # re-fit when the padded demand > 1.10 x the current tile
const SHRINK_THRESH := 0.70
const MOVE_CAP_FRAC := 0.25

## The tracked tile state: the grid's world origin and per-axis half-extents.
var center := Vector3.ZERO
var extent := Vector3.ONE

## The last coverage demand (max over axes of |env_mid - center| + env_ext,
## times the pad) — the probe's "the tile covers the structure" assertion.
var last_demand := 0.0
var re_fits := 0

## Re-fit the tile from a position sample. `stride` = floats per point
## (3 for xyz, 4 for a vec4 buffer), `step` = the subsample stride (the
## caller may pre-subsample with step=1).
func compute(samples: PackedFloat32Array, stride := 3, step := 1,
		move_cap_frac := MOVE_CAP_FRAC, min_extent := 1.0,
		pct_lo := PCT_LO, pct_hi := PCT_HI, pad := PAD,
		grow_thresh := GROW_THRESH, shrink_thresh := SHRINK_THRESH) -> void:
	var n := samples.size() / maxi(stride, 1)
	if n <= 0:
		return
	var ax := [PackedFloat32Array(), PackedFloat32Array(), PackedFloat32Array()]
	for i in range(0, n, maxi(step, 1)):
		var base := i * stride
		for a in range(3):
			ax[a].append(samples[base + a])
	var env_lo := Vector3(1e30, 1e30, 1e30)
	var env_hi := Vector3(-1e30, -1e30, -1e30)
	for a in range(3):
		env_lo[a] = _percentile(ax[a], pct_lo)
		env_hi[a] = _percentile(ax[a], pct_hi)
	var env_mid := (env_lo + env_hi) * 0.5
	var env_ext := (env_hi - env_lo) * 0.5
	# Coverage demand around the CURRENT center (before the move): the tile
	# must cover the envelope with the pad; the move only improves coverage.
	last_demand = 0.0
	for a in range(3):
		last_demand = maxf(last_demand, absf(env_mid[a] - center[a]) + env_ext[a])
	last_demand *= pad
	var ext_max := 0.0
	for a in range(3):
		ext_max = maxf(ext_max, extent[a])
	var scale := 1.0
	if last_demand > ext_max * grow_thresh:
		scale = last_demand / ext_max
		re_fits += 1
	elif last_demand < ext_max * shrink_thresh:
		scale = maxf(last_demand, min_extent) / ext_max
		re_fits += 1
	if scale != 1.0:
		extent = extent * scale   # aspect-preserving: the box_scale path
	# Soft move cap on the center (the home-window discipline) + a
	# sub-percent dead band: the window does not jitter on the finite-
	# sample percentile noise (a centered structure => no move =>
	# bit-identical to the fixed box in the compatibility regime).
	var cap: float = move_cap_frac * minf(minf(extent.x, extent.y), extent.z)
	var d := env_mid - center
	var dl := d.length()
	if cap > 0.0 and dl > cap:
		d = d.normalized() * cap
	elif dl < cap * 0.02:
		d = Vector3.ZERO
	center += d


## Deterministic percentile: sorts the caller's copy in place.
func _percentile(vals: PackedFloat32Array, p: float) -> float:
	if vals.size() == 0:
		return 0.0
	vals.sort()
	var ix := int(floor(float(vals.size() - 1) * p))
	return vals[ix]
