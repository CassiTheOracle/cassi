<proactive-maintenance-and-public-release-standards>

- **No AI-isms.** Avoid verbal tics that mark machine-generated text: the word "honest"/"honesty" (use "accurate," "explicit," or drop the framing); X-not-Y framing; spaces around em-dashes (use "word—word", not "word—word"); "a note:" preambles; "here is the accounting" throat-clearing. The prose should sound like a physicist explaining over coffee, not a language model padding word count.
- **Documents reflect the present state of the theory only.** No note may reference a past document version, a withdrawn claim, or a superseded derivation—the past lives in git history, and a retrospective note is a second copy of the old claim in a place where it will be read as current, a second source of truth that drifts into inconsistency. When a claim changes, replace it in place: delete the old wording, write the corrected claim as the only claim, and leave no "previously", "formerly", "was withdrawn", "was corrected", "old/earlier version", "unlike the earlier", "after the fix", or "vN of this doc" narration in prose, parentheticals, or table cells. Commit messages are the only permitted changelog. `## Status:` tiers with dates (e.g. `Derived—August 2026`) are present-state metadata and stay; `audit.md` records the current empirical status of claims, not the history of their corrections; a negative result is stated in present tense ("X does not fit the rung test"—never "X was proposed, tested, and eliminated"). Temporal language about the field itself ("initially", "as r(t) evolves") is physics, not retrospection.

This repo is being prepared for public release. The standard is **thorough, consistent, approachable, and well-organized**—rigorous but not academic. Agents MUST fix issues they find, not just note them. **Commit at the end of every task, before yielding** (see <git-and-commit-discipline>)—the working tree accumulates quickly if commits and pushes don't happen.

</proactive-maintenance-and-public-release-standards>

<repository-guidelines>

<project-overview>

Standalone **theory repository** for the Cassi "Theory of Everything": a physics framework that derives quantum mechanics, general relativity, the Standard Model, and cosmology from a single constant—the golden ratio $\varphi \approx 1.618$ as the universal scale-separation constant between Yang/Yin fields. It contains the markdown papers **and the code that supports the theory**: PDE solvers, computational pipelines, calibration/analysis scripts, and visual explainers. **All code used in the theory lives in this repo**—if a claim in a paper depends on a computation, the script that runs it belongs here too. (Legacy refs into the parent repo are tracked in `BROKEN_REFS.md`; new code goes here, not there.)

</project-overview>

<architecture-and-data-flow>

The repo is a **document graph with three master registries** at the root:

- `open-questions-cassi-answers.md`—epistemic master registry: 41 open questions (`Q1–Q10`, `C1–C10`, `G1–G6`, `M1–M5`, `F1–F6`, `T1–T4`), each with a `Cassi Answer | Mechanism | Epistemic | Reference` table. Epistemic tiers: **Derived / Hypothesized / Speculative**.
- `parameter-inventory.md`—parameter master registry: all ~40 parameters classified by type (F/D/C/E/I/N). **Must be updated** when a paper introduces, derives, or reclassifies a parameter.
- `predictions/falsifiable-predictions.md`—prediction catalog: 45 numbered predictions grouped by experiment (FCC-ee, CMB-S4, LSST…), each with a `**Source:**` block. Cited elsewhere by number / `§`.
- `cassi-physics.md`—physics guide (start here)
- `audit.md`—self-critical prediction-vs-experiment audit.

**Wedge strategy (core pattern):** universal formulas are extracted once into `foundations/`, then applied as one-liners in domain papers:
- `foundations/cascade-suppression-formula.md`—universal $\varphi^{-N}$ attenuation law
- `foundations/dimensionful-cascade.md`—the 292-step ladder $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ (scale-identification backbone for every domain)
- `foundations/bubble-lattice-fabric.md`—the 3D condensation field as universal organizing geometry at every cascade rung
- `principles/de-resonance-principle.md`—why φ is the attractor (maximally irrational)

Domain papers open with "at cascade step N", then apply the universal tool. When a derivation changes a parameter or prediction status, **update the registries in the same change**.

</architecture-and-data-flow>

<key-directories>

