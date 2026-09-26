extends Node
## CassiQwen L15 — deterministic full-field GPU receipt.
##
## This is deliberately a windowed, bridge-off probe. It consumes only the
## prepared CPU fixture, seeds the canonical mind engine through
## seed_full_field(), and records cumulative checkpoints. No model, bridge, or
## network action is involved.

const PROTOCOL := "CassiQwen L15 embedding-to-field lift"
const VERSION := 1
const SEED_PATH := "res://_diag/cassi_qwen_embedding_field_seed.json"
const GPU_PATH := "res://_diag/cassi_qwen_embedding_field_gpu.json"
const GRID_N := 32
const DIMENSION := 1536
const PHI := 1.618033988749895
const AMPLITUDE := 1.0
const DT := 0.005
const LAYOUT := "x + N*(y + N*z)"
const DTYPE := "float32-le"
const HORIZONS := [0, 1, 4, 16, 64, 256, 1024, 2048]
const CASE_IDS := [
	"anchor", "near", "orthogonal", "opposite",
	"anchor_shuffled", "near_shuffled", "zero",
]
const CASE_BASIS := {
	"anchor": "canonical",
	"near": "canonical",
	"orthogonal": "canonical",
	"opposite": "canonical",
	"anchor_shuffled": "shuffled",
	"near_shuffled": "shuffled",
	"zero": "zero",
}

var _engine: Node
var _cells: int = GRID_N * GRID_N * GRID_N


func _ready() -> void:
	var seed: Dictionary = _read_seed()
	var receipt: Dictionary = _new_receipt()
	var prepared: Array = []
	if seed.is_empty() or not _prepare_seed(seed, prepared):
		_write_and_quit(receipt, "seed configuration or case-size validation failed")
		return

	_engine = load("res://scripts/cassi_mind_engine.gd").new()
	_engine.grid_n = GRID_N
	_engine.auto_step = false
	_engine.serve_bridge = false
	add_child(_engine)
	if _engine._rd == null or not _engine._pipe.is_valid():
		_write_and_quit(receipt, "canonical mind engine initialization failed")
		return

	var receipt_cases: Array = []
	var run_valid: bool = true
	for prepared_value in prepared:
		var prepared_case: Dictionary = prepared_value
		var run: Dictionary = _run_case(prepared_case)
		receipt_cases.append(run["case"])
		run_valid = run_valid and bool(run["valid"])
	receipt["cases"] = receipt_cases
	receipt["finite"] = run_valid
	receipt["verdict"] = "PASS" if run_valid else "INVALID"
	_write_and_quit(receipt, "" if run_valid else "one or more GPU checkpoints violated the receipt contract")


func _new_receipt() -> Dictionary:
	return {
		"protocol": PROTOCOL,
		"version": VERSION,
		"grid_n": GRID_N,
		"dimension": DIMENSION,
		"phi": PHI,
		"dt": DT,
		"layout": LAYOUT,
		"dtype": DTYPE,
		"horizons": HORIZONS.duplicate(),
		"cases": [],
		"finite": false,
		"verdict": "INVALID",
	}


func _read_seed() -> Dictionary:
	if not FileAccess.file_exists(SEED_PATH):
		return {}
	var file: FileAccess = FileAccess.open(SEED_PATH, FileAccess.READ)
	if file == null:
		return {}
	var text: String = file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		return {}
	return parsed


