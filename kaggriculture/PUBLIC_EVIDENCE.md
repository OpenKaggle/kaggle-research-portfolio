# Kaggriculture public evidence boundary

The Kaggriculture workbench keeps the evidence that lets readers inspect the
research without turning this repository into a mirror of competition files or
other participants' work.

## Included evidence

[`remote/summary_latest.json`](remote/summary_latest.json) is a first-party
research receipt produced from our read-only monitoring run.  It retains the
granularity needed to audit the recorded results:

- episode identifiers, timing, status, outcome, rewards, and margin;
- which seat belonged to the monitored submission;
- public game context used by the analysis; and
- per-episode diagnostic aggregates for our agent's log stream, including its
  digest, record count, duration summary, and stdout/stderr counts.

It is an evidence manifest, not a replay archive: at this snapshot it indexes
two monitored submissions and 830 completed or validation episodes.  The
Kaggriculture rules state that episode replays may be publicly available, but
this repository does not rely on that fact to redistribute replay bytes.

## Not included

- downloaded replay JSON, full state/action trajectories, or agent-log
  stdout/stderr records;
- organizer-provided downloads and any hidden or private competition input;
- third-party Kaggle notebooks, their copied metadata, or their extracted
  action tapes; and
- credentials, generated submission archives, environments, and local caches.

The former `remote/logs/episode-*-logs.json` files were literal platform log
downloads (719 records per file), so their metadata has been retained only in
the evidence manifest.  The removed `agents/*/actions.json` and
`agents/last_mile_harvest/tapes.json` fixtures came from third-party Kaggle
notebook lineages; even where upstream code is openly licensed, this archive
links to those sources rather than mirroring their notebooks or extracted
assets.

## Release check

Before publishing a new evidence update, verify that every added artifact is
either original OpenKaggle source or a reviewed first-party derivative.  Check
that it contains no original input rows or binary payloads, raw replay/log
stream, local file path, credential, or unreviewed third-party export.  Record
the acquisition route and a content digest when the derivative is based on an
official endpoint.
