extends Node

const N := 32
const STEPS := 16
const SIGMA := 0.5
const ANSWER := Vector3(-0.125, 0.0, 0.0)
const RETRIEVE := Vector3(0.125, 0.0, 0.0)
const ALIGNED_RELAY := Vector3.ZERO
const SHUFFLED_RELAY := Vector3(0.0, 0.0, 0.75)

var _engine: Node


func _ready() -> void:
	_engine = load("res://scripts/cassi_mind_engine.gd").new()
	_engine.grid_n = N
	_engine.auto_step = false
	_engine.serve_bridge = false
	add_child(_engine)
	if _engine._rd == null or not _engine._pipe.is_valid():
		_write_and_quit({"protocol": "CassiQwen L14 local pool coupling", "verdict": "INVALID", "reason": "engine initialization failed"})
		return
	var receipt: Dictionary = {"protocol": "CassiQwen L14 local pool coupling", "arms": {}}
	for arm in ["off", "aligned", "shuffled", "swapped"]:
		receipt["arms"][arm] = _run_arm(arm)
	var aligned: Dictionary = receipt["arms"]["aligned"]
	var shuffled: Dictionary = receipt["arms"]["shuffled"]
	var swapped: Dictionary = receipt["arms"]["swapped"]
	var invalid: bool = not bool(aligned.get("finite", false)) or not bool(shuffled.get("finite", false)) or not bool(swapped.get("finite", false))
	if invalid:
		receipt["verdict"] = "INVALID"
	elif abs(float(aligned["answer_retrieve_difference"]) - float(shuffled["answer_retrieve_difference"])) <= 1.0e-9:
		receipt["verdict"] = "NULL"
	elif abs(float(aligned["answer_retrieve_difference"]) - float(swapped["answer_retrieve_difference"])) <= 1.0e-9:
		receipt["verdict"] = "NULL"
	else:
		receipt["verdict"] = "MECHANISM-DIFFERENCE"
	_write_and_quit(receipt)


func _write_and_quit(receipt: Dictionary) -> void:
	var path := "res://_diag/cassi_qwen_local_pool.json"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(receipt, "\t"))
		file.close()
	print("[CassiQwenLocalPool] ", JSON.stringify({"verdict": receipt.get("verdict", "INVALID"), "path": path}))
	_engine.queue_free()
	get_tree().quit(0 if receipt.get("verdict", "INVALID") != "INVALID" else 1)


func _run_arm(arm: String) -> Dictionary:
	_engine._clear_field()
	_engine.deposit(ANSWER.x, ANSWER.y, ANSWER.z, 0.8466667, 0.0875, SIGMA)
	_engine.deposit(RETRIEVE.x, RETRIEVE.y, RETRIEVE.z, 0.7066667, 0.08, SIGMA)
	if arm != "off":
		var relay_position: Vector3 = ALIGNED_RELAY if arm != "shuffled" else SHUFFLED_RELAY
		var resolve_cy := 0.62
		var resolve_ci := 0.05
		var block_cy := 0.05
		var block_ci := 0.62
		if arm == "swapped":
			resolve_cy = 0.05
			resolve_ci = 0.62
			block_cy = 0.62
			block_ci = 0.05
		_engine.deposit(relay_position.x, relay_position.y, relay_position.z, resolve_cy, resolve_ci, SIGMA)
		_engine.deposit(relay_position.x, relay_position.y, relay_position.z, block_cy, block_ci, SIGMA)
	_engine._flush_pending()
	if arm != "off":
		_engine.step_n(STEPS)
	var readback: Array = _engine.readback_ey_ei()
	var ey: PackedFloat32Array = readback[0]
	var ei: PackedFloat32Array = readback[1]
	var answer_q := _local_q(ey, ei, ANSWER)
	var retrieve_q := _local_q(ey, ei, RETRIEVE)
	var state: Dictionary = _engine.compute_state()
	var finite: bool = is_finite(answer_q) and is_finite(retrieve_q) and answer_q >= 0.0 and retrieve_q >= 0.0 and is_finite(float(state["max_eps2"]))
	return {"finite": finite, "state": state, "answer_q": answer_q, "retrieve_q": retrieve_q, "answer_retrieve_difference": answer_q - retrieve_q}


func _local_q(ey: PackedFloat32Array, ei: PackedFloat32Array, position: Vector3) -> float:
	var gx: int = int(floor((position.x + 1.0) * 0.5 * float(N) + 0.5)) % N
	var gy: int = int(floor((position.y + 1.0) * 0.5 * float(N) + 0.5)) % N
	var gz: int = int(floor((position.z + 1.0) * 0.5 * float(N) + 0.5)) % N
	var total := 0.0
	var offsets := [Vector3i.ZERO, Vector3i.LEFT, Vector3i.RIGHT, Vector3i.UP, Vector3i.DOWN, Vector3i(0, 0, 1), Vector3i(0, 0, -1)]
	for offset in offsets:
		var x: int = (gx + offset.x + N) % N
		var y: int = (gy + offset.y + N) % N
		var z: int = (gz + offset.z + N) % N
		var index: int = x * N * N + y * N + z
		total += ey[index] * ey[index] + ei[index] * ei[index]
	return total
