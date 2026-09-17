# CUHK-X Small — ImageNet MobileNetV3-Small initialization preregistration

Frozen: 2026-09-11 22:16 CST, before this task inspected any current Thermal
fold result.  This is a separate initialization experiment, not an amendment
to, resumption of, or interpretation of a running scratch output directory.

## Question and allowed scope

This arm asks whether a public ImageNet initialization improves the stability
of the already-preregistered Thermal B0/P2 comparison.  It does not change the
P2 hypothesis, clips, subjects, temporal sampling, optimizer, schedule, or
promotion gates.  No external training examples, action-recognition model,
test payload, Kaggle result, or current fold result may inform the decision to
run it.

The competition host permits public pretrained models when they remain
publicly accessible and are disclosed:

- https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724404

The frozen P2 plan already permits public ImageNet weights if URL, version,
license, and hash are recorded and both B0/P2 arms use the same initialization.
No other external data or model is permitted in this quick-kill.

## Pinned source and pending provenance

- Identifier: `MobileNet_V3_Small_Weights.IMAGENET1K_V1`.
- TorchVision version: `v0.15.2`.
- Architecture source:
  https://raw.githubusercontent.com/pytorch/vision/v0.15.2/torchvision/models/mobilenetv3.py
- Supporting layer source:
  https://raw.githubusercontent.com/pytorch/vision/v0.15.2/torchvision/ops/misc.py
- Weight URL:
  https://download.pytorch.org/models/mobilenet_v3_small-047dcff4.pth
- HTTP HEAD on 2026-09-11 CST: `Content-Length: 10306551`,
  `Last-Modified: Mon, 08 Feb 2021 11:56:01 GMT`, range-capable.
- Filename hash prefix: `047dcff4`; this is **not** accepted as the complete
  SHA-256.
- Full weight SHA-256: `PENDING_ACTION_TIME_DOWNLOAD`; absence blocks loading,
  training, promotion, and release.
- TorchVision code license: BSD-3-Clause:
  https://raw.githubusercontent.com/pytorch/vision/v0.15.2/LICENSE
- Weight/data-derived terms: `PENDING_COMPATIBLE_USE_RECORD`.  TorchVision
  explicitly warns that pretrained weights may have terms inherited from their
  training data and that the user must establish permission.  The competition
  permits separately identified incompatible-license input pretrained models,
  but this does not remove the disclosure requirement:
  https://docs.pytorch.org/vision/main/models.html

No weight body was downloaded for this preregistration.

## Exact architecture and mapping audit

The pinned reference has 2,542,856 parameters with a 1,000-class head.  The
clean-room 40-class model has 1,558,856 parameters.  Their difference is
exactly the reference head (`1,025,000`) minus the local head (`41,000`).

The focused offline audit is:

`src/audit_imagenet_mobilenet_v3_compatibility.py`

It derives the pinned reference state shapes independently from the published
configuration and maps them semantically to the clean-room names.  The only
naming-layout differences are the `features`/`blocks` namespaces,
TorchVision's nested projection `Conv2dNormActivation`, and the
`fc1`/`fc2` versus `reduce`/`expand` squeeze-excitation names.

The reference `classifier.3.weight` and `classifier.3.bias` are excluded.
The excluded local 40-class head is initialized once with an isolated CPU
generator seeded `20260911`: weight entries are sampled from
`Normal(mean=0, std=0.01)` and bias entries are zero.  It is then included in
one shared initial state copied to both arms.  No arm may independently
recreate or randomize its head.

### First convolution

Both models have a `[16, 3, 3, 3]` stem, but RGB semantics do not match
`[frame, positive_delta, negative_delta]`.  Direct RGB-channel assignment is
therefore forbidden.  For reference tensor `W` the frozen transform is:

```text
W_local[:, 0, :, :] = W[:, 0, :, :] + W[:, 1, :, :] + W[:, 2, :, :]
W_local[:, 1, :, :] = 0
W_local[:, 2, :, :] = 0
```

