extends Node
## Cassi Mind Engine — self-contained two-fluid field sidecar.
## Runs the proven compute/cassi_two_fluid.glsl on a LOCAL RenderingDevice
## (windowed on this rig: --headless yields no RD, even local — see the
## GPU battery skill) and serves a loopback TCP bridge (line-delimited
## JSON) for the OhMyPi plugin.
##
## Protocol (one JSON object per line, both directions):
##   {"cmd":"ping"}                      -> {"ok":true,"cmd":"ping","step":..,"t":..}
##   {"cmd":"clear"}                     -> {"ok":true,"cmd":"clear"}
##   {"cmd":"deposit","x":..,"y":..,"z":..,"cy":..,"ci":..,"sigma":..}
##                                       -> {"ok":true,"cmd":"deposit","pending":..}
##   {"cmd":"step","n":..}               -> {"ok":true,"cmd":"step","step":..,"t":..}
##   {"cmd":"state"}                     -> {"ok":true,"cmd":"state","step":..,"t":..,
##                                           "mean_ey":..,"mean_ei":..,"max_eps2":..}
##   {"cmd":"project","k":..}            -> {"ok":true,"cmd":"project","step":..,"t":..,
##                                           "cells":[{i,gx,gy,gz,x,y,z,ey,ei,q},..]} (top-k by q)
##   {"cmd":"readout"}                   -> {"ok":true,"cmd":"readout","ey_b64":..,"ei_b64":..,
##                                           "q_b64":..,"eps2_b64":..}
##   {"cmd":"snapshot","label":..}       -> {"ok":true,"cmd":"snapshot","path":..}
##   {"cmd":"qi_snapshot","schema":"cassi.qi.native-state.v1","revision":..,
##      "state_sha256":..,"contract_sha256":..,"state_f32_base64":..}
##                                       -> {"ok":true,"cmd":"qi_snapshot",...}
##   {"cmd":"qi_state"}                  -> read-only canonical-Qi snapshot metadata
##   {"cmd":"qi_project","k":..}         -> top-k active Qi modes by p0²+p1²
##   {"cmd":"qi_clear"}                  -> clears only the read-only Qi mirror
##
## Coordinates are physical: box [-extent, extent]^3. Deposits scatter with
## a TSC kernel (separable quadratic spline, partition of unity, 27 cells),
## added to EY/EI only (velocity untouched). The field state is the truth;
## nothing is written to disk except explicit snapshots.

const PHI := 1.618033988749895
const QI_SCHEMA := "cassi.qi.native-state.v1"
const QI_MODE_COUNT := 6144
const QI_WAVE_MODE_COUNT := 3072
const QI_SCALE_COUNT := 4
const QI_PLANE_COUNT := 9
const QI_STATE_FLOATS := QI_MODE_COUNT * QI_SCALE_COUNT * QI_PLANE_COUNT
const QI_STATE_BYTES := QI_STATE_FLOATS * 4

@export var grid_n := 64
@export var dt := 0.005
@export var extent := Vector3(1.0, 1.0, 1.0)
@export var steps_per_frame := 1
@export var auto_step := true
@export var serve_bridge := true
@export var bridge_port := 7599

var _rd: RenderingDevice
var _shader: RID
var _pipe: RID
var _us: RID
var _ey: RID
var _ei: RID
var _q: RID
var _vel: RID
var _rho: RID
var _scratch: RID  # two-fluid PDE double-buffer scratch (cassi_two_fluid.glsl binding 5)
var _fi_fallback: RID  # zeroed shared two-fluid bindings 6/7; mind sidecar keeps FI disabled
var _pc := PackedFloat32Array()
var _step := 0
var _t := 0.0
var _server: TCPServer
var _peers: Array[StreamPeerTCP] = []
var _peer_buf: Dictionary = {}
var _pending := PackedFloat32Array()
var _qi_state := PackedByteArray()
var _qi_revision := -1
var _qi_state_sha256 := ""
var _qi_contract_sha256 := ""


func _ready() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		push_error("[MindEngine] no local RenderingDevice (headless/dummy renderer) — run windowed")
		return
	_make_buffers()
	_load_pipeline()
	if serve_bridge:
		_server = TCPServer.new()
		var err: Error = _server.listen(bridge_port, "127.0.0.1")
		if err != OK:
			push_error("[MindEngine] TCP listen failed: %d" % err)
	print("[MindEngine] ready N=%d dt=%.4f bridge=%s port=%d" % [grid_n, dt, str(serve_bridge), bridge_port])


