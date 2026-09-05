# CassiFI public paper release

This is the source document for a generated public-safe release containing the technical paper, its implementation source, fixed configurations and schemas, one synthetic public exchange fixture, and bounded evaluation receipts.

The release deliberately excludes all private corpus bytes, trained and historical checkpoints, raw historical evidence, local diagnostics, caches, and archived experiments. Hashes and bounded result summaries document omitted evidence without granting distribution rights to it.

## Current status

Carina Gardner approved the author metadata, declarations, Apache-2.0 code license, CC BY 4.0 manuscript license, rendered PDF, exclusion boundary, and external publication of version 0.1.0. The exact release can be built and verified locally or from a fresh repository clone.

System readiness is separate. Resource telemetry and the authenticated live CassiFI–CassiCosmos integration remain open even though the bounded paper release is publication-ready.

## Build and verify locally

From `CassiFI/prototype`:

```powershell
python verification/public_release.py build --output ../cassifi-paper-public-1
python verification/public_release.py verify --root ../cassifi-paper-public-1
python verification/public_release.py smoke --root ../cassifi-paper-public-1
```

The output directory must not already exist and must remain outside `prototype/`. Building does not upload, publish, accept legal terms, or change `public-release-policy.json`.

The verifier checks the exact file inventory, byte hashes, safe relative paths, forbidden data/checkpoint classes, the synthetic public fixture, the tracked hash-bound summary of the excluded local evaluation, publication status, license assignments, and text disclosure patterns.

## Render locally

The repository retains a generated `cassi-technical-paper.pdf`. To inspect a fresh HTML rendering before regenerating that PDF:

```powershell
python verification/render_paper.py --output ../cassi-technical-paper.preview.html
```

The renderer uses `markdown-it-py`, embeds the publication SVG, and leaves TeX rendering to MathJax in the local browser preview. The generated preview is not added to the source bundle.
