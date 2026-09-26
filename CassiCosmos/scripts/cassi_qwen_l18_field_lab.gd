extends Node
## CassiQwen L18 field laboratory.
##
## This scene owns the only TCP listener for the laboratory and instantiates
## the canonical two-fluid engine as a child.  The engine remains on its local
## RenderingDevice; the laboratory never enables the engine bridge.

const PROTOCOL := "CassiQwen L18 field-output loop"
const VERSION := 1
const HOST := "127.0.0.1"
const PORT := 7601
const GRID_N := 32
const CELLS := GRID_N * GRID_N * GRID_N
const DT := 0.005
const PHI := 1.618033988749895
const LAYOUT := "x + N*(y + N*z)"
const DTYPE := "float32-le"
const RETAINED_WEIGHT := 0.9
const STEPS_PER_LAYER := 4
const TRUNK_LAYER_COUNT := 64
const RECEIPT_PATH := "res://_diag/cassi_qwen_l18_field_lab.jsonl"

var _engine: Node
var _server: TCPServer
var _peers: Array[StreamPeerTCP] = []
var _peer_buf: Dictionary = {}
var _zero_field := PackedFloat32Array()
var _token_index := -1
var _layer_index := -1
var _event_count := 0
var _event_log: Array = []
var _closing := false
var _receipt_written := false


func _ready() -> void:
	_zero_field.resize(CELLS)
	var engine_script: GDScript = load("res://scripts/cassi_mind_engine.gd") as GDScript
	if engine_script == null:
		push_error("[CassiQwenL18FieldLab] canonical mind engine script load failed")
		return
	var child: Variant = engine_script.new()
	if not (child is Node):
		push_error("[CassiQwenL18FieldLab] canonical mind engine is not a Node")
		return
	_engine = child
	_engine.set("grid_n", GRID_N)
	_engine.set("dt", DT)
	_engine.set("auto_step", false)
	_engine.set("serve_bridge", false)
	add_child(_engine)

	_server = TCPServer.new()
	var listen_error: Error = _server.listen(PORT, HOST)
	if listen_error != OK:
		push_error("[CassiQwenL18FieldLab] TCP listen failed: %d" % listen_error)
		return
	print("[CassiQwenL18FieldLab] ready N=%d dt=%.4f host=%s port=%d" % [GRID_N, DT, HOST, PORT])


func _process(_delta: float) -> void:
	if _closing or _server == null:
		return
	_poll_server()


func _exit_tree() -> void:
	if _server != null:
		_server.stop()
	for peer in _peers:
		peer.disconnect_from_host()
	_peers.clear()
	_peer_buf.clear()


func _poll_server() -> void:
	while _server.is_connection_available():
		var peer: StreamPeerTCP = _server.take_connection()
		if peer != null:
			_peers.append(peer)
			_peer_buf[peer] = PackedByteArray()

	var dead: Array[StreamPeerTCP] = []
	for peer in _peers:
		if peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			dead.append(peer)
			continue
		var available: int = peer.get_available_bytes()
		if available <= 0:
			continue
		var packet: Array = peer.get_data(available)
		if packet.size() < 2 or packet[0] != OK:
			continue
		var accumulated: PackedByteArray = _peer_buf[peer]
		accumulated.append_array(packet[1])
		var consumed: int = 0
		while true:
			var newline: int = accumulated.find(10, consumed)
			if newline < 0:
				break
			var line: String = accumulated.slice(consumed, newline).get_string_from_utf8()
			consumed = newline + 1
			var response: String = _handle_line(line)
			if response != "":
				peer.put_data((response + "\n").to_utf8_buffer())
			if _closing:
				break
		if consumed > 0:
			accumulated = accumulated.slice(consumed)
		_peer_buf[peer] = accumulated
		if _closing:
			break

	for peer in dead:
		_peers.erase(peer)
		_peer_buf.erase(peer)


func _handle_line(line: String) -> String:
	var parsed: Variant = JSON.parse_string(line)
	if parsed == null or not (parsed is Dictionary):
		return _error_response("", "bad json")
	var request: Dictionary = parsed
	var command: String = str(request.get("cmd", ""))
	match command:
		"hello":
			return _hello_response()
		"reset":
			return _reset_response()
		"blend":
			return _blend_response(request)
		"readout":
			return _readout_response()
		"snapshot":
			return _snapshot_response()
		"restore":
			return _restore_response(request)
		"shutdown":
			return _shutdown_response()
		_:
			return _error_response(command, "unknown cmd: " + command)


