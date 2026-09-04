## CassiLayout — the cross-boundary contract schema (SINGLE SOURCE OF TRUTH).
##
## DATA-ONLY. No logic, no functions — plain consts. Consumed by
## scripts/contracts/assert_layout.gd (the build-time layout assert, run in
## the battery's pre-flight) and referenced from cassi_sim.gd /
## cassi_physics_engine.gd / cassi_tree_worker.gd. Every entry MUST match the
## GLSL layout(...) blocks and the host PackedByteArray allocations exactly —
## assert_layout.gd is the enforcement (the class-killer for the season's
## real bugs: the merge 64-vs-92-B PC mismatch that flooded stderr and broke
## particle_merge; the storage-vs-render periodic-wrap disagreement; liveness
## drift).
##
## Conventions (2026-08-15, verified against the shader sources):
##   - PC sizes are FLOAT COUNTS (scalar float members; every PC below is
##     scalar-only — no vec members).
##   - Periodic-coordinate identity: the N³ field grids are PERIODIC-INDEXED
##     with the `((i % N) + N) % N` wrap (deposit, nbody samplers, instancer,
##     qhist). The Voronoi site wrap uses `mod()` (cassi_voronoi_cells.glsl
##     mode 4 — the M1 unwrap target). The tree arm is OPEN-boundary (never
##     wraps). The render side must use the SAME `% N` wrap as storage — the
##     instancer fold class was exactly a render/storage disagreement.
##   - Liveness convention: the per-particle position buffer is
##     vec4(pos.xyz, mass) and `w <= 0.0` means DEAD — deposit / nbody /
##     merge / BH-accretion / instancer skip it; accretion writes w = 0.0
##     on swallow; merge writes w = 0.0 on coalesce.
##   - The window-origin convention (movable home-window, 3e3f9a6): the
##     field grid's world-origin offset rides bh[0].yzw (floats 4/8/12);
##     the per-axis half-extents ride bh[2].yzw. Zero origin = the legacy
##     fixed-origin box.

## Push-constant float counts per shader (from the GLSL layout blocks).
const PC := {
	"cassi_particle_merge": 26,   # 104 B — the merge cadence/geometry + boxless site-read PC
	"cassi_nbody_gravity": 15,    # 60 B — the nbody selector PC (mode 0-4)
	"cassi_instancer": 32,        # 128 B — AT the RDNA3 Vulkan push-constant cap; nothing more may be added
	"cassi_blend_pos": 5,         # 20 B — alpha@0, packed@4, win@8/12/16
	"cassi_mass_deposit": 9,      # 36 B — N, particle_N, extent_xyz, off_xyz, mode
	"cassi_two_fluid": 17,        # 68 B — the two-fluid PDE PC (grid-space; + ham_completion, U1 toggle)
	"cassi_poisson": 7,           # 28 B — N, axis, dir, mode, extent_xyz
	"cassi_qhist": 15,            # 60 B — histogram + extent_xyz + win_xyz + boxless + n_sites
	"cassi_occupancy": 10,        # 40 B — lim_xyz, ext_xyz, pads
	"cassi_rotation_stress": 24, # 96 B — conservative vector stress and scale reservoirs
	"cassi_rotation_orientation_instancer": 4, # 16 B — renderer-only object axes
	"cassi_presentation_macro_lod": 4, # 16 B — renderer-only site billboards
	"cassi_presentation_trails": 16, # 64 B — renderer-only velocity ribbons
	"cassi_tree_build": 19,       # 76 B — S, bmin_xyz, half, eps2, PHI, PHI_6, leaf/maxlevels, modes 10-13, grid_N, ext_xyz, floor
	"cassi_tree_gravity": 8,      # 32 B — Np, theta, eps2, pad, tnm + Arm 2 q_cent, alpha, coherence_theta
	"cassi_tree_momcon": 3,       # 12 B — N_f, op, pad
	"cassi_coarse_grad": 8,       # 32 B — the coarse-gradient PC
	"cassi_voronoi_cells": 18,    # 72 B — the cell/JFA steering PC (modes 0-12; + J_wind, amendment 3c)
	"cassi_jfa": 8,               # 32 B — N, jump, read_a, n_sites, h_xyz, pad
	"cassi_condensation": 4,      # 16 B — N, threshold, pads
	"cassi_field_render": 11,     # 44 B — the field-render PC
	"cassi_field_learn": 16,      # 64 B — embodied reward/plasticity/control PC
	"cassi_site_shortlist": 3,    # 12 B — n_sites, q_floor, mode (Arm 1 coherence-filtered site shortlist)
	"cassi_site_hash": 9,         # 36 B — ext_xyz, H, shortlist bound, tile origin xyz, mode
	"cassi_voronoi_render_topology": 8, # 32 B — N, site count, mode/read, jump, tile extents
	"cassi_voronoi_render_adjacency": 4, # 16 B — open-label adjacency bitset pass
	"cassi_voronoi_adjacency_csr": 8, # 32 B — site count, words, mode, capacity, generation, pads
	"cassi_voronoi_optical_payload": 8, # 32 B — site count, extents, opacity, pads
	"cassi_voronoi_fused_volume": 32, # 128 B — camera/ray, topology, traversal, reserved controls
	"cassi_workbench_field": 14, # 56 B — bounded align selection
	"cassi_workbench_particle": 14, # 56 B — bounded particle impulse
}


