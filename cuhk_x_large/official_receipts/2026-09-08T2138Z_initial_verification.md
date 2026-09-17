# Initial official verification receipt

Verified at 2026-09-08 21:38 UTC / 2026-09-09 05:38 Beijing time.

## Entry and deadline

- Official competition: `cuhk-x-competition-large-model-track`
- Kaggle account before join: `userHasEntered=False`
- Kaggle rules accepted in the official browser UI on 2026-09-08 UTC.
- Post-join UI state: `Submit Prediction`, `Team`, and `Submissions` tabs visible; toast read `Rules accepted. Good luck!`
- Kaggle team name: `Jiayi Du`; one member, account `jahyee`, team leader.
- Official final deadline / leaderboard freeze: 2026-09-15 15:55 UTC = 2026-09-15 23:55 Beijing time.
- Team merger lock: official challenge website says seven days before the submission deadline. At verification time the Kaggle team UI still permitted two invitations, but no team change was made.

## Eligibility, prizes, and later deliverables

- Open to students, researchers, and industry teams worldwide; cross-institution and international teams permitted.
- CUHK AIoT Lab members/direct collaborators may participate but are prize-ineligible. This identity condition is not inferable from local data and has not been asserted.
- Kaggle private-leaderboard Top 15 advances to Sep 16–30 selection/verification; Top 6 advances to UbiComp 2026 finals on Oct 11 in Shanghai.
- Cash prizes are decided at the finals, not directly by Kaggle rank: USD 6,000 / 3,000 / 1,000.
- Top-15 package is due by 2026-09-22 23:59 UTC per the official challenge site: full code, checkpoint, `inference.sh`, README, and signed honor declaration.
- Verification includes a recorded Zoom inference run and organizer reproduction. An accuracy gap greater than 10% from the Kaggle private score is disqualifying.
- Large Model Track permits pretrained models, LVLMs, closed-source APIs, and training-data pseudo-labeling. Test answers, manual test labeling, multi-accounting, and collusion are forbidden.

## External registration

- Official form was visibly open at verification time: <https://openaiotlab.github.io/CUHK-X-Challenge/#registration>
- It requires team name, contact email, affiliation, country/region, track selection, team member name(s), and acceptance of linked IP/competition terms. Faculty advisor is optional.
- The form was not submitted because the required real identity/contact values were not provided. The Kaggle team name to match exactly is `Jiayi Du`.

## Downloaded Kaggle package

The package contains metadata/QA CSVs only; it does not contain the referenced video/media files.

| File | Bytes | SHA-256 |
|---|---:|---|
| `cuhk-x-competition-large-model-track.zip` | 90,994 | `6a9dc7dd59c1bec120f4d408b911695e1592b81c10845dce3c1306a3cb876433` |
| `training_qa.csv` | 702,424 | `2509ed00f9305d552378618d8987559bdff7a4b56241c630ba99dc4051f535bc` |
| `test_qa.csv` | 136,860 | `d694c7abc5a003d5c9048098880f0f77716fae0eb18d1c9fe9330e4e987320a5` |
| `sample_submission.csv` | 9,144 | `456905af98ce5257042f3779982e5b48e0ea248fcdf38eb79c9dd3e4f88a0a38` |

Rows/schema:

- `training_qa.csv`: 4,087 rows; `qa_id,source,path,category,question,A,B,C,D,answer`
- `test_qa.csv`: 682 rows / 208 clips; `qa_id,source,path,category,question,A,B,C,D,prediction`
- `sample_submission.csv`: 682 rows; `qa_id,prediction`

Important: the Overview example calls the output field `answer`, but the downloaded sample and actual test file use `prediction`. Submission tooling follows the downloaded sample exactly.

## Data/license controls

- Competition data: non-commercial research/competition use only, not redistributable.
- Dataset access terms state that explicit written owner permission is required before accessing the full media dataset and that institutional ethics/IRB/REC requirements apply.
- Raw competition files are stored only under the ignored local directory `cuhk_x_large/data/raw/`.

Official sources:

- <https://www.kaggle.com/competitions/cuhk-x-competition-large-model-track>
- <https://www.kaggle.com/competitions/cuhk-x-competition-large-model-track/rules>
- <https://openaiotlab.github.io/CUHK-X-Challenge/>