func _hello_response() -> String:
	var response := _base_response("hello")
	response["server"] = {"host": HOST, "port": PORT, "lab_only": true}
	response["engine"] = {"grid_n": GRID_N, "dt": DT, "auto_step": false, "serve_bridge": false}
	response["field"] = _field_schema()
	var state: Dictionary = _state_payload()
	response["state"] = state
	response["finite"] = bool(state.get("finite", false))
	return JSON.stringify(response)


func _reset_response() -> String:
	if _engine == null:
		return _error_response("reset", "canonical engine unavailable")
	if not _engine.seed_full_field(_zero_field, _zero_field):
		return _error_response("reset", "canonical engine rejected zero field")
	_token_index = -1
	_layer_index = -1
	var response := _base_response("reset")
	var captured: Dictionary = _capture_field(false)
	response["state"] = captured["state"]
	response["metrics"] = captured["metrics"]
	response["field"] = captured["field"]
	response["finite"] = bool(captured["valid"])
	return JSON.stringify(response)


func _snapshot_response() -> String:
	if _engine == null:
		return _error_response("snapshot", "canonical engine unavailable")
	var captured: Dictionary = _capture_field(true)
	var response := _base_response("snapshot")
	response["state"] = captured["state"]
	response["metrics"] = captured["metrics"]
	response["field"] = captured["field"]
	response["ey_b64"] = str(captured["field"].get("ey_b64", ""))
	response["ei_b64"] = str(captured["field"].get("ei_b64", ""))
	response["event_count"] = _event_count
	response["finite"] = bool(captured["valid"])
	return JSON.stringify(response)


func _restore_response(request: Dictionary) -> String:
	if _engine == null:
		return _error_response("restore", "canonical engine unavailable")
	var ey_result: Dictionary = _decode_field(request.get("ey_b64", null))
	var ei_result: Dictionary = _decode_field(request.get("ei_b64", null))
	if not bool(ey_result["ok"]) or not bool(ei_result["ok"]):
		return _error_response("restore", "ey_b64 and ei_b64 must each contain exactly %d finite f32 values" % CELLS)
	var step_result: Dictionary = _read_integer(request, "step")
	var time_result: Dictionary = _read_number(request, "t")
	var token_result: Dictionary = _read_integer(request, "token_index")
	var layer_result: Dictionary = _read_integer(request, "layer_index")
	var count_result: Dictionary = _read_integer(request, "event_count")
	if not bool(step_result["ok"]) or not bool(time_result["ok"]) \
			or not bool(token_result["ok"]) or not bool(layer_result["ok"]) \
			or not bool(count_result["ok"]):
		return _error_response("restore", "step, t, token_index, layer_index, and event_count must be finite integers/numbers")
	var step_value: int = int(step_result["value"])
	var time_value: float = float(time_result["value"])
	var token_value: int = int(token_result["value"])
	var layer_value: int = int(layer_result["value"])
	var event_count_value: int = int(count_result["value"])
	if step_value < 0 or token_value < -1 or layer_value < -1 or layer_value >= TRUNK_LAYER_COUNT \
			or event_count_value < 0:
		return _error_response("restore", "restore metadata is outside the field session bounds")
	if not _engine.restore_full_field(ey_result["values"], ei_result["values"], step_value, time_value):
		return _error_response("restore", "canonical engine rejected field or clock")
	_token_index = token_value
	_layer_index = layer_value
	_event_count = event_count_value
	_event_log.clear()
	var captured: Dictionary = _capture_field(true)
	var response := _base_response("restore")
	response["state"] = captured["state"]
	response["metrics"] = captured["metrics"]
	response["field"] = captured["field"]
	response["ey_b64"] = str(captured["field"].get("ey_b64", ""))
	response["ei_b64"] = str(captured["field"].get("ei_b64", ""))
	response["event_count"] = _event_count
	response["finite"] = bool(captured["valid"])
	return JSON.stringify(response)


