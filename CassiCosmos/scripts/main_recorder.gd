extends Node3D

# ═══════════════════════════════════════════════════════════════════════
# Background recording mode (Movie Maker batch job).
#
# Run via the console exe with --write-movie and a fixed fps; this scene
# owns the orbital camera, applies command-line overrides, and quits when
# the requested frame count is reached (Movie Maker finalizes the AVI on
# quit). No UI nodes: the video shows only the particles; progress goes
# to stdout.
# ═══════════════════════════════════════════════════════════════════════

# ── Scene defaults ──
@export var record_frames: int = 900          # 30 s at 30 fps
@export var record_fps: int = 30
@export var orbit_radius: float = 150.0       # camera distance from origin
@export var orbit_elevation: float = 0.35     # fixed height angle (rad)
@export var orbit_speed: float = 0.12         # rad/s around Y
@export var recording_size: Vector2i = Vector2i(1920, 1080)

var _cam: Camera3D
var _sim: Node3D
var _frame_count: int = 0
var _angle: float = 0.0


func _ready() -> void:
	# Children init before the root: CassiSim already ran its _ready with
	# the scene defaults. Grab it and the camera, then apply overrides.
	_cam = get_node("Camera3D") as Camera3D
	_sim = get_node("CassiSim")
	_cam.fov = 65.0
	_cam.near = 0.1
	_cam.far = 2000.0

	# Movie fps: the reliable mechanism is --fixed-fps N on the command
	# line -- main.cpp passes it straight to MovieWriter::begin() at engine
	# start (verified: AVI strh fps matches; a runtime
	# ProjectSettings.set_setting("movie_writer/fps", ...) is a no-op for
	# the recording because begin() already ran -- keep it only so the
	# scene arg and the project setting never disagree on bare runs). The
	# AVI RESOLUTION is likewise fixed at engine start from the project
	# settings display/window/size/viewport_width/height (the window size
	# and the width_override pair are ignored or DPI-scaled on Windows) --
	# record.ps1 patches project.godot's viewport settings for the run.
	if record_fps != int(ProjectSettings.get_setting("movie_writer/fps", 30)):
		ProjectSettings.set_setting("movie_writer/fps", record_fps)

	get_window().size = recording_size
	print("[Recorder] window size after apply: %dx%d (requested %dx%d)" % [
		get_window().size.x, get_window().size.y, recording_size.x, recording_size.y])

	# ── Inherit the current settings from scenes/main.tscn ──
	# The recorder no longer carries its own settings copy: whatever is
	# currently set on main.tscn's CassiSim node (editor edits are written
	# to the file) IS the config. Load the scene WITHOUT adding it to the
	# tree (no _ready, no GPU work), copy the curated properties, free it,
	# then reinit so the sim's _ready-time buffers match. The recorder
	# owns suppress_readbacks / max_steps_per_frame / playing itself.
	var reinit_needed := false
	var inherit_list := [
		"grid_N", "N_particles", "dt", "xi", "softening", "particle_size",
		"cluster_radius", "num_clusters", "cluster_separation", "merger_speed",
		"source_strength", "qi_condensation_threshold", "bh_acc_rate",
		"bh_max_age", "black_holes_enabled", "gravity_mode", "realsim_drag", "realsim_viscosity",
		"realsim_friction", "river_calibrate_gn", "river_pi_ref",
		"river_q_ref", "field_attractor_init", "initial_radius_fraction",
		"initial_condition", "mode",
	]
	var main_scene := load("res://scenes/main.tscn")
	if main_scene != null:
		var inst = main_scene.instantiate()  # NOT added to the tree
		var src = inst.get_node_or_null("CassiSim")
		if src == null:
			push_warning("[Recorder] main.tscn has no CassiSim node — using script defaults")
		else:
			for p in inherit_list:
				var v = src.get(p)
				if v != null:
					_sim.set(p, v)
			reinit_needed = true
			print("[Recorder] inherited from main.tscn: grid=%d particles=%d grav=%d init=%d sep=%.1f" % [
				_sim.get("grid_N"), _sim.get("N_particles"), _sim.get("gravity_mode"),
				_sim.get("initial_condition"), _sim.get("cluster_separation")])
		inst.free()
	else:
		push_warning("[Recorder] main.tscn not readable — using script defaults")

	# ── Command-line overrides (args after `--`) ──
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"--record-frames":
				record_frames = int(kv[1])
			"--record-fps":
				record_fps = int(kv[1])
				ProjectSettings.set_setting("movie_writer/fps", record_fps)
			"--grid":
				_sim.set("grid_N", int(kv[1]))
				reinit_needed = true
			"--particles":
				_sim.set("N_particles", int(kv[1]))
				reinit_needed = true
			"--gravity":
				_sim.set("gravity_mode", int(kv[1]))
				reinit_needed = true
			"--init":
				_sim.set("initial_condition", int(kv[1]))
				reinit_needed = true
			"--bhs":
				# BH toggle: live export set, no reinit needed (the host
				# re-encodes bh[3].x next frame).
				_sim.set("black_holes_enabled", int(kv[1]) != 0)
			"--steps":
				_sim.set("max_steps_per_frame", int(kv[1]))
			"--orbit-speed":
				orbit_speed = float(kv[1])
			"--orbit-radius":
				orbit_radius = float(kv[1])

	# The sim already ran _ready with script defaults; reinit applies the
	# inherited settings + CLI overrides (fresh buffers/field/particles at
	# the new sizes).
	if reinit_needed:
		_sim.call("reinit")

	print("[Recorder] frames=%d fps=%d size=%dx%d grid=%d particles=%d grav=%d init=%d steps=%d orbit=%.2f rad/s" % [
		record_frames, record_fps, recording_size.x, recording_size.y,
		_sim.get("grid_N"), _sim.get("N_particles"), _sim.get("gravity_mode"),
		_sim.get("initial_condition"), _sim.get("max_steps_per_frame"), orbit_speed])


func _process(delta: float) -> void:
	# Slow orbital camera: rotate around Y at a fixed elevation, always
	# looking at the origin (the cluster sits there).
	_angle += orbit_speed * delta
	var e := orbit_elevation
	_cam.position = Vector3(
		orbit_radius * cos(_angle) * cos(e),
		orbit_radius * sin(e),
		orbit_radius * sin(_angle) * cos(e))
	_cam.look_at(Vector3.ZERO, Vector3.UP)

	_frame_count += 1
	if _frame_count % 30 == 0 or _frame_count == record_frames:
		var sim_t := float(_sim.get("_time"))
		print("[Recorder] frame %d/%d (sim t=%.2f)" % [_frame_count, record_frames, sim_t])

	if _frame_count >= record_frames:
		print("[Recorder] done")
		get_tree().quit(0)
