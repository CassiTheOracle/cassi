class_name FieldWorkbench
extends RefCounted

const SCHEMA_VERSION := 2
const PARTICLE_PROGRAM_SCHEMA := "cassi.particle-program.v1"
const OP_DEPOSIT := "deposit"
const OP_ALIGN := "align"
const OP_IMPULSE := "impulse"
const OP_ARRANGE := "arrange"
const PHI := 1.618033988749895
const PHI_INV2 := 0.3819660112501051
const PREVIEW_SAMPLE_LIMIT := 512

var _host: Object
var _log: Array[Dictionary] = []
var _queued: Array[Dictionary] = []
var _next_id := 1
var _baseline: Dictionary = {}
var _checkpoint: Dictionary = {}
var _automatic_checkpoint: Dictionary = {}
var _request_ledger: Dictionary = {}
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
	_automatic_checkpoint.clear()
	_request_ledger.clear()
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
	if not bool(state.get("authority_ready", true)):
		return _fail("authority_not_ready", {"state": state})
	return _ok({
		"state": state,
		"mutable": not bool(state.get("playing", false)),
		"particle_mutable": true,
		"field_mutable": not bool(state.get("boxless_active", false)),
	})

func _gate(allow_boxless_particles := false) -> Dictionary:
	var available := status()
	if not available.ok:
		return available
	if bool(available.state.get("boxless_active", false)) and not allow_boxless_particles:
		return _fail("boxless_grid_ownership_rejected", {"state": available.state})
	if bool(available.state.get("playing", false)):
		return _fail("playing_rejected")
	return _ok({"state": available.state})

func queue_command(command: Dictionary) -> Dictionary:
	var normalized := _normalize_command(command)
	if not normalized.ok:
		return normalized
	var metadata: Dictionary = normalized.get("metadata", {})
	if not metadata.is_empty():
		var request_id := str(metadata.request_id)
		var digest := str(metadata.program_digest)
		if _request_ledger.has(request_id):
			var prior: Dictionary = _request_ledger[request_id]
			if str(prior.digest) != digest:
				return _fail("request_id_conflict")
			return _ok({"id": int(prior.id), "duplicate": true, "status": str(prior.status), "receipt": prior.get("receipt", {})})
	var queued := _queue(str(normalized.command.kind), normalized.command.args, metadata)
	if queued.ok and not metadata.is_empty():
		_request_ledger[str(metadata.request_id)] = {
			"digest": str(metadata.program_digest),
			"id": int(queued.id),
			"status": "queued",
		}
	return queued

func _queue(kind: String, args: Dictionary, metadata: Dictionary = {}) -> Dictionary:
	var gate := _gate(kind == OP_ARRANGE)
	if not gate.ok:
		return gate
	var command := {"id": _next_id, "kind": kind, "args": args.duplicate(true)}
	for key in metadata:
		command[key] = metadata[key]
	_next_id += 1
	_queued.append(command)
	return _ok({"id": command.id, "command": command.duplicate(true)})