func _blend_response(request: Dictionary) -> String:
	var token_result: Dictionary = _read_integer(request, "token_index")
	var layer_result: Dictionary = _read_integer(request, "layer_index")
	if not bool(token_result["ok"]) or not bool(layer_result["ok"]):
		return _error_response("blend", "token_index and layer_index must be integers")
	var token_value: int = int(token_result["value"])
	var layer_value: int = int(layer_result["value"])
	if token_value < 0 or layer_value < 0 or layer_value >= TRUNK_LAYER_COUNT:
		return _error_response_with_metadata("blend", "token/layer index out of range", token_value, layer_value)

	var retained_result: Dictionary = _read_number(request, "retained_weight")
	if not bool(retained_result["ok"]):
		return _error_response_with_metadata("blend", "retained_weight must be finite", token_value, layer_value)
	var retained: float = float(retained_result["value"])
	if retained < 0.0 or retained > 1.0 or retained != RETAINED_WEIGHT:
		return _error_response_with_metadata("blend", "retained_weight must equal %.6f" % RETAINED_WEIGHT, token_value, layer_value)

	var steps_result: Dictionary = _read_integer(request, "steps_per_layer")
	if not bool(steps_result["ok"]) or int(steps_result["value"]) != STEPS_PER_LAYER:
		return _error_response_with_metadata("blend", "steps_per_layer must equal %d" % STEPS_PER_LAYER, token_value, layer_value)

	var ey_result: Dictionary = _decode_field(request.get("ey_b64", null))
	var ei_result: Dictionary = _decode_field(request.get("ei_b64", null))
	if not bool(ey_result["ok"]) or not bool(ei_result["ok"]):
		return _error_response_with_metadata("blend", "ey_b64 and ei_b64 must each contain exactly %d finite f32 values" % CELLS, token_value, layer_value)
	var ey: PackedFloat32Array = ey_result["values"]
	var ei: PackedFloat32Array = ei_result["values"]
	if _engine == null:
		return _error_response_with_metadata("blend", "canonical engine unavailable", token_value, layer_value)
	if not _engine.blend_full_field(ey, ei, retained):
		return _error_response_with_metadata("blend", "canonical engine rejected full-field blend", token_value, layer_value)
	_engine.step_n(STEPS_PER_LAYER)

	_token_index = token_value
	_layer_index = layer_value
	_event_count += 1
	var captured: Dictionary = _capture_field(false)
	var captured_state: Dictionary = captured["state"]
	var captured_field: Dictionary = captured["field"]
	var response := _base_response("blend")
	response["token_index"] = _token_index
	response["layer_index"] = _layer_index
	response["steps_per_layer"] = STEPS_PER_LAYER
	response["retained_weight"] = retained
	response["state"] = captured_state
	response["metrics"] = captured["metrics"]
	response["field"] = captured_field
	response["finite"] = bool(captured["valid"])
	_event_log.append({
		"event_index": _event_count - 1,
		"token_index": _token_index,
		"layer_index": _layer_index,
		"step": int(captured_state.get("step", -1)),
		"t": float(captured_state.get("t", 0.0)),
		"field_sha256": str(captured_field.get("sha256", "")),
		"metrics": captured["metrics"],
		"finite": bool(captured["valid"]),
	})
	return JSON.stringify(response)


func _readout_response() -> String:
	if _engine == null:
		return _error_response("readout", "canonical engine unavailable")
	var captured: Dictionary = _capture_field(true)
	var response := _base_response("readout")
	response["state"] = captured["state"]
	response["metrics"] = captured["metrics"]
	response["field"] = captured["field"]
	var captured_field: Dictionary = captured["field"]
	response["ey_b64"] = str(captured_field.get("ey_b64", ""))
	response["ei_b64"] = str(captured_field.get("ei_b64", ""))
	response["finite"] = bool(captured["valid"])
	return JSON.stringify(response)


func _shutdown_response() -> String:
	if _closing:
		return _error_response("shutdown", "shutdown already requested")
	_closing = true
	call_deferred("_finish_shutdown")
	var response := _base_response("shutdown")
	response["receipt_path"] = RECEIPT_PATH
	response["event_count"] = _event_count
	return JSON.stringify(response)


func _finish_shutdown() -> void:
	if _receipt_written:
		return
	_receipt_written = true
	var captured: Dictionary = {}
	if _engine != null:
		captured = _capture_field(false)
	var receipt := {
		"protocol": PROTOCOL,
		"version": VERSION,
		"host": HOST,
		"port": PORT,
		"grid_n": GRID_N,
		"cells": CELLS,
		"dt": DT,
		"phi": PHI,
		"layout": LAYOUT,
		"dtype": DTYPE,
		"retained_weight": RETAINED_WEIGHT,
		"steps_per_layer": STEPS_PER_LAYER,
		"token_index": _token_index,
		"layer_index": _layer_index,
		"event_count": _event_count,
		"events": _event_log,
		"state": captured.get("state", {}),
		"metrics": captured.get("metrics", {}),
		"field": captured.get("field", {}),
		"finite": bool(captured.get("valid", false)),
	}
	_write_receipt(receipt)
	if _engine != null:
		_engine.queue_free()
	if _server != null:
		_server.stop()
	get_tree().quit(0)