func _prepare_seed(seed: Dictionary, prepared: Array) -> bool:
	if str(seed.get("protocol", "")) != PROTOCOL:
		return false
	var version_value: Variant = seed.get("version", -1)
	if not _number_equals(version_value, float(VERSION)):
		return false
	if not _number_equals(seed.get("grid_n", -1), float(GRID_N)):
		return false
	if not _number_equals(seed.get("dimension", -1), float(DIMENSION)):
		return false
	if not _number_equals(seed.get("phi", NAN), PHI):
		return false
	if not _number_equals(seed.get("amplitude", NAN), AMPLITUDE):
		return false
	if not _number_equals(seed.get("dt", NAN), DT):
		return false
	if str(seed.get("layout", "")) != LAYOUT or str(seed.get("dtype", "")) != DTYPE:
		return false

	var horizons_value: Variant = seed.get("horizons", null)
	if not (horizons_value is Array):
		return false
	var seed_horizons: Array = horizons_value
	if seed_horizons.size() != HORIZONS.size():
		return false
	for i in range(HORIZONS.size()):
		var horizon_value: Variant = seed_horizons[i]
		if not _number_equals(horizon_value, float(HORIZONS[i])):
			return false

	var basis_value: Variant = seed.get("basis", null)
	if not (basis_value is Dictionary):
		return false
	var cases_value: Variant = seed.get("cases", null)
	if not (cases_value is Array):
		return false
	var seed_cases: Array = cases_value
	if seed_cases.size() != CASE_IDS.size():
		return false

	var by_id: Dictionary = {}
	for case_value in seed_cases:
		if not (case_value is Dictionary):
			return false
		var case_data: Dictionary = case_value
		var case_id: String = str(case_data.get("id", ""))
		if not CASE_BASIS.has(case_id) or by_id.has(case_id):
			return false
		var basis_label: String = str(case_data.get("basis", ""))
		if basis_label != str(CASE_BASIS[case_id]):
			return false

		var signed_field: PackedFloat32Array = _decode_f32(case_data.get("signal_b64", null), _cells)
		var ey: PackedFloat32Array = _decode_f32(case_data.get("ey_b64", null), _cells)
		var ei: PackedFloat32Array = _decode_f32(case_data.get("ei_b64", null), _cells)
		if signed_field.size() != _cells or ey.size() != _cells or ei.size() != _cells:
			return false
		if not _finite(signed_field) or not _finite(ey) or not _finite(ei):
			return false

		var embedding_value: Variant = case_data.get("embedding_b64", null)
		var embedding := PackedFloat32Array()
		if case_id == "zero":
			if embedding_value != null:
				return false
			if not _byte_zero(signed_field) or not _byte_zero(ey) or not _byte_zero(ei):
				return false
		else:
			if embedding_value == null:
				return false
			embedding = _decode_f32(embedding_value, DIMENSION)
			if embedding.size() != DIMENSION or not _finite(embedding):
				return false
		by_id[case_id] = {
			"id": case_id,
			"basis": basis_label,
			"embedding": embedding,
			"signal": signed_field,
			"ey": ey,
			"ei": ei,
		}

	if by_id.size() != CASE_IDS.size():
		return false
	for case_id in CASE_IDS:
		if not by_id.has(case_id):
			return false
		prepared.append(by_id[case_id])
	return true


func _number_equals(value: Variant, expected: float) -> bool:
	if not (value is int or value is float):
		return false
	var actual: float = float(value)
	return not is_nan(actual) and not is_inf(actual) and actual == expected


func _decode_f32(value: Variant, count: int) -> PackedFloat32Array:
	if not (value is String):
		return PackedFloat32Array()
	var encoded: String = str(value)
	var raw: PackedByteArray = Marshalls.base64_to_raw(encoded)
	if raw.size() != count * 4:
		return PackedFloat32Array()
	return raw.to_float32_array()


func _run_case(prepared_case: Dictionary) -> Dictionary:
	var receipt_case: Dictionary = {
		"id": str(prepared_case["id"]),
		"basis": str(prepared_case["basis"]),
		"checkpoints": [],
	}
	var seed_ey: PackedFloat32Array = prepared_case["ey"]
	var seed_ei: PackedFloat32Array = prepared_case["ei"]
	if not _engine.seed_full_field(seed_ey, seed_ei):
		return {"case": receipt_case, "valid": false}

	var checkpoints: Array = []
	var case_valid: bool = true
	var previous_step: int = 0
	for horizon_value in HORIZONS:
		var target_step: int = int(horizon_value)
		if target_step < previous_step:
			case_valid = false
			break
		if target_step > previous_step:
			_engine.step_n(target_step - previous_step)
		var captured: Dictionary = _capture_checkpoint(target_step)
		checkpoints.append(captured["checkpoint"])
		var checkpoint_valid: bool = bool(captured["valid"])
		if str(prepared_case["id"]) == "zero":
			checkpoint_valid = checkpoint_valid and bool(captured["zero"])
		case_valid = case_valid and checkpoint_valid
		previous_step = target_step
	receipt_case["checkpoints"] = checkpoints
	return {"case": receipt_case, "valid": case_valid and checkpoints.size() == HORIZONS.size()}


