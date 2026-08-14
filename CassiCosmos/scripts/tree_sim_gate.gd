extends Node
## tree_sim_gate.gd — FRESH-EYES isolation of the sim-scene tree-gravity
## global-RD no-op.
##
## QUESTION: the bare-Node probe (scripts/tree_grd_probe.gd rung G) runs the
## IDENTICAL mode-10->mode-9 full-set tree-build construction on the GLOBAL
## RenderingDevice from _process and lands (ctr[0]=1). Inside the sim scene
## (cassi_sim.gd, meshless_mode+meshless_gravity) the same construction does
## NOT execute: the counters buffer stays driver-zeroed across 60-120 settled
## frames, no error, all loud guards pass, for EVERY variant tried (real
## buffers, dummy, minimal PC, fresh shader/pipeline/set, fresh SPIR-V,
## standalone short list). The tree shaders are exonerated; the remaining
## variable is the sim-scene/sim-flow CONTEXT.
##
## THIS GATE is a fresh-eyes worker's own scene. It starts from the WORKING
## probe rung-G construction in a bare Node and ADDS sim-context ingredients
## one at a time (cumulative), each controlled by a --rungs=<set> user arg.
## Sentinel readback each run; the FIRST rung that breaks the sentinel names
## the culprit.
##
## Rungs (cumulative letters):
##   (none)   baseline = probe rung-G (mode 10 -> mode 9, full set, ONE
##            compute list per _process, frame_post_draw + self-stall readback)
##   a   MeshInstance3D + MultiMesh whose renderer-DR buffer is written each
##       frame via a compute dispatch (GPU-direct instancer, sim replica)
##   b   Camera3D + DirectionalLight3D + WorldEnvironment nodes in the scene
##   c   one extra trivial compute chain per frame (cassi_voronoi_cells mode 7)
##   d   ~40 storage buffers + ~15 pipelines created at startup (resource scale)
##   e   TWO compute_list_begin/end pairs per _process (list interleaving)
##   f   free+recreate tree pipeline/set every 30 frames while dispatching
##       every frame (the sim's _shaders_ready retry pattern)
##
## Usage (from repo root, windowed — NEVER --headless):
##   Godot_v4.7...exe --path <repo> res://scenes/tree_sim_gate.tscn --rungs=abcde
## stdout is piped by the caller into _diag/tree_sim_gate_<rungs>.log.

const SETTLE_FRAMES := 40      # settled frames of sentinel readback before verdict
const RETRY_EVERY := 30        # rung f: free+recreate this often (frames)
const EXTRA_PIPE_COUNT := 15   # rung d: extra pipelines
const EXTRA_BUF_COUNT := 40    # rung d: extra storage buffers

var _rd: RenderingDevice
var _active: Dictionary = {}   # letter -> true for each active rung

# Tree-build resources (probe rung-G construction).
var _build_shader: RID
var _build_pipe: RID
var _pc: PackedByteArray
var _us_tree: RID
var _us_alt: RID               # rung f: a separately-created set (old-RID check)
var _ctr: RID                  # sentinel counters buffer (binding 8)
var _bh_buf: RID               # rung p: bh-header mock buffer
var _b_tree: Array[RID] = []   # bindings 0-13 (real sizes, like the sim)

# Extras.
var _vor_shader: RID; var _vor_pipe: RID; var _vor_pc: PackedByteArray
var _us_vor: RID
var _extra_bufs: Array[RID] = []
var _extra_pipes: Array[RID] = []
var _extra_shaders: Array[RID] = []

# GPU-direct MultiMesh instancer (rung a).
var _mmi: MultiMeshInstance3D
var _mm: MultiMesh
var _mm_rd_rid: RID
var _inst_shader: RID; var _inst_pipe: RID; var _us_inst: RID
var _inst_pc: PackedByteArray
var _inst_pos: RID   # tiny 1-particle position buffer for the instancer

# State.
var _frame := 0
var _results: Array[String] = []
var _first_fail := -1
var _quit_dispatch := false

func _ready() -> void:
	_parse_rungs()
	print("[TreeGate] active rungs: ", (_active.keys() if _active.size() > 0 else ["(none)"]))
	_rd = RenderingServer.get_rendering_device()
	if _rd == null:
		push_error("[TreeGate] no global RenderingDevice (headless/dummy?)")
		_quit_dispatch = true
		return
	print("[TreeGate] global RD acquired: ", _rd != null)
	_setup_scene_nodes()     # rung b
	_setup_multimesh()       # rung a
	_setup_tree()            # probe rung-G construction (always)
	_setup_extra_chain()     # rung c/d
	_setup_instancer()       # rung a
	print("[TreeGate] setup complete; starting frame loop.")


