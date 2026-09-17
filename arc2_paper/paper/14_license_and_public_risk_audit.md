# License and public-release risk audit

Status: **conditional / not release-cleared**  
Checked: 2026-09-09 (Asia/Shanghai)  
Scope: candidate public notebook, source bundle, model inputs, offline wheels,
paper, receipts, logs, and cover. This is an engineering release audit, not
legal advice.

## Evidence standard

- **Direct**: the exact local file or exact upstream asset page carries the
  license evidence.
- **Declared**: a project manifest or notice names a license, but the exact
  upstream asset record or license text has not been frozen.
- **Missing**: no adequate release artifact is present. Missing evidence is a
  blocker, not permission by inference.

## Inventory and decision

| Asset | Intended handling | Evidence | Status | Release decision |
| --- | --- | --- | --- | --- |
| Original TRM-compatible orchestration/source bundle | MIT-0 | `public_assets/trm_source/LICENSE` and `LICENSE-MIT-0`, both SHA-256 `0860d23c8b1347b0b4234ed0c34a445a7330593b2af615a56d05ea02a506514e` | Direct for this bundle | Allow only after the final source archive is enumerated and every original file is covered |
| Paper/Writeup | CC BY 4.0, subject to final Kaggle rule check | Policy is recorded in `00_rules_and_registration.md`; no paper license file exists yet | Missing grant artifact | Block publication package until author approval and a CC BY 4.0 license/notice are added |
| ARC-AGI-2 files | Preserve Apache-2.0 | Upstream `official/ARC-AGI-2/LICENSE`, SHA-256 `8360699be7ffadd4b460e4287c1f7d0ada282518ee8e375fff603b1b3ecbb43f` | Direct | Do not redistribute evaluator-only solution copies; link to the official source and preserve the notice for any permitted data copy |
| Qwen fine-tune `sorokin/qwen3_4b_grids15_sft139/Transformers/bfloat16/1` | Prefer an attached public Kaggle Model reference, not a repackaged weight archive | The [exact Kaggle variation](https://www.kaggle.com/models/sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16) and unauthenticated API report public access, Apache 2.0, version 1, and 7,267,271,302 bytes; the [upstream Qwen3-4B license](https://huggingface.co/Qwen/Qwen3-4B/blob/main/LICENSE) is also Apache-2.0. Frozen receipt SHA-256: `ea52c069f4cfe1fdb5cb736c923524c13c3783a961c535e8f1d10867ac4d44f7` | Direct and frozen | Allow by exact Kaggle Model attachment; do not repackage 7.27 GB of weights unless needed and separately manifested |
| TRM checkpoint `cpmpml/arc-prize-trm-031/step_220708` | Attach by public Kaggle Dataset reference only | Unauthenticated Kaggle API returned HTTP 200, `isPrivate=false`, version 1, and `CC0: Public Domain`; authenticated metadata independently returned `CC0-1.0`. The receipt above also binds the local checkpoint SHA-256 `dbf771737d9799b84faf009c24c5376831f095d2cfd66debbe9a505a445bfc31` | Direct and frozen | Allow by exact public Kaggle Dataset attachment; recheck point-in-time status before final binding |
| Source dataset `christopherdaleman/arc-proof-search-trm-2026-source` | Attach by exact Kaggle Dataset reference | The frozen local bundle has hash-bound MIT-0 and third-party notices, but no current exact Kaggle asset record is frozen | Local license evidence; exact asset access/provenance unresolved | Block a public-notebook claim until a no-credential access and exact asset receipt is captured |
| Bootstrap notebook `sorokin/pip-install-unsloth-flash-patch` | Attach by exact Kaggle Kernel reference | Frozen local metadata for the exact slug records `is_private=false`, and the clean seven-cell notebook is hashed; no notebook-level license was found | Historical public metadata; license missing | Block a public-notebook claim until current no-credential access and an exact license decision are frozen |
| TinyRecursiveModels | Preserve MIT notice | Commit `e7b68717f0a6c4cbb4ce6fbef787b14f42083bd9`; bundled license SHA-256 `a17df02e2c90fbbb4b2fc0f0262ae429ef9c628c45ee434499fd9aeb987735a4` | Direct | Allow with commit pin, modification notice, attribution, and bundled license |
| Icecuber / `top-quarks/ARC-solution` | Preserve MIT notice | Commit `9407072659de1270358c2ba34c527785214dd68b`; bundled license SHA-256 `7789cd54fb8b265bac4358c88967306d08cb84c05dac15de7ee0db114c4d471a` | Direct | Allow with commit pin, modification notice, attribution, and bundled license |
| Seven wheels with embedded license text | Redistribute unmodified only if still needed for the offline notebook | Exact wheel and embedded-license hashes below | Direct | Allow after copying the embedded notices into the release inventory and retaining the unmodified wheels |
| `antlr4-python3-runtime==4.9.3` wheel | Preserve the exact tag's upstream license beside the unmodified wheel | Wheel metadata says BSD; wheel SHA-256 `f1fbfc655cf72ab92b7f0a911ab2cc4fa075506ad14f2f3e27ffc6ae6c54e49d`; the wheel lacks a notice file, so the [official 4.9.3 tag license](https://github.com/antlr/antlr4/blob/4.9.3/LICENSE.txt) is bundled at `public_assets/trm_source/third_party/antlr4/LICENSE.txt`, SHA-256 `64f3d26b8407ef4400b0036c3f4b74e2f99c556f33c9ae66347479bb83e42791` | Direct exact-version evidence | Allow with the unmodified wheel, the separately bundled license, and provenance link |
| Generated cover `media/cover_candidate_v2.png` | Use as Kaggle Media Gallery cover | Original generated image SHA-256 `a1b96ee8da0ae8f49869b1413701e83b958826d9ac7111cf808a1c2c0da851be`; exact generation/edit prompts and content audit are in `media/cover_manifest.md` | Proven provenance; output-rights conclusion not frozen | Recheck the applicable image-service terms immediately before publication; do not claim exclusive copyright or third-party endorsement |

The Qwen base-model license corroborates the family license but would not, by
itself, license a fine-tuned derivative. The exact Kaggle variation's displayed
Apache-2.0 field and public API record are therefore the relevant direct
evidence. The TRM checkpoint is independently supported by both a no-credential
public API response and authenticated Kaggle metadata; a stale notebook input
label is not allowed to override those current asset records.

## Offline wheel inventory

| Distribution | Metadata license | Wheel SHA-256 | Embedded license SHA-256 |
| --- | --- | --- | --- |
| `adam-atan2-pytorch==0.2.4` | MIT | `404d1c5ba331633a6f6e395891ed28cb13a7cf622ac824ba9913b8286ad97e99` | `13b4464bb9292484ad939cdaffee0356158401a99feb9114d0234c2f6e66ab87` |
| `antlr4-python3-runtime==4.9.3` | BSD | `f1fbfc655cf72ab92b7f0a911ab2cc4fa075506ad14f2f3e27ffc6ae6c54e49d` | not in wheel; exact-tag bundled copy `64f3d26b8407ef4400b0036c3f4b74e2f99c556f33c9ae66347479bb83e42791` |
| `argdantic==1.3.3` | MIT classifier | `2f8d7ede4103cf8e162a0b888f58f4e8c9691ebedc65702bfd6602ef76c79748` | `e3efb2064d4cf45001b67b5bc336ac3c2b859420248bfbe5f64c82462abf1c61` |
| `coolname==2.2.0` | BSD | `4d1563186cfaf71b394d5df4c744f8c41303b6846413645e31d31915cdeb13e8` | `30633d2e9dcca7d31378f3652419794793c73fd8e158f74da3fc5d822bbec97e` |
| `hydra-core==1.3.2` | MIT | `fa0238a9e31df3373b35b0bfb672c34cc92718d21f81311d8996a16de1141d8b` | `52412d7bc7ce4157ea628bbaacb8829e0a9cb3c58f57f99176126bc8cf2bfc85` |
| `omegaconf==2.3.0` | BSD classifier | `7b4df175cdb08ba400f45cae3bdcae7ba8365db4d165fc65fd04b050ab63b46b` | `b31375ed5d5cbe7ec2d0c4c14df8afa7a8e5501bbe25f70b6cbc461685f4b91a` |
| `pydantic-settings==2.10.1` | MIT | `a60952460b99cf661dc25c29c0ef171721f98bfcb52ef8d9ea4c943d7c8cc796` | `eb355a753e020346d33d83bf9769135b89fc610568ac531a01c295bcee7fd998` |
| `python-dotenv==1.1.1` | BSD-3-Clause | `31f23644fe2602f88ff55e1f5c79ba497e01224ee7737937930c448e4d0e24dc` | `80619b7049f08c81683ad0e01f08f257a840652dd71ee83146d36658c7d2c2b9` |

## Public-package allowlist

Only the following classes may enter a release candidate, and only after a
fresh path/secret scan and manifest hash:

1. Exact scored notebook/source versions and compact reproduction scripts.
2. Machine-readable receipts needed to substantiate paper claims.
3. Third-party license/notice files and a generated dependency inventory.
4. Paper text, evidence-backed figures, and the cover after the final rights
   and visual-risk check.
5. Links to public model assets in preference to redistributing weights.

The executable policy is `tools/audit_release_manifest.py`. Preliminary
manifest `manifests/public_release_preflight_v1.json` passes over 11 exact
files and two public asset references. It deliberately labels itself
`PRELIMINARY_NOT_FINAL`; the scored notebook and final archive must receive a
new `FINAL_RELEASE_CANDIDATE` manifest.

The frozen V3 notebook also has an independent exact dependency inventory at
`manifests/v3_notebook_dependency_inventory_v1.json`. Its notebook, metadata,
and preregistration hashes match, and all five metadata dependencies are
enumerated. The audit intentionally fails on the source dataset and bootstrap
notebook because their current public-access/license receipts are missing.
Local identity and historical metadata are separately frozen in
`results/v3_dependency_local_evidence_2026-09-09.json`; they narrow the risk
but cannot satisfy the current-access/license gate. This failure is a release
blocker, not a runtime or Accuracy result.

## Exclusions and redaction rules

Do not publish as part of the project bundle:

- Kaggle API credentials, cookies, tokens, private URLs, local usernames,
  absolute machine paths, environment dumps, or unrelated personal data;
- the whole `kaggle_runs/` tree, caches, temporary build trees, `__pycache__`,
  or raw logs that have not passed a targeted disclosure scan;
- `evaluator_only/` solution material or evaluator correctness labels in a
  deployable candidate/selector artifact;
- downloaded model weights when a stable public attachment can be used;
- employer/institution material without written approval.

The Kaggle username, team name, submission ID, public URLs, and author identity
are intentional publication fields once the author signs off; they must not be
removed by a generic scrubber.

## Release gates

- [x] Exact dated TRM checkpoint license/public-access receipt frozen at
  `results/model_asset_license_access_2026-09-09.json`.
- [x] Exact Qwen fine-tune variation public-access, version, byte count, and
  Apache-2.0 receipt frozen in the same file.
- [ ] Generate a final archive manifest covering every source file, wheel,
  model reference, notice, and SHA-256.
- [ ] Add MIT-0 and CC BY 4.0 grant files/notices to their intended scopes and
  obtain author plus employer/institution approval where applicable.
- [ ] Recheck current Kaggle rules and generated-cover service terms.
- [ ] Run a targeted credential/private-path/evaluator-label scan on the exact
  release archive and inspect every hit manually. The preliminary V2-smoke
  allowlist passes, but it is not the final archive.
- [ ] Verify the public notebook works without a private dependency and that
  all linked assets are accessible without special permission.
- [ ] Resolve both V3 dependency-audit failures with current exact-asset
  public-access/license receipts; do not infer accessibility from attachment
  metadata or a historical successful run.

Until all eight boxes are checked, `license-compatible`, `fully reproducible`,
and `public-release ready` are prohibited claims.
