extends Node
## FMM/tree gravity GPU verify (Stage 5, wave 2) — open-boundary octree
## build + walk vs the numpy prototype (research/meshless/stage5_fmm.py).
##
## Self-contained: creates its OWN local RenderingDevice (display-
## independent) and runs the full tree pipeline on the identical 8192-point
## config the prototype's G13 uses (uniform box + one Plummer cluster, seed
## 20260813 — the SAME seed):
##   1. generate 8192 sources (pos, mass=1, EY, EI synthetic field) on CPU
##   2. compute/cassi_tree_build.glsl: prepare (Morton key + chord weight
##      w = m·g from EY/EI) → bitonic sort (91 stages) → level-by-level
##      octree split (host loop ≤ MAX_LEVELS) → moments (W, COM, quadrupole)
##   3. compute/cassi_tree_gravity.glsl: one-thread-per-target walk with
##      quadrupole, θ=0.5, both hardening rules, self-exclusion
##   4. dump to res://_diag/fmm_gpu.json (positions, masses, EY, EI, theta,
##      eps2, node_count, forces, interaction counts) — the numpy verifier
##      research/meshless/stage5_verify.py computes the gates:
##        G16 GPU tree force vs prototype tree force (identical points):
##            median relative diff ≤ 5e-3
##        G17 GPU tree vs the DIRECT O(N²) sum: median ≤ 1e-2
##        G18 self-exclusion spot-check: own-source contribution absent
##
## Local checks here are structural (pipelines build, no NaN, forces bounded,
## interactions > 0); the physics gates live in stage5_verify.py.
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_fmm.tscn

const N := 8192
const L := 6.0
const PHI := 1.618033988749895
const PHI6 := 17.94427190999916
const PHI_INV2 := 0.381966011250105
const THETA := 0.5
const EPS2 := 1e-6
const LEAF_CAP := 1
const MAX_LEVELS := 14
const NODE_MAX := 8 * N + 64

var _rd: RenderingDevice
var _tree_us: RID
var _tree_us_g: RID
var _build_shader: RID
var _grav_shader: RID
var _build_pipe: RID
var _grav_pipe: RID

var _src_table: RID
var _src_w: RID
var _src_key: RID
var _src_order: RID
var _node_cf: RID
var _node_w: RID
var _node_q: RID
var _node_r: RID
var _node_qq: RID  # Arm 2: per-node mean q (nodeQq binding 14)
var _ctr: RID
var _force_out: RID
var _inter: RID
var _tp_dummy: RID

var _build_pc := PackedFloat32Array()
var _grav_pc := PackedFloat32Array()
var _checks := 0
var _failures := 0
var _t0_ms := 0


func _ready() -> void:
	_t0_ms = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false,
			"headless/dummy renderer? fall back to windowed run")
		_finish()
		return
	_check("local RenderingDevice acquired", true)
	if not _load_pipelines():
		_finish()
		return
	_make_buffers()

	# deterministic source config (seed 20260813, uniform + Plummer cluster)
	var src := _make_sources()
	var box := _box(src)          # {min: Vector3, half: float}
	_init_root(src, box)

	_build_tree(box)
	var node_count := _node_count()
	_check("tree build: node_count in (1, NODE_MAX)", node_count > 1 and node_count < NODE_MAX,
		"nodes=%d" % node_count)

	_walk(node_count)
	var forces := _force_readback()
	var inter := _inter_readback()
	_check_walk(forces, inter)

	_dump_json(src, box, node_count, forces, inter)
	_finish()


# ── shaders / buffers / uniform set ────────────────────────────────────
func _load_pipelines() -> bool:
	var bsf := load("res://compute/cassi_tree_build.glsl") as RDShaderFile
	var gsf := load("res://compute/cassi_tree_gravity.glsl") as RDShaderFile
	if bsf == null or gsf == null:
		_check("shaders load", false)
		return false
	_build_shader = _rd.shader_create_from_spirv(bsf.get_spirv())
	_grav_shader = _rd.shader_create_from_spirv(gsf.get_spirv())
	_build_pipe = _rd.compute_pipeline_create(_build_shader)
	_grav_pipe = _rd.compute_pipeline_create(_grav_shader)
	var ok: bool = _build_pipe.is_valid() and _grav_pipe.is_valid()
	_check("compute pipelines build", ok)
	return ok


