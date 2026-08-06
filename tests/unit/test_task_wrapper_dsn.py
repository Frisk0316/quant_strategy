"""F78 guard: scheduled wrappers that write to the DB must source DATABASE_URL.

`config/settings.yaml` keeps `storage.timescale_dsn: null` and `load_config()` only
bridges a process-level `DATABASE_URL`, so a wrapper that skips `.env` runs, writes
nothing, and exits 1 with no alert. That cost 65 hours of forward-only H-039 data
between 2026-08-03 and 2026-08-06.

The worklog and public-status wrappers are deliberately absent from this list: they
are local-file-only by design and must not gain a DSN.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LOADER = "scripts\\_load_dotenv.cmd"

DB_WRITING_WRAPPERS = (
    "scripts/market_data/run_xvenue_options_snapshot_task.cmd",
    "scripts/market_data/run_liq_ingest_task.cmd",
    "scripts/run_h014_shadow_task.cmd",
)


@pytest.mark.parametrize("wrapper", DB_WRITING_WRAPPERS)
def test_db_writing_wrapper_loads_dotenv_before_running_python(wrapper: str) -> None:
    text = (REPO_ROOT / wrapper).read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]

    call_index = next(
        (i for i, line in enumerate(lines) if line.lower() == f"call {LOADER}".lower()),
        None,
    )
    assert call_index is not None, f"{wrapper} must call {LOADER}"

    # Loading after the interpreter has already started would not help it.
    python_index = next(
        (i for i, line in enumerate(lines) if "python.exe" in line.lower()),
        None,
    )
    assert python_index is not None, f"{wrapper} no longer invokes python"
    assert call_index < python_index, f"{wrapper} loads .env after starting python"


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe loader")
def test_loader_exports_the_dotenv_value_verbatim(tmp_path: Path) -> None:
    dsn = "postgresql://quant:p@ss=word@localhost:5432/quant"
    (tmp_path / ".env").write_text(
        f"OTHER=ignored\nDATABASE_URL={dsn}\nTRAILING=ignored\n", encoding="utf-8"
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "_load_dotenv.cmd").write_text(
        (REPO_ROOT / "scripts" / "_load_dotenv.cmd").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    probe = tmp_path / "probe.cmd"
    probe.write_text(
        "@echo off\r\n"
        f'cd /d "{tmp_path}"\r\n'
        f"call {LOADER}\r\n"
        'echo|set /p="%DATABASE_URL%"\r\n',
        encoding="ascii",
    )

    # No check=True: `echo|set /p` always exits 1, which says nothing about the loader.
    result = subprocess.run(["cmd", "/c", str(probe)], capture_output=True, text=True)
    assert result.stdout == dsn


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe loader")
def test_loader_is_quiet_when_dotenv_is_absent(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "_load_dotenv.cmd").write_text(
        (REPO_ROOT / "scripts" / "_load_dotenv.cmd").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    probe = tmp_path / "probe.cmd"
    probe.write_text(
        "@echo off\r\n" f'cd /d "{tmp_path}"\r\n' f"call {LOADER}\r\n" "exit /b %ERRORLEVEL%\r\n",
        encoding="ascii",
    )

    result = subprocess.run(["cmd", "/c", str(probe)], capture_output=True, text=True)
    assert result.returncode == 0
