# Official visual data download status

Recorded: 2026-09-08 22:58 UTC / 2026-09-09 06:58 BJT

## Official Google Drive inventory

The organizer-linked Google Drive folders expose these files:

| File | Google Drive ID | Expected bytes |
|---|---|---:|
| `HARn.zip` | `1GuSzwNvCQmhyv_qOaNyNjYeme_Y3ZS2r` | 1,956,322,919 |
| `HAU.zip` | `10h_RRoxwcoJubTrXhrYxlZn_7_mrd06t` | 3,674,779,437 |
| `large_model_track_test.zip` | `1JFG1tTsfzZR84XSwZ1GB6MkXj9UP8opw` | 1,994,984,736 |

The inventory sizes match the public Hugging Face repository metadata. No
Hugging Face file was downloaded because that mirror requires authentication
and acceptance of contact-information sharing.

## Google quota behavior

- Unbounded downloads returned a 2,009-byte HTML `Quota exceeded` page, which
  was rejected and deleted rather than treated as a ZIP.
- Bounded byte ranges returned correct ZIP bytes for HARn and HAU initially.
- The verified range downloader stopped cleanly when Google changed a later
  HARn range to an HTML quota response.
- Current HARn verified contiguous prefix: `603980800 / 1956322919` bytes
  (30.9%).
- Incomplete files are never hashed or treated as valid datasets.

Resume command after quota recovery:

```bash
python scripts/range_download.py \
  --url 'https://drive.usercontent.google.com/download?id=1GuSzwNvCQmhyv_qOaNyNjYeme_Y3ZS2r&export=download&confirm=t' \
  --output data/raw/media/HARn.zip \
  --expected-size 1956322919 \
  --chunk-mib 32
```

After completion, run a full ZIP integrity test and SHA-256 before extraction.