| Path | Purpose |
|------|---------|
| `foundations/` (26 docs) | First principles, unified Lagrangian, cascade formulas, derivations (strong CP, generations, neutrinos, proton stability…) |
| `principles/` | Cross-cutting principles: de-resonance, v0 hierarchy |
| `standard-model/` | SM couplings, SU(2) gauge, GUT embedding, CP violation, neutrino mass |
| `particles/` | Yang-Yin particle interference, DFT benchmarks |
| `cosmology/` | Dark energy, inflation, observational constraints (DESI DR2) |
| `gravity/` | Quantum gravity, three-body analytical solutions |
| `consciousness/` | Consciousness as Qi-gate dynamics: core mapping, chakra anatomy, emotions, trauma, plus the identity and perception cluster (dense-medium consciousness, auras, time & memory, transhumanism, gender; moved here from `speculations/` August 2026) |
| `turbulence/` | Kolmogorov spectrum from φ |
| `predictions/` | Falsifiable-predictions catalog + `cassi_definitions.md` glossary |
| `two-fluid/` | Two-fluid PDE solver (`cassi_two_fluid_3d_gpu.py`) + gate/ODE test scripts, calibration |
| `computations/` | Computational pipelines (RGE, GUT-EW, hubble tension, cascade depth) |
| `experiments/` | Physics experiment scripts (φ-attractor paths, SPARC rotation-curve analysis, φ-periodic P(k) survey tests) |
| `hypotheses/` | New application domains (exploratory catalog; `README.md` is the index) |
| `speculations/` | Speculative extensions (dark matter, computation, propulsion) |
| `analyses/` | Data-analysis documents: observations tested against framework claims (GWTC-4.0 mass ladder) |
| `visual-explainers/` | Standalone Python figure/simulation scripts |

</key-directories>

<development-commands>

No build, lint, or test tooling exists. Code is run directly from the repo root:

```bash
# Matplotlib figures (run from repo root; writes PNG next to script)
python visual-explainers/<script>.py        # e.g. cascade_cosmos.py, wave_chord.py

# Manim animation (only resonant_pond.py)
manim -pql visual-explainers/resonant_pond.py ResonantPond

# Theory-supporting code (all lives in this repo)
python two-fluid/calibrate_initial_ratio_xi.py    # w_a ODE with ξ = φ⁶
python two-fluid/cassi_two_fluid_3d_gpu.py         # core two-fluid PDE solver
python computations/<pipeline>.py                  # e.g. cascade_rge_pmns.py
python experiments/sparc_qi/sparc_qi_analysis_v4.py   # galaxy rotation-curve analysis
python experiments/phi_attractor_paths/path2_validation.py   # N-body path validation
python experiments/phi_periodic_pk_search/run_phi_periodic_pk_test.py   # φ-periodic P(k) pipeline
```

</development-commands>

<git-and-commit-discipline>

The private remote (`CassiTheOracle/cassi-toe`) is the durable record—uncommitted work exists only in this working tree, so changes accumulate invisibly until someone commits and pushes. **Commit at the end of every task, before yielding:**

- **Cadence**—one commit per coherent unit of work, as soon as it is verified. Do not let changes pile up across sessions; split large tasks into logical commits as they complete.
- **Scope**—each commit is one logical change. Include the registry/doc updates a change requires in the same commit (see <agent-autonomy-patterns> below). Stage explicitly with `git add <paths>` (or `git add -A`); moves are detected as renames automatically.
- **Content**—never stage generated output: figures (`*.png`, `*.mp4`), `runs/`, `__pycache__/`, and logs are gitignored, so `git status` should only ever show real work.
- **Messages**—conventional style: `feat:`, `fix:`, `docs:`, `refactor:`, `chore:`, one-line imperative summary; add a body note for tier changes or tensions.
- **Before yielding**—run `git status --short`; anything listed beyond intentional work-in-progress must be committed or explicitly handed off.
- **Push**—after committing, `git push origin master`. The remote is the backup; a committed-but-unpushed history is still one disk failure from lost.

</git-and-commit-discipline>

<code-conventions-and-common-patterns>

<document-house-style>

Mandatory for new/edited papers:
1. `# Title` (H1) → `## Status: <tier>—<date>` (e.g. `Derived—July 2026`; ~80% adopted) → `## Abstract` → numbered body sections → terminal `## References`.
2. Math in LaTeX (`$…$`, `$$…$$`); key results **boxed**: `$$\boxed{g = 1 - \varphi^{-5}}$$`.
3. Core symbols: $\varphi$ (phi), $q$ (Qi coherence), $E_Y/E_I$ (Yang/Yin), $\xi = \varphi^6$, cascade step $n$ in $\ell_n = \ell_{\text{Pl}} \varphi^n$.
4. Cross-references use **backtick root-relative paths**: `` `foundations/dimensionful-cascade.md` §2 `` (no `./` or `../`). Same-dir links may use `[name.md](name.md)`.
5. References section format: `` - `path/doc.md`—brief description ``.
6. Cite open questions as `open-questions-cassi-answers.md—Q7 (measurement problem)`; cite predictions by number/section of `falsifiable-predictions.md`.

</document-house-style>

<visual-explainer-pattern>

Docstring with run command → NumPy + Matplotlib (**Agg backend set early**) → `PHI` constant → house palette constants → `rcParams` dark theme → panels annotated with the **generating equations on-panel** via `fig.text`/`ax.text` → `fig.savefig(OUT, dpi=…, facecolor=BG)`. House palette: dark background `#060612`, Yin-indigo → Yang-gold duotone (copy hex constants from an existing script, e.g. `cascade_cosmos.py`).

