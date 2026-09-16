"""The optional computer must execute and recover outside the source checkout."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_cassipi_runtime import build_runtime, verify_runtime


def test_packaged_computer_executes_learns_and_recovers(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    build_runtime(runtime)
    verify_runtime(runtime)
    program = r'''
import json
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from cassi_field_owner import FieldIntelligenceOwner
root = Path(sys.argv[2])
source = {"kind":"circuit","source":{"inputs":["x"],"gates":[],"assertions":[["x",1]],"relations":[],"clauses":[]}}
with FieldIntelligenceOwner(root) as owner:
    owner.operate_computer("configure", computer_id="main", action="configure", arguments={"profile":{"program_capacity":16,"stack_capacity":16,"max_steps":100}})
    owner.operate_computer("load", computer_id="main", action="load", arguments={"program":[[1,0,42,1,0],[0,0,0,0,0]]})
    owner.operate_computer("run", computer_id="main", action="advance", arguments={"steps":10})
    inspection = owner.state.computers[0].inspect()
    assert inspection["task"]["status"] == "halted"
    assert inspection["task"]["left"] == [42]
    before = inspection["policy_state_sha256"]
    solved = owner.operate_computer("learn", computer_id="main", action="solve", arguments={"source":source,"budget":300,"method":"conflict"})
    assert solved["receipt"]["status"] == "sat"
    assert solved["receipt"]["audit"]["checked"]
    assert owner.state.computers[0].inspect()["policy_state_sha256"] != before
    expected = owner.state.state_sha256
with FieldIntelligenceOwner(root) as owner:
    assert owner.state.state_sha256 == expected
    repeated = owner.operate_computer("learn", computer_id="main", action="solve", arguments={"source":source,"budget":300,"method":"conflict"})
    assert repeated["receipt"] == solved["receipt"]
    assert repeated["checkpoint_receipt"] == {**solved["checkpoint_receipt"], "replayed":True}
    assert owner.state.state_sha256 == expected
print(json.dumps({"halted":True,"learned":True,"recovered":True,"state_sha256":expected}))
'''
    result = subprocess.run(
        [sys.executable, "-I", "-c", program, str(runtime), str(tmp_path / "field")],
        cwd=tmp_path, capture_output=True, text=True, timeout=120, check=False,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["halted"] and value["learned"] and value["recovered"]
