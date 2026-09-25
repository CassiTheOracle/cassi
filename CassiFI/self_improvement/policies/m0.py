"""M0: Cassi's seed improver.

It works through the functions with the most measured time first, shows the
brain the function, its measured cost, where that cost goes, and the module
context it depends on, and retries a function once with the reason its
previous rewrite failed.  Its successor procedure hands the next generation the
complete record of what each call produced.
"""
from __future__ import annotations

import ast
import re
import textwrap
from pathlib import Path

SYSTEM = (
    "You are Cassi's performance engineer. You rewrite one Python 3.12 function from Cassi's own source so it "
    "runs faster while every observable behavior stays exactly the same."
)
MAX_ATTEMPTS = 3
COMPLETION = 3000


def _module_view(root: str, target: dict) -> tuple[str, str]:
    """Imports/constants of the target's module and the same-module definitions it calls."""

    path = Path(root) / target["file"]
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (OSError, SyntaxError):
        return "", ""
    header: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(ast.get_source_segment(text, node) or "")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            segment = ast.get_source_segment(text, node) or ""
            if segment.count("\n") < 3 and len(segment) < 240:
                header.append(segment)
    definitions: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.setdefault(node.name, []).append(textwrap.dedent(ast.get_source_segment(text, node) or ""))
    called: list[str] = []
    for callee in target.get("callees", []):
        module, _, name = callee["function"].partition(":")
        if module != target["module"] or name == target["name"] or name not in definitions:
            continue
        for source in definitions[name][:1]:
            lines = source.splitlines()
            if len(lines) > 60:
                source = "\n".join(lines[:60]) + "\n    ..."
            called.append(source)
        if len(called) >= 3:
            break
    if target.get("method"):
        class_name = target["qualname"].split(".")[0]
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__" and item.name != target["name"]:
                        source = textwrap.dedent(ast.get_source_segment(text, item) or "")
                        lines = source.splitlines()
                        if len(lines) > 40:
                            source = "\n".join(lines[:40]) + "\n    ..."
                        called.insert(0, f"# class {class_name}\n{source}")
                break
    return "\n".join(header[:80]), "\n\n".join(called)


def _prompt(target: dict, root: str, rules: str, previous: dict | None) -> str:
    header, called = _module_view(root, target)
    base = target.get("base", {})
    calls = max(1, int(base.get("calls") or target["profile"]["calls"]))
    seconds = float(base.get("seconds") or target["profile"]["cumulative"])
    kind = "method" if target.get("method") else "function"
    lines = [
        f"Module `{target['file']}` (Cassi's own source). {kind.capitalize()} to speed up: `{target['qualname']}`.",
        "",
        f"Measured on Cassi's anchor: {calls} calls, {seconds:.4f} s inclusive in total "
        f"({1e6 * seconds / calls:.1f} microseconds per call).",
        "Where its time goes (profiler, cumulative seconds including children):",
    ]
    for callee in target.get("callees", [])[:8]:
        lines.append(f"  - {callee['function']}  calls {callee['calls']}  {callee['cumulative']:.4f} s")
    if target.get("callers"):
        lines.append("Called from: " + ", ".join(f"{c['function']} ({c['calls']} calls)" for c in target["callers"][:3]))
    if header:
        lines += ["", "Module imports and constants:", "```python", header, "```"]
    if called:
        lines += ["", "Definitions it relies on in the same module:", "```python", called, "```"]
    lines += ["", f"The {kind}:", "```python", textwrap.dedent(target["source"]).rstrip(), "```", "", "Rules:", rules]
    if previous is not None:
        lines += [
            "",
            "Your previous rewrite of this function was rejected:",
            previous.get("detail", "")[:1200],
        ]
        if previous.get("candidate"):
            lines += ["```python", previous["candidate"][:4000], "```"]
        lines.append("Fix the cause and try a different speedup if that one did not pay off.")
    lines += [
        "",
        "First name where the time goes and your plan in two or three sentences, then give the complete "
        f"replacement {kind} in one ```python block.",
    ]
    return "\n".join(lines)