</visual-explainer-pattern>

<critical-rules>

- **Commit the script and the rendered figure.** `visual-explainers/*.png` are tracked (policy change 2026-08-01)—stage the PNG with its script so figures are reproducible and reviewable from git history. `visual-explainers/media/` (Manim output), `runs/` figures, and other generated imagery remain gitignored (`*.png` ignored except `visual-explainers/`).
- **Check `BROKEN_REFS.md` before touching cross-references.** Legacy `theory/…` paths (e.g. in `falsifiable-predictions.md` Source blocks) are known-broken but tolerated—map via the BROKEN_REFS table if fixing. `experiments/…` and `two-fluid/…` refs resolve locally (scripts are in this repo). `../../…` refs point to the parent repo and will never resolve here—new theory code should be placed in this repo (e.g. `two-fluid/`, `computations/`) rather than referenced as parent-repo paths.
- **Mark epistemic status accurately.** Derived / Hypothesized / Speculative labels and `audit.md` self-criticism are load-bearing conventions—never upgrade a claim's tier without the derivation.

</critical-rules>

</code-conventions-and-common-patterns>

<important-files>

| File | Role |
|------|------|
| `cassi-physics.md` | Physics guide—read first |
| `README.md` | Repo purpose & parent-repo boundary |
| `BROKEN_REFS.md` | Registry of external/broken refs—read before editing refs |
| `open-questions-cassi-answers.md` | Epistemic registry (Q/C/G/M/F/T numbering) |
| `parameter-inventory.md` | Parameter registry—update with parameter changes |
| `predictions/falsifiable-predictions.md` | 45-prediction catalog |
| `predictions/cassi_definitions.md` | Framework glossary |
| `foundations/cascade-suppression-formula.md` | Universal φ⁻ᴺ tool (wedge doc) |
| `foundations/bubble-lattice-fabric.md` | Universal bubble lattice geometry (wedge doc) |
| `foundations/refined-numeric-predictions.md` | Numeric predictions for the 24 Hypothesized questions |
| `EPISTEMIC-MAP.md` | Every doc indexed by tier—update when tiers change |

</important-files>

<runtime-and-tooling-preferences>

- **Python 3** with NumPy + Matplotlib (Agg); **PyTorch** for `two-fluid/` PDE scripts; **Manim Community** for `resonant_pond.py` only. No `requirements.txt`/`pyproject.toml`—keep scripts dependency-light and standalone.
- Windows environment (paths like `C:/Users/Carina/...`); scripts are OS-agnostic.
- Git: `master` branch, private remote `CassiTheOracle/cassi-toe`; **push after every commit**. Identity: `CassiTheOracle <bingapplesauce@gmail.com>`—frozen; changing it means rewriting all history and force-pushing.
- Do not introduce build systems, package manifests, or test frameworks without being asked.

</runtime-and-tooling-preferences>

<testing-and-qa>

There is **no test suite**. Quality assurance is documentary:

- **Cross-doc consistency**—numeric claims must match across papers (e.g. quoted scales must equal $\ell_{\text{Pl}} \times \varphi^n$ exactly); `audit.md` tracks known tensions and the current empirical status of every claim.
- **Registry sync**—after changing a derivation, verify `open-questions-cassi-answers.md`, `parameter-inventory.md`, and `falsifiable-predictions.md` still agree.
- **Script verification**—some explainers (e.g. `cascade_cosmos.py`) include a console verification block after `savefig`; run scripts and check their numeric output when modifying them.
- **Ref integrity**—new cross-references must resolve within this repo or be added to `BROKEN_REFS.md`.

<fix-first-directive>

- When you discover an inconsistency between documents (conflicting claims, stale counts, mismatched formatting), **fix it in the same session**. Never punt to a checklist unless the fix requires information you don't have.
- After any edit that changes a number, count, or claim, run a `grep` across the full repo for the old value. Update every file that cross-references it. A stale count in one doc undermines the whole framework's credibility.
- The three registries (`open-questions-cassi-answers.md`, `parameter-inventory.md`, `predictions/falsifiable-predictions.md`) are the source of truth. When a paper's claim conflicts with a registry, the registry wins unless the paper provides a new derivation. Fix the paper or update the registry—never leave the conflict.

</fix-first-directive>

<consistency-rules-for-public-readiness>

