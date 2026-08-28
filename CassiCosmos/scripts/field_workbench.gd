class_name FieldWorkbench
extends RefCounted

const SCHEMA_VERSION := 2
const OP_DEPOSIT := "deposit"
const OP_ALIGN := "align"
const OP_IMPULSE := "impulse"
const PHI := 1.618033988749895
const PHI_INV2 := 0.3819660112501051

var _host: Object
var _log: Array[Dictionary] = []
var _queued: Array[Dictionary] = []
var _next_id := 1
var _baseline: Dictionary = {}
var _checkpoint: Dictionary = {}
var _last_error := ""

func _init(host: Object = null) -> void:
	_host = host

func last_error() -> String:
	return _last_error

func command_log() -> Array[Dictionary]:
	return _log.duplicate(true)

func queued_commands() -> Array[Dictionary]:
	return _queued.duplicate(true)

func clear_command_log() -> void:
	_log.clear()
	_next_id = 1

func invalidate_state() -> void:
	_queued.clear()
	_log.clear()
	_baseline.clear()
	_checkpoint.clear()
	_next_id = 1

func _fail(error: String, extra: Dictionary = {}) -> Dictionary:
	_last_error = error
	var result := {"ok": false, "error": error}
	for key in extra:
		result[key] = extra[key]
	return result

func _ok(extra: Dictionary = {}) -> Dictionary:
	_last_error = ""
	var result := {"ok": true}
	for key in extra:
		result[key] = extra[key]
	return result

func status() -> Dictionary:
	if _host == null or not _host.has_method("_workbench_state"):
		return _fail("host_unavailable")
	var state: Dictionary = _host.call("_workbench_state")
	if bool(state.get("decoupled_active", false)):
		return _fail("decoupled_active_rejected", {"state": state})
	if bool(state.get("boxless_active", false)):
		return _fail("boxless_grid_ownership_rejected", {"state": state})
	return _ok({"state": state, "mutable": not bool(state.get("playing", false))})

func _gate() -> Dictionary:
	var available := status()
	if not available.ok:
		return available
	if bool(available.state.get("playing", false)):
		return _fail("playing_rejected")
	return _ok({"state": available.state})

func queue_command(command: Dictionary) -> Dictionary:
	var normalized := _normalize_command(command)
	if not normalized.ok:
		return normalized
	return _queue(str(normalized.command.kind), normalized.command.args)

func _queue(kind: String, args: Dictionary) -> Dictionary:
	var gate := _gate()
	if not gate.ok:
		return gate
	var command := {"id": _next_id, "kind": kind, "args": args.duplicate(true)}
	_next_id += 1
	_queued.append(command)
	return _ok({"id": command.id, "command": command.duplicate(true)})

func _normalize_command(command: Dictionary) -> Dictionary:
	var kind := str(command.get("kind", command.get("tool", ""))).to_lower()
	if kind in ["0", "deposit"]:
		kind = OP_DEPOSIT
	elif kind in ["1", "align"]:
		kind = OP_ALIGN
	elif kind in ["2", "impulse"]:
		kind = OP_IMPULSE
	else:
		return _fail("unknown_command")
	var center: Variant = command.get("center", Vector3.ZERO)
	var radius := float(command.get("radius", 0.0))
	if not center is Vector3 or not center.is_finite() or not is_finite(radius) or radius <= 0.0:
		return _fail("invalid_selection")
	if kind == OP_DEPOSIT:
		var amount := float(command.get("strength", 0.0))
		if not is_finite(amount):
			return _fail("invalid_deposit_parameters")
		return _ok({"command": {"kind": kind, "args": {"center": center, "radius": radius, "strength": amount, "weighted": bool(command.get("weighted", false))}}})
	if kind == OP_ALIGN:
		var blend := float(command.get("strength", 1.0))
		if not is_finite(blend) or blend < 0.0 or blend > 1.0:
			return _fail("invalid_align_parameters")
		return _ok({"command": {"kind": kind, "args": {"center": center, "radius": radius, "strength": blend}}})
	var impulse: Variant = command.get("impulse", command.get("direction", command.get("vector", Vector3.ZERO)))
	if not impulse is Vector3:
		return _fail("invalid_impulse_parameters")
	if command.has("direction") and not command.has("impulse"):
		impulse *= float(command.get("strength", 1.0))
	if not impulse.is_finite():
		return _fail("invalid_impulse_parameters")
	return _ok({"command": {"kind": kind, "args": {"center": center, "radius": radius, "impulse": impulse}}})

