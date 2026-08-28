extends Node3D
## Additive, read-only topology/circulation observatory.
##
## The phase is deliberately reconstructed from the live EY/EI pair for each
## snapshot.  It is not a new buffer and it is not a persistent compact phase
## field.  The arm freezes CassiSim, advances small manual batches, reads the
## existing field/particle buffers, writes one receipt, and exits.

const REPORT_PATH: String = "res://_diag/topology_observatory_live.json"
const GRID_N: int = 64
const PARTICLES: int = 4096
const FROZEN_BATCH_STEPS: int = 8
const EPOCH_COUNT: int = 1
const MAX_PARENT_SAMPLES: int = 4096
const PHASE_FIELD_STATUS: String = "transient_derived_from_EY_EI"
const EPSILON: float = 1.0e-20

var sim: Node3D
var _finished: bool = false


func _ready() -> void:
	sim = get_node_or_null("../CassiSim") as Node3D
	if sim == null:
		_fail("CassiSim node not found")
		return
	if not sim.has_method("_run_physics_steps"):
		_fail("CassiSim manual-step method unavailable")
		return

	# This arm is additive: it never changes the default main scene.  The
	# scene-local CassiSim is paused; only explicit frozen batches advance it.
	sim.playing = false
	await get_tree().process_frame
	await get_tree().process_frame
	var waited: int = 0
	while (not bool(sim._shaders_ready)) and waited < 600:
		waited += 1
		await get_tree().process_frame
	if not bool(sim._shaders_ready):
		_fail("CassiSim shaders did not become ready")
		return
	if not _buffers_ready():
		_fail("required live buffers are not ready")
		return

	var self_tests: Dictionary = _run_detector_self_tests()
	if not bool(self_tests.get("passed", false)):
		_fail("detector self-tests failed", {"self_tests": self_tests})
		return
	# One frozen manual batch is enough for the receipt.  The following
	# process-frame waits let CassiSim's renderer-owned compute work finish
	# before the single live readback.
	sim._run_physics_steps(FROZEN_BATCH_STEPS)
	await get_tree().process_frame
	await get_tree().process_frame

	var epochs: Array = []
	var topology_summaries: Array = []
	var parent_summaries: Array = []
	var phase_rate_summaries: Array = []
	var final_ey := PackedFloat32Array()
	var final_ei := PackedFloat32Array()
	var final_parent_vorticity: float = 0.0
	var final_parent_angular_velocity: float = 0.0

	for epoch in range(EPOCH_COUNT):
		var snap: Dictionary = _read_snapshot()
		if not bool(snap.get("ok", false)):
			_fail(str(snap.get("error", "snapshot readback failed")), {"epoch": epoch})
			return
		var ey: PackedFloat32Array = snap["ey"]
		var ei: PackedFloat32Array = snap["ei"]
		var q: PackedFloat32Array = snap["q"]
		var q_summary: Dictionary = _scalar_summary(q)
		var pi_y: PackedFloat32Array = snap["pi_y"]
		var pi_i: PackedFloat32Array = snap["pi_i"]
		var topology: Dictionary = _detect_topology(ey, ei, sim.grid_N)
		var parent: Dictionary = _estimate_parent_circulation(snap.get("pos", PackedFloat32Array()), snap.get("particle_vel", PackedFloat32Array()), sim.N_particles)
		var phase_rate: Dictionary = _compute_child_phase_rate(ey, ei, pi_y, pi_i, parent)
		var epoch_record: Dictionary = {
			"epoch": epoch,
			"step": int(sim._step_count),
			"t": float(sim._step_count) * float(sim.dt),
			"topology": topology,
			"parent_circulation": parent,
			"child_phase_rate": phase_rate,
			"q_summary": q_summary,
			"phase_field_status": PHASE_FIELD_STATUS,
		}
		epochs.append(epoch_record)
		topology_summaries.append(topology)
		parent_summaries.append(parent)
		phase_rate_summaries.append(phase_rate)
		final_ey = ey
		final_ei = ei
		final_parent_vorticity = float(parent.get("vorticity_z", 0.0))
		final_parent_angular_velocity = float(parent.get("angular_velocity_z", 0.0))
		print("[topology-observatory] epoch=%d step=%d plaquettes=%d defects=%d components=%d omega_z=%s child=%s" % [
			epoch, int(sim._step_count), int(topology.get("plaquettes", 0)),
			int(topology.get("nonzero_count", 0)), int(topology.get("component_count", 0)),
			_sci(final_parent_angular_velocity), _sci(float(phase_rate.get("weighted_mean", 0.0)))])

	if final_ey.size() != sim.grid_N * sim.grid_N * sim.grid_N:
		_fail("no final snapshot available")
		return

	# The GPU uses idx3 order (x fastest).  The frozen JSON contract uses
	# C-order (z fastest) so numpy reshape((N,N,N)) addresses [x,y,z].
	var receipt_ey := _to_receipt_order(final_ey, sim.grid_N)
	var receipt_ei := _to_receipt_order(final_ei, sim.grid_N)
	var report: Dictionary = {
		"status": "measured",
		"phase_field_status": PHASE_FIELD_STATUS,
		"grid_N": sim.grid_N,
		"ey": receipt_ey,
		"ei": receipt_ei,
		"parent_vorticity": final_parent_vorticity,
		"config": _config(),
		"epochs": epochs,
		"detector_convention": _detector_convention(),
		"detector_self_tests": self_tests,
		"topology_summaries": topology_summaries,
		"parent_circulation_summaries": parent_summaries,
		"child_phase_rate_summaries": phase_rate_summaries,
		"live_snapshot": {
			"grid_N": sim.grid_N,
			"ey": receipt_ey,
			"ei": receipt_ei,
			"parent_vorticity": final_parent_vorticity,
			"parent_angular_velocity_z": final_parent_angular_velocity,
			"phase_field_status": PHASE_FIELD_STATUS,
		},
	}
	if not _write_report(report):
		_fail("cannot write observatory report")
		return
	_finished = true
	get_tree().quit(0)