This exactly preserves the reference stem response to a grayscale image
replicated across RGB when B0 supplies `[frame, 0, 0]`.  P2 begins with no
pretrained assumption about signed-delta semantics, while gradients may learn
both delta kernels.  B0 and P2 receive byte-identical stem tensors.

### Functional mismatch discovered before execution

State shapes are not sufficient for execution compatibility.  TorchVision
uses BatchNorm `eps=0.001, momentum=0.01`; the current clean-room class uses
PyTorch defaults `eps=0.00001, momentum=0.1`.  Consequently the current class
is `NO_GO` for ImageNet execution even when every tensor shape maps.  A future
isolated ImageNet constructor must set the reference BatchNorm values in both
B0 and P2.  The scratch constructor and any running scratch output must remain
unchanged.

## Fair comparison and frozen gates

- One mapped initial state is created, hashed, and deep-copied to B0 and P2.
- B0 remains `[frame, zero, zero]`, no TSM, temporal mean pooling.
- P2 remains `[frame, positive_delta, negative_delta]` with the frozen TSM
  blocks `{1,2,4,5,6,7,9,10}`.
- All eight midpoint indices, `112x112` preprocessing, optimizer, schedule,
  augmentations, seed, train clips, and held-out clips remain identical.
- Fold order remains subjects `6, 18, 5, 21`.
- Stop after subjects 6 and 18 if both P2-minus-B0 gains are below `+0.01`.
- Full promotion still requires median gain `>=+0.02`, at least three of four
  nonnegative gains, and worst-subject gain `>=-0.02`.
- Subject overlap and clip overlap must both be zero; no public-leaderboard
  feedback enters selection.
- FP32 remains one checkpoint `<95,000,000` bytes; final competition limit is
  one checkpoint `<100,000,000` bytes.  Two clean offline inference outputs
  must be byte-identical.
- Use a new output directory and a distinct run fingerprint containing the
  weight SHA-256, mapping-policy identifier, reference version, normalization
  values, and this receipt SHA-256.  A scratch output directory must reject
  the ImageNet binding and vice versa.

## Mapping go/no-go gate

Weight download is not authorized merely by this receipt.  Before any fit,
the compatibility audit must show all of the following:

1. exact published small configuration and expected parameter counts;
2. 100% coverage of reference non-head state entries;
3. 100% coverage of local non-head destination state entries;
4. no duplicate destination and no shape mismatch;
5. 100% handled eligible parameter elements;
6. at least 99.95% direct-copy eligible parameter elements;
7. the stem is the only transformed tensor and the 1,000-class head is the
   only excluded learned component;
8. reference BatchNorm hyperparameters are active in the isolated arm; and
9. exact full weight SHA-256 and compatible-use/disclosure record are bound.

Any failure is `REJECT_IMAGENET_INITIALIZATION`; thresholds may not be relaxed
after seeing fold or Kaggle results.  Shape success alone is
`SHAPE_MAPPING_GO_EXECUTION_BLOCKED`, not permission to train.

## State at freeze

The offline audit completed with:

- 244 reference state entries; after excluding the two 1,000-class head
  tensors, all 242/242 entries map to all 242/242 local non-head entries;
- zero shape mismatches and zero duplicate destinations;
- 1,517,856/1,517,856 eligible parameter elements handled (100%);
- 1,517,424 elements copied exactly (99.9715388%);
- only the 432-element stem tensor transformed by the frozen grayscale rule;
- all 34 current BatchNorm modules incompatible with the pinned reference
  hyperparameters despite their state shapes matching; and
- three focused synthetic tests passing, including grayscale stem response
  equivalence and byte-identical B0/P2 mapped initial states.

Decision: `SHAPE_MAPPING_GO_EXECUTION_BLOCKED`.  The existing class is
`NO_GO` for this ImageNet arm until an isolated reference-BatchNorm constructor
exists and passes the same audit.  Exact weight SHA-256 and compatible-use
record remain action-time blockers.  No weight body was downloaded, no package
was installed, no model was trained, no test data or current fold result was
read, and no running output was touched.
