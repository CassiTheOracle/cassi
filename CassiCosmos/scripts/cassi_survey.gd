extends Node
## Cassi space-sim survey exporter — snapshots the LIVE sim state to disk
## for the theory repo's Python pipelines (P(k) log-periodic search,
## cascade analysis). Reads the sim's RD buffers directly.
##
## LOW RATE BY DESIGN: the default 10 s cadence is for statistical
## pipelines (downsampled field + particle snapshots), NOT for movie
## frames — every dump is a full-grid readback that stalls the global
## RenderingDevice (buffer_get_data self-syncs). Do not lower the cadence
## into the sub-second range in a live/render loop.
##
## Add this node under the sim (a sibling of the CassiSim node, or a child
## of it). Two triggers, either/both:
##   - a wall-clock cadence (`survey_interval_seconds`, default 10.0);
##   - the `survey_key` keypress (default S).
## Harness scenes may call take_snapshot() directly (see
## scripts/verify_survey.gd) — that path ignores `enabled`.
##
## Output: <output_root>/survey_<YYYYMMDD_HHMMSS>/
##   meta.json     — grid_N, extents, particle_count, step/time, arm mode
##   field_ey.raw  — float32 little-endian, grid_N³ values (EY field)
##   field_ei.raw  — float32 little-endian, grid_N³ values (EI field)
##   field_q.raw   — float32 little-endian, grid_N³ values (Qi coherence,
##                   written only when the buffer exists)
##   particles.raw — float32 little-endian, xyz per particle (positions
##                   only; the pos buffer's per-particle vec4 is x,y,z,mass)

@export var sim_path: NodePath = NodePath("../CassiSim")
## Wall-clock cadence in seconds between automatic snapshots (default 10 s —
## LOW rate by design for statistical pipelines; ≤ 0 disables the cadence).
@export var survey_interval_seconds: float = 10.0
## Keypress that triggers a snapshot (default KEY_S).
@export var survey_key: Key = KEY_S
## Output root directory (survey_<timestamp>/ subdirs are created here).
@export var output_root: String = "res://_diag"
## Master switch for the automatic triggers (_process cadence + keypress).
## Explicit take_snapshot() calls (harness scenes) bypass this.
@export var enabled: bool = true
## Write particles.raw (positions only). Particle dumps can be large; toggle
## off for field-only surveys.
@export var dump_particles: bool = true

var _sim: Node = null
var _t: float = 0.0
var _last_dir: String = ""


func _ready() -> void:
	# Resolve the sim: a child-of-sim placement, else the sim_path (default
	# "../CassiSim" works for a sibling of the CassiSim node under a common
	# parent).
	if get_parent() != null and get_parent().get("_field_ey") != null:
		_sim = get_parent()
	elif not sim_path.is_empty():
		_sim = get_node_or_null(sim_path)
	if _sim == null:
		push_warning("[CassiSurvey] sim not found (path '%s') — survey idle" % [sim_path])
	elif _sim.get("_field_ey") == null:
		push_warning("[CassiSurvey] sim has no _field_ey — survey idle")


func _process(delta: float) -> void:
	if not enabled or _sim == null:
		return
	_t += delta
	if survey_interval_seconds > 0.0 and _t >= survey_interval_seconds:
		_t = 0.0
		take_snapshot()


func _unhandled_input(event: InputEvent) -> void:
	if not enabled:
		return
	if event is InputEventKey and event.pressed and event.keycode == survey_key:
		take_snapshot()
		get_viewport().set_input_as_handled()