func _capture_field(include_b64: bool) -> Dictionary:
	if _engine == null:
		return {"valid": false, "state": {}, "metrics": {"finite": false}, "field": {}}
	var readback: Array = _engine.readback_ey_ei()
	if readback.size() != 2:
		return {"valid": false, "state": _state_payload(), "metrics": {"finite": false}, "field": {}}
	var ey: PackedFloat32Array = readback[0]
	var ei: PackedFloat32Array = readback[1]
	var shaped: bool = ey.size() == CELLS and ei.size() == CELLS
	var finite_values: bool = shaped and _finite_values(ey) and _finite_values(ei)
	var metrics: Dictionary = _field_metrics(ey, ei, shaped and finite_values)
	var field: Dictionary = _field_payload(ey, ei, include_b64)
	var valid: bool = shaped and finite_values and bool(metrics.get("finite", false))
	return {"valid": valid, "state": _state_payload(), "metrics": metrics, "field": field}


func _state_payload() -> Dictionary:
	if _engine == null:
		return {"step": -1, "t": 0.0, "token_index": _token_index, "layer_index": _layer_index, "finite": false}
	var source: Dictionary = _engine.compute_state()
	var state := {
		"step": int(source.get("step", -1)),
		"t": float(source.get("t", 0.0)),
		"mean_ey": float(source.get("mean_ey", 0.0)),
		"mean_ei": float(source.get("mean_ei", 0.0)),
		"max_eps2": float(source.get("max_eps2", 0.0)),
		"token_index": _token_index,
		"layer_index": _layer_index,
	}
	state["finite"] = _finite_scalar(float(state["t"])) \
			and _finite_scalar(float(state["mean_ey"])) \
			and _finite_scalar(float(state["mean_ei"])) \
			and _finite_scalar(float(state["max_eps2"]))
	return state


func _field_metrics(ey: PackedFloat32Array, ei: PackedFloat32Array, valid_values: bool) -> Dictionary:
	if not valid_values:
		return {"finite": false, "ey_l2": 0.0, "ei_l2": 0.0, "epsilon_l2": 0.0, "max_abs": 0.0}
	var ey_sq := 0.0
	var ei_sq := 0.0
	var epsilon_sq := 0.0
	var max_abs := 0.0
	var finite_derived := true
	for i in range(CELLS):
		var ey_value: float = ey[i]
		var ei_value: float = ei[i]
		var q_value: float = ey_value * ey_value + ei_value * ei_value
		var epsilon: float = ey_value - PHI * ei_value
		var epsilon_value: float = epsilon * epsilon
		if is_nan(q_value) or is_inf(q_value) or is_nan(epsilon_value) or is_inf(epsilon_value):
			finite_derived = false
		ey_sq += ey_value * ey_value
		ei_sq += ei_value * ei_value
		epsilon_sq += epsilon_value
		max_abs = maxf(max_abs, maxf(absf(ey_value), absf(ei_value)))
	var ey_l2: float = sqrt(ey_sq)
	var ei_l2: float = sqrt(ei_sq)
	var epsilon_l2: float = sqrt(epsilon_sq)
	var finite: bool = finite_derived and _finite_scalar(ey_l2) and _finite_scalar(ei_l2) \
			and _finite_scalar(epsilon_l2) and _finite_scalar(max_abs)
	return {
		"finite": finite,
		"ey_l2": ey_l2,
		"ei_l2": ei_l2,
		"epsilon_l2": epsilon_l2,
		"max_abs": max_abs,
	}


