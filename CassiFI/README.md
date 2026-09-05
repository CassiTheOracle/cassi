# CassiFI

The CassiFI root is reserved for post-prototype development. The paper implementation is isolated from that work:

- [`prototype/`](prototype/README.md) — self-contained local paper bundle: implementation, configuration, exact corpus inputs, checkpoints, tests, and retained evidence.
- [`prototype/cassi-technical-paper.md`](prototype/cassi-technical-paper.md) — the paper paired with this implementation.
- [`prototype/IMPLEMENTATION-AND-PUBLICATION-PLAN.md`](prototype/IMPLEMENTATION-AND-PUBLICATION-PLAN.md) — executed bounded implementation/evaluation work and the remaining system requirements.
- [`prototype/paper-version.json`](prototype/paper-version.json) — the verified local implementation/evidence manifest binding the current paper and retained release.
- [`prototype/public-release-policy.json`](prototype/public-release-policy.json) — the fail-closed policy for the corpus-free public paper release, including the author-approved licenses and exclusion boundary.
- [`legacy/prototype/`](legacy/prototype/README.md) — retired experiments and generated historical material, outside the active prototype dependency closure.

Run paper commands from `prototype/`, not from this directory. There are no root-level compatibility launchers or imports into the archive. Repository/session metadata remains at its existing location.

The local bundle is complete, but corpus redistribution rights are not established. Large inputs, checkpoints, and run artifacts remain Git-ignored. The version inventory records their bytes; the corpus-free public release substitutes bounded hash-linked summaries and a synthetic fixture, so cloning Git is not equivalent to copying the private local bundle.
