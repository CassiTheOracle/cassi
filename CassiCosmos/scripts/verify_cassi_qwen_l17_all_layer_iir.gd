extends Node
## CassiQwen L17 — all-layer residual IIR field GPU receipt.
##
## This is a windowed, bridge-off probe.  It consumes only the prepared CPU
## seed, blends one validated full field for each model layer, advances four
## existing PDE steps per update, and writes the frozen raw receipt.  No model,
## hidden-state decode, network, bridge, or field-to-model path is involved.

const PROTOCOL := "CassiQwen L17 all-layer IIR field observatory"
const VERSION := 1
const SEED_PATH := "res://_diag/cassi_qwen_all_layer_iir_seed.json"
const GPU_PATH := "res://_diag/cassi_qwen_all_layer_iir_gpu.json"
const GRID_N := 32
const CELLS := GRID_N * GRID_N * GRID_N
const DIMENSION := 5120
const PHI := 1.618033988749895
const AMPLITUDE := 1.0
const DT := 0.005
const LAYOUT := "x + N*(y + N*z)"
const DTYPE := "float32-le"
const RETAINED_WEIGHT := 0.9
const STEPS_PER_LAYER := 4
const LAYER_COUNT := 64
const LAYER_CHECKPOINTS := [0, 1, 2, 3, 7, 15, 31, 47, 63]
const CONTINUATION_HORIZONS := [0, 1, 4, 16, 64]
const MAX_ABS_BOUND := 10.0
const FIRST_BLEND_TOL := 2.0e-6

var _engine: Node
var _zero_field := PackedFloat32Array()


func _ready() -> void:
	var seed: Dictionary = _read_seed()
	var receipt: Dictionary = _new_receipt(str(seed.get("capture_sha256", "")))
	var prepared: Dictionary = _prepare_seed(seed)
	if prepared.is_empty():
		_write_and_quit(receipt, "seed metadata, layer schema, or float payload validation failed")
		return

	var engine_script: GDScript = load("res://scripts/cassi_mind_engine.gd") as GDScript
	if engine_script == null:
		_write_and_quit(receipt, "canonical mind engine script load failed")
		return
	_engine = engine_script.new()
	_engine.grid_n = GRID_N
	_engine.dt = DT
	_engine.auto_step = false
	_engine.serve_bridge = false
	add_child(_engine)
	_zero_field.resize(CELLS)

	if not _verify_engine_contract(prepared["canonical_layers"]):
		_write_and_quit(receipt, "blend_full_field contract validation failed")
		return

	var arms: Array = []
	var run_valid := true
	var arm_specs: Array = [
		{"id": "forward_canonical", "basis": "canonical", "source": "canonical", "reverse": false, "zero": false},
		{"id": "reverse_canonical", "basis": "canonical", "source": "canonical", "reverse": true, "zero": false},
		{"id": "forward_shuffled", "basis": "shuffled", "source": "shuffled", "reverse": false, "zero": false},
		{"id": "zero", "basis": "zero", "source": "", "reverse": false, "zero": true},
	]
	for spec_value in arm_specs:
		var spec: Dictionary = spec_value
		var source_layers: Array = []
		if not bool(spec["zero"]):
			source_layers = prepared["%s_layers" % str(spec["source"])]
		var run: Dictionary = _run_arm(spec, source_layers)
		arms.append(run["arm"])
		run_valid = run_valid and bool(run["valid"])

	receipt["arms"] = arms
	receipt["finite"] = run_valid
	receipt["verdict"] = "PASS" if run_valid else "INVALID"
	_write_and_quit(receipt, "" if run_valid else "one or more L17 GPU checkpoints violated the receipt contract")


func _new_receipt(capture_hash: String) -> Dictionary:
	return {
		"protocol": PROTOCOL,
		"version": VERSION,
		"grid_n": GRID_N,
		"dimension": DIMENSION,
		"phi": PHI,
		"dt": DT,
		"layout": LAYOUT,
		"dtype": DTYPE,
		"retained_weight": RETAINED_WEIGHT,
		"steps_per_layer": STEPS_PER_LAYER,
		"layer_count": LAYER_COUNT,
		"layer_checkpoints": LAYER_CHECKPOINTS.duplicate(),
		"continuation_horizons": CONTINUATION_HORIZONS.duplicate(),
		"capture_sha256": capture_hash,
		"finite": false,
		"verdict": "INVALID",
		"arms": [],
	}


