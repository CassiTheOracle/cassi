extends Node3D
## Registered, isolated native site/particle experiment. No production edits.
## Engine variants only freeze post-setup geometry and select registered scalars.

const PHI := 1.618033988749895
const FLOAT_ROLES := ["pos", "vel", "sites", "site_psi_y", "site_psi_i", "site_pi_y", "site_pi_i", "field_q", "site_eps", "site_vol"]
var _eng = null
var _rd: RenderingDevice = null
var _config: Dictionary = {}
var _input: Dictionary = {}
var _receipt: Dictionary = {}
var _out := ""
var _started_ms := 0
var _steps := 0
var _finished := false
var _initialized := false
var _kicked := false
var _ns := 0
var _input_path := ""
var _accepted_telemetry: Dictionary = {}
var _accepted_raw_telemetry := PackedInt32Array()
var _io_error := ""


func _ready() -> void:
	_started_ms = Time.get_ticks_msec()
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--input="):
			_input_path = argument.trim_prefix("--input=")
	if _input_path.is_empty():
		push_error("NativeSphere requires --input=<registered arm JSON>")
		get_tree().quit(1)
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(_input_path))
	if not parsed is Dictionary:
		push_error("NativeSphere invalid input JSON")
		get_tree().quit(1)
		return
	_input = parsed
	_config = _input["config"]
	_out = str(_input["out_dir"])
	DirAccess.make_dir_recursive_absolute(_out.path_join("blobs"))
	_receipt = {"schema": "cassi_native_sphere_arm_v1", "id": str(_config["id"]),
		"config": _config, "status": "RUNNING", "completed_steps": 0,
		"source_hashes": _input["source_hashes"], "snapshots": [], "errors": [],
		"started_utc": Time.get_datetime_string_from_system(true),
		"engine_variant": _input["engine_variant"], "runtime_seconds": 0.0}
	_save_receipt()
	print("[NativeSphere] BEGIN id=%s frozen=%s radius=%.2f" % [
		str(_config["id"]), str(_config["freeze_field"]), float(_config["radius"])])
	var script := load(str(_input["engine_variant"])) as GDScript
	if script == null or not script.can_instantiate():
		_finish("SETUP_FAILED", "engine variant did not load")
		return
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_finish("SETUP_FAILED", "local RenderingDevice unavailable; windowed run required")
		return
	_eng = script.new()
	var cfg: Dictionary = {
		"rd": _rd, "rd_global": false, "owns_rd": false,
		"N_particles": int(_config["particle_count"]), "grid_N": int(_config["grid_N"]),
		"seed": int(_config["seed"]), "dt": float(_config["dt"]),
		"cluster_radius": 10.0, "box_aspect": Vector3.ONE, "box_scale": 1.0,
		"cluster_separation": 0.0, "num_clusters": 1, "merger_speed": 0.0,
		"initial_condition": 2, "initial_arrangement": 2, "initial_motion": 1,
		"initial_speed": 0.0, "initial_total_mass": float(_config["total_mass"]),
		"initial_radius_fraction": 0.8, "initial_v_circ_factor": 0.0,
		"source_strength": 0.0, "winding_coupling": 0.0, "xi": 17.94427191,
		"gravity_mode": 0, "softening": 0.1, "river_calibrate_gn": false,
		"field_attractor_init": false, "freeze_field": bool(_config["freeze_field"]),
		"meshless_mode": true, "meshless_gravity": true, "gridless_physics": true,
		"boxless_field": false, "home_window": false, "window_center": Vector3.ZERO,
		"physical_matter_enabled": false, "physical_radiation_enabled": false,
		"particle_merge": false, "black_holes_enabled": false, "bh_accretion": false,
		"field_particles": false, "rotation_stress_enabled": false,
		"realsim_drag": 0.0, "realsim_viscosity": 0.0, "realsim_friction": 0.0,
		"dual_grid": false, "multi_rung_seed": false, "cascade_level": false,
		"q_weighted_com": false, "coherence_theta": false,
		"tree_hierarchical_refit": false, "tree_cadence": 1,
	}
	if not bool(_eng.setup(cfg)) or not bool(_eng.finish_setup()):
		_finish("SETUP_FAILED", "native engine setup failed")
		return
	_ns = int(_eng.get("_ml_tree_nsrc"))
	var ext: Vector3 = _eng.call("_extents")
	var expected_ns := 2 * int(_config["site_lattice_n1"]) ** 3
	if _ns != expected_ns or ext.distance_to(Vector3(15.0, 15.0, 15.0)) > 0.00001:
		_finish("SETUP_FAILED", "effective site count or extents differ from registration")
		return
	# Seed the raster label map before the first native topology remap reads it.
	# Initialization alone defers the rebuild; all accepted dynamics are boxless.
	_eng.boxless_field = true
	_eng.call("_ml_scatter_and_jfa")
	_eng.call("_mesh_rebuild")
	_receipt["topology_initialization"] = "native_scatter_and_jfa_before_first_rebuild"
	if bool(_eng.physical_matter_active()) or bool(_eng.physical_radiation_active()):
		_finish("SETUP_FAILED", "excluded physical matter/radiation mode active")
		return
	_receipt["runtime_configuration"] = {"gridless_physics": bool(_eng.gridless_physics),
		"physical_matter_active": bool(_eng.physical_matter_active()),
		"physical_radiation_active": bool(_eng.physical_radiation_active()),
		"particle_merge": bool(_eng.particle_merge), "black_holes_enabled": bool(_eng.black_holes_enabled),
		"freeze_field": bool(_eng.freeze_field), "site_count": _ns,
		"grid_N": int(_eng.grid_N), "extents": [ext.x, ext.y, ext.z],
		"tree_cadence": 1, "accepted_steps_per_request": 1,
		"particle_count": int(_eng.N_particles), "boxless_field": bool(_eng.boxless_field),
		"geometry_mode": str(_config["geometry_mode"])}
	if not _seed_particles():
		return
	if not _restore_registered_field():
		return
	_initialized = true
	_refresh_observation(true)
	if not _snapshot("initial"):
		return
	print("[NativeSphere] READY sites=%d topology=%d" % [_ns, int(_eng.get("_topology_generation"))])


