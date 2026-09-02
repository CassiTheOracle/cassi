extends Node
## Frozen PWA0-PWA8 focused fixture: the shipped decoupled authority, pure
## preview, deterministic sphere→ring Apply, cache/render publication,
## idempotency, one step, and exact automatic Undo.

const MAX_WAIT_FRAMES := 600
const PARTICLE_COUNT := 96
const EXPECTED_PROGRAM_DIGEST := "858acbfe6298fd3526fdb7785280d23ec1f22fe6a402adcb1a52eb3b6a8c6010"

var _sim: Node
var _checks := 0
var _failures := 0
var _started_ms := 0

func _ready() -> void:
	_started_ms = Time.get_ticks_msec()
	print("[ParticleWorldAgent] frozen PWA0-PWA8; seed=1729 actual_grid=64 particles=96 decoupled=true boxless=true")
	_sim = Node3D.new()
	_sim.name = "ParticleWorldCassiSim"
	_sim.set_script(load("res://scripts/cassi_sim.gd"))
	_sim.playing = false
	_sim.grid_N = 64
	_sim.N_particles = PARTICLE_COUNT
	_sim.dt = 0.002
	_sim.cluster_radius = 4.0
	_sim.num_clusters = 1
	_sim.cluster_separation = 0.0
	_sim.initial_condition = 2
	_sim.initial_radius_fraction = 0.25
	_sim.source_strength = 0.0
	_sim.black_holes_enabled = false
	_sim.particle_merge = false
	_sim.meshless_mode = true
	_sim.meshless_gravity = true
	_sim.boxless_field = true
	_sim.gridless_physics = true
	_sim.dual_grid = false
	_sim.multi_rung_seed = false
	_sim.tracking_envelope = false
	_sim.home_window_enabled = false
	_sim.physics_decoupled = true
	_sim.ic_seed = 1729
	_sim.suppress_readbacks = true
	_sim.box_aspect = Vector3.ONE
	add_child(_sim)
	await _wait_for_ready()
	if _failures == 0:
		_run_gates()
	_finish()

func _wait_for_ready() -> void:
	for _frame in range(MAX_WAIT_FRAMES):
		await get_tree().process_frame
		var engine: Variant = _sim.get("_physics_engine")
		if bool(_sim.get("_shaders_ready")) and bool(_sim.get("_decoupled_active")) \
				and engine != null and engine.workbench_ready():
			_check("PWA0: decoupled authority ready", true)
			return
	_check("PWA0: decoupled authority ready", false, "readiness timeout")

func _program(request_id := "pwa-ring-0001", radius := 2.0) -> Dictionary:
	return {
		"schema": "cassi.particle-program.v1",
		"operation": "arrange",
		"selection": {
			"type": "sphere",
			"center": [0.0, 0.0, 0.0],
			"radius": 100.0,
		},
		"target": {
			"type": "ring",
			"center": [0.0, 0.0, 0.0],
			"normal": [0.0, 1.0, 0.0],
			"radius": radius,
			"phase": 0.0,
		},
		"motion": {"type": "exact", "velocity_policy": "zero"},
		"constraints": {
			"maximum_particles": PARTICLE_COUNT,
			"maximum_displacement": 100.0,
			"maximum_speed": 10.0,
		},
		"source": {"kind": "explicit"},
		"request_id": request_id,
	}
