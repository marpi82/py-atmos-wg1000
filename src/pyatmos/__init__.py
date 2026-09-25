"""ATMOS WG1000 local WebSocket client."""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version

from pyatmos.client import AtmosClient
from pyatmos.feed import AtmosFeed, ValueStore
from pyatmos.i18n import LanguageCatalog

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

try:
    __version__ = version("py-atmos")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["AtmosClient", "AtmosFeed", "LanguageCatalog", "ValueStore", "__version__"]
