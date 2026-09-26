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
##   g   RD-buffer HANDOFF rung: a STORAGE_BUFFER_USAGE RD buffer created by US
##       and handed to RenderingServer via multimesh_set_buffer on a real
##       MultiMesh whose MeshInstance3D DRAWS it every frame (the sim's actual
##       mode: the renderer consumes a global-RD buffer). Plus a per-frame
##       instancer write into that handed-off buffer, then modes 10->9.
##   h   DISPATCH-VOLUME rung: the tree chain FIRST in the frame list, then a
##       loop of 16 x ~15-dispatch dummy chains (~240 dispatches, voronoi mode
##       7 + cheap shader with barriers), then a _render_frame-style second
##       list. Sentinel readback after 120 frames (~$n-360 dispatches/frame).
##   i   PER-FRAME BUFFER_UPDATE rung: several buffer_update calls on OTHER
##       buffers BEFORE compute_list_begin each frame (sim's bh-header +
##       field-update pattern), then the tree chain, sentinel after 120 frames.
##   w   FULL-CHAIN rung: the sim's ENTIRE _dispatch_tree_gravity sequence in
##       ONE list — modes 10/9/7, bitonic (91), split/commit (14 x 2), moments,
##       then the WALK on a second pipeline+set — with the sim's IN-PLACE PC
##       mutation. Replicates the sim construction never tested by earlier
##       rungs (which stopped at modes 10->9).
##
## Usage (from repo root, windowed — NEVER --headless):
##   Godot_v4.7...exe --path <repo> res://scenes/tree_sim_gate.tscn --rungs=abcde
## stdout is piped by the caller into _diag/tree_sim_gate_<rungs>.log.

const SETTLE_FRAMES := 40      # settled frames of sentinel readback before verdict
const SETTLE_FRAMES_HEAVY := 120  # rungs h/i: spec asks 120 settled frames
const RETRY_EVERY := 30        # rung f: free+recreate this often (frames)
const EXTRA_PIPE_COUNT := 15   # rung d: extra pipelines
const EXTRA_BUF_COUNT := 40    # rung d: extra storage buffers

var _rd: RenderingDevice
var _active: Dictionary = {}   # letter -> true for each active rung

# Tree-build resources (probe rung-G construction).
var _build_shader: RID
var _build_pipe: RID
var _pc: PackedByteArray
var _tree_build_pc_bytes: PackedByteArray   # rung w: in-place mutated PC
var _tree_grav_pc_bytes: PackedByteArray    # rung w: 5-float walk PC
var _us_tree: RID
var _us_alt: RID               # rung f: a separately-created set (old-RID check)
var _ctr: RID                  # sentinel counters buffer (binding 8)
var _bh_buf: RID               # rung p: bh-header mock buffer

# Rung g (RD-buffer handoff): a global-RD storage buffer handed to a
# MultiMesh via multimesh_set_buffer; the renderer DRAWS it every frame while
# we write it via compute.
var _mm_g: MultiMesh
var _mmi_g: MultiMeshInstance3D
var _handoff_rid: RID = RID()   # the RD buffer given to the renderer
var _us_inst_g: RID             # instancer set binding _handoff_rid
var _perf_up_bufs: Array[RID] = []  # rung i: distinct per-frame-updated buffers
var _b_tree: Array[RID] = []   # bindings 0-13 (real sizes, like the sim)

# Rung w (full sim tree chain): the walk shader/pipeline/set + buffers.
var _walk_shader: RID; var _walk_pipe: RID
var _us_walk: RID
var _walk_pc: PackedByteArray   # 5 floats (N, theta, eps2, use_tp, node_cnt)
var _tree_grad: RID             # vec4[Np] walk output
var _tree_icount: RID           # uint[Np]
var _tree_pos: RID              # vec4[Np] target positions
var _node_qq: RID               # float[node cap] — Arm 2 per-node mean q (binding 14)

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
	_setup_handoff_multimesh()  # rung g
	_setup_tree()            # probe rung-G construction (always)
	_setup_extra_chain()     # rung c/d
	_setup_instancer()       # rung a
	_setup_walk()            # rung w
	print("[TreeGate] setup complete; starting frame loop.")