func queue_deposit(center: Vector3, radius: float, strength: float, weighted := false) -> Dictionary:
	return queue_command({"kind": OP_DEPOSIT, "center": center, "radius": radius, "strength": strength, "weighted": weighted})

func queue_align(center: Vector3, radius: float, strength := 1.0) -> Dictionary:
	return queue_command({"kind": OP_ALIGN, "center": center, "radius": radius, "strength": strength})

func queue_impulse(center: Vector3, radius: float, impulse: Vector3) -> Dictionary:
	return queue_command({"kind": OP_IMPULSE, "center": center, "radius": radius, "impulse": impulse})

func pause() -> Dictionary:
	if _host != null and _host.has_method("_workbench_pause"):
		_host.call("_workbench_pause")
	return _ok()

func resume() -> Dictionary:
	if _host != null and _host.has_method("_workbench_resume"):
		_host.call("_workbench_resume")
	return _ok()

func step(count := 1) -> Dictionary:
	if count < 1:
		return _fail("invalid_step_count")
	var applied := apply_queued()
	if not applied.ok:
		return applied
	_host.call("_workbench_step", count)
	return _ok({"applied": applied.applied, "steps": count})

func apply_queued() -> Dictionary:
	var gate := _gate()
	if not gate.ok:
		return gate
	if _queued.is_empty():
		return _ok({"applied": 0, "commands": []})
	var commands := _queued.duplicate(true)
	var cpu_commands: Array[Dictionary] = []
	var results: Array[Dictionary] = []
	for command in commands:
		if _host.has_method("_workbench_apply_gpu") and command.kind in [OP_ALIGN, OP_IMPULSE]:
			var gpu: Dictionary = _host.call("_workbench_apply_gpu", [command])
			if not gpu.ok:
				return gpu
			command["backend"] = "gpu"
			command["applied"] = gpu.get("applied", {})
			command["applied_step"] = _host.call("_workbench_step_count")
			_log.append(command.duplicate(true))
			results.append(command.duplicate(true))
		else:
			cpu_commands.append(command)
	if not cpu_commands.is_empty():
		var buffers: Dictionary = _host.call("_workbench_read_buffers")
		if not _valid_buffers(buffers):
			return _fail("invalid_host_buffers")
		if _baseline.is_empty():
			_baseline = _snapshot(buffers)
		for command in cpu_commands:
			var result := _apply_one(command, buffers)
			if not result.ok:
				return result
			command["backend"] = "cpu"
			command["requested"] = result.requested
			command["applied"] = result.applied
			command["applied_step"] = _host.call("_workbench_step_count")
			_log.append(command.duplicate(true))
			results.append(command.duplicate(true))
		_host.call("_workbench_write_buffers", buffers)
	_queued.clear()
	results.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.id) < int(b.id))
	return _ok({"applied": results.size(), "commands": results})