func _config() -> Dictionary:
	return {
		"grid_N": int(sim.grid_N),
		"N_particles": int(sim.N_particles),
		"dt": float(sim.dt),
		"gravity_mode": int(sim.gravity_mode),
		"box_scale": float(sim.box_scale),
		"cluster_radius": float(sim.cluster_radius),
		"gridless_physics": bool(sim.gridless_physics),
		"meshless_mode": bool(sim.meshless_mode),
		"physics_decoupled": bool(sim.physics_decoupled),
		"playing": false,
		"source_strength": float(sim.source_strength),
		"field_attractor_init": bool(sim.field_attractor_init),
		"black_holes_enabled": bool(sim.black_holes_enabled),
		"particle_merge": bool(sim.particle_merge),
		"bh_accretion": bool(sim.bh_accretion),
		"ic_seed": int(sim.ic_seed),
	}


func _scalar_summary(values: PackedFloat32Array) -> Dictionary:
	var count: int = 0
	var total: float = 0.0
	var min_value: float = INF
	var max_value: float = -INF
	for value in values:
		if not is_finite(value):
			continue
		count += 1
		total += value
		min_value = minf(min_value, value)
		max_value = maxf(max_value, value)
	return {
		"finite_count": count,
		"mean": total / float(count) if count > 0 else null,
		"min": min_value if count > 0 else null,
		"max": max_value if count > 0 else null,
	}


func _detector_convention() -> Dictionary:
	return {
		"phase": "theta=atan2(EI,EY), using GDScript atan(y,x)",
		"edge_wrap": "(-pi,pi]",
		"plaquette_orientation": "XY then YZ then ZX, positive circulation follows the listed right-hand normal",
		"winding": "round(sum(delta_theta)/(2*pi))",
		"dual_defect": "nonzero open-domain plaquettes become dual lattice edges; endpoints follow (xy: (x,y,z-1)->(x,y,z), yz: (x-1,y,z)->(x,y,z), zx: (x,y-1,z)->(x,y,z))",
		"boundary_crossing": "an edge crosses the open boundary when either endpoint is -1 or n-1 along its dual-link normal axis",
		"phase_field_status": PHASE_FIELD_STATUS,
		"child_omega_F": "(EY*PiI-EI*PiY)/(EY^2+EI^2), finite amplitude only",
		"parent_fit": "centered particle position/velocity covariance, deterministic first-sample order",
		"native_buffer_flat_order": "GPU idx3 = x + grid_N*(y + grid_N*z), x fastest; receipt arrays are reordered to C-order (x,y,z), z fastest",
	}


