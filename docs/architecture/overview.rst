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

Two acquisition loops cover the live paths Home Assistant needs:

* :class:`pyatmos_wg1000.feed.AtmosFeed` polls a fixed list of HOD16 register
  ids and publishes :class:`pyatmos_wg1000.feed.RegisterUpdate` when a raw word
  changes.
* :class:`pyatmos_wg1000.feed.InfoFeed` polls the Info page dump
  (:meth:`pyatmos_wg1000.client.AtmosClient.fetch_info`) and publishes
  :class:`pyatmos_wg1000.feed.InfoUpdate` when the assembled rows change.
  Captions and ``0xFF`` value escapes are resolved with
  :class:`pyatmos_wg1000.i18n.LanguageCatalog` and OwnText outside the feed.

There is no subscription message. A quiet register or an unchanged Info dump
produces no event after the first sample. Temperature scaling stays in
:func:`pyatmos_wg1000.protocol.params.decode_acd_temperature` and is applied by the
integration, not stored a second time.

.. code-block:: python

   from pyatmos_wg1000 import AtmosClient, InfoFeed

   async with AtmosClient("192.168.1.10", verify_tls=False) as client:
       await client.hello()
       await client.login("user", "secret")
       feed = InfoFeed(client)
       async for update in feed.bus.subscribe():
           print(len(update.dump.items))
