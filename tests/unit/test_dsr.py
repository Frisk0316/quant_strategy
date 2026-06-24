import numpy as np

from okx_quant.analytics.dsr import deflated_sharpe, psr


def test_deflated_sharpe_uses_return_series_units():
    returns = np.tile([0.01005, -0.00995], 2_500)
    sample_sr = returns.mean() / returns.std(ddof=1)
    annualized_sr = sample_sr * np.sqrt(365 * 24)

    dsr = deflated_sharpe(
        returns,
        sr=annualized_sr,
        sr_list=[annualized_sr - 0.1, annualized_sr, annualized_sr + 0.1],
        N=20,
    )

    assert dsr < psr(returns)
    assert dsr < 0.99