func _buffers_ready() -> bool:
	if not is_instance_valid(sim):
		return false
	var rd = sim._rd
	if rd == null:
		return false
	if not sim._field_ey.is_valid() or not sim._field_ei.is_valid():
		return false
	if not sim._field_vel.is_valid() or not sim._field_q.is_valid():
		return false
	if not sim._vel_buf.is_valid() or not sim._pos_buf.is_valid():
		return false
	return true


func _read_snapshot() -> Dictionary:
	var n: int = int(sim.grid_N)
	var nc: int = n * n * n
	var np: int = int(sim.N_particles)
	var rd = sim._rd
	var ey: PackedFloat32Array = rd.buffer_get_data(sim._field_ey, 0, nc * 4).to_float32_array()
	var ei: PackedFloat32Array = rd.buffer_get_data(sim._field_ei, 0, nc * 4).to_float32_array()
	var fv: PackedFloat32Array = rd.buffer_get_data(sim._field_vel, 0, nc * 16).to_float32_array()
	var q: PackedFloat32Array = rd.buffer_get_data(sim._field_q, 0, nc * 4).to_float32_array()
	var particle_vel: PackedFloat32Array = rd.buffer_get_data(sim._vel_buf, 0, np * 16).to_float32_array()
	var pos: PackedFloat32Array = rd.buffer_get_data(sim._pos_buf, 0, np * 16).to_float32_array()
	if ey.size() < nc or ei.size() < nc or fv.size() < nc * 4 or q.size() < nc:
		return {"ok": false, "error": "field readback size mismatch"}
	if particle_vel.size() < np * 4 or pos.size() < np * 4:
		return {"ok": false, "error": "particle readback size mismatch"}
	var pi_y := PackedFloat32Array()
	var pi_i := PackedFloat32Array()
	pi_y.resize(nc)
	pi_i.resize(nc)
	for id in range(nc):
		pi_y[id] = fv[id * 4]
		pi_i[id] = fv[id * 4 + 1]
	return {
		"ok": true,
		"ey": ey,
		"ei": ei,
		"q": q,
		"pi_y": pi_y,
		"pi_i": pi_i,
		"particle_vel": particle_vel,
		"pos": pos,
	}


func _wrap_edge(d: float) -> float:
	var w: float = fposmod(d + PI, TAU) - PI
	if w <= -PI:
		w += TAU
	return w


func _theta(ey: PackedFloat32Array, ei: PackedFloat32Array, id: int) -> float:
	return atan2(ei[id], ey[id])


func _idx(x: int, y: int, z: int, n: int) -> int:
	return x + n * (y + n * z)