func _normalize_command(command: Dictionary) -> Dictionary:
	if str(command.get("schema", "")) == PARTICLE_PROGRAM_SCHEMA:
		var program := _normalize_particle_program(command)
		if not program.ok:
			return program
		var normalized: Dictionary = program.program
		var digest := _program_digest(normalized)
		return _ok({
			"command": {"kind": OP_ARRANGE, "args": {
				"selection": normalized.selection,
				"target": normalized.target,
				"motion": normalized.motion,
				"constraints": normalized.constraints,
			}},
			"metadata": {
				"program": normalized,
				"program_digest": digest,
				"request_id": str(normalized.request_id),
			},
		})
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
	if _queued.is_empty():
		return _ok({"applied": 0, "commands": []})
	var particle_only := true
	for queued_command in _queued:
		if str(queued_command.kind) != OP_ARRANGE:
			particle_only = false
			break
	var gate := _gate(particle_only)
	if not gate.ok:
		return gate
	var commands := _queued.duplicate(true)
	var buffers: Dictionary = _host.call("_workbench_read_buffers")
	if not _valid_buffers(buffers):
		return _reject_queued(commands, "invalid_host_buffers")
	if _baseline.is_empty():
		_baseline = _snapshot(buffers)
	var pre_digest := _buffer_digest(buffers)
	var automatic := _checkpoint_from(gate.state, buffers)
	automatic["particle_only"] = particle_only
	var results: Array[Dictionary] = []
	for command in commands:
		var result: Dictionary
		if command.kind == OP_ARRANGE:
			var plan := _arrangement_plan(command.args, buffers)
			if not plan.ok:
				return _reject_queued(commands, str(plan.error), plan)
			result = _apply_arrangement(command, buffers, plan)
		else:
			result = _apply_one(command, buffers)
		if not result.ok:
			return _reject_queued(commands, str(result.error), result)
		command["backend"] = "authority_pending"
		command["requested"] = result.requested
		command["applied"] = result.applied
		command["applied_step"] = _host.call("_workbench_step_count")
		command["pre_state_digest"] = pre_digest
		command["post_state_digest"] = _buffer_digest(buffers)
		if result.has("receipt"):
			var receipt: Dictionary = result.receipt
			receipt["pre_state_digest"] = pre_digest
			receipt["post_state_digest"] = command.post_state_digest
			receipt["world_step"] = command.applied_step
			command["receipt"] = receipt
		results.append(command.duplicate(true))
	var expected_digest := _buffer_digest(buffers)
	var write_result: Variant = _host.call("_workbench_write_buffers", buffers, particle_only)
	if not write_result is Dictionary or not bool(write_result.get("ok", false)):
		var write_error := "authority_write_failed" if not write_result is Dictionary else str(write_result.get("error", "authority_write_failed"))
		var rollback := _rollback_authority(automatic)
		if not rollback.ok:
			return _reject_queued(commands, "authority_rollback_failed", {"write_error": write_error, "rollback": rollback})
		return _reject_queued(commands, write_error, write_result if write_result is Dictionary else {})
	var backend := str(write_result.get("backend", "authoritative_cpu"))
	for index in range(results.size()):
		results[index]["backend"] = backend
		var backend_receipt: Dictionary = results[index].get("receipt", {})
		if not backend_receipt.is_empty():
			backend_receipt["backend"] = backend
			results[index]["receipt"] = backend_receipt
	var committed_buffers: Dictionary = _host.call("_workbench_read_buffers")
	if not _valid_buffers(committed_buffers):
		var invalid_rollback := _rollback_authority(automatic)
		if not invalid_rollback.ok:
			return _reject_queued(commands, "authority_rollback_failed", {"write_error": "authority_verification_read_failed", "rollback": invalid_rollback})
		return _reject_queued(commands, "authority_verification_read_failed")
	var committed_digest := _buffer_digest(committed_buffers)
	if committed_digest != expected_digest:
		var mismatch_rollback := _rollback_authority(automatic)
		if not mismatch_rollback.ok:
			return _reject_queued(commands, "authority_rollback_failed", {"write_error": "authority_verification_mismatch", "rollback": mismatch_rollback})
		return _reject_queued(commands, "authority_verification_mismatch", {
			"expected_digest": expected_digest,
			"actual_digest": committed_digest,
		})
	_automatic_checkpoint = automatic
	var applied_request_ids: Array[String] = []
	for result_command in results:
		if result_command.has("request_id"):
			applied_request_ids.append(str(result_command.request_id))
	_automatic_checkpoint["applied_request_ids"] = applied_request_ids
	for command in results:
		_log.append(command.duplicate(true))
		if command.has("request_id"):
			_request_ledger[str(command.request_id)] = {
				"digest": str(command.program_digest),
				"id": int(command.id),
				"status": "applied",
				"receipt": command.get("receipt", {}),
			}
	_queued.clear()
	results.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.id) < int(b.id))
	return _ok({"applied": results.size(), "commands": results, "backend": backend, "pre_state_digest": pre_digest, "post_state_digest": committed_digest})

func preview_command(command: Dictionary) -> Dictionary:
	var gate := _gate(true)
	if not gate.ok:
		return gate
	var normalized := _normalize_command(command)
	if not normalized.ok:
		return normalized
	if str(normalized.command.kind) != OP_ARRANGE:
		return _fail("preview_requires_particle_program")
	var buffers: Dictionary = _host.call("_workbench_read_buffers")
	if not _valid_buffers(buffers):
		return _fail("invalid_host_buffers")
	var plan := _arrangement_plan(normalized.command.args, buffers)
	if not plan.ok:
		return plan
	var metadata: Dictionary = normalized.get("metadata", {})
	return _ok({
		"program": metadata.get("program", {}),
		"program_digest": metadata.get("program_digest", ""),
		"request_id": metadata.get("request_id", ""),
		"affected_count": plan.ids.size(),
		"target_sample": plan.target_sample,
		"target_bounds": plan.target_bounds,
		"maximum_displacement": plan.maximum_displacement,
		"rms_target_error": plan.rms_target_error,
		"state_digest": _buffer_digest(buffers),
	})

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