func selected_readout(center: Vector3, radius: float) -> Dictionary:
	if radius <= 0.0 or not center.is_finite():
		return _fail("invalid_readout_parameters")
	var available := status()
	if not available.ok:
		return available
	var buffers: Dictionary = _host.call("_workbench_read_buffers")
	if not _valid_buffers(buffers):
		return _fail("invalid_host_buffers")
	var geometry := _geometry(buffers)
	var cell_count := 0
	var sum_ey := 0.0
	var sum_ei := 0.0
	var sum_intensity := 0.0
	var sum_qcoh := 0.0
	var sum_epsilon := 0.0
	for id in range(geometry.cells):
		var cell_pos := _cell_position(id, geometry)
		if _periodic_distance(cell_pos, center, geometry.extents).length_squared() <= radius * radius:
			cell_count += 1
			var ey: float = buffers.ey[id]
			var ei: float = buffers.ei[id]
			var rho := ey + ei
			var epsilon := ey - PHI * ei
			sum_ey += ey
			sum_ei += ei
			sum_intensity += ey * ey + ei * ei
			sum_qcoh += rho * rho / (rho * rho + PHI_INV2 + epsilon * epsilon)
			sum_epsilon += epsilon
	var particle_count := 0
	var particle_mass := 0.0
	var momentum := Vector3.ZERO
	for particle in range(buffers.pos.size() / 4):
		var mass: float = buffers.pos[particle * 4 + 3]
		if mass <= 0.0:
			continue
		var position := Vector3(buffers.pos[particle * 4], buffers.pos[particle * 4 + 1], buffers.pos[particle * 4 + 2])
		if _periodic_distance(position, center, geometry.extents).length_squared() <= radius * radius:
			particle_count += 1
			particle_mass += mass
			momentum += Vector3(buffers.pvel[particle * 4], buffers.pvel[particle * 4 + 1], buffers.pvel[particle * 4 + 2]) * mass
	var denom := maxf(cell_count, 1)
	var rho_mean: float = (sum_ey + sum_ei) / denom
	var epsilon_mean: float = sum_epsilon / denom
	var q_legacy: float = rho_mean * rho_mean / (rho_mean * rho_mean + PHI_INV2 + epsilon_mean * epsilon_mean)
	return _ok({"count": cell_count, "ey": sum_ey / denom, "ei": sum_ei / denom, "mean_ey": sum_ey / denom, "mean_ei": sum_ei / denom, "field_intensity": sum_intensity / denom, "q_coh": sum_qcoh / denom, "q": q_legacy, "epsilon": epsilon_mean, "rho": rho_mean, "mass": particle_mass, "particle_count": particle_count, "particle_mass": particle_mass, "momentum": momentum})

func _apply_one(command: Dictionary, buffers: Dictionary) -> Dictionary:
	var geometry := _geometry(buffers)
	var args: Dictionary = command.args
	var ids: Array[int] = []
	var weights: Array[float] = []
	if command.kind != OP_IMPULSE:
		for id in range(geometry.cells):
			var distance := _periodic_distance(_cell_position(id, geometry), args.center, geometry.extents)
			if distance.length_squared() <= args.radius * args.radius:
				ids.append(id)
				var weight := 1.0
				if bool(args.get("weighted", false)):
					weight = maxf(0.0, 1.0 - distance.length() / args.radius)
				weights.append(weight)
	if command.kind == OP_DEPOSIT and ids.is_empty():
		return _fail("empty_deposit_selection")
	var requested := {"cells": ids.size(), "yang": 0.0, "yin": 0.0}
	var applied := requested.duplicate(true)
	if command.kind == OP_DEPOSIT:
		var weight_sum := 0.0
		for weight in weights:
			weight_sum += weight
		for index in range(ids.size()):
			var amount: float = float(args.strength) * weights[index] / maxf(weight_sum, 1e-20)
			var id: int = ids[index]
			buffers.ey[id] += amount
			buffers.ei[id] += amount
			buffers.q[id] = buffers.ey[id] * buffers.ey[id] + buffers.ei[id] * buffers.ei[id]
			applied.yang += amount
			applied.yin += amount
	elif command.kind == OP_ALIGN:
		var target := Vector2(PHI, 1.0).normalized()
		for id in ids:
			var value := Vector2(buffers.ey[id], buffers.ei[id])
			var magnitude := value.length()
			if magnitude <= 0.0 or float(args.strength) == 0.0:
				continue
			var mixed := value.normalized().lerp(target, float(args.strength))
			var direction := target if mixed.length_squared() <= 1e-20 else mixed.normalized()
			var aligned := direction * magnitude
			buffers.ey[id] = aligned.x
			buffers.ei[id] = aligned.y
			buffers.q[id] = magnitude * magnitude
	elif command.kind == OP_IMPULSE:
		for particle in range(buffers.pos.size() / 4):
			var mass: float = buffers.pos[particle * 4 + 3]
			if mass <= 0.0:
				continue
			var position := Vector3(buffers.pos[particle * 4], buffers.pos[particle * 4 + 1], buffers.pos[particle * 4 + 2])
			if _periodic_distance(position, args.center, geometry.extents).length_squared() <= args.radius * args.radius:
				buffers.pvel[particle * 4] += args.impulse.x
				buffers.pvel[particle * 4 + 1] += args.impulse.y
				buffers.pvel[particle * 4 + 2] += args.impulse.z
				applied.cells += 1
	return _ok({"requested": requested, "applied": applied})

