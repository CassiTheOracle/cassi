extends Node
## verify_core — the single production smoke gate for CassiCosmos.
##
## Boots the real res://scenes/main.tscn (the shipped production configuration)
## and asserts only observables a broken build would violate:
##   1  production scene loads (CassiSim + SimUI + Camera3D, scripts attached)
##   2  the simulation reaches a ready, non-failed state inside the boot budget
##   3  stepping is deterministic — frame pacing is frozen before any explicit
##      window, and each explicit window executes exactly its requested steps
##   4  sampled particle/velocity state stays finite (field roles included when
##      the grid path exposes them)
##   5  particles stay alive and move a bounded, non-zero distance
##   6  forces act — sampled velocities change within a bounded envelope
##   7  sampled particle mass stays conserved
##   8  field telemetry matches the mode contract. On the shipped configuration
##      (gridless_physics = true) the engine allocates its grid-field buffers at
##      1 cell by design — the site buffer is authoritative — so the EY/EI/q
##      aggregates are reported UNAVAILABLE, never passed vacuously; their band
##      and blow-up guards run when the grid path is actually present
##   9  the site-native field telemetry the engine itself reports on the
##      gridless path (weighted q_mean, site q range) stays finite and bounded
##  10  the production renderer draws a visible frame (PNG written)
##  11  the production UI builds with its default-off controls
##  12  the production scene declares its pinned configuration contract
##
## The contract fingerprint is read before the scene enters the tree: several
## exports (the qi color bands among them) are re-resolved at boot from a
## machine-local user:// config, so the post-boot values are runtime state and
## are recorded in the receipt unjudged.
##
## This gate deliberately does NOT re-derive physics: analytic identities, the
## φ-box stencil battery, local-RD engine branches (FFT/FMM/merge/BH/radiation),
## the 7599 mind engine and the audit-grade export contracts are manual probes,
## run when their subsystem is touched. Coverage is the shipped default path.
##
## Run windowed (the global RenderingDevice needs a real window on this rig):
##   "<console exe>" --path . res://scenes/verify_core.tscn
## Named fast fixture (reduced particle count — NOT exact production coverage;
## the receipt records which mode ran):
##   "<console exe>" --path . res://scenes/verify_core.tscn -- --fast
##
## Exit 0 only when every check passes. Receipt:
## res://_diag/core/core_receipt.json  (+ core_frame.png)

const SCENE_PATH := "res://scenes/main.tscn"
const OUTPUT_DIR := "res://_diag/core"
const RECEIPT_PATH := OUTPUT_DIR + "/core_receipt.json"
const FRAME_PATH := OUTPUT_DIR + "/core_frame.png"

const WINDOW_SIZE := Vector2i(960, 540)
const STEP_WINDOW := 8                 # explicit steps per sampling window
const WINDOW_COUNT := 2                # windows after the pre-window baseline
const BOOT_TIMEOUT_SEC := 240.0
const WARMUP_MIN_STEPS := 2            # decoupled bootstrap: first publish needs steps
const FREEZE_FRAMES := 3               # frames used to prove pacing is frozen
const SAMPLE_CHUNK := 65536            # particles per contiguous readback chunk
const SAMPLE_CHUNKS := 3               # chunks spread across the particle buffer
const FAST_PARTICLES := 65536

# Bands. These are sanity envelopes for a smoke gate, widened deliberately; the
# measured values land in the receipt. Freeze tighter numbers only from a run on
# a settled tree (see the notebook/plan), never from a provisional run.
const MIN_MOVING_FRACTION := 0.90      # of sampled particles
const MAX_MEAN_DISPLACEMENT := 4096.0  # world units per 8-step window (box is φ·1500-scale)
const MASS_DRIFT_TOL := 5.0e-3         # relative, sampled chunks, across all windows
const CHARGE_DRIFT_TOL := 5.0e-2       # relative, full-field EY/EI sums (grid path only)
const Q_ABS_MAX := 1.0e6               # blow-up guard on max |q| (grid path only)
const MAX_MEAN_VELOCITY_DELTA := 1.0e3 # mean |Δv| per 8-step window (site path)
const MIN_NONBACKGROUND := 0.002       # lit-pixel fraction of the captured frame
const LIT_THRESHOLD := 0.02            # per-channel value counted as lit