func _make_buffers() -> void:
	_src_table = _rd.storage_buffer_create(2 * N * 16)
	_src_w = _rd.storage_buffer_create(N * 4)
	_src_key = _rd.storage_buffer_create(N * 4)
	_src_order = _rd.storage_buffer_create(N * 4)
	_node_cf = _rd.storage_buffer_create(NODE_MAX * 16)
	_node_w = _rd.storage_buffer_create(NODE_MAX * 16)
	_node_q = _rd.storage_buffer_create(2 * NODE_MAX * 16)
	_node_r = _rd.storage_buffer_create(NODE_MAX * 16)
	_node_qq = _rd.storage_buffer_create(NODE_MAX * 4)  # Arm 2: per-node mean q
	_ctr = _rd.storage_buffer_create(8 * 4)
	_force_out = _rd.storage_buffer_create(N * 16)
	_inter = _rd.storage_buffer_create(N * 4)
	# binding 11 (TargetPos, use_tp OFF here): the walk declares it but the
	# verify targets ARE the sources — bind a tiny dummy so the pipeline's
	# required set is complete.
	var _g5 := _rd.storage_buffer_create(4)  # dummy meshless gather sources (9-13)
	var _g6 := _rd.storage_buffer_create(4)
	var _g7 := _rd.storage_buffer_create(4)
	var _g8 := _rd.storage_buffer_create(4)
	var _g9 := _rd.storage_buffer_create(4)
	_tp_dummy = _g5
	_tree_us = _rd.uniform_set_create([
		_u_storage(0, _src_table), _u_storage(1, _src_w),
		_u_storage(2, _src_key), _u_storage(3, _src_order),
		_u_storage(4, _node_cf), _u_storage(5, _node_w),
		_u_storage(6, _node_q), _u_storage(7, _node_r),
		_u_storage(8, _ctr),
		_u_storage(9, _g5), _u_storage(10, _g6),
		_u_storage(11, _g7), _u_storage(12, _g8), _u_storage(13, _g9),
		_u_storage(14, _node_qq),
	], _build_shader, 0)
	# The gravity shader reads subsets of the same buffers; it uses binding
	# 0/3/4/5/6/7/8 + 9/10/11.
	_tree_us_g = _rd.uniform_set_create([
		_u_storage(0, _src_table), _u_storage(3, _src_order),
		_u_storage(4, _node_cf), _u_storage(5, _node_w),
		_u_storage(6, _node_q), _u_storage(7, _node_r),
		_u_storage(8, _ctr), _u_storage(9, _force_out),
		_u_storage(10, _inter), _u_storage(11, _tp_dummy),
		_u_storage(14, _node_qq),
	], _grav_shader, 0)
	# build PC (19 floats) + gravity PC (8 floats: 0-4 θ/eps/etc + Arm 2 q_cent/α/toggle)
	_build_pc.resize(19)
	_grav_pc.resize(8)
	_grav_pc[5] = 0.0; _grav_pc[6] = 0.0; _grav_pc[7] = 0.0  # Arm 2 OFF in verify


func _u_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# ── deterministic 8192-source config (seed 20260813) ────────────────────
# uniform box [0,6]³ (4096) + Plummer cluster at (3,3,3), a0=0.6 (4096);
# masses all 1.0; EY/EI from the prototype G13 synthetic field. The numpy
# verifier reads these EXACT values from the JSON dump, so no cross-language
# RNG matching is needed — only this seed is used to regenerate the same
# config if re-run.
func _make_sources() -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var src := PackedFloat32Array()
	src.resize(2 * N * 4)
	var a0 := 0.6
	var c := Vector3(3.0, 3.0, 3.0)
	for i in range(N):
		var p: Vector3
		if i < 4096:
			p = Vector3(rng.randf() * L, rng.randf() * L, rng.randf() * L)
		else:
			var u: float = rng.randf()
			var r: float = a0 * pow(u, 1.0 / 3.0) / sqrt(max(1.0 - pow(u, 2.0 / 3.0), 1e-12))
			var dir := _gauss3(rng)
			p = c + r * dir.normalized()
		# clamp into the box (the open field: nothing wraps)
		p = Vector3(clampf(p.x, 0.0, L), clampf(p.y, 0.0, L), clampf(p.z, 0.0, L))
		var base := i * 8
		src[base + 0] = p.x
		src[base + 1] = p.y
		src[base + 2] = p.z
		src[base + 3] = 1.0                       # mass
		src[base + 4] = 1.0 + 0.3 * sin(2.0 * p.x) * cos(2.0 * p.y)   # EY
		src[base + 5] = 0.6 + 0.2 * cos(2.0 * p.z)                   # EI
		src[base + 6] = 0.0
		src[base + 7] = 0.0
	return src


