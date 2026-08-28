extends Node

const N := 32
const STEPS := 16
const ROLES := {
	"answer": Vector3(0.72, 0.0, 0.0),
	"clarify": Vector3(-0.72, 0.0, 0.0),
	"retrieve": Vector3(0.0, 0.72, 0.0),
	"think": Vector3(0.0, -0.72, 0.0),
	"tool": Vector3(0.0, 0.0, 0.72),
	"stop": Vector3(0.0, 0.0, -0.72),
	"abstain": Vector3.ZERO,
}
const CANDIDATE_FEATURES := {
	"answer": {"support": 0.88, "goal": 0.90, "urgency": 0.76, "contradiction": 0.12, "missing": 0.08, "risk": 0.08, "cost": 0.05},
	"retrieve": {"support": 0.62, "goal": 0.80, "urgency": 0.70, "contradiction": 0.05, "missing": 0.10, "risk": 0.05, "cost": 0.12},
}

var _engine: Node


func _ready() -> void:
	_engine = load("res://scripts/cassi_mind_engine.gd").new()
	_engine.grid_n = N
	_engine.auto_step = false
	_engine.serve_bridge = false
	add_child(_engine)
	if _engine._rd == null or not _engine._pipe.is_valid():
		_write_and_quit({"protocol": "CassiQwen L11c GPU relational parity", "verdict": "INVALID", "reason": "engine initialization failed"})
		return
	var receipt: Dictionary = {"protocol": "CassiQwen L11c GPU relational parity", "arms": {}}
	for arm in ["field_off", "relation_aligned", "relation_shuffled", "channel_swapped"]:
		receipt["arms"][arm] = _run_arm(arm)
	var aligned: Dictionary = receipt["arms"]["relation_aligned"]
	var shuffled: Dictionary = receipt["arms"]["relation_shuffled"]
	var swapped: Dictionary = receipt["arms"]["channel_swapped"]
	var invalid: bool = not bool(aligned.get("finite", false)) or not bool(shuffled.get("finite", false)) or not bool(swapped.get("finite", false))
	if invalid:
		receipt["verdict"] = "INVALID"
	elif is_equal_approx(float(aligned["answer_retrieve_difference"]), float(shuffled["answer_retrieve_difference"])):
		receipt["verdict"] = "NULL"
	elif is_equal_approx(float(aligned["answer_retrieve_difference"]), float(swapped["answer_retrieve_difference"])):
		receipt["verdict"] = "NULL"
	else:
		receipt["verdict"] = "MECHANISM-DIFFERENCE"
	_write_and_quit(receipt)


func _write_and_quit(receipt: Dictionary) -> void:
	var path := "res://_diag/cassi_qwen_relational_field.json"
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(receipt, "\t"))
		file.close()
	print("[CassiQwenRelational] ", JSON.stringify({"verdict": receipt.get("verdict", "INVALID"), "path": path}))
	_engine.queue_free()
	get_tree().quit(0 if receipt.get("verdict", "INVALID") != "INVALID" else 1)


func _run_arm(arm: String) -> Dictionary:
	_engine._clear_field()
	for role in ROLES:
		var features: Dictionary = CANDIDATE_FEATURES.get(role, {"support": 0.05, "goal": 0.05, "urgency": 0.05, "contradiction": 0.05, "missing": 0.05, "risk": 0.05, "cost": 0.05})
		var cy: float = (features["support"] + features["goal"] + features["urgency"]) / 3.0
		var ci: float = (features["contradiction"] + features["missing"] + features["risk"] + features["cost"]) / 4.0
		var position: Vector3 = ROLES[role]
		_engine.deposit(position.x, position.y, position.z, cy, ci, 1.0)
	if arm != "field_off":
		var source: Vector3 = ROLES["retrieve"]
		var target: Vector3 = ROLES["answer"] if arm != "relation_shuffled" else ROLES["stop"]
		var relay: Vector3 = (source + target) * 0.5
		var resolve_cy := 0.62
		var resolve_ci := 0.05
		var block_cy := 0.05
		var block_ci := 0.62
		if arm == "channel_swapped":
			resolve_cy = 0.05
			resolve_ci = 0.62
			block_cy = 0.62
			block_ci = 0.05
		_engine.deposit(relay.x, relay.y, relay.z, resolve_cy, resolve_ci, 1.0)
		_engine.deposit(relay.x, relay.y, relay.z, block_cy, block_ci, 1.0)
	_engine._flush_pending()
	if arm != "field_off":
		_engine.step_n(STEPS)
	var readback: Array = _engine.readback_ey_ei()
	var ey: PackedFloat32Array = readback[0]
	var ei: PackedFloat32Array = readback[1]
	var local_q: Dictionary = {}
	var finite: bool = true
	for role in ROLES:
		local_q[role] = _local_q(ey, ei, ROLES[role])
		finite = finite and is_finite(float(local_q[role])) and float(local_q[role]) >= 0.0
	var state: Dictionary = _engine.compute_state()
	finite = finite and is_finite(float(state["max_eps2"]))
	return {"finite": finite, "state": state, "local_q": local_q, "answer_retrieve_difference": float(local_q["answer"]) - float(local_q["retrieve"])}


func _local_q(ey: PackedFloat32Array, ei: PackedFloat32Array, position: Vector3) -> float:
	var gx: int = int(floor((position.x + 1.0) * 0.5 * float(N) + 0.5)) % N
	var gy: int = int(floor((position.y + 1.0) * 0.5 * float(N) + 0.5)) % N
	var gz: int = int(floor((position.z + 1.0) * 0.5 * float(N) + 0.5)) % N
	var total := 0.0
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			for dz in range(-1, 2):
				var x: int = (gx + dx + N) % N
				var y: int = (gy + dy + N) % N
				var z: int = (gz + dz + N) % N
				var index: int = x * N * N + y * N + z
				total += ey[index] * ey[index] + ei[index] * ei[index]
	return total
