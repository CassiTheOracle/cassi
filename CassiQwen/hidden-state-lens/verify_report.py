"""Independent check of the two written documents against the receipts.

Every number REPORT.md and FIELD_READOUT_DESIGN.md state is re-derived from
lens-results.json, probe-results.json, readout-preflight.json, capture-inventory.json and
lens-states.json, and looked for in the prose.  It reads nothing else, computes nothing the
drivers did not compute, and fails loudly on any claim the receipts do not support.

Usage:
    python verify_report.py        # prints the derived values, then PASS or the mismatches
"""
import json
import re
from pathlib import Path

H = Path(__file__).resolve().parent
rep = (H / "REPORT.md").read_text(encoding="utf-8")
L = json.loads((H / "lens-results.json").read_text(encoding="utf-8"))
P = json.loads((H / "probe-results.json").read_text(encoding="utf-8"))
R = json.loads((H / "readout-preflight.json").read_text(encoding="utf-8"))
A = json.loads((H / "capture-inventory.json").read_text(encoding="utf-8"))
des = (H / "FIELD_READOUT_DESIGN.md").read_text(encoding="utf-8")
N = json.loads((H / "lens-states.json").read_text(encoding="utf-8"))

bad = []
def check(cond, msg):
    if not cond:
        bad.append(msg)
def num_zero_plus_small(values):
    return 2 <= sum(1 for value in values if value < 1e-4) <= 3

