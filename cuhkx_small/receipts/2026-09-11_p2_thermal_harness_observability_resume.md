# P2 Thermal TSM harness: observability and safe resume

Date: 2026-09-11 (Asia/Shanghai)

## Scope and invariants

- Changed only the future-run experiment harness and its focused tests.
- Did not inspect, signal, stop, restart, or otherwise interact with PID 80012.
- Preserved the frozen subject order `[6, 18, 5, 21]`, promotion/kill gates,
  model, preprocessing, optimizer, seeds, epoch count, batch behavior, comparator
  ordering, and candidate ordering.
- No test data is read or recorded.

## Implemented behavior

1. Each completed training epoch emits one structured JSON progress event to
   stdout and atomically replaces `progress.json`. Epoch events contain only
   training loss/accuracy and run/fold/variant identity; protected binding and
   `test_data_read=false` fields cannot be overridden by event details.
2. `run_binding.json` binds an output directory to the resolved Thermal root,
   dataset fingerprint and root checks, extraction receipt path and SHA-256,
   frozen configuration/order/gates, source SHA-256, runtime versions, resolved
   device, seed, and model topology. A mismatch rejects reuse before training.
3. A fold receipt is atomically published only after both the comparator and
   candidate complete. It includes the metrics/histories and timing already used
   by the final report, a result SHA-256, exact run/fold/subject/seed identity,
   leakage results, `test_data_read=false`, and an explicit declaration that no
   learned weights were saved.
4. A restarted future run validates data discovery, image audit, root/report
   binding, frozen split, leakage, and the fold receipt before skipping a fully
   complete fold. A missing, partial, corrupt, or mismatched receipt fails closed
   or causes the whole fold to be rerun. Mid-fold state is deliberately not
   resumed.
5. The final report is now atomically written and records the run binding,
   resumed folds, and each fold receipt SHA-256. The original rule remains: a
   learned checkpoint is produced only by a qualifying four-fold run after all
   scientific gates pass.
6. Future runs may optionally set PyTorch's CPU intra-op pool with
   `--torch-threads N` and its inter-op pool with `--torch-interop-threads N`.
   Both default to unset, so the harness calls neither setter unless explicitly
   requested. Inter-op is applied first, immediately after argument parsing and
   before data discovery or tensor work; a late/unsafe PyTorch rejection fails
   closed. Requested and effective values are recorded in progress, the final
   report, and the run fingerprint, so a resume under different thread settings
   is rejected.

## Verification

- `train_p2_thermal_tsm.py` and its test module compile successfully.
- Focused binding/progress/receipt test passes, including deterministic binding,
  extraction-receipt mismatch rejection, protected progress fields, atomic-file
  cleanup, receipt integrity rejection, and absence of per-fold `.pt` files.
- Focused CPU-thread test passes, including no setter calls on the default path,
  explicit intra-op/inter-op configuration, positive-value enforcement, and
  fingerprint mismatch rejection for changed thread settings.
- Full CUHK Small test discovery passes: 25 tests in 40.819 seconds.

## Files changed

- `cuhkx_small/src/train_p2_thermal_tsm.py`
- `cuhkx_small/src/test_train_p2_thermal_tsm.py`
- `cuhkx_small/receipts/2026-09-11_p2_thermal_harness_observability_resume.md`