## The pinned production contract: what main.tscn sets on its CassiSim node.
const PINNED_OVERRIDES := {
	"dt": 0.05,
	"num_clusters": 3,
	"cluster_separation": 1500.0,
	"rotation_stress_enabled": true,
	"bh_accretion": false,
	"vsync_enabled": true,
	"river_calibrate_gn": true,
	"field_attractor_init": true,
	"initial_condition": 6,
	"initial_motion": 1,
	"initial_speed": 1.0,
	"gridless_physics": true,
	"tree_hierarchical_refit": true,
	"q_weighted_com": true,
	"observatory_style": 1,
	"compact_render_data": true,
	"presentation_color_scheme": 1,
	"presentation_trails_enabled": true,
	"presentation_volume_history_enabled": true,
	"qi_cycle": Vector2(0.005, 1.0),
	"qi_approach": Vector2(0.8, 1.0),
	"volume_dynamic_resolution": true,
}

## Defaults main.tscn does NOT override, so production inherits them. The
## particle count is the only axis the named fast fixture is allowed to change.
const PINNED_INHERITED := {
	"grid_N": 64,
	"N_particles": 2500000,
	"gravity_mode": 4,
	"meshless_gravity": true,
	"physics_decoupled": true,
	"level_swap": true,
	"particle_merge": false,
	"black_holes_enabled": false,
	"field_intelligence_enabled": false,
	"physical_matter_enabled": false,
	"field_particles": false,
}

var _world: Node3D
var _sim: Node
var _camera: Camera3D
var _ui: Control
var _capture: Node
var _dev: RenderingDevice
var _fast := false

var _rows: Array[Dictionary] = []
var _failures := 0
var _t0 := 0
var _receipt := {}
var _warmup := {}
var _boot_failed := false


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT_DIR))
	for argument in OS.get_cmdline_user_args():
		if argument == "--fast":
			_fast = true
	_receipt["mode"] = "fast_fixture(%d particles)" % FAST_PARTICLES if _fast else "exact_production"
	get_window().size = WINDOW_SIZE

	_world = load(SCENE_PATH).instantiate()
	_sim = _world.get_node_or_null("CassiSim")
	_camera = _world.get_node_or_null("Camera3D")
	_ui = _world.get_node_or_null("UILayer/SimUI")
	_check("production scene loads (CassiSim + Camera3D + SimUI present, scripts attached)",
			_sim != null and _sim.get_script() != null and _camera != null and _ui != null and _ui.get_script() != null,
			"sim=%s camera=%s ui=%s" % [_sim != null, _camera != null, _ui != null])
	if _sim == null or _camera == null or _ui == null:
		_finish()
		return

	# Deterministic drive: no frame pacing may advance the simulation until the
	# deliberate warm-up below, and never after it is frozen again.
	_sim.set("playing", false)
	if _fast:
		_sim.set("N_particles", FAST_PARTICLES)

	# Fingerprint the SCENE CONTRACT here, before add_child. Several exports are
	# re-resolved at boot from machine-local sources (load_color_defaults() reads
	# a user:// config file), so post-boot values are runtime state, not the
	# scene's declaration; they land in the receipt unjudged.
	_check_fingerprint(_capture_config())

	_world.tree_entered.connect(func() -> void: get_tree().current_scene = _world, CONNECT_ONE_SHOT)
	get_tree().root.add_child.call_deferred(_world)
	await _world.ready
	_dev = _sim.get("_rd")
	_capture = _ui.get("_capture_helper")

	await _boot_and_warm_up()
	if not _boot_failed:
		await _run_checks()
	_finish()


# ── boot ───────────────────────────────────────────────────────────────

