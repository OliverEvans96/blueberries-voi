"""Browser / slim interactive entry (ADR 0099 / T-044).

Import graph for Pyodide and ``[browser]`` installs: derived Abdella arrays only.
Does not import pyarrow or matplotlib.
"""

from __future__ import annotations

from blueberries_voi.model.abdella_product import (
    DEFAULT_DERIVED_ABDELLA_PATH,
    PRODUCT_KEYS,
    ArrivalAgeProduct,
    arrival_ages_from_array,
    load_derived_abdella_arrival_ages,
)

BROWSER_ENTRY: bool = True

__all__ = [
    "BROWSER_ENTRY",
    "DEFAULT_DERIVED_ABDELLA_PATH",
    "PRODUCT_KEYS",
    "ArrivalAgeProduct",
    "arrival_ages_from_array",
    "load_derived_abdella_arrival_ages",
]
