extends Node
## tree_grd_probe.gd — ISOLATION LADDER for the tree-gravity global-RD no-op.
##
## Narrow diagnostic (fresh-eyes, new files only): pin down WHICH ingredient
## stops compute/cassi_tree_build.glsl's dispatch landing on the sim's GLOBAL
## RenderingDevice (RenderingServer.get_rendering_device()), when the local-RD
## verify scenes run the identical shader fine and the sim's OTHER global-RD
## shaders (cassi_voronoi_cells / cassi_jfa / cassi_poisson) do execute.
##
## Ladder rungs (each a fresh dispatch + frame_post_draw + self-stalling
## buffer_get_data readback; every rung prints PASS/FAIL on its sentinel):
##   A. mode 9 ONCE in _ready, single compute_list_begin/end, minimal set
##      (binding 8 = ctr only)  -> does ctr[0] become 1?
##   B. same but NO uniform set bound at all (does Godot require a set?)
##   C. same as A but dispatched from _process after 5 frames
##   D. same as A but with the build shader's FULL set (bindings 0-13)
##   E. same as D but through a dedicated list that ALSO contains one
##      cells-style dispatch (17-float voronoi PC) before mode 9
##   F. CONTROL: cassi_voronoi_cells.glsl mode 7 (reset) in this same probe
##      structure — a known-working shader; if F fails the probe is at fault.
##   G. SUPPLEMENTARY: the sim's EXACT opening — mode 10 ROOT_SEED then
##      mode 9 CTR_RESET, FULL set, ONE list, barrier between (isolates the
##      pass-ORDER as a potential ingredient once D proves mode 9 lands).
##
## The FIRST failing rung isolates the ingredient. See
## research/meshless/tree_grd_probe.md for the writeup.

# ---------------------------------------------------------------------------
# RenderingDevice + probe resources
# ---------------------------------------------------------------------------
var _rd: RenderingDevice

# build shader (cassi_tree_build.glsl): pipeline + the 19-float PC.
var _build_shader: RID
var _build_pipe: RID
var _pc: PackedByteArray

# voronoi control (cassi_voronoi_cells.glsl): pipeline + 17-float PC.
var _vor_shader: RID
var _vor_pipe: RID
var _vor_pc: PackedByteArray

# Minimal build set = only binding 8 (ctr). Full build set = bindings 0-13.
var _us_min: RID
var _us_full: RID
var _us_full_E: RID   # like _us_full but binding 8 = _ctr_E (rung E)
var _us_full_G: RID   # like _us_full but binding 8 = _ctr_G (supp. rung G)
# Full voronoi set used by the control (mode 7 touches 8=vol, 10=cen).
var _us_vor: RID

# Per-rung sentinel buffers (fresh so rungs cannot contaminate each other).
var _ctr_A: RID
var _ctr_B: RID
var _ctr_C: RID
var _ctr_D: RID
var _ctr_E: RID
var _ctr_G: RID
var _vol_F: RID   # voronoi mode-7 resets vol to 0.0 (sentinel: nonzero->0)

# Dummy buffers that flesh out the FULL build set (bindings 0-13) + voronoi set.
var _b_tree: Array[RID] = []   # 14 build buffers, indexed by binding 0..13
var _b_vor: Array[RID] = []    # 16 voronoi buffers, indexed by binding 0..15

# State machine.
var _frame := 0
var _ready_A_pending := false
var _ready_B_pending := false
var _seq_C_started := false
var _results: Array[String] = []
var _quit := false

func _ready() -> void:
	_rd = RenderingServer.get_rendering_device()
	if _rd == null:
		push_error("[TreeGrdProbe] no global RenderingDevice (headless/dummy?)")
		_quit = true
		return
	print("[TreeGrdProbe] global RD acquired: ", _rd != null)
	_setup()
	# ---- Rung A: mode 9 in _ready, minimal set, single list ----
	_ready_A_pending = true
	_dispatch_build_mode9(_ctr_A, _us_min)
	_ready_A_pending = false
	await RenderingServer.frame_post_draw
	_print_verdict("A", "build mode9 in _ready, minimal set", _read_ctr(_ctr_A))
	# ---- Rung B: same but with NO set bound ----
	_ready_B_pending = true
	_dispatch_build_mode9(_ctr_B, RID())
	_ready_B_pending = false
	await RenderingServer.frame_post_draw
	_print_verdict("B", "build mode9 in _ready, NO uniform set", _read_ctr(_ctr_B))

	# Hand off to _process for C-F (C needs to fire after 5 frames).
	_results.append("[TreeGrdProbe] rungs A,B done. Waiting for frame 5 in _process.")

