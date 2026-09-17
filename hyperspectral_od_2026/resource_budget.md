# Resource budget — 2026-09-09

## Local machine

- Free space at preflight: 27,205,332,992 bytes (about 25.3 GiB).
- Official current competition payload: 15,653,423,958 bytes (about 14.6 GiB), before filesystem overhead.
- Kaggle's all-files download is a single archive. Keeping that archive while extracting would require roughly 29.2 GiB plus overhead and cannot fit safely.
- Downloading all 7,003 files individually would fit only narrowly and leave roughly 10.8 GiB before processed images/checkpoints. It is deferred to avoid starving the host disk.
- Local environment has Pillow, NumPy, and scikit-learn, but no PyTorch, Ultralytics, OpenCV, or pycocotools installation and no assumed CUDA GPU.

## Kaggle plan

- Use a private Kaggle T4 job with the competition mounted as a source; do not copy competition data to a public dataset.
- Generate pseudo-RGB images in `/kaggle/working`, train one YOLO11m checkpoint, validate, then infer 1,000 Phase-1 test images.
- Estimated working storage: 1–3 GiB for pseudo-RGB images, labels, plots, and checkpoint.
- Requested training: 50 epochs, 640-pixel input, auto batch, early stopping patience 12.
- Expected runtime envelope: preprocessing 10–40 minutes, training/inference 2–6 hours on one T4; stop well inside Kaggle's notebook runtime limit.

## Submission budget

- Limit: 3 submissions per team per day.
- Phase 1 goal: spend one slot only after the 8-column schema, contiguous `id`, image IDs, class range, confidence range, bounding boxes, one-checkpoint provenance, and stability gates pass.
- Reserve at least two daily slots for a verified regression fix or a single-variable threshold/band follow-up.

