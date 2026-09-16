extends RefCounted
class_name CassiQiFlow

## CASSI QI-FLOW — native-site Qi-flow inspection renderer (render-only).
##
## What it draws, all from the AUTHORITATIVE committed site state (never the
## coherence shortlist, never the packed next-state half):
##   1. Yang / Yin / Net current-aligned graph paths
##      (compute/cassi_qi_flow.glsl mode 2, shaders/qi_flow_filament.gdshader)
##   2. a low-opacity site-field reconstruction layer over every site —
##      coherence q, signed imbalance, or field amplitude
##      (modes 3, shaders/qi_flow_site.gdshader)
##   3. restrained luminous markers on the real BH records
##      (mode 4, shaders/qi_flow_source.gdshader)
##
## Lifecycle:
##   setup(sim: Node3D, rd: RenderingDevice) -> bool
##   update(frame: Dictionary, settings: Dictionary) -> bool
##   statistics() -> Dictionary
##   shutdown() -> void
##
## update() opens ONE ordered global-RD compute list and never submits or
## syncs. Cross-list visibility is not guaranteed on the global device, so
## the whole chain (clear → currents → geometry) lives in a single list with
## explicit barriers. The caller invokes update() outside its own compute
## list, using the global RD that renders the scene.
##
## This renderer never writes physics state. Its only writes are its own
## node/stat buffers and the MultiMesh instance buffers it owns. Borrowed
## RIDs (sites/psi/pi/volume/CSR/BH, and the MultiMesh RD buffers the
## RenderingServer hands out) are never freed here.

const SHADER_PATH := "res://compute/cassi_qi_flow.glsl"
const FILAMENT_SHADER_PATH := "res://shaders/qi_flow_filament.gdshader"
const SITE_SHADER_PATH := "res://shaders/qi_flow_site.gdshader"
const SOURCE_SHADER_PATH := "res://shaders/qi_flow_source.gdshader"

const MODE_CLEAR := 0.0
const MODE_NODES := 1.0
const MODE_FILAMENTS := 2.0
const MODE_SITES := 3.0
const MODE_SOURCES := 4.0

const WORKGROUP := 256
const SEED_CAP := 1024                 # seeds per channel (contract)
const SEGMENTS := 16                   # short segments per streamline
const FILAMENT_SLOTS := SEED_CAP * 2   # Both = Yang slots then Yin slots
const SOURCE_CAP := 15                 # BH record slots
const NODE_VEC4 := 4                   # vec4 per site in the node buffer
const MIN_MULTIMESH_RECORDS := 16      # 4 vec4 = one instance record
const NODE_CAPACITY_FLOOR := 1024
const SITE_CAPACITY_FLOOR := 1024
const SITE_CAPACITY_CEIL := 262144
const STREAM_WIDTH_FRACTION := 0.10    # of the mean site spacing sqrt(c2)
const SPLAT_SCALE := 1.6               # broad, low-opacity scalar supports
const SEED_SALT := 1337.0
const INTENSITY_NOTE := "intensity=(|J|/ref)^0.35; ref=GPU atomic max per channel (clamped display scale)"
const CUE_NOTE := "animated brightness = direction cue on accepted field time; NOT a parcel/energy speed"
const GEOMETRY_NOTE := "current-aligned CSR graph paths (min-image, 16 segments/seed)"

## One renderer-owned MultiMesh layer (filaments / site splats / BH markers).
class Layer:
	var mmi: MultiMeshInstance3D = null
	var mm: MultiMesh = null
	var mat: ShaderMaterial = null
	var rd_rid: RID = RID()
	var capacity: int = 0
	var is_ready: bool = false

var _rd: RenderingDevice = null
var _sim: Node3D = null
var _shader: RID = RID()
var _pipe: RID = RID()
var _uniform_set: RID = RID()
var _node_buffer: RID = RID()
var _stats_buffer: RID = RID()
var _node_capacity: int = 0
var _pc := PackedByteArray()
var _descriptor_key := PackedInt64Array()
var _key_scratch := PackedInt64Array()
var _filaments := Layer.new()
var _sites := Layer.new()
var _sources := Layer.new()
var _available: bool = false
var _reason: String = "not set up"
var _statistics: Dictionary = {}
var _updates: int = 0

## Host-settable render tuning (no physics meaning). Defaults are the
## constants below; a host may nudge them live.
var stream_min_align: float = 0.10      # 0 keeps paths through right-angle turns
var splat_scale: float = SPLAT_SCALE    # site splat radius / mean site spacing
var stream_width_fraction: float = STREAM_WIDTH_FRACTION