func _process(_delta: float) -> void:
	if _rd == null:
		return
	if auto_step:
		for i in range(steps_per_frame):
			_step_pde()
	if serve_bridge and _server != null:
		_poll_bridge()


# ── setup ────────────────────────────────────────────────────────────────
func _make_buffers() -> void:
	var cells: int = grid_n * grid_n * grid_n
	_ey = _rd.storage_buffer_create(cells * 4)
	_ei = _rd.storage_buffer_create(cells * 4)
	_q = _rd.storage_buffer_create(cells * 4)
	_vel = _rd.storage_buffer_create(cells * 16)
	_rho = _rd.storage_buffer_create(cells * 4)
	var zero := PackedByteArray()
	zero.resize(cells * 4)
	_rd.buffer_update(_ey, 0, cells * 4, zero)
	_rd.buffer_update(_ei, 0, cells * 4, zero)
	_rd.buffer_update(_q, 0, cells * 4, zero)
	_rd.buffer_update(_rho, 0, cells * 4, zero)
	var zero16 := PackedByteArray()
	zero16.resize(cells * 16)
	_rd.buffer_update(_vel, 0, cells * 16, zero16)
	# PDE double-buffer scratch (vec4 per cell — pass A writes the new
	# field here, pass B copies to the canonical buffers; read/write
	# buffers never alias, so the 19-point stencil is race-free)
	_scratch = _rd.storage_buffer_create(cells * 16)
	_rd.buffer_update(_scratch, 0, cells * 16, zero16)
	var fi_zero := PackedByteArray(); fi_zero.resize(128)
	_fi_fallback = _rd.storage_buffer_create(128, fi_zero)


func _load_pipeline() -> void:
	var sf := load("res://compute/cassi_two_fluid.glsl") as RDShaderFile
	if sf == null:
		push_error("[MindEngine] two-fluid shader load failed")
		return
	_shader = _rd.shader_create_from_spirv(sf.get_spirv())
	_pipe = _rd.compute_pipeline_create(_shader)
	_us = _rd.uniform_set_create([
		_u(0, _ey), _u(1, _ei), _u(2, _q), _u(3, _vel), _u(4, _rho),
		_u(5, _scratch),
		_u(6, _fi_fallback), _u(7, _fi_fallback),
	], _shader, 0)
	if not _pipe.is_valid():
		push_error("[MindEngine] compute pipeline build failed")


