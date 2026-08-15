extends RefCounted
class_name CassiMergeCommon
## Shared merge helpers for the two Cassi particle-merge drivers
## (cassi_sim.gd — global-RD inline port; cassi_physics_engine.gd — local-RD
## engine worker). These were byte-identical duplicates in both files and
## drifted once (the per-cycle cc-zero, F1); centralising them so the two
## twins cannot diverge again.
##
## Two helpers:
##   hash_geometry(extents, r_m)  — the spatial-hash sizing math (must stay
##     fp-identical to the old _setup_buffers inline code).
##   merge_pc_values(dict)        — the 24-float merge push constant (the
##     shader PC block ends at cyc_slot@23 — 96 B, NOT 23 floats).
##
## pass_mode@15 and cyc_slot@23 are left as 0.0 here; each caller fills them
## per dispatch (they vary every dispatch).


## Merge spatial-hash geometry from the box half-extents and the merge radius
## R_m (= ½·h₀, the shortest-axis cube-equivalent cell). Reproduces the
## `_setup_buffers` formulas EXACTLY (fp-identical): per axis
## nx = max(⌊2·extent_i/R_m⌋, 8), cell_w = 2·extent_i/nx.
## Returns { nx, ny, nz, total, cell_wx, cell_wy, cell_wz }.
static func hash_geometry(extents: Vector3, r_m: float) -> Dictionary:
	var nx := maxi(int(floor(2.0 * extents.x / r_m)), 8)
	var ny := maxi(int(floor(2.0 * extents.y / r_m)), 8)
	var nz := maxi(int(floor(2.0 * extents.z / r_m)), 8)
	var total: int = nx * ny * nz
	return {
		"nx": nx, "ny": ny, "nz": nz, "total": total,
		"cell_wx": 2.0 * extents.x / float(nx),
		"cell_wy": 2.0 * extents.y / float(ny),
		"cell_wz": 2.0 * extents.z / float(nz),
	}


## The merge push constant as 24 floats, mirroring compute/cassi_particle_merge.glsl
## PC block: indices
##   0 N, 1 phi, 2 phi_inv2, 3 q_threshold(=phi_inv2), 4 R_m,
##   5..7 extent.xyz, 8 grid_N, 9..11 hash_nxyz, 12..14 cell_w.xyz,
##   15 pass_mode (0 here; caller fills), 16 g_n, 17 xi, 18 h0(=2·R_m), 19 dt,
##   20 f_subsonic, 21 f_virial, 22 f_order, 23 cyc_slot (0 here; caller fills).
##
## `d` keys: n_particles(float), phi, phi_inv2, r_m, extent(Vector3),
## grid_n(float), hash_nx, hash_ny, hash_nz (ints), cell_wx, cell_wy, cell_wz
## (floats), g_n, xi, dt (floats), subsonic, virial, order (bools).
static func merge_pc_values(d: Dictionary) -> PackedFloat32Array:
	var e: Vector3 = d.get("extent", Vector3.ZERO)
	var f := PackedFloat32Array()
	f.resize(24)   # 24 floats = 96 B — the shader PC block (cyc_slot@23)
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
	return f
