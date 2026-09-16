extends Node
## Cassi presentation camera director — a manual-first pose source for the
## interactive (`free_camera.gd`) and recording (`main_recorder.gd`) scenes.
##
## Ownership model (research/presentation/remaining_presentation_features_design.md
## Design decision D): the director is a pose SOURCE, never a second camera
## writer. It computes a target pose; the node that owns the Camera3D applies
## it. The director itself has no `_process()` and never writes a transform.
##
## Modes:
##   MANUAL   — the free camera is the sole writer; `is_directing()` is
##              false and `sample_pose()` returns the current camera pose
##              unchanged. Manual input always wins: any camera control
##              calls `request_manual_takeover()`, which flips the mode to
##              MANUAL before the next transform write.
##   DIRECTED — the director computes a preset-driven camera pose
##              (Wide envelope / Focus core / Record orbit / Follow structure).
##   RECORDER — `main_recorder.gd` remains the sole camera writer and
##              samples a director pose; the director reproduces the classic
##              deterministic record orbit (no roll).
##
## Targets come from the sibling `CassiSim.get_presentation_camera_target()`
## when that method exists; otherwise they fall back to the deterministic
## spawn centroid / extent derived from the sim's cluster exports (the same
## math `main_recorder.gd` uses), so the RECORD orbit is bit-compatible with
## the recorder's fixed orbit. A missing sim degrades to the origin with a
## sane default radius — never stale coordinates.

# ── Modes and presets ───────────────────────────────────────────────────
## Camera ownership: MANUAL = the free camera is the sole writer; DIRECTED =
## the director proposes a preset-driven pose; RECORDER = the recorder
## remains the sole writer and samples a director pose.
enum Mode { MANUAL, DIRECTED, RECORDER }
## Motion style in DIRECTED mode: WIDE_ENVELOPE frames the whole spawn
## envelope at a slow, wide orbit; FOCUS_CORE hugs the core tighter and
## faster; RECORD_ORBIT reproduces the classic recorder orbit.
## FOLLOW_STRUCTURE fits live particle bounds at the current viewing angle.
## RECORDER mode always uses the classic record orbit regardless of preset.
enum Preset { WIDE_ENVELOPE, FOCUS_CORE, RECORD_ORBIT, FOLLOW_STRUCTURE }

signal mode_changed(next_mode: int, next_preset: int)

# ═══════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════

## Camera ownership mode. Defaults to MANUAL (director off), so adding the
## node to a scene never changes existing camera behavior by itself.
@export_enum("Manual", "Directed", "Recorder") var mode: int = Mode.MANUAL

## Motion preset used while `mode == DIRECTED`; RECORDER mode always uses
## the classic record orbit.
@export_enum("Wide envelope", "Focus core", "Record orbit", "Follow structure") var preset: int = Preset.WIDE_ENVELOPE

# ═══════════════════════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════════════════════

var _sim: Node = null
## Current orbit angle about the target's Y axis (rad), accumulated per
## `sample_pose`; deterministic for a fixed frame cadence.
var _orbit_angle: float = 0.0
var _follow_initialized := false
var _follow_basis := Basis.IDENTITY
var _follow_distance := 0.0
var _follow_center := Vector3.ZERO

# Classic recorder cadence — mirrors main_recorder.gd's exports
# (orbit_speed = 0.12 rad/s, orbit_elevation = 0.35 rad) so the RECORD
# orbit reproduces the recorder's fixed orbit exactly.
const RECORD_SPEED: float = 0.12
const RECORD_ELEVATION: float = 0.35
## Wide-envelope orbit: slow drift at 1.4× the spawn extent so the whole
## envelope stays framed.
const WIDE_SPEED: float = 0.05
const WIDE_RADIUS_FRAC: float = 1.4
const WIDE_ELEVATION: float = 0.28
## Focus-core orbit: tighter (0.55× the spawn extent) and faster.
const FOCUS_SPEED: float = 0.22
const FOCUS_RADIUS_FRAC: float = 0.55
const FOCUS_ELEVATION: float = 0.5
## Fallback orbit radius when no sibling CassiSim exposes cluster geometry
## (matches main_recorder.gd's default orbit_radius).
const DEFAULT_RADIUS: float = 150.0
## Follow mode holds its pose until more than 10% of the measured living
## particle sample leaves the viewport. A triggered correction contains 92%
## of the sample, leaving a two-point hysteresis band before movement can
## restart, and eases toward the new pose.
const FOLLOW_MAX_OUTSIDE_FRAC: float = 0.10
const FOLLOW_FIT_FRAC: float = 0.92
const FOLLOW_PROJECTED_TAIL_FRAC: float = 0.01
const FOLLOW_CENTER_PASSES: int = 2
const FOLLOW_RESPONSE: float = 3.0