func _process(_delta: float) -> void:
	if _quit:
		return
	_frame += 1
	if _frame == 5 and not _seq_C_started:
		_seq_C_started = true
		_run_sequence_CDEF()

# ---------------------------------------------------------------------------
# Resource setup: shaders, pipelines, uniform sets, sentinel buffers.
# ---------------------------------------------------------------------------
func _setup() -> void:
	# Build shader + 19-float PC.
	_build_shader = _load_shader_rd("res://compute/cassi_tree_build.glsl")
	if _build_shader.is_valid():
		_build_pipe = _rd.compute_pipeline_create(_build_shader)
		print("[TreeGrdProbe] tree-build pipeline valid=", _build_pipe.is_valid())
	_pc = PackedFloat32Array([
		64.0,    # 0  N_f
		0.0, 0.0, 0.0,  # 1-3 bmin.xyz
		1.0,     # 4  bhalf
		1.0e-6,  # 5  eps2
		1.618,   # 6  phi
		17.944,  # 7  xi = phi^6
		1.0,     # 8  leaf_cap
		14.0,    # 9  max_levels
		9.0,     # 10 mode (set per rung)
		0.0, 0.0, 0.0,  # 11-13 b_k/b_j/b_m
		0.0, 0.0, 0.0, 0.0, 0.0,  # 14-18 grid/extents/floor
	]).to_byte_array()

	# Voronoi control shader + 17-float PC (mode 7: vol+cen reset).
	_vor_shader = _load_shader_rd("res://compute/cassi_voronoi_cells.glsl")
	if _vor_shader.is_valid():
		_vor_pipe = _rd.compute_pipeline_create(_vor_shader)
		print("[TreeGrdProbe] voronoi-cell pipeline valid=", _vor_pipe.is_valid())
	_vor_pc = PackedFloat32Array([
		7.0,  # mode (reset vol+cen)
		64.0,  # N_f (grid N)
		64.0,  # n_sites
		0.01, 0.5, 0.5, 0.5,  # dt, hx, hy, hz
		0.25,  # C2
		0.1,   # OM2
		1.618, # PHI
		0.001, # source_strength
		1.0e-3,# rho_floor
		1.0,   # drift_cap
		0.5,   # kappa
		0.1,   # lam
		0.05,  # T_steer
		2.0,   # lloyd_p
	]).to_byte_array()

	# ---- Sentinel buffers (fresh per rung, zeroed except voronoi vol) ----
	_ctr_A = _rd.storage_buffer_create(64 * 4)
	_ctr_B = _rd.storage_buffer_create(64 * 4)
	_ctr_C = _rd.storage_buffer_create(64 * 4)
	_ctr_D = _rd.storage_buffer_create(64 * 4)
	_ctr_E = _rd.storage_buffer_create(64 * 4)
	_ctr_G = _rd.storage_buffer_create(64 * 4)
	# rung F's voronoi vol sentinel starts at 1.0 -> mode 7 must zero it.
	_vol_F = _rd.storage_buffer_create(64 * 4)
	var ones := PackedByteArray()
	ones.resize(64 * 4)
	for i in range(64):
		ones.encode_float(i * 4, 1.0)
	_rd.buffer_update(_vol_F, 0, ones.size(), ones)

	# ---- Full build set: dummy buffers for bindings 0-13 (task sizes) ----
	# 0=64xvec4x2 (2048B) | 1,2,3,8=64x4 | 4=256xvec4 | 5=256xvec4
	# 6=512xvec4 | 7=256xivec4 | 9=64xvec4 | 10,11,12,13=64x4
	var sizes := [2048, 256, 256, 256, 4096, 4096, 8192, 4096, 256,
		1024, 256, 256, 256, 256]
	for s in sizes:
		_b_tree.append(_rd.storage_buffer_create(s))
	_us_min = _rd.uniform_set_create(
		[_us_storage(8, _ctr_A)], _build_shader, 0)
	# Full set: binding 8 is rung-D/E's counters buffer.
	_us_full = _rd.uniform_set_create([
		_us_storage(0, _b_tree[0]), _us_storage(1, _b_tree[1]),
		_us_storage(2, _b_tree[2]), _us_storage(3, _b_tree[3]),
		_us_storage(4, _b_tree[4]), _us_storage(5, _b_tree[5]),
		_us_storage(6, _b_tree[6]), _us_storage(7, _b_tree[7]),
		_us_storage(8, _ctr_D),
		_us_storage(9, _b_tree[8]),
		_us_storage(10, _b_tree[9]), _us_storage(11, _b_tree[10]),
		_us_storage(12, _b_tree[11]), _us_storage(13, _b_tree[12]),
	], _build_shader, 0)
	# Rung E full set: identical but binding 8 -> _ctr_E (separate sentinel).
	_us_full_E = _rd.uniform_set_create([
		_us_storage(0, _b_tree[0]), _us_storage(1, _b_tree[1]),
		_us_storage(2, _b_tree[2]), _us_storage(3, _b_tree[3]),
		_us_storage(4, _b_tree[4]), _us_storage(5, _b_tree[5]),
		_us_storage(6, _b_tree[6]), _us_storage(7, _b_tree[7]),
		_us_storage(8, _ctr_E),
		_us_storage(9, _b_tree[8]),
		_us_storage(10, _b_tree[9]), _us_storage(11, _b_tree[10]),
		_us_storage(12, _b_tree[11]), _us_storage(13, _b_tree[12]),
	], _build_shader, 0)
	# Rung G full set (supp. sim-opening repro): binding 8 -> _ctr_G.
	_us_full_G = _rd.uniform_set_create([
		_us_storage(0, _b_tree[0]), _us_storage(1, _b_tree[1]),
		_us_storage(2, _b_tree[2]), _us_storage(3, _b_tree[3]),
		_us_storage(4, _b_tree[4]), _us_storage(5, _b_tree[5]),
		_us_storage(6, _b_tree[6]), _us_storage(7, _b_tree[7]),
		_us_storage(8, _ctr_G),
		_us_storage(9, _b_tree[8]),
		_us_storage(10, _b_tree[9]), _us_storage(11, _b_tree[10]),
		_us_storage(12, _b_tree[11]), _us_storage(13, _b_tree[12]),
	], _build_shader, 0)

	# ---- Full voronoi set (16 buffers 0-15) ----
	for s in [640, 4096, 256, 256, 256, 256, 256, 256, 0, 4096, 0, 256,
			256, 256, 256, 256]:
		if s == 0:
			_b_vor.append(RID())  # filled below for 8 and 10
		else:
			_b_vor.append(_rd.storage_buffer_create(s))
	_b_vor[8] = _vol_F    # vol (mode-7 sentinel)
	_b_vor[10] = _rd.storage_buffer_create(64 * 16)  # cen
	_us_vor = _rd.uniform_set_create([
		_us_storage(0, _b_vor[0]), _us_storage(1, _b_vor[1]),
		_us_storage(2, _b_vor[2]), _us_storage(3, _b_vor[3]),
		_us_storage(4, _b_vor[4]), _us_storage(5, _b_vor[5]),
		_us_storage(6, _b_vor[6]), _us_storage(7, _b_vor[7]),
		_us_storage(8, _b_vor[8]), _us_storage(9, _b_vor[9]),
		_us_storage(10, _b_vor[10]), _us_storage(11, _b_vor[11]),
		_us_storage(12, _b_vor[12]), _us_storage(13, _b_vor[13]),
		_us_storage(14, _b_vor[14]), _us_storage(15, _b_vor[15]),
	], _vor_shader, 0)
	print("[TreeGrdProbe] sets: min=", _us_min.is_valid(),
		" full=", _us_full.is_valid(), " vor=", _us_vor.is_valid())