func _parse_rungs() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--rungs="):
			for ch in a.trim_prefix("--rungs="):
				_active[ch] = true


func rung_active(r: String) -> bool:
	return _active.has(r)


# ---------------------------------------------------------------------------
# Scene nodes (rung b): Camera3D + DirectionalLight3D + WorldEnvironment.
# ---------------------------------------------------------------------------
func _setup_scene_nodes() -> void:
	if not rung_active("b"):
		return
	var we := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.02, 0.02, 0.04)
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	we.environment = env
	add_child(we)
	var cam := Camera3D.new()
	cam.position = Vector3(0, 300, 500)
	cam.fov = 70.0
	add_child(cam)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, -30, 0)
	add_child(light)
	print("[TreeGate] rung b: Camera3D + DirectionalLight3D + WorldEnvironment added")


# ---------------------------------------------------------------------------
# GPU-direct MultiMesh instance (rung a) — sim replica.
# ---------------------------------------------------------------------------
func _setup_multimesh() -> void:
	if not rung_active("a"):
		return
	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.instance_count = 64
	var buf := PackedFloat32Array()
	buf.resize(64 * 16)
	_mm.buffer = buf
	_mmi = MultiMeshInstance3D.new()
	_mmi.multimesh = _mm
	add_child(_mmi)
	_mm_rd_rid = RenderingServer.multimesh_get_buffer_rd_rid(_mm.get_rid())
	print("[TreeGate] rung a: MultiMesh instance buffer RD RID valid=", _mm_rd_rid.is_valid())


func _setup_instancer() -> void:
	if not rung_active("a"):
		return
	if not _mm_rd_rid.is_valid():
		push_error("[TreeGate] rung a instancer: renderer buffer RID invalid — skip")
		return
	_inst_pos = _rd.storage_buffer_create(64 * 16)   # 1+ particle vec4 pos
	_inst_shader = _load_shader_rd("res://compute/cassi_instancer.glsl")
	if _inst_shader.is_valid():
		_inst_pipe = _rd.compute_pipeline_create(_inst_shader)
	# instancer set: 0=pos, 1=instances(renderer MM buffer), 2/3 empty dummy
	var empty := _rd.storage_buffer_create(4)
	var fq := _rd.storage_buffer_create(64 * 4)
	var vel := _rd.storage_buffer_create(64 * 16)   # binding 2 vel
	_us_inst = _rd.uniform_set_create([
		_us_storage(0, _inst_pos),
		_us_storage(1, _mm_rd_rid),
		_us_storage(2, vel),
		_us_storage(3, fq),
		_us_storage(4, empty),
		_us_storage(5, empty),
	], _inst_shader, 0)
	var pcf := PackedFloat32Array()
	pcf.resize(32)
	pcf[0] = 1.0      # N_f
	pcf[6] = 64.0     # particle_N = write 64 instances
	_inst_pc = pcf.to_byte_array()
	print("[TreeGate] rung a: instancer pipe valid=", _inst_pipe.is_valid(),
		" set valid=", _us_inst.is_valid(), " pc bytes=", _inst_pc.size())