func _read_seed() -> Dictionary:
	if not FileAccess.file_exists(SEED_PATH):
		return {}
	var file: FileAccess = FileAccess.open(SEED_PATH, FileAccess.READ)
	if file == null:
		return {}
	var text := file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		return {}
	return parsed


func _prepare_seed(seed: Dictionary) -> Dictionary:
	if str(seed.get("protocol", "")) != PROTOCOL:
		return {}
	if not _number_equals(seed.get("version", -1), float(VERSION)):
		return {}
	if not _number_equals(seed.get("grid_n", -1), float(GRID_N)):
		return {}
	if not _number_equals(seed.get("dimension", -1), float(DIMENSION)):
		return {}
	if not _number_equals(seed.get("phi", NAN), PHI):
		return {}
	if not _number_equals(seed.get("amplitude", NAN), AMPLITUDE):
		return {}
	if not _number_equals(seed.get("dt", NAN), DT):
		return {}
	if str(seed.get("layout", "")) != LAYOUT:
		return {}
	if str(seed.get("dtype", "")) != DTYPE:
		return {}
	if not _number_equals(seed.get("retained_weight", NAN), RETAINED_WEIGHT):
		return {}
	if not _number_equals(seed.get("steps_per_layer", -1), float(STEPS_PER_LAYER)):
		return {}
	if not _number_equals(seed.get("layer_count", -1), float(LAYER_COUNT)):
		return {}
	if not _numbers_equal(seed.get("layer_checkpoints", null), LAYER_CHECKPOINTS):
		return {}
	if not _numbers_equal(seed.get("continuation_horizons", null), CONTINUATION_HORIZONS):
		return {}

	var capture_hash_value: Variant = seed.get("capture_sha256", null)
	if not (capture_hash_value is String):
		return {}
	var capture_hash := str(capture_hash_value)
	if capture_hash.length() != 64 or not _is_hex(capture_hash):
		return {}

	var canonical_layers: Array = _decode_layer_group(seed.get("canonical_layers", null))
	var shuffled_layers: Array = _decode_layer_group(seed.get("shuffled_layers", null))
	if canonical_layers.size() != LAYER_COUNT or shuffled_layers.size() != LAYER_COUNT:
		return {}

	return {
		"capture_sha256": capture_hash,
		"canonical_layers": canonical_layers,
		"shuffled_layers": shuffled_layers,
	}


func _decode_layer_group(value: Variant) -> Array:
	if not (value is Array):
		return []
	var encoded_layers: Array = value
	if encoded_layers.size() != LAYER_COUNT:
		return []
	var layers: Array = []
	for expected_index in range(LAYER_COUNT):
		var layer_value: Variant = encoded_layers[expected_index]
		if not (layer_value is Dictionary):
			return []
		var layer_data: Dictionary = layer_value
		if not _number_equals(layer_data.get("layer_index", -1), float(expected_index)):
			return []
		var ey := _decode_f32(layer_data.get("ey_b64", null), CELLS)
		var ei := _decode_f32(layer_data.get("ei_b64", null), CELLS)
		if ey.size() != CELLS or ei.size() != CELLS:
			return []
		if not _finite(ey) or not _finite(ei) or not _any_nonzero(ey, ei):
			return []

		var norm_value: Variant = layer_data.get("hidden_l2_norm", null)
		if not (norm_value is int or norm_value is float):
			return []
		var hidden_norm := float(norm_value)
		if not _finite_scalar(hidden_norm) or hidden_norm <= 0.0:
			return []
		var state_hash_value: Variant = layer_data.get("hidden_state_sha256", null)
		if not (state_hash_value is String):
			return []
		var state_hash := str(state_hash_value)
		if state_hash.length() != 64 or not _is_hex(state_hash):
			return []
		layers.append({
			"layer_index": expected_index,
			"ey": ey,
			"ei": ei,
			"hidden_l2_norm": hidden_norm,
			"hidden_state_sha256": state_hash,
		})
	return layers


