"""Independent verifier for concurrent temporal/evidence batch receipts."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassifi.temporal-evidence-action-batch.v1"
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "case_elapsed_seconds", "completion_index", "completion_order", "worker_id", "content_digest", "receipt_digest", "self_check"})


def canonical(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(v: Any) -> Any:
    if isinstance(v, Mapping):
        return {str(k): strip_timing(x) for k, x in v.items() if str(k) not in TIMING_KEYS}
    if isinstance(v, list):
        return [strip_timing(x) for x in v]
    return v


def digest(r: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(strip_timing(r)).encode()).hexdigest()


def chosen(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    x = row.get("selection", {}).get("selected")
    return x if isinstance(x, Mapping) else None


def transitions_ok(row: Mapping[str, Any]) -> bool:
    ts = row.get("transitions", [])
    if not isinstance(ts, list):
        return False
    return all(isinstance(t, Mapping) and isinstance(t.get("receipt"), Mapping) and t["receipt"].get("action") == t.get("action") and t["receipt"].get("observation") == t.get("observation") and t.get("before_state_sha256") != t.get("after_state_sha256") for t in ts)


def candidate_ok(row: Mapping[str, Any]) -> bool:
    s = row.get("selection", {})
    cs = s.get("candidates", [])
    c = chosen(row)
    return isinstance(cs, list) and s.get("candidate_count") == len(cs) and isinstance(c, Mapping) and any(isinstance(x, Mapping) and x.get("candidate_sha256") == c.get("candidate_sha256") and x.get("action") == c.get("action") and x.get("skill_id") == c.get("skill_id") for x in cs)


def source_bytes(source: Mapping[str, Any]) -> bytes | None:
    encoded = source.get("content_base64")
    if not isinstance(encoded, str):
        return None
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        return None


def source_steps(source: Mapping[str, Any]) -> Any:
    raw = source_bytes(source)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value.get("steps") if isinstance(value, Mapping) else None


def held_out_source_check(row: Mapping[str, Any]) -> dict[str, bool]:
    setup = row.get("setup", {})
    held = setup.get("held_out_source") if isinstance(setup, Mapping) else None
    learning = setup.get("learning", []) if isinstance(setup, Mapping) else []
    if not isinstance(held, Mapping) or not isinstance(learning, list) or not learning:
        return {"held_out_source_digest_absent_from_training": False, "held_out_source_not_replayed": False}
    held_raw = source_bytes(held)
    train_sources = [item.get("source") for item in learning if isinstance(item, Mapping) and isinstance(item.get("source"), Mapping)]
    train_raw = [source_bytes(source) for source in train_sources]
    held_digest = None if held_raw is None else hashlib.sha256(held_raw).hexdigest()
    train_digests = [hashlib.sha256(raw).hexdigest() for raw in train_raw if raw is not None]
    absent = held_digest is not None and held_digest not in train_digests
    held_steps = source_steps(held)
    not_replayed = held_steps is not None and all(source_steps(source) != held_steps for source in train_sources)
    return {"held_out_source_digest_absent_from_training": absent, "held_out_source_not_replayed": not_replayed}


def predicates(r: Mapping[str, Any]) -> dict[str, bool]:
    rows = r.get("rows")
    if not isinstance(rows, list) or len(rows) < 8:
        return {"shape": False}
    by = {x.get("name"): x for x in rows if isinstance(x, Mapping)}
    required = {"continuity-baseline", "continuity-baseline-reversed", "three-candidate", "multi-step-consequence", "unsupported-held-out-composition", "control-no-workspace", "control-insufficient-margin", "control-forbidden-operation", "control-infeasible-operation", "control-wrong-consequence", "control-order-permutation"}
    order = [x.get("name") for x in rows]
    if len(by) != len(rows) or not required.issubset(by) or r.get("parallelism", {}).get("canonical_case_order") != order or order != sorted(order):
        return {"shape": False}
    def s(n: str) -> Mapping[str, Any]:
        return by[n].get("selection", {})
    base = by["continuity-baseline"]
    no = by["control-no-workspace"]
    margin = by["control-insufficient-margin"]
    forb = by["control-forbidden-operation"]
    infeas = by["control-infeasible-operation"]
    wrong = by["control-wrong-consequence"]
    multi = by["multi-step-consequence"]
    unsupported = by["unsupported-held-out-composition"]
    perm = by["control-order-permutation"]
    source_checks = held_out_source_check(unsupported)
    supported = s("continuity-baseline").get("status") == "selected" and s("continuity-baseline").get("reason") in {"resonant-compatibility", "categorical-singleton"} and float(s("continuity-baseline").get("selection_margin", 0)) > float(base.get("minimum_margin", 0)) and candidate_ok(base) and base.get("field_setup", {}).get("available") is True and base.get("read_only") is True and base.get("state_unchanged") is True
    abstain = all(s(n).get("status") == "unresolved" and chosen(by[n]) is None and transitions_ok(by[n]) for n in ("control-no-workspace", "control-insufficient-margin", "control-forbidden-operation", "control-infeasible-operation"))
    no_ok = s("control-no-workspace").get("reason") == "resonant-workspace-unavailable" and no.get("field_setup", {}).get("available") is False
    margin_ok = s("control-insufficient-margin").get("reason") == "insufficient-resonant-margin" and float(margin.get("minimum_margin", 0)) > 1e-12
    forb_ok = all(not bool(x.get("authorized")) for x in forb.get("operations", []))
    infeas_ok = all(not bool(x.get("feasible")) for x in infeas.get("operations", []))
    wd = wrong.get("consequence", {})
    wrong_ok = isinstance(wd, Mapping) and wd.get("expected_goal") != wd.get("observed_goal") and len(wrong.get("transitions", [])) >= 1 and transitions_ok(wrong)
    md = multi.get("consequence", {})
    multi_ok = isinstance(md, Mapping) and md.get("expected_goal") == md.get("observed_goal") and md.get("position") == "done" and len(multi.get("transitions", [])) >= 2 and transitions_ok(multi)
    unsupported_ok = source_checks["held_out_source_digest_absent_from_training"] and source_checks["held_out_source_not_replayed"] and s("unsupported-held-out-composition").get("status") == "unresolved" and not chosen(unsupported) and unsupported.get("transitions") == [] and unsupported.get("expected_observed", {}).get("expected") == "unsupported" and unsupported.get("expected_observed", {}).get("observed") == "unsupported" and unsupported.get("expected_observed", {}).get("match") is True
    order_ok = (chosen(base) or {}).get("action") == (chosen(perm) or {}).get("action") and (chosen(base) or {}).get("skill_id") == (chosen(perm) or {}).get("skill_id")
    summary = r.get("summary", {})
    agg = summary == {"case_count": len(rows), "selected_case_count": sum(s(x.get("name")).get("status") == "selected" for x in rows), "multi_step_case_count": sum(x.get("case_family") == "multi-step" for x in rows), "control_case_count": sum(x.get("case_family") in {"no-workspace-lesion", "insufficient-margin", "forbidden-operation", "infeasible-operation", "wrong-consequence"} for x in rows), "unsupported_case_count": sum(x.get("case_family") == "unsupported-held-out-composition" for x in rows), "field_available_case_count": sum(bool(x.get("field_setup", {}).get("available")) for x in rows), "read_only_case_count": sum(bool(x.get("read_only") and x.get("state_unchanged")) for x in rows), "canonical_case_order": order}
    p = r.get("parallelism", {})
    conc = p.get("case_count") == len(rows) and isinstance(p.get("requested_worker_count"), int) and isinstance(p.get("used_worker_count"), int) and p["requested_worker_count"] >= p["used_worker_count"] >= 2 and p["used_worker_count"] <= len(rows) and isinstance(p.get("completion_order"), list) and sorted(p["completion_order"]) == order
    return {"shape": True, "field_supported_selection": supported, "three_candidate_case": s("three-candidate").get("candidate_count", 0) >= 3, "multi_step_consequence": multi_ok, "held_out_source_digest_absent_from_training": source_checks["held_out_source_digest_absent_from_training"], "held_out_composition_unsupported": unsupported_ok, "no_workspace_abstains": no_ok and abstain, "insufficient_margin_abstains": margin_ok and abstain, "forbidden_operation_abstains": forb_ok and abstain, "infeasible_operation_abstains": infeas_ok and abstain, "wrong_action_consequence_fails": wrong_ok, "order_permutation_invariant": order_ok, "aggregates_rederived": agg, "concurrency_metadata": conc}


def verify(r: Mapping[str, Any]) -> dict[str, Any]:
    actual = digest(r)
    c = predicates(r)
    c["schema"] = r.get("schema") == SCHEMA
    c["digest"] = bool(r.get("content_digest")) and r.get("content_digest") == actual and r.get("receipt_digest") == actual
    c["status"] = r.get("status") == "MEASURED"
    m = copy.deepcopy(r)
    br = next((x for x in m.get("rows", []) if x.get("name") == "continuity-baseline"), {})
    br.get("selection", {}).get("selected", {})["action"] = "mutated-action"
    c["selected_action_anchor_fires"] = not predicates(m).get("field_supported_selection", False)
    m = copy.deepcopy(r)
    next((x for x in m.get("rows", []) if x.get("name") == "multi-step-consequence"), {}).setdefault("consequence", {})["expected_goal"] = "wrong-goal"
    c["expected_goal_anchor_fires"] = not predicates(m).get("multi_step_consequence", False)
    m = copy.deepcopy(r)
    m.setdefault("parallelism", {})["case_count"] = int(m.get("parallelism", {}).get("case_count", 0)) + 1
    c["case_count_anchor_fires"] = not predicates(m).get("concurrency_metadata", False)
    m = copy.deepcopy(r)
    m.setdefault("parallelism", {})["used_worker_count"] = 1
    c["concurrency_anchor_fires"] = not predicates(m).get("concurrency_metadata", False)
    m = copy.deepcopy(r)
    next((x for x in m.get("rows", []) if x.get("name") == "control-forbidden-operation"), {}).get("selection", {})["status"] = "selected"
    c["control_anchor_fires"] = not predicates(m).get("forbidden_operation_abstains", False)
    m = copy.deepcopy(r)
    unsupported_row = next((x for x in m.get("rows", []) if x.get("name") == "unsupported-held-out-composition"), {})
    held = unsupported_row.get("setup", {}).get("held_out_source", {})
    train = unsupported_row.get("setup", {}).get("learning", [{}])[0].get("source", {})
    if isinstance(held, dict) and isinstance(train, dict) and "content_base64" in train:
        held["content_base64"] = train["content_base64"]
    c["held_out_scope_anchor_fires"] = not predicates(m).get("held_out_composition_unsupported", False)
    c["evaluation_matches"] = all(r.get("evaluation", {}).get(k) is v for k, v in c.items() if k in r.get("evaluation", {}))
    c["verified"] = all(bool(v) for k, v in c.items() if k != "verified")
    return {"status": "verified" if c["verified"] else "failed", "content_digest": actual, "checks": c}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", type=Path, default=Path("_diag/temporal-evidence-action-batch/exploration.json"))
    a = p.parse_args()
    out = verify(json.loads(a.receipt.read_text(encoding="utf-8")))
    print(json.dumps(out, sort_keys=True))
    if out["status"] != "verified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
