# CUHK-X Small Model Track: official discussion rule clarification

## Superseding status note (2026-09-11 12:43 CST)

The official challenge registration described as unverified in section 5 was
subsequently completed and confirmed for solo team `Jiayi Du`, both Small and
Large tracks, affiliation `Stiftung Louisenlund`, country/region `Germany`,
with no faculty advisor. See `2026-09-11_official_team_registration.md`.

The host later clarified in official discussion 740749 that INT8 and similar
quantization are permitted and encouraged. This does not relax the packaging
rule: every learned weight loaded for inference, including ensembles, must be
contained in one on-disk checkpoint strictly smaller than 100 MB. Operationally
the FP32 model must pass its frozen offline gate before quantization; an INT8
artifact must then lose no more than 0.5 percentage point offline.

Official thread:
https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/740749

Checked: `2026-09-11T03:24:05Z` / `2026-09-11T11:24:06+08:00`.

This receipt corrects the earlier conservative interpretation of the phrase
“No LLMs for development.” It does not delete or rewrite the historical audit
files. Where they conflict on this point, the competition host's later,
specific Kaggle discussion answers below control the operating policy.

## 1. AI coding assistants are allowed

Official discussion:
https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724942

Topic: **Clarification on “No LLMs for development”**. The response is by
`Gvine15`, marked **Competition Host**.

Host clarification:

- The restriction concerns the submitted model, not the tools used to develop
  it.
- ChatGPT, Codex, Copilot, Cursor, and similar AI coding assistants are allowed
  for writing and debugging code.
- The submitted Small Model inference model cannot be an LLM.
- The final checkpoint used for inference must be a permitted small
  architecture and must be under 100 MB on disk.

Corrected operating boundary:

- Codex may write and debug experiment code.
- No LLM or closed-source model/API may be a dependency of final inference.
- No LLM/API labeling of training data, and no manual or automated labeling of
  competition test clips from their contents.
- All learned inference weights must be contained in one checkpoint. Use a
  conservative hard gate of `<100,000,000` bytes before any candidate can be
  submitted.

## 2. External data and pretrained models are allowed with conditions

Official discussion:
https://www.kaggle.com/competitions/cuhk-x-competition-small-model-track/discussion/724404

Topic: **Are external datasets allowed for training?**. The response is by
`Gvine15`, marked **Competition Host**.

Host clarification:

- Additional public datasets are permitted if they are freely and publicly
  accessible so winning solutions remain reproducible.
- Every external dataset must be disclosed in the final write-up.
- The same requirements apply to pretrained models: public availability and
  disclosure.
- A request-form dataset is allowed only when the form is open to anyone with
  no restrictive eligibility. The final report must document both the access
  procedure and how the data was used.

Every external component therefore needs a provenance record containing its
public URL, version/date, content hash where available, license, access steps,
and exact use in training. An experiment does not pass the compliance gate if
any of these fields are missing.

## 3. Validation and submission gates

No new model submission may be made unless all gates pass:

1. **Non-LLM inference:** the executable inference graph contains no LLM,
   closed-source API, or undisclosed learned component.
2. **Single checkpoint:** every learned inference weight is inside one file,
   and its measured on-disk size is `<100,000,000` bytes; record SHA-256.
3. **Subject-disjoint validation:** no subject appears in both training and
   validation.
4. **Clip-disjoint validation:** no semantic clip or frame derived from that
   clip crosses the split boundary.
5. **License/provenance:** every code, dataset, and pretrained-model dependency
   has a recorded source and compatible use right; all external data/model use
   is report-ready.
6. **Promotion gate:** a candidate needs a predeclared offline improvement over
   its control on the same frozen split. A failed gate is recorded but not
   submitted.

The official published cross-subject test is users `10–11` and `25–26`, while
the released training subjects are users `1–9` and `16–24`. Internal folds must
be made only from the 18 training subjects and remain subject- and clip-disjoint.

## 4. Current Kaggle administrative state

