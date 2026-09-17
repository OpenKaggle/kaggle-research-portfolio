# Third-party notices — provisional Biohub baseline

This document inventories third-party material in the promoted `BH-0001` baseline. It is a working compliance record, not a final winner-delivery license statement. The final submission and model have not been selected.

## Reused notebook source

- Source: `reyhanksatria/biohub-cell-tracking-0-946-lb`
- Author shown by Kaggle: REYHAN KSATRIA
- Verified source-page license: Apache-2.0
- Frozen source SHA-256: `ae8e01a262211045161984e469e8be23e3386bab9140fe12df503dc6a1e010e6`
- Local reproduction change: dependency paths only; no model or threshold change

Any distribution must retain the applicable Apache-2.0 license, copyright, attribution, and NOTICE obligations. The current evidence does not establish an unrestricted right to offer every reused source portion solely under the MIT license required for a winning submission. Before winner delivery, obtain authoritative compatibility confirmation or replace the reused notebook logic with independently authored code whose provenance is documented.

## Public model artifacts

| Role | Kaggle dataset | License | Selected checkpoint SHA-256 |
|---|---|---|---|
| Primary graph generator | `pilkwang/biohub-tracking-support-pack-50ep-v1` | CC0-1.0 | `12f6881ee3620a831697ca098ff8f48e687a24225f4e048b538deec3562fe771` |
| Center-prior detector | `pilkwang/biohub-deepcenter-unet3d-center-prior-v1` | CC0-1.0 | `8040999a92f6b7bbd98fa8cf458141e045c0f9ad7c936bdb3b18e1f7edafe2a0` |
| Secondary graph generator | `pilkwang/biohub-temporal-unet3d-seed314159-v1` | CC0-1.0 | `9bac2fa0dadc4a6fc1899e0caf187f4b553e0a7cd90ba1261a68b35ffe9e305f` |

## Offline-installed software dependencies

The completed Kaggle log proves that the notebook installed its missing packages from attached offline wheels with dependency resolution disabled. Exact wheel versions are recorded in `artifacts/baseline_winner_delivery_provenance.json`; authoritative license evidence is recorded in `artifacts/baseline_dependency_license_inventory.json`.

| Package | Version | License |
|---|---|---|
| polars | 1.42.0 | MIT |
| tracksdata | 0.1.0rc6.dev3+g980c2d30a | BSD-3-Clause |
| zarr | 3.2.1 | MIT |
| PySCIPOpt | 6.2.1 | MIT; bundled SCIP >=8.0.3 is Apache-2.0 |
| geff | 1.2.0.1.1 | MIT |
| geff-spec | 1.1.1 | MIT |
| ilpy | 0.6.0 | MIT |
| imagecodecs | 2026.6.26 | BSD-3-Clause |
| rustworkx | 0.18.0 | Apache-2.0 |
| numcodecs | 0.15.1 | MIT |
| donfig | 0.8.1.post1 | MIT |
| bidict | 0.23.1 | MPL-2.0 |

The identifier-level inventory for these twelve packages is complete. The exact wheel hashes and the primary license file embedded in every wheel are archived and verified by `artifacts/baseline_dependency_license_archive.json`; the twelve texts are stored under `THIRD_PARTY_LICENSES/`. Nine files are byte-identical to their wheel member and three differ only by an added final line feed.

This does not close the whole binary-distribution review. The exact PySCIPOpt wheel contains `libscip.so.10.0`, `libgfortran` and `libquadmath`, and its SCIP binary exposes an Ipopt/EPL notice, while the wheel includes only the PySCIPOpt MIT license file. The exact Imagecodecs wheel contains many native codec modules and bundled shared libraries while including one Imagecodecs BSD-3-Clause license file. Those bundled-component licenses and notices have not yet been enumerated. Redistribution of the wheels has not been decided, and the Kaggle base-image packages were not frozen by the completed run.

Before a winner package is declared ready:

1. Capture an exact environment freeze, Python patch version, CUDA and driver information from the final selected run.
2. Complete the bundled-native-component license/NOTICE inventory for every shipped binary wheel, including MPL-2.0 covered-file obligations for `bidict` if its wheel is redistributed.
3. Include the full Apache-2.0 license and every applicable upstream NOTICE file.
4. Confirm that the source-code grant required by the competition can be made without contradicting upstream obligations.
5. Regenerate this inventory against the exact final notebook, checkpoints, and archive.
