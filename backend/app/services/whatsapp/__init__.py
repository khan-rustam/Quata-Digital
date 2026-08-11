"""QCP — the Quata Communications Platform.

    QuataPay · QuataFood · Abaqwa · QuataTrade · (and the next one)
                              │
                              ▼
                     QCP  ── this package ──►  Meta Graph API
                              │
                    ┌─────────┴─────────┐
              Quata Verify            QUATA
          (authentication only)   (everything else)

Products call QCP. **Only QCP talks to Meta.** The two business accounts are
kept apart by the storage engine rather than by convention: see
``models/whatsapp.py`` for the composite foreign keys and ``routing.py`` for
the choke point that mints the only thing ``meta.py`` will send.

The public facade — the only names another package should import — is
``send()``, ``get_message()``, ``sweep_pending()`` and
``stats()``. They are resolved lazily below so that importing, say,
``webhooks`` never drags the whole delivery path (and its Meta client) into
a process that only ingests.
"""
from __future__ import annotations

from typing import Any


# facade name → (submodule, attribute)
_FACADE = {
    "send": ("dispatch", "send"),
    "get_message": ("dispatch", "get_message"),
    "sweep_pending": ("dispatch", "sweep_pending"),
    "stats": ("dispatch", "stats"),
    # No ``sync_registry`` entry. It named ``registry.sync_registry``, which
    # never existed: ``registry.py`` is the routing-rule write surface, and
    # products are upserted by ``app/seeds/whatsapp_seed.py`` and registered
    # through ``POST /admin/qcp/products``. A facade name that resolves to an
    # AttributeError is worse than no name at all.
}

__all__ = list(_FACADE)


def __getattr__(name: str) -> Any:
    target = _FACADE.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    from importlib import import_module

    return getattr(import_module(f"{__name__}.{module_name}"), attribute)