Live authenticated checks:

- Rules accepted: yes.
- Team: `Jiayi Du`; solo member `Jiayi Du` / `jahyee`; team leader.
- Kaggle final deadline: `2026-09-15 15:55:00 UTC` =
  `2026-09-15 23:55:00 Asia/Shanghai`.
- Existing smoke submission: ID `56107602`, `COMPLETE`, public score `0.03482`.
- Final-submission selection: `0/2` manually selected. Kaggle labels the smoke
  submission an auto-selection candidate and states that, when fewer than two
  are manually selected, it automatically selects the best-scoring successful
  submissions. No selection was changed during this audit.

The smoke submission remains preserved as the valid-participation proof. No
new model submission was made.

## 5. Official website registration status

Official registration page:
https://openaiotlab.github.io/CUHK-X-Challenge/#registration

The form is currently open. In the authenticated browser used for this audit,
all form fields were blank, both track checkboxes and the required agreement
checkbox were unchecked, and no local/session-storage receipt existed. This
does not prove that a submission from another browser or session never
occurred, but there is no verifiable registration receipt in the campaign.

To complete or prove registration, the participant must personally provide or
confirm:

- Team Name: must exactly match Kaggle, `Jiayi Du`.
- Contact Email.
- Affiliation.
- Country / Region.
- Track: Small Model Track (HAR).
- Member 1 / team-leader legal or preferred name.
- Optional faculty advisor, if applicable.
- Required agreement to the competition rules and Kaggle Terms of Service.

No identity field was guessed, entered, or transmitted, and no legal agreement
was accepted on the participant's behalf.

## 6. License boundary

The current official repository remains unchanged upstream and locally at
commit `df03910a6960db5af9179e370e130bf61d9616d0`. Its `LICENSE` SHA-256 remains
`f91f3c1aee1491a919a88cf2cdcd247532ef0d21b2b412882163ccac5ea06a03`.

The Kaggle rules require a winning Submission and its source code to be
licensed under Apache 2.0 without limiting commercial use. They separately
permit incompatible-license input data or pretrained models if clearly
identified. The CUHK-X License v2.0, however, applies a non-commercial grant to
the organizer's source code as well as the dataset. The rules do not expressly
extend the data/pretrained-model exception to organizer source code.

Operational consequence: original participant-authored code can be prepared
for Apache 2.0, and CUHK-X data can remain a separately identified input under
its own terms. Code derived from the organizer repository remains
**reference-only** until the organizer provides written compatibility guidance
or permission. This is a compliance risk assessment, not a legal opinion.

## 7. Top-15 / verification package checklist

The official challenge site says Top-15 teams are notified at the leaderboard
freeze and must upload code plus checkpoint within 48 hours. A separate detail
on the same site lists `2026-09-22 23:59 UTC`. Because these statements differ,
use the earlier operational deadline: **within 48 hours of the organizer's
notification or leaderboard freeze**, unless the organizer confirms otherwise
in writing.

Prepare, but do not transmit before a Top-15 notice:

- Complete training code.
- Complete inference code.
- Single final checkpoint at `checkpoints/model.pth`, `<100,000,000` bytes,
  with SHA-256 and parameter/model-size audit.
- `inference.sh` accepting the organizer data directory and producing the
  exact Kaggle `path,prediction` schema.
- Reproduction `README` with commands, seeds, frozen subject/clip split,
  preprocessing, hyperparameters, runtimes, expected metrics, and hardware.
- Required computational-environment description and exact dependency locks.
- Signed honor declaration — must be signed by the participant, never by the
  assistant.
- External dataset/pretrained-model inventory with URLs, access procedure,
  versions, licenses, hashes, and usage disclosure.
- Third-party code/license inventory and confirmation that participant-owned
  deliverable code can be licensed as required.

Verification then includes a recorded Zoom run on newly released seen and
unseen subjects, an organizer reproduction, and a disqualification threshold
when the accuracy gap exceeds 10% relative to the private leaderboard score.
