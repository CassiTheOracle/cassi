extends Node3D
## Site-native physics gate.
##
## This arm deliberately runs the production physics topology with a small
## particle count and checks the authoritative site state, source mass,
## cached tree force, telemetry, snapshot contract, and CSR status. It does
## not read any raster field buffer for its verdict.

var _sim: Node
var _started := false
var _outside_probe_started := false
var _frames := 0
var _outside_probe_position := Vector3.ZERO

func _enter_tree() -> void:
	_sim = get_node("CassiSim")
	_sim.ic_seed = 20260819
	_sim.N_particles = 8192
	_sim.grid_N = 64
	_sim.num_clusters = 1
	_sim.cluster_separation = 0.0
	_sim.cluster_radius = 20.0
	_sim.box_scale = 2.0
	_sim.gridless_physics = true
	_sim.boxless_field = true
	_sim.physics_decoupled = true
	_sim.black_holes_enabled = true
	_sim.qi_condensation_threshold = 0.0
	_sim.particle_merge = false
	_sim.suppress_readbacks = true

func _process(_delta: float) -> void:
	_frames += 1
	if not _sim._shaders_ready or _sim._physics_engine == null:
		return
	var eng: RefCounted = _sim._physics_engine
	if not bool(eng.get("_meshless_query_ready")):
		eng.publish_render_query()
	eng.service_render_topology()
	if not bool(eng.get("_topology_ready")):
		if _frames > 1200:
			_fail("topology timeout")
		return
	if not _started:
		_started = true
		eng.set("_cond_step_counter", 99)
		_sim._run_physics_steps(3)
		return
	if _frames < 16:
		return
	if not _outside_probe_started:
		_outside_probe_started = true
		# Put one target just beyond the +X site face. Black-hole point forces
		# are disabled for this extra step so only the production site-tree
		# path can accelerate it; the first three steps retain the BH gate.
		var ext: Vector3 = eng._extents()
		var probe_record: PackedFloat32Array = eng._rd.buffer_get_data(
				eng._pos_buf, 0, 16).to_float32_array()
		if probe_record.size() < 4:
			_fail("outside-force probe position readback failed")
			return
		var center: Vector3 = eng.get("_window_center")
		_outside_probe_position = center + Vector3(ext.x * 1.05, 0.0, 0.0)
		probe_record[0] = _outside_probe_position.x
		probe_record[1] = _outside_probe_position.y
		probe_record[2] = _outside_probe_position.z
		eng._rd.buffer_update(eng._pos_buf, 0, 16, probe_record.to_byte_array())
		var zero_record := PackedFloat32Array([0.0, 0.0, 0.0, 0.0]).to_byte_array()
		eng._rd.buffer_update(eng._vel_buf, 0, 16, zero_record)
		eng._rd.buffer_update(eng._acc_buf, 0, 16, zero_record)
		eng.set("black_holes_enabled", false)
		_sim._run_physics_steps(1)
		return
	var result := _check(eng)
	print("[GridlessPhysics] %s" % [JSON.stringify(result)])
	get_tree().quit(0 if bool(result.get("pass", false)) else 1)