func _write_instancer() -> void:
	# One trivial instancer dispatch writing the renderer MM buffer each frame
	# as its OWN compute list (rung a + e interleave).
	if _inst_pipe.is_valid() and _us_inst.is_valid() and _mm_rd_rid.is_valid():
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _inst_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_inst, 0)
		_rd.compute_list_set_push_constant(cl, _inst_pc, _inst_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_end()


func _write_instancer_in_list(cl: int) -> void:
	# Same instancer write, but APPENDED into an already-open compute list
	# (the sim's frame list carries tree + steps + instancer together).
	if _inst_pipe.is_valid() and _us_inst.is_valid() and _mm_rd_rid.is_valid():
		_rd.compute_list_bind_compute_pipeline(cl, _inst_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_inst, 0)
		_rd.compute_list_set_push_constant(cl, _inst_pc, _inst_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)


# ---------------------------------------------------------------------------
# Tree-build probe rung-G construction (ALWAYS active).
# ---------------------------------------------------------------------------
func _setup_tree(fresh: bool = false) -> void:
	# Guard: never overwrite live RIDs without freeing (leak-safe for the
	# fresh-only rung f; from _ready they are RID() so the free is a no-op).
	if fresh:
		if _build_pipe.is_valid(): _rd.free_rid(_build_pipe)
		if _us_tree.is_valid(): _rd.free_rid(_us_tree)
		if _build_shader.is_valid(): _rd.free_rid(_build_shader)
	_build_shader = _load_shader_rd("res://compute/cassi_tree_build.glsl")
	if not _build_shader.is_valid():
		push_error("[TreeGate] tree-build shader failed to load")
		return
	_build_pipe = _rd.compute_pipeline_create(_build_shader)
	print("[TreeGate] tree-build pipeline valid=", _build_pipe.is_valid())

	_pc = PackedFloat32Array([
		64.0, 0.0, 0.0, 0.0,       # N_f, bmin.xyz
		1.0, 1.0e-6,               # bhalf, eps2
		1.618, 17.944,             # phi, xi
		1.0, 14.0, 9.0,            # leaf_cap, max_levels, mode(override)
		0.0, 0.0, 0.0,             # b_k, b_j, b_m
		0.0, 0.0, 0.0, 0.0, 0.0,   # grid_N, ext.xyz, field_floor
	]).to_byte_array()

	# Sentinel + full build set (bindings 0-13), real-ish sizes.
	_ctr = _rd.storage_buffer_create(64 * 4)
	_bh_buf = _rd.storage_buffer_create(64 * 4)
	_b_tree.clear()
	var sizes := [2048, 256, 256, 256, 4096, 4096, 8192, 4096, 256,
		1024, 256, 256, 256, 256]
	for s in sizes:
		_b_tree.append(_rd.storage_buffer_create(s))
	_b_tree[8] = _ctr   # binding 8 = counters (sentinel)
	_us_tree = _rd.uniform_set_create([
		_us_storage(0, _b_tree[0]), _us_storage(1, _b_tree[1]),
		_us_storage(2, _b_tree[2]), _us_storage(3, _b_tree[3]),
		_us_storage(4, _b_tree[4]), _us_storage(5, _b_tree[5]),
		_us_storage(6, _b_tree[6]), _us_storage(7, _b_tree[7]),
		_us_storage(8, _b_tree[8]),
		_us_storage(9, _b_tree[9]), _us_storage(10, _b_tree[10]),
		_us_storage(11, _b_tree[11]), _us_storage(12, _b_tree[12]),
		_us_storage(13, _b_tree[13]),
	], _build_shader, 0)
	print("[TreeGate] tree set valid=", _us_tree.is_valid())


func _pc_mode(mode: float) -> PackedByteArray:
	var p := _pc.duplicate()
	p.encode_float(10 * 4, mode)
	return p


# ---------------------------------------------------------------------------
# Rung c/d: extra chain (cassi_voronoi_cells mode 7) + resource scale.
# ---------------------------------------------------------------------------
func _setup_extra_chain() -> void:
	if rung_active("c") or rung_active("e"):
		_vor_shader = _load_shader_rd("res://compute/cassi_voronoi_cells.glsl")
		if _vor_shader.is_valid():
			_vor_pipe = _rd.compute_pipeline_create(_vor_shader)
		_vor_pc = PackedFloat32Array([
			7.0, 64.0, 64.0, 0.01, 0.5, 0.5, 0.5,
			0.25, 0.1, 1.618, 0.001, 1.0e-3, 1.0, 0.5, 0.1, 0.05, 2.0,
		]).to_byte_array()
		# 16 buffers for the voronoi set (bindings 0-15).
		var vb: Array[RID] = []
		for b in range(16):
			var sz := 64 * 16 if b == 10 else 64 * 4   # cen = vec4 per cell
			vb.append(_rd.storage_buffer_create(sz))
		var uniform_list: Array[RDUniform] = []
		for b in range(16):
			uniform_list.append(_us_storage(b, vb[b]))
		_us_vor = _rd.uniform_set_create(uniform_list, _vor_shader, 0)
		print("[TreeGate] extra-chain (voronoi mode7) pipe=", _vor_pipe.is_valid(),
			" set=", _us_vor.is_valid())
	# Resource scale (rung d): ~40 buffers + ~15 pipelines.
	if rung_active("d"):
		for i in range(EXTRA_BUF_COUNT):
			_extra_bufs.append(_rd.storage_buffer_create(64 * 4))
		for i in range(EXTRA_PIPE_COUNT):
			var s := _load_shader_rd("res://compute/cassi_tree_build.glsl")
			if s.is_valid():
				_extra_shaders.append(s)
				_extra_pipes.append(_rd.compute_pipeline_create(s))
		print("[TreeGate] rung d: %d buffers, %d extra pipelines created"
			% [EXTRA_BUF_COUNT, _extra_pipes.size()])


func _dispatch_extra_chain() -> void:
	if _vor_pipe.is_valid() and _us_vor.is_valid():
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _vor_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_vor, 0)
		_rd.compute_list_set_push_constant(cl, _vor_pc, _vor_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_end()


# ---------------------------------------------------------------------------
# Frame work: dispatch the tree chain + rung extras, then sentinel readback.
# ---------------------------------------------------------------------------
func _dispatch_tree_chain() -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _build_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_tree, 0)
	# mode 10 root seed, then mode 9 counter reset (probe rung-G opening).
	_rd.compute_list_set_push_constant(cl, _pc_mode(10.0), _pc.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_rd.compute_list_set_push_constant(cl, _pc_mode(9.0), _pc.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_end()


func _process(_delta: float) -> void:
	if _quit_dispatch:
		return
	_frame += 1

	# Rung f: free+recreate the tree pipeline/set every RETRY_EVERY frames,
	# while still dispatching every frame (the sim's _shaders_ready retry).
	if rung_active("f") and _frame % RETRY_EVERY == 0:
		print("[TreeGate] rung f frame %d: free+recreate tree pipe/set"
			% _frame)
		_setup_tree(true)   # freshens shader+pipe+set (frees old)

		# Rung p: a per-frame global-RD buffer_update BEFORE the tree list,
		# replicating the sim's bh-header buffer_update at line 771 that runs
		# before compute_list_begin in the SAME _process.
		if rung_active("p") and _frame <= SETTLE_FRAMES:
			var bh := PackedByteArray()
			bh.resize(64 * 4)
			bh.encode_float(48, 0.0)
			_rd.buffer_update(_bh_buf, 0, bh.size(), bh)

	if _frame <= SETTLE_FRAMES:
		# Frame list #1: tree chain (+ instancer write appended to the SAME
		# list when rung a and NOT rung e — replicating the sim's frame list
		# that carries tree + steps + instancer in ONE list).
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _build_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree, 0)
		_rd.compute_list_set_push_constant(cl, _pc_mode(10.0), _pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_rd.compute_list_set_push_constant(cl, _pc_mode(9.0), _pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		if rung_active("a") and not rung_active("e"):
			_write_instancer_in_list(cl)   # in-list, like the sim's frame list
		_rd.compute_list_end()
		# Rung a + rung e: the instancer write becomes a SEPARATE list,
		# whose output is a renderer-owned buffer (sim's list-interleave).
		if rung_active("a") and rung_active("e"):
			_write_instancer()
		# Rung c: the extra voronoi chain as its own list (list #3).
		if rung_active("c"):
			_dispatch_extra_chain()
		# Readback (self-stall) via frame_post_draw, mirroring the sim's
		# _render_frame readbacks that flush the frame's pending lists.
		await RenderingServer.frame_post_draw
		var v := _read_ctr()
		var ok := v == 1
		_results.append("frame %3d  ctr[0]=%d  %s" % [ _frame, v,
			("PASS" if ok else "FAIL") ])
		if not ok and _first_fail < 0:
			_first_fail = _frame
		if _frame == SETTLE_FRAMES:
			_verdict()


func _verdict() -> void:
	print("[TreeGate] === ladder verdict ===")
	var ok_all := _first_fail < 0
	for r in _results:
		print(r)
	var rung_name := ("".join(_active.keys()) if _active.size() > 0 else "base")
	print("[TreeGate] rungs active: ", rung_name,
		" | sentinel ", ("LANDED (ctr[0]=1)" if ok_all else "DID NOT land (driver-zeroed)"),
		" | first-fail-frame=", _first_fail)
	_quit_dispatch = true
	get_tree().quit()


# ---------------------------------------------------------------------------
# Readback helpers.
# ---------------------------------------------------------------------------
func _read_ctr() -> int:
	var data := _rd.buffer_get_data(_ctr, 0, 8 * 4)
	if data.size() < 8:
		return -1
	return data.decode_u32(0)


func _us_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _load_shader_rd(path: String) -> RID:
	if not ResourceLoader.exists(path):
		push_error("[TreeGate] missing shader " + path)
		return RID()
	var sf: RDShaderFile = load(path)
	if sf == null:
		push_error("[TreeGate] load failed " + path)
		return RID()
	var spirv = sf.get_spirv()
	if spirv == null:
		push_error("[TreeGate] SPIR-V fail " + path)
		return RID()
	return _rd.shader_create_from_spirv(spirv)
