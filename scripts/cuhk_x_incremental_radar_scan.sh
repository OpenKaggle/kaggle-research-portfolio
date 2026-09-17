#!/usr/bin/env bash
# Read-only CUHK-X radar. It never joins, accepts terms, downloads competition
# files, executes kernels, submits predictions, or posts messages.

set -u

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"
report_root="$repo_root/reports/cuhk_x_incremental_radar_snapshots"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
snapshot_dir="$report_root/$stamp"
manifest="$snapshot_dir/manifest.tsv"

mkdir -p "$snapshot_dir/raw" "$snapshot_dir/normalized" "$snapshot_dir/stderr"
printf 'source_id\ttype\turl\tstatus\tsha256\tchecked_utc\n' > "$manifest"

if [ -x "$repo_root/.venv/bin/kaggle" ]; then
  kaggle_cli="$repo_root/.venv/bin/kaggle"
else
  kaggle_cli="$(command -v kaggle || true)"
fi

hash_file() {
  local input_file="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$input_file" | awk '{print $1}'
  else
    sha256sum "$input_file" | awk '{print $1}'
  fi
}

normalize_file() {
  local input_file="$1"
  LC_ALL=C sed -E \
    -e '/^Next Page Token:/d' \
    -e '/^Warning: --page-size/d' \
    -e 's/[[:space:]]+$//' \
    "$input_file"
}

capture() {
  local source_id="$1"
  local source_type="$2"
  local source_url="$3"
  local safe_id raw_file normalized_file stderr_file checked_utc status digest
  shift 3
  safe_id="$(printf '%s' "$source_id" | tr -c 'A-Za-z0-9._-' '_')"
  raw_file="$snapshot_dir/raw/$safe_id.txt"
  normalized_file="$snapshot_dir/normalized/$safe_id.txt"
  stderr_file="$snapshot_dir/stderr/$safe_id.log"
  checked_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if "$@" >"$raw_file" 2>"$stderr_file"; then
    status="OK"
  else
    status="ERROR"
  fi
  normalize_file "$raw_file" > "$normalized_file"
  digest="$(hash_file "$normalized_file")"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$source_id" "$source_type" "$source_url" "$status" "$digest" "$checked_utc" >> "$manifest"
}

capture_kaggle_track() {
  local track="$1"
  local slug="$2"
  local base_url="https://www.kaggle.com/competitions/$slug"
  local topics_file topic_id

  capture "kaggle_${track}_list" "competition_status" "$base_url" \
    "$kaggle_cli" competitions list --search "$slug" --page-size 100 -v
  capture "kaggle_${track}_pages" "rules_description_evaluation" "$base_url" \
    "$kaggle_cli" competitions pages "$slug" --content -v
  capture "kaggle_${track}_files" "data_file_metadata_only" "$base_url/data" \
    "$kaggle_cli" competitions files "$slug" --page-size 100 -v
  capture "kaggle_${track}_topics" "discussion_index" "$base_url/discussion" \
    "$kaggle_cli" competitions topics list "$slug" -v
  capture "kaggle_${track}_code" "code_index" "$base_url/code" \
    "$kaggle_cli" kernels list --competition "$slug" --page-size 100 --sort-by hotness -v
  capture "kaggle_${track}_leaderboard" "leaderboard_snapshot_no_inference" "$base_url/leaderboard" \
    "$kaggle_cli" competitions leaderboard "$slug" --show --page-size 400 -v
  capture "kaggle_${track}_submissions" "own_submission_receipts" "$base_url/submissions" \
    "$kaggle_cli" competitions submissions "$slug" --page-size 100 -v

  topics_file="$snapshot_dir/normalized/kaggle_${track}_topics.txt"
  if [ -s "$topics_file" ]; then
    LC_ALL=C grep -Eo '[0-9]{6}' "$topics_file" | sort -u | while IFS= read -r topic_id; do
      capture "kaggle_${track}_topic_${topic_id}" "discussion_full_text" "$base_url/discussion/$topic_id" \
        "$kaggle_cli" competitions topics show "$slug/$topic_id"
    done
  fi
}

if [ -n "$kaggle_cli" ]; then
  capture_kaggle_track "large" "cuhk-x-competition-large-model-track"
  capture_kaggle_track "small" "cuhk-x-competition-small-model-track"
else
  printf 'kaggle_cli\ttool_availability\tlocal://kaggle-cli\tERROR\tNOT_AVAILABLE\t%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$manifest"
fi

capture "challenge_site" "official_challenge_site" "https://openaiotlab.github.io/CUHK-X-Challenge/" \
  curl -fsSL --max-time 30 "https://openaiotlab.github.io/CUHK-X-Challenge/"
capture "cuhkx_project_site" "official_project_site" "https://openaiotlab.github.io/CUHK-X/" \
  curl -fsSL --max-time 30 "https://openaiotlab.github.io/CUHK-X/"
capture "cuhkx_arxiv" "primary_paper" "https://arxiv.org/abs/2512.07136" \
  curl -fsSL --max-time 30 "https://arxiv.org/abs/2512.07136"