func _checkpoint_from(state: Dictionary, buffers: Dictionary) -> Dictionary:
	return {
		"schema_version": SCHEMA_VERSION,
		"signature": _compatibility_signature(state),
		"buffers": _snapshot(buffers),
		"step": int(state.get("step", 0)),
		"time": float(state.get("time", 0.0)),
		"digest": _buffer_digest(buffers),
		"log": _log.duplicate(true),
		"next_id": _next_id,
		"request_ledger": _request_ledger.duplicate(true),
	}
func _rollback_authority(source: Dictionary) -> Dictionary:
	var write_result: Variant = _host.call("_workbench_write_buffers", _snapshot(source.buffers), bool(source.get("particle_only", false)))
	if not write_result is Dictionary or not bool(write_result.get("ok", false)):
		return _fail("rollback_write_failed")
	if _host.has_method("_workbench_restore_clock"):
		_host.call("_workbench_restore_clock", int(source.step), float(source.time))
	var restored: Dictionary = _host.call("_workbench_read_buffers")
	if not _valid_buffers(restored):
		return _fail("rollback_read_failed")
	var actual := _buffer_digest(restored)
	if actual != str(source.digest):
		return _fail("rollback_digest_mismatch", {"expected": source.digest, "actual": actual})
	return _ok({"digest": actual})


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
	_checkpoint = _checkpoint_from(state, buffers)
	return _ok({"checkpoint": _checkpoint.duplicate(true), "digest": _checkpoint.digest, "summary": summarize_buffers(buffers)})

func _restore_checkpoint_source(source: Dictionary, state: Dictionary) -> Dictionary:
	if source.is_empty() or int(source.get("schema_version", -1)) != SCHEMA_VERSION:
		return _fail("checkpoint_unavailable")
	if str(source.get("signature", "")) != _compatibility_signature(state):
		return _fail("checkpoint_signature_mismatch")
	var buffers: Dictionary = source.get("buffers", {})
	if not _valid_buffers(buffers):
		return _fail("checkpoint_buffer_mismatch")
	var write_result: Variant = _host.call("_workbench_write_buffers", _snapshot(buffers), bool(source.get("particle_only", false)))
	if write_result is Dictionary and not bool(write_result.get("ok", false)):
		return _fail(str(write_result.get("error", "authority_write_failed")))
	if _host.has_method("_workbench_restore_clock"):
		_host.call("_workbench_restore_clock", int(source.get("step", 0)), float(source.get("time", 0.0)))
	_log = source.get("log", []).duplicate(true)
	_next_id = int(source.get("next_id", _next_id))
	_request_ledger = source.get("request_ledger", {}).duplicate(true)
	_queued.clear()
	return _ok({"digest": _buffer_digest(buffers), "summary": summarize_buffers(buffers)})

func restore_checkpoint(checkpoint: Dictionary = {}) -> Dictionary:
	var gate := _gate()
	if not gate.ok:
		return gate
	var source := checkpoint if not checkpoint.is_empty() else _checkpoint
	return _restore_checkpoint_source(source, gate.state)

func undo_last_apply() -> Dictionary:
	var gate := _gate(true)
	if not gate.ok:
		return gate
	if _automatic_checkpoint.is_empty():
		return _fail("undo_unavailable")
	var source := _automatic_checkpoint
	var restored := _restore_checkpoint_source(source, gate.state)
	if not restored.ok:
		return restored
	for request_id in source.get("applied_request_ids", []):
		_request_ledger.erase(str(request_id))
	_automatic_checkpoint.clear()
	restored["undone"] = true
	return restored

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
	if not buffers.has_all(["grid_N", "extents", "window_center", "ey", "ei", "q", "vel", "pos", "pvel", "acc"]):
		return false
	var n: int = int(buffers.grid_N)
	var cells := n * n * n
	return n > 0 and buffers.ey.size() == cells and buffers.ei.size() == cells and buffers.q.size() == cells \
		and buffers.vel.size() == cells * 4 and buffers.pos.size() == buffers.pvel.size() \
		and buffers.pos.size() == buffers.acc.size() and buffers.pos.size() % 4 == 0

