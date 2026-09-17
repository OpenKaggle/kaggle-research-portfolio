# Failure taxonomy

Assign one primary code per failed task output after the run is frozen. Add any
number of secondary tags. Apply the decision tree below; do not choose the label
that makes the system look best.

| Code | Primary failure | Operational test |
| --- | --- | --- |
| F00 | infrastructure | Run, dependency, model load, or receipt failed before valid candidates |
| F01 | timeout/budget starvation | Correct family was not run or stopped due to the fixed budget |
| F02 | invalid decode | Candidate grid is empty, ragged, out of bounds, bad color, or wrong schema |
| F03 | representation/object error | Oracle union fails; traces show the required segmentation, component, relation, or role assignment was absent |
| F04 | transformation/composition error | Oracle union fails; required objects were represented but the operation or composition depth was absent |
| F05 | output geometry error | Oracle union fails; content was plausible but dimensions, crop, tiling, alignment, or clipping was wrong |
| F06 | spurious demo fit | Oracle union fails; selected hypotheses fit demonstrations but a preregistered valid LOO/contract test exposes instability |
| F07 | no candidate coverage, unclassified | Oracle union fails and none of F03–F06 can be supported from frozen traces |
| F08 | gate false accept | The anchor pair was correct, an accepted override displaced its only correct output, and the selected pair failed |
| F09 | gate false reject | The anchor pair failed, a correct eligible override existed, and the gate abstained |
| F10 | correlated slot waste | The pool contains a correct candidate, but both selected attempts express the same residual failure |
| F11 | underdetermined hypothesis | The pool contains the correct candidate among multiple demonstration-consistent hypotheses with indistinguishable preregistered evidence |
| F12 | selector misranking | The pool contains a correct candidate but no more specific F08–F11 selector cause applies |
| F14 | ambiguous/data issue | Task ambiguity or suspected data error prevents a defensible assignment |

## Primary-code decision tree

1. Use F14 only when the task itself cannot be scored or interpreted
   defensibly; document the evidence.
2. Otherwise test F00, then F01, then F02.
3. If the portfolio oracle is wrong, use the first supported diagnostic among
   F03–F06; use F07 only when the cause is genuinely unclassifiable.
4. If the portfolio oracle is correct but the selected pair is wrong, test F08,
   F09, F10, and F11 in that order, then use F12.
5. A correctly retained but wrong anchor is an outcome, not a causal primary
   label. Record `anchor_retained` as a secondary tag alongside F03–F07.

## Secondary tags

- `size_same`, `size_crop`, `size_expand`, `multi_test`;
- `color_role`, `literal_color`, `palette_mapping`;
- `component`, `hole`, `line_ray`, `symmetry_d4`, `count`, `panel`, `gravity`,
  `occlusion`, `boundary_clip`, `recursive_relation`;
- `neural_only`, `trm_only`, `program_only`, `cross_family_agreement`;
- `loo_fail`, `contract_fail`, `ood_evidence`, `low_confidence`;
- `train_eval_coverage_collapse`, `retrospective_rule`, `support_abstention`;
- `beneficial_override`, `harmful_override`, `neutral_override`.
- `anchor_retained`, `gate_accept`, `gate_reject`, `gate_not_applicable`.

## Aggregate shift diagnostic

In addition to per-output failures, report selector coverage by data split and
solver family. A large coverage collapse is not coded as improved safety merely
because abstention avoids wrong direct selections. The current V175 pilot is
the reference example: 28.53% retrospective public-training coverage with
100% direct precision, but 0% coverage on the current public evaluation. This
must be labeled evidence-support shift, not successful generalization.

## Failure review rule

Public-evaluation failure labels are descriptive after the prospective run.
They cannot alter the headline method. A method change prompted by these labels
starts a new exploratory version and must be validated on a different locked
set or the final hidden Kaggle evaluation.

The machine-readable log must pass `tools/validate_failure_log.py`. Rows with
an oracle-correct/selected-wrong failure require a correct candidate ID; gate
false accepts/rejects must also match their anchor and gate-action fields.
