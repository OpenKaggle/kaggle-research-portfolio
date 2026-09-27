# Data boundary

This portfolio preserves source code, documentation, and research evidence.
It does not redistribute organizer-provided competition data, literal
episode/replay payloads, record-level splits, predictions, checkpoints, or
third-party notebook copies without a clear permission.

For Kaggriculture, keep downloaded replay payloads, agent-log streams,
third-party action tapes, and other literal platform files in an ignored local
working directory. Publish the agent source, evaluation procedure, detailed
first-party derived evidence, and a hash manifest instead.  The tracked
`kaggriculture/remote/summary_latest.json` is an example: it records
episode-level outcomes, public-environment context, and aggregated diagnostics
for our seats, but contains neither replay state/actions nor the downloaded
stdout/stderr stream.  Its scope and checks are documented in
[`kaggriculture/PUBLIC_EVIDENCE.md`](kaggriculture/PUBLIC_EVIDENCE.md).

For BioHub, obtain data through the official competition route and keep
train/test membership and prediction metadata outside the public tree.

Before any new research receipt is committed, determine its provenance rather
than treating every derived artifact as prohibited.  A reviewed first-party
aggregate or validation record may remain detailed enough to audit a claim.
Do remove original records and payloads, literal raw traces, local paths,
credentials, and third-party exports unless the applicable source explicitly
permits redistribution and the required attribution is retained. If bytes
cannot be redistributed, document their official source, expected layout,
version, and checksum rather than copying them here.