# ── Lifecycle ──────────────────────────────────────────────────────────


func setup(sim: Node3D, rd: RenderingDevice) -> bool:
	if _rd != null:
		return _available
	if sim == null:
		_reason = "setup: no simulation node"
		return false
	if rd == null:
		_reason = "setup: no RenderingDevice"
		return false
	_sim = sim
	_rd = rd
	_shader = _load_shader(SHADER_PATH)
	if not _shader.is_valid():
		_reason = "setup: compute shader unavailable (%s)" % SHADER_PATH
		return false
	_pipe = _rd.compute_pipeline_create(_shader)
	if not _pipe.is_valid():
		_reason = "setup: compute pipeline creation failed"
		return false
	_pc.resize(32 * 4)
	if not _ensure_node_capacity(NODE_CAPACITY_FLOOR):
		_reason = "setup: node buffer allocation failed"
		return false
	_stats_buffer = _rd.storage_buffer_create(8 * 4, PackedByteArray())
	if not _stats_buffer.is_valid():
		_reason = "setup: statistics buffer allocation failed"
		return false
	if not _create_layer(_filaments, "QiFlowFilaments", FILAMENT_SHADER_PATH, FILAMENT_SLOTS * SEGMENTS):
		_reason = "setup: filament layer unavailable"
		return false
	if not _create_layer(_sites, "QiFlowSiteField", SITE_SHADER_PATH, SITE_CAPACITY_FLOOR):
		_reason = "setup: site field layer unavailable"
		return false
	if not _create_layer(_sources, "QiFlowSources", SOURCE_SHADER_PATH, SOURCE_CAP):
		_reason = "setup: source layer unavailable"
		return false
	_descriptor_key = PackedInt64Array()
	_available = true
	_reason = "ready"
	return true


func shutdown() -> void:
	_free_layer(_filaments)
	_free_layer(_sites)
	_free_layer(_sources)
	if _rd != null:
		if _uniform_set.is_valid() and _rd.uniform_set_is_valid(_uniform_set):
			_rd.free_rid(_uniform_set)
		if _pipe.is_valid() and _rd.compute_pipeline_is_valid(_pipe):
			_rd.free_rid(_pipe)
		if _shader.is_valid():
			_rd.free_rid(_shader)
		if _stats_buffer.is_valid():
			_rd.free_rid(_stats_buffer)
		if _node_buffer.is_valid():
			_rd.free_rid(_node_buffer)
	_uniform_set = RID()
	_pipe = RID()
	_shader = RID()
	_stats_buffer = RID()
	_node_buffer = RID()
	_node_capacity = 0
	_descriptor_key = PackedInt64Array()
	_available = false
	_reason = "shut down"
	_rd = null
	_sim = null
	_statistics = {}


func is_available() -> bool:
	return _available


func unavailable_reason() -> String:
	return _reason


func statistics() -> Dictionary:
	if _statistics.is_empty():
		return {
			"available": _available,
			"reason": _reason,
			"sites": 0,
			"time": 0.0,
			"quantity": _quantity_label(0.0),
		}
	return _statistics.duplicate()


# ── Per-frame update ───────────────────────────────────────────────────