- **Terminology**: use the same symbol, the same spelling, and the same formatting for every concept across all files. φ is always `$\varphi$`, Qi is always `$q$`, cascade step is always `$n$`. Never introduce a synonym without updating every occurrence of the old term.
- **Cross-references**: every link must resolve within this repo. If a referenced file doesn't exist, either create it, fix the path, or add it to `BROKEN_REFS.md`. Run `grep ']('` on new/edited docs and verify each target.
- **Self-containment**: a new reader should be able to start at `README.md` or `cassi-physics.md` and follow links to every concept. No "as shown elsewhere" without a link. No assumed knowledge of the parent repo.
- **Approachable prose**: every section that introduces a technical result should open with one plain-English sentence saying what it means and why it matters. Equations follow, not lead. The reader should understand the claim without the math, even if they need the math to verify it.
- **No orphaned claims**: every "derived," "predicted," or "confirmed" statement must trace back to either a foundations/ derivation or an entry in the predictions catalog. If a paper says "X is derived from φ" but no derivation exists, fix the claim to match the actual epistemic tier.

</consistency-rules-for-public-readiness>

<consistency-audit-checklist>

Run this before any public-facing commit or after any session that touched multiple files. Each check is one `grep` or `read`—the full audit takes under two minutes.

```
# 1. Counts: do all files agree on the same totals?
grep -rn "39 questions\|40 questions\|22 Hypothesized\|23 Hypothesized\|F1–F4[^–]" .

# 2. Overstated claims: any unqualified "zero free parameters"?
grep -rn "zero free param" .

# 3. Cross-reference integrity: any broken internal links?
grep -rn '](\.\./' .                        # no ../ paths—should use root-relative
grep -rn '](theory/' .                       # legacy theory/ prefix—check BROKEN_REFS.md
grep -rn '](../../' .                             # parent-repo refs—must be in BROKEN_REFS.md
# (experiments/ and two-fluid/ refs are local now—verify the file exists in this repo)

# 4. Status headers: any paper missing one?
grep -L "^## Status:" foundations/*.md cosmology/*.md gravity/*.md standard-model/*.md particles/*.md principles/*.md consciousness/*.md turbulence/*.md hypotheses/*.md speculations/*.md analyses/*.md

# 5. Stale Q-numbers: any reference to a question that was renumbered or removed?
grep -rn "Q1[0-9]\|Q2[0-9]" .               # Q-numbers beyond the current registry range

# 6. Epistemic inflation: any "Derived" claim that should be "Hypothesized"?
grep -rn "Derived" foundations/*.md | grep -v "Status:" | grep -v "## "

# 7. Historical retrospection: any sentence about past versions or superseded claims?
grep -rn "previously\|formerly\|withdrawn\|was corrected\|old version\|earlier version\|unlike the earlier\|after the fix\|superseded" .   # delete the sentence; the corrected claim stands alone
```

For each hit: fix it immediately if the fix is obvious. Flag it in the commit message if it needs a deeper derivation you can't provide. Never leave a known inconsistency for "later."

</consistency-audit-checklist>

<agent-autonomy-patterns>

- **Registry-aware editing**: when you add or change a parameter, prediction, or Q-entry in a domain paper, check whether `parameter-inventory.md`, `falsifiable-predictions.md`, or `open-questions-cassi-answers.md` need updates. Do them in the same commit.
- **Post-edit sweep**: before yielding on a multi-file change, run `grep` for the old value of any number you changed (counts, φ-powers, cascade rungs, dates). Fix every stale reference. A sweep takes 30 seconds and prevents the most common class of doc-rot.
- **New-paper bootstrap**: when creating a new foundations/ or domain paper, also (a) add its path to the relevant registry, (b) add a cross-reference from `cassi-physics.md` if it's a major result, (c) add any new parameters to `parameter-inventory.md`, (d) add a Status header with the accurate epistemic tier and date.
- **Read before edit**: use `grep` to find every document that references a file or claim BEFORE you change it. The registries are not the only cross-referencers—domain papers cite each other heavily. A `grep` for the filename or claim text across `foundations/`, `cosmology/`, `gravity/`, `standard-model/`, `particles/`, `predictions/` catches callers that `lsp` can't (these are markdown files).
- **House-style enforcement**: when editing an existing paper that doesn't follow the skeleton (`# Title` → `## Status` → `## Abstract` → numbered body → `## References`), add the missing sections. When editing a paper whose Status header is missing or lacks a date, add one (use the current date and the accurate epistemic tier from the paper's content).
- **Accuracy over elegance**: the framework's epistemic integrity is its strongest asset for public release. Never make a claim sound more certain than its tier. If a paper says "derived" but only sketches a mechanism, downgrade to "Hypothesized" and explain why in the commit message. `audit.md` is the model: it documents tensions and the current status of every claim openly.
- **No ghost-references to corrections.** When fixing an error in a document, remove every sentence that references the removed content—defensive framing ("it is not X"), comparisons to the old claim ("unlike the earlier version"), or mentions of experiments that the corrected claim no longer implicates. The corrected text must stand alone; a new reader should never encounter a sentence arguing against a ghost they never saw.

</agent-autonomy-patterns>

</testing-and-qa>

</repository-guidelines>