# Recorder-supplied orbit values preserve command-line framing overrides
# while the recorder still remains the only camera writer.
var _has_recorder_orbit: bool = false
var _recorder_target: Vector3 = Vector3.ZERO
var _recorder_radius: float = DEFAULT_RADIUS
var _recorder_elevation: float = RECORD_ELEVATION
var _recorder_speed: float = RECORD_SPEED

# ═══════════════════════════════════════════════════════════════════════
# Director API
# ═══════════════════════════════════════════════════════════════════════

## Switch to MANUAL (free-camera ownership). Called by the camera owner on
## any manual control; manual input always wins immediately.
func request_manual_takeover() -> void:
	if mode == Mode.MANUAL:
		return
	mode = Mode.MANUAL
	mode_changed.emit(mode, preset)



## Start an interactive directed preset. The camera owner samples the
## resulting pose; this node still never writes a Camera3D transform.
func set_directed_preset(next_preset: int) -> void:
	preset = clampi(next_preset, Preset.WIDE_ENVELOPE, Preset.FOLLOW_STRUCTURE)
	_follow_initialized = false
	mode = Mode.DIRECTED
	mode_changed.emit(mode, preset)


## Opt in to the deterministic recorder orbit while preserving single-writer
## camera ownership in `main_recorder.gd`.
func set_recorder_directing() -> void:
	mode = Mode.RECORDER
	mode_changed.emit(mode, preset)


## Supply the recorder's already-resolved target and command-line orbit
## overrides. This is intentionally a pose-input API, not a Camera3D write.
func configure_recorder_orbit(target: Vector3, radius: float, elevation: float,
		speed: float) -> void:
	_has_recorder_orbit = true
	_recorder_target = target
	_recorder_radius = maxf(radius, 1e-3)
	_recorder_elevation = elevation
	_recorder_speed = maxf(speed, 0.0)

## True while the director is proposing motion (DIRECTED or RECORDER);
## false in MANUAL, where the free camera is the sole writer.
func is_directing() -> bool:
	return mode != Mode.MANUAL


## Sample the director's next camera pose for `delta` seconds. The caller
## (free_camera.gd or main_recorder.gd) remains the sole Camera3D writer and
## applies the returned transform. In MANUAL the current camera pose is
## returned unchanged (the camera owner keeps what it has).
func sample_pose(delta: float, camera: Camera3D) -> Transform3D:
	if mode == Mode.MANUAL:
		if camera == null:
			return Transform3D()
		return camera.global_transform
	if mode == Mode.DIRECTED and preset == Preset.FOLLOW_STRUCTURE and camera != null:
		return _sample_structure_pose(delta, camera)
	var target: Vector3 = _presentation_target()
	var base_radius: float = _framing_radius()
	var speed: float
	var radius: float
	var elevation: float
	if mode == Mode.RECORDER:
		if _has_recorder_orbit:
			target = _recorder_target
			speed = _recorder_speed
			radius = _recorder_radius
			elevation = _recorder_elevation
		else:
			speed = RECORD_SPEED
			radius = base_radius
			elevation = RECORD_ELEVATION
	elif preset == Preset.RECORD_ORBIT:
		speed = RECORD_SPEED
		radius = base_radius
		elevation = RECORD_ELEVATION
	elif preset == Preset.FOCUS_CORE:
		speed = FOCUS_SPEED
		radius = maxf(base_radius * FOCUS_RADIUS_FRAC, 1.0)
		elevation = FOCUS_ELEVATION
	else:
		speed = WIDE_SPEED
		radius = maxf(base_radius * WIDE_RADIUS_FRAC, 1.0)
		elevation = WIDE_ELEVATION
	_orbit_angle += speed * maxf(delta, 0.0)
	var pos: Vector3 = target + Vector3(
		radius * cos(_orbit_angle) * cos(elevation),
		radius * sin(elevation),
		radius * sin(_orbit_angle) * cos(elevation))
	var pose := Transform3D()
	pose.origin = pos
	return pose.looking_at(target, Vector3.UP)