func _buffer_digest(buffers: Dictionary) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	for key in ["ey", "ei", "q", "vel", "pos", "pvel", "acc"]:
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
	for key in ["ey", "ei", "q", "vel", "pos", "pvel", "acc"]:
		if converted.has(key):
			converted[key] = PackedFloat32Array(converted[key])
	return converted

func _sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()

func _keys_match(value: Dictionary, required: Array, optional: Array = []) -> bool:
	for key in required:
		if not value.has(key):
			return false
	for key in value:
		if not required.has(key) and not optional.has(key):
			return false
	return true

func _finite_float(value: Variant, positive := false) -> Variant:
	if not value is int and not value is float:
		return null
	var result := float(value)
	if not is_finite(result) or (positive and result <= 0.0):
		return null
	return result

func _vector3_value(value: Variant) -> Variant:
	if value is Vector3:
		return value if value.is_finite() else null
	if not value is Array or value.size() != 3:
		return null
	var x: Variant = _finite_float(value[0])
	var y: Variant = _finite_float(value[1])
	var z: Variant = _finite_float(value[2])
	if x == null or y == null or z == null:
		return null
	return Vector3(float(x), float(y), float(z))

func _unit_vector(value: Variant) -> Variant:
	var vector: Variant = _vector3_value(value)
	if vector == null or (vector as Vector3).length_squared() <= 1e-24:
		return null
	return (vector as Vector3).normalized()

func _normalize_selection(value: Variant) -> Dictionary:
	if not value is Dictionary or not _keys_match(value, ["type"], ["center", "radius", "half_extents"]):
		return _fail("invalid_particle_selection")
	var kind := str(value.get("type", ""))
	if kind == "all":
		if value.size() != 1:
			return _fail("invalid_particle_selection")
		return _ok({"selection": {"type": "all"}})
	if kind == "sphere":
		if not _keys_match(value, ["type", "center", "radius"]):
			return _fail("invalid_particle_selection")
		var center: Variant = _vector3_value(value.center)
		var radius: Variant = _finite_float(value.radius, true)
		if center == null or radius == null:
			return _fail("invalid_particle_selection")
		return _ok({"selection": {"type": kind, "center": center, "radius": radius}})
	if kind == "box":
		if not _keys_match(value, ["type", "center", "half_extents"]):
			return _fail("invalid_particle_selection")
		var center: Variant = _vector3_value(value.center)
		var half_extents: Variant = _vector3_value(value.half_extents)
		if center == null or half_extents == null or (half_extents as Vector3).x <= 0.0 or (half_extents as Vector3).y <= 0.0 or (half_extents as Vector3).z <= 0.0:
			return _fail("invalid_particle_selection")
		return _ok({"selection": {"type": kind, "center": center, "half_extents": half_extents}})
	return _fail("invalid_particle_selection")