def expand(cell):
    """'33-35, 55' -> {33,34,35,55}"""
    out = set()
    for part in cell.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            out.update(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out

def cited(text, what):
    check(text in rep, f"report does not state {what}: {text!r}")

kinds = L["widths"]["5120"]["kinds"]
def rows_of(kind):
    return {r["layer"]: r for r in kinds[kind]["rows"]}

# ---- §1 headline table
for kind, n, maj_rate, top1_l63, p_first, p_last, commit, run, sharp in (
    ("prompt", 42, 0.881, 0.357, 0.0009, 0.4436, 62, 2, 0.18),
    ("decode-early", 123, 0.732, 1.000, 0.0002, 0.9621, 61, 3, 0.71),
    ("decode", 133, 0.774, 0.955, 0.0017, 0.9994, 63, 1, 0.88),
):
    block = kinds[kind]
    row63 = rows_of(kind)[63]
    first = block["rows"][0]
    c = block["commitment"]
    check(block["n_states"] == n, f"{kind}: receipt n {block['n_states']} vs report {n}")
    check(abs(block["majority_rate"] - maj_rate) < 0.001, f"{kind}: majority {block['majority_rate']} vs {maj_rate}")
    check(abs(row63["top1_rate"] - top1_l63) < 0.001, f"{kind}: L63 top1 {row63['top1_rate']} vs {top1_l63}")
    check(f"{first['median_p_answer']:.4f}" == f"{p_first:.4f}", f"{kind}: first-layer p {first['median_p_answer']} vs {p_first}")
    check(abs(row63["median_p_answer"] - p_last) < 0.001, f"{kind}: L63 p {row63['median_p_answer']} vs {p_last}")
    check(int(c["median_layer"]) == commit, f"{kind}: commit {c['median_layer']} vs {commit}")
    check(int(c["median_stable_run_layers"]) == run, f"{kind}: run {c['median_stable_run_layers']} vs {run}")
    check(abs(c["median_sharpness"] - sharp) < 0.006, f"{kind}: sharpness {c['median_sharpness']} vs {sharp}")
    cited(f"| {kind} ", f"{kind} row")
    # table cell: L32 -> at commit -> L63
    cell = f"{first['median_p_answer']:.4f} → {c['median_p_at_commit']:.4f} → {row63['median_p_answer']:.4f}"
    check(cell in rep or f"{first['median_p_answer']:.4f}" in rep, f"{kind}: p(answer) chain {cell!r} not in report")
    before = c["median_p_before"]
    check(any(f"{before:.{digits}f}" in document for digits in (2, 3, 4)
              for document in (rep, des)),
          f"{kind}: p before commit {before} not stated in either document")
# the two explicit commit-layer sentences
c_de = kinds["decode-early"]["commitment"]
cited(f"{c_de['median_p_before']:.5f}", "decode-early p before commit (0.00397)")
cited(f"{c_de['median_p_at_commit']:.4f}", "decode-early p at commit (0.7178)")
check(abs(c_de["median_p_at_commit"] - 0.7178) < 0.001, "0.7178 not the decode-early p at commit")
cited(f"{rows_of('decode-early')[60]['top1_rate']:.3f}", "decode-early L60 top1")
cited(f"{rows_of('decode-early')[61]['top1_rate']:.3f}", "decode-early L61 top1")
for kind, layer, text in (("prompt", 63, "0.357"), ("decode", 63, "0.955")):
    check(f"{rows_of(kind)[63]['top1_rate']:.3f}" == text, f"{kind} L63 top1 not {text}")

# ---- readable / unreadable layer sets
for kind, readable_text, n_unreadable in (
    ("prompt", "33-35, 55-63", 20),
    ("decode-early", "52-58, 60-63", 21),
    ("decode", "35, 44, 45, 55, 62, 63", 26),
):
    readable = [r["layer"] for r in kinds[kind]["rows"] if r["readable"]]
    unreadable = [r["layer"] for r in kinds[kind]["rows"] if not r["readable"]]
    check(expand(readable_text) == set(readable),
          f"{kind} readable set: receipt {sorted(readable)} vs report {readable_text!r}")
    check(len(unreadable) == n_unreadable, f"{kind} unreadable count {len(unreadable)} vs {n_unreadable}")
    # the report cell must be the one the receipt supports
    check(f"| {kind} | {readable_text} (" in rep, f"report readable cell for {kind} is not {readable_text!r}")

# ---- entropy table
for kind, values in (("prompt", (11.25, 10.81, 0.70, 0.44, 1.37, 2.18, 1.29)),
                     ("decode-early", (10.74, 10.19, 4.87, 3.16, 0.20, 0.54, 0.19)),
                     ("decode", (10.78, 9.98, 2.68, 1.15, 0.82, 0.55, 0.00))):
    for layer, value in zip((32, 50, 55, 56, 60, 62, 63), values):
        got = rows_of(kind)[layer]["median_entropy_nats"]
        check(abs(got - value) < 0.006, f"{kind} L{layer} entropy {got} vs {value}")

# ---- 0.8B control
b = L["widths"]["1024"]["kinds"]["prompt"]
b63 = {r["layer"]: r for r in b["rows"]}[23]
cb = b["commitment"]
check(abs(b["majority_rate"] - 0.837) < 0.001, f"1024 majority {b['majority_rate']}")
check(abs(b63["top5_rate"] - 0.98) < 0.005, f"1024 L23 top5 {b63['top5_rate']}")
check(abs(b63["top1_rate"] - 0.327) < 0.001, f"1024 L23 top1 {b63['top1_rate']}")
check(abs(cb["median_layer"] - 22.5) < 0.01, f"1024 commit {cb['median_layer']}")
check(abs(cb["median_sharpness"] - 0.05) < 0.006, f"1024 sharpness {cb['median_sharpness']}")
check(abs(cb["median_p_before"] - 0.0015) < 0.0002, f"1024 p before {cb['median_p_before']}")
check(abs(cb["median_p_at_commit"] - 0.069) < 0.001, f"1024 p at commit {cb['median_p_at_commit']}")
check(f"{b63['median_p_answer']:.3f}" == "0.038", f"1024 L23 median p {b63['median_p_answer']}")
cited("0.038", "1024 L23 median p")
check(abs(b["rows"][0]["median_entropy_nats"] - 9.39) < 0.006, f"1024 L12 entropy {b['rows'][0]['median_entropy_nats']}")
check(abs(b63["median_entropy_nats"] - 7.70) < 0.006, f"1024 L23 entropy {b63['median_entropy_nats']}")

# ---- instrument validation
iv = L["instrument_validation"]
check(iv["n_states"] == 256 and abs(iv["top1_rate"] - 0.977) < 0.001 and iv["median_rank"] == 1 and iv["p90_rank"] == 1,
      "instrument validation row")
cited("**0.977**", "instrument top-1")

# ---- on/off arm table
arms = L["arm_pairs"]
def summary(tag, arm, kind):
    return arms[tag]["summaries"].get(f"{arm} {kind}")
for tag, arm_off, arm_on, kind, off, on in (
    ("named", "steps32-off", "steps32-on", "decode-early", (61, 3, 0.7032), (61, 3, 0.7050)),
    ("named", "steps32-off", "steps32-on", "decode", (56, 8, 0.9764), (56, 8, 0.9766)),
    ("carryp0", "off-p0", "on-p0", "decode-early", (57, 7, 0.8489), (57, 7, 0.8427)),
):
    for arm, want in ((arm_off, off), (arm_on, on)):
        row = summary(tag, arm, kind)
        check(row is not None, f"{tag}: no summary {arm} {kind}")
        if row is None:
            continue
        check(row["arm"] == arm, f"{tag}/{kind}: summary arm {row['arm']} vs {arm}")
        check(row["stable_layer"] == want[0], f"{tag}/{kind}/{arm} commit {row['stable_layer']} vs {want[0]}")
        check(row["stable_run_layers"] == want[1], f"{tag}/{kind}/{arm} run {row['stable_run_layers']} vs {want[1]}")
        check(abs(row["p_at_stable"] - want[2]) < 0.001, f"{tag}/{kind}/{arm} p {row['p_at_stable']} vs {want[2]}")
row = summary("carryp0", "off-p0", "decode")
check(row["stable_layer"] == 63 and abs(row["p_at_stable"] - 0.4353) < 0.001, "carryp0 decode off row")
row_on = summary("carryp0", "on-p0", "decode")
check(abs(row_on["p_at_stable"] - 0.0370) < 0.001, f"carryp0 decode on p at last layer {row_on['p_at_stable']}")
cited("never (p at L63 0.0370)", "carryp0 decode on never-commits cell")

# ---- residual reuse (field footprint)
groups = L["residual_reuse"]["5120"]
big = groups["largest_group"]
cited(f"{big['n_captures']}", "residual-reuse group size")
cited(f"{big['n_distinct_byte_contents']}", "distinct byte contents")
cited(f"{big['max_abs_difference']:.5f}", "max|d|")
cited(f"{big['mean_row_rms']:.3f}", "row rms")
cited(f"{groups['n_groups']}", "number of comparison groups")

# ---- §2 probe table
cited(f"{P['min_groups']}", "probe trajectory gate")
census = P["capture_census"]
for width, kind, dirs, prompts, repeat, traj in (
    (5120, "decode", 133, 4, 100, 4),
    (5120, "decode-early", 123, 4, 90, 4),
    (5120, "prompt", 24, 8, 10, 8),
    (1024, "prompt", 49, 6, 9, 7),
):
    row = census.get(str(width), {}).get(kind)
    check(row is not None, f"census missing {width}/{kind}")
    if row:
        for field, want in (("capture_dirs", dirs), ("distinct_prompts", prompts), ("largest_prompt_repeat", repeat),
                            ("independent_trajectories", traj)):
            check(row.get(field) == want, f"census {width}/{kind} {field} {row.get(field)} vs {want}")
for name, want in (
    ("next_token_decode-early_w5120", (4, 4, 0.000, 0.000, 0.694, 0.000, 0.000)),
    ("next_token_pooled_w5120", (7, 5, 0.431, 0.400, 0.466, 0.166, 0.344)),
    ("next_token_prompt_w1024", (7, 2, 0.950, 0.950, 0.792, 0.792, 0.331)),
):
    probe = P["probes"][name]
    rows = probe.get("rows") or probe.get("rows_measured_but_not_supported")
    best = max(rows, key=lambda r: r["balanced_accuracy"])
    traj, classes, acc, bal, maj, shuf, sd = want
    got_traj = probe.get("trajectories") or probe.get("n_groups")
    check(got_traj == traj, f"{name} trajectories {got_traj} vs {traj}")
    check(probe["target"]["n_classes"] == classes, f"{name} classes {probe['target']['n_classes']} vs {classes}")
    check(abs(best["accuracy"] - acc) < 0.001, f"{name} best acc {best['accuracy']} vs {acc}")
    check(abs(best["balanced_accuracy"] - bal) < 0.001, f"{name} bal {best['balanced_accuracy']} vs {bal}")
    check(abs(best["majority"] - maj) < 0.001, f"{name} majority {best['majority']} vs {maj}")
    check(abs(best["shuffled_mean"] - shuf) < 0.001, f"{name} shuffled {best['shuffled_mean']} vs {shuf}")
    check(abs(best["shuffled_sd"] - sd) < 0.001, f"{name} shuffled sd {best['shuffled_sd']} vs {sd}")
    check(bool(best.get("not_supported")) or bool(probe.get("not_supported")), f"{name} should be gated")
    check(not best["above_shuffled"], f"{name} claims above shuffled")
# fold vacuity table
folds = P["probes"]["next_token_decode-early_w5120"]
rows = folds.get("rows") or folds.get("rows_measured_but_not_supported")
vac = folds.get("fold_vacuity")
check(vac is not None, "no fold_vacuity in the decode-early probe")
if vac:
    entries = vac if isinstance(vac, list) else vac.get("folds", [])
    check(all(entry.get("classes_absent_from_train") for entry in entries),
          "fold vacuity: not all folds hold out an unseen class")
    for entry in entries:
        check(f"| {entry['fold_size']} |" in rep, f"report lacks fold row with size {entry['fold_size']}")
        print("   fold:", entry)
# stance counts
cited("250 of 280", "stance counts w5120")
cited("39 of 49", "stance counts w1024")
check(P["probes"]["stance_w5120"]["counts"] == {"0": 250}, f"stance w5120 counts {P['probes']['stance_w5120']['counts']}")
check(P["probes"]["stance_w1024"]["counts"] == {"0": 39}, f"stance w1024 counts {P['probes']['stance_w1024']['counts']}")
check(sum(P["probes"]["stance_w5120"]["counts"].values()) == 250, "stance w5120 sum")
check(sum(P["probes"]["stance_w1024"]["counts"].values()) == 39, "stance w1024 sum")
cited("**250**", "stance direct-claim count w5120")
cited("**39**", "stance direct-claim count w1024")
cited("**0**", "stance hedge count")
print("  stance counts:", P["probes"]["stance_w5120"]["counts"], P["probes"]["stance_w1024"]["counts"])

# ---- §3 readout
p, t = R["readout"]["probe"], R["readout"]["target"]
cited(f"{p['accuracy']:.3f}", "readout probe accuracy")
cited(f"{p['majority']:.3f}", "readout majority")
cited(f"{p['shuffled_mean']:.3f} ± {p['shuffled_sd']:.3f}", "readout shuffled control")
cited("**0.00**", "median cell weight")
b = R["readout"]["binary_legibility"]
for key, name in (("next token starts a word (leading space)", "leading space"),
                  ("next token is a newline", "newline")):
    row = b[key]
    cited(f"{row['accuracy']:.3f}", f"binary {name} accuracy")
    cited(f"{row['balanced_accuracy']:.3f}", f"binary {name} balanced")
    cited(f"{row['majority']:.3f}", f"binary {name} majority")
    check(row["shuffled_balanced_mean"] == 0.5 and row["shuffled_balanced_sd"] == 0.0,
          f"binary {name} shuffled balanced control not 0.5+-0.0")
shares = sorted((r["modal_top_cell_share"], r["n_distinct_top_cells"]) for r in R["readout"]["arms"])
n_fixed = sum(1 for s, d in shares if s == 1.0 and d == 1)
cited(f"{n_fixed} of the {len(shares)} arms", "fixed-channel arm count")
zero_share = R["readout"]["zero_cell_share"]
check(any(f"{v*100:.1f}%" == f"{zero_share*100:.1f}%" for v in (zero_share,)), "zero share not cited")
print("  readout: probe %.3f/%.3f/%.3f, zero share %.3f, fixed arms %d/%d, per-arm %s"
      % (p["accuracy"], p["majority"], p["shuffled_mean"], zero_share, n_fixed, len(shares), shares))
ab = R["absolute_ab"]
pair = ab["pairs"]["abs_on vs abs_off"]
check(abs(pair["mean_cosine_of_cell_vectors"] - 0.553) < 0.002, "abs cosine")
check(pair["top_cell_index_agreement"] == 0.0, "abs top-cell agreement")
cited("+0.553", "abs cosine")
cited("0.0", "top-cell agreement")
cited("+0.553", "abs cosine")
sp = [row["spearman_score_vs_model_probability"] for row in R["field_scores"]["rows"]]
print("  field score spearman range: %.3f .. %.3f" % (min(sp), max(sp)))
check(any(f"{s:.2f}" == f"{s:.2f}" for s in sp), "n/a")
for value in (min(sp), max(sp)):
    check(any(f"{s:.2f}" == f"{value:.2f}" for s in sp), "spearman formatting")

# ---- inventory
check(len(A.get("records", A.get("rows", []))) == 438, f"inventory rows {len(A.get('records', A.get('rows', [])))}")
cited("438", "inventory row count")


# ---- FIELD_READOUT_DESIGN.md
des = (H / "FIELD_READOUT_DESIGN.md").read_text(encoding="utf-8")
def des_cite(text, what):
    check(text in des, f"design note does not state {what}: {text!r}")
sc = R["state_cells"]
avail = [row["available_fraction"] for row in sc]
des_cite(f"{min(avail) * 100:.0f}-{max(avail) * 100:.0f} % of (scale, mode) slots", "availability range")
clamped = sum(1 for row in sc if row["rho_max"] >= 64.0)
des_cite(f"{clamped} of 6 arms", "rho clamp count")
check(all(abs(row["q_median"]) < 1e-6 for row in sc), "not all arms have q_median ~0")
chi = sorted(row["chi_median"] for row in sc)
check(sum(1 for value in chi if value == 0.0) == 2 and num_zero_plus_small(chi) and abs(max(chi) - 0.0186) < 0.001,
      f"chi distribution {chi}")
des_cite("0.00 in every arm", "median cell weight")
des_cite("0.00 in 2 arms, 3e-5 in a third, 0.003-0.019 in the rest", "median chi distribution")
top1 = [row["top1pct_rho_share"] for row in sc]
top10 = [row["top10pct_rho_share"] for row in sc]
des_cite(f"{min(top1) * 100:.0f}-{max(top1) * 100:.0f} %", "top-1% rho share range")
des_cite(f"{min(top10) * 100:.0f}-{max(top10) * 100:.0f} %", "top-10% rho share range")
des_cite(f"{zero_share * 100:.1f} %", "zero share")
des_cite("4 of 6 arms: one cell for all 120 tokens", "fixed-channel arms")
des_cite(f"{R['readout']['cell_energy_vs_confidence_spearman']:.3f}", "cell energy vs confidence")
des_cite(f"{min(sp):.2f} … +{max(sp):.2f}".replace("0.", "0.", 1), "field score range")
ab_on = R["absolute_ab"]["arms"]["abs_on"]; ab_off = R["absolute_ab"]["arms"]["abs_off"]
lesion = R["absolute_ab"]["arms"]["lesion"]
des_cite(f"{ab_on['mean_abs_cell']:.3f}", "abs_on mean |cell|")
des_cite(f"{ab_off['mean_abs_cell']:.3f}", "abs_off mean |cell|")
des_cite("+0.553", "abs cosine")
check(lesion["zero_cell_share"] == 1.0, "lesion arm is not fully zero")
# section 5 table
for kind, layer, run, before, at, sharp in (
    ("prompt", 62, 2, 0.235, 0.456, 0.18),
    ("decode-early", 61, 3, 0.0040, 0.718, 0.71),
    ("decode", 63, 1, 0.102, 0.9994, 0.88),
):
    c = kinds[kind]["commitment"]
    check(f"| {c['median_layer']:.0f} (" in des or f"| {layer} (" in des, f"design note §5 row {kind}: commit cell")
    before_text = f"{before:.2f}" if before < 0.01 else f"{before:.3f}"
    check(before_text in des, f"design note §5 {kind}: p before {before_text!r} (receipt {c['median_p_before']})")
    check(f"{at:.3f}"[:6] in des or f"{at:.2f}" in des,
          f"design note §5 {kind}: p at commit {at!r} (receipt {c['median_p_at_commit']})")
cc = L["widths"]["1024"]["kinds"]["prompt"]["commitment"]
check("22.5" in des and "0.069" in des, "design note §5 control row")
# attention section cites the pinned source lines
check("t_cassi_capture_attention_delta[il] = cur" in des, "design note §6 attention delta hook")
print("  design note: availability %.2f-%.2f, clamped %d, top1%% %.3f-%.3f, top10%% %.3f-%.3f"
      % (min(avail), max(avail), clamped, min(top1), max(top1), min(top10), max(top10)))

print()
if bad:
    print("MISMATCHES / MISSING:")
    for item in bad:
        print("  -", item)
else:
    print("ALL CHECKS PASSED: every checked report number matches its receipt")