func _verify_engine_contract(canonical_layers: Array) -> bool:
	if canonical_layers.size() != LAYER_COUNT:
		return false
	if not _engine.seed_full_field(_zero_field, _zero_field):
		return false
	var baseline_state: Dictionary = _engine.compute_state()
	var baseline_readback: Array = _engine.readback_ey_ei()
	if not _state_is_zero(baseline_state, baseline_readback, 0):
		return false

	var short_ey := PackedFloat32Array()
	short_ey.resize(CELLS - 1)
	if _engine.blend_full_field(short_ey, _zero_field, RETAINED_WEIGHT):
		return false
	if not _unchanged_zero(baseline_state):
		return false

	var nan_ey := PackedFloat32Array()
	nan_ey.resize(CELLS)
	nan_ey[0] = NAN
	if _engine.blend_full_field(nan_ey, _zero_field, RETAINED_WEIGHT):
		return false
	if not _unchanged_zero(baseline_state):
		return false
	var huge_ey := PackedFloat32Array()
	huge_ey.resize(CELLS)
	huge_ey[0] = 1.0e30
	if _engine.blend_full_field(huge_ey, _zero_field, RETAINED_WEIGHT):
		return false
	if not _unchanged_zero(baseline_state):
		return false


	if _engine.blend_full_field(_zero_field, _zero_field, -0.01):
		return false
	if not _unchanged_zero(baseline_state):
		return false
	if _engine.blend_full_field(_zero_field, _zero_field, 1.01):
		return false
	if not _unchanged_zero(baseline_state):
		return false

	_engine.step_n(1)
	var clock_before: Dictionary = _engine.compute_state()
	var first_layer: Dictionary = canonical_layers[0]
	var first_ey: PackedFloat32Array = first_layer["ey"]
	var first_ei: PackedFloat32Array = first_layer["ei"]
	if not _engine.blend_full_field(first_ey, first_ei, RETAINED_WEIGHT):
		return false
	var clock_after: Dictionary = _engine.compute_state()
	if not _clock_equals(clock_before, clock_after):
		return false
	var readback: Array = _engine.readback_ey_ei()
	if readback.size() != 2:
		return false
	var actual_ey: PackedFloat32Array = readback[0]
	var actual_ei: PackedFloat32Array = readback[1]
	var mix_error := _first_blend_error(actual_ey, actual_ei, first_ey, first_ei)
	if not _finite_scalar(mix_error) or mix_error > FIRST_BLEND_TOL:
		return false
	return _engine.seed_full_field(_zero_field, _zero_field)


