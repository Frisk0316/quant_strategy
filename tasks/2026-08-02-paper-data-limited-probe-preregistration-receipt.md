---
status: current
type: task
owner: codex
created: 2026-08-02
last_reviewed: 2026-08-02
expires: none
superseded_by: null
---

# Paper-data limited-probe pre-registration receipt — 2026-08-02

Recorded after synthetic/unit verification and before any H-040 through H-046
candidate database read, Stage 2 evaluation, or Stage 3 execution. The run is
an incomplete limited probe (`complete_round: false`) and cannot authorize
promotion, shadow, demo, or live trading.

| path | hash |
| --- | --- |
| `docs/superpowers/specs/2026-08-02-paper-data-limited-probe.md` | `cb6b2bda772a6093d2ec7f20ef487e67ab79dfc768b4ea14e6b0f640abcd8b17` |
| `docs/HYPOTHESIS_LEDGER.md` | `1b6c1551dc65bf4a1fc33ab33afe31565df2b166be77bcb2266140e3658c2405` |
| `docs/EXPERIMENT_REGISTRY.md` | `8bbfc610d20991a27f003eec65cb37b6f3e49155cd43a1f07f0caf559f30b965` |
| `backtesting/paper_signal_probe.py` | `4f6e5bda9a61b182ab91ff19ab215444d5fdf1bd47ccec600c4e185c3d4181c9` |
| `scripts/run_paper_signal_limited_probe.py` | `9456a5c3535dcfdd9a0fe9ff14a53fe93f75f90481f56b57ccb703c014f23b61` |

Pre-seal checks:

- Targeted unit tests: 23 passed.
- Ruff: passed.
- No candidate result directory existed or was read.
- Tests used synthetic fixtures only; they did not query candidate data from
  the project database.

