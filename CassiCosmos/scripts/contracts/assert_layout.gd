extends SceneTree
## Build-time layout assertion (the contract class-killer, M0 commit 1).
##
## Standalone, --check-only-runnable (no project boot, no GPU):
##   <bench>/Godot_v4.7.1-stable_win64_console.exe --headless \
##       --script res://scripts/contracts/assert_layout.gd
##
## Reads, per covered shader, the GLSL `layout(push_constant)` block and the
## `layout(set = S, binding = B)` declarations with regexes and asserts them
## against scripts/contracts/layout.gd (the single source of truth): the PC
## float count, the per-set binding list, the "canonical layout" header line,
## and — for the host side — every `_x_pc_bytes = PackedByteArray();
## resize(N * 4)` allocation in cassi_sim.gd / cassi_physics_engine.gd /
## cassi_tree_worker.gd. This is the gate that would have caught the merge
## 64-vs-92-B PC mismatch (the stderr flood that broke particle_merge), the
## storage-vs-render periodic-wrap disagreement, and liveness drift.
##
## Exit 0 = every covered object matches the schema; 1 = any mismatch
## (printed per object).

const ROOT := "res://"
const SCHEMA := "res://scripts/contracts/layout.gd"
const HOST_SCRIPTS := [
	"res://scripts/cassi_sim.gd",
	"res://scripts/cassi_physics_engine.gd",
	"res://scripts/cassi_tree_worker.gd",
]

var _fail := 0

func _initialize() -> void:
	quit(run())


func run() -> int:
	var L: GDScript = load(SCHEMA)
	if L == null:
		printerr("[assert_layout] FATAL: cannot load %s" % SCHEMA)
		return 1
	for name in L.COVERED:
		_check_shader(L, name)
	_check_host(L)
	for s in L.COVERED:
		_check_header(L, s)
	print("[assert_layout] %s: %d mismatch(es)" % ["PASS" if _fail == 0 else "FAIL", _fail])
	return 1 if _fail > 0 else 0


## PC + binding check for one shader.
func _check_shader(L: GDScript, name: String) -> void:
	var p := "%scompute/%s.glsl" % [ROOT, name]
	var src := _read(p)
	if src.is_empty():
		_fail += 1
		printerr("[assert_layout] FAIL %s: cannot read %s" % [name, p])
		return
	var pc := RegEx.create_from_string(r'layout\(push_constant[^)]*\)\s*uniform\s+\w+\s*\{([^}]*)\}')
	var m := pc.search(src)
	var nf := 0
	if m:
		nf = RegEx.create_from_string(r'\bfloat\s+\w+').search_all(m.get_string(1)).size()
	if nf != int(L.PC[name]):
		_fail += 1
		printerr("[assert_layout] FAIL %s: PC %d floats (schema %d)" % [name, nf, int(L.PC[name])])
	var bind := RegEx.create_from_string(r'layout\(set = (\d+), binding = (\d+)')
	var got := {}
	for mm in bind.search_all(src):
		var s := int(mm.get_string(1))
		var b := int(mm.get_string(2))
		got[s] = got.get(s, []) + [b]
	var expected: Dictionary = L.BINDINGS[name]
	if got.size() != expected.size():
		_fail += 1
		printerr("[assert_layout] FAIL %s: set count %d (schema %d)" % [name, got.size(), expected.size()])
	for s in expected:
		var want: Array = (expected[s] as Array).duplicate()
		var have: Array = (got.get(s, []) as Array).duplicate()
		have.sort()
		want.sort()
		if have != want:
			_fail += 1
			printerr("[assert_layout] FAIL %s: set %d bindings %s (schema %s)" % [name, s, have, want])


## Host PackedByteArray allocation check against the schema.
func _check_host(L: GDScript) -> void:
	for hp in HOST_SCRIPTS:
		var src := _read(hp)
		if src.is_empty():
			_fail += 1
			printerr("[assert_layout] FAIL host: cannot read %s" % hp)
			continue
		# Float-count allocations: _x_pc_bytes = PackedByteArray(); resize(N * 4)
		var re_f := RegEx.create_from_string(r'(_\w+_pc_bytes)\s*=\s*PackedByteArray\(\);\s*\w+\.resize\((\d+)\s*\*\s*4\)')
		for mm in re_f.search_all(src):
			var vn := mm.get_string(1)
			var n := int(mm.get_string(2))
			if L.HOST_PC_FLOATS.has(vn) and n != int(L.HOST_PC_FLOATS[vn]):
				_fail += 1
				printerr("[assert_layout] FAIL host %s: %s resize %d floats (schema %d)" % [hp, vn, n, int(L.HOST_PC_FLOATS[vn])])
		# Byte-count allocations: _blend_pc = PackedByteArray(); resize(B)
		var re_b := RegEx.create_from_string(r'(_blend_pc)\s*=\s*PackedByteArray\(\);\s*\w+\.resize\((\d+)\)')
		for mm in re_b.search_all(src):
			var vn := mm.get_string(1)
			var b := int(mm.get_string(2))
			if L.HOST_PC_BYTES.has(vn) and b != int(L.HOST_PC_BYTES[vn]):
				_fail += 1
				printerr("[assert_layout] FAIL host %s: %s resize %d B (schema %d B)" % [hp, vn, b, int(L.HOST_PC_BYTES[vn])])


## The canonical-layout header line must be present in each covered shader.
func _check_header(L: GDScript, name: String) -> void:
	var p := "%scompute/%s.glsl" % [ROOT, name]
	var src := _read(p)
	if not src.contains("canonical layout: scripts/contracts/layout.gd"):
		_fail += 1
		printerr("[assert_layout] FAIL %s: missing 'canonical layout: scripts/contracts/layout.gd' header line" % name)


func _read(p: String) -> String:
	if not FileAccess.file_exists(p):
		return ""
	var f := FileAccess.open(p, FileAccess.READ)
	if f == null:
		return ""
	var s := f.get_as_text()
	f.close()
	return s
