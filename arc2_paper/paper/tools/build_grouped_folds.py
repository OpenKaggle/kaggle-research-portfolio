#!/usr/bin/env python3
"""Build deterministic, leakage-resistant ARC task folds.

Exact groups are invariant to a global D4 transform, a global color relabeling,
and (for tasks with at most five demonstrations) demonstration order. A second,
object-centric signature ignores absolute component position. Small collisions
under that stronger abstraction are grouped conservatively; large collisions
are emitted for review instead of being merged silently.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
from collections import Counter, defaultdict, deque
from pathlib import Path


SEED = "arc2026-paper-grouped-folds-v1"
FOLD_COUNT = 5
MAX_OBJECT_COLLISION = 4
ARC1_COMMIT = "399030444e0ab0cc8b4e199870fb20b863846f34"
ARC2_COMMIT = "f3283f727488ad98fe575ea6a5ac981e4a188e49"


def d4(grid: list[list[int]], variant: int) -> list[list[int]]:
    value = [list(row) for row in grid]
    if variant >= 4:
        value = [list(reversed(row)) for row in value]
        variant -= 4
    for _ in range(variant):
        value = [list(row) for row in zip(*value[::-1])]
    return value


def color_normalize(payload: dict) -> dict:
    mapping: dict[int, int] = {}

    def visit(grid: list[list[int]]) -> list[list[int]]:
        result = []
        for row in grid:
            normalized_row = []
            for value in row:
                if value not in mapping:
                    mapping[value] = len(mapping)
                normalized_row.append(mapping[value])
            result.append(normalized_row)
        return result

    return {
        split: [
            {key: visit(pair[key]) for key in ("input", "output")}
            for pair in payload[split]
        ]
        for split in ("train", "test")
    }


def exact_fingerprint(task: dict) -> str:
    train_count = len(task["train"])
    if train_count <= 5:
        train_orders = itertools.permutations(range(train_count))
    else:
        forward = tuple(range(train_count))
        train_orders = (forward, tuple(reversed(forward)))

    orders = list(train_orders)
    encodings = []
    for variant in range(8):
        transformed_train = [
            {key: d4(pair[key], variant) for key in ("input", "output")}
            for pair in task["train"]
        ]
        transformed_test = [
            {key: d4(pair[key], variant) for key in ("input", "output")}
            for pair in task["test"]
        ]
        for order in orders:
            payload = {
                "train": [transformed_train[index] for index in order],
                "test": transformed_test,
            }
            encodings.append(
                json.dumps(color_normalize(payload), separators=(",", ":"), sort_keys=True)
            )
    canonical = min(encodings)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def binary_d4(mask: list[list[int]]) -> str:
    return min(
        json.dumps(d4(mask, variant), separators=(",", ":"))
        for variant in range(8)
    )


def components(grid: list[list[int]], color: int) -> list[tuple]:
    height, width = len(grid), len(grid[0])
    unseen = {(r, c) for r in range(height) for c in range(width) if grid[r][c] == color}
    found = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        queue = deque([start])
        cells = [start]
        while queue:
            row, col = queue.popleft()
            for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
                    cells.append(neighbor)
        rows = [row for row, _ in cells]
        cols = [col for _, col in cells]
        top, bottom = min(rows), max(rows)
        left, right = min(cols), max(cols)
        cell_set = set(cells)
        mask = [
            [1 if (row, col) in cell_set else 0 for col in range(left, right + 1)]
            for row in range(top, bottom + 1)
        ]
        touches = sum(
            (
                top == 0,
                bottom == height - 1,
                left == 0,
                right == width - 1,
            )
        )
        found.append((len(cells), bottom - top + 1, right - left + 1, touches, binary_d4(mask)))
    return sorted(found)


def object_grid_signature(grid: list[list[int]]) -> tuple:
    colors = sorted({value for row in grid for value in row})
    background_candidates = []
    for background in colors:
        color_groups = []
        for color in colors:
            if color == background:
                continue
            color_groups.append(tuple(components(grid, color)))
        background_candidates.append((len(colors), tuple(sorted(color_groups))))
    return min(background_candidates)


def shape_relation(input_grid: list[list[int]], output_grid: list[list[int]]) -> tuple:
    ih, iw = len(input_grid), len(input_grid[0])
    oh, ow = len(output_grid), len(output_grid[0])
    relation = (
        "same" if (ih, iw) == (oh, ow)
        else "crop" if oh <= ih and ow <= iw
        else "expand" if oh >= ih and ow >= iw
        else "mixed"
    )
    return relation, oh - ih, ow - iw


def object_fingerprint(task: dict) -> str:
    train_rows = sorted(
        (
            shape_relation(pair["input"], pair["output"]),
            object_grid_signature(pair["input"]),
            object_grid_signature(pair["output"]),
        )
        for pair in task["train"]
    )
    test_rows = sorted(
        (
            shape_relation(pair["input"], pair["output"]),
            object_grid_signature(pair["input"]),
            object_grid_signature(pair["output"]),
        )
        for pair in task["test"]
    )
    encoded = json.dumps(
        {"train": train_rows, "test": test_rows},
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cells(grid: list[list[int]]) -> int:
    return len(grid) * len(grid[0])


def work(task: dict) -> int:
    train = sum(cells(pair["input"]) + cells(pair["output"]) for pair in task["train"])
    test = sum(cells(pair["input"]) for pair in task["test"])
    return 16 * train + 8 * test


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def tree_hash(paths: list[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    here = Path(__file__).resolve()
    paper_root = here.parents[1]
    arc_root = paper_root.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=arc_root / "official/ARC-AGI-2/data/training",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=paper_root / "manifests/grouped_folds_v1.json",
    )
    parser.add_argument(
        "--arc1-dir",
        type=Path,
        required=True,
        help="pinned checkout of https://github.com/fchollet/ARC-AGI",
    )
    args = parser.parse_args()

    paths = sorted(args.data_dir.glob("*.json"))
    tasks = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in paths}
    if len(tasks) != 1000:
        raise RuntimeError(f"expected 1000 training tasks, found {len(tasks)}")

    arc1_training = {path.stem for path in (args.arc1_dir / "data/training").glob("*.json")}
    arc1_evaluation = {path.stem for path in (args.arc1_dir / "data/evaluation").glob("*.json")}
    if len(arc1_training) != 400 or len(arc1_evaluation) != 400:
        raise RuntimeError(
            f"expected ARC-AGI-1 400/400 tasks, found {len(arc1_training)}/{len(arc1_evaluation)}"
        )
    if arc1_training & arc1_evaluation:
        raise RuntimeError("ARC-AGI-1 training/evaluation task IDs overlap")
    arc1_commit = subprocess.run(
        ["git", "-C", str(args.arc1_dir), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if arc1_commit != ARC1_COMMIT:
        raise RuntimeError(
            f"ARC-AGI-1 checkout must be pinned at {ARC1_COMMIT}, found {arc1_commit}"
        )
    provenance = {
        task_id: (
            "arc_agi_1_training"
            if task_id in arc1_training
            else "arc_agi_1_evaluation"
            if task_id in arc1_evaluation
            else "not_in_arc_agi_1_pin"
        )
        for task_id in tasks
    }
    provenance_totals = Counter(provenance.values())
    if sum(provenance_totals.values()) != len(tasks):
        raise RuntimeError(f"unexpected provenance counts: {provenance_totals}")

    exact_by_hash: dict[str, list[str]] = defaultdict(list)
    object_by_hash: dict[str, list[str]] = defaultdict(list)
    task_fingerprints = {}
    for task_id, task in tasks.items():
        exact = exact_fingerprint(task)
        objects = object_fingerprint(task)
        task_fingerprints[task_id] = {"exact": exact, "objects": objects}
        exact_by_hash[exact].append(task_id)
        object_by_hash[objects].append(task_id)

    union = UnionFind(sorted(tasks))
    basis_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for basis, clusters in (("d4_color_demo_exact", exact_by_hash),):
        for ids in clusters.values():
            for left in ids:
                for right in ids:
                    if left < right:
                        union.union(left, right)
                        basis_by_pair[(left, right)].add(basis)

    object_review = []
    for fingerprint, ids in object_by_hash.items():
        if len(ids) < 2:
            continue
        if len(ids) <= MAX_OBJECT_COLLISION:
            for left in ids:
                for right in ids:
                    if left < right:
                        union.union(left, right)
                        basis_by_pair[(left, right)].add("object_component_signature")
        else:
            object_review.append({"fingerprint": fingerprint, "task_ids": sorted(ids)})

    grouped: dict[str, list[str]] = defaultdict(list)
    for task_id in sorted(tasks):
        grouped[union.find(task_id)].append(task_id)

    ordered_work = sorted(tasks, key=lambda task_id: (work(tasks[task_id]), task_id))
    quartile = {}
    for index, task_id in enumerate(ordered_work):
        quartile[task_id] = min(4, index * 4 // len(ordered_work) + 1)

    group_rows = []
    for task_ids in grouped.values():
        group_id = hashlib.sha256((SEED + ":" + ",".join(task_ids)).encode()).hexdigest()[:16]
        pair_bases = sorted(
            {
                basis
                for pair, bases in basis_by_pair.items()
                if pair[0] in task_ids and pair[1] in task_ids
                for basis in bases
            }
        )
        q_counts = Counter(quartile[task_id] for task_id in task_ids)
        provenance_counts = Counter(provenance[task_id] for task_id in task_ids)
        group_rows.append(
            {
                "group_id": group_id,
                "task_ids": sorted(task_ids),
                "size": len(task_ids),
                "basis": pair_bases or ["singleton"],
                "quartile_counts": {str(key): q_counts.get(key, 0) for key in range(1, 5)},
                "provenance_counts": dict(sorted(provenance_counts.items())),
                "work": sum(work(tasks[task_id]) for task_id in task_ids),
            }
        )

    group_rows.sort(
        key=lambda row: (
            -row["size"],
            -row["work"],
            hashlib.sha256((SEED + ":" + row["group_id"]).encode()).hexdigest(),
        )
    )
    target_tasks = len(tasks) / FOLD_COUNT
    target_quartile = len(tasks) / 4 / FOLD_COUNT
    target_work = sum(work(task) for task in tasks.values()) / FOLD_COUNT
    folds = [
        {
            "fold": index,
            "task_ids": [],
            "group_ids": [],
            "quartile_counts": Counter(),
            "provenance_counts": Counter(),
            "work": 0,
        }
        for index in range(FOLD_COUNT)
    ]
    for group in group_rows:
        def incremental_cost(fold: dict) -> tuple:
            before = (len(fold["task_ids"]) - target_tasks) ** 2
            after = (len(fold["task_ids"]) + group["size"] - target_tasks) ** 2
            q_delta = 0.0
            for q in range(1, 5):
                current = fold["quartile_counts"][q]
                addition = group["quartile_counts"][str(q)]
                q_delta += (current + addition - target_quartile) ** 2 - (current - target_quartile) ** 2
            provenance_delta = 0.0
            for source, total in provenance_totals.items():
                target = total / FOLD_COUNT
                current = fold["provenance_counts"][source]
                addition = group["provenance_counts"].get(source, 0)
                provenance_delta += (current + addition - target) ** 2 - (current - target) ** 2
            work_delta = (
                ((fold["work"] + group["work"] - target_work) / target_work) ** 2
                - ((fold["work"] - target_work) / target_work) ** 2
            )
            return (
                after - before + 2 * q_delta + 2 * provenance_delta + 25 * work_delta,
                fold["fold"],
            )

        chosen = min(folds, key=incremental_cost)
        chosen["task_ids"].extend(group["task_ids"])
        chosen["group_ids"].append(group["group_id"])
        chosen["work"] += group["work"]
        for q in range(1, 5):
            chosen["quartile_counts"][q] += group["quartile_counts"][str(q)]
        for source, count in group["provenance_counts"].items():
            chosen["provenance_counts"][source] += count

    task_to_fold = {}
    for fold in folds:
        fold["task_ids"].sort()
        fold["group_ids"].sort()
        fold["quartile_counts"] = {
            str(q): fold["quartile_counts"][q] for q in range(1, 5)
        }
        fold["provenance_counts"] = dict(sorted(fold["provenance_counts"].items()))
        fold["task_count"] = len(fold["task_ids"])
        for task_id in fold["task_ids"]:
            if task_id in task_to_fold:
                raise RuntimeError(f"task assigned twice: {task_id}")
            task_to_fold[task_id] = fold["fold"]

    if set(task_to_fold) != set(tasks):
        raise RuntimeError("folds do not cover every task")
    for group in group_rows:
        assigned = {task_to_fold[task_id] for task_id in group["task_ids"]}
        if len(assigned) != 1:
            raise RuntimeError(f"group split across folds: {group['group_id']}")

    try:
        manifest_data_path = str(args.data_dir.resolve().relative_to(arc_root.resolve()))
    except ValueError:
        manifest_data_path = str(args.data_dir.resolve())

    manifest = {
        "version": 1,
        "seed": SEED,
        "fold_count": FOLD_COUNT,
        "dataset": {
            "path": manifest_data_path,
            "tasks": len(tasks),
            "tree_sha256": tree_hash(paths, args.data_dir),
            "upstream_commit": ARC2_COMMIT,
            "arc_agi_1_provenance_commit": arc1_commit,
            "provenance_counts": dict(sorted(provenance_totals.items())),
            "arc_agi_1_ids_absent_from_arc_agi_2_training": {
                "training": len(arc1_training - set(tasks)),
                "evaluation": len(arc1_evaluation - set(tasks)),
            },
        },
        "grouping": {
            "exact": "global D4 + global first-occurrence color relabel + demo-order canonicalization (full through five demos; forward/reverse above five)",
            "object": "color-agnostic 4-connected component mask/area/bbox/border signature with input-output shape relation",
            "object_collision_merge_limit": MAX_OBJECT_COLLISION,
            "large_object_collisions": object_review,
        },
        "summary": {
            "groups": len(group_rows),
            "non_singleton_groups": sum(row["size"] > 1 for row in group_rows),
            "largest_group": max(row["size"] for row in group_rows),
            "large_object_review_clusters": len(object_review),
        },
        "groups": sorted(group_rows, key=lambda row: row["group_id"]),
        "folds": folds,
        "task_fingerprints": {
            task_id: {
                **task_fingerprints[task_id],
                "provenance": provenance[task_id],
                "work_quartile": quartile[task_id],
            }
            for task_id in sorted(tasks)
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": manifest["summary"], "folds": [
        {
            key: fold[key]
            for key in ("fold", "task_count", "quartile_counts", "provenance_counts", "work")
        }
        for fold in folds
    ]}, indent=2))


if __name__ == "__main__":
    main()