## Preserve the viewing angle and closely fit the central 90% of the measured
## living particles. After the initial fit, hold the camera perfectly still
## until more than 10% of that sample lies outside the current viewport; a
## triggered correction eases both center and distance instead of snapping.
func _sample_structure_pose(delta: float, camera: Camera3D) -> Transform3D:
	var sim := _find_sim()
	var bounds := AABB(_presentation_target(), Vector3.ZERO)
	var points := PackedVector3Array()
	var supports_particle_sample := sim != null \
			and sim.has_method("get_presentation_structure_points")
	if sim != null and sim.has_method("get_presentation_structure_bounds"):
		bounds = sim.call("get_presentation_structure_bounds")
	else:
		var extent := Vector3.ONE * _framing_radius()
		bounds = AABB(bounds.position - extent, extent * 2.0)
	if supports_particle_sample:
		points = sim.call("get_presentation_structure_points")
		# Wait for the first compact GPU sample instead of framing the broad
		# spawn fallback and then visibly correcting it half a second later.
		if points.is_empty():
			return camera.global_transform
	if not _follow_initialized:
		_follow_basis = camera.global_basis.orthonormalized()
	var tangents := _viewport_tangents(camera)
	if _follow_initialized and supports_particle_sample \
			and _outside_view_fraction(points, camera, tangents) <= FOLLOW_MAX_OUTSIDE_FRAC:
		return camera.global_transform

	var target_center := _sample_center(points, bounds.get_center())
	target_center = _center_projected_envelope(
			points, bounds, target_center, tangents, camera.near)
	var target_distance := _sample_fit_distance(
			points, bounds, target_center, tangents, camera.near)
	if not _follow_initialized:
		_follow_center = target_center
		_follow_distance = target_distance
	else:
		var blend := 1.0 - exp(-FOLLOW_RESPONSE * maxf(delta, 0.0))
		_follow_center = _follow_center.lerp(target_center, blend)
		_follow_distance = lerpf(_follow_distance, target_distance, blend)
	_follow_initialized = true
	return Transform3D(
			_follow_basis, _follow_center + _follow_basis.z * _follow_distance)


func _viewport_tangents(camera: Camera3D) -> Vector2:
	var viewport_size := camera.get_viewport().get_visible_rect().size
	var aspect := viewport_size.x / maxf(viewport_size.y, 1.0)
	var tan_x := tan(deg_to_rad(camera.fov) * 0.5)
	var tan_y := tan_x
	if camera.keep_aspect == Camera3D.KEEP_HEIGHT:
		tan_x *= aspect
	else:
		tan_y /= maxf(aspect, 0.001)
	return Vector2(maxf(tan_x, 0.001), maxf(tan_y, 0.001))


func _outside_view_fraction(
		points: PackedVector3Array, camera: Camera3D, tangents: Vector2) -> float:
	var outside := 0
	var valid := 0
	var inverse_basis := camera.global_basis.orthonormalized().transposed()
	for point in points:
		if not point.is_finite():
			continue
		valid += 1
		var local := inverse_basis * (point - camera.global_position)
		var depth := -local.z
		if depth <= camera.near \
				or absf(local.x) > depth * tangents.x \
				or absf(local.y) > depth * tangents.y:
			outside += 1
	return float(outside) / float(valid) if valid > 0 else 0.0


func _sample_center(
		points: PackedVector3Array, fallback: Vector3) -> Vector3:
	if points.is_empty():
		return fallback
	var xs := PackedFloat32Array()
	var ys := PackedFloat32Array()
	var zs := PackedFloat32Array()
	var inverse_basis := _follow_basis.transposed()
	for point in points:
		if not point.is_finite():
			continue
		var local := inverse_basis * point
		xs.append(local.x)
		ys.append(local.y)
		zs.append(local.z)
	if xs.is_empty():
		return fallback
	xs.sort()
	ys.sort()
	zs.sort()
	var tail_fraction := (1.0 - FOLLOW_FIT_FRAC) * 0.5
	var lower := floori(float(xs.size() - 1) * tail_fraction)
	var upper := ceili(float(xs.size() - 1) * (1.0 - tail_fraction))
	var local_center := Vector3(
			(xs[lower] + xs[upper]) * 0.5,
			(ys[lower] + ys[upper]) * 0.5,
			(zs[lower] + zs[upper]) * 0.5)
	return _follow_basis * local_center