func _normalize_target(value: Variant) -> Dictionary:
	if not value is Dictionary or not value.has("type"):
		return _fail("invalid_particle_target")
	var kind := str(value.type)
	var target := {"type": kind}
	if kind == "line":
		if not _keys_match(value, ["type", "center", "direction", "length"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var direction: Variant = _unit_vector(value.direction)
		var length: Variant = _finite_float(value.length, true)
		if center == null or direction == null or length == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "direction": direction, "length": length})
	elif kind == "ring":
		if not _keys_match(value, ["type", "center", "normal", "radius", "phase"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var normal: Variant = _unit_vector(value.normal)
		var radius: Variant = _finite_float(value.radius, true)
		var phase: Variant = _finite_float(value.phase)
		if center == null or normal == null or radius == null or phase == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "normal": normal, "radius": radius, "phase": phase})
	elif kind == "sphere":
		if not _keys_match(value, ["type", "center", "radius"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var radius: Variant = _finite_float(value.radius, true)
		if center == null or radius == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "radius": radius})
	elif kind == "grid":
		if not _keys_match(value, ["type", "center", "spacing"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var spacing: Variant = _finite_float(value.spacing, true)
		if center == null or spacing == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "spacing": spacing})
	elif kind in ["helix", "double_helix"]:
		if not _keys_match(value, ["type", "center", "axis", "radius", "pitch", "turns", "phase"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var axis: Variant = _unit_vector(value.axis)
		var radius: Variant = _finite_float(value.radius, true)
		var pitch: Variant = _finite_float(value.pitch, true)
		var turns: Variant = _finite_float(value.turns, true)
		var phase: Variant = _finite_float(value.phase)
		if center == null or axis == null or radius == null or pitch == null or turns == null or phase == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "axis": axis, "radius": radius, "pitch": pitch, "turns": turns, "phase": phase})
	elif kind == "point_cloud":
		if not _keys_match(value, ["type", "points"]) or not value.points is Array or value.points.is_empty() or value.points.size() > 8192:
			return _fail("invalid_particle_target")
		var indexed: Array[Dictionary] = []
		for index in range(value.points.size()):
			var point: Variant = _vector3_value(value.points[index])
			if point == null:
				return _fail("invalid_particle_target")
			indexed.append({"point": point, "index": index})
		indexed.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
			var pa: Vector3 = a.point
			var pb: Vector3 = b.point
			if pa.x != pb.x: return pa.x < pb.x
			if pa.y != pb.y: return pa.y < pb.y
			if pa.z != pb.z: return pa.z < pb.z
			return int(a.index) < int(b.index))
		var points: Array = []
		for entry in indexed:
			points.append(entry.point)
		target["points"] = points
	elif kind == "translate":
		if not _keys_match(value, ["type", "offset"]):
			return _fail("invalid_particle_target")
		var offset: Variant = _vector3_value(value.offset)
		if offset == null:
			return _fail("invalid_particle_target")
		target["offset"] = offset
	elif kind == "scale":
		if not _keys_match(value, ["type", "center", "factor"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var factor: Variant = _finite_float(value.factor, true)
		if center == null or factor == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "factor": factor})
	elif kind == "rotate":
		if not _keys_match(value, ["type", "center", "axis", "angle_radians"]):
			return _fail("invalid_particle_target")
		var center: Variant = _vector3_value(value.center)
		var axis: Variant = _unit_vector(value.axis)
		var angle: Variant = _finite_float(value.angle_radians)
		if center == null or axis == null or angle == null:
			return _fail("invalid_particle_target")
		target.merge({"center": center, "axis": axis, "angle_radians": angle})
	else:
		return _fail("invalid_particle_target")
	return _ok({"target": target})

func _normalize_motion(value: Variant) -> Dictionary:
	if not value is Dictionary or not value.has("type"):
		return _fail("invalid_particle_motion")
	var kind := str(value.type)
	if kind == "exact":
		if not _keys_match(value, ["type", "velocity_policy"]) or str(value.velocity_policy) not in ["preserve", "zero"]:
			return _fail("invalid_particle_motion")
		return _ok({"motion": {"type": kind, "velocity_policy": str(value.velocity_policy)}})
	if kind == "steer":
		if not _keys_match(value, ["type", "speed"]):
			return _fail("invalid_particle_motion")
		var speed: Variant = _finite_float(value.speed, true)
		if speed == null:
			return _fail("invalid_particle_motion")
		return _ok({"motion": {"type": kind, "speed": speed}})
	return _fail("invalid_particle_motion")

func _normalize_constraints(value: Variant) -> Dictionary:
	if not value is Dictionary or not _keys_match(value, ["maximum_particles", "maximum_displacement", "maximum_speed"]):
		return _fail("invalid_particle_constraints")
	var maximum_particles: Variant = _finite_float(value.maximum_particles, true)
	if maximum_particles == null or float(maximum_particles) != floorf(float(maximum_particles)):
		return _fail("invalid_particle_constraints")
	var displacement: Variant = _finite_float(value.maximum_displacement, true)
	var speed: Variant = _finite_float(value.maximum_speed, true)
	if displacement == null or speed == null:
		return _fail("invalid_particle_constraints")
	return _ok({"constraints": {
		"maximum_particles": int(maximum_particles),
		"maximum_displacement": displacement,
		"maximum_speed": speed,
	}})