func _run_arm(spec: Dictionary, source_layers: Array) -> Dictionary:
	var is_reverse: bool = bool(spec["reverse"])
	var layer_order: Array = []
	for order_index in range(LAYER_COUNT):
		layer_order.append(LAYER_COUNT - 1 - order_index if is_reverse else order_index)
	var arm: Dictionary = {
		"id": str(spec["id"]),
		"basis": str(spec["basis"]),
		"layer_order": layer_order,
		"first_blend_contract": {"pass": false, "max_abs_error": -1.0},
		"layer_summaries": [],
		"layer_checkpoints": [],
		"continuation_checkpoints": [],
	}
	if not _engine.seed_full_field(_zero_field, _zero_field):
		return {"arm": arm, "valid": false}
	var initial_state: Dictionary = _engine.compute_state()
	var initial_readback: Array = _engine.readback_ey_ei()
	var arm_valid := _state_is_zero(initial_state, initial_readback, 0)
	var checkpoint_rows: Dictionary = {}
	var first_contract_pass := false
	var first_contract_error := -1.0
	var is_zero_arm: bool = bool(spec["zero"])

	for update_index in range(LAYER_COUNT):
		var layer_index := LAYER_COUNT - 1 - update_index if is_reverse else update_index
		var incoming_ey: PackedFloat32Array = _zero_field
		var incoming_ei: PackedFloat32Array = _zero_field
		if not is_zero_arm:
			var layer_data: Dictionary = source_layers[layer_index]
			incoming_ey = layer_data["ey"]
			incoming_ei = layer_data["ei"]
		var blend_ok: bool = _engine.blend_full_field(incoming_ey, incoming_ei, RETAINED_WEIGHT)
		arm_valid = arm_valid and blend_ok
		if update_index == 0:
			var first_readback: Array = _engine.readback_ey_ei()
			if first_readback.size() == 2:
				var first_ey: PackedFloat32Array = first_readback[0]
				var first_ei: PackedFloat32Array = first_readback[1]
				first_contract_error = _first_blend_error(first_ey, first_ei, incoming_ey, incoming_ei)
				first_contract_pass = _finite_scalar(first_contract_error) and first_contract_error <= FIRST_BLEND_TOL
				if is_zero_arm:
					first_contract_pass = first_contract_pass and _byte_zero(first_ey) and _byte_zero(first_ei)
				else:
					first_contract_pass = first_contract_pass and _finite(first_ey) and _finite(first_ei)
			else:
				first_contract_error = -1.0
				first_contract_pass = false
			arm_valid = arm_valid and first_contract_pass
		for pde_step in range(STEPS_PER_LAYER):
			_engine.step_n(1)
			if is_zero_arm:
				var zero_readback: Array = _engine.readback_ey_ei()
				arm_valid = arm_valid and _readback_is_zero(zero_readback)

		var expected_step := (update_index + 1) * STEPS_PER_LAYER
		var keep_raw := LAYER_CHECKPOINTS.has(layer_index)
		var captured: Dictionary = _capture_state(expected_step, keep_raw)
		var summary: Dictionary = {
			"layer_index": layer_index,
			"update_index": update_index,
			"step": int(captured["step"]),
			"t": float(captured["t"]),
			"finite": bool(captured["finite"]),
			"max_abs": float(captured["max_abs"]),
			"ey_l2": float(captured["ey_l2"]),
			"ei_l2": float(captured["ei_l2"]),
			"epsilon_l2": float(captured["epsilon_l2"]),
		}
		arm["layer_summaries"].append(summary)
		arm_valid = arm_valid and bool(captured["valid"])
		if is_zero_arm:
			arm_valid = arm_valid and bool(captured["zero"])
		if LAYER_CHECKPOINTS.has(layer_index):
			var checkpoint: Dictionary = summary.duplicate()
			checkpoint["ey_b64"] = str(captured["ey_b64"])
			checkpoint["ei_b64"] = str(captured["ei_b64"])
			checkpoint_rows[layer_index] = checkpoint

	arm["first_blend_contract"] = {
		"pass": first_contract_pass,
		"max_abs_error": first_contract_error,
	}
	for checkpoint_layer in LAYER_CHECKPOINTS:
		if not checkpoint_rows.has(checkpoint_layer):
			arm_valid = false
		else:
			arm["layer_checkpoints"].append(checkpoint_rows[checkpoint_layer])

	var previous_horizon := 0
	for horizon_value in CONTINUATION_HORIZONS:
		var horizon := int(horizon_value)
		if horizon < previous_horizon:
			arm_valid = false
			break
		if horizon > previous_horizon:
			var delta := horizon - previous_horizon
			if is_zero_arm:
				for continuation_step in range(delta):
					_engine.step_n(1)
					var continuation_zero: Array = _engine.readback_ey_ei()
					arm_valid = arm_valid and _readback_is_zero(continuation_zero)
			else:
				_engine.step_n(delta)
		var continuation_capture: Dictionary = _capture_state(LAYER_COUNT * STEPS_PER_LAYER + horizon, true)
		var continuation: Dictionary = {
			"horizon": horizon,
			"step": int(continuation_capture["step"]),
			"t": float(continuation_capture["t"]),
			"finite": bool(continuation_capture["finite"]),
			"max_abs": float(continuation_capture["max_abs"]),
			"ey_l2": float(continuation_capture["ey_l2"]),
			"ei_l2": float(continuation_capture["ei_l2"]),
			"epsilon_l2": float(continuation_capture["epsilon_l2"]),
			"ey_b64": str(continuation_capture["ey_b64"]),
			"ei_b64": str(continuation_capture["ei_b64"]),
		}
		arm["continuation_checkpoints"].append(continuation)
		arm_valid = arm_valid and bool(continuation_capture["valid"])
		if is_zero_arm:
			arm_valid = arm_valid and bool(continuation_capture["zero"])
		previous_horizon = horizon
	arm_valid = arm_valid and arm["layer_summaries"].size() == LAYER_COUNT
	arm_valid = arm_valid and arm["layer_checkpoints"].size() == LAYER_CHECKPOINTS.size()
	arm_valid = arm_valid and arm["continuation_checkpoints"].size() == CONTINUATION_HORIZONS.size()
	return {"arm": arm, "valid": arm_valid}


