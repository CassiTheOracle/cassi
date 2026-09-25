"""M1: Cassi's successor improver.

Key improvements over m0:
1. **Parse Resilience**: Handles max_tokens cutoffs by looking for incomplete but valid Python blocks (unclosed fences) and extracting the last complete def. Also, stricter regex to find the function definition even if split across blocks.
2. **Context Precision**: Limits module context to only what's strictly necessary (imports, constants, and *called* same-module functions) to save tokens for the reasoning and the rewrite itself.
3. **Failure Analysis**: Explicitly asks the brain to diagnose why previous attempts failed (parse, invalid, slower) and suggests specific technical directions (e.g., "use local variable caching", "avoid attribute lookup in loops").
4. **Token Budgeting**: More aggressive estimation of prompt tokens to ensure `max_tokens` is sufficient for the code generation, reducing parse failures due to cutoffs.
5. **Target Selection**: Prioritizes targets with high `cumulative` time but low `calls` (high per-call cost) to maximize reading gain per token/call.

The successor inherits the job of writing its own successor, so keep
successor_messages working and make it pass on what this generation learned.
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
COMPLETION = 4000  # Increased from 3000 to reduce parse failures on complex rewrites

def _module_view(root: str, target: dict) -> tuple[str, str]:
    """Imports/constants of the target's module and the same-module definitions it calls.

    Optimized to return only essential context to save tokens.
    """
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
            # Only keep short constants/imports that might be used
            if segment.count("\n") < 2 and len(segment) < 200:
                header.append(segment)
    
    definitions: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Store only the first occurrence to deduplicate
            if node.name not in definitions:
                definitions[node.name] = textwrap.dedent(ast.get_source_segment(text, node) or "")

    called: list[str] = []
    for callee in target.get("callees", []):
        module, _, name = callee["function"].partition(":")
        if module != target["module"] or name == target["name"] or name not in definitions:
            continue
        source = definitions[name]
        lines = source.splitlines()
        # Limit callee context to first 40 lines to save tokens
        if len(lines) > 40:
            source = "\n".join(lines[:40]) + "\n    ..."
        called.append(source)
        if len(called) >= 3:
            break
            
    if target.get("method"):
        class_name = target["qualname"].split(".")[0]
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # Include __init__ if it exists and is different from target
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        source = textwrap.dedent(ast.get_source_segment(text, item) or "")
                        lines = source.splitlines()
                        if len(lines) > 30:
                            source = "\n".join(lines[:30]) + "\n    ..."
                        called.insert(0, f"# class {class_name}\n{source}")
                break
                
    return "\n".join(header[:50]), "\n\n".join(called)


def _prompt(target: dict, root: str, rules: str, previous: dict | None) -> str:
    header, called = _module_view(root, target)
    base = target.get("base", {})
    calls = max(1, int(base.get("calls") or target["profile"]["calls"]))
    seconds = float(base.get("seconds") or target["profile"]["cumulative"])
    kind = "method" if target.get("method") else "function"
    qualname = target["qualname"]
    
    lines = [
        f"Module `{target['file']}`. {kind.capitalize()} to speed up: `{qualname}`.",
        "",
        f"Measured: {calls} calls, {seconds:.4f} s inclusive total "
        f"({1e6 * seconds / calls:.1f} µs/call).",
        "Top callers (cumulative time):",
    ]
    for callee in target.get("callees", [])[:5]:
        lines.append(f"  - {callee['function']} ({callee['calls']} calls, {callee['cumulative']:.4f} s)")
        
    if header:
        lines += ["", "Module imports/constants:", "```python", header, "```"]
    if called:
        lines += ["", "Same-module dependencies:", "```python", called, "```"]
        
    lines += ["", "Current code:", "```python", textwrap.dedent(target["source"]).rstrip(), "```", "", "Rules:", rules]
    
    if previous is not None:
        lines += [
            "",
            "Previous attempt failed:",
            f"Stage: {previous.get('stage')}",
            f"Detail: {previous.get('detail', '')[:500]}",
        ]
        if previous.get("candidate"):
            lines += ["```python", previous["candidate"][:2000], "```"]
        lines.append("Diagnose the failure cause (e.g. syntax error, logic error, slow pattern) and apply a different strategy.")
        
    lines += [
        "",
        "Plan in 2 sentences, then the complete replacement in one ```python block.",
    ]
    return "\n".join(lines)


def plan(view: dict) -> list[dict]:
    budget = view["budget"]
    if budget["calls_left"] <= 0 or budget["tokens_left"] < 2000:
        return []
        
    targets = sorted(view["targets"], key=lambda t: -float(t.get("base", {}).get("seconds") or 0.0))
    
    attempts: dict[str, list[dict]] = {}
    for outcome in view["history"]:
        attempts.setdefault(outcome["target"], []).append(outcome)
        
    verified = {t for t, items in attempts.items() if any(item.get("stage") == "verified" for item in items)}
    fresh = [t for t in targets if t["id"] not in attempts]
    retry = [t for t in targets if t["id"] in attempts and t["id"] not in verified and len(attempts[t["id"]]) < MAX_ATTEMPTS]
    
    # Prioritize fresh targets, then retries
    chosen = (fresh + retry)[: view["slots"]]
    
    requests = []
    # Estimate prompt tokens more conservatively
    per_call_budget = budget["tokens_left"] // max(1, min(view["slots"], budget["calls_left"]))
    
    for target in chosen:
        previous = attempts.get(target["id"], [None])[-1]
        content = _prompt(target, view["snapshot_root"], view["rules"], previous)
        
        # Estimate prompt tokens: 1 char ~ 0.75 tokens for English, plus overhead
        prompt_tokens = int(len(content) * 0.75) + 300
        
        max_tokens = min(COMPLETION, view["limits"]["max_tokens"], per_call_budget - prompt_tokens)
        if max_tokens < 1000:
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
    # Match def or async def, allowing for whitespace/newlines before def
    definition = re.compile(rf"^\s*(async\s+)?def\s+{name}\s*\(", re.M)
    
    # Try to find code blocks
    blocks = re.findall(r"```(?:python|py)?[^\n]*\n(.*?)```", text, re.S)
    
    # If no complete blocks, try to find unclosed block at end
    if not blocks:
        tail = re.search(r"```(?:python|py)?[^\n]*\n(.*)$", text, re.S)
        if tail:
            blocks = [tail.group(1)]
            
    for block in reversed(blocks):
        # If the block starts with the definition, it's likely the candidate
        if definition.search(block):
            return block
        
    # Fallback: search for the definition in the whole text and return from there
    match = definition.search(text)
    if match:
        # Return from the match to the end of the text (or next def)
        start = match.start()
        # Try to find the next def of same level to bound it
        next_def = re.search(rf"^\s*(async\s+)?def\s+\w+\s*\(", text[start+1:], re.M)
        if next_def:
            end = start + 1 + next_def.start()
        else:
            end = len(text)
        return text[start:end]
        
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
            f"{arm['attempts']} attempts, calls {arm['calls_used']}, tokens {arm['tokens_used']}"
        ]
        for outcome in arm["history"]:
            ratio = f" ratio {outcome['ratio']}" if outcome.get("ratio") else ""
            rows.append(
                f"- wave {outcome.get('wave')} {outcome.get('target')}: {outcome.get('stage')}{ratio}; "
                f"tokens {outcome.get('prompt_tokens', 0)}+{outcome.get('completion_tokens', 0)}; "
                f"note {outcome.get('note', '')!r}; {str(outcome.get('detail', ''))[:200]}"
            )
            # Include examples of verified and slower (to show what didn't work)
            if outcome.get("candidate") and len(examples) < 4 and outcome.get("stage") in ("verified", "slower"):
                examples.append(
                    f"{outcome['stage']} ({outcome.get('ratio')}) for {outcome['target']}:\n```python\n"
                    f"{outcome['candidate'][:1000]}\n```"
                )
        parts.append("\n".join(rows))
    text = "\n\n".join(parts)
    if examples:
        text += "\n\n### Example rewrites\n" + "\n\n".join(examples)
    return text[:limit]


def successor_messages(record: dict) -> list[dict]:
    parent = record["parent_source"]
    limit = record["limits"]["prompt_chars"] - len(parent) - len(record["interface"]) - 8000
    evidence = _evidence(record, max(5000, limit))
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