func _field_payload(ey: PackedFloat32Array, ei: PackedFloat32Array, include_b64: bool) -> Dictionary:
	var ey_raw: PackedByteArray = ey.to_byte_array()
	var ei_raw: PackedByteArray = ei.to_byte_array()
	var ey_descriptor: Dictionary = _raw_descriptor(ey_raw, include_b64)
	var ei_descriptor: Dictionary = _raw_descriptor(ei_raw, include_b64)
	var ey_hash: String = str(ey_descriptor["sha256"])
	var ei_hash: String = str(ei_descriptor["sha256"])
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(ey_raw)
	context.update(ei_raw)
	var combined_hash: String = context.finish().hex_encode()
	var field := {
		"grid_n": GRID_N,
		"dtype": DTYPE,
		"shape": [CELLS],
		"volume_shape": [GRID_N, GRID_N, GRID_N],
		"layout": LAYOUT,
		"ey": ey_descriptor,
		"ei": ei_descriptor,
		"ey_sha256": ey_hash,
		"ei_sha256": ei_hash,
		"sha256": combined_hash,
		"bytes": ey_raw.size() + ei_raw.size(),
	}
	if include_b64:
		field["ey_b64"] = Marshalls.raw_to_base64(ey_raw)
		field["ei_b64"] = Marshalls.raw_to_base64(ei_raw)
	return field


func _raw_descriptor(raw: PackedByteArray, include_b64: bool) -> Dictionary:
	var descriptor := {
		"dtype": DTYPE,
		"shape": [CELLS],
		"layout": LAYOUT,
		"bytes": raw.size(),
		"sha256": _sha256(raw),
	}
	if include_b64:
		descriptor["b64"] = Marshalls.raw_to_base64(raw)
	return descriptor


func _field_schema() -> Dictionary:
	return {
		"grid_n": GRID_N,
		"cells": CELLS,
		"shape": [CELLS],
		"volume_shape": [GRID_N, GRID_N, GRID_N],
		"channels": 2,
		"channel_names": ["EY", "EI"],
		"dtype": DTYPE,
		"layout": LAYOUT,
		"phi": PHI,
	}


func _decode_field(value: Variant) -> Dictionary:
	if not (value is String):
		return {"ok": false, "values": PackedFloat32Array()}
	var raw: PackedByteArray = Marshalls.base64_to_raw(str(value))
	if raw.size() != CELLS * 4:
		return {"ok": false, "values": PackedFloat32Array()}
	var values: PackedFloat32Array = raw.to_float32_array()
	if values.size() != CELLS or not _finite_values(values):
		return {"ok": false, "values": PackedFloat32Array()}
	return {"ok": true, "values": values}


func _finite_values(values: PackedFloat32Array) -> bool:
	for value in values:
		if is_nan(value) or is_inf(value):
			return false
	return true


func _finite_scalar(value: float) -> bool:
	return not is_nan(value) and not is_inf(value)


func _read_number(request: Dictionary, key: String) -> Dictionary:
	var value: Variant = request.get(key, null)
	if not (value is int or value is float):
		return {"ok": false, "value": 0.0}
	var number: float = float(value)
	return {"ok": _finite_scalar(number), "value": number}


func _read_integer(request: Dictionary, key: String) -> Dictionary:
	var value: Variant = request.get(key, null)
	if not (value is int or value is float):
		return {"ok": false, "value": -1}
	var number: float = float(value)
	if not _finite_scalar(number) or number != floor(number):
		return {"ok": false, "value": -1}
	return {"ok": true, "value": int(number)}


func _base_response(command: String) -> Dictionary:
	return {
		"ok": true,
		"cmd": command,
		"protocol": PROTOCOL,
		"version": VERSION,
		"token_index": _token_index,
		"layer_index": _layer_index,
	}


func _error_response(command: String, message: String) -> String:
	return JSON.stringify({
		"ok": false,
		"cmd": command,
		"protocol": PROTOCOL,
		"version": VERSION,
		"error": message,
		"token_index": _token_index,
		"layer_index": _layer_index,
		"finite": false,
	})


func _error_response_with_metadata(command: String, message: String, token: int, layer: int) -> String:
	return JSON.stringify({
		"ok": false,
		"cmd": command,
		"protocol": PROTOCOL,
		"version": VERSION,
		"error": message,
		"token_index": token,
		"layer_index": layer,
		"finite": false,
	})


func _sha256(raw: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(raw)
	return context.finish().hex_encode()


func _write_receipt(receipt: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_diag"))
	var file: FileAccess = null
	if FileAccess.file_exists(RECEIPT_PATH):
		file = FileAccess.open(RECEIPT_PATH, FileAccess.READ_WRITE)
		if file != null:
			file.seek_end()
	else:
		file = FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file == null:
		push_error("[CassiQwenL18FieldLab] failed to open receipt path: " + RECEIPT_PATH)
		return
	file.store_line(JSON.stringify(receipt))
	file.close()
