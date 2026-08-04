from decimal import Decimal
from types import SimpleNamespace

import pytest

import scripts.run_okx_demo_smoke as smoke_script
from scripts.run_okx_demo_smoke import _demo_credentials, _resting_buy_price


def test_demo_smoke_price_is_tick_aligned_and_close_below_bid():
    bid = Decimal("100000.05")
    tick = Decimal("0.1")

    price = _resting_buy_price(bid, tick)

    assert price == Decimal("99900.0")
    assert price < bid
    assert price % tick == 0


def test_demo_credentials_ignore_live_names(tmp_path, monkeypatch):
    for name in (
        "OKX_DEMO_API_KEY",
        "OKX_DEMO_SECRET",
        "OKX_DEMO_PASSPHRASE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OKX_API_KEY", "live-key")
    monkeypatch.setenv("OKX_SECRET", "live-secret")
    monkeypatch.setenv("OKX_PASSPHRASE", "live-passphrase")
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OKX_API_KEY=file-live-key\nOKX_SECRET=file-live-secret\n"
        "OKX_PASSPHRASE=file-live-passphrase\n",
        encoding="utf-8",
    )

    assert _demo_credentials(env_file) == ("", "", "")


@pytest.mark.asyncio
async def test_demo_smoke_with_only_live_credentials_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        smoke_script,
        "load_config",
        lambda **_kwargs: SimpleNamespace(
            is_demo=lambda: True,
            system=SimpleNamespace(mode="demo"),
        ),
    )
    for name in (
        "OKX_DEMO_API_KEY",
        "OKX_DEMO_SECRET",
        "OKX_DEMO_PASSPHRASE",
    ):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OKX_API_KEY=live-key\nOKX_SECRET=live-secret\nOKX_PASSPHRASE=live-passphrase\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="blocked-pending-user-key.*OKX_DEMO_API_KEY"):
        await smoke_script.smoke("BTC-USDT", env_file=env_file)