func update(frame: Dictionary, settings: Dictionary) -> bool:
	if _rd == null or not _shader.is_valid() or not _pipe.is_valid():
		return _unavailable("renderer not set up")
	if not (_filaments.is_ready and _sites.is_ready and _sources.is_ready):
		return _unavailable("renderer layers not ready")

	var sites: RID = frame.get("sites", RID())
	var psi_y: RID = frame.get("psi_y", RID())
	var psi_i: RID = frame.get("psi_i", RID())
	var pi_y: RID = frame.get("pi_y", RID())
	var pi_i: RID = frame.get("pi_i", RID())
	var volumes: RID = frame.get("volumes", RID())
	var offsets: RID = frame.get("offsets", RID())
	var neighbors: RID = frame.get("neighbors", RID())
	var topology_status: RID = frame.get("topology_status", RID())
	var bh: RID = frame.get("bh", RID())
	var missing := ""
	if not sites.is_valid():
		missing = "sites"
	elif not psi_y.is_valid():
		missing = "psi_y"
	elif not psi_i.is_valid():
		missing = "psi_i"
	elif not pi_y.is_valid():
		missing = "pi_y"
	elif not pi_i.is_valid():
		missing = "pi_i"
	elif not volumes.is_valid():
		missing = "volumes"
	elif not offsets.is_valid():
		missing = "offsets"
	elif not neighbors.is_valid():
		missing = "neighbors"
	elif not topology_status.is_valid():
		missing = "topology_status"
	elif not bh.is_valid():
		missing = "bh"
	if missing != "":
		return _unavailable("frame key '%s' is not a valid RID" % missing)

	var count: int = int(frame.get("count", 0))
	if count <= 0:
		return _unavailable("no authoritative sites in this frame")
	var generation: int = int(frame.get("generation", 0))
	if generation <= 0:
		return _unavailable("topology generation not published")

	var extents: Vector3 = frame.get("extents", Vector3.ZERO)
	if not _finite_vec3(extents) or extents.x <= 0.0 or extents.y <= 0.0 or extents.z <= 0.0:
		return _unavailable("invalid extents")
	var offset: Vector3 = frame.get("offset", Vector3.ZERO)
	var render_origin: Vector3 = frame.get("render_origin", Vector3.ZERO)
	if not _finite_vec3(offset) or not _finite_vec3(render_origin):
		return _unavailable("invalid render offsets")
	var c2: float = float(frame.get("c2", 0.0))
	if not is_finite(c2) or c2 <= 0.0:
		return _unavailable("c2 is not positive finite")
	var phi: float = float(frame.get("phi", 0.0))
	if not is_finite(phi) or absf(phi) < 1.0e-3:
		return _unavailable("phi is not positive finite")
	var volume_floor: float = float(frame.get("volume_floor", 0.0))
	if not is_finite(volume_floor):
		volume_floor = 0.0
	var time: float = float(frame.get("time", 0.0))
	if not is_finite(time):
		time = 0.0
	var winding: float = float(frame.get("winding", 0.0))
	if not is_finite(winding):
		winding = 0.0
	var camera: Camera3D = frame.get("camera", null)
	if camera == null or not is_instance_valid(camera):
		return _unavailable("no camera in this frame")
	var bh_enabled: bool = bool(frame.get("bh_enabled", false))

	var channel: int = clampi(int(settings.get("channel", 0)), 0, 3)
	var scalar_mode: int = clampi(int(settings.get("scalar", 0)), 0, 2)
	var density: float = clampf(float(settings.get("density", 0.5)), 0.1, 1.0)
	var gain: float = clampf(float(settings.get("gain", 1.0)), 0.1, 4.0)
	var cutaway: float = clampf(float(settings.get("cutaway", 0.0)), 0.0, 1.0)
	var show_field: bool = bool(settings.get("show_field", true))
	var show_sources: bool = bool(settings.get("show_sources", true))

	var seeds: int = clampi(int(round(float(SEED_CAP) * density)), 1, SEED_CAP)
	var active_slots: int = seeds * 2 if channel == 0 else seeds

	if not _ensure_node_capacity(count):
		return _unavailable("node buffer allocation failed")
	if not _ensure_layer_capacity(_sites, mini(count, SITE_CAPACITY_CEIL)):
		return _unavailable("site field capacity allocation failed")

	if _descriptor_changed(
			sites, psi_y, psi_i, pi_y, pi_i, volumes, offsets, neighbors,
			topology_status, bh, count) or not _uniform_set.is_valid() \
			or not _rd.uniform_set_is_valid(_uniform_set):
		if not _create_descriptor_set(
				sites, psi_y, psi_i, pi_y, pi_i, volumes, offsets, neighbors,
				topology_status, bh):
			return _unavailable("descriptor set creation failed")

	var spacing := maxf(sqrt(c2), 1.0e-6)
	_fill_push_constants(
		frame, channel, scalar_mode, seeds, active_slots, spacing, extents,
		offset, render_origin, c2, phi, volume_floor, generation,
		bh_enabled, show_field, show_sources, camera)

	_sync_material_uniforms(camera, extents, offset, time, gain, scalar_mode,
			cutaway)
	var camera_local := _sim.to_local(camera.global_position)
	var bounds := AABB(offset - extents * 1.1, extents * 2.2)
	_filaments.mm.custom_aabb = bounds
	_sites.mm.custom_aabb = bounds
	# The fifteen GPU-positioned sources may outlive a moving field window.
	# Bound their draw by the camera's reach, not the old CPU-zero transforms.
	var camera_reach := Vector3.ONE * camera.far * 4.0
	_sources.mm.custom_aabb = AABB(camera_local - camera_reach, camera_reach * 2.0)

	_filaments.mmi.visible = true
	_sites.mmi.visible = show_field
	_sources.mmi.visible = show_sources and bh_enabled

	var site_dispatched: int = _sites.capacity
	var site_stride: int = ceili(float(count) / float(maxi(_sites.capacity, 1)))
	var cl := _rd.compute_list_begin()
	_dispatch(cl, MODE_CLEAR, 1)
	_rd.compute_list_add_barrier(cl)
	_dispatch(cl, MODE_NODES, ceili(float(count) / float(WORKGROUP)))
	_rd.compute_list_add_barrier(cl)
	_dispatch(cl, MODE_FILAMENTS, ceili(float(FILAMENT_SLOTS) / float(WORKGROUP)))
	if show_field:
		# Dispatched over the whole layer capacity, not just the live site
		# count: every slot is rewritten each frame, so a topology rebuild
		# that shrinks the site array cannot leave a stale splat behind.
		_dispatch(cl, MODE_SITES, ceili(float(_sites.capacity) / float(WORKGROUP)))
	if show_sources and bh_enabled:
		_dispatch(cl, MODE_SOURCES, 1)
	_rd.compute_list_end()

	_updates += 1
	_available = true
	_reason = "ready"
	_statistics = {
		"available": true,
		"reason": "ready",
		"sites": count,
		"time": time,
		"quantity": _quantity_label(winding),
		"channel": channel,
		"channel_name": _channel_name(channel),
		"scalar": scalar_mode,
		"scalar_name": _scalar_name(scalar_mode),
		"seeds_per_channel": seeds,
		"filament_slots": active_slots,
		"segments_per_stream": SEGMENTS,
		"site_instances": site_dispatched if show_field else 0,
		"site_stride": site_stride,
		"source_instances": SOURCE_CAP if (show_sources and bh_enabled) else 0,
		"generation": generation,
		"cutaway": cutaway,
		"density": density,
		"gain": gain,
		"winding": winding,
		"bh_enabled": bh_enabled,
		"updates": _updates,
		"normalization": INTENSITY_NOTE,
		"cue": CUE_NOTE,
		"geometry": GEOMETRY_NOTE,
	}
	return true


