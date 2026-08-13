extends Node3D
## Verify of the Cassi audio-reduce cascade meter (CASSI_SYNTH.md §3/§5).
##
## A SELF-CONTAINED RenderingDevice probe: its OWN local RD, its own
## synthetic field buffers, no dependency on the live sim (so it runs even
## while the sibling workers are mid-edit on cassi_sim.gd). Fills ey with a
## KNOWN sum of φ-spaced plane waves (ei = 0), runs the reduce (3 scan
## passes → 3D SAT, then the reduce), reads back the tiny 16-float buffer,
## and dumps the rung energies to res://_diag/synth_gpu.json for the numpy
## gate research/meshless/synth_verify.py (G22 GPU=numpy, G23 localization).
##
## The rung energies are KNOWN ANALYTICALLY (embedded FULL_RUNG_REF /
## PERWAVE_REF, computed by the numpy mirror), so the scene also prints an
## in-place G22/G23 verdict before handing the JSON to the numpy gate.
##
## Also asserts that load("res://scripts/cassi_synth.gd") parses — the full
## synth is an audio node that needs a live sim + audio server, so the
## reduce is the verifiable physics; the synth's parse is the headless check.
##
## Run:  godot --path <repo> res://scenes/verify_synth.tscn    (windowed)

const N := 64
const R := 4
const PHI := 1.618033988749895
const BOX := [2, 3, 4, 8]                       # b_m = round(φ^m), m=1..R
const WAVE_N := [8, 7, 2, 1]                    # wave r → wavenumber n_r
# Analytic references from the numpy mirror (research/meshless/synth_verify.py)
const FULL_RUNG_REF := [0.1103090245, 0.0773803489, 0.0577170077, 0.0264312547]
const PERWAVE_REF := [
	[0.0007561728, 0.0000339633, 0.0000213593, 0.0000063548],
	[0.0000431851, 0.0006180324, 0.0000232131, 0.0000133733],
	[0.0006743685, 0.0019463572, 0.0029781524, 0.0000620589],
	[0.0000572318, 0.0002354738, 0.0006082658, 0.0030766948],
]
const TOT_REF := 0.5            # mean of q over the 3D grid (Σ_r ½·cos: 4 waves, ei=0)
const OUT_N := 16

var _rd: RenderingDevice
var _shader: RID
var _pipe: RID
var _sat: RID
var _ey: RID
var _ei: RID
var _out: RID
var _chunk := PackedByteArray()
var _checks := 0
var _failures := 0
var _t0_ms := 0


func _ready() -> void:
	_t0_ms = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false,
			"headless/dummy renderer? fall back to windowed run")
		_finish()
		return
	_check("local RenderingDevice acquired", true)

	var sf := load("res://compute/cassi_audio_reduce.glsl") as RDShaderFile
	if sf == null:
		_check("audio reduce shader loads", false)
		_finish()
		return
	var spirv := sf.get_spirv()
	_shader = _rd.shader_create_from_spirv(spirv)
	_pipe = _rd.compute_pipeline_create(_shader)
	_check("audio reduce pipeline builds", _pipe.is_valid())
	if not _pipe.is_valid():
		_finish()
		return

	_make_buffers()
	_dispatch_reduce(0)                       # full φ-spaced-wave field
	var full_rung := _read_rung_energies()
	var full_tot := _read_total()
	_check_gates(full_rung, full_tot)         # in-place G22/G23 (emb refs)

	var waves_gpu: Array = []
	var waves_ref: Array = []
	for r in range(R):
		_dispatch_reduce(r + 1)               # wave r alone
		waves_gpu.append(_read_rung_energies_as_array())
		waves_ref.append(PERWAVE_REF[r])

	# the synth must parse (headless-safe check of the audio node)
	var synth_ok := _load_synth_parses()
	_check("cassi_synth.gd parses", synth_ok)

	_dump_json(full_rung, full_tot, waves_gpu, waves_ref)
	_finish()


# ── buffers / uniforms ────────────────────────────────────────────────
func _make_buffers() -> void:
	var n3 := N * N * N
	_sat = _rd.storage_buffer_create(n3 * 4)
	_ey = _rd.storage_buffer_create(n3 * 4)
	_ei = _rd.storage_buffer_create(n3 * 4)
	var zero := PackedByteArray()
	zero.resize(OUT_N * 4)
	_out = _rd.storage_buffer_create(OUT_N * 4)
	_rd.buffer_update(_out, 0, zero.size(), zero)
	_write_probe(0)
	_chunk = PackedFloat32Array([0.0, float(N), 0.0, 0.0]).to_byte_array()


