# Kagglepred release audit — 2026-09-28

The local portfolio is approximately 120 GiB. This audit is intentionally
non-destructive: no local files were removed and no raw competition data was
copied into the release staging directory.

## First-party source candidates

`first-party-source-manifest.csv` contains 853 small text/source/derived files,
about 11.7 MiB total, with SHA-256 hashes. It covers the clearly identified
source areas of ARC-AGI-2, Tree Species HSI, TartanIMU, CUHK-X, Traffic Flow,
Kaggriculture, Poker, Playground S6E9, hyperspectral OD, and ARC-AGI-3.

This is a review manifest, not an automatic license grant. Each project still
needs its existing OpenKaggle repository's README, upstream notices, and
competition boundary to govern publication.

## Largest local areas and current decision

| Area | Approx. size | Decision |
| --- | ---: | --- |
| `kaggriculture/remote` + replay reports | 27 GiB | Raw episode/replay material stays local; publish compact derived receipts and hashes only. |
| `traffic/data` + public notebook outputs | 24 GiB | Official data and generated submissions stay local; release source code and selected derived metrics. |
| `cuhk_x_large/data` + cache | 18 GiB | Official data/cache stays local; release scripts, reports, and model manifests only. |
| `tree_species_hsi_2026/raw` + downloads | 13 GiB | Official hyperspectral inputs and sample submissions stay local; release code, reports, and hashes. |
| `arc2_paper/public_assets` | 8.8 GiB | Model/checkpoint bytes need upstream license and lineage confirmation before separate artifact upload. |
| `tartan_imu/data` | 2.6 GiB | Competition package stays local; source and selected weights require separate provenance review. |
| `poker/work` | 2.3 GiB | Prepared feature tables require data-license review; source/tests are candidates. |
| `cuhkx_small/data` | 4.2 GiB | Official/public mirror archives stay local; source/config/receipts are candidates. |

The full per-area count/byte summary is in `excluded-area-inventory.csv`.

## Next publication route

1. Cherry-pick the source manifest into the matching OpenKaggle repositories or
   attach it to the portfolio index.
2. Upload only selected first-party artifact families to a dedicated GitHub
   Release or Kaggle Dataset, with the manifest and provenance note alongside
   them.
3. Fresh-download each remote artifact and compare SHA-256 before any local
   cleanup.
4. Keep official inputs, third-party copies, raw replay/episode logs, caches,
   and unclassified model bundles local until those checks pass.

