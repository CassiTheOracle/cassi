class_name CassiTreeConsts
## Shared meshless-TREE constant holder — the dedup target for the tree
## constants previously re-declared in cassi_tree_worker.gd /
## cassi_sim.gd / cassi_physics_engine.gd (review_sim.md #7).
##
## DATA-ONLY: plain consts, no logic. Consumers reference these as
## `CassiTreeConsts.X` so a value lives in exactly one place. Every entry
## MUST match the value each consuming file produced before the dedup —
## see the PHI_6 double-spelling note below.

const ML_TREE_LEAF_CAP := 1
const ML_TREE_MAX_LEVELS := 14
const ML_TREE_NODE_MAX_MULT := 8
const ML_TREE_FIELD_FLOOR := 1e-6   # source-mass recipe field-density floor
const ML_TREE_THETA := 0.5
const PHI: float = 1.618033988749895

# PHI_6 carries TWO spellings that were written two different ways across
# the codebase and MUST be kept separate:
#   - PHI_6 (computed)  — the sim + engine's original: PHI*PHI*PHI*PHI*PHI*PHI
#   - PHI_6_ROUNDED     — the tree worker's original rounded literal.
# The two spellings are NOT the same expression, and are not guaranteed to
# produce the same float32 bit pattern: in pure float32 arithmetic the
# computed form lands 1 ULP above the rounded literal (0x418f8ddf vs
# 0x418f8dde ≈ 17.944273 vs 17.944271); if the compiler const-folds the
# product in double precision then truncates, they coincide (both land on
# the rounded literal). Either way, each file's tree build PC must encode
# the value IT always produced, so picking any single spelling would
# silently change the OTHER file's encoded value by up to 1 ULP. Keep BOTH
# named consts — the worker binds the rounded one, the sim/engine bind the
# computed one — so the encoded float32 stays byte-for-byte what each file
# produced before the dedup.
const PHI_6: float = PHI * PHI * PHI * PHI * PHI * PHI  # φ⁶ ≈ 17.94427191 (computed spelling — sim/engine)
const PHI_6_ROUNDED: float = 17.94427191               # φ⁶ literal (the tree worker's rounded spelling)
