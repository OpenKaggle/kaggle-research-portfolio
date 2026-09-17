#!/usr/bin/env python3
"""Synthetic, label-boundary, and determinism checks for the typed-object family."""

from __future__ import annotations

import copy

from typed_object_correspondence import predictions_for_grid, solve_task, valid_grid


def example(
    height: int,
    width: int,
    top: int,
    left: int,
    noise: tuple[int, int] | None = None,
) -> dict:
    grid = [[0 for _ in range(width)] for _ in range(height)]
    for row in range(top, top + 2):
        for column in range(left, left + 2):
            grid[row][column] = 2
    if noise is not None:
        grid[noise[0]][noise[1]] = 8
    return {"input": grid, "output": [[2, 2], [2, 2]]}


def main() -> None:
    task = {
        "train": [
            example(6, 7, 1, 1),
            example(7, 6, 4, 3),
            example(8, 8, 2, 5),
        ],
        "test": [{"input": example(9, 7, 6, 1)["input"]}],
    }
    first, trace = solve_task(task)
    second, second_trace = solve_task(copy.deepcopy(task))
    assert first == [[[2, 2], [2, 2]]]
    assert first == second
    assert trace == second_trace
    assert trace["accepted"] is True
    assert all(row["unique_correct"] for row in trace["loo"])
    assert all(valid_grid(grid) for grid in first)

    spurious = {
        "train": [
            example(6, 7, 1, 1, (5, 6)),
            example(7, 6, 4, 3, (0, 0)),
            example(8, 8, 2, 5, (7, 1)),
        ],
        "test": [{"input": example(9, 7, 6, 1, (0, 6))["input"]}],
    }
    prediction, rejected = solve_task(spurious)
    assert prediction is None
    assert rejected["reason"] == "leave_one_demo_out_not_unique_and_exact"

    polluted = copy.deepcopy(task)
    polluted["test"][0]["output"] = [[2, 2], [2, 2]]
    prediction, rejected = solve_task(polluted)
    assert prediction is None
    assert rejected["reason"] == "test_output_or_extra_field_forbidden"

    one_demo = copy.deepcopy(task)
    one_demo["train"] = one_demo["train"][:1]
    prediction, rejected = solve_task(one_demo)
    assert prediction is None
    assert rejected["reason"] == "requires_at_least_two_demos_and_one_test"

    grid = task["train"][0]["input"]
    assert predictions_for_grid(grid) == predictions_for_grid(copy.deepcopy(grid))
    print("typed-object correspondence synthetic regression passed")


if __name__ == "__main__":
    main()
