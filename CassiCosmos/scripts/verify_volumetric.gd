extends Node
## Volumetric verify — ray-marched rendering of the Cassi Qi field.
##
## Self-contained: builds a KNOWN analytic φ-attractor-like field (central
## condensate blob + ε Yin/Yang structure, research/volumetric/volumetric_design.md
## §5) into a 64³ RG float 3D texture, renders ONE frame through a SubViewport
## with compute/cassi_volumetric.gdshader (the fragment raymarcher), and dumps:
##   _diag/volumetric_frame.png   — the sRGB PNG preview
##   _diag/volumetric_pixels.json — the raw RGBAF pixel floats + the full
##                                  geometry/palette/analytic parameter set
## research/volumetric/volumetric_verify.py recomputes the SAME analytic field
## and raymarch in NumPy and gates G35 (≤1e-1 relative L2; pink hue at the
## φ-gate pixel).
##
## Run (WINDOWED — the sim's global-RD rule; NEVER --headless):
##   godot --path <repo> res://scenes/verify_volumetric.tscn

const PHI := 1.618033988749895
const N := 64
const E := Vector3(PHI, 1.0, PHI * PHI)   # φ-aspect box HALF-extents

# analytic field (§5)
const SIGMA := 0.62
const A_CORE := 0.5
const B_CORE := 0.5
const EPS := 0.06
const SIGMA_EPS := 0.18
const P1 := Vector3(0.85, 0.25, -0.35)
const P2 := Vector3(0.95, -0.20, 0.30)

# palette / model (§3) — a_top = 0.93: PINK at the white point (the house
# palette, cassi_sim.gd:2461 — "red never appears at high coherence"). The
# φ-gate pixel targets the pink SHELL via a ray TANGENT to the r_gate sphere
# (impact parameter = r_gate): such a ray samples r ≥ r_gate only, so the
# pink shell is accumulated WITHOUT dilution by the achromatic white core.
# With GATE_PA = 0.95 the accumulated pink hue is 0.90-0.91 for step counts
# 160-448 (design §7) — robustly in [0.90, 0.97].
const A_LO := 0.2
const A_HI := 0.5
const A_TOP := 0.93
const GATE_PA := 0.95                   # φ-gate approach progress (pink shell)
const APPROACH_ON := 1.0
const Q_LO := 0.0002
const Q_HI := 0.001
const SLOPE := 1.0 / log(5.0)          # 1/ln(q_hi/q_lo)  (ln = log in GDScript)
const S_ABS := 2.0
const S_EM := 0.31                  # scaled so peak linear radiance ~ 1.0 (no 8-bit saturation)
const S_FOG := 0.0
const GLOW := 0.0
const EPS_T := 0.001
const STEPS := 224                      # GPU march steps

# camera (mirrored exactly in the NumPy reference)
const VIEWPORT := Vector2i(256, 256)
const CAM_POS := Vector3(-4.5, 0.8, 2.6)
const CAM_TARGET := Vector3(0.0, 0.0, 0.0)
const CAM_UP := Vector3(0.0, 1.0, 0.0)
const FOV_DEG := 55.0

var _viewport: SubViewport
var _camera: Camera3D
var _checks := 0
var _failures := 0


func _ready() -> void:
	_build_scene()
	_setup_material()
	for _f in range(3):
		await get_tree().process_frame
	await _grab_and_dump()
	_finish()


func _build_scene() -> void:
	# The SubViewport is our off-screen render target (its own 3D world).
	_viewport = SubViewport.new()
	_viewport.name = "VolViewport"
	_viewport.size = VIEWPORT
	_viewport.transparent_bg = false
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	_viewport.snap_2d_transforms_to_pixel = true
	add_child(_viewport)

	var vp_root := Node3D.new()
	vp_root.name = "VolWorld"
	_viewport.add_child(vp_root)

	_camera = Camera3D.new()
	_camera.name = "Cam"
	_camera.current = true
	_camera.fov = FOV_DEG
	_camera.position = CAM_POS
	_camera.look_at_from_position(CAM_POS, CAM_TARGET, CAM_UP)
	vp_root.add_child(_camera)