func capture_checkpoint() -> Dictionary:
	var gate := _gate()
	if not gate.ok:
		return gate
	var state: Dictionary = gate.state
	for key in ["meshless_mode", "particle_merge", "black_holes_enabled", "tracking_envelope", "home_window_enabled"]:
		if bool(state.get(key, false)):
			return _fail("checkpoint_incompatible_" + key)
	var buffers: Dictionary = _host.call("_workbench_read_buffers")
	if not _valid_buffers(buffers):
		return _fail("invalid_host_buffers")
	_checkpoint = {"schema_version": SCHEMA_VERSION, "signature": _compatibility_signature(state), "buffers": _snapshot(buffers), "step": int(state.get("step", 0)), "time": float(state.get("time", 0.0))}
	_checkpoint["digest"] = _buffer_digest(buffers)
	return _ok({"checkpoint": _checkpoint.duplicate(true), "digest": _checkpoint.digest, "summary": summarize_buffers(buffers)})

func restore_checkpoint(checkpoint: Dictionary = {}) -> Dictionary:
	var gate := _gate()
	if not gate.ok:
		return gate
	var source := checkpoint if not checkpoint.is_empty() else _checkpoint
	if source.is_empty() or int(source.get("schema_version", -1)) != SCHEMA_VERSION:
		return _fail("checkpoint_unavailable")
	if str(source.get("signature", "")) != _compatibility_signature(gate.state):
		return _fail("checkpoint_signature_mismatch")
	var buffers: Dictionary = source.get("buffers", {})
	if not _valid_buffers(buffers):
		return _fail("checkpoint_buffer_mismatch")
	_host.call("_workbench_write_buffers", _snapshot(buffers))
	if _host.has_method("_workbench_restore_clock"):
		_host.call("_workbench_restore_clock", int(source.get("step", 0)), float(source.get("time", 0.0)))
	return _ok({"digest": _buffer_digest(buffers), "summary": summarize_buffers(buffers)})

func run_branch(name: String, commands: Array, steps := 0) -> Dictionary:
	if name.is_empty() or steps < 0:
		return _fail("invalid_branch")
	var restored := restore_checkpoint()
	if not restored.ok:
		return restored
	_queued.clear()
	for command in commands:
		if not command is Dictionary:
			return _fail("invalid_branch_command")
		var queued := queue_command(command)
		if not queued.ok:
			return queued
	var applied := apply_queued()
	if not applied.ok:
		return applied
	if steps > 0:
		_host.call("_workbench_step", steps)
	var buffers: Dictionary = _host.call("_workbench_read_buffers")
	var summary := summarize_buffers(buffers)
	return _ok({"name": name, "applied": applied.applied, "steps": steps, "digest": _buffer_digest(buffers), "summary": summary, "difference": difference_view(summarize_buffers(_checkpoint.buffers), summary)})