func _capture_checkpoint(expected_step: int) -> Dictionary:
	var readback: Array = _engine.readback_ey_ei()
	var ey: PackedFloat32Array = readback[0]
	var ei: PackedFloat32Array = readback[1]
	var raw_finite: bool = ey.size() == _cells and ei.size() == _cells \
			and _finite(ey) and _finite(ei)
	var ey_l2: float = 0.0
	var ei_l2: float = 0.0
	var epsilon_l2: float = 0.0
	var max_abs: float = 0.0
	if raw_finite:
		var ey_sq: float = 0.0
		var ei_sq: float = 0.0
		var epsilon_sq: float = 0.0
		for i in range(_cells):
			var ey_value: float = ey[i]
			var ei_value: float = ei[i]
			ey_sq += ey_value * ey_value
			ei_sq += ei_value * ei_value
			var epsilon: float = ey_value - PHI * ei_value
			epsilon_sq += epsilon * epsilon
			max_abs = maxf(max_abs, maxf(absf(ey_value), absf(ei_value)))
		ey_l2 = sqrt(ey_sq)
		ei_l2 = sqrt(ei_sq)
		epsilon_l2 = sqrt(epsilon_sq)
	var state: Dictionary = _engine.compute_state()
	var actual_step: int = int(state.get("step", -1))
	var actual_t: float = float(state.get("t", NAN))
	var metrics_finite: bool = _finite_scalar(ey_l2) and _finite_scalar(ei_l2) \
			and _finite_scalar(epsilon_l2) and _finite_scalar(max_abs)
	var checkpoint_finite: bool = raw_finite and metrics_finite
	var time_ok: bool = _finite_scalar(actual_t) \
			and absf(actual_t - float(expected_step) * DT) <= 1.0e-6
	var valid: bool = checkpoint_finite and actual_step == expected_step \
			and time_ok and max_abs <= 10.0
	var checkpoint: Dictionary = {
		"step": actual_step,
		"t": actual_t,
		"finite": checkpoint_finite,
		"max_abs": max_abs,
		"ey_l2": ey_l2,
		"ei_l2": ei_l2,
		"epsilon_l2": epsilon_l2,
		"ey_b64": Marshalls.raw_to_base64(ey.to_byte_array()),
		"ei_b64": Marshalls.raw_to_base64(ei.to_byte_array()),
	}
	return {
		"checkpoint": checkpoint,
		"valid": valid,
		"zero": checkpoint_finite and _byte_zero(ey) and _byte_zero(ei),
	}


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


func _write_and_quit(receipt: Dictionary, message: String) -> void:
	if message != "":
		print("[CassiQwenEmbeddingField] ", message)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_diag"))
	var file: FileAccess = FileAccess.open(GPU_PATH, FileAccess.WRITE)
	if file == null:
		receipt["finite"] = false
		receipt["verdict"] = "INVALID"
		print("[CassiQwenEmbeddingField] failed to write ", GPU_PATH)
	else:
		file.store_string(JSON.stringify(receipt, "\t"))
		file.close()
		print("[CassiQwenEmbeddingField] ", JSON.stringify({
			"verdict": receipt["verdict"], "path": GPU_PATH,
		}))
	if _engine != null:
		_engine.queue_free()
	get_tree().quit(0 if receipt["verdict"] != "INVALID" else 1)