# ---------------------------------------------------------------------------
# Dispatchers.
# ---------------------------------------------------------------------------
func _load_shader_rd(path: String) -> RID:
	if not ResourceLoader.exists(path):
		push_error("[TreeGrdProbe] missing shader " + path)
		return RID()
	var sf: RDShaderFile = load(path)
	if sf == null:
		push_error("[TreeGrdProbe] load failed " + path)
		return RID()
	var spirv = sf.get_spirv()
	if spirv == null:
		push_error("[TreeGrdProbe] SPIR-V fail " + path)
		return RID()
	return _rd.shader_create_from_spirv(spirv)

func _us_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u

func _pc_mode(mode: float) -> PackedByteArray:
	var p := _pc.duplicate()
	p.encode_float(10 * 4, mode)
	return p

# Record ONE build-pipeline dispatch (mode 9) inside a single list.
# `set_rid` may be RID() (rung B: no set bound).
func _dispatch_build_mode9(ctr_buf: RID, set_rid: RID) -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _build_pipe)
	if set_rid.is_valid():
		_rd.compute_list_bind_uniform_set(cl, set_rid, 0)
	_rd.compute_list_set_push_constant(cl, _pc_mode(9.0), _pc.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_end()

# ---------------------------------------------------------------------------
# Rungs C-F (dispatched from _process state machine).
# ---------------------------------------------------------------------------
func _run_sequence_CDEF() -> void:
	# Rung C: same as A but from _process (minimal set).
	_dispatch_build_mode9(_ctr_C, _us_min)
	await RenderingServer.frame_post_draw
	_print_verdict("C", "build mode9 from _process(frame5), minimal set",
		_read_ctr(_ctr_C))

	# Rung D: full build set (bindings 0-13) bound, still mode 9 only.
	_dispatch_build_mode9(_ctr_D, _us_full)
	await RenderingServer.frame_post_draw
	_print_verdict("D", "build mode9, FULL build set (0-13)",
		_read_ctr(_ctr_D))

	# Rung E: dedicated list that ALSO runs one cells-style (voronoi mode 7)
	# dispatch BEFORE the build mode 9 — same-list coexistence test.
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _vor_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_vor, 0)
	_rd.compute_list_set_push_constant(cl, _vor_pc, _vor_pc.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _build_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_full_E, 0)
	_rd.compute_list_set_push_constant(cl, _pc_mode(9.0), _pc.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_end()
	await RenderingServer.frame_post_draw
	_print_verdict("E", "build mode9 + cells mode7 in ONE list(same-list)",
		_read_ctr(_ctr_E))

	# Rung F: CONTROL — voronoi mode 7 (reset). vol sentinel: 1.0 -> 0.0.
	var clf := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(clf, _vor_pipe)
	_rd.compute_list_bind_uniform_set(clf, _us_vor, 0)
	_rd.compute_list_set_push_constant(clf, _vor_pc, _vor_pc.size())
	_rd.compute_list_dispatch(clf, 1, 1, 1)  # 64 threads >= n_sites(64)
	_rd.compute_list_end()
	await RenderingServer.frame_post_draw
	var vf := _read_float(_vol_F, 0)
	_print_verdict_raw("F", "CONTROL voronoi mode7 reset (vol)", vf <= 1.0e-9,
		"vol[0]=%.4f (expect ~0)" % vf)

	# Rung G (supplementary): reproduce the SIM's exact tree opening — mode 10
	# ROOT_SEED then mode 9 CTR_RESET, full set, one list, barrier between.
	# If the opening lands, the basic dispatch is exonerated on the global RD
	# too; the sim's no-op must then be gating/ordering elsewhere.
	var clg := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(clg, _build_pipe)
	_rd.compute_list_bind_uniform_set(clg, _us_full_G, 0)
	_rd.compute_list_set_push_constant(clg, _pc_mode(10.0), _pc.size())
	_rd.compute_list_dispatch(clg, 1, 1, 1)
	_rd.compute_list_add_barrier(clg)
	_rd.compute_list_set_push_constant(clg, _pc_mode(9.0), _pc.size())
	_rd.compute_list_dispatch(clg, 1, 1, 1)
	_rd.compute_list_end()
	await RenderingServer.frame_post_draw
	_print_verdict("G", "SIM-opening repro mode10->mode9, full set, one list",
		_read_ctr(_ctr_G))

	# Summary + exit.
	print("[TreeGrdProbe] === ladder summary ===")
	var first_fail := -1
	for r in _results:
		print(r)
		if r.contains("FAIL") and first_fail < 0:
			first_fail = _results.find(r)
	print("[TreeGrdProbe] first failing rung = ", first_fail)
	_quit = true
	get_tree().quit()

# ---------------------------------------------------------------------------
# Readbacks + verdict printers.
# ---------------------------------------------------------------------------
func _read_ctr(buf: RID) -> int:
	var data := _rd.buffer_get_data(buf, 0, 8 * 4)  # ctr[0..1]
	if data.size() < 8:
		return -1
	return data.decode_u32(0)

func _read_float(buf: RID, byte_off: int) -> float:
	var data := _rd.buffer_get_data(buf, byte_off, 4)
	return data.decode_float(0) if data.size() >= 4 else -999.0

func _print_verdict(rung: String, desc: String, ctr0: int) -> void:
	var ok := ctr0 == 1
	var line := "[TreeGrdProbe] RUNG %s %s | %s | ctr[0]=%d (expect 1) %s" % [
		rung, ("PASS" if ok else "FAIL"), desc, ctr0,
		("<<FIRST FAILING" if (not ok and not _any_earlier_fail()) else "")]
	_results.append(line)
	print(line)

func _print_verdict_raw(rung: String, desc: String, ok: bool,
		sval: String) -> void:
	var line := "[TreeGrdProbe] RUNG %s %s | %s | %s" % [
		rung, ("PASS" if ok else "FAIL"), desc, sval]
	_results.append(line)
	print(line)

func _any_earlier_fail() -> bool:
	for r in _results:
		if r.contains("FAIL"):
			return true
	return false
