extends Node
## ───────────────────────────────────────────────────────────────────────────
## verify_exclusive_scan — validates the on-GPU exclusive prefix-sum shader
## (compute/cassi_exclusive_scan.glsl, FIX B: the spatial-hash cell scan the
## particle-merge pass uses to avoid the host CPU scan). Builds the scan
## pipeline on a local RD, fills a random uint count buffer, runs the four
## scan passes (1 block-scan cc→cs, 2 block-scan L1 in place, 3 single level-2,
## 4 add_carries + ch=cs), reads cs back, and compares against a CPU reference
## exclusive scan. Verifies at two sizes: a small non-multiple (padding edge)
## and ~100k cells (multi-block two-level path).
##
## Windowed console exe (local RD needs a real GPU; NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <repo> \
##       res://scenes/verify_exclusive_scan.tscn
## ───────────────────────────────────────────────────────────────────────────

const SHADER := "res://compute/cassi_exclusive_scan.glsl"
const BLOCK := 256

var _rd: RenderingDevice = null
var _checks := 0
var _failures := 0
var _shader: RID
var _pipe: RID
var _us: RID
var _cc: RID; var _cs: RID; var _scr: RID; var _ch: RID
var _cc_buf: PackedInt32Array
var _n := 0
var _nb1a := 256
var _nb2 := 1


func _ready() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		print("[EXSCAN] FAIL: no local RD (run windowed)")
		get_tree().quit(1)
		return
	var sf = load(SHADER) as RDShaderFile
	_shader = _rd.shader_create_from_spirv(sf.get_spirv())
	if not _shader.is_valid():
		print("[EXSCAN] FAIL: scan shader did not build")
		get_tree().quit(1)
		return
	_pipe = _rd.compute_pipeline_create(_shader)
	_check("scan pipeline built on local RD", _pipe.is_valid())
	# Sizes: (name, element count)
	_run_size("S1 small (non-multiple)", 1000)
	_run_size("S2 two-level (100k, ~8.88M-path)", 100000)
	_run_size("S3 exact-256-multiple", 65536)
	print("[EXSCAN] RESULT: %s (checks=%d failures=%d)" % ["PASS" if _failures == 0 else "FAIL", _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


func _run_size(label: String, n: int) -> void:
	_n = n
	var E := _n
	var nb1 = (E + BLOCK - 1) / BLOCK
	# mirror the merge-host computation of the scratch regions
	_nb1a = ((nb1 + BLOCK - 1) / BLOCK) * BLOCK
	_nb2 = (nb1 + BLOCK - 1) / BLOCK
	# ── build buffers ──
	var cc := PackedInt32Array(); cc.resize(n)
	var rng := RandomNumberGenerator.new(); rng.seed = 12345 + n
	var tot = 0
	for i in range(n):
		# sparse-ish counts (most 0, some small) like the real cell distribution
		cc[i] = (rng.randi() % 40) if (rng.randf() < 0.5) else 0
		tot += cc[i]
	_cc = _rd.storage_buffer_create(maxi(n, 1) * 4)
	_rd.buffer_update(_cc, 0, n * 4, cc.to_byte_array())
	_cs = _rd.storage_buffer_create(maxi(n, 1) * 4)
	_scr = _rd.storage_buffer_create((_nb1a + _nb2 + 8) * 4)
	_ch = _rd.storage_buffer_create(maxi(n, 1) * 4)
	# cpu reference exclusive scan
	var cpu := PackedInt32Array(); cpu.resize(n)
	var run := 0
	for i in range(n):
		cpu[i] = run
		run += cc[i]
	print("\n[EXSCAN] %s: n=%d  cc-sum=%d" % [label, n, tot])
	_scan_all()
	var got := _read_cs()
	# verify vs reference
	var ok := true
	var first_bad := -1
	for i in range(n):
		if got[i] != cpu[i]:
			ok = false; first_bad = i; break
	_check("%s exclusive-scan matches CPU reference (n=%d)" % [label, n],
		ok, "first_mismatch=%d got=%d cpu=%d" % [first_bad, got[first_bad] if first_bad >= 0 else -1, cpu[first_bad] if first_bad >= 0 else -1])
	if _us.is_valid(): _rd.free_rid(_us)
	_us = RID()
	_rd.free_rid(_cc); _rd.free_rid(_cs); _rd.free_rid(_scr); _rd.free_rid(_ch)


func _scan_all() -> void:
	var E := _n
	var nb1 = (E + BLOCK - 1) / BLOCK
	# pass 1: cc -> cs (size E)
	_dispatch(1, E, nb1)
	# pass 2: scan scr(L1) in place (size nb1)
	_dispatch(2, nb1, _nb2)
	# pass 3: single workgroup scan of L2 (size nb2 <= 256)
	_dispatch(3, _nb2, 1)
	# pass 4: add carries + ch=cs (size E)
	_dispatch(4, E, nb1)


func _dispatch(pm: int, size: int, groups: int) -> void:
	var pc := PackedFloat32Array([float(size), float(pm), float(_nb1a), 0.0]).to_byte_array()
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	if not _us.is_valid():
		_us = _rd.uniform_set_create([
			_u(15, _cc), _u(16, _cs), _u(17, _scr), _u(18, _ch),
		], _shader, 0)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	_rd.compute_list_set_push_constant(cl, pc, pc.size())
	_rd.compute_list_dispatch(cl, maxi(groups, 1), 1, 1)
	_rd.compute_list_end()
	# submit each pass separately so the ordering is explicit (local RD)
	_rd.submit(); _rd.sync()


func _u(b: int, rid: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = b
	u.add_id(rid)
	return u


func _read_cs() -> PackedInt32Array:
	return _rd.buffer_get_data(_cs, 0, _n * 4).to_int32_array()


func _check(name: String, ok2: bool, detail: String = "") -> void:
	_checks += 1
	if not ok2: _failures += 1
	print("[%s] %s%s" % ["PASS" if ok2 else "FAIL", name, ("  " + detail) if detail != "" else ""])