func summarize_buffers(buffers: Dictionary) -> Dictionary:
	if not _valid_buffers(buffers):
		return {}
	var n: int = buffers.ey.size()
	var intensity := 0.0
	var coherence := 0.0
	var disequilibrium := 0.0
	for id in range(n):
		var ey: float = buffers.ey[id]
		var ei: float = buffers.ei[id]
		var rho := ey + ei
		var epsilon := ey - PHI * ei
		intensity += ey * ey + ei * ei
		coherence += rho * rho / (rho * rho + PHI_INV2 + epsilon * epsilon)
		disequilibrium += absf(epsilon)
	var live := 0
	var speed := 0.0
	for particle in range(buffers.pos.size() / 4):
		if buffers.pos[particle * 4 + 3] > 0.0:
			live += 1
			speed += Vector3(buffers.pvel[particle * 4], buffers.pvel[particle * 4 + 1], buffers.pvel[particle * 4 + 2]).length()
	return {"field_intensity": intensity / maxf(n, 1), "q_coh": coherence / maxf(n, 1), "abs_epsilon": disequilibrium / maxf(n, 1), "live_particles": live, "mean_particle_speed": speed / maxf(live, 1)}

func difference_view(baseline: Dictionary, branch: Dictionary) -> Dictionary:
	var delta := {}
	var scales := {}
	for key in ["field_intensity", "q_coh", "abs_epsilon", "mean_particle_speed"]:
		var base := float(baseline.get(key, 0.0))
		var value := float(branch.get(key, 0.0))
		delta[key] = value - base
		scales[key] = maxf(absf(base), 1e-12)
	return {"baseline": baseline.duplicate(true), "branch": branch.duplicate(true), "delta": delta, "scales": scales}

func save_scenario() -> Dictionary:
	if _baseline.is_empty():
		var current: Dictionary = _host.call("_workbench_read_buffers")
		if not _valid_buffers(current):
			return _fail("baseline_unavailable")
		_baseline = _snapshot(current)
	var unsigned := {"schema_version": SCHEMA_VERSION, "grid_N": _baseline.grid_N, "baseline": _json_buffers(_baseline), "operations": _json_value(_log)}
	var normalized: Dictionary = JSON.parse_string(JSON.stringify(unsigned))
	var canonical := JSON.stringify(normalized)
	normalized["checksum"] = _sha256(canonical.to_utf8_buffer())
	return _ok({"scenario": normalized, "version": SCHEMA_VERSION, "digest": normalized.checksum})

func replay_scenario(scenario: Dictionary) -> Dictionary:
	if int(scenario.get("schema_version", -1)) != SCHEMA_VERSION:
		return _fail("scenario_schema_mismatch")
	var expected: String = str(scenario.get("checksum", ""))
	var unsigned := scenario.duplicate(true)
	unsigned.erase("checksum")
	var normalized = JSON.parse_string(JSON.stringify(unsigned))
	var actual := _sha256(JSON.stringify(normalized).to_utf8_buffer())
	if expected.is_empty() or expected != actual:
		return _fail("scenario_checksum_mismatch")
	var baseline: Dictionary = _from_json_buffers(scenario.get("baseline", {}))
	if not _valid_buffers(baseline):
		return _fail("scenario_buffer_mismatch")
	var gate := _gate()
	if not gate.ok:
		return gate
	_host.call("_workbench_write_buffers", baseline)
	_baseline = _snapshot(baseline)
	_log.clear()
	_queued.clear()
	_next_id = 1
	for operation in scenario.get("operations", []):
		if not operation is Dictionary or not operation.has("kind") or not operation.has("args"):
			return _fail("scenario_operation_invalid")
		_queued.append({"id": _next_id, "kind": operation.kind, "args": _from_json_value(operation.args)})
		_next_id += 1
	var replayed := apply_queued()
	if replayed.ok:
		replayed["version"] = SCHEMA_VERSION
		replayed["digest"] = expected
	return replayed