func _unavailable(reason: String) -> bool:
	_reason = reason
	_available = false
	for layer: Layer in [_filaments, _sites, _sources]:
		if layer.mmi != null and is_instance_valid(layer.mmi):
			layer.mmi.visible = false
	_statistics = {
		"available": false,
		"reason": reason,
		"sites": 0,
		"time": 0.0,
		"quantity": _quantity_label(0.0),
	}
	return false


# ── Push constants / dispatch ──────────────────────────────────────────


func _fill_push_constants(
		frame: Dictionary,
		channel: int,
		scalar_mode: int,
		seeds: int,
		active_slots: int,
		spacing: float,
		extents: Vector3,
		offset: Vector3,
		render_origin: Vector3,
		c2: float,
		phi: float,
		volume_floor: float,
		generation: int,
		bh_enabled: bool,
		show_field: bool,
		show_sources: bool,
		camera: Camera3D) -> void:
	var count: int = int(frame.get("count", 0))
	var right := camera.global_transform.basis.x.normalized()
	var forward := -camera.global_transform.basis.z.normalized()
	_pc.encode_float(0, 0.0)                       # cfg0.x — mode (per dispatch)
	_pc.encode_float(4, float(count))              # cfg0.y — site count
	_pc.encode_float(8, float(active_slots))       # cfg0.z — active filament slots
	_pc.encode_float(12, float(channel))           # cfg0.w — channel mode
	_pc.encode_float(16, extents.x)                # cfg1.x
	_pc.encode_float(20, extents.y)                # cfg1.y
	_pc.encode_float(24, extents.z)                # cfg1.z
	_pc.encode_float(28, clampf(splat_scale, 0.05, 3.0))    # cfg1.w — splat scale
	_pc.encode_float(32, offset.x)                 # cfg2.x
	_pc.encode_float(36, offset.y)                 # cfg2.y
	_pc.encode_float(40, offset.z)                 # cfg2.z
	_pc.encode_float(44, clampf(stream_min_align, -1.0, 1.0))   # cfg2.w — min alignment
	_pc.encode_float(48, c2)                       # cfg3.x
	_pc.encode_float(52, phi)                      # cfg3.y
	_pc.encode_float(56, volume_floor)             # cfg3.z
	_pc.encode_float(60, float(scalar_mode))       # cfg3.w — scalar mode
	_pc.encode_float(64, float(seeds))             # cfg4.x
	_pc.encode_float(68, 0.0)                     # cfg4.y — reserved
	_pc.encode_float(72, clampf(stream_width_fraction, 0.01, 0.5) * spacing)   # cfg4.z — ribbon width
	_pc.encode_float(76, SEED_SALT)                # cfg4.w — seed salt
	_pc.encode_float(80, right.x)                  # cfg5.x
	_pc.encode_float(84, right.y)
	_pc.encode_float(88, right.z)
	_pc.encode_float(92, 1.0 if (show_sources and bh_enabled) else 0.0)  # cfg5.w
	_pc.encode_float(96, forward.x)                # cfg6.x
	_pc.encode_float(100, forward.y)
	_pc.encode_float(104, forward.z)
	_pc.encode_float(108, 1.0 if show_field else 0.0)                    # cfg6.w
	_pc.encode_float(112, float(generation))       # cfg7.x
	_pc.encode_float(116, render_origin.x)         # cfg7.y
	_pc.encode_float(120, render_origin.y)         # cfg7.z
	_pc.encode_float(124, render_origin.z)         # cfg7.w