func _normalize_particle_program(command: Dictionary) -> Dictionary:
	if not _keys_match(command, ["schema", "operation", "selection", "target", "motion", "constraints", "source", "request_id"]):
		return _fail("invalid_particle_program_keys")
	if str(command.schema) != PARTICLE_PROGRAM_SCHEMA or str(command.operation) != OP_ARRANGE:
		return _fail("invalid_particle_program_identity")
	var selection := _normalize_selection(command.selection)
	if not selection.ok: return selection
	var target := _normalize_target(command.target)
	if not target.ok: return target
	var motion := _normalize_motion(command.motion)
	if not motion.ok: return motion
	var constraints := _normalize_constraints(command.constraints)
	if not constraints.ok: return constraints
	if not command.source is Dictionary or not _keys_match(command.source, ["kind"], ["text"]):
		return _fail("invalid_particle_source")
	var source_kind := str(command.source.kind)
	if source_kind not in ["chat", "manual", "explicit"]:
		return _fail("invalid_particle_source")
	var source := {"kind": source_kind}
	if command.source.has("text"):
		if not command.source.text is String or (command.source.text as String).to_utf8_buffer().size() > 16384:
			return _fail("invalid_particle_source")
		source["text"] = command.source.text
	var request_id := str(command.request_id)
	var request_pattern := RegEx.new()
	request_pattern.compile("^[A-Za-z0-9][A-Za-z0-9._:-]*$")
	if request_id.to_utf8_buffer().size() > 256 or request_pattern.search(request_id) == null:
		return _fail("invalid_request_id")
	var program := {
		"schema": PARTICLE_PROGRAM_SCHEMA,
		"operation": OP_ARRANGE,
		"selection": selection.selection,
		"target": target.target,
		"motion": motion.motion,
		"constraints": constraints.constraints,
		"source": source,
		"request_id": request_id,
	}
	if _canonical_json(program).to_utf8_buffer().size() > 65536:
		return _fail("particle_program_too_large")
	return _ok({"program": program})

func _canonical_json(value: Variant) -> String:
	if value is Vector3:
		return "[%s,%s,%s]" % [JSON.stringify(value.x), JSON.stringify(value.y), JSON.stringify(value.z)]
	if value is Array or value is PackedInt32Array or value is PackedFloat32Array:
		var items: PackedStringArray = []
		for item in value:
			items.append(_canonical_json(item))
		return "[" + ",".join(items) + "]"
	if value is Dictionary:
		var keys: Array = value.keys()
		keys.sort()
		var items: PackedStringArray = []
		for key in keys:
			items.append(JSON.stringify(str(key)) + ":" + _canonical_json(value[key]))
		return "{" + ",".join(items) + "}"
	return JSON.stringify(value)

func _program_digest(program: Dictionary) -> String:
	return _sha256(_canonical_json(program).to_utf8_buffer())

func _reject_queued(commands: Array[Dictionary], error: String, extra: Dictionary = {}) -> Dictionary:
	for command in commands:
		if command.has("request_id"):
			_request_ledger[str(command.request_id)] = {
				"digest": str(command.program_digest),
				"id": int(command.id),
				"status": "rejected",
				"receipt": {"ok": false, "error": error},
			}
	_queued.clear()
	var details := extra.duplicate(true)
	details.erase("ok")
	details.erase("error")
	return _fail(error, details)

func _selected_particle_ids(selection: Dictionary, buffers: Dictionary) -> PackedInt32Array:
	var ids := PackedInt32Array()
	var extents: Vector3 = buffers.extents
	for particle in range(buffers.pos.size() / 4):
		if buffers.pos[particle * 4 + 3] <= 0.0:
			continue
		var position := Vector3(buffers.pos[particle * 4], buffers.pos[particle * 4 + 1], buffers.pos[particle * 4 + 2])
		var selected: bool = selection.type == "all"
		if selection.type == "sphere":
			selected = _periodic_distance(position, selection.center, extents).length_squared() <= float(selection.radius) * float(selection.radius)
		elif selection.type == "box":
			var delta := _periodic_distance(position, selection.center, extents).abs()
			selected = delta.x <= selection.half_extents.x and delta.y <= selection.half_extents.y and delta.z <= selection.half_extents.z
		if selected:
			ids.append(particle)
	return ids

