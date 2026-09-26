extends SceneTree

const SEED_X := 0.25
const SEED_Y := -0.4
const SEED_Z := 0.6
const SEED_CY := 1.4562
const SEED_CI := 0.9
const SEED_SIGMA := 1.0
const SEED_STEPS := 1
const BRIDGE_PORT := 7599

var _root: Node
var _engine: Node


func _initialize() -> void:
	_root = Node.new()
	get_root().add_child(_root)
	_start()


func _start() -> void:
	_engine = load("res://scripts/cassi_mind_engine.gd").new()
	_engine.grid_n = 32
	_engine.auto_step = false
	_engine.serve_bridge = false
	_engine.bridge_port = BRIDGE_PORT
	_root.add_child(_engine)
	if _engine._rd == null or not _engine._pipe.is_valid():
		push_error("[CassiQwenSeededMind] engine initialization failed")
		quit(1)
		return
	_engine.deposit(SEED_X, SEED_Y, SEED_Z, SEED_CY, SEED_CI, SEED_SIGMA)
	_engine._flush_pending()
	_engine.step_n(SEED_STEPS)
	_engine.serve_bridge = true
	_engine._server = TCPServer.new()
	var listen_error: Error = _engine._server.listen(BRIDGE_PORT, "127.0.0.1")
	if listen_error != OK:
		push_error("[CassiQwenSeededMind] bridge listener failed: %d" % listen_error)
		quit(1)
		return
	var state: Dictionary = _engine.compute_state()
	print("[CassiQwenSeededMind] ready N=%d step=%d t=%.4f port=%d max_eps2=%.9f" % [
		_engine.grid_n, state["step"], state["t"], BRIDGE_PORT, state["max_eps2"],
	])