func _center_projected_envelope(
		points: PackedVector3Array, bounds: AABB, initial_center: Vector3,
		tangents: Vector2, near_plane: float) -> Vector3:
	if points.is_empty():
		return initial_center
	var center := initial_center
	var inverse_basis := _follow_basis.transposed()
	for _pass in range(FOLLOW_CENTER_PASSES):
		var distance := _sample_fit_distance(
				points, bounds, center, tangents, near_plane)
		var projected_x := PackedFloat32Array()
		var projected_y := PackedFloat32Array()
		for point in points:
			if not point.is_finite():
				continue
			var local := inverse_basis * (point - center)
			var depth := distance - local.z
			if depth <= near_plane:
				continue
			projected_x.append(local.x / (depth * tangents.x))
			projected_y.append(local.y / (depth * tangents.y))
		if projected_x.is_empty():
			return center
		projected_x.sort()
		projected_y.sort()
		var lower := floori(
				float(projected_x.size() - 1) * FOLLOW_PROJECTED_TAIL_FRAC)
		var upper := ceili(
				float(projected_x.size() - 1) * (1.0 - FOLLOW_PROJECTED_TAIL_FRAC))
		var offset := Vector3(
				(projected_x[lower] + projected_x[upper])
						* 0.5 * distance * tangents.x,
				(projected_y[lower] + projected_y[upper])
						* 0.5 * distance * tangents.y,
				0.0)
		center += _follow_basis * offset
	return center


func _sample_fit_distance(
		points: PackedVector3Array, bounds: AABB, center: Vector3,
		tangents: Vector2, near_plane: float) -> float:
	var distances := PackedFloat32Array()
	var inverse_basis := _follow_basis.transposed()
	for point in points:
		if not point.is_finite():
			continue
		var local := inverse_basis * (point - center)
		distances.append(local.z + maxf(
				absf(local.x) / tangents.x,
				absf(local.y) / tangents.y) + near_plane * 2.0)
	if not distances.is_empty():
		distances.sort()
		var fit_index := clampi(
				int(ceil(float(distances.size()) * FOLLOW_FIT_FRAC)) - 1,
				0, distances.size() - 1)
		return maxf(distances[fit_index], maxf(near_plane * 2.0, 0.01))

	var distance := maxf(near_plane * 2.0, 0.01)
	for i in range(8):
		var local := inverse_basis * (bounds.get_endpoint(i) - center)
		distance = maxf(distance, local.z + maxf(
				absf(local.x) / tangents.x,
				absf(local.y) / tangents.y) + near_plane * 2.0)
	return distance

# ═══════════════════════════════════════════════════════════════════════
# Target framing
# ═══════════════════════════════════════════════════════════════════════

## The orbit target: the sim's presentation camera target when the sibling
## CassiSim exposes it, otherwise the deterministic spawn centroid.
func _presentation_target() -> Vector3:
	var sim := _find_sim()
	if sim != null and sim.has_method("get_presentation_camera_target"):
		var t: Vector3 = sim.call("get_presentation_camera_target")
		return t
	return _spawn_centroid()


## The sibling CassiSim node, cached; re-resolved lazily when missing or
## freed (the node can be added after this one's _ready).
func _find_sim() -> Node:
	if not is_instance_valid(_sim):
		var parent := get_parent()
		_sim = parent.get_node_or_null("CassiSim") if parent != null else null
	return _sim


## Share the simulation's explicit arrangement and cached geometry bounds.
func _spawn_centroid() -> Vector3:
	var sim := _find_sim()
	if sim == null:
		return Vector3.ZERO
	return sim.call("_cluster_centroid")


## The simulation owns spawn framing for both interactive and recording views.
func _framing_radius() -> float:
	var sim := _find_sim()
	if sim == null:
		return DEFAULT_RADIUS
	return float(sim.call("_camera_framing_radius"))
