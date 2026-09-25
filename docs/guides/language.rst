Language catalog
================

Download the tables once, while setting the integration up.

.. code-block:: python

   catalog = await LanguageCatalog.fetch(client)
   print(catalog.language.code)
   for language in catalog.languages():
       print(language.gateway_index, language.code, language.name)

``fetch`` without a ``language`` argument sends Hello, reads ``USER1_LANG``,
and selects that column. The gateway answers parameter reads only after
Hello. Pass ``"ENG"`` or ``2`` to override the gateway index. ``2`` means
the third language column.

Lookups
-------

UI strings use the id from ``Lang.json``:

.. code-block:: python

   catalog.text("TXT2_LOGIN_BTN")

Regulator strings use the ``T16_`` prefix and the numeric row from
``texty_brana.json``:

.. code-block:: python

   catalog.text("T16_90")

An empty cell falls back to the ``ENG`` column. An unknown key returns
``None``. The panel would show an error token instead; the library does not.
