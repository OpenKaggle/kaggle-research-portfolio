# HSI mount smoke v3 — version 1 path failure and version 2 preflight

Recorded 2026-09-17 Asia/Shanghai.

## Remote version 1 terminal result

- Kernel: `jahyee/hsi-2026-data-mount-smoke-v3`, version 1.
- Official terminal status: `ERROR`.
- Workload result: terminal `FAIL` after 0.000611 seconds, before reading any competition file.
- Exact failure: the frozen source expected
  `/kaggle/input/competitions/hyperspectral-object-detection-challenge-2026`,
  but that root was absent.
- Training, inference, GPU, dynamic download, and submission all remained false.
- Downloaded terminal receipt SHA-256:
  `55a5b8a87a8431d9baafc60100717f9d7477cf9464614d4652c51aae65010226`.
- Downloaded log SHA-256:
  `08a2a77f1c999d68aa2c6d2eff2b7f340a45a2b2be58c323ee93d24e5184bbb3`.

## Single-variable version 2 repair

The competition mount root is changed only to Kaggle's script-kernel layout:
`/kaggle/input/hyperspectral-object-detection-challenge-2026`.  Inventory,
hash, sample, CPU-only, no-network, no-training, no-submission, and ten-minute
hard-stop contracts are unchanged.

- Repaired source SHA-256:
  `a13d472e6a986844a1f9c020c566aaef053b92b7e48a62cd2a1cd75a1e66d7f7`.
- Kernel metadata SHA-256:
  `3aac808c2f82a5d00b7ff1af6da3e95a02400d69ee0c1a995685278b56acbb05`.
- Repaired test SHA-256:
  `e6ae6a64db6bf13533e56350d1a962cd99e7169b0a6add967cbb40661571615d`.
- Local static/unit tests: 6/6 PASS under CPython 3.13.2.

This receipt authorizes only a private CPU-only rerun of this exact repaired
mount smoke.  It does not authorize GPU training or a competition submission.

## Remote version 2 terminal result

Version 2 also terminated `ERROR`/receipt `FAIL` before any competition-file
read.  The repaired root was still absent, proving that the CLI kernel push did
not materialize the declared `competition_sources` attachment in the runtime.
This is now an attachment/control-plane failure, not another path hypothesis.

- Elapsed: 0.000583 seconds.
- Terminal receipt SHA-256:
  `765ed9d04bc6bc9bd640f2988ee6c6633d0ff975f2613746766fa5d61ddead4d`.
- Downloaded log SHA-256:
  `417405b5d547bb887c7e62f5a27fac572abf41738662bd14a540f9cea14c04f8`.
- Training, inference, accelerator use, network download, and submission all
  remained false.

No third path-only rerun is justified.  The next action must explicitly attach
the joined competition source in Kaggle's notebook UI (and verify the remote
attachment) or replace the transport with a separately resource-audited data
route.  Until then, YOLO training remains blocked.

## Kaggle UI attachment audit and terminal decision

On 2026-09-17 the authenticated Kaggle UI was audited directly:

- The official Data page is accessible and exposes the complete 15.65 GB,
  7,003-file competition payload.
- The competition has no Code tab.  Its direct `/code` route returns
  `We can't find that page`.
- The existing private mount-smoke notebook's Add Input → Competition
  Datasets search did not return this competition when queried by exact slug,
  exact title, `Hyperspectral`, or `Object Detection Challenge 2026`.
- No file was downloaded, no source was attached, and no notebook version was
  run during this audit.

The pre-registered UI-attachment gate therefore has a terminal
`FAIL_ATTACHMENT_ROUTE_UNAVAILABLE` outcome.  The HOD line is sealed without
testing the model hypothesis: no third mount attempt, local 15.65 GB download,
GPU training, or leaderboard submission is authorized.  Reopening requires a
new official, auditable attachment or transport route; the mere passage of
time does not reopen the old plan.