## Host PackedByteArray allocations (float count per var; BLEND is special —
## allocated in BYTES via resize(20), the others via resize(N * 4)).
const HOST_PC_FLOATS := {
	"_merge_pc_bytes": 26,
	"_merge_scan_pc_bytes": 4,
	"_nbody_pc_bytes": 15,
	"_instancer_pc_bytes": 32,
	"_md_pc_bytes": 9,
	"_topology_pc_bytes": 8,
	"_volume_pc_bytes": 32,
	"_volume_resolve_pc_bytes": 32,
	"_shortlist_pc_bytes": 3,
	"_hash_pc_bytes": 9,
	"_topology_optical_pc_bytes": 8,
	"_workbench_field_pc": 14,
	"_topology_adj_pc_bytes": 4,
	"_workbench_particle_pc": 14,
	"_cell_pc_bytes": 18,
	"_jfa_pc_bytes": 8,
	"_raster_pc_bytes": 8,
	"_tree_build_pc_bytes": 19,
	"_tree_grav_pc_bytes": 8,
	"_cond_pc_bytes": 4,
	"_rotation_pc_bytes": 24,
	"_rotation_axis_pc": 4,
	"_macro_lod_pc": 4,
	"_trail_pc": 16,
}
const HOST_PC_BYTES := {
	"_blend_pc": 20,   # 5 floats
}

## The BH header: vec4 bh[36] = 576 B.
##   bh[0].x     = cascade multigrid enable (0.0 = off; legacy callers keep it 0)
##   bh[0].yzw   = the field-grid world-origin offset (window center; floats 4/8/12)
##   bh[1].xyz   = the dual-grid offset h_i/2 = extent_i/N (floats 16/20/24)
##   bh[1].w     = G_N (float 28)
##   bh[2].x     = cluster radius (the Plummer softening scale)
##   bh[2].yzw   = per-axis box half-extents (floats 36/40/44)
##   bh[3].xyzw  = black_holes_enabled, dual_grid, gradient_order, tree G_SCALE
##   bh[4..]     = BH records (vec4[pos.xyz, mass] + vec4[vel.xyz, age]; max 15)
const BH_HEADER_VEC4S := 36
const BH_WINDOW_ORIGIN_FLOAT := 4   # bh[0].y
const BH_EXTENT_FLOAT := 36         # bh[2].y

## Binding maps per shader: set -> [binding, ...]. From the GLSL
## `layout(set = S, binding = B, ...)` declarations.
const BINDINGS := {
	"cassi_particle_merge": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]},
	"cassi_nbody_gravity": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 1: [0, 1, 2, 3], 2: [0, 1]},
	"cassi_instancer": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]},
	"cassi_blend_pos": {0: [0, 1, 2]},
	"cassi_mass_deposit": {0: [0, 1, 2]},
	"cassi_two_fluid": {0: [0, 1, 2, 3, 4, 5, 6, 7]},
	"cassi_poisson": {0: [0, 1, 2, 3]},
	"cassi_qhist": {0: [0, 1, 2, 3, 4, 5, 6, 7]},
	"cassi_occupancy": {0: [0, 1, 2]},
	"cassi_rotation_stress": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]},
	"cassi_rotation_orientation_instancer": {0: [0, 1, 2]},
	"cassi_presentation_macro_lod": {0: [0, 1, 2]},
	"cassi_presentation_trails": {0: [0, 1, 2]},
	"cassi_tree_build": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]},
	"cassi_tree_gravity": {0: [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14]},
	"cassi_tree_momcon": {0: [0, 1, 2, 3]},
	"cassi_coarse_grad": {0: [0, 1, 2, 3]},
	"cassi_voronoi_cells": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]},
	"cassi_jfa": {0: [0, 1, 2]},
	"cassi_condensation": {0: [0], 1: [0]},
	"cassi_field_render": {0: [0, 1, 2, 3, 4, 5], 2: [0]},
	"cassi_field_learn": {0: [0, 1, 2]},
	"cassi_voronoi_render_topology": {0: [0, 1, 2, 3]},
	"cassi_voronoi_render_adjacency": {0: [0, 1]},
	"cassi_voronoi_adjacency_csr": {0: [0, 1, 2, 3, 4]},
	"cassi_voronoi_optical_payload": {0: [0, 1, 2, 3, 4, 5]},
	"cassi_voronoi_fused_volume": {0: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]},
	"cassi_workbench_field": {0: [0, 1, 2]},
	"cassi_workbench_particle": {0: [0, 1]},
	"cassi_site_shortlist": {0: [0, 1, 2, 3, 4]},
	"cassi_site_hash": {0: [0, 1, 2, 3, 4]},
}

## The covered shader set (name -> GLSL file), all of which must carry the
## "canonical layout: scripts/contracts/layout.gd §" header line.
const COVERED := [
	"cassi_particle_merge", "cassi_nbody_gravity", "cassi_instancer",
	"cassi_blend_pos", "cassi_mass_deposit", "cassi_two_fluid",
	"cassi_poisson", "cassi_qhist", "cassi_occupancy", "cassi_tree_build",
	"cassi_tree_gravity", "cassi_tree_momcon", "cassi_coarse_grad", "cassi_voronoi_cells",
	"cassi_jfa", "cassi_condensation", "cassi_field_render", "cassi_site_shortlist",
	"cassi_site_hash", "cassi_voronoi_render_topology", "cassi_voronoi_render_adjacency",
	"cassi_voronoi_adjacency_csr",
	"cassi_rotation_stress", "cassi_rotation_orientation_instancer",
	"cassi_presentation_macro_lod", "cassi_presentation_trails",
	"cassi_voronoi_optical_payload", "cassi_voronoi_fused_volume",
	"cassi_workbench_field", "cassi_workbench_particle", "cassi_field_learn",
]