func _to_receipt_order(values: PackedFloat32Array, n: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(n * n * n)
	for x in range(n):
		for y in range(n):
			for z in range(n):
				var source_id: int = _idx(x, y, z, n)
				var receipt_id: int = x * n * n + y * n + z
				out[receipt_id] = values[source_id]
	return out


func _plaquette(ey: PackedFloat32Array, ei: PackedFloat32Array, n: int, axis: int, x: int, y: int, z: int) -> int:
	var x1: int = x + 1
	var y1: int = y + 1
	var z1: int = z + 1
	var a: int
	var b: int
	var c: int
	var d: int
	if axis == 0: # XY; normal +Z
		a = _idx(x, y, z, n)
		b = _idx(x1, y, z, n)
		c = _idx(x1, y1, z, n)
		d = _idx(x, y1, z, n)
	elif axis == 1: # YZ; normal +X
		a = _idx(x, y, z, n)
		b = _idx(x, y1, z, n)
		c = _idx(x, y1, z1, n)
		d = _idx(x, y, z1, n)
	else: # ZX; normal +Y
		a = _idx(x, y, z, n)
		b = _idx(x, y, z1, n)
		c = _idx(x1, y, z1, n)
		d = _idx(x1, y, z, n)
	var sum: float = _wrap_edge(_theta(ey, ei, b) - _theta(ey, ei, a))
	sum += _wrap_edge(_theta(ey, ei, c) - _theta(ey, ei, b))
	sum += _wrap_edge(_theta(ey, ei, d) - _theta(ey, ei, c))
	sum += _wrap_edge(_theta(ey, ei, a) - _theta(ey, ei, d))
	return int(round(sum / TAU))


func _coord_axis(value: Vector3i, axis: int) -> int:
	if axis == 0:
		return value.x
	if axis == 1:
		return value.y
	return value.z


func _detect_topology(ey: PackedFloat32Array, ei: PackedFloat32Array, n: int) -> Dictionary:
	var total: int = 3 * n * (n - 1) * (n - 1)
	var nonzero: int = 0
	var positive: int = 0
	var negative: int = 0
	var signed_sum: int = 0
	var abs_sum: int = 0
	var amplitude_min: float = INF
	var amplitude_max: float = 0.0
	var phase_valid: bool = ey.size() == n * n * n and ei.size() == n * n * n
	var edges: Array = []
	var endpoint_owner: Dictionary = {}
	var parent: Array = []
	var orientation_nonzero: Array = [0, 0, 0]
	var orientation_positive: Array = [0, 0, 0]
	var orientation_negative: Array = [0, 0, 0]
	var orientation_signed: Array = [0, 0, 0]
	var orientation_max_abs: Array = [0, 0, 0]
	for id in range(mini(ey.size(), ei.size())):
		var amplitude: float = sqrt(ey[id] * ey[id] + ei[id] * ei[id])
		if not is_finite(amplitude):
			phase_valid = false
			continue
		amplitude_min = minf(amplitude_min, amplitude)
		amplitude_max = maxf(amplitude_max, amplitude)
	for axis in range(3):
		var x_limit: int = n if axis == 1 else n - 1
		var y_limit: int = n if axis == 2 else n - 1
		var z_limit: int = n if axis == 0 else n - 1
		for z in range(z_limit):
			for y in range(y_limit):
				for x in range(x_limit):
					var w: int = _plaquette(ey, ei, n, axis, x, y, z)
					if w == 0:
						continue
					nonzero += 1
					orientation_nonzero[axis] += 1
					if w > 0:
						positive += 1
						orientation_positive[axis] += 1
					else:
						negative += 1
						orientation_negative[axis] += 1
					orientation_max_abs[axis] = maxi(int(orientation_max_abs[axis]), absi(w))
					orientation_signed[axis] += w
					abs_sum += absi(w)
					var a: Vector3i
					var b: Vector3i
					if axis == 0:
						a = Vector3i(x, y, z - 1)
						b = Vector3i(x, y, z)
					elif axis == 1:
						a = Vector3i(x - 1, y, z)
						b = Vector3i(x, y, z)
					else:
						a = Vector3i(x, y - 1, z)
						b = Vector3i(x, y, z)
					var edge_id: int = edges.size()
					edges.append({"a": a, "b": b, "w": w, "axis": axis})
					parent.append(edge_id)
					if endpoint_owner.has(a):
						_union(parent, edge_id, int(endpoint_owner[a]))
					else:
						endpoint_owner[a] = edge_id
					if endpoint_owner.has(b):
						_union(parent, edge_id, int(endpoint_owner[b]))
					else:
						endpoint_owner[b] = edge_id
	var grouped: Dictionary = {}
	for edge_id in range(edges.size()):
		var root: int = _find(parent, edge_id)
		var ids: Array = grouped.get(root, [])
		ids.append(edge_id)
		grouped[root] = ids
	var roots: Array = grouped.keys()
	roots.sort()
	var components: Array = []
	var sizes: Array = []
	var signed_components: Array = []
	for component_index in range(roots.size()):
		var ids: Array = grouped[roots[component_index]]
		var degrees: Dictionary = {}
		var orientation_counts: Dictionary = {"xy": 0, "yz": 0, "zx": 0}
		var component_positive: int = 0
		var component_negative: int = 0
		var component_signed: int = 0
		var boundary_crossings: int = 0
		for edge_id in ids:
			var edge: Dictionary = edges[edge_id]
			var a: Vector3i = edge["a"]
			var b: Vector3i = edge["b"]
			var axis: int = int(edge["axis"])
			degrees[a] = int(degrees.get(a, 0)) + 1
			degrees[b] = int(degrees.get(b, 0)) + 1
			var orientation_name: String = ["xy", "yz", "zx"][axis]
			orientation_counts[orientation_name] = int(orientation_counts[orientation_name]) + 1
			var w: int = int(edge["w"])
			component_signed += w
			component_positive += int(w > 0)
			component_negative += int(w < 0)
			var normal_axis: int = 2 if axis == 0 else (0 if axis == 1 else 1)
			boundary_crossings += int(_coord_axis(a, normal_axis) < 0 or _coord_axis(a, normal_axis) >= n)
			boundary_crossings += int(_coord_axis(b, normal_axis) < 0 or _coord_axis(b, normal_axis) >= n)
		var sign: String = "mixed"
		if component_positive > 0 and component_negative == 0:
			sign = "positive"
		elif component_negative > 0 and component_positive == 0:
			sign = "negative"
		var closed: bool = boundary_crossings == 0
		for endpoint in degrees.keys():
			if int(degrees[endpoint]) != 2:
				closed = false
				break
		components.append({
			"component_id": component_index + 1,
			"length": ids.size(),
			"positive_plaquettes": component_positive,
			"negative_plaquettes": component_negative,
			"net_winding": component_signed,
			"sign": sign,
			"closed": closed,
			"boundary_crossings": boundary_crossings,
			"orientation_counts": orientation_counts,
		})
		sizes.append(ids.size())
		signed_components.append(component_signed)
	var orientation_metrics: Dictionary = {}
	var names: Array = ["xy", "yz", "zx"]
	for axis in range(3):
		var x_size: int = n - 1 if axis != 1 else n
		var y_size: int = n - 1 if axis != 2 else n
		var z_size: int = n if axis == 0 else n - 1
		orientation_metrics[names[axis]] = {
			"shape": [x_size, y_size, z_size],
			"nonzero_count": orientation_nonzero[axis],
			"positive_count": orientation_positive[axis],
			"negative_count": orientation_negative[axis],
			"sum_winding": orientation_signed[axis],
			"max_abs_winding": orientation_max_abs[axis],
		}
	var phase_min: Variant = amplitude_min if amplitude_min < INF else null
	var phase_max: Variant = amplitude_max if amplitude_min < INF else null
	return {
		"grid_N": n,
		"plaquettes": total,
		"nonzero_count": nonzero,
		"positive_count": positive,
		"negative_count": negative,
		"signed_winding_sum": signed_sum,
		"absolute_winding_sum": abs_sum,
		"component_count": components.size(),
		"component_sizes": sizes,
		"component_signed_winding": signed_components,
		"components": components,
		"orientation_metrics": orientation_metrics,
		"phase_valid": phase_valid,
		"amplitude_min": phase_min,
		"amplitude_max": phase_max,
		"phase_field_status": PHASE_FIELD_STATUS,
	}




func _find(parent: Array, a: int) -> int:
	var root: int = a
	while int(parent[root]) != root:
		root = int(parent[root])
	var current: int = a
	while int(parent[current]) != current:
		var next: int = int(parent[current])
		parent[current] = root
		current = next
	return root


func _union(parent: Array, a: int, b: int) -> void:
	var ra: int = _find(parent, a)
	var rb: int = _find(parent, b)
	if ra == rb:
		return
	if ra < rb:
		parent[rb] = ra
	else:
		parent[ra] = rb


func _estimate_parent_circulation(pos: PackedFloat32Array, vel: PackedFloat32Array, particle_count: int) -> Dictionary:
	var count: int = mini(particle_count, MAX_PARENT_SAMPLES)
	if pos.size() < count * 4 or vel.size() < count * 4 or count < 2:
		return {"available": false, "reason": "particle position/velocity readback unavailable", "sample_count": 0}
	var mean_p := Vector3.ZERO
	var mean_v := Vector3.ZERO
	for i in range(count):
		var b: int = i * 4
		mean_p += Vector3(pos[b], pos[b + 1], pos[b + 2])
		mean_v += Vector3(vel[b], vel[b + 1], vel[b + 2])
	mean_p /= float(count)
	mean_v /= float(count)
	var numerator: float = 0.0
	var denominator: float = 0.0
	var cross_sum := Vector3.ZERO
	var inertia_xx: float = 0.0
	var inertia_yy: float = 0.0
	var inertia_zz: float = 0.0
	for i in range(count):
		var b: int = i * 4
		var r: Vector3 = Vector3(pos[b], pos[b + 1], pos[b + 2]) - mean_p
		var v: Vector3 = Vector3(vel[b], vel[b + 1], vel[b + 2]) - mean_v
		numerator += r.x * v.y - r.y * v.x
		denominator += r.x * r.x + r.y * r.y
		cross_sum += r.cross(v)
		inertia_xx += r.y * r.y + r.z * r.z
		inertia_yy += r.x * r.x + r.z * r.z
		inertia_zz += r.x * r.x + r.y * r.y
	var omega_z: float = numerator / denominator if denominator > EPSILON else 0.0
	var vorticity_z: float = 2.0 * omega_z
	return {
		"available": denominator > EPSILON,
		"sample_count": count,
		"angular_velocity_z": omega_z,
		"vorticity_z": vorticity_z,
		"position_velocity_covariance_xy": numerator,
		"position_inertia_xy": denominator,
		"cross_covariance": [cross_sum.x, cross_sum.y, cross_sum.z],
		"inertia_diagonal": [inertia_xx, inertia_yy, inertia_zz],
		"mean_position": [mean_p.x, mean_p.y, mean_p.z],
		"mean_velocity": [mean_v.x, mean_v.y, mean_v.z],
	}


func _compute_child_phase_rate(ey: PackedFloat32Array, ei: PackedFloat32Array, pi_y: PackedFloat32Array, pi_i: PackedFloat32Array, parent: Dictionary) -> Dictionary:
	var count: int = mini(ey.size(), mini(ei.size(), mini(pi_y.size(), pi_i.size())))
	var finite_count: int = 0
	var weighted_sum: float = 0.0
	var weighted_sq_sum: float = 0.0
	var weight_sum: float = 0.0
	var min_rate: float = INF
	var max_rate: float = -INF
	for id in range(count):
		var y: float = ey[id]
		var i: float = ei[id]
		var py: float = pi_y[id]
		var pii: float = pi_i[id]
		var amplitude: float = sqrt(y * y + i * i)
		var den: float = y * y + i * i
		if not is_finite(amplitude) or not is_finite(den) or den <= EPSILON:
			continue
		var rate: float = (y * pii - i * py) / den
		if not is_finite(rate):
			continue
		finite_count += 1
		weight_sum += amplitude
		weighted_sum += amplitude * rate
		weighted_sq_sum += amplitude * rate * rate
		min_rate = minf(min_rate, rate)
		max_rate = maxf(max_rate, rate)
	var mean: float = weighted_sum / weight_sum if weight_sum > EPSILON else 0.0
	var variance: float = weighted_sq_sum / weight_sum - mean * mean if weight_sum > EPSILON else 0.0
	var stddev: float = sqrt(maxf(variance, 0.0))
	var parent_available: bool = bool(parent.get("available", false))
	var parent_omega: float = float(parent.get("angular_velocity_z", 0.0))
	var relation: String = "unavailable"
	var signed_product: float = 0.0
	if weight_sum <= EPSILON or finite_count == 0:
		relation = "no_finite_amplitude"
	elif not parent_available or not is_finite(parent_omega):
		relation = "parent_unavailable"
	else:
		signed_product = mean * parent_omega
		var tol: float = 1.0e-9 * maxf(1.0, absf(mean * parent_omega))
		if absf(signed_product) <= tol:
			relation = "near_zero"
		elif signed_product > 0.0:
			relation = "same_sign"
		else:
			relation = "opposite_sign"
	return {
		"grid_N": int(sim.grid_N),
		"finite_count": finite_count,
		"weight_sum_amplitude": weight_sum,
		"weighted_mean": mean,
		"weighted_std": stddev,
		"min": min_rate if finite_count > 0 else null,
		"max": max_rate if finite_count > 0 else null,
		"parent_angular_velocity_z": parent_omega if parent_available else null,
		"signed_product": signed_product if parent_available else null,
		"signed_relation_to_parent": relation,
		"phase_field_status": PHASE_FIELD_STATUS,
	}


func _run_detector_self_tests() -> Dictionary:
	var n: int = 33
	var uniform_y := PackedFloat32Array()
	var uniform_i := PackedFloat32Array()
	uniform_y.resize(n * n * n)
	uniform_i.resize(n * n * n)
	for id in range(uniform_y.size()):
		uniform_y[id] = cos(0.35)
		uniform_i[id] = sin(0.35)
	var uniform := _detect_topology(uniform_y, uniform_i, n)

	var wave_y := PackedFloat32Array()
	var wave_i := PackedFloat32Array()
	wave_y.resize(n * n * n)
	wave_i.resize(n * n * n)
	for z in range(n):
		for y in range(n):
			for x in range(n):
				var theta: float = 0.20 + TAU * 3.0 * float(x) / float(n)
				var id: int = _idx(x, y, z, n)
				wave_y[id] = cos(theta)
				wave_i[id] = sin(theta)
	var plane_wave := _detect_topology(wave_y, wave_i, n)

	var rotated_y := PackedFloat32Array()
	var rotated_i := PackedFloat32Array()
	rotated_y.resize(n * n * n)
	rotated_i.resize(n * n * n)
	for id in range(uniform_y.size()):
		var theta: float = 0.35 + 1.23456789
		rotated_y[id] = cos(theta)
		rotated_i[id] = sin(theta)
	var global_rotation := _detect_topology(rotated_y, rotated_i, n)

	var line_y := PackedFloat32Array()
	var line_i := PackedFloat32Array()
	line_y.resize(n * n * n)
	line_i.resize(n * n * n)
	var line_x0: int = n / 2 - 1
	var line_y0: int = n / 2 - 1
	for z in range(n):
		for y in range(n):
			for x in range(n):
				var theta: float = atan2(float(y) - (float(line_y0) + 0.5), float(x) - (float(line_x0) + 0.5))
				var id: int = _idx(x, y, z, n)
				line_y[id] = cos(theta)
				line_i[id] = sin(theta)
	var straight_line := _detect_topology(line_y, line_i, n)

	var ring_y := PackedFloat32Array()
	var ring_i := PackedFloat32Array()
	ring_y.resize(n * n * n)
	ring_i.resize(n * n * n)
	var center: float = (float(n) - 1.0) / 2.0
	var ring_radius: float = 8.5
	for z in range(n):
		for y in range(n):
			for x in range(n):
				var dx: float = float(x) - center
				var dy: float = float(y) - center
				var rho: float = sqrt(dx * dx + dy * dy)
				var theta: float = atan2(float(z) - center, rho - ring_radius)
				var id: int = _idx(x, y, z, n)
				ring_y[id] = cos(theta)
				ring_i[id] = sin(theta)
	var vortex_ring := _detect_topology(ring_y, ring_i, n)

	var passed: bool = int(uniform.get("nonzero_count", -1)) == 0
	passed = passed and int(plane_wave.get("nonzero_count", -1)) == 0
	passed = passed and int(global_rotation.get("nonzero_count", -1)) == 0
	passed = passed and int(straight_line.get("nonzero_count", 0)) > 0
	passed = passed and int(vortex_ring.get("nonzero_count", 0)) > 0
	return {
		"passed": passed,
		"uniform": uniform,
		"plane_wave": plane_wave,
		"global_phase_rotation": global_rotation,
		"seeded_straight_line": straight_line,
		"seeded_vortex_ring": vortex_ring,
		"phase_field_status": PHASE_FIELD_STATUS,
	}


func _write_report(report: Dictionary) -> bool:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_diag"))
	var file := FileAccess.open(REPORT_PATH, FileAccess.WRITE)
	if file == null:
		printerr("[topology-observatory] cannot open ", REPORT_PATH)
		return false
	file.store_string(JSON.stringify(report, "\t"))
	file.close()
	print("[topology-observatory] report -> ", REPORT_PATH)
	return true


func _fail(reason: String, extra: Dictionary = {}) -> void:
	if _finished:
		return
	var report: Dictionary = {
		"status": "failed",
		"failure": reason,
		"phase_field_status": PHASE_FIELD_STATUS,
		"config": {"grid_N": GRID_N, "N_particles": PARTICLES},
	}
	for key in extra.keys():
		report[key] = extra[key]
	if not _write_report(report):
		printerr("[topology-observatory] failed to write failure report")
	_finished = true
	get_tree().quit(1)


func _sci(value: float) -> String:
	if not is_finite(value) or value == 0.0:
		return str(value)
	var exponent: int = int(floor(log(absf(value)) / log(10.0)))
	var mantissa: float = value / pow(10.0, float(exponent))
	return "%.3fe%d" % [mantissa, exponent]