def plan(view: dict) -> list[dict]:
    budget = view["budget"]
    if budget["calls_left"] <= 0 or budget["tokens_left"] < 1500:
        return []
    targets = sorted(view["targets"], key=lambda t: -float(t.get("base", {}).get("seconds") or 0.0))
    attempts: dict[str, list[dict]] = {}
    for outcome in view["history"]:
        attempts.setdefault(outcome["target"], []).append(outcome)
    verified = {t for t, items in attempts.items() if any(item.get("stage") == "verified" for item in items)}
    fresh = [t for t in targets if t["id"] not in attempts]
    retry = [t for t in targets if t["id"] in attempts and t["id"] not in verified and len(attempts[t["id"]]) < MAX_ATTEMPTS]
    chosen = (fresh + retry)[: view["slots"]]
    requests = []
    per_call = budget["tokens_left"] // max(1, min(view["slots"], budget["calls_left"]))
    for target in chosen:
        previous = attempts.get(target["id"], [None])[-1]
        content = _prompt(target, view["snapshot_root"], view["rules"], previous)
        prompt_tokens = len(content) // 3 + 200
        max_tokens = min(COMPLETION, view["limits"]["max_tokens"], per_call - prompt_tokens)
        if max_tokens < 700:
            continue
        requests.append({
            "target": target["id"],
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": 0.4 if previous is None else 0.7,
            "thinking": False,
            "note": "first attempt" if previous is None else f"retry after {previous.get('stage')}",
        })
    return requests


def parse(text: str, target: dict) -> str | None:
    name = re.escape(target["name"])
    definition = re.compile(rf"^\s*(async\s+)?def\s+{name}\s*\(", re.M)
    blocks = re.findall(r"```(?:python|py)?[^\n]*\n(.*?)```", text, re.S)
    if not blocks:
        tail = re.search(r"```(?:python|py)?[^\n]*\n(.*)$", text, re.S)
        blocks = [tail.group(1)] if tail else []
    for block in reversed(blocks):
        if definition.search(block):
            return block
    return None


def _evidence(record: dict, limit: int) -> str:
    parts: list[str] = []
    for comparison in record.get("comparisons", []):
        parts.append(
            f"Successor trial {comparison['parent']} vs {comparison['child']}: readings {comparison['readings']}, "
            f"verified {comparison.get('verified')}, promoted {comparison['promoted']}."
        )
    examples: list[str] = []
    for arm in reversed(record.get("rounds", [])):
        rows = [
            f"### Arm {arm['label']} run by {arm['policy']}: reading {arm['reading']}, verified {arm['verified']} of "
            f"{arm['attempts']} attempts, calls {arm['calls_used']}, tokens {arm['tokens_used']}, stages {arm.get('stages')}"
        ]
        for outcome in arm["history"]:
            ratio = f" ratio {outcome['ratio']}" if outcome.get("ratio") else ""
            rows.append(
                f"- wave {outcome.get('wave')} {outcome.get('target')}: {outcome.get('stage')}{ratio}; "
                f"tokens {outcome.get('prompt_tokens', 0)}+{outcome.get('completion_tokens', 0)}; "
                f"note {outcome.get('note', '')!r}; {str(outcome.get('detail', ''))[:220]}"
            )
            if outcome.get("candidate") and len(examples) < 6 and outcome.get("stage") in ("verified", "screen", "slower"):
                examples.append(
                    f"{outcome['stage']} ({outcome.get('ratio')}) for {outcome['target']}:\n```python\n"
                    f"{outcome['candidate'][:1500]}\n```"
                )
        parts.append("\n".join(rows))
    text = "\n\n".join(parts)
    if examples:
        text += "\n\n### Example rewrites\n" + "\n\n".join(examples)
    return text[:limit]


def successor_messages(record: dict) -> list[dict]:
    parent = record["parent_source"]
    limit = record["limits"]["prompt_chars"] - len(parent) - len(record["interface"]) - 6000
    evidence = _evidence(record, max(4000, limit))
    user = f"""Write policy m{record['generation']}, the successor of {record['parent']}.

## What a policy is
{record['interface']}

## Rules every rewrite must satisfy
{record['rules']}

## The current policy ({record['parent']})
```python
{parent}
```

## What happened under this lineage
{evidence}

## Task
Study the evidence: which prompts and choices produced verified speedups, where calls and tokens were spent without a
result (parse failures, invalid candidates, changed outputs, slower rewrites), and what information the brain lacked.
Then write the complete successor module. It inherits the job of writing its own successor, so keep
successor_messages working and make it pass on what this generation learned.
The successor is promoted only if, on untouched functions with the same budget, its arm earns a higher reading than
{record['parent']}'s.  Use only the Python standard library; keep the module self-contained.
Answer with at most ten short bullet points of analysis, then the complete module in one ```python block."""
    return [
        {"role": "system", "content": "You are Cassi, improving the procedure you use to improve your own code."},
        {"role": "user", "content": user},
    ]
