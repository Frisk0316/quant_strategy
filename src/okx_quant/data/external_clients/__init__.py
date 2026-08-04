"""HTTP adapters for external feature datasets."""

from okx_quant.data.external_clients.binance_oi import BinanceOIClient
from okx_quant.data.external_clients.cboe import CBOEClient
from okx_quant.data.external_clients.cftc_cot import CFTCCOTClient
from okx_quant.data.external_clients.coinmetrics_community import CoinMetricsCommunityClient
from okx_quant.data.external_clients.deribit_dvol import (
    DeribitDVOLClient,
    DeribitHistoricalVolatilityClient,
    DeribitRealizedVolatilityClient,
)
from okx_quant.data.external_clients.deribit_funding import DeribitFundingClient
from okx_quant.data.external_clients.deribit_option_flow import DeribitOptionFlowClient
from okx_quant.data.external_clients.deribit_option_surface import DeribitOptionSurfaceClient
from okx_quant.data.external_clients.fear_greed import FearGreedClient
from okx_quant.data.external_clients.fred import FREDClient
from okx_quant.data.external_clients.nasdaq_data_link import NasdaqDataLinkClient
from okx_quant.data.external_clients.okx_liquidation import OKXLiquidationClient
from okx_quant.data.external_clients.xvenue_options_iv import (
    CrossVenueOptionsIVClient,
)
from okx_quant.data.external_clients.yfinance_client import YFinanceClient
from okx_quant.data.external_clients.wikimedia_pageviews import WikimediaPageviewsClient

__all__ = [
    "BinanceOIClient",
    "CBOEClient",
    "CFTCCOTClient",
    "CoinMetricsCommunityClient",
    "CrossVenueOptionsIVClient",
    "DeribitDVOLClient",
    "DeribitHistoricalVolatilityClient",
    "DeribitRealizedVolatilityClient",
    "DeribitFundingClient",
    "DeribitOptionFlowClient",
    "DeribitOptionSurfaceClient",
    "FearGreedClient",
    "FREDClient",
    "NasdaqDataLinkClient",
    "OKXLiquidationClient",
    "YFinanceClient",
    "WikimediaPageviewsClient",
]