func _dispatch(cl: int, mode: float, groups: int) -> void:
	if groups <= 0:
		return
	_pc.encode_float(0, mode)
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _uniform_set, 0)
	_rd.compute_list_set_push_constant(cl, _pc, _pc.size())
	_rd.compute_list_dispatch(cl, groups, 1, 1)


# ── Materials ──────────────────────────────────────────────────────────


func _sync_material_uniforms(
		camera: Camera3D,
		extents: Vector3,
		offset: Vector3,
		time: float,
		gain: float,
		scalar_mode: int,
		cutaway: float) -> void:
	# Camera-relative cutaway: a plane through the domain centre whose normal
	# follows the camera. At 0 nothing is removed; at 1 the camera-facing half
	# of the domain is removed, exposing the interior of every layer. The
	# plane is expressed in WORLD space, which is what the materials compare
	# against (MODEL_MATRIX includes the MultiMesh instance transform).
	var cut_enabled := 0.0
	var cut_center := Vector3.ZERO
	var cut_normal := Vector3(0.0, 0.0, -1.0)
	var cut_threshold := 0.0
	if cutaway > 0.0001 and _sim != null and is_instance_valid(_sim):
		cut_normal = -camera.global_transform.basis.z.normalized()
		cut_center = _sim.global_transform * offset
		var world_scale := _sim.global_transform.basis.get_scale()
		var half := Vector3(
			absf(extents.x * world_scale.x),
			absf(extents.y * world_scale.y),
			absf(extents.z * world_scale.z))
		var reach: float = absf(cut_normal.x) * half.x \
				+ absf(cut_normal.y) * half.y \
				+ absf(cut_normal.z) * half.z
		cut_threshold = lerpf(-reach, 0.0, cutaway)
		cut_enabled = 1.0

	for layer: Layer in [_filaments, _sites, _sources]:
		var mat: ShaderMaterial = layer.mat
		if mat == null:
			continue
		mat.set_shader_parameter("cut_enabled", cut_enabled)
		mat.set_shader_parameter("cut_center", cut_center)
		mat.set_shader_parameter("cut_normal", cut_normal)
		mat.set_shader_parameter("cut_threshold", cut_threshold)
		mat.set_shader_parameter("gain", gain)
	_filaments.mat.set_shader_parameter("field_time", time)
	var inverse_extents := Vector3.ONE / extents
	var world_to_field := Transform3D(Basis.from_scale(inverse_extents),
			-offset * inverse_extents) * _sim.global_transform.affine_inverse()
	_filaments.mat.set_shader_parameter("world_to_field", world_to_field)
	_sites.mat.set_shader_parameter("world_to_field", world_to_field)
	_sites.mat.set_shader_parameter("scalar_mode", float(scalar_mode))


# ── GPU buffers ────────────────────────────────────────────────────────


func _ensure_node_capacity(needed: int) -> bool:
	if _rd == null:
		return false
	if _node_buffer.is_valid() and _node_capacity >= needed:
		return true
	var capacity := _round_capacity(needed)
	var zero := PackedFloat32Array()
	zero.resize(capacity * NODE_VEC4 * 4)
	var buffer := _rd.storage_buffer_create(zero.size() * 4, zero.to_byte_array())
	if not buffer.is_valid():
		push_error("[CassiQiFlow] node buffer allocation failed")
		return false
	if _node_buffer.is_valid():
		_rd.free_rid(_node_buffer)
	_node_buffer = buffer
	_node_capacity = capacity
	_descriptor_key = PackedInt64Array()   # descriptors referenced the old RID
	return true