func _check(eng: RefCounted) -> Dictionary:
	var ns := int(eng.get("_ml_tree_nsrc"))
	var sites: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_sites, 0, ns * 16).to_float32_array()
	var psy: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_psi_y, 0, ns * 4).to_float32_array()
	var psi: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_psi_i, 0, ns * 4).to_float32_array()
	var piy: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_pi_y, 0, ns * 4).to_float32_array()
	var pii: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_pi_i, 0, ns * 4).to_float32_array()
	var q: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_q, 0, ns * 4).to_float32_array()
	var vol: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_vol, 0, ns * 4).to_float32_array()
	var mass: PackedFloat32Array = eng._rd.buffer_get_data(eng._ml_mass, 0, ns * 4).to_float32_array()
	var acc: PackedFloat32Array = eng._rd.buffer_get_data(eng._acc_buf, 0, eng.N_particles * 16).to_float32_array()
	var finite := sites.size() == ns * 4 and psy.size() == ns and psi.size() == ns
	var q_ok := true
	var vol_ok := true
	var mass_sum := 0.0
	for i in range(ns):
		finite = finite and is_finite(psy[i]) and is_finite(psi[i]) and is_finite(piy[i]) and is_finite(pii[i])
		q_ok = q_ok and is_finite(q[i]) and q[i] >= -1e-5 and q[i] <= 1.00001
		vol_ok = vol_ok and is_finite(vol[i]) and vol[i] > 0.0
		mass_sum += maxf(mass[i], 0.0)
	var pos: PackedFloat32Array = eng._rd.buffer_get_data(eng._pos_buf, 0, eng.N_particles * 16).to_float32_array()
	var mass_fix: PackedInt32Array = eng._rd.buffer_get_data(eng._ml_mass_fix, 0, ns * 16).to_int32_array()
	var hash_cells: int = int(eng.HASH_H) * int(eng.HASH_H) * int(eng.HASH_H)
	var hash_starts: PackedInt32Array = eng._rd.buffer_get_data(eng._hash_cell_start, 0, (hash_cells + 1) * 4).to_int32_array()
	var hash_cfg: PackedFloat32Array = eng._rd.buffer_get_data(eng._hash_cfg, 0, 16).to_float32_array()
	var hash_sites: PackedInt32Array = eng._rd.buffer_get_data(eng._hash_cell_sites, 0, ns * 4).to_int32_array()
	var pos_mass_sum := 0.0
	for i in range(3, pos.size(), 4):
		pos_mass_sum += maxf(pos[i], 0.0)
	var fix_sum := 0
	for v in mass_fix:
		fix_sum += v
	var first_hash := hash_sites[0] if not hash_sites.is_empty() else -1
	var first_pos := Vector3(pos[0], pos[1], pos[2]) if pos.size() >= 3 else Vector3.ZERO
	var first_tile: Vector3 = first_pos + eng._extents()
	var acc_nonzero := false
	for i in range(0, acc.size(), 4):
		if is_finite(acc[i]) and Vector3(acc[i], acc[i + 1], acc[i + 2]).length_squared() > 1e-14:
			acc_nonzero = true
			break
	var outside_acc := Vector3(acc[0], acc[1], acc[2])
	var outside_force_ok := is_finite(outside_acc.x) and is_finite(outside_acc.y) \
			and is_finite(outside_acc.z) and outside_acc.length_squared() > 1e-14
	var bh: PackedFloat32Array = eng._rd.buffer_get_data(eng._bh_buf, 0, 36 * 16).to_float32_array()
	var bh_mass := 0.0
	for slot in range(15):
		var mass_index := (4 + slot * 2) * 4 + 3
		if mass_index < bh.size():
			bh_mass = maxf(bh_mass, bh[mass_index])
	var bh_ok := is_finite(bh_mass) and bh_mass > 0.0
	var tel: Dictionary = eng.readback_telemetry()
	var snap: Dictionary = eng.readback_snapshot()
	var status: PackedInt32Array = eng._rd.buffer_get_data(eng._topology_status, 0, 16).to_int32_array()
	var pass_gate := bool(eng.gridless_physics) and bool(eng.meshless_mode) and ns > 0 \
		and finite and q_ok and vol_ok and mass_sum > 0.0 and acc_nonzero and bh_ok \
		and outside_force_ok \
		and status.size() >= 4 and status[0] > 0 and status[2] == 0 and status[3] == ns \
		and is_finite(float(tel.get("q_mean", NAN))) and int(snap.get("generation", 0)) > 0
	return {"pass": pass_gate, "sites": ns, "mass_sum": mass_sum, "bh_mass": bh_mass,
		"mass_fix_sum": fix_sum, "particle_mass_sum": pos_mass_sum,
		"first_pos": first_pos, "first_tile": first_tile, "first_hash": first_hash,
		"hash_cfg": hash_cfg, "hash_start0": hash_starts[0] if not hash_starts.is_empty() else -1,
		"hash_start_last": hash_starts[hash_starts.size() - 1] if not hash_starts.is_empty() else -1,
		"acc_nonzero": acc_nonzero, "outside_probe_position": _outside_probe_position,
		"outside_acc": outside_acc, "outside_force_ok": outside_force_ok,
		"topology": status, "telemetry": tel,
		"snapshot_generation": snap.get("generation", 0)}

func _fail(reason: String) -> void:
	print("[GridlessPhysics] FAIL %s" % [reason])
	get_tree().quit(1)
