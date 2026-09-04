extends RefCounted
class_name CassiMergeCommon
## Shared merge helpers for the two Cassi particle-merge drivers
## (cassi_sim.gd — global-RD inline port; cassi_physics_engine.gd — local-RD
## engine worker). These were byte-identical duplicates in both files and
## drifted once (the per-cycle cc-zero, F1); centralising them so the two
## twins cannot diverge again.
##
## Shared surfaces:
##   next_pair_phase(phase, count) — large-cloud cursor over every possible
##     cell entry, paired with pair_phase_pc().
##   merge_batch_result(counts, first, count) — summed count + final slot for
##     a submitted batch, including batches after the first four cycles.
##   hash_geometry(extents, r_m)   — bounded anisotropic spatial-hash sizing.
##   merge_pc_values(dict)         — the 26-float merge push constant (the
##     shader PC block ends at n_sites@25 — 104 B).
##
## pass_mode@15 and cyc_slot@23 are left as 0.0 here; each caller fills them
## per dispatch (they vary every dispatch).

## Large-N pass_best visits one bounded source shard and one neighbor-cell
## entry per cadence. The host keeps a 64-bit linear cursor, but sends its
## (source shard, cell) lane in pass_mode's fractional bits and its entry
## round in cyc_slot. Since a cell cannot contain more than N particles, this
## exhausts the actual occupancy for every cloud supported by the shader's
## existing float N/index ABI (N < 2^24), rather than imposing the old
## 64-entry cap. Five hundred twelve source shards bound site-coherence and
## contended hop work to ceil(N/512) active sources per pass while every
## particle still receives or forwards only under the same sink invariant.
const FULL_PAIR_SCAN_PARTICLE_LIMIT := 64
const PAIR_NEIGHBOR_CELLS := 27
const PAIR_SOURCE_SHARDS := 512
const PAIR_PHASE_LANES := PAIR_NEIGHBOR_CELLS * PAIR_SOURCE_SHARDS
const PAIR_LANE_DENOMINATOR := 16384.0
const FLOAT_EXACT_INDEX_LIMIT := 1 << 24


static func next_pair_phase(phase: int, particle_count: int) -> int:
	var phase_count: int = PAIR_PHASE_LANES * maxi(particle_count, 1)
	return (phase + 1) % phase_count


static func pair_phase_pc(phase: int) -> Vector2:
	var lane := phase % PAIR_PHASE_LANES
	var entry_round := phase / PAIR_PHASE_LANES
	return Vector2(4.0 + float(lane) / PAIR_LANE_DENOMINATOR, float(entry_round))

## Return (sum, final-slot count) for one submitted merge-cycle batch.
## Keeping the offset in this shared helper prevents the two drivers from
## accidentally rereading slots 0..count after the first batch.
static func merge_batch_result(
		counts: PackedInt32Array, first: int, count: int) -> Vector2i:
	var merged := 0
	var end := first + count
	for slot in range(first, end):
		merged += counts[slot]
	return Vector2i(merged, counts[end - 1])


## Merge spatial-hash geometry from the box half-extents and merge radius
## R_m (= ½·h₀). Raw per-axis dimensions make cell widths >= R_m, which is
## the exact 27-neighbor coverage condition. An anisotropic box used to
## multiply the dense count/scan allocation by its aspect volume (8.88 M
## cells at the default φ:1:φ² box). Uniformly coarsen those dimensions to
## at most the shortest-axis cube: this keeps physical hash cells isotropic,
## preserves cell_w >= R_m and periodic 27-neighbor coverage, and bounds the
## dense scan independently of box aspect. Large-N pass_best time-slices the
## full cell occupancy, so coarser cells do not introduce a 64-entry omission.
## Cubic boxes are unchanged, including the existing verifier geometry.
## Returns { nx, ny, nz, total, cell_wx, cell_wy, cell_wz }.
static func hash_geometry(extents: Vector3, r_m: float) -> Dictionary:
	var nx := maxi(int(floor(2.0 * extents.x / r_m)), 8)
	var ny := maxi(int(floor(2.0 * extents.y / r_m)), 8)
	var nz := maxi(int(floor(2.0 * extents.z / r_m)), 8)
	var raw_total: int = nx * ny * nz
	var shortest_n := mini(nx, mini(ny, nz))
	var target_total: int = shortest_n * shortest_n * shortest_n
	if raw_total > target_total:
		var scale := pow(float(raw_total) / float(target_total), 1.0 / 3.0)
		nx = maxi(int(floor(float(nx) / scale)), 8)
		ny = maxi(int(floor(float(ny) / scale)), 8)
		nz = maxi(int(floor(float(nz) / scale)), 8)
	var total: int = nx * ny * nz
	return {
		"nx": nx, "ny": ny, "nz": nz, "total": total,
		"cell_wx": 2.0 * extents.x / float(nx),
		"cell_wy": 2.0 * extents.y / float(ny),
		"cell_wz": 2.0 * extents.z / float(nz),
	}