func _build_field_texture() -> Texture3D:
	# ImageTexture3D.create(format, w, h, depth, mips, images) takes an
	# Array[Image] of depth slices, one N×N Image per z.
	var images: Array[Image] = []
	images.resize(N)
	for z in range(N):
		var slice := Image.create(N, N, false, Image.FORMAT_RGF)
		for y in range(N):
			for x in range(N):
				var wx := (float(x) + 0.5) / float(N) * 2.0 - 1.0
				var wy := (float(y) + 0.5) / float(N) * 2.0 - 1.0
				var wz := (float(z) + 0.5) / float(N) * 2.0 - 1.0
				var p := Vector3(wx * E.x, wy * E.y, wz * E.z)
				var vy: float = _field_ey(p)
				var vi: float = _field_ei(p)
				slice.set_pixel(x, y, Color(vy, vi, 0.0, 1.0))
		images[z] = slice
	var tex := ImageTexture3D.new()
	var err := tex.create(Image.FORMAT_RGF, N, N, N, false, images)
	_check("ImageTexture3D built", err == OK)
	return tex


func _field_ey(p: Vector3) -> float:
	var r2 := p.x * p.x + (PHI * p.y) * (PHI * p.y) + (p.z / PHI) * (p.z / PHI)
	var core := A_CORE * exp(-r2 / (SIGMA * SIGMA))
	var d1 := p - P1
	return core + EPS * exp(-(d1.dot(d1)) / (SIGMA_EPS * SIGMA_EPS))


func _field_ei(p: Vector3) -> float:
	var r2 := p.x * p.x + (PHI * p.y) * (PHI * p.y) + (p.z / PHI) * (p.z / PHI)
	var core := B_CORE * exp(-r2 / (SIGMA * SIGMA))
	var d2 := p - P2
	return core + EPS * exp(-(d2.dot(d2)) / (SIGMA_EPS * SIGMA_EPS))


func _setup_material() -> void:
	var mat := ShaderMaterial.new()
	var sh := load("res://compute/cassi_volumetric.gdshader") as Shader
	_check("raymarch shader loads", sh != null)
	mat.shader = sh

	# camera basis (forward/right/up orthonormal — identical in NumPy)
	var fwd := (CAM_TARGET - CAM_POS).normalized()
	var right := fwd.cross(CAM_UP).normalized()
	var up := right.cross(fwd).normalized()
	var tanhf := tan(deg_to_rad(FOV_DEG) * 0.5)

	mat.set_shader_parameter("u_box_half", E)
	mat.set_shader_parameter("u_cam_pos", CAM_POS)
	mat.set_shader_parameter("u_cam_forward", fwd)
	mat.set_shader_parameter("u_cam_right", right)
	mat.set_shader_parameter("u_cam_up", up)
	mat.set_shader_parameter("u_tan_half_fov", tanhf)
	mat.set_shader_parameter("u_img_size", Vector2(VIEWPORT))
	mat.set_shader_parameter("u_steps", STEPS)
	mat.set_shader_parameter("u_field", _build_field_texture())
	mat.set_shader_parameter("a_lo", A_LO)
	mat.set_shader_parameter("a_hi", A_HI)
	mat.set_shader_parameter("a_top", A_TOP)
	mat.set_shader_parameter("approach_on", APPROACH_ON)
	mat.set_shader_parameter("q_lo", Q_LO)
	mat.set_shader_parameter("q_hi", Q_HI)
	mat.set_shader_parameter("slope", SLOPE)
	mat.set_shader_parameter("s_abs", S_ABS)
	mat.set_shader_parameter("s_em", S_EM)
	mat.set_shader_parameter("s_fog", S_FOG)
	mat.set_shader_parameter("fog_color", Color(0.0, 0.0, 0.01, 1.0))
	mat.set_shader_parameter("GLOW_GAIN", GLOW)
	mat.set_shader_parameter("EPS_T", EPS_T)

	# fullscreen quad carrying the raymarch, child of the camera so it always
	# sits on the view axis and inherits the camera orientation. The shader
	# computes rays purely from the uniform camera geometry and is
	# cull_disabled, so only the quad's screen coverage matters — sized to
	# over-cover the 55° FOV at the near offset.
	var mesh := QuadMesh.new()
	mesh.size = Vector2(12.0, 12.0)     # > 2·1.5·tan(55°/2) ≈ 3.1 at 1.5 units
	var mi := MeshInstance3D.new()
	mi.name = "VolQuad"
	mi.mesh = mesh
	mi.material_override = mat
	mi.position = Vector3(0.0, 0.0, -2.0)   # 2 units in front of the camera
	_camera.add_child(mi)