func _gauss3(rng: RandomNumberGenerator) -> Vector3:
	# three independent standard gaussians via Box–Muller (1.5 pairs from 3
	# uniforms) — an isotropic 3D direction, not confined to a plane
	var u1: float = max(rng.randf(), 1e-9)
	var u2: float = rng.randf() * TAU
	var r1: float = sqrt(-2.0 * log(u1))
	var gx: float = r1 * cos(u2)
	var gy: float = r1 * sin(u2)
	var u3: float = max(rng.randf(), 1e-9)
	var u4: float = rng.randf() * TAU
	var r2: float = sqrt(-2.0 * log(u3))
	var gz: float = r2 * cos(u4)
	return Vector3(gx, gy, gz)


func _box(src: PackedFloat32Array) -> Dictionary:
	var lo := Vector3(INF, INF, INF)
	var hi := Vector3(-INF, -INF, -INF)
	for i in range(N):
		var b := i * 8
		var p := Vector3(src[b], src[b + 1], src[b + 2])
		lo = lo.min(p)
		hi = hi.max(p)
	var half := 0.5 * maxf(hi.x - lo.x, maxf(hi.y - lo.y, hi.z - lo.z))
	half = half * (1.0 + 1e-6) + 1e-9   # strict containment
	return {"min": (lo + hi) * 0.5 - Vector3(half, half, half), "half": half}


func _init_root(src: PackedFloat32Array, box: Dictionary) -> void:
	# source table upload (pos,m,EY,EI), root node 0, counters
	_rd.buffer_update(_src_table, 0, src.size() * 4, src.to_byte_array())
	_src_cache = src
	var mn: Vector3 = box["min"]
	var half: float = box["half"]
	var cc := mn + Vector3(half, half, half)
	var cf := PackedFloat32Array([cc.x, cc.y, cc.z, half]).to_byte_array()
	_rd.buffer_update(_node_cf, 0, 16, cf)
	var nr := PackedInt32Array([0, N, -1, 0]).to_byte_array()
	_rd.buffer_update(_node_r, 0, 16, nr)
	# counters: [0]=node_cnt=1 (root), [1]=split front=0, [2]=level_end=1
	# (the atomic-front/frontier split model — cassi_tree_build.glsl mode 5/8)
	var c := PackedInt32Array([1, 0, 1, 0, 0, 0, 0, 0]).to_byte_array()
	_rd.buffer_update(_ctr, 0, 32, c)


var _src_cache := PackedFloat32Array()


# ── build: prepare → bitonic sort → level loop → moments ────────────────
func _build_tree(box: Dictionary) -> void:
	var mn: Vector3 = box["min"]
	var half: float = box["half"]
	_build_fill_common(mn, half)
	# prepare (mode 0): Morton keys + chord weights
	_build_pc[10] = 0.0
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _build_pipe)
	_rd.compute_list_bind_uniform_set(cl, _tree_us, 0)
	_rd.compute_list_set_push_constant(cl, _build_pc.to_byte_array(), _build_pc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(N) / 64.0)), 1, 1)
	_rd.compute_list_add_barrier(cl)
	# bitonic sort: 91 stages, one list with barriers between
	var stages := _bitonic_stages()
	for st in stages:
		_build_pc[10] = 1.0
		_build_pc[11] = float(st[0])   # k
		_build_pc[12] = float(st[1])   # j
		_build_pc[13] = 1.0
		_rd.compute_list_set_push_constant(cl, _build_pc.to_byte_array(), _build_pc.size() * 4)
		_rd.compute_list_dispatch(cl, int(ceil(float(N) / 64.0)), 1, 1)
		_rd.compute_list_add_barrier(cl)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()

	# level-by-level split — SELF-CONTAINED rounds (no host readback):
	# mode 5 (atomic front, capped by ctr[2]=level_end) → barrier → mode 8
	# (commit: ctr[2]=ctr[0]) → barrier, MAX_LEVELS times, all in ONE list.
	_build_pc[10] = 5.0   # round 0 splits the root; later rounds the frontier
	var scl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(scl, _build_pipe)
	_rd.compute_list_bind_uniform_set(scl, _tree_us, 0)
	for _depth in range(MAX_LEVELS):
		_build_pc[10] = 5.0
		_rd.compute_list_set_push_constant(scl, _build_pc.to_byte_array(), _build_pc.size() * 4)
		_rd.compute_list_dispatch(scl, int(ceil(float(NODE_MAX) / 64.0)), 1, 1)
		_rd.compute_list_add_barrier(scl)
		_build_pc[10] = 8.0
		_rd.compute_list_set_push_constant(scl, _build_pc.to_byte_array(), _build_pc.size() * 4)
		_rd.compute_list_dispatch(scl, 1, 1, 1)
		_rd.compute_list_add_barrier(scl)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()

	# moments (mode 6): W / COM / quadrupole for every node
	_build_pc[10] = 6.0
	var ncount := int(_read_uint(_ctr, 0))
	var mcl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(mcl, _build_pipe)
	_rd.compute_list_bind_uniform_set(mcl, _tree_us, 0)
	_rd.compute_list_set_push_constant(mcl, _build_pc.to_byte_array(), _build_pc.size() * 4)
	_rd.compute_list_dispatch(mcl, int(ceil(float(ncount) / 64.0)), 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _build_fill_common(mn: Vector3, half: float) -> void:
	_build_pc[0] = float(N)
	_build_pc[1] = mn.x
	_build_pc[2] = mn.y
	_build_pc[3] = mn.z
	_build_pc[4] = half
	_build_pc[5] = EPS2
	_build_pc[6] = PHI
	_build_pc[7] = PHI6
	_build_pc[8] = float(LEAF_CAP)
	_build_pc[9] = float(MAX_LEVELS)
	_build_pc[13] = 0.0


func _bitonic_stages() -> Array:
	# bitonic sort stages for N = 2^13 = 8192: (k, j) pairs, 91 of them.
	# Integer ops (shifts) — GDScript `/` on ints can yield float.
	var out := []
	var k := 2
	while k <= N:
		var j := k >> 1
		while j >= 1:
			out.append([k, j])
			j = j >> 1
		k = k << 1
	return out


# ── walk: one thread per target, per-thread stack ───────────────────────
func _walk(node_count: int) -> void:
	_grav_pc[0] = float(N)
	_grav_pc[1] = THETA
	_grav_pc[2] = EPS2
	_grav_pc[3] = 0.0   # use_tp OFF — verify targets ARE the sources (src[2i])
	_grav_pc[4] = float(node_count)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _grav_pipe)
	_rd.compute_list_bind_uniform_set(cl, _tree_us_g, 0)
	_rd.compute_list_set_push_constant(cl, _grav_pc.to_byte_array(), _grav_pc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(N) / 64.0)), 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _force_readback() -> PackedFloat32Array:
	var b := _rd.buffer_get_data(_force_out, 0, N * 16)
	return b.to_float32_array()


