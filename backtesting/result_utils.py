"""Helpers for normalizing strategy outputs inside validators and reports."""
from __future__ import annotations

from typing import Any

import pandas as pd


def extract_returns(result: Any) -> pd.Series | Any:
    """
    Normalize strategy outputs to a return series when possible.

    Supported inputs:
    - pd.Series / array-like values
    - dicts containing a ``returns`` key
    - objects exposing a ``returns`` attribute
    """
    if isinstance(result, pd.Series):
        return result

    if isinstance(result, dict) and "returns" in result:
        return result["returns"]

    if hasattr(result, "returns"):
        return getattr(result, "returns")

    return result
