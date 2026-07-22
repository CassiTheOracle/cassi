# Repository Guidelines

## Project Overview

Standalone **theory-document repository** for the Cassi "Theory of Everything": a physics framework that derives quantum mechanics, general relativity, the Standard Model, and cosmology from a single constant — the golden ratio $\varphi \approx 1.618$ as the universal scale-separation constant between Yang/Yin fields. Extracted from the parent [Cassi physics repo](https://github.com/carinasgardner/physics); it contains **only markdown papers and Python visual-explainer scripts** — no simulation code, experiments, or PDE solvers (those live in the parent repo; see `BROKEN_REFS.md`).

## Architecture & Data Flow

The repo is a **document graph with three master registries** at the root:

- `open-questions-cassi-answers.md` — epistemic master registry: 40 open questions (`Q1–Q10`, `C1–C10`, `G1–G6`, `M1–M5`, `F1–F5`, `T1–T4`), each with a `Cassi Answer | Mechanism | Epistemic | Reference` table. Epistemic tiers: **Derived / Hypothesized / Speculative**.
- `parameter-inventory.md` — parameter master registry: all ~40 parameters classified by type (F/D/C/E/I/N). **Must be updated** when a paper introduces, derives, or reclassifies a parameter.
- `predictions/falsifiable-predictions.md` — prediction catalog: 31 numbered predictions grouped by experiment (FCC-ee, CMB-S4, LSST…), each with a `**Source:**` block. Cited elsewhere by number / `§`.
- `TOE.md` — manually curated executive summary / master narrative (start here).
- `audit.md` — self-critical prediction-vs-experiment audit.

**Wedge strategy (core pattern):** universal formulas are extracted once into `foundations/`, then applied as one-liners in domain papers:
- `foundations/cascade-suppression-formula.md` — universal $\varphi^{-N}$ attenuation law
- `foundations/dimensionful-cascade.md` — the 292-step ladder $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ (scale-identification backbone for every domain)
- `principles/de-resonance-principle.md` — why φ is the attractor (maximally irrational)

Domain papers open with "at cascade step N", then apply the universal tool. When a derivation changes a parameter or prediction status, **update the registries in the same change**.

## Key Directories

| Path | Purpose |
|------|---------|
| `foundations/` (19 docs) | First principles, unified Lagrangian, cascade formulas, derivations (strong CP, generations, neutrinos, proton stability…) |
| `principles/` | Cross-cutting principles: de-resonance, v0 hierarchy |
| `standard-model/` | SM couplings, SU(2) gauge, GUT embedding, CP violation, neutrino mass |
| `particles/` | Yang-Yin particle interference, DFT benchmarks |
| `cosmology/` | Dark energy, inflation, observational constraints (DESI DR2) |
| `gravity/` | Quantum gravity, three-body analytical solutions |
| `consciousness/` | Consciousness as Qi-gate dynamics (single bridge doc; psychology content lives in parent repo) |
| `turbulence/` | Kolmogorov spectrum from φ |
| `predictions/` | Falsifiable-predictions catalog + `cassi_definitions.md` glossary |
| `visual-explainers/` | Standalone Python figure/simulation scripts |

## Development Commands

No build, lint, or test tooling exists. The only runnable artifacts:

```bash
# Matplotlib figures (run from repo root; writes PNG next to script)
python visual-explainers/<script>.py        # e.g. cascade_cosmos.py, wave_chord.py

# Manim animation (only resonant_pond.py)
manim -pql visual-explainers/resonant_pond.py ResonantPond
```

## Code Conventions & Common Patterns

### Document house style (mandatory for new/edited papers)
1. `# Title` (H1) → `## Status: <tier> — <date>` (e.g. `Derived — July 2026`; ~80% adopted) → `## Abstract` → numbered body sections → terminal `## References`.
2. Math in LaTeX (`$…$`, `$$…$$`); key results **boxed**: `$$\boxed{g = 1 - \varphi^{-5}}$$`.
3. Core symbols: $\varphi$ (phi), $q$ (Qi coherence), $E_Y/E_I$ (Yang/Yin), $\xi = \varphi^6$, cascade step $n$ in $\ell_n = \ell_{\text{Pl}} \varphi^n$.
4. Cross-references use **backtick root-relative paths**: `` `foundations/dimensionful-cascade.md` §2 `` (no `./` or `../`). Same-dir links may use `[name.md](name.md)`.
5. References section format: `` - `path/doc.md` — brief description ``.
6. Cite open questions as `open-questions-cassi-answers.md — Q7 (measurement problem)`; cite predictions by number/section of `falsifiable-predictions.md`.

### Visual explainer pattern (all `visual-explainers/*.py`)
Docstring with run command → NumPy + Matplotlib (**Agg backend set early**) → `PHI` constant → house palette constants → `rcParams` dark theme → panels annotated with the **generating equations on-panel** via `fig.text`/`ax.text` → `fig.savefig(OUT, dpi=…, facecolor=BG)`. House palette: dark background `#060612`, Yin-indigo → Yang-gold duotone (copy hex constants from an existing script, e.g. `cascade_cosmos.py`).

### Critical rules
- **Commit the script, never the figure.** `*.png` / `*.mp4` are gitignored; `visual-explainers/.gitignore` also ignores `media/` (Manim output).
- **Check `BROKEN_REFS.md` before touching cross-references.** Legacy `theory/…` paths (e.g. in `falsifiable-predictions.md` Source blocks) are known-broken but tolerated — map via the BROKEN_REFS table if fixing. `experiments/…`, `two-fluid/…`, `../../…` refs point to the parent repo and will never resolve here.
- **Mark epistemic status honestly.** Derived / Hypothesized / Speculative labels and `audit.md` self-criticism are load-bearing conventions — never upgrade a claim's tier without the derivation.
- Commits follow conventional style: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`.

## Important Files

| File | Role |
|------|------|
| `TOE.md` | Master narrative — read first |
| `README.md` | Repo purpose & parent-repo boundary |
| `BROKEN_REFS.md` | Registry of external/broken refs — read before editing refs |
| `open-questions-cassi-answers.md` | Epistemic registry (Q/C/G/M/F/T numbering) |
| `parameter-inventory.md` | Parameter registry — update with parameter changes |
| `predictions/falsifiable-predictions.md` | 31-prediction catalog |
| `predictions/cassi_definitions.md` | Framework glossary |
| `foundations/cascade-suppression-formula.md` | Universal φ⁻ᴺ tool (wedge doc) |
| `foundations/refined-numeric-predictions.md` | Numeric predictions for the 23 Hypothesized questions |

## Runtime/Tooling Preferences

- **Python 3** with NumPy + Matplotlib (Agg); **Manim Community** for `resonant_pond.py` only. No `requirements.txt`/`pyproject.toml` — keep scripts dependency-light and standalone.
- Windows environment (paths like `C:/Users/Carina/...`); scripts are OS-agnostic.
- Git: `master` branch, **no remote configured** — local-only history.
- Do not introduce build systems, package manifests, or test frameworks without being asked.

## Testing & QA

There is **no test suite**. Quality assurance is documentary:

- **Cross-doc consistency** — numeric claims must match across papers (e.g. quoted scales must equal $\ell_{\text{Pl}} \times \varphi^n$ exactly); `audit.md` tracks known tensions and past errors.
- **Registry sync** — after changing a derivation, verify `open-questions-cassi-answers.md`, `parameter-inventory.md`, and `falsifiable-predictions.md` still agree.
- **Script verification** — some explainers (e.g. `cascade_cosmos.py`) include a console verification block after `savefig`; run scripts and check their numeric output when modifying them.
- **Ref integrity** — new cross-references must resolve within this repo or be added to `BROKEN_REFS.md`.

## Proactive Maintenance & Public-Release Standards

This repo is being prepared for public release. The standard is **thorough, consistent, approachable, and well-organized** — rigorous but not academic. Agents MUST fix issues they find, not just note them.

### Fix-first directive
- When you discover an inconsistency between documents (conflicting claims, stale counts, mismatched formatting), **fix it in the same session**. Never punt to a checklist unless the fix requires information you don't have.
- After any edit that changes a number, count, or claim, run a `grep` across the full repo for the old value. Update every file that cross-references it. A stale count in one doc undermines the whole framework's credibility.
- The three registries (`open-questions-cassi-answers.md`, `parameter-inventory.md`, `predictions/falsifiable-predictions.md`) are the source of truth. When a paper's claim conflicts with a registry, the registry wins unless the paper provides a new derivation. Fix the paper or update the registry — never leave the conflict.

### Consistency rules for public-readiness
- **Terminology**: use the same symbol, the same spelling, and the same formatting for every concept across all files. φ is always `$\varphi$`, Qi is always `$q$`, cascade step is always `$n$`. Never introduce a synonym without updating every occurrence of the old term.
- **Cross-references**: every link must resolve within this repo. If a referenced file doesn't exist, either create it, fix the path, or add it to `BROKEN_REFS.md`. Run `grep ']('` on new/edited docs and verify each target.
- **Self-containment**: a new reader should be able to start at `README.md` or `TOE.md` and follow links to every concept. No "as shown elsewhere" without a link. No assumed knowledge of the parent repo.
- **Approachable prose**: every section that introduces a technical result should open with one plain-English sentence saying what it means and why it matters. Equations follow, not lead. The reader should understand the claim without the math, even if they need the math to verify it.
- **No orphaned claims**: every "derived," "predicted," or "confirmed" statement must trace back to either a foundations/ derivation or an entry in the predictions catalog. If a paper says "X is derived from φ" but no derivation exists, fix the claim to match the actual epistemic tier.

### Consistency audit checklist
Run this before any public-facing commit or after any session that touched multiple files. Each check is one `grep` or `read` — the full audit takes under two minutes.

```
# 1. Counts: do all files agree on the same totals?
grep -rn "39 questions\|40 questions\|22 Hypothesized\|23 Hypothesized\|F1–F4[^–]" .

# 2. Overstated claims: any unqualified "zero free parameters"?
grep -rn "zero free param" .

# 3. Cross-reference integrity: any broken internal links?
grep -rn '](\.\./' .                        # no ../ paths — should use root-relative
grep -rn '](theory/' .                       # legacy theory/ prefix — check BROKEN_REFS.md
grep -rn '](experiments/\|](two-fluid/' .    # parent-repo refs — must be in BROKEN_REFS.md

# 4. Status headers: any paper missing one?
grep -L "^## Status:" foundations/*.md cosmology/*.md gravity/*.md standard-model/*.md particles/*.md principles/*.md consciousness/*.md turbulence/*.md

# 5. Stale Q-numbers: any reference to a question that was renumbered or removed?
grep -rn "Q1[0-9]\|Q2[0-9]" .               # Q-numbers beyond the current registry range

# 6. Epistemic inflation: any "Derived" claim that should be "Hypothesized"?
grep -rn "Derived" foundations/*.md | grep -v "Status:" | grep -v "## "
```

For each hit: fix it immediately if the fix is obvious (stale count, missing header, wrong path). Flag it in the commit message if it needs a deeper derivation you can't provide. Never leave a known inconsistency for "later."

### Agent autonomy patterns
- **Registry-aware editing**: when you add or change a parameter, prediction, or Q-entry in a domain paper, check whether `parameter-inventory.md`, `falsifiable-predictions.md`, or `open-questions-cassi-answers.md` need updates. Do them in the same commit.
- **Post-edit sweep**: before yielding on a multi-file change, run `grep` for the old value of any number you changed (counts, φ-powers, cascade rungs, dates). Fix every stale reference. A sweep takes 30 seconds and prevents the most common class of doc-rot.
- **New-paper bootstrap**: when creating a new foundations/ or domain paper, also (a) add its path to the relevant registry, (b) add a cross-reference from `TOE.md` if it's a major result, (c) add any new parameters to `parameter-inventory.md`, (d) add a Status header with honest epistemic tier and date.
- **Read before edit**: use `grep` to find every document that references a file or claim BEFORE you change it. The registries are not the only cross-referencers — domain papers cite each other heavily. A `grep` for the filename or claim text across `foundations/`, `cosmology/`, `gravity/`, `standard-model/`, `particles/`, `predictions/` catches callers that `lsp` can't (these are markdown files).
- **House-style enforcement**: when editing an existing paper that doesn't follow the skeleton (`# Title` → `## Status` → `## Abstract` → numbered body → `## References`), add the missing sections. When editing a paper whose Status header is missing or lacks a date/date, add one (use the current date and the honest epistemic tier from the paper's content).
- **Honesty over elegance**: the framework's epistemic integrity is its strongest asset for public release. Never make a claim sound more certain than its tier. If a paper says "derived" but only sketches a mechanism, downgrade to "Hypothesized" and explain why in the commit message. `audit.md` is the model: it documents tensions and past errors openly.