func _compatibility_signature(state: Dictionary) -> String:
	return "%s|%s|%s|%s|%s|%s|%s" % [state.get("grid_N", 0), state.get("extents", Vector3.ZERO), state.get("window_center", Vector3.ZERO), state.get("meshless_mode", false), state.get("particle_merge", false), state.get("black_holes_enabled", false), state.get("decoupled_active", false)]

func _geometry(buffers: Dictionary) -> Dictionary:
	var n: int = int(buffers.grid_N)
	return {"n": n, "cells": n * n * n, "extents": buffers.extents, "window_center": buffers.get("window_center", Vector3.ZERO)}

func _cell_position(id: int, geometry: Dictionary) -> Vector3:
	var n: int = geometry.n
	var i := id % n
	var j := (id / n) % n
	var k := id / (n * n)
	return geometry.window_center + Vector3((i + 0.5) * 2.0 * geometry.extents.x / n - geometry.extents.x, (j + 0.5) * 2.0 * geometry.extents.y / n - geometry.extents.y, (k + 0.5) * 2.0 * geometry.extents.z / n - geometry.extents.z)

func _periodic_distance(a: Vector3, b: Vector3, extents: Vector3) -> Vector3:
	var distance := a - b
	for axis in ["x", "y", "z"]:
		var period := 2.0 * extents[axis]
		if distance[axis] > extents[axis]:
			distance[axis] -= period
		elif distance[axis] < -extents[axis]:
			distance[axis] += period
	return distance

func _snapshot(buffers: Dictionary) -> Dictionary:
	return buffers.duplicate(true)

func _valid_buffers(buffers: Dictionary) -> bool:
	if not buffers.has_all(["grid_N", "extents", "window_center", "ey", "ei", "q", "vel", "pos", "pvel"]):
		return false
	var n: int = int(buffers.grid_N)
	var cells := n * n * n
	return n > 0 and buffers.ey.size() == cells and buffers.ei.size() == cells and buffers.q.size() == cells and buffers.vel.size() == cells * 4 and buffers.pos.size() == buffers.pvel.size() and buffers.pos.size() % 4 == 0

func _buffer_digest(buffers: Dictionary) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	for key in ["ey", "ei", "q", "vel", "pos", "pvel"]:
		context.update((buffers[key] as PackedFloat32Array).to_byte_array())
	context.update(str(buffers.grid_N).to_utf8_buffer())
	context.update(str(buffers.extents).to_utf8_buffer())
	context.update(str(buffers.window_center).to_utf8_buffer())
	return context.finish().hex_encode()

func _json_value(value):
	if value is Vector3:
		return {"__vector3": [value.x, value.y, value.z]}
	if value is PackedFloat32Array or value is Array:
		var array := []
		for item in value:
			array.append(_json_value(item))
		return array
	if value is Dictionary:
		var dictionary := {}
		for key in value:
			dictionary[str(key)] = _json_value(value[key])
		return dictionary
	return value

func _from_json_value(value):
	if value is Dictionary:
		if value.has("__vector3"):
			var v: Array = value["__vector3"]
			return Vector3(float(v[0]), float(v[1]), float(v[2]))
		var dictionary := {}
		for key in value:
			dictionary[key] = _from_json_value(value[key])
		return dictionary
	if value is Array:
		var array := []
		for item in value:
			array.append(_from_json_value(item))
		return array
	return value

func _json_buffers(buffers: Dictionary) -> Dictionary:
	return _json_value(buffers)

func _from_json_buffers(value: Dictionary) -> Dictionary:
	var converted: Dictionary = _from_json_value(value)
	for key in ["ey", "ei", "q", "vel", "pos", "pvel"]:
		if converted.has(key):
			converted[key] = PackedFloat32Array(converted[key])
	return converted

func _sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()
