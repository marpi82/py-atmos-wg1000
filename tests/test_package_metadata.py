"""Package metadata smoke tests."""

from __future__ import annotations

from importlib.metadata import version

import pyatmos_wg1000


def test_public_version_matches_distribution_metadata() -> None:
    """Installed distribution name must drive ``pyatmos_wg1000.__version__``."""
    assert pyatmos_wg1000.__version__ == version("py-atmos-wg1000")
