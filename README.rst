py-atmos-wg1000
===============

Async Python library for the local WebSocket API of an **ATMOS WG1000** gateway.
It is the data layer for a future Home Assistant integration: a heavy catalog at
configuration time, and a light value feed at runtime.

**PyPI name:** ``py-atmos-wg1000`` (PyPI rejected ``py-atmos`` / ``pyatmos`` as too similar to the existing ``pyatmos`` project).
Import as ``import pyatmos_wg1000``.

**Status:** early. The frame codec, language tables, and register poller are in
place. Writes to the boiler are encoded but have not been sent to a live gateway.

Install
-------

.. code-block:: bash

   pip install py-atmos-wg1000

Two paths
---------

Configuration (heavy)
   Download ``Lang.json`` and ``texty_brana.json``, pick a language by column
   code (``POL``) or by the gateway index in ``USER1_LANG``, and resolve labels.
   This is ``pyatmos_wg1000.i18n.LanguageCatalog``. Drop it after the entities exist.

Runtime (light)
   Keep one WebSocket, log in, and poll a fixed set of register ids.
   ``pyatmos_wg1000.feed.AtmosFeed`` stores raw words and publishes
   ``pyatmos_wg1000.feed.RegisterUpdate`` only when a word changes. It does not
   load the language files.

The gateway does not push temperatures. The socket stays open and the feed asks
again on an interval. The panel uses 30 seconds for circuit temperatures.

Credentials
-----------

Copy ``.env.example`` to ``.env``. The real file is gitignored.

.. code-block:: text

   PYATMOS_URL=https://192.168.0.10
   PYATMOS_USER=user
   PYATMOS_PASSWORD=secret

Development
-----------

Python 3.13. Version comes from git tags (``hatch-vcs``), with fallback ``0.0.0``
until the first tag. See ``CONTRIBUTING.md``, ``AGENTS.md``, and ``SECURITY.md``.

.. code-block:: bash

   uv sync --group dev --group test --locked
   uv run pre-commit install --hook-type pre-commit --hook-type pre-push
   uv run --group dev --group test poe validate