func _grab_and_dump() -> void:
	await RenderingServer.frame_post_draw
	var img := _viewport.get_texture().get_image()
	var w := img.get_width()
	var h := img.get_height()
	_check("viewport image captured (%dx%d)" % [w, h], w == VIEWPORT.x and h == VIEWPORT.y)

	var ok := img.save_png("res://_diag/volumetric_frame.png")
	_check("PNG frame written to res://_diag/volumetric_frame.png", ok == OK)

	# raw pixels: prefer RGBAF (16 B/px); a SubViewport typically returns an
	# 8-bit display image (RGB8 = 3 B/px or RGBA8 = 4 B/px) — handle both.
	var wbytes := img.get_data()
	var bpc := 0
	if wbytes.size() == w * h * 16:
		bpc = 16
	elif wbytes.size() == w * h * 4:
		bpc = 4
	elif wbytes.size() == w * h * 3:
		bpc = 3
	_check("viewport image is RGBAF/RGBA8/RGB8 (%d B/px)" % bpc, bpc > 0,
		"got %d bytes" % wbytes.size())
	if bpc == 16:
		var rr := PackedFloat32Array()
		rr.resize(w * h * 4)
		for i in range(w * h):
			var off := i * 16
			for c in range(4):
				rr[i * 4 + c] = wbytes.decode_float(off + c * 4)
		_dump(rr, w, h)
	else:
		var rr8 := PackedFloat32Array()
		rr8.resize(w * h * 4)
		for i in range(w * h):
			rr8[i * 4 + 0] = float(wbytes[i * bpc + 0]) / 255.0
			rr8[i * 4 + 1] = float(wbytes[i * bpc + 1]) / 255.0
			rr8[i * 4 + 2] = float(wbytes[i * bpc + 2]) / 255.0
			rr8[i * 4 + 3] = 1.0
		_dump(rr8, w, h)


func _dump(rr: PackedFloat32Array, w: int, h: int) -> void:
	# φ-gate pixel = the pixel whose ray TANGENTLY grazes the r_gate sphere
	# (impact parameter = r_gate) on the horizontal through the origin
	# projection — where the pink shell shows without the white-core dilution.
	var r_gate: float = _phi_gate_radius()
	var gp := _tangent_gate_pixel(r_gate)
	var gj := gp.x
	var gi := gp.y
	var gpx := rr[(gi * w + gj) * 4]
	var gpy := rr[(gi * w + gj) * 4 + 1]
	var gpb := rr[(gi * w + gj) * 4 + 2]

	# RGBAF bytes for the verifier (decode in python step)
	var flat := PackedByteArray()
	flat.resize(w * h * 16)
	for i in range(w * h):
		var off := i * 16
		for c in range(4):
			flat.encode_float(off + c * 4, rr[i * 4 + c])

	var d := {
		"viewport": [w, h],
		"N": N, "E": [E.x, E.y, E.z],
		"phi": PHI,
		"sigma": SIGMA, "A_core": A_CORE, "B_core": B_CORE,
		"eps": EPS, "sigma_eps": SIGMA_EPS,
		"P1": [P1.x, P1.y, P1.z], "P2": [P2.x, P2.y, P2.z],
		"a_lo": A_LO, "a_hi": A_HI, "a_top": A_TOP, "approach_on": APPROACH_ON,
		"q_lo": Q_LO, "q_hi": Q_HI, "slope": SLOPE,
		"s_abs": S_ABS, "s_em": S_EM, "s_fog": S_FOG,
		"glow": GLOW, "eps_t": EPS_T, "steps": STEPS,
		"cam_pos": [CAM_POS.x, CAM_POS.y, CAM_POS.z],
		"cam_target": [CAM_TARGET.x, CAM_TARGET.y, CAM_TARGET.z],
		"cam_up": [CAM_UP.x, CAM_UP.y, CAM_UP.z],
		"fov_deg": FOV_DEG,
		"gate_radius": r_gate,
		"gate_pixel": [gj, gi],
		"gate_rgb": [gpx, gpy, gpb],
		"pixels_b64": Marshalls.raw_to_base64(flat),
	}
	var f := FileAccess.open("res://_diag/volumetric_pixels.json", FileAccess.WRITE)
	_check("RGBAF JSON written to res://_diag/volumetric_pixels.json", f != null)
	if f:
		f.store_string(JSON.stringify(d))
		f.close()
	print("[VerifyVolumetric] φ-gate pixel=(%d,%d) rgb=(%.3f %.3f %.3f)" % [gj, gi, gpx, gpy, gpb])


