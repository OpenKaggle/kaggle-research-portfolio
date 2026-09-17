# CUHK-X Small Model Track: class-mapping acquisition and schema audit

Audit completed: `2026-09-09T10:39:33Z` / `2026-09-09T18:39:33+08:00`.

## Live eligibility and deadline recheck

- The organizer challenge site still renders the team-registration form and says it is required for prize, announcement, certificate, and finals eligibility.
- The published eligibility remains open to students, researchers, and industry teams worldwide; AIoT Lab members and direct collaborators are ineligible for prizes.
- The form still requires identity fields that have not been supplied: contact email, affiliation, country/region, and team-leader name. No registration was submitted and no identity fields were invented.
- Kaggle's live competition listing still reports deadline `2026-09-15 15:55:00 UTC`, equal to `2026-09-15 23:55:00 Asia/Shanghai`; `userHasEntered=True` and submissions remain available.
- The existing submission remains `COMPLETE`: ID `56107602`, public score `0.03482`, private score unavailable.

## Official class mapping

- Public organizer-linked Google Drive file ID: `1P01HMoKSrkC-Lx3G_kkIZ-Q0ajHe77AG`.
- Local artifact: `../data/raw/class_mapping.csv`.
- Download endpoint: Google's public file-download endpoint; no Hugging Face gate was accepted and no contact information was disclosed.
- Transfer runtime: approximately 1.9 seconds.
- Size: 841 bytes; 41 lines including header.
- SHA-256: `09f5794978faedb2bb478f41de0bf8545bf346e2b49b85eabb9504e238d0b7cb`.
- MIME inspection: CSV text.

Schema validation passed:

- Exact header: `action_id,action_name` (CRLF line endings normalized during validation only; the downloaded bytes were not rewritten).
- Exactly 40 data rows.
- `action_id` values are unique and contiguous integers `0` through `39` in ascending order.
- Every `action_name` is non-empty and begins with its matching numeric ID.
- The ID domain exactly matches the Kaggle submission prediction range `0` through `39`.

This is a data-contract milestone only. No model code, labels, predictions, or test annotations were generated or modified.

## Current blocking state

- Organizer registration remains blocked solely on user-supplied identity fields.
- Local free space fell to about 31 GiB at the live recheck, below the 41.558 GiB compressed training split before extraction; the capacity guard remains in force.
- The pinned organizer repository is still clean and unchanged at `df03910a6960db5af9179e370e130bf61d9616d0` locally and upstream.