func _run_gates() -> void:
	var status: Dictionary = _sim.workbench_status()
	_check("PWA0: ordinary boxless decoupled authority ready", _ok(status) and status.state.authority == "decoupled_engine" and bool(status.state.authority_ready) and bool(status.state.boxless_active), str(status))
	var before: Dictionary = _sim.call("_workbench_read_buffers")
	var before_digest := _digest(before)
	var masses := _mass_bytes(before.pos)

	var wire_program: Dictionary = JSON.parse_string(JSON.stringify(_program()))
	var preview: Dictionary = _sim.workbench_preview(wire_program)
	_check("PWA2: JSON transport preserves integer constraints", _ok(preview), str(preview))
	var after_preview: Dictionary = _sim.call("_workbench_read_buffers")
	_check("PWA3: preview is pure", _ok(preview) and _digest(after_preview) == before_digest, str(preview))
	_check("PWA2: Python/Godot canonical digest parity", str(preview.get("program_digest", "")) == EXPECTED_PROGRAM_DIGEST, str(preview.get("program_digest", "")))
	_check("PWA4: exact target count and bounded ghost sample", int(preview.get("affected_count", -1)) == PARTICLE_COUNT and preview.get("target_sample", []).size() == PARTICLE_COUNT, str(preview))

	var applied: Dictionary = _sim.workbench_apply(_program())
	var after_apply: Dictionary = _sim.call("_workbench_read_buffers")
	_check("PWA5: authoritative GPU ring Apply", _ok(applied) and str(applied.get("backend", "")) == "authoritative_gpu" and str(applied.commands[0].backend) == "authoritative_gpu" and _is_ring(after_apply.pos, 2.0), str(applied))
	_check("PWA5: mass bytes preserved", _mass_bytes(after_apply.pos) == masses)
	_check("PWA5: particle-only Apply preserves grid compatibility buffers", before.ey.to_byte_array() == after_apply.ey.to_byte_array() and before.ei.to_byte_array() == after_apply.ei.to_byte_array() and before.q.to_byte_array() == after_apply.q.to_byte_array() and before.vel.to_byte_array() == after_apply.vel.to_byte_array(), "grid compatibility bytes unchanged")
	_check("PWA6: exact motion zeroes velocity and acceleration caches", _xyz_zero(after_apply.pvel) and _all_zero(after_apply.acc))
	_check("PWA6: previous/render snapshots refreshed", _render_snapshots_match(after_apply.pos))
	var engine: Variant = _sim.get("_physics_engine")
	_check("PWA6: gravity cache invalidated", engine != null and bool(engine.get("_grav_warmup")))

	var apply_digest := _digest(after_apply)
	var duplicate: Dictionary = _sim.workbench_apply(_program())
	_check("PWA7: duplicate request is idempotent", _ok(duplicate) and bool(duplicate.get("duplicate", false)) and _digest(_sim.call("_workbench_read_buffers")) == apply_digest, str(duplicate))
	var conflict: Dictionary = _sim.workbench_apply(_program("pwa-ring-0001", 3.0))
	_check("PWA7: conflicting duplicate rejects without mutation", not _ok(conflict) and _digest(_sim.call("_workbench_read_buffers")) == apply_digest, str(conflict))
	var unsafe := _program("pwa-oob-0001", 1000.0)
	var rejected: Dictionary = _sim.workbench_preview(unsafe)
	_check("PWA7: out-of-bounds target rejects without mutation", not _ok(rejected) and _digest(_sim.call("_workbench_read_buffers")) == apply_digest, str(rejected))

	var before_step := int(_sim.get("_step_count"))
	var stepped: Dictionary = _sim.workbench_step(1)
	_check("PWA8: one explicit decoupled step", _ok(stepped) and int(_sim.get("_step_count")) == before_step + 1 and not _sim.playing, str(stepped))
	var undone: Dictionary = _sim.workbench_undo()
	var after_undo: Dictionary = _sim.call("_workbench_read_buffers")
	_check("PWA8: exact automatic Undo restores authority and clock", _ok(undone) and _digest(after_undo) == before_digest and int(_sim.get("_step_count")) == 0, str(undone))
	_check("PWA8: Undo republishes render snapshots", _render_snapshots_match(after_undo.pos))

func _mass_bytes(pos: PackedFloat32Array) -> PackedByteArray:
	var masses := PackedFloat32Array()
	masses.resize(pos.size() / 4)
	for particle in range(masses.size()):
		masses[particle] = pos[particle * 4 + 3]
	return masses.to_byte_array()

func _is_ring(pos: PackedFloat32Array, radius: float) -> bool:
	var live := 0
	for particle in range(pos.size() / 4):
		var offset := particle * 4
		if pos[offset + 3] <= 0.0:
			continue
		live += 1
		var point := Vector3(pos[offset], pos[offset + 1], pos[offset + 2])
		if absf(point.y) > 2e-4 or absf(Vector2(point.x, point.z).length() - radius) > 2e-4:
			return false
	return live == PARTICLE_COUNT

func _xyz_zero(values: PackedFloat32Array) -> bool:
	for particle in range(values.size() / 4):
		var offset := particle * 4
		if values[offset] != 0.0 or values[offset + 1] != 0.0 or values[offset + 2] != 0.0:
			return false
	return true

func _all_zero(values: PackedFloat32Array) -> bool:
	for value in values:
		if value != 0.0:
			return false
	return true

func _render_snapshots_match(pos: PackedFloat32Array) -> bool:
	var rd: RenderingDevice = _sim.get("_rd")
	if rd == null:
		return false
	var previous := rd.buffer_get_data(_sim.get("_pos_prev_buf")).to_float32_array()
	var rendered := rd.buffer_get_data(_sim.get("_pos_render_buf")).to_float32_array()
	return previous.to_byte_array() == pos.to_byte_array() and rendered.to_byte_array() == pos.to_byte_array()

func _digest(buffers: Dictionary) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	for key in ["ey", "ei", "q", "vel", "pos", "pvel", "acc"]:
		var values: PackedFloat32Array = buffers[key]
		context.update(values.to_byte_array())
	return context.finish().hex_encode()

func _ok(value: Variant) -> bool:
	return value is Dictionary and bool(value.get("ok", false))

func _check(label: String, passed: bool, detail := "") -> void:
	_checks += 1
	if passed:
		print("PASS %s%s" % [label, (" — " + detail) if detail != "" else ""])
	else:
		_failures += 1
		print("FAIL %s%s" % [label, (" — " + detail) if detail != "" else ""])

func _finish() -> void:
	print("[ParticleWorldAgent] %d checks, %d failures, elapsed=%d ms" % [_checks, _failures, Time.get_ticks_msec() - _started_ms])
	get_tree().quit(0 if _failures == 0 else 1)