func _inter_readback() -> PackedInt32Array:
	var b := _rd.buffer_get_data(_inter, 0, N * 4)
	return b.to_int32_array()


func _read_uint(buf: RID, off: int) -> int:
	var b := _rd.buffer_get_data(buf, off, 4)
	return b.decode_s32(0) if b.size() >= 4 else 0


func _node_count() -> int:
	return _read_uint(_ctr, 0)


# ── structural checks ───────────────────────────────────────────────────
func _check_walk(forces: PackedFloat32Array, inter: PackedInt32Array) -> void:
	var nan := false
	var max_mag := 0.0
	var sum_mag := 0.0
	var min_inter := 1 << 30
	for i in range(N):
		var fx := forces[i * 4]
		var fy := forces[i * 4 + 1]
		var fz := forces[i * 4 + 2]
		if is_nan(fx) or is_inf(fx) or is_nan(fy) or is_inf(fy) or is_nan(fz) or is_inf(fz):
			nan = true
		var m := sqrt(fx * fx + fy * fy + fz * fz)
		max_mag = max(max_mag, m)
		sum_mag += m
		min_inter = min(min_inter, inter[i])
	_check("walk: no NaN/Inf in forces", not nan)
	_check("walk: forces finite (max |a|=%.3f)" % max_mag, max_mag < 1e6)
	_check("walk: every target had >= 1 interaction", min_inter > 0, "min=%d" % min_inter)


# ── JSON dump for the numpy verifier ────────────────────────────────────
func _dump_json(src: PackedFloat32Array, box: Dictionary, node_count: int,
		forces: PackedFloat32Array, inter: PackedInt32Array) -> void:
	var mn: Vector3 = box["min"]
	var d := {
		"N": N, "L": L,
		"theta": THETA, "eps2": EPS2, "leaf_cap": LEAF_CAP, "max_levels": MAX_LEVELS,
		"phi": PHI, "phi6": PHI6,
		"box_min": [mn.x, mn.y, mn.z], "box_half": box["half"],
		"node_count": node_count, "node_max": NODE_MAX,
		"src_b64": Marshalls.raw_to_base64(src.to_byte_array()),
		"forces_b64": Marshalls.raw_to_base64(forces.to_byte_array()),
		"inter_b64": Marshalls.raw_to_base64(inter.to_byte_array()),
	}
	var f := FileAccess.open("res://_diag/fmm_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump written to res://_diag/fmm_gpu.json", false,
			"FileAccess failed")
		return
	f.store_string(JSON.stringify(d))
	f.close()
	_check("JSON dump written to res://_diag/fmm_gpu.json", true)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0_ms
	print("[VerifyFMM] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyFMM] RESULT: PASS — dump for stage5_verify.py")
	else:
		print("[VerifyFMM] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
