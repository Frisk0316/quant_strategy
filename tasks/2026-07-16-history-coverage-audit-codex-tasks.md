---
status: current
type: task
owner: claude
created: 2026-07-16
last_reviewed: 2026-07-16
expires: 2026-10-16
superseded_by: null
---

# Codex Task B: Data-history coverage audit + backfill priority (unblock H-010)

Claude-authored plan (user-requested 2026-07-16). Codex implements; Claude
reviews. Motivation: the single highest-ROI lever against the low pass rate is
longer history (H-014 only passed after extending 2.5y -> ~6y). The blocked
backfills need human/local network runs (OKX 1m is stuck on `WinError 10013` +
rejected escalation), so Codex's deliverable is the read-only audit that ranks
where backfill pays off, plus prepped-and-verified commands for the human run.

Domain-rule caveat carried from the ledger: re-running a failed hypothesis on a
longer window is a RETRY. It consumes K and needs an ex-ante rationale written
before looking at results. Longer history is a legitimate, pre-registerable
variation but is NOT a free gate re-attempt. This task only surfaces the gap; it
does not authorize any re-run.

## Filled Implementation template

```text
Task: Build a data-history coverage audit that ranks backfill ROI, and prep+verify
the OKX BTC/ETH 1m backfill that unblocks H-010.

Strategy/spec source: docs/DATA_FLOW.md; scripts/market_data/ingest.py;
  backtesting/pipeline_stage2_registry.py frozen window START=2024-01-01;
  H-010 status in docs/HYPOTHESIS_LEDGER.md (OKX 1m still 0 rows / 0% as of E-035).

Required behavior:
- New scripts/audit_history_coverage.py: for every canonical_candles (inst_id,
  source_primary, bar) and external_observations dataset_id, report earliest ts,
  latest ts, row count, gap-vs-expected. Emit JSON + markdown ranked by
  history_gap_years (venue plausible-earliest minus what we hold). DB read only,
  no network. If no DSN, exit with a clean SKIP status, not a crash.
- Produce a prioritized backfill list (markdown) keyed to blocked families:
  P1 OKX BTC/ETH-USDT-SWAP 1m (unblocks H-010 / F-XVENUE-LEADLAG),
  P2 extend Binance/Deribit majors 1m + funding earlier than 2024,
  P3 external features (stablecoin supply, coinbase premium) for H-016/H-017.
- For OKX 1m: assemble the exact scripts/market_data/ingest.py command + a
  post-run coverage check reusing probe_xvenue. DO NOT run the network fetch
  (sandbox blocks it) - output the command for a human/local run plus a one-shot
  verify command asserting OKX coverage_ratio >= 0.95 and alignment >= 0.95.

PERMITTED FILES (only edit these):
- scripts/audit_history_coverage.py             (new)
- scripts/verify_okx_1m_backfill.py             (new: thin wrapper over probe_xvenue)
- tests/unit/test_audit_history_coverage.py     (new)
- docs/DATA_FLOW.md                             (add audit + backfill-priority section)
- docs/RUNBOOK.md                               (record OKX 1m ingest + verify commands)

FORBIDDEN (do not touch):
- src/okx_quant/** trading core, config/risk.yaml
- research/, existing results/** artifacts, docs/HYPOTHESIS_LEDGER.md, EXPERIMENT_REGISTRY.md
- Any live ingest run inside the sandbox (network blocked; command is output-only)
- No cross-venue substitution (I19 stands: missing OKX candles are not filled from Binance)

SCOPE LIMIT: read-only audit + command prep. No schema change, no data mutation.

REQUIRED ON COMPLETION:
- List changed files (git diff --stat).
- Run the new unit test and paste the output tail.
- Update DATA_FLOW.md and RUNBOOK.md per the AGENTS.md docs-update matrix.
- Do not commit unless committing was requested.

ACCEPTANCE CRITERIA (binary):
- [ ] audit script emits per-dataset earliest/latest/rows + ranked gap table.
- [ ] backfill-priority markdown lists P1-P3 with the family each unblocks.
- [ ] OKX 1m ingest command + verify command recorded in RUNBOOK, runnable by a human.
- [ ] verify script returns nonzero if OKX coverage/alignment < threshold.
- [ ] Audit runs with DSN present and SKIPs cleanly without one; unit test covers both.
- [ ] Diff contains only permitted files.

REPORT: changed files, test tail, current OKX 1m coverage number observed,
whether any venue's max-available-history had to be assumed (mark UNCONFIRMED).
```

## Reviewer notes (Claude)

- "venue plausible-earliest" is an assumption input, not a fact — Codex must mark
  it UNCONFIRMED and cite the source (venue listing date / data-vendor coverage),
  never fabricate a date.
- The OKX 1m run itself remains a human/local operation; this task ends when the
  command + verify are recorded, not when data lands.
- Fresh-verifier check per docs/ai/MODEL_DISPATCH.md.