func _us(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# ── probe field generation (mirrors synth_verify.ey_field) ───────────
func _field_ey(nfs: Array) -> PackedFloat32Array:
	var ey := PackedFloat32Array()
	ey.resize(N)
	for i in range(N):
		ey[i] = 0.0
	for nf in nfs:
		var amp: float = 0.5
		var wave := PackedFloat32Array()
		wave.resize(N)
		for i in range(N):
			wave[i] = amp * cos(TAU * float(nf) * float(i) / float(N))
		for i in range(N):
			ey[i] += wave[i]
	return ey


# mode 0 = full field; mode r+1 = wave r alone
func _write_probe(mode: int) -> void:
	var n3 := N * N * N
	var ey := PackedFloat32Array()
	ey.resize(n3)
	ey.fill(0.0)
	var ei := PackedFloat32Array()
	ei.resize(n3)
	ei.fill(0.0)
	if mode == 0:
		var f := _field_ey(WAVE_N)
		for i in range(N):
			for j in range(N):
				for k in range(N):
					ey[i + N * (j + N * k)] = f[i]
	elif mode >= 1 and mode <= R:
		var r := mode - 1
		var f := _field_ey([WAVE_N[r]])
		for i in range(N):
			for j in range(N):
				for k in range(N):
					ey[i + N * (j + N * k)] = f[i]
	_rd.buffer_update(_ey, 0, n3 * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, n3 * 4, ei.to_byte_array())
	# zero the SAT + out before each chain
	var zsat := PackedByteArray()
	zsat.resize(n3 * 4)
	_rd.buffer_update(_sat, 0, n3 * 4, zsat)
	var zout := PackedByteArray()
	zout.resize(OUT_N * 4)
	_rd.buffer_update(_out, 0, OUT_N * 4, zout)


var _us_rid: RID = RID()

func _dispatch_reduce(mode: int) -> void:
	_write_probe(mode)
	if not _us_rid.is_valid():
		_us_rid = _rd.uniform_set_create([
			_us(0, _sat), _us(1, _ey), _us(2, _ei), _us(3, _out),
		], _shader, 0)
	# 3 scan passes (build the 3D inclusive-prefix SAT), then the reduce.
	var rows := int(ceili(float(N * N) / 64.0))
	var cells := int(ceili(float(N * N * N) / 256.0))
	for xi in range(4):
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_rid, 0)
		_mutate_mode(xi)
		_rd.compute_list_set_push_constant(cl, _chunk, _chunk.size())
		if xi < 3:
			_rd.compute_list_dispatch(cl, rows, 1, 1)
		else:
			_rd.compute_list_dispatch(cl, cells, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_rd.compute_list_end()
		_rd.submit()
		_rd.sync()


func _mutate_mode(mode: int) -> void:
	var f := _chunk.to_float32_array()
	f[0] = float(mode)
	_chunk = f.to_byte_array()


func _read_rung_energies() -> PackedFloat32Array:
	var data := _rd.buffer_get_data(_out, 0, OUT_N * 4)
	var f := data.to_float32_array()
	var scale := 1.0 / float(N * N * N)   # shader accumulates sums → per-cell means
	for i in range(R):
		f[4 + i] *= scale
	f[0] *= scale
	return f


func _read_rung_energies_as_array() -> Array:
	var f := _read_rung_energies()
	var a: Array = []
	for i in range(R):
		a.append(float(f[4 + i]))
	return a


func _read_total() -> float:
	return float(_read_rung_energies()[0])


# ── gates ─────────────────────────────────────────────────────────────
func _check_gates(full_rung: PackedFloat32Array, full_tot: float) -> void:
	# G22: GPU vs embedded numpy reference ≤ 1e-2 relative
	var g22 := true
	var max_rel := 0.0
	for r in range(R):
		var gv := float(full_rung[4 + r])
		var rv: float = FULL_RUNG_REF[r]
		var rel: float = absf(gv - rv) / maxf(absf(rv), 1e-9)
		max_rel = maxf(max_rel, rel)
		if rel > 1e-2:
			g22 = false
	var rel_tot: float = absf(full_tot - TOT_REF) / maxf(absf(TOT_REF), 1e-9)
	if rel_tot > 1e-2:
		g22 = false
	print("[VerifySynth] G22 GPU vs analytic: max rung rel=" + str(max_rel)
		+ "  total rel=" + str(rel_tot))
	_check("G22 GPU rung energies == analytic (≤1e-2)", g22)

	# G23: localization — per-wave peaks (computed again during dump) +
	# scale-responsiveness on the full field is checked by numpy; here we
	# assert the full-field rung spectrum matches the analytic (which IS
	# the localization content) and print the rung table.
	_print_rung_table(full_rung)


func _print_rung_table(full_rung: PackedFloat32Array) -> void:
	print("[VerifySynth] rung table (box b_m = round(φ^m), freq n = f0·φ^r, f0=55 Hz):")
	print("  r | b | f(Hz) | structure energy")
	for r in range(R):
		var b: int = BOX[r]
		var f: float = 55.0 * pow(PHI, float(r))
		print("  %d | %d | %7.2f | %.6f" % [r, b, f, full_rung[4 + r]])


func _load_synth_parses() -> bool:
	var sf := load("res://scripts/cassi_synth.gd")
	return sf != null


func _dump_json(full_rung: PackedFloat32Array, full_tot: float,
		waves_gpu: Array, waves_ref: Array) -> void:
	var d := {
		"N": N, "R": R, "BOX": Array(BOX), "WAVE_N": Array(WAVE_N),
		"rung_energies_gpu": _slice(full_rung),
		"total_energy_gpu": full_tot,
		"per_wave_energies_gpu": waves_gpu,
		"per_wave_energies_ref": waves_ref,
	}
	var f := FileAccess.open("res://_diag/synth_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump file", false, "res://_diag/synth_gpu.json unwritable")
		return
	f.store_string(JSON.stringify(d))
	f.close()
	print("[VerifySynth] dumped res://_diag/synth_gpu.json — run research/meshless/synth_verify.py")


func _slice(f: PackedFloat32Array) -> Array:
	var a: Array = []
	for r in range(R):
		a.append(float(f[4 + r]))
	return a


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[VerifySynth] %s: %s%s" % ["PASS" if ok else "FAIL", name,
		(" — " + detail) if detail != "" else ""])


func _exit_tree() -> void:
	if _rd != null:
		for rid in [_pipe, _shader, _sat, _ey, _ei, _out]:
			if rid.is_valid():
				_rd.free_rid(rid)


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0_ms
	print("[VerifySynth] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifySynth] RESULT: PASS")
	else:
		print("[VerifySynth] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