func _capture_state(expected_step: int, include_raw: bool = false) -> Dictionary:
	var readback: Array = _engine.readback_ey_ei()
	var ey: PackedFloat32Array = PackedFloat32Array()
	var ei: PackedFloat32Array = PackedFloat32Array()
	if readback.size() == 2:
		ey = readback[0]
		ei = readback[1]
	var raw_shape := ey.size() == CELLS and ei.size() == CELLS
	var raw_finite := raw_shape and _finite(ey) and _finite(ei)
	var ey_sq := 0.0
	var ei_sq := 0.0
	var epsilon_sq := 0.0
	var max_abs := 0.0
	var derived_finite := raw_finite
	if raw_finite:
		for i in range(CELLS):
			var ey_value: float = ey[i]
			var ei_value: float = ei[i]
			var q_value := ey_value * ey_value + ei_value * ei_value
			var epsilon := ey_value - PHI * ei_value
			if is_nan(q_value) or is_inf(q_value) or is_nan(epsilon) or is_inf(epsilon):
				derived_finite = false
			ey_sq += ey_value * ey_value
			ei_sq += ei_value * ei_value
			epsilon_sq += epsilon * epsilon
			max_abs = maxf(max_abs, maxf(absf(ey_value), absf(ei_value)))
	var ey_l2 := sqrt(ey_sq)
	var ei_l2 := sqrt(ei_sq)
	var epsilon_l2 := sqrt(epsilon_sq)
	var state: Dictionary = _engine.compute_state()
	var actual_step := int(state.get("step", -1))
	var actual_t := float(state.get("t", NAN))
	var metrics_finite := _finite_scalar(ey_l2) and _finite_scalar(ei_l2) \
			and _finite_scalar(epsilon_l2) and _finite_scalar(max_abs)
	var checkpoint_finite := raw_finite and derived_finite and metrics_finite
	var time_ok := _finite_scalar(actual_t) and absf(actual_t - float(expected_step) * DT) <= 1.0e-6
	var valid := checkpoint_finite and actual_step == expected_step and time_ok and max_abs <= MAX_ABS_BOUND
	var ey_b64 := ""
	var ei_b64 := ""
	if include_raw and raw_shape:
		ey_b64 = Marshalls.raw_to_base64(ey.to_byte_array())
		ei_b64 = Marshalls.raw_to_base64(ei.to_byte_array())
	return {
		"step": actual_step,
		"t": actual_t,
		"finite": checkpoint_finite,
		"max_abs": max_abs,
		"ey_l2": ey_l2,
		"ei_l2": ei_l2,
		"epsilon_l2": epsilon_l2,
		"ey_b64": ey_b64,
		"ei_b64": ei_b64,
		"valid": valid,
		"zero": checkpoint_finite and _byte_zero(ey) and _byte_zero(ei),
	}


func _first_blend_error(actual_ey: PackedFloat32Array, actual_ei: PackedFloat32Array,
		incoming_ey: PackedFloat32Array, incoming_ei: PackedFloat32Array) -> float:
	if actual_ey.size() != CELLS or actual_ei.size() != CELLS \
			or incoming_ey.size() != CELLS or incoming_ei.size() != CELLS:
		return INF
	var max_error := 0.0
	var incoming_scale := 1.0 - RETAINED_WEIGHT
	for i in range(CELLS):
		var expected_ey := incoming_scale * incoming_ey[i]
		var expected_ei := incoming_scale * incoming_ei[i]
		var error_ey := absf(actual_ey[i] - expected_ey)
		var error_ei := absf(actual_ei[i] - expected_ei)
		max_error = maxf(max_error, maxf(error_ey, error_ei))
	return max_error


