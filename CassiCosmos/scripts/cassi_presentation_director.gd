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
##   DIRECTED — the director computes a preset-driven orbit pose
##              (Wide envelope / Focus core / Record orbit).
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
## faster; RECORD_ORBIT reproduces the classic recorder orbit. RECORDER
## mode always uses the classic record orbit regardless of preset.
enum Preset { WIDE_ENVELOPE, FOCUS_CORE, RECORD_ORBIT }

signal mode_changed(next_mode: int, next_preset: int)

# ═══════════════════════════════════════════════════════════════════════
# Exports
# ═══════════════════════════════════════════════════════════════════════

## Camera ownership mode. Defaults to MANUAL (director off), so adding the
## node to a scene never changes existing camera behavior by itself.
@export_enum("Manual", "Directed", "Recorder") var mode: int = Mode.MANUAL

## Motion preset used while `mode == DIRECTED`; RECORDER mode always uses
## the classic record orbit.
@export_enum("Wide envelope", "Focus core", "Record orbit") var preset: int = Preset.WIDE_ENVELOPE

# ═══════════════════════════════════════════════════════════════════════
# State
# ═══════════════════════════════════════════════════════════════════════

var _sim: Node = null
## Current orbit angle about the target's Y axis (rad), accumulated per
## `sample_pose`; deterministic for a fixed frame cadence.
var _orbit_angle: float = 0.0

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
	preset = clampi(next_preset, Preset.WIDE_ENVELOPE, Preset.RECORD_ORBIT)
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


## Mean of the cluster centers, mirroring cassi_sim.gd::_cluster_centroid /
## main_recorder.gd::_spawn_centroid (ring for nc <= 8, Fibonacci sphere
## above). A missing sim degrades to the origin — never stale coordinates.
func _spawn_centroid() -> Vector3:
	var sim := _find_sim()
	if sim == null:
		return Vector3.ZERO
	var nc := maxi(1, int(sim.get("num_clusters")))
	var sep := float(sim.get("cluster_separation"))
	var acc := Vector3.ZERO
	for i in range(nc):
		if nc > 8:
			var phi := acos(1.0 - 2.0 * (float(i) + 0.5) / float(nc))
			var th := PI * (1.0 + sqrt(5.0)) * float(i)
			acc += Vector3(sep * sin(phi) * cos(th), sep * sin(phi) * sin(th), sep * cos(phi))
		else:
			var angle := float(i) * PI * 2.0 / float(nc)
			acc += Vector3(sep * cos(angle), 0.0, sep * sin(angle))
	return acc / float(nc)


## Orbit distance that frames the spawn region: the cluster-ring radius
## plus the per-cluster ball radius, mirroring cassi_sim.gd /
## main_recorder.gd. A missing sim falls back to the recorder's default.
func _framing_radius() -> float:
	var sim := _find_sim()
	if sim == null:
		return DEFAULT_RADIUS
	var nc := maxi(1, int(sim.get("num_clusters")))
	var sep := float(sim.get("cluster_separation"))
	var cluster_r := maxf(float(sim.get("cluster_radius")), 1e-3)
	var ring_r: float = sep if nc > 1 else 0.0
	return maxf(maxf(ring_r, cluster_r) + cluster_r, 1.0)