func _prepare_target(target: Dictionary) -> Dictionary:
	var prepared := target.duplicate(true)
	if target.type == "point_cloud":
		var lengths := PackedFloat32Array([0.0])
		var total := 0.0
		for index in range(1, target.points.size()):
			total += (target.points[index] as Vector3).distance_to(target.points[index - 1])
			lengths.append(total)
		prepared["_arc_lengths"] = lengths
		prepared["_arc_total"] = total
	elif target.type == "ring":
		var basis := _axis_basis(target.normal)
		prepared["_basis_0"] = basis[0]
		prepared["_basis_1"] = basis[1]
	elif target.type in ["helix", "double_helix"]:
		var basis := _axis_basis(target.axis)
		prepared["_basis_0"] = basis[0]
		prepared["_basis_1"] = basis[1]
	return prepared

func _axis_basis(axis: Vector3) -> Array[Vector3]:
	var reference := Vector3.RIGHT if absf(axis.dot(Vector3.UP)) > 0.9 else Vector3.UP
	var first := axis.cross(reference).normalized()
	return [first, axis.cross(first).normalized()]

func _point_cloud_target(target: Dictionary, index: int, count: int) -> Vector3:
	var points: Array = target.points
	if points.size() == 1 or float(target._arc_total) <= 1e-20:
		return points[0]
	var distance := (float(index) + 0.5) * float(target._arc_total) / float(count)
	var lengths: PackedFloat32Array = target._arc_lengths
	var low := 1
	var high := lengths.size() - 1
	while low < high:
		var middle := (low + high) / 2
		if lengths[middle] < distance:
			low = middle + 1
		else:
			high = middle
	var segment := low
	var start := float(lengths[segment - 1])
	var finish := float(lengths[segment])
	var amount := 0.0 if finish <= start else (distance - start) / (finish - start)
	return (points[segment - 1] as Vector3).lerp(points[segment], amount)

func _target_position(target: Dictionary, index: int, count: int, source: Vector3) -> Vector3:
	var kind := str(target.type)
	if kind == "line":
		var amount := 0.5 if count == 1 else float(index) / float(count - 1)
		return target.center + target.direction * float(target.length) * (amount - 0.5)
	if kind == "ring":
		var angle := float(target.phase) + TAU * float(index) / float(count)
		return target.center + float(target.radius) * (target._basis_0 * cos(angle) + target._basis_1 * sin(angle))
	if kind == "sphere":
		var y := 1.0 - 2.0 * (float(index) + 0.5) / float(count)
		var radial := sqrt(maxf(0.0, 1.0 - y * y))
		var angle := PI * (3.0 - sqrt(5.0)) * float(index)
		return target.center + float(target.radius) * Vector3(radial * cos(angle), y, radial * sin(angle))
	if kind == "grid":
		var side := maxi(1, int(ceili(pow(float(count), 1.0 / 3.0))))
		var x := index % side
		var y := (index / side) % side
		var z := index / (side * side)
		var offset := 0.5 * float(side - 1)
		return target.center + float(target.spacing) * (Vector3(x, y, z) - Vector3.ONE * offset)
	if kind in ["helix", "double_helix"]:
		var strand := index % 2 if kind == "double_helix" else 0
		var strand_count := int(ceili(float(count) / 2.0)) if kind == "double_helix" else count
		var strand_index := index / 2 if kind == "double_helix" else index
		var amount := 0.5 if strand_count <= 1 else float(strand_index) / float(strand_count - 1)
		var angle := float(target.phase) + TAU * float(target.turns) * amount + PI * float(strand)
		return target.center + target.axis * (float(target.pitch) * float(target.turns) * (amount - 0.5)) + float(target.radius) * (target._basis_0 * cos(angle) + target._basis_1 * sin(angle))
	if kind == "point_cloud":
		return _point_cloud_target(target, index, count)
	if kind == "translate":
		return source + target.offset
	if kind == "scale":
		return target.center + (source - target.center) * float(target.factor)
	return target.center + Quaternion(target.axis, float(target.angle_radians)) * (source - target.center)

func _target_in_bounds(target: Vector3, buffers: Dictionary) -> bool:
	var center: Vector3 = buffers.window_center
	var extents: Vector3 = buffers.extents
	var local := target - center
	return target.is_finite() and absf(local.x) <= extents.x + 1e-5 and absf(local.y) <= extents.y + 1e-5 and absf(local.z) <= extents.z + 1e-5