func _state_is_zero(state: Dictionary, readback: Array, expected_step: int) -> bool:
	return int(state.get("step", -1)) == expected_step \
			and _finite_scalar(float(state.get("t", NAN))) \
			and absf(float(state.get("t", NAN)) - float(expected_step) * DT) <= 1.0e-6 \
			and _readback_is_zero(readback)


func _unchanged_zero(before: Dictionary) -> bool:
	var after: Dictionary = _engine.compute_state()
	if not _clock_equals(before, after):
		return false
	return _readback_is_zero(_engine.readback_ey_ei())


func _clock_equals(before: Dictionary, after: Dictionary) -> bool:
	var before_step := int(before.get("step", -1))
	var after_step := int(after.get("step", -1))
	var before_t := float(before.get("t", NAN))
	var after_t := float(after.get("t", NAN))
	return before_step == after_step and _finite_scalar(before_t) and _finite_scalar(after_t) \
			and before_t == after_t


func _readback_is_zero(readback: Array) -> bool:
	if readback.size() != 2:
		return false
	var ey: PackedFloat32Array = readback[0]
	var ei: PackedFloat32Array = readback[1]
	return ey.size() == CELLS and ei.size() == CELLS and _byte_zero(ey) and _byte_zero(ei)


func _finite_scalar(value: float) -> bool:
	return not is_nan(value) and not is_inf(value)


func _finite(values: PackedFloat32Array) -> bool:
	for value in values:
		if is_nan(value) or is_inf(value):
			return false
	return true


func _byte_zero(values: PackedFloat32Array) -> bool:
	var raw: PackedByteArray = values.to_byte_array()
	for byte_value in raw:
		if byte_value != 0:
			return false
	return true


func _any_nonzero(first: PackedFloat32Array, second: PackedFloat32Array) -> bool:
	for value in first:
		if value != 0.0:
			return true
	for value in second:
		if value != 0.0:
			return true
	return false


func _number_equals(value: Variant, expected: float) -> bool:
	if not (value is int or value is float):
		return false
	var actual := float(value)
	return _finite_scalar(actual) and actual == expected


func _numbers_equal(value: Variant, expected: Array) -> bool:
	if not (value is Array):
		return false
	var actual: Array = value
	if actual.size() != expected.size():
		return false
	for i in range(expected.size()):
		if not _number_equals(actual[i], float(expected[i])):
			return false
	return true


func _is_hex(text: String) -> bool:
	for i in range(text.length()):
		var code := text.unicode_at(i)
		var digit := code >= 48 and code <= 57
		var lower := code >= 97 and code <= 102
		var upper := code >= 65 and code <= 70
		if not (digit or lower or upper):
			return false
	return true


func _decode_f32(value: Variant, count: int) -> PackedFloat32Array:
	if not (value is String):
		return PackedFloat32Array()
	var raw: PackedByteArray = Marshalls.base64_to_raw(str(value))
	if raw.size() != count * 4:
		return PackedFloat32Array()
	return raw.to_float32_array()


func _write_and_quit(receipt: Dictionary, message: String) -> void:
	if message != "":
		print("[CassiQwenL17IIR] ", message)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_diag"))
	var tmp_path := GPU_PATH + ".tmp"
	var file: FileAccess = FileAccess.open(tmp_path, FileAccess.WRITE)
	var write_ok := file != null
	if write_ok:
		file.store_string(JSON.stringify(receipt, "\t"))
		file.close()
		var destination_ok := true
		if FileAccess.file_exists(GPU_PATH):
			destination_ok = DirAccess.remove_absolute(ProjectSettings.globalize_path(GPU_PATH)) == OK
		if destination_ok:
			destination_ok = DirAccess.rename_absolute(
				ProjectSettings.globalize_path(tmp_path),
				ProjectSettings.globalize_path(GPU_PATH)) == OK
		write_ok = destination_ok
	if not write_ok:
		receipt["finite"] = false
		receipt["verdict"] = "INVALID"
		print("[CassiQwenL17IIR] failed to atomically write ", GPU_PATH)
	else:
		print("[CassiQwenL17IIR] ", JSON.stringify({
			"verdict": receipt["verdict"], "path": GPU_PATH,
		}))
	if _engine != null:
		_engine.queue_free()
	get_tree().quit(0 if receipt["verdict"] == "PASS" else 1)
