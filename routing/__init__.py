"""AgentSystem — Multi-model routing package (PR3).

Public surface:

* :class:`ModelProfile`, :class:`ModelCatalog`, :func:`build_catalog`,
  :func:`load_catalog`, :class:`ModelCatalogError` — declarative model catalog.
* :class:`ModelRouter`, :class:`ResolvedModel`, :func:`get_router`,
  :func:`reset_router_for_tests` — credential-aware client routing.

The catalog layer is pure data (no network, no secrets). The router layer is the
only place that touches credentials, and it reads them live from
``config.ModelConfig`` so cached routers still reflect environment changes.
"""

from routing.profiles import (
    BUILDABLE_PROVIDERS,
    KNOWN_PROVIDERS,
    ModelCatalog,
    ModelCatalogError,
    ModelProfile,
    build_catalog,
    load_catalog,
)
from routing.router import (
    ModelRouter,
    ResolvedModel,
    get_router,
    reset_router_for_tests,
)

__all__ = [
    "BUILDABLE_PROVIDERS",
    "KNOWN_PROVIDERS",
    "ModelCatalog",
    "ModelCatalogError",
    "ModelProfile",
    "build_catalog",
    "load_catalog",
    "ModelRouter",
    "ResolvedModel",
    "get_router",
    "reset_router_for_tests",
]