func _arrangement_plan(args: Dictionary, buffers: Dictionary) -> Dictionary:
	var ids := _selected_particle_ids(args.selection, buffers)
	if ids.is_empty():
		return _fail("empty_particle_selection")
	if ids.size() > int(args.constraints.maximum_particles):
		return _fail("particle_selection_limit_exceeded", {"selected": ids.size()})
	if args.motion.type == "steer" and float(args.motion.speed) > float(args.constraints.maximum_speed):
		return _fail("particle_speed_limit_exceeded")
	var target := _prepare_target(args.target)
	var maximum_displacement := 0.0
	var squared_error := 0.0
	var target_min := Vector3(INF, INF, INF)
	var target_max := Vector3(-INF, -INF, -INF)
	var sample: Array[Vector3] = []
	var sample_count := mini(PREVIEW_SAMPLE_LIMIT, ids.size())
	var target_positions := PackedVector3Array()
	target_positions.resize(ids.size())
	var next_sample := 0
	for order in range(ids.size()):
		var particle := int(ids[order])
		var source := Vector3(buffers.pos[particle * 4], buffers.pos[particle * 4 + 1], buffers.pos[particle * 4 + 2])
		if not source.is_finite():
			return _fail("nonfinite_particle_state")
		var resolved := _target_position(target, order, ids.size(), source)
		target_positions[order] = resolved
		if not _target_in_bounds(resolved, buffers):
			return _fail("particle_target_out_of_bounds", {"particle": particle, "target": resolved})
		var displacement := source.distance_to(resolved)
		if displacement > float(args.constraints.maximum_displacement):
			return _fail("particle_displacement_limit_exceeded", {"particle": particle, "displacement": displacement})
		maximum_displacement = maxf(maximum_displacement, displacement)
		squared_error += displacement * displacement
		target_min = target_min.min(resolved)
		target_max = target_max.max(resolved)
		if next_sample < sample_count and order == int(floor(float(next_sample) * float(ids.size()) / float(sample_count))):
			sample.append(resolved)
			next_sample += 1
	return _ok({
		"ids": ids,
		"target": target,
		"target_positions": target_positions,
		"target_sample": sample,
		"target_bounds": {"min": target_min, "max": target_max},
		"maximum_displacement": maximum_displacement,
		"rms_target_error": sqrt(squared_error / float(ids.size())),
	})

func _apply_arrangement(command: Dictionary, buffers: Dictionary, plan: Dictionary) -> Dictionary:
	var ids: PackedInt32Array = plan.ids
	var target_positions: PackedVector3Array = plan.target_positions
	for order in range(ids.size()):
		var particle := int(ids[order])
		var offset := particle * 4
		var source := Vector3(buffers.pos[offset], buffers.pos[offset + 1], buffers.pos[offset + 2])
		var target := target_positions[order]
		if command.args.motion.type == "exact":
			buffers.pos[offset] = target.x
			buffers.pos[offset + 1] = target.y
			buffers.pos[offset + 2] = target.z
			if command.args.motion.velocity_policy == "zero":
				buffers.pvel[offset] = 0.0
				buffers.pvel[offset + 1] = 0.0
				buffers.pvel[offset + 2] = 0.0
		else:
			var delta := target - source
			var velocity := Vector3.ZERO if delta.length_squared() <= 1e-24 else delta.normalized() * float(command.args.motion.speed)
			buffers.pvel[offset] = velocity.x
			buffers.pvel[offset + 1] = velocity.y
			buffers.pvel[offset + 2] = velocity.z
	if command.args.motion.type == "exact":
		buffers.acc.fill(0.0)
		buffers["_positions_changed"] = true
	var metrics := {
		"particles": ids.size(),
		"maximum_displacement": plan.maximum_displacement,
		"rms_target_error": plan.rms_target_error,
	}
	return _ok({
		"requested": {"particles": ids.size()},
		"applied": metrics,
		"receipt": {
			"schema": "cassi.particle-result.v1",
			"request_id": str(command.get("request_id", "")),
			"program_digest": str(command.get("program_digest", "")),
			"status": "applied",
			"affected_count": ids.size(),
			"maximum_displacement": plan.maximum_displacement,
			"rms_target_error": plan.rms_target_error,
		},
	})