func _create_descriptor_set(
		sites: RID,
		psi_y: RID,
		psi_i: RID,
		pi_y: RID,
		pi_i: RID,
		volumes: RID,
		offsets: RID,
		neighbors: RID,
		topology_status: RID,
		bh: RID) -> bool:
	if _uniform_set.is_valid() and _rd.uniform_set_is_valid(_uniform_set):
		_rd.free_rid(_uniform_set)
	_uniform_set = RID()
	if not _filaments.rd_rid.is_valid() or not _sites.rd_rid.is_valid() \
			or not _sources.rd_rid.is_valid():
		return false
	_uniform_set = _rd.uniform_set_create([
		_storage_uniform(0, sites),
		_storage_uniform(1, psi_y),
		_storage_uniform(2, psi_i),
		_storage_uniform(3, pi_y),
		_storage_uniform(4, pi_i),
		_storage_uniform(5, volumes),
		_storage_uniform(6, offsets),
		_storage_uniform(7, neighbors),
		_storage_uniform(8, topology_status),
		_storage_uniform(9, bh),
		_storage_uniform(10, _node_buffer),
		_storage_uniform(11, _stats_buffer),
		_storage_uniform(12, _filaments.rd_rid),
		_storage_uniform(13, _sites.rd_rid),
		_storage_uniform(14, _sources.rd_rid),
	], _shader, 0)
	if not _uniform_set.is_valid():
		push_warning("[CassiQiFlow] uniform set creation failed")
		return false
	return true


## True when any descriptor-relevant RID, capacity or the site count changed.
## The scratch key is filled IN PLACE (a uniquely referenced PackedInt64Array
## mutates without reallocating), so the steady-state frame allocates nothing
## and the cached copy is only rewritten on a real change.
##
## The topology generation is deliberately NOT part of the key: it can change
## without any RID changing, and that case is safe because every update
## recomputes the currents and rebuilds all geometry from scratch.
func _descriptor_changed(
		sites: RID,
		psi_y: RID,
		psi_i: RID,
		pi_y: RID,
		pi_i: RID,
		volumes: RID,
		offsets: RID,
		neighbors: RID,
		topology_status: RID,
		bh: RID,
		count: int) -> bool:
	if _key_scratch.size() != 18:
		_key_scratch.resize(18)
	_key_scratch[0] = sites.get_id()
	_key_scratch[1] = psi_y.get_id()
	_key_scratch[2] = psi_i.get_id()
	_key_scratch[3] = pi_y.get_id()
	_key_scratch[4] = pi_i.get_id()
	_key_scratch[5] = volumes.get_id()
	_key_scratch[6] = offsets.get_id()
	_key_scratch[7] = neighbors.get_id()
	_key_scratch[8] = topology_status.get_id()
	_key_scratch[9] = bh.get_id()
	_key_scratch[10] = _node_buffer.get_id()
	_key_scratch[11] = _stats_buffer.get_id()
	_key_scratch[12] = _filaments.rd_rid.get_id()
	_key_scratch[13] = _sites.rd_rid.get_id()
	_key_scratch[14] = _sources.rd_rid.get_id()
	_key_scratch[15] = count
	_key_scratch[16] = _node_capacity
	_key_scratch[17] = _sites.capacity
	if _key_scratch == _descriptor_key:
		return false
	_descriptor_key = _key_scratch.duplicate()
	return true


