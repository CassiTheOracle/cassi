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
##
## Coordinates are physical: box [-extent, extent]^3. Deposits scatter with
## a TSC kernel (separable quadratic spline, partition of unity, 27 cells),
## added to EY/EI only (velocity untouched). The field state is the truth;
## nothing is written to disk except explicit snapshots.

const PHI := 1.618033988749895

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
var _pc := PackedFloat32Array()
var _step := 0
var _t := 0.0
var _server: TCPServer
var _peers: Array[StreamPeerTCP] = []
var _peer_buf: Dictionary = {}
var _pending := PackedFloat32Array()


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
	# PDE double-buffer scratch (vec4 per cell — pass A writes the new
	# field here, pass B copies to the canonical buffers; read/write
	# buffers never alias, so the 19-point stencil is race-free)
	_scratch = _rd.storage_buffer_create(cells * 16)
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
		_:
			return JSON.stringify({"ok": false, "error": "unknown cmd: " + cmd})