func _u(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# ── stepping ─────────────────────────────────────────────────────────────
func _fill_pc() -> void:
	_pc.resize(17)
	_pc[0] = float(grid_n)
	_pc[1] = dt
	_pc[2] = _t
	_pc[3] = PHI
	_pc[4] = 0.0  # xi
	_pc[5] = 0.0  # eps2
	_pc[6] = 0.0  # particle_N
	_pc[7] = 0.0  # mode
	_pc[8] = 0.0  # source_strength
	_pc[9] = 0.0  # num_clusters
	_pc[10] = 0.0  # gravity_mode
	_pc[11] = extent.x
	_pc[12] = extent.y
	_pc[13] = extent.z
	_pc[14] = 0.0  # pass_sel: 0 = pass A (compute → scratch), 1 = pass B (scratch → field)
	_pc[15] = 20.0  # omega2 = ω₀² (the two-fluid resonance; default 20.0 — bit-identical to the hardcode)
	_pc[16] = 0.0  # ham_completion OFF (U1 toggle, offset 64)


func _step_pde() -> void:
	if _rd == null or _pipe == RID() or not _pipe.is_valid():
		return
	_flush_pending()
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	# Two-pass double-buffered PDE (cassi_two_fluid.glsl): pass A computes
	# the new field into the scratch buffer (reads canonical, writes
	# scratch — no in-dispatch aliasing), pass B copies scratch to the
	# canonical field. The single-pass neighbor-stencil write race made
	# the field 1-ULP nondeterministic — this is the determinism fix.
	_fill_pc()
	_pc[14] = 0.0  # pass A
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	_rd.compute_list_dispatch(cl, grid_n / 4, grid_n / 4, grid_n / 4)
	_rd.compute_list_add_barrier(cl)
	_fill_pc()
	_pc[14] = 1.0  # pass B
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	_rd.compute_list_dispatch(cl, grid_n / 4, grid_n / 4, grid_n / 4)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	_step += 1
	_t += dt


func step_n(n: int) -> void:
	var done := 0
	while done < n:
		_step_pde()
		done += 1


# ── deposition (TSC scatter, CPU side, 27 cells) ────────────────────────
func deposit(x: float, y: float, z: float, cy: float, ci: float, sigma: float = 1.0) -> void:
	_pending.append_array(PackedFloat32Array([x, y, z, cy, ci, sigma]))

# Replace the complete canonical field without reallocating any GPU resource.
# The validation pass is side-effect free: no buffer update or engine-state
# mutation occurs until both channels and their derived q values are valid.
func seed_full_field(ey_values: PackedFloat32Array, ei_values: PackedFloat32Array) -> bool:
	var cells: int = grid_n * grid_n * grid_n
	if ey_values.size() != cells or ei_values.size() != cells:
		return false
	var q_values := PackedFloat32Array()
	q_values.resize(cells)
	for i in range(cells):
		var ey_value: float = ey_values[i]
		var ei_value: float = ei_values[i]
		if is_nan(ey_value) or is_inf(ey_value) or is_nan(ei_value) or is_inf(ei_value):
			return false
		var q_value: float = ey_value * ey_value + ei_value * ei_value
		if is_nan(q_value) or is_inf(q_value):
			return false
		q_values[i] = q_value
		if is_nan(q_values[i]) or is_inf(q_values[i]):
			return false
	if _rd == null or not _ey.is_valid() or not _ei.is_valid() or not _q.is_valid() \
			or not _vel.is_valid() or not _rho.is_valid() or not _scratch.is_valid():
		return false

	var zero4 := PackedByteArray()
	zero4.resize(cells * 4)
	var zero16 := PackedByteArray()
	zero16.resize(cells * 16)
	_rd.buffer_update(_ey, 0, cells * 4, ey_values.to_byte_array())
	_rd.buffer_update(_ei, 0, cells * 4, ei_values.to_byte_array())
	_rd.buffer_update(_q, 0, cells * 4, q_values.to_byte_array())
	_rd.buffer_update(_rho, 0, cells * 4, zero4)
	_rd.buffer_update(_vel, 0, cells * 16, zero16)
	_rd.buffer_update(_scratch, 0, cells * 16, zero16)
	_pending = PackedFloat32Array()
	_step = 0
	_t = 0.0
	return true


# Restore a previously captured full field and its exact simulation clock.
# This is explicit/default-off: only a session owner that already holds raw
# EY/EI bytes may invoke it. Validation remains side-effect free until the
# field itself and its clock metadata are both known valid.
func restore_full_field(ey_values: PackedFloat32Array, ei_values: PackedFloat32Array,
		step_value: int, time_value: float) -> bool:
	if step_value < 0 or is_nan(time_value) or is_inf(time_value) or time_value < 0.0:
		return false
	var expected_time: float = float(step_value) * dt
	if absf(time_value - expected_time) > maxf(1.0e-6, absf(expected_time) * 1.0e-6):
		return false
	if not seed_full_field(ey_values, ei_values):
		return false
	_step = step_value
	_t = time_value
	return true
# Blend an incoming complete field into the canonical channels without
# reallocating GPU resources or resetting any PDE state. This path is
# explicit/default-off: no bridge command or automatic caller invokes it.
func blend_full_field(ey_values: PackedFloat32Array, ei_values: PackedFloat32Array,
		retained_weight: float) -> bool:
	var cells: int = grid_n * grid_n * grid_n
	if is_nan(retained_weight) or is_inf(retained_weight) \
			or retained_weight < 0.0 or retained_weight > 1.0:
		return false
	if ey_values.size() != cells or ei_values.size() != cells:
		return false
	if _rd == null or not _ey.is_valid() or not _ei.is_valid() or not _q.is_valid() \
			or not _vel.is_valid() or not _rho.is_valid() or not _scratch.is_valid():
		return false

	# Validate both incoming channels before flushing any pending deposits or
	# touching a canonical GPU buffer. Derived q is validated below from the
	# actual mixed channels, which is the only q value this API writes.
	for i in range(cells):
		var ey_value: float = ey_values[i]
		var ei_value: float = ei_values[i]
		if is_nan(ey_value) or is_inf(ey_value) or is_nan(ei_value) or is_inf(ei_value):
			return false

	# Preflight the current field and pending deposits on CPU. This keeps the
	# eventual flush after every input/output validation and makes rejection
	# observationally side-effect free even with pending deposits.
	var current_ey: PackedFloat32Array = _rd.buffer_get_data(
		_ey, 0, cells * 4).to_float32_array()
	var current_ei: PackedFloat32Array = _rd.buffer_get_data(
		_ei, 0, cells * 4).to_float32_array()
	if _pending.size() % 6 != 0:
		return false
	var pending_index: int = 0
	while pending_index < _pending.size():
		for pending_offset in range(6):
			var pending_value: float = _pending[pending_index + pending_offset]
			if is_nan(pending_value) or is_inf(pending_value):
				return false
		_scatter(current_ey, current_ei, _pending[pending_index],
			_pending[pending_index + 1], _pending[pending_index + 2],
			_pending[pending_index + 3], _pending[pending_index + 4],
			_pending[pending_index + 5])
		pending_index += 6
	var mixed_ey := PackedFloat32Array()
	var mixed_ei := PackedFloat32Array()
	var q_values := PackedFloat32Array()
	mixed_ey.resize(cells)
	mixed_ei.resize(cells)
	q_values.resize(cells)
	var incoming_weight: float = 1.0 - retained_weight
	for i in range(cells):
		var current_ey_value: float = current_ey[i]
		var current_ei_value: float = current_ei[i]
		if is_nan(current_ey_value) or is_inf(current_ey_value) \
				or is_nan(current_ei_value) or is_inf(current_ei_value):
			return false
		var mixed_ey_value: float = retained_weight * current_ey_value \
				+ incoming_weight * ey_values[i]
		var mixed_ei_value: float = retained_weight * current_ei_value \
				+ incoming_weight * ei_values[i]
		var q_value: float = mixed_ey_value * mixed_ey_value \
				+ mixed_ei_value * mixed_ei_value
		if is_nan(mixed_ey_value) or is_inf(mixed_ey_value) \
				or is_nan(mixed_ei_value) or is_inf(mixed_ei_value) \
				or is_nan(q_value) or is_inf(q_value):
			return false
		mixed_ey[i] = mixed_ey_value
		mixed_ei[i] = mixed_ei_value
		q_values[i] = q_value
		if is_nan(q_values[i]) or is_inf(q_values[i]):
			return false

	# All input, pending values, mixed channels, and q values are valid now.
	# Flush the real pending deposits only after this complete validation.
	_flush_pending()
	# Only the canonical channels and derived q are written. PDE buffers,
	# clocks, and all RIDs remain intact; validated pending deposits are
	# drained before the blend.
	_rd.buffer_update(_ey, 0, cells * 4, mixed_ey.to_byte_array())
	_rd.buffer_update(_ei, 0, cells * 4, mixed_ei.to_byte_array())
	_rd.buffer_update(_q, 0, cells * 4, q_values.to_byte_array())
	return true


func _flush_pending() -> void:
	if _pending.size() == 0:
		return
	var cells: int = grid_n * grid_n * grid_n
	var ey := _rd.buffer_get_data(_ey, 0, cells * 4).to_float32_array()
	var ei := _rd.buffer_get_data(_ei, 0, cells * 4).to_float32_array()
	var i := 0
	while i < _pending.size():
		_scatter(ey, ei, _pending[i], _pending[i + 1], _pending[i + 2],
			_pending[i + 3], _pending[i + 4], _pending[i + 5])
		i += 6
	_rd.buffer_update(_ey, 0, cells * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, cells * 4, ei.to_byte_array())
	_pending = PackedFloat32Array()

func _spline_w(t: float) -> float:

	var at := absf(t)
	if at <= 0.5:
		return 0.75 - at * at
	if at <= 1.5:
		var d := 1.5 - at
		return 0.5 * d * d
	return 0.0


func _scatter(ey: PackedFloat32Array, ei: PackedFloat32Array, x: float, y: float, z: float,
		cy: float, ci: float, sigma: float) -> void:
	var n := grid_n
	var gx: float = (x / extent.x + 1.0) * 0.5 * float(n)
	var gy: float = (y / extent.y + 1.0) * 0.5 * float(n)
	var gz: float = (z / extent.z + 1.0) * 0.5 * float(n)
	var fx: float = gx - floor(gx + 0.5)
	var fy: float = gy - floor(gy + 0.5)
	var fz: float = gz - floor(gz + 0.5)
	var i0 := int(floor(gx + 0.5)) % n
	var j0 := int(floor(gy + 0.5)) % n
	var k0 := int(floor(gz + 0.5)) % n
	# Per-axis weights. The TSC kernel is a partition of unity ONLY for
	# sigma == 1.0 (the Stage-0 pin, kept bit-identical). For sigma != 1.0
	# the rescaled argument breaks the partition of unity over the fixed
	# 27-cell stencil, so we renormalize each axis to sum 1.0 — this
	# guarantees Σ(scatter) == cy/ci exactly for ANY sigma (charge-exact),
	# and larger sigma yields a flatter ("broader") envelope across the
	# same cells. sigma semantics contract: "renormalized flatness".
	var wx := PackedFloat32Array()
	var wy := PackedFloat32Array()
	var wz := PackedFloat32Array()
	var sx := 0.0
	var sy := 0.0
	var sz := 0.0
	for d in range(-1, 2):
		var ax: float = _spline_w((fx - float(d)) / sigma)
		var ay: float = _spline_w((fy - float(d)) / sigma)
		var az: float = _spline_w((fz - float(d)) / sigma)
		wx.append(ax)
		wy.append(ay)
		wz.append(az)
		sx += ax
		sy += ay
		sz += az
	var renorm: bool = sigma != 1.0
	for i in range(3):
		if renorm:
			wx[i] = 0.0 if sx == 0.0 else wx[i] / sx
			wy[i] = 0.0 if sy == 0.0 else wy[i] / sy
			wz[i] = 0.0 if sz == 0.0 else wz[i] / sz
	for di in range(3):
		var wi: float = wx[di]
		var ii: int = (i0 + di - 1 + n) % n
		for dj in range(3):
			var wj: float = wy[dj]
			var jj: int = (j0 + dj - 1 + n) % n
			for dk in range(3):
				var wk: float = wz[dk]
				var idx: int = ii * n * n + jj * n + kk(k0, dk - 1, n)
				var w := wi * wj * wk
				ey[idx] += cy * w
				ei[idx] += ci * w


func kk(k0: int, dk: int, n: int) -> int:
	return (k0 + dk + n) % n


# ── readouts ─────────────────────────────────────────────────────────────
func readback_ey_ei() -> Array:
	var cells: int = grid_n * grid_n * grid_n
	var ey := _rd.buffer_get_data(_ey, 0, cells * 4).to_float32_array()
	var ei := _rd.buffer_get_data(_ei, 0, cells * 4).to_float32_array()
	return [ey, ei]


func compute_state() -> Dictionary:
	var cells: int = grid_n * grid_n * grid_n
	var rb := readback_ey_ei()
	var ey: PackedFloat32Array = rb[0]
	var ei: PackedFloat32Array = rb[1]
	var mean_ey := 0.0
	var mean_ei := 0.0
	var max_eps2 := 0.0
	for i in range(cells):
		mean_ey += ey[i]
		mean_ei += ei[i]
		var eps: float = ey[i] - PHI * ei[i]
		max_eps2 = maxf(max_eps2, eps * eps)
	mean_ey /= float(cells)
	mean_ei /= float(cells)
	return {
		"step": _step, "t": _t,
		"mean_ey": mean_ey, "mean_ei": mean_ei, "max_eps2": max_eps2,
	}


func compute_readout() -> Dictionary:
	var rb := readback_ey_ei()
	var ey: PackedFloat32Array = rb[0]
	var ei: PackedFloat32Array = rb[1]
	var cells: int = grid_n * grid_n * grid_n
	var q := PackedFloat32Array()
	var eps2 := PackedFloat32Array()
	q.resize(cells)
	eps2.resize(cells)
	for i in range(cells):
		q[i] = ey[i] * ey[i] + ei[i] * ei[i]
		var eps: float = ey[i] - PHI * ei[i]
		eps2[i] = eps * eps
	return {
		"ey_b64": Marshalls.raw_to_base64(ey.to_byte_array()),
		"ei_b64": Marshalls.raw_to_base64(ei.to_byte_array()),
		"q_b64": Marshalls.raw_to_base64(q.to_byte_array()),
		"eps2_b64": Marshalls.raw_to_base64(eps2.to_byte_array()),
	}


## Projection — top-k attractor readout (the field-read stage).
## q is computed CPU-side from the ey/ei readback (NOT the `_q` GPU buffer,
## which is stale outside steps). Flat index i = gx*N*N + gy*N + gz (x-major,
## matching the `_scatter` ii*n*n + jj*n + kk layout). Physical coords use the
## box map (2*g/(N-1)-1)*extent. Cells sorted by q DESC, ties by flat index ASC.
func compute_projection(k: int) -> Dictionary:
	var cells: int = grid_n * grid_n * grid_n
	if k < 1:
		k = 8
	k = mini(k, 4096)
	if k > cells:
		k = cells
	var rb := readback_ey_ei()
	var ey: PackedFloat32Array = rb[0]
	var ei: PackedFloat32Array = rb[1]
	# O(N*k) top-k scan over {q, i} pairs. k is tiny; N=grid_n^3 = 262144 for
	# the default N=64, so a manual scan beats a full Array sort hands-down.
	var top: Array = []
	top.resize(k)
	for t in range(k):
		top[t] = {"q": -1.0e30, "i": -1}
	for i in range(cells):
		var qv: float = ey[i] * ey[i] + ei[i] * ei[i]
		# Insertion position among the running top-k (kept sorted q DESC).
		var pos: int = k - 1
		while pos >= 0 and (qv > (top[pos]["q"] as float)
				or (qv == (top[pos]["q"] as float) and i < (top[pos]["i"] as int))):
			pos -= 1
		if pos < k - 1:
			# Shift [pos+1, k-1) right, drop the tail.
			var t := k - 1
			while t > pos + 1:
				top[t] = top[t - 1]
				t -= 1
			top[pos + 1] = {"q": qv, "i": i}
	var out: Array = []
	out.resize(k)
	var n := grid_n
	for t in range(k):
		var idx: int = top[t]["i"] as int
		var gx: int = idx / (n * n)
		var rem: int = idx % (n * n)
		var gy: int = rem / n
		var gz: int = rem % n
		out[t] = {
			"i": idx,
			"gx": gx, "gy": gy, "gz": gz,
			"x": (2.0 * float(gx) / float(n - 1) - 1.0) * extent.x,
			"y": (2.0 * float(gy) / float(n - 1) - 1.0) * extent.y,
			"z": (2.0 * float(gz) / float(n - 1) - 1.0) * extent.z,
			"ey": ey[idx], "ei": ei[idx],
			"q": top[t]["q"] as float,
		}
	return {"step": _step, "t": _t, "cells": out}


func _sha256_hex(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	if context.start(HashingContext.HASH_SHA256) != OK:
		return ""
	if context.update(bytes) != OK:
		return ""
	return context.finish().hex_encode()


func accept_qi_snapshot(obj: Dictionary) -> Dictionary:
	if str(obj.get("schema", "")) != QI_SCHEMA:
		return {"ok": false, "error": "unsupported Qi schema"}
	var revision: int = int(obj.get("revision", -1))
	var expected_sha256: String = str(obj.get("state_sha256", "")).to_lower()
	var contract_sha256: String = str(obj.get("contract_sha256", "")).to_lower()
	if revision < 0 or expected_sha256.length() != 64 or contract_sha256.length() != 64:
		return {"ok": false, "error": "invalid Qi metadata"}
	var encoded: String = str(obj.get("state_f32_base64", ""))
	var bytes: PackedByteArray = Marshalls.base64_to_raw(encoded)
	if bytes.size() != QI_STATE_BYTES:
		return {"ok": false, "error": "Qi state byte length mismatch"}
	var actual_sha256: String = _sha256_hex(bytes)
	if actual_sha256 == "" or actual_sha256 != expected_sha256:
		return {"ok": false, "error": "Qi state SHA-256 mismatch"}
	for offset in range(0, QI_STATE_BYTES, 4):
		var value: float = bytes.decode_float(offset)
		if is_nan(value) or is_inf(value):
			return {"ok": false, "error": "non-finite Qi state"}
	if revision < _qi_revision:
		return {"ok": false, "error": "stale Qi revision"}
	if revision == _qi_revision:
		if expected_sha256 != _qi_state_sha256 or contract_sha256 != _qi_contract_sha256:
			return {"ok": false, "error": "conflicting Qi revision"}
		return qi_state_info().merged({"idempotent": true})
	_qi_state = bytes.duplicate()
	_qi_revision = revision
	_qi_state_sha256 = actual_sha256
	_qi_contract_sha256 = contract_sha256
	return qi_state_info().merged({"idempotent": false})


func qi_state_info() -> Dictionary:
	return {
		"ok": true,
		"cmd": "qi_state",
		"schema": QI_SCHEMA,
		"available": _qi_state.size() == QI_STATE_BYTES,
		"revision": _qi_revision,
		"state_sha256": _qi_state_sha256,
		"contract_sha256": _qi_contract_sha256,
		"state_bytes": _qi_state.size(),
		"mode_count": QI_MODE_COUNT,
		"wave_mode_count": QI_WAVE_MODE_COUNT,
		"scale_count": QI_SCALE_COUNT,
		"plane_count": QI_PLANE_COUNT,
	}


func compute_qi_projection(k: int) -> Dictionary:
	if _qi_state.size() != QI_STATE_BYTES:
		return {"ok": false, "cmd": "qi_project", "error": "Qi state unavailable"}
	if k < 1:
		k = 8
	k = mini(k, QI_WAVE_MODE_COUNT)
	var top: Array = []
	top.resize(k)
	for t in range(k):
		top[t] = {"q": -1.0e30, "mode": -1, "p0": 0.0, "p1": 0.0}
	for mode in range(QI_WAVE_MODE_COUNT):
		var base: int = mode * QI_PLANE_COUNT * 4
		var p0: float = _qi_state.decode_float(base)
		var p1: float = _qi_state.decode_float(base + 4)
		var q: float = p0 * p0 + p1 * p1
		var pos: int = k - 1
		while pos >= 0 and (q > float(top[pos]["q"]) \
				or (q == float(top[pos]["q"]) and mode < int(top[pos]["mode"]))):
			pos -= 1
		if pos < k - 1:
			var t: int = k - 1
			while t > pos + 1:
				top[t] = top[t - 1]
				t -= 1
			top[pos + 1] = {"q": q, "mode": mode, "p0": p0, "p1": p1}
	return qi_state_info().merged({"cmd": "qi_project", "modes": top}, true)


func _clear_qi_snapshot() -> void:
	_qi_state = PackedByteArray()
	_qi_revision = -1
	_qi_state_sha256 = ""
	_qi_contract_sha256 = ""


func _clear_field() -> void:
	var cells: int = grid_n * grid_n * grid_n
	var zero := PackedByteArray()
	zero.resize(cells * 4)
	_rd.buffer_update(_ey, 0, cells * 4, zero)
	_rd.buffer_update(_ei, 0, cells * 4, zero)
	_rd.buffer_update(_q, 0, cells * 4, zero)
	_rd.buffer_update(_rho, 0, cells * 4, zero)
	var zero16 := PackedByteArray()
	zero16.resize(cells * 16)
	_rd.buffer_update(_vel, 0, cells * 16, zero16)
	# Keep the descriptor-bound scratch RID stable across clear.
	_rd.buffer_update(_scratch, 0, cells * 16, zero16)
	_pending = PackedFloat32Array()
	_step = 0
	_t = 0.0


func write_snapshot(label: String) -> String:
	var rb := readback_ey_ei()
	var cells: int = grid_n * grid_n * grid_n
	var q := PackedFloat32Array()
	var eps2 := PackedFloat32Array()
	q.resize(cells)
	eps2.resize(cells)
	var ey: PackedFloat32Array = rb[0]
	var ei: PackedFloat32Array = rb[1]
	for i in range(cells):
		q[i] = ey[i] * ey[i] + ei[i] * ei[i]
		var eps: float = ey[i] - PHI * ei[i]
		eps2[i] = eps * eps
	var d := {
		"N": grid_n, "dt": dt, "step": _step, "t": _t,
		"extent": [extent.x, extent.y, extent.z],
		"ey_b64": Marshalls.raw_to_base64(ey.to_byte_array()),
		"ei_b64": Marshalls.raw_to_base64(ei.to_byte_array()),
		"q_b64": Marshalls.raw_to_base64(q.to_byte_array()),
		"eps2_b64": Marshalls.raw_to_base64(eps2.to_byte_array()),
	}
	var path := "res://_diag/mind_engine_snapshot_%d_%s.json" % [int(Time.get_unix_time_from_system()), label]
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		return "write failed: " + path
	f.store_string(JSON.stringify(d))
	f.close()
	return path


# ── TCP bridge ───────────────────────────────────────────────────────────
func _poll_bridge() -> void:
	if _server == null:
		return
	while _server.is_connection_available():
		var p := _server.take_connection()
		if p != null:
			_peers.append(p)
			_peer_buf[p] = PackedByteArray()
	var dead: Array[StreamPeerTCP] = []
	for p in _peers:
		if p.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			dead.append(p)
			continue
		var avail := p.get_available_bytes()
		if avail <= 0:
			continue
		var data: Array = p.get_data(avail)
		if data[0] != OK:
			continue
		var acc: PackedByteArray = _peer_buf[p]
		acc.append_array(data[1])
		while true:
			var nl := acc.find(10)
			if nl < 0:
				break
			var line := acc.slice(0, nl).get_string_from_utf8()
			acc = acc.slice(nl + 1)
			var resp := _handle_line(line)
			if resp != "":
				p.put_data((resp + "\n").to_utf8_buffer())
		_peer_buf[p] = acc
	for d in dead:
		_peers.erase(d)
		_peer_buf.erase(d)


func _handle_line(line: String) -> String:
	var obj: Variant = JSON.parse_string(line)
	if obj == null or not (obj is Dictionary):
		return JSON.stringify({"ok": false, "error": "bad json"})
	var cmd: String = str(obj.get("cmd", ""))
	match cmd:
		"ping":
			return JSON.stringify({"ok": true, "cmd": "ping", "step": _step, "t": _t})
		"clear":
			_clear_field()
			return JSON.stringify({"ok": true, "cmd": "clear"})
		"deposit":
			deposit(float(obj.get("x", 0.0)), float(obj.get("y", 0.0)),
				float(obj.get("z", 0.0)), float(obj.get("cy", 0.0)),
				float(obj.get("ci", 0.0)), float(obj.get("sigma", 1.0)))
			return JSON.stringify({"ok": true, "cmd": "deposit", "pending": _pending.size() / 6})
		"step":
			var n: int = int(obj.get("n", 1))
			step_n(n)
			return JSON.stringify({"ok": true, "cmd": "step", "step": _step, "t": _t})
		"state":
			var st := compute_state()
			st["ok"] = true
			st["cmd"] = "state"
			return JSON.stringify(st)
		"readout":
			var ro := compute_readout()
			ro["ok"] = true
			ro["cmd"] = "readout"
			ro["step"] = _step
			ro["t"] = _t
			return JSON.stringify(ro)
		"project":
			var proj_k: int = 8
			if obj.has("k"):
				var kv: Variant = obj["k"]
				if kv is int or kv is float:
					proj_k = int(kv)
			var pr := compute_projection(proj_k)
			pr["ok"] = true
			pr["cmd"] = "project"
			return JSON.stringify(pr)
		"snapshot":
			return JSON.stringify({"ok": true, "cmd": "snapshot",
				"path": write_snapshot(str(obj.get("label", "")))})
		"qi_snapshot":
			var qi_reply: Dictionary = accept_qi_snapshot(obj)
			if bool(qi_reply.get("ok", false)):
				qi_reply["cmd"] = "qi_snapshot"
			return JSON.stringify(qi_reply)
		"qi_state":
			return JSON.stringify(qi_state_info())
		"qi_project":
			var qi_k: int = 8
			if obj.has("k") and (obj["k"] is int or obj["k"] is float):
				qi_k = int(obj["k"])
			return JSON.stringify(compute_qi_projection(qi_k))
		"qi_clear":
			_clear_qi_snapshot()
			return JSON.stringify({"ok": true, "cmd": "qi_clear"})
		_:
			return JSON.stringify({"ok": false, "error": "unknown cmd: " + cmd})


func _exit_tree() -> void:
	for peer in _peers:
		peer.disconnect_from_host()
	_peers.clear()
	_peer_buf.clear()
	if _server != null:
		_server.stop()
		_server = null
	if _rd != null:
		for rid in [_us, _fi_fallback, _scratch, _rho, _vel, _q, _ei, _ey, _pipe, _shader]:
			if rid.is_valid():
				_rd.free_rid(rid)
		_rd.free()
		_rd = null