## Analytic radius where q(r) = q_gate (the pink shell at GATE_PA): design
## §5. With a_top = 0.93 (pink at the white point) the palette emission at the
## gate has hue 0.8 + (0.93−0.8)·GATE_PA = 0.9235 — in the pink band [0.90,0.97]
## — at lightness 0.975; the accumulated pixel hue is 0.90-0.91 because the
## tangent ray (see _tangent_gate_pixel) never enters the achromatic white core.
func _phi_gate_radius() -> float:
	var q0 := A_CORE * A_CORE + B_CORE * B_CORE        # q(0) = 0.5 = a_hi
	var q_gate := A_LO + GATE_PA * (A_HI - A_LO)
	var r2_gate := -0.5 * SIGMA * SIGMA * log(q_gate / q0)
	return sqrt(r2_gate)


## The φ-gate pixel (col, row): the pixel on the horizontal through the origin
## projection whose ray's impact parameter to the origin is closest to r_gate —
## a ray TANGENT to the pink shell. Such a ray samples r ≥ r_gate only, so its
## accumulated emission is the pink shell without the white-core dilution. The
## formula is mirrored exactly in volumetric_verify.py (tangent_gate_pixel).
func _tangent_gate_pixel(r_gate: float) -> Vector2i:
	var fwd := (CAM_TARGET - CAM_POS).normalized()
	var right := fwd.cross(CAM_UP).normalized()
	var up := right.cross(fwd).normalized()
	var tanhf := tan(deg_to_rad(FOV_DEG) * 0.5)
	var aspect := float(VIEWPORT.x) / float(VIEWPORT.y)
	var w := VIEWPORT.x

	# origin projection (row py)
	var d := -CAM_POS
	var zc := d.dot(fwd)
	var ndc_y := d.dot(up) / (zc * tanhf)
	var py := int(round((1.0 - (ndc_y * 0.5 + 0.5)) * float(VIEWPORT.y - 1)))
	py = clampi(py, 0, VIEWPORT.y - 1)

	# on row py, find the col whose ray impact parameter ~ r_gate
	var best_b := 1e30
	var best_j := 0
	for j in range(w):
		var ndc_x := (float(j) / float(w - 1)) * 2.0 - 1.0
		var rdn := fwd + right * (ndc_x * tanhf * aspect) + up * (ndc_y * tanhf)
		rdn = rdn.normalized()
		var rod := CAM_POS.dot(rdn)
		var b2 := CAM_POS.dot(CAM_POS) - rod * rod
		var b := sqrt(maxf(b2, 0.0))
		if absf(b - r_gate) < absf(best_b - r_gate):
			best_b = b
			best_j = j
	return Vector2i(best_j, py)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyVolumetric] checks=%d failures=%d" % [_checks, _failures])
	if _failures == 0:
		print("[VerifyVolumetric] RESULT: PASS — frame dumped for volumetric_verify.py")
	else:
		print("[VerifyVolumetric] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
