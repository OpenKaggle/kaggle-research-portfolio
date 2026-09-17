#!/usr/bin/env python3
"""Fixed, demonstration-only typed-object correspondence solver family.

The program vocabulary is task-independent. A task is accepted only when all
programs fitting the visible demonstrations agree on each test output and the
same inference procedure uniquely reconstructs every held-out demonstration.
No test output is accepted by this module or used during selection.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Iterable


Grid = list[list[int]]
GridKey = tuple[tuple[int, ...], ...]
Point = tuple[int, int]


def valid_grid(grid: Any) -> bool:
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and isinstance(grid[0], list)
        and 1 <= len(grid[0]) <= 30
        and all(isinstance(row, list) and len(row) == len(grid[0]) for row in grid)
        and all(type(value) is int and 0 <= value <= 9 for row in grid for value in row)
    )


def grid_key(grid: Grid) -> GridKey:
    return tuple(tuple(row) for row in grid)


def copy_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]


def modal_color(grid: Grid) -> int:
    counts = Counter(value for row in grid for value in row)
    return min(counts, key=lambda color: (-counts[color], color))


@dataclass(frozen=True)
class Object:
    cells: tuple[tuple[int, int, int], ...]
    top: int
    bottom: int
    left: int
    right: int

    @property
    def area(self) -> int:
        return len(self.cells)

    @property
    def height(self) -> int:
        return self.bottom - self.top + 1

    @property
    def width(self) -> int:
        return self.right - self.left + 1

    @property
    def bbox_area(self) -> int:
        return self.height * self.width

    @property
    def density(self) -> Fraction:
        return Fraction(self.area, self.bbox_area)

    @property
    def colors(self) -> tuple[int, ...]:
        return tuple(sorted({color for _, _, color in self.cells}))

    @property
    def shape_signature(self) -> tuple[Point, ...]:
        return tuple(sorted((row - self.top, column - self.left) for row, column, _ in self.cells))

    @property
    def color_signature(self) -> tuple[int, ...]:
        return self.colors


def connected_objects(grid: Grid, connectivity: int, segmentation: str) -> list[Object]:
    background = modal_color(grid)
    height, width = len(grid), len(grid[0])
    neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        neighbors += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    seen: set[Point] = set()
    objects: list[Object] = []
    for start_row in range(height):
        for start_column in range(width):
            start = (start_row, start_column)
            start_color = grid[start_row][start_column]
            if start in seen or start_color == background:
                continue
            queue = [start]
            seen.add(start)
            cells: list[tuple[int, int, int]] = []
            cursor = 0
            while cursor < len(queue):
                row, column = queue[cursor]
                cursor += 1
                color = grid[row][column]
                cells.append((row, column, color))
                for delta_row, delta_column in neighbors:
                    neighbor = row + delta_row, column + delta_column
                    nr, nc = neighbor
                    if not (0 <= nr < height and 0 <= nc < width) or neighbor in seen:
                        continue
                    neighbor_color = grid[nr][nc]
                    connected = neighbor_color != background and (
                        segmentation == "foreground" or neighbor_color == start_color
                    )
                    if connected:
                        seen.add(neighbor)
                        queue.append(neighbor)
            rows = [row for row, _, _ in cells]
            columns = [column for _, column, _ in cells]
            objects.append(
                Object(
                    cells=tuple(sorted(cells)),
                    top=min(rows),
                    bottom=max(rows),
                    left=min(columns),
                    right=max(columns),
                )
            )
    return sorted(objects, key=lambda item: (item.top, item.left, item.bottom, item.right, item.cells))


def unique_extreme(
    objects: list[Object],
    metric: Callable[[Object], Any],
    maximize: bool,
) -> Object | None:
    if not objects:
        return None
    values = [metric(item) for item in objects]
    extreme = max(values) if maximize else min(values)
    selected = [item for item, value in zip(objects, values) if value == extreme]
    return selected[0] if len(selected) == 1 else None


def repeated_outlier(objects: list[Object], attribute: str) -> Object | None:
    if len(objects) < 3:
        return None
    signatures = [getattr(item, attribute) for item in objects]
    counts = Counter(signatures)
    repeated = [signature for signature, count in counts.items() if count > 1]
    outliers = [item for item, signature in zip(objects, signatures) if counts[signature] == 1]
    return outliers[0] if len(repeated) == 1 and len(outliers) == 1 else None


def select_object(name: str, objects: list[Object], grid: Grid) -> Object | None:
    selectors: dict[str, tuple[Callable[[Object], Any], bool]] = {
        "largest_area": (lambda item: item.area, True),
        "smallest_area": (lambda item: item.area, False),
        "largest_bbox": (lambda item: item.bbox_area, True),
        "smallest_bbox": (lambda item: item.bbox_area, False),
        "topmost": (lambda item: item.top, False),
        "bottommost": (lambda item: item.bottom, True),
        "leftmost": (lambda item: item.left, False),
        "rightmost": (lambda item: item.right, True),
        "densest": (lambda item: item.density, True),
        "sparsest": (lambda item: item.density, False),
        "most_colors": (lambda item: len(item.colors), True),
        "fewest_colors": (lambda item: len(item.colors), False),
    }
    if name == "only":
        return objects[0] if len(objects) == 1 else None
    if name == "shape_outlier":
        return repeated_outlier(objects, "shape_signature")
    if name == "color_outlier":
        return repeated_outlier(objects, "color_signature")
    if name in {"rarest_global_colors", "commonest_global_colors"}:
        counts = Counter(value for row in grid for value in row)
        return unique_extreme(
            objects,
            lambda item: sum(counts[color] for color in item.colors),
            name == "commonest_global_colors",
        )
    metric, maximize = selectors[name]
    return unique_extreme(objects, metric, maximize)


def spatial_transform(grid: Grid, name: str) -> Grid:
    if name == "identity":
        return copy_grid(grid)
    if name == "rotate90":
        return [list(row) for row in zip(*grid[::-1])]
    if name == "rotate180":
        return [row[::-1] for row in grid[::-1]]
    if name == "rotate270":
        return [list(row) for row in zip(*grid)][::-1]
    if name == "flip_horizontal":
        return [row[::-1] for row in grid]
    if name == "flip_vertical":
        return grid[::-1]
    if name == "transpose":
        return [list(row) for row in zip(*grid)]
    if name == "anti_transpose":
        return spatial_transform(spatial_transform(grid, "transpose"), "rotate180")
    raise ValueError(f"unknown spatial transform: {name}")


def scale(grid: Grid, factor: int) -> Grid | None:
    if len(grid) * factor > 30 or len(grid[0]) * factor > 30:
        return None
    result: Grid = []
    for row in grid:
        expanded = [value for value in row for _ in range(factor)]
        result.extend(expanded[:] for _ in range(factor))
    return result


def crop_object(grid: Grid, item: Object, selected_only: bool, recolor: int | None) -> Grid:
    background = modal_color(grid)
    if selected_only:
        result = [[background for _ in range(item.width)] for _ in range(item.height)]
    else:
        result = [row[item.left : item.right + 1] for row in grid[item.top : item.bottom + 1]]
    for row, column, color in item.cells:
        result[row - item.top][column - item.left] = color if recolor is None else recolor
    return result


@dataclass(frozen=True, order=True)
class Program:
    segmentation: str
    connectivity: int
    selector: str
    operation: str
    transform: str = "identity"
    scale_factor: int = 1
    recolor: int | None = None

    @property
    def program_id(self) -> str:
        color = "preserve" if self.recolor is None else str(self.recolor)
        return (
            f"{self.segmentation}:c{self.connectivity}:{self.selector}:{self.operation}:"
            f"{self.transform}:s{self.scale_factor}:r{color}"
        )


SEGMENTATIONS = ("monochrome", "foreground")
CONNECTIVITIES = (4, 8)
SELECTORS = (
    "only",
    "largest_area",
    "smallest_area",
    "largest_bbox",
    "smallest_bbox",
    "topmost",
    "bottommost",
    "leftmost",
    "rightmost",
    "densest",
    "sparsest",
    "most_colors",
    "fewest_colors",
    "shape_outlier",
    "color_outlier",
    "rarest_global_colors",
    "commonest_global_colors",
)
TRANSFORMS = (
    "identity",
    "rotate90",
    "rotate180",
    "rotate270",
    "flip_horizontal",
    "flip_vertical",
    "transpose",
    "anti_transpose",
)


def predictions_for_grid(grid: Grid) -> dict[Program, Grid]:
    if not valid_grid(grid):
        return {}
    background = modal_color(grid)
    predictions: dict[Program, Grid] = {}
    for segmentation in SEGMENTATIONS:
        for connectivity in CONNECTIVITIES:
            objects = connected_objects(grid, connectivity, segmentation)
            for selector in SELECTORS:
                item = select_object(selector, objects, grid)
                if item is None:
                    continue
                for operation, selected_only in (
                    ("crop_patch", False),
                    ("crop_selected", True),
                ):
                    for recolor in (None, *range(10)):
                        base = crop_object(grid, item, selected_only, recolor)
                        for transform in TRANSFORMS:
                            transformed = spatial_transform(base, transform)
                            for factor in (1, 2, 3):
                                output = scale(transformed, factor)
                                if output is None or not valid_grid(output):
                                    continue
                                program = Program(
                                    segmentation,
                                    connectivity,
                                    selector,
                                    operation,
                                    transform,
                                    factor,
                                    recolor,
                                )
                                predictions[program] = output

                isolated = [[background for _ in row] for row in grid]
                for row, column, color in item.cells:
                    isolated[row][column] = color
                predictions[
                    Program(segmentation, connectivity, selector, "isolate_canvas")
                ] = isolated

                erased = copy_grid(grid)
                for row, column, _ in item.cells:
                    erased[row][column] = background
                predictions[
                    Program(segmentation, connectivity, selector, "erase_selected")
                ] = erased

                for recolor in range(10):
                    recolored = copy_grid(grid)
                    for row, column, _ in item.cells:
                        recolored[row][column] = recolor
                    predictions[
                        Program(
                            segmentation,
                            connectivity,
                            selector,
                            "recolor_selected_canvas",
                            recolor=recolor,
                        )
                    ] = recolored
    return predictions


def common_programs(match_sets: Iterable[set[Program]]) -> set[Program]:
    iterator = iter(match_sets)
    try:
        result = set(next(iterator))
    except StopIteration:
        return set()
    for values in iterator:
        result.intersection_update(values)
    return result


def solve_task(task: dict[str, Any]) -> tuple[list[Grid] | None, dict[str, Any]]:
    train = task.get("train")
    tests = task.get("test")
    if not isinstance(train, list) or len(train) < 2 or not isinstance(tests, list) or not tests:
        return None, {"accepted": False, "reason": "requires_at_least_two_demos_and_one_test"}
    if any(set(example) != {"input", "output"} for example in train):
        return None, {"accepted": False, "reason": "invalid_training_example_fields"}
    if any(set(example) != {"input"} for example in tests):
        return None, {"accepted": False, "reason": "test_output_or_extra_field_forbidden"}
    if any(not valid_grid(example["input"]) or not valid_grid(example["output"]) for example in train):
        return None, {"accepted": False, "reason": "invalid_training_grid"}
    if any(not valid_grid(example["input"]) for example in tests):
        return None, {"accepted": False, "reason": "invalid_test_grid"}

    train_maps = [predictions_for_grid(example["input"]) for example in train]
    match_sets = [
        {
            program
            for program, prediction in predictions.items()
            if prediction == example["output"]
        }
        for example, predictions in zip(train, train_maps)
    ]
    full_programs = common_programs(match_sets)
    if not full_programs:
        return None, {"accepted": False, "reason": "no_all_demo_program"}

    loo_rows = []
    for heldout_index, heldout in enumerate(train):
        fold_programs = common_programs(
            match_sets[index] for index in range(len(train)) if index != heldout_index
        )
        missing = sum(program not in train_maps[heldout_index] for program in fold_programs)
        heldout_outputs = {
            grid_key(train_maps[heldout_index][program])
            for program in fold_programs
            if program in train_maps[heldout_index]
        }
        correct_key = grid_key(heldout["output"])
        loo_rows.append(
            {
                "heldout_index": heldout_index,
                "fold_programs": len(fold_programs),
                "invalid_on_heldout": missing,
                "distinct_heldout_outputs": len(heldout_outputs),
                "unique_correct": missing == 0 and heldout_outputs == {correct_key},
            }
        )
    if not all(row["unique_correct"] for row in loo_rows):
        return None, {
            "accepted": False,
            "reason": "leave_one_demo_out_not_unique_and_exact",
            "all_demo_programs": len(full_programs),
            "loo": loo_rows,
        }

    predictions: list[Grid] = []
    test_rows = []
    for test_index, test in enumerate(tests):
        test_map = predictions_for_grid(test["input"])
        missing = sum(program not in test_map for program in full_programs)
        groups: dict[GridKey, list[str]] = defaultdict(list)
        for program in full_programs:
            if program in test_map:
                groups[grid_key(test_map[program])].append(program.program_id)
        if missing or len(groups) != 1:
            return None, {
                "accepted": False,
                "reason": "test_prediction_not_unique",
                "all_demo_programs": len(full_programs),
                "test_index": test_index,
                "invalid_on_test": missing,
                "distinct_test_outputs": len(groups),
                "loo": loo_rows,
            }
        key, program_ids = next(iter(groups.items()))
        predictions.append([list(row) for row in key])
        test_rows.append(
            {
                "test_index": test_index,
                "agreeing_programs": len(program_ids),
                "program_ids": sorted(program_ids),
            }
        )
    return predictions, {
        "accepted": True,
        "reason": "all_demo_and_loo_unique_agreement",
        "all_demo_programs": len(full_programs),
        "loo": loo_rows,
        "tests": test_rows,
    }
