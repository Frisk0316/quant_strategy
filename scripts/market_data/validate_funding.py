"""Validate funding-rate coverage in TimescaleDB."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from okx_quant.core.config import load_config
from okx_quant.data.candle_store import CandleStore


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


async def validate_funding(
    *,
    dsn: str,
    instruments: tuple[str, ...],
    start: datetime | None,
    end: datetime | None,
    max_gap_hours: float | None,
    fail_on_gap: bool,
) -> None:
    store = await CandleStore.from_dsn(dsn)
    try:
        total_gaps = 0

        for inst_id in instruments:
            summary = await store.summarize_funding_rates(inst_id, start=start, end=end)
            intervals = await store.funding_interval_distribution(inst_id, start=start, end=end)
            if max_gap_hours is None:
                gaps = []
            else:
                gaps = await store.detect_funding_gaps(
                    inst_id,
                    start=start,
                    end=end,
                    expected_interval=timedelta(hours=max_gap_hours),
                )
            total_gaps += len(gaps)

            rows = int(summary.get("rows") or 0)
            first_ts = summary.get("first_ts")
            last_ts = summary.get("last_ts")
            max_apr = summary.get("max_apr")
            apr_gt_5 = int(summary.get("apr_gt_5pct") or 0)
            apr_gt_12 = int(summary.get("apr_gt_12pct") or 0)

            click.echo(f"{inst_id}")
            click.echo(f"  rows       : {rows}")
            click.echo(f"  first_ts   : {first_ts}")
            click.echo(f"  last_ts    : {last_ts}")
            click.echo(f"  max_apr    : {float(max_apr):.4%}" if max_apr is not None else "  max_apr    : n/a")
            click.echo(f"  APR > 5%   : {apr_gt_5}")
            click.echo(f"  APR > 12%  : {apr_gt_12}")
            click.echo("  intervals  :")
            if intervals:
                for item in intervals:
                    click.echo(
                        f"    {float(item['funding_interval_hours']):.4g}h: {int(item['rows'])}"
                    )
            else:
                click.echo("    n/a")
            if max_gap_hours is None:
                click.echo("  gaps       : skipped (--max-gap-hours not set)")
            else:
                click.echo(f"  gaps > {max_gap_hours:g}h: {len(gaps)}")
            for gap in gaps[:10]:
                click.echo(
                    f"    {gap['gap_start']} -> {gap['gap_end']} "
                    f"({gap['gap']})"
                )
            if len(gaps) > 10:
                click.echo(f"    ... {len(gaps) - 10} more")

        if total_gaps:
            click.echo(f"\nFunding validation finished with {total_gaps} gap(s).")
            if fail_on_gap:
                raise SystemExit(1)
        else:
            click.echo("\nFunding validation passed.")
    finally:
        await store.close()


@click.command()
@click.option("--inst", multiple=True, help="Instrument to validate. Defaults to SWAP symbols in config.")
@click.option("--start", default=None, help="Start date YYYY-MM-DD")
@click.option("--end", default=None, help="End date YYYY-MM-DD (exclusive)")
@click.option("--max-gap-hours", default=None, type=float,
              help="Optional max allowed adjacent funding timestamp gap. Not set = report intervals only.")
@click.option("--fail-on-gap/--no-fail-on-gap", default=True, show_default=True)
@click.option("--config", default="config/settings.yaml", show_default=True)
def cli(
    inst: tuple[str, ...],
    start: str | None,
    end: str | None,
    max_gap_hours: float | None,
    fail_on_gap: bool,
    config: str,
) -> None:
    """Check funding_rates timestamp coverage."""
    cfg = load_config(settings_path=config, require_secrets=False)
    dsn = cfg.storage.timescale_dsn
    if not dsn:
        click.echo("ERROR: storage.timescale_dsn not set", err=True)
        sys.exit(1)

    instruments = inst or tuple(s for s in cfg.system.symbols if s.endswith("-SWAP"))
    if not instruments:
        click.echo("ERROR: no SWAP instruments to validate", err=True)
        sys.exit(1)

    asyncio.run(validate_funding(
        dsn=dsn,
        instruments=instruments,
        start=_parse_dt(start),
        end=_parse_dt(end),
        max_gap_hours=max_gap_hours,
        fail_on_gap=fail_on_gap,
    ))


if __name__ == "__main__":
    cli()