capture "cuhkx_acm" "publisher_paper_page" "https://doi.org/10.1145/3745756.3809209" \
  curl -fsSL --max-time 30 "https://doi.org/10.1145/3745756.3809209"

capture_github_repo() {
  local source_id="$1"
  local repo="$2"
  capture "${source_id}_repo" "github_repo_metadata" "https://github.com/$repo" \
    gh api "repos/$repo"
  capture "${source_id}_head" "github_commits" "https://github.com/$repo/commits" \
    gh api "repos/$repo/commits?per_page=100"
  capture "${source_id}_releases" "github_releases" "https://github.com/$repo/releases" \
    gh api "repos/$repo/releases?per_page=100"
  capture "${source_id}_issues" "github_issues" "https://github.com/$repo/issues" \
    gh api "repos/$repo/issues?state=all&per_page=100"
}

capture_github_repo "challenge_repo" "openaiotlab/CUHK-X-Challenge"
capture_github_repo "cuhkx_repo" "openaiotlab/CUHK-X"
capture "challenge_repo_tree" "official_github_file_tree" "https://github.com/openaiotlab/CUHK-X-Challenge/tree/main" \
  gh api "repos/openaiotlab/CUHK-X-Challenge/git/trees/main?recursive=1"
capture "challenge_repo_index" "official_challenge_source" "https://github.com/openaiotlab/CUHK-X-Challenge/blob/main/index.html" \
  gh api "repos/openaiotlab/CUHK-X-Challenge/contents/index.html?ref=main"
capture "challenge_repo_leaderboard_cache" "official_generated_leaderboard_cache" "https://github.com/openaiotlab/CUHK-X-Challenge/blob/main/leaderboard_data.json" \
  gh api "repos/openaiotlab/CUHK-X-Challenge/contents/leaderboard_data.json?ref=main"
capture "cuhkx_repo_tree" "official_github_file_tree" "https://github.com/openaiotlab/CUHK-X/tree/main" \
  gh api "repos/openaiotlab/CUHK-X/git/trees/main?recursive=1"
for source_path in README.md LICENSE Small_Model_Track/README.md Large_Model_Track/README.md
do
  source_id="$(printf '%s' "$source_path" | tr '/.' '__')"
  capture "cuhkx_${source_id}" "official_repository_file" "https://github.com/openaiotlab/CUHK-X/blob/main/$source_path" \
    gh api "repos/openaiotlab/CUHK-X/contents/$source_path?ref=main"
done

for repo in \
  "mit-han-lab/temporal-shift-module" \
  "statist-bhfz/kaggle_cmi_1st_place_solution" \
  "AIFrontierLab/HAROOD" \
  "facebookresearch/DomainBed" \
  "QwenLM/Qwen3-VL" \
  "sangminwoo/ActionMAE" \
  "facebookresearch/ImageBind" \
  "facebookresearch/imu2clip"
do
  repo_id="$(printf '%s' "$repo" | tr '/-' '__')"
  capture "adjacent_${repo_id}" "adjacent_primary_repository" "https://github.com/$repo" \
    gh api "repos/$repo/commits?per_page=1"
done

for arxiv_id in 2606.01631 2410.10624 2410.00003 2211.13916
do
  capture "adjacent_arxiv_${arxiv_id}" "adjacent_primary_paper" "https://arxiv.org/abs/$arxiv_id" \
    curl -fsSL --max-time 30 "https://arxiv.org/abs/$arxiv_id"
done

capture "adjacent_cvf_cvpr2025" "adjacent_primary_conference_index" "https://openaccess.thecvf.com/CVPR2025" \
  curl -fsSL --max-time 30 "https://openaccess.thecvf.com/CVPR2025"
capture "adjacent_cvf_cvpr2021" "adjacent_primary_conference_index" "https://openaccess.thecvf.com/CVPR2021" \
  curl -fsSL --max-time 30 "https://openaccess.thecvf.com/CVPR2021"
capture "adjacent_cvf_cvprw2025" "adjacent_primary_conference_index" "https://openaccess.thecvf.com/CVPR2025_workshops" \
  curl -fsSL --max-time 30 "https://openaccess.thecvf.com/CVPR2025_workshops"

previous_manifest="$(find "$report_root" -mindepth 2 -maxdepth 2 -name manifest.tsv ! -path "$manifest" -print | sort | tail -1)"
if [ -n "$previous_manifest" ]; then
  cut -f1-5 "$previous_manifest" > "$snapshot_dir/previous.comparable.tsv"
  cut -f1-5 "$manifest" > "$snapshot_dir/current.comparable.tsv"
  diff -u "$snapshot_dir/previous.comparable.tsv" "$snapshot_dir/current.comparable.tsv" \
    > "$snapshot_dir/delta.diff" || true
else
  printf 'No previous manifest found; this snapshot is the rescan baseline.\n' > "$snapshot_dir/delta.diff"
fi

hash_file "$manifest" > "$snapshot_dir/manifest.sha256"
printf '%s\n' "$snapshot_dir"
