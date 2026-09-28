# Kaggle portfolio release audit (2026-09-28)

This folder is a non-destructive inventory of the local Kaggle portfolio. It does not copy competition data or model files.

- `first-party-source-manifest.csv` hashes small source/derived-text candidates from clearly identified project areas. It is a staging manifest, not a blanket license grant.
- `excluded-area-inventory.csv` summarizes larger or mixed-provenance areas by project, area, file count, and bytes; raw file names are intentionally omitted.

Release sequence: verify ownership/license, upload only cleared artifact families to the appropriate OpenKaggle repository or Kaggle Dataset, fresh-download, compare SHA-256, then consider local cleanup. Official inputs, third-party copies, raw replays, caches, and large model bundles remain local until that sequence is complete.