## Public dump entry point — writes one snapshot regardless of `enabled`.
## Returns the meta Dictionary (empty on failure). The snapshot dir is
## also available via get_last_dir().
func take_snapshot() -> Dictionary:
	if _sim == null:
		push_warning("[CassiSurvey] no sim — skipping snapshot")
		return {}
	var ey_rid = _sim.get("_field_ey")
	if ey_rid == null or not ey_rid.is_valid():
		push_warning("[CassiSurvey] sim field buffers not ready — skipping snapshot")
		return {}

	var N: int = int(_sim.grid_N)
	var nc: int = N * N * N
	var dir_path := "%s/survey_%s" % [output_root, _timestamp()]
	_ensure_dir(dir_path)

	var meta := _collect_meta(N)
	meta["dir_path"] = dir_path

	# Field buffers: ey/ei always; q when valid.
	var ey: PackedFloat32Array = _read_float_buffer(_sim._field_ey, nc)
	var ei: PackedFloat32Array = _read_float_buffer(_sim._field_ei, nc)
	_write_raw("%s/field_ey.raw" % dir_path, ey.to_byte_array())
	_write_raw("%s/field_ei.raw" % dir_path, ei.to_byte_array())
	meta["field_ey_bytes"] = ey.size() * 4
	meta["field_ei_bytes"] = ei.size() * 4
	meta["field_q"] = false

	var q_rid = _sim.get("_field_q")
	if q_rid != null and q_rid.is_valid():
		var q: PackedFloat32Array = _read_float_buffer(_sim._field_q, nc)
		_write_raw("%s/field_q.raw" % dir_path, q.to_byte_array())
		meta["field_q"] = true
		meta["field_q_bytes"] = q.size() * 4

	# Particles: positions only (x,y,z per particle; skip the mass w).
	if dump_particles and _sim.get("_pos_buf") != null and _sim._pos_buf.is_valid():
		var np: int = int(_sim.N_particles)
		var pf: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
		if pf.size() >= np * 4:
			var xyz := PackedFloat32Array()
			xyz.resize(np * 3)
			for i in range(np):
				xyz[i * 3]     = pf[i * 4]
				xyz[i * 3 + 1] = pf[i * 4 + 1]
				xyz[i * 3 + 2] = pf[i * 4 + 2]
			_write_raw("%s/particles.raw" % dir_path, xyz.to_byte_array())
			meta["particles_written"] = np
		else:
			push_warning("[CassiSurvey] pos readback too small (%d bytes) — particles skipped" % pf.size())
			meta["particles_written"] = 0

	# meta.json last so a partially-written snapshot is never misread.
	_write_text("%s/meta.json" % dir_path, JSON.stringify(meta))
	_last_dir = dir_path

	var gm: Variant = meta.get("gravity_mode_name", "?")
	print("[CassiSurvey] snapshot -> %s (grid=%d³ particles=%d step=%d t=%.3f arm=%s)" % [
		dir_path, N, meta.get("particle_count", 0), meta.get("step", 0),
		meta.get("time", 0.0), gm])
	return meta


func get_last_dir() -> String:
	return _last_dir


# ═══════════════════════════════════════════════════════════════════════
# Internals
# ═══════════════════════════════════════════════════════════════════════

func _read_float_buffer(rid: RID, count: int) -> PackedFloat32Array:
	return _sim._rd.buffer_get_data(rid, 0, count * 4).to_float32_array()


func _collect_meta(N: int) -> Dictionary:
	var meta := {
		"grid_N": N,
		"particle_count": int(_sim.N_particles),
		"step": int(_sim._step_count),
		"time": float(_sim._time),
		"dt": float(_sim.dt),
		"meshless_mode": bool(_sim.meshless_mode),
		"timestamp": _timestamp(),
	}
	var gm: int = int(_sim.gravity_mode)
	meta["gravity_mode"] = gm
	var names := ["River", "Heuristic", "Plummer reference", "River self", "RealSim"]
	meta["gravity_mode_name"] = names[gm] if gm >= 0 and gm < names.size() else "?"
	var e: Vector3 = _sim._extents()
	meta["extents"] = {"x": e.x, "y": e.y, "z": e.z}
	return meta


func _timestamp() -> String:
	var d := Time.get_date_string_from_system()
	var t := Time.get_time_string_from_system()
	return "%s_%s" % [d.replace("-", ""), t.replace(":", "")]


func _ensure_dir(dir_path: String) -> void:
	var g := ProjectSettings.globalize_path(dir_path)
	if not DirAccess.dir_exists_absolute(g):
		var err := DirAccess.make_dir_recursive_absolute(g)
		if err != OK:
			push_warning("[CassiSurvey] make_dir %s failed (err %d)" % [g, err])


func _write_raw(path: String, bytes: PackedByteArray) -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path(path), FileAccess.WRITE)
	if f == null:
		push_warning("[CassiSurvey] cannot open %s (err %d)" % [path, FileAccess.get_open_error()])
		return
	f.store_buffer(bytes)
	f.close()


func _write_text(path: String, text: String) -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path(path), FileAccess.WRITE)
	if f == null:
		push_warning("[CassiSurvey] cannot open %s (err %d)" % [path, FileAccess.get_open_error()])
		return
	f.store_string(text)
	f.close()