func _restore_registered_field() -> bool:
	# The initial local topology rebuild includes a state-remap pass. Seed the
	# registered native IID field after that geometry operation, not before it.
	var sites := _rd.buffer_get_data(_eng.get("_ml_sites"), 0, _ns * 16).to_float32_array()
	# Local topology moves tile sites without publishing the renderer's derived
	# world-source buffer. Publish that same coordinate transform once at t=0.
	var world_sites := sites.duplicate()
	var ext: Vector3 = _eng.call("_extents")
	for s in range(_ns):
		world_sites[4 * s] -= ext.x
		world_sites[4 * s + 1] -= ext.y
		world_sites[4 * s + 2] -= ext.z
	_rd.buffer_update(_eng.get("_ml_sites_world"), 0, world_sites.size() * 4, world_sites.to_byte_array())
	_eng.call("_init_site_state_direct", sites, _ns, _eng.call("_extents"))
	var y := _rd.buffer_get_data(_eng.get("_ml_psi_y"), 0, _ns * 4).to_float32_array()
	var i := _rd.buffer_get_data(_eng.get("_ml_psi_i"), 0, _ns * 4).to_float32_array()
	var y_min := INF
	var y_max := -INF
	var i_min := INF
	var i_max := -INF
	for s in range(_ns):
		y_min = minf(y_min, y[s])
		y_max = maxf(y_max, y[s])
		i_min = minf(i_min, i[s])
		i_max = maxf(i_max, i[s])
	if y_min >= y_max or i_min >= i_max \
			or minf(y_min, i_min) < -0.010001 or maxf(y_max, i_max) > 0.010001:
		_finish("SETUP_FAILED", "registered independent native field initialization did not land")
		return false
	_receipt["field_initialization"] = {
		"method": "native_init_site_state_direct_after_initial_topology",
		"tree_source_geometry": "current_tile_sites_minus_fixed_extents_at_origin",
		"seed": int(_config["seed"]), "ey_min": y_min, "ey_max": y_max,
		"ei_min": i_min, "ei_max": i_max,
		"ey_sha256": _sha(y.to_byte_array()), "ei_sha256": _sha(i.to_byte_array())}
	return true


