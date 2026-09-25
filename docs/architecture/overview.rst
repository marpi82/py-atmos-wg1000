Architecture
============

The gateway web UI does two different jobs on one binary WebSocket
(``wss://<host>/api/wss``). This library keeps those jobs apart.

Configuration
-------------

Before login the gateway will send ``Lang.json`` and ``texty_brana.json``.
Both files are tables: column 0 is the row id, and every later column is a
language (``CES``, ``ENG``, ``POL``, and the rest of the header).

``USER1_LANG`` is a zero-based index into those language columns. The UI adds
one before it indexes the row, because column 0 is not a language. Index ``8``
is therefore column 9. On the table shipped with the gateway that column is
``POL``.

:class:`pyatmos_wg1000.i18n.LanguageCatalog` is the only object that holds those
tables. Build entity names from it, then discard it.

Runtime
-------

:class:`pyatmos_wg1000.feed.AtmosFeed` is the acquisition loop:

1. The caller logs in with :meth:`pyatmos_wg1000.client.AtmosClient.login`.
2. The feed reads a fixed list of register ids.
3. :class:`pyatmos_wg1000.feed.ValueStore` keeps the raw 32-bit word.
4. :class:`pyatmos_wg1000.feed.EventBus` yields a :class:`pyatmos_wg1000.feed.RegisterUpdate`
   when that word changes.

There is no subscription message. A quiet register produces no event after the
first sample. Temperature scaling stays in
:func:`pyatmos_wg1000.protocol.params.decode_acd_temperature` and is applied by the
integration, not stored a second time.

.. code-block:: python

   feed = AtmosFeed(client, [hod16_id(Hod16.AF), hod16_id(Hod16.O1_TEPLOTA)])
   task = feed.start()
   async for update in feed.bus.subscribe():
       print(update.register_id, update.value)
