"""HTTP adapters for external feature datasets."""

from okx_quant.data.external_clients.binance_oi import BinanceOIClient
from okx_quant.data.external_clients.deribit_dvol import DeribitDVOLClient
from okx_quant.data.external_clients.fear_greed import FearGreedClient
from okx_quant.data.external_clients.fred import FREDClient
from okx_quant.data.external_clients.nasdaq_data_link import NasdaqDataLinkClient
from okx_quant.data.external_clients.okx_liquidation import OKXLiquidationClient
from okx_quant.data.external_clients.yfinance_client import YFinanceClient

__all__ = [
    "BinanceOIClient",
    "DeribitDVOLClient",
    "FearGreedClient",
    "FREDClient",
    "NasdaqDataLinkClient",
    "OKXLiquidationClient",
    "YFinanceClient",
]