## The merge push constant as 26 floats, mirroring compute/cassi_particle_merge.glsl
## PC block: indices
##   0 N, 1 phi, 2 phi_inv2, 3 q_threshold(=phi_inv2), 4 R_m,
##   5..7 extent.xyz, 8 grid_N, 9..11 hash_nxyz, 12..14 cell_w.xyz,
##   15 pass_mode (0 here; caller fills), 16 g_n, 17 xi, 18 h0(=2·R_m), 19 dt,
##   20 f_subsonic, 21 f_virial, 22 f_order, 23 cyc_slot (0 here; caller fills),
##   24 boxless (0 = grid trilinear; 1 = site-direct, merge_boxless_prereg.md),
##   25 n_sites (Voronoi site count for the nearest-site boxless read).
##
## `d` keys: n_particles(float), phi, phi_inv2, r_m, extent(Vector3),
## grid_n(float), hash_nx, hash_ny, hash_nz (ints), cell_wx, cell_wy, cell_wz
## (floats), g_n, xi, dt (floats), subsonic, virial, order (bools),
## boxless (bool), n_sites (int).
static func merge_pc_values(d: Dictionary) -> PackedFloat32Array:
	var e: Vector3 = d.get("extent", Vector3.ZERO)
	var f := PackedFloat32Array()
	f.resize(26)   # 26 floats = 104 B — the shader PC block (n_sites@25)
	f[0] = float(d.get("n_particles", 0.0))
	f[1] = float(d.get("phi", 0.0))
	f[2] = float(d.get("phi_inv2", 0.0))
	f[3] = float(d.get("phi_inv2", 0.0))     # q_threshold = φ⁻²
	f[4] = float(d.get("r_m", 0.0))          # R_m = ½·h₀
	f[5] = e.x                               # extent_x
	f[6] = e.y                               # extent_y
	f[7] = e.z                               # extent_z
	f[8] = float(d.get("grid_n", 0.0))
	f[9] = float(d.get("hash_nx", 1))
	f[10] = float(d.get("hash_ny", 1))
	f[11] = float(d.get("hash_nz", 1))
	f[12] = float(d.get("cell_wx", 0.0))
	f[13] = float(d.get("cell_wy", 0.0))
	f[14] = float(d.get("cell_wz", 0.0))
	f[15] = 0.0                              # pass_mode — set per dispatch
	f[16] = float(d.get("g_n", 0.0))
	f[17] = float(d.get("xi", 0.0))
	f[18] = 2.0 * float(d.get("r_m", 0.0))   # h₀ = 2·R_m
	f[19] = float(d.get("dt", 0.0))
	f[20] = 1.0 if d.get("subsonic", false) else 0.0
	f[21] = 1.0 if d.get("virial", false) else 0.0
	f[22] = 1.0 if d.get("order", false) else 0.0
	f[23] = 0.0                              # cyc_slot — set per dispatch
	f[24] = 1.0 if d.get("boxless", false) else 0.0
	f[25] = float(d.get("n_sites", 0))
	return f