## Setup runs with pacing frozen. The decoupled bootstrap publishes only after
## the engine has executed steps, so the warm-up is an explicit, recorded
## playing=true window, after which pacing is frozen again.
func _boot_and_warm_up() -> void:
	var setup_ok := await _await_setup()
	_check("simulation reaches setup ready without fail-closed state", setup_ok,
			"shaders_ready=%s gridless_failure=%s engine_ready=%s" % [
				_sim.get("_shaders_ready"), _sim.get("_gridless_failure"), _engine_ready()])
	if not setup_ok:
		_boot_failed = true
		return

	var steps_at_warmup := _executed()
	var warmup_start_ms := Time.get_ticks_msec()
	_sim.set("playing", true)
	var booted := await _await_first_publish()
	_sim.set("playing", false)
	_warmup = {
		"steps_start": steps_at_warmup,
		"steps_end": _executed(),
		"sec": float(Time.get_ticks_msec() - warmup_start_ms) / 1000.0,
		"first_publish": booted,
	}
	_check("production scene completes its decoupled bootstrap (first publish lands)", booted,
			"warm-up executed %d steps in %.2f s" % [_warmup["steps_end"] - _warmup["steps_start"], _warmup["sec"]])
	if not booted:
		_boot_failed = true
		return

	# Freeze proof: with pacing off, the step counter must not move on its own.
	var frozen_at := _executed()
	await _frames(FREEZE_FRAMES)
	_check("frame pacing is frozen before the explicit windows",
			_executed() == frozen_at, "counter %d -> %d over %d frames" % [frozen_at, _executed(), FREEZE_FRAMES])