func _seed_particles() -> bool:
	var n := int(_config["particle_count"])
	var radius := float(_config["radius"])
	var mass := float(_config["total_mass"]) / float(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = int(_config["seed"]) + 0x504F5349
	var pos := PackedFloat32Array()
	var vel := PackedFloat32Array()
	var acc := PackedFloat32Array()
	pos.resize(n * 4)
	vel.resize(n * 4)
	acc.resize(n * 4)
	var center := Vector3.ZERO
	for p in range(n):
		var z := rng.randf_range(-1.0, 1.0)
		var angle := rng.randf_range(0.0, TAU)
		var radial := pow(rng.randf(), 1.0 / 3.0)
		var xy := sqrt(maxf(0.0, 1.0 - z * z))
		var v := Vector3(xy * cos(angle), xy * sin(angle), z) * radial
		pos[4 * p] = v.x
		pos[4 * p + 1] = v.y
		pos[4 * p + 2] = v.z
		pos[4 * p + 3] = mass
		center += v
	center /= float(n)
	var support := 0.0
	for p in range(n):
		var v := Vector3(pos[4 * p], pos[4 * p + 1], pos[4 * p + 2]) - center
		support = maxf(support, v.length())
	for p in range(n):
		var v := (Vector3(pos[4 * p], pos[4 * p + 1], pos[4 * p + 2]) - center) * (radius / support)
		pos[4 * p] = v.x
		pos[4 * p + 1] = v.y
		pos[4 * p + 2] = v.z
	var buffers: Dictionary = _eng.workbench_read_buffers()
	buffers["pos"] = pos
	buffers["pvel"] = vel
	buffers["acc"] = acc
	var result: Dictionary = _eng.workbench_write_buffers(buffers, true)
	if not bool(result.get("ok", false)):
		_finish("SETUP_FAILED", "particle IC commit rejected: " + str(result))
		return false
	_eng.call("_invalidate_particle_queries")
	return true


func _process(_delta: float) -> void:
	if _finished or not _initialized:
		return
	if (Time.get_ticks_msec() - _started_ms) / 1000.0 > float(_config["wall_timeout_seconds"]):
		_finish("TIMEOUT", "registered wall-clock stopping rule")
		return
	for _index in range(8):
		if _steps >= int(_config["target_steps"]):
			_finish("COMPLETE", "")
			return
		# One accepted step per tree build: not an eight-step cached-force batch.
		_eng.run_steps(1, true)
		var observed := int(_eng.get("_executed"))
		if observed != _steps + 1:
			_finish("EXECUTION_FAILED", "accepted step counter did not advance exactly once")
			return
		_steps = observed
		var is_kick := _steps == int(_config["perturb_step"]) and not _kicked
		if _steps % int(_config["snapshot_stride"]) == 0 or _steps == int(_config["target_steps"]) or is_kick:
			_refresh_observation(false)
			if not _snapshot("before_perturbation" if is_kick else "sample"):
				return
		if is_kick:
			if not _apply_kick():
				return
			_kicked = true
			_refresh_observation(true)
			if not _snapshot("after_perturbation"):
				return
		if _steps % 200 == 0:
			print("[NativeSphere] PROGRESS id=%s step=%d/%d t=%.3f" % [
				str(_config["id"]), _steps, int(_config["target_steps"]), float(_eng.get("_time"))])


func _apply_kick() -> bool:
	var buffers: Dictionary = _eng.workbench_read_buffers()
	var pos: PackedFloat32Array = buffers["pos"]
	var vel: PackedFloat32Array = buffers["pvel"]
	var n := int(_config["particle_count"])
	var com := Vector3.ZERO
	var mass := 0.0
	for p in range(n):
		var mp := float(pos[4 * p + 3])
		com += mp * Vector3(pos[4 * p], pos[4 * p + 1], pos[4 * p + 2])
		mass += mp
	com /= mass
	var kicks := PackedVector3Array()
	kicks.resize(n)
	var mean_kick := Vector3.ZERO
	var speed := float(_config["perturb_fraction"]) * sqrt(pow(PHI, -3.0) * mass / float(_config["radius"]))
	for p in range(n):
		var delta := Vector3(pos[4 * p], pos[4 * p + 1], pos[4 * p + 2]) - com
		kicks[p] = delta.normalized() * speed
		mean_kick += float(pos[4 * p + 3]) * kicks[p]
	mean_kick /= mass
	for p in range(n):
		var kick := kicks[p] - mean_kick
		vel[4 * p] += kick.x
		vel[4 * p + 1] += kick.y
		vel[4 * p + 2] += kick.z
	buffers["pvel"] = vel
	var result: Dictionary = _eng.workbench_write_buffers(buffers, true)
	if not bool(result.get("ok", false)):
		_finish("EXECUTION_FAILED", "perturbation commit rejected: " + str(result))
		return false
	_eng.call("_invalidate_particle_queries")
	_receipt["perturbation"] = {"step": _steps, "t": float(_eng.get("_time")),
		"nominal_speed": speed, "mean_kick_removed": [mean_kick.x, mean_kick.y, mean_kick.z],
		"commit_backend": str(result.get("backend", ""))}
	return true


func _refresh_observation(initialize_acceleration: bool) -> void:
	# Refresh deposited/source/derived readouts at the accepted particle boundary.
	# No field commit or particle drift. Acceleration is initialized only after an IC/kick.
	_accepted_telemetry = _eng.readback_telemetry()
	_accepted_raw_telemetry = _rd.buffer_get_data(_eng.get("_tel_buf"), 0, 48).to_int32_array()
	_eng.update_bh_header()
	var cl := _rd.compute_list_begin()
	_eng.call("_site_mass_dispatches", cl)
	_eng.call("_site_physics_dispatch", cl, 0.0)
	_eng.call("_site_physics_dispatch", cl, 2.0)
	_eng.call("_tree_run_in_list", cl)
	if initialize_acceleration:
		_eng.call("_site_nbody_dispatch", cl, 2.0)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	if initialize_acceleration:
		_eng.set("_grav_warmup", false)


func _snapshot(phase: String) -> bool:
	var data: Dictionary = _eng.readback_snapshot()
	var pos: PackedFloat32Array = data["pos"]
	var ey: PackedFloat32Array = data["site_psi_y"]
	var ei: PackedFloat32Array = data["site_psi_i"]
	for role in FLOAT_ROLES:
		var values: PackedFloat32Array = data[role]
		for value in values:
			if not is_finite(value):
				_finish("NUMERICAL_STOP", "nonfinite authoritative role " + str(role))
				return false
	for volume in data["site_vol"]:
		if float(volume) <= 0.0:
			_finish("TOPOLOGY_FAILED", "registered positive-volume topology condition failed")
			return false
	for index in range(ey.size()):
		if absf(ey[index]) > 1.0e6 or absf(ei[index]) > 1.0e6:
			_finish("NUMERICAL_STOP", "registered field-amplitude safety bound")
			return false
	for index in range(0, pos.size(), 4):
		if Vector3(pos[index], pos[index + 1], pos[index + 2]).length() > 1.0e6 * float(_config["radius"]):
			_finish("NUMERICAL_STOP", "registered particle-distance safety bound")
			return false
	var topo_bytes := _rd.buffer_get_data(_eng.get("_topology_status"), 0, 16)
	var topo := topo_bytes.to_int32_array()
	if topo.size() != 4 or topo[0] <= 0 or topo[1] <= 0 or topo[2] != 0 or topo[3] != _ns:
		_finish("TOPOLOGY_FAILED", "invalid/nonfiring topology status: " + str(topo))
		return false
	var files: Dictionary = {}
	for role in FLOAT_ROLES:
		var values: PackedFloat32Array = data[role]
		files[role] = _store(values.to_byte_array(), "float32")
	var extra: Dictionary = {"acc": ["_acc_buf", int(_config["particle_count"]) * 16],
		"site_mass": ["_ml_mass", _ns * 4], "tree_sources": ["_tl_src", _ns * 32],
		"tree_weights": ["_tl_srcw", _ns * 4]}
	for role in extra:
		var desc: Array = extra[role]
		var bytes := _rd.buffer_get_data(_eng.get(str(desc[0])), 0, int(desc[1]))
		files[role] = _store(bytes, "float32")
	if _steps == 0 or _steps == int(_config["target_steps"]):
		var offsets := _rd.buffer_get_data(_eng.get("_topology_offsets"), 0, (_ns + 1) * 4)
		var offset_values := offsets.to_int32_array()
		var edges := int(offset_values[_ns])
		files["offsets"] = _store(offsets, "uint32")
		files["neighbors"] = _store(_rd.buffer_get_data(_eng.get("_topology_neighbors"), 0, edges * 4), "uint32")
		for role in ["lap_y", "lap_i", "grad_y", "grad_i"]:
			var key := "_ml_" + str(role)
			var count := _ns * (4 if str(role).begins_with("grad") else 1)
			files[role] = _store(_rd.buffer_get_data(_eng.get(key), 0, count * 4), "float32")
	var telemetry: Dictionary = _eng.readback_telemetry()
	if not _io_error.is_empty():
		_finish("IO_FAILED", _io_error)
		return false
	var raw_tel := _rd.buffer_get_data(_eng.get("_tel_buf"), 0, 48).to_int32_array()
	if raw_tel[10] <= 0:
		_finish("TOPOLOGY_FAILED", "zero field operator samples")
		return false
	var frame: Dictionary = {"step": _steps, "t": float(_eng.get("_time")), "phase": phase,
		"files": files, "topology_status": Array(topo), "telemetry": telemetry,
		"field_operator_samples": int(raw_tel[10]), "source_boundary_step": _steps,
		"accepted_step_telemetry": _accepted_telemetry,
		"accepted_step_raw_telemetry": Array(_accepted_raw_telemetry),
		"observation_refresh": "mass_derived_tree_only_no_field_commit_no_particle_drift",
		"wall_seconds": (Time.get_ticks_msec() - _started_ms) / 1000.0}
	_receipt["snapshots"].append(frame)
	_save_receipt()
	return true


func _sha(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()


func _store(bytes: PackedByteArray, dtype: String) -> Dictionary:
	var raw_sha := _sha(bytes)
	var relative := "blobs/" + raw_sha + ".gz"
	var path := _out.path_join(relative)
	var compressed := bytes.compress(FileAccess.COMPRESSION_GZIP)
	if not FileAccess.file_exists(path):
		var file := FileAccess.open(path, FileAccess.WRITE)
		if file == null:
			_io_error = "could not write " + path
		else:
			file.store_buffer(compressed)
			file.close()
	return {"path": relative, "sha256": _sha(compressed), "bytes": compressed.size(),
		"count": bytes.size() / 4, "encoding": "gzip", "dtype": dtype,
		"raw_sha256": raw_sha, "raw_bytes": bytes.size()}


func _save_receipt() -> void:
	_receipt["completed_steps"] = _steps
	_receipt["runtime_seconds"] = (Time.get_ticks_msec() - _started_ms) / 1000.0
	var file := FileAccess.open(_out.path_join("receipt.json"), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(_receipt, "\t"))
		file.close()


func _finish(status: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	_receipt["status"] = status
	if not reason.is_empty():
		_receipt["errors"].append(reason)
	_save_receipt()
	print("[NativeSphere] END id=%s status=%s steps=%d seconds=%.3f reason=%s" % [
		str(_config.get("id", "unknown")), status, _steps,
		float(_receipt.get("runtime_seconds", 0.0)), reason])
	if _eng != null:
		_eng.shutdown()
		_eng = null
	if _rd != null:
		_rd.free()
		_rd = null
	get_tree().quit(0 if status == "COMPLETE" else 1)