func _parse_rungs() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--rungs="):
			for ch in a.trim_prefix("--rungs="):
				_active[ch] = true


func rung_active(r: String) -> bool:
	return _active.has(r)


func _settle_count() -> int:
	# Rungs h/i push the sim's real per-frame load; the spec asks for a
	# 120-frame settle there. All other rungs settle at 40.
	if rung_active("h") or rung_active("i"):
		return SETTLE_FRAMES_HEAVY
	return SETTLE_FRAMES


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
	var lut_off := _rd.storage_buffer_create(16)    # binding 6 LUT flag: OFF (zero) — the instancer's color-as-LUT branch is dead
	var zero16 := PackedByteArray(); zero16.resize(16)
	_rd.buffer_update(lut_off, 0, 16, zero16)
	_us_inst = _rd.uniform_set_create([
		_us_storage(0, _inst_pos),
		_us_storage(1, _mm_rd_rid),
		_us_storage(2, vel),
		_us_storage(3, fq),
		_us_storage(4, empty),
		_us_storage(5, empty),
		_us_storage(6, lut_off),
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
# Rung g: RD-buffer HANDOFF — we create a global-RD storage buffer, hand it
# to a real MultiMesh via RenderingServer.multimesh_set_buffer, attach a
# MeshInstance3D that DRAWS it every frame (the renderer consumes a
# global-RD buffer), and write it each frame via the GPU-direct instancer
# bound against that same handed-off buffer. This is the sim's actual
# VRAM-handoff shape: a global-RD buffer consumed by the renderer while the
# tree modes 10->9 also dispatch each frame.
# ---------------------------------------------------------------------------
func _setup_handoff_multimesh() -> void:
	if not rung_active("g"):
		return
	# The rung-spec described `multimesh_set_buffer(multimesh_rid, rd_rid)`,
	# but in Godot 4.7 that API takes a PackedFloat32Array, NOT an RID (the
	# parser rejected the RID form). The sim's ACTUAL handoff — and the only
	# valid "renderer consumes a global-RD buffer" form — is the reverse:
	# the renderer allocates the instance buffer (from instance_count) and we
	# grab its RD RID via `multimesh_get_buffer_rd_rid`, bind it in a compute
	# set, AND draw it every frame via a MeshInstance3D with a material.
	_mm_g = MultiMesh.new()
	_mm_g.transform_format = MultiMesh.TRANSFORM_3D
	_mm_g.use_colors = true
	var qm := QuadMesh.new()
	qm.size = Vector2(0.5, 0.5)
	_mm_g.mesh = qm
	_mm_g.instance_count = 64
	_mm_g.custom_aabb = AABB(Vector3(-200, -200, -200), Vector3(400, 400, 400))
	_handoff_rid = RenderingServer.multimesh_get_buffer_rd_rid(_mm_g.get_rid())
	_mmi_g = MultiMeshInstance3D.new()
	_mmi_g.multimesh = _mm_g
	add_child(_mmi_g)
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/particle_billboard.gdshader")
	_mmi_g.material_override = mat
	print("[TreeGate] rung g: renderer buffer RD RID=", _handoff_rid.is_valid(),
		" drawn via MeshInstance3D + particle_billboard every frame")

	# Instancer set binding THIS renderer buffer (bindings 0-5 like the sim).
	var pos := _rd.storage_buffer_create(64 * 16)
	var vel := _rd.storage_buffer_create(64 * 16)
	var fq := _rd.storage_buffer_create(64 * 4)
	var inst_sh := _load_shader_rd("res://compute/cassi_instancer.glsl")
	if not inst_sh.is_valid():
		push_error("[TreeGate] rung g: instancer shader load failed")
	if not _inst_pipe.is_valid():
		_inst_shader = inst_sh
		_inst_pipe = _rd.compute_pipeline_create(inst_sh)
	if _inst_pc.is_empty():
		var pcf := PackedFloat32Array()
		pcf.resize(32)
		pcf[0] = 1.0
		pcf[6] = 64.0
		_inst_pc = pcf.to_byte_array()
	var lut_off_g := _rd.storage_buffer_create(16)  # LUT flag OFF (zero-filled)
	var zero16g := PackedByteArray(); zero16g.resize(16)
	_rd.buffer_update(lut_off_g, 0, 16, zero16g)
	_us_inst_g = _rd.uniform_set_create([
		_us_storage(0, pos), _us_storage(1, _handoff_rid),
		_us_storage(2, vel), _us_storage(3, fq),
		_us_storage(4, fq), _us_storage(5, fq),
		_us_storage(6, lut_off_g),
	], inst_sh, 0)
	print("[TreeGate] rung g: instancer pipe=", _inst_pipe.is_valid(),
		" set on renderer buffer=", _us_inst_g.is_valid())


func _write_handoff() -> void:
	# Write the handed-off renderer buffer via the instancer each frame.
	if _inst_pipe.is_valid() and _us_inst_g.is_valid() and _handoff_rid.is_valid():
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _inst_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_inst_g, 0)
		_rd.compute_list_set_push_constant(cl, _inst_pc, _inst_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_end()


func _write_handoff_in_list(cl: int) -> void:
	if _inst_pipe.is_valid() and _us_inst_g.is_valid() and _handoff_rid.is_valid():
		_rd.compute_list_bind_compute_pipeline(cl, _inst_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_inst_g, 0)
		_rd.compute_list_set_push_constant(cl, _inst_pc, _inst_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)


# ---------------------------------------------------------------------------
# Rung h: DISPATCH VOLUME — the sim's real per-frame load. Tree chain FIRST
# in the frame list, then ~240 dummy dispatches (16 chains of ~15), then a
# _render_frame-style second list (a trivial repaint dispatch).
# ---------------------------------------------------------------------------
const VOLUME_CHAINS := 16
const VOLUME_DISPS_PER_CHAIN := 15

func _dispatch_volume_chain(cl: int) -> void:
	# 15 voronoi mode-7 dispatches with barriers (cheap shader, complete set).
	for _i in range(VOLUME_DISPS_PER_CHAIN):
		_rd.compute_list_bind_compute_pipeline(cl, _vor_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_vor, 0)
		_rd.compute_list_set_push_constant(cl, _vor_pc, _vor_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)


func _volume_second_list() -> void:
	# _render_frame-style standalone repaint list after the main list.
	if _vor_pipe.is_valid() and _us_vor.is_valid():
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _vor_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_vor, 0)
		_rd.compute_list_set_push_constant(cl, _vor_pc, _vor_pc.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_rd.compute_list_end()


# ---------------------------------------------------------------------------
# Rung i: PER-FRAME BUFFER_UPDATE — several buffer_update calls on OTHER
# buffers BEFORE compute_list_begin each frame (the sim's bh-header + field
# encode-and-update pattern, _run_physics_steps lines ~758-793).
# ---------------------------------------------------------------------------
func _perframe_updates() -> void:
	if not rung_active("i"):
		return
	var f := PackedFloat32Array()
	f.resize(16)
	f[0] = float(_frame)
	f[1] = 1.0
	f[2] = 0.0
	f[3] = 0.0
	var b := f.to_byte_array()
	for buf in _perf_up_bufs:
		_rd.buffer_update(buf, 0, b.size(), b)


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
		1024, 256, 256, 256, 256, 4096]   # [14] = nodeQq (Arm 2 per-node mean q)
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
		_us_storage(14, _b_tree[14]),
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
	if rung_active("c") or rung_active("e") or rung_active("h") or rung_active("i"):
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
	# Rung i: distinct buffers updated per-frame (bh-header + field pattern).
	if rung_active("i"):
		for i in range(6):
			_perf_up_bufs.append(_rd.storage_buffer_create(64 * 4))
		print("[TreeGate] rung i: %d per-frame-update buffers created"
			% _perf_up_bufs.size())
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


# ---------------------------------------------------------------------------
# Rung w: the sim's FULL _dispatch_tree_gravity chain, in ONE list, with the
# sim's IN-PLACE PC mutation (a persistent PackedByteArray re-encoded per
# mode) — the exact construction the sim runs that earlier rungs did not.
# ---------------------------------------------------------------------------
func _setup_walk() -> void:
	if not rung_active("w"):
		return
	_walk_shader = _load_shader_rd("res://compute/cassi_tree_gravity.glsl")
	if _walk_shader.is_valid():
		_walk_pipe = _rd.compute_pipeline_create(_walk_shader)
	_walk_pc = PackedByteArray(); _walk_pc.resize(8 * 4)
	_tree_build_pc_bytes = _pc.duplicate()   # 19-float build PC (persistent, in-place)
	_tree_grav_pc_bytes = PackedByteArray(); _tree_grav_pc_bytes.resize(8 * 4)
	_tree_grad = _rd.storage_buffer_create(64 * 16)   # Np = 64
	_tree_icount = _rd.storage_buffer_create(64 * 4)
	_tree_pos = _rd.storage_buffer_create(64 * 16)
	_node_qq = _rd.storage_buffer_create(8 * 64 * 4)   # nodeQq binding 14 (node cap 8·Nsrc+64)
	# Walk set: 0=src, 3=order, 4=cf, 5=w, 6=q, 7=r, 8=ctr, 9=grad, 10=icount,
	# 11=pos, 14=nodeQq. (Uses the build set's _b_tree slots + walk-only buffers.)
	if _walk_shader.is_valid():
		_us_walk = _rd.uniform_set_create([
			_us_storage(0, _b_tree[0]), _us_storage(3, _b_tree[3]),
			_us_storage(4, _b_tree[4]), _us_storage(5, _b_tree[5]),
			_us_storage(6, _b_tree[6]), _us_storage(7, _b_tree[7]),
			_us_storage(8, _b_tree[8]),
			_us_storage(9, _tree_grad), _us_storage(10, _tree_icount),
			_us_storage(11, _tree_pos),
			_us_storage(14, _node_qq),
		], _walk_shader, 0)
	print("[TreeGate] rung w: walk pipe=", _walk_pipe.is_valid(),
		" walk set=", _us_walk.is_valid())


func _dispatch_full_tree_chain(cl: int) -> void:
	# Faithful copy of cassi_sim.gd _dispatch_tree_gravity (modes 10/9/7/1/5/8/6
	# + walk), with the sim's IN-PLACE PC mutation on a persistent
	# _tree_build_pc_bytes (the same PackedByteArray re-encoded per mode, and
	# carried across frames — the exact object the sim dispatches). Dispatch
	# is recorded into the ALREADY-OPEN list `cl` (the sim's frame list),
	# which the caller ends AFTER this returns — exactly like _run_physics_steps
	# continues the same `cl` with _step_dispatches + instancer.
	var N_src := 64
	var Np := 64
	var pg_src := 1
	var bp: PackedByteArray = _tree_build_pc_bytes
	# Re-baseline the in-place persistent PC this frame (like the sim sets the
	# constants each _dispatch_tree_gravity call) but KEEP the same object.
	bp.encode_float(0, float(N_src))
	bp.encode_float(4, 1.000001)
	# gather fields (mode 7 reads bindings 9-13 via grid_N/extents)
	bp.encode_float(14, 64.0)
	bp.encode_float(15, 1.0); bp.encode_float(16, 1.0); bp.encode_float(17, 1.0)
	bp.encode_float(18, 1.0e-6)
	# Walk PC: 5 floats, in-place on _tree_grav_pc_bytes.
	var wp: PackedByteArray = _tree_grav_pc_bytes
	wp.encode_float(0, float(Np))
	wp.encode_float(1, 0.5)
	wp.encode_float(2, 1.0e-6)
	wp.encode_float(3, 1.0)   # use_tp
	wp.encode_float(4, float(8 * N_src + 64))
	# Arm 2 OFF here (probe): q_cent/α default, toggle = 0 → shader dead.
	wp.encode_float(5, 0.0)
	wp.encode_float(6, 1.0)
	wp.encode_float(7, 0.0)

	# 0a. root seed (mode 10) + counter reset (mode 9) — the sentinel.
	_rd.compute_list_bind_compute_pipeline(cl, _build_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_tree, 0)
	bp.encode_float(10, 10.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	bp.encode_float(10, 9.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 1. gather (mode 7)
	bp.encode_float(10, 7.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, pg_src, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 2. bitonic (N_src=64 -> 21 comparator stages)
	var k := 2
	while k <= N_src:
		var j := k >> 1
		while j >= 1:
			bp.encode_float(10, 1.0); bp.encode_float(11, float(k))
			bp.encode_float(12, float(j)); bp.encode_float(13, 1.0)
			_rd.compute_list_set_push_constant(cl, bp, bp.size())
			_rd.compute_list_dispatch(cl, pg_src, 1, 1)
			_rd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	_rd.compute_list_add_barrier(cl)
	# 3. BFS split (14 x [mode 5 split -> mode 8 commit])
	var tnm := 8 * N_src + 64
	var pg_all := ceili(float(tnm) / 64.0)
	for _depth in range(14):
		bp.encode_float(10, 5.0)
		_rd.compute_list_set_push_constant(cl, bp, bp.size())
		_rd.compute_list_dispatch(cl, pg_all, 1, 1)
		_rd.compute_list_add_barrier(cl)
		bp.encode_float(10, 8.0)
		_rd.compute_list_set_push_constant(cl, bp, bp.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
	# 4. moments (mode 6)
	bp.encode_float(10, 6.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, pg_all, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 5. walk (second pipeline + set, same list)
	_rd.compute_list_bind_compute_pipeline(cl, _walk_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_walk, 0)
	_rd.compute_list_set_push_constant(cl, wp, wp.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# NOTE: caller ends the list (like _run_physics_steps continues `cl`).


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
	if rung_active("p") and _frame <= _settle_count():
		var bh := PackedByteArray()
		bh.resize(64 * 4)
		bh.encode_float(48, 0.0)
		_rd.buffer_update(_bh_buf, 0, bh.size(), bh)

	if _frame <= _settle_count():
		# Rung i: several buffer_updates on OTHER buffers BEFORE
		# compute_list_begin each frame (sim bh-header + field pattern).
		if rung_active("i") and not _quit_dispatch:
			_perframe_updates()
		# Rung w: the sim's ENTIRE tree chain (build modes + walk) recorded
		# into ONE list that the caller opens and continues — exactly like
		# _run_physics_steps passes its frame `cl` to _dispatch_tree_gravity.
		if rung_active("w"):
			var cw := _rd.compute_list_begin()
			_dispatch_full_tree_chain(cw)
			# Rung h: continue the SAME list with ~240 dummy dispatches,
			# mimicking the steps that follow the tree in the sim's list.
			if rung_active("h"):
				for _ci in range(VOLUME_CHAINS):
					_dispatch_volume_chain(cw)
			_rd.compute_list_end()
			if rung_active("h"):
				_volume_second_list()
			await RenderingServer.frame_post_draw
			var vw := _read_ctr()
			_results.append("frame %3d  ctr[0]=%d  %s" % [ _frame, vw,
				("PASS" if vw == 1 else "FAIL") ])
			if vw != 1 and _first_fail < 0:
				_first_fail = _frame
			if _frame == _settle_count():
				_verdict()
			return
		# Frame list #1: tree chain (+ rung-extras appended to the SAME list
		# — replicating the sim's frame list that carries tree + steps +
		# instancer in ONE list).
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
		if rung_active("g"):
			_write_handoff_in_list(cl)     # write the handed-off renderer buffer
		# Rung h: ~240 dummy dispatches (16 x 15) after the tree, same list.
		if rung_active("h"):
			for _ci in range(VOLUME_CHAINS):
				_dispatch_volume_chain(cl)
		_rd.compute_list_end()
		# Rung a + rung e: the instancer write becomes a SEPARATE list.
		if rung_active("a") and rung_active("e"):
			_write_instancer()
		# Rung c: the extra voronoi chain as its own list (list #3).
		if rung_active("c"):
			_dispatch_extra_chain()
		# Rung h: a _render_frame-style second list (trivial repaint).
		if rung_active("h"):
			_volume_second_list()
		# Readback (self-stall) via frame_post_draw, mirroring the sim's
		# _render_frame readbacks that flush the frame's pending lists.
		await RenderingServer.frame_post_draw
		var v := _read_ctr()
		var ok := v == 1
		_results.append("frame %3d  ctr[0]=%d  %s" % [ _frame, v,
			("PASS" if ok else "FAIL") ])
		if not ok and _first_fail < 0:
			_first_fail = _frame
		if _frame == _settle_count():
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