func _await_setup() -> bool:
	var deadline := Time.get_ticks_msec() + int(BOOT_TIMEOUT_SEC * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if bool(_sim.get("_gridless_failure")):
			return false
		if bool(_sim.get("_shaders_ready")) and _engine_ready():
			return true
		await get_tree().process_frame
	return false


func _await_first_publish() -> bool:
	var deadline := Time.get_ticks_msec() + int(BOOT_TIMEOUT_SEC * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if bool(_sim.get("_gridless_failure")):
			return false
		if not bool(_sim.get("_decoupled_boot_wait")) and int(_sim.get("_step_count")) >= WARMUP_MIN_STEPS:
			return true
		await get_tree().process_frame
	return false


func _engine_ready() -> bool:
	if not bool(_sim.get("_decoupled_active")):
		return true
	var engine: Object = _sim.get("_physics_engine")
	return engine != null and bool(engine.call("setup_ready"))


# ── checks ─────────────────────────────────────────────────────────────

func _run_checks() -> void:
	_receipt["runtime_config"] = _capture_config()
	_receipt["runtime_config_note"] = ("live post-boot values, informational only — exports such as the qi color " +
			"bands are re-resolved at boot from the user:// color-defaults config")
	_check_ui()

	var baseline := _sample()
	await _capture_frame()

	var windows: Array[Dictionary] = []
	for index in WINDOW_COUNT:
		if not _run_window(index + 1):
			break
		windows.append(_sample())
	_receipt["windows"] = windows.map(func(entry: Dictionary) -> Dictionary:
		var row := entry.duplicate()
		row.erase("pos")
		row.erase("vel")
		return row)

	if windows.size() < WINDOW_COUNT:
		_check("explicit step windows execute", false, "only %d/%d windows ran" % [windows.size(), WINDOW_COUNT])
		return

	_check_finiteness(baseline, windows)
	_check_motion(windows)
	_check_forces(windows)
	_check_mass_conservation(baseline, windows)
	_check_field_telemetry(baseline, windows)
	_check_site_telemetry(baseline, windows)


func _run_window(index: int) -> bool:
	var before := _executed()
	_sim.call("_run_physics_steps", STEP_WINDOW)
	var after := _executed()
	_check("explicit window %d executes exactly %d steps" % [index, STEP_WINDOW],
			after - before == STEP_WINDOW, "executed %d -> %d" % [before, after])
	return after - before == STEP_WINDOW


func _check_finiteness(baseline: Dictionary, windows: Array[Dictionary]) -> void:
	var bad: Array[String] = []
	for entry in [baseline] + windows:
		for key in ["pos_finite", "vel_finite"]:
			if not bool(entry[key]):
				bad.append(String(key).trim_suffix("_finite"))
		if _field_authoritative(entry):
			for key in ["ey_finite", "ei_finite", "q_finite"]:
				if not bool(entry[key]):
					bad.append(String(key).trim_suffix("_finite"))
	_check("sampled particle/velocity/field state is finite", bad.is_empty(),
			"" if bad.is_empty() else "non-finite: %s" % ", ".join(bad))


func _check_motion(windows: Array[Dictionary]) -> void:
	var previous: PackedFloat32Array = windows[0]["pos"]
	for index in range(1, windows.size()):
		var current: PackedFloat32Array = windows[index]["pos"]
		var shared := mini(previous.size(), current.size()) / 4
		if shared <= 0:
			_check("sampled particles move without vanishing", false, "empty position sample")
			return
		var moved := 0
		var displacement := 0.0
		var alive := 0
		for particle in shared:
			var base := particle * 4
			if current[base + 3] <= 0.0:
				continue
			alive += 1
			var dx := current[base] - previous[base]
			var dy := current[base + 1] - previous[base + 1]
			var dz := current[base + 2] - previous[base + 2]
			var distance := sqrt(dx * dx + dy * dy + dz * dz)
			displacement += distance
			if distance > 0.0:
				moved += 1
		var moving_fraction := float(moved) / float(shared)
		var mean := displacement / float(shared)
		_check("window %d: sampled particles are alive and moving a bounded distance" % index,
				alive > 0 and moving_fraction >= MIN_MOVING_FRACTION and mean > 0.0 and mean < MAX_MEAN_DISPLACEMENT,
				"alive %d/%d, moving %.3f, mean displacement %.4f world units" % [alive, shared, moving_fraction, mean])
		previous = current


## Velocities are the authoritative site state on the shipped gridless path:
## the tree-walk KDK writes them in place, so a window with zero mean |Δv| means
## forces stopped being applied, and an unbounded one means blow-up.
func _check_forces(windows: Array[Dictionary]) -> void:
	var previous: PackedFloat32Array = windows[0]["vel"]
	for index in range(1, windows.size()):
		var current: PackedFloat32Array = windows[index]["vel"]
		var shared := mini(previous.size(), current.size()) / 4
		if shared <= 0:
			_check("forces act on the sampled velocities", false, "empty velocity sample")
			return
		var delta := 0.0
		for particle in shared:
			var base := particle * 4
			var dx := current[base] - previous[base]
			var dy := current[base + 1] - previous[base + 1]
			var dz := current[base + 2] - previous[base + 2]
			delta += sqrt(dx * dx + dy * dy + dz * dz)
		var mean := delta / float(shared)
		_check("window %d: forces change the sampled velocities within a bounded envelope" % index,
				is_finite(mean) and mean > 0.0 and mean < MAX_MEAN_VELOCITY_DELTA,
				"mean |Δv| %.6f over %d steps (envelope 0..%.1f), max |v| %.4f" % [
					mean, STEP_WINDOW, MAX_MEAN_VELOCITY_DELTA, float(windows[index]["vel_abs_max"])])
		previous = current


func _check_mass_conservation(baseline: Dictionary, windows: Array[Dictionary]) -> void:
	var first_mass := float(baseline["mass"])
	var last_mass := float(windows[windows.size() - 1]["mass"])
	var mass_drift := 0.0 if first_mass == 0.0 else absf(last_mass - first_mass) / absf(first_mass)
	_check("sampled particle mass is conserved across the run",
			first_mass > 0.0 and mass_drift <= MASS_DRIFT_TOL,
			"mass %.6f -> %.6f (relative drift %.5f)" % [first_mass, last_mass, mass_drift])


## On the shipped configuration (gridless_physics = true) the engine allocates
## its grid-field buffers at 1 cell by design — the authoritative state is the
## site buffer, so the EY/EI/q aggregates are UNAVAILABLE, not passing. The
## mode contract is asserted either way; the band checks run only when the grid
## path is actually present.
func _check_field_telemetry(baseline: Dictionary, windows: Array[Dictionary]) -> void:
	var cells := int(baseline["field_cells"])
	var gridless := bool(_sim.get("gridless_physics"))
	var expected := 1 if gridless else int(pow(int(_sim.get("grid_N")), 3))
	_check("field telemetry matches the mode contract",
			cells == expected and cells > 0,
			"role buffers hold %d cell(s), expected %d (%s)" % [cells, expected,
				"gridless site-native path — descriptor-sized placeholders by design"
				if gridless else "grid field path"])
	_receipt["field_telemetry"] = {
		"cells": cells,
		"expected": expected,
		"gridless": gridless,
		"aggregates_available": _field_authoritative(baseline),
	}
	if not _field_authoritative(baseline):
		return

	for key in ["ey", "ei"]:
		var first := float(baseline[key])
		var last := float(windows[windows.size() - 1][key])
		var drift := 0.0 if first == 0.0 else absf(last - first) / absf(first)
		_check("field %s sum stays within band (post-baseline invariant)" % key.to_upper(),
				is_finite(last) and drift <= CHARGE_DRIFT_TOL,
				"sum %.4f -> %.4f (relative drift %.5f)" % [first, last, drift])

	var worst := 0.0
	for entry in [baseline] + windows:
		worst = maxf(worst, float(entry["q_abs_max"]))
	_check("field stays bounded (max |q| blow-up guard)", is_finite(worst) and worst <= Q_ABS_MAX,
			"max |q| = %.4f over %d windows" % [worst, windows.size() + 1])


func _field_authoritative(entry: Dictionary) -> bool:
	return int(entry["field_cells"]) >= 2


## The engine's authoritative site-native field observable. On the shipped
## gridless path the raster role buffers are 1-cell placeholders, so the site
## statistics are the field state that can actually fail: readback_telemetry()
## computes them in its gridless branch (the site-stats buffer when published,
## otherwise the volume-weighted site rows of the meshless arrays).
func _site_telemetry() -> Dictionary:
	var engine: Object = _sim.get("_physics_engine")
	if not bool(_sim.get("_decoupled_active")) or engine == null:
		return {}
	return engine.call("readback_telemetry")


## Recorded and judged only where the site buffer is the authoritative state.
## The raster band checks above cannot see it, so dropping this would leave the
## shipped path with no field blow-up invariant at all.
func _check_site_telemetry(baseline: Dictionary, windows: Array[Dictionary]) -> void:
	if not bool(_sim.get("gridless_physics")):
		return
	var rows: Array = [baseline] + windows
	for entry in rows:
		if not bool(entry["site_telemetry_present"]):
			_check("site-native field telemetry is reported by the engine", false,
					"no site telemetry on the gridless path (missing q statistics, or the " +
					"field-particle catalog branch answered instead)")
			return
	var finite := true
	var worst_mean := 0.0
	var worst_abs := 0.0
	for entry in rows:
		var q_mean := float(entry["site_q_mean"])
		var q_min := float(entry["site_q_min"])
		var q_max := float(entry["site_q_max"])
		finite = finite and is_finite(q_mean) and is_finite(q_min) and is_finite(q_max)
		worst_mean = maxf(worst_mean, absf(q_mean))
		worst_abs = maxf(worst_abs, maxf(absf(q_min), absf(q_max)))
	_check("site-native field telemetry stays finite and bounded",
			finite and worst_abs > 0.0 and worst_abs <= Q_ABS_MAX,
			"weighted |q_mean| up to %.6f, site |q| range up to %.6f over %d samples (guard %.0f; must be nonzero)" % [
				worst_mean, worst_abs, rows.size(), Q_ABS_MAX])
	_receipt["site_telemetry"] = {
		"samples": rows.size(),
		"q_mean_abs_max": worst_mean,
		"q_abs_max": worst_abs,
		"finite": finite,
	}


func _capture_config() -> Dictionary:
	var snapshot := {}
	for key in PINNED_OVERRIDES:
		snapshot[key] = _sim.get(key)
	for key in PINNED_INHERITED:
		snapshot[key] = _sim.get(key)
	return snapshot


func _check_fingerprint(declared: Dictionary) -> void:
	var mismatches: Array[String] = []
	for key in PINNED_OVERRIDES:
		if not _matches(declared[key], PINNED_OVERRIDES[key]):
			mismatches.append("%s = %s (pinned %s)" % [key, str(declared[key]), str(PINNED_OVERRIDES[key])])
	for key in PINNED_INHERITED:
		if _fast and key == "N_particles":
			continue
		if not _matches(declared[key], PINNED_INHERITED[key]):
			mismatches.append("%s = %s (inherited %s)" % [key, str(declared[key]), str(PINNED_INHERITED[key])])
	_receipt["fingerprint_mismatches"] = mismatches
	var detail := "mode %s; " % _receipt["mode"]
	if mismatches.is_empty():
		detail += "all %d values match" % (PINNED_OVERRIDES.size() + PINNED_INHERITED.size() - (1 if _fast else 0))
		if _fast:
			detail += " (N_particles replaced by the named fast fixture)"
	else:
		detail += " | ".join(mismatches)
	_check("production scene declares the pinned contract", mismatches.is_empty(), detail)


func _check_ui() -> void:
	var missing: Array[String] = []
	var defaulted_on: Array[String] = []
	for control_name in ["VfxSizeBtn", "VfxGlowBtn", "VfxDepthBtn", "VfxTwoAxisBtn", "presentation_profileToggle"]:
		var control := _ui.find_child(control_name, true, false)
		if control == null or not control is CheckButton:
			missing.append(control_name)
		elif (control as CheckButton).button_pressed:
			defaulted_on.append(control_name)
	if _ui.find_child("field_particlesToggle", true, false) == null:
		missing.append("field_particlesToggle")
	_check("production UI builds with its default-off controls", missing.is_empty() and defaulted_on.is_empty(),
			"missing: %s; defaulted on: %s" % [", ".join(missing) if not missing.is_empty() else "none",
				", ".join(defaulted_on) if not defaulted_on.is_empty() else "none"])
	_check("production capture helper is wired to the UI", _capture != null,
			"capture helper %s" % ("present" if _capture != null else "missing"))


# ── sampling ───────────────────────────────────────────────────────────

func _sample() -> Dictionary:
	var field_state: Dictionary = _sim.call("get_field_role_state")
	var ey := _read_floats(field_state.get("ey", RID()))
	var ei := _read_floats(field_state.get("ei", RID()))
	var q := _read_floats(field_state.get("q", RID()))
	var site := _site_telemetry()
	# Presence must exclude the field-particle catalog branch of
	# readback_telemetry(), which reports zeros by design: a default-zero dict
	# must never be able to masquerade as a healthy site field.
	var site_keys := (site.has("q_mean") and site.has("q_min") and site.has("q_max")
			and not bool(site.get("field_particles", false)))
	var pos := _read_particle_chunks(_particle_rid())
	var vel := _read_particle_chunks(_vel_rid())
	return {
		"field_cells": ey.size(),
		"ey": _sum(ey),
		"ei": _sum(ei),
		"q_abs_max": _abs_max(q),
		"ey_finite": _is_finite(ey),
		"ei_finite": _is_finite(ei),
		"q_finite": _is_finite(q),
		"site_telemetry_present": site_keys,
		"site_q_mean": float(site.get("q_mean", NAN)),
		"site_q_min": float(site.get("q_min", NAN)),
		"site_q_max": float(site.get("q_max", NAN)),
		"sampled_particles": pos.size() / 4,
		"pos_finite": _is_finite(pos),
		"vel_finite": _is_finite(vel),
		"vel_abs_max": _abs_max(vel),
		"mass": _mass_sum(pos),
		"alive": _alive_count(pos),
		"pos": pos,
		"vel": vel,
	}


func _read_floats(rid: RID) -> PackedFloat32Array:
	if not rid.is_valid() or _dev == null:
		return PackedFloat32Array()
	return _dev.buffer_get_data(rid).to_float32_array()


## Contiguous chunks spread across the particle buffer — a sample, never a full
## readback (the production buffer is 40 MB at 2.5M particles).
func _read_particle_chunks(rid: RID) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	if not rid.is_valid() or _dev == null:
		return out
	var particles := maxi(int(_sim.get("N_particles")), 1)
	var chunk_particles := mini(SAMPLE_CHUNK, particles)
	var chunk_bytes := chunk_particles * 16
	var span := particles * 16 - chunk_bytes
	for index in SAMPLE_CHUNKS:
		var offset := 0
		if span > 0 and SAMPLE_CHUNKS > 1:
			offset = int(round(float(span) * float(index) / float(SAMPLE_CHUNKS - 1)))
			offset = (offset / 16) * 16
		var raw := _dev.buffer_get_data(rid, offset, chunk_bytes)
		if raw.size() == 0:
			break
		out.append_array(raw.to_float32_array())
	return out


func _particle_rid() -> RID:
	var engine: Object = _sim.get("_physics_engine")
	if bool(_sim.get("_decoupled_active")) and engine != null:
		var rid: RID = engine.get("_pos_buf")
		if rid.is_valid():
			return rid
	return _sim.get("_pos_buf")


func _vel_rid() -> RID:
	var engine: Object = _sim.get("_physics_engine")
	if bool(_sim.get("_decoupled_active")) and engine != null:
		var rid: RID = engine.get("_vel_buf")
		if rid.is_valid():
			return rid
	return _sim.get("_vel_buf")


func _sum(values: PackedFloat32Array) -> float:
	var total := 0.0
	for value in values:
		total += value
	return total


func _abs_max(values: PackedFloat32Array) -> float:
	var worst := 0.0
	for value in values:
		worst = maxf(worst, absf(value))
	return worst


func _is_finite(values: PackedFloat32Array) -> bool:
	if values.size() == 0:
		return false
	for value in values:
		if not is_finite(value):
			return false
	return true


## Mass lives in pos.w; dead particles are marked with pos.w = 0.
func _mass_sum(pos: PackedFloat32Array) -> float:
	var total := 0.0
	for particle in pos.size() / 4:
		total += pos[particle * 4 + 3]
	return total


func _alive_count(pos: PackedFloat32Array) -> int:
	var alive := 0
	for particle in pos.size() / 4:
		if pos[particle * 4 + 3] > 0.0:
			alive += 1
	return alive


# ── capture ────────────────────────────────────────────────────────────

func _capture_frame() -> void:
	await RenderingServer.frame_post_draw
	var texture := get_viewport().get_texture()
	if texture == null:
		_check("production renderer draws a visible frame", false, "no viewport texture")
		return
	var image := texture.get_image()
	if image == null or image.is_empty():
		_check("production renderer draws a visible frame", false, "empty viewport image")
		return
	image.save_png(ProjectSettings.globalize_path(FRAME_PATH))
	var step_x := maxi(image.get_width() / 64, 1)
	var step_y := maxi(image.get_height() / 36, 1)
	var sampled := 0
	var lit := 0
	for y in range(0, image.get_height(), step_y):
		for x in range(0, image.get_width(), step_x):
			sampled += 1
			var pixel := image.get_pixel(x, y)
			if maxf(pixel.r, maxf(pixel.g, pixel.b)) > LIT_THRESHOLD:
				lit += 1
	var fraction := 0.0 if sampled == 0 else float(lit) / float(sampled)
	_receipt["frame"] = {
		"path": FRAME_PATH,
		"width": image.get_width(),
		"height": image.get_height(),
		"lit_fraction": fraction,
	}
	_check("production renderer draws a visible frame", fraction >= MIN_NONBACKGROUND,
			"%dx%d, lit fraction %.4f (floor %.4f), saved %s" % [
				image.get_width(), image.get_height(), fraction, MIN_NONBACKGROUND, FRAME_PATH])


# ── plumbing ───────────────────────────────────────────────────────────

func _matches(actual: Variant, expected: Variant) -> bool:
	if expected is float:
		return actual is float and is_equal_approx(float(actual), float(expected))
	if expected is Vector2:
		return actual is Vector2 and (actual as Vector2).is_equal_approx(expected)
	return actual == expected


func _executed() -> int:
	var engine: Object = _sim.get("_physics_engine")
	if bool(_sim.get("_decoupled_active")) and engine != null:
		return int(engine.get("_executed"))
	return int(_sim.get("_step_count"))


func _frames(count: int) -> void:
	for _index in count:
		await get_tree().process_frame


func _check(label: String, passed: bool, detail := "") -> void:
	_rows.append({"check": label, "ok": passed, "detail": detail})
	if not passed:
		_failures += 1
	print("[%s] %s%s" % ["PASS" if passed else "FAIL", label, "" if detail == "" else "  — " + detail])


func _finish() -> void:
	_receipt["checks"] = _rows
	_receipt["failures"] = _failures
	_receipt["passed"] = _rows.size() - _failures
	_receipt["warmup"] = _warmup
	_receipt["total_sec"] = float(Time.get_ticks_msec() - _t0) / 1000.0
	var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(_receipt, "\t"))
		file.close()
	print("VERIFY CORE RESULT: %d/%d checks passed in %.1f s (%s)" % [
		_rows.size() - _failures, _rows.size(), _receipt["total_sec"], _receipt["mode"]])
	print("receipt: %s" % RECEIPT_PATH)
	get_tree().quit(0 if _failures == 0 and _rows.size() > 0 else 1)
