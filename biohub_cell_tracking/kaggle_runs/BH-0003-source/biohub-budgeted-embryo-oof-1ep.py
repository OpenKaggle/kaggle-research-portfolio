"""Budgeted two-fold embryo-isolated OOF for Biohub cell tracking."""

from __future__ import annotations

import contextlib
import gc
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROTOCOL = json.loads('{"competition":"biohub-cell-tracking-during-development","created_at_utc":"2026-09-09T07:01:21.220911+00:00","data_manifest_sha256":"a585c8f16b6a52334fa8555c771210179cbc50713c32c764b5ca80cb883ea306","folds":[{"fold":0,"holdout":["44b6_e29f0176","44b6_90724892","44b6_74d0c52e","44b6_341df25f","44b6_d2f34f90","44b6_8cc6506c","44b6_7a302da0","44b6_d29c9ab2"],"holdout_selection_proxy_bytes":{"44b6_341df25f":612,"44b6_74d0c52e":523,"44b6_7a302da0":869,"44b6_8cc6506c":738,"44b6_90724892":369,"44b6_d29c9ab2":1664,"44b6_d2f34f90":670,"44b6_e29f0176":256},"monitor":["6bba_0e7c0d07","6bba_3db54e20","6bba_55b7eebe","6bba_e5e44988","6bba_9e23430b","6bba_e16ffc58","6bba_3fda6b25","6bba_09961292"],"monitor_selection_proxy_bytes":{"6bba_09961292":2523,"6bba_0e7c0d07":499,"6bba_3db54e20":892,"6bba_3fda6b25":1703,"6bba_55b7eebe":1067,"6bba_9e23430b":1307,"6bba_e16ffc58":1492,"6bba_e5e44988":1172},"seed":20260909,"train":["6bba_05b6850b","6bba_05db0fb1","6bba_062c8d37","6bba_07477033","6bba_07e24132","6bba_085bf656","6bba_0c7fa718","6bba_12665c0e","6bba_13f19531","6bba_15403b9a","6bba_1d0d8384","6bba_1ebfb80d","6bba_1f58c2f6","6bba_207c6aaf","6bba_20852818","6bba_2312ac41","6bba_23af9eeb","6bba_2540cd90","6bba_2646afc7","6bba_268e1230","6bba_2819ca14","6bba_283bf9f1","6bba_312f0dc3","6bba_32db13fc","6bba_337b1b3a","6bba_372c8cb8","6bba_3a1849c2","6bba_3abfe10a","6bba_3c5691b6","6bba_43fea39d","6bba_474be664","6bba_48816121","6bba_4aa14c89","6bba_4f99ce20","6bba_4ffd3da3","6bba_55c70843","6bba_57b7cc1e","6bba_5a4d9360","6bba_5b28472a","6bba_5c039895","6bba_5c824876","6bba_5dfe9ad1","6bba_5f89039d","6bba_61dd1e0d","6bba_61ecbe65","6bba_6321a359","6bba_6479435d","6bba_67ebd073","6bba_6ca87370","6bba_6db0e9b4","6bba_6feb10f0","6bba_6feeb0b1","6bba_705ec2c9","6bba_718b21f9","6bba_74686d6a","6bba_767a1e17","6bba_76db78c1","6bba_784a78c9","6bba_786893ac","6bba_789f8168","6bba_78a7bd97","6bba_7af54fde","6bba_7b5d3b2c","6bba_7d3058ae","6bba_7f87b3d8","6bba_80d12824","6bba_825bd1c6","6bba_87289e13","6bba_8b7818bf","6bba_907271db","6bba_91951b3a","6bba_96833384","6bba_969618f6","6bba_971fa5e0","6bba_9a41d029","6bba_a5e926bb","6bba_a90a0b9c","6bba_ab78413d","6bba_acd782a8","6bba_ae82a791","6bba_aeee7805","6bba_af149c94","6bba_afb141ff","6bba_b1ae37b9","6bba_b204cac7","6bba_b329af44","6bba_b693381b","6bba_bb9f20c3","6bba_bbb708ca","6bba_c27cba08","6bba_c328f2fd","6bba_c73a1d11","6bba_cdcfe533","6bba_cf35214c","6bba_cff5865f","6bba_d0fc38b5","6bba_d1acb6ff","6bba_d2b9fc0c","6bba_d3da753b","6bba_d5eae175","6bba_d6ecebbb","6bba_d82a4fc6","6bba_debd7bfa","6bba_df673a83","6bba_ebdf3b34","6bba_ebff6e76","6bba_ed9377fd","6bba_edf14583","6bba_eebc57a5","6bba_ef7b4f7e","6bba_f17befbc","6bba_f1fde7e0","6bba_f20478e9","6bba_f4ae811c","6bba_f8ffd5e7","6bba_fbc898dc","6bba_fc516dc6","6bba_fc5f39dc","6bba_fc83837d","6bba_fe670320"],"train_embryo":"6bba","validation_embryo":"44b6"},{"fold":1,"holdout":["6bba_0e7c0d07","6bba_3db54e20","6bba_55b7eebe","6bba_e5e44988","6bba_9e23430b","6bba_e16ffc58","6bba_3fda6b25","6bba_09961292"],"holdout_selection_proxy_bytes":{"6bba_09961292":2523,"6bba_0e7c0d07":499,"6bba_3db54e20":892,"6bba_3fda6b25":1703,"6bba_55b7eebe":1067,"6bba_9e23430b":1307,"6bba_e16ffc58":1492,"6bba_e5e44988":1172},"monitor":["44b6_e29f0176","44b6_90724892","44b6_74d0c52e","44b6_341df25f","44b6_d2f34f90","44b6_8cc6506c","44b6_7a302da0","44b6_d29c9ab2"],"monitor_selection_proxy_bytes":{"44b6_341df25f":612,"44b6_74d0c52e":523,"44b6_7a302da0":869,"44b6_8cc6506c":738,"44b6_90724892":369,"44b6_d29c9ab2":1664,"44b6_d2f34f90":670,"44b6_e29f0176":256},"seed":20260910,"train":["44b6_0113de3b","44b6_0b24845f","44b6_0c582fdc","44b6_0db75fae","44b6_12dfb391","44b6_144b256d","44b6_1574802b","44b6_18ced818","44b6_1d530831","44b6_24264f12","44b6_267148e4","44b6_2a2eff9f","44b6_2f31fc2f","44b6_33b596bf","44b6_3a861e03","44b6_3bb3690f","44b6_40c45f5a","44b6_415c0a3a","44b6_53f95252","44b6_551a5dba","44b6_5740d24b","44b6_587a1e22","44b6_5f15d135","44b6_668e0cc7","44b6_66f9292d","44b6_706092f0","44b6_71a4179f","44b6_7e557709","44b6_808952d6","44b6_81c256f0","44b6_87bba6c4","44b6_8f5ab931","44b6_8f9ecab4","44b6_949adeb1","44b6_95029e92","44b6_97725144","44b6_996155de","44b6_9be80b04","44b6_9bfa6a0a","44b6_a21120c2","44b6_a2bb48bb","44b6_aaf8b0ea","44b6_abf82518","44b6_b2c44266","44b6_c15fded2","44b6_c50204e0","44b6_c771cb04","44b6_c8e2a523","44b6_c96cfa10","44b6_cf2536e8","44b6_cf8fed6b","44b6_d5e7d891","44b6_d754aa59","44b6_d78e09d9","44b6_db3c847b","44b6_ddf577ad","44b6_deabac95","44b6_e28840c6","44b6_e31261b4","44b6_e35b117d","44b6_e57ff5c6","44b6_eb2880fc","44b6_f28707c6"],"train_embryo":"44b6","validation_embryo":"6bba"}],"limitations":["Only one training epoch is used per embryo direction because live telemetry disproved the original 12-epoch budget.","Only eight validation movies per embryo are fully inferred and scored.","Checkpoint selection uses only the same-embryo monitor subset; the cross-embryo holdout does not participate in training or selection.","Promotion requires directionally consistent results in both embryo directions; this reduced protocol cannot justify leaderboard-only tuning."],"protocol":"budgeted_leave_one_embryo_out_1ep_recovery","purpose":"runtime-corrected honest generalization and error diagnosis; not a direct proxy for BH-0001","recovery_parent":{"activity_receipt_checked_at_utc":"2026-09-09T06:50:08.400000Z","current_run_script_version_id":348373083,"failed_budget_assumption":"12 epochs projected from nonrepresentative reference timing","launch_condition":"current 12-epoch kernel must be terminal","protocol_sha256":"b51946e4dc46086a6af7a66bb8d6a7f8bef532ce9639e54001f75d1ad033f21b"},"runtime_budget":{"conservative_batches_per_epoch_each_fold":1454,"contingency_seconds":10800.0,"estimated_inference_seconds":4800.70864868164,"estimated_total_hours_with_reserve":9.434896846856011,"estimated_total_seconds_with_reserve":33965.62864868164,"estimated_training_seconds_two_folds":15964.92,"evaluation_seconds":1800.0,"headroom_hours":2.565103153143989,"headroom_seconds":9234.371351318361,"inference_safety_factor":2.0,"observed_fold_0_batches_per_epoch":1454,"observed_median_seconds_per_batch":5.49,"official_limit_hours":12,"passes_prelaunch_runtime_gate":true,"reference_inference_seconds_16_movies":2400.35432434082,"setup_seconds":600.0,"source":"authenticated official Kaggle UI telemetry from the active 12-epoch run"},"selection":{"fixed_before_modeling":true,"method":"eight fixed order-statistic quantiles of compressed GEFF node-id chunk bytes","model_selection":"same-embryo monitor only; final cross-embryo holdout is untouched until inference","monitor_samples_per_fold":8,"validation_samples_per_fold":8,"visible_test_copies_excluded":["44b6_0113de3b","44b6_0b24845f","6bba_05b6850b","6bba_05db0fb1"]},"training":{"augmentations":"disabled for deterministic diagnostic","batch_size":8,"downsample_zyx":[1,4,4],"epochs":1,"learning_rate":0.0001,"warm_start":null}}')
SOURCE_PROTOCOL_SHA256 = "42853eb6259d2f9eddc24229fe9d52ede1f4801d8eb745ea71c323db9e078692"
OFFICIAL_METRICS_SOURCE = 'import warnings\nfrom typing import Literal, NamedTuple\n\nimport polars as pl\nimport tracksdata as td\n\n\nclass EvaluationResult(NamedTuple):\n    """Counts returned by :func:`evaluate`."""\n\n    edge_tp: int\n    edge_fp: int\n    edge_fn: int\n    division_tp: int\n    division_fp: int\n    division_fn: int\n    num_pred_nodes: int\n\n\nclass DatasetsResult(NamedTuple):\n    """Cumulative (micro-averaged) Jaccards plus the combined score."""\n\n    edge_jaccard: float\n    division_jaccard: float\n    score: float\n\n\n# Penalty coefficient for the adjusted edge Jaccard:\n#   J_adj = max(0, J · (1 - ADJUSTMENT_ALPHA · total_node_ratio))\nADJUSTMENT_ALPHA: float = 0.1\n\n# Weight of the division Jaccard in the combined run-level score:\n#   score = adj_edge_jaccard + SCORE_DIVISION_WEIGHT · division_jaccard\nSCORE_DIVISION_WEIGHT: float = 0.1\n\nCOUNT_COLUMNS: tuple[str, ...] = (\n    "edge_tp", "edge_fp", "edge_fn",\n    "division_tp", "division_fp", "division_fn",\n    "num_pred_nodes",\n)\nMETRIC_COLUMNS: tuple[str, ...] = COUNT_COLUMNS + (\n    "node_recall", "total_node_ratio", "edge_jaccard", "adj_edge_jaccard",\n)\n\n\ndef _jaccard(tp: int, fp: int, fn: int) -> float:\n    denom = tp + fp + fn\n    return tp / denom if denom > 0 else float("nan")\n\n\n# function is split for easier testing\ndef _evaluate_matched_graph(\n    graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n) -> pl.DataFrame:\n    edge_attrs = graph.edge_attrs(attr_keys=[td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK])\n    # Guard against duplicate edges (same source→target pair appearing multiple times).\n    # tracksdata\'s match() inner-join marks all duplicates as matched, which inflates\n    # the intersection count and can push scores above 1.0. Sort matched rows first\n    # so the dedup keeps the matched copy when duplicates disagree on the mask.\n    edge_attrs = edge_attrs.sort(\n        td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK, descending=True,\n    ).unique(\n        subset=[td.DEFAULT_ATTR_KEYS.EDGE_SOURCE, td.DEFAULT_ATTR_KEYS.EDGE_TARGET],\n        keep="first",\n    )\n    node_attrs = graph.node_attrs(\n        attr_keys=[td.DEFAULT_ATTR_KEYS.NODE_ID, td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID, td.DEFAULT_ATTR_KEYS.T]\n    )\n\n    # Drop edges that do not connect consecutive frames, i.e. keep only edges where\n    # t_target == t_source + 1. This removes backward-in-time edges (t_target <= t_source)\n    # and any edge spanning more than a single time step (t_target - t_source > 1).\n    node_times = node_attrs.select(td.DEFAULT_ATTR_KEYS.NODE_ID, td.DEFAULT_ATTR_KEYS.T)\n    edge_attrs = edge_attrs.join(\n        node_times.rename({td.DEFAULT_ATTR_KEYS.T: "_source_t"}),\n        left_on=td.DEFAULT_ATTR_KEYS.EDGE_SOURCE,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    ).join(\n        node_times.rename({td.DEFAULT_ATTR_KEYS.T: "_target_t"}),\n        left_on=td.DEFAULT_ATTR_KEYS.EDGE_TARGET,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    ).filter(\n        pl.col("_target_t") - pl.col("_source_t") == 1\n    ).drop("_source_t", "_target_t")\n\n    # Collapse merges: when several predicted nodes match the same ground-truth\n    # node, multiple predicted edges can map onto the same ground-truth edge\n    # (identical matched source/target pair). tracksdata marks all of them as\n    # matched, inflating the intersection. Keep only the edge with the lowest\n    # EDGE_ID per matched GT edge and discard the rest with a warning.\n    matched_ids = node_attrs.select(\n        td.DEFAULT_ATTR_KEYS.NODE_ID, td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID\n    )\n    edge_attrs = edge_attrs.join(\n        matched_ids.rename({td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID: "_matched_source"}),\n        left_on=td.DEFAULT_ATTR_KEYS.EDGE_SOURCE,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    ).join(\n        matched_ids.rename({td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID: "_matched_target"}),\n        left_on=td.DEFAULT_ATTR_KEYS.EDGE_TARGET,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    )\n    # Only edges whose endpoints both match a GT node can collapse onto a GT edge.\n    both_matched = (\n        pl.col("_matched_source").is_not_null()\n        & pl.col("_matched_target").is_not_null()\n        & (pl.col("_matched_source") != -1)\n        & (pl.col("_matched_target") != -1)\n    )\n    edge_attrs = edge_attrs.with_columns(\n        (\n            both_matched\n            & (\n                pl.col(td.DEFAULT_ATTR_KEYS.EDGE_ID)\n                != pl.col(td.DEFAULT_ATTR_KEYS.EDGE_ID)\n                .min()\n                .over("_matched_source", "_matched_target")\n            )\n        ).alias("_is_merge_dup")\n    )\n    n_merge_dropped = int(edge_attrs["_is_merge_dup"].sum())\n    if n_merge_dropped > 0:\n        warnings.warn(\n            f"Dropped {n_merge_dropped} merged edge(s) mapping onto the same "\n            "ground-truth edge; kept the lowest edge id per merge.",\n            stacklevel=2,\n        )\n    edge_attrs = edge_attrs.filter(~pl.col("_is_merge_dup")).drop(\n        "_matched_source", "_matched_target", "_is_merge_dup"\n    )\n\n    # Cap out-degree: a dividing cell has at most two children, so a predicted node\n    # with more than two outgoing edges is biologically invalid. Keep the two edges\n    # with the lowest EDGE_ID per source and drop the rest with a warning.\n    edge_attrs = edge_attrs.with_columns(\n        pl.col(td.DEFAULT_ATTR_KEYS.EDGE_ID)\n        .rank("ordinal")\n        .over(td.DEFAULT_ATTR_KEYS.EDGE_SOURCE)\n        .alias("_out_rank")\n    )\n    n_outdeg_dropped = int((edge_attrs["_out_rank"] > 2).sum())\n    if n_outdeg_dropped > 0:\n        warnings.warn(\n            f"Dropped {n_outdeg_dropped} outgoing edge(s) from nodes with more than "\n            "two children; kept the two lowest edge ids per source.",\n            stacklevel=2,\n        )\n    edge_attrs = edge_attrs.filter(pl.col("_out_rank") <= 2).drop("_out_rank")\n\n    # I\'m assuming valid ground-truth edges are always 100% correct if they have an edge.\n    # Therefore, we don\'t have cases where the cell divided, but not in the ground truth.\n    gt_node_ids = gt_graph.node_ids()\n    gt_node_attrs = pl.DataFrame(\n        {\n            td.DEFAULT_ATTR_KEYS.NODE_ID: gt_node_ids,\n            "out_degree": gt_graph.out_degree(gt_node_ids),\n            "in_degree": gt_graph.in_degree(gt_node_ids),\n        }\n    ).with_columns(\n        (pl.col("out_degree") > 0).alias("out_valid"),\n        (pl.col("in_degree") > 0).alias("in_valid"),\n    )\n\n    # merging ground truth graph into the predicted graph\n    node_attrs = node_attrs.join(\n        gt_node_attrs,\n        left_on=td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    ).with_columns(\n        pl.col("out_valid").fill_null(False),\n        pl.col("in_valid").fill_null(False),\n    )\n\n    # merge out valid into source and in valid into target\n    edge_attrs = edge_attrs.join(\n        node_attrs.select(td.DEFAULT_ATTR_KEYS.NODE_ID, "out_valid"),\n        left_on=td.DEFAULT_ATTR_KEYS.EDGE_SOURCE,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    ).join(\n        node_attrs.select(td.DEFAULT_ATTR_KEYS.NODE_ID, "in_valid"),\n        left_on=td.DEFAULT_ATTR_KEYS.EDGE_TARGET,\n        right_on=td.DEFAULT_ATTR_KEYS.NODE_ID,\n        how="left",\n    )\n\n    edge_attrs = edge_attrs.with_columns(\n        (pl.col("out_valid") | pl.col("in_valid")).alias("pred_valid"),\n    )\n\n    # sanity check that `pred_valid` is a superset of all matched edges\n    assert edge_attrs.filter(td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK)["pred_valid"].all()\n\n    return edge_attrs\n\n\ndef _compute_score(\n    edge_attrs: pl.DataFrame,\n    gt_num_edges: int,\n    metric: Literal["jaccard", "dice"],\n) -> float:\n    intersection = int(edge_attrs[td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK].sum())\n    n_valid_pred_edges = int(edge_attrs["pred_valid"].sum())\n\n    if metric == "jaccard":\n        num = intersection\n        denom = gt_num_edges + n_valid_pred_edges - intersection\n    elif metric == "dice":\n        num = 2 * intersection\n        denom = gt_num_edges + n_valid_pred_edges\n    else:\n        raise ValueError(f"Invalid metric: {metric}")\n\n    return num / denom if denom > 0 else float("nan")\n\n\ndef _evaluate(\n    graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    metric: Literal["jaccard", "dice"],\n    scale: tuple[float, ...] | None,\n    max_distance: float,\n) -> float:\n    if td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID in graph.node_attr_keys():\n        warnings.warn("Graph already matched, overwriting previous matching.")\n        # Reset matching attributes to defaults before re-matching\n        all_node_ids = graph.node_ids()\n        graph.update_node_attrs(\n            node_ids=all_node_ids,\n            attrs={\n                td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID: -1,\n                td.DEFAULT_ATTR_KEYS.MATCH_SCORE: 0.0,\n            },\n        )\n        all_edge_ids = graph.edge_ids()\n        if len(all_edge_ids) > 0:\n            graph.update_edge_attrs(\n                edge_ids=all_edge_ids,\n                attrs={td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK: False},\n            )\n\n    from tracksdata.metrics import DistanceMatching\n    matching = DistanceMatching(max_distance=max_distance, scale=scale)\n\n    if graph.num_edges() == 0 or graph.num_nodes() == 0:\n        warnings.warn("Predicted graph has no edges or no nodes, returning score 0.0.")\n        return 0.0\n\n    from tracksdata.options import get_options, set_options\n\n    prev_show_progress = get_options().show_progress\n    set_options(show_progress=False)\n    try:\n        with warnings.catch_warnings():\n            from scipy.sparse import SparseEfficiencyWarning\n            warnings.filterwarnings("ignore", category=SparseEfficiencyWarning)\n            graph.match(gt_graph, matching=matching)\n    finally:\n        set_options(show_progress=prev_show_progress)\n\n    edge_attrs = _evaluate_matched_graph(graph, gt_graph)\n\n    return _compute_score(edge_attrs, gt_graph.num_edges(), metric)\n\n\ndef evaluate(\n    graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None = None,\n    max_distance: float = 7.0,\n) -> EvaluationResult:\n    """\n    Evaluate a predicted graph against a ground-truth graph using\n    centroid-distance node matching.\n\n    Computes edge TP/FP/FN, division TP/FP/FN (via\n    :func:`tracking_cellmot.division_metrics.evaluate_divisions`), and the\n    total number of predicted nodes (irrespective of matching).\n\n    Parameters\n    ----------\n    graph : tracksdata.graph.BaseGraph\n        The predicted graph. Matching attributes are written onto *graph*\n        as a side effect.\n    gt_graph : tracksdata.graph.BaseGraph\n        The ground truth graph.\n    scale : tuple[float, ...] | None, optional\n        Physical scale for each spatial dimension (e.g., (z, y, x)) to\n        account for anisotropy. If None, assumes isotropic data.\n    max_distance : float, optional\n        Maximum distance between centroids to be considered as a match.\n\n    Returns\n    -------\n    EvaluationResult\n    """\n    from .division_metrics import evaluate_divisions\n\n    # Match graph against gt_graph (in place); discard the returned score.\n    _evaluate(graph, gt_graph, "jaccard", scale, max_distance)\n\n    if graph.num_edges() == 0:\n        edge_tp = 0\n        edge_fp = 0\n        edge_fn = gt_graph.num_edges()\n    else:\n        edge_attrs = _evaluate_matched_graph(graph, gt_graph)\n        edge_tp = int(edge_attrs[td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK].sum())\n        edge_valid_pred = int(edge_attrs["pred_valid"].sum())\n        edge_fp = edge_valid_pred - edge_tp\n        edge_fn = gt_graph.num_edges() - edge_tp\n\n    div = evaluate_divisions(\n        graph, gt_graph, scale=scale, max_distance=max_distance,\n    )\n\n    return EvaluationResult(\n        edge_tp=edge_tp,\n        edge_fp=edge_fp,\n        edge_fn=edge_fn,\n        division_tp=div.tp,\n        division_fp=div.fp,\n        division_fn=div.fn,\n        num_pred_nodes=graph.num_nodes(),\n    )\n\n\ndef evaluate_datasets(\n    graph_pairs: list[tuple[td.graph.BaseGraph, td.graph.BaseGraph]],\n    scale: tuple[float, ...] | None = None,\n    max_distance: float = 7.0,\n) -> DatasetsResult:\n    """Run :func:`evaluate` on each (pred, gt) pair and return cumulative\n    (micro-averaged) edge and division Jaccard.\n\n    Per-pair TP/FP/FN counts are summed across the whole list before the\n    Jaccard is computed, so larger datasets dominate the score naturally.\n\n    Parameters\n    ----------\n    graph_pairs : list of (pred_graph, gt_graph)\n        Predicted / ground-truth graph pairs. Each *pred_graph* is mutated\n        in place by matching (same side effect as :func:`evaluate`).\n    scale : tuple[float, ...] | None, optional\n        Physical voxel scale used for centroid-distance matching.\n    max_distance : float, optional\n        Maximum centroid distance for a match.\n\n    Returns\n    -------\n    DatasetsResult\n        Named tuple with ``edge_jaccard``, ``division_jaccard``, and the\n        combined ``score = edge_jaccard + SCORE_DIVISION_WEIGHT *\n        division_jaccard``. If no divisions exist anywhere in the input\n        the division term is dropped and ``score = edge_jaccard``.\n    """\n    edge_tp = edge_fp = edge_fn = 0\n    div_tp = div_fp = div_fn = 0\n    for pred, gt in graph_pairs:\n        r = evaluate(pred, gt, scale=scale, max_distance=max_distance)\n        edge_tp += r.edge_tp\n        edge_fp += r.edge_fp\n        edge_fn += r.edge_fn\n        div_tp += r.division_tp\n        div_fp += r.division_fp\n        div_fn += r.division_fn\n\n    edge_jaccard = _jaccard(edge_tp, edge_fp, edge_fn)\n    has_divisions = (div_tp + div_fp + div_fn) > 0\n    division_jaccard = _jaccard(div_tp, div_fp, div_fn) if has_divisions else float("nan")\n    score = edge_jaccard + SCORE_DIVISION_WEIGHT * division_jaccard if has_divisions else edge_jaccard\n\n    return DatasetsResult(\n        edge_jaccard=edge_jaccard,\n        division_jaccard=division_jaccard,\n        score=score,\n    )\n\n\ndef _matched_node_ids(graph: td.graph.BaseGraph) -> pl.DataFrame:\n    """Return a DataFrame with NODE_ID and MATCHED_NODE_ID (as Int64) for *graph*."""\n    node_attrs = graph.node_attrs(\n        attr_keys=[td.DEFAULT_ATTR_KEYS.NODE_ID, td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID]\n    )\n    return node_attrs\n\n\ndef node_recall(\n    graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n) -> float:\n    """Fraction of GT nodes that were matched by a predicted node.\n\n    The predicted graph must already be matched (e.g. via :func:`evaluate` or\n    ``graph.match``).\n    """\n    node_attrs = _matched_node_ids(graph)\n    matched = node_attrs.filter(\n        pl.col(td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID).is_not_null()\n        & (pl.col(td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID) != -1)\n    )\n    n_matched_gt = matched[td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID].n_unique()\n    return n_matched_gt / gt_graph.num_nodes()\n\n\ndef per_sample_metrics(\n    er: EvaluationResult,\n    n_total: float,\n    node_recall: float,\n) -> dict:\n    """Derive per-sample metric columns from an :class:`EvaluationResult`.\n\n    Computes ``edge_jaccard``, ``total_node_ratio`` (``(N_pred − N_total) / N_total``),\n    and the adjusted edge Jaccard ``J_adj = max(0, J · (1 − α · total_node_ratio))``\n    with α = :data:`ADJUSTMENT_ALPHA`.\n\n    Parameters\n    ----------\n    er\n        Counts for one (pred, gt) pair — see :func:`evaluate`.\n    n_total\n        Target node count (e.g. from the GEFF ``estimated_number_of_nodes``\n        metadata extra). Pass ``float("nan")`` when unavailable; that makes\n        ``total_node_ratio`` and ``adj_edge_jaccard`` also NaN.\n    node_recall\n        Fraction of GT nodes matched by a predicted node.\n\n    Returns\n    -------\n    dict\n        One entry per key in :data:`METRIC_COLUMNS`.\n    """\n    if n_total > 0:\n        total_node_ratio = (er.num_pred_nodes - n_total) / n_total\n    else:\n        total_node_ratio = float("nan")\n\n    edge_denom = er.edge_tp + er.edge_fp + er.edge_fn\n    edge_jaccard = er.edge_tp / edge_denom if edge_denom > 0 else float("nan")\n    if edge_jaccard == edge_jaccard and total_node_ratio == total_node_ratio:\n        adj_edge_jaccard = max(\n            0.0, edge_jaccard * (1 - ADJUSTMENT_ALPHA * total_node_ratio),\n        )\n    else:\n        adj_edge_jaccard = float("nan")\n\n    return {\n        "edge_tp": er.edge_tp, "edge_fp": er.edge_fp, "edge_fn": er.edge_fn,\n        "division_tp": er.division_tp,\n        "division_fp": er.division_fp,\n        "division_fn": er.division_fn,\n        "num_pred_nodes": er.num_pred_nodes,\n        "node_recall": node_recall,\n        "total_node_ratio": total_node_ratio,\n        "edge_jaccard": edge_jaccard,\n        "adj_edge_jaccard": adj_edge_jaccard,\n    }\n\n\ndef nan_metrics_row() -> dict:\n    """Return a dict with every :data:`METRIC_COLUMNS` key set to NaN."""\n    return {col: float("nan") for col in METRIC_COLUMNS}\n\n\ndef summarise(rows: list[dict]) -> dict:\n    """Aggregate per-sample metric rows into a run-level summary.\n\n    - ``edge_jaccard`` / ``division_jaccard``: micro-averaged across valid rows\n      (TP/FP/FN summed, then Jaccard).\n    - ``adj_edge_jaccard``: per-sample adjusted Jaccard weight-averaged by\n      sample size ``w_i = TP_i + FP_i + FN_i``; rows with NaN are skipped.\n    - ``score``: ``adj_edge_jaccard + SCORE_DIVISION_WEIGHT · division_jaccard``.\n\n    Parameters\n    ----------\n    rows\n        Per-sample dicts as produced by :func:`per_sample_metrics`. Rows with\n        NaN ``edge_tp`` are treated as failed evaluations and skipped.\n    """\n    valid = [r for r in rows if r["edge_tp"] == r["edge_tp"]]\n    if not valid:\n        return {\n            "n": 0, "edge_jaccard": float("nan"),\n            "division_jaccard": float("nan"),\n            "division_tp": 0, "division_fp": 0, "division_fn": 0,\n            "node_recall": float("nan"),\n            "adj_edge_jaccard": float("nan"), "n_adj": 0,\n            "score": float("nan"),\n        }\n    totals = {c: sum(r[c] for r in valid) for c in COUNT_COLUMNS}\n\n    adj_rows = [r for r in valid if r["adj_edge_jaccard"] == r["adj_edge_jaccard"]]\n    weights = [r["edge_tp"] + r["edge_fp"] + r["edge_fn"] for r in adj_rows]\n    total_w = sum(weights)\n    if total_w > 0:\n        adj_edge_jaccard = sum(\n            w * r["adj_edge_jaccard"] for w, r in zip(weights, adj_rows)\n        ) / total_w\n    else:\n        adj_edge_jaccard = float("nan")\n\n    division_total = (\n        totals["division_tp"] + totals["division_fp"] + totals["division_fn"]\n    )\n    if division_total == 0:\n        warnings.warn(\n            "No divisions present across any sample in this split; "\n            "dropping division term from the combined score."\n        )\n        division_jaccard = float("nan")\n        score = adj_edge_jaccard\n    else:\n        division_jaccard = _jaccard(\n            totals["division_tp"], totals["division_fp"], totals["division_fn"],\n        )\n        score = adj_edge_jaccard + SCORE_DIVISION_WEIGHT * division_jaccard\n    return {\n        "n": len(valid),\n        "edge_jaccard": _jaccard(\n            totals["edge_tp"], totals["edge_fp"], totals["edge_fn"],\n        ),\n        "division_jaccard": division_jaccard,\n        "division_tp": totals["division_tp"],\n        "division_fp": totals["division_fp"],\n        "division_fn": totals["division_fn"],\n        "node_recall": sum(r["node_recall"] for r in valid) / len(valid),\n        "adj_edge_jaccard": adj_edge_jaccard,\n        "n_adj": len(adj_rows),\n        "score": score,\n    }\n'
OFFICIAL_DIVISION_METRICS_SOURCE = 'import warnings\nfrom typing import NamedTuple\n\nimport polars as pl\nimport tracksdata as td\n\n\nclass DivisionCounts(NamedTuple):\n    """Counts for division event evaluation."""\n\n    tp: int\n    fn: int\n    fp: int\n\n\nclass DivisionScores(NamedTuple):\n    """Result of :func:`score_divisions`.\n\n    Attributes\n    ----------\n    scores : dict[int, int]\n        Mapping from GT dividing-node ID to 1 (recovered) or 0 (not).\n    tp_forks : set[int]\n        Predicted dividing nodes paired to GT divisions.\n    fp_forks : set[int]\n        Predicted dividing nodes that were considered for a GT division\n        but did not become a true positive, including local-topology\n        rejects, bipartite leftovers, evaluable spurious forks, malformed\n        local branches, and forks whose branch evidence spans distinct GT\n        components.\n    """\n\n    scores: dict[int, int]\n    tp_forks: set[int]\n    fp_forks: set[int]\n\n\ndef _reset_matching_attrs(graph: td.graph.BaseGraph) -> None:\n    """Reset any pre-existing match attrs in place so a fresh ``.match()`` isn\'t\n    contaminated by stale values carried in from a previous matching pass."""\n    node_keys = graph.node_attr_keys()\n    if td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID in node_keys:\n        node_ids = graph.node_ids()\n        if len(node_ids) > 0:\n            reset: dict = {td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID: -1}\n            if td.DEFAULT_ATTR_KEYS.MATCH_SCORE in node_keys:\n                reset[td.DEFAULT_ATTR_KEYS.MATCH_SCORE] = 0.0\n            graph.update_node_attrs(node_ids=node_ids, attrs=reset)\n    if td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK in graph.edge_attr_keys():\n        edge_ids = graph.edge_ids()\n        if len(edge_ids) > 0:\n            graph.update_edge_attrs(\n                edge_ids=edge_ids,\n                attrs={td.DEFAULT_ATTR_KEYS.MATCHED_EDGE_MASK: False},\n            )\n\n\ndef extract_divisions(\n    graph: td.graph.BaseGraph,\n) -> dict[int, td.graph.BaseGraph]:\n    """Extract individual division events as separate subgraphs.\n\n    Each division event includes the parent of the dividing node, the\n    dividing node, its children, and the grandchildren::\n\n        parent → divider → child1 → grandchild1\n                         → child2 → grandchild2\n\n    Parameters\n    ----------\n    graph : td.graph.BaseGraph\n        The input tracking graph.\n\n    Returns\n    -------\n    dict[int, td.graph.BaseGraph]\n        Mapping from dividing node ID to a subgraph containing the\n        parent, divider, children, and grandchildren.\n    """\n    divisions: dict[int, td.graph.BaseGraph] = {}\n    for div_node in graph.dividing_nodes():\n        parents = graph.predecessors(div_node)\n        children = graph.successors(div_node)\n        grandchildren = [gc for child in children for gc in graph.successors(child)]\n        keep = [*parents, div_node, *children, *grandchildren]\n        divisions[div_node] = graph.filter(node_ids=keep).subgraph()\n    return divisions\n\n\ndef match_divisions(\n    pred_graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None = None,\n    max_distance: float = 7.0,\n) -> dict[int, td.graph.BaseGraph]:\n    """Match the predicted graph against each GT division subgraph.\n\n    Extracts division events from *gt_graph* via :func:`extract_divisions`,\n    then runs ``pred_graph.match(gt_div, ...)`` for each one independently.\n    A fresh copy of *pred_graph* is used per division so matchings don\'t\n    interfere.\n\n    Parameters\n    ----------\n    pred_graph : td.graph.BaseGraph\n        The predicted tracking graph.\n    gt_graph : td.graph.BaseGraph\n        The ground-truth tracking graph.\n    scale : tuple[float, ...] | None\n        Physical voxel scale used for centroid-distance matching.\n    max_distance : float\n        Maximum centroid distance for a match.\n\n    Returns\n    -------\n    dict[int, td.graph.BaseGraph]\n        Mapping from GT dividing-node ID to the matched copy of\n        *pred_graph* for that division.\n    """\n    from tracksdata.metrics import DistanceMatching\n\n    matching = DistanceMatching(max_distance=max_distance, scale=scale)\n\n    gt_divisions = extract_divisions(gt_graph)\n    matched: dict[int, td.graph.BaseGraph] = {}\n\n    from tracksdata.options import get_options, set_options\n\n    prev_show_progress = get_options().show_progress\n    set_options(show_progress=False)\n    try:\n        for div_node, gt_div in gt_divisions.items():\n            pred_copy = pred_graph.copy()\n            _reset_matching_attrs(pred_copy)\n            with warnings.catch_warnings():\n                from scipy.sparse import SparseEfficiencyWarning\n\n                warnings.filterwarnings("ignore", category=SparseEfficiencyWarning)\n                pred_copy.match(gt_div, matching=matching)\n            matched[div_node] = pred_copy\n    finally:\n        set_options(show_progress=prev_show_progress)\n\n    return matched\n\n\ndef _match_full(\n    pred_graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None,\n    max_distance: float,\n) -> td.graph.BaseGraph:\n    """Match the full pred graph against the full GT graph, return the matched copy."""\n    from tracksdata.metrics import DistanceMatching\n\n    matching = DistanceMatching(max_distance=max_distance, scale=scale)\n\n    pred_copy = pred_graph.copy()\n    _reset_matching_attrs(pred_copy)\n\n    from tracksdata.options import get_options, set_options\n\n    prev_show_progress = get_options().show_progress\n    set_options(show_progress=False)\n    try:\n        with warnings.catch_warnings():\n            from scipy.sparse import SparseEfficiencyWarning\n\n            warnings.filterwarnings("ignore", category=SparseEfficiencyWarning)\n            pred_copy.match(gt_graph, matching=matching)\n    finally:\n        set_options(show_progress=prev_show_progress)\n\n    return pred_copy\n\n\ndef _matched_node_attrs(graph: td.graph.BaseGraph) -> pl.DataFrame:\n    """Return pred/GT node-ID pairs for matched prediction nodes."""\n    node_attrs = graph.node_attrs(\n        attr_keys=[\n            td.DEFAULT_ATTR_KEYS.NODE_ID,\n            td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID,\n        ],\n    )\n    return node_attrs.filter(\n        pl.col(td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID).is_not_null()\n        & (pl.col(td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID) != -1)\n    )\n\n\ndef _matched_division_nodes(\n    matched_attrs: pl.DataFrame,\n    gt_div: td.graph.BaseGraph,\n    divider_id: int,\n) -> tuple[set[int], list[set[int]]] | None:\n    """Group matched pred nodes by their role in a GT division window.\n\n    The parent side contains the GT divider (the parent cell) and its\n    immediate predecessor (the grandparent). Each daughter side contains\n    one GT child and its immediate successors (the grandchildren).\n    """\n    if matched_attrs.is_empty():\n        return None\n\n    node_to_gt = dict(\n        zip(\n            matched_attrs[td.DEFAULT_ATTR_KEYS.NODE_ID].to_list(),\n            matched_attrs[td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID].to_list(),\n            strict=True,\n        )\n    )\n    gt_children = gt_div.successors(divider_id)\n    if len(gt_children) < 2:\n        return None\n\n    gt_parent_ids = {divider_id, *gt_div.predecessors(divider_id)}\n    parent_ids = {pred_id for pred_id, gt_id in node_to_gt.items() if gt_id in gt_parent_ids}\n    daughter_ids = [\n        {pred_id for pred_id, gt_id in node_to_gt.items() if gt_id in {child, *gt_div.successors(child)}}\n        for child in gt_children\n    ]\n    if not parent_ids or sum(bool(ids) for ids in daughter_ids) < 2:\n        return None\n    return parent_ids, daughter_ids\n\n\ndef _is_strongly_connected_division(\n    pred_graph: td.graph.BaseGraph,\n    pred_div: int,\n    parent_ids: set[int],\n    daughter_ids: list[set[int]],\n) -> bool:\n    """Check a predicted division\'s local directed topology.\n\n    The prediction window mirrors :func:`extract_divisions`: an immediate\n    predecessor (grandparent), *pred_div* (parent), its children, and their\n    children (grandchildren). The parent match must be the fork itself or\n    its immediate predecessor. Matches from at least two GT daughter\n    lineages must occur in two distinct predicted child lineages.\n\n    Parameters\n    ----------\n    pred_graph : td.graph.BaseGraph\n        The predicted tracking graph.\n    pred_div : int\n        Candidate predicted dividing node (the parent/fork).\n    parent_ids : set[int]\n        Prediction node IDs matched to the GT parent side (grandparent or\n        dividing parent).\n    daughter_ids : list[set[int]]\n        Prediction node IDs matched to each GT daughter lineage (child or\n        grandchild), grouped by lineage.\n\n    Returns\n    -------\n    bool\n        Whether the local prediction topology connects the parent side to\n        at least two distinct daughter lineages through *pred_div*.\n    """\n    pred_parent_ids = {pred_div, *pred_graph.predecessors(pred_div)}\n    if pred_parent_ids.isdisjoint(parent_ids):\n        return False\n\n    pred_lineages = [{child, *pred_graph.successors(child)} for child in pred_graph.successors(pred_div)]\n    lineage_edges = {\n        gt_lineage: {\n            pred_lineage for pred_lineage, pred_ids in enumerate(pred_lineages) if not matched_ids.isdisjoint(pred_ids)\n        }\n        for gt_lineage, matched_ids in enumerate(daughter_ids)\n    }\n    return len(_bipartite_max_matching(list(lineage_edges), lineage_edges)) >= 2\n\n\ndef _bipartite_max_matching(\n    left: list[int],\n    edges: dict[int, set[int]],\n) -> dict[int, int]:\n    """Maximum-cardinality bipartite matching via DFS augmenting paths.\n\n    *edges* maps each left-side vertex to the set of adjacent right-side\n    vertices. Returns only the matched pairs as a ``left → right`` dict.\n    """\n    match_r: dict[int, int] = {}\n    match_l: dict[int, int] = {}\n\n    def augment(u: int, seen: set[int]) -> bool:\n        for v in edges.get(u, ()):\n            if v in seen:\n                continue\n            seen.add(v)\n            if v not in match_r or augment(match_r[v], seen):\n                match_l[u] = v\n                match_r[v] = u\n                return True\n        return False\n\n    for u in left:\n        augment(u, set())\n\n    return match_l\n\n\ndef score_divisions(\n    pred_graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None = None,\n    max_distance: float = 7.0,\n) -> DivisionScores:\n    """Score each GT division: 1 if the prediction recovers it, 0 otherwise.\n\n    For each GT division, the predicted graph is matched against its\n    parent/divider/children/grandchildren window. Candidate pred forks are\n    restricted to the matched parent-side nodes and their immediate\n    successors. A candidate is valid only when its local topology contains\n    a matched parent and matches from two GT daughter lineages on distinct\n    predicted child branches. A fork is rejected when two direct-child\n    branches have nearest matched evidence in distinct reliable GT components.\n    An unmatched child may use unambiguous grandchild evidence as a fallback;\n    matched children take precedence over downstream matches.\n\n    A maximum-cardinality bipartite matching is then computed so each pred\n    fork serves at most one GT division, and each GT division is paired\n    with at most one pred fork. A GT division scores 1 only if paired;\n    rejected candidates and valid candidates left unpaired are returned as\n    false-positive forks.\n\n    Parameters\n    ----------\n    pred_graph : td.graph.BaseGraph\n        The predicted tracking graph.\n    gt_graph : td.graph.BaseGraph\n        The ground-truth tracking graph.\n    scale : tuple[float, ...] | None\n        Physical voxel scale used for centroid-distance matching.\n    max_distance : float\n        Maximum centroid distance for a match.\n\n    Returns\n    -------\n    DivisionScores\n        The per-division scores and the predicted forks classified as true\n        positives or false positives. False-positive forks include local\n        topology rejects, cross-GT-component branches, locally merged branches,\n        evaluable spurious forks, and valid candidates left unmatched by the\n        bipartite pairing.\n    """\n    matched = match_divisions(\n        pred_graph,\n        gt_graph,\n        scale,\n        max_distance,\n    )\n    gt_divisions = extract_divisions(gt_graph)\n    pred_div_nodes = {\n        node_id for node_id in pred_graph.node_ids()\n        if pred_graph.out_degree(node_id) >= 2\n    }\n    evaluable_forks, cross_component_forks, malformed_forks = (\n        _pred_division_fork_sets(pred_graph, gt_graph, scale, max_distance)\n    )\n    invalid_forks = cross_component_forks | malformed_forks\n\n    candidates: dict[int, set[int]] = {}\n    considered: set[int] = set()\n    for div_node, matched_pred in matched.items():\n        matched_nodes = _matched_division_nodes(_matched_node_attrs(matched_pred), gt_divisions[div_node], div_node)\n        if matched_nodes is None:\n            candidates[div_node] = set()\n            continue\n\n        parent_ids, daughter_ids = matched_nodes\n        local_nodes = parent_ids | {\n            successor for parent_id in parent_ids for successor in matched_pred.successors(parent_id)\n        }\n        local_forks = local_nodes & pred_div_nodes\n        considered |= local_forks\n        candidates[div_node] = {\n            pred_div\n            for pred_div in local_forks - invalid_forks\n            if _is_strongly_connected_division(matched_pred, pred_div, parent_ids, daughter_ids)\n        }\n\n    pairing = _bipartite_max_matching(list(candidates), candidates)\n    scores = {div: int(div in pairing) for div in candidates}\n    tp_forks = set(pairing.values())\n    # Use a set union so forks supported by multiple FP rules are counted once.\n    # Invalid forks were excluded from the pairing above and therefore cannot\n    # also be true positives.\n    fp_forks = (considered | evaluable_forks | invalid_forks) - tp_forks\n    return DivisionScores(scores=scores, tp_forks=tp_forks, fp_forks=fp_forks)\n\n\ndef _gt_weak_component_ids(graph: td.graph.BaseGraph) -> dict[int, int]:\n    """Map each GT node to its weakly connected component ID."""\n    component_ids: dict[int, int] = {}\n    for seed in graph.node_ids():\n        if seed in component_ids:\n            continue\n        component_ids[seed] = seed\n        stack = [seed]\n        while stack:\n            current = stack.pop()\n            for neighbor in graph.successors(current) + graph.predecessors(current):\n                if neighbor not in component_ids:\n                    component_ids[neighbor] = seed\n                    stack.append(neighbor)\n    return component_ids\n\n\ndef _branch_component_evidence(\n    graph: td.graph.BaseGraph,\n    pred_div: int,\n    child: int,\n    pred_to_gt: dict[int, int],\n    gt_component: dict[int, int],\n) -> tuple[int | None, bool]:\n    """Return one GT component for a predicted child branch.\n\n    Direct-child evidence takes precedence over grandchildren so downstream\n    errors do not invalidate a correctly matched division. Grandchildren are\n    fallback evidence only when the child is unmatched. The boolean marks a\n    locally merged branch that cannot be assigned uniquely to this fork.\n    """\n    if set(graph.predecessors(child)) != {pred_div}:\n        return None, True\n    if child in pred_to_gt:\n        return gt_component[pred_to_gt[child]], False\n\n    grandchildren = graph.successors(child)\n    if any(set(graph.predecessors(node)) != {child} for node in grandchildren):\n        return None, True\n\n    components = {\n        gt_component[pred_to_gt[node]]\n        for node in grandchildren\n        if node in pred_to_gt\n    }\n    if len(components) == 1:\n        return next(iter(components)), False\n    return None, False\n\n\ndef _pred_division_fork_sets(\n    pred_graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None,\n    max_distance: float,\n) -> tuple[set[int], set[int], set[int]]:\n    """Return evaluable, cross-component, and malformed predicted forks.\n\n    Cross-component evidence must come from distinct direct-child branches.\n    A matched child identifies its branch; otherwise an unambiguous matched\n    grandchild may identify it. Merged local branches are malformed.\n    """\n    matched_pred = _match_full(pred_graph, gt_graph, scale, max_distance)\n    matched_attrs = _matched_node_attrs(matched_pred)\n    pred_to_gt = dict(\n        zip(\n            matched_attrs[td.DEFAULT_ATTR_KEYS.NODE_ID].to_list(),\n            matched_attrs[td.DEFAULT_ATTR_KEYS.MATCHED_NODE_ID].to_list(),\n            strict=True,\n        )\n    )\n\n    pred_forks = {\n        node_id for node_id in matched_pred.node_ids()\n        if matched_pred.out_degree(node_id) >= 2\n    }\n    evaluable_forks = {\n        pred_id for pred_id in pred_forks\n        if pred_id in pred_to_gt and gt_graph.out_degree(pred_to_gt[pred_id]) >= 1\n    }\n\n    gt_component = _gt_weak_component_ids(gt_graph)\n    cross_component_forks: set[int] = set()\n    malformed_forks: set[int] = set()\n    for pred_id in pred_forks:\n        branch_evidence: list[int] = []\n        for child in matched_pred.successors(pred_id):\n            component, malformed = _branch_component_evidence(\n                matched_pred, pred_id, child, pred_to_gt, gt_component\n            )\n            if malformed:\n                malformed_forks.add(pred_id)\n                break\n            if component is not None:\n                branch_evidence.append(component)\n        else:\n            if len(set(branch_evidence)) >= 2:\n                cross_component_forks.add(pred_id)\n\n    return evaluable_forks, cross_component_forks, malformed_forks\n\n\ndef count_matched_pred_divisions(\n    pred_graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None = None,\n    max_distance: float = 7.0,\n) -> int:\n    """Count predicted division nodes whose matched GT node is annotated.\n\n    Matches the full predicted graph against the full GT graph.  Among\n    predicted nodes that were matched to a GT node, counts how many are\n    dividing (out-degree >= 2) in the prediction *and* whose matched GT\n    node has at least one child.  A matched GT node with no children marks\n    the end of the annotation — we can\'t tell whether the cell actually\n    divided there, so such predicted divisions are excluded from the count\n    (and therefore from the FP tally).\n\n    Parameters\n    ----------\n    pred_graph : td.graph.BaseGraph\n        The predicted tracking graph.\n    gt_graph : td.graph.BaseGraph\n        The ground-truth tracking graph.\n    scale : tuple[float, ...] | None\n        Physical voxel scale used for centroid-distance matching.\n    max_distance : float\n        Maximum centroid distance for a match.\n\n    Returns\n    -------\n    int\n        Number of matched predicted division nodes.\n    """\n    evaluable_forks, _, _ = _pred_division_fork_sets(\n        pred_graph, gt_graph, scale, max_distance\n    )\n    return len(evaluable_forks)\n\n\ndef evaluate_divisions(\n    pred_graph: td.graph.BaseGraph,\n    gt_graph: td.graph.BaseGraph,\n    scale: tuple[float, ...] | None = None,\n    max_distance: float = 7.0,\n) -> DivisionCounts:\n    """Compute TP, FN, and FP counts for division events.\n\n    - **TP**: GT divisions correctly recovered in the prediction\n      (matched nodes connected and forking).\n    - **FN**: GT divisions not recovered.\n    - **FP**: Spurious predicted divisions, including forks matched to an\n      annotated GT node, local-topology rejects, bipartite leftovers, and\n      forks whose distinct child branches have nearest matched evidence in\n      distinct GT components, and forks with locally merged branches. Fork IDs\n      are unioned, so a fork supported by multiple rules counts once.\n\n    Parameters\n    ----------\n    pred_graph : td.graph.BaseGraph\n        The predicted tracking graph.\n    gt_graph : td.graph.BaseGraph\n        The ground-truth tracking graph.\n    scale : tuple[float, ...] | None\n        Physical voxel scale used for centroid-distance matching.\n    max_distance : float\n        Maximum centroid distance for a match.\n\n    Returns\n    -------\n    DivisionCounts\n        Named tuple with ``tp``, ``fn``, and ``fp`` fields.\n    """\n    result = score_divisions(\n        pred_graph,\n        gt_graph,\n        scale,\n        max_distance,\n    )\n    tp = sum(result.scores.values())\n    fn = len(result.scores) - tp\n    return DivisionCounts(tp=tp, fn=fn, fp=len(result.fp_forks))\n'
OFFICIAL_METRIC_COMMIT = "075fc5f5a52d11077f9dc2b074644618f26939e2"
EXPECTED_OFFICIAL_METRIC_SHA256 = {
    "metrics.py": "cfdd596e3f8909cca14db0682889738b19ff75c3808b3773175aba9367ca7444",
    "division_metrics.py": "0635c38621a38f1eb4b55a302b4a817a88e9094930dfc2dab16faeeee60f4dc9",
}
WORKING = Path("/kaggle/working")
INPUT = Path("/kaggle/input")
TRAIN_DIR = INPUT / "competitions" / "biohub-cell-tracking-during-development" / "train"
REPO_DIR = WORKING / "budgeted_oof_repo"
METHOD = "budgeted_embryo_oof_1ep_recovery"
EXPECTED_SUPPORT_MANIFEST_SHA256 = "7f01c0b2f9491606a1b543339e072230e25317d9c70fb9a18aea59e002a995eb"
EXPECTED_SOURCE_SHA256 = {
    "scripts/train_unet_transformer.py": "c4f6317736bb3bb1ec8f3f6e9a6d935a463e3f0f1f685481b2d13218d35dc9ea",
    "scripts/predict_unet_transformer.py": "c44e771ba5980b820f93091e03a303c25dfe8f3232e501f54dc9565731c234b9",
    "scripts/evaluate.py": "614813cc51c3581c6ccda4bb20725a19da8ecac4a27620654bfca58319cffa3c",
}
PACKAGE_NAMES = [
    "tracksdata", "zarr", "pyscipopt", "geff", "geff-spec", "ilpy",
    "polars", "polars-runtime-32", "blosc2", "dask", "imagecodecs",
    "pyarrow", "rustworkx", "sqlalchemy", "donfig", "google-crc32c",
    "numcodecs",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_names(names: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest()


def find_support_root() -> Path:
    matches = []
    for path in INPUT.rglob("ARTIFACT_MANIFEST.json"):
        if sha256(path) == EXPECTED_SUPPORT_MANIFEST_SHA256:
            matches.append(path.parent)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one pinned support artifact, found {matches}")
    return matches[0]


class Tee:
    def __init__(self, stream, path: Path):
        self.stream = stream
        self.handle = path.open("w", encoding="utf-8")

    def write(self, value: str):
        self.stream.write(value)
        self.handle.write(value)
        self.handle.flush()
        return len(value)

    def flush(self):
        self.stream.flush()
        self.handle.flush()

    def close(self):
        self.handle.close()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    import numpy as np
    import torch

    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True, warn_only=True)


def score_predictions(prediction_dir: Path, holdout: list[str]) -> tuple[list[dict], dict]:
    import tracksdata as td
    from geff import GeffMetadata
    from biohub_tracking.metrics import evaluate, node_recall, per_sample_metrics, summarise

    rows = []
    details = []
    for name in holdout:
        pred_result = td.graph.IndexedRXGraph.from_geff(prediction_dir / f"{name}.geff")
        gt_result = td.graph.IndexedRXGraph.from_geff(TRAIN_DIR / f"{name}.geff")
        pred = pred_result[0] if isinstance(pred_result, tuple) else pred_result
        gt = gt_result[0] if isinstance(gt_result, tuple) else gt_result
        counts = evaluate(
            pred, gt, scale=(1.625, 0.40625, 0.40625), max_distance=7.0
        )
        recall = node_recall(pred, gt) if pred.num_nodes() and pred.num_edges() else 0.0
        meta = GeffMetadata.read(TRAIN_DIR / f"{name}.geff")
        n_total = float((meta.extra or {}).get("estimated_number_of_nodes", float("nan")))
        row = per_sample_metrics(counts, n_total, recall)
        rows.append(row)
        details.append({"dataset": name, **row})
        print(
            f"OOF {name}: edge={counts.edge_tp}/{counts.edge_fp}/{counts.edge_fn} "
            f"division={counts.division_tp}/{counts.division_fp}/{counts.division_fn} "
            f"node_recall={recall:.6f}",
            flush=True,
        )
    return details, summarise(rows)


def main() -> None:
    started = time.time()
    if not TRAIN_DIR.is_dir():
        raise FileNotFoundError(TRAIN_DIR)
    support_root = find_support_root()
    print("Pinned support root:", support_root, flush=True)
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install", "--no-index",
            "--find-links", str(support_root / "wheels"), *PACKAGE_NAMES,
        ]
    )

    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    shutil.copytree(support_root / "repo", REPO_DIR)
    for relative, expected in EXPECTED_SOURCE_SHA256.items():
        actual = sha256(REPO_DIR / relative)
        if actual != expected:
            raise RuntimeError(f"Source checksum mismatch for {relative}: {actual}")
    metric_dir = REPO_DIR / "src" / "biohub_tracking"
    (metric_dir / "metrics.py").write_text(OFFICIAL_METRICS_SOURCE, encoding="utf-8")
    (metric_dir / "division_metrics.py").write_text(
        OFFICIAL_DIVISION_METRICS_SOURCE, encoding="utf-8"
    )
    for name, expected in EXPECTED_OFFICIAL_METRIC_SHA256.items():
        actual = sha256(metric_dir / name)
        if actual != expected:
            raise RuntimeError(f"Official metric checksum mismatch for {name}: {actual}")

    scripts_dir = REPO_DIR / "scripts"
    sys.path[:0] = [str(REPO_DIR / "src"), str(scripts_dir)]
    os.chdir(REPO_DIR)

    available = sorted(path.name.removesuffix(".zarr") for path in TRAIN_DIR.glob("*.zarr"))
    by_embryo = {
        embryo: sorted(name for name in available if name.startswith(f"{embryo}_"))
        for embryo in ("44b6", "6bba")
    }
    expected_all_hashes = {
        "44b6": "9a38aeec8ed9ac8433e480b854ef185b4886cb839a5dc1770e01cfc582113e42",
        "6bba": "bad2d65342f49bbf5adfc7005519430d029c78c65907fd6a2cb311da553698a5",
    }
    for embryo, expected in expected_all_hashes.items():
        actual = hash_names(by_embryo[embryo])
        if actual != expected:
            raise RuntimeError(f"Competition data inventory mismatch for {embryo}: {actual}")

    visible_test_copies = set(PROTOCOL["selection"]["visible_test_copies_excluded"])
    for fold in PROTOCOL["folds"]:
        train_set = set(fold["train"])
        monitor_set = set(fold["monitor"])
        holdout_set = set(fold["holdout"])
        if train_set & monitor_set or train_set & holdout_set or monitor_set & holdout_set:
            raise RuntimeError(f"Fold {fold['fold']} is not disjoint")
        if visible_test_copies & monitor_set or visible_test_copies & holdout_set:
            raise RuntimeError(f"Fold {fold['fold']} uses visible-test copies for evaluation")
        if not all(name.startswith(f"{fold['train_embryo']}_") for name in train_set | monitor_set):
            raise RuntimeError(f"Fold {fold['fold']} train/monitor embryo mismatch")
        if not all(name.startswith(f"{fold['validation_embryo']}_") for name in holdout_set):
            raise RuntimeError(f"Fold {fold['fold']} holdout embryo mismatch")

    training_splits = [
        {"split": fold["fold"], "train": fold["train"], "test": fold["monitor"]}
        for fold in PROTOCOL["folds"]
    ]
    inference_splits = [
        {"split": fold["fold"], "train": [], "test": fold["holdout"]}
        for fold in PROTOCOL["folds"]
    ]
    training_splits_path = REPO_DIR / "budgeted_oof_training_splits.json"
    inference_splits_path = REPO_DIR / "budgeted_oof_inference_splits.json"
    training_splits_path.write_text(json.dumps(training_splits, indent=2) + "\n")
    inference_splits_path.write_text(json.dumps(inference_splits, indent=2) + "\n")
    (WORKING / "budgeted_oof_protocol.json").write_text(
        json.dumps(PROTOCOL, indent=2) + "\n"
    )

    from train_unet_transformer import train
    from predict_unet_transformer import PredictConfig, predict

    fold_receipts = []
    all_detail_rows = []
    all_metric_rows = []
    for fold in PROTOCOL["folds"]:
        fold_index = int(fold["fold"])
        fold_started = time.time()
        seed_everything(int(fold["seed"]))
        train_log_path = WORKING / f"fold_{fold_index}_train.log"
        train_tee = Tee(sys.stdout, train_log_path)
        with contextlib.redirect_stdout(train_tee):
            model = train(
                data_dir=TRAIN_DIR,
                fold=fold_index,
                splits_file=training_splits_path,
                method=METHOD,
                n_epochs=int(PROTOCOL["training"]["epochs"]),
                lr=float(PROTOCOL["training"]["learning_rate"]),
                batch_size=int(PROTOCOL["training"]["batch_size"]),
                num_workers=4,
                unet_out_channels=32,
                unet_layers=[32, 64, 128],
                downsample=(1, 4, 4),
                det_loss_weight=1.0,
                det_neg_weight=0.01,
                seed=int(fold["seed"]),
                augmentations=[],
                window_size=2,
                pool_kernel_um=5.0,
                data_parallel=True,
            )
        train_tee.close()
        del model
        gc.collect()
        try:
            import torch
            torch.cuda.empty_cache()
        except Exception:
            pass

        weight_path = REPO_DIR / "weights" / METHOD / f"split_{fold_index}" / "edge_predictor_best.pth"
        if not weight_path.is_file():
            raise FileNotFoundError(weight_path)
        predict_log_path = WORKING / f"fold_{fold_index}_predict.log"
        predict_tee = Tee(sys.stdout, predict_log_path)
        predict_started = time.time()
        with contextlib.redirect_stdout(predict_tee):
            predict(
                data_dir=TRAIN_DIR,
                fold=fold_index,
                splits_file=inference_splits_path,
                weights_path=weight_path,
                cfg=PredictConfig(
                    det_threshold=0.965,
                    use_ilp=True,
                    ilp_edge_weight=-1.0,
                    ilp_appearance_weight=0.0,
                    ilp_disappearance_weight=2.0,
                    ilp_division_weight=1.0,
                ),
                method=METHOD,
                debug_video=None,
                unet_batch_size=4,
                video_slice=None,
                evaluate=False,
            )
        predict_tee.close()

        prediction_matches = sorted(
            REPO_DIR.glob(f"predictions/*/{METHOD}/split_{fold_index}")
        )
        if len(prediction_matches) != 1:
            raise RuntimeError(f"Expected one prediction directory, found {prediction_matches}")
        details, summary = score_predictions(prediction_matches[0], fold["holdout"])
        all_detail_rows.extend({"fold": fold_index, **row} for row in details)
        all_metric_rows.extend(details)
        train_text = train_log_path.read_text(encoding="utf-8")
        best_matches = re.findall(r"Best score \(acc\*recall\): ([0-9.]+)", train_text)
        fold_receipts.append(
            {
                "fold": fold_index,
                "seed": fold["seed"],
                "train_embryo": fold["train_embryo"],
                "holdout_embryo": fold["validation_embryo"],
                "train_datasets": len(fold["train"]),
                "monitor_datasets": len(fold["monitor"]),
                "holdout_datasets": len(fold["holdout"]),
                "monitor_best_acc_times_recall": float(best_matches[-1]) if best_matches else None,
                "holdout_summary": summary,
                "weights_sha256": sha256(weight_path),
                "train_log_sha256": sha256(train_log_path),
                "predict_log_sha256": sha256(predict_log_path),
                "prediction_seconds": time.time() - predict_started,
                "fold_seconds": time.time() - fold_started,
            }
        )
        partial = {
            "status": "running",
            "completed_folds": len(fold_receipts),
            "folds": fold_receipts,
            "per_sample": all_detail_rows,
        }
        (WORKING / "budgeted_oof_partial.json").write_text(
            json.dumps(partial, indent=2, allow_nan=True) + "\n"
        )

    from biohub_tracking.metrics import summarise
    combined_rows = [
        {key: value for key, value in row.items() if key not in {"dataset", "fold"}}
        for row in all_detail_rows
    ]
    receipt = {
        "status": "complete",
        "source_protocol_sha256": SOURCE_PROTOCOL_SHA256,
        "embedded_protocol_canonical_sha256": hashlib.sha256(
            json.dumps(PROTOCOL, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest(),
        "support_manifest_sha256": EXPECTED_SUPPORT_MANIFEST_SHA256,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "official_metric_commit": OFFICIAL_METRIC_COMMIT,
        "official_metric_sha256": EXPECTED_OFFICIAL_METRIC_SHA256,
        "ground_truth_scope": "official train only",
        "competition_test_accessed": False,
        "visible_test_copies_used_for_monitor_or_holdout": False,
        "folds": fold_receipts,
        "combined_holdout_summary": summarise(combined_rows),
        "per_sample": all_detail_rows,
        "total_seconds": time.time() - started,
    }
    receipt_path = WORKING / "budgeted_oof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=True) + "\n")
    print(json.dumps(receipt, indent=2, allow_nan=True), flush=True)


if __name__ == "__main__":
    main()