func _storage_uniform(binding: int, buffer: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(buffer)
	return uniform


func _round_capacity(needed: int) -> int:
	var capacity := SITE_CAPACITY_FLOOR
	while capacity < needed and capacity < SITE_CAPACITY_CEIL:
		capacity *= 2
	return maxi(capacity, needed)


# ── MultiMesh layers ───────────────────────────────────────────────────


func _create_layer(
		layer: Layer,
		node_name: String,
		material_path: String,
		capacity: int) -> bool:
	if _sim == null or _rd == null:
		return false
	var mesh := QuadMesh.new()
	mesh.size = Vector2.ONE
	var multimesh := MultiMesh.new()
	multimesh.transform_format = MultiMesh.TRANSFORM_3D
	multimesh.use_colors = false
	multimesh.use_custom_data = true
	multimesh.mesh = mesh
	multimesh.instance_count = capacity
	# Force the renderer-owned storage allocation up front. The finite zero
	# records also make a not-yet-published topology explicitly invisible.
	var zero := PackedFloat32Array()
	zero.resize(capacity * MIN_MULTIMESH_RECORDS)
	multimesh.buffer = zero
	var instance := MultiMeshInstance3D.new()
	instance.name = node_name
	instance.multimesh = multimesh
	instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var material := ShaderMaterial.new()
	var shader_resource := load(material_path) as Shader
	if shader_resource == null:
		push_error("[CassiQiFlow] material shader could not be loaded: %s" % material_path)
		instance.free()
		return false
	material.shader = shader_resource
	material.render_priority = 0
	instance.material_override = material
	_sim.add_child(instance)
	var rd_rid := RenderingServer.multimesh_get_buffer_rd_rid(multimesh.get_rid())
	if not rd_rid.is_valid():
		push_error("[CassiQiFlow] %s could not acquire its MultiMesh RD buffer" % node_name)
		_sim.remove_child(instance)
		instance.free()
		return false
	instance.visible = false
	layer.mmi = instance
	layer.mm = multimesh
	layer.mat = material
	layer.rd_rid = rd_rid
	layer.capacity = capacity
	layer.is_ready = true
	return true


func _ensure_layer_capacity(layer: Layer, needed: int) -> bool:
	if not layer.is_ready or layer.mm == null:
		return false
	var target := maxi(needed, 1)
	if layer.capacity >= target:
		return true
	var capacity := _round_capacity(target)
	var zero := PackedFloat32Array()
	zero.resize(capacity * MIN_MULTIMESH_RECORDS)
	layer.mm.instance_count = capacity
	layer.mm.buffer = zero
	var rd_rid := RenderingServer.multimesh_get_buffer_rd_rid(layer.mm.get_rid())
	if not rd_rid.is_valid():
		push_error("[CassiQiFlow] MultiMesh buffer regrowth failed")
		layer.is_ready = false
		return false
	layer.rd_rid = rd_rid
	layer.capacity = capacity
	_descriptor_key = PackedInt64Array()   # descriptors referenced the old RID
	return true


func _free_layer(layer: Layer) -> void:
	if layer.mmi != null and is_instance_valid(layer.mmi):
		if layer.mmi.get_parent() != null:
			layer.mmi.get_parent().remove_child(layer.mmi)
		layer.mmi.free()
	layer.mmi = null
	layer.mm = null
	layer.mat = null
	layer.rd_rid = RID()
	layer.capacity = 0
	layer.is_ready = false


# ── Shader loading ─────────────────────────────────────────────────────


func _load_shader(path: String) -> RID:
	if not ResourceLoader.exists(path):
		push_error("[CassiQiFlow] shader not found: %s" % path)
		return RID()
	var shader_file := load(path) as RDShaderFile
	if shader_file == null:
		push_error("[CassiQiFlow] shader resource invalid: %s" % path)
		return RID()
	var spirv := shader_file.get_spirv()
	if spirv == null:
		push_error("[CassiQiFlow] SPIR-V compile failed: %s" % path)
		return RID()
	return _rd.shader_create_from_spirv(spirv)


# ── Readback helpers (GPU numeric smoke; call from the frame context) ───


## Dumps the node-current records. Returns empty when no frame has been
## rendered. `limit` <= 0 reads every site the buffer holds.
func readback_nodes(limit: int = 0) -> Dictionary:
	if _rd == null or not _node_buffer.is_valid() or _node_capacity <= 0:
		return {}
	var sites := _node_capacity if limit <= 0 else mini(limit, _node_capacity)
	var raw := _rd.buffer_get_data(_node_buffer, 0, sites * NODE_VEC4 * 16)
	var floats := raw.to_float32_array()
	var jy := PackedFloat32Array()
	var ji := PackedFloat32Array()
	var q := PackedFloat32Array()
	var imbalance := PackedFloat32Array()
	var amplitude := PackedFloat32Array()
	var magnitude_y := PackedFloat32Array()
	var magnitude_i := PackedFloat32Array()
	var field_ok := PackedFloat32Array()
	var valid := PackedFloat32Array()
	var position := PackedFloat32Array()
	var stride := NODE_VEC4 * 4
	var available := floats.size() / stride
	for index in range(available):
		var base := index * stride
		jy.append(floats[base])
		jy.append(floats[base + 1])
		jy.append(floats[base + 2])
		q.append(floats[base + 3])
		ji.append(floats[base + 4])
		ji.append(floats[base + 5])
		ji.append(floats[base + 6])
		imbalance.append(floats[base + 7])
		amplitude.append(floats[base + 8])
		magnitude_y.append(floats[base + 9])
		magnitude_i.append(floats[base + 10])
		field_ok.append(floats[base + 11])
		position.append(floats[base + 12])
		position.append(floats[base + 13])
		position.append(floats[base + 14])
		valid.append(floats[base + 15])
	return {
		"capacity": _node_capacity,
		"sites_read": available,
		"layout": "4 vec4 per site: (J_Y.xyz,q) (J_I.xyz,imbalance) (amplitude,|J_Y|,|J_I|,field_ok) (local.xyz,valid)",
		"jy": jy, "ji": ji, "q": q, "imbalance": imbalance,
		"amplitude": amplitude, "magnitude_y": magnitude_y,
		"magnitude_i": magnitude_i, "field_ok": field_ok,
		"valid": valid, "position": position,
	}


## Decoded statistics atomics: the per-channel max magnitudes the shaders
## normalize against (float bit patterns published on the GPU).
func readback_statistics() -> Dictionary:
	if _rd == null or not _stats_buffer.is_valid():
		return {}
	var raw := _rd.buffer_get_data(_stats_buffer, 0, 8 * 4)
	if raw.size() < 32:
		return {}
	return {
		"max_magnitude_y": raw.decode_float(0),
		"max_magnitude_i": raw.decode_float(4),
		"max_amplitude": raw.decode_float(8),
		"raw_0": raw.decode_u32(0), "raw_1": raw.decode_u32(4),
		"raw_2": raw.decode_u32(8), "raw_3": raw.decode_u32(12),
	}


## Dumps a layer's MultiMesh instance records (4 vec4 each: 3x4 transform +
## custom data). `kind` is "filament", "site" or "source".
func readback_instances(kind: String, limit: int = 0) -> Dictionary:
	if _rd == null:
		return {}
	var layer: Layer = null
	if kind == "filament":
		layer = _filaments
	elif kind == "site":
		layer = _sites
	elif kind == "source":
		layer = _sources
	if layer == null or not layer.is_ready or layer.capacity <= 0:
		return {}
	var instances := layer.capacity if limit <= 0 else mini(limit, layer.capacity)
	var raw := _rd.buffer_get_data(layer.rd_rid, 0, instances * MIN_MULTIMESH_RECORDS * 4)
	return {
		"kind": kind,
		"capacity": layer.capacity,
		"instances_read": instances,
		"records": raw.to_float32_array(),
		"layout": "16 floats per instance: rows 0..2 = 3x4 row-major transform, row 3 = custom data",
	}


## Tuning accessor: "filament", "site" or "source". The host can nudge the
## material knobs (width_scale, alpha_scale, emission_strength, scalar
## palettes, cue_rate, opacity_scale, size_scale …) without touching the
## render path. Returns null for an unknown kind.
func material(kind: String) -> ShaderMaterial:
	if kind == "filament":
		return _filaments.mat
	if kind == "site":
		return _sites.mat
	if kind == "source":
		return _sources.mat
	return null


## The per-site record count last dispatched to the site-field layer.
func site_capacity() -> int:
	return _sites.capacity


func filament_slots() -> int:
	return FILAMENT_SLOTS


func seeds_per_channel() -> int:
	return SEED_CAP


func segments_per_stream() -> int:
	return SEGMENTS


# ── Labels ─────────────────────────────────────────────────────────────


func _channel_name(channel: int) -> String:
	if channel == 0:
		return "Both (Yang gold + Yin teal)"
	if channel == 1:
		return "Yang (gold)"
	if channel == 2:
		return "Yin (teal)"
	return "Net (Yang + Yin summed)"


func _scalar_name(scalar: int) -> String:
	if scalar == 0:
		return "coherence q"
	if scalar == 1:
		return "signed imbalance (y - phi*i) / |rho|"
	return "field amplitude |rho| = |psi_y + psi_i|"


func _quantity_label(winding: float) -> String:
	var label := "c2-wave graph-bond energy current: Py=-c2*dy*(pi_y_i+pi_y_j)/(2d), Pi=-phi*c2*di*(pi_i_i+pi_i_j)/(2d); J=sum(P*d)/(2*V)"
	if absf(winding) > 1.0e-9:
		label += " — c2-wave channel only: the solver's winding term (%.4f) is NOT folded in, and this is not a conserved energy flux" % winding
	return label


func _finite_vec3(value: Vector3) -> bool:
	return is_finite(value.x) and is_finite(value.y) and is_finite(value.z)
